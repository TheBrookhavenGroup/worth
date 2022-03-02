
import json
from datetime import date
from django.db.models import Sum
from django.conf import settings
from collections import defaultdict

from worth.utils import cround, is_near_zero
from worth.dt import our_now, lbd_prior_month, prior_business_day
from trades.models import Trade
from accounts.models import CashRecord
from markets.models import Ticker
from markets.utils import get_price, is_futures
from markets.tbgyahoo import yahoo_url
from analytics.models import PPMResult
from trades.utils import get_futures_pnl, avg_open_price


def get_balances(account=None, ticker=None):
    # balances[<account>]->[<ticker>]-><qty>
    balances = defaultdict(lambda: defaultdict(lambda: 0.0))

    cash_f = (ticker is not None) and (ticker == 'CASH')

    qs = Trade.more_filtering(account, ticker)
    qs = qs.values_list('account__name', 'ticker__ticker', 'reinvest', 'q', 'p',
                        'commission', 'ticker__market__cs', 'ticker__market__ib_exchange')
    futures_accounts = []
    for a, ti, reinvest, q, p, c, cs, e in qs:
        portfolio = balances[a]

        if is_futures(e):
            futures_accounts.append(a)
            continue

        if not reinvest:
            cash_amount = -q * p * cs - c
            portfolio['CASH'] += cash_amount

        if not cash_f:
            portfolio[ti] += q

    qs = CashRecord.objects.filter(ignored=False)
    if account is not None:
        qs = qs.filter(account__name=account)

    qs = qs.values('account__name').order_by('account__name').annotate(total=Sum('amt'))
    for result in qs:
        total = result['total']
        if abs(total) < 0.001:
            continue
        a = result['account__name']
        balances[a]['CASH'] += total

    for a in set(futures_accounts):
        pnl, total = get_futures_pnl(a=a)
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


def futures_pnl_ymd():

    today = our_now().date()
    yesterday = prior_business_day(today)

    eoy = lbd_prior_month(date(today.year, 1, 1))
    lm = lbd_prior_month(today)

    def to_dict(x):
        return dict([(i[0].ticker, i[1:]) for i in x])

    pnl_total, total = get_futures_pnl()
    pnl_total = to_dict(pnl_total)
    pnl_yesterday = to_dict(get_futures_pnl(yesterday)[0])
    pnl_prior_month = to_dict(get_futures_pnl(lm)[0])
    pnl_end_of_year = to_dict(get_futures_pnl(eoy)[0])

    return pnl_end_of_year, pnl_prior_month, pnl_yesterday, pnl_total


def futures_pnl(current_year=True):
    formats = json.dumps({'columnDefs': [{'targets': [1, 2, 3, 4, 5, 6],
                                          'className': 'dt-body-right'}], 'ordering': False})
    headings = ['Ticker', 'Pos', 'Price', 'PnL', 'Today', 'MTD', 'YTD']

    pnl_end_of_year, pnl_prior_month, pnl_yesterday, pnl_total = futures_pnl_ymd()

    tickers = set(pnl_total.keys()).\
        union(set(pnl_yesterday.keys())).\
        union(set(pnl_prior_month.keys())).\
        union(set(pnl_end_of_year.keys()))

    tickers = list(tickers)

    data = []
    ytd_total = mtd_total = today_total = 0.0
    for ticker in tickers:
        pos, price, pnl = pnl_total[ticker]

        if ticker in pnl_yesterday:
            daily = pnl_yesterday[ticker][2]
            daily = pnl - daily
        else:
            daily = pnl

        if ticker in pnl_prior_month:
            mtd = pnl_prior_month[ticker][2]
            mtd = pnl - mtd
        else:
            mtd = pnl

        if ticker in pnl_end_of_year:
            ytd = pnl_end_of_year[ticker][2]
            ytd = pnl - ytd
        else:
            ytd = pnl

        t = Ticker.objects.get(ticker=ticker)

        if is_near_zero(ytd):
            continue

        ytd_total += ytd
        mtd_total += mtd
        today_total += daily

        pos = cround(pos, 0)
        price = cround(price, t.market.pprec)
        pnl = cround(pnl, 0)
        daily = cround(daily, 0)
        mtd = cround(mtd, 0)
        ytd = cround(ytd, 0)

        data.append([ticker, pos, price, pnl, daily, mtd, ytd])

    data.append(['TOTAL', '', '', '', cround(today_total, 0), cround(mtd_total, 0), cround(ytd_total, 0)])

    return headings, data, formats


def valuations(account=None, ticker=None):
    formats = json.dumps({'columnDefs': [{'targets': [2, 3, 4], 'className': 'dt-body-right'}],
                          # 'ordering': False
                          })

    headings = ['Account', 'Ticker', 'Q', 'P', 'Value']
    data = []
    balances = get_balances(account, ticker)

    d = lbd_prior_month(our_now().date())

    # futures_total = get_futures_pnl(d=d)[1]
    # balances['MSRKIB']['CASH'] += futures_total

    total_worth = 0
    for a in balances.keys():
        portfolio = balances[a]
        for ticker in portfolio.keys():
            t = Ticker.objects.get(ticker=ticker)
            m = t.market
            q = portfolio[ticker]
            if is_near_zero(q):
                continue

            p = get_price(t)

            if m.is_futures:
                value = q * (p - avg_open_price(a, t)) * m.cs
            else:
                value = q * p * m.cs

            total_worth += value

            qstr = cround(q, 3)
            pstr = cround(p, m.pprec)
            vstr = cround(value, 3)

            if ticker == 'CASH':
                url = 'CASH'
            else:
                url = yahoo_url(t)

            data.append([a, url, qstr, pstr, vstr])

    data.append(['AAA Total', '', '', '', cround(total_worth, 3)])

    PPMResult.objects.create(value=total_worth)

    return headings, data, formats
