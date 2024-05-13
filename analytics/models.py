from datetime import date
from django.db import models


class PPMResult(models.Model):
    d = models.DateField(default=date.today, unique=True)
    value = models.FloatField()

    def __str__(self):
        return f"{self.d} {self.value / 1.e6:.3f}M"
