from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.contrib import messages
from django.forms import ModelForm, ModelChoiceField
from django.urls import reverse
from django.utils.html import format_html
from .models import Account, Receivable, CashRecord, Expense, Vendor
from tbgutils.dt import our_now


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


def duplicate_receivable(modeladmin, request, qs):
    d = our_now().date()
    for rec in qs:
        invoice = rec.invoice[:-8] + d.strftime("%Y%m%d")
        new_rec = Receivable(expected=rec.expected, client=rec.client,
                             invoice=invoice, amt=rec.amt)
        new_rec.save()


def recievable2cash(modeladmin, request, qs):
    d = our_now().date()
    a = Account.objects.get(name='TBG')
    for rec in qs:
        if rec.received is None:
            description = f"{rec.client} - {rec.invoice}"
            new_rec = CashRecord(d=d, description=description, account=a,
                                 category="DE", amt=rec.amt)
            new_rec.save()

            rec.received = d
            rec.save()


class ReceivableNotReceivedFilter(SimpleListFilter):
    title = "Recieved"
    parameter_name = 'received'

    def lookups(self, request, model_admin):
        return [('no', 'Not Received'), ('yes', 'Received')]

    def queryset(self, request, queryset):
        if 'no' == self.value():
            return queryset.filter(received=None)
        elif 'yes' == self.value():
            return queryset.filter(received__isnull=False)

        return queryset


@admin.register(Receivable)
class ReceivableAdmin(admin.ModelAdmin):
    date_hierarchy = 'invoiced'
    list_display = ('invoice', 'invoiced', 'received', 'client', 'amt')
    ordering = ('-invoiced', )
    actions = [duplicate_receivable, recievable2cash]
    list_filter = [ReceivableNotReceivedFilter]


def set_cleared_flag(modeladmin, request, qs):
    for rec in qs:
        rec.cleared_f = True
        rec.save()


def duplicate_record(modeladmin, request, qs):
    d = our_now().date()
    for rec in qs:
        new_rec = CashRecord(d=d,
                             description=rec.description,
                             account=rec.account,
                             category=rec.category,
                             amt=rec.amt)
        new_rec.save()


def toggle_ignored_flag(modeladmin, request, qs):
    for rec in qs:
        rec.ignored = not rec.ignored
        rec.save()


def sum_amt(modeladmin, request, qs):
    total = 0
    for rec in qs:
        total += rec.amt

    messages.add_message(request, messages.INFO, f"Total: {total}")


@admin.register(CashRecord)
class CashRecordAdmin(admin.ModelAdmin):
    date_hierarchy = 'd'
    list_display = ('account', 'd', 'description', 'amt',
                    'cleared_f', 'ignored')
    list_filter = ('cleared_f', ActiveTradeAccountFilter, 'ignored')
    search_fields = ('account__name', 'description')
    ordering = ('account', '-d')
    actions = [duplicate_record, set_cleared_flag, toggle_ignored_flag,
               sum_amt]


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'url')
    ordering = ('name', )


def duplicate_expense(modeladmin, request, qs):
    d = our_now().date()
    for rec in qs:
        new_rec = Expense(vendor=rec.vendor,
                          client=rec.client,
                          invoice=invoice,
                          amt=rec.amt)
        new_rec.save()


def duplicate_expense_record(modeladmin, request, qs):
    d = our_now().date()
    for rec in qs:
        new_rec = Expense(d=d,
                          description=rec.description,
                          account=rec.account,
                          vendor=rec.vendor,
                          amt=rec.amt)
        new_rec.save()


def expense_form_factory(d, a):
    class CashForm(ModelForm):
        cash_transaction = ModelChoiceField(
            queryset=CashRecord.objects.filter(account=a, d__gte=d))
    return CashForm


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    date_hierarchy = 'd'
    list_display = ('d', 'vendor', 'description', 'amt', 'paid',
                    'cash_transaction_link')
    list_filter = ('vendor', 'account')
    search_fields = ('vendor__name', 'description')
    ordering = ('-d',)
    actions = [duplicate_expense_record, sum_amt]

    def get_form(self, request, obj=None, **kwargs):
        if obj is not None and obj.d is not None:
            kwargs['form'] = expense_form_factory(obj.d, obj.account)
        return super(ExpenseAdmin, self).get_form(request, obj, **kwargs)

    def cash_transaction_link(self, obj):
        if obj.cash_transaction is not None:
            link = reverse("admin:accounts_cashrecord_change",
                           args=[obj.cash_transaction.id])
            return format_html('<a href="{}">cash</a>', link)
        else:
            return "Unassigned"
    cash_transaction_link.short_description = 'Cash Transaction'
