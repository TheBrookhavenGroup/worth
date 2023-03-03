import pandas as pd
from cachetools.func import lru_cache
from django.db import models
from django.db.models import Q
from django.core.validators import MinValueValidator
from django.conf import settings
from moneycounter.dt import day_start_next_day
from markets.models import Ticker, NOT_FUTURES_EXCHANGES
from accounts.models import Account


class Trade(models.Model):
    dt = models.DateTimeField(null=False, blank=False)
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    ticker = models.ForeignKey(Ticker, on_delete=models.CASCADE)
    reinvest = models.BooleanField(default=False, blank=False, null=False)
    q = models.DecimalField(max_digits=20, decimal_places=10, default=0, blank=False, null=False)
    p = models.FloatField(blank=False, null=False)
    commission = models.FloatField(default=0.0, validators=[MinValueValidator(0.0)])
    note = models.CharField(max_length=180, blank=True, null=True)
    trade_id = models.IntegerField(blank=True, null=True)

    class Meta:
        ordering = ['dt']

    def __str__(self):
        return f"{self.account} {self.dt} {self.ticker.ticker} {self.q} @ {self.p} c={self.commission} id={self.trade_id}"

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
    def futures_trades(cls, account=None, ticker=None, only_non_qualified=False):
        if type(account) == str:
            account = Account.objects.get(name=account)
        qs = cls.more_filtering(account, ticker, only_non_qualified)
        return qs.filter(~Q(ticker__market__ib_exchange__in=(NOT_FUTURES_EXCHANGES))).order_by('dt')

    @classmethod
    def equity_trades(cls, account=None, ticker=None, only_non_qualified=False):
        if type(account) == str:
            account = Account.objects.get(name=account)
        qs = cls.more_filtering(account, ticker, only_non_qualified)
        return qs.filter(ticker__market__ib_exchange__in=(NOT_FUTURES_EXCHANGES)).order_by('dt')

    @classmethod
    def any_trades(cls, account=None, ticker=None, only_non_qualified=False):
        if type(account) == str:
            account = Account.objects.get(name=account)
        qs = cls.more_filtering(account, ticker, only_non_qualified).order_by('dt')
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
            df = pd.DataFrame.from_records(list(qs), coerce_float=True, columns=columns)

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


def copy_trades_df(d=None, t=None, a=None, only_non_qualified=False, active_f=True):
    df = get_trades_df(a=a, t=t, only_non_qualified=only_non_qualified, active_f=active_f)
    df = df.copy(deep=True)
    if (not df.empty) and (d is not None):
        dt = day_start_next_day(d)
        mask = df['dt'] < dt
        df = df.loc[mask]
    return df


def get_non_qualified_equity_trades_df(active_f=True):
    qs = Trade.equity_trades(only_non_qualified=True)
    if active_f:
        qs = qs.filter(account__active_f=True)
    qs = qs.order_by('dt')
    return Trade.qs_to_df(qs)
