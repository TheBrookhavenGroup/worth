import datetime
import pandas as pd
from django.test import TestCase, override_settings
from trades.tests import make_trades, make_trades_split, make_lifo_trades

from analytics.pnl import pnl, pnl_if_closed
from markets.utils import get_price


@override_settings(USE_PRICE_FEED=False)
class PnLTests(TestCase):
    def setUp(self):
        make_trades()

    @staticmethod
    def results(d=None):

        df, total = pnl(d=d)

        def get_pnl(ticker):
            try:
                p = df[df.Ticker == ticker].iloc[0][-1]
            except IndexError:
                p = 0
            return p

        coh = df[df.Account == 'ALL COH'].iloc[0][-1]
        cash = df[df.Ticker == 'CASH'].iloc[0][4]
        msft = get_pnl('MSFT')
        amzn = get_pnl('AMZN')
        aapl = get_pnl('AAPL')

        return {'TOTAL': total, 'COH': coh, 'CASH': cash, 'MSFT': msft, 'AAPL': aapl, 'AMZN': amzn}, df

    def test_today(self):
        data, _ = self.results()

        self.assertAlmostEqual(1021456.2, data['TOTAL'])

        cash = data['CASH']
        self.assertAlmostEqual(974435.0, cash)
        self.assertEqual('974,435', data['COH'])
        self.assertAlmostEqual(-50.0, data['MSFT'])
        self.assertAlmostEqual(7370, data['AMZN'])

    def test_givendate(self):
        data, _ = self.results(d=datetime.date(2021, 10, 23))
        self.assertAlmostEqual(500, data['AAPL'])

        data, _ = self.results(d=datetime.date(2021, 10, 30))
        self.assertAlmostEqual(100, data['AAPL'])

    def test_sell(self):
        # AAPL was sold on 10/25/2021
        data, df = self.results(d=datetime.date(2021, 10, 25))

        aapl_today = list(df[df.Ticker == 'AAPL'].Today)[0]
        self.assertAlmostEqual(-400, aapl_today)

        total_today = list(df[df.Account == 'TOTAL'].Today)[0]
        self.assertAlmostEqual(3360.0, total_today)

        cash_today = list(df[df.Ticker == 'CASH'].Today)[0]
        self.assertAlmostEqual(24660.0, cash_today)


@override_settings(USE_PRICE_FEED=False)
class PnLSplitTests(TestCase):
    def setUp(self):
        self.aapl_ticker, self.msft_ticker = make_trades_split()

    def check_pnl(self, ticker, df, x):
        pos = sum(i[0] for i in x)
        price = get_price(ticker)
        x.append((-pos, price))
        expected_pnl = -sum([i * j for i, j in x])

        pnl = df[df.Ticker == str(ticker)].iloc[0][-1]
        self.assertAlmostEqual(expected_pnl, pnl)

    def test_split(self):
        df, total = pnl(a='MSFidelity')

        # Split
        # These are the trades used for testing with zero for price on split shares added.
        x = [(50, 305), (150, 0), (-100, 200)]
        self.check_pnl(self.aapl_ticker, df, x)

        # Reverse split
        # In a reverse split the split q is negative
        x = [(150, 125), (-100, 0), (-25, 330)]
        self.check_pnl(self.msft_ticker, df, x)


@override_settings(USE_PRICE_FEED=False)
class PnLIfClosedTests(TestCase):
    def setUp(self):
        make_trades()

    def test_if_closed(self):
        expected = pd.DataFrame({'a': ['MSFidelity', 'MSFidelity', 'MSFidelity'],
                                 't': ['MSFT', 'MBXIX', 'AMZN'],
                                 'wap': [310.00, 29.01431, 69.10526],
                                 'cs': [1.0, 1.0, 1.0],
                                 'q': [10.0, 1001.4, 95.0],
                                 'price': [305.0, 33.0, 115.0],
                                 'pnl': [-50.0, 3991.274, 4360.000]})

        df, format_rec = pnl_if_closed()
        pd.testing.assert_frame_equal(df, expected)
