"""AI-facing helper functions for the Worth project."""

from __future__ import annotations

import argparse
import configparser
import os
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

import psycopg2


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


def _credentials_path() -> Path:
    primary = Path("~/.worth").expanduser()
    if primary.exists():
        return primary

    fallback = Path("/root/dotfiles/secrets/worth/.worth")
    if fallback.exists():
        return fallback

    raise FileNotFoundError("Worth credentials not found at ~/.worth or the Codex fallback")


def _connection():
    config = configparser.ConfigParser()
    config.read(_credentials_path())
    if "POSTGRES" not in config:
        raise RuntimeError("Worth credentials have no [POSTGRES] section")

    postgres = config["POSTGRES"]
    return psycopg2.connect(
        host=os.environ.get("PGHOST", "host.docker.internal"),
        port=os.environ.get("PGPORT", "5432"),
        user=postgres["USER"],
        password=postgres["PASS"],
        dbname=postgres["DB"],
    )


def _money(value: Decimal) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.2f}"


def _percent(value: Decimal | None) -> str:
    return "N/A" if value is None else f"{value:,.2f}%"


def analyze(ticker: str) -> str:
    """Return a Markdown performance report for a ticker.

    The report uses the newest stored close and includes active and closed
    accounts. Database work is performed in a read-only transaction.
    """
    ticker = ticker.strip().upper()
    if not ticker:
        raise ValueError("A ticker is required")

    with _connection() as connection:
        connection.set_session(readonly=True)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT t.id, m.symbol
                FROM markets_ticker AS t
                JOIN markets_market AS m ON m.id = t.market_id
                WHERE UPPER(t.ticker) = %s
                ORDER BY m.symbol, t.id
                """,
                (ticker,),
            )
            matches = cursor.fetchall()
            if not matches:
                raise LookupError(f"Ticker {ticker} is absent from the database")
            if len(matches) > 1:
                markets = ", ".join(str(row[1]) for row in matches)
                raise LookupError(f"Ticker {ticker} is ambiguous across markets: {markets}")

            ticker_id = matches[0][0]
            cursor.execute(
                """
                SELECT d, c
                FROM markets_dailyprice
                WHERE ticker_id = %s
                ORDER BY d DESC
                LIMIT 1
                """,
                (ticker_id,),
            )
            price_row: tuple[date, Decimal] | None = cursor.fetchone()
            if price_row is None:
                raise LookupError(f"Ticker {ticker} has no stored closing price")
            price_date, latest_price = price_row

            cursor.execute(
                """
                SELECT
                    a.name,
                    a.active_f,
                    m.cs * (
                        SUM(-tr.q * tr.p) + SUM(tr.q) * %s
                    ) - SUM(tr.commission) AS pnl,
                    SUM(
                        CASE WHEN tr.q > 0
                        THEN tr.q * tr.p + tr.commission
                        ELSE 0
                        END
                    ) AS purchase_cost
                FROM trades_trade AS tr
                JOIN accounts_account AS a ON a.id = tr.account_id
                JOIN markets_ticker AS t ON t.id = tr.ticker_id
                JOIN markets_market AS m ON m.id = t.market_id
                WHERE tr.ticker_id = %s
                GROUP BY a.id, a.name, a.active_f, m.cs
                ORDER BY a.name
                """,
                (latest_price, ticker_id),
            )
            rows = cursor.fetchall()

    if not rows:
        raise LookupError(f"Ticker {ticker} has no trades")

    accounts = [
        AccountPerformance(
            account=row[0],
            active=row[1],
            pnl=Decimal(row[2]),
            purchase_cost=Decimal(row[3]),
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
