from django.contrib import admin
from .models import Market, Ticker, DailyBar
from .utils import populate_historical_price_data


@admin .register(Market)
class MarketAdmin(admin.ModelAdmin):
    list_display = ('symbol', 'name')
    list_filter = ('ib_exchange', )
    search_fields = list_display


def get_historical_prices(modeladmin, request, qs):
    for ticker in qs:
        populate_historical_price_data(ticker)


@admin .register(Ticker)
class TickerAdmin(admin.ModelAdmin):
    list_display = ('ticker', 'market')
    list_filter = ('market', )
    search_fields = ('ticker', )
    actions = [get_historical_prices, ]


@admin .register(DailyBar)
class DailyBarAdmin(admin.ModelAdmin):
    date_hierarchy = 'd'
    list_display = ('ticker', 'd', 'c')
    search_fields = ('=ticker__ticker', )
