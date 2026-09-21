"""Django app configuration for the CMS."""

from django.apps import AppConfig


class CmsConfig(AppConfig):
    """Registers the Wagtail page models under the ``cms`` app label."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.cms"
    label = "cms"
    verbose_name = "CMS"
