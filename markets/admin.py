from django.contrib import admin
from .models import Market, Ticker, DailyBar


@admin .register(Market)
class MarketAdmin(admin.ModelAdmin):
    list_display = ('symbol', 'name')
    list_filter = ('ib_exchange', )


@admin .register(Ticker)
class TickerAdmin(admin.ModelAdmin):
    list_display = ('ticker', 'market')


@admin .register(DailyBar)
class DailyBarAdmin(admin.ModelAdmin):
    list_display = ('ticker', 'c')
