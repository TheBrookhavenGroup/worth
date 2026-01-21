from django.contrib.admin.apps import AdminConfig


# The purpose of ALLAdmin is to eliminate password protection for the admin site.
class ALLAdminConfig(AdminConfig):
    default_site = "worth.admin.ALLAdmin"
