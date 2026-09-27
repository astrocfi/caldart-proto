"""The verification endpoints, who may call them, and what the reads show.

``PUT /leader/members/{user_id}/verification`` and
``PUT /leader/aircraft/{id}/verification`` are open to the four verifying roles and a
system administrator.  The status card, the search rows, the aircraft record, and the
profile each carry the verified state, and the search still costs a fixed number of
queries.  The contract is
``docs/developer/api-aircraft.rst`` and ``docs/developer/api-profile.rst``.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from django.utils import timezone
from pytest_django.fixtures import DjangoAssertNumQueries
from rest_framework import serializers
from rest_framework.test import APIClient

from apps.accounts.models import AccountKind, User
from apps.accounts.roles import (
    ACCOUNT_ADMIN,
    DART_LEADER,
    MEMBER,
    SYSTEM_ADMIN,
    USER_ADMIN,
    VERIFIER,
)
from apps.aircraft.models import Aircraft
from apps.darts.models import Dart
from apps.members.models import MedicalType, MemberProfile, MembershipPlan, PhotoIdType
from tests.conftest import role_matrix
from tests.factories import AircraftFactory, MemberProfileFactory, MembershipFactory, UserFactory

pytestmark = pytest.mark.django_db

SEARCH_URL = "/api/v1/leader/search"
PROFILE_URL = "/api/v1/me/profile"

#: A person's item slugs, in the order the screens list them.
PERSON_ITEMS = ["certificate", "medical", "photo_id"]

#: When the items of a verified fixture were stamped.
STAMPED_AT = datetime(2026, 1, 15, 17, 0, tzinfo=timezone.get_current_timezone())

#: The queries a leader search costs, however many rows it returns.
LEADER_SEARCH_QUERIES = 4

#: The queries one page of the register costs, however many rows are verified.
AIRCRAFT_LIST_QUERIES = 4


def member_verification_url(user: User) -> str:
    """``/leader/members/{user_id}/verification`` for ``user``."""
    return f"/api/v1/leader/members/{user.pk}/verification"


def aircraft_verification_url(aircraft: Aircraft) -> str:
    """``/leader/aircraft/{id}/verification`` for ``aircraft``."""
    return f"/api/v1/leader/aircraft/{aircraft.pk}/verification"


def status_url(user: User) -> str:
    """``/leader/members/{user_id}/status`` for ``user``."""
    return f"/api/v1/leader/members/{user.pk}/status"


def rendered(moment: datetime) -> str:
    """``moment`` as the API renders a timestamp."""
    return str(serializers.DateTimeField().to_representation(moment))


def stamps(by: User, *slugs: str) -> dict[str, object]:
    """The verification columns that mark each of ``slugs`` verified by ``by``."""
    columns: dict[str, object] = {}
    for slug in slugs:
        columns[f"{slug}_verified_at"] = STAMPED_AT
        columns[f"{slug}_verified_by"] = by
    return columns


@pytest.fixture
def stamper(db: None) -> User:
    """The account that verified the fixtures' items, named Dana Holt."""
    return UserFactory(email="stamper@example.test", first_name="Dana", last_name="Holt")


@pytest.fixture
def pilot(db: None, dart: Dart, annual_plan: MembershipPlan) -> User:
    """A current member with a current medical, nothing verified, and one airplane."""
    today = timezone.localdate()
    user = UserFactory(email="pilot@example.test", first_name="Ana", last_name="Bracco")
    profile = MemberProfileFactory(
        user=user,
        dart=dart,
        certificate_number="3181234",
        medical_type=MedicalType.THIRD,
        medical_expiration=today + timedelta(days=120),
        photo_id_type=PhotoIdType.PASSPORT,
    )
    profile.aircraft.add(AircraftFactory(n_number="N172SP"))
    MembershipFactory(
        user=user,
        plan=annual_plan,
        starts_on=today - timedelta(days=30),
        ends_on=today + timedelta(days=300),
    )
    return user


@pytest.fixture
def leader_client(api_client: APIClient, dart_leader: User) -> APIClient:
    """A client signed in as the ``dart_leader`` fixture."""
    api_client.force_login(dart_leader)
    return api_client


# --------------------------------------------------------------------------
# Who may verify
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("slug", "allowed"),
    role_matrix(VERIFIER, DART_LEADER, USER_ADMIN, ACCOUNT_ADMIN, SYSTEM_ADMIN),
)
def test_member_verification_role_matrix(
    api_client: APIClient,
    all_role_users: dict[str, User],
    pilot: User,
    slug: str,
    allowed: bool,
) -> None:
    """Only a verifying role or a system administrator may verify a member."""
    api_client.force_login(all_role_users[slug])
    response = api_client.put(member_verification_url(pilot), {"verified": []}, format="json")
    assert response.status_code == (200 if allowed else 403)


@pytest.mark.parametrize(
    ("slug", "allowed"),
    role_matrix(VERIFIER, DART_LEADER, USER_ADMIN, ACCOUNT_ADMIN, SYSTEM_ADMIN),
)
def test_aircraft_verification_role_matrix(
    api_client: APIClient,
    all_role_users: dict[str, User],
    aircraft: Aircraft,
    slug: str,
    allowed: bool,
) -> None:
    """Only a verifying role or a system administrator may verify an aircraft."""
    api_client.force_login(all_role_users[slug])
    response = api_client.put(
        aircraft_verification_url(aircraft), {"verified": True}, format="json"
    )
    assert response.status_code == (200 if allowed else 403)


def test_member_verification_requires_authentication(api_client: APIClient, pilot: User) -> None:
    """An anonymous caller is refused."""
    response = api_client.put(member_verification_url(pilot), {"verified": []}, format="json")
    assert response.status_code == 401


@pytest.mark.parametrize("kind", ["unknown", "donor", "deactivated"])
def test_member_verification_answers_404_for_someone_the_check_never_shows(
    leader_client: APIClient, kind: str
) -> None:
    """An unknown id, a donor, and a deactivated account are all 404."""
    if kind == "unknown":
        url = "/api/v1/leader/members/999999/verification"
    else:
        target = UserFactory(
            kind=AccountKind.DONOR if kind == "donor" else AccountKind.MEMBER,
            is_active=kind != "deactivated",
        )
        url = member_verification_url(target)
    assert leader_client.put(url, {"verified": []}, format="json").status_code == 404


def test_aircraft_verification_answers_404_for_an_unknown_aircraft(
    leader_client: APIClient,
) -> None:
    """No aircraft has that id."""
    response = leader_client.put(
        "/api/v1/leader/aircraft/999999/verification", {"verified": True}, format="json"
    )
    assert response.status_code == 404


def test_a_verifier_may_verify_their_own_record(
    api_client: APIClient, verifier: User, today: date
) -> None:
    """Self-verification is allowed: nothing checks the actor against the target."""
    MemberProfileFactory(user=verifier)
    api_client.force_login(verifier)
    response = api_client.put(
        member_verification_url(verifier), {"verified": PERSON_ITEMS}, format="json"
    )
    assert response.json()["go_no_go"]["verified"] is True


# --------------------------------------------------------------------------
# The member verification body
# --------------------------------------------------------------------------
def test_verifying_all_three_items_turns_the_card_verified(
    leader_client: APIClient, pilot: User
) -> None:
    """The response is the status card, reading verified."""
    response = leader_client.put(
        member_verification_url(pilot), {"verified": PERSON_ITEMS}, format="json"
    )
    assert response.json()["go_no_go"]["verified"] is True


def test_the_card_names_who_verified_and_when(
    leader_client: APIClient, pilot: User, dart_leader: User, today: date
) -> None:
    """Each item's verification carries the verifier's name and the time."""
    response = leader_client.put(
        member_verification_url(pilot), {"verified": ["medical"]}, format="json"
    )
    assert response.json()["medical"]["verification"] == {
        "verified": True,
        "verified_by": dart_leader.display_name,
        "verified_at": rendered(timezone.now()),
    }


def test_a_given_field_is_written_and_an_omitted_one_left_alone(
    leader_client: APIClient, pilot: User
) -> None:
    """``photo_id_type`` is written; the certificate, not sent, keeps its number."""
    response = leader_client.put(
        member_verification_url(pilot),
        {"photo_id_type": "drivers_license", "verified": []},
        format="json",
    )
    body = response.json()
    assert (body["photo_id"]["type"], body["certificate"]["number"]) == (
        "drivers_license",
        "3181234",
    )


def test_an_unknown_item_is_refused(leader_client: APIClient, pilot: User) -> None:
    """A slug outside the catalog is refused under ``verified``."""
    response = leader_client.put(
        member_verification_url(pilot), {"verified": ["medical", "hours"]}, format="json"
    )
    assert (response.status_code, response.json()) == (
        400,
        {"verified": ["Unknown item 'hours'."]},
    )


def test_verified_is_required(leader_client: APIClient, pilot: User) -> None:
    """A body without ``verified`` is refused under that field."""
    response = leader_client.put(member_verification_url(pilot), {}, format="json")
    assert (response.status_code, list(response.json())) == (400, ["verified"])


def test_a_certificate_needs_a_number_on_the_merged_record(
    leader_client: APIClient, pilot: User
) -> None:
    """Blanking the number of a stored certificate is refused as the profile form does."""
    response = leader_client.put(
        member_verification_url(pilot),
        {"certificate_number": "", "verified": []},
        format="json",
    )
    assert response.json() == {"certificate_number": ["Give your pilot certificate number."]}


def test_a_medical_needs_an_expiration_on_the_merged_record(
    leader_client: APIClient, pilot: User
) -> None:
    """Clearing the expiration of a stored medical is refused as the profile form does."""
    response = leader_client.put(
        member_verification_url(pilot),
        {"medical_expiration": None, "verified": []},
        format="json",
    )
    assert response.json() == {
        "medical_expiration": ["Give the expiration date of your medical certificate."]
    }


def test_a_refused_body_writes_nothing(leader_client: APIClient, pilot: User) -> None:
    """A refusal leaves every item unverified and the fields as they were."""
    leader_client.put(
        member_verification_url(pilot),
        {"certificate_number": "", "verified": PERSON_ITEMS},
        format="json",
    )
    assert MemberProfile.objects.get(user=pilot).certificate_verified_at is None


# --------------------------------------------------------------------------
# The aircraft verification body
# --------------------------------------------------------------------------
def test_verifying_the_insurance_answers_the_aircraft_record(
    leader_client: APIClient, aircraft: Aircraft, dart_leader: User, today: date
) -> None:
    """The response is the detail record, carrying the verification."""
    response = leader_client.put(
        aircraft_verification_url(aircraft), {"verified": True}, format="json"
    )
    assert response.json()["insurance_verification"] == {
        "verified": True,
        "verified_by": dart_leader.display_name,
        "verified_at": rendered(timezone.now()),
    }


def test_the_insurance_fields_are_written(leader_client: APIClient, aircraft: Aircraft) -> None:
    """A given insurance field is written; an omitted one is left alone."""
    policy = aircraft.insurance_policy_number
    response = leader_client.put(
        aircraft_verification_url(aircraft),
        {"insurance_carrier": "USAIG", "verified": True},
        format="json",
    )
    body = response.json()
    assert (body["insurance_carrier"], body["insurance_policy_number"]) == ("USAIG", policy)


def test_a_negative_insurance_amount_is_refused(
    leader_client: APIClient, aircraft: Aircraft
) -> None:
    """The money fields are validated as the register validates them."""
    response = leader_client.put(
        aircraft_verification_url(aircraft),
        {"insurance_hull_cents": -1, "verified": True},
        format="json",
    )
    assert response.json() == {"insurance_hull_cents": ["Enter an amount of $0 or more."]}


def test_the_insurance_verified_flag_is_required(
    leader_client: APIClient, aircraft: Aircraft
) -> None:
    """A body without ``verified`` is refused under that field."""
    response = leader_client.put(aircraft_verification_url(aircraft), {}, format="json")
    assert (response.status_code, list(response.json())) == (400, ["verified"])


def test_the_insurance_body_writes_no_other_field(
    leader_client: APIClient, aircraft: Aircraft
) -> None:
    """A register field outside the insurance, such as the make, is ignored."""
    leader_client.put(
        aircraft_verification_url(aircraft),
        {"make": "Piper", "verified": True},
        format="json",
    )
    aircraft.refresh_from_db()
    assert aircraft.make != "Piper"


# --------------------------------------------------------------------------
# The check screens open to every verifying role
# --------------------------------------------------------------------------
@pytest.mark.parametrize("role", [VERIFIER, USER_ADMIN])
def test_the_register_record_lists_pilots_to_every_verifying_role(
    api_client: APIClient, all_role_users: dict[str, User], pilot: User, role: str
) -> None:
    """A verifier and a user administrator see who flies the airplane."""
    aircraft = Aircraft.objects.get(n_number="N172SP")
    api_client.force_login(all_role_users[role])
    response = api_client.get(f"/api/v1/aircraft/{aircraft.pk}")
    assert [row["user_id"] for row in response.json()["pilots"]] == [pilot.pk]


# --------------------------------------------------------------------------
# The status card and the search rows
# --------------------------------------------------------------------------
def test_the_card_reads_unverified_for_a_fresh_profile(
    leader_client: APIClient, pilot: User
) -> None:
    """Nothing verified: every item reads unverified and the verdict flag is false."""
    body = leader_client.get(status_url(pilot)).json()
    assert body["go_no_go"] == {"membership": True, "medical": True, "verified": False}


def test_the_card_carries_the_photo_id(
    leader_client: APIClient, pilot: User, stamper: User
) -> None:
    """``photo_id`` carries the type and its verification."""
    MemberProfile.objects.filter(user=pilot).update(**stamps(stamper, "photo_id"))
    body = leader_client.get(status_url(pilot)).json()
    assert body["photo_id"] == {
        "type": "passport",
        "verification": {
            "verified": True,
            "verified_by": "Dana Holt",
            "verified_at": rendered(STAMPED_AT),
        },
    }


def test_the_card_carries_the_certificate_verification(
    leader_client: APIClient, pilot: User
) -> None:
    """An unverified certificate reads ``verified`` false with no name or date."""
    body = leader_client.get(status_url(pilot)).json()
    assert body["certificate"]["verification"] == {
        "verified": False,
        "verified_by": None,
        "verified_at": None,
    }


def test_the_card_is_verified_only_when_all_three_items_are(
    leader_client: APIClient, pilot: User, stamper: User
) -> None:
    """Two of three items verified still reads ``verified`` false."""
    MemberProfile.objects.filter(user=pilot).update(**stamps(stamper, "certificate", "medical"))
    assert leader_client.get(status_url(pilot)).json()["go_no_go"]["verified"] is False


@pytest.mark.parametrize(("roles", "expected"), [([MEMBER], False), ([MEMBER, VERIFIER], True)])
def test_the_card_says_whether_the_member_is_a_verifier(
    leader_client: APIClient, pilot: User, roles: list[str], expected: bool
) -> None:
    """``is_verifier`` follows the verifier role."""
    pilot.set_roles(roles)
    assert leader_client.get(status_url(pilot)).json()["is_verifier"] is expected


def test_the_cards_aircraft_rows_carry_insurance_verified(
    leader_client: APIClient, pilot: User, stamper: User
) -> None:
    """Each airplane on the card says whether its insurance is verified."""
    Aircraft.objects.filter(n_number="N172SP").update(**stamps(stamper, "insurance"))
    rows = leader_client.get(status_url(pilot)).json()["aircraft"]
    assert [row["insurance_verified"] for row in rows] == [True]


def test_a_card_for_an_account_with_no_profile_reads_unverified(
    leader_client: APIClient,
) -> None:
    """An account with no profile has nothing verified and a *Not provided* photo ID."""
    user = UserFactory()
    body = leader_client.get(status_url(user)).json()
    assert (body["photo_id"]["type"], body["go_no_go"]["verified"]) == ("not_provided", False)


def test_a_search_row_reads_verified_when_all_three_items_are(
    leader_client: APIClient, pilot: User, stamper: User
) -> None:
    """The row's ``go_no_go.verified`` follows the three items."""
    MemberProfile.objects.filter(user=pilot).update(**stamps(stamper, *PERSON_ITEMS))
    rows = leader_client.get(SEARCH_URL, {"q": "Bracco"}).json()
    assert [row["go_no_go"]["verified"] for row in rows] == [True]


@pytest.mark.parametrize("size", [3, 20])
def test_the_verified_flag_costs_the_search_no_query(
    leader_client: APIClient,
    stamper: User,
    django_assert_num_queries: DjangoAssertNumQueries,
    size: int,
) -> None:
    """Twenty verified matches cost the same queries as three."""
    for index in range(size):
        user = UserFactory(email=f"row{index}@example.test", last_name="Querycount")
        MemberProfileFactory(user=user, **stamps(stamper, *PERSON_ITEMS))
    with django_assert_num_queries(LEADER_SEARCH_QUERIES):
        rows = leader_client.get(SEARCH_URL, {"q": "Querycount"}).json()
    assert [row["go_no_go"]["verified"] for row in rows] == [True] * size


# --------------------------------------------------------------------------
# The register
# --------------------------------------------------------------------------
def test_the_register_carries_the_insurance_verification(
    api_client: APIClient, member: User, stamper: User
) -> None:
    """``GET /aircraft/{id}`` carries ``insurance_verification`` to any member."""
    aircraft = AircraftFactory(**stamps(stamper, "insurance"))
    api_client.force_login(member)
    body = api_client.get(f"/api/v1/aircraft/{aircraft.pk}").json()
    assert body["insurance_verification"] == {
        "verified": True,
        "verified_by": "Dana Holt",
        "verified_at": rendered(STAMPED_AT),
    }


@pytest.mark.parametrize("size", [3, 20])
def test_the_verifier_names_cost_the_register_no_query(
    api_client: APIClient,
    member: User,
    stamper: User,
    django_assert_num_queries: DjangoAssertNumQueries,
    size: int,
) -> None:
    """A page of verified aircraft costs the same queries at three rows and twenty."""
    for _ in range(size):
        AircraftFactory(**stamps(stamper, "insurance"))
    api_client.force_login(member)
    with django_assert_num_queries(AIRCRAFT_LIST_QUERIES):
        body = api_client.get("/api/v1/aircraft").json()
    assert [row["insurance_verification"]["verified"] for row in body["results"]] == [True] * size


def test_the_profile_aircraft_rows_carry_insurance_verified(
    api_client: APIClient, pilot: User
) -> None:
    """A member's own aircraft rows say whether the insurance is verified."""
    api_client.force_login(pilot)
    rows = api_client.get(PROFILE_URL).json()["aircraft"]
    assert [row["insurance_verified"] for row in rows] == [False]


# --------------------------------------------------------------------------
# The profile
# --------------------------------------------------------------------------
def test_the_profile_carries_the_three_verifications(
    api_client: APIClient, pilot: User, stamper: User
) -> None:
    """``verification`` names each item's state; only the medical is verified here."""
    MemberProfile.objects.filter(user=pilot).update(**stamps(stamper, "medical"))
    api_client.force_login(pilot)
    verification = api_client.get(PROFILE_URL).json()["verification"]
    assert {slug: state["verified"] for slug, state in verification.items()} == {
        "certificate": False,
        "medical": True,
        "photo_id": False,
    }


def test_a_member_writes_their_photo_id_type(api_client: APIClient, pilot: User) -> None:
    """``photo_id_type`` is writable on ``PATCH /me/profile``."""
    api_client.force_login(pilot)
    response = api_client.patch(PROFILE_URL, {"photo_id_type": "military_id"}, format="json")
    assert response.json()["photo_id_type"] == "military_id"


def test_a_member_cannot_write_their_own_verification(api_client: APIClient, pilot: User) -> None:
    """``verification`` is read-only: sending it verifies nothing."""
    api_client.force_login(pilot)
    api_client.patch(
        PROFILE_URL,
        {"verification": {"medical": {"verified": True}}},
        format="json",
    )
    assert MemberProfile.objects.get(user=pilot).medical_verified_at is None


def test_the_member_record_carries_the_profile_verification(
    account_admin_client: APIClient, pilot: User, stamper: User
) -> None:
    """``GET /admin/members/{id}`` carries the same ``verification`` in the profile."""
    MemberProfile.objects.filter(user=pilot).update(**stamps(stamper, "certificate"))
    body = account_admin_client.get(f"/api/v1/admin/members/{pilot.pk}").json()
    assert body["profile"]["verification"]["certificate"]["verified_by"] == "Dana Holt"


def test_the_roles_list_names_the_verifier_second(api_client: APIClient, member: User) -> None:
    """``GET /roles`` lists the verifier between member and DART leader."""
    api_client.force_login(member)
    slugs = [row["slug"] for row in api_client.get("/api/v1/roles").json()]
    assert slugs[:3] == [MEMBER, VERIFIER, DART_LEADER]
