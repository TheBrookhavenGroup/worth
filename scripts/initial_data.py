import re
from django.db import transaction
from worth.utils import yyyymmdd2dt
from accounts.models import Account, CashRecord
from markets.models import Market, Ticker
from trades.models import Trade
from markets.utils import add_ticker


def add_accounts():
    data = [
        ['TDA', 'MSRK', 'TDA', '232-304102'],
        ['MSIRAIB', 'MS', 'IB', 'U4421888'],
        ['MSRKIB', 'MSRK', 'IB', 'U625895'],
        ['RKCSIRA2', 'RK', 'CS', '6624-0050'],
        ['TRP', 'RK', 'TRP', 'Plan ID 61475'],
        ['MSRKFidelity', 'MSRK', 'Fidelity', 'Z03-842406']
    ]
    for n, o, b, a in data:
        Account(name=n, owner=o, broker=b, broker_account=a).save()


def add_markets():
    data = [
        ['ZM', 'Zoom', 'ARCA', 'STOCK', 1, 0, 1, 1, 4],
        ['BEVVF', 'Bee Vectoring ADR', 'SMART', 'STOCK', 1, 0, 1, 1, 4],
        ['NFLX', 'Netflix', 'ARCA', 'STOCK', 1, 0, 1, 1, 4],
        ['BA', 'Boeing', 'ARCA', 'STOCK', 1, 0, 1, 1, 4],
        ['TSLA', 'Tesla', 'ARCA', 'STOCK', 1, 0, 1, 1, 4],
        ['PYPL', 'Paypal', 'ARCA', 'STOCK', 1, 0, 1, 1, 4],
        ['AAPL', 'Apple', 'ARCA', 'STOCK', 1, 0, 1, 1, 4],
        ['TWLO', 'Twilio', 'ARCA', 'STOCK', 1, 0, 1, 1, 4],
        ['MNDT', 'Mandiant', 'SMART', 'STOCK', 1, 0, 1, 1, 4],
        ['AMKR', 'Amkor', 'ARCA', 'STOCK', 1, 0, 1, 1, 4],
        ['DOCN', 'Digital Ocean', 'ARCA', 'STOCK', 1, 0, 1, 1, 4],
        ['NVDA', 'Nvidia', 'ARCA', 'STOCK', 1, 0, 1, 1, 4],
        ['OKTA', 'Okta', 'ARCA', 'STOCK', 1, 0, 1, 1, 4],
        ['MSFT', 'Microsoft', 'ARCA', 'STOCK', 1, 0, 1, 1, 4],
        ['CRM', 'Salesforce', 'ARCA', 'STOCK', 1, 0, 1, 1, 4],
        ['NG', 'Natural Gas Futures', 'CME', 'NYM', 10000, 2.36, 1, 1, 3],
        ['CL', 'Light Sweet Crude Oil Futures', 'CME', 'NYM', 1000, 2.36, 1, 1, 2],
        ['ES', 'E-Mini S&P 500 Futures', 'CME', 'CME', 50, 2.01, 1, 1, 2],
        ['KC', 'Coffee', 'NYBOT', 'NYB', 37500, 2.46, 1, 0.01, 4]
    ]
    for s, n, ie, ye, cs, c, ipf, ypf, pprec in data:
        Market(symbol=s, name=n, ib_exchange=ie, yahoo_exchange=ye, cs=cs, commission=c,
               ib_price_factor=ipf, yahoo_price_factor=ypf, pprec=pprec).save()

    data = [
        ['ZM', 'ZM'],
        ['BEVVF', 'BEVVF'],
        ['NFLX', 'NFLX'],
        ['BA', 'BA'],
        ['TSLA', 'TSLA'],
        ['PYPL', 'PYPL'],
        ['AAPL', 'AAPL'],
        ['TWLO', 'TWLO'],
        ['MNDT', 'MNDT'],
        ['AMKR', 'AMKR'],
        ['DOCN', 'DOCN'],
        ['NVDA', 'NVDA'],
        ['OKTA', 'OKTA'],
        ['MSFT', 'MSFT'],
        ['CRM', 'CRM'],
        ['NG', 'NGK2022'],
        ['ES', 'ESM2022'],
        ['KC', 'KCK2022'],
    ]

    for s, t in data:
        m = Market.objects.get(symbol=s)
        t = Ticker(ticker=t, market=m)
        t.save()


def get_account(a):
    if Account.objects.filter(name=a).exists():
        account = Account.objects.get(name=a)
    else:
        account = Account(name=a, owner='MSRK', broker='', broker_account=a, description='')
        account.save()
    return account


def cash_balance(account):
    balance = 0

    qs = Trade.objects.filter(account__name=account).values_list('reinvest', 'q', 'p', 'commission')
    for reinvest, q, p, c in qs:
        if not reinvest:
            print('inside cash_balance: ', account, balance, q, p, c)
            balance += -q * p - c

    qs = CashRecord.objects.filter(account__name=account).values_list('amt')
    for q in qs:
        q = q[0]
        print('inside cash_balance q=', q)
        balance += q

    return balance


def fix_none_accounts(none_accounts):
    # These accounts had no associated cash accounts.
    for a in none_accounts.keys():
        balance = cash_balance(a)
        a = get_account(a)
        description = 'Stub to close account because there never was this cash account.'
        CashRecord(account=a, d=none_accounts[a.name].date(), description=description,
                   category=CashRecord.DE, amt=-balance).save()


@transaction.atomic
def add_trades():
    fn = '/Users/ms/data/trades.dat'
    none_accounts = {}
    with open(fn) as fh:
        lines = fh.readlines()
        for line in lines:
            line = re.sub(r'\!.*\n', r'\n', line)
            line = line.replace('\n', '')
            if not line:
                continue

            print(line)
            a, t, ca, d, r_f, q, p, c, c_f, note, junk = line.split('|')
            if t in ['FBroker', 'FDRXX']:
                t = 'cash'

            if ca in ['FBroker', 'FDRXX']:
                ca = 'cash'

            dt = yyyymmdd2dt(d)

            if ca.lower() == 'none':
                none_accounts[a] = dt

            a = get_account(a)
            q = float(q)
            p = float(p)
            r_f = r_f == '1'
            if c == '':
                c = 0.0
            else:
                c = float(c)

            if t.lower() == 'cash':
                CashRecord(account=a, d=dt.date(), description=note, amt=q).save()
                continue

            if ca.lower() == 'none' and not r_f:
                description = f'Stub to cover {t} purchase.'
                if q >= 0:
                    x = q * p + c
                else:
                    x = -q * p + c
                CashRecord(account=a, d=dt.date(), description=description,
                           category=CashRecord.DE, amt=x).save()

            t = add_ticker(t)
            trade = Trade(dt=dt, account=a, ticker=t, reinvest=r_f, q=q, p=p, commission=c, note=note)
            trade.save()

    fix_none_accounts(none_accounts)


def bofa():
    a = get_account('BofA')
    fn = '/Users/ms/data/bofa.csv'
    with open(fn) as fh:
        lines = fh.readlines()
        for line in lines:
            line = re.sub(r'\!.*\n', r'\n', line)
            line = line.replace('\n', '')
            if not line:
                continue

            print(line)
            category, typ, d, description, amount, cleared = line.split(',')

            cleared_f = (len(cleared) > 0 and 'x' == cleared)

            dt = yyyymmdd2dt(d)
            amt = float(amount)

            CashRecord(account=a, d=dt.date(), description=description,
                       category=category, amt=amt, cleared_f=cleared_f).save()


@transaction.atomic()
def do():
    add_accounts()
    add_markets()
    add_trades()
    bofa()


do()
