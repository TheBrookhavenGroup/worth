from django.contrib import admin
from .models import Trade


@admin.register(Trade)
class MarketAdmin(admin.ModelAdmin):
    list_display = ('dt', 'account', 'ticker', 'q', 'p')
    list_filter = ('account', 'ticker')
    search_fields = ('dt', 'note')
    ordering = ('account', '-dt')
