import datetime
import pandas as pd
from moneycounter import realized_gains
from django.test import TestCase, override_settings
from trades.models import get_non_qualified_equity_trades_df
from trades.tests import make_trades, make_trades_split, make_lifo_trades

from analytics.pnl import pnl
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

        return {'TOTAL': total, 'COH': coh, 'CASH': cash, 'MSFT': msft, 'AAPL': aapl, 'AMZN': amzn}

    def test_today(self):
        data = self.results()

        self.assertAlmostEqual(1017420.0, data['TOTAL'])

        self.assertAlmostEqual(1003445.0, data['CASH'])
        self.assertEqual('1M', data['COH'])
        self.assertAlmostEqual(-50.0, data['MSFT'])
        self.assertAlmostEqual(7370, data['AMZN'])

    def test_givendate(self):
        data = self.results(d=datetime.date(2021, 10, 23))
        self.assertAlmostEqual(500, data['AAPL'])

        data = self.results(d=datetime.date(2021, 10, 30))
        self.assertAlmostEqual(100, data['AAPL'])


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
class RealizedPnLTests(TestCase):
    def setUp(self):
        make_lifo_trades()

    def test_realized(self):
        trades_df = get_non_qualified_equity_trades_df()
        realized = realized_gains(trades_df, 2022)

        expected = pd.DataFrame({'a': ['Fidelity', 'Fidelity', 'Schwab'],
                                 't': ['AAPL', 'AMZN', 'AAPL'],
                                 'realized': [300.0, 750.0, 100.0]})

        pd.testing.assert_frame_equal(realized, expected)