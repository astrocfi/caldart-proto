"""App configuration for the reminders app."""

from django.apps import AppConfig

from apps.mail.purposes import register_purpose_labels


class RemindersConfig(AppConfig):
    """Registers the ``apps.reminders`` module under the app label ``reminders``.

    When the app starts it registers the reminder purposes' labels with the mail app,
    so the email log names the days of the stored reminder schedule.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.reminders"
    label = "reminders"
    verbose_name = "Reminders"

    def ready(self) -> None:
        """Register the reminder purposes' labels with the email log's purposes."""
        # The models cannot be imported until the app registry is ready.
        from .models import reminder_purpose_labels

        register_purpose_labels(reminder_purpose_labels)
