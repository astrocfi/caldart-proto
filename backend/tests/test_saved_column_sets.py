"""Named sets of a report's columns, saved per account.

``GET``, ``POST`` and ``DELETE /reports/{slug}/column-sets``: a caller sees and changes
only their own sets, saving under a name they already use replaces that set's columns,
the columns are checked against the report's registry, and a caller the report does
not admit is refused.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.reports.models import SavedColumnSet
from tests.conftest import role_matrix
from tests.factories import SavedColumnSetFactory

pytestmark = pytest.mark.django_db

MEMBERS_SETS_URL = "/api/v1/reports/members/column-sets"


def sets_url(slug: str) -> str:
    """The column-sets endpoint of the report ``slug``."""
    return f"/api/v1/reports/{slug}/column-sets"


def test_the_list_holds_only_the_callers_own_sets_for_that_report(
    account_admin_client: APIClient, account_admin: User, member: User
) -> None:
    """Another account's sets, and the caller's sets for another report, are left out."""
    own = SavedColumnSetFactory(user=account_admin, name="Roster", columns=["name", "phone"])
    SavedColumnSetFactory(user=member, name="Theirs")
    SavedColumnSetFactory(
        user=account_admin, report="aircraft", name="Planes", columns=["n_number"]
    )

    response = account_admin_client.get(MEMBERS_SETS_URL)

    assert response.json() == [{"id": own.pk, "name": "Roster", "columns": ["name", "phone"]}]


def test_the_list_is_ordered_by_name(account_admin_client: APIClient, account_admin: User) -> None:
    """Sets come back alphabetically, whatever order they were saved in."""
    SavedColumnSetFactory(user=account_admin, name="Zulu")
    SavedColumnSetFactory(user=account_admin, name="Alpha")

    names = [row["name"] for row in account_admin_client.get(MEMBERS_SETS_URL).json()]

    assert names == ["Alpha", "Zulu"]


def test_saving_a_new_name_creates_a_set(
    account_admin_client: APIClient, account_admin: User
) -> None:
    """A ``POST`` under a name the caller has not used answers 201 with the new set."""
    response = account_admin_client.post(
        MEMBERS_SETS_URL, {"name": "Roster", "columns": ["phone", "name"]}, format="json"
    )

    saved = SavedColumnSet.objects.get(user=account_admin, report="members")
    assert response.status_code == 201
    assert response.json() == {"id": saved.pk, "name": "Roster", "columns": ["phone", "name"]}


def test_saving_under_an_existing_name_replaces_its_columns(
    account_admin_client: APIClient, account_admin: User
) -> None:
    """The caller's set of that name keeps its id and takes the new columns."""
    existing = SavedColumnSetFactory(user=account_admin, name="Roster", columns=["name"])

    response = account_admin_client.post(
        MEMBERS_SETS_URL, {"name": "Roster", "columns": ["email", "dart"]}, format="json"
    )

    assert response.status_code == 201
    assert response.json() == {"id": existing.pk, "name": "Roster", "columns": ["email", "dart"]}


def test_saving_under_an_existing_name_leaves_one_set(
    account_admin_client: APIClient, account_admin: User
) -> None:
    """An overwrite does not add a second row."""
    SavedColumnSetFactory(user=account_admin, name="Roster", columns=["name"])

    account_admin_client.post(
        MEMBERS_SETS_URL, {"name": "Roster", "columns": ["email"]}, format="json"
    )

    assert SavedColumnSet.objects.filter(user=account_admin).count() == 1


def test_names_differing_only_in_case_are_two_sets(
    account_admin_client: APIClient, account_admin: User
) -> None:
    """The name is compared exactly, so ``roster`` does not replace ``Roster``."""
    SavedColumnSetFactory(user=account_admin, name="Roster", columns=["name"])

    account_admin_client.post(
        MEMBERS_SETS_URL, {"name": "roster", "columns": ["email"]}, format="json"
    )

    assert SavedColumnSet.objects.filter(user=account_admin).count() == 2


def test_another_accounts_set_of_the_same_name_is_left_alone(
    account_admin_client: APIClient, account_admin: User, dart_leader: User
) -> None:
    """Saving replaces only the caller's own set, never another account's."""
    theirs = SavedColumnSetFactory(user=dart_leader, name="Roster", columns=["name"])

    account_admin_client.post(
        MEMBERS_SETS_URL, {"name": "Roster", "columns": ["email"]}, format="json"
    )

    theirs.refresh_from_db()
    assert theirs.columns == ["name"]


@pytest.mark.parametrize(
    ("body", "errors"),
    [
        ({"name": "Bad", "columns": ["nope"]}, {"columns": ["Unknown column: nope"]}),
        ({"name": "Bad", "columns": ["name", "name"]}, {"columns": ["Repeated column: name"]}),
        ({"name": "Bad", "columns": []}, {"columns": ["Choose at least one column."]}),
        ({"name": "", "columns": ["name"]}, {"name": ["This field may not be blank."]}),
        (
            {"name": "x" * 61, "columns": ["name"]},
            {"name": ["Ensure this field has no more than 60 characters."]},
        ),
    ],
    ids=["unknown", "repeated", "empty", "blank-name", "long-name"],
)
def test_a_bad_set_is_refused_with_the_reason(
    account_admin_client: APIClient, body: dict[str, object], errors: dict[str, list[str]]
) -> None:
    """The columns are checked against the report's registry, and the name must fit."""
    response = account_admin_client.post(MEMBERS_SETS_URL, body, format="json")

    assert response.status_code == 400
    assert response.json() == errors


def test_a_report_with_fixed_columns_keeps_no_sets(treasurer_client: APIClient) -> None:
    """A fixed report has nothing to choose, so saving a set of its columns is refused."""
    response = treasurer_client.post(
        sets_url("contributions"), {"name": "Mine", "columns": ["name"]}, format="json"
    )

    assert response.status_code == 400
    assert response.json() == {"columns": ["This report's columns are fixed."]}


def test_deleting_removes_the_callers_own_set(
    account_admin_client: APIClient, account_admin: User
) -> None:
    """``DELETE`` answers 204 and the set is gone."""
    own = SavedColumnSetFactory(user=account_admin)

    response = account_admin_client.delete(f"{MEMBERS_SETS_URL}/{own.pk}")

    assert response.status_code == 204
    assert SavedColumnSet.objects.filter(pk=own.pk).exists() is False


def test_deleting_another_accounts_set_is_not_found(
    account_admin_client: APIClient, dart_leader: User
) -> None:
    """Another account's set answers 404 and survives."""
    theirs = SavedColumnSetFactory(user=dart_leader)

    response = account_admin_client.delete(f"{MEMBERS_SETS_URL}/{theirs.pk}")

    assert response.status_code == 404
    assert SavedColumnSet.objects.filter(pk=theirs.pk).exists() is True


def test_deleting_a_set_under_another_report_is_not_found(
    account_admin_client: APIClient, account_admin: User
) -> None:
    """A set is deleted through its own report's URL only."""
    own = SavedColumnSetFactory(user=account_admin, report="aircraft", columns=["n_number"])

    response = account_admin_client.delete(f"{MEMBERS_SETS_URL}/{own.pk}")

    assert response.status_code == 404


def test_an_unknown_report_is_not_found(account_admin_client: APIClient) -> None:
    """A slug the registry does not hold answers 404."""
    assert account_admin_client.get(sets_url("nothing")).status_code == 404


def test_an_anonymous_caller_is_refused(api_client: APIClient) -> None:
    """Saved sets belong to an account, so an anonymous caller answers 401."""
    assert api_client.get(MEMBERS_SETS_URL).status_code == 401


@pytest.mark.parametrize(
    ("role", "allowed"), role_matrix("dart_leader", "account_admin", "system_admin")
)
def test_the_members_report_sets_follow_the_reports_roles(
    api_client: APIClient, all_role_users: dict[str, User], role: str, allowed: bool
) -> None:
    """Only a caller who may read the report may keep sets of its columns."""
    api_client.force_login(all_role_users[role])

    response = api_client.get(MEMBERS_SETS_URL)

    assert response.status_code == (200 if allowed else 403)
