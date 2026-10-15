"""App configuration for the mail app."""

from django.apps import AppConfig
from django.core import checks


class MailConfig(AppConfig):
    """Registers the ``apps.mail`` module under the app label ``mail``.

    Once the apps are loaded it registers ``apps.mail.checks.check_bounce_address``
    with Django's system checks.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.mail"
    label = "mail"
    verbose_name = "Mail"

    def ready(self) -> None:
        """Register the mail settings' system checks."""
        # Inline: the checks module is imported once the app registry is ready.
        from apps.mail.checks import check_bounce_address

        checks.register(check_bounce_address)
