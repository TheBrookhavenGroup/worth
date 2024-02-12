from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.db.models import Q
from django.contrib import messages
from tbgutils.dt import our_now, day_start, prior_business_day
from markets.models import NOT_FUTURES_EXCHANGES
from accounts.models import Account
from trades.models import Trade
from trades.ib_flex import get_trades, lbd


class GetTradesFilter(SimpleListFilter):
    title = "Get Trades"
    parameter_name = 'new_trades'

    def lookups(self, request, model_admin):
        return [('today', 'Today'), ('lbd', 'LBD')]

    def queryset(self, request, queryset):

        if self.value() is not None:
            if 'lbd' == self.value():
                get_trades(report_id=lbd)
                t = day_start(prior_business_day())
            else:
                get_trades()
                t = day_start(our_now())
            return queryset.filter(dt__gte=t)
        return queryset


class NoCommissionFilter(SimpleListFilter):
    title = "No Commission"
    parameter_name = 'no_commission'

    def lookups(self, request, model_admin):
        return [('no', 'No Commission')]

    def queryset(self, request, queryset):
        if 'no' == self.value():
            return queryset.filter(commission__range=(-0.001, 0.001))
        return queryset


class ExchangeTypeFilter(SimpleListFilter):
    title = "Exchange Type"
    parameter_name = 'exchange_type'

    def lookups(self, request, model_admin):
        return [('futures', 'Futures'), ('equities', 'Equities')]

    def queryset(self, request, queryset):
        v = self.value()
        if 'futures' == v:
            return queryset.filter(
                ~Q(ticker__market__ib_exchange__in=NOT_FUTURES_EXCHANGES))
        elif 'equities' == v:
            return queryset.filter(
                ticker__market__ib_exchange__in=NOT_FUTURES_EXCHANGES)
        return queryset


class IsActiveAccountFilter(SimpleListFilter):
    title = "Active Accounts Only"
    parameter_name = 'activeaccount'

    def lookups(self, request, model_admin):
        return [('active', 'Active'), ('not_active', 'Not Active')]

    def queryset(self, request, queryset):
        v = self.value()
        if v:
            flag = 'active' == v
            return queryset.filter(account__active_f=flag)
        return queryset


class TradesAccountFilter(SimpleListFilter):
    title = "Active Account"
    parameter_name = 'active_account'

    def lookups(self, request, model_admin):
        active = Account.objects.filter(active_f=True).all()
        return [(a.id, a.name) for a in active]

    def queryset(self, request, queryset):
        v = self.value()
        if v:
            return queryset.filter(account_id=v)
        return queryset


class BuySellFilter(SimpleListFilter):
    title = "Buy/Sell"
    parameter_name = 'buy_sell'

    def lookups(self, request, model_admin):
        return [('buy', 'Buy'), ('sell', 'Sell')]

    def queryset(self, request, queryset):
        v = self.value()
        if 'buy' == v:
            return queryset.filter(q__gte=0.0)
        elif 'sell' == v:
            return queryset.filter(q__lt=0.0)
        return queryset


class SplitsFilter(SimpleListFilter):
    title = "Splits"
    parameter_name = 'splits'

    def lookups(self, request, model_admin):
        return [('yes', 'Yes'), ('no', 'No')]

    def queryset(self, request, queryset):
        v = self.value()
        if 'yes' == v:
            return queryset.filter(reinvest=True, p__gt=-0.001, p__lt=0.001)
        elif 'no' == v:
            return queryset.filter(~Q(reinvest=True, p__gt=-0.001, p__lt=0.001))
        return queryset


def duplicate_record(modeladmin, request, qs):
    t = our_now()
    for rec in qs:
        new_rec = Trade(dt=t, account=rec.account, ticker=rec.ticker,
                        reinvest=rec.reinvest,
                        q=rec.q, p=rec.p, commission=rec.commission,
                        note=rec.note)
        new_rec.save()


def sum_commissions(modeladmin, request, qs):
    total = 0
    for rec in qs:
        total += rec.commission

    messages.add_message(request, messages.INFO, f"Sum commissions: {total}")


@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    def time_date(self, obj):
        return obj.dt.date()

    time_date.short_description = 'Date'

    date_hierarchy = 'dt'

    list_display = (
        'dt', 'account', 'ticker', 'q', 'p', 'commission', 'reinvest',
        'trade_id',
        'note')
    list_filter = (
        GetTradesFilter, NoCommissionFilter, BuySellFilter, ExchangeTypeFilter,
        TradesAccountFilter, IsActiveAccountFilter, SplitsFilter, 'reinvest')
    search_fields = ('account__name', 'dt', 'note', 'ticker__ticker')
    ordering = ('account', '-dt')
    actions = [duplicate_record, sum_commissions]
