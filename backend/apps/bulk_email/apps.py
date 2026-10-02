"""App configuration for the bulk email app."""

from django.apps import AppConfig


class BulkEmailConfig(AppConfig):
    """Registers the ``apps.bulk_email`` module under the app label ``bulk_email``."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.bulk_email"
    label = "bulk_email"
    verbose_name = "Bulk email"
