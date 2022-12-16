import datetime
from datetime import date
import pandas as pd
from django.test import TestCase
from analytics.utils import fifo


class FifoTests(TestCase):
    def setUp(self):
        d = [date(2020, 3, 22),
             date(2020, 4, 25),
             date(2021, 10, 22),
             date(2021, 10, 25),
             date(2021, 10, 26),
             date(2022, 1, 6),
             date(2022, 2, 6),
             date(2022, 3, 6)]

        self.df = pd.DataFrame({'d': d,
                                'q': [100, -10, 100, -190, 10, 10, -10.0, 10.0],
                                'p': [300, 301, 300, 301, 306, 307, 315, 310],
                                'cs': [1, 1, 1, 1, 1, 1, 1, 1]})

    def test_fifo(self):
        year = 2022
        dt = datetime.datetime(year, 1, 1)
        dt = pd.Timestamp(dt, tz='UTC')
        pnl = fifo(self.df, dt.date())
        self.assertAlmostEqual(pnl, 90)
