"""App configuration for the darts app."""

from django.apps import AppConfig


class DartsConfig(AppConfig):
    """Registers the ``apps.darts`` module under the app label ``darts``."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.darts"
    label = "darts"
    verbose_name = "DARTs"
