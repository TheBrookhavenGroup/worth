import json
from django.db.models import Sum
from django.utils.safestring import mark_safe
from django.conf import settings
from collections import defaultdict

from worth.utils import cround
from trades.models import Trade
from accounts.models import CashRecord
from markets.models import Ticker
from worth.utils import is_near_zero
from markets.utils import get_price


def get_balances(account=None, ticker=None):
    # balances[<account>]->[<symbol>]-><qty>
    balances = defaultdict(lambda: defaultdict(lambda: 0.0))

    qs = Trade.objects
    if account is not None:
        account = account.upper()
        qs = qs.filter(account__name=account)

    cash_f = False
    if ticker is not None:
        ticker = ticker.upper()
        if ticker == 'CASH':
            cash_f = True
        else:
            qs = qs.filter(ticker__ticker=ticker)

    qs = qs.values_list('account__name', 'ticker__ticker', 'reinvest', 'q', 'p', 'commission')
    for a, ti, reinvest, q, p, c in qs:
        portfolio = balances[a]

        if not reinvest:
            cash_amount = -q * p - c
            portfolio['CASH'] += cash_amount

        if not cash_f:
            portfolio[ti] += q

    qs = CashRecord.objects
    if account is not None:
        qs = qs.filter(account__name=account)

    qs = qs.values('account__name').order_by('account__name').annotate(total=Sum('amt'))
    for result in qs:
        total = result['total']
        if abs(total) < 0.001:
            continue
        a = result['account__name']
        balances[a]['CASH'] += total

    empty_accounts = [a for a in balances if abs(balances[a]['CASH']) < 0.001]
    for a in empty_accounts:
        del balances[a]['CASH']
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

    headings = ['Account', 'Ticker', 'Q', 'P', 'Value']
    data = []
    balances = get_balances(account, ticker)
    total_worth = 0
    for a in balances.keys():
        portfolio = balances[a]
        for ticker in portfolio.keys():
            t = Ticker.objects.get(ticker=ticker.upper())
            q = portfolio[ticker]
            if is_near_zero(q):
                continue

            p = get_price(t)
            value = q * p
            total_worth += value

            qstr = cround(q, 3)
            pstr = cround(p, t.market.pprec)
            vstr = cround(value, 3)

            data.append([a, ticker, qstr, pstr, vstr])
    data.append(['AAA Total', '', '', '', cround(total_worth, 3)])
    data.append([mark_safe('<a href=https://commonologygame.com>commonology</a>'), '', '', '', ''])

    return headings, data, formats
