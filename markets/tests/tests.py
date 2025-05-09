from markets.tbgyahoo import yahooQuotes
from markets.models import Ticker
from trades.tests import make_trades
from django.test import TestCase, tag
from tbgutils.dt import next_business_day
import yfinance as yf


def get_prices(tickers, d):
    start_date = d
    end_date = next_business_day(d)

    # Download the historical data
    data = yf.download(
        tickers=' '.join(tickers),
        start=start_date,
        end=end_date,
        interval='1d',
        group_by='ticker',
        auto_adjust=True,
        prepost=True  # Include pre-market and after-hours data
    )

    print(f"data={data}")

    # Extract just the closing prices for the target date
    result = {}
    date_str = d.strftime('%Y-%m-%d')

    for ticker in tickers:
        try:
            matching_dates = data[ticker].index[
                data[ticker].index.strftime('%Y-%m-%d') == date_str]
            if len(matching_dates) > 0:
                result[ticker] = data[ticker].loc[
                    matching_dates[0], 'Close']
        except KeyError:
            pass

    return result


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
            price = v
            self.assertTrue(price > 1e-4)

    def test_single_quotes(self):
        tickers = ['AAPL']
        tickers_objs = [i for i in Ticker.objects.filter(ticker__in=tickers)]
        result = yahooQuotes(tickers=tickers_objs)
        for k, v in result.items():
            self.assertIn(k, tickers)
            price = v
            self.assertTrue(price > 1e-4)
