"""The aircraft register's change history.

Every write to a register record leaves one ``AircraftChange`` row saying who
changed it, when, and which columns moved, and stamps ``Aircraft.updated_by``.
``GET /aircraft/{id}/changes`` reads that trail back for an account
administrator.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import ACCOUNT_ADMIN, SYSTEM_ADMIN
from apps.aircraft.models import Aircraft, AircraftChange, AircraftChangeKind
from apps.aircraft.services import changed_fields, record_change
from tests.conftest import role_matrix
from tests.factories import AircraftChangeFactory, AircraftFactory, UserFactory

pytestmark = pytest.mark.django_db

LIST_URL = "/api/v1/aircraft"


def detail_url(aircraft: Aircraft) -> str:
    """``/aircraft/{id}`` for ``aircraft``."""
    return f"{LIST_URL}/{aircraft.pk}"


def changes_url(aircraft: Aircraft) -> str:
    """``/aircraft/{id}/changes`` for ``aircraft``."""
    return f"{LIST_URL}/{aircraft.pk}/changes"


def creation_payload() -> dict[str, object]:
    """A complete, valid body for ``POST /aircraft``."""
    return {
        "n_number": "N4321Q",
        "make": "Cirrus",
        "model": "SR22",
        "year": 2019,
        "owner_type": "individual",
        "owner_name": "Marta Reyes",
        "seats": 4,
    }


# --------------------------------------------------------------------------
# record_change and changed_fields
# --------------------------------------------------------------------------
def test_record_change_stamps_the_aircraft_with_the_actor(member: User) -> None:
    """``record_change`` writes ``updated_by`` on the record it logs."""
    aircraft = AircraftFactory(n_number="N11RC")
    record_change(aircraft, actor=member, kind=AircraftChangeKind.UPDATED, fields=["model"])
    aircraft.refresh_from_db()
    assert aircraft.updated_by == member


def test_record_change_writes_one_row_naming_the_fields(member: User) -> None:
    """The stored row carries the kind and the column names it was given."""
    aircraft = AircraftFactory(n_number="N12RC")
    change = record_change(
        aircraft, actor=member, kind=AircraftChangeKind.UPDATED, fields=["make", "model"]
    )
    assert change.fields == ["make", "model"]


def test_record_change_keeps_no_fields_for_a_creation(member: User) -> None:
    """A ``created`` row names no columns: the whole record is the change."""
    aircraft = AircraftFactory(n_number="N13RC")
    change = record_change(aircraft, actor=member, kind=AircraftChangeKind.CREATED, fields=[])
    assert change.fields == []


def test_record_change_accepts_no_actor() -> None:
    """A change with nobody signed in stores ``changed_by`` as null."""
    aircraft = AircraftFactory(n_number="N14RC")
    change = record_change(aircraft, actor=None, kind=AircraftChangeKind.CREATED, fields=[])
    assert change.changed_by is None


def test_changed_fields_names_only_the_columns_whose_value_moves() -> None:
    """A value equal to the stored one is not a change."""
    aircraft = AircraftFactory(n_number="N15RC", make="Cessna", model="182T Skylane")
    assert changed_fields(aircraft, {"make": "Cessna", "model": "SR22"}) == ["model"]


def test_changed_fields_is_empty_when_nothing_moves() -> None:
    """Resending the stored values names no column."""
    aircraft = AircraftFactory(n_number="N16RC", make="Cessna", model="182T Skylane")
    assert changed_fields(aircraft, {"make": "Cessna"}) == []


def test_changed_fields_ignores_a_key_the_model_does_not_carry() -> None:
    """A key that is not a concrete column, such as a relation, is left out."""
    aircraft = AircraftFactory(n_number="N17RC")
    assert changed_fields(aircraft, {"pilots": []}) == []


def test_a_change_row_orders_newest_first(member: User) -> None:
    """``AircraftChange`` reads newest first, so a history needs no ordering."""
    aircraft = AircraftFactory(n_number="N18RC")
    first = AircraftChangeFactory(aircraft=aircraft, changed_by=member)
    second = AircraftChangeFactory(aircraft=aircraft, changed_by=member)
    assert list(aircraft.changes.all()) == [second, first]


def test_deleting_an_aircraft_deletes_its_history(member: User) -> None:
    """The history is part of the record, so it goes with it."""
    aircraft = AircraftFactory(n_number="N19RC")
    AircraftChangeFactory(aircraft=aircraft, changed_by=member)
    aircraft.delete()
    assert AircraftChange.objects.count() == 0


def test_deleting_the_actor_keeps_the_change(member: User) -> None:
    """An account that goes away leaves its changes behind, unattributed."""
    aircraft = AircraftFactory(n_number="N20RC")
    change = AircraftChangeFactory(aircraft=aircraft, changed_by=member)
    member.delete()
    change.refresh_from_db()
    assert change.changed_by is None


def test_a_change_reads_as_the_registration_and_the_kind(member: User) -> None:
    """``str`` names the aircraft and what happened to it."""
    aircraft = AircraftFactory(n_number="N21RC")
    change = AircraftChangeFactory(
        aircraft=aircraft, changed_by=member, kind=AircraftChangeKind.CREATED
    )
    assert str(change) == "N21RC created"


# --------------------------------------------------------------------------
# The register's writes
# --------------------------------------------------------------------------
def test_creating_an_aircraft_records_a_created_change(api_client: APIClient, member: User) -> None:
    """``POST /aircraft`` leaves a ``created`` row attributed to the caller."""
    api_client.force_login(member)
    response = api_client.post(LIST_URL, creation_payload())
    assert response.status_code == 201
    change = AircraftChange.objects.get(aircraft_id=response.json()["id"])
    assert change.kind == AircraftChangeKind.CREATED


def test_a_created_change_names_no_fields(api_client: APIClient, member: User) -> None:
    """Nothing "changed" on a creation, so the row's field list is empty."""
    api_client.force_login(member)
    response = api_client.post(LIST_URL, creation_payload())
    change = AircraftChange.objects.get(aircraft_id=response.json()["id"])
    assert change.fields == []


def test_creating_an_aircraft_stamps_updated_by(api_client: APIClient, member: User) -> None:
    """The record's last writer is the member who added it."""
    api_client.force_login(member)
    response = api_client.post(LIST_URL, creation_payload())
    assert Aircraft.objects.get(pk=response.json()["id"]).updated_by == member


def test_patching_an_aircraft_records_the_changed_fields(
    api_client: APIClient, account_admin: User
) -> None:
    """The row names the columns whose value the body actually moved."""
    aircraft = AircraftFactory(n_number="N30PA", make="Cessna", model="182T Skylane")
    api_client.force_login(account_admin)
    response = api_client.patch(detail_url(aircraft), {"make": "Cessna", "model": "SR22"})
    assert response.status_code == 200
    assert AircraftChange.objects.get(aircraft=aircraft).fields == ["model"]


def test_patching_an_aircraft_records_an_updated_change(
    api_client: APIClient, account_admin: User
) -> None:
    """An edit is an ``updated`` row, not a second ``created`` one."""
    aircraft = AircraftFactory(n_number="N31PA")
    api_client.force_login(account_admin)
    api_client.patch(detail_url(aircraft), {"model": "SR22"})
    assert AircraftChange.objects.get(aircraft=aircraft).kind == AircraftChangeKind.UPDATED


def test_patching_an_aircraft_stamps_the_editor(api_client: APIClient, account_admin: User) -> None:
    """``updated_by`` follows the last editor, not the creator."""
    creator = UserFactory(email="creator@example.test")
    aircraft = AircraftFactory(n_number="N32PA", created_by=creator)
    api_client.force_login(account_admin)
    api_client.patch(detail_url(aircraft), {"model": "SR22"})
    aircraft.refresh_from_db()
    assert aircraft.updated_by == account_admin


def test_putting_an_aircraft_records_the_changed_fields(
    api_client: APIClient, account_admin: User
) -> None:
    """A ``PUT`` is recorded on the same terms as a ``PATCH``."""
    aircraft = AircraftFactory(n_number="N33PA", make="Cessna", model="182T Skylane")
    api_client.force_login(account_admin)
    response = api_client.put(
        detail_url(aircraft), {"n_number": "N33PA", "make": "Cessna", "model": "SR22"}
    )
    assert response.status_code == 200
    assert AircraftChange.objects.get(aircraft=aircraft).fields == ["model"]


def test_a_refused_edit_records_nothing(api_client: APIClient, member: User) -> None:
    """A 403 leaves no trail: nothing was changed."""
    aircraft = AircraftFactory(n_number="N34PA", created_by=UserFactory(email="other@example.test"))
    api_client.force_login(member)
    assert api_client.patch(detail_url(aircraft), {"model": "SR22"}).status_code == 403
    assert AircraftChange.objects.count() == 0


def test_an_invalid_edit_records_nothing(api_client: APIClient, account_admin: User) -> None:
    """A 400 leaves no trail either."""
    aircraft = AircraftFactory(n_number="N35PA")
    api_client.force_login(account_admin)
    assert api_client.patch(detail_url(aircraft), {"make": ""}).status_code == 400
    assert AircraftChange.objects.count() == 0


# --------------------------------------------------------------------------
# The history endpoint
# --------------------------------------------------------------------------
def test_the_history_requires_authentication(api_client: APIClient) -> None:
    """An anonymous caller gets a 401, not a history."""
    aircraft = AircraftFactory(n_number="N40HI")
    assert api_client.get(changes_url(aircraft)).status_code == 401


@pytest.mark.parametrize(("slug", "allowed"), role_matrix(ACCOUNT_ADMIN, SYSTEM_ADMIN))
def test_history_role_matrix(
    api_client: APIClient, all_role_users: dict[str, User], slug: str, allowed: bool
) -> None:
    """Only an account or system administrator reads who changed a record."""
    aircraft = AircraftFactory(n_number="N41HI")
    api_client.force_login(all_role_users[slug])
    assert api_client.get(changes_url(aircraft)).status_code == (200 if allowed else 403)


def test_the_history_404s_for_an_unknown_aircraft(
    api_client: APIClient, account_admin: User
) -> None:
    """An id no aircraft carries is a 404."""
    api_client.force_login(account_admin)
    assert api_client.get(f"{LIST_URL}/999999/changes").status_code == 404


def test_the_history_is_empty_for_a_record_nobody_has_touched(
    api_client: APIClient, account_admin: User
) -> None:
    """A seeded record with no writes since reads as an empty list."""
    aircraft = AircraftFactory(n_number="N42HI")
    api_client.force_login(account_admin)
    assert api_client.get(changes_url(aircraft)).json() == []


def test_the_history_is_newest_first(api_client: APIClient, account_admin: User) -> None:
    """The most recent change is the first row."""
    aircraft = AircraftFactory(n_number="N43HI")
    AircraftChangeFactory(aircraft=aircraft, kind=AircraftChangeKind.CREATED)
    latest = AircraftChangeFactory(aircraft=aircraft, kind=AircraftChangeKind.UPDATED)
    api_client.force_login(account_admin)
    rows = api_client.get(changes_url(aircraft)).json()
    assert rows[0]["id"] == latest.pk


def test_the_history_is_not_paginated(api_client: APIClient, account_admin: User) -> None:
    """An aircraft has few changes, so the response is a bare array."""
    aircraft = AircraftFactory(n_number="N44HI")
    AircraftChangeFactory(aircraft=aircraft)
    api_client.force_login(account_admin)
    assert isinstance(api_client.get(changes_url(aircraft)).json(), list)


def test_a_history_row_names_the_actor(api_client: APIClient, fixed_name_admin: User) -> None:
    """``changed_by`` carries the account's id and display name."""
    aircraft = AircraftFactory(n_number="N45HI")
    AircraftChangeFactory(aircraft=aircraft, changed_by=fixed_name_admin)
    api_client.force_login(fixed_name_admin)
    row = api_client.get(changes_url(aircraft)).json()[0]
    assert row["changed_by"] == {"id": fixed_name_admin.pk, "name": fixed_name_admin.display_name}


def test_a_history_row_with_no_actor_reads_null(api_client: APIClient, account_admin: User) -> None:
    """A change the seed or a command made carries no account."""
    aircraft = AircraftFactory(n_number="N46HI")
    AircraftChangeFactory(aircraft=aircraft, changed_by=None)
    api_client.force_login(account_admin)
    assert api_client.get(changes_url(aircraft)).json()[0]["changed_by"] is None


def test_a_history_row_carries_the_kind_and_the_fields(
    api_client: APIClient, account_admin: User
) -> None:
    """The row says what happened and to which columns."""
    aircraft = AircraftFactory(n_number="N47HI")
    AircraftChangeFactory(
        aircraft=aircraft,
        kind=AircraftChangeKind.UPDATED,
        fields=["insurance_carrier", "insurance_expiration"],
    )
    api_client.force_login(account_admin)
    row = api_client.get(changes_url(aircraft)).json()[0]
    assert row["fields"] == ["insurance_carrier", "insurance_expiration"]


def test_a_history_row_carries_the_timestamp(api_client: APIClient, account_admin: User) -> None:
    """``changed_at`` is the moment the change was written."""
    aircraft = AircraftFactory(n_number="N48HI")
    change = AircraftChangeFactory(aircraft=aircraft)
    api_client.force_login(account_admin)
    row = api_client.get(changes_url(aircraft)).json()[0]
    assert datetime.fromisoformat(row["changed_at"]) == change.changed_at


def test_the_history_covers_one_aircraft_only(api_client: APIClient, account_admin: User) -> None:
    """Another airframe's changes do not appear in this one's history."""
    aircraft = AircraftFactory(n_number="N49HI")
    other = AircraftFactory(n_number="N50HI")
    AircraftChangeFactory(aircraft=other)
    api_client.force_login(account_admin)
    assert api_client.get(changes_url(aircraft)).json() == []
