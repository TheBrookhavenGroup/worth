from django.db import models
from markets.models import Ticker
from accounts.models import Account

class Trade(models.Model):
    dt = models.DateTimeField(null=False, blank=False)
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    ticker = models.ForeignKey(Ticker, on_delete=models.CASCADE)
    reinvest = models.BooleanField(default=True, blank=False, null=False)
    q = models.FloatField(blank=False, null=False)
    p = models.FloatField(blank=False, null=False)
    commission = models.FloatField(blank=True, null=False)
    note = models.CharField(max_length=180, blank=True, null=True)

    def __str__(self):
        return f"{self.dt} {self.ticker.ticker} {self.q} @ {self.p}"

    def save(self, *args, **kwargs):
        if self.commission is None:
            self.commission = self.q * self.ticker.market.commission
        super().save(*args, **kwargs)

    def calc_commission(self):
        return self.q * self.ticker.market.commission

