from django.views.generic.base import TemplateView
from accounts.statement_utils import ib_statements


class GetIBStatementsView(TemplateView):
    template_name = 'accounts/ib_statements.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filenames'] = ib_statements()
        context['title'] = 'IB Statements Retrieved'
        return context
