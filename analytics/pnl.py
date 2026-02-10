import numpy as np
import pandas as pd
from datetime import date
from collections import OrderedDict
import json
from tbgutils.str import cround, is_near_zero
from worth.utils import df_to_jqtable
from tbgutils.dt import our_now, lbd_prior_month, prior_business_day
from moneycounter.pnl import pnl_calc
from markets.models import get_ticker, NOT_FUTURES_EXCHANGES, DailyPrice, Ticker
from analytics.models import PPMResult
from trades.models import copy_trades_df, bucketed_trades
from trades.utils import pnl_asof, open_position_pnl
from markets.utils import ticker_url, get_price
from accounts.utils import get_account_url


def format_rec(a, t, pos=0, price=1, value=0, daily=0, mtd=0, ytd=0, pnl=0):
    if a == "TOTAL":
        return [
            a,
            "",
            "",
            "",
            cround(value, 2),
            cround(daily, 2),
            cround(mtd, 2),
            cround(ytd, 0),
            "",
        ]

    if a == "ALL COH":
        return [a, "", "", "", cround(value, 0), "", "", "", ""]

    t = get_ticker(t)
    pprec = t.market.pprec
    vprec = t.market.vprec
    t = ticker_url(t)

    pos = cround(pos, 0)
    if is_near_zero(price):
        price = ""
    else:
        price = cround(price, pprec)

    if is_near_zero(value):
        value = ""
    else:
        value = cround(value, vprec)
    if is_near_zero(daily):
        daily = ""
    else:
        # Show just the rounded daily value; percent not available here
        daily = f"{cround(daily, 2)}"
    mtd = cround(mtd, 2)
    ytd = cround(ytd, 0)
    if is_near_zero(pnl):
        pnl = ""
    else:
        pnl = cround(pnl, vprec)

    a = get_account_url(a)
    return [a, t, pos, price, value, daily, mtd, ytd, pnl]


def daily_pos(a=None):
    """
    Build a dataframe of daily opening/closing positions per ticker using
    trades.models.bucketed_trades().

    Args:
        a: Optional account name to filter trades. If None, uses all accounts.

    Returns:
        pandas.DataFrame with columns
        ['d', 'a', 'ticker', 'opening_pos', 'closing_pos']
        where positions are computed per account. If `a` is provided, only that
        account is included; otherwise, rows are per-account rather than
        aggregated across accounts.
    """
    trades_df = bucketed_trades(a=a)
    if trades_df is None or trades_df.empty:
        return pd.DataFrame(columns=["d", "a", "ticker", "opening_pos", "closing_pos"])

    # Aggregate net traded quantity per (date, ticker)
    dq = (
        trades_df[["d", "a", "t", "q"]]
        .groupby(["d", "a", "t"], as_index=False)["q"]
        .sum()
        .rename(columns={"t": "ticker"})
    )

    if dq.empty:
        return pd.DataFrame(columns=["d", "a", "ticker", "opening_pos", "closing_pos"])

    # Sort by account, ticker then date to compute cumulative position per (a,t)
    dq.sort_values(["a", "ticker", "d"], inplace=True)
    dq["closing_pos"] = dq.groupby(["a", "ticker"])["q"].cumsum()
    dq["opening_pos"] = dq["closing_pos"] - dq["q"]

    pos_df = dq[["d", "a", "ticker", "opening_pos", "closing_pos"]].copy()
    pos_df.reset_index(drop=True, inplace=True)
    return pos_df, trades_df


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

    df = pd.merge(pnl_eod, pnl_eoy, on=["a", "t"], how="outer", suffixes=("_yesterday", "_year"))
    # Note: merge only uses suffixes if both df's have the same column headings.
    #        so this one wouldn't use them anyway
    df = pd.merge(df, pnl_total, on=["a", "t"], how="outer")
    df = pd.merge(df, pnl_eom, on=["a", "t"], how="outer", suffixes=("", "_month"))
    numeric_cols = df.select_dtypes(include="number").columns
    df[numeric_cols] = df[numeric_cols].fillna(value=0)

    result = pd.DataFrame(
        OrderedDict(
            (
                ("Account", df.a),
                ("Ticker", df.t),
                ("Pos", df.q),
                ("Price", df.price),
                ("Value", df.value),
                ("Today", df.pnl - df.pnl_yesterday),
                ("MTD", df.pnl - df.pnl_month),
                ("YTD", df.pnl - df.pnl_year),
                ("PnL", df.pnl),
            )
        )
    )

    # Remove old irrelevant records - things that did not have a position or
    # a trade this year.
    x = 0.001
    filter_index = result[
        (np.abs(result.Pos) < x) & (np.abs(result.YTD) < x) & (np.abs(result.Value) < x)
    ].index
    result.drop(filter_index, inplace=True)

    # Calculate Account Cash Balances
    cash = pd.merge(cash, cash_eod, how="outer", on="a", suffixes=("", "_eod"))
    cash = pd.merge(cash, cash_eom, how="outer", on="a", suffixes=("", "_eom"))
    cash = pd.merge(cash, cash_eoy, how="outer", on="a", suffixes=("", "_eoy"))
    numeric_cols = df.select_dtypes(include="number").columns
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
    cash.rename(columns={"a": "Account"}, inplace=True)
    cash["Ticker"] = "CASH"
    cash["Pos"] = cash_balance
    cash["Price"] = 1.0
    cash["Value"] = cash.Pos
    cash["Today"] = cash.Pos - q_eod
    cash["MTD"] = cash.Pos - q_eom
    cash["YTD"] = cash.Pos - q_eoy
    cash["PnL"] = 0

    for col in "q", "q_eod", "q_eom", "q_eoy":
        try:
            cash.drop([col], axis=1, inplace=True)
        except KeyError:
            pass

    today_total = result.Today.sum()
    mtd_total = result.MTD.sum()
    ytd_total = result.YTD.sum()
    pnl_total = result.PnL.sum()

    result = pd.concat([result, cash])
    result.reset_index(inplace=True, drop=True)

    cash_flags = result["Ticker"].apply(lambda x: get_ticker(x).market.is_cash)
    coh = result[cash_flags]

    try:
        coh = coh.Pos.sum()
    except AttributeError:
        coh = 0

    result.loc[len(result) + 1] = [
        "TOTAL",
        "",
        0,
        0,
        total_worth,
        today_total,
        mtd_total,
        ytd_total,
        pnl_total,
    ]
    result.loc[len(result) + 1] = ["ALL COH", "", "", "", coh, "", "", "", ""]

    return result, total_worth, today_total, pnl_total


def pnl_summary(d=None, a=None, active_f=True):
    result, total_worth, total_today, total_pnl = pnl(d=d, a=a, active_f=active_f)

    today = date.today()

    if not d:
        d = today

    if (a is None) and (d != today):
        PPMResult.objects.update_or_create(d=d, defaults={"value": total_worth})

    headings, data, formats = df_to_jqtable(df=result, formatter=format_rec)

    return headings, data, formats, total_worth, total_today, total_pnl


def format_if_closed(a, t, q=0, wap=0, cs=1, price=0, value=0, pnl=0):
    t = get_ticker(t)
    pprec = t.market.pprec
    vprec = t.market.vprec
    t = ticker_url(t)

    q = cround(q, 0)
    if is_near_zero(price):
        price = ""
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


def ticker_pnl(t, active_f=True):
    """
    What is the total pnl earned for the given ticker?
    :param t:
    :param active_f:
    :return:
    """

    df = copy_trades_df(t=t, active_f=active_f)
    if df.empty:
        return 0.0

    g1 = df.groupby(["a", "t"])[["cs", "q", "p"]]
    # Sum up pnl for all accounts
    total_pnl = 0.0
    for (_, ticker_symbol), g in g1:
        ticker = get_ticker(ticker_symbol)
        price = get_price(ticker)
        total_pnl += pnl_calc(g, price)

    return total_pnl


def performance():
    formats = json.dumps(
        {
            "columnDefs": [
                {"targets": [0], "className": "dt-nowrap"},
                {"targets": [1, 2, 3], "className": "dt-body-right"},
            ],
            "pageLength": 100,
        }
    )

    headings = ["Year", "Value ($)", "Gain ($)", "YTD ROI (%)"]

    d = date.today()
    n_months = 120

    dtes = [d, prior_business_day(d)] + [d := lbd_prior_month(d) for i in range(int(n_months))]
    dtes.reverse()
    d_exists = PPMResult.objects.filter(d__in=dtes).values_list("d", flat=True)
    for d in set(dtes) - set(d_exists):
        pnl_summary(d, active_f=False)
    values = PPMResult.objects.filter(d__in=dtes).order_by("d").values_list("value", flat=True)

    values = list(values)
    data = list(zip(dtes, values))

    # roll-up data by year
    years = sorted(list(set([d.year for d in dtes])))
    values = [[i for d, i in data if d.year == y][-1] for y in years]

    current_value = values[-1]
    total_gain = values[-1] - values[0]

    data = [
        [y, cround(i, 2), cround(i - j, 0), cround(i / j - 1, symbol="%")]
        for y, i, j in zip(years[1:], values[1:], values[:-1])
    ]

    totals = ["Total", cround(current_value, 2), cround(total_gain, 2), ""]
    data.append(totals)

    return headings, data, formats


def add_close_to_pos(pos_df):
    # If no positions, return as-is with an empty 'close' column
    if pos_df is None or len(pos_df) == 0:
        empty = pd.DataFrame(
            columns=["d", "ticker", "opening_pos", "closing_pos", "close"]
        )  # noqa: E501
        return empty

    # Fetch closing prices for each (d, ticker) present in pos_df
    dates = sorted(set(pos_df["d"].tolist()))
    tickers = sorted(set(pos_df["ticker"].tolist()))

    if dates and tickers:
        price_qs = DailyPrice.objects.filter(ticker__ticker__in=tickers, d__in=dates).values_list(
            "ticker__ticker", "d", "c"
        )
        prices = (
            pd.DataFrame.from_records(
                list(price_qs), columns=["ticker", "d", "close"]
            )  # noqa: E501
            if price_qs
            else pd.DataFrame(columns=["ticker", "d", "close"])  # noqa: E501
        )
    else:
        prices = pd.DataFrame(columns=["ticker", "d", "close"]).head(0)

    # Merge prices into positions
    pos_df = (
        pos_df.merge(prices, on=["ticker", "d"], how="left")
        if not prices.empty
        else pos_df.assign(close=pd.NA)
    )  # noqa: E501

    # Only keep close where there is a non-zero closing position
    if not pos_df.empty:
        mask_zero = pos_df["closing_pos"].fillna(0) == 0
        pos_df.loc[mask_zero, "close"] = pd.NA

    return pos_df


def daily_pnl(a=None, start=None, end=None):
    """
    Build a daily PnL dataframe per account and include ALL business days in
    the requested range, even if there were no trades that day.

    Returns (pnl_df, pos_df, trades_df)
    - pnl_df: DataFrame with columns ['d','a','pnl']
    - pos_df: DataFrame with columns
      ['d','a','ticker','opening_pos','closing_pos','close','d_prev','prev_close']
    - trades_df: DataFrame of bucketed trades (as returned by trades.models.bucketed_trades)
    """
    # All trades (bucketed to trading day) for the specified account
    trades_all = bucketed_trades(a=a)

    # Establish date range (inclusive) to cover all business days
    if start is None and end is None:
        if trades_all is not None and len(trades_all):
            start = trades_all["d"].min()
            end = trades_all["d"].max()
        else:
            # No trades at all and no range specified -> nothing to do
            empty_pnl = pd.DataFrame(columns=["d", "a", "pnl"])  # empty
            empty_pos = pd.DataFrame(
                columns=[
                    "d",
                    "a",
                    "ticker",
                    "opening_pos",
                    "closing_pos",
                    "close",
                    "d_prev",
                    "prev_close",
                ]
            )  # noqa: E501
            empty_trades = pd.DataFrame(columns=["d", "dt", "a", "t", "q", "p", "c", "r"])
            return empty_pnl, empty_pos, empty_trades
    elif start is None:
        start = end
    elif end is None:
        end = start

    # Business-day calendar for the full period
    dates_full = pd.bdate_range(start=start, end=end).date.tolist()
    if not dates_full:
        empty_pnl = pd.DataFrame(columns=["d", "a", "pnl"])  # no business days
        empty_pos = pd.DataFrame(
            columns=[
                "d",
                "a",
                "ticker",
                "opening_pos",
                "closing_pos",
                "close",
                "d_prev",
                "prev_close",
            ]
        )  # noqa: E501
        empty_trades = pd.DataFrame(columns=["d", "dt", "a", "t", "q", "p", "c", "r"])
        return empty_pnl, empty_pos, empty_trades

    # If there are no trades but an account was specified, still emit zero rows
    if trades_all is None or len(trades_all) == 0:
        accounts = [a] if a else []
        if not accounts:
            empty_pnl = pd.DataFrame(columns=["d", "a", "pnl"])
            empty_pos = pd.DataFrame(
                columns=[
                    "d",
                    "a",
                    "ticker",
                    "opening_pos",
                    "closing_pos",
                    "close",
                    "d_prev",
                    "prev_close",
                ]
            )  # noqa: E501
            empty_trades = pd.DataFrame(columns=["d", "dt", "a", "t", "q", "p", "c", "r"])
            return empty_pnl, empty_pos, empty_trades
        base = pd.MultiIndex.from_product([dates_full, accounts], names=["d", "a"]).to_frame(
            index=False
        )  # noqa: E501
        base["pnl"] = 0.0
        empty_pos = pd.DataFrame(
            columns=[
                "d",
                "a",
                "ticker",
                "opening_pos",
                "closing_pos",
                "close",
                "d_prev",
                "prev_close",
            ]
        )  # noqa: E501
        empty_trades = pd.DataFrame(columns=["d", "dt", "a", "t", "q", "p", "c", "r"])
        return base[["d", "a", "pnl"]], empty_pos, empty_trades

    trades_all = trades_all[trades_all["d"] <= end].copy()

    # Determine accounts to report
    accounts = [a] if a else sorted(trades_all["a"].dropna().unique().tolist())
    if not accounts:
        empty_pnl = pd.DataFrame(columns=["d", "a", "pnl"])  # empty
        empty_pos = pd.DataFrame(
            columns=[
                "d",
                "a",
                "ticker",
                "opening_pos",
                "closing_pos",
                "close",
                "d_prev",
                "prev_close",
            ]
        )  # noqa: E501
        empty_trades = pd.DataFrame(columns=["d", "dt", "a", "t", "q", "p", "c", "r"])
        return empty_pnl, empty_pos, empty_trades

    # Net traded quantity per (d,a,t)
    dq = (
        trades_all.groupby(["d", "a", "t"], as_index=False)["q"].sum().sort_values(["a", "t", "d"])
    )

    # Initial offsets (trades prior to start)
    pre_start = dq[dq["d"] < start]
    offsets = (
        pre_start.groupby(["a", "t"], as_index=False)["q"].sum().rename(columns={"q": "offset"})
    )

    # Daily net_q within [start, end] but reindexed to include all business days
    in_range = dq[dq["d"].between(start, end)]

    def _build_series(g):
        s = g.set_index("d")["q"]
        s = s.reindex(dates_full, fill_value=0.0)
        return s

    # Expand to all days for each (a,t)
    parts = []
    for (acc, tkr), g in in_range.groupby(["a", "t"], as_index=False):
        s = _build_series(g)
        df_part = s.reset_index().rename(columns={"index": "d", 0: "q"})
        df_part["a"] = acc
        df_part["t"] = tkr
        parts.append(df_part)

    # Also include pairs that only have pre-start offset (no trades in range)
    only_offsets = []
    for row in offsets.itertuples(index=False):
        acc, tkr = row.a, row.t
        if in_range[(in_range["a"] == acc) & (in_range["t"] == tkr)].empty:
            df_part = pd.DataFrame({"d": dates_full, "q": 0.0, "a": acc, "t": tkr})
            only_offsets.append(df_part)

    net_by_day = (
        pd.concat(parts + only_offsets, ignore_index=True)
        if (parts or only_offsets)
        else pd.DataFrame(columns=["d", "q", "a", "t"])
    )

    # Merge offsets and compute opening/closing positions across all days
    if len(net_by_day):
        net_by_day = net_by_day.merge(offsets, on=["a", "t"], how="left")
        net_by_day["offset"] = net_by_day["offset"].fillna(0.0)
        net_by_day.sort_values(["a", "t", "d"], inplace=True)
        net_by_day["closing_pos"] = (
            net_by_day.groupby(["a", "t"])
            .apply(lambda x: (x["offset"].iloc[0] + x["q"].cumsum()), include_groups=False)
            .reset_index(level=[0, 1], drop=True)
        )
        net_by_day["opening_pos"] = net_by_day["closing_pos"] - net_by_day["q"]
        pos_df = net_by_day.rename(columns={"t": "ticker"})[
            ["d", "a", "ticker", "opening_pos", "closing_pos"]
        ]
    else:
        pos_df = pd.DataFrame(columns=["d", "a", "ticker", "opening_pos", "closing_pos"]).head(0)

    # Attach prices and then fill missing using markets.utils.get_price
    pos_df = add_close_to_pos(pos_df)
    # General fallback: for any date where we have a non-zero closing position
    # but missing/zero close, fetch via get_price(ticker, d)
    try:
        if len(pos_df):
            need_close = pos_df["closing_pos"].fillna(0) != 0
            # Treat NA or 0.0 as missing
            close_missing = pos_df["close"].isna() | (
                pd.to_numeric(pos_df["close"], errors="coerce").fillna(0.0) == 0.0
            )
            need_close &= close_missing
            if need_close.any():
                need_pairs = pos_df.loc[need_close, ["ticker", "d"]].drop_duplicates()
                tickers_needed = sorted(set(need_pairs["ticker"]))
                t_map = {t.ticker: t for t in Ticker.objects.filter(ticker__in=tickers_needed)}
                price_map = {}
                for rec in need_pairs.itertuples(index=False):
                    tk = rec.ticker
                    dd = rec.d
                    t_obj = t_map.get(tk)
                    if t_obj is None:
                        continue
                    try:
                        p = get_price(t_obj, d=dd)
                        if p is not None and float(p) > 0:
                            price_map[(tk, dd)] = float(p)
                    except Exception:
                        # leave missing
                        pass
                if price_map:
                    keys = list(zip(pos_df["ticker"], pos_df["d"]))
                    mapped = pd.Series(keys).map(price_map)
                    # Only fill rows in need_close
                    pos_df.loc[need_close, "close"] = mapped.loc[need_close].combine_first(
                        pos_df.loc[need_close, "close"]
                    )

                # Last-chance per-row fill for any remaining rows still missing/zero
                # (defensive alignment with the Prices table shown in Daily Trades view)
                remaining = pos_df[need_close]
                remaining_mask = remaining["close"].isna() | (
                    pd.to_numeric(remaining["close"], errors="coerce").fillna(0.0) <= 0.0
                )
                if remaining_mask.any():
                    for idx, row in remaining.loc[remaining_mask].iterrows():
                        t_obj = t_map.get(row["ticker"]) if "t_map" in locals() else None
                        try:
                            if t_obj is None:
                                t_obj = Ticker.objects.filter(ticker=row["ticker"]).first()
                            if t_obj is not None:
                                p = get_price(t_obj, d=row["d"])
                                if p is not None and float(p) > 0:
                                    pos_df.at[idx, "close"] = float(p)
                        except Exception:
                            # keep as missing if any error
                            pass
    except Exception:
        # Continue even if price fetch fails
        pass
    if len(pos_df):
        d_prev_map = {d0: prior_business_day(d0) for d0 in dates_full}
        prev_dates = sorted(set(d_prev_map.values()))
        tickers = sorted(set(pos_df["ticker"].tolist()))
        if tickers and prev_dates:
            price_prev_qs = DailyPrice.objects.filter(
                ticker__ticker__in=tickers, d__in=prev_dates
            ).values_list("ticker__ticker", "d", "c")
            prev_prices = (
                pd.DataFrame.from_records(
                    list(price_prev_qs), columns=["ticker", "d_prev", "prev_close"]
                )  # noqa: E501
                if price_prev_qs
                else pd.DataFrame(columns=["ticker", "d_prev", "prev_close"])
            )
        else:
            prev_prices = pd.DataFrame(columns=["ticker", "d_prev", "prev_close"]).head(0)

        pos_df["d_prev"] = pos_df["d"].map(d_prev_map)
        if not prev_prices.empty:
            pos_df = pd.merge(pos_df, prev_prices, on=["ticker", "d_prev"], how="left")
        else:
            pos_df["prev_close"] = pd.NA

        # Fallback for prev_close: if opening_pos != 0 and prev_close missing/zero
        try:
            need_prev = pos_df["opening_pos"].fillna(0) != 0
            prev_missing = pos_df["prev_close"].isna() | (
                pd.to_numeric(pos_df["prev_close"], errors="coerce").fillna(0.0) == 0.0
            )
            need_prev &= prev_missing & pos_df["d_prev"].notna()
            if need_prev.any():
                need_prev_pairs = pos_df.loc[need_prev, ["ticker", "d_prev"]].drop_duplicates()
                need_prev_pairs.rename(columns={"d_prev": "d"}, inplace=True)
                tickers_prev = sorted(set(need_prev_pairs["ticker"]))
                t_map_prev = {t.ticker: t for t in Ticker.objects.filter(ticker__in=tickers_prev)}
                prev_price_map = {}
                for rec in need_prev_pairs.itertuples(index=False):
                    tk = rec.ticker
                    dd = rec.d
                    t_obj = t_map_prev.get(tk)
                    if t_obj is None:
                        continue
                    try:
                        p = get_price(t_obj, d=dd)
                        if p is not None and float(p) > 0:
                            prev_price_map[(tk, dd)] = float(p)
                    except Exception:
                        pass
                if prev_price_map:
                    keys_prev = list(zip(pos_df["ticker"], pos_df["d_prev"]))
                    mapped_prev = pd.Series(keys_prev).map(prev_price_map)
                    pos_df.loc[need_prev, "prev_close"] = mapped_prev.loc[need_prev].combine_first(
                        pos_df.loc[need_prev, "prev_close"]
                    )

                # Last-chance per-row fill for any remaining prev_close still missing/zero
                remaining_prev = pos_df[need_prev]
                remaining_prev_mask = remaining_prev["prev_close"].isna() | (
                    pd.to_numeric(remaining_prev["prev_close"], errors="coerce").fillna(0.0) <= 0.0
                )
                if remaining_prev_mask.any():
                    for idx, row in remaining_prev.loc[remaining_prev_mask].iterrows():
                        t_obj = t_map_prev.get(row["ticker"]) if "t_map_prev" in locals() else None
                        try:
                            if t_obj is None:
                                t_obj = Ticker.objects.filter(ticker=row["ticker"]).first()
                            if t_obj is not None and pd.notna(row.get("d_prev")):
                                p = get_price(t_obj, d=row["d_prev"])
                                if p is not None and float(p) > 0:
                                    pos_df.at[idx, "prev_close"] = float(p)
                        except Exception:
                            pass
        except Exception:
            pass

    # Contract size per ticker
    cs_map = {}
    try:
        tickers_all = sorted(set(pos_df["ticker"].tolist()))
        if tickers_all:
            tcs = Ticker.objects.filter(ticker__in=tickers_all).values_list("ticker", "market__cs")
            cs_map = {t: float(cs) for t, cs in tcs}
    except Exception:
        cs_map = {}

    # Synthetic opening trades
    open_syn_cols = ["d", "a", "t", "cs", "q", "p", "c"]
    if len(pos_df):
        open_mask = pos_df["opening_pos"].fillna(0) != 0
        open_df = pos_df.loc[open_mask, ["d", "a", "ticker", "opening_pos", "prev_close"]].copy()
        open_df.rename(
            columns={"ticker": "t", "opening_pos": "q", "prev_close": "p"}, inplace=True
        )
        open_df["cs"] = open_df["t"].map(cs_map).astype(float)
        open_df["c"] = 0.0
        open_df = open_df.dropna(subset=["p", "cs"]) if len(open_df) else (open_df)
        open_df = open_df[open_syn_cols] if len(open_df) else open_df
    else:
        open_df = pd.DataFrame(columns=open_syn_cols).head(0)

    # Synthetic closing trades
    if len(pos_df):
        close_mask = pos_df["closing_pos"].fillna(0) != 0
        close_df = pos_df.loc[close_mask, ["d", "a", "ticker", "closing_pos", "close"]].copy()
        close_df.rename(columns={"ticker": "t", "closing_pos": "q", "close": "p"}, inplace=True)
        close_df["q"] = -close_df["q"]
        close_df["cs"] = close_df["t"].map(cs_map).astype(float)
        close_df["c"] = 0.0
        close_df = close_df.dropna(subset=["p", "cs"]) if len(close_df) else close_df
        close_df = close_df[open_syn_cols] if len(close_df) else close_df
    else:
        close_df = pd.DataFrame(columns=open_syn_cols).head(0)

    # Real trades in range only (also build a trades_df with full columns for callers)
    real_cols = ["d", "a", "t", "cs", "q", "p", "c"]
    if trades_all is not None and len(trades_all):
        in_range_mask = trades_all["d"].isin(dates_full)
        real_df = trades_all.loc[in_range_mask, ["d", "a", "t", "cs", "q", "p", "c"]].copy()
        # Expose the original bucketed trades with time/flags for the range
        trade_cols = [
            col for col in ["d", "dt", "a", "t", "q", "p", "c", "r"] if col in trades_all.columns
        ]
        trades_df = trades_all.loc[in_range_mask, trade_cols].copy()
    else:
        real_df = pd.DataFrame(columns=real_cols).head(0)
        trades_df = pd.DataFrame(columns=["d", "dt", "a", "t", "q", "p", "c", "r"]).head(0)

    # Combine all lines
    lines = [df for df in (open_df, close_df, real_df) if len(df)]
    all_lines = (
        pd.concat(lines, ignore_index=True) if lines else pd.DataFrame(columns=real_cols).head(0)
    )

    if len(all_lines):
        for col in ("cs", "q", "p", "c"):
            all_lines[col] = (
                pd.to_numeric(all_lines[col], errors="coerce").fillna(0.0).astype(float)
            )
        all_lines["val"] = all_lines["cs"] * all_lines["q"] * all_lines["p"]
        pnl_by_da = all_lines.groupby(["d", "a"], as_index=False).agg(
            val_sum=("val", "sum"), comm_sum=("c", "sum")
        )
        pnl_by_da["pnl"] = -pnl_by_da["val_sum"] - pnl_by_da["comm_sum"]
        pnl_df = pnl_by_da[["d", "a", "pnl"]]
    else:
        pnl_df = pd.DataFrame(columns=["d", "a", "pnl"]).head(0)

    # Ensure all business days are present for all accounts, filling  0
    base = pd.MultiIndex.from_product([dates_full, accounts], names=["d", "a"]).to_frame(
        index=False
    )
    pnl_full = base.merge(pnl_df, on=["d", "a"], how="left").fillna({"pnl": 0.0})
    pnl_full.sort_values(["d", "a"], inplace=True)
    pnl_full.reset_index(drop=True, inplace=True)
    # Return PnL, enriched positions dataframe, and bucketed trades in range
    return pnl_full[["d", "a", "pnl"]], pos_df, trades_df
