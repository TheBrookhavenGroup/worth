from datetime import datetime, date
import json

from django.views.generic.base import TemplateView
from analytics.cash import cash_sums, total_cash
from analytics.pnl import futures_pnl, year_pnl
from trades.ib_flex import get_trades
from worth.dt import lbd_prior_month, our_now, lbd_of_month
from worth.utils import is_near_zero
from markets.tbgyahoo import yahoo_url
from markets.models import Ticker
from trades.utils import weighted_average_price, valuations
from markets.utils import get_price, ticker_admin_url


class CheckingView(TemplateView):
    template_name = 'analytics/checking.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        account_name = 'BofA'
        context['account'] = account_name
        balance, statement_balance = cash_sums(account_name)
        context['balance'] = balance
        context['statement_balance'] = statement_balance
        return context


class PPMView(TemplateView):
    template_name = 'analytics/table.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        getter = self.request.GET.get
        ticker = getter('ticker')
        account = getter('account')

        d = getter('d')
        if d is not None:
            try:
                d = datetime.strptime(d, '%Y%m%d').date()
            except Exception:
                n = 0
                if d.isnumeric():
                    n = int(d)
                    d = our_now()
                    while n > 0:
                        d = lbd_prior_month(d)
                        n -= 1

            context['d'] = d
        context['headings1'], context['data1'], context['formats'] = \
            year_pnl(d=d, account=account, ticker=ticker)
        context['title'] = 'PPM'
        return context


class FuturesPnLView(TemplateView):
    template_name = 'analytics/table.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        getter = self.request.GET.get

        d = getter('d')
        if d is not None:
            d = datetime.strptime(d, '%Y%m%d').date()

        context['headings1'], context['data1'], context['formats'] = futures_pnl(d=d)
        context['title'] = 'Futures PnL'
        return context


class TotalCashView(TemplateView):
    template_name = 'analytics/total_cash.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        getter = self.request.GET.get
        context['total_cash'] = total_cash()
        return context


class GetIBTradesView(TemplateView):
    template_name = 'analytics/table.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['headings1'], context['data1'], context['formats'] = get_trades()
        context['title'] = 'IB Futures Trades'
        return context


class TickerView(TemplateView):
    template_name = 'analytics/ticker.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ticker = Ticker.objects.get(ticker=context['ticker'])
        context['tickeradmin'] = ticker_admin_url(self.request, ticker)
        context['title'] = yahoo_url(ticker)
        context['description'] = ticker.description
        pos, wap = weighted_average_price(ticker)
        if is_near_zero(pos):
            context['msg'] = 'Zero position.'
        else:
            context['pos'] = pos
            context['open_price'] = wap

            try:
                price = get_price(ticker)
                context['price'] = price
                context['capital'] = pos * price
                context['pnl'] = ticker.market.cs * pos * (price - wap)
            except IndexError:
                context['msg'] = 'Could not get a price for this ticker.'

        return context


class ValueChartView(TemplateView):
    title = 'Value Chart'
    template_name = 'analytics/value_chart.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        getter = self.request.GET.get

        d = datetime.today().date()
        n_months = getter('n_months')
        if n_months is not None:
            x_axis = [d] + [d := lbd_prior_month(d) for i in range(int(n_months))]
            x_axis.reverse()
        else:
            y = d.year
            m = d.month
            x_axis = [lbd_of_month(date(y, i, 1)) for i in range(1, m)]
            x_axis.append(d)

        accnt = getter('accnt')

        def get_all(v):
            return sum([i[-1] / 1.e6 for i in v if i[0] != 'ALL'])

        y_axis = [get_all(valuations(i, account=accnt)) for i in x_axis]
        x_axis = [f'{d:%Y-%m}' for d in x_axis]

        options = {
            "series": [{"name": "Value", "data": y_axis}],
            "chart": {"height": 350, "type": 'line', "zoom": {"enabled": True}},
            "dataLabels": {"enabled": False},
            "stroke": {"curve": "straight"},
            "title": {"text": self.title, "align": 'center', 'offsetY': 10},
            "grid": {"row": {"colors": ['#f3f3f3', 'transparent'], "opacity": 0.5}},
            "xaxis": {"categories": x_axis},
            "yaxis": {'decimalsInFloat': 2},
        }

        context['options'] = json.dumps(options)
        context['title'] = self.title
        context['exclude_quick_links_caption'] = True
        return context
