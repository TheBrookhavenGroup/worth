
import numpy as np
import pandas as pd
from datetime import date, datetime, time
from collections import OrderedDict
import json
from tbgutils.str import cround, is_near_zero
from worth.utils import df_to_jqtable
from tbgutils.dt import our_now, lbd_prior_month, prior_business_day, next_business_day
from moneycounter.pnl import pnl_calc
from markets.models import get_ticker, NOT_FUTURES_EXCHANGES, DailyPrice, Ticker
from analytics.models import PPMResult
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

    if is_near_zero(value):
        value = ''
    else:
        value = cround(value, vprec)
    if is_near_zero(daily):
        daily = ''
    else:
        # Show just the rounded daily value; percent not available here
        daily = f"{cround(daily, 2)}"
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


def daily_pnl(a=None, start=None, end=None):
    """
    Build a daily PnL dataframe per account.

    Definition (synthetic-trade formulation):
      For each day d and (account a, ticker t), treat:
        - Opening position as a trade of quantity = start_pos at price = prior business day close.
        - Closing position as a trade of quantity = -close_pos at price = today's close.
      Combine these with any actual trades that day, and compute daily PnL as:
        PnL(d,a) = - Σ_t Σ_lines [ cs * q * p ] - Σ(commission)

    Args:
        a: optional account name to filter trades.
        start: optional inclusive start date (datetime.date).
        end: optional inclusive end date (datetime.date).

    Returns:
        pandas.DataFrame with columns ['d', 'a', 'open_value', 'close_value', 'pnl']
        sorted by date, account.
    """
    # Get trades (all time). We'll compute opening positions using ALL prior history,
    # and restrict real trades and output rows to the requested date range.
    df_all = copy_trades_df(a=a)
    if df_all.empty:
        return pd.DataFrame(columns=["d", "a", "open_value", "close_value", "pnl"])  # empty frame

    # Convert timestamp to US/Eastern and bucket to TRADING DAY using per-market t_close
    # Rule: trading day for a given market is from prior day t_close (exclusive)
    #       to current day t_close (inclusive). If trade time is after t_close, it
    #       belongs to the next business day. Weekends roll forward to next business day.
    df_all = df_all.copy()
    dt_series = pd.to_datetime(df_all["dt"], utc=True, errors="coerce")
    # If any values were NaT due to errors, try without forcing UTC and then localize
    if dt_series.isna().any():
        dt_alt = pd.to_datetime(df_all["dt"], errors="coerce")
        # localize naive to UTC for consistency
        dt_alt = dt_alt.dt.tz_localize('UTC')
        dt_series = dt_alt.fillna(dt_series)
    df_all["_dt_eastern"] = dt_series.dt.tz_convert('America/New_York')

    # Resolve per-ticker market close times
    tickers = sorted(set(df_all['t'].dropna().tolist()))
    if tickers:
        tclose_qs = (
            Ticker.objects
            .filter(ticker__in=tickers)
            .values_list('ticker', 'market__t_close')
        )
        tclose_map = {t: tc for t, tc in tclose_qs}
    else:
        tclose_map = {}

    def _trading_day_row(row):
        ts = row.get('_dt_eastern')
        t = row.get('t')
        if pd.isna(ts) or t is None:
            return None
        d0 = ts.date()
        # Weekend -> next business day
        if ts.weekday() >= 5:
            return next_business_day(d0)
        t_close = tclose_map.get(t)
        # Fallback to 18:00 if not found
        if t_close is None:
            cutoff_time = time(18, 0)
        else:
            cutoff_time = t_close
        cutoff_dt = ts.tz_convert('America/New_York').tzinfo  # ensure tz present
        # Build cutoff as local datetime
        cutoff_local = pd.Timestamp(datetime.combine(d0, cutoff_time), tz='America/New_York')
        if ts <= cutoff_local:
            return d0
        return next_business_day(d0)

    df_all["d"] = df_all.apply(_trading_day_row, axis=1)

    # Establish date range (inclusive)
    if end is None and start is None:
        # default to the dates present in the data: min..max of available trading days
        start = min(df_all["d"].min(), date.today())
        end = df_all["d"].max()
    elif start is None:
        start = end
    elif end is None:
        end = start

    target_mask = (df_all["d"] >= start) & (df_all["d"] <= end)

    # Build the list of BUSINESS days in the requested range (Mon–Fri only)
    # Weekends are excluded so we don't generate PnL rows for non-trading days.
    dates_full = pd.bdate_range(start=start, end=end).date.tolist()

    # Real trades strictly within the requested range
    df_range = df_all.loc[target_mask].copy()
    if df_range.empty:
        # Even if there are no trades in range, we may still have MTM if a position is carried.
        # We will continue using positions from prior history to compute MTM rows.
        pass

    # Collect dates we need closes for (include prior business day for each)
    dates = sorted(set(dates_full))
    # Map each date to its prior business day
    d_prev_map = {d0: prior_business_day(d0) for d0 in dates}
    prev_dates = sorted(set(d_prev_map.values()))
    all_price_dates = sorted(set(dates) | set(prev_dates))

    # --- Positions for synthetic trades ---
    # IMPORTANT: compute starting positions using ALL history up to each day,
    # not just trades within the requested range. Also produce rows for days with no trades
    # in the requested range so that pure MTM is captured.
    daily_q_all = (
        df_all.groupby(["a", "t", "cs", "d"], as_index=False)["q"]
        .sum()
        .sort_values(["a", "t", "d"]) 
    )

    # Compute cumulative up to the day before `start` to get opening offsets
    pre_mask = daily_q_all["d"] < start
    if not daily_q_all.empty and pre_mask.any():
        tmp = daily_q_all.copy()
        tmp["cum_q"] = tmp.groupby(["a", "t"])['q'].cumsum()
        offsets = (
            tmp[pre_mask]
            .sort_values(["a", "t", "d"])
            .groupby(["a", "t"], as_index=False)
            .tail(1)[["a", "t", "cum_q"]]
            .rename(columns={"cum_q": "offset"})
        )
    else:
        offsets = pd.DataFrame(columns=["a", "t", "offset"]).astype({"offset": float})

    # Keys for all (a,t,cs) combos with any history
    if not daily_q_all.empty:
        keys = daily_q_all[["a", "t", "cs"]].drop_duplicates()
    else:
        keys = pd.DataFrame(columns=["a", "t", "cs"]).head(0)

    # q over the requested dates only
    q_range = daily_q_all[daily_q_all["d"].isin(dates)][["a", "t", "cs", "d", "q"]].copy()

    # Cross join keys with dates to ensure a row per (a,t) per day
    if not keys.empty and dates:
        dates_df = pd.DataFrame({"d": dates})
        keys["_key"] = 1
        dates_df["_key"] = 1
        full = pd.merge(keys, dates_df, on="_key").drop(columns=["_key"])  # (a,t,cs) x dates
        full = pd.merge(full, q_range, on=["a", "t", "cs", "d"], how="left")
        full["q"] = full["q"].fillna(0.0)
        # attach offsets
        full = pd.merge(full, offsets, on=["a", "t"], how="left")
        full["offset"] = full["offset"].fillna(0.0)
        # compute start_pos as position at start of day (offset + cum of prior days in range)
        full = full.sort_values(["a", "t", "d"]).copy()
        full["cum_in_range"] = full.groupby(["a", "t"])['q'].cumsum()
        full["start_pos"] = full["offset"] + full.groupby(["a", "t"])['q'].cumsum().shift(1, fill_value=0)
        pos = full[["a", "t", "cs", "d", "start_pos", "q"]].reset_index(drop=True)
    else:
        pos = pd.DataFrame(columns=["a", "t", "cs", "d", "start_pos", "q"])  # no positions

    # Determine tickers to fetch prices for: any ticker appearing in pos (carried or traded)
    tickers = sorted(set(pos['t'].tolist())) if not pos.empty else []

    # Fetch closes from DailyPrice using ticker symbol and date for required tickers
    if tickers:
        prices_qs = (
            DailyPrice.objects
            .filter(ticker__ticker__in=tickers, d__in=all_price_dates)
            .values_list("ticker__ticker", "d", "c")
        )
        prices = (
            pd.DataFrame.from_records(list(prices_qs), columns=["t", "d", "close"]) if prices_qs
            else pd.DataFrame(columns=["t", "d", "close"])
        )
        # For cash tickers (no bars), synthesize closes using fixed_price if present
        ticker_objs = Ticker.objects.filter(ticker__in=tickers)\
            .values_list("ticker", "market__symbol", "fixed_price")
        to_df = (pd.DataFrame.from_records(list(ticker_objs),
                                          columns=["t", "symbol", "fixed_price"])
                 if ticker_objs else pd.DataFrame(columns=["t", "symbol", "fixed_price"]))
        cash_tickers = set()
        if not to_df.empty:
            cash_tickers = set(to_df[to_df.symbol.str.lower() == "cash"]["t"].tolist())
        if cash_tickers:
            cash_prices_rows = []
            fixed_price_map = {row.t: (1.0 if pd.isna(row.fixed_price) else float(row.fixed_price))
                               for row in to_df.itertuples(index=False)}
            for tkr in cash_tickers:
                for d0 in all_price_dates:
                    cash_prices_rows.append((tkr, d0, fixed_price_map.get(tkr, 1.0)))
            cash_prices = pd.DataFrame.from_records(cash_prices_rows, columns=["t", "d", "close"])
            prices = cash_prices if prices.empty else pd.concat([prices, cash_prices], ignore_index=True)
    else:
        prices = pd.DataFrame(columns=["t", "d", "close"]).head(0)

    # Attach today's and prior day's close prices
    pos_m = pd.merge(pos, prices, how="left", on=["t", "d"]) if not prices.empty else pos.copy()
    pos_m.rename(columns={"close": "close_d"}, inplace=True)
    pos_m["d_prev"] = pos_m["d"].map(d_prev_map)
    prev_prices = prices.copy()
    prev_prices.rename(columns={"d": "d_prev", "close": "close_prev"}, inplace=True)
    pos_m = pd.merge(pos_m, prev_prices, how="left", on=["t", "d_prev"]) if not prev_prices.empty else pos_m

    # Closing position = opening position + net trades of the day
    pos_m["close_pos"] = pos_m["start_pos"] + pos_m["q"].fillna(0)

    # Build synthetic opening and closing trades (commission = 0)
    open_syn = pos_m[["d", "a", "t", "cs", "start_pos", "close_prev"]].copy()
    open_syn.rename(columns={"start_pos": "q", "close_prev": "p"}, inplace=True)
    open_syn["c"] = 0.0

    close_syn = pos_m[["d", "a", "t", "cs", "close_pos", "close_d"]].copy()
    close_syn.rename(columns={"close_pos": "q", "close_d": "p"}, inplace=True)
    close_syn["q"] = -close_syn["q"]
    close_syn["c"] = 0.0

    # Filter out rows that have no exposure and no activity: start_pos == 0 and q == 0 and close_pos == 0
    # This prevents generating synthetic lines for dormant (a,t) on idle days.
    if not pos_m.empty:
        mask_active = (pos_m["start_pos"].abs() > 0) | (pos_m["q"].abs() > 0) | (pos_m["close_pos"].abs() > 0)
        pos_m = pos_m.loc[mask_active].copy()
        open_syn = open_syn.loc[mask_active].copy()
        close_syn = close_syn.loc[mask_active].copy()

    # Actual trades for the day (already filtered by date range)
    # Include 'dt' to preserve within-day order for position tracking
    real_trades = df_range[["d", "a", "t", "cs", "q", "p", "c", "dt"]].copy()

    # --- Price fallback policy: if a prev or close price is missing, use most recent prior price ---
    _px_cache = {}

    def _fallback_price(ticker_sym, on_date):
        key = (ticker_sym, on_date)
        if key in _px_cache:
            return _px_cache[key]
        rec = (
            DailyPrice.objects
            .filter(ticker__ticker=ticker_sym, d__lt=on_date)
            .order_by('-d')
            .values_list('c', flat=True)
            .first()
        )
        _px_cache[key] = float(rec) if rec is not None else None
        return _px_cache[key]

    # Ensure we have prev/close prices; if missing, fetch exact day price first,
    # then back-fill using most recent prior DB price as a last resort.
    if not pos_m.empty:
        need_prev = pos_m['close_prev'].isna()
        if need_prev.any():
            for idx in pos_m[need_prev].index:
                tkr = pos_m.at[idx, 't']
                dd_prev = pos_m.at[idx, 'd_prev']
                # Try exact price for prior business day
                try:
                    px = get_price(tkr, dd_prev) if pd.notna(dd_prev) else None
                except Exception:
                    px = None
                if px is None:
                    # Fallback to most recent prior available in DB
                    px = _fallback_price(tkr, dd_prev if pd.notna(dd_prev) else pos_m.at[idx, 'd'])
                if px is not None:
                    pos_m.at[idx, 'close_prev'] = float(px)
        need_close = pos_m['close_d'].isna()
        if need_close.any():
            for idx in pos_m[need_close].index:
                tkr = pos_m.at[idx, 't']
                dd = pos_m.at[idx, 'd']
                # Try exact price for the day
                try:
                    px = get_price(tkr, dd)
                except Exception:
                    px = None
                if px is None:
                    # Fallback to most recent prior available in DB
                    px = _fallback_price(tkr, dd)
                if px is not None:
                    pos_m.at[idx, 'close_d'] = float(px)

    # --- Synthetic-trade daily PnL per new definition ---
    # Construct combined lines: opening synthetic, actual trades, and closing synthetic.
    # Daily PnL(d,a) = - sum(cs * q * p) - sum(commission)

    # Prepare synthetic frames to align with real trades schema
    open_syn_use = open_syn.rename(columns={"p": "p", "q": "q"})["d a t cs q p c".split()].copy()
    close_syn_use = close_syn.rename(columns={"p": "p", "q": "q"})["d a t cs q p c".split()].copy()
    real_use = real_trades[["d", "a", "t", "cs", "q", "p", "c"]].copy()
    for fr in (open_syn_use, close_syn_use, real_use):
        if 'c' not in fr.columns:
            fr['c'] = 0.0
        fr['c'] = fr['c'].fillna(0.0)

    combined = pd.concat([open_syn_use, real_use, close_syn_use], ignore_index=True)
    if combined.empty:
        return pd.DataFrame(columns=["d", "a", "open_value", "close_value", "pnl"])  # unlikely, but safe

    # Compute open and close values for reference/reporting (not used by table view)
    pos_values = pos_m.copy()
    pos_values["open_value_line"] = pos_values["cs"] * pos_values["start_pos"] * pos_values["close_prev"]
    pos_values["close_value_line"] = pos_values["cs"] * pos_values["close_pos"] * pos_values["close_d"]
    oc = (
        pos_values.groupby(["d", "a"], as_index=False)[["open_value_line", "close_value_line"]]
        .sum()
        .rename(columns={"open_value_line": "open_value", "close_value_line": "close_value"})
    )

    combined['line_val'] = combined['cs'] * combined['q'] * combined['p']
    grouped = combined.groupby(["d", "a"], as_index=False).agg({"line_val": "sum", "c": "sum"})
    grouped.rename(columns={"line_val": "sum_val", "c": "commission"}, inplace=True)
    grouped["pnl"] = -grouped["sum_val"] - grouped["commission"]

    res = pd.merge(oc, grouped[["d", "a", "pnl"]], on=["d", "a"], how="right")
    # If open/close values are missing (e.g., no pos for that account-day), set to 0
    if 'open_value' not in res.columns:
        res['open_value'] = 0.0
    if 'close_value' not in res.columns:
        res['close_value'] = 0.0
    res[['open_value', 'close_value']] = res[['open_value', 'close_value']].fillna(0.0)

    res = res[["d", "a", "open_value", "close_value", "pnl"]].copy()
    res.sort_values(["d", "a"], inplace=True)
    res.reset_index(drop=True, inplace=True)
    return res
