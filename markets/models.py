from django.db import models

NOT_FUTURES_EXCHANGES = ['CASH', 'STOCK', 'ARCA', 'SMART']
EXCHANGES = [(i, i) for i in NOT_FUTURES_EXCHANGES + ['CME', 'NYM', 'NYBOT', 'NYB']]
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


class Ticker(models.Model):
    ticker = models.CharField(max_length=20, unique=True, blank=False, null=False)
    market = models.ForeignKey(Market, on_delete=models.CASCADE)
    fixed_price = models.FloatField(null=True, blank=True,
                                    help_text="If set then this is the price that will always be used.")

    def __str__(self):
        return f"{self.ticker}"

    @property
    def year(self):
        if market.is_futures:
            y = int(market.symbol[-4:])
        else:
            y = None
        return y

    @property
    def month(self):
        if market.is_futures:
            y = int(market.symbol[-5:-4])
        else:
            y = None
        return y

    @property
    def yahoo_ticker(self):
        return self.ticker


class DailyBar(models.Model):
    ticker = models.ForeignKey(Ticker, on_delete=models.CASCADE)
    d = models.DateField(null=False)
    o = models.FloatField()
    h = models.FloatField()
    l = models.FloatField()
    c = models.FloatField()
    v = models.FloatField()
    oi = models.FloatField()

    def __str__(self):
        return f"{self.o}|{self.h}|{self.l}|{self.c}|{self.v}|{self.oi}"
