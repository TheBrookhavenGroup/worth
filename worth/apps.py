from django.contrib.admin.apps import AdminConfig


class ALLAdminConfig(AdminConfig):
    default_site = 'ALL.admin.ALLAdmin'
