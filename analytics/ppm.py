from markets.tbgyahoo import yahooQuote
from collections import defaultdict
from functools import cache
from worth.utils import cround
from trades.models import Trade
from accounts.models import CashRecord
from worth.utils import is_near_zero


default_prices = defaultdict(lambda: 1.0)
default_prices['V-NPI'] = 0.0
default_prices['V-KOL'] = 0.0
default_prices['V-MED'] = 0.0
default_prices['V-CAR'] = 0.0
default_prices['V-CAD'] = 0.0
default_prices['V-FND'] = 0.0
default_prices['V-TSA'] = 0.0
for i in ['cash', 'SNAXX', 'FBroker', 'FDRXX']:
    default_prices[i] = 1.0


@cache
def get_price(ticker):
    if ticker in default_prices:
        p = default_prices[ticker]
    else:
        p = yahooQuote(ticker)[0]
    return p


def get_balances():
    # balances[<account>]->[<symbol>]-><qty>
    balances = defaultdict(lambda: {})

    qs = Trade.objects.values_list('account__name', 'ticker__ticker', 'reinvest', 'q', 'p', 'commission')
    for a, ticker, reinvest, q, p, c in qs:
        if a in balances:
            portfolio = balances[a]
        else:
            portfolio = {}
            balances[a] = portfolio

        cash_amount = -q * p - c
        if 'cash' not in portfolio:
            portfolio['cash'] = cash_amount
        else:
            portfolio['cash'] += cash_amount

        if ticker not in portfolio:
            portfolio[ticker] = q
        else:
            portfolio[ticker] += q

    qs = CashRecord.objects.values_list('account__name', 'amt')
    for a, q in qs:
        if a in balances:
            portfolio = balances[a]
            if 'cash' not in portfolio:
                portfolio['cash'] = q
            else:
                portfolio['cash'] += q

    return balances


def valuations():
    headings = ['Account', 'Ticker', 'Q', 'P', 'Value']
    data = []
    balances = get_balances()
    for a in balances.keys():
        portfolio = balances[a]
        for ticker in portfolio.keys():
            q = portfolio[ticker]
            if is_near_zero(q):
                continue
            if 'cash' == ticker:
                p = 1.0
            else:
                p = get_price(ticker)
            value = q * p

            nsig = 9 if q > 900e3 else None
            qstr = cround(q, 3, 15, nsig=nsig) if q else 15 * ' '
            pstr = cround(p, 3, 15) if q else 15 * ' '
            vstr = cround(value, 3, 15)

            data.append([a, ticker, qstr, pstr, vstr])

    return headings, data
