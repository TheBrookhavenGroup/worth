import re
from datetime import datetime
from cachetools import cached
from django.db import IntegrityError
from markets.models import DailyBar, Market, Ticker


def tbg_ticker2ticker(ticker):
    if len(re.findall("\.", ticker)) != 1:
        return None
    symbol, exchange = ticker.split('.')
    symbol, mo, yr = symbol[:-3], symbol[-3:-2], symbol[-2:]

    try:
        m = Market.objects.get(symbol=symbol)
    except Market.DoesNotExist:
        m = Market.objects.get_or_create(symbol=symbol, name=symbol, ib_exchange='CME', yahoo_exchange='CME')[0]

    yr = int(yr)
    if yr < 25:
        yr = 2000 + yr
    else:
        yr = 1900 + yr

    ticker = f"{symbol}{mo}{yr}"

    try:
        ticker = Ticker.objects.get(ticker=ticker)
    except Ticker.DoesNotExist:
        ticker = None
    return ticker


@cached(cache={})
def get_ticker(ticker):
    print(ticker)
    return tbg_ticker2ticker(ticker)


def process_line(line):
    id, d, o, h, l, c, v, oi, ti = line.strip().split(',')
    d = datetime.strptime(d, '%Y-%m-%d')
    o = float(o)
    h = float(h)
    l = float(l)
    c = float(c)
    v = int(v)
    if '' == oi:
        oi = 0
    else:
        oi = int(oi)

    ticker = get_ticker(ti)

    if ticker is None:
        print(f"No ticker for {ti}")
    else:
        try:
            bar = DailyBar.objects.create(ticker=ticker, d=d, o=o, h=h, l=l, c=c, v=v, oi=oi)
        except IntegrityError:
            print(f'Could not add {line}')


fn = 'dailybars.csv'
fh = open(fn, 'r')
l = fh.readline()
while True:
    l = fh.readline()
    if '' == l:
        break
    process_line(l)
fh.close()
