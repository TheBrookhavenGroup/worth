from django.db import models
from django.utils import timezone


class PPMResult(models.Model):
    dt = models.DateTimeField(default=timezone.now)
    value = models.FloatField()

    def __str__(self):
        return f"{self.dt} {self.value/1.e6:.3f}M"
