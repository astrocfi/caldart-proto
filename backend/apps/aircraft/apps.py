"""App configuration for the aircraft register."""

from django.apps import AppConfig


class AircraftConfig(AppConfig):
    """Django app configuration for ``apps.aircraft``, under the ``aircraft`` label."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.aircraft"
    label = "aircraft"
    verbose_name = "Aircraft"
