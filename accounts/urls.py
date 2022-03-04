from django.urls import path
from .views import GetIBStatementsView


app_name = 'accounts'

urlpatterns = [
    path('ib_statements/', GetIBStatementsView.as_view(), name='get_ib_statements'),
]
