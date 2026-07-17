"""AI-facing helper functions for the Worth project."""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import django
from django.db.models import Case, DecimalField, ExpressionWrapper, F, Sum, Value, When

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@dataclass(frozen=True)
class AccountPerformance:
    account: str
    active: bool
    pnl: Decimal
    purchase_cost: Decimal

    @property
    def roi(self) -> Decimal | None:
        if not self.purchase_cost:
            return None
        return Decimal("100") * self.pnl / self.purchase_cost


def _setup_django() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "worth.settings")
    django.setup()


def _money(value: Decimal) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.2f}"


def _percent(value: Decimal | None) -> str:
    return "N/A" if value is None else f"{value:,.2f}%"


def analyze(ticker: str) -> str:
    """Return a Markdown performance report for a ticker.

    The report uses the newest stored close and includes active and closed
    accounts. Database work is performed through the Django ORM.
    """
    ticker = ticker.strip().upper()
    if not ticker:
        raise ValueError("A ticker is required")

    _setup_django()

    from markets.models import DailyPrice, Ticker
    from trades.models import Trade

    matches = list(
        Ticker.objects.filter(ticker__iexact=ticker)
        .select_related("market")
        .order_by("market__symbol")
    )
    if not matches:
        raise LookupError(f"Ticker {ticker} is absent from the database")
    if len(matches) > 1:
        markets = ", ".join(match.market.symbol for match in matches)
        raise LookupError(f"Ticker {ticker} is ambiguous across markets: {markets}")

    ticker_record = matches[0]
    price_record = DailyPrice.objects.filter(ticker=ticker_record).order_by("-d").first()
    if price_record is None:
        raise LookupError(f"Ticker {ticker} has no stored closing price")

    latest_price = Decimal(str(price_record.c))
    price_date = price_record.d
    decimal_field = DecimalField(max_digits=40, decimal_places=10)
    trade_value = ExpressionWrapper(F("q") * F("p"), output_field=decimal_field)
    rows = list(
        Trade.objects.filter(ticker=ticker_record)
        .values("account__name", "account__active_f")
        .annotate(
            traded_value=Sum(trade_value),
            quantity=Sum("q"),
            commissions=Sum("commission"),
            purchase_cost=Sum(
                Case(
                    When(q__gt=0, then=trade_value + F("commission")),
                    default=Value(Decimal("0")),
                    output_field=decimal_field,
                )
            ),
        )
        .order_by("account__name")
    )

    if not rows:
        raise LookupError(f"Ticker {ticker} has no trades")

    contract_multiplier = Decimal(str(ticker_record.market.cs))
    accounts = [
        AccountPerformance(
            account=row["account__name"],
            active=row["account__active_f"],
            pnl=contract_multiplier * (-row["traded_value"] + row["quantity"] * latest_price)
            - row["commissions"],
            purchase_cost=row["purchase_cost"],
        )
        for row in rows
    ]
    total_pnl = sum((account.pnl for account in accounts), Decimal("0"))
    total_cost = sum((account.purchase_cost for account in accounts), Decimal("0"))
    total_roi = Decimal("100") * total_pnl / total_cost if total_cost else None

    lines = [
        f"{ticker}'s latest stored close is **{_money(latest_price)}**, dated "
        f"**{price_date.isoformat()}**.",
        "",
        "| Account | Status | PnL | Cumulative ROI |",
        "|---|---|---:|---:|",
    ]
    lines.extend(
        f"| {account.account} | {'Active' if account.active else 'Closed'} | "
        f"{_money(account.pnl)} | {_percent(account.roi)} |"
        for account in accounts
    )
    lines.extend(
        [
            f"| **All accounts** |  | **{_money(total_pnl)}** | " f"**{_percent(total_roi)}** |",
            "",
            "ROI is cumulative—not annualized, time-weighted, or XIRR. "
            "Purchase cost includes buy commissions.",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze a Worth ticker")
    parser.add_argument("ticker", help="ticker symbol, for example AAPL")
    args = parser.parse_args()
    print(analyze(args.ticker))


if __name__ == "__main__":
    main()
