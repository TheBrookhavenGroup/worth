from django.contrib import admin
from .models import Trade


@admin.register(Trade)
class MarketAdmin(admin.ModelAdmin):
    def time_date(self, obj):
        return obj.dt.date()
    time_date.short_description = 'Date'

    list_display = ('time_date', 'account', 'ticker', 'q', 'p', 'note')
    list_filter = ('account', )
    search_fields = ('account__name', 'dt', 'note', 'ticker__ticker')
    ordering = ('account', '-dt')
