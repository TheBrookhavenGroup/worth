from cachetools.func import ttl_cache
from django.utils.safestring import mark_safe
from .models import Account


@ttl_cache(maxsize=1000, ttl=10)
def get_account_url(a):
    if type(a) is str:
        try:
            a = Account.objects.get(name=a)
        except Account.DoesNotExist:
            return a

    img = '<img src="/static/img/chart.png" height="15">'

    if type(a) is Account:
        if a.url is not None:
            a = f'<a href={a.url} target="_blank">{a.name}</a>' + \
                f'<a href="/value_chart?accnt={a.name}" target="_blank">{img}</a>'
            a = mark_safe(a)
        else:
            a = a.name

    return a


def get_active_accounts():
    accounts = Account.objects.filter(active_f=True).all()
    return [get_account_url(a) for a in accounts]
