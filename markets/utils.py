from cachetools.func import ttl_cache
from django.conf import settings
from worth.utils import y1_to_y4
from markets.tbgyahoo import yahooHistory, yahooQuote
from markets.models import DailyBar
from markets.models import Ticker, Market


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

    if type(ticker) == str:
        ticker = Ticker.objects.get(ticker=ticker)

    if ticker.fixed_price is None:
        p = yahooQuote(ticker)[0]
        p *= ticker.market.yahoo_price_factor
    else:
        p = ticker.fixed_price

    return p


def add_ticker(t):
    if Ticker.objects.filter(ticker=t).exists():
        ticker = Ticker.objects.get(ticker=t)
    else:
        m = Market(symbol=t, name=t)
        m.save()

        ticker = Ticker(ticker=t, market=m)
        ticker.save()

    return ticker


def ib_symbol2ticker(symbol):
    symbol, mo, yr = symbol[:-2], symbol[-2:-1], symbol[-1:]
    m = Market.objects.get(symbol=symbol)
    yr = y1_to_y4(yr)
    ticker = f"{symbol}{mo}{yr}"
    ticker = Ticker.objects.get_or_create(ticker=ticker, market=m)
    return ticker[0]


def tbg_ticker2ticker(ticker):
    symbol, exchange = ticker.split('.')
    symbol, mo, yr = symbol[:-3], symbol[-3:-2], symbol[-2:]

    try:
        m = Market.objects.get(symbol=symbol)
    except Market.DoesNotExist:
        m = Market.objects.get_or_create(symbol=symbol, name=symbol, ib_exchange='CME', yahoo_exchange='CME')[0]

    yr = int(yr)
    if yr > 80:
        yr = 1900 + yr
    else:
        yr = 2000 + yr

    ticker = f"{symbol}{mo}{yr}"

    ticker = Ticker.objects.get_or_create(ticker=ticker, market=m)
    return ticker[0]
