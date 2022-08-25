from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.db.models import Q
from worth.dt import our_now, day_start, prior_business_day
from markets.models import NOT_FUTURES_EXCHANGES
from trades.models import Trade
from trades.ib_flex import get_trades, lbd
from accounts.admin import ActiveAccountFilter


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
            return queryset.filter(~Q(ticker__market__ib_exchange__in=NOT_FUTURES_EXCHANGES))
        elif 'equities' == v:
            return queryset.filter(ticker__market__ib_exchange__in=NOT_FUTURES_EXCHANGES)
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


@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    def time_date(self, obj):
        return obj.dt.date()
    time_date.short_description = 'Date'

    date_hierarchy = 'dt'

    list_display = ('dt', 'account', 'ticker', 'q', 'p', 'commission', 'reinvest', 'trade_id', 'note')
    list_filter = (GetTradesFilter, NoCommissionFilter, BuySellFilter, ExchangeTypeFilter,
                   ActiveAccountFilter, SplitsFilter, 'reinvest')
    search_fields = ('account__name', 'dt', 'note', 'ticker__ticker')
    ordering = ('account', '-dt')
