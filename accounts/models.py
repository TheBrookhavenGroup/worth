from datetime import date
from cachetools.func import lru_cache
import pandas as pd
from django.db.models import Sum
from django.db import models


class Account(models.Model):
    name = models.CharField(max_length=50, unique=True, blank=False)
    owner = models.CharField(max_length=50)
    broker = models.CharField(max_length=50)
    broker_account = models.CharField(max_length=50, unique=True, blank=False)
    description = models.CharField(max_length=200, blank=True)
    active_f = models.BooleanField(default=True)
    qualified_f = models.BooleanField(default=False, help_text='Tax status - set flag if account is qualified.')
    url = models.URLField(blank=True, null=True)
    reconciled_f = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name}"


def get_bofa_account():
    return Account.objects.get(name='BofA')


class Receivable(models.Model):
    invoiced = models.DateField(default=date.today)
    expected = models.DateField(blank=True, null=True)
    received = models.DateField(blank=True, null=True)
    client = models.CharField(max_length=100, blank=True)
    invoice = models.CharField(max_length=80, blank=True)
    amt = models.FloatField()


class CashRecord(models.Model):

    AB = 'AB'
    AV = 'AV'
    BF = 'BF'
    BNK = 'BNK'
    BM = 'BM'
    BH = 'BH'
    CH = 'CH'
    CE = 'CE'
    DE = 'DE'
    ED = 'ED'
    FC = 'FC'
    GN = 'GN'
    HO = 'HO'
    HS = 'HS'
    IN = 'IN'
    MD = 'MD'
    OL = 'OL'
    PR = 'PR'
    SA = 'SA'
    SB = 'SB'
    TA = 'TA'
    TX = 'TX'
    UT = 'UT'
    VA = 'VA'
    WA = 'WA'
    GB = 'GB'
    IT = 'IT'
    GU = 'GU'

    CATEGORY_CHOICES = [
        (AB, 'Avi Bar Mitzvah'),
        (AV, 'Deposit to Avi account'),
        (BF, 'Bank fee'),
        (BNK, 'Bank Check'),
        (BM, 'Bar Mitzvah'),
        (BH, 'Baltimore House'),
        (CH, 'Charity'),
        (CE, 'College Expenses'),
        (DE, 'Deposits'),
        (ED, 'Education/Lessons/Tutoring'),
        (FC, 'Food & Clothing'),
        (GN, 'General'),
        (HO, 'House - Mortgage/Rent/Maintenance/Renovation'),
        (HS, 'Health Savings Account'),
        (IN, 'Insurance'),
        (MD, 'Medical'),
        (OL, 'business officers loan to Brookhaven'),
        (PR, 'Professional'),
        (SA, 'Savings'),
        (SB, 'Sailboat'),
        (TA, 'Taxes and Accounting'),
        (UT, 'Utilities'),
        (VA, 'Vacation'),
        (WA, 'Wages from tutoring'),
        (GB, 'Gila Bat Mitzvah'),
        (IT, 'Interest'),
        (GU, 'Gila UTMA')
    ]

    account = models.ForeignKey(Account, on_delete=models.CASCADE, default=get_bofa_account)
    d = models.DateField()
    category = models.CharField(max_length=3, choices=CATEGORY_CHOICES, default=GN)
    description = models.CharField(max_length=180)
    amt = models.FloatField()
    cleared_f = models.BooleanField(default=False)
    ignored = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        get_cash_df.cache_clear()
        super().save(*args, **kwargs)


@lru_cache(maxsize=10)
def get_cash_df(a=None, d=None, pivot=False, active_f=True):
    qs = CashRecord.objects.filter(ignored=False)

    if active_f:
        qs = qs.filter(account__active_f=True)

    if d is not None:
        qs = qs.filter(d__lte=d)
    if a is not None:
        qs = qs.filter(account__name=a)

    qs = qs.values('account__name').order_by('account__name').annotate(total=Sum('amt'))

    columns = ['a', 'q']
    if len(qs):
        df = pd.DataFrame.from_records(list(qs))
        df.columns = columns
    else:
        df = pd.DataFrame(columns=columns)

    if pivot:
        df = df.groupby('a')['q'].sum().reset_index()

    return df


def copy_cash_df(d=None, a=None, pivot=False, active_f=True):
    df = get_cash_df(d=d, a=a, pivot=pivot, active_f=active_f)
    df = df.copy(deep=True)
    return df
