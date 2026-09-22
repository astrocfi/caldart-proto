"""Member self-service API: profile, membership, payments, catalogs."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.aircraft.models import Aircraft
from apps.members.models import Dart, MemberProfile, MembershipPlan
from tests.conftest import ROLE_MATRIX
from tests.factories import (
    AircraftFactory,
    DartFactory,
    MemberProfileFactory,
    MembershipFactory,
    MembershipPlanFactory,
    PaymentFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db

PROFILE_URL = "/api/v1/me/profile"
MEMBERSHIP_URL = "/api/v1/me/membership"
PAYMENTS_URL = "/api/v1/me/payments"
DARTS_URL = "/api/v1/darts"
PLANS_URL = "/api/v1/plans"

#: The smallest body a PUT will accept.
MINIMAL_PUT = {"phone": "555-0100"}


# --------------------------------------------------------------------------
# Role matrix
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("method", "url"),
    [
        ("get", PROFILE_URL),
        ("put", PROFILE_URL),
        ("patch", PROFILE_URL),
        ("get", MEMBERSHIP_URL),
        ("get", PAYMENTS_URL),
        ("post", "/api/v1/me/profile/aircraft"),
        ("delete", "/api/v1/me/profile/aircraft/1"),
    ],
)
def test_me_endpoints_are_401_when_anonymous(api_client: APIClient, method: str, url: str) -> None:
    """Every ``/me`` endpoint is 401 for a client with no session."""
    response = getattr(api_client, method)(url, {} if method in {"put", "patch", "post"} else None)
    assert response.status_code == 401


@pytest.mark.parametrize("url", [PROFILE_URL, MEMBERSHIP_URL, PAYMENTS_URL])
@pytest.mark.parametrize("slug", ROLE_MATRIX)
def test_every_role_reads_its_own_profile(
    api_client: APIClient, all_role_users: dict[str, User], url: str, slug: str
) -> None:
    """Every role, not just member, can read its own profile, membership and payments."""
    api_client.force_login(all_role_users[slug])
    assert api_client.get(url).status_code == 200


def test_catalogs_are_public(
    api_client: APIClient, dart: Dart, annual_plan: MembershipPlan
) -> None:
    """The DART and plan catalogs need no session."""
    assert api_client.get(DARTS_URL).status_code == 200
    assert api_client.get(PLANS_URL).status_code == 200


# --------------------------------------------------------------------------
# Catalogs
# --------------------------------------------------------------------------
def test_darts_lists_active_darts_in_order(api_client: APIClient, db: None) -> None:
    """The DART list carries only active rows, ordered by ``sort_order``."""
    DartFactory(name="Zulu", sort_order=2, is_active=True)
    DartFactory(name="Alpha", sort_order=1, is_active=True)
    DartFactory(name="Retired", sort_order=0, is_active=False)

    rows = api_client.get(DARTS_URL).json()

    assert [row["name"] for row in rows] == ["Alpha", "Zulu"]
    assert set(rows[0]) == {"id", "name", "airport_identifier", "city"}


def test_plans_lists_active_plans_in_order(api_client: APIClient, db: None) -> None:
    """The plan list carries only active rows, ordered by ``sort_order``."""
    MembershipPlanFactory(name="Annual", slug="annual", sort_order=1)
    MembershipPlanFactory(name="Life", slug="life", duration_days=None, sort_order=2)
    MembershipPlanFactory(name="Retired", slug="retired", sort_order=0, is_active=False)

    rows = api_client.get(PLANS_URL).json()

    assert [row["slug"] for row in rows] == ["annual", "life"]
    assert set(rows[0]) == {"slug", "name", "price_cents", "duration_days", "description"}
    assert rows[1]["duration_days"] is None


def test_catalogs_are_not_paginated(
    api_client: APIClient, dart: Dart, annual_plan: MembershipPlan
) -> None:
    """Both catalog endpoints return a plain list, not a paginated envelope."""
    assert isinstance(api_client.get(DARTS_URL).json(), list)
    assert isinstance(api_client.get(PLANS_URL).json(), list)


# --------------------------------------------------------------------------
# Reading the profile
# --------------------------------------------------------------------------
def test_get_profile_returns_the_documented_shape(
    api_client: APIClient, member: User, profile: MemberProfile, aircraft: Aircraft
) -> None:
    """A profile with an aircraft returns the documented shape, aircraft included."""
    profile.aircraft.add(aircraft)
    api_client.force_login(member)
    assert profile.dart is not None
    assert aircraft.insurance_expiration is not None

    data = api_client.get(PROFILE_URL).json()

    assert data["phone"] == profile.phone
    assert data["dart"] == {"id": profile.dart_id, "name": profile.dart.name}
    assert data["medical_is_current"] is True
    assert data["aircraft"] == [
        {
            "id": aircraft.id,
            "n_number": aircraft.n_number,
            "make": aircraft.make,
            "model": aircraft.model,
            "insurance_is_current": True,
            "insurance_expiration": aircraft.insurance_expiration.isoformat(),
            "insurance_summary": aircraft.insurance_summary,
        }
    ]


def test_get_profile_hides_admin_only_fields(
    api_client: APIClient, member: User, profile: MemberProfile
) -> None:
    """``notes`` and ``how_heard`` never appear in the member's own view."""
    profile.notes = "Do not call before noon"
    profile.how_heard = "A friend"
    profile.save(update_fields=["notes", "how_heard"])
    api_client.force_login(member)

    data = api_client.get(PROFILE_URL).json()

    assert "notes" not in data
    assert "how_heard" not in data


def test_get_profile_creates_one_when_the_member_has_none(
    api_client: APIClient, member: User
) -> None:
    """A first ``GET`` with no existing profile row creates one and returns it."""
    assert not MemberProfile.objects.filter(user=member).exists()
    api_client.force_login(member)

    response = api_client.get(PROFILE_URL)

    assert response.status_code == 200
    assert response.json()["phone"] == ""
    assert MemberProfile.objects.filter(user=member).exists()


def test_get_profile_null_dart_reads_as_null(
    api_client: APIClient, member: User, profile_factory: type[MemberProfileFactory]
) -> None:
    """A profile with no DART reports ``dart: null``."""
    profile_factory(user=member, dart=None)
    api_client.force_login(member)
    assert api_client.get(PROFILE_URL).json()["dart"] is None


# --------------------------------------------------------------------------
# Writing the profile
# --------------------------------------------------------------------------
def test_put_updates_every_writable_section(
    api_client: APIClient, member: User, dart: Dart, profile: MemberProfile
) -> None:
    """A full ``PUT`` writes every writable section: contact, aviation, and flags."""
    api_client.force_login(member)

    response = api_client.put(
        PROFILE_URL,
        {
            "phone": "650-555-0101",
            "phone_alt": "650-555-0102",
            "address_line1": "1 Embarcadero",
            "city": "San Carlos",
            "state": "ca",
            "postal_code": "94070",
            "county": "San Mateo",
            "emergency_contact_name": "Dana Lee",
            "emergency_contact_phone": "650-555-0199",
            "home_airport_identifier": "SQL",
            "home_airport_city": "San Carlos",
            "dart_id": dart.id,
            "pilot_certificate_type": "commercial",
            "certificate_number": "3141592",
            "ifr_rated": "yes",
            "ratings": ["instrument", "multi_engine"],
            "medical_type": "second",
            "medical_expiration": "2030-01-31",
            "total_hours": 1200,
            "vol_ground_team": True,
            "vol_newsletter": True,
        },
        format="json",
    )

    assert response.status_code == 200, response.json()
    data = response.json()
    assert data["state"] == "CA"  # normalized
    assert data["dart"] == {"id": dart.id, "name": dart.name}
    assert data["ratings"] == ["instrument", "multi_engine"]
    assert data["vol_ground_team"] is True
    assert data["vol_fundraising"] is False

    profile.refresh_from_db()
    assert profile.phone == "650-555-0101"
    assert profile.total_hours == 1200


def test_put_requires_a_phone_number(
    api_client: APIClient, member: User, profile: MemberProfile
) -> None:
    """A ``PUT`` with no phone number is refused, naming ``phone``."""
    api_client.force_login(member)
    response = api_client.put(PROFILE_URL, {"city": "Napa"}, format="json")
    assert response.status_code == 400
    assert "phone" in response.json()


def test_put_clears_fields_left_out_of_the_body(
    api_client: APIClient, member: User, profile: MemberProfile
) -> None:
    """A ``PUT`` clears every writable field the body leaves out, back to its default."""
    profile.vol_ground_team = True
    profile.save(update_fields=["vol_ground_team"])
    api_client.force_login(member)

    response = api_client.put(PROFILE_URL, MINIMAL_PUT, format="json")

    assert response.status_code == 200, response.json()
    profile.refresh_from_db()
    assert profile.city == ""
    assert profile.pilot_certificate_type == "none"
    assert profile.ratings == []
    assert profile.dart is None
    assert profile.total_hours is None
    assert profile.vol_ground_team is False
    assert profile.state == "CA"  # back to the model default


def test_patch_leaves_untouched_fields_alone(
    api_client: APIClient, member: User, profile: MemberProfile
) -> None:
    """A ``PATCH`` writes only the fields it carries, leaving the rest as they were."""
    api_client.force_login(member)
    original_city = profile.city

    response = api_client.patch(PROFILE_URL, {"phone_alt": "555-0111"}, format="json")

    assert response.status_code == 200
    profile.refresh_from_db()
    assert profile.phone_alt == "555-0111"
    assert profile.city == original_city


def test_patch_rejects_a_blank_phone(
    api_client: APIClient, member: User, profile: MemberProfile
) -> None:
    """A ``PATCH`` clearing the phone number to blank is refused, naming ``phone``."""
    api_client.force_login(member)
    response = api_client.patch(PROFILE_URL, {"phone": ""}, format="json")
    assert response.status_code == 400
    assert "phone" in response.json()


def test_admin_only_fields_are_not_writable(
    api_client: APIClient, member: User, profile: MemberProfile
) -> None:
    """A member ``PATCH`` cannot write ``notes`` or ``how_heard``: they stay blank."""
    api_client.force_login(member)
    response = api_client.patch(
        PROFILE_URL, {"notes": "promote me", "how_heard": "nowhere"}, format="json"
    )
    assert response.status_code == 200
    profile.refresh_from_db()
    assert profile.notes == ""
    assert profile.how_heard == ""


def test_aircraft_is_read_only_on_the_profile(
    api_client: APIClient, member: User, profile: MemberProfile, aircraft: Aircraft
) -> None:
    """A ``PATCH`` cannot attach an aircraft to the profile: that field is read-only."""
    api_client.force_login(member)
    response = api_client.patch(PROFILE_URL, {"aircraft": [aircraft.id]}, format="json")
    assert response.status_code == 200
    assert profile.aircraft.count() == 0


def test_a_member_can_only_edit_their_own_profile(
    api_client: APIClient,
    member: User,
    profile: MemberProfile,
    profile_factory: type[MemberProfileFactory],
) -> None:
    """A member's ``PATCH`` never reaches another member's profile."""
    other = profile_factory(user=UserFactory(email="other@example.test"))
    api_client.force_login(member)

    api_client.patch(PROFILE_URL, {"phone": "555-9999"}, format="json")

    other.refresh_from_db()
    assert other.phone != "555-9999"


# -- validation ------------------------------------------------------------
def test_medical_expiration_is_required_for_a_real_medical(
    api_client: APIClient, member: User, profile_factory: type[MemberProfileFactory]
) -> None:
    """Setting a real medical type with no expiration date is refused."""
    profile_factory(user=member, medical_type="none", medical_expiration=None)
    api_client.force_login(member)

    response = api_client.patch(PROFILE_URL, {"medical_type": "basicmed"}, format="json")

    assert response.status_code == 400
    assert "medical_expiration" in response.json()


def test_medical_expiration_may_be_omitted_when_there_is_no_medical(
    api_client: APIClient, member: User, profile_factory: type[MemberProfileFactory]
) -> None:
    """A profile with no medical type needs no expiration date."""
    profile_factory(user=member, medical_type="none", medical_expiration=None)
    api_client.force_login(member)
    assert api_client.put(PROFILE_URL, MINIMAL_PUT, format="json").status_code == 200


def test_medical_expiration_supplied_together_is_accepted(
    api_client: APIClient, member: User, profile: MemberProfile
) -> None:
    """Setting the medical type and its expiration date together is accepted."""
    api_client.force_login(member)
    response = api_client.patch(
        PROFILE_URL,
        {"medical_type": "basicmed", "medical_expiration": "2029-05-31"},
        format="json",
    )
    assert response.status_code == 200
    assert response.json()["medical_expiration"] == "2029-05-31"


def test_certificate_number_is_required_for_a_real_certificate(
    api_client: APIClient, member: User, profile_factory: type[MemberProfileFactory]
) -> None:
    """Setting a real certificate type with no certificate number is refused."""
    profile_factory(user=member, pilot_certificate_type="none", certificate_number="")
    api_client.force_login(member)

    response = api_client.patch(PROFILE_URL, {"pilot_certificate_type": "private"}, format="json")

    assert response.status_code == 400
    assert "certificate_number" in response.json()


def test_certificate_number_is_not_required_without_a_certificate(
    api_client: APIClient, member: User, profile_factory: type[MemberProfileFactory]
) -> None:
    """A profile with no certificate type needs no certificate number."""
    profile_factory(user=member, pilot_certificate_type="none", certificate_number="")
    api_client.force_login(member)
    assert api_client.put(PROFILE_URL, MINIMAL_PUT, format="json").status_code == 200


def test_ratings_must_come_from_the_allowed_list(
    api_client: APIClient, member: User, profile: MemberProfile
) -> None:
    """An unrecognized rating value is refused, naming ``ratings``."""
    api_client.force_login(member)
    response = api_client.patch(PROFILE_URL, {"ratings": ["warp_drive"]}, format="json")
    assert response.status_code == 400
    assert "ratings" in response.json()


def test_ratings_are_de_duplicated(
    api_client: APIClient, member: User, profile: MemberProfile
) -> None:
    """A repeated rating is written only once, in the order first seen."""
    api_client.force_login(member)
    response = api_client.patch(PROFILE_URL, {"ratings": ["cfi", "cfi", "glider"]}, format="json")
    assert response.status_code == 200
    assert response.json()["ratings"] == ["cfi", "glider"]


@pytest.mark.parametrize("state", ["California", "C", "1A"])
def test_state_must_be_two_letters(
    api_client: APIClient, member: User, profile: MemberProfile, state: str
) -> None:
    """A state value that is not two letters is refused, naming ``state``."""
    api_client.force_login(member)
    response = api_client.patch(PROFILE_URL, {"state": state}, format="json")
    assert response.status_code == 400
    assert "state" in response.json()


@pytest.mark.parametrize("postal_code", ["9403", "abcde", "94040-12"])
def test_postal_code_must_look_like_a_zip(
    api_client: APIClient, member: User, profile: MemberProfile, postal_code: str
) -> None:
    """A postal code that does not look like a ZIP is refused, naming ``postal_code``."""
    api_client.force_login(member)
    response = api_client.patch(PROFILE_URL, {"postal_code": postal_code}, format="json")
    assert response.status_code == 400
    assert "postal_code" in response.json()


def test_postal_code_accepts_zip_plus_four(
    api_client: APIClient, member: User, profile: MemberProfile
) -> None:
    """A ZIP+4 postal code is accepted."""
    api_client.force_login(member)
    response = api_client.patch(PROFILE_URL, {"postal_code": "94040-1234"}, format="json")
    assert response.status_code == 200


def test_dart_id_may_be_cleared(
    api_client: APIClient, member: User, profile: MemberProfile
) -> None:
    """Setting ``dart_id`` to null clears the profile's DART."""
    api_client.force_login(member)
    response = api_client.patch(PROFILE_URL, {"dart_id": None}, format="json")
    assert response.status_code == 200
    assert response.json()["dart"] is None


def test_dart_id_rejects_an_inactive_dart(
    api_client: APIClient, member: User, profile: MemberProfile
) -> None:
    """A retired DART cannot be set on the profile, naming ``dart_id``."""
    retired = DartFactory(name="Retired DART", is_active=False)
    api_client.force_login(member)
    response = api_client.patch(PROFILE_URL, {"dart_id": retired.id}, format="json")
    assert response.status_code == 400
    assert "dart_id" in response.json()


def test_dart_id_rejects_an_unknown_dart(
    api_client: APIClient, member: User, profile: MemberProfile
) -> None:
    """An id with no matching DART is refused."""
    api_client.force_login(member)
    response = api_client.patch(PROFILE_URL, {"dart_id": 999_999}, format="json")
    assert response.status_code == 400


# --------------------------------------------------------------------------
# Membership and payments
# --------------------------------------------------------------------------
def test_membership_reports_status_and_history(
    api_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    life_plan: MembershipPlan,
    today: date,
    days: Callable[[int], timedelta],
) -> None:
    """The membership endpoint reports the current status plus newest-first history."""
    MembershipFactory(
        user=member,
        plan=annual_plan,
        starts_on=today - days(400),
        ends_on=today - days(36),
        status="expired",
    )
    MembershipFactory(user=member, plan=annual_plan, starts_on=today - days(35))
    api_client.force_login(member)

    data = api_client.get(MEMBERSHIP_URL).json()

    assert data["status"] == "current"
    assert data["plan"] == "Annual"
    assert data["is_lifetime"] is False
    assert data["expires_on"] == (today - days(35) + timedelta(days=364)).isoformat()
    assert len(data["history"]) == 2
    assert set(data["history"][0]) == {"id", "plan", "starts_on", "ends_on", "status", "source"}
    # Newest term first (Membership.Meta ordering).
    assert data["history"][0]["starts_on"] > data["history"][1]["starts_on"]


def test_membership_for_a_member_who_never_joined(api_client: APIClient, member: User) -> None:
    """A member with no membership row reports the documented empty shape."""
    api_client.force_login(member)
    data = api_client.get(MEMBERSHIP_URL).json()
    assert data == {
        "status": "none",
        "expires_on": None,
        "plan": None,
        "is_lifetime": False,
        "history": [],
    }


def test_membership_reports_a_lifetime_term(
    api_client: APIClient, member: User, life_plan: MembershipPlan, today: date
) -> None:
    """A lifetime membership reports ``is_lifetime: true`` and a null expiration."""
    MembershipFactory(user=member, plan=life_plan, starts_on=today, ends_on=None)
    api_client.force_login(member)
    data = api_client.get(MEMBERSHIP_URL).json()
    assert data["is_lifetime"] is True
    assert data["expires_on"] is None


def test_payments_are_newest_first_and_scoped_to_the_caller(
    api_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    user_factory: type[UserFactory],
) -> None:
    """The payments list is newest first and never includes another member's rows."""
    stranger = user_factory(email="stranger@example.test")
    PaymentFactory(user=stranger, plan=annual_plan, provider_ref="theirs")
    older = PaymentFactory(user=member, plan=annual_plan, provider_ref="mine-1")
    newer = PaymentFactory(user=member, plan=annual_plan, provider_ref="mine-2")
    api_client.force_login(member)

    rows = api_client.get(PAYMENTS_URL).json()

    assert [row["id"] for row in rows] == [newer.id, older.id]
    assert set(rows[0]) == {
        "id",
        "plan",
        "amount_cents",
        "contribution_cents",
        "provider",
        "status",
        "completed_at",
    }
    assert rows[0]["plan"] == "Annual"


def test_payments_without_a_plan_report_a_null_plan(api_client: APIClient, member: User) -> None:
    """A donation payment with no plan reports ``plan: null``."""
    PaymentFactory(user=member, plan=None, provider_ref="donation-1")
    api_client.force_login(member)
    assert api_client.get(PAYMENTS_URL).json()[0]["plan"] is None


def test_payments_is_empty_for_a_new_member(api_client: APIClient, member: User) -> None:
    """A member with no payments gets an empty list."""
    api_client.force_login(member)
    assert api_client.get(PAYMENTS_URL).json() == []


def test_profile_reports_a_stale_medical_as_not_current(
    api_client: APIClient, member: User, profile_factory: type[MemberProfileFactory], today: date
) -> None:
    """A medical that expired yesterday reports ``medical_is_current: false``."""
    profile_factory(user=member, medical_type="third", medical_expiration=today - timedelta(days=1))
    api_client.force_login(member)
    assert api_client.get(PROFILE_URL).json()["medical_is_current"] is False


def test_attached_aircraft_summary_flags_expired_insurance(
    api_client: APIClient, member: User, profile: MemberProfile, today: date
) -> None:
    """An attached aircraft with lapsed insurance reports it as not current."""
    lapsed = AircraftFactory(n_number="N999ZZ", insurance_expiration=today - timedelta(days=2))
    profile.aircraft.add(lapsed)
    api_client.force_login(member)
    assert api_client.get(PROFILE_URL).json()["aircraft"][0]["insurance_is_current"] is False
