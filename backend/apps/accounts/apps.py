"""App configuration for the accounts app."""

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Registers the app under the label ``accounts``.

    Django loads it from the dotted path ``apps.accounts``, so the label has to be
    stated: the default would be ``accounts`` only by accident of the last segment.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    label = "accounts"
    verbose_name = "Accounts"
