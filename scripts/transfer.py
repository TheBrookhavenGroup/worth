# Transfer all stocks from TDA to MSRKCS2

from datetime import datetime
from tbgutils.dt import set_tz
from trades.models import Trade, get_trades_df
from markets.models import Ticker, DailyPrice
from accounts.models import Account, CashRecord
from trades.utils import open_position_pnl
from analytics.pnl import pnl


def transfer_cash_balance(d, a_from, a_to):
    *_, cash = pnl(d=d, a=a_from)
    print(float(cash))

    rec = CashRecord(account=a_from, d=d, description=note, amt=-cash)
    print(f"Cash: {rec}")
    rec.save()

    rec = CashRecord(account=a_to, d=d, description=note, amt=cash)
    print(f"Cash: {rec}")
    rec.save()


# Inputs
t = set_tz(datetime(2023, 11, 6, 16, 15))
d = t.date()
from_account = "TDA"
to_account = "MSRKCS2"

a_from = Account.objects.get(name=from_account)
a_to = Account.objects.get(name=to_account)
note = f"Transfer from {from_account} to {to_account}."

# Get prices
qs = DailyPrice.objects.filter(d=d).all()
prices = {i.ticker.ticker: i.c for i in qs}

# Get open positions not incluing cash
df = get_trades_df(a=from_account)
df = open_position_pnl(df)
positions = [(row["t"], row["position"]) for index, row in df.iterrows()]


# Process

transfer_cash_balance(d, a_from, a_to)

for ticker, pos in positions:
    p = prices[ticker]
    ticker = Ticker.objects.get(ticker=ticker)
    print(ticker, pos, p)

    rec = Trade(dt=t, account=a_to, ticker=ticker, q=pos, p=p, note=note)
    print(f"Trade: {rec}")
    rec.save()

    rec = Trade(dt=t, account=a_from, ticker=ticker, q=-pos, p=p, note=note)
    print(f"Trade: {rec}")
    rec.save()

    cash_note = f"Transfer {ticker.ticker} to {to_account}"
    rec = CashRecord(account=a_from, d=d, description=cash_note, amt=-pos * p)
    print(f"Cash: {rec}")
    rec.save()

    cash_note = f"Transfer {ticker.ticker} from {from_account}"
    rec = CashRecord(account=a_to, d=d, description=cash_note, amt=pos * p)
    print(f"Cash: {rec}")
    rec.save()

transfer_cash_balance(d, a_from, a_to)
