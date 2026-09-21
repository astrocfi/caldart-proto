"""App configuration for the accounts app."""

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Registers the app under the label ``accounts``.

    Django loads it from the dotted path ``apps.accounts``.  The label restates the
    last segment of that path, which is the label Django derives by default, so
    migrations and model references read ``accounts.<Model>``.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    label = "accounts"
    verbose_name = "Accounts"
