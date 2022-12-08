import datetime
from django.test import TestCase, override_settings
from trades.tests import make_trades, make_trades_split
from analytics.pnl import pnl
from markets.utils import get_price


@override_settings(USE_PRICE_FEED=False)
class PnLTests(TestCase):
    def setUp(self):
        make_trades()

    @staticmethod
    def results(d=None):
        df, total = pnl(d=d)

        coh = df[df.Account == 'ALL COH'].iloc[0][-1]
        cash = df[df.Ticker == 'CASH'].iloc[0][4]
        msft = df[df.Ticker == 'MSFT'].iloc[0][-1]
        try:
            aapl = df[df.Ticker == 'AAPL'].iloc[0][-1]
        except IndexError:
            aapl = 0

        return {'TOTAL': total, 'COH': coh, 'CASH': cash, 'MSFT': msft, 'AAPL': aapl}

    def test_today(self):
        data = self.results()

        self.assertAlmostEqual(1017420.0, data['TOTAL'])

        self.assertAlmostEqual(1003445.0, data['CASH'])
        self.assertEqual('1M', data['COH'])
        self.assertAlmostEqual(-50.0, data['MSFT'])

    def test_givendate(self):
        data = self.results(d=datetime.date(2021, 10, 23))

        self.assertEqual(500, data['AAPL'])


@override_settings(USE_PRICE_FEED=False)
class PnLSplitTests(TestCase):
    def setUp(self):
        self.aapl_ticker, self.msft_ticker = make_trades_split()

    def check_pnl(self, ticker, pnl, x):
        pos = sum(i[0] for i in x)
        price = get_price(ticker)
        x.append((-pos, price))
        expected_pnl = -sum([i * j for i, j in x])

        value = [i for i in pnl if ticker == i[0]][0][3]
        self.assertAlmostEqual(expected_pnl, value)

    def test_split(self):
        pnl = pnl_summary(a='MSFidelity')[1]

        # Split
        # These are the trades used for testing with zero for price on split shares added.
        x = [(50, 305), (150, 0), (-100, 200)]
        self.check_pnl(self.aapl_ticker, pnl, x)

        # Reverse split
        # In a reverse split the split q is negative
        x = [(150, 125), (-100, 0), (-25, 330)]
        self.check_pnl(self.msft_ticker, pnl, x)
