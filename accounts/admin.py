from django.contrib import admin
from .models import Account, CashRecord
from worth.utils import our_now


@admin .register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('name', )


def set_cleared_flag(modeladmin, request, qs):
    for rec in qs:
        rec.cleared_f = True
        rec.save()


def duplicate_record(modeladmin, request, qs):
    d = our_now().date()
    for rec in qs:
        new_rec = CashRecord(d=d, description=rec.description, account=rec.account,
                             type=rec.type, category=rec.category, amt=rec.amt)
        new_rec.save()


@admin .register(CashRecord)
class CashRecordAdmin(admin.ModelAdmin):
    date_hierarchy = 'd'
    list_display = ('account', 'd', 'description', 'amt', 'cleared_f')
    list_filter = ('cleared_f', 'account')
    search_fields = ('account', 'description')
    ordering = ('account', '-d')
    actions = [duplicate_record, set_cleared_flag]
