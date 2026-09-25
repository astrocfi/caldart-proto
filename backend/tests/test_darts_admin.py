"""The account administrator's DART screen: list, create, edit, deactivate, delete.

Covers the role matrix on every endpoint, the counts the list carries, the
fields a row does and does not carry, the airport-identifier rule the profile
form shares, and what a delete leaves behind: unaffiliated members and an
unlinked website page.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import TYPE_CHECKING

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import ACCOUNT_ADMIN, SYSTEM_ADMIN
from apps.darts.models import MAX_AIRPORT_IDENTIFIERS, MAX_DART_CONTACTS, Dart, DartContact
from apps.members.models import MemberProfile
from caldart import audit
from tests.conftest import role_matrix
from tests.factories import (
    DartFactory,
    MemberProfileFactory,
    UserFactory,
    make_dart_index,
    make_dart_page,
    make_home_page,
)

if TYPE_CHECKING:
    # rest_framework.test.APIClient.get() is typed to return this class, but it
    # exists only in the stub: rest_framework monkey-patches Django's test response
    # at runtime rather than defining a real subclass.
    from rest_framework.response import _MonkeyPatchedResponse as ApiResponse

pytestmark = pytest.mark.django_db

LIST_URL = "/api/v1/admin/darts"


def detail_url(dart: Dart) -> str:
    """Build the detail URL for one DART."""
    return f"/api/v1/admin/darts/{dart.pk}"


@pytest.fixture
def audit_log(caplog: pytest.LogCaptureFixture) -> Iterator[pytest.LogCaptureFixture]:
    """Capture the ``caldart.audit`` records a test provokes.

    The audit logger does not propagate to the root logger, so ``caplog`` alone
    sees nothing: its handler is attached to the audit logger for the test and
    taken off again afterwards.
    """
    logger = logging.getLogger(audit.LOGGER_NAME)
    logger.addHandler(caplog.handler)
    try:
        yield caplog
    finally:
        logger.removeHandler(caplog.handler)


def audit_messages(caplog: pytest.LogCaptureFixture) -> list[str]:
    """Every audit message captured, in the order it was logged."""
    return [record.getMessage() for record in caplog.records if record.name == audit.LOGGER_NAME]


def names(response: ApiResponse) -> list[str]:
    """The DART names in a list response, in the order it returned them."""
    return [row["name"] for row in response.json()]


# --------------------------------------------------------------------------
# Who may work with DARTs
# --------------------------------------------------------------------------
@pytest.mark.parametrize(("slug", "allowed"), role_matrix(ACCOUNT_ADMIN, SYSTEM_ADMIN))
def test_role_matrix_for_the_list(
    api_client: APIClient, all_role_users: dict[str, User], slug: str, allowed: bool
) -> None:
    """Only account and system admins read the DART list; every other role gets 403."""
    api_client.force_login(all_role_users[slug])
    assert api_client.get(LIST_URL).status_code == (200 if allowed else 403)


@pytest.mark.parametrize(("slug", "allowed"), role_matrix(ACCOUNT_ADMIN, SYSTEM_ADMIN))
def test_role_matrix_for_create(
    api_client: APIClient, all_role_users: dict[str, User], slug: str, allowed: bool
) -> None:
    """Only account and system admins create a DART; every other role gets 403."""
    api_client.force_login(all_role_users[slug])
    response = api_client.post(
        LIST_URL, {"name": f"Test {slug}", "airport_identifiers": "PAO"}, format="json"
    )
    assert response.status_code == (201 if allowed else 403)


def test_the_list_is_unauthenticated_as_401(api_client: APIClient, db: None) -> None:
    """An anonymous caller is told to sign in rather than refused outright."""
    assert api_client.get(LIST_URL).status_code == 401


# --------------------------------------------------------------------------
# Reading
# --------------------------------------------------------------------------
def test_the_list_is_alphabetical_and_holds_retired_darts(
    account_admin_client: APIClient,
) -> None:
    """Every DART is listed, retired ones too, in one alphabetical run."""
    DartFactory(name="Watsonville")
    DartFactory(name="Angwin")
    DartFactory(name="Closed Field", is_active=False)
    assert names(account_admin_client.get(LIST_URL)) == ["Angwin", "Closed Field", "Watsonville"]


def test_each_row_counts_the_members_on_that_dart(account_admin_client: APIClient) -> None:
    """``member_count`` is the number of profiles naming the DART."""
    dart = DartFactory(name="Hayward")
    MemberProfileFactory(user=UserFactory(email="one@example.test"), dart=dart)
    MemberProfileFactory(user=UserFactory(email="two@example.test"), dart=dart)
    row = account_admin_client.get(LIST_URL).json()[0]
    assert row["member_count"] == 2


def test_a_dart_nobody_is_on_counts_zero(account_admin_client: APIClient) -> None:
    """``member_count`` is zero for a DART with no profiles on it."""
    DartFactory(name="Angwin")
    assert account_admin_client.get(LIST_URL).json()[0]["member_count"] == 0


def test_a_dart_row_names_its_airports_and_no_town(account_admin_client: APIClient) -> None:
    """A DART is its name, its airports, its website and whether it is active.

    A team is identified by the fields it flies from, so the row carries no
    town of its own.
    """
    DartFactory(name="Angwin", airport_identifiers="2O3")
    row = account_admin_client.get(LIST_URL).json()[0]

    assert row["airport_identifiers"] == "2O3"
    assert "city" not in row


def test_the_public_catalog_carries_no_town(api_client: APIClient, db: None) -> None:
    """``GET /darts`` answers the same fields the administrator's screen edits."""
    DartFactory(name="Angwin", airport_identifiers="2O3")
    row = api_client.get("/api/v1/darts").json()[0]

    assert row["airport_identifiers"] == "2O3"
    assert "city" not in row


# --------------------------------------------------------------------------
# Writing
# --------------------------------------------------------------------------
def test_creating_a_dart_returns_it_with_its_counts(account_admin_client: APIClient) -> None:
    """A create answers 201 with the stored row, counts included."""
    response = account_admin_client.post(
        LIST_URL,
        {"name": "Santa Ynez", "airport_identifiers": "iza"},
        format="json",
    )
    assert response.status_code == 201, response.json()
    assert response.json()["airport_identifiers"] == "IZA"


def test_a_dart_needs_a_name(account_admin_client: APIClient) -> None:
    """A blank name is refused, naming ``name``."""
    response = account_admin_client.post(LIST_URL, {"name": "   "}, format="json")
    assert response.status_code == 400
    assert response.json()["name"] == ["Give the DART a name."]


def test_two_darts_may_not_share_a_name(account_admin_client: APIClient) -> None:
    """The name is the DART's identity, so a repeat is refused."""
    DartFactory(name="Napa")
    response = account_admin_client.post(LIST_URL, {"name": "Napa"}, format="json")
    assert response.status_code == 400
    assert "name" in response.json()


@pytest.mark.parametrize(
    "identifier",
    ["AP", "APCXX", "XAPC"],
    ids=["too-short", "too-long", "four-without-the-k"],
)
def test_an_airport_identifier_is_three_characters(
    account_admin_client: APIClient, identifier: str
) -> None:
    """Three characters is the stored form; a fourth is only ever an ICAO ``K``."""
    response = account_admin_client.post(
        LIST_URL, {"name": "Napa", "airport_identifiers": identifier}, format="json"
    )
    assert response.status_code == 400
    assert response.json()["airport_identifiers"] == [
        "Use three-character identifiers, separated by commas, like CCR, C83."
    ]


@pytest.mark.parametrize(
    ("typed", "stored"),
    [("kls", "KLS"), ("l08", "L08"), ("kcrq", "CRQ"), ("KKAB", "KAB")],
    ids=["k-is-the-identifier", "digits", "icao-form-trimmed", "both"],
)
def test_the_icao_k_is_trimmed_and_a_real_k_is_kept(
    account_admin_client: APIClient, typed: str, stored: str
) -> None:
    """``KCRQ`` and ``CRQ`` are one airport, and Kelso really is ``KLS``."""
    response = account_admin_client.post(
        LIST_URL, {"name": f"Team {typed}", "airport_identifiers": typed}, format="json"
    )
    assert response.status_code == 201, response.json()
    assert response.json()["airport_identifiers"] == stored


def test_a_pasted_icao_list_is_stored_in_the_one_spelling(
    account_admin_client: APIClient,
) -> None:
    """San Diego's fields, pasted as ICAO, are stored as the three-character form."""
    response = account_admin_client.post(
        LIST_URL,
        {"name": "San Diego", "airport_identifiers": "KCRQ, KMYF, KOKB, F70, L08"},
        format="json",
    )
    assert response.status_code == 201, response.json()
    assert response.json()["airport_identifiers"] == "CRQ, MYF, OKB, F70, L08"


def test_a_list_separated_by_spaces_alone_is_read_as_a_list(
    account_admin_client: APIClient,
) -> None:
    """A pasted list often has no commas, and no identifier holds a space."""
    response = account_admin_client.post(
        LIST_URL, {"name": "Contra Costa", "airport_identifiers": "CCR C83"}, format="json"
    )
    assert response.status_code == 201, response.json()
    assert response.json()["airport_identifiers"] == "CCR, C83"


def test_a_dart_may_fly_from_several_airports(account_admin_client: APIClient) -> None:
    """Contra Costa covers two fields, and the list is stored as ``"CCR, C83"``."""
    response = account_admin_client.post(
        LIST_URL, {"name": "Contra Costa", "airport_identifiers": "ccr,c83"}, format="json"
    )
    assert response.status_code == 201, response.json()
    assert response.json()["airport_identifiers"] == "CCR, C83"


def test_every_dart_needs_an_airport(account_admin_client: APIClient) -> None:
    """A DART is organized around a field, so an empty list is refused."""
    response = account_admin_client.post(
        LIST_URL, {"name": "Nowhere", "airport_identifiers": " , "}, format="json"
    )
    assert response.status_code == 400
    assert response.json()["airport_identifiers"] == ["Give the DART at least one airport."]


def test_an_airport_may_not_be_listed_twice(account_admin_client: APIClient) -> None:
    """A repeated field is a typo, not two airports -- ``KPAO`` and ``PAO`` included."""
    response = account_admin_client.post(
        LIST_URL, {"name": "Twice", "airport_identifiers": "PAO, kpao"}, format="json"
    )
    assert response.status_code == 400
    assert response.json()["airport_identifiers"] == ["That list names the same airport twice."]


def test_an_airport_list_has_a_limit(account_admin_client: APIClient) -> None:
    """A list longer than the cap is prose, not a list of fields."""
    airports = ", ".join(f"X{index:02d}" for index in range(MAX_AIRPORT_IDENTIFIERS + 1))
    response = account_admin_client.post(
        LIST_URL, {"name": "Everywhere", "airport_identifiers": airports}, format="json"
    )
    assert response.status_code == 400
    assert response.json()["airport_identifiers"] == [
        f"A DART may list at most {MAX_AIRPORT_IDENTIFIERS} airports."
    ]


def test_editing_a_dart_saves_the_fields_it_carried(account_admin_client: APIClient) -> None:
    """A PATCH edits only what it names and answers with the whole row."""
    dart = DartFactory(name="Napa", website_url="https://napa.example.org/")
    response = account_admin_client.patch(
        detail_url(dart), {"website_url": "https://napadart.example.org/"}, format="json"
    )
    assert response.status_code == 200, response.json()
    assert response.json()["website_url"] == "https://napadart.example.org/"
    assert response.json()["name"] == "Napa"


def test_retiring_a_dart_keeps_it_and_its_members(account_admin_client: APIClient) -> None:
    """Turning off ``is_active`` leaves the row and every profile on it alone."""
    dart = DartFactory(name="Napa")
    MemberProfileFactory(user=UserFactory(email="one@example.test"), dart=dart)
    response = account_admin_client.patch(detail_url(dart), {"is_active": False}, format="json")
    assert response.status_code == 200
    dart.refresh_from_db()
    assert dart.members.count() == 1


# --------------------------------------------------------------------------
# Deleting
# --------------------------------------------------------------------------
def test_deleting_a_dart_nobody_is_on_removes_it(account_admin_client: APIClient) -> None:
    """A DART with no members and no pages is deleted outright."""
    dart = DartFactory(name="Angwin")
    assert account_admin_client.delete(detail_url(dart)).status_code == 204
    assert not Dart.objects.filter(pk=dart.pk).exists()


def test_deleting_a_dart_makes_its_members_unaffiliated(
    account_admin_client: APIClient,
) -> None:
    """A member on a deleted DART keeps their record and loses the team."""
    dart = DartFactory(name="Napa")
    profile = MemberProfileFactory(user=UserFactory(email="one@example.test"), dart=dart)

    assert account_admin_client.delete(detail_url(dart)).status_code == 204

    profile.refresh_from_db()
    assert profile.dart is None


def test_deleting_a_dart_keeps_the_member_itself(account_admin_client: APIClient) -> None:
    """Unaffiliating a member is not deleting them: the profile is still there."""
    dart = DartFactory(name="Napa")
    profile = MemberProfileFactory(user=UserFactory(email="one@example.test"), dart=dart)

    assert account_admin_client.delete(detail_url(dart)).status_code == 204

    assert MemberProfile.objects.filter(pk=profile.pk).exists()


def test_deleting_a_dart_keeps_the_website_page_it_was_linked_to(
    account_admin_client: APIClient,
) -> None:
    """The team's own page is content, so it survives the team and loses the link."""
    dart = DartFactory(name="Napa")
    page = make_dart_page(make_dart_index(make_home_page()), dart)

    assert account_admin_client.delete(detail_url(dart)).status_code == 204

    page.refresh_from_db()
    assert page.dart is None


def test_the_delete_audit_line_counts_the_members_and_the_pages(
    account_admin_client: APIClient, audit_log: pytest.LogCaptureFixture
) -> None:
    """The line says what the delete left behind, because it cannot be undone."""
    dart = DartFactory(name="Napa")
    MemberProfileFactory(user=UserFactory(email="one@example.test"), dart=dart)
    make_dart_page(make_dart_index(make_home_page()), dart)

    account_admin_client.delete(detail_url(dart))

    line = audit_messages(audit_log)[-1]
    assert line.startswith("action=dart.delete ")
    assert line.endswith(" members=1 pages=1")


# --------------------------------------------------------------------------
# The people who run a DART
# --------------------------------------------------------------------------
def test_a_dart_is_created_with_its_people(account_admin_client: APIClient) -> None:
    """The contacts in the body are stored with the DART, in the order given."""
    response = account_admin_client.post(
        LIST_URL,
        {
            "name": "Napa",
            "airport_identifiers": "APC",
            "contacts": [
                {"name": "Helen Marchetti", "title": "DART leader", "phone": "(707) 555 0133"},
                {"name": "Victor Ocampo", "title": "Deputy leader", "email": "v@example.test"},
            ],
        },
        format="json",
    )
    assert response.status_code == 201, response.json()
    contacts = response.json()["contacts"]
    assert [contact["name"] for contact in contacts] == ["Helen Marchetti", "Victor Ocampo"]


def test_a_contact_phone_is_stored_in_the_one_shape(account_admin_client: APIClient) -> None:
    """However it is typed, a contact's number is stored as ``XXX-XXX-XXXX``."""
    response = account_admin_client.post(
        LIST_URL,
        {
            "name": "Napa",
            "airport_identifiers": "APC",
            "contacts": [{"name": "Helen", "title": "Leader", "phone": "+1 (707) 555.0133"}],
        },
        format="json",
    )
    assert response.json()["contacts"][0]["phone"] == "707-555-0133"


def test_a_contact_phone_that_is_not_ten_digits_is_refused(
    account_admin_client: APIClient,
) -> None:
    """A half-typed number is refused rather than stored as typed."""
    response = account_admin_client.post(
        LIST_URL,
        {
            "name": "Napa",
            "airport_identifiers": "APC",
            "contacts": [{"name": "Helen", "title": "Leader", "phone": "707-555"}],
        },
        format="json",
    )
    assert response.status_code == 400
    assert response.json()["contacts"] == {
        "0": {"phone": ["Use a ten-digit number like 415-555-0100."]}
    }


def test_a_contact_needs_a_name(account_admin_client: APIClient) -> None:
    """A listing without a name names nobody."""
    response = account_admin_client.post(
        LIST_URL,
        {
            "name": "Napa",
            "airport_identifiers": "APC",
            "contacts": [{"name": "", "title": "Leader"}],
        },
        format="json",
    )
    assert response.status_code == 400
    assert response.json()["contacts"]["0"]["name"] == ["Give the person a name."]


def test_a_contact_needs_a_title(account_admin_client: APIClient) -> None:
    """A name without a job does not say who to ask for what."""
    response = account_admin_client.post(
        LIST_URL,
        {
            "name": "Napa",
            "airport_identifiers": "APC",
            "contacts": [{"name": "Helen", "title": ""}],
        },
        format="json",
    )
    assert response.status_code == 400
    assert response.json()["contacts"]["0"]["title"] == ["Say what this person does."]


def test_a_contact_may_be_email_only(account_admin_client: APIClient) -> None:
    """Not everyone gives a number, and a listing without one is still useful."""
    response = account_admin_client.post(
        LIST_URL,
        {
            "name": "Napa",
            "airport_identifiers": "APC",
            "contacts": [{"name": "Helen", "title": "Leader", "email": "h@example.test"}],
        },
        format="json",
    )
    assert response.status_code == 201, response.json()
    assert response.json()["contacts"][0]["phone"] == ""


def test_a_dart_lists_at_most_five_people(account_admin_client: APIClient) -> None:
    """A longer list is a roster, which is what the member records are for."""
    contacts = [
        {"name": f"Person {index}", "title": "Volunteer"} for index in range(MAX_DART_CONTACTS + 1)
    ]
    response = account_admin_client.post(
        LIST_URL,
        {"name": "Napa", "airport_identifiers": "APC", "contacts": contacts},
        format="json",
    )
    assert response.status_code == 400
    assert response.json()["contacts"] == [f"A DART may list at most {MAX_DART_CONTACTS} people."]


def test_editing_the_contacts_replaces_them(account_admin_client: APIClient) -> None:
    """The list sent is the list stored: that is how the screen edits it."""
    dart = DartFactory(name="Napa")
    DartContact.objects.create(dart=dart, name="Old Leader", title="DART leader")

    response = account_admin_client.patch(
        detail_url(dart),
        {"contacts": [{"name": "New Leader", "title": "DART leader"}]},
        format="json",
    )

    assert response.status_code == 200, response.json()
    assert [contact["name"] for contact in response.json()["contacts"]] == ["New Leader"]


def test_an_edit_that_leaves_the_contacts_out_keeps_them(
    account_admin_client: APIClient,
) -> None:
    """Renaming a DART is not a way to lose its officers by omission."""
    dart = DartFactory(name="Napa")
    DartContact.objects.create(dart=dart, name="Helen", title="DART leader")

    response = account_admin_client.patch(detail_url(dart), {"name": "Angwin"}, format="json")

    assert [contact["name"] for contact in response.json()["contacts"]] == ["Helen"]


def test_deleting_a_dart_takes_its_contacts_with_it(account_admin_client: APIClient) -> None:
    """A contact belongs to its DART and has no life without it."""
    dart = DartFactory(name="Angwin")
    DartContact.objects.create(dart=dart, name="Helen", title="DART leader")

    assert account_admin_client.delete(detail_url(dart)).status_code == 204
    assert DartContact.objects.count() == 0


def test_the_public_catalog_carries_the_people_too(api_client: APIClient, db: None) -> None:
    """``GET /darts`` is how a visitor finds who to ask, so it names them."""
    dart = DartFactory(name="Napa")
    DartContact.objects.create(dart=dart, name="Helen", title="DART leader")

    rows = api_client.get("/api/v1/darts").json()

    assert rows[0]["contacts"][0] == {
        "id": dart.contacts.get().pk,
        "name": "Helen",
        "title": "DART leader",
        "phone": "",
        "email": "",
    }


def test_a_dart_carries_a_link_to_its_own_website(account_admin_client: APIClient) -> None:
    """Many teams run a site of their own, and the record links to it."""
    response = account_admin_client.post(
        LIST_URL,
        {
            "name": "Palo Alto",
            "airport_identifiers": "PAO",
            "website_url": "https://paloaltodart.example.org/",
        },
        format="json",
    )
    assert response.status_code == 201, response.json()
    assert response.json()["website_url"] == "https://paloaltodart.example.org/"


def test_a_website_link_that_is_not_a_url_is_refused(account_admin_client: APIClient) -> None:
    """A typo in the address is caught here rather than on the public page."""
    response = account_admin_client.post(
        LIST_URL,
        {"name": "Palo Alto", "airport_identifiers": "PAO", "website_url": "paloaltodart"},
        format="json",
    )
    assert response.status_code == 400
    assert "website_url" in response.json()


@pytest.mark.parametrize(("slug", "allowed"), role_matrix(ACCOUNT_ADMIN, SYSTEM_ADMIN))
def test_role_matrix_for_delete(
    api_client: APIClient, all_role_users: dict[str, User], slug: str, allowed: bool
) -> None:
    """Only account and system admins delete a DART; every other role gets 403."""
    dart = DartFactory(name=f"Field {slug}")
    api_client.force_login(all_role_users[slug])
    assert api_client.delete(detail_url(dart)).status_code == (204 if allowed else 403)
