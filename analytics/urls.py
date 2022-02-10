from django.urls import path
from .views import CheckingView


app_name = 'analytics'

urlpatterns = [
    path('checking/', CheckingView.as_view()),
]
