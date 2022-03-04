from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.db.models import Q
from markets.models import NOT_FUTURES_EXCHANGES
from trades.models import Trade
from accounts.admin import ActiveAccountFilter


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
            return queryset.filter(~Q(ticker__market__ib_exchange__in=NOT_FUTURES_EXCHANGES))
        elif 'equities' == v:
            return queryset.filter(ticker__market__ib_exchange__in=NOT_FUTURES_EXCHANGES)
        return queryset


@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    def time_date(self, obj):
        return obj.dt.date()
    time_date.short_description = 'Date'

    date_hierarchy = 'dt'

    list_display = ('time_date', 'account', 'ticker', 'q', 'p', 'commission', 'reinvest', 'trade_id', 'note')
    list_filter = (NoCommissionFilter, ExchangeTypeFilter, ActiveAccountFilter)
    search_fields = ('account__name', 'dt', 'note', 'ticker__ticker')
    ordering = ('account', '-dt')
