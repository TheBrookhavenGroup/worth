import re
from django.db import transaction
from worth.utils import dt2dt
from accounts.models import Account, CashRecord
from markets.models import Market, Ticker
from trades.models import Trade


account = Account.objects.get(name='FUTURES')


@transaction.atomic
def add_trades():
    fn = '/Users/ms/Documents/dev/worth/futures_trades.csv'
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
            market = Market.objects.get(symbol=t[:-5])
            print(f"Creating ticker {t}.")
            ticker = Ticker(ticker=t, market=market)
            ticker.save()

        trade = Trade(dt=dt, account=account, ticker=ticker, q=q, p=p, commission=c, note=note)
        trade.save()


add_trades()
