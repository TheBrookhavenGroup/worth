from datetime import datetime
import json
import urllib
import requests


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


def yahooHistory(ticker, multiplier=1.0, p=4):
    """
      Get historical yahoo prices for the given ticker symbol.
      ticker can be KCH22.NYB or ^GSPC or MSFT
    """
    t = datetime.now().strftime('%s')
    url = 'https://query1.finance.yahoo.com/v8/finance/chart/' + ticker + '?interval=1d&period1=0&period2=' + t
    data = yahoo_get(url)
    data = json.loads(data)
    data = data['chart']['result'][0]
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

    def scale(x):
        return round(x * multiplier, ndigits=p)

    data = [(j[0], scale(j[1]), scale(j[2]), scale(j[3]), scale(j[4]), j[5], j[6]) for j in data]
    return data


def yahooQuote(ticker):
    url = 'https://query1.finance.yahoo.com/v6/finance/quote?region=US&lang=en&symbols=' + ticker.yahoo_ticker
    data = yahoo_get(url)
    data = json.loads(data)
    data = data['quoteResponse']['result'][0]
    multiplier = ticker.market.yahoo_price_factor
    return data['regularMarketPrice'] * multiplier, data['regularMarketPreviousClose'] * multiplier


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
