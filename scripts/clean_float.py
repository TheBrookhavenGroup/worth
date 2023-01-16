# Try to round q values so they sum to zero appropriately.

from django.db.models import Sum
from trades.models import Trade


def add_to_last_trade(a, t, q):
    qs = Trade.objects.filter(account__name=a).filter(ticker__ticker=t).order_by('-dt')
    for i in qs:
        i.qd += q
        i.save()
        break


def find_small_q():
    qs = Trade.objects.values_list('ticker__ticker', 'account__name').annotate(Sum('q'))
    qs = qs.order_by('account__name', 'ticker__name')
    for t, a, q in qs:
        if q == 0:
            continue
        if q < 0.001 and q > -0.001:
            print(a, t, q)
