"""The people a DART lists: any number of them, and which of them receive the roster.

Covers the list having no cap, the ``receives_roster`` tick on each person, the
``roster_recipients`` count and ``roster_sent_at`` stamp the account administrator's
DART screen reads, the public catalog leaving the tick out, and the demo seed
ticking each team's leader and deputy leader.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from rest_framework.test import APIClient

from apps.darts.models import Dart, DartContact
from apps.members.seed import seed_darts
from tests.factories import DartContactFactory, DartFactory

pytestmark = pytest.mark.django_db

LIST_URL = "/api/v1/admin/darts"


def _people(count: int) -> list[dict[str, str]]:
    """``count`` contacts as the DART form posts them, numbered from 1."""
    return [
        {"name": f"Person {index}", "title": "Volunteer", "email": f"p{index}@example.test"}
        for index in range(1, count + 1)
    ]


def test_a_dart_lists_any_number_of_people(account_admin_client: APIClient) -> None:
    """Eight people are stored, all of them, in the order given."""
    response = account_admin_client.post(
        LIST_URL,
        {"name": "Napa", "airport_identifiers": "APC", "contacts": _people(8)},
        format="json",
    )

    assert response.status_code == 201, response.json()
    assert [contact["name"] for contact in response.json()["contacts"]] == [
        f"Person {index}" for index in range(1, 9)
    ]


def test_a_sixth_person_can_be_added_to_a_dart_of_five(account_admin_client: APIClient) -> None:
    """Editing a DART that already lists five people may add a sixth."""
    dart = DartFactory(name="Napa")
    for position in range(5):
        DartContactFactory(dart=dart, name=f"Person {position + 1}", sort_order=position)

    response = account_admin_client.patch(
        f"{LIST_URL}/{dart.pk}", {"contacts": _people(6)}, format="json"
    )

    assert response.status_code == 200, response.json()
    assert dart.contacts.count() == 6


def test_a_person_does_not_receive_the_roster_unless_ticked(
    account_admin_client: APIClient,
) -> None:
    """A contact posted without ``receives_roster`` is stored unticked."""
    response = account_admin_client.post(
        LIST_URL,
        {"name": "Napa", "airport_identifiers": "APC", "contacts": _people(1)},
        format="json",
    )

    assert response.json()["contacts"][0]["receives_roster"] is False


def test_the_roster_tick_is_stored_per_person(account_admin_client: APIClient) -> None:
    """Each person's tick is stored as given, and read back on the admin list."""
    contacts = _people(3)
    ticked = [
        {**contacts[0], "receives_roster": True},
        {**contacts[1], "receives_roster": False},
        {**contacts[2], "receives_roster": True},
    ]
    account_admin_client.post(
        LIST_URL,
        {"name": "Napa", "airport_identifiers": "APC", "contacts": ticked},
        format="json",
    )

    row = account_admin_client.get(LIST_URL).json()[0]

    assert [contact["receives_roster"] for contact in row["contacts"]] == [True, False, True]


def test_a_person_without_an_email_may_be_ticked(account_admin_client: APIClient) -> None:
    """The tick is accepted for a phone-only person; the sender skips them later."""
    response = account_admin_client.post(
        LIST_URL,
        {
            "name": "Napa",
            "airport_identifiers": "APC",
            "contacts": [
                {
                    "name": "Helen",
                    "title": "DART leader",
                    "phone": "707-555-0133",
                    "receives_roster": True,
                }
            ],
        },
        format="json",
    )

    assert response.status_code == 201, response.json()
    assert DartContact.objects.get().receives_roster is True


def test_roster_recipients_counts_ticked_people_with_an_email(
    account_admin_client: APIClient,
) -> None:
    """Only a ticked person with an address counts: unticked or address-less do not."""
    dart = DartFactory(name="Napa")
    DartContactFactory(dart=dart, receives_roster=True)
    DartContactFactory(dart=dart, receives_roster=True)
    DartContactFactory(dart=dart, receives_roster=True, email="")
    DartContactFactory(dart=dart, receives_roster=False)

    row = account_admin_client.get(LIST_URL).json()[0]

    assert row["roster_recipients"] == 2


def test_an_edit_answers_with_the_new_roster_count(account_admin_client: APIClient) -> None:
    """The PATCH response counts the people it just wrote, not the ones it replaced."""
    dart = DartFactory(name="Napa")
    DartContactFactory(dart=dart, receives_roster=True)
    contacts = [{**person, "receives_roster": True} for person in _people(3)]

    response = account_admin_client.patch(
        f"{LIST_URL}/{dart.pk}", {"contacts": contacts}, format="json"
    )

    assert response.json()["roster_recipients"] == 3


def test_a_dart_never_sent_a_roster_reads_null(account_admin_client: APIClient) -> None:
    """``roster_sent_at`` is null until a roster has gone out."""
    DartFactory(name="Napa")

    assert account_admin_client.get(LIST_URL).json()[0]["roster_sent_at"] is None


def test_the_admin_list_carries_when_the_roster_was_last_sent(
    account_admin_client: APIClient,
) -> None:
    """``roster_sent_at`` reads back the moment the last roster went out."""
    sent = datetime(2026, 9, 1, 13, 0, tzinfo=UTC)
    DartFactory(name="Napa", roster_sent_at=sent)

    row = account_admin_client.get(LIST_URL).json()[0]

    assert datetime.fromisoformat(row["roster_sent_at"]) == sent


def test_roster_sent_at_is_not_written_by_the_screen(account_admin_client: APIClient) -> None:
    """Only the sender stamps it: a PATCH that names it leaves it alone."""
    dart = DartFactory(name="Napa")

    account_admin_client.patch(
        f"{LIST_URL}/{dart.pk}", {"roster_sent_at": "2026-09-01T13:00:00Z"}, format="json"
    )

    dart.refresh_from_db()
    assert dart.roster_sent_at is None


def test_the_public_catalog_leaves_the_roster_tick_out(api_client: APIClient) -> None:
    """Who receives the roster is the administrator's business, not a visitor's."""
    dart = DartFactory(name="Napa")
    DartContactFactory(dart=dart, receives_roster=True)

    contact = api_client.get("/api/v1/darts").json()[0]["contacts"][0]

    assert "receives_roster" not in contact


def test_the_seed_ticks_each_dart_leader_and_deputy() -> None:
    """Every seeded DART sends its roster to its leader and its deputy leader."""
    seed_darts()

    for dart in Dart.objects.all():
        ticked = [contact.title for contact in dart.contacts.filter(receives_roster=True)]
        assert ticked == ["DART leader", "Deputy leader"], dart.name
