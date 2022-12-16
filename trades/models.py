import pandas as pd
from cachetools.func import lru_cache
from django.db import models
from django.db.models import Q
from django.core.validators import MinValueValidator
from django.conf import settings
from worth.dt import day_start_next_day
from markets.models import Ticker, NOT_FUTURES_EXCHANGES
from accounts.models import Account


class Trade(models.Model):
    dt = models.DateTimeField(null=False, blank=False)
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    ticker = models.ForeignKey(Ticker, on_delete=models.CASCADE)
    reinvest = models.BooleanField(default=False, blank=False, null=False)
    q = models.FloatField(blank=False, null=False)
    p = models.FloatField(blank=False, null=False)
    commission = models.FloatField(default=0.0, validators=[MinValueValidator(0.0)])
    note = models.CharField(max_length=180, blank=True, null=True)
    trade_id = models.IntegerField(blank=True, null=True)

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
            ticker = ticker.upper()
            qs = qs.filter(ticker__ticker=ticker)

        if only_non_qualified:
            qs = qs.filter(account__qualified_f=False)

        return qs

    @classmethod
    def futures_trades(cls, account=None, ticker=None, only_non_qualified=False):
        qs = cls.more_filtering(account, ticker, only_non_qualified)
        return qs.filter(~Q(ticker__market__ib_exchange__in=(NOT_FUTURES_EXCHANGES)))

    @classmethod
    def equity_trades(cls, account=None, ticker=None, only_non_qualified=False):
        qs = cls.more_filtering(account, ticker, only_non_qualified)
        return qs.filter(ticker__market__ib_exchange__in=(NOT_FUTURES_EXCHANGES))


def trades_qs_to_df(qs):
    fields = ('account__name', 'ticker__ticker',
              'ticker__market__ib_exchange', 'ticker__market__cs',
              'dt', 'q', 'p', 'commission', 'reinvest')

    qs = qs.values_list(*fields)
    df = pd.DataFrame.from_records(list(qs))

    df.columns = ['a', 't', 'e', 'cs', 'dt', 'q', 'p', 'c', 'r']

    factor = settings.PPM_FACTOR
    if factor is not False:
        df.q *= factor

    return df


@lru_cache(maxsize=10)
def get_trades_df(a=None, only_non_qualified=False):
    if a is not None:
        qs = Trade.objects.filter(account__name=a)
    else:
        qs = Trade.objects.filter(account__active_f=True)

    if only_non_qualified:
        qs = qs.filter(account__qualified_f=False)

    qs.order_by('dt')
    return trades_qs_to_df(qs)


def copy_trades_df(d=None, a=None, only_non_qualified=False):
    df = get_trades_df(a=a, only_non_qualified=only_non_qualified)
    df = df.copy(deep=True)
    if d is not None:
        dt = day_start_next_day(d)
        mask = df['dt'] < dt
        df = df.loc[mask]
    return df


def get_non_qualified_equity_trades_df():
    qs = Trade.equity_trades(only_non_qualified=True).order_by('dt')
    return trades_qs_to_df(qs)
