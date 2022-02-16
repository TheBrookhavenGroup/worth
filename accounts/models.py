from django.db import models


class Account(models.Model):
    name = models.CharField(max_length=50, unique=True, blank=False)
    owner = models.CharField(max_length=50)
    broker = models.CharField(max_length=50)
    broker_account = models.CharField(max_length=50, unique=True, blank=False)
    description = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"{self.name}"


def get_bofa_account():
    return Account.objects.get(name='BofA')


class CashRecord(models.Model):
    UNSPECIFIED = 'U'
    ATM = 'A'
    BILL_PAY = 'B'
    CELL_PHONE_DEPOSIT = 'C'
    AUTO_DEDUCTED = 'D'
    ELECTRONIC_TRANSFER = 'E'
    PAID_ON_IRS_SITE = 'I'
    DEBIT_CARD = 'M'
    TRANSFER_TO_SAVINGS = 'S'
    PAYPAL = 'P'
    TRANSFER = 'T'
    ZELLE = 'Z'

    TYPE_CHOICES = [
        (UNSPECIFIED, ''),
        (ATM, 'ATM'),
        (BILL_PAY, 'Bill Pay'),
        (CELL_PHONE_DEPOSIT, 'Cell Phone Depoist'),
        (AUTO_DEDUCTED, 'Auto Deducted'),
        (ELECTRONIC_TRANSFER, 'Electronic Transfer'),
        (PAID_ON_IRS_SITE, 'Paid on IRS Site'),
        (DEBIT_CARD, 'Debit Card'),
        (TRANSFER_TO_SAVINGS, 'Transfer to Savings'),
        (PAYPAL, 'PayPal'),
        (TRANSFER, 'Transfer'),
        (ZELLE, 'Zelle')
    ]

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
    ignored = models.BooleanField(default=False)
    d = models.DateField()
    type = models.CharField(max_length=1, choices=TYPE_CHOICES, default=UNSPECIFIED)
    category = models.CharField(max_length=3, choices=CATEGORY_CHOICES, default=GN)
    description = models.CharField(max_length=180)
    amt = models.FloatField()
    cleared_f = models.BooleanField(default=False)
