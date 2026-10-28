from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        from django.contrib import admin

        from .forms import ProtectedAdminAuthenticationForm

        admin.site.login_form = ProtectedAdminAuthenticationForm
