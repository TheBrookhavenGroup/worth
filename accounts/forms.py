from datetime import date
from django.forms import (
    Form,
    MultipleChoiceField,
    CheckboxSelectMultiple,
    ModelChoiceField,
    DecimalField,
    DateField,
    DateInput,
)
from accounts.utils import get_active_accounts
from .models import Account


class AccountForm(Form):
    accounts = MultipleChoiceField(
        widget=CheckboxSelectMultiple(attrs={"onclick": "this.form.submit();"}),
        choices=[],
        required=False,
    )

    def __init__(self, *args, **kwargs):
        # Set the accounts field choices each time the form is rendered.
        super().__init__(*args, **kwargs)
        a = get_active_accounts()
        self.fields["accounts"].choices = [i[:2] for i in a]
        self.fields["accounts"].initial = [i[0] for i in a if i[2]]


class CashTransferForm(Form):
    d = DateField(
        label="Transaction Date",
        widget=DateInput(attrs={"type": "date"}),
        initial=date.today(),
    )
    from_account = ModelChoiceField(queryset=None)
    to_account = ModelChoiceField(queryset=None)
    amt = DecimalField(max_digits=10, decimal_places=2, min_value=0.01)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["from_account"].queryset = Account.objects.filter(active_f=True).all()
        self.fields["to_account"].queryset = Account.objects.filter(active_f=True).all()


class DifferenceForm(Form):
    amt = DecimalField(
        label="Statement cash blance", max_digits=10, decimal_places=2, min_value=0.01
    )
