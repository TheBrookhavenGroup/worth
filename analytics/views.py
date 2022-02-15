from django.views.generic.base import TemplateView
from analytics.cash import cash_sums
from analytics.ppm import valuations


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
    template_name = 'analytics/ppm.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['headings1'], context['data1'] = valuations()
        return context
