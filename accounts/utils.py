from datetime import date
import json
from cachetools.func import ttl_cache
from django.utils.safestring import mark_safe
from .models import Account, Receivable


@ttl_cache(maxsize=1000, ttl=10)
def get_account_url(a):
    img = '<img src="/static/img/chart.png" height="15">'

    if type(a) is str:
        try:
            a = Account.objects.get(name=a)
        except Account.DoesNotExist:
            if "ALL" == a:
                a = f'{a}<a href="/value_chart" target="_blank">{img}</a>'
            return mark_safe(a)

    if type(a) is Account:
        chart_url = f'<a href="/value_chart?accnt={a.name}" target="_blank">{img}</a>'
        diff_url = f'<a href="/difference?accnt={a.name}" target="_blank">Diff</a>'
        if a.url is None:
            a = f"{a.name}{chart_url}"
        else:
            a = (
                f'<a href={a.url} target="_blank">{a.name}</a>{chart_url} '
                f"{diff_url}"
            )

    return mark_safe(a)


def get_active_accounts():
    accounts = Account.objects.filter(active_f=True).order_by("id").all()
    return [(a.id, get_account_url(a), a.reconciled_f) for a in accounts]


def get_receivables(y=None):
    if y is None:
        y = date.today().year

    formats = json.dumps(
        {
            "columnDefs": [
                {"targets": [0], "className": "dt-nowrap"},
                {"targets": [1, 2, 3], "className": "dt-body-right"},
            ],
            "pageLength": 100,
        }
    )

    headings = ["Client", "Date Received", "Invoice", "Amt"]

    total = 0
    data = []
    for i in Receivable.objects.filter(received__year=y).order_by("client").all():
        data.append([i.client, i.received, i.invoice, i.amt])
        total += i.amt

    data.append(["Total", "", "", total])

    return headings, data, formats
