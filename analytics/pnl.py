
import numpy as np
import pandas as pd
from datetime import date
from collections import OrderedDict
import json
from tbgutils.str import cround, is_near_zero
from worth.utils import df_to_jqtable
from tbgutils.dt import our_now, lbd_prior_month, prior_business_day
from moneycounter.pnl import pnl_calc
from markets.models import get_ticker, NOT_FUTURES_EXCHANGES
from analytics.models import PPMResult
from analytics.utils import roi
from trades.models import copy_trades_df
from trades.utils import pnl_asof, open_position_pnl
from markets.utils import ticker_url, get_price
from accounts.utils import get_account_url


def format_rec(a, t, pos=0, price=1, value=0, daily=0, mtd=0, ytd=0, pnl=0):
    if a == 'TOTAL':
        return [a, '', '', '', cround(value, 2), cround(daily, 2),
                cround(mtd, 2), cround(ytd, 0), '']

    if a == 'ALL COH':
        return [a, '', '', '', cround(value, 0), '', '', '', '']

    t = get_ticker(t)
    pprec = t.market.pprec
    vprec = t.market.vprec
    t = ticker_url(t)

    pos = cround(pos, 0)
    if is_near_zero(price):
        price = ''
    else:
        price = cround(price, pprec)
    daily_pcnt = cround(roi(value - daily, daily), 1, symbol='%')
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


def pnl(d=None, a=None, active_f=True):
    if d is None:
        d = our_now().date()

    yesterday = prior_business_day(d)
    eoy = lbd_prior_month(date(d.year, 1, 1))
    lm = lbd_prior_month(d)

    pnl_total, cash = pnl_asof(d=d, a=a, active_f=active_f)
    pnl_eod, cash_eod = pnl_asof(d=yesterday, a=a, active_f=active_f)
    pnl_eom, cash_eom = pnl_asof(d=lm, a=a, active_f=active_f)
    pnl_eoy, cash_eoy = pnl_asof(d=eoy, a=a, active_f=active_f)

    # The Value of Futures positions is already added to the cash and should
    # not be added to the total again.
    total_worth = pnl_total[pnl_total.e.isin(NOT_FUTURES_EXCHANGES)]
    try:
        cash_sum = cash.q.sum()
    except AttributeError:
        cash_sum = 0

    total_worth = total_worth.value.sum() + cash_sum

    df = pd.merge(pnl_eod, pnl_eoy, on=['a', 't'], how='outer',
                  suffixes=('_yesterday', '_year'))
    # Note: merge only uses suffixes if both df's have the same column headings.
    #        so this one wouldn't use them anyway
    df = pd.merge(df, pnl_total, on=['a', 't'], how='outer')
    df = pd.merge(df, pnl_eom, on=['a', 't'], how='outer',
                  suffixes=('', '_month'))
    numeric_cols = df.select_dtypes(include='number').columns
    df[numeric_cols] = df[numeric_cols].fillna(value=0)

    result = pd.DataFrame(OrderedDict((('Account', df.a),
                                       ('Ticker', df.t),
                                       ('Pos', df.q),
                                       ('Price', df.price),
                                       ('Value', df.value),
                                       ('Today', df.pnl - df.pnl_yesterday),
                                       ('MTD', df.pnl - df.pnl_month),
                                       ('YTD', df.pnl - df.pnl_year),
                                       ('PnL', df.pnl))))

    # Remove old irrelevant records - things that did not have a position or
    # a trade this year.
    x = 0.001
    filter_index = result[(np.abs(result.Pos) < x) & (np.abs(result.YTD) < x)
                          & (np.abs(result.Value) < x)].index
    result.drop(filter_index, inplace=True)

    # Calculate Account Cash Balances
    cash = pd.merge(cash, cash_eod, how='outer', on='a', suffixes=('', '_eod'))
    cash = pd.merge(cash, cash_eom, how='outer', on='a', suffixes=('', '_eom'))
    cash = pd.merge(cash, cash_eoy, how='outer', on='a', suffixes=('', '_eoy'))
    numeric_cols = df.select_dtypes(include='number').columns
    df[numeric_cols] = df[numeric_cols].fillna(value=0)

    try:
        cash_balance = cash.q
    except AttributeError:
        cash_balance = 0

    try:
        q_eod = cash.q_eod
    except AttributeError:
        q_eod = 0

    try:
        q_eom = cash.q_eom
    except AttributeError:
        q_eom = 0

    try:
        q_eoy = cash.q_eoy
    except AttributeError:
        q_eoy = 0

    cash.reset_index(inplace=True, drop=True)
    cash.rename(columns={'a': 'Account'}, inplace=True)
    cash['Ticker'] = 'CASH'
    cash['Pos'] = cash_balance
    cash['Price'] = 1.0
    cash['Value'] = cash.Pos
    cash['Today'] = cash.Pos - q_eod
    cash['MTD'] = cash.Pos - q_eom
    cash['YTD'] = cash.Pos - q_eoy
    cash['PnL'] = 0

    for col in 'q', 'q_eod', 'q_eom', 'q_eoy':
        try:
            cash.drop([col], axis=1, inplace=True)
        except KeyError:
            pass

    today_total = result.Today.sum()
    mtd_total = result.MTD.sum()
    ytd_total = result.YTD.sum()

    result = pd.concat([result, cash])
    result.reset_index(inplace=True, drop=True)

    cash_flags = result["Ticker"].apply(lambda x: get_ticker(x).market.is_cash)
    coh = result[cash_flags]

    try:
        coh = coh.Pos.sum()
    except AttributeError:
        coh = 0

    result.loc[len(result) + 1] = ['TOTAL', '', 0, 0, total_worth, today_total,
                                   mtd_total, ytd_total, 0]
    result.loc[len(result) + 1] = ['ALL COH', '', '', '', coh, '', '', '', '']

    return result, total_worth, today_total, cash_balance


def pnl_summary(d=None, a=None, active_f=True):
    result, total_worth, total_today, _ = pnl(d=d, a=a, active_f=active_f)

    today = date.today()

    if not d:
        d = today

    if (a is None) and (d != today):
        PPMResult.objects.update_or_create(d=d, defaults={'value': total_worth})

    headings, data, formats = df_to_jqtable(df=result, formatter=format_rec)

    return headings, data, formats, total_worth, total_today


def format_if_closed(a, t, q=0, wap=0, cs=1, price=0, value=0, pnl=0):
    t = get_ticker(t)
    pprec = t.market.pprec
    vprec = t.market.vprec
    t = ticker_url(t)

    q = cround(q, 0)
    if is_near_zero(price):
        price = ''
    else:
        price = cround(price, pprec)

    cs = cround(cs, pprec)
    wap = cround(wap, pprec)
    q = cround(q, vprec)
    value = cround(value, 0)
    pnl = cround(pnl, vprec)

    a = get_account_url(a)
    return [a, t, q, wap, cs, price, value, pnl]


def pnl_if_closed(a=None):
    """
        What would the PnL be if we closed out the position today?

        Copy trades_df
        Remove all closed positions.
        Add close out trade for each open position.
        total_realized_gains() just like RealizedGainView to calculate
        expected realized gains.
    """

    df = copy_trades_df(a=a)
    df = df[df.e.isin(NOT_FUTURES_EXCHANGES)]
    df = open_position_pnl(df)

    return df, format_if_closed


def ticker_pnl(t):
    """
    What is the total pnl earned for the given ticker?
    :param t:
    :return:
    """

    df = copy_trades_df(t=t)
    g1 = df.groupby(['a', 't'])[['cs', 'q', 'p']]
    ticker, g = [(t, g) for (_, t), g in g1][0]
    price = get_price(ticker)
    pnl = pnl_calc(g, price)
    return pnl


def performance():
    formats = json.dumps({'columnDefs': [
        {"targets": [0], 'className': "dt-nowrap"},
        {'targets': [1, 2, 3], 'className': 'dt-body-right'}],
        'pageLength': 100})

    headings = ['Year', 'Value ($)', 'Gain ($)', 'YTD ROI (%)']

    d = date.today()
    n_months = 120

    dtes = [d, prior_business_day(d)] + \
           [d := lbd_prior_month(d) for i in range(int(n_months))]
    dtes.reverse()
    d_exists = PPMResult.objects.filter(d__in=dtes).values_list('d', flat=True)
    for d in set(dtes) - set(d_exists):
        pnl_summary(d, active_f=False)
    values = PPMResult.objects.filter(d__in=dtes).order_by('d').\
        values_list('value', flat=True)

    values = list(values)
    data = list(zip(dtes, values))

    # roll-up data by year
    years = sorted(list(set([d.year for d in dtes])))
    values = [[i for d, i in data if d.year == y][-1] for y in years]

    current_value = values[-1]
    total_gain = values[-1] - values[0]

    data = [[y, cround(i, 2), cround(i - j, 0), cround(i / j - 1, symbol='%')]
            for y, i, j in zip(years[1:], values[1:], values[:-1])]

    totals = ['Total', cround(current_value, 2), cround(total_gain, 2), '']
    data.append(totals)

    return headings, data, formats
