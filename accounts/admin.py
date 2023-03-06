from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from .models import Account, Receivable, CashRecord
from moneycounter.dt import our_now


class ActiveAccountFilter(SimpleListFilter):
    title = "Active Accounts"
    parameter_name = 'active'

    def lookups(self, request, model_admin):
        active = Account.objects.filter(active_f=True).all()
        return [(a.id, a.name) for a in active]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(id=self.value())

        return queryset


class ActiveTradeAccountFilter(ActiveAccountFilter):
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(account__id=self.value())

        return queryset


def set_qualified_flag(modeladmin, request, qs):
    for rec in qs:
        rec.qualified_f = True
        rec.save()


def clear_qualified_flag(modeladmin, request, qs):
    for rec in qs:
        rec.qualified_f = False
        rec.save()


@admin .register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('name', )
    list_filter = ('active_f', 'qualified_f', ActiveAccountFilter)
    actions = [set_qualified_flag, clear_qualified_flag]


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


def toggle_ignored_flag(modeladmin, request, qs):
    for rec in qs:
        rec.ignored = not rec.ignored
        rec.save()


@admin.register(Receivable)
class ReceivableAdmin(admin.ModelAdmin):
    date_hierarchy = 'invoiced'
    list_display = ('invoiced', 'received', 'description', 'amt')
    ordering = ('-invoiced', )


@admin.register(CashRecord)
class CashRecordAdmin(admin.ModelAdmin):
    date_hierarchy = 'd'
    list_display = ('account', 'd', 'description', 'amt', 'cleared_f', 'ignored')
    list_filter = ('cleared_f', ActiveTradeAccountFilter, 'ignored')
    search_fields = ('account__name', 'description')
    ordering = ('account', '-d')
    actions = [duplicate_record, set_cleared_flag, toggle_ignored_flag]
