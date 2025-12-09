import pandas as pd
from cachetools.func import lru_cache
from django.db import models
from django.db.models import Q
from django.core.validators import MinValueValidator
from django.conf import settings
from tbgutils.dt import day_start_next_day, next_business_day
from datetime import time, datetime, date as date_cls
from markets.models import Ticker, NOT_FUTURES_EXCHANGES
from accounts.models import Account


class Trade(models.Model):
    dt = models.DateTimeField(null=False, blank=False)
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    ticker = models.ForeignKey(Ticker, on_delete=models.CASCADE)
    reinvest = models.BooleanField(default=False, blank=False, null=False)
    q = models.DecimalField(max_digits=20, decimal_places=10, default=0,
                            blank=False, null=False)
    p = models.DecimalField(max_digits=20, decimal_places=10, default=0,
                            blank=False, null=False)
    commission = models.DecimalField(max_digits=20, decimal_places=10,
                                     default=0, blank=False, null=False,
                                     validators=[MinValueValidator(0.0)])
    note = models.CharField(max_length=180, blank=True, null=True)
    trade_id = models.IntegerField(blank=True, null=True)

    class Meta:
        ordering = ['dt']

    def __str__(self):
        return (f"{self.account} {self.dt} {self.ticker.ticker} {self.q} @ "
                f"{self.p} c={self.commission} id={self.trade_id}")

    def save(self, *args, **kwargs):
        get_trades_df.cache_clear()
        if self.commission is None:
            self.commission = abs(self.q * self.ticker.market.commission)
        elif self.commission < 0:
            self.commission = -self.commission
        super().save(*args, **kwargs)

    @classmethod
    def more_filtering(cls, account, ticker=None, only_non_qualified=False):
        qs = Trade.objects
        if account is not None:
            qs = qs.filter(account__name=account)

        if ticker is not None:
            if type(ticker) is str:
                ticker = ticker.upper()
                qs = qs.filter(ticker__ticker=ticker)
            else:
                qs = qs.filter(ticker=ticker)

        if only_non_qualified:
            qs = qs.filter(account__qualified_f=False)

        qs.order_by('dt')

        return qs

    @classmethod
    def futures_trades(cls, account=None, ticker=None,
                       only_non_qualified=False):
        if isinstance(account, str):
            account = Account.objects.get(name=account)
        qs = cls.more_filtering(account, ticker, only_non_qualified)
        return qs.filter(~Q(ticker__market__ib_exchange__in=(
            NOT_FUTURES_EXCHANGES))).order_by('dt')

    @classmethod
    def equity_trades(cls, account=None, ticker=None, only_non_qualified=False):
        if isinstance(account, str):
            account = Account.objects.get(name=account)
        qs = cls.more_filtering(account, ticker, only_non_qualified)
        return qs.filter(
            ticker__market__ib_exchange__in=(NOT_FUTURES_EXCHANGES)).order_by(
            'dt')

    @classmethod
    def any_trades(cls, account=None, ticker=None, only_non_qualified=False):
        if isinstance(account, str):
            account = Account.objects.get(name=account)
        qs = cls.more_filtering(account, ticker, only_non_qualified).order_by(
            'dt')
        return qs

    @classmethod
    def qs_to_df(cls, qs):
        fields = ('account__name', 'ticker__ticker',
                  'ticker__market__ib_exchange', 'ticker__market__cs',
                  'dt', 'q', 'p', 'commission', 'reinvest')

        qs = qs.values_list(*fields)
        columns = ['a', 't', 'e', 'cs', 'dt', 'q', 'p', 'c', 'r']
        if len(qs):
            df = pd.DataFrame.from_records(list(qs), coerce_float=True)
            df.columns = columns
        else:
            df = pd.DataFrame.from_records(list(qs), coerce_float=True,
                                           columns=columns)

        factor = settings.PPM_FACTOR
        if factor is not False:
            df.q *= factor

        # df = df.convert_dtypes(convert_string=True)
        return df


@lru_cache(maxsize=10)
def get_trades_df(a=None, t=None, only_non_qualified=False, active_f=True):
    #  Use copy_trades_df() which calls this to preserve the cached df
    qs = Trade.objects
    if a is not None:
        qs = qs.filter(account__name=a)

    if t is not None:
        qs = qs.filter(ticker__ticker=t)

    if active_f:
        qs = qs.filter(account__active_f=True)

    if only_non_qualified:
        qs = qs.filter(account__qualified_f=False)

    qs.order_by('dt')
    df = Trade.qs_to_df(qs)
    return df


def copy_trades_df(d=None, t=None, a=None, only_non_qualified=False,
                   active_f=True):
    df = get_trades_df(a=a, t=t, only_non_qualified=only_non_qualified,
                       active_f=active_f)
    df = df.copy(deep=True)
    if (not df.empty) and (d is not None):
        dt = day_start_next_day(d)
        mask = df['dt'] < dt
        df = df.loc[mask]
    return df


def bucketed_trades(d=None, t=None, a=None, only_non_qualified=False,
                    active_f=True):
    """
    Return trades dataframe bucketed by trading day per market close.

    Arguments are the same as `copy_trades_df`.
    - Gets a dataframe via `copy_trades_df`.
    - Adds a `d` column (date) for each trade such that if the trade's
      timestamp (in America/New_York) is later than the Market.t_close
      for its ticker, the date is moved to the next business day.
    """
    df = copy_trades_df(d=d, t=t, a=a, only_non_qualified=only_non_qualified,
                        active_f=active_f)

    if df.empty:
        return df

    # Normalize timestamps to America/New_York for trading-day bucketing
    # If values are tz-aware, convert to Eastern. If naive, assume they are
    # stored in local America/New_York wall time and localize accordingly.
    if not pd.api.types.is_datetime64_any_dtype(df['dt']):
        df['dt'] = pd.to_datetime(df['dt'], errors='coerce')
    if pd.api.types.is_datetime64tz_dtype(df['dt']):
        df['_dt_eastern'] = df['dt'].dt.tz_convert('America/New_York')
    else:
        # Naive timestamps -> interpret as America/New_York wall time
        df['_dt_eastern'] = (
            pd.to_datetime(df['dt'], errors='coerce')
            .dt.tz_localize('America/New_York')
        )

    # Map tickers to their market close times
    tickers = sorted(set(df['t'].dropna().tolist()))
    if tickers:
        tclose_qs = (
            Ticker.objects
            .filter(ticker__in=tickers)
            .values_list('ticker', 'market__t_close')
        )
        tclose_map = {tkr: tc for tkr, tc in tclose_qs}
    else:
        tclose_map = {}

    def _trading_day_row(row):
        ts = row['_dt_eastern']
        tkr = row['t']
        d0 = ts.date()
        # If weekend, always move to next business day
        if ts.weekday() >= 5:
            return next_business_day(d0)
        t_close = tclose_map.get(tkr)
        cutoff_time = t_close if t_close is not None else time(18, 0)
        cutoff_local = pd.Timestamp(datetime.combine(d0, cutoff_time),
                                    tz='America/New_York')
        return d0 if ts <= cutoff_local else next_business_day(d0)

    df['d'] = df.apply(_trading_day_row, axis=1)
    # Ensure 'd' is a pure date column (not datetime/timestamp)
    df['d'] = df['d'].apply(lambda x: x if isinstance(x, date_cls) else
                getattr(x, 'date', lambda: x)())

    # Drop helper column used for computation
    if '_dt_eastern' in df.columns:
        df.drop(columns=['_dt_eastern'], inplace=True)

    return df


def get_non_qualified_equity_trades_df(active_f=True):
    qs = Trade.equity_trades(only_non_qualified=True)
    if active_f:
        qs = qs.filter(account__active_f=True)
    qs = qs.order_by('dt')
    return Trade.qs_to_df(qs)
