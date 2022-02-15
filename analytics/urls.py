from django.urls import path
from .views import CheckingView, PPMView


app_name = 'analytics'

urlpatterns = [
    path('checking/', CheckingView.as_view(), name='checking'),
    path('ppm/', PPMView.as_view(), name='ppm'),
]
