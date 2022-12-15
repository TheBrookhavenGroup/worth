from datetime import date
from worth.dt import lbd_prior_month, day_start_next_day, day_start
from worth.utils import is_not_near_zero
from trades.utils import pnl_asof
from trades.models import get_non_qualified_equity_trades_df


def pcnt_change(initial, final=None, delta=None):
    if is_not_near_zero(initial):
        if delta is None:
            delta = final - initial
        return delta / initial

    return 0


def taxable_gains(year):
    """
    Calculate taxable gains for the given year.
    That is gains from anything sold during that year.
    Also, YTD PnL for Futures trades and positions.

    Do not include retirement accounts.
    """

    d = date(year, 12, 31)
    eoy = lbd_prior_month(date(year, 1, 1))

    pnl_total, cash = pnl_asof(d=d)
    pnl_eoy, cash_eoy = pnl_asof(d=eoy)
    trades_df = get_non_qualified_equity_trades_df()

    # Find any stock sells this year
    t1 = day_start(date(year, 1, 1))
    t2 = day_start_next_day(date(year, 12, 31))
    mask = (trades_df['dt'] >= t1) & (trades_df['dt'] < t2) & (trades_df['q'] < 0)
    sells_df = trades_df.loc[mask]

    print(sells_df)

    # For each ticker in sells_df calculate realized and unrealized gains.
    # Remove all closed out trades using LIFO  ---- take a look at WAP..
    # Make a df for each account/ticker combination in sells_df
    #

    ...
    # TODO finish here
