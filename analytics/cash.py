from accounts.models import CashRecord
from trades.utils import get_balances


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
    balances = get_balances()
    for a in balances.keys():
        portfolio = balances[a]
        if 'CASH' in portfolio:
            cash = portfolio['CASH']
            total += cash
    return total
