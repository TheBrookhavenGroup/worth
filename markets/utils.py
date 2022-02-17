from cachetools.func import ttl_cache
from django.conf import settings
from markets.tbgyahoo import yahooHistory, yahooQuote
from markets.models import DailyBar
from markets.models import Ticker


def populate_historical_price_data(ticker, d_i=None, d_f=None):
    data = yahooHistory(ticker.yahoo_ticker)
    print(ticker)
    for d, o, h, l, c, v, oi in data:
        if (d_i is not None) and (d < d_i):
            continue
        if (d_f is not None) and (d > d_f):
            continue
        DailyBar(ticker=ticker, d=d, o=o, h=h, l=l, c=c, v=v, oi=oi).save()


@ttl_cache(maxsize=128, ttl=60)
def get_price(ticker):
    if not settings.USE_PRICE_FEED:
        return 1.0

    t = Ticker.objects.get(ticker=ticker.upper())

    if t.fixed_price is None:
        p = yahooQuote(ticker)[0]
    else:
        p = t.fixed_price

    return p
