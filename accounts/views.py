from django.contrib import messages
from django.shortcuts import render
from django.db import transaction, IntegrityError
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, FormView
from accounts.statement_utils import ib_statements
from .utils import get_receivables
from .forms import AccountForm, CashTransferForm
from .models import Account, CashRecord


class GetIBStatementsView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/ib_statements.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filenames'] = ib_statements(decrypt=True)
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


class ReceivablesView(LoginRequiredMixin, TemplateView):
    template_name = 'analytics/table.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['headings1'], context['data1'], context['formats'] = (
            get_receivables())
        context['title'] = 'Receivables'
        return context


class CashTransferView(LoginRequiredMixin, FormView):
    template_name = 'accounts/cash_transfer.html'
    form_class = CashTransferForm
    success_url = '/accounts/cash_transfer/'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Cash Transfer'
        return context

    def post(self, request, *args, **kwargs):
        form = self.form_class(request.POST)
        if form.is_valid():
            d = form.cleaned_data['d']
            from_accnt = form.cleaned_data['from_account']
            to_accnt = form.cleaned_data['to_account']
            amt = form.cleaned_data['amt']
            s = f"{d} from_account: {from_accnt}, " \
                f"to_account: {to_accnt}, amt: {amt}"
            try:
                with transaction.atomic():
                    CashRecord.objects.create(d=d, account=from_accnt, amt=-amt,
                                description=f"Transfer to {to_accnt}")
                    CashRecord.objects.create(d=d, account=to_accnt, amt=amt,
                                description=f"Transfer from {to_accnt}")
                messages.add_message(request, messages.INFO, s)
            except IntegrityError:
                messages.add_message(request, messages.ERROR, f"FAILED: {s}")

        return render(request, self.template_name, {'form': form})
