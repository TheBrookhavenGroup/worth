from django.db import models
from django.db.models import Q
from markets.models import Ticker, NOT_FUTURES_EXCHANGES
from accounts.models import Account


class Trade(models.Model):
    dt = models.DateTimeField(null=False, blank=False)
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    ticker = models.ForeignKey(Ticker, on_delete=models.CASCADE)
    reinvest = models.BooleanField(default=True, blank=False, null=False)
    q = models.FloatField(blank=False, null=False)
    p = models.FloatField(blank=False, null=False)
    commission = models.FloatField(default=0.0)
    note = models.CharField(max_length=180, blank=True, null=True)

    def __str__(self):
        return f"{self.dt} {self.ticker.ticker} {self.q} @ {self.p}"

    def save(self, *args, **kwargs):
        if self.commission is None:
            self.commission = self.q * self.ticker.market.commission
        super().save(*args, **kwargs)

    def calc_commission(self):
        return self.q * self.ticker.market.commission

    @classmethod
    def more_filtering(cls, account, ticker):
        qs = Trade.objects
        if account is not None:
            account = account.upper()
            qs = qs.filter(account__name=account)

        if ticker is not None:
            ticker = ticker.upper()
            qs = qs.filter(ticker__ticker=ticker)

        return qs

    @classmethod
    def futures_trades(cls, account=None, ticker=None):
        qs = cls.more_filtering(account, ticker)
        return qs.filter(~Q(ticker__market__ib_exchange__in=(NOT_FUTURES_EXCHANGES)))

    @classmethod
    def equity_trades(cls, account=None, ticker=None):
        qs = cls.more_filtering(account, ticker)
        return qs.filter(ticker__market__ib_exchange__in=(NOT_FUTURES_EXCHANGES))
