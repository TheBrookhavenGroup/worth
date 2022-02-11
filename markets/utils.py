from markets.tbgyahoo import yahooHistory
from markets.models import DailyBar


def populate_historical_price_data(ticker, d_i=None, d_f=None):
    data = yahooHistory(ticker.yahoo_ticker)
    print(ticker)
    for d, o, h, l, c, v, oi in data:
        if (d_i is not None) and (d < d_i):
            continue
        if (d_f is not None) and (d > d_f):
            continue
        DailyBar(ticker=ticker, d=d, o=o, h=h, l=l, c=c, v=v, oi=oi).save()
