from django.contrib import admin


class ALLAdmin(admin.AdminSite):
    index_template = "admin/index.html"
    enable_nav_sidebar = True
