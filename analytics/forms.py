from django import forms
from accounts.models import Account


class PnLForm(forms.Form):
    account = forms.ModelChoiceField(queryset=Account.objects.all(), required=False)
    days = forms.IntegerField(min_value=0, required=False, help_text="How many days back?")
