"""App configuration for the reports app."""

from django.apps import AppConfig


class ReportsConfig(AppConfig):
    """Registers the ``apps.reports`` module under the app label ``reports``."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.reports"
    label = "reports"
    verbose_name = "Reports"
