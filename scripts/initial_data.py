
from django.db import transaction
from accounts.models import Account
from markets.models import Market, Ticker

@transaction.atomic
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

@transaction.atomic
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
        print(s)
        m = Market.objects.get(symbol=s)
        t = Ticker(ticker=t)
        t.market = m
        t.save()
