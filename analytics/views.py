from datetime import datetime

from django.views.generic.base import TemplateView
from analytics.cash import cash_sums, total_cash
from analytics.pnl import futures_pnl, year_pnl
from trades.ib_flex import get_trades
from worth.dt import lbd_prior_month, our_now
from markets.tbgyahoo import yahoo_url
from markets.models import Ticker
from trades.utils import weighted_average_price


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
            n = 0
            if d.isnumeric():
                n = int(d)
                d = our_now()
                while n > 0:
                    d = lbd_prior_month(d)
                    n -= 1
            else:
                d = datetime.strptime(d, '%Y%m%d').date()
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
        context['title'] = yahoo_url(ticker)
        pos, wap = weighted_average_price(ticker)
        context['pos'] = pos
        context['open_price'] = wap
        return context
