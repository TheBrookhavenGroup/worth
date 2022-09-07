from django.urls import path
from .views import CheckingView, PPMView, FuturesPnLView, GetIBTradesView, TotalCashView, TickerView, ValueChartView


app_name = 'analytics'

urlpatterns = [
    path('checking/', CheckingView.as_view(), name='checking'),
    path('cash/', TotalCashView.as_view(), name='cash'),
    path('getibtrades/', GetIBTradesView.as_view(), name='getibtrades'),
    path('ppm/', PPMView.as_view(), name='ppm'),
    path('futures/', FuturesPnLView.as_view(), name='futures'),
    path('ticker/<ticker>/', TickerView.as_view(), name='ticker_view'),
    path('value_chart/', ValueChartView.as_view(), name='value_chart')
]
