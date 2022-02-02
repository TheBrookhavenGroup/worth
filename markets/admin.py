from django.contrib import admin
from .models import Market, Ticker


@admin .register(Market)
class MarketAdmin(admin.ModelAdmin):
    list_display = ('symbol', 'name')
    list_filter = ('ib_exchange', )


@admin .register(Ticker)
class TickerAdmin(admin.ModelAdmin):
    list_display = ('ticker', 'market')
