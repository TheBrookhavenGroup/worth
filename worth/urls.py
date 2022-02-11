
from django.contrib import admin
from django.urls import path, include
from django.views.generic.base import RedirectView

admin.site.site_header = "Worth Administration"
admin.site.site_title = "Worth Administration"

urlpatterns = [
    path('admin/', admin.site.urls, name='admin'),
    path('', RedirectView.as_view(url='admin', permanent=False)),
    path('', include('analytics.urls')),
]
