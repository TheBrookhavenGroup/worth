from django.contrib import admin
from .models import Trade
from accounts.admin import ActiveAccountFilter


@admin.register(Trade)
class MarketAdmin(admin.ModelAdmin):
    def time_date(self, obj):
        return obj.dt.date()
    time_date.short_description = 'Date'

    date_hierarchy = 'dt'

    list_display = ('time_date', 'account', 'ticker', 'q', 'p', 'commission', 'note')
    list_filter = (ActiveAccountFilter, )
    search_fields = ('account__name', 'dt', 'note', 'ticker__ticker')
    ordering = ('account', '-dt')
