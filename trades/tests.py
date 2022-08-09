import datetime
from django.test import TestCase
from worth.dt import our_localize, next_business_day
from accounts.models import Account, CashRecord
from markets.models import Market, Ticker
from trades.models import Trade
from trades.utils import weighted_average_price


def make_trades():
    a = Account.objects.create(name='MSFidelity', owner='MS', broker='Fidelity', broker_account='123',
                               description='Testing Account', active_f=True)

    d = datetime.date(year=2021, month=10, day=21)
    CashRecord.objects.create(account=a, d=d, category='DE', description='Open account', amt=1e6, cleared_f=True)

    m = Market.objects.create(symbol='CASH', name='cash', ib_exchange='CASH', yahoo_exchange='CASH', cs=1, commission=0,
                              ib_price_factor=1, yahoo_price_factor=1, pprec=4, vprec=3)
    Ticker.objects.create(ticker='CASH', market=m, fixed_price=1.0)
    Ticker.objects.create(ticker='C_O_H', market=m, fixed_price=1.0)

    m = Market.objects.create(symbol='STOCK', name='Equity', ib_exchange='STOCK', yahoo_exchange='STOCK', cs=1,
                              commission=0, ib_price_factor=1, yahoo_price_factor=1, pprec=4, vprec=0)

    t = Ticker.objects.create(ticker='AAPL', market=m)
    dt = our_localize(datetime.datetime(year=2021, month=10, day=22, hour=10, minute=0, second=0))
    Trade.objects.create(dt=dt, account=a, ticker=t, q=100, p=300, reinvest=False)
    dt = our_localize(datetime.datetime(year=2021, month=10, day=22, hour=11, minute=0, second=0))
    Trade.objects.create(dt=dt, account=a, ticker=t, q=-100, p=301, reinvest=False)

    # Note: setting fixed_price here for testing so that we don't keep going to yahoo for data.
    t = Ticker.objects.create(ticker='MSFT', market=m, fixed_price=300.00)
    dt = our_localize(datetime.datetime(year=2021, month=10, day=22, hour=10, minute=30, second=0))
    Trade.objects.create(dt=dt, account=a, ticker=t, q=10, p=310, reinvest=False)

    t = Ticker.objects.create(ticker='AMZN', market=m)
    dt = our_localize(datetime.datetime(year=2021, month=10, day=22, hour=10, minute=0, second=0))
    for q, p in [(80, 68.0), (-80, 72.0), (100, 75.0), (120, 77.00), (75, 99.00), (-190, 101.0), (-10, 110.0)]:
        dt = next_business_day(dt)
        Trade.objects.create(dt=dt, account=a, ticker=t, q=q, p=p, reinvest=False)

    m = Market.objects.create(symbol='ES', name='EMini SP500', ib_exchange='CME', yahoo_exchange='CME', cs=50,
                              commission=2.1, ib_price_factor=1, yahoo_price_factor=1, pprec=2, vprec=0)
    # Note: setting fixed_price here for testing so that we don't keep going to yahoo for data.
    t = Ticker.objects.create(ticker='ESZ2021', market=m, fixed_price=4600.00)
    dt = our_localize(datetime.datetime(year=2021, month=10, day=22, hour=12, minute=30, second=0))
    Trade.objects.create(dt=dt, account=a, ticker=t, q=2, p=4500.00, reinvest=False)
    dt = our_localize(datetime.datetime(year=2021, month=10, day=22, hour=13, minute=0, second=0))
    Trade.objects.create(dt=dt, account=a, ticker=t, q=-2, p=4600.00, reinvest=False)


class TradesTests(TestCase):
    def setUp(self):
        make_trades()
        self.a = Account.objects.first()
        self.trade = Trade.objects.first()

    def test_setup(self):
        self.assertEqual('MSFidelity', self.a.name)
        self.assertAlmostEqual(100, self.trade.q)

    def test_wap(self):
        # Test weighted average price
        t = Ticker.objects.get(ticker='AMZN')
        pos, wap = weighted_average_price(t)
        self.assertAlmostEqual(95, pos)
        self.assertAlmostEqual(75, wap)
