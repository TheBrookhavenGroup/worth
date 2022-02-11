from accounts.models import Account, CashRecord


def cash_sums(account_name):
    qs = CashRecord.objects.filter(account__name=account_name).order_by('d').all()
    total = 0
    total_cleared = 0
    for rec in qs:
        a = rec.amt
        total += a
        if rec.cleared_f:
            total_cleared += a
    return total, total_cleared