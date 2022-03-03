from cachetools.func import ttl_cache
from django.conf import settings
from worth.dt import y1_to_y4, is_lbd_of_month
from markets.tbgyahoo import yahooHistory, yahooQuote
from markets.models import DailyBar, TBGDailyBar
from markets.models import Ticker, Market, NOT_FUTURES_EXCHANGES


def is_futures(exchange):
    return exchange not in NOT_FUTURES_EXCHANGES


@ttl_cache(maxsize=1000, ttl=30)
def get_yahoo_history(ticker):
    if type(ticker) == str:
        ticker = Ticker.objects.get(ticker=ticker)
    return yahooHistory(ticker)


def populate_historical_price_data(ticker, d_i=None, d_f=None, lbd_f=True):
    data = get_yahoo_history(ticker)
    for d, o, h, l, c, v, oi in data:
        if lbd_f and not is_lbd_of_month(d):
            continue
        if (d_i is not None) and (d < d_i):
            continue
        if (d_f is not None) and (d > d_f):
            continue
        DailyBar.objects.create(ticker=ticker, d=d, o=o, h=h, l=l, c=c, v=v, oi=oi)


def get_historical_bar(ticker, d):
    data = get_yahoo_history(ticker)
    bar = next(filter(lambda x: x[0] >= d, data), None)
    if bar:
        if d == bar[0]:
            return bar

        # Get last bar prior to d
        i = data.index(bar)
        if i >= 0:
            return data[i - 1]

        return None

    return None


@ttl_cache(maxsize=1000, ttl=60)
def get_price(ticker, d=None):
    if not settings.USE_PRICE_FEED:
        return 1.0

    if type(ticker) == str:
        ticker = Ticker.objects.get(ticker=ticker)

    if ticker.fixed_price is None:
        if d is None:
            p = yahooQuote(ticker)[0]
            p *= ticker.market.yahoo_price_factor
        else:
            if DailyBar.objects.filter(ticker=ticker).filter(d=d).exists():
                p = DailyBar.objects.filter(ticker=ticker).filter(d=d).first()
                p = p.c
            else:
                bar = get_historical_bar(ticker, d)
                if bar is None:
                    if TBGDailyBar.objects.filter(ticker=ticker, d=d).exists():
                        print("Bar exists in TBGDaily: {d} {ticker}")
                    else:
                        print("Cannot find bar in TBGDaily: {d} {ticker}")
                    p = 0.0
                else:
                    d_bar, o, h, l, c, v, oi = bar
                    if d_bar != d:
                        print(f"Using price found on {d_bar} for {d} for {ticker}")
                    DailyBar.objects.create(ticker=ticker, d=d, o=o, h=h, l=l, c=c, v=v, oi=oi)
                    p = c
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
