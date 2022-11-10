from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, FormView
from accounts.statement_utils import ib_statements
from .forms import AccountForm
from .models import Account


class GetIBStatementsView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/ib_statements.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filenames'] = ib_statements()
        context['title'] = 'IB Statements Retrieved'
        return context


class AccountsView(LoginRequiredMixin, FormView):
    template_name = 'accounts/accounts.html'
    form_class = AccountForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Accounts'
        return context

    def post(self, request, *args, **kwargs):
        context = self.get_context_data()
        form = self.form_class(request.POST)
        if form.is_valid():
            ids = [int(i) for i in form.cleaned_data['accounts']]
            Account.objects.all().update(reconciled_f=False)
            Account.objects.filter(id__in=ids).update(reconciled_f=True)

        return render(request, self.template_name, {'form': form})
