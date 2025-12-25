from django import forms
from accounts.models import Account
from trades.models import Trade


def list_accounts_without_trades(active_f=True):
    qs = Account.objects.filter(active_f=active_f).exclude(
        id__in=list(Trade.objects.values_list("account__id", flat=True))
    )
    return qs


class PnLForm(forms.Form):
    account = forms.ModelChoiceField(queryset=None, required=False)
    days = forms.IntegerField(min_value=0, required=False, help_text="How many days back?")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = Account.objects.filter(active_f=True).all()


class CheckingForm(forms.Form):
    account = forms.ModelChoiceField(queryset=None, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = list_accounts_without_trades()
