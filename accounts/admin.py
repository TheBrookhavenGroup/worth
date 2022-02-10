from django.contrib import admin
from .models import Account, CashRecord


@admin .register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('name', )


@admin .register(CashRecord)
class CashRecordAdmin(admin.ModelAdmin):
    list_display = ('account', 'd', 'description', 'amt', 'cleared_f')
    list_filter = ('account', )
    search_fields = ('account', 'd', 'descripton')
    ordering = ('account', '-d')
