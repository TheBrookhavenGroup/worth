from django.views.generic.base import TemplateView
from accounts.statement_utils import ib_statements
from accounts.utils import get_active_accounts


class GetIBStatementsView(TemplateView):
    template_name = 'accounts/ib_statements.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filenames'] = ib_statements()
        context['title'] = 'IB Statements Retrieved'
        return context


class AccountsView(TemplateView):
    template_name = 'accounts/accounts.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Accounts'
        context['accounts'] = get_active_accounts()
        return context
