import json
from django.conf import settings
from ib_insync.flexreport import FlexReport, FlexError
from tbgutils.dt import dt2dt, set_tz
from accounts.models import Account
from trades.models import Trade
from markets.utils import ib_symbol2ticker


daily = '224849'
lbd = '224850'
last30days = '646507'


def get_trades(report_id='224849'):
    formats = json.dumps({'columnDefs': [{"targets": [0], 'className': "dt-nowrap"},
                                         {"targets": [1], 'className': "dt-body-left"},
                                         {'targets': [2, 3, 4], 'className': 'dt-body-right'}],
                          # 'ordering': False
                          })

    headings = ['Date-Time', 'Ticker', 'Q', 'P', 'Commission']
    data = []

    try:
        report = FlexReport(settings.IB_FLEX_TOKEN, report_id)
    except FlexError as e:
        msg = str(e)
        data.append([msg, '', '', '', ''])
        print(msg)
        return headings, data, formats

    # print(report.topics())
    # {'TradeConfirm', 'FlexQueryResponse', 'FlexStatements', 'FlexStatement'}

    trades = report.extract('TradeConfirm')
    account = Account.objects.get(name='MSRKIB')
    for i in trades:
        t = dt2dt(i.dateTime)
        ticker = ib_symbol2ticker(i.symbol)

        # do not need to scale i.price by tickers.ib_price_factor, flex already converted it to dollars.
        p = i.price
        q = i.quantity
        try:
            trade = Trade.objects.get(trade_id=i.tradeID)
            trade.dt = t
            trade.ticker = ticker
            trade.q = q
            trade.p = p
            trade.commission = -i.commission
        except Trade.DoesNotExist:
            trade = Trade(dt=t, account=account, ticker=ticker, q=q, p=p, commission=i.commission, trade_id=i.tradeID)
        trade.save()

        data.append([set_tz(trade.dt).strftime("%Y%m%d %H:%M:%S"), trade.ticker, trade.q, trade.p, trade.commission])

    return headings, data, formats
