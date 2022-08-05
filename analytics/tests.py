import datetime
from django.test import TestCase
from trades.tests import make_trades
from .pnl import year_pnl


class PnLTests(TestCase):
    def setUp(self):
        make_trades()

    def results(self, ticker=None, d=None):
        headings, data, formats = year_pnl(d=d, ticker=ticker, yahoo_f=False)

        all_dict = data_dict = dict([(str(i[1]), i[2:]) for i in data if i[0] == 'ALL'])
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
        self.assertEqual('1.010M', x[value_i])

        x = data_dict['CASH']
        self.assertEqual('1.007M', x[value_i])
        self.assertEqual(coh, '1M')

        x = data_dict['MSFT']
        self.assertEqual('-100', x[pnl_i])
        self.assertEqual('10', x[pos_i])
        self.assertEqual('3,000', x[value_i])

        data_dict, coh = self.results(d=datetime.date(2021, 10, 22))
        x = data_dict['AAPL']
        self.assertEqual('100', x[pnl_i])

        # Test if we can force AAPL to show even if position was closed out long ago.
        data_dict, coh = self.results(ticker='AAPL')
        x = data_dict['AAPL']
        self.assertEqual('100', x[pnl_i])
        x = data_dict['ALL']
        self.assertEqual('1.010M', x[value_i])
