from datetime import datetime
import json
import requests
from django.utils.safestring import mark_safe


def yahoo_get(url):
    with requests.session():
        header = {'Connection': 'keep-alive',
                  'Expires': '-1',
                  'Upgrade-Insecure-Requests': '1',
                  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) \
                           AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.99 Safari/537.36'
                  }

        website = requests.get(url, headers=header)

    return website.text


def yahooHistory(ticker):
    """
      Get historical yahoo prices for the given ticker symbol.
      ticker can be KCH22.NYB or ^GSPC or MSFT
    """
    t = datetime.now().strftime('%s')
    base_url = 'https://query1.finance.yahoo.com/v8/finance/chart/'
    url = base_url + ticker.yahoo_ticker + '?interval=1d&period1=0&period2=' + t
    data = yahoo_get(url)
    data = json.loads(data)
    data = data['chart']['result']
    if (data is None) or ('timestamp' not in data[0]):
        print(f"Cannot get prices for {ticker} from yahoo.")
        return []
    else:
        data = data[0]

    times = data['timestamp']
    times = [datetime.fromtimestamp(t).date() for t in times]
    data = data['indicators']['quote'][0]
    data = zip(times, data['open'], data['high'], data['low'], data['close'], data['volume'], [0 for i in times])

    def is_data_good(d, o, h, l, c, v, oi):
        try:
            o * h * l * c
        except TypeError:
            return False

        return True

    data = [i for i in data if is_data_good(*i)]

    multiplier = ticker.market.yahoo_price_factor
    p = ticker.market.pprec

    def scale(x):
        return round(x * multiplier, ndigits=p)

    data = [(j[0], scale(j[1]), scale(j[2]), scale(j[3]), scale(j[4]), j[5], j[6]) for j in data]
    return data


def yahooQuotes(tickers):
    result = {t.yahoo_ticker: t for t in tickers}
    tickers = [t.yahoo_ticker for t in tickers]
    tickers = ','.join(tickers)
    url = f'https://query1.finance.yahoo.com/v6/finance/quote?region=US&lang=en&symbols={tickers}'
    data = yahoo_get(url)
    data = json.loads(data)

    for quote in data['quoteResponse']['result']:
        symbol = quote['symbol']
        ticker = result[symbol]
        multiplier = ticker.market.yahoo_price_factor
        price = quote['regularMarketPrice'] * multiplier, quote['regularMarketPreviousClose'] * multiplier
        result[symbol] = price

    return result


def yahooQuote(ticker):
    quotes = yahooQuotes([ticker])
    return quotes[ticker.yahoo_ticker]


def yahoo_url(ticker):
    if ticker.market.is_cash:
        url = ticker.ticker
    else:
        url = mark_safe(f'https://finance.yahoo.com/quote/{ticker.yahoo_ticker}/')
        url = mark_safe(f'<a href="{url}" target="_blank">{ticker.ticker}</a>')
    return url


# ####################
# #  MAIN            #
# ####################
#
# if __name__ == "__main__":
#     if False:
#         q = yahooHistory('^VIX')
#         for i in q:
#             print(i)
#
#     if True:
#         # print yahooHistory('KCH22.NYB', multiplier=0.01, p=4)
#         print(yahooHistory('NGH22.NYM'))
#
#     if False:
#         print(yahooQuote('KCH22.NYB', multiplier=0.01, p=4))
