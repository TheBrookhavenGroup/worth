
from cachetools.func import ttl_cache
from django.db import transaction
from moneycounter.dt import dt2dt
from accounts.models import Account, CashRecord
from markets.models import Market, Ticker
from trades.models import Trade


account = Account.objects.get(name='FUTURES')


@ttl_cache(maxsize=500, ttl=10)
def get_market(s):
    try:
        m = Market.objects.get(symbol=s)
    except Market.DoesNotExist:
        print(f'Making market for {s}')
        m = Market.objects.get_or_create(symbol=s, name=s,
                                         ib_exchange='CME', yahoo_exchange='CME')
        m = m[0]
    return m


@transaction.atomic
def add_trades():
    fn = '/Users/ms/Documents/dev/ALL/futures_trades.csv'
    # "id", "cash_accnt", "d", "t", "reinv_f", "q", "p", "c", "c_f", "note", "account", "ticker"
    with open(fn) as fh:
        lines = fh.readlines()

    for line in lines:
        line = line.replace('"', '')
        line = line.replace("'", '')
        id, cash_account, d, t, reinv_f, q, p, c, c_f, note, a, ticker = line.split(',')
        dt = f"{d} {t}"

        dt = dt2dt(dt)
        q = float(q)
        p = float(p)
        c = float(c)

        t, exchange = ticker.split('.')
        t = t[:-2] + '20' + t[-2:]

        print(f"{t} {dt} {q} {p} {c}")

        try:
            ticker = Ticker.objects.get(ticker=t)
        except Ticker.DoesNotExist as e:
            market = get_market(t[:-5])
            print(f"Creating ticker {t}.")
            ticker = Ticker(ticker=t, market=market)
            ticker.save()

        trade = Trade(dt=dt, account=account, ticker=ticker, q=q, p=p, commission=c, note=note)
        trade.save()


add_trades()
