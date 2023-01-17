import re
from datetime import datetime, date
from cachetools import cached
from django.db import IntegrityError
from markets.models import TBGDailyBar, Market, Ticker
from markets.tbgyahoo import yahooHistory


def tbg_ticker2ticker(ticker):
    try:
        ticker = Ticker.objects.get(ticker=ticker)
        return ticker
    except Ticker.DoesNotExist:
        print(f"{ticker} not found, trying to make it.")

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


def insert(ti, d, o, h, l, c, v=0, oi=0):
    if '-' in d:
        d = datetime.strptime(d, '%Y-%m-%d')
    elif '/' in d:
        d = datetime.strptime(d, '%m/%d/%Y')
    else:
        d = datetime.strptime(d, '%Y%m%d')
    d = date(d.year, d.month, d.day)
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
            bar = TBGDailyBar.objects.update_or_create(ticker=ticker, d=d,
                                                       defaults={'o': o, 'h': h, 'l': l, 'c': c, 'v': v, 'oi': oi})
        except IntegrityError as e:
            print(e)
            print(f'Could not add {ti} {d} {o} {h} {l} {c} {oi}')


def process_line(line):
    id, d, o, h, l, c, v, oi, ti = line.strip().split(',')
    insert(ti, d, o, h, l, c, v, oi)


def do_csv():
    fn = 'dailybars.csv'
    fh = open(fn, 'r')
    l = fh.readline()
    while True:
        l = fh.readline()
        if '' == l:
            break
        process_line(l)
    fh.close()


def do_txt():
    txt = '''
    AAL20210716P5.00 20210128 0.550 0.550 0.550 0.550
    AAL20210716P5.00 20210129 0.405 0.405 0.405 0.405
    AAL20210716P5.00 20210225 0.160 0.160 0.160 0.160
    AAL20210716P5.00 20210226 0.130 0.130 0.130 0.130
    UAL20210618P18.00 20210128 0.180 0.180 0.180 0.180
    UAL20210618P18.00 20210129 0.250 0.250 0.250 0.250
    UAL20210618P18.00 20210225 0.065 0.065 0.065 0.065
    UAL20210618P18.00 20210226 0.325 0.325 0.325 0.325
    QQQ210115P290 20201231 1.180 1.180 1.180 1.180
    ACTC 20210128 23.59 24.39 22.5 23.32
    ACTC 20210129 23.4 24.47 22.48 23.97
    ACTC 20210225 22.5 23.45 20.71 21.09
    ACTC 20210226 21.07 21.706 19.51 20.79
    ACTC 20210330 15.6 15.95 15 15.67
    ACTC 20210331 17 18.23 16.46 17.88
    ACTC 20210429 17.45 17.484 16.5 16.67
    ACTC 20210430 16.03 16.399 16 16.18
    FLIR 20201231 43.56 43.99 43.39 43.83
    FLIR 20210128 54.50 54.745 52.86 52.88
    FLIR 20210129 54.90 53.08 51.82 52.05
    FLIR 20210225 54.76 55.00 53.33 53.62
    FLIR 20210226 53.65 54.73 52.95 54.57
    FLIR 20210330 55.89 56.20 55.62 56.04
    FLIR 20210331 56.47 56.11 56.84 56.09
    FLIR 20210429 60.30 60.38 60.66 60.18
    FLIR 20210430 59.97 59.96 60.39 59.95
    MNDT 20210729 22.78 22.78 22.80 22.75
    MNDT 20210830 22.86 22.86 22.88 22.85
    MNDT 20210929 17.79 17.89 17.52 17.56
    MNDT 20211028 17.31 17.56 17.26 17.51
    MNDT 20211129 17.23 17.58 17.18 17.24
    MNDT 20211229 17.4282 17.79 17.4282 17.56
    MNDT 20220128 14.16 14.24 13.755 14.24
    MNDT 20220225 18.70 19.33 18.2214 19.30
    '''

    txt = '''
    CTXS 20200528 139.31 142.79 139.0163 141.19
    CTXS 20200629 142.46 145.399 141.03 144.82
    CTXS 20200730 138.40 152.01 136.93 141.69
    CTXS 20200828 143.08 146.49 142.62 144.03
    CTXS 20200929 137.92 139.05 136.89 136.95
    CTXS 20201029 115.01 116.13 113.70 113.92
    CTXS 20201127 121.73 123.94 120.60 122.44
    NGJ2020 20200227 1.748 1.750 1.740 1.740
    QQQ210115P290 20201230 1.155 1.155 1.155 1.155
    SPY200331P289 20200228 9.725 9.725 9.725 9.725
    SPY200331P310 20200227 18.925 18.925 18.925 18.925
    SPY200619P220 20200429 1.090 1.090 1.090 1.090
    SPY200619P220 20200430 1.345 1.345 1.345 1.345
    SPY200619P220 20200528 0.155 0.155 0.155 0.155
    SPY200619P220 20200529 0.125 0.125 0.125 0.125
    SPY200821P280 20200730 0.470 0.470 0.470 0.470
    SPY200821P280 20200731 0.395 0.395 0.395 0.395
    USO210115C4 20200429 0.110 0.110 0.110 0.110
    USO210115C4 20200430 0.160 0.160 0.160 0.160
    WORK 20190530 3.75 3.77 3.68 3.77
    WORK 20190531 3.75 3.77 3.68 3.77
    '''

    txt = '''
    AAL20210716P5.00	    20201127 0.32
    AAL20210716P5.00	    20201130 0.32
    AAL20210716P5.00	    20201230 0.19
    AAL20210716P5.00	    20201231 0.19
    AAPL150731C00128000	    20150630 2.720
    AAPL150731C00128000	    20150730 0.015
    AAPL150731C00128000	    20150731 0.005
    AAPL151211C00119000	    20151130 1.355
    AAPL20150501C132	    20150429 0.16
    AAPL20150501C132	    20150430 0.15
    SPY200415P220		    20200330 2.385
    SPY200415P220		    20200331 2.300
    UAL20210618P18.00	    20201127 0.375
    UAL20210618P18.00	    20201130 0.465
    UAL20210618P18.00	    20201230 0.350
    UAL20210618P18.00	    20201231 0.325
    USO210115C2		        20200429 0.570
    USO210115C2             20200430 0.710
    '''

    for line in txt.split('\n'):
        line = line.strip()
        if not line:
            continue

        items = line.split()
        if len(items) == 3:
            ti, d, c = items
            o = h = l = 0
        else:
            ti, d, o, h, l, c = items
        print(f'{ti} {d} {o} {h} {l} {c}')
        insert(ti, d, o, h, l, c)


def do_investing_com(ticker):
    fn = f'/Users/ms/Downloads/{ticker}.csv'
    with open(fn, 'r') as fh:
        l = fh.readline()
        while len(l):
            l = fh.readline()
            l = l.replace('"', '')
            if not l:
                continue
            # NOTE: Price is before ohl
            print(l)
            try:
                d, c, o, h, l, _, _ = l.strip().split(',')
            except ValueError as e:
                print(e)

            insert(ticker, d, o, h, l, c)


# May 16, 2019 - July 10, 2019
def copy_bevvf_to_bee():
    #  BEVVF prices are good enough for estimating portfolio values
    bevvf = Ticker.objects.get(ticker='BEVVF')
    data = yahooHistory(bevvf)
    # fd = date(2019, 5, 16)
    # ld = date(2019, 7, 10)

    ticker = 'BEE'
    for d, o, h, l, c, v, oi in data:
        print(ticker, d, c)
        # insert(ticker, str(d), o, h, l, c, v=0, oi=0)
