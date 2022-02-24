import json
from django.conf import settings
from ib_insync.flexreport import FlexReport
from worth.utils import dt2dt
from accounts.models import Account
from trades.models import Trade
from markets.utils import ib_symbol2ticker


daily = '224849'
last30days = '646507'


def get_trades(report_id='224849'):
    formats = json.dumps({'columnDefs': [{'targets': [1], 'className': 'dt-body-left'}],
                          # 'ordering': False
                          })

    headings = ['Trade']
    data = []

    report = FlexReport(settings.FLEX_TOKEN, report_id)

    # print(report.topics())
    # {'TradeConfirm', 'FlexQueryResponse', 'FlexStatements', 'FlexStatement'}

    trades = report.extract('TradeConfirm')
    account = Account.objects.get(name='FUTURES')
    for i in trades:
        t = dt2dt(i.dateTime)
        ticker = ib_symbol2ticker(i.symbol)
        q = i.quantity
        if i.buySell == 'SELL':
            q *= -1
        try:
            trade = Trade.objects.get(trade_id=i.tradeID)
            trade.dt = t
            trade.ticker = ticker
            trade.q = q
            trade.p = i.price
            trade.commission = i.commission
        except Trade.DoesNotExist:
            trade = Trade(dt=t, account=account, ticker=ticker, reinvest=True,
                          q=q, p=i.price, commission=i.commission,
                          trade_id=i.tradeID)
        trade.save()
        data.append([str(trade)])

    return headings, data, formats
