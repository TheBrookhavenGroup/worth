import datetime

import pandas as pd
from django.test import TestCase, override_settings

from accounts.models import Account, CashRecord
from analytics.pnl import pnl, pnl_if_closed
from markets.utils import get_price
from trades.tests import make_trades, make_trades_split


@override_settings(USE_PRICE_FEED=False, FIFO=True)
class PnLTests(TestCase):
    def setUp(self):
        make_trades()

    @staticmethod
    def results(d=None):
        df, total, _, _ = pnl(d=d)

        def get_ytd(ticker):
            try:
                p = df.loc[df.Ticker == ticker, "YTD"].iloc[0]
            except IndexError:
                p = 0
            return p

        coh = df[df.Account == "ALL COH"].iloc[0, 4]
        cash = df[df.Ticker == "CASH"].iloc[0, 4]
        msft = get_ytd("MSFT")
        amzn = get_ytd("AMZN")
        aapl = get_ytd("AAPL")

        return {
            "TOTAL": total,
            "COH": coh,
            "CASH": cash,
            "MSFT": msft,
            "AAPL": aapl,
            "AMZN": amzn,
        }, df

    def test_today(self):
        data, df = self.results(d=datetime.date(2021, 11, 3))
        self.assertNotIn("PnL", df.columns)

        self.assertAlmostEqual(1021456.2, data["TOTAL"])

        cash = data["CASH"]
        self.assertAlmostEqual(974435.0, cash)
        self.assertEqual(974435.0, data["COH"])
        self.assertAlmostEqual(-50.0, data["MSFT"])
        self.assertAlmostEqual(7370, data["AMZN"])

    def test_givendate(self):
        data, _ = self.results(d=datetime.date(2021, 10, 23))
        self.assertAlmostEqual(500, data["AAPL"])

        data, _ = self.results(d=datetime.date(2021, 10, 30))
        self.assertAlmostEqual(100, data["AAPL"])

    def test_sell(self):
        # AAPL was sold on 10/25/2021
        account = Account.objects.get(name="MSFidelity")
        for category, amount in ((CashRecord.DV, 12.0), (CashRecord.IT, 3.0)):
            CashRecord.objects.create(
                account=account,
                d=datetime.date(2021, 10, 25),
                category=category,
                amt=amount,
                description="Cash income",
            )
        for category, amount, ignored in (
            (CashRecord.TR, 1000.0, False),
            (CashRecord.BF, -2.0, False),
            (CashRecord.DV, 99.0, True),
        ):
            CashRecord.objects.create(
                account=account,
                d=datetime.date(2021, 10, 25),
                category=category,
                amt=amount,
                ignored=ignored,
                description="Excluded from cash income",
            )
        _, df = self.results(d=datetime.date(2021, 10, 25))

        aapl_today = df.loc[df.Ticker == "AAPL", "Today"].iloc[0]
        self.assertAlmostEqual(-400, aapl_today)

        total_today = df.loc[df.Account == "TOTAL", "Today"].iloc[0]
        self.assertAlmostEqual(3375.0, total_today)

        cash = df[df.Ticker == "CASH"].iloc[0]
        self.assertAlmostEqual(15.0, cash.Today)
        self.assertAlmostEqual(15.0, cash.MTD)
        self.assertAlmostEqual(15.0, cash.YTD)


@override_settings(USE_PRICE_FEED=False, FIFO=True)
class PnLSplitTests(TestCase):
    def setUp(self):
        self.aapl_ticker, self.msft_ticker = make_trades_split()

    def check_position(self, ticker, df, x):
        pos = sum(i[0] for i in x)
        price = get_price(ticker)
        row = df[df.Ticker == str(ticker)].iloc[0]
        self.assertAlmostEqual(pos, row.Pos)
        self.assertAlmostEqual(price, row.Price)
        self.assertAlmostEqual(pos * price, row.Value)

    def test_split(self):
        df, *_ = pnl(d=datetime.date(2020, 9, 1), a="MSFidelity")

        # Split
        # These are the trades used for testing with zero for price on split
        # shares added.
        x = [(50, 305), (150, 0), (-100, 200)]
        self.check_position(self.aapl_ticker, df, x)

        # Reverse split
        # In a reverse split the split q is negative
        x = [(150, 125), (-100, 0), (-25, 330)]
        self.check_position(self.msft_ticker, df, x)


@override_settings(USE_PRICE_FEED=False, FIFO=True)
class PnLIfClosedTests(TestCase):
    def setUp(self):
        make_trades()

    def test_if_closed(self):
        expected = pd.DataFrame(
            {
                "a": ["MSFidelity", "MSFidelity", "MSFidelity"],
                "t": ["MSFT", "MBXIX", "AMZN"],
                "position": [10.0, 1001.4, 95.0],
                "wap": [310.00, 29.01431, 94.36842],
                "cs": [1.0, 1.0, 1.0],
                "price": [305.0, 33.0, 115.0],
                "value": [3050.0, 33046.2, 10925.0],
                "pnl": [-50.0, 3991.274, 1960.0],
            }
        )

        df, _ = pnl_if_closed()

        df.sort_values(by=["t"], inplace=True, ignore_index=True)
        expected.sort_values(by=["t"], inplace=True, ignore_index=True)

        print(df)
        print(expected)

        pd.testing.assert_frame_equal(df, expected)
