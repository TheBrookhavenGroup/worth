import datetime
from django.test import TestCase, override_settings
from trades.tests import make_trades, make_trades_split
from analytics.pnl import pnl_summary
from markets.utils import get_price


@override_settings(USE_PRICE_FEED=False)
class PnLTests(TestCase):
    def setUp(self):
        make_trades()

    @staticmethod
    def results(d=None):
        headings, data, formats, total_worth = pnl_summary(d=d)

        total = [i for i in data if i[0] == 'TOTAL'][-1][4]
        coh = [i for i in data if i[0] == 'ALL COH'][-1][-1]
        cash = [i for i in data if i[1] == 'CASH'][-1][4]
        msft = [i for i in data if 'MSFT' in i[1]]
        if msft:
            msft = msft[-1][-7:]
        amzn = [i for i in data if 'AMZN' in i[1]]
        if amzn:
            amzn = amzn[-1][-7:]
        aapl = [i for i in data if 'AAPL' in i[1]]
        if aapl:
            aapl = aapl[-1][-7:]

        return {'TOTAL': total, 'COH': coh, 'CASH': cash, 'MSFT': msft, 'AMZN': amzn, 'AAPL': aapl}

    def test_setup(self):
        data = self.results()
        pos_i, value_i, pnl_i = 0, 2, 6

        self.assertEqual('1.02M', data['TOTAL'])

        self.assertEqual('1.003M', data['CASH'])
        self.assertEqual('1M', data['COH'])

        x = data['MSFT']
        self.assertEqual('-50', x[pnl_i])
        self.assertEqual('10', x[pos_i])
        self.assertEqual('3,050', x[value_i])

        data = self.results(d=datetime.date(2021, 10, 23))
        x = data['AAPL']
        self.assertEqual('100', x[pnl_i])


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
