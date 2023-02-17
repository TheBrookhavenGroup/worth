from datetime import date
import pandas as pd
import numpy as np

from accounts.models import copy_cash_df
from markets.models import get_ticker, NOT_FUTURES_EXCHANGES
from trades.models import Trade, copy_trades_df
from markets.utils import get_price
from moneycounter import wap_calc


def weighted_average_price(ticker, account=None):
    if type(ticker) == str:
        ticker = get_ticker(ticker)

    qs = Trade.equity_trades(account=account, ticker=ticker).order_by('dt')
    df = Trade.qs_to_df(qs)

    pos = df.q.sum()
    wap = wap_calc(df)

    return pos, wap


def open_pnl(ticker=None, account=None):
    qs = Trade.equity_trades(account=account, ticker=ticker)
    df = Trade.qs_to_df(qs)

    pnl = open_position_pnl(df)
    open_pnl = pnl.pnl.sum()

    return open_pnl


def price_mapper(x, d):
    epsilon = 1e-10
    if x.q > -epsilon and x.q < epsilon:
        price = 0
    else:
        ti = get_ticker(x.t)
        price = get_price(ti, d)
    return price


def pnl_asof(d=None, a=None, only_non_qualified=False, active_f=True):
    """
    Calculate PnL from all trades - need that for cash flow.
    Calculate Cash balances.
    Return YTD data for active positions.
    """

    df = copy_trades_df(d=d, a=a, only_non_qualified=only_non_qualified, active_f=active_f)

    if df.empty:
        pnl = pd.DataFrame(columns=['a', 't', 'qp', 'qpr', 'q', 'cs', 'c', 'e', 'price', 'pnl', 'value'])
    else:
        df['qp'] = -df.q * df.p

        reinvested_recs = df[df.r == True]
        df['qpr'] = reinvested_recs.qp - reinvested_recs.c

        pnl = pd.pivot_table(df, index=["a", "t"],
                             aggfunc={'qp': np.sum, 'qpr': np.sum, 'q': np.sum, 'cs': np.max, 'c': np.sum, 'e': 'first'}
                             ).reset_index(['a', 't'])
        pnl['price'] = pnl.apply(lambda x: price_mapper(x, d), axis=1)
        pnl['pnl'] = pnl.cs * (pnl.qp + pnl.q * pnl.price) - pnl.c
        pnl['value'] = pnl.cs * pnl.q * pnl.price

    # Need to add cash flow to cash records for each account.
    pnl['cash_flow'] = pnl.qp - pnl.c - pnl.qpr

    # The full pnl for futures should be added to cash
    # The cs * sum(q*p) for everything else, not the pnl, should be added to cash
    # Pivot on these to get cash contributions for each account

    futures_cash = pnl[~pnl.e.isin(NOT_FUTURES_EXCHANGES)]
    futures_cash = futures_cash.groupby('a')['pnl'].sum().reset_index()

    non_futures_cash = pnl[pnl.e.isin(NOT_FUTURES_EXCHANGES)]
    non_futures_cash = non_futures_cash.groupby('a')['cash_flow'].sum().reset_index()

    if futures_cash.empty:
        cash_adj = non_futures_cash
        cash_adj.rename(columns={'cash_flow': 'q'}, inplace=True)
    elif non_futures_cash.empty:
        cash_adj = futures_cash
        cash_adj.rename(columns={'pnl': 'q'}, inplace='True')
    else:
        cash_adj = pd.merge(futures_cash, non_futures_cash, how='outer', on='a')
        cash_adj.fillna(0, inplace=True)
        cash_adj['q'] = cash_adj.cash_flow + cash_adj.pnl
        cash_adj.drop(['cash_flow', 'pnl'], axis=1, inplace=True)

    cash = copy_cash_df(d=d, a=a, pivot=True, active_f=active_f)
    # if empty: cash = pd.DataFrame(columns=['a', 'q'])
    # concat with axis=1 is an outer join
    cash = pd.merge(cash, cash_adj, on='a', how='outer')
    cash.fillna(0, inplace=True)
    cash.q_x = cash.q_x + cash.q_y
    cash.drop(['q_y'], axis=1, inplace=True)
    cash.rename(columns={'q_x': 'q'}, inplace=True)

    return pnl, cash


def open_position_pnl(df):
    """
    :param df: trades dataframe
    :return: dataframe of open positions and pnl if realized today.
    """

    # Get only trades that are in position.
    pos = pd.pivot_table(df, index=["a", "t"], aggfunc={'q': np.sum, 'cs': 'first'}).reset_index(['a', 't'])
    pos = pos[pos.q != 0]
    df = pd.merge(df, pos, how='inner', on=['a', 't'])
    df.drop(['q_y', 'cs_y'], axis=1, inplace=True)
    df.rename(columns={'q_x': 'q', 'cs_x': 'cs'}, inplace=True)

    df = df.groupby(['a', 't']).apply(wap_calc).reset_index(name='wap')

    df = pd.merge(df, pos, how='inner', on=['a', 't'])

    df['price'] = df.apply(lambda x: price_mapper(x, d=date.today()), axis=1)

    df['pnl'] = df.cs * df.q * (df.price - df.wap)

    df.sort_values(by=["pnl"], ignore_index=True, inplace=True)

    return df
