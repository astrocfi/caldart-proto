"""Django app configuration for the members domain."""

from django.apps import AppConfig


class MembersConfig(AppConfig):
    """Registers the members app under the label ``members``."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.members"
    label = "members"
    verbose_name = "Members"
