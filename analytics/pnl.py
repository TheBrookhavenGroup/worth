import json
import numpy as np
import pandas as pd
from datetime import date
from collections import OrderedDict
from worth.utils import cround, is_near_zero, is_not_near_zero, union_keys, df_to_jqtable
from worth.dt import our_now, lbd_prior_month, prior_business_day
from markets.models import get_ticker
from analytics.models import PPMResult
from analytics.utils import pcnt_change
from trades.utils import valuations, get_futures_pnl, get_equties_pnl
from markets.utils import ticker_url
from accounts.utils import get_account_url


headings = ['Account', 'Ticker', 'Pos', 'Price', 'Value', 'Today', 'MTD', 'YTD', 'PnL']


def format_rec(a, t, pos=0, price=1, value=0, daily=0, mtd=0, ytd=0, pnl=0):
    if a == 'TOTAL':
        return [a, '', '', '', '', cround(daily, 2), cround(mtd, 2), cround(ytd, 0), '']
    if t == 'ALL COH':
        return [t, '', '', '', '', '', '', '', cround(pnl, 0), ]

    t = get_ticker(t)
    pprec = t.market.pprec
    vprec = t.market.vprec
    t = ticker_url(t)

    pos = cround(pos, 0)
    if is_near_zero(price):
        price = ''
    else:
        price = cround(price, pprec)
    daily_pcnt = cround(pcnt_change(value - daily, delta=daily), 1, symbol='%')
    if is_near_zero(value):
        value = ''
    else:
        value = cround(value, vprec)
    if is_near_zero(daily):
        daily = ''
    else:
        daily = f"{cround(daily, 2)}  {daily_pcnt}"
    mtd = cround(mtd, 2)
    ytd = cround(ytd, 0)
    if is_near_zero(pnl):
        pnl = ''
    else:
        pnl = cround(pnl, vprec)

    a = get_account_url(a)
    return [a, t, pos, price, value, daily, mtd, ytd, pnl]


def futures_pnl(d=None, a='MSRKIB'):
    if d is None:
        d = our_now().date()

    yesterday = prior_business_day(d)
    eoy = lbd_prior_month(date(d.year, 1, 1))
    lm = lbd_prior_month(d)

    pnl_total = get_futures_pnl(d=None)
    pnl_yesterday = get_futures_pnl(d=yesterday)
    pnl_prior_month = get_futures_pnl(d=lm)
    pnl_end_of_year = get_futures_pnl(d=eoy)

    df = pd.merge(pnl_yesterday, pnl_end_of_year, on=['a', 't'], how='outer', suffixes=('_yesterday', '_year'))
    # Note - merge only uses suffixes if both df's have the same column headings.
    #        so this one wouldn't use them anyway
    df = pd.merge(df, pnl_total, on=['a', 't'], how='outer')
    df = pd.merge(df, pnl_prior_month, on=['a', 't'], how='outer', suffixes=('', '_month'))
    df = df.fillna(value=0)

    result = pd.DataFrame(OrderedDict((('Account', df.a),
                                       ('Ticker', df.t),
                                       ('Pos', df.q),
                                       ('Price', df.price),
                                       ('Value', df.value),
                                       ('Today', df.pnl - df.pnl_yesterday),
                                       ('MTD', df.pnl - df.pnl_month),
                                       ('YTD', df.pnl - df.pnl_year),
                                       ('PnL', df.pnl))))

    filter_index = result[(np.abs(result['YTD']) < 0.0001) & (np.abs(result['Value']) < 0.001)].index
    result.drop(filter_index, inplace=True)

    today_total = result.Today.sum()
    mtd_total = result.MTD.sum()
    ytd_total = result.YTD.sum()
    result.loc[len(result)] = format_rec('TOTAL', '', 0, 0, 0, today_total, mtd_total, ytd_total, 0)

    headings, data, formats = df_to_jqtable(df=result, formatter=format_rec)

    return headings, data, formats


def year_pnl(d=None, account=None, ticker=None):
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

        if a == 'ALL':
            total_worth = value
        else:
            total_coh += value

        data.append(format_rec(a, 'CASH', value, 1.0, value, daily, mtd, ytd))

    data.append(format_rec('ALL COH', 'ALL COH', pnl=total_coh))
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

        default = [0, 0, 0, 0]
        for t in tickers:
            pos, price, pnl = total_pnl.get(t, default)
            value = pos * price
            daily = pnl - yesterday_pnl.get(t, default)[2]
            mtd = pnl - lm_pnl.get(t, default)[2]
            ytd = pnl - eoy_pnl.get(t, default)[2]

            show_ticker_f = (ticker is not None) and (t == ticker)
            if show_ticker_f:
                ticker_total_pnl += pnl

            if show_ticker_f or not (is_near_zero(pos) and is_near_zero(daily)):
                data.append(format_rec(a, t, pos, price, value, daily, mtd, ytd, pnl))

    if is_not_near_zero(ticker_total_pnl):
        data.append(format_rec('ALL', ticker, pnl=ticker_total_pnl))

    if (account is None) and (d is None or (d == date.today())):
        PPMResult.objects.create(value=total_worth)

    return headings, data, formats
