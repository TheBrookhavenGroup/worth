from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from .models import Account, CashRecord
from worth.dt import our_now


class ActiveAccountFilter(SimpleListFilter):
    title = "Active Accounts"
    parameter_name = 'active'

    def lookups(self, request, model_admin):
        active = Account.objects.filter(active_f=True).all()
        return [(a.id, a.name) for a in active]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(account__id=self.value())
        else:
            return queryset


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
                             category=rec.category, amt=rec.amt)
        new_rec.save()


@admin .register(CashRecord)
class CashRecordAdmin(admin.ModelAdmin):
    date_hierarchy = 'd'
    list_display = ('account', 'd', 'description', 'amt', 'cleared_f')
    list_filter = ('cleared_f', ActiveAccountFilter)
    search_fields = ('account', 'description')
    ordering = ('account', '-d')
    actions = [duplicate_record, set_cleared_flag]
