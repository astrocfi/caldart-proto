"""App configuration for the notifications app."""

from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    """Registers ``apps.notifications`` under the app label ``notifications``.

    When the app starts it subscribes its dispatcher to every event the project
    raises, so an event reaches the addresses subscribed to it.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.notifications"
    label = "notifications"
    verbose_name = "Notifications"

    def ready(self) -> None:
        """Subscribe the dispatcher to the project's events."""
        from caldart import events

        from . import dispatch

        events.subscribe(dispatch.handle)
