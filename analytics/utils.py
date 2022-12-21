from datetime import date
import pandas as pd
from moneycounter import realized_gains
from moneycounter.dt import lbd_prior_month
from worth.utils import cround, is_not_near_zero
from trades.models import get_non_qualified_equity_trades_df, NOT_FUTURES_EXCHANGES
from trades.utils import pnl_asof


def roi(initial, delta):
    if is_not_near_zero(initial):
        return delta / initial

    return 0


def format_realized_rec(a, t, realized):
    realized = cround(realized, 2)
    return [a, t, realized]


def total_realized_gains(year):
    d = date(year, 1, 1)
    eoy = lbd_prior_month(date(year, 1, 1))

    # Equity Gains
    trades_df = get_non_qualified_equity_trades_df()
    realized = realized_gains(trades_df, year)

    # Futures Gains
    pnl, _ = pnl_asof(only_non_qualified=True)
    pnl_eoy, _ = pnl_asof(d=eoy, only_non_qualified=True)

    pnl = pnl[~pnl.e.isin(NOT_FUTURES_EXCHANGES)]
    pnl_eoy = pnl_eoy[~pnl_eoy.e.isin(NOT_FUTURES_EXCHANGES)]
    df = pd.merge(pnl, pnl_eoy, on=['a', 't'], how='outer', suffixes=('', '_year'))
    df = df.fillna(value=0)

    df['realized'] = df.pnl - df.pnl_year
    df = pd.DataFrame({'a': df.a, 't': df.t, 'realized': df.realized})

    df = df[df.realized != 0]

    realized = pd.concat([realized, df])

    return realized, format_realized_rec
