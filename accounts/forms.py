from django.forms import Form, MultipleChoiceField, CheckboxSelectMultiple
from accounts.utils import get_active_accounts


class AccountForm(Form):
    accounts = MultipleChoiceField(widget=CheckboxSelectMultiple(attrs={'onclick': 'this.form.submit();'}),
                                   choices=[])

    def __init__(self, *args, **kwargs):
        # Set the accounts field choices each time the form is rendered.
        super().__init__(*args, **kwargs)
        a = get_active_accounts()
        self.fields['accounts'].choices = [i[:2] for i in a]
        self.fields['accounts'].initial = [i[0] for i in a if i[2]]
