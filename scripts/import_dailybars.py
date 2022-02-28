from datetime import datetime
from cachetools import cached
from django.db import IntegrityError
from markets.utils import tbg_ticker2ticker
from markets.models import DailyBar


@cached(cache={})
def get_ticker(ticker):
    print(ticker)
    return tbg_ticker2ticker(ticker)


def process_line(l):
    id, d, o, h, l, c, v, oi, ticker = l.strip().split(',')
    d = datetime.strptime(d, '%Y-%m-%d')
    o = float(o)
    h = float(h)
    l = float(l)
    c = float(c)
    v = int(v)
    oi = int(oi)
    ticker = get_ticker(ticker)

    try:
        bar = DailyBar.objects.create(ticker=ticker, d=d, o=o, h=h, l=l, c=c, v=v, oi=oi)
    except IntegrityError:
        print('Could not add {l}')


fn = 'dailybars.csv'
fh = open(fn, 'r')
l = fh.readline()
while True:
    l = fh.readline()
    if '' == l:
        break
    process_line(l)
fh.close()
