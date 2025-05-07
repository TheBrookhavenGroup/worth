from datetime import datetime, date
import requests
from django.utils.safestring import mark_safe
import yfinance as yf
from tbgutils.dt import next_business_day
import pandas as pd


def yahoo_get(url):
    with requests.session():
        header = {'Connection': 'keep-alive',
                  'Expires': '-1',
                  'Upgrade-Insecure-Requests': '1',
                  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) '
                                'AppleWebKit/537.36 (KHTML, like Gecko) '
                                'Chrome/54.0.2840.99 Safari/537.36'
                  }

        website = requests.get(url, headers=header)

    return website.text


def yahooHistory(ticker):
    """
    Get historical yahoo prices for the given ticker symbol using yfinance.
    ticker can be KCH22.NYB or ^GSPC or MSFT

    Returns a list of tuples with (date, open, high, low, close, volume, open_interest)
    """
    yahoo_ticker = ticker.yahoo_ticker
    try:
        # Download all historical data for this ticker
        df = yf.download(
            tickers=yahoo_ticker,
            period="max",  # Get all available data
            interval="1d",
            auto_adjust=False,
            prepost=False
        )

        if df.empty:
            print(f"Cannot get prices for {yahoo_ticker} from yahoo.")
            return []

        # Convert the DataFrame to the expected output format
        multiplier = ticker.market.yahoo_price_factor
        p = ticker.market.pprec

        def scale(x):
            if x is None or pd.isna(x):
                return None
            return round(x * multiplier, ndigits=p)

        # Process the data into the expected format
        result = []
        for index, row in df.iterrows():
            try:
                if any([pd.isna(i) for i in row.values]):
                    continue

                date = index.date()
                open_price = scale(row['Open'][yahoo_ticker])
                high_price = scale(row['High'][yahoo_ticker])
                low_price = scale(row['Low'][yahoo_ticker])
                close_price = scale(row['Close'][yahoo_ticker])
                volume = row['Volume'][yahoo_ticker]
                if pd.isna(volume):
                    volume = 0
                else:
                    volume = int(volume)
                open_interest = 0  # YFinance doesn't provide open interest

                result.append(
                    (date, open_price, high_price, low_price, close_price,
                     volume, open_interest))
            except (TypeError, ValueError) as e:
                print(
                    f"Error processing row for {ticker} on {index.date()}: {e}")
                continue

        return result

    except Exception as e:
        print(f"Error fetching history for {ticker} with yfinance: {e}")
        return []


def get_prices(tickers, d=None):
    """
    This gets one price or many prices in a single web request.
    """
    if d is None:
        d = date.today()
    end_date = next_business_day(d)

    # Download the historical data
    data = yf.download(
        tickers=' '.join(tickers),
        start=d,
        end=end_date,
        interval='1d',
        group_by='ticker',
        auto_adjust=True,
    )

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


def yahooQuotes(tickers, d=None):
    '''
        yf.download gets all the prices with a single web request.
    '''

    yahoo_tickers = [t.yahoo_ticker for t in tickers]
    prices = get_prices(yahoo_tickers, d)

    result = {}
    for t in tickers:
        yt = t.yahoo_ticker
        p = prices[yt]
        if p:
            multiplier = t.market.yahoo_price_factor
            result[yt] = p * multiplier

    return result


def yahooQuote(ticker):
    quotes = yahooQuotes([ticker])
    return quotes[ticker.yahoo_ticker]


def yahoo_url(ticker):
    if ticker.market.is_cash:
        url = ticker.ticker
    else:
        url = f'https://finance.yahoo.com/quote/{ticker.yahoo_ticker}/'
        url = mark_safe(url)
        url = mark_safe(f'<a href="{url}" target="_blank">{ticker.ticker}</a>')
    return url
