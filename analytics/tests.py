
from django.test import TestCase
from trades.tests import make_trades
from .pnl import year_pnl


class PnLTests(TestCase):
    def setUp(self):
        make_trades()

    def test_setup(self):
        headings, data, formats = year_pnl(yahoo_f=False)

        data_dict = dict([(str(i[1]), i[2:]) for i in data if i[0] != 'AAA Total'])
        data_dict['AAA Total'] = data[0][2:]
        pos_i, value_i, pnl_i = 0, 2, 6

        x = data_dict['AAA Total']
        self.assertEqual('1,010,000.000', x[value_i])

        x = data_dict['CASH']
        self.assertEqual('1,007,000.000', x[value_i])

        x = data_dict['AAPL']
        self.assertEqual('100', x[pnl_i])

        x = data_dict['MSFT']
        self.assertEqual('-100', x[pnl_i])
        self.assertEqual('10', x[pos_i])
        self.assertEqual('3,000', x[value_i])
