from django.db import models
from django.dispatch import receiver
from django.db.models.signals import pre_save

NOT_FUTURES_EXCHANGES = ['CASH', 'STOCK', 'BOND', 'ARCA', 'SMART']
EXCHANGES = [(i, i) for i in NOT_FUTURES_EXCHANGES + ['CME', 'NYM', 'NYMEX', 'NYBOT', 'NYB', 'CFE', 'ECBOT']]
MAX_EXCHANGES_LEN = max([len(i[0]) for i in EXCHANGES]) + 1


class Market(models.Model):
    symbol = models.CharField(max_length=20, unique=True, blank=False, null=False)
    name = models.CharField(max_length=50)
    ib_exchange = models.CharField(max_length=MAX_EXCHANGES_LEN, choices=EXCHANGES,
                                   blank=False, default='STOCK')
    yahoo_exchange = models.CharField(max_length=MAX_EXCHANGES_LEN, choices=EXCHANGES,
                                      blank=False, default='STOCK')
    cs = models.FloatField(default=1.0, blank=False)
    commission = models.FloatField(default=0.0)
    ib_price_factor = models.FloatField(default=1.0, blank=False)
    yahoo_price_factor = models.FloatField(default=1.0, blank=False)
    pprec = models.IntegerField(default=4, blank=False)

    def __str__(self):
        return f"{self.symbol}"

    def description(self):
        return f'{self.symbol}|{self.name}|{self.ib_exchange}|{self.yahoo_exchange}|{self.cs}|' \
               f'{self.commission}|{self.ib_price_factor}|{self.yahoo_price_factor}'

    @property
    def is_futures(self):
        return self.ib_exchange not in NOT_FUTURES_EXCHANGES


@receiver(pre_save, sender=Market)
def upcase_symbol(sender, instance, **kwargs):
    instance.symbol = instance.symbol.upper()


class Ticker(models.Model):
    ticker = models.CharField(max_length=20, unique=True, blank=False, null=False)
    market = models.ForeignKey(Market, on_delete=models.CASCADE)
    fixed_price = models.FloatField(null=True, blank=True,
                                    help_text="If set then this is the price that will always be used.")

    def __str__(self):
        return f"{self.ticker}"

    @property
    def year(self):
        if self.market.is_futures:
            y = int(self.ticker[-4:])
        else:
            y = None
        return y

    @property
    def month(self):
        if self.market.is_futures:
            m = self.ticker[-5:-4]
        else:
            m = None
        return m

    @property
    def symbol(self):
        return self.market.symbol

    @property
    def yahoo_ticker(self):
        ticker = self.ticker
        e = self.market.yahoo_exchange
        if e in NOT_FUTURES_EXCHANGES:
            return ticker

        ticker = ticker[:-4] + ticker[-2:] + '.' + e
        return ticker

    def __lt__(self, other):
        return (self.symbol, self.year, self.month) < (other.symbol, other.year, other.month)

    @staticmethod
    def key_sorting(obj):
        return (obj.record.code, obj.code)

    @property
    def is_futures(self):
        return self.market.yahoo_exchange not in NOT_FUTURES_EXCHANGES


@receiver(pre_save, sender=Ticker)
def upcase_ticker(sender, instance, **kwargs):
    instance.ticker = instance.ticker.upper()


class DailyPrice(models.Model):
    ticker = models.ForeignKey(Ticker, on_delete=models.CASCADE)
    d = models.DateField(null=False)
    c = models.FloatField(help_text='Closing Price')

    class Meta:
        unique_together = [["ticker", "d"]]

    def __str__(self):
        return f"{self.d} {self.c}"


class TBGDailyBar(models.Model):
    ticker = models.ForeignKey(Ticker, on_delete=models.CASCADE)
    d = models.DateField(null=False)
    o = models.FloatField()
    h = models.FloatField()
    l = models.FloatField()
    c = models.FloatField()
    v = models.FloatField()
    oi = models.FloatField()

    class Meta:
        unique_together = [["ticker", "d"]]

    def __str__(self):
        return f"{self.d}|{self.o}|{self.h}|{self.l}|{self.c}|{self.v}|{self.oi}"
