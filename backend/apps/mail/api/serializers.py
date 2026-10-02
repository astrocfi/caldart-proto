"""Serializers for the email log endpoints."""

from __future__ import annotations

from rest_framework import serializers

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
    null and blank unless ``status`` is ``bounced``.
    """

    user_id = serializers.IntegerField(read_only=True, allow_null=True)
    user_name = serializers.SerializerMethodField()
    purpose_label = serializers.SerializerMethodField()

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
