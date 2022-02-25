
from django.contrib import admin
from django.urls import path, include
from django.views.generic.base import RedirectView

title = "Worth Administration"
admin.site.site_header = title
admin.site.site_title = title


urlpatterns = [
    path('admin/', admin.site.urls, name='admin'),
    path('', RedirectView.as_view(url='admin', permanent=False)),
    path('', include('analytics.urls')),
]
