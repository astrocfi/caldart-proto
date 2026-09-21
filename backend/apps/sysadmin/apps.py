"""App configuration for the system administration app."""

from django.apps import AppConfig


class SysadminConfig(AppConfig):
    """Django app config for ``apps.sysadmin``, labeled ``sysadmin``."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.sysadmin"
    label = "sysadmin"
    verbose_name = "System administration"
