from django.urls import path
from .views import (GetIBStatementsView, AccountsView, ReceivablesView,
                    CashTransferView, DifferenceView)


app_name = 'accounts'

urlpatterns = [
    path('ib_statements/', GetIBStatementsView.as_view(), name='get_ib_statements'),
    path('receivables/', ReceivablesView.as_view(), name='receivables'),
    path('accounts/', AccountsView.as_view(), name='accounts'),
    path('cash_transfer/', CashTransferView.as_view(), name='cash_transfer'),
    path('difference/', DifferenceView.as_view(), name='difference'),
    path('difference/<preserved_filters>', DifferenceView.as_view(), name='difference'),
]
