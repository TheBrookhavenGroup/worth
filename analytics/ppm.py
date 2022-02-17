import json
from django.db.models import Sum
from django.utils.safestring import mark_safe
from django.conf import settings
from markets.tbgyahoo import yahooQuote
from collections import defaultdict
from cachetools.func import ttl_cache

from worth.utils import cround
from trades.models import Trade
from accounts.models import CashRecord
from worth.utils import is_near_zero
from markets.models import Ticker


@ttl_cache(maxsize=128, ttl=60)
def get_price(ticker):
    if not settings.USE_PRICE_FEED:
        return 1.0

    t = Ticker.objects.get(ticker=ticker.upper())

    if t.fixed_price is None:
        p = yahooQuote(ticker)[0]
    else:
        p = t.fixed_price

    return p


def get_balances(account=None, ticker=None):
    # balances[<account>]->[<symbol>]-><qty>
    balances = defaultdict(lambda: defaultdict(lambda: 0.0))

    qs = Trade.objects.values_list('account__name', 'ticker__ticker', 'reinvest', 'q', 'p', 'commission')
    for a, ticker, reinvest, q, p, c in qs:
        portfolio = balances[a]

        if not reinvest:
            cash_amount = -q * p - c
            portfolio['cash'] += cash_amount

        portfolio[ticker] += q

    qs = CashRecord.objects.values('account__name').order_by('account__name').annotate(total=Sum('amt'))
    for result in qs:
        total = result['total']
        if abs(total) < 0.001:
            continue
        a = result['account__name']
        balances[a]['cash'] += total

    empty_accounts = [a for a in balances if abs(balances[a]['cash']) < 0.001]
    for a in empty_accounts:
        del balances[a]['cash']
        if len(balances[a].keys()) == 0:
            del balances[a]

    # Scale results for demo purposes.  PPM_FACTOR defaults to False.
    factor = settings.PPM_FACTOR
    if factor is not False:
        for k, v in balances.items():
            for j in v.keys():
                v[j] *= factor

    return balances


def valuations(account=None, ticker=None):
    formats = json.dumps({'columnDefs': [{'targets': [2, 3, 4], 'className': 'dt-body-right'}],
                          # 'ordering': False
                          })
    print(formats)

    headings = ['Account', 'Ticker', 'Q', 'P', 'Value']
    data = []
    balances = get_balances(account, ticker)
    total_worth = 0
    for a in balances.keys():
        portfolio = balances[a]
        for ticker in portfolio.keys():
            q = portfolio[ticker]
            if is_near_zero(q):
                continue

            p = get_price(ticker)
            value = q * p
            total_worth += value

            nsig = 9 if q > 900e3 else None
            qstr = cround(q, 3)
            pstr = cround(p, 3)
            vstr = cround(value, 3)

            data.append([a, ticker, qstr, pstr, vstr])
    data.append(['AAA Total', '', '', '', cround(total_worth, 3)])
    data.append([mark_safe('<a href=https://commonologygame.com>commonology</a>'), '', '', '', ''])

    return headings, data, formats
