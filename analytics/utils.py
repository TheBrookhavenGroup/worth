from datetime import date
import json
import pandas as pd
from moneycounter import realized_gains
from tbgutils.dt import lbd_prior_month
from tbgutils.str import cround, is_not_near_zero
from trades.models import (get_non_qualified_equity_trades_df,
                           NOT_FUTURES_EXCHANGES)
from trades.utils import pnl_asof
from accounts.models import get_expenses_df, get_income_df


def roi(initial, delta):
    if is_not_near_zero(initial):
        return delta / initial

    return 0


def format_realized_rec(a, t, realized):
    realized = cround(realized, 2)
    return [a, t, realized]


def total_realized_gains(year):
    eoy = lbd_prior_month(date(year, 1, 1))

    # Equity Gains
    trades_df = get_non_qualified_equity_trades_df()
    realized = realized_gains(trades_df, year)

    # Futures Gains
    pnl, _ = pnl_asof(only_non_qualified=True)
    pnl_eoy, _ = pnl_asof(d=eoy, only_non_qualified=True)

    pnl = pnl[~pnl.e.isin(NOT_FUTURES_EXCHANGES)]
    pnl_eoy = pnl_eoy[~pnl_eoy.e.isin(NOT_FUTURES_EXCHANGES)]
    df = pd.merge(pnl, pnl_eoy, on=['a', 't'], how='outer',
                  suffixes=('', '_year'))
    df = df.fillna(value=0)

    df['realized'] = df.pnl - df.pnl_year
    df = pd.DataFrame({'a': df.a, 't': df.t, 'realized': df.realized})

    df = df[df.realized != 0]

    realized = pd.concat([realized, df])

    total = pd.DataFrame({'a': ['Total'], 't': [''],
                          'realized': [realized.realized.sum()]})

    realized = pd.concat([realized, total])

    return realized, format_realized_rec


def format_income_rec(vendor, description, amount):
    amount = cround(amount, 2)
    return vendor, description, amount


def income(year):
    income_df = get_income_df(year)

    income_df = income_df.pivot_table(index=['client'], values='amt',
                                      aggfunc='sum')
    income_df = income_df.reset_index().set_index(['client'])
    income_df = income_df.sort_index()
    income_df = income_df.reset_index()

    # Add row with total of amount
    total = pd.DataFrame({'client': ['Total'], 'amt': [income_df.amt.sum()]})
    income_df = pd.concat([income_df, total])

    formats = json.dumps(
        {'columnDefs': [{"targets": [0], 'className': "dt-body-left"},
                        {"targets": [1], 'className': "dt-body-right"}],
         'ordering': False,
         'pageLength': 100})

    return income_df, formats


def format_expense_rec(vendor, description, amount):
    amount = cround(amount, 2)
    return vendor, description, amount


def expenses(year):
    expenses_df = get_expenses_df(year)

    expenses_df = expenses_df.pivot_table(index=['description', 'vendor'],
                                          values='amt', aggfunc='sum')
    expenses_df = expenses_df.reset_index().set_index(['vendor', 'description'])
    expenses_df = expenses_df.sort_index()
    expenses_df = expenses_df.reset_index()

    # Add row with total of amount
    total = pd.DataFrame({'vendor': ['Total'], 'description': [''],
                          'amt': [expenses_df.amt.sum()]})
    expenses_df = pd.concat([expenses_df, total])

    formats = json.dumps(
        {'columnDefs': [{"targets": [0, 1], 'className': "dt-body-left"},
                        {"targets": [2], 'className': "dt-body-right"}],
         'ordering': False,
         'pageLength': 100})

    return expenses_df, formats
