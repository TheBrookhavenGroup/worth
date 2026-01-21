from importlib import import_module

from django.conf import settings
from django.contrib import admin


# The purpose of ALLAdmin is to eliminate password protection for the admin site.
class ALLAdmin(admin.AdminSite):
    index_template = "admin/index.html"
    enable_nav_sidebar = True

    def _noadminpw_enabled(self):
        settings_module = import_module(settings.SETTINGS_MODULE)
        return getattr(
            settings_module,
            "NOADMINPW",
            getattr(settings_module, "noadminpw", False),
        )

    def _wrap_admin_class(self, admin_class):
        base_class = admin_class or admin.ModelAdmin
        if getattr(base_class, "_noadminpw_wrapped", False):
            return base_class

        class OpenAdmin(base_class):
            _noadminpw_wrapped = True

            def has_module_permission(self, request):
                if self.admin_site._noadminpw_enabled():
                    return True
                return super().has_module_permission(request)

            def has_view_permission(self, request, obj=None):
                if self.admin_site._noadminpw_enabled():
                    return True
                return super().has_view_permission(request, obj=obj)

            def has_add_permission(self, request):
                if self.admin_site._noadminpw_enabled():
                    return True
                return super().has_add_permission(request)

            def has_change_permission(self, request, obj=None):
                if self.admin_site._noadminpw_enabled():
                    return True
                return super().has_change_permission(request, obj=obj)

            def has_delete_permission(self, request, obj=None):
                if self.admin_site._noadminpw_enabled():
                    return True
                return super().has_delete_permission(request, obj=obj)

        return OpenAdmin

    def register(self, model_or_iterable, admin_class=None, **options):
        admin_class = self._wrap_admin_class(admin_class)
        return super().register(model_or_iterable, admin_class=admin_class, **options)

    def has_permission(self, request):
        if self._noadminpw_enabled():
            return True
        return super().has_permission(request)
