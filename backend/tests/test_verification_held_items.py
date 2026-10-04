"""An item a person does not hold has nothing to verify, and both checks read one rule.

A pilot certificate of ``none``, a medical of ``none``, and a photo ID of
``not_provided`` are items the person does not hold: ``verify_member`` never stamps
one, and a stamp left on one does not make the person verified.  The aircraft check's
pilot list carries each pilot's member check verdict, so the two checks never disagree
about the same person.  The rules are ``docs/developer/verification.rst`` and
``docs/developer/api-aircraft.rst``.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.aircraft.models import Aircraft
from apps.aircraft.verification import verify_insurance
from apps.darts.models import Dart
from apps.members.models import (
    MedicalType,
    MemberProfile,
    MembershipPlan,
    PhotoIdType,
    PilotCertificateType,
)
from apps.members.verification import is_fully_verified, is_held, verify_member
from tests.factories import AircraftFactory, MemberProfileFactory, MembershipFactory, UserFactory

pytestmark = pytest.mark.django_db

AIRCRAFT_URL = "/api/v1/leader/aircraft"
SEARCH_URL = "/api/v1/leader/search"

#: A person's item slugs, in the order the screens list them.
PERSON_ITEMS = ["certificate", "medical", "photo_id"]

#: When the stamped fixtures were verified.
STAMPED_AT = datetime(2026, 1, 15, 17, 0, tzinfo=timezone.get_current_timezone())


def all_stamps(by: User) -> dict[str, object]:
    """Verification columns stamping all three items by ``by`` at :data:`STAMPED_AT`."""
    stamps: dict[str, object] = {}
    for slug in PERSON_ITEMS:
        stamps[f"{slug}_verified_at"] = STAMPED_AT
        stamps[f"{slug}_verified_by"] = by
    return stamps


@pytest.fixture
def stamper(db: None) -> User:
    """The account that verified the stamped fixtures."""
    return UserFactory(email="stamper@example.test", first_name="Dana", last_name="Holt")


@pytest.fixture
def non_pilot(db: None) -> MemberProfile:
    """A profile holding no pilot certificate, no medical, and no photo ID."""
    return MemberProfileFactory(
        user=UserFactory(email="ground@example.test", first_name="Gil", last_name="Ground"),
        pilot_certificate_type=PilotCertificateType.NONE,
        certificate_number="",
        medical_type=MedicalType.NONE,
        medical_expiration=None,
        photo_id_type=PhotoIdType.NOT_PROVIDED,
    )


@pytest.mark.parametrize(
    ("field", "value", "slug"),
    [
        ("pilot_certificate_type", PilotCertificateType.NONE, "certificate"),
        ("medical_type", MedicalType.NONE, "medical"),
        ("photo_id_type", PhotoIdType.NOT_PROVIDED, "photo_id"),
    ],
    ids=["no-certificate", "no-medical", "no-photo-id"],
)
def test_an_item_marked_none_is_not_held(field: str, value: str, slug: str) -> None:
    """Each item's ``none`` value means the person does not hold it."""
    profile = MemberProfileFactory.build(**{field: value})
    assert is_held(profile, slug) is False


@pytest.mark.parametrize("slug", PERSON_ITEMS)
def test_an_item_with_a_value_is_held(slug: str) -> None:
    """A certificate, a medical class, and a kind of photo ID are each held."""
    profile = MemberProfileFactory.build(photo_id_type=PhotoIdType.PASSPORT)
    assert is_held(profile, slug) is True


def test_verifying_a_non_pilot_stamps_nothing_they_do_not_hold(
    non_pilot: MemberProfile, dart_leader: User
) -> None:
    """Asking to verify three items the person does not hold leaves them unverified."""
    verify_member(dart_leader, non_pilot.user, changes={}, verified=PERSON_ITEMS)
    non_pilot.refresh_from_db()
    assert [slug for slug in PERSON_ITEMS if getattr(non_pilot, f"{slug}_is_verified")] == []


def test_verifying_stamps_the_held_items_beside_one_not_held(
    dart_leader: User,
) -> None:
    """A pilot with no photo ID on file has only the certificate and medical stamped."""
    profile = MemberProfileFactory(photo_id_type=PhotoIdType.NOT_PROVIDED)
    verify_member(dart_leader, profile.user, changes={}, verified=PERSON_ITEMS)
    profile.refresh_from_db()
    verified = [slug for slug in PERSON_ITEMS if getattr(profile, f"{slug}_is_verified")]
    assert verified == ["certificate", "medical"]


def test_a_stamp_on_an_item_not_held_does_not_verify_the_person(
    non_pilot: MemberProfile, stamper: User
) -> None:
    """Stamps left on items the person does not hold leave them not fully verified."""
    for column, value in all_stamps(stamper).items():
        setattr(non_pilot, column, value)
    assert is_fully_verified(non_pilot) is False


def test_a_pilot_with_every_held_item_stamped_is_fully_verified(stamper: User) -> None:
    """A certificate, a medical, and a photo ID, all stamped, verify the person."""
    profile = MemberProfileFactory.build(photo_id_type=PhotoIdType.PASSPORT, **all_stamps(stamper))
    assert is_fully_verified(profile) is True


@pytest.fixture
def flown(db: None) -> Aircraft:
    """The airplane the pilot-list tests attach their pilots to."""
    return AircraftFactory(n_number="N100ML")


def _attach(user: User, aircraft: Aircraft, **profile: object) -> None:
    """Give ``user`` a profile with ``profile``'s fields, flying ``aircraft``."""
    MemberProfileFactory(user=user, **profile).aircraft.add(aircraft)


def test_the_pilot_list_reads_a_friend_as_a_friend(
    api_client: APIClient, dart_leader: User, friend: User, flown: Aircraft
) -> None:
    """A friend who flies the airplane is listed with ``membership_status`` ``friend``."""
    _attach(friend, flown)
    api_client.force_login(dart_leader)
    pilots = api_client.get(AIRCRAFT_URL, {"n_number": flown.n_number}).json()["pilots"]
    assert [pilot["membership_status"] for pilot in pilots] == ["friend"]


def test_the_pilot_list_carries_the_member_checks_verdict(
    api_client: APIClient,
    dart_leader: User,
    dart: Dart,
    annual_plan: MembershipPlan,
    stamper: User,
    flown: Aircraft,
) -> None:
    """A current pilot whose items nobody has verified is cleared on neither check.

    The pilot's ``go_no_go`` on the aircraft card equals the member check's search row
    for the same person, ``verified`` false among it.
    """
    today = timezone.localdate()
    user = UserFactory(email="pilot@example.test", first_name="Ana", last_name="Bracco")
    _attach(user, flown, dart=dart, photo_id_type=PhotoIdType.PASSPORT)
    MembershipFactory(
        user=user,
        plan=annual_plan,
        starts_on=today - timedelta(days=30),
        ends_on=today + timedelta(days=300),
    )
    api_client.force_login(dart_leader)
    pilot = api_client.get(AIRCRAFT_URL, {"n_number": flown.n_number}).json()["pilots"][0]
    row = api_client.get(SEARCH_URL, {"q": "Bracco"}).json()[0]
    assert pilot["go_no_go"] == row["go_no_go"]
    assert pilot["go_no_go"] == {"membership": True, "medical": True, "verified": False}


def test_insurance_with_no_policy_on_file_is_never_stamped(dart_leader: User) -> None:
    """Asking to verify an aircraft with no insurance expiration leaves it unverified."""
    aircraft = AircraftFactory(n_number="N44BE", insurance_expiration=None)
    verify_insurance(aircraft, actor=dart_leader, changes={}, verified=True)
    aircraft.refresh_from_db()
    assert aircraft.insurance_is_verified is False
