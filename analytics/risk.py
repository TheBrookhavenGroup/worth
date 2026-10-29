import pandas as pd

from analytics.pnl import daily_pnl
from accounts.models import TradeSize


def daily_returns(a=None, start=None, end=None):
    """
    Compute daily returns per account by dividing daily PnL by TradeSize.

    Parameters
    - a: optional account name (string) to filter
    - start, end: optional inclusive date range (date or str parsable by pandas)

    Returns
    - DataFrame with columns ['d', 'a', 'pnl', 'ts', 'ret'] where 'ret' = pnl / ts
      (ts is the TradeSize for that account/date). If TradeSize is missing or
      zero for a given row, 'ret' will be NaN.
    """

    pnl_df, _pos_df, _trades_df = daily_pnl(a=a, start=start, end=end)

    # Ensure expected columns exist even when empty
    if pnl_df is None or pnl_df.empty:
        return pd.DataFrame(columns=["d", "a", "pnl", "ts", "ret"])  # empty result

    # Load TradeSize data as a DataFrame with account name
    # IMPORTANT: we intentionally do NOT filter by start date so that earlier
    # trade sizes can carry forward to subsequent days. We only cap by end date.
    qs = TradeSize.objects.all()
    if a is not None:
        qs = qs.filter(a__name=a)
    # Determine the last date in the reporting range from pnl_df/end
    end_cap = end or pnl_df["d"].max()
    if end_cap is not None:
        qs = qs.filter(d__lte=end_cap)

    qs = qs.values_list("a__name", "d", "size")
    if len(qs):
        ts_df = pd.DataFrame.from_records(list(qs), columns=["a", "d", "ts"])
    else:
        ts_df = pd.DataFrame(columns=["a", "d", "ts"])

    # If there is no TradeSize data at all, return with ts and ret as NaN
    if ts_df.empty:
        merged = pnl_df.copy()
        merged["ts"] = pd.NA
        merged["ret"] = pd.NA
        return merged[["d", "a", "pnl", "ts", "ret"]]

    # To use merge_asof, convert dates to datetime64 and sort by account/date
    pnl_work = pnl_df[["d", "a", "pnl"]].copy()
    ts_work = ts_df.copy()
    pnl_work["_d_dt"] = pd.to_datetime(pnl_work["d"])
    ts_work["_d_dt"] = pd.to_datetime(ts_work["d"])

    pnl_work = pnl_work.sort_values(["a", "_d_dt"])  # type: ignore[arg-type]
    ts_work = ts_work.sort_values(["a", "_d_dt"])  # type: ignore[arg-type]

    # Align each pnl day with the latest TradeSize on or before that day per account
    merged = pd.merge_asof(
        pnl_work,
        ts_work[["a", "_d_dt", "ts"]],
        left_on="_d_dt",
        right_on="_d_dt",
        by="a",
        direction="backward",
        allow_exact_matches=True,
    )

    # Compute returns safely (NaN if ts missing or zero)
    merged["ret"] = merged.apply(
        lambda r: (r["pnl"] / r["ts"]) if pd.notna(r["ts"]) and r["ts"] else pd.NA,
        axis=1,
    )

    # Restore original schema
    merged["d"] = merged["d"].dt.date if hasattr(merged["d"], "dt") else merged["d"]
    return merged[["d", "a", "pnl", "ts", "ret"]]


def sharpe(
    df: pd.DataFrame, rf_daily: float = 0.0, periods_per_year: int = 252
) -> pd.Series | float:
    """
    Compute the Sharpe ratio from a DataFrame returned by ``daily_returns()``.

    Parameters
    - df: DataFrame with columns including 'ret' (daily simple returns) and optionally 'a' (account).
    - rf_daily: daily risk-free rate to subtract from returns (default 0.0).
    - periods_per_year: trading days per year for annualization (default 252).

    Returns
    - If multiple accounts are present, returns a Series indexed by account ('a') with annualized Sharpe ratios.
    - If a single account (or no 'a' column), returns a single float (annualized Sharpe).

    Notes
    - Sharpe = sqrt(periods_per_year) * mean(excess_return) / std(return)
    - Rows with missing/NaN returns are ignored. If std is zero or not computable, result is NaN.
    """

    if df is None or df.empty:
        # Empty input → NaN result matching expected output shape
        return float("nan")

    # Determine the returns column
    ret_col = "ret" if "ret" in df.columns else ("r" if "r" in df.columns else None)
    if ret_col is None:
        return float("nan")

    # Work on a copy to avoid side effects
    x = df[[c for c in [ret_col, "a"] if c in df.columns]].copy()
    x[ret_col] = pd.to_numeric(x[ret_col], errors="coerce")
    x = x.dropna(subset=[ret_col])

    if x.empty:
        return float("nan")

    def sharpe_from_series(s: pd.Series) -> float:
        s = pd.to_numeric(s, errors="coerce").dropna()
        if s.empty:
            return float("nan")
        excess = s - rf_daily
        vol = s.std(ddof=1)
        if vol == 0 or pd.isna(vol):
            return float("nan")
        return (excess.mean() / vol) * (periods_per_year**0.5)

    if "a" in x.columns and x["a"].nunique() > 1:
        result = x.groupby("a")[ret_col].apply(sharpe_from_series)
    else:
        result = sharpe_from_series(x[ret_col])

    return result


def volatility(df: pd.DataFrame, periods_per_year: int = 252) -> pd.Series | float:
    """
    Compute annualized volatility from a DataFrame returned by ``daily_returns()``.
    """
    if df is None or df.empty:
        return float("nan")

    ret_col = "ret" if "ret" in df.columns else ("r" if "r" in df.columns else None)
    if ret_col is None:
        return float("nan")

    x = df[[c for c in [ret_col, "a"] if c in df.columns]].copy()
    x[ret_col] = pd.to_numeric(x[ret_col], errors="coerce")
    x = x.dropna(subset=[ret_col])

    if x.empty:
        return float("nan")

    def vol_from_series(s: pd.Series) -> float:
        s = pd.to_numeric(s, errors="coerce").dropna()
        if s.empty:
            return float("nan")
        return s.std(ddof=1) * (periods_per_year**0.5)

    if "a" in x.columns and x["a"].nunique() > 1:
        return x.groupby("a")[ret_col].apply(vol_from_series)
    return vol_from_series(x[ret_col])


def total_return(df: pd.DataFrame) -> pd.Series | float:
    """
    Compute simple return by summing daily PnL / daily trade size.

    With constant trade size this equals total PnL / trade size.
    """
    if df is None or df.empty:
        return float("nan")

    ret_col = "ret" if "ret" in df.columns else ("r" if "r" in df.columns else None)
    if ret_col is None:
        return float("nan")

    x = df[[c for c in [ret_col, "a"] if c in df.columns]].copy()
    x[ret_col] = pd.to_numeric(x[ret_col], errors="coerce")
    x = x.dropna(subset=[ret_col])

    if x.empty:
        return float("nan")

    def tr_from_series(s: pd.Series) -> float:
        return s.sum()

    if "a" in x.columns and x["a"].nunique() > 1:
        return x.groupby("a")[ret_col].apply(tr_from_series)
    return tr_from_series(x[ret_col])


def annualized_return(df: pd.DataFrame, days_per_year: int = 365) -> pd.Series | float:
    """Annualize simple return using the inclusive calendar-day reporting span.

    Formula: (1 + sum(daily PnL / trade size)) ** (365 / days) - 1.
    Dates with missing returns still count toward elapsed time. Returns below
    -100% have no real geometric annualization and yield NaN.
    """
    if df is None or df.empty or "d" not in df.columns:
        return float("nan")

    ret_col = "ret" if "ret" in df.columns else ("r" if "r" in df.columns else None)
    if ret_col is None:
        return float("nan")

    def annualize(group):
        returns = pd.to_numeric(group[ret_col], errors="coerce").dropna()
        dates = pd.to_datetime(group["d"], errors="coerce").dropna()
        if returns.empty or dates.empty:
            return float("nan")
        days = (dates.max() - dates.min()).days + 1
        base = 1 + returns.sum()
        if base < 0:
            return float("nan")
        return base ** (days_per_year / days) - 1

    if "a" in df.columns and df["a"].nunique() > 1:
        return pd.Series({account: annualize(group) for account, group in df.groupby("a")})
    return annualize(df)


def maximum_drawdown(df: pd.DataFrame) -> pd.Series | float:
    """Largest peak-to-trough decline, displayed as a positive fraction.

    Use equity = 1 + cumulative sum of daily PnL / trade size, consistent
    with the performance view's cumulative return. Include starting equity
    of 1 so an initial loss counts. Sort dates within each account.
    """
    if df is None or df.empty:
        return float("nan")
    ret_col = "ret" if "ret" in df.columns else ("r" if "r" in df.columns else None)
    if ret_col is None:
        return float("nan")

    def drawdown(group):
        if "d" in group.columns:
            group = group.sort_values("d", kind="stable")
        returns = pd.to_numeric(group[ret_col], errors="coerce").dropna()
        if returns.empty:
            return float("nan")
        equity = 1 + returns.cumsum()
        peak = equity.cummax().clip(lower=1.0)
        return ((peak - equity) / peak).max()

    if "a" in df.columns and df["a"].nunique() > 1:
        return pd.Series({account: drawdown(group) for account, group in df.groupby("a")})
    return drawdown(df)


def maximum_drawdown_recovery(df: pd.DataFrame) -> pd.Series | float | int | None:
    """Calendar days from the first deepest trough to regaining its prior peak.

    None means not recovered by the last observation; NaN means unavailable.
    Zero drawdown has zero recovery days. Ties use the earliest trough.
    """
    if df is None or df.empty or "d" not in df.columns:
        return float("nan")
    ret_col = "ret" if "ret" in df.columns else ("r" if "r" in df.columns else None)
    if ret_col is None:
        return float("nan")

    def recovery(group):
        work = (
            pd.DataFrame(
                {
                    "d": pd.to_datetime(group["d"], errors="coerce"),
                    "r": pd.to_numeric(group[ret_col], errors="coerce"),
                }
            )
            .dropna()
            .sort_values("d", kind="stable")
            .reset_index(drop=True)
        )
        if work.empty:
            return float("nan")
        equity = 1 + work["r"].cumsum()
        peaks = equity.cummax().clip(lower=1.0)
        drawdowns = (peaks - equity) / peaks
        trough = drawdowns.idxmax()
        if drawdowns.iloc[trough] == 0:
            return 0
        recovered = equity.iloc[trough + 1 :]
        recovered = recovered[recovered >= peaks.iloc[trough] - 1e-12]
        if recovered.empty:
            return None
        return (work.loc[recovered.index[0], "d"] - work.loc[trough, "d"]).days

    if "a" in df.columns and df["a"].nunique() > 1:
        return pd.Series(
            {account: recovery(group) for account, group in df.groupby("a")}, dtype=object
        )
    return recovery(df)
