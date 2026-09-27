"""A verified item is cleared by any write that moves its fields, and the services verify.

A person's three items (pilot certificate, medical, and photo ID) and an aircraft's
insurance each cover a fixed set of fields.  Every place those fields are written --
the member's own profile, an administrator's edit, an aircraft edit, and the two
verification services -- clears the item whose stored value moved and leaves the
others alone.  ``verify_member`` and ``verify_insurance`` write the fields and the
verified state together, record one audit line, and raise one
``verification_changed`` event when an item changed state.  The rules are
``docs/developer/verification.rst``.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.aircraft.models import Aircraft, AircraftChange
from apps.aircraft.verification import clear_stale_insurance, verify_insurance
from apps.members.models import MedicalType, MemberProfile, PhotoIdType, PilotCertificateType
from apps.members.services import update_member
from apps.members.verification import clear_stale, verify_member
from caldart import audit
from tests.conftest import RecordedEvents, audit_messages
from tests.factories import AircraftFactory, MemberProfileFactory, UserFactory

pytestmark = pytest.mark.django_db

PROFILE_URL = "/api/v1/me/profile"

#: A person's item slugs, in the order the screens list them.
PERSON_ITEMS = ("certificate", "medical", "photo_id")

#: When the items of a verified fixture were stamped.
STAMPED_AT = datetime(2026, 1, 15, 17, 0, tzinfo=timezone.get_current_timezone())


def verified_slugs(profile: MemberProfile) -> list[str]:
    """The slugs of ``profile``'s verified items, read afresh from the database."""
    profile.refresh_from_db()
    return [slug for slug in PERSON_ITEMS if getattr(profile, f"{slug}_is_verified")]


def raised(recorded: RecordedEvents, slug: str) -> list[dict[str, object]]:
    """The payloads of every ``slug`` event recorded, in the order raised."""
    return [dict(payload) for name, payload in recorded if name == slug]


@pytest.fixture
def stamper(db: None) -> User:
    """The account that verified the fixtures' items before each test began."""
    return UserFactory(email="stamper@example.test", first_name="Dana", last_name="Holt")


@pytest.fixture
def verified_profile(member: User, stamper: User) -> MemberProfile:
    """The ``member`` fixture's complete profile, with all three items verified."""
    stamps: dict[str, object] = {}
    for slug in PERSON_ITEMS:
        stamps[f"{slug}_verified_at"] = STAMPED_AT
        stamps[f"{slug}_verified_by"] = stamper
    return MemberProfileFactory(
        user=member,
        pilot_certificate_type=PilotCertificateType.PRIVATE,
        certificate_number="3181234",
        medical_type=MedicalType.THIRD,
        medical_expiration=timezone.localdate() + timedelta(days=300),
        photo_id_type=PhotoIdType.PASSPORT,
        **stamps,
    )


@pytest.fixture
def verified_aircraft(stamper: User) -> Aircraft:
    """An insured aircraft whose insurance was verified before each test began."""
    return AircraftFactory(
        n_number="N172SP",
        insurance_verified_at=STAMPED_AT,
        insurance_verified_by=stamper,
    )


@pytest.fixture
def member_client(api_client: APIClient, member: User) -> APIClient:
    """A client signed in as the ``member`` fixture."""
    api_client.force_login(member)
    return api_client


# --------------------------------------------------------------------------
# clear_stale
# --------------------------------------------------------------------------
def test_clear_stale_clears_only_the_item_whose_field_moved(
    verified_profile: MemberProfile,
) -> None:
    """A new medical type clears the medical and leaves the certificate and photo ID."""
    cleared = clear_stale(verified_profile, {"medical_type": MedicalType.SECOND})
    assert cleared == ["medical"]


def test_clear_stale_sets_both_columns_of_a_cleared_item_to_null(
    verified_profile: MemberProfile,
) -> None:
    """The cleared item carries neither a date nor a verifier."""
    clear_stale(verified_profile, {"photo_id_type": PhotoIdType.DRIVERS_LICENSE})
    assert (verified_profile.photo_id_verified_at, verified_profile.photo_id_verified_by) == (
        None,
        None,
    )


def test_clear_stale_clears_nothing_for_a_value_resent_unchanged(
    verified_profile: MemberProfile,
) -> None:
    """Resending every covered field at its stored value clears nothing."""
    changes = {
        "pilot_certificate_type": verified_profile.pilot_certificate_type,
        "certificate_number": verified_profile.certificate_number,
        "medical_type": verified_profile.medical_type,
        "medical_expiration": verified_profile.medical_expiration,
        "photo_id_type": verified_profile.photo_id_type,
    }
    assert clear_stale(verified_profile, changes) == []


def test_clear_stale_ignores_a_field_no_item_covers(verified_profile: MemberProfile) -> None:
    """Ratings, IFR, the flight review, and hours are not verified, so clear nothing."""
    changes = {"ifr_rated": "yes", "ratings": ["instrument"], "total_hours": 9000}
    assert clear_stale(verified_profile, changes) == []


def test_clear_stale_does_not_report_an_item_that_was_not_verified(member: User) -> None:
    """Moving an unverified item's field clears nothing, so nothing is reported."""
    profile = MemberProfileFactory(user=member)
    assert clear_stale(profile, {"certificate_number": "9999999"}) == []


def test_clear_stale_insurance_clears_on_a_moved_insurance_field(
    verified_aircraft: Aircraft,
) -> None:
    """A moved insurance field clears the insurance, and the call says so."""
    assert clear_stale_insurance(verified_aircraft, ["insurance_carrier"]) is True


def test_clear_stale_insurance_saves_the_cleared_columns(verified_aircraft: Aircraft) -> None:
    """The cleared insurance reads unverified from the database."""
    clear_stale_insurance(verified_aircraft, ["insurance_expiration"])
    verified_aircraft.refresh_from_db()
    assert verified_aircraft.insurance_is_verified is False


def test_clear_stale_insurance_leaves_it_for_a_field_it_does_not_cover(
    verified_aircraft: Aircraft,
) -> None:
    """Moving the notes or the owner leaves the insurance verified."""
    assert clear_stale_insurance(verified_aircraft, ["notes", "owner_name"]) is False


# --------------------------------------------------------------------------
# The member's own profile
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("patch", "left"),
    [
        ({"medical_type": "second"}, ["certificate", "photo_id"]),
        ({"medical_expiration": "2031-01-01"}, ["certificate", "photo_id"]),
        ({"certificate_number": "7654321"}, ["medical", "photo_id"]),
        ({"pilot_certificate_type": "commercial"}, ["medical", "photo_id"]),
        ({"photo_id_type": "state_id"}, ["certificate", "medical"]),
        ({"ifr_rated": "yes", "total_hours": 1200}, list(PERSON_ITEMS)),
    ],
    ids=["medical-type", "medical-expiration", "number", "certificate", "photo-id", "unverified"],
)
def test_a_members_own_edit_clears_the_item_it_moves(
    member_client: APIClient,
    verified_profile: MemberProfile,
    patch: dict[str, object],
    left: list[str],
) -> None:
    """``PATCH /me/profile`` clears exactly the items whose fields changed."""
    response = member_client.patch(PROFILE_URL, patch, format="json")
    assert response.status_code == 200
    assert verified_slugs(verified_profile) == left


def test_a_members_own_edit_resending_the_values_clears_nothing(
    member_client: APIClient, verified_profile: MemberProfile
) -> None:
    """A form that resends the stored certificate and medical keeps every item."""
    body = {
        "pilot_certificate_type": "private",
        "certificate_number": "3181234",
        "medical_type": "third",
        "medical_expiration": verified_profile.medical_expiration.isoformat()
        if verified_profile.medical_expiration is not None
        else None,
        "photo_id_type": "passport",
    }
    member_client.patch(PROFILE_URL, body, format="json")
    assert verified_slugs(verified_profile) == list(PERSON_ITEMS)


def test_a_members_own_edit_raises_profile_changed_and_no_verification_event(
    member_client: APIClient,
    verified_profile: MemberProfile,
    recorded_events: RecordedEvents,
) -> None:
    """Clearing an item by an edit is told by ``profile_changed`` alone."""
    member_client.patch(PROFILE_URL, {"medical_type": "second"}, format="json")
    assert [slug for slug, _ in recorded_events] == ["profile_changed"]


# --------------------------------------------------------------------------
# An administrator's edit
# --------------------------------------------------------------------------
def test_an_administrators_edit_clears_the_item_it_moves(
    account_admin: User, member: User, verified_profile: MemberProfile
) -> None:
    """``update_member`` with a new certificate number clears the certificate alone."""
    update_member(account_admin, member, profile={"certificate_number": "1111111"})
    assert verified_slugs(verified_profile) == ["medical", "photo_id"]


def test_an_administrators_edit_through_the_api_clears_the_item_it_moves(
    account_admin_client: APIClient, member: User, verified_profile: MemberProfile
) -> None:
    """``PATCH /admin/members/{id}`` with a new photo ID type clears the photo ID."""
    response = account_admin_client.patch(
        f"/api/v1/admin/members/{member.pk}",
        {"profile": {"photo_id_type": "military_id"}},
        format="json",
    )
    assert response.status_code == 200
    assert verified_slugs(verified_profile) == ["certificate", "medical"]


# --------------------------------------------------------------------------
# An aircraft edit
# --------------------------------------------------------------------------
def test_an_aircraft_edit_moving_an_insurance_field_clears_the_insurance(
    account_admin_client: APIClient, verified_aircraft: Aircraft
) -> None:
    """``PATCH /aircraft/{id}`` with a new carrier leaves the insurance unverified."""
    response = account_admin_client.patch(
        f"/api/v1/aircraft/{verified_aircraft.pk}",
        {"insurance_carrier": "USAIG"},
        format="json",
    )
    assert response.status_code == 200
    verified_aircraft.refresh_from_db()
    assert verified_aircraft.insurance_is_verified is False


def test_an_aircraft_edit_moving_no_insurance_field_keeps_the_insurance(
    account_admin_client: APIClient, verified_aircraft: Aircraft
) -> None:
    """An edit to the notes, resending the carrier unchanged, keeps it verified."""
    account_admin_client.patch(
        f"/api/v1/aircraft/{verified_aircraft.pk}",
        {"notes": "Hangar 4", "insurance_carrier": verified_aircraft.insurance_carrier},
        format="json",
    )
    verified_aircraft.refresh_from_db()
    assert verified_aircraft.insurance_is_verified is True


def test_an_aircraft_edit_raises_aircraft_changed_and_no_verification_event(
    account_admin_client: APIClient,
    verified_aircraft: Aircraft,
    recorded_events: RecordedEvents,
) -> None:
    """Clearing the insurance by an edit is told by ``aircraft_changed`` alone."""
    account_admin_client.patch(
        f"/api/v1/aircraft/{verified_aircraft.pk}",
        {"insurance_expiration": "2030-01-01"},
        format="json",
    )
    assert [slug for slug, _ in recorded_events] == ["aircraft_changed"]


# --------------------------------------------------------------------------
# verify_member
# --------------------------------------------------------------------------
def test_verify_member_stamps_each_item_with_the_actor(
    dart_leader: User, member: User, today: date
) -> None:
    """Every item named is stamped with the verifier."""
    MemberProfileFactory(user=member)
    profile = verify_member(dart_leader, member, changes={}, verified=list(PERSON_ITEMS))
    assert [getattr(profile, f"{slug}_verified_by") for slug in PERSON_ITEMS] == [
        dart_leader
    ] * 3


def test_verify_member_stamps_each_item_with_the_time(
    dart_leader: User, member: User, today: date
) -> None:
    """Every item named is stamped with the moment of the save."""
    MemberProfileFactory(user=member)
    profile = verify_member(dart_leader, member, changes={}, verified=["medical"])
    assert profile.medical_verified_at == timezone.now()


def test_verify_member_leaves_an_already_verified_stamp_alone(
    dart_leader: User, member: User, stamper: User, verified_profile: MemberProfile
) -> None:
    """Re-verifying an item keeps who verified it first, and when."""
    profile = verify_member(dart_leader, member, changes={}, verified=list(PERSON_ITEMS))
    assert (profile.certificate_verified_by, profile.certificate_verified_at) == (
        stamper,
        STAMPED_AT,
    )


def test_verify_member_clears_an_item_left_out(
    dart_leader: User, member: User, verified_profile: MemberProfile
) -> None:
    """An item missing from ``verified`` ends unverified."""
    verify_member(dart_leader, member, changes={}, verified=["certificate", "medical"])
    assert verified_slugs(verified_profile) == ["certificate", "medical"]


def test_verify_member_writes_the_changes(
    dart_leader: User, member: User, verified_profile: MemberProfile
) -> None:
    """The fields in ``changes`` are written to the profile."""
    verify_member(
        dart_leader, member, changes={"photo_id_type": PhotoIdType.STATE_ID}, verified=[]
    )
    verified_profile.refresh_from_db()
    assert verified_profile.photo_id_type == PhotoIdType.STATE_ID


def test_verify_member_restamps_a_changed_item_that_is_ticked(
    dart_leader: User, member: User, verified_profile: MemberProfile, today: date
) -> None:
    """A changed field clears its item first, so ticking it stamps the new verifier."""
    profile = verify_member(
        dart_leader,
        member,
        changes={"medical_expiration": today + timedelta(days=700)},
        verified=list(PERSON_ITEMS),
    )
    assert (profile.medical_verified_by, profile.medical_verified_at) == (
        dart_leader,
        timezone.now(),
    )


def test_verify_member_leaves_a_changed_item_unticked_unverified(
    dart_leader: User, member: User, verified_profile: MemberProfile
) -> None:
    """A changed field whose item is not in ``verified`` ends unverified."""
    verify_member(
        dart_leader,
        member,
        changes={"certificate_number": "2222222"},
        verified=["medical", "photo_id"],
    )
    assert verified_slugs(verified_profile) == ["medical", "photo_id"]


def test_verify_member_creates_a_missing_profile(dart_leader: User, member: User) -> None:
    """An account with no profile row gets one, with the items verified."""
    verify_member(dart_leader, member, changes={}, verified=["photo_id"])
    assert MemberProfile.objects.get(user=member).photo_id_verified_by == dart_leader


def test_verify_member_records_the_audit_line(
    dart_leader: User,
    member: User,
    verified_profile: MemberProfile,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """``member.verify`` names the items verified and cleared, by slug."""
    verify_member(
        dart_leader,
        member,
        changes={"medical_type": MedicalType.FIRST},
        verified=["certificate", "medical"],
    )
    assert audit_messages(audit_log)[-1] == (
        f"action={audit.MEMBER_VERIFY} actor={dart_leader.pk} target={member.pk} "
        "verified=medical cleared=photo_id"
    )


def test_verify_member_raises_one_verification_changed_event(
    dart_leader: User,
    member: User,
    verified_profile: MemberProfile,
    recorded_events: RecordedEvents,
) -> None:
    """One event per save names the actor, the member, and the items by label."""
    verify_member(
        dart_leader,
        member,
        changes={"medical_type": MedicalType.FIRST},
        verified=["certificate", "medical"],
    )
    assert raised(recorded_events, "verification_changed") == [
        {"user": member, "verified": ["Medical"], "cleared": ["Photo ID"], "actor": dart_leader}
    ]


def test_verify_member_raises_profile_changed_for_the_fields_it_writes(
    dart_leader: User,
    member: User,
    verified_profile: MemberProfile,
    recorded_events: RecordedEvents,
) -> None:
    """The field write is told as ``profile_changed``, under the verifier's name."""
    verify_member(
        dart_leader, member, changes={"photo_id_type": PhotoIdType.OTHER}, verified=["photo_id"]
    )
    assert raised(recorded_events, "profile_changed") == [
        {"user": member, "fields": ["Photo ID"], "actor": dart_leader}
    ]


def test_verify_member_raises_nothing_when_no_item_changes_state(
    dart_leader: User,
    member: User,
    verified_profile: MemberProfile,
    recorded_events: RecordedEvents,
) -> None:
    """Re-verifying what is already verified, with no change, raises nothing."""
    verify_member(dart_leader, member, changes={}, verified=list(PERSON_ITEMS))
    assert recorded_events == []


def test_verify_member_with_no_changes_leaves_the_profile_stamp_alone(
    dart_leader: User, member: User, verified_profile: MemberProfile
) -> None:
    """Verifying alone is not a profile edit, so ``profile_updated_at`` stays put."""
    before = verified_profile.profile_updated_at
    verify_member(dart_leader, member, changes={}, verified=["medical"])
    verified_profile.refresh_from_db()
    assert verified_profile.profile_updated_at == before


# --------------------------------------------------------------------------
# verify_insurance
# --------------------------------------------------------------------------
def test_verify_insurance_stamps_the_actor_and_the_time(
    dart_leader: User, aircraft: Aircraft, today: date
) -> None:
    """A verified save stamps the verifier and the moment."""
    result = verify_insurance(aircraft, actor=dart_leader, changes={}, verified=True)
    assert (result.insurance_verified_by, result.insurance_verified_at) == (
        dart_leader,
        timezone.now(),
    )


def test_verify_insurance_clears_when_not_verified(
    dart_leader: User, verified_aircraft: Aircraft
) -> None:
    """``verified`` false leaves the insurance unverified."""
    verify_insurance(verified_aircraft, actor=dart_leader, changes={}, verified=False)
    verified_aircraft.refresh_from_db()
    assert verified_aircraft.insurance_verified_at is None


def test_verify_insurance_leaves_an_already_verified_stamp_alone(
    dart_leader: User, stamper: User, verified_aircraft: Aircraft
) -> None:
    """Re-verifying keeps who verified it first."""
    result = verify_insurance(verified_aircraft, actor=dart_leader, changes={}, verified=True)
    assert result.insurance_verified_by == stamper


def test_verify_insurance_restamps_after_a_change(
    dart_leader: User, verified_aircraft: Aircraft, today: date
) -> None:
    """A changed field clears the insurance first, so a verified save stamps anew."""
    result = verify_insurance(
        verified_aircraft,
        actor=dart_leader,
        changes={"insurance_expiration": today + timedelta(days=400)},
        verified=True,
    )
    assert (result.insurance_verified_by, result.insurance_verified_at) == (
        dart_leader,
        timezone.now(),
    )


def test_verify_insurance_writes_the_changes_with_a_history_row(
    dart_leader: User, verified_aircraft: Aircraft
) -> None:
    """The fields are written and the register's history names the columns moved."""
    verify_insurance(
        verified_aircraft,
        actor=dart_leader,
        changes={"insurance_carrier": "USAIG"},
        verified=True,
    )
    change = AircraftChange.objects.get(aircraft=verified_aircraft)
    assert (change.changed_by, change.fields) == (dart_leader, ["insurance_carrier"])


def test_verify_insurance_records_the_audit_line(
    dart_leader: User, aircraft: Aircraft, audit_log: pytest.LogCaptureFixture
) -> None:
    """``aircraft.verify`` names the aircraft and whether the insurance is verified."""
    verify_insurance(aircraft, actor=dart_leader, changes={}, verified=True)
    assert audit_messages(audit_log)[-1] == (
        f"action={audit.AIRCRAFT_VERIFY} actor={dart_leader.pk} target={aircraft.pk} "
        "verified=true"
    )


def test_verify_insurance_raises_one_verification_changed_event(
    dart_leader: User, aircraft: Aircraft, recorded_events: RecordedEvents
) -> None:
    """The event names the aircraft, the actor, and Insurance as verified."""
    verify_insurance(aircraft, actor=dart_leader, changes={}, verified=True)
    assert raised(recorded_events, "verification_changed") == [
        {"aircraft": aircraft, "verified": ["Insurance"], "cleared": [], "actor": dart_leader}
    ]


def test_verify_insurance_raises_a_clearing_event(
    dart_leader: User, verified_aircraft: Aircraft, recorded_events: RecordedEvents
) -> None:
    """Clearing a verified insurance names Insurance as cleared."""
    verify_insurance(verified_aircraft, actor=dart_leader, changes={}, verified=False)
    assert raised(recorded_events, "verification_changed") == [
        {
            "aircraft": verified_aircraft,
            "verified": [],
            "cleared": ["Insurance"],
            "actor": dart_leader,
        }
    ]


def test_verify_insurance_raises_nothing_when_the_state_holds(
    dart_leader: User, verified_aircraft: Aircraft, recorded_events: RecordedEvents
) -> None:
    """Re-verifying with no change raises no event at all."""
    verify_insurance(verified_aircraft, actor=dart_leader, changes={}, verified=True)
    assert recorded_events == []
