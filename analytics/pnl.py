
import numpy as np
import pandas as pd
from datetime import date
from collections import OrderedDict
from moneycounter.str_utils import cround, is_near_zero
from moneycounter import wap_calc
from worth.utils import df_to_jqtable
from moneycounter.dt import our_now, lbd_prior_month, prior_business_day
from markets.models import get_ticker, NOT_FUTURES_EXCHANGES
from analytics.models import PPMResult
from analytics.utils import roi
from trades.models import copy_trades_df
from trades.utils import pnl_asof, price_mapper, open_position_pnl
from markets.utils import ticker_url
from accounts.utils import get_account_url


def format_rec(a, t, pos=0, price=1, value=0, daily=0, mtd=0, ytd=0, pnl=0):
    if a == 'TOTAL':
        return [a, '', '', '', cround(value, 2), cround(daily, 2), cround(mtd, 2), cround(ytd, 0), '']
    if a == 'ALL COH':
        return [a, '', '', '', '', '', '', '', cround(pnl, 0), ]

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


def pnl(d=None, a=None):
    if d is None:
        d = our_now().date()

    yesterday = prior_business_day(d)
    eoy = lbd_prior_month(date(d.year, 1, 1))
    lm = lbd_prior_month(d)

    pnl_total, cash = pnl_asof(d=d, a=a)
    pnl_eod, cash_eod = pnl_asof(d=yesterday, a=a)
    pnl_eom, cash_eom = pnl_asof(d=lm, a=a)
    pnl_eoy, cash_eoy = pnl_asof(d=eoy, a=a)

    # The Value of Futures positions is already added to the cash and should not be added to the total again.
    total_worth = pnl_total[pnl_total.e.isin(NOT_FUTURES_EXCHANGES)]
    total_worth = total_worth.value.sum() + cash.q.sum()

    df = pd.merge(pnl_eod, pnl_eoy, on=['a', 't'], how='outer', suffixes=('_yesterday', '_year'))
    # Note - merge only uses suffixes if both df's have the same column headings.
    #        so this one wouldn't use them anyway
    df = pd.merge(df, pnl_total, on=['a', 't'], how='outer')
    df = pd.merge(df, pnl_eom, on=['a', 't'], how='outer', suffixes=('', '_month'))
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

    # Remove old irrelevant records - things that did not have a position or a trade this year.
    x = 0.001
    filter_index = result[(np.abs(result.Pos) < x) & (np.abs(result.YTD) < x) & (np.abs(result.Value) < x)].index
    result.drop(filter_index, inplace=True)

    # Calculate Account Cash Balances
    cash = pd.merge(cash, cash_eod, how='outer', on='a', suffixes=('', '_eod'))
    cash = pd.merge(cash, cash_eom, how='outer', on='a', suffixes=('', '_eom'))
    cash = pd.merge(cash, cash_eoy, how='outer', on='a', suffixes=('', '_eoy'))
    cash.fillna(0, inplace=True)

    cash.reset_index(inplace=True, drop=True)
    cash.rename(columns={'a': 'Account'}, inplace=True)
    cash['Ticker'] = 'CASH'
    cash['Pos'] = cash.q
    cash['Price'] = 1.0
    cash['Value'] = cash.Pos
    cash['Today'] = cash.Pos - cash.q_eod
    cash['MTD'] = cash.Pos - cash.q_eom
    cash['YTD'] = cash.Pos - cash.q_eoy
    cash['PnL'] = 0
    cash.drop(['q', 'q_eod', 'q_eom', 'q_eoy'], axis=1, inplace=True)

    today_total = result.Today.sum()
    mtd_total = result.MTD.sum()
    ytd_total = result.YTD.sum()

    result = pd.concat([result, cash])
    result.reset_index(inplace=True, drop=True)

    result.loc[len(result) + 1] = ['TOTAL', '', 0, 0, total_worth, today_total, mtd_total, ytd_total, 0]

    coh = result[result.Ticker == "CASH"]
    coh = coh.Pos.sum()
    result.loc[len(result) + 1] = ['ALL COH', '', '', '', '', '', '', '', cround(coh, 0)]

    return result, total_worth


def pnl_summary(d=None, a=None):
    result, total_worth = pnl(d=d, a=a)

    if (d is None) or (d == date.today()):
        PPMResult.objects.create(value=total_worth)

    headings, data, formats = df_to_jqtable(df=result, formatter=format_rec)

    return headings, data, formats, total_worth


def format_if_closed(a, t, wap=0, cs=1, q=0, price=0, pnl=0):
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
    pnl = cround(pnl, vprec)

    a = get_account_url(a)
    return [a, t, cs, q, wap, price, pnl]


def pnl_if_closed(a=None):
    """
        Copy trades_df
        Remove all closed positions.
        Add close out trade for each open position.
        total_realized_gains() just like RealizedGainView to calculate expected realized gains.
    """

    df = copy_trades_df(a=a)
    df = df[df.e.isin(NOT_FUTURES_EXCHANGES)]
    df = open_position_pnl(df)

    return df, format_if_closed
