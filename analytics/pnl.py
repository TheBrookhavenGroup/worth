import json
from datetime import date
from worth.utils import cround, is_near_zero
from worth.dt import our_now, lbd_prior_month, prior_business_day
from markets.models import Ticker
from analytics.models import PPMResult
from trades.utils import valuations, get_futures_pnl, get_balances
from markets.tbgyahoo import yahoo_url


def futures_pnl_ymd(d=None, a='MSRKIB'):
    if d is None:
        d = our_now().date()

    yesterday = prior_business_day(d)

    eoy = lbd_prior_month(date(d.year, 1, 1))
    lm = lbd_prior_month(d)

    def to_dict(x):
        return dict([(i[0].ticker, i[1:]) for i in x])

    pnl_total, total = get_futures_pnl(d=d, a=a)
    pnl_total = to_dict(pnl_total)
    pnl_yesterday = to_dict(get_futures_pnl(d=yesterday, a=a)[0])
    pnl_prior_month = to_dict(get_futures_pnl(d=lm, a=a)[0])
    pnl_end_of_year = to_dict(get_futures_pnl(d=eoy, a=a)[0])

    return pnl_end_of_year, pnl_prior_month, pnl_yesterday, pnl_total


def futures_pnl(d=None, a='MSRKIB'):
    headings = ['Ticker', 'Pos', 'Price', 'PnL', 'Today', 'MTD', 'YTD']
    formats = json.dumps({'columnDefs': [{'targets': [i for i in range(1, len(headings))],
                                          'className': 'dt-body-right'}], 'ordering': False})

    pnl_end_of_year, pnl_prior_month, pnl_yesterday, pnl_total = futures_pnl_ymd(d=d, a=a)

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
            daily = pnl_yesterday[ticker][-1]
            daily = pnl - daily
        else:
            daily = pnl

        if ticker in pnl_prior_month:
            mtd = pnl_prior_month[ticker][-1]
            mtd = pnl - mtd
        else:
            mtd = pnl

        if ticker in pnl_end_of_year:
            ytd = pnl_end_of_year[ticker][-1]
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
        daily = cround(daily, 2)
        mtd = cround(mtd, 2)
        ytd = cround(ytd, 0)

        data.append([ticker, pos, price, pnl, daily, mtd, ytd])

    data.append(['TOTAL', '', '', '', cround(today_total, 2), cround(mtd_total, 2), cround(ytd_total, 0)])

    cash = get_balances(d=d, account=a)[a]['CASH']
    data.append(['CASH', cround(cash, 2), '', '', '', '', ''])

    return headings, data, formats


def pnl_ymd(d=None, account=None, ticker=None):
    if d is None:
        d = our_now().date()

    yesterday = prior_business_day(d)

    eoy = lbd_prior_month(date(d.year, 1, 1))
    lm = lbd_prior_month(d)

    def to_dict(x):
        return dict([((i[0], i[1]), i[2:]) for i in x])

    total_value = to_dict(valuations(d=d, account=account, ticker=ticker))
    yesterday_value = to_dict(valuations(d=yesterday, account=account, ticker=ticker))
    lm_value = to_dict(valuations(d=lm, account=account, ticker=ticker))
    eoy_value = to_dict(valuations(d=eoy, account=account, ticker=ticker))

    return eoy_value, lm_value, yesterday_value, total_value


def ppm_pnl(d=None, account=None, ticker=None):
    headings = ['Account', 'Ticker', 'Pos', 'Price', 'Value', 'Today', 'MTD', 'YTD']
    formats = json.dumps({'columnDefs': [{'targets': [i for i in range(2, len(headings))],
                                          'className': 'dt-body-right'}]})
    # , 'ordering': False})

    eoy_value, lm_value, yesterday_value, total_value = pnl_ymd(d=d, account=account, ticker=ticker)

    ks = set(total_value.keys()).\
        union(set(yesterday_value.keys())).\
        union(set(lm_value.keys())).\
        union(set(eoy_value.keys()))

    ks = list(ks)

    data = []
    ytd_total = mtd_total = today_total = 0.0
    for k in ks:
        a, t = k
        pos, price, value = total_value[k]

        if k in yesterday_value:
            daily = yesterday_value[k][-1]
            daily = value - daily
        else:
            daily = value

        if k in lm_value:
            mtd = lm_value[k][-1]
            mtd = value - mtd
        else:
            mtd = value

        if k in eoy_value:
            ytd = eoy_value[k][-1]
            ytd = value - ytd
        else:
            ytd = value

        pprec = 4
        vprec = 0
        if a == 'AAA Total':
            vprec = 3
        else:
            t = Ticker.objects.get(ticker=t)
            pprec = t.market.pprec
            t = yahoo_url(t)

        ytd_total += ytd
        mtd_total += mtd
        today_total += daily

        pos = cround(pos, 0)
        price = cround(price, pprec)
        value = cround(value, vprec)
        daily = cround(daily, 2)
        mtd = cround(mtd, 2)
        ytd = cround(ytd, 0)

        data.append([a, t, pos, price, value, daily, mtd, ytd])

    if (account is None) and (ticker is None) and (not d or (d == date.today())):
        total_worth = total_value[('AAA Total', '')][-1]
        PPMResult.objects.create(value=total_worth)

    return headings, data, formats
