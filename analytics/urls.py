from django.urls import path
from .views import (CheckingView, PnLView, GetIBTradesView, TotalCashView,
                    TickerView, ValueChartView, RealizedGainView,
                    PnLIfClosedView, IncomeExpenseView, income_csv_view,
                    expenses_csv_view)


app_name = 'analytics'

urlpatterns = [
    path('checking/', CheckingView.as_view(), name='checking'),
    path('cash/', TotalCashView.as_view(), name='cash'),
    path('getibtrades/', GetIBTradesView.as_view(), name='getibtrades'),
    path('pnl/', PnLView.as_view(), name='pnl'),
    path('ticker/<ticker>/', TickerView.as_view(), name='ticker_view'),
    path('value_chart/', ValueChartView.as_view(), name='value_chart'),
    path('realized/', RealizedGainView.as_view(), name='realized'),
    path('pnlifclosed/', PnLIfClosedView.as_view(), name='pnlifclosed'),
    path('incomeexpense/', IncomeExpenseView.as_view(), name='incomeexpense'),
    path('income/csv/<int:param>', income_csv_view, name='incomecsv'),
    path('expenses/csv/<int:param>', expenses_csv_view, name='expensescsv'),
]
