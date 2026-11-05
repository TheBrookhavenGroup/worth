from calendar import month_name

from django import forms
from tbgutils.dt import our_now
from accounts.models import Account
from trades.models import Trade


def list_accounts_without_trades(active_f=True):
    qs = Account.objects.filter(active_f=active_f).exclude(
        id__in=list(Trade.objects.values_list("account__id", flat=True))
    )
    return qs


class PnLForm(forms.Form):
    month = forms.TypedChoiceField(
        choices=[(month, month_name[month]) for month in range(1, 13)],
        coerce=int,
        help_text="Past months use the last business day; the current month uses today.",
    )
    year = forms.TypedChoiceField(coerce=int)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        today = our_now().date()
        self.fields["year"].choices = [(year, year) for year in range(today.year, 1899, -1)]
        self.fields["month"].initial = today.month
        self.fields["year"].initial = today.year


class CheckingForm(forms.Form):
    account = forms.ModelChoiceField(queryset=None, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = list_accounts_without_trades()
