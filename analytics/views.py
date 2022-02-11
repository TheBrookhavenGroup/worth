from django.views.generic.base import TemplateView
from .cash import cash_sums
from markets.tbgyahoo import yahooQuote

class CheckingView(TemplateView):
    template_name = 'analytics/checking.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        account_name = 'BofA'
        context['account'] = account_name
        balance, statement_balance = cash_sums(account_name)
        context['balance'] = balance
        context['statement_balance'] = statement_balance
        context['aapl_price'] = yahooQuote('AAPL')
        return context
