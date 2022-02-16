from django.contrib import admin
from .models import Account, CashRecord


@admin .register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('name', )


def set_cleared_flag(modeladmin, request, qs):
    for rec in qs:
        rec.cleared_f = True
        rec.save()


@admin .register(CashRecord)
class CashRecordAdmin(admin.ModelAdmin):
    date_hierarchy = 'd'
    list_display = ('account', 'd', 'description', 'amt', 'cleared_f')
    list_filter = ('cleared_f', 'account')
    search_fields = ('account', 'description')
    ordering = ('account', '-d')
    actions = [set_cleared_flag]
