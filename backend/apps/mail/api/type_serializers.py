"""Serializers for the email types and the email preferences endpoints."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.mail.models import EmailType
from apps.mail.types import SENDER_ROLES, EmailTypeFields

#: The highest ``position`` a type may take: the largest value its column holds.
MAX_POSITION = 2_147_483_647


class EmailTypeSerializer(serializers.ModelSerializer[EmailType]):
    """One email type as the system administrator's screen reads and writes it.

    ``slug`` is read-only and follows ``name``.  ``sender_roles`` lists role slugs from
    ``dart_leader`` and ``management``, in that order, once each; an empty list means
    only a system administrator may send the type.  ``position`` is optional on input,
    from 0 to :data:`MAX_POSITION`: left out, a new type goes after every other and an
    edited one keeps its place.
    """

    # Declared rather than generated so it carries no unique validator: the service
    # checks the name against every other type, case and slug included, and says so in
    # its own words, where the model's validator would answer first, in Django's.
    name = serializers.CharField(max_length=60)
    sender_roles = serializers.ListField(
        child=serializers.ChoiceField(choices=list(SENDER_ROLES)), allow_empty=True
    )
    position = serializers.IntegerField(min_value=0, max_value=MAX_POSITION, required=False)

    class Meta:
        model = EmailType
        fields = ["id", "name", "slug", "description", "allow_opt_out", "sender_roles", "position"]
        read_only_fields = ["id", "slug"]

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
    """One type the caller may send: what the compose screen's choice shows."""

    class Meta:
        model = EmailType
        fields = ["id", "name", "description", "allow_opt_out"]
        read_only_fields = fields


class EmailPreferenceSerializer(serializers.Serializer[dict[str, object]]):
    """One type a person may turn off, and whether they have.

    ``email_type`` is the type's id; ``name`` and ``description`` are the type's own.
    ``opted_out`` is true when the person receives none of that type.
    """

    email_type = serializers.IntegerField()
    name = serializers.CharField()
    description = serializers.CharField()
    opted_out = serializers.BooleanField()


class EmailPreferenceChangeSerializer(serializers.Serializer[dict[str, object]]):
    """One change in a ``PUT`` of email preferences: a type's id and the choice."""

    email_type = serializers.IntegerField()
    opted_out = serializers.BooleanField()
