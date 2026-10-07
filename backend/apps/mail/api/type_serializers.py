"""Serializers for the email types and the email preferences endpoints."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.mail.models import EmailType, OptOutSource
from apps.mail.types import SENDER_ROLES, EmailTypeFields
from caldart.messages import when_missing

#: The highest ``position`` a type may take: the largest value its column holds.
MAX_POSITION = 2_147_483_647


class EmailTypeSerializer(serializers.ModelSerializer[EmailType]):
    """One email type as the system administrator's screen reads and writes it.

    ``slug`` is read-only and follows ``name``.  ``sender_roles`` lists role slugs from
    ``dart_leader`` and ``management``, in that order, once each; an empty list means
    only a system administrator may send the type.  ``position`` is optional on input,
    from 0 to :data:`MAX_POSITION`: left out, a new type goes after every other and an
    edited one keeps its place.  ``in_use`` is read-only and true once a bulk email has
    the type, which then cannot be deleted.
    """

    # Declared rather than generated so it carries no unique validator: the service
    # checks the name against every other type, case and slug included, and says so in
    # its own words, where the model's validator would answer first, in Django's.
    name = serializers.CharField(
        max_length=60, error_messages=when_missing("Give the email type a name.")
    )
    sender_roles = serializers.ListField(
        child=serializers.ChoiceField(choices=list(SENDER_ROLES)), allow_empty=True
    )
    position = serializers.IntegerField(min_value=0, max_value=MAX_POSITION, required=False)
    in_use = serializers.SerializerMethodField()

    class Meta:
        model = EmailType
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "allow_opt_out",
            "sender_roles",
            "position",
            "in_use",
        ]
        read_only_fields = ["id", "slug", "in_use"]
        extra_kwargs = {
            "description": {
                "error_messages": when_missing("Say in one sentence what this email is for.")
            }
        }

    def get_in_use(self, email_type: EmailType) -> bool:
        """True once a bulk email has the type, so that it cannot be deleted."""
        return email_type.bulk_emails.exists()

    def to_fields(self) -> EmailTypeFields:
        """The validated input as the service takes it; no ``position`` is ``None``."""
        data: dict[str, Any] = self.validated_data
        return EmailTypeFields(
            name=data["name"].strip(),
            description=data["description"].strip(),
            allow_opt_out=data["allow_opt_out"],
            sender_roles=list(data["sender_roles"]),
            position=data.get("position"),
        )


class SendableEmailTypeSerializer(serializers.ModelSerializer[EmailType]):
    """One type the caller may send: what the compose screen's choice shows.

    ``is_mission`` is true for the Mission type, the only one a mission callout offers.
    """

    is_mission = serializers.BooleanField(read_only=True)

    class Meta:
        model = EmailType
        fields = ["id", "name", "description", "allow_opt_out", "is_mission"]
        read_only_fields = fields


class EmailPreferenceSerializer(serializers.Serializer[dict[str, object]]):
    """One type a person may turn off, and whether they have.

    ``email_type`` is the type's id; ``name`` and ``description`` are the type's own.
    ``opted_out`` is true when the person receives none of that type.  For a type
    turned off, ``opted_out_source`` says where (``profile``, ``unsubscribe``, or
    ``admin``) and ``opted_out_at`` when; they are ``""`` and null for a type left on.
    """

    email_type = serializers.IntegerField()
    name = serializers.CharField()
    description = serializers.CharField()
    opted_out = serializers.BooleanField()
    opted_out_source = serializers.ChoiceField(
        choices=[("", "Not turned off"), *OptOutSource.choices], allow_blank=True
    )
    opted_out_at = serializers.DateTimeField(allow_null=True)


class EmailPreferenceChangeSerializer(serializers.Serializer[dict[str, object]]):
    """One change in a ``PUT`` of email preferences: a type's id and the choice."""

    email_type = serializers.IntegerField()
    opted_out = serializers.BooleanField()
