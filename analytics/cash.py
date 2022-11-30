from accounts.models import CashRecord
from trades.utils import pnl_asof


def cash_sums(account_name):
    qs = CashRecord.objects.filter(account__name=account_name).filter(ignored=False).order_by('d').all()
    total = 0
    total_cleared = 0
    for rec in qs:
        a = rec.amt
        total += a
        if rec.cleared_f:
            total_cleared += a
    return total, total_cleared


def total_cash():
    total = 0.0
    _, cash = pnl_asof()
    total = cash.q.sum()
    return total
