from django.urls import path
from .views import api_t_close


urlpatterns = [
    path("markets/api/t_close/", api_t_close, name="api_t_close"),
]
