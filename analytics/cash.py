from decimal import Decimal

from django.db.models import DecimalField, ExpressionWrapper, F, OuterRef, Subquery, Sum
from django.utils import timezone

from accounts.models import Account, CashRecord
from markets.models import DailyPrice, NOT_FUTURES_EXCHANGES, Ticker
from trades.models import Trade
from trades.utils import pnl_asof


def cash_sums(account_id, d):
    account_name = Account.objects.get(id=account_id)

    _, total = pnl_asof(d, a=account_name, cleared=False)
    _, total_cleared = pnl_asof(d, a=account_name, cleared=True)

    total = total.q.sum()
    total_cleared = total_cleared.q.sum()

    return total, total_cleared


def current_cash_report(account=None):
    """Return uninvested cash and CASH-market holdings across all accounts.

    Reinvestments affect positions but do not withdraw uninvested cash.
    Futures contribute marked-to-market PnL, following pnl_asof's convention.
    Missing prices leave affected account totals unavailable.
    """
    now = timezone.now()
    today = timezone.localdate(now)
    zero = Decimal("0")

    def decimal(value):
        return Decimal(str(value))

    def money(value):
        if value is None:
            return "Unavailable"
        return f"{'-' if value < 0 else ''}${abs(value):,.2f}"

    accounts = Account.objects.order_by("name")
    if account:
        accounts = accounts.filter(name=account)
    balances = {
        a.id: {
            "account": a.name,
            "status": "Active" if a.active_f else "Closed",
            "qualified": a.qualified_f,
            "uninvested": zero,
            "holdings": zero,
        }
        for a in accounts
    }
    for rec in (
        CashRecord.objects.filter(account_id__in=balances, ignored=False, d__lte=today)
        .values("account_id")
        .annotate(amount=Sum("amt"))
    ):
        balances[rec["account_id"]]["uninvested"] = decimal(rec["amount"])

    trades = Trade.objects.filter(account_id__in=balances, dt__lte=now)
    trade_value = ExpressionWrapper(
        -F("q") * F("p"), output_field=DecimalField(max_digits=40, decimal_places=10)
    )
    for rec in (
        trades.filter(reinvest=False, ticker__market__ib_exchange__in=NOT_FUTURES_EXCHANGES)
        .values("account_id")
        .annotate(flow=Sum(trade_value), commissions=Sum("commission"))
    ):
        balances[rec["account_id"]]["uninvested"] += rec["flow"] - rec["commissions"]

    latest = DailyPrice.objects.filter(ticker_id=OuterRef("pk"), d__lte=today).order_by("-d")
    tickers = {
        t.id: t
        for t in Ticker.objects.select_related("market").annotate(
            stored_close=Subquery(latest.values("c")[:1]),
            stored_date=Subquery(latest.values("d")[:1]),
        )
    }
    holdings = []
    warnings = []
    for rec in (
        trades.values("account_id", "ticker_id")
        .annotate(quantity=Sum("q"), flow=Sum(trade_value), commissions=Sum("commission"))
        .order_by("account__name", "ticker__ticker")
    ):
        ticker = tickers[rec["ticker_id"]]
        is_cash = ticker.market.is_cash
        if not is_cash and not ticker.market.is_futures:
            continue
        quantity = rec["quantity"]
        if abs(quantity) < Decimal("0.00000001"):
            quantity = zero
        price = ticker.fixed_price if ticker.fixed_price is not None else ticker.stored_close
        balance = balances[rec["account_id"]]
        field = "holdings" if is_cash else "uninvested"
        value = zero
        if quantity:
            if price is None:
                value = None
                warnings.append(
                    f"No fixed price or stored close for {balance['account']}: {ticker.ticker}."
                )
            else:
                value = quantity * decimal(price) * decimal(ticker.market.cs)
        if not is_cash and value is not None:
            value += decimal(ticker.market.cs) * rec["flow"] - rec["commissions"]
        if value is None or balance[field] is None:
            balance[field] = None
        else:
            balance[field] += value
        if is_cash and quantity:
            holdings.append(
                {
                    "account": balance["account"],
                    "qualification": "Qualified" if balance["qualified"] else "Non-qualified",
                    "ticker": ticker.ticker,
                    "quantity": f"{quantity:,.2f}",
                    "price": money(decimal(price)) if price is not None else "Unavailable",
                    "price_date": (
                        "Fixed price" if ticker.fixed_price is not None else ticker.stored_date
                    ),
                    "value": money(value),
                }
            )

    rows = []
    totals = {"uninvested": zero, "holdings": zero, "total": zero}
    groups = {
        qualified: {
            "label": "Qualified" if qualified else "Non-qualified",
            "rows": [],
            "totals": dict(totals),
        }
        for qualified in (True, False)
    }
    for balance in balances.values():
        group = groups[balance["qualified"]]
        balance["total"] = (
            balance["uninvested"] + balance["holdings"]
            if balance["uninvested"] is not None and balance["holdings"] is not None
            else None
        )
        for field in totals:
            value = balance[field]
            totals[field] = (
                None if value is None or totals[field] is None else totals[field] + value
            )
            subtotal = group["totals"][field]
            group["totals"][field] = (
                None if value is None or subtotal is None else subtotal + value
            )
        if any(
            balance[field] is None or abs(balance[field]) >= Decimal("0.005") for field in totals
        ):
            row = {**balance, **{field: money(balance[field]) for field in totals}}
            rows.append(row)
            group["rows"].append(row)
    for group in groups.values():
        group["totals"] = {field: money(value) for field, value in group["totals"].items()}
    return {
        "as_of": now,
        "rows": rows,
        "cash_groups": list(groups.values()),
        "holdings": holdings,
        "warnings": warnings,
        "totals": {field: money(value) for field, value in totals.items()},
    }
