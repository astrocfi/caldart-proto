"""The aircraft coverage policy: its endpoint, the rule, and where the rule is shown.

``docs/developer/api-aircraft.rst`` describes ``/aircraft/coverage-policy`` and the
``coverage`` every aircraft carries; the user guide's aircraft register, aircraft check,
and My aircraft pages describe what each reader sees.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.aircraft.coverage import CATEGORY_NOT_RECORDED, current_rule
from apps.aircraft.models import (
    DEFAULT_MIN_LIABILITY_PER_OCCURRENCE_CENTS,
    DEFAULT_MIN_LIABILITY_PER_PERSON_CENTS,
    Aircraft,
    AircraftCoveragePolicy,
)
from apps.aircraft.seed import COVERAGE_NOTE, seed_coverage_policy
from tests.conftest import role_matrix
from tests.factories import (
    AircraftFactory,
    MemberProfileFactory,
    MembershipFactory,
    make_site_settings,
)

# Aircraft are for current members, so the `member` these tests act as holds a term.
pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("member_is_current")]

POLICY_URL = "/api/v1/aircraft/coverage-policy"
LEADER_AIRCRAFT_URL = "/api/v1/leader/aircraft"

#: What the check says of a helicopter while helicopters are excluded.
HELICOPTERS_EXCLUDED = "Not covered: helicopters are excluded by CalDART's policy"


def _exclude(
    *, categories: list[str] | None = None, airworthiness: list[str] | None = None
) -> None:
    """Store a policy excluding ``categories`` and ``airworthiness``."""
    policy = AircraftCoveragePolicy.load()
    policy.excluded_categories = categories or []
    policy.excluded_airworthiness = airworthiness or []
    policy.save()


def _body(**overrides: Any) -> dict[str, Any]:
    """A complete ``PUT`` body excluding helicopters, with ``overrides`` merged in."""
    body: dict[str, Any] = {
        "excluded_categories": ["helicopter"],
        "excluded_airworthiness": [],
        "min_liability_per_occurrence_cents": DEFAULT_MIN_LIABILITY_PER_OCCURRENCE_CENTS,
        "min_liability_per_person_cents": DEFAULT_MIN_LIABILITY_PER_PERSON_CENTS,
        "note": "Helicopters are not covered.",
    }
    body.update(overrides)
    return body


@pytest.fixture
def admin_client(api_client: APIClient, account_admin: User) -> APIClient:
    """A client signed in as an account administrator."""
    api_client.force_login(account_admin)
    return api_client


@pytest.fixture
def leader_client(api_client: APIClient, dart_leader: User) -> APIClient:
    """A client signed in as a DART leader."""
    api_client.force_login(dart_leader)
    return api_client


# -- the endpoint -------------------------------------------------------------


def test_reading_the_policy_needs_a_signed_in_caller(api_client: APIClient) -> None:
    """An anonymous caller is answered 401."""
    assert api_client.get(POLICY_URL).status_code == 401


def test_a_policy_never_written_does_not_exclude_anything(
    api_client: APIClient, member: User
) -> None:
    """Before an administrator writes one, the policy excludes nothing but low liability.

    The minimums start at $1,000,000 per occurrence and $100,000 per person.
    """
    api_client.force_login(member)
    assert api_client.get(POLICY_URL).json() == {
        "excluded_categories": [],
        "excluded_airworthiness": [],
        "min_liability_per_occurrence_cents": 100_000_000,
        "min_liability_per_person_cents": 10_000_000,
        "note": "",
    }


@pytest.mark.parametrize("role", [slug for slug, _ in role_matrix()])
def test_every_signed_in_role_reads_the_policy(
    api_client: APIClient, all_role_users: dict[str, User], role: str
) -> None:
    """Every role, as a current member, account administrator included, gets a 200."""
    MembershipFactory(user=all_role_users[role])
    api_client.force_login(all_role_users[role])
    assert api_client.get(POLICY_URL).status_code == 200


@pytest.mark.parametrize(("role", "allowed"), role_matrix("system_admin"))
def test_only_a_system_administrator_writes_the_policy(
    api_client: APIClient, all_role_users: dict[str, User], role: str, allowed: bool
) -> None:
    """Only a system administrator writes the policy; every other role is a 403."""
    api_client.force_login(all_role_users[role])
    response = api_client.put(POLICY_URL, _body(), format="json")
    assert response.status_code == (200 if allowed else 403)


def test_a_written_policy_is_stored_and_answered(system_admin_client: APIClient) -> None:
    """The ``PUT`` answers the stored policy, with the lists in choice order."""
    response = system_admin_client.put(
        POLICY_URL,
        _body(
            excluded_categories=["gyroplane", "helicopter"],
            excluded_airworthiness=["light_sport", "experimental", "experimental"],
            min_liability_per_occurrence_cents=200_000_000,
            min_liability_per_person_cents=0,
            note="  Rotorcraft and homebuilts are not covered.  ",
        ),
        format="json",
    )
    assert response.json() == {
        "excluded_categories": ["helicopter", "gyroplane"],
        "excluded_airworthiness": ["experimental", "light_sport"],
        "min_liability_per_occurrence_cents": 200_000_000,
        "min_liability_per_person_cents": 0,
        "note": "Rotorcraft and homebuilts are not covered.",
    }


def test_a_written_policy_records_who_wrote_it(
    system_admin_client: APIClient, system_admin: User
) -> None:
    """The row keeps the account that last wrote it."""
    system_admin_client.put(POLICY_URL, _body(), format="json")
    assert AircraftCoveragePolicy.load().updated_by == system_admin


def test_a_django_superuser_writes_the_policy(api_client: APIClient, superuser: User) -> None:
    """A Django superuser passes the system-administrator check."""
    api_client.force_login(superuser)
    assert api_client.put(POLICY_URL, _body(), format="json").status_code == 200


@pytest.mark.parametrize("field", ["excluded_categories", "excluded_airworthiness"])
def test_an_unknown_value_in_a_list_is_refused(system_admin_client: APIClient, field: str) -> None:
    """A value outside the choice list is a 400 naming the list."""
    response = system_admin_client.put(POLICY_URL, _body(**{field: ["spaceship"]}), format="json")
    assert (response.status_code, list(response.json())) == (400, [field])


@pytest.mark.parametrize(
    "field", ["min_liability_per_occurrence_cents", "min_liability_per_person_cents"]
)
def test_a_negative_minimum_is_refused(system_admin_client: APIClient, field: str) -> None:
    """A minimum is $0 or more: a negative one is a 400 naming it."""
    response = system_admin_client.put(POLICY_URL, _body(**{field: -1}), format="json")
    assert response.json() == {field: ["Enter an amount of $0 or more."]}


def test_a_note_longer_than_the_limit_is_refused(system_admin_client: APIClient) -> None:
    """The note is a short statement: more than 1,000 characters is a 400."""
    response = system_admin_client.put(POLICY_URL, _body(note="x" * 1001), format="json")
    assert (response.status_code, list(response.json())) == (400, ["note"])


def test_there_is_only_ever_one_policy(system_admin_client: APIClient) -> None:
    """Writing twice updates the one row rather than adding a second."""
    system_admin_client.put(POLICY_URL, _body(), format="json")
    system_admin_client.put(POLICY_URL, _body(note="Changed."), format="json")
    assert AircraftCoveragePolicy.objects.count() == 1


# -- the rule -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("policy", "category", "airworthiness", "expected"),
    [
        ({"categories": ["helicopter"]}, "helicopter", "standard", (True, HELICOPTERS_EXCLUDED)),
        ({"categories": ["helicopter"]}, "airplane", "standard", (False, "")),
        (
            {"airworthiness": ["experimental"]},
            "airplane",
            "experimental",
            (True, "Not covered: experimental aircraft are excluded by CalDART's policy"),
        ),
        (
            {"categories": ["helicopter"], "airworthiness": ["experimental"]},
            "helicopter",
            "experimental",
            (True, HELICOPTERS_EXCLUDED),
        ),
        ({"categories": ["helicopter"]}, "", "", (False, CATEGORY_NOT_RECORDED)),
        (
            {"airworthiness": ["light_sport"]},
            "",
            "light_sport",
            (True, "Not covered: light-sport aircraft are excluded by CalDART's policy"),
        ),
        ({"categories": ["helicopter"]}, "", "standard", (False, CATEGORY_NOT_RECORDED)),
        ({}, "glider", "", (False, "")),
    ],
    ids=[
        "category-excluded",
        "category-covered",
        "airworthiness-excluded",
        "both-name-the-category",
        "nothing-recorded",
        "no-category-but-airworthiness-excluded",
        "no-category",
        "empty-policy",
    ],
)
def test_the_rule_judges_an_aircraft(
    policy: dict[str, list[str]],
    category: str,
    airworthiness: str,
    expected: tuple[bool, str],
) -> None:
    """Either listed value excludes; a missing category is said rather than judged."""
    _exclude(**policy)
    found = current_rule().judge(Aircraft(category=category, airworthiness=airworthiness))
    assert (found.excluded, found.reason) == expected


def test_the_reason_names_the_organization_from_the_site_settings() -> None:
    """The organization in the reason is the one the site settings name."""
    make_site_settings(org_name="Example DART Network")
    _exclude(categories=["balloon"])
    reason = current_rule().judge(Aircraft(category="balloon")).reason
    assert reason == "Not covered: balloons are excluded by Example DART Network's policy"


# -- the liability minimums ---------------------------------------------------


def _insured(per_occurrence: int, per_person: int, **fields: Any) -> Aircraft:
    """An unsaved airplane with a policy on file carrying these limits, in cents."""
    return Aircraft(
        category="airplane",
        insurance_liability_per_occurrence_cents=per_occurrence,
        insurance_liability_per_person_cents=per_person,
        insurance_expiration=timezone.localdate() + timedelta(days=90),
        **fields,
    )


@pytest.mark.parametrize(
    ("per_occurrence", "per_person", "expected"),
    [
        (100_000_000, 10_000_000, (False, "")),
        (200_000_000, 20_000_000, (False, "")),
        (
            50_000_000,
            10_000_000,
            (
                True,
                "Not covered: liability is under CalDART's minimum of $1,000,000 per occurrence",
            ),
        ),
        (
            100_000_000,
            5_000_000,
            (True, "Not covered: liability is under CalDART's minimum of $100,000 per person"),
        ),
        (
            0,
            0,
            (
                True,
                "Not covered: liability is under CalDART's minimum of $1,000,000 per "
                "occurrence and $100,000 per person",
            ),
        ),
    ],
    ids=["exactly-the-minimums", "above", "occurrence-short", "person-short", "both-short"],
)
def test_a_recorded_policy_under_a_minimum_is_not_covered(
    per_occurrence: int, per_person: int, expected: tuple[bool, str]
) -> None:
    """The default minimums exclude a policy carrying less, naming each minimum missed."""
    found = current_rule().judge(_insured(per_occurrence, per_person))
    assert (found.excluded, found.reason) == expected


def test_an_aircraft_without_a_policy_on_file_is_not_judged_on_its_liability() -> None:
    """Without an insurance expiry there isn't a policy to fall short of the minimums."""
    found = current_rule().judge(Aircraft(category="airplane"))
    assert (found.excluded, found.reason) == (False, "")


def test_a_minimum_of_zero_sets_no_minimum() -> None:
    """A policy whose minimums are both $0 accepts any liability."""
    policy = AircraftCoveragePolicy.load()
    policy.min_liability_per_occurrence_cents = 0
    policy.min_liability_per_person_cents = 0
    policy.save()
    assert current_rule().judge(_insured(0, 0)).excluded is False


def test_a_changed_minimum_applies_to_every_aircraft_at_once(admin_client: APIClient) -> None:
    """Raising a minimum excludes an aircraft already on the register at once."""
    aircraft = AircraftFactory(
        insurance_liability_per_occurrence_cents=100_000_000,
        insurance_expiration=timezone.localdate() + timedelta(days=90),
    )
    policy = AircraftCoveragePolicy.load()
    policy.min_liability_per_occurrence_cents = 200_000_000
    policy.save()
    body = admin_client.get(f"/api/v1/aircraft/{aircraft.pk}").json()
    assert body["coverage"] == {
        "excluded": True,
        "reason": "Not covered: liability is under CalDART's minimum of $2,000,000 per occurrence",
    }


def test_an_exclusion_by_category_is_named_before_the_liability() -> None:
    """An excluded category is the reason, even when the liability falls short too."""
    _exclude(categories=["helicopter"])
    aircraft = _insured(0, 0)
    aircraft.category = "helicopter"
    assert current_rule().judge(aircraft).reason == HELICOPTERS_EXCLUDED


def _verification_url(aircraft: Aircraft) -> str:
    """The aircraft check's verification endpoint for ``aircraft``."""
    return f"/api/v1/leader/aircraft/{aircraft.pk}/verification"


def test_insurance_under_a_minimum_cannot_be_verified(leader_client: APIClient) -> None:
    """Verifying a policy under the per-person minimum is refused under that field."""
    aircraft = AircraftFactory(
        insurance_liability_per_person_cents=5_000_000,
        insurance_expiration=timezone.localdate() + timedelta(days=90),
    )
    response = leader_client.put(_verification_url(aircraft), {"verified": True}, format="json")
    assert (response.status_code, response.json()) == (
        400,
        {
            "insurance_liability_per_person_cents": [
                "Under CalDART's minimum of $100,000 per person."
            ]
        },
    )


def test_the_refusal_judges_the_amounts_as_they_would_be_saved(leader_client: APIClient) -> None:
    """Correcting a short amount in the same save verifies the insurance."""
    aircraft = AircraftFactory(
        insurance_liability_per_occurrence_cents=50_000_000,
        insurance_expiration=timezone.localdate() + timedelta(days=90),
    )
    response = leader_client.put(
        _verification_url(aircraft),
        {"insurance_liability_per_occurrence_cents": 100_000_000, "verified": True},
        format="json",
    )
    assert response.json()["insurance_verification"]["verified"] is True


def test_insurance_under_a_minimum_is_saved_unverified(leader_client: APIClient) -> None:
    """A save that doesn't verify records a short amount as it is."""
    aircraft = AircraftFactory(insurance_expiration=timezone.localdate() + timedelta(days=90))
    response = leader_client.put(
        _verification_url(aircraft),
        {"insurance_liability_per_occurrence_cents": 50_000_000, "verified": False},
        format="json",
    )
    assert response.json()["insurance_liability_per_occurrence_cents"] == 50_000_000


# -- where it is shown --------------------------------------------------------


def test_the_register_record_carries_its_coverage(admin_client: APIClient) -> None:
    """``GET /aircraft/{id}`` answers whether the policy excludes it, and why."""
    _exclude(categories=["helicopter"])
    aircraft = AircraftFactory(category="helicopter")
    body = admin_client.get(f"/api/v1/aircraft/{aircraft.pk}").json()
    assert body["coverage"] == {"excluded": True, "reason": HELICOPTERS_EXCLUDED}


def test_the_aircraft_check_shows_an_excluded_aircraft(leader_client: APIClient) -> None:
    """The leader's aircraft check carries the exclusion and its reason."""
    _exclude(categories=["helicopter"])
    AircraftFactory(n_number="N781SH", category="helicopter")
    body = leader_client.get(LEADER_AIRCRAFT_URL, {"n_number": "N781SH"}).json()
    assert body["coverage"] == {"excluded": True, "reason": HELICOPTERS_EXCLUDED}


def test_the_aircraft_check_says_when_no_category_is_recorded(leader_client: APIClient) -> None:
    """An aircraft without a category is not excluded, and the check says so."""
    _exclude(categories=["helicopter"])
    AircraftFactory(n_number="N55NC")
    body = leader_client.get(LEADER_AIRCRAFT_URL, {"n_number": "N55NC"}).json()
    assert body["coverage"] == {"excluded": False, "reason": CATEGORY_NOT_RECORDED}


def test_the_member_check_reads_the_rule_for_the_members_aircraft(
    leader_client: APIClient,
) -> None:
    """Each aircraft on the member's status card carries its coverage."""
    _exclude(categories=["helicopter"])
    pilot = MemberProfileFactory()
    pilot.aircraft.set(
        [AircraftFactory(n_number="N1HE", category="helicopter"), AircraftFactory(n_number="N2AP")]
    )
    body = leader_client.get(f"/api/v1/leader/members/{pilot.user_id}/status").json()
    assert [(row["n_number"], row["coverage"]["excluded"]) for row in body["aircraft"]] == [
        ("N1HE", True),
        ("N2AP", False),
    ]


def test_my_aircraft_carries_the_coverage(api_client: APIClient, member: User) -> None:
    """The member's own aircraft list marks an excluded aircraft."""
    _exclude(airworthiness=["experimental"])
    api_client.force_login(member)
    aircraft = AircraftFactory(category="airplane", airworthiness="experimental")
    response = api_client.post(
        "/api/v1/me/profile/aircraft", {"aircraft_id": aircraft.pk}, format="json"
    )
    assert response.json()["aircraft"][0]["coverage"]["excluded"] is True


def _register_queries(client: APIClient) -> int:
    """How many queries one ``GET /aircraft`` page costs ``client``."""
    with CaptureQueriesContext(connection) as captured:
        client.get("/api/v1/aircraft")
    return len(captured)


def test_the_register_reads_the_policy_once_per_page(admin_client: APIClient) -> None:
    """Judging every row of a page doesn't cost a query per row."""
    _exclude(categories=["helicopter"])
    AircraftFactory(n_number="N1HE", category="helicopter")
    one_row = _register_queries(admin_client)
    for number in range(2, 6):
        AircraftFactory(n_number=f"N{number}HE", category="helicopter")
    assert _register_queries(admin_client) == one_row


# -- the seed -----------------------------------------------------------------


def test_the_seed_excludes_helicopters_with_a_note() -> None:
    """The seeded policy excludes helicopters alone and publishes the sample note."""
    seed_coverage_policy()
    policy = AircraftCoveragePolicy.load()
    assert (policy.excluded_categories, policy.excluded_airworthiness, policy.note) == (
        ["helicopter"],
        [],
        COVERAGE_NOTE,
    )
