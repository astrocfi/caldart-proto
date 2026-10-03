"""Serializers for the email log endpoints."""

from __future__ import annotations

from rest_framework import serializers

from apps.mail.dns_check import DnsStatus
from apps.mail.links import log_links
from apps.mail.models import EmailLog
from apps.mail.purposes import purpose_label, purpose_labels
from caldart.runs import RunActionSerializer


class EmailLogSerializer(serializers.ModelSerializer[EmailLog]):
    """One row of ``GET /system/emails``.

    ``user_id`` is null for a message sent to an address with no account behind it.
    ``user_name`` is the recipient's name as it was at send time, falling back to
    the linked account's current name when that was not recorded; it is empty
    when neither names anybody.  ``error`` is blank unless ``status`` is
    ``failed``, and ``attachments`` is a comma-separated list of filenames,
    blank when the message carried none.  ``purpose_label`` is the purpose in words,
    from ``apps.mail.purposes``, or the purpose itself when no label names it.
    ``bounced_at`` is when the bounce check read a permanent-failure report for the
    message and ``bounce_detail`` that report's status code and diagnostic; they are
    null and blank unless ``status`` is ``bounced``.  ``link`` is the portal page the
    message belongs to, such as ``/bulk-email/sent/9`` for a copy of a bulk email
    (``apps.mail.links``), and blank for a message that stands alone.
    """

    user_id = serializers.IntegerField(read_only=True, allow_null=True)
    user_name = serializers.SerializerMethodField()
    purpose_label = serializers.SerializerMethodField()
    link = serializers.SerializerMethodField()

    class Meta:
        model = EmailLog
        fields = [
            "id",
            "to_email",
            "user_id",
            "user_name",
            "purpose",
            "purpose_label",
            "subject",
            "sent_at",
            "status",
            "error",
            "attachments",
            "bounced_at",
            "bounce_detail",
            "link",
        ]
        read_only_fields = fields

    def get_user_name(self, obj: EmailLog) -> str:
        """Return the recipient's name at send time, or ``""`` when nobody was named."""
        return obj.recipient_name

    def get_purpose_label(self, obj: EmailLog) -> str:
        """Return the words for the row's purpose, or its template name when unlabeled.

        The labels come from the context's ``purpose_labels`` when the caller read them
        once for a whole page, since the reminders' labels come from the stored
        reminder schedule, and are read afresh otherwise.
        """
        labels = self.context.get("purpose_labels")
        return purpose_label(obj.purpose, labels=labels if labels is not None else purpose_labels())

    def get_link(self, obj: EmailLog) -> str:
        """Return the portal page the message belongs to, or ``""`` for none.

        The links come from the context's ``log_links`` when the caller read them once
        for a whole page, and are read for this row alone otherwise.
        """
        links = self.context.get("log_links")
        found = links if links is not None else log_links([obj])
        return found.get(obj.pk, "")


class EmailPurposeSerializer(serializers.Serializer[dict[str, str]]):
    """One entry of ``GET /system/emails/purposes``: a purpose and its label."""

    value = serializers.CharField()
    # DRF's Field.label is a different thing from this serializer's own `label`
    # field, so the stubs see the declaration as a narrowing of the attribute.
    label = serializers.CharField()  # type: ignore[assignment]


class BounceRunRequestSerializer(serializers.Serializer[dict[str, bool]]):
    """``POST /system/bounces/run`` body: ``dry_run``, defaulting to ``False``."""

    dry_run = serializers.BooleanField(default=False)


class BounceRunResultSerializer(serializers.Serializer[dict[str, object]]):
    """What one bounce check found, and who each failure was about.

    ``enabled`` is false when ``BOUNCE_IMAP_URL`` is empty and nothing was read; the
    counts are then zero.  ``skipped`` counts the messages left unread in the mailbox:
    one the server would not hand over, and one too large to be a report.  Each
    action's ``kind`` is ``bounced`` (``on`` is the day the message was sent) or
    ``unmatched`` (``member`` is empty and ``on`` null), and its ``detail`` is the
    report's status code and diagnostic.
    """

    enabled = serializers.BooleanField()
    bounced = serializers.IntegerField()
    unmatched = serializers.IntegerField()
    ignored = serializers.IntegerField()
    skipped = serializers.IntegerField()
    actions = RunActionSerializer(many=True)


class MailDeliveryFindingSerializer(serializers.Serializer[dict[str, object]]):
    """One line of the mail delivery check.

    ``name`` is the line's title, ``status`` is ``pass``, ``warn``, or ``fail``,
    ``detail`` says what the record is for and what was found, and ``fix`` says what to
    ask for; ``fix`` is blank when ``status`` is ``pass``.
    """

    name = serializers.CharField()
    status = serializers.ChoiceField(choices=[status.value for status in DnsStatus])
    detail = serializers.CharField()
    fix = serializers.CharField()


class MailDeliveryCheckSerializer(serializers.Serializer[dict[str, object]]):
    """The mail delivery check: the ``domain`` it ran for, its findings, and when.

    ``domain`` is the domain of the site's From address, blank when the From address
    has none.  ``checked_at`` is when the lookups were made; a cached report keeps the
    time it was made.
    """

    domain = serializers.CharField()
    checked_at = serializers.DateTimeField()
    findings = MailDeliveryFindingSerializer(many=True)
