from django.db.models import Sum
from accounts.models import CashRecord
from trades.utils import pnl_asof


def cash_sums(account_name=None, account_id=None):
    qs = CashRecord.objects.filter(ignored=False)
    if account_name:
        qs = qs.filter(account__name=account_name)
    elif account_id:
        qs = qs.filter(account__id=account_id)
    total = qs.aggregate(Sum('amt'))['amt__sum'] or 0
    total_cleared = qs.filter(cleared_f=True). \
        aggregate(Sum('amt'))['amt__sum'] or 0
    return total, total_cleared
