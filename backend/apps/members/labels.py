"""The words a notification uses for a member record's fields.

A ``profile_changed`` event names the fields an edit moved by their labels, so the
email reads DART and Air Care Alliance number rather than ``dart`` and
``air_care_alliance_number``.
"""

from __future__ import annotations

from collections.abc import Mapping

from django.db.models import Field
from django.utils.text import capfirst

from apps.accounts.models import User
from apps.members.models import MemberProfile

#: The account columns a ``profile_changed`` event names: a member record shows the
#: name alongside the profile.
NAME_FIELDS = ("first_name", "last_name")

#: The label a ``profile_changed`` event gives a field whose model name reads badly;
#: every other profile field is its model field's name with a capital letter.
_FIELD_LABELS: dict[str, str] = {
    "first_name": "First name",
    "last_name": "Last name",
    "phone_alt": "Alternate phone",
    "phone_alt_extension": "Alternate phone extension",
    "address_line1": "Address line 1",
    "address_line2": "Address line 2",
    "dart": "DART",
    "air_care_alliance_number": "Air Care Alliance number",
    "home_airport_identifier": "Home airport",
    "secondary_airport_identifier": "Secondary airport",
    "how_heard": "How they heard of CalDART",
}


def profile_field_label(name: str) -> str:
    """The words a notification uses for the profile or name field ``name``.

    ``dart`` reads DART, ``phone_alt`` Alternate phone, ``first_name`` First name, and
    so on; a field with no label of its own reads as its model field's verbose name with
    a capital letter, e.g. ``city`` -> City, ``county`` -> California county.  A name
    that is no profile field raises ``FieldDoesNotExist``.
    """
    if name in _FIELD_LABELS:
        return _FIELD_LABELS[name]
    field = MemberProfile._meta.get_field(name)
    # ``get_field`` also answers reverse relations, which carry no verbose name; a
    # profile has none, so one here means the caller named something that is not a
    # profile field at all.
    if not isinstance(field, Field):
        raise TypeError(f"MemberProfile.{name} is not a field with a label.")
    return capfirst(str(field.verbose_name))


def changed_field_labels(row: User | MemberProfile, changes: Mapping[str, object]) -> list[str]:
    """The labels of the fields in ``changes`` whose value differs from ``row``'s.

    ``row`` is a profile or an account read before the write; ``changes`` maps field
    names to the values about to be written.  A field resent at the value it holds
    is left out, and the labels come in the order ``changes`` gives the fields.
    """
    return [
        profile_field_label(name) for name, value in changes.items() if getattr(row, name) != value
    ]
