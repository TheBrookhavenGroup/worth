
from django.contrib import admin
from django.urls import path, include

admin.site.site_header = "Worth Administration"
admin.site.site_title = "Worth Administration"

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('analytics.urls')),
]
