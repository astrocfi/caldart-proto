"""Serializers for the DART catalog and the account administrator's DART screen."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from apps.darts.models import (
    AIRPORT_IDENTIFIER_RE,
    AIRPORT_IDENTIFIERS_MESSAGE,
    MAX_AIRPORT_IDENTIFIERS,
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


class DartAdminContactSerializer(DartContactSerializer):
    """One person on a DART as the account administrator edits them.

    The public fields, plus ``receives_roster``: whether the person is sent the
    team's roster.  The tick is the administrator's business, so the public
    catalog leaves it out.
    """

    class Meta(DartContactSerializer.Meta):
        fields = [*DartContactSerializer.Meta.fields, "receives_roster"]


class DartSerializer(serializers.ModelSerializer[Dart]):
    """``GET /darts`` -- the public DART catalog, with the people who run each team."""

    contacts = DartContactSerializer(many=True, read_only=True)

    class Meta:
        model = Dart
        fields = ["id", "name", "airport_identifiers", "website_url", "contacts"]
        read_only_fields = fields


class DartRefSerializer(serializers.ModelSerializer[Dart]):
    """The ``dart: {id, name}`` stub nested in a profile."""

    class Meta:
        model = Dart
        fields = ["id", "name"]
        read_only_fields = fields


class DartAdminSerializer(serializers.ModelSerializer[Dart]):
    """``GET/POST /admin/darts`` and ``GET/PATCH/DELETE /admin/darts/{id}``.

    ``contacts`` is written with the DART: the list given, of any length,
    replaces the list stored, because that is how the screen edits it -- every
    row, saved together.  ``member_count`` and ``page_count`` say what a
    deletion would leave behind: the members whose profile names this DART, and
    the website pages linked to it.  ``roster_recipients`` counts the people
    ticked to receive the roster who have an email address, and
    ``roster_sent_at`` is when the last roster went out (null when none has);
    both are read-only.
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
    contacts = DartAdminContactSerializer(many=True, required=False)
    member_count = serializers.IntegerField(read_only=True)
    page_count = serializers.IntegerField(read_only=True)
    roster_recipients = serializers.SerializerMethodField()

    class Meta:
        model = Dart
        fields = [
            "id",
            "name",
            "airport_identifiers",
            "website_url",
            "is_active",
            "contacts",
            "member_count",
            "page_count",
            "roster_recipients",
            "roster_sent_at",
        ]
        read_only_fields = ["roster_sent_at"]

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

    def get_roster_recipients(self, dart: Dart) -> int:
        """How many of ``dart``'s people are ticked for the roster and have an email.

        Counted from the contacts themselves rather than annotated on the
        queryset, so the answer to a save counts the people that save wrote.
        """
        return sum(
            1 for contact in dart.contacts.all() if contact.receives_roster and contact.email != ""
        )

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
    "DartAdminContactSerializer",
    "DartAdminSerializer",
    "DartContactSerializer",
    "DartRefSerializer",
    "DartSerializer",
]
