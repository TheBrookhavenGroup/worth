import datetime
from django.test import TestCase, override_settings
from unittest.mock import patch
from markets.models import Market, Ticker
from trades.tests import make_trades, make_trades_split
from analytics.pnl import year_pnl, valuations, get_equties_pnl
from markets.utils import get_price


@override_settings(USE_PRICE_FEED=False)
class PnLTests(TestCase):
    def setUp(self):
        make_trades()

    def results(self, ticker=None, d=None):
        headings, data, formats = year_pnl(d=d, ticker=ticker)

        all_dict = data_dict = dict([(str(i[1]), i[2:]) for i in data if i[0].startswith('ALL<a')])
        all_dict['ALL'] = all_dict['CASH']
        del all_dict['CASH']

        data_dict = dict([(str(i[1]), i[2:]) for i in data if i[0] not in ['ALL', 'ALL COH']])

        data_dict = {**data_dict, **all_dict}

        coh = [i for i in data if i[0] == 'ALL COH'][0][-1]

        return data_dict, coh

    def test_setup(self):
        data_dict, coh = self.results()
        pos_i, value_i, pnl_i = 0, 2, 6

        x = data_dict['ALL']
        self.assertEqual('1.017M', x[value_i])

        x = data_dict['CASH']
        self.assertEqual('1.003M', x[value_i])
        self.assertEqual(coh, '1M')

        def find_key(x):
            for i in data_dict.keys():
                if x in i:
                    return i

        x = data_dict[find_key('MSFT')]
        self.assertEqual('-50', x[pnl_i])
        self.assertEqual('10', x[pos_i])
        self.assertEqual('3,050', x[value_i])

        data_dict, coh = self.results(d=datetime.date(2021, 10, 22))
        x = data_dict[find_key('AAPL')]
        self.assertEqual('100', x[pnl_i])

        # Test if we can force AAPL to show even if position was closed out long ago.
        data_dict, coh = self.results(ticker='AAPL')
        x = data_dict[find_key('AAPL')]
        self.assertEqual('100', x[pnl_i])
        x = data_dict[find_key('ALL')]
        self.assertEqual('1.017M', x[value_i])


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
        pnl = get_equties_pnl('MSFidelity')[0]

        # Split
        # These are the trades used for testing with zero for price on split shares added.
        x = [(50, 305), (150, 0), (-100, 200)]
        self.check_pnl(self.aapl_ticker, pnl, x)

        # Reverse split
        # In a reverse split the split q is negative
        x = [(150, 125), (-100, 0), (-25, 330)]
        self.check_pnl(self.msft_ticker, pnl, x)
