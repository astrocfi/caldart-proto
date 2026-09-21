"""App configuration for payments."""

from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    """Registers the ``payments`` app, which holds the ``Payment`` ledger."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.payments"
    label = "payments"
    verbose_name = "Payments"
