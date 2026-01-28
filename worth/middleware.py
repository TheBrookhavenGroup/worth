from django.conf import settings
from django.contrib.auth import get_user_model, login


class NoAdminPwAutoLoginMiddleware:
    """Auto-authenticate a user when NOADMINPW is enabled."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(settings, "NOADMINPW", False) and not request.user.is_authenticated:
            user_model = get_user_model()
            user, _created = user_model.objects.get_or_create(
                username="noadminpw",
                defaults={"is_staff": True, "is_superuser": True},
            )
            # Use the default auth backend.
            user.backend = "django.contrib.auth.backends.ModelBackend"
            login(request, user)

        return self.get_response(request)
