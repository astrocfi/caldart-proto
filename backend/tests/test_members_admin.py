"""Account-administrator member management.

Covers the role matrix on every endpoint, each list filter against a
deliberately mixed data set, ordering, member creation with and without a
password, nested profile updates, the delete guard rails, and the arithmetic
of a manually granted term.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any, cast

import pytest
from django.core import mail
from django.utils import timezone
from pytest_django.fixtures import DjangoAssertNumQueries, DjangoCaptureOnCommitCallbacks
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import (
    ACCOUNT_ADMIN,
    DART_LEADER,
    MEMBER,
    SYSTEM_ADMIN,
    USER_ADMIN,
    WEBSITE_ADMIN,
)
from apps.members.models import (
    Dart,
    MedicalType,
    MemberProfile,
    Membership,
    MembershipPlan,
    MembershipSource,
    MembershipStatusChoices,
    PilotCertificateType,
)
from apps.payments.models import Payment
from tests.factories import (
    AircraftFactory,
    DartFactory,
    MemberProfileFactory,
    MembershipFactory,
    PaymentFactory,
    UserFactory,
)

if TYPE_CHECKING:
    # rest_framework.test.APIClient.get() is typed to return this class, but it
    # exists only in the stub: rest_framework monkey-patches Django's test response
    # at runtime rather than defining a real subclass.
    from rest_framework.response import _MonkeyPatchedResponse as ApiResponse

pytestmark = pytest.mark.django_db

ONE_DAY = timedelta(days=1)
LIST_URL = "/api/v1/admin/members"
CSV_URL = "/api/v1/admin/members/export.csv"
PDF_URL = "/api/v1/admin/members/export.pdf"

#: Roles that may use the members-admin API at all.
ALLOWED_ROLES = {ACCOUNT_ADMIN, SYSTEM_ADMIN}
DENIED_ROLES = [MEMBER, DART_LEADER, USER_ADMIN, WEBSITE_ADMIN]


def detail_url(user: User) -> str:
    """``/admin/members/{id}``, which reads, edits and deletes ``user``'s record."""
    return f"{LIST_URL}/{user.pk}"


def grant_url(user: User) -> str:
    """``/admin/members/{id}/memberships``, which grants ``user`` a term by hand."""
    return f"{LIST_URL}/{user.pk}/memberships"


def membership_url(term: Membership) -> str:
    """``/admin/memberships/{id}``, which corrects ``term``'s end date or status."""
    return f"/api/v1/admin/memberships/{term.pk}"


def first_membership(user: User) -> Membership:
    """Return ``user``'s first membership term, given every caller knows one exists."""
    term = user.memberships.first()
    assert term is not None
    return term


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------
@pytest.fixture
def population(
    annual_plan: MembershipPlan, life_plan: MembershipPlan, today: date, dart: Dart
) -> dict[str, User]:
    """A mixed member table: current, expiring, expired, lifetime and never."""
    day = timedelta(days=1)
    other_dart = DartFactory(name="Livermore", airport_identifier="LVK", city="Livermore")
    aircraft = AircraftFactory(n_number="N4242C")

    people: dict[str, User] = {}

    current = UserFactory(email="current@example.test", first_name="Ana", last_name="Bracco")
    MemberProfileFactory(
        user=current,
        dart=dart,
        phone="415-555-0100",
        certificate_number="1234567",
        pilot_certificate_type=PilotCertificateType.PRIVATE,
        medical_type=MedicalType.THIRD,
        city="Palo Alto",
    )
    current.profile.aircraft.add(aircraft)
    MembershipFactory(user=current, plan=annual_plan, starts_on=today - 100 * day)
    people["current"] = current

    expiring = UserFactory(email="expiring@example.test", first_name="Bo", last_name="Chen")
    MemberProfileFactory(
        user=expiring,
        dart=other_dart,
        phone="510-555-0111",
        pilot_certificate_type=PilotCertificateType.COMMERCIAL,
        medical_type=MedicalType.BASICMED,
    )
    MembershipFactory(
        user=expiring, plan=annual_plan, starts_on=today - 350 * day, ends_on=today + 14 * day
    )
    people["expiring"] = expiring

    expired = UserFactory(email="expired@example.test", first_name="Cleo", last_name="Duarte")
    MemberProfileFactory(
        user=expired,
        dart=dart,
        phone="650-555-0122",
        pilot_certificate_type=PilotCertificateType.STUDENT,
        medical_type=MedicalType.NONE,
    )
    MembershipFactory(
        user=expired,
        plan=annual_plan,
        starts_on=today - 500 * day,
        ends_on=today - 135 * day,
        status=MembershipStatusChoices.EXPIRED,
    )
    people["expired"] = expired

    lifetime = UserFactory(email="lifetime@example.test", first_name="Dev", last_name="Ellis")
    MemberProfileFactory(user=lifetime, dart=other_dart, phone="707-555-0133")
    MembershipFactory(user=lifetime, plan=life_plan, starts_on=today - 900 * day, ends_on=None)
    people["lifetime"] = lifetime

    never = UserFactory(email="never@example.test", first_name="Eve", last_name="Franco")
    MemberProfileFactory(user=never, dart=None, phone="")
    people["never"] = never

    return people


#: The fixture members, so a filter assertion can ignore the admin doing the
#: filtering and any bulk rows a test adds.
POPULATION_EMAILS = {
    "current@example.test",
    "expiring@example.test",
    "expired@example.test",
    "lifetime@example.test",
    "never@example.test",
}


def rows(response: ApiResponse) -> list[dict[str, Any]]:
    """Return the ``results`` list of a paginated member list response."""
    return cast(list[dict[str, Any]], response.json()["results"])


def emails(response: ApiResponse) -> set[str]:
    """Return the set of ``email`` values in a paginated member list response."""
    return {row["email"] for row in rows(response)}


# --------------------------------------------------------------------------
# Role matrix
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("method", "path_for", "payload"),
    [
        ("get", lambda u, t: LIST_URL, None),
        ("get", lambda u, t: CSV_URL, None),
        ("get", lambda u, t: PDF_URL, None),
        ("get", lambda u, t: detail_url(u), None),
        ("post", lambda u, t: LIST_URL, {"email": "anon@example.test"}),
        ("patch", lambda u, t: detail_url(u), {"first_name": "Nope"}),
        ("delete", lambda u, t: detail_url(u), None),
        ("post", lambda u, t: grant_url(u), {"plan": "annual"}),
        ("patch", lambda u, t: membership_url(t), {"note": "nope"}),
    ],
)
def test_every_endpoint_is_401_when_anonymous(
    api_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    method: str,
    path_for: Callable[[User, Membership], str],
    payload: dict[str, Any] | None,
) -> None:
    """Every members-admin endpoint refuses an anonymous caller with a 401."""
    term = MembershipFactory(user=member, plan=annual_plan)
    response = getattr(api_client, method)(path_for(member, term), payload, format="json")
    assert response.status_code == 401


@pytest.mark.parametrize("role", DENIED_ROLES)
def test_reads_are_forbidden_without_account_admin(
    api_client: APIClient, all_role_users: dict[str, User], population: dict[str, User], role: str
) -> None:
    """A role outside account admin and system admin is refused every read."""
    api_client.force_login(all_role_users[role])
    target = population["current"]
    for url in (LIST_URL, CSV_URL, PDF_URL, detail_url(target)):
        assert api_client.get(url).status_code == 403, url


@pytest.mark.parametrize("role", DENIED_ROLES)
def test_writes_are_forbidden_without_account_admin(
    api_client: APIClient,
    all_role_users: dict[str, User],
    population: dict[str, User],
    annual_plan: MembershipPlan,
    role: str,
) -> None:
    """A role outside account admin and system admin is refused every write."""
    api_client.force_login(all_role_users[role])
    target = population["current"]
    term = first_membership(target)

    assert api_client.post(LIST_URL, {"email": "x@example.test"}).status_code == 403
    assert api_client.patch(detail_url(target), {"first_name": "X"}).status_code == 403
    assert api_client.post(grant_url(target), {"plan": "annual"}).status_code == 403
    assert api_client.patch(membership_url(term), {"note": "x"}).status_code == 403
    assert api_client.delete(detail_url(target)).status_code == 403


@pytest.mark.parametrize("role", sorted(ALLOWED_ROLES))
def test_account_and_system_admins_may_read(
    api_client: APIClient, all_role_users: dict[str, User], population: dict[str, User], role: str
) -> None:
    """An account admin or system admin may use every read endpoint."""
    api_client.force_login(all_role_users[role])
    assert api_client.get(LIST_URL).status_code == 200
    assert api_client.get(detail_url(population["current"])).status_code == 200
    assert api_client.get(CSV_URL).status_code == 200
    assert api_client.get(PDF_URL).status_code == 200


# --------------------------------------------------------------------------
# List: shape, pagination, filters, ordering
# --------------------------------------------------------------------------
def test_row_shape_matches_the_portal_member_row(
    account_admin_client: APIClient, population: dict[str, User], today: date
) -> None:
    """A list row carries exactly the fields the portal's member row needs."""
    response = account_admin_client.get(LIST_URL, {"search": "current@example.test"})
    assert response.status_code == 200
    (row,) = rows(response)
    assert set(row) == {
        "user_id",
        "name",
        "email",
        "phone",
        "dart",
        "is_active",
        "membership",
        "pilot_certificate_type",
        "medical_type",
        "medical_expiration",
        "medical_is_current",
        "aircraft",
        "joined_on",
    }
    assert row["name"] == "Ana Bracco"
    assert row["dart"] == "Palo Alto"
    assert row["phone"] == "415-555-0100"
    assert row["aircraft"] == ["N4242C"]
    assert row["medical_is_current"] is True
    assert row["membership"]["status"] == "current"
    assert row["joined_on"] == (today - timedelta(days=100)).isoformat()


def test_list_is_paginated(account_admin_client: APIClient, population: dict[str, User]) -> None:
    """The list is paginated to the requested page size, with a next link."""
    response = account_admin_client.get(LIST_URL, {"page_size": 2})
    body = response.json()
    assert body["count"] == User.objects.count()
    assert len(body["results"]) == 2
    assert body["next"] == f"http://testserver{LIST_URL}?page=2&page_size=2"


@pytest.mark.parametrize(
    ("status_value", "expected"),
    [
        ("current", {"current@example.test", "expiring@example.test", "lifetime@example.test"}),
        ("expired", {"expired@example.test"}),
        ("none", {"never@example.test"}),
    ],
)
def test_status_filter_puts_each_member_in_one_bucket(
    account_admin_client: APIClient,
    population: dict[str, User],
    status_value: str,
    expected: set[str],
) -> None:
    """Each of the five fixture members lands in exactly one status bucket."""
    response = account_admin_client.get(LIST_URL, {"status": status_value, "page_size": "200"})
    assert emails(response) & POPULATION_EMAILS == expected


def test_status_filter_partitions_the_table(
    account_admin_client: APIClient, population: dict[str, User]
) -> None:
    """The four status buckets add up to the whole table, with no member in two."""
    total = account_admin_client.get(LIST_URL).json()["count"]
    counts = [
        account_admin_client.get(LIST_URL, {"status": value}).json()["count"]
        for value in ("current", "new", "expired", "none")
    ]
    assert sum(counts) == total


def test_ordering_by_dart_sorts_on_the_team_name(
    account_admin_client: APIClient, population: dict[str, User]
) -> None:
    """``?ordering=dart`` sorts by team, keeping the unaffiliated at the end."""
    response = account_admin_client.get(LIST_URL, {"ordering": "dart", "page_size": "200"})
    darts = [row["dart"] for row in response.json()["results"]]

    named = [dart for dart in darts if dart]
    assert named == sorted(named)
    assert all(dart is None for dart in darts[len(named) :])


def test_ordering_by_pilot_ranks_current_medicals_first(
    account_admin_client: APIClient,
    annual_plan: MembershipPlan,
    user_factory: type[UserFactory],
) -> None:
    """``?ordering=pilot`` reads in the order the column's marks do."""
    today = timezone.localdate()
    for email, certificate, medical, expiration in (
        ("lapsed@example.test", PilotCertificateType.PRIVATE, MedicalType.THIRD, today - ONE_DAY),
        ("nonpilot@example.test", PilotCertificateType.NONE, MedicalType.NONE, None),
        ("current@example.test", PilotCertificateType.PRIVATE, MedicalType.THIRD, today + ONE_DAY),
    ):
        owner = user_factory(email=email, roles=["member"])
        MemberProfileFactory(
            user=owner,
            pilot_certificate_type=certificate,
            medical_type=medical,
            medical_expiration=expiration,
        )

    response = account_admin_client.get(LIST_URL, {"ordering": "pilot", "page_size": "200"})
    order = [row["email"] for row in response.json()["results"]]

    assert order.index("current@example.test") < order.index("lapsed@example.test")
    assert order.index("lapsed@example.test") < order.index("nonpilot@example.test")


def test_an_unpaid_term_reads_as_new_and_not_as_expired(
    account_admin_client: APIClient, annual_plan: MembershipPlan, user_factory: type[UserFactory]
) -> None:
    """Somebody who joined but has not paid is ``new``, whatever the term's dates."""
    joiner = user_factory(email="unpaid@example.test", roles=["member"])
    today = timezone.localdate()
    MembershipFactory(
        user=joiner,
        plan=annual_plan,
        starts_on=today - timedelta(days=2),
        ends_on=today + timedelta(days=363),
        status=MembershipStatusChoices.NEW,
    )

    rows = account_admin_client.get(LIST_URL, {"status": "new", "page_size": "200"}).json()
    assert [row["email"] for row in rows["results"]] == ["unpaid@example.test"]
    assert rows["results"][0]["membership"]["status"] == "new"

    for other in ("current", "expired", "none"):
        emails_in_bucket = emails(account_admin_client.get(LIST_URL, {"status": other}))
        assert "unpaid@example.test" not in emails_in_bucket


def test_expiring_within_uses_the_computed_expiry(
    account_admin_client: APIClient, population: dict[str, User]
) -> None:
    """The ``expiring_within`` filter matches on the computed coverage end."""
    response = account_admin_client.get(LIST_URL, {"expiring_within": 30})
    assert emails(response) == {"expiring@example.test"}
    # A lifetime member never turns up in an expiry window.
    assert "lifetime@example.test" not in emails(response)
    assert account_admin_client.get(LIST_URL, {"expiring_within": 400}).json()["count"] == 2


def test_expiring_within_follows_a_renewal(
    account_admin_client: APIClient,
    population: dict[str, User],
    annual_plan: MembershipPlan,
    today: date,
) -> None:
    """Renewing early moves the member out of the expiring window at once."""
    expiring = population["expiring"]
    MembershipFactory(
        user=expiring,
        plan=annual_plan,
        starts_on=today + timedelta(days=15),
        ends_on=today + timedelta(days=379),
    )
    response = account_admin_client.get(LIST_URL, {"expiring_within": 30})
    assert "expiring@example.test" not in emails(response)


@pytest.mark.parametrize(
    ("term", "expected"),
    [
        ("Bracco", "current@example.test"),
        ("ana", "current@example.test"),
        ("expiring@example.test", "expiring@example.test"),
        ("510-555-0111", "expiring@example.test"),
        ("1234567", "current@example.test"),
        ("Ana Bracco", "current@example.test"),
    ],
)
def test_search_covers_name_email_phone_and_certificate_number(
    account_admin_client: APIClient,
    fixed_name_population: dict[str, User],
    term: str,
    expected: str,
) -> None:
    """A search matches name, email, phone or certificate number.

    The signed-in administrator is in the list too, so their name is pinned: a
    Faker-drawn name containing ``ana`` would otherwise match the search as well.
    """
    response = account_admin_client.get(LIST_URL, {"search": term})
    assert emails(response) == {expected}


def test_certificate_and_medical_filters(
    account_admin_client: APIClient, population: dict[str, User]
) -> None:
    """The certificate and medical filters narrow the list independently."""
    response = account_admin_client.get(LIST_URL, {"certificate": PilotCertificateType.COMMERCIAL})
    assert emails(response) == {"expiring@example.test"}
    response = account_admin_client.get(LIST_URL, {"medical": MedicalType.BASICMED})
    assert emails(response) == {"expiring@example.test"}


def test_dart_filter_accepts_an_id_or_a_name(
    account_admin_client: APIClient, population: dict[str, User], dart: Dart
) -> None:
    """The ``dart`` filter matches by numeric id or by name."""
    by_id = account_admin_client.get(LIST_URL, {"dart": dart.pk})
    assert emails(by_id) == {"current@example.test", "expired@example.test"}
    by_name = account_admin_client.get(LIST_URL, {"dart": "Livermore"})
    assert emails(by_name) == {"expiring@example.test", "lifetime@example.test"}


def test_role_filter(
    account_admin_client: APIClient, population: dict[str, User], account_admin: User
) -> None:
    """The role filter matches an account holding that role."""
    response = account_admin_client.get(LIST_URL, {"role": ACCOUNT_ADMIN})
    assert emails(response) == {account_admin.email}


def test_is_active_filter(account_admin_client: APIClient, population: dict[str, User]) -> None:
    """The ``is_active`` filter separates active from deactivated accounts."""
    never = population["never"]
    never.is_active = False
    never.save(update_fields=["is_active"])
    assert "never@example.test" in emails(
        account_admin_client.get(LIST_URL, {"is_active": "false"})
    )
    assert "never@example.test" not in emails(
        account_admin_client.get(LIST_URL, {"is_active": "true"})
    )


def test_filters_combine(
    account_admin_client: APIClient, population: dict[str, User], dart: Dart
) -> None:
    """Two filters combine with AND, not OR."""
    response = account_admin_client.get(LIST_URL, {"status": "current", "dart": str(dart.pk)})
    assert emails(response) == {"current@example.test"}


@pytest.fixture
def fixed_name_population(population: dict[str, User], account_admin: User) -> dict[str, User]:
    """``population`` with the signed-in admin given a fixed name too.

    ``account_admin`` otherwise carries a Faker-generated name, which would make
    an ordering or search assertion depend on whichever name Faker drew for
    this run.
    """
    account_admin.first_name, account_admin.last_name = "Zoe", "Yeager"
    account_admin.save(update_fields=["first_name", "last_name"])
    return population


def test_ordering_by_name_is_the_default(
    account_admin_client: APIClient, fixed_name_population: dict[str, User]
) -> None:
    """With no ordering given, the list sorts by last name."""
    names = [row["name"] for row in rows(account_admin_client.get(LIST_URL, {"page_size": 200}))]
    assert names == sorted(names, key=lambda value: value.split()[-1])


@pytest.mark.parametrize("field", ["name", "email", "expires_on", "joined"])
def test_ordering_accepts_every_documented_field(
    account_admin_client: APIClient, population: dict[str, User], field: str
) -> None:
    """Every documented ordering field, ascending and descending, is accepted."""
    assert account_admin_client.get(LIST_URL, {"ordering": field}).status_code == 200
    assert account_admin_client.get(LIST_URL, {"ordering": f"-{field}"}).status_code == 200


def test_ordering_by_expires_on_puts_lifetime_last(
    account_admin_client: APIClient, population: dict[str, User]
) -> None:
    """Ordering by expiry sorts dated expiries and puts lifetime members last."""
    ordered = rows(
        account_admin_client.get(LIST_URL, {"status": "current", "ordering": "expires_on"})
    )
    expiries = [row["membership"]["expires_on"] for row in ordered]
    assert expiries[0] is not None
    assert expiries[-1] is None
    dated = [value for value in expiries if value]
    assert dated == sorted(dated)


def test_ordering_by_joined(account_admin_client: APIClient, population: dict[str, User]) -> None:
    """Ordering by ``joined`` sorts members by their join date."""
    ordered = rows(account_admin_client.get(LIST_URL, {"ordering": "joined", "page_size": "200"}))
    joined = [row["joined_on"] for row in ordered if row["joined_on"]]
    assert joined == sorted(joined)


def test_the_list_does_not_scale_its_query_count_with_the_page(
    account_admin_client: APIClient,
    population: dict[str, User],
    django_assert_max_num_queries: DjangoAssertNumQueries,
) -> None:
    """Fetching a full page of members costs a fixed, small number of queries."""
    for index in range(30):
        MemberProfileFactory(user=UserFactory(email=f"bulk{index}@example.test"))
    with django_assert_max_num_queries(8):
        assert account_admin_client.get(LIST_URL, {"page_size": 50}).status_code == 200


# --------------------------------------------------------------------------
# Retrieve
# --------------------------------------------------------------------------
def test_detail_returns_the_whole_record(
    account_admin_client: APIClient, population: dict[str, User], annual_plan: MembershipPlan
) -> None:
    """The detail view returns the account, profile, memberships and payments."""
    member = population["current"]
    member.profile.notes = "Called about the Napa exercise."
    member.profile.how_heard = "EAA chapter meeting"
    member.profile.save()
    PaymentFactory(user=member, plan=annual_plan, amount_cents=6_500, contribution_cents=2_000)

    body = account_admin_client.get(detail_url(member)).json()
    assert set(body) == {
        "id",
        "created_at",
        "email",
        "first_name",
        "last_name",
        "name",
        "is_active",
        "roles",
        "membership",
        "profile",
        "memberships",
        "payments",
        "joined_on",
    }
    assert body["profile"]["notes"] == "Called about the Napa exercise."
    assert body["profile"]["how_heard"] == "EAA chapter meeting"
    assert body["profile"]["dart"] == {"id": member.profile.dart_id, "name": "Palo Alto"}
    assert body["profile"]["aircraft"][0]["n_number"] == "N4242C"
    assert len(body["memberships"]) == 1
    assert body["payments"][0]["amount_cents"] == 6_500
    assert body["payments"][0]["contribution_cents"] == 2_000


def test_detail_404s_for_an_unknown_id(account_admin_client: APIClient) -> None:
    """The detail view returns a 404 for an id on file for no member."""
    assert account_admin_client.get(f"{LIST_URL}/999999").status_code == 404


# --------------------------------------------------------------------------
# Create
# --------------------------------------------------------------------------
def test_create_with_a_password(account_admin_client: APIClient, dart: Dart) -> None:
    """Creating a member with a password given creates the account outright."""
    payload = {
        "email": "newbie@example.test",
        "first_name": "Nova",
        "last_name": "Ito",
        "password": "correct-horse-battery",
        "profile": {
            "phone": "408-555-0199",
            "city": "San Jose",
            "dart_id": dart.pk,
            "pilot_certificate_type": PilotCertificateType.PRIVATE,
            "certificate_number": "3141592",
            "ratings": ["instrument", "cfi"],
            "notes": "Joined at the Watsonville airshow.",
        },
    }
    response = account_admin_client.post(LIST_URL, payload, format="json")
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "newbie@example.test"
    assert body["roles"] == [MEMBER]
    assert body["profile"]["phone"] == "408-555-0199"
    assert body["profile"]["ratings"] == ["instrument", "cfi"]
    assert body["profile"]["notes"] == "Joined at the Watsonville airshow."
    assert body["membership"]["status"] == "none"

    user = User.objects.get(email="newbie@example.test")
    assert user.check_password("correct-horse-battery")
    assert user.has_role(MEMBER)
    assert MemberProfile.objects.filter(user=user).exists()
    assert mail.outbox == []


def test_create_without_a_password_emails_an_invitation(
    account_admin_client: APIClient,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """Creating a member with no password mails a set-your-password invitation."""
    with django_capture_on_commit_callbacks(execute=True):
        response = account_admin_client.post(
            LIST_URL, {"email": "invited@example.test"}, format="json"
        )
    assert response.status_code == 201

    user = User.objects.get(email="invited@example.test")
    assert not user.has_usable_password()
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == ["invited@example.test"]
    assert "/portal/reset-password?uid=" in message.body
    assert "token=" in message.body


def test_create_rejects_a_duplicate_email(
    account_admin_client: APIClient, population: dict[str, User]
) -> None:
    """Creating a member with an email already on file, in any case, is a 400."""
    response = account_admin_client.post(LIST_URL, {"email": "CURRENT@example.test"}, format="json")
    assert response.status_code == 400
    assert "email" in response.json()


def test_create_rejects_a_weak_password(account_admin_client: APIClient) -> None:
    """Creating a member with a weak password is refused and creates nothing."""
    response = account_admin_client.post(
        LIST_URL, {"email": "weak@example.test", "password": "123"}, format="json"
    )
    assert response.status_code == 400
    assert "password" in response.json()
    assert not User.objects.filter(email="weak@example.test").exists()


def test_create_applies_the_same_profile_rules_as_the_member_form(
    account_admin_client: APIClient,
) -> None:
    """The admin serializer extends `/me/profile`'s, so its rules hold here too."""
    response = account_admin_client.post(
        LIST_URL,
        {"email": "sloppy@example.test", "profile": {"state": "California", "postal_code": "9"}},
        format="json",
    )
    assert response.status_code == 400
    assert set(response.json()["profile"]) == {"state", "postal_code"}

    response = account_admin_client.post(
        LIST_URL,
        {"email": "sloppy@example.test", "profile": {"medical_type": MedicalType.THIRD}},
        format="json",
    )
    assert response.status_code == 400
    assert "medical_expiration" in response.json()["profile"]


def test_create_needs_nothing_but_an_email(account_admin_client: APIClient) -> None:
    """An administrator records what they were told, which may be very little."""
    response = account_admin_client.post(LIST_URL, {"email": "sparse@example.test"}, format="json")
    assert response.status_code == 201
    assert response.json()["profile"]["phone"] == ""


def test_a_partial_profile_patch_is_judged_against_the_stored_row(
    account_admin_client: APIClient, population: dict[str, User]
) -> None:
    """Sending one field must not trip a rule the rest of the profile satisfies."""
    member = population["current"]
    response = account_admin_client.patch(
        detail_url(member), {"profile": {"medical_type": MedicalType.FIRST}}, format="json"
    )
    assert response.status_code == 200
    assert response.json()["profile"]["medical_type"] == MedicalType.FIRST


def test_create_rejects_an_unknown_rating(account_admin_client: APIClient) -> None:
    """Creating a member with an unknown certificate rating is a 400."""
    response = account_admin_client.post(
        LIST_URL,
        {"email": "rating@example.test", "profile": {"ratings": ["rocket"]}},
        format="json",
    )
    assert response.status_code == 400


# --------------------------------------------------------------------------
# Update
# --------------------------------------------------------------------------
def test_patch_updates_the_user_and_the_nested_profile(
    account_admin_client: APIClient, population: dict[str, User], dart: Dart
) -> None:
    """A patch updates the account fields and the nested profile together."""
    member = population["expired"]
    response = account_admin_client.patch(
        detail_url(member),
        {
            "first_name": "Cleopatra",
            "is_active": False,
            "profile": {"phone": "650-555-9999", "notes": "Lapsed; sent a note."},
        },
        format="json",
    )
    assert response.status_code == 200
    body = response.json()
    assert body["first_name"] == "Cleopatra"
    assert body["is_active"] is False
    assert body["profile"]["phone"] == "650-555-9999"
    assert body["profile"]["notes"] == "Lapsed; sent a note."
    # Untouched profile fields survive a partial update.
    assert body["profile"]["dart"]["name"] == dart.name

    member.refresh_from_db()
    assert member.first_name == "Cleopatra"
    assert member.profile.phone == "650-555-9999"


def test_patch_can_clear_the_dart(
    account_admin_client: APIClient, population: dict[str, User]
) -> None:
    """`dart` reads back nested and is written as `dart_id`, as on /me/profile."""
    member = population["current"]
    response = account_admin_client.patch(
        detail_url(member), {"profile": {"dart_id": None}}, format="json"
    )
    assert response.status_code == 200
    assert response.json()["profile"]["dart"] is None


def test_patch_rejects_an_email_already_in_use(
    account_admin_client: APIClient, population: dict[str, User]
) -> None:
    """A patch that reuses another account's email is refused with a 400."""
    response = account_admin_client.patch(
        detail_url(population["current"]), {"email": "expired@example.test"}, format="json"
    )
    assert response.status_code == 400


def test_patch_creates_a_profile_when_the_account_has_none(account_admin_client: APIClient) -> None:
    """A patch creates the profile row when the target account has none."""
    bare = UserFactory(email="bare@example.test", roles=[MEMBER])
    response = account_admin_client.patch(
        detail_url(bare), {"profile": {"phone": "916-555-0000"}}, format="json"
    )
    assert response.status_code == 200
    assert response.json()["profile"]["phone"] == "916-555-0000"


def test_put_is_not_offered(account_admin_client: APIClient, population: dict[str, User]) -> None:
    """The detail endpoint offers no ``PUT``, only ``PATCH``."""
    assert account_admin_client.put(detail_url(population["current"]), {}).status_code == 405


# --------------------------------------------------------------------------
# Delete
# --------------------------------------------------------------------------
def test_delete_hard_deletes_and_cascades(
    account_admin_client: APIClient, population: dict[str, User]
) -> None:
    """A member who never paid goes, and the profile and terms go with them."""
    member = population["current"]
    pk = member.pk

    assert account_admin_client.delete(detail_url(member)).status_code == 204
    assert not User.objects.filter(pk=pk).exists()
    assert not MemberProfile.objects.filter(user_id=pk).exists()
    assert not Membership.objects.filter(user_id=pk).exists()


def test_delete_is_refused_for_a_member_with_payments(
    account_admin_client: APIClient, population: dict[str, User], annual_plan: MembershipPlan
) -> None:
    """Payments are kept, so the account that made them cannot be deleted."""
    member = population["current"]
    payment = PaymentFactory(user=member, plan=annual_plan)

    response = account_admin_client.delete(detail_url(member))

    assert response.status_code == 403
    assert User.objects.filter(pk=member.pk).exists()
    assert Payment.objects.filter(pk=payment.pk).exists()


def test_you_cannot_delete_yourself(account_admin_client: APIClient, account_admin: User) -> None:
    """An account admin cannot delete their own account through this endpoint."""
    assert account_admin_client.delete(detail_url(account_admin)).status_code == 403
    assert User.objects.filter(pk=account_admin.pk).exists()


def test_an_account_admin_cannot_delete_a_system_admin(
    account_admin_client: APIClient, system_admin: User
) -> None:
    """An account admin cannot delete a system administrator's account."""
    response = account_admin_client.delete(detail_url(system_admin))
    assert response.status_code == 403
    assert User.objects.filter(pk=system_admin.pk).exists()


def test_a_system_admin_can_delete_a_system_admin(
    api_client: APIClient, system_admin: User
) -> None:
    """A system administrator can delete another system administrator's account."""
    other = UserFactory(email="root2@example.test", roles=[MEMBER, SYSTEM_ADMIN])
    api_client.force_login(system_admin)
    assert api_client.delete(detail_url(other)).status_code == 204
    assert not User.objects.filter(pk=other.pk).exists()


# --------------------------------------------------------------------------
# Granting and editing terms
# --------------------------------------------------------------------------
def test_grant_to_a_current_member_starts_the_day_after_the_expiry(
    account_admin_client: APIClient,
    population: dict[str, User],
    annual_plan: MembershipPlan,
    account_admin: User,
    today: date,
) -> None:
    """Granting a term to a current member starts it the day the old one ends."""
    member = population["current"]
    expiry = first_membership(member).ends_on
    assert expiry is not None

    response = account_admin_client.post(
        grant_url(member), {"plan": annual_plan.slug, "note": "Comped by the board"}, format="json"
    )
    assert response.status_code == 201
    body = response.json()
    assert body["starts_on"] == (expiry + timedelta(days=1)).isoformat()
    assert body["ends_on"] == (expiry + timedelta(days=365)).isoformat()
    assert body["source"] == MembershipSource.MANUAL
    assert body["granted_by"] == account_admin.display_name
    assert body["note"] == "Comped by the board"


def test_grant_to_an_expired_member_starts_today(
    account_admin_client: APIClient,
    population: dict[str, User],
    annual_plan: MembershipPlan,
    today: date,
) -> None:
    """Granting a term to an expired member starts it today."""
    member = population["expired"]
    response = account_admin_client.post(
        grant_url(member), {"plan": annual_plan.slug}, format="json"
    )
    assert response.status_code == 201
    assert response.json()["starts_on"] == today.isoformat()
    assert response.json()["ends_on"] == (today + timedelta(days=364)).isoformat()


def test_grant_of_a_lifetime_plan_has_no_end_date(
    account_admin_client: APIClient,
    population: dict[str, User],
    life_plan: MembershipPlan,
    today: date,
) -> None:
    """Granting a lifetime plan leaves the term with no end date."""
    member = population["never"]
    response = account_admin_client.post(grant_url(member), {"plan": life_plan.slug}, format="json")
    assert response.status_code == 201
    assert response.json()["ends_on"] is None
    assert response.json()["starts_on"] == today.isoformat()

    detail = account_admin_client.get(detail_url(member)).json()
    assert detail["membership"] == {
        "status": "current",
        "expires_on": None,
        "plan": life_plan.name,
        "is_lifetime": True,
    }


def test_grant_honors_an_explicit_start_date(
    account_admin_client: APIClient,
    population: dict[str, User],
    annual_plan: MembershipPlan,
    today: date,
) -> None:
    """Granting a term with an explicit start date honors it."""
    member = population["never"]
    start = today - timedelta(days=10)
    response = account_admin_client.post(
        grant_url(member), {"plan": annual_plan.slug, "starts_on": start.isoformat()}, format="json"
    )
    assert response.status_code == 201
    assert response.json()["starts_on"] == start.isoformat()
    assert response.json()["ends_on"] == (start + timedelta(days=364)).isoformat()


def test_grant_rejects_an_unknown_plan(
    account_admin_client: APIClient, population: dict[str, User]
) -> None:
    """Granting a term for an unknown plan slug is refused with a 400."""
    response = account_admin_client.post(
        grant_url(population["never"]), {"plan": "platinum"}, format="json"
    )
    assert response.status_code == 400


def test_grant_404s_for_an_unknown_member(
    account_admin_client: APIClient, annual_plan: MembershipPlan
) -> None:
    """Granting a term to an unknown member id returns a 404."""
    response = account_admin_client.post(
        f"{LIST_URL}/999999/memberships", {"plan": annual_plan.slug}, format="json"
    )
    assert response.status_code == 404


def test_patch_a_term_changes_its_end_date_status_and_note(
    account_admin_client: APIClient, population: dict[str, User], today: date
) -> None:
    """A patch to a term changes its end date, status and note."""
    term = first_membership(population["current"])
    new_end = today + timedelta(days=5)
    response = account_admin_client.patch(
        membership_url(term),
        {"ends_on": new_end.isoformat(), "note": "Shortened after a refund"},
        format="json",
    )
    assert response.status_code == 200
    term.refresh_from_db()
    assert term.ends_on == new_end
    assert term.note == "Shortened after a refund"

    listed = account_admin_client.get(LIST_URL, {"search": "current@example.test"}).json()[
        "results"
    ][0]
    assert listed["membership"]["expires_on"] == new_end.isoformat()


def test_patch_a_term_to_canceled_drops_the_membership(
    account_admin_client: APIClient, population: dict[str, User]
) -> None:
    """Patching a term's status to canceled drops it from the reported membership."""
    term = first_membership(population["current"])
    response = account_admin_client.patch(
        membership_url(term), {"status": "canceled"}, format="json"
    )
    assert response.status_code == 200
    term.refresh_from_db()
    assert term.status == MembershipStatusChoices.CANCELED
    listed = account_admin_client.get(LIST_URL, {"search": "current@example.test"}).json()[
        "results"
    ][0]
    assert listed["membership"]["status"] == "none"


def test_patch_a_term_rejects_an_end_before_the_start(
    account_admin_client: APIClient, population: dict[str, User], today: date
) -> None:
    """A patch that would end a term before it starts is refused with a 400."""
    term = first_membership(population["current"])
    response = account_admin_client.patch(
        membership_url(term),
        {"ends_on": (term.starts_on - timedelta(days=1)).isoformat()},
        format="json",
    )
    assert response.status_code == 400
    assert "ends_on" in response.json()


def test_patch_a_term_cannot_move_its_plan_or_start(
    account_admin_client: APIClient,
    population: dict[str, User],
    life_plan: MembershipPlan,
    today: date,
) -> None:
    """A patch to a term cannot change its plan or its start date."""
    term = first_membership(population["current"])
    original_start = term.starts_on
    response = account_admin_client.patch(
        membership_url(term),
        {"starts_on": today.isoformat(), "plan": life_plan.slug},
        format="json",
    )
    assert response.status_code == 200
    term.refresh_from_db()
    assert term.starts_on == original_start
    assert term.plan_id != life_plan.pk
