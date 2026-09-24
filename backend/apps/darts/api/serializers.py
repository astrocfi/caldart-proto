"""Serializers for the DART catalog and the account administrator's DART screen."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from apps.darts.models import (
    AIRPORT_IDENTIFIER_RE,
    AIRPORT_IDENTIFIERS_MESSAGE,
    MAX_AIRPORT_IDENTIFIERS,
    MAX_DART_CONTACTS,
    Dart,
    DartContact,
    split_airport_identifiers,
)
from caldart.phone import PHONE_RE, normalize_phone

#: What a contact's phone field answers when it cannot be read as ten digits.
PHONE_MESSAGE = "Use a ten-digit number like 415-555-0100."

#: How long a typed number may be before it is refused on length alone.
RAW_PHONE_LENGTH = 24


class DartContactSerializer(serializers.ModelSerializer[DartContact]):
    """One named volunteer on a DART: who they are, and how to reach them."""

    phone = serializers.CharField(max_length=RAW_PHONE_LENGTH, required=False, allow_blank=True)

    class Meta:
        model = DartContact
        fields = ["id", "name", "title", "phone", "email"]
        extra_kwargs = {
            "name": {"error_messages": {"blank": "Give the person a name."}},
            "title": {"error_messages": {"blank": "Say what this person does."}},
        }

    def validate_phone(self, value: str) -> str:
        """The number in canonical form, or blank: a contact may be email-only."""
        normalized = normalize_phone(value)
        if not normalized:
            return ""
        if not PHONE_RE.match(normalized):
            raise serializers.ValidationError(PHONE_MESSAGE)
        return normalized


class DartSerializer(serializers.ModelSerializer[Dart]):
    """``GET /darts`` -- the public DART catalog, with the people who run each team."""

    contacts = DartContactSerializer(many=True, read_only=True)

    class Meta:
        model = Dart
        fields = ["id", "name", "airport_identifiers", "city", "website_url", "contacts"]
        read_only_fields = fields


class DartRefSerializer(serializers.ModelSerializer[Dart]):
    """The ``dart: {id, name}`` stub nested in a profile."""

    class Meta:
        model = Dart
        fields = ["id", "name"]
        read_only_fields = fields


class DartAdminSerializer(serializers.ModelSerializer[Dart]):
    """``GET/POST /admin/darts`` and ``GET/PATCH/DELETE /admin/darts/{id}``.

    ``contacts`` is written with the DART: the list given replaces the list
    stored, because that is how the screen edits it -- five rows, saved
    together.  ``member_count`` and ``page_count`` say what a deletion would
    leave behind: the members whose profile names this DART, and the website
    pages linked to it.
    """

    #: Named here for its message: "This field may not be blank." tells an
    #: administrator what a serializer thinks, not what to do about it.
    name = serializers.CharField(
        max_length=120,
        error_messages={"blank": "Give the DART a name.", "required": "Give the DART a name."},
        validators=[
            UniqueValidator(
                queryset=Dart.objects.all(), message="A DART with that name already exists."
            )
        ],
    )
    #: Named here for its message too: every DART flies from somewhere, and
    #: "This field may not be blank." does not say what to type.
    airport_identifiers = serializers.CharField(
        max_length=120,
        error_messages={
            "blank": "Give the DART at least one airport.",
            "required": "Give the DART at least one airport.",
        },
    )
    contacts = DartContactSerializer(many=True, required=False)
    member_count = serializers.IntegerField(read_only=True)
    page_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Dart
        fields = [
            "id",
            "name",
            "airport_identifiers",
            "city",
            "website_url",
            "is_active",
            "contacts",
            "member_count",
            "page_count",
        ]

    def validate_airport_identifiers(self, value: str) -> str:
        """The airports this DART flies from, as ``"CCR, C83"``.

        Every DART has at least one, so an empty list is refused with "Give the
        DART at least one airport."  Each identifier is three letters or digits
        once its ICAO ``K`` has been trimmed -- ``CCR``, ``C83``, and ``KCRQ``
        which is stored as ``CRQ`` -- and anything else is refused with
        ``AIRPORT_IDENTIFIERS_MESSAGE``, as is a list longer than
        ``MAX_AIRPORT_IDENTIFIERS`` or one naming the same field twice, whichever
        spelling each was typed in.  What comes back is the canonical,
        upper-cased, comma-separated form.
        """
        airports = split_airport_identifiers(value)
        if not airports:
            raise serializers.ValidationError("Give the DART at least one airport.")
        if len(airports) > MAX_AIRPORT_IDENTIFIERS:
            raise serializers.ValidationError(
                f"A DART may list at most {MAX_AIRPORT_IDENTIFIERS} airports."
            )
        if len(set(airports)) != len(airports):
            raise serializers.ValidationError("That list names the same airport twice.")
        if any(not AIRPORT_IDENTIFIER_RE.match(airport) for airport in airports):
            raise serializers.ValidationError(AIRPORT_IDENTIFIERS_MESSAGE)
        return ", ".join(airports)

    def validate_contacts(self, value: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """At most ``MAX_DART_CONTACTS`` people, because this is not a roster."""
        if len(value) > MAX_DART_CONTACTS:
            raise serializers.ValidationError(
                f"A DART may list at most {MAX_DART_CONTACTS} people."
            )
        return value

    def create(self, validated_data: dict[str, Any]) -> Dart:
        """Create the DART and its people together."""
        contacts = validated_data.pop("contacts", [])
        dart = super().create(validated_data)
        self._write_contacts(dart, contacts)
        return dart

    def update(self, instance: Dart, validated_data: dict[str, Any]) -> Dart:
        """Update the DART, replacing its people when the body carried them.

        A body without ``contacts`` leaves the stored list alone, so a PATCH of
        the name is not a way to lose the team's officers by omission.
        """
        contacts = validated_data.pop("contacts", None)
        dart = super().update(instance, validated_data)
        if contacts is not None:
            self._write_contacts(dart, contacts)
        return dart

    def _write_contacts(self, dart: Dart, contacts: list[dict[str, Any]]) -> None:
        """Replace ``dart``'s contacts with ``contacts``, in the order given."""
        dart.contacts.all().delete()
        for position, contact in enumerate(contacts):
            fields = {key: value for key, value in contact.items() if key != "id"}
            DartContact.objects.create(dart=dart, sort_order=position, **fields)


__all__ = [
    "DartAdminSerializer",
    "DartContactSerializer",
    "DartRefSerializer",
    "DartSerializer",
]
