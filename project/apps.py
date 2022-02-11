from django.contrib.admin.apps import AdminConfig


class WorthAdminConfig(AdminConfig):
    default_site = 'project.admin.WorthAdmin'
