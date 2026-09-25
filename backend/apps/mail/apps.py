"""App configuration for the mail app."""

from django.apps import AppConfig


class MailConfig(AppConfig):
    """Registers the ``apps.mail`` module under the app label ``mail``."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.mail"
    label = "mail"
    verbose_name = "Mail"
