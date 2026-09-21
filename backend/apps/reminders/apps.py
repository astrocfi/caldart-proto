"""App configuration for the reminders app."""

from django.apps import AppConfig


class RemindersConfig(AppConfig):
    """Registers the ``apps.reminders`` module under the app label ``reminders``."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.reminders"
    label = "reminders"
    verbose_name = "Reminders"
