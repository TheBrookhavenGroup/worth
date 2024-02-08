from django.db.models import Sum
from accounts.models import CashRecord, Account
from trades.utils import pnl_asof


def cash_sums(account_id, d):
    account_name = Account.objects.get(id=account_id)

    _, total = pnl_asof(d, a=account_name, cleared=False)
    _, total_cleared = pnl_asof(d, a=account_name, cleared=True)

    total = total.q.sum()
    total_cleared = total_cleared.q.sum()

    return total, total_cleared
