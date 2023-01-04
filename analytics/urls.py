from django.urls import path
from .views import CheckingView, PnLView, GetIBTradesView, TotalCashView, \
    TickerView, ValueChartView, RealizedGainView, PnLIfClosedView


app_name = 'analytics'

urlpatterns = [
    path('checking/', CheckingView.as_view(), name='checking'),
    path('cash/', TotalCashView.as_view(), name='cash'),
    path('getibtrades/', GetIBTradesView.as_view(), name='getibtrades'),
    path('pnl/', PnLView.as_view(), name='pnl'),
    path('ticker/<ticker>/', TickerView.as_view(), name='ticker_view'),
    path('value_chart/', ValueChartView.as_view(), name='value_chart'),
    path('realized/', RealizedGainView.as_view(), name='realized'),
    path('pnlifclosed/', PnLIfClosedView.as_view(), name='pnlifclosed')
]
