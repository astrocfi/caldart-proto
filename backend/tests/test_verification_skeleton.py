"""The schema, role, catalog, and labels that verification is built on.

A verifier is the least privileged staff role; the four verifying roles are the
verifier, the DART leader, the user administrator, and the account administrator.  A
person's three items and an aircraft's insurance each cover a fixed set of fields, and
a fresh profile or aircraft starts with every item unverified.  The
``verification_changed`` event is in the notification catalog, and its email log
purpose has a label.
"""

from __future__ import annotations

import pytest
from django.contrib.auth.models import Group

from apps.accounts.models import User
from apps.accounts.permissions import IsVerifier
from apps.accounts.roles import (
    ACCOUNT_ADMIN,
    DART_LEADER,
    MEMBER,
    ROLE_DESCRIPTIONS,
    ROLE_LABELS,
    ROLE_SLUGS,
    STAFF_ROLE_SLUGS,
    USER_ADMIN,
    VERIFIER,
    VERIFY_ROLES,
)
from apps.aircraft.models import Aircraft
from apps.aircraft.verification import INSURANCE_FIELDS, INSURANCE_LABEL
from apps.mail.purposes import PURPOSE_LABELS
from apps.members.models import MemberProfile, PhotoIdType
from apps.members.verification import ITEM_LABELS, ITEMS
from apps.notifications.events import EVENTS
from caldart.events import EVENT_SLUGS
from tests.factories import AircraftFactory, MemberProfileFactory

pytestmark = pytest.mark.django_db

#: A person's verified item slugs, in the order the screens list them.
PERSON_ITEMS = ("certificate", "medical", "photo_id")


# -- the role --------------------------------------------------------------------
def test_the_verifier_sits_between_member_and_dart_leader() -> None:
    """``verifier`` is the second role, the least privileged staff role."""
    assert ROLE_SLUGS[:3] == (MEMBER, VERIFIER, DART_LEADER)


def test_the_verifier_is_a_staff_role() -> None:
    """``verifier`` is among the staff roles, first of them."""
    assert STAFF_ROLE_SLUGS[0] == VERIFIER


def test_the_verifier_is_labeled_as_the_screens_name_it() -> None:
    """The role reads *Verifier*."""
    assert ROLE_LABELS[VERIFIER] == "Verifier"


def test_the_verifier_is_described_by_what_it_verifies() -> None:
    """The description names the items and the two check screens."""
    assert ROLE_DESCRIPTIONS[VERIFIER] == (
        "Verify a member's pilot certificate, medical, and photo ID, and an "
        "aircraft's insurance, from the member check and the aircraft check."
    )


def test_the_verifying_roles_are_the_four() -> None:
    """The verifier, the DART leader, and the user and account administrators verify."""
    assert VERIFY_ROLES == (VERIFIER, DART_LEADER, USER_ADMIN, ACCOUNT_ADMIN)


def test_is_verifier_requires_a_verifying_role() -> None:
    """``IsVerifier`` admits exactly the holders of ``VERIFY_ROLES``."""
    assert IsVerifier.required_roles == VERIFY_ROLES


def test_the_verifier_role_group_exists_on_a_fresh_database() -> None:
    """The role seed migration creates the ``verifier`` group."""
    assert Group.objects.filter(name=VERIFIER).exists()


def test_the_verifier_fixture_holds_member_and_verifier(verifier: User) -> None:
    """The ``verifier`` fixture is a member who also holds the verifier role."""
    assert verifier.roles == [MEMBER, VERIFIER]


# -- the items -------------------------------------------------------------------
def test_a_person_has_three_items_in_screen_order() -> None:
    """The items are the pilot certificate, the medical, and the photo ID."""
    assert tuple(item.slug for item in ITEMS) == PERSON_ITEMS


@pytest.mark.parametrize(
    ("slug", "fields"),
    [
        ("certificate", ("pilot_certificate_type", "certificate_number")),
        ("medical", ("medical_type", "medical_expiration")),
        ("photo_id", ("photo_id_type",)),
    ],
)
def test_each_item_covers_its_fields(slug: str, fields: tuple[str, ...]) -> None:
    """Each item covers exactly the profile fields whose change clears it."""
    assert next(item.fields for item in ITEMS if item.slug == slug) == fields


def test_every_covered_field_is_a_profile_field() -> None:
    """No item names a field ``MemberProfile`` does not have."""
    columns = {field.name for field in MemberProfile._meta.concrete_fields}
    assert {name for item in ITEMS for name in item.fields} <= columns


def test_the_item_labels_are_the_screen_names() -> None:
    """``ITEM_LABELS`` names each item as the screens do, in order."""
    assert ITEM_LABELS == {
        "certificate": "Pilot certificate",
        "medical": "Medical",
        "photo_id": "Photo ID",
    }


def test_insurance_covers_the_six_insurance_fields() -> None:
    """The insurance item covers every insurance field of the aircraft."""
    assert INSURANCE_FIELDS == (
        "insurance_carrier",
        "insurance_policy_number",
        "insurance_liability_per_occurrence_cents",
        "insurance_liability_per_person_cents",
        "insurance_hull_cents",
        "insurance_expiration",
    )


def test_every_insurance_field_is_an_aircraft_field() -> None:
    """``INSURANCE_FIELDS`` names only columns ``Aircraft`` has."""
    columns = {field.name for field in Aircraft._meta.concrete_fields}
    assert set(INSURANCE_FIELDS) <= columns


def test_the_insurance_item_reads_insurance() -> None:
    """The insurance item is labeled *Insurance*."""
    assert INSURANCE_LABEL == "Insurance"


# -- the columns -----------------------------------------------------------------
def test_the_photo_id_choices_are_the_six_kinds() -> None:
    """``PhotoIdType`` offers the six kinds, *Not provided* first."""
    assert PhotoIdType.choices == [
        ("not_provided", "Not provided"),
        ("drivers_license", "Driver's license"),
        ("passport", "Passport"),
        ("state_id", "State ID card"),
        ("military_id", "Military ID"),
        ("other", "Other"),
    ]


def test_a_fresh_profile_has_no_photo_id() -> None:
    """A profile's photo ID type defaults to *Not provided*."""
    assert MemberProfileFactory().photo_id_type == PhotoIdType.NOT_PROVIDED


@pytest.mark.parametrize("slug", PERSON_ITEMS)
@pytest.mark.parametrize("suffix", ["verified_at", "verified_by"])
def test_a_fresh_profile_records_no_verification(slug: str, suffix: str) -> None:
    """Every verification column of a new profile is empty."""
    assert getattr(MemberProfileFactory(), f"{slug}_{suffix}") is None


@pytest.mark.parametrize("slug", PERSON_ITEMS)
def test_a_fresh_profile_reads_unverified(slug: str) -> None:
    """Every item of a new profile reads unverified."""
    assert getattr(MemberProfileFactory(), f"{slug}_is_verified") is False


@pytest.mark.parametrize("column", ["insurance_verified_at", "insurance_verified_by"])
def test_a_fresh_aircraft_records_no_verification(column: str) -> None:
    """Both insurance verification columns of a new aircraft are empty."""
    assert getattr(AircraftFactory(), column) is None


def test_a_fresh_aircraft_reads_unverified() -> None:
    """A new aircraft's insurance reads unverified."""
    assert AircraftFactory().insurance_is_verified is False


@pytest.mark.parametrize("slug", PERSON_ITEMS)
def test_a_stamped_item_reads_verified(slug: str, verifier: User) -> None:
    """An item whose ``verified_at`` is set reads verified."""
    profile = MemberProfileFactory()
    setattr(profile, f"{slug}_verified_at", profile.created_at)
    setattr(profile, f"{slug}_verified_by", verifier)
    assert getattr(profile, f"{slug}_is_verified") is True


def test_stamped_insurance_reads_verified(verifier: User) -> None:
    """Insurance whose ``insurance_verified_at`` is set reads verified."""
    aircraft = AircraftFactory()
    aircraft.insurance_verified_at = aircraft.created_at
    aircraft.insurance_verified_by = verifier
    assert aircraft.insurance_is_verified is True


# -- the event -------------------------------------------------------------------
def test_the_event_follows_profile_changed() -> None:
    """``verification_changed`` comes right after ``profile_changed``."""
    index = EVENT_SLUGS.index("profile_changed")
    assert EVENT_SLUGS[index + 1] == "verification_changed"


def test_the_catalog_lists_the_event_as_verification_recorded() -> None:
    """The catalog names the event *Verification recorded* under Accounts."""
    event = EVENTS["verification_changed"]
    assert (event.label, event.category) == ("Verification recorded", "Accounts")


def test_the_event_goes_to_the_user_and_account_administrators() -> None:
    """Only the two administrators may be sent the event."""
    assert EVENTS["verification_changed"].roles == (USER_ADMIN, ACCOUNT_ADMIN)


def test_the_event_is_described_by_what_was_verified() -> None:
    """The catalog's description names the items."""
    assert EVENTS["verification_changed"].description == (
        "A verifier verified or cleared a member's certificate, medical, or photo ID, "
        "or an aircraft's insurance."
    )


def test_the_purpose_is_labeled_verification_recorded() -> None:
    """The email log reads the purpose as *Notification: Verification recorded*."""
    assert (
        PURPOSE_LABELS["notification_verification_changed"] == "Notification: Verification recorded"
    )
