from datetime import date, timedelta
from django.contrib import messages
from django.shortcuts import render
from django.db import transaction, IntegrityError
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, FormView
from accounts.statement_utils import ib_statements
from .utils import get_receivables
from .forms import AccountForm, CashTransferForm, DifferenceForm
from .models import Account, CashRecord
from analytics.cash import cash_sums


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

        return render(request, self.template_name, context)


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


class DifferenceView(LoginRequiredMixin, FormView):
    template_name = 'accounts/difference.html'
    form_class = DifferenceForm
    success_url = '/accounts/difference/'

    @staticmethod
    def parse_preserved(preserved_filters):
        x = preserved_filters.removeprefix('_changelist_filters=')
        x = dict([i.split('=') for i in x.split('&')])
        y, m, d = int(x['d__year']), int(x['d__month']), int(x['d__day'])
        d = date(y, m, d)
        a = x['active']
        name = Account.objects.get(id=int(a))
        return {'account_id': a, 'account': name, 'd': d}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Cash Balance Difference Calculator'

        try:
            x = self.parse_preserved(self.kwargs['preserved_filters'])
            context.update(x)
            account_id = x['account_id']
            d = x['d']
        except KeyError:
            d = date.today()
            d = date(d.year, d.month, 1)
            d -= timedelta(days=1)
            name = self.request.GET['accnt']
            a = Account.objects.get(name=name)
            account_id = a.id
            context['account_id'] = account_id
            context['account'] = name
            context['d'] = d

        _, total_cleared = cash_sums(account_id, d)
        context['total_cleared'] = total_cleared

        return context

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        form = self.form_class(request.POST)
        context = self.get_context_data(**kwargs)
        if form.is_valid():
            amt = form.cleaned_data['amt']

            _, total_cleared = cash_sums(context['account_id'], context['d'])
            context['total_cleared'] = total_cleared

            delta = float(amt) - total_cleared
            if delta > 0:
                context['delta_msg'] = ("Statement exceeds our records by")
            else:
                context['delta_msg'] = ("Our records exceed the statement by")
                delta = -delta

            context['delta'] = delta

        return render(request, self.template_name, context)
