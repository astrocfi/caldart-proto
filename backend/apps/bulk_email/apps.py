"""App configuration for the bulk email app."""

from django.apps import AppConfig
from django.db.models.signals import post_save

from apps.mail.links import register_log_links


class BulkEmailConfig(AppConfig):
    """Registers the ``apps.bulk_email`` module under the app label ``bulk_email``.

    When the app is ready it ties bounces back to their copies: every save of a
    ``mail.EmailLog`` row reaches ``apps.bulk_email.delivery.on_email_log_saved``, which
    marks the bulk copy a bounced row records as bounced.  It also gives the email log
    the link from each bulk copy to its bulk email (``apps.mail.links``), so the mail
    app never imports this one.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.bulk_email"
    label = "bulk_email"
    verbose_name = "Bulk email"

    def ready(self) -> None:
        """Connect the bounce receiver and register the email log's links."""
        # Imported here: the models are not loaded when this module is imported.
        from apps.bulk_email.delivery import email_log_links, on_email_log_saved
        from apps.mail.models import EmailLog

        post_save.connect(
            on_email_log_saved, sender=EmailLog, dispatch_uid="bulk_email.on_email_log_saved"
        )
        register_log_links(email_log_links)
