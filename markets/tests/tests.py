from django.test import TestCase
from markets.tbgyahoo import yahooQuotes
from markets.models import Ticker
from trades.tests import make_trades
from django.test import TestCase, tag


@tag('inhibit_test')
class YahooTests(TestCase):
    def setUp(self):
        make_trades()

    def test_multiple_quotes(self):
        tickers = ['AAPL', 'MSFT']
        tickers_objs = [i for i in Ticker.objects.filter(ticker__in=tickers)]
        result = yahooQuotes(tickers=tickers_objs)
        for k, v in result.items():
            self.assertIn(k, tickers)
            price, prev_close = v
            self.assertTrue(price > 1e-4)
            self.assertTrue(prev_close > 1e-4)

    def test_single_quotes(self):
        tickers = ['AAPL']
        tickers_objs = [i for i in Ticker.objects.filter(ticker__in=tickers)]
        result = yahooQuotes(tickers=tickers_objs)
        for k, v in result.items():
            self.assertIn(k, tickers)
            price, prev_close = v
            self.assertTrue(price > 1e-4)
            self.assertTrue(prev_close > 1e-4)
