from django.db import models


class Account(models.Model):
    name = models.CharField(max_length=50, unique=True, blank=False)
    owner = models.CharField(max_length=50)
    broker = models.CharField(max_length=50)
    broker_account = models.CharField(max_length=50, unique=True, blank=False)
    description = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"{self.name}"
