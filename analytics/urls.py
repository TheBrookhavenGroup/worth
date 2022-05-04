from django.urls import path
from .views import CheckingView, PPMView, PPMViewNew, FuturesPnLView, GetIBTradesView, TotalCashView


app_name = 'analytics'

urlpatterns = [
    path('checking/', CheckingView.as_view(), name='checking'),
    path('cash/', TotalCashView.as_view(), name='cash'),
    path('getibtrades/', GetIBTradesView.as_view(), name='getibtrades'),
    path('ppm/', PPMView.as_view(), name='ppm'),
    path('ppm_new/', PPMViewNew.as_view(), name='ppmnew'),
    path('futures/', FuturesPnLView.as_view(), name='futures'),
]
