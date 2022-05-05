
from collections import defaultdict
from cachetools.func import ttl_cache
from django.conf import settings
from django.db.models import Sum, F, Q
from accounts.models import CashRecord
from worth.utils import is_near_zero
from worth.dt import day_start_next_day
from accounts.models import Account
from markets.models import Ticker, NOT_FUTURES_EXCHANGES
from trades.models import Trade
from markets.utils import get_price


@ttl_cache(maxsize=1000, ttl=10)
def valuations(d=None, account=None, ticker=None):
    data = []

    balances = get_balances(d, account, ticker)

    ALL = 0
    for a in balances.keys():
        portfolio = balances[a]
        for ticker in portfolio.keys():
            t = Ticker.objects.get(ticker=ticker)
            m = t.market
            q = portfolio[ticker]
            if is_near_zero(q):
                continue

            p = get_price(t, d=d)

            if m.is_futures:
                # Need this for futures trades made outside MSRKIB
                value = q * (p - avg_open_price(a, t)) * m.cs
            else:
                value = q * p * m.cs

            ALL += value

            data.append([a, ticker, q, p, value])

    data.append(['ALL', 'CASH', '', '', ALL])

    return data


def pnl_calculator(qs, d=None):
    qs = qs.annotate(pos=Sum(F('q')),
                     qp=Sum(F('q') * F('p')),
                     c=Sum(F('commission')))
    result = []
    total = 0.0
    for ti, pos, qp, commission in qs:
        ticker = Ticker.objects.get(ticker=ti)
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


@ttl_cache(maxsize=1000, ttl=10)
def get_futures_pnl(a='MSRKIB', d=None):
    qs = trades_qs(a, d).filter(~Q(ticker__market__ib_exchange__in=NOT_FUTURES_EXCHANGES))
    return pnl_calculator(qs, d=d)


@ttl_cache(maxsize=1000, ttl=10)
def get_equties_pnl(a, d=None):
    qs = trades_qs(a, d).filter(Q(ticker__market__ib_exchange__in=NOT_FUTURES_EXCHANGES))
    return pnl_calculator(qs, d=d)


def avg_open_price(account, ticker):
    if type(account) == str:
        account = Account.objects.get(name=account)

    if type(ticker) == str:
        ticker = Ticker.objects.get(ticker=ticker)

    pos = 0
    qp_sum = 0
    commissions = 0
    # Use LIFO
    qs = Trade.objects.filter(account=account, ticker=ticker).values_list('q', 'p', 'commission').order_by('dt')
    for q, p, c in qs:
        if is_near_zero(pos + q):
            qp_sum = 0
            pos = 0
            commissions = 0
        else:
            if q * pos < 0:
                qp_sum *= 1 - abs(q) / pos
                commissions -= c
            else:
                qp_sum += q * p
                commissions += c

            pos += q

    if is_near_zero(pos):
        avg_price = 0.0
    else:
        avg_price = (qp_sum - commissions) / pos

    return avg_price


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
        pnl, total = get_futures_pnl(d=d, a=a)
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
