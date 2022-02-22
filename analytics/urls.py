from django.urls import path
from .views import CheckingView, PPMView, TotalCashView


app_name = 'analytics'

urlpatterns = [
    path('checking/', CheckingView.as_view(), name='checking'),
    path('cash/', TotalCashView.as_view(), name='cash'),
    path('ppm/', PPMView.as_view(), name='ppm'),
]
