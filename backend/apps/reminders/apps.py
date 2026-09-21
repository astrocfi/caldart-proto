"""App configuration for the reminders app."""

from django.apps import AppConfig


class RemindersConfig(AppConfig):
    """Registers the ``reminders`` app under the ``apps.reminders`` label."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.reminders"
    label = "reminders"
    verbose_name = "Reminders"
