"""First and last names: editable on the member's own profile, and stored normalized.

A name typed entirely in upper or entirely in lower case is stored in title case by
``caldart.casing.person_name``, applied in ``User.save()``, so every write path stores the
same result; a name typed in mixed case is kept as typed.  ``manage.py normalize_casing``
applies the same rules to the rows already stored.  The docs pages are
``docs/user/member/profile.rst`` and ``docs/developer/setup.rst``.
"""

from __future__ import annotations

from collections.abc import Iterator
from io import StringIO

import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.members.models import MemberProfile
from caldart.casing import person_last_name, person_name
from tests.conftest import REGISTER_URL, register_payload
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

PROFILE_URL = "/api/v1/me/profile"
CHECKOUT_URL = "/api/v1/donations/checkout"
MOCK_COMPLETE_URL = "/api/v1/donations/mock/complete"


def admin_members_url(user: User) -> str:
    """The account-administrator detail endpoint for ``user``."""
    return f"/api/v1/admin/members/{user.id}"


def store_raw(user: User, **fields: str) -> None:
    """Write ``fields`` straight to ``user``'s row, past ``save()``, as an old row."""
    User.objects.filter(pk=user.pk).update(**fields)


def store_raw_profile(profile: MemberProfile, **fields: str) -> None:
    """Write ``fields`` straight to ``profile``'s row, past ``save()``."""
    MemberProfile.objects.filter(pk=profile.pk).update(**fields)


def run_normalize(*args: str) -> str:
    """Run ``normalize_casing`` with ``args`` and return what it printed."""
    out = StringIO()
    call_command("normalize_casing", *args, stdout=out)
    return out.getvalue()


@pytest.fixture(autouse=True)
def empty_throttle_cache() -> Iterator[None]:
    """Clear the throttles' counters: shared state no test may inherit."""
    cache.clear()
    yield
    cache.clear()


# --------------------------------------------------------------------------
# person_name
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("SMITH", "Smith"),
        ("smith", "Smith"),
        ("MCDONALD", "McDonald"),
        ("mcdonald", "McDonald"),
        ("o'brien", "O'Brien"),
        ("O'BRIEN", "O'Brien"),
        ("smith-jones", "Smith-Jones"),
        ("VAN DER BERG", "Van der Berg"),
        ("jan van der berg", "Jan van der Berg"),
        ("maria de la cruz", "Maria de la Cruz"),
        ("JOHN SMITH III", "John Smith III"),
        ("macarthur", "Macarthur"),
        ("DeAnna", "DeAnna"),
        ("MacArthur", "MacArthur"),
        ("van Dyke", "van Dyke"),
        ("  mary   ann  ", "Mary Ann"),
        ("  DeAnna   Lee ", "DeAnna Lee"),
        ("", ""),
        ("   ", ""),
        ("J.R.", "J.R."),
        ("a.j.", "A.J."),
        ("o\u2019brien", "O\u2019Brien"),
        ("TJ", "TJ"),
        ("tj", "TJ"),
        ("DJ SMITH", "DJ Smith"),
    ],
    ids=[
        "upper-case",
        "lower-case",
        "mc-upper",
        "mc-lower",
        "o-apostrophe-lower",
        "o-apostrophe-upper",
        "hyphenated-parts-each-cased",
        "particles-lower-after-the-first-word",
        "particles-lower-in-a-lower-case-name",
        "spanish-particles",
        "a-generational-suffix-stays-upper",
        "mac-is-not-split",
        "mixed-case-kept",
        "mixed-case-mac-kept",
        "mixed-case-particle-kept",
        "whitespace-trimmed-and-collapsed",
        "mixed-case-still-trimmed-and-collapsed",
        "blank-stays-blank",
        "spaces-only-is-blank",
        "upper-case-initials-with-periods-kept",
        "each-letter-after-a-period-capitalized",
        "typographic-apostrophe-honored-and-kept",
        "vowel-less-initials-kept-upper",
        "vowel-less-initials-upper-cased",
        "vowel-less-first-word-upper-the-rest-title-cased",
    ],
)
def test_person_name_matches_the_documented_examples(value: str, expected: str) -> None:
    """A one-case name is title-cased with the documented exceptions; mixed is kept."""
    assert person_name(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("van dyke", "van Dyke"),
        ("VAN DER BERG", "van der Berg"),
        ("de la cruz", "de la Cruz"),
        ("VAN", "Van"),
        ("Van Dyke", "Van Dyke"),
        ("mcdonald iii", "McDonald III"),
    ],
    ids=[
        "a-leading-particle-stays-lower",
        "leading-particles-stay-lower",
        "spanish-leading-particles",
        "a-particle-alone-is-a-name",
        "mixed-case-kept",
        "the-other-rules-still-apply",
    ],
)
def test_person_last_name_keeps_a_leading_particle_lower(value: str, expected: str) -> None:
    """A last name keeps a leading particle lower; otherwise it is ``person_name``."""
    assert person_last_name(value) == expected


def test_person_name_capitalizes_a_leading_particle() -> None:
    """A first name, or a whole name, still capitalizes a particle as its first word."""
    assert person_name("van dyke") == "Van Dyke"


# --------------------------------------------------------------------------
# The model's save method
# --------------------------------------------------------------------------
def test_saving_an_account_keeps_a_last_names_leading_particle_lower() -> None:
    """``User.save()`` keeps a last name's leading particle lower, not a first name's."""
    user = UserFactory(first_name="van", last_name="van dyke")
    user.refresh_from_db()
    assert (user.first_name, user.last_name) == ("Van", "van Dyke")


def test_saving_an_account_normalizes_both_names() -> None:
    """``User.save()`` passes the first and the last name through ``person_name``."""
    user = UserFactory(first_name="MARY ANN", last_name="mcdonald")
    user.refresh_from_db()
    assert (user.first_name, user.last_name) == ("Mary Ann", "McDonald")


def test_saving_an_account_keeps_a_mixed_case_name_as_typed() -> None:
    """A name typed in mixed case is a deliberate spelling and is stored unchanged."""
    user = UserFactory(first_name="DeAnna", last_name="van Dyke")
    user.refresh_from_db()
    assert (user.first_name, user.last_name) == ("DeAnna", "van Dyke")


# --------------------------------------------------------------------------
# Registration, the administrator's editor, and the donation form
# --------------------------------------------------------------------------
def test_registration_stores_normalized_names(api_client: APIClient) -> None:
    """``POST /auth/register`` stores ``SMITH`` as ``Smith``."""
    response = api_client.post(
        REGISTER_URL, register_payload(first_name="NORA", last_name="SMITH"), format="json"
    )
    assert response.status_code in {200, 201}, response.json()
    user = User.objects.get(email="new.member@example.test")
    assert (user.first_name, user.last_name) == ("Nora", "Smith")


def test_admin_edit_stores_normalized_names(account_admin_client: APIClient, member: User) -> None:
    """An administrator's ``PATCH /admin/members/{id}`` stores the same casing."""
    response = account_admin_client.patch(
        admin_members_url(member), {"first_name": "o'brien", "last_name": "smith-jones"}
    )
    assert response.status_code == 200, response.json()
    assert (response.json()["first_name"], response.json()["last_name"]) == (
        "O'Brien",
        "Smith-Jones",
    )


def test_a_donation_stores_the_donors_names_normalized(api_client: APIClient) -> None:
    """A settled public gift stores the donor's names normalized."""
    checkout = api_client.post(
        CHECKOUT_URL,
        {
            "first_name": "PAT",
            "last_name": "GIVER",
            "email": "pat.giver@example.test",
            "phone": "415-555-0100",
            "contribution_cents": 10_000,
            "provider": "mock",
        },
        format="json",
    )
    assert checkout.status_code == 201, checkout.json()
    body = checkout.json()
    complete = api_client.post(
        MOCK_COMPLETE_URL,
        {"payment_id": body["payment_id"], "token": body["token"]},
        format="json",
    )
    assert complete.status_code == 200, complete.json()
    donor = User.objects.get(email="pat.giver@example.test")
    assert (donor.first_name, donor.last_name) == ("Pat", "Giver")


# --------------------------------------------------------------------------
# The member's own profile
# --------------------------------------------------------------------------
def test_get_profile_carries_the_account_names(
    api_client: APIClient, member: User, profile: MemberProfile
) -> None:
    """``GET /me/profile`` reads the first and last name off the account."""
    api_client.force_login(member)
    body = api_client.get(PROFILE_URL).json()
    assert (body["first_name"], body["last_name"]) == (member.first_name, member.last_name)


def test_patch_profile_saves_normalized_names_on_the_account(
    api_client: APIClient, member: User, profile: MemberProfile
) -> None:
    """A member's own ``PATCH`` stores ``SMITH`` as ``Smith`` and keeps ``DeAnna``."""
    api_client.force_login(member)
    response = api_client.patch(
        PROFILE_URL, {"first_name": "DeAnna", "last_name": "SMITH"}, format="json"
    )
    assert response.status_code == 200, response.json()
    member.refresh_from_db()
    assert (member.first_name, member.last_name) == ("DeAnna", "Smith")


def test_patch_profile_answers_with_the_stored_names(
    api_client: APIClient, member: User, profile: MemberProfile
) -> None:
    """The response to the save carries the names as stored, not as typed."""
    api_client.force_login(member)
    response = api_client.patch(
        PROFILE_URL, {"first_name": "nora", "last_name": "VAN DER BERG"}, format="json"
    )
    assert (response.json()["first_name"], response.json()["last_name"]) == (
        "Nora",
        "van der Berg",
    )


def test_put_profile_saves_the_names_with_the_rest(
    api_client: APIClient, member: User, profile: MemberProfile
) -> None:
    """A full ``PUT`` writes the names along with the profile fields."""
    api_client.force_login(member)
    response = api_client.put(
        PROFILE_URL,
        {"first_name": "Rosa", "last_name": "Diaz", "phone": "415-555-0100", "state": "CA"},
        format="json",
    )
    assert response.status_code == 200, response.json()
    member.refresh_from_db()
    assert (member.first_name, member.last_name) == ("Rosa", "Diaz")


def test_put_profile_without_names_leaves_them_alone(
    api_client: APIClient, member: User, profile: MemberProfile
) -> None:
    """The names live on the account, so a ``PUT`` that omits them does not clear them."""
    before = (member.first_name, member.last_name)
    api_client.force_login(member)
    response = api_client.put(PROFILE_URL, {"phone": "415-555-0100", "state": "CA"}, format="json")
    assert response.status_code == 200, response.json()
    member.refresh_from_db()
    assert (member.first_name, member.last_name) == before


@pytest.mark.parametrize("field", ["first_name", "last_name"])
def test_patch_profile_refuses_a_blank_name(
    api_client: APIClient, member: User, profile: MemberProfile, field: str
) -> None:
    """A blank name is refused in words that suit a member and an administrator alike."""
    api_client.force_login(member)
    response = api_client.patch(PROFILE_URL, {field: "   "}, format="json")
    assert response.status_code == 400
    assert response.json()[field] == [f"Enter a {field.replace('_', ' ')}."]


def test_a_profile_name_change_names_the_field_in_the_event(
    api_client: APIClient,
    member: User,
    profile: MemberProfile,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Changing a name raises ``profile_changed`` naming Last name."""
    seen: list[dict[str, object]] = []
    monkeypatch.setattr(
        "apps.members.api.profile_serializers.events.emit",
        lambda name, **kwargs: seen.append({"name": name, **kwargs}),
    )
    api_client.force_login(member)
    api_client.patch(PROFILE_URL, {"last_name": "Quintero"}, format="json")
    assert [(event["name"], event["fields"]) for event in seen] == [
        ("profile_changed", ["Last name"])
    ]


def test_resending_a_name_in_another_case_is_not_a_change(
    api_client: APIClient,
    member: User,
    profile: MemberProfile,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``SMITH`` resent for a stored ``Smith`` stores the same name and raises nothing."""
    member.last_name = "Smith"
    member.save()
    seen: list[str] = []
    monkeypatch.setattr(
        "apps.members.api.profile_serializers.events.emit",
        lambda name, **kwargs: seen.append(name),
    )
    api_client.force_login(member)
    api_client.patch(PROFILE_URL, {"last_name": "SMITH"}, format="json")
    assert seen == []


# --------------------------------------------------------------------------
# manage.py normalize_casing
# --------------------------------------------------------------------------
def test_normalize_casing_rewrites_names_stored_in_one_case() -> None:
    """The command title-cases an upper-case last name already stored."""
    user = UserFactory(email="ann@example.test", first_name="Ann")
    store_raw(user, last_name="SMITH")
    run_normalize()
    user.refresh_from_db()
    assert user.last_name == "Smith"


def test_normalize_casing_rewrites_the_street_and_city_already_stored() -> None:
    """The command title-cases a street and a city stored before the rule existed."""
    profile = MemberProfile.objects.create(user=UserFactory(), phone="415-555-0100")
    store_raw_profile(profile, address_line1="1 MAIN ST", city="palo alto")
    run_normalize()
    profile.refresh_from_db()
    assert (profile.address_line1, profile.city) == ("1 Main St", "Palo Alto")


def test_normalize_casing_prints_one_line_per_changed_field() -> None:
    """Each change is printed as ``<email>: <field> "<old>" -> "<new>"``."""
    user = UserFactory(email="ann@example.test", first_name="Ann", last_name="Lee")
    store_raw(user, last_name="SMITH")
    profile = MemberProfile.objects.create(user=user, phone="415-555-0100")
    store_raw_profile(profile, city="palo alto")
    lines = run_normalize().splitlines()
    assert lines[:2] == [
        'ann@example.test: last_name "SMITH" -> "Smith"',
        'ann@example.test: city "palo alto" -> "Palo Alto"',
    ]


def test_normalize_casing_reports_nothing_for_rows_already_normalized() -> None:
    """A database already in order prints no change lines, only the count."""
    UserFactory(first_name="DeAnna", last_name="McDonald")
    assert run_normalize().splitlines() == ["Changed 0 fields."]


def test_normalize_casing_dry_run_lists_without_writing() -> None:
    """``--dry-run`` prints the change and leaves the row as it was."""
    user = UserFactory(email="ann@example.test", first_name="Ann")
    store_raw(user, last_name="SMITH")
    output = run_normalize("--dry-run")
    user.refresh_from_db()
    assert user.last_name == "SMITH"
    assert 'ann@example.test: last_name "SMITH" -> "Smith"' in output.splitlines()


def test_normalize_casing_writes_only_the_changed_column_of_the_changed_row() -> None:
    """The run issues one ``UPDATE``: the changed row's changed column, nothing else."""
    UserFactory(first_name="Ann", last_name="Lee")
    changed = UserFactory(first_name="Bo", last_name="Lee")
    store_raw(changed, last_name="SMITH")
    with CaptureQueriesContext(connection) as queries:
        run_normalize()
    updates = [query["sql"] for query in queries if query["sql"].startswith("UPDATE")]
    statements = [update.split(" WHERE ") for update in updates]
    assert [statement[0] for statement in statements] == [
        'UPDATE "accounts_user" SET "last_name" = \'Smith\''
    ]
    assert [statement[1] for statement in statements] == [f'"accounts_user"."id" = {changed.pk}']
