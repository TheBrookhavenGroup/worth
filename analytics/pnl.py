import json
from datetime import date
from worth.utils import cround, is_near_zero, is_not_near_zero, union_keys
from worth.dt import our_now, lbd_prior_month, prior_business_day
from markets.models import Ticker
from analytics.models import PPMResult
from analytics.utils import pcnt_change
from trades.utils import valuations, get_futures_pnl, get_equties_pnl, get_balances
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


def format_rec(a, t, pos, price, value, daily, mtd, ytd, pnl, yahoo_f=True):
    t = Ticker.objects.get(ticker=t)
    pprec = t.market.pprec
    vprec = t.market.vprec
    if yahoo_f and t != 'CASH':
        t = yahoo_url(t)

    pos = cround(pos, 0)
    price = cround(price, pprec)
    daily_pcnt = cround(pcnt_change(value - daily, delta=daily), 1, symbol='%')
    value = cround(value, vprec, symbol='#')
    daily = f"{cround(daily, 2)}  {daily_pcnt}"
    mtd = cround(mtd, 2)
    ytd = cround(ytd, 0)
    pnl = cround(pnl, vprec, symbol='#')

    return [a, t, pos, price, value, daily, mtd, ytd, pnl]


def year_pnl(d=None, account=None, ticker=None, yahoo_f=True):
    headings = ['Account', 'Ticker', 'Pos', 'Price', 'Value', 'Today', 'MTD', 'YTD', 'PnL']
    formats = json.dumps({'columnDefs': [{'targets': [i for i in range(2, len(headings))],
                                          'className': 'dt-body-right'}]})
    # , 'ordering': False})

    if d is None:
        d = our_now().date()

    yesterday = prior_business_day(d)
    eoy = lbd_prior_month(date(d.year, 1, 1))
    lm = lbd_prior_month(d)

    def to_dict(x):
        # key would be account and value is cash value
        return dict([(i[0], i[-1]) for i in x if i[1] == 'CASH'])

    data = []
    total_cash_value = to_dict(valuations(d=d, account=account))
    yesterday_cash_value = to_dict(valuations(d=yesterday, account=account))
    lm_cash_value = to_dict(valuations(d=lm, account=account))
    eoy_cash_value = to_dict(valuations(d=eoy, account=account))

    accounts = union_keys([total_cash_value, yesterday_cash_value, lm_cash_value], first='ALL')

    total_worth = 0
    total_coh = 0
    for a in accounts:
        value = total_cash_value.get(a, 0)
        daily = value - yesterday_cash_value.get(a, 0)
        mtd = value - lm_cash_value.get(a, 0)
        ytd = value - eoy_cash_value.get(a, 0)
        data.append(format_rec(a, 'CASH', value, 1.0, value, daily, mtd, ytd, value, yahoo_f=yahoo_f))
        if a == 'ALL':
            total_worth = value
        else:
            total_coh += value

    data.append(['ALL COH', 'CASH', 0, 0, 0, 0, 0, 0, cround(total_coh, 0, symbol='#')])
    accounts.remove('ALL')

    def pnl_to_dict(x):
        return dict([(str(i[0]), i[1:]) for i in x])

    ticker_total_pnl = 0
    for a in accounts:
        x = get_equties_pnl(d=d, a=a)
        total_pnl = pnl_to_dict(x[0])
        yesterday_pnl = pnl_to_dict(get_equties_pnl(d=yesterday, a=a)[0])
        lm_pnl = pnl_to_dict(get_equties_pnl(d=lm, a=a)[0])
        eoy_pnl = pnl_to_dict(get_equties_pnl(d=eoy, a=a)[0])

        tickers = union_keys([total_pnl, yesterday_pnl, lm_pnl])

        for t in tickers:
            pos, price, pnl = total_pnl.get(t, [0, 0, 0])
            value = pos * price
            daily = pnl - yesterday_pnl.get(t, [0, 0, 0])[2]
            mtd = pnl - lm_pnl.get(t, [0, 0, 0])[2]
            ytd = pnl - eoy_pnl.get(t, [0, 0, 0])[2]

            show_ticker_f = (ticker is not None) and (t == ticker)
            if show_ticker_f:
                ticker_total_pnl += pnl

            if show_ticker_f or not (is_near_zero(pos) and is_near_zero(daily)):
                data.append(format_rec(a, t, pos, price, value, daily, mtd, ytd, pnl, yahoo_f=yahoo_f))

    if is_not_near_zero(ticker_total_pnl):
        data.append(format_rec('ALL', ticker, 0, 0, 0, 0, 0, 0, ticker_total_pnl, yahoo_f=yahoo_f))

    if (account is None) and (d is None or (d == date.today())):
        PPMResult.objects.create(value=total_worth)

    return headings, data, formats
