import pandas as pd
import numpy as np
from collections import defaultdict
from cachetools.func import ttl_cache
from django.conf import settings
from django.db.models import Sum, F, Q
from accounts.models import CashRecord
from worth.utils import is_near_zero
from worth.dt import day_start_next_day
from accounts.models import Account
from markets.models import get_ticker, NOT_FUTURES_EXCHANGES
from trades.models import Trade, get_futures_df, get_equity_df
from markets.utils import get_price


'''
weighted_average_price(t, a) - query db values q,p and calculate wap
get_balances(d, a, t) - query trades and cash,  calculate cash realized contributions, balances[k]=v
valuations(d, account, ticker) - use get_balances() for query - for each pos get price and value it.

These two functions get everything even if pos is zero or no trades in date range.
get_futures_pnl(a, d) - query trade sums and return [[t, p, pos, pnl]], total
get_equities_pnl(a, d) - same as get_futures_pnl but just equities

'''


def wap(data):
    # weighted average price
    n = len(data)

    #  close out lifo trades
    for i in range(1, n):
        (q, p) = data[i]
        for j in range(i - 1, -1, -1):
            q2 = data[j][0]
            if q * q2 >= 0.0:
                continue
            if abs(q) <= abs(q2):
                q2 += q
                q = 0
            else:
                q += q2
                q2 = 0
            data[j][0] = q2
            if is_near_zero(q):
                break
        data[i][0] = q

    # Calculate WAP
    pqsum = 0.0
    qsum = 0.0
    for x in data:
        (q, p) = x
        pqsum += p * q
        qsum += q

    if 0 == is_near_zero(qsum):
        wap = pqsum / qsum
    else:
        wap = 0.0
    return qsum, wap


def weighted_average_price(ticker, account=None):
    if type(ticker) == str:
        ticker = get_ticker(ticker)

    if account is None:
        qs = Trade.objects.filter(ticker=ticker).values_list('q', 'p').order_by('dt')
    else:
        if type(account) == str:
            account = Account.objects.get(name=account)
        qs = Trade.objects.filter(account=account, ticker=ticker).values_list('q', 'p').order_by('dt')
    return wap([list(i) for i in qs])


@ttl_cache(maxsize=1000, ttl=10)
def valuations(d=None, account=None, ticker=None):
    data = []

    balances = get_balances(d, account, ticker)

    ALL = 0
    for a in balances.keys():
        portfolio = balances[a]
        for ticker in portfolio.keys():
            t = get_ticker(ticker)
            m = t.market
            q = portfolio[ticker]
            if is_near_zero(q):
                continue

            p = get_price(t, d=d)

            if m.is_futures:
                # Need this for futures trades made outside MSRKIB
                open_price = weighted_average_price(t, account=a)
                value = q * (p - open_price) * m.cs
            else:
                value = q * p * m.cs

            ALL += value

            data.append([a, ticker, q, p, value])

    data.append(['ALL', 'CASH', '', '', '', ALL])

    return data


def add_sums(qs):
    return qs.annotate(pos=Sum(F('q')), qp=Sum(F('q') * F('p')), c=Sum(F('commission')))


def pnl_calculator(qs, d=None):
    qs = add_sums(qs)
    result = []
    total = 0.0
    for ti, pos, qp, commission in qs:
        ticker = get_ticker(ti)
        market = ticker.market
        pos = int(pos)
        pnl = -qp
        if pos == 0:
            price = 0
        else:
            price = get_price(ticker, d)
            pnl += pos * price

        pnl *= market.cs
        pnl -= commission
        total += pnl
        result.append((ticker, pos, price, pnl))

    return result, total


def trades_qs(a, d):
    a = Account.objects.get(name=a)
    qs = Trade.objects.values_list('ticker__ticker').filter(account=a)

    if d is not None:
        dt = day_start_next_day(d)
        qs = qs.filter(dt__lt=dt)

    return qs


def get_futures_pnl(a='MSRKIB', d=None):
    def price_mapper(x):
        if x['q'] == 0:
            price = 0
        else:
            ti = get_ticker(x['t'])
            price = get_price(ti, d)
        return price

    df = get_futures_df(a=a)
    if d is not None:
        dt = day_start_next_day(d)
        mask = df['dt'] < dt
        df = df.loc[mask]

    df = df.astype({"q": int})

    df['qp'] = -df.q * df.p
    result = pd.pivot_table(df, index=["a", "t"],
                            aggfunc={'qp': np.sum, 'q': np.sum, 'cs': np.max, 'c': np.sum}).reset_index(['a', 't'])
    result['price'] = result.apply(lambda x: price_mapper(x), axis=1)
    result['pnl'] = result.cs * (result.qp + result.q * result.price) - result.c
    result['value'] = result.cs * result.q * result.price

    result = result.drop(['c', 'cs', 'qp'], axis=1)

    return result


@ttl_cache(maxsize=1000, ttl=10)
def get_equties_pnl(a, d=None):
    df = get_equity_df(a)
    qs = trades_qs(a, d).filter(Q(ticker__market__ib_exchange__in=NOT_FUTURES_EXCHANGES))
    return pnl_calculator(qs, d=d)


def get_balances(d=None, account=None, ticker=None):
    # balances[<account>]->[<ticker>]-><qty>
    balances = defaultdict(lambda: defaultdict(lambda: 0.0))

    qs = Trade.more_filtering(account, ticker)
    if d is not None:
        dt = day_start_next_day(d)
        qs = qs.filter(dt__lt=dt)

    qs = qs.filter(ticker__market__ib_exchange__in=NOT_FUTURES_EXCHANGES)
    qs = qs.values_list('account__name', 'ticker__ticker', 'q', 'p', 'commission', 'ticker__market__cs', 'reinvest')
    for a, ti, q, p, c, cs, reinvest in qs:
        portfolio = balances[a]

        if not reinvest:
            cash_amount = -q * p * cs - c
            portfolio['CASH'] += cash_amount

        portfolio[ti] += q

    qs = CashRecord.objects.filter(ignored=False)
    if d is not None:
        qs = qs.filter(d__lte=d)
    if account is not None:
        qs = qs.filter(account__name=account)

    qs = qs.values('account__name').order_by('account__name').annotate(total=Sum('amt'))
    for result in qs:
        total = result['total']
        if abs(total) < 0.001:
            continue
        a = result['account__name']
        balances[a]['CASH'] += total

    qs = Trade.more_filtering(account, ticker).values_list('account__name')
    if d is not None:
        qs = qs.filter(dt__lt=dt)
    futures_accounts = qs.filter(~Q(ticker__market__ib_exchange__in=NOT_FUTURES_EXCHANGES)).distinct()

    for a in set([i[0] for i in futures_accounts]):
        f = get_futures_pnl(d=d, a=a)
        total = f.pnl.sum()
        balances[a]['CASH'] += total

    for a in balances:
        balances[a] = {k: v for k, v in balances[a].items() if abs(v) > 0.001}
    balances = {k: v for k, v in balances.items() if len(v.keys())}

    # Scale results for demo purposes.  PPM_FACTOR defaults to False.
    factor = settings.PPM_FACTOR
    if factor is not False:
        for k, v in balances.items():
            for j in v.keys():
                v[j] *= factor

    return balances
