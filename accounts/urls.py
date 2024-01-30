from django.urls import path
from .views import (GetIBStatementsView, AccountsView, ReceivablesView,
                    CashTransferView)


app_name = 'accounts'

urlpatterns = [
    path('ib_statements/', GetIBStatementsView.as_view(), name='get_ib_statements'),
    path('receivables/', ReceivablesView.as_view(), name='receivables'),
    path('accounts/', AccountsView.as_view(), name='accounts'),
    path('cash_transfer/', CashTransferView.as_view(), name='cash_transfer'),
]
