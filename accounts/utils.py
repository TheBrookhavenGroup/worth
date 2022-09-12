from cachetools.func import ttl_cache
from django.utils.safestring import mark_safe
from .models import Account


@ttl_cache(maxsize=1000, ttl=10)
def get_account_url(a):
    img = '<img src="/static/img/chart.png" height="15">'

    if type(a) is str:
        try:
            a = Account.objects.get(name=a)
        except Account.DoesNotExist:
            if 'ALL' == a:
                a = f'{a}<a href="/value_chart" target="_blank">{img}</a>'
            return mark_safe(a)

    if type(a) is Account:
        chart_url = f'<a href="/value_chart?accnt={a.name}" target="_blank">{img}</a>'
        if a.url is None:
            a = f'{a.name}{chart_url}'
        else:
            a = f'<a href={a.url} target="_blank">{a.name}</a>{chart_url}'

    return mark_safe(a)


def get_active_accounts():
    accounts = Account.objects.filter(active_f=True).all()
    return [get_account_url(a) for a in accounts]
