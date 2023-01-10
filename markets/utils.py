from cachetools.func import ttl_cache
from django.conf import settings
from django.urls import reverse
from django.utils.safestring import mark_safe
from datetime import date
from moneycounter.dt import y1_to_y4, is_lbd_of_month, most_recent_business_day
from markets.tbgyahoo import yahooHistory, yahooQuote
from markets.models import DailyPrice, TBGDailyBar
from markets.models import Ticker, Market, NOT_FUTURES_EXCHANGES


def is_futures(exchange):
    return exchange not in NOT_FUTURES_EXCHANGES


def ticker_url(ticker):
    if ticker.market.is_cash:
        url = ticker.ticker
    else:
        ticker = ticker.ticker
        url = reverse('analytics:ticker_view', kwargs={'ticker': ticker})
        url = mark_safe(f'<a href={url}>{ticker}</a>')
    return url


def ticker_admin_url(request, ticker):
    from django.contrib.sites.shortcuts import get_current_site
    url = get_current_site(request)
    url = f'{request.scheme}://{url}/admin/markets/ticker/{ticker.id}/change/'
    url = f'<a href="{url}" target="_blank">admin ticker</a>'
    return mark_safe(url)


@ttl_cache(maxsize=1000, ttl=10)
def get_yahoo_history(ticker):
    print(f"Getting yahoo history for {ticker}.")
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
        DailyPrice.objects.create(ticker=ticker, d=d, c=c)


def get_historical_bar(ticker, d):
    print(f"Getting yahoo history for {ticker} on {d}.")
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


fixed_prices = {'AAPL': 305.0, 'MSFT': 305.0, 'AMZN': 115.0, 'ESZ2021': 4300.0}


@ttl_cache(maxsize=1000, ttl=10)
def get_price(ticker, d=None):
    d = most_recent_business_day(d)

    if not settings.USE_PRICE_FEED:
        return fixed_prices.get(ticker.yahoo_ticker, 1.0)

    if type(ticker) == str:
        ticker = Ticker.objects.get(ticker=ticker)

    if ticker.fixed_price is None:
        if (d is None) or (d == date.today()):
            p = yahooQuote(ticker)[0]
            p *= ticker.market.yahoo_price_factor
        else:
            if DailyPrice.objects.filter(ticker=ticker).filter(d=d).exists():
                p = DailyPrice.objects.filter(ticker=ticker).filter(d=d).first()
                p = p.c
            else:
                bar = get_historical_bar(ticker, d)
                if bar is None:
                    if TBGDailyBar.objects.filter(ticker=ticker, d=d).exists():
                        print(f"Bar exists in TBGDaily, saving to DailyPrice: {d} {ticker}")
                        tb = TBGDailyBar.objects.get(ticker=ticker, d=d)
                        p = tb.c
                        DailyPrice.objects.create(ticker=ticker, d=d, c=p)
                    else:
                        print(f"Cannot find price in TBGDaily: {d} {ticker}")
                        print(f"Try https://www.barchart.com/futures/quotes/{ticker}/interactive-chart")
                        p = 0.0
                else:
                    d_bar, o, h, l, c, v, oi = bar
                    if d_bar != d:
                        print(f"Using price found on {d_bar} for {d} for {ticker}")
                    DailyPrice.objects.create(ticker=ticker, d=d, c=c)
                    p = c
    else:
        p = ticker.fixed_price

    # print(f"Got price for {ticker} for {d} = {p}")
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
