"""Saved recipient groups: fixed and live, added to a batch, and saved from a batch.

A fixed group holds its accounts unchanged until somebody adds or removes one; a live
group holds filter sets that run afresh on each use.  Adding a group to a batch merges
it with the same handling of people already there as any add, and the add is named
after the group.  Deleting a group leaves every batch it was added to as it was.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import AccountKind
from apps.accounts.roles import MANAGEMENT, SYSTEM_ADMIN
from apps.bulk_email import batch, groups, job
from apps.bulk_email.models import (
    BatchAdd,
    BulkEmail,
    BulkEmailStatus,
    GroupKind,
    RecipientGroup,
    RecipientStatus,
)
from apps.bulk_email.templates import duplicate
from caldart.exceptions import DomainError, DomainValidationError
from tests.conftest import read_csv, role_matrix
from tests.factories import (
    BulkEmailFactory,
    DartFactory,
    add_to_batch,
    make_group,
    make_person,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from apps.accounts.models import User
    from apps.darts.models import Dart

pytestmark = pytest.mark.django_db

GROUPS_URL = "/api/v1/bulk-email/groups"
FRIENDS_IN_MARIN = {"kind": "friend", "county": "Marin"}
NAPA = {"county": "Napa"}


def group_url(group: RecipientGroup, path: str = "") -> str:
    """``/api/v1/bulk-email/groups/{id}`` and ``path`` for ``group``."""
    return f"{GROUPS_URL}/{group.pk}{path}"


def emails(accounts: Iterable[User]) -> list[str]:
    """The addresses of ``accounts``, in order."""
    return [account.email for account in accounts]


def batch_emails(bulk: BulkEmail) -> list[str]:
    """Everybody in ``bulk``'s batch, by address, in send order."""
    return [row.recipient.email for row in batch.batch_rows(bulk)]


@pytest.fixture(autouse=True)
def _no_pause(monkeypatch: pytest.MonkeyPatch) -> None:
    """Take the pacing's pause out, so a run sends at once."""
    monkeypatch.setattr(job, "sleep", lambda seconds: None)


@pytest.fixture
def bulk(management: User) -> BulkEmail:
    """A draft from CalDART management with an empty batch."""
    return BulkEmailFactory(sender=management)


@pytest.fixture
def marin_dart() -> Dart:
    """The Marin DART."""
    return DartFactory(name="Marin DART")


@pytest.fixture
def ann(marin_dart: Dart) -> User:
    """Ann Able, a friend in Marin and the Marin DART."""
    return make_person("ann@example.test", "Ann", "Able", kind=AccountKind.FRIEND, dart=marin_dart)


@pytest.fixture
def bob(marin_dart: Dart) -> User:
    """Bob Burns, a friend in Marin and the Marin DART."""
    return make_person("bob@example.test", "Bob", "Burns", kind=AccountKind.FRIEND, dart=marin_dart)


@pytest.fixture
def board(ann: User, bob: User) -> RecipientGroup:
    """The Board, a fixed group of Ann and Bob."""
    return make_group("Board", people=(ann, bob))


@pytest.fixture
def marin_friends() -> RecipientGroup:
    """Marin friends, a live group of every friend in Marin."""
    return make_group("Marin friends", filter_sets=(FRIENDS_IN_MARIN,))


# --------------------------------------------------------------------------
# Who a group holds
# --------------------------------------------------------------------------
def test_a_fixed_group_holds_its_accounts(board: RecipientGroup) -> None:
    """A fixed group's people are its accounts, in surname order."""
    assert emails(groups.group_accounts(board)) == ["ann@example.test", "bob@example.test"]


def test_a_fixed_group_holds_its_accounts_unchanged(board: RecipientGroup) -> None:
    """Somebody who would match the same filters later does not join a fixed group."""
    make_person("cal@example.test", "Cal", "Cole", kind=AccountKind.FRIEND)
    assert emails(groups.group_accounts(board)) == ["ann@example.test", "bob@example.test"]


def test_a_live_group_re_runs_its_filters(ann: User, marin_friends: RecipientGroup) -> None:
    """Somebody who matches the filters later is in a live group the next time."""
    make_person("cal@example.test", "Cal", "Cole", kind=AccountKind.FRIEND)
    assert emails(groups.group_accounts(marin_friends)) == [
        "ann@example.test",
        "cal@example.test",
    ]


def test_a_live_group_drops_somebody_who_stops_matching(
    ann: User, bob: User, marin_friends: RecipientGroup
) -> None:
    """A person whose county changes leaves a live group of a county."""
    bob.profile.county = "Napa"
    bob.profile.save()
    assert emails(groups.group_accounts(marin_friends)) == ["ann@example.test"]


def test_a_live_group_is_the_union_of_its_filter_sets(ann: User) -> None:
    """Each filter set adds the people it chooses; nobody is there twice."""
    make_person("ned@example.test", "Ned", "Noble", county="Napa")
    group = make_group("Two counties", filter_sets=(FRIENDS_IN_MARIN, NAPA, FRIENDS_IN_MARIN))
    assert emails(groups.group_accounts(group)) == ["ann@example.test", "ned@example.test"]


def test_a_live_group_without_filters_holds_nobody(ann: User) -> None:
    """A live group whose filter sets were all taken out is empty, not everybody."""
    group = make_group("Empty", filter_sets=(FRIENDS_IN_MARIN,))
    group.filter_sets.all().delete()
    assert emails(groups.group_accounts(group)) == []


def test_deleting_an_account_takes_it_out_of_a_fixed_group(
    ann: User, board: RecipientGroup
) -> None:
    """The group keeps everybody else."""
    ann.delete()
    assert emails(groups.group_accounts(board)) == ["bob@example.test"]


# --------------------------------------------------------------------------
# Adding a group to a batch
# --------------------------------------------------------------------------
def test_adding_a_group_puts_its_people_in_the_batch(
    bulk: BulkEmail, management: User, board: RecipientGroup
) -> None:
    """Everybody in the group joins the batch."""
    groups.add_group(bulk, board, actor=management)
    assert batch_emails(bulk) == ["ann@example.test", "bob@example.test"]


def test_adding_a_group_merges_without_duplicates(
    bulk: BulkEmail, management: User, ann: User, board: RecipientGroup
) -> None:
    """Somebody in the batch already is counted, not added twice."""
    batch.add_filters(bulk, {"search": "ann@example.test"}, actor=management)
    result = groups.add_group(bulk, board, actor=management)
    assert result == batch.AddResult(added=1, already_present=1, count=2)


def test_a_group_add_is_named_after_the_group(
    management_client: APIClient, bulk: BulkEmail, board: RecipientGroup
) -> None:
    """The batch's add reads ``Group: <name>`` and links the group."""
    management_client.post(
        f"/api/v1/bulk-email/{bulk.pk}/batch/add-group", {"group": board.pk}, format="json"
    )
    adds = management_client.get(f"/api/v1/bulk-email/{bulk.pk}/batch").json()["adds"]
    assert [(add["label"], add["group"]) for add in adds] == [("Group: Board", board.pk)]


def test_the_batch_csv_names_the_group_that_chose_each_person(
    management_client: APIClient, bulk: BulkEmail, management: User, board: RecipientGroup
) -> None:
    """The *Chosen by* column carries the group's add label."""
    groups.add_group(bulk, board, actor=management)
    rows = read_csv(management_client.get(f"/api/v1/bulk-email/{bulk.pk}/batch.csv"))
    assert [row[5] for row in rows[1:]] == ["Group: Board", "Group: Board"]


def test_adding_a_live_group_uses_whoever_matches_now(
    bulk: BulkEmail, management: User, ann: User, marin_friends: RecipientGroup
) -> None:
    """A live group's add runs its filters at the moment it is added."""
    make_person("cal@example.test", "Cal", "Cole", kind=AccountKind.FRIEND)
    groups.add_group(bulk, marin_friends, actor=management)
    assert batch_emails(bulk) == ["ann@example.test", "cal@example.test"]


def test_adding_a_group_to_a_queued_email_takes_it_back_to_a_draft(
    management: User, board: RecipientGroup
) -> None:
    """As any change to the batch does."""
    queued = BulkEmailFactory(sender=management, status=BulkEmailStatus.QUEUED)
    groups.add_group(queued, board, actor=management)
    queued.refresh_from_db()
    assert queued.status == BulkEmailStatus.DRAFT


def test_a_group_cannot_be_added_to_an_email_that_has_started(
    management_client: APIClient, management: User, board: RecipientGroup
) -> None:
    """Once an email has started sending, its batch does not change: 409."""
    started = BulkEmailFactory(
        sender=management,
        status=BulkEmailStatus.SENT,
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    response = management_client.post(
        f"/api/v1/bulk-email/{started.pk}/batch/add-group", {"group": board.pk}, format="json"
    )
    assert response.status_code == 409


def test_adding_an_unknown_group_is_refused(management_client: APIClient, bulk: BulkEmail) -> None:
    """A group id nobody has is a 400 keyed ``group``."""
    response = management_client.post(
        f"/api/v1/bulk-email/{bulk.pk}/batch/add-group", {"group": 9999}, format="json"
    )
    assert response.status_code == 400
    assert list(response.json()) == ["group"]


def test_deleting_a_group_leaves_a_sent_emails_history(
    management_client: APIClient, bulk: BulkEmail, management: User, board: RecipientGroup
) -> None:
    """The people and the add's name stay with the send once the group is deleted."""
    groups.add_group(bulk, board, actor=management)
    bulk.status = BulkEmailStatus.QUEUED
    bulk.start_at = datetime(2026, 1, 1, tzinfo=UTC)
    bulk.save()
    job.run_sender()
    assert management_client.delete(group_url(board)).status_code == 204
    adds = management_client.get(f"/api/v1/bulk-email/{bulk.pk}/batch").json()["adds"]
    assert [(add["label"], add["group"]) for add in adds] == [("Group: Board", None)]
    assert list(bulk.recipients.values_list("status", flat=True)) == [
        RecipientStatus.SENT,
        RecipientStatus.SENT,
    ]


def test_renaming_a_group_leaves_the_name_its_adds_were_made_under(
    management_client: APIClient, bulk: BulkEmail, management: User, board: RecipientGroup
) -> None:
    """An add keeps the name the group had when it was added."""
    groups.add_group(bulk, board, actor=management)
    management_client.patch(group_url(board), {"name": "Directors"}, format="json")
    assert BatchAdd.objects.get(bulk_email=bulk).label == "Group: Board"


# --------------------------------------------------------------------------
# Saving a batch as a group
# --------------------------------------------------------------------------
def test_saving_a_batch_as_a_fixed_group_keeps_its_accounts(
    management_client: APIClient, bulk: BulkEmail, ann: User, bob: User
) -> None:
    """A fixed group holds everybody in the batch, skipped or not."""
    bob.is_active = False
    bob.save()
    add_to_batch(bulk, ann, bob)
    response = management_client.post(
        f"/api/v1/bulk-email/{bulk.pk}/save-group",
        {"name": "Hangar crew", "kind": "fixed"},
        format="json",
    )
    assert response.status_code == 201
    assert (response.json()["kind"], response.json()["count"]) == ("fixed", 2)


def test_saving_a_batch_as_a_live_group_keeps_its_filters(
    bulk: BulkEmail, management: User, ann: User
) -> None:
    """A live group holds each add's filters once, in the order they were added."""
    batch.add_filters(bulk, FRIENDS_IN_MARIN, actor=management)
    batch.add_filters(bulk, NAPA, actor=management)
    batch.add_filters(bulk, FRIENDS_IN_MARIN, actor=management)
    group = groups.save_group(bulk, name="Mixed", kind=GroupKind.LIVE, actor=management)
    assert [filter_set.filters for filter_set in group.filter_sets.all()] == [
        FRIENDS_IN_MARIN,
        NAPA,
    ]


def test_saving_a_live_group_takes_in_the_filters_of_a_live_group_added(
    bulk: BulkEmail, management: User, ann: User, marin_friends: RecipientGroup
) -> None:
    """A live group added to the batch contributes its own filter sets."""
    groups.add_group(bulk, marin_friends, actor=management)
    batch.add_filters(bulk, NAPA, actor=management)
    group = groups.save_group(bulk, name="Mixed", kind=GroupKind.LIVE, actor=management)
    assert [filter_set.filters for filter_set in group.filter_sets.all()] == [
        FRIENDS_IN_MARIN,
        NAPA,
    ]


def test_a_batch_with_a_fixed_group_cannot_be_saved_as_a_live_group(
    management_client: APIClient, bulk: BulkEmail, management: User, board: RecipientGroup
) -> None:
    """A fixed group's people have no filters to keep: 400 keyed ``batch``."""
    groups.add_group(bulk, board, actor=management)
    response = management_client.post(
        f"/api/v1/bulk-email/{bulk.pk}/save-group",
        {"name": "Mixed", "kind": "live"},
        format="json",
    )
    assert response.status_code == 400
    assert response.json() == {"batch": [groups.NO_FILTERS_MESSAGE]}


def test_a_batch_copied_from_another_email_cannot_be_saved_as_a_live_group(
    management: User, ann: User
) -> None:
    """People copied by **Duplicate** have no filters behind them."""
    original = BulkEmailFactory(sender=management)
    add_to_batch(original, ann)
    copy = duplicate(original, actor=management, copy_recipients=True)
    with pytest.raises(DomainValidationError, match="no filters to save"):
        groups.save_group(copy, name="Copy", kind=GroupKind.LIVE, actor=management)


def test_an_empty_batch_cannot_be_saved_as_a_group(
    management_client: APIClient, bulk: BulkEmail
) -> None:
    """There is nobody to save: 400 keyed ``batch``."""
    response = management_client.post(
        f"/api/v1/bulk-email/{bulk.pk}/save-group",
        {"name": "Nobody", "kind": "fixed"},
        format="json",
    )
    assert response.status_code == 400
    assert response.json() == {"batch": [groups.EMPTY_BATCH_MESSAGE]}


def test_a_group_name_is_unique_ignoring_case(
    management_client: APIClient, bulk: BulkEmail, ann: User, board: RecipientGroup
) -> None:
    """Saving under a name another group has is refused."""
    add_to_batch(bulk, ann)
    response = management_client.post(
        f"/api/v1/bulk-email/{bulk.pk}/save-group",
        {"name": "board", "kind": "fixed"},
        format="json",
    )
    assert response.status_code == 400
    assert response.json() == {
        "name": ['A group named "board" already exists. Choose another name.']
    }


# --------------------------------------------------------------------------
# The Recipient groups screen
# --------------------------------------------------------------------------
def test_the_list_holds_every_group_with_its_count_now(
    management_client: APIClient, ann: User, board: RecipientGroup, marin_friends: RecipientGroup
) -> None:
    """Each group's count is how many it holds now, a live group's filters run afresh."""
    make_person("cal@example.test", "Cal", "Cole", kind=AccountKind.FRIEND)
    rows = management_client.get(GROUPS_URL).json()
    assert [(row["name"], row["kind"], row["count"]) for row in rows] == [
        ("Board", "fixed", 2),
        ("Marin friends", "live", 3),
    ]


def test_a_live_group_lists_its_filter_sets_in_words(
    management_client: APIClient, marin_friends: RecipientGroup
) -> None:
    """Each filter set reads as the batch names an add."""
    sets = management_client.get(group_url(marin_friends)).json()["filter_sets"]
    assert [filter_set["label"] for filter_set in sets] == ["Kind: Friends only, County: Marin"]


def test_making_an_empty_group(management_client: APIClient, management: User) -> None:
    """``POST`` makes a group with nobody and no filters in it."""
    response = management_client.post(
        GROUPS_URL, {"name": "Seminar", "kind": "live"}, format="json"
    )
    assert response.status_code == 201
    assert (response.json()["count"], response.json()["created_by"]) == (
        0,
        management.display_name,
    )


def test_renaming_a_group(management_client: APIClient, board: RecipientGroup) -> None:
    """``PATCH`` with a name renames it."""
    management_client.patch(group_url(board), {"name": "Directors"}, format="json")
    board.refresh_from_db()
    assert board.name == "Directors"


def test_a_groups_kind_cannot_change(management_client: APIClient, board: RecipientGroup) -> None:
    """A fixed group stays fixed."""
    response = management_client.patch(group_url(board), {"kind": "live"}, format="json")
    assert response.status_code == 400
    assert response.json() == {"kind": ["A group's kind cannot change. Save a new group instead."]}


def test_a_groups_people_are_listed_with_their_dart(
    management_client: APIClient, ann: User, board: RecipientGroup
) -> None:
    """``GET .../members`` lists everybody in the group now, with the count."""
    body = management_client.get(group_url(board, "/members")).json()
    assert body["count"] == 2
    assert body["people"][0] == {
        "user_id": ann.pk,
        "name": "Ann Able",
        "email": "ann@example.test",
        "kind": "friend",
        "dart_name": "Marin DART",
        "is_active": True,
    }


def test_a_groups_people_download_as_a_csv(
    management_client: APIClient, board: RecipientGroup
) -> None:
    """The CSV lists everybody in the group, named for the group's id."""
    response = management_client.get(group_url(board, "/members.csv"))
    assert response["Content-Disposition"] == (
        f'attachment; filename="caldart-recipient-group-{board.pk}.csv"'
    )
    assert read_csv(response) == [
        ["Name", "Email", "Kind", "DART"],
        ["Ann Able", "ann@example.test", "Friend", "Marin DART"],
        ["Bob Burns", "bob@example.test", "Friend", "Marin DART"],
    ]


def test_adding_a_person_to_a_fixed_group(
    management_client: APIClient, board: RecipientGroup
) -> None:
    """``POST .../members`` puts the account in the group."""
    cal = make_person("cal@example.test", "Cal", "Cole")
    response = management_client.post(group_url(board, "/members"), {"user": cal.pk}, format="json")
    assert response.status_code == 201
    assert emails(groups.group_accounts(board))[-1] == "cal@example.test"


def test_adding_somebody_in_the_group_already_is_refused(
    management_client: APIClient, ann: User, board: RecipientGroup
) -> None:
    """Nobody is in a group twice."""
    response = management_client.post(group_url(board, "/members"), {"user": ann.pk}, format="json")
    assert response.status_code == 400
    assert response.json() == {"user": ["Ann Able is in this group already."]}


def test_a_donor_cannot_join_a_group(
    management_client: APIClient, board: RecipientGroup, user_factory: type
) -> None:
    """Only a member or a friend can be in a group."""
    donor = user_factory(email="dee@example.test", kind=AccountKind.DONOR)
    response = management_client.post(
        group_url(board, "/members"), {"user": donor.pk}, format="json"
    )
    assert response.status_code == 400
    assert response.json() == {"user": ["Choose a member or a friend."]}


def test_removing_a_person_from_a_fixed_group(
    management_client: APIClient, ann: User, board: RecipientGroup
) -> None:
    """``DELETE .../members/{user_id}`` takes them out."""
    response = management_client.delete(group_url(board, f"/members/{ann.pk}"))
    assert response.status_code == 204
    assert emails(groups.group_accounts(board)) == ["bob@example.test"]


def test_removing_somebody_not_in_the_group_is_not_found(
    management_client: APIClient, board: RecipientGroup
) -> None:
    """An account that is not in the group is a 404."""
    cal = make_person("cal@example.test")
    assert management_client.delete(group_url(board, f"/members/{cal.pk}")).status_code == 404


def test_a_live_group_has_no_people_to_add(
    management_client: APIClient, ann: User, marin_friends: RecipientGroup
) -> None:
    """People are added to a fixed group only: 409."""
    response = management_client.post(
        group_url(marin_friends, "/members"), {"user": ann.pk}, format="json"
    )
    assert response.status_code == 409
    assert response.json() == {"detail": groups.NOT_FIXED_MESSAGE}


def test_adding_a_filter_set_to_a_live_group(
    management_client: APIClient, marin_friends: RecipientGroup
) -> None:
    """``POST .../filters`` adds a set after the others."""
    response = management_client.post(
        group_url(marin_friends, "/filters"), {"filters": {**NAPA, "search": ""}}, format="json"
    )
    assert response.status_code == 201
    assert [filter_set.filters for filter_set in marin_friends.filter_sets.all()] == [
        FRIENDS_IN_MARIN,
        NAPA,
    ]


def test_a_filter_the_member_list_refuses_is_refused(
    management_client: APIClient, marin_friends: RecipientGroup
) -> None:
    """A filter that is not the member list's is a 400 keyed ``filters``."""
    response = management_client.post(
        group_url(marin_friends, "/filters"), {"filters": {"colour": "red"}}, format="json"
    )
    assert response.status_code == 400
    assert response.json() == {"filters": {"colour": ["Not a filter of the member list."]}}


def test_removing_a_filter_set_from_a_live_group(
    management_client: APIClient, marin_friends: RecipientGroup
) -> None:
    """``DELETE .../filters/{fid}`` takes the set out."""
    filter_set = marin_friends.filter_sets.get()
    response = management_client.delete(group_url(marin_friends, f"/filters/{filter_set.pk}"))
    assert response.status_code == 204
    assert not marin_friends.filter_sets.exists()


def test_a_fixed_group_has_no_filters_to_add(
    management_client: APIClient, board: RecipientGroup
) -> None:
    """Filter sets belong to a live group only: 409."""
    response = management_client.post(
        group_url(board, "/filters"), {"filters": NAPA}, format="json"
    )
    assert response.status_code == 409
    assert response.json() == {"detail": groups.NOT_LIVE_MESSAGE}


def test_changing_a_groups_people_moves_its_last_edited_time(board: RecipientGroup) -> None:
    """Adding somebody counts as an edit of the group."""
    before = board.updated_at
    groups.add_member(board, make_person("cal@example.test").pk)
    board.refresh_from_db()
    assert board.updated_at > before


def test_the_people_search_finds_members_and_friends(
    management_client: APIClient, ann: User
) -> None:
    """The search reads as the member list's, by name or address."""
    response = management_client.get(f"{GROUPS_URL}/people", {"search": "able"})
    assert response.json() == [{"id": ann.pk, "name": "Ann Able", "email": "ann@example.test"}]


def test_a_blank_people_search_finds_nobody(management_client: APIClient, ann: User) -> None:
    """Nothing typed, nothing found."""
    assert management_client.get(f"{GROUPS_URL}/people", {"search": " "}).json() == []


def test_the_delete_does_not_touch_sending_rules_for_other_groups(
    board: RecipientGroup, marin_friends: RecipientGroup
) -> None:
    """Deleting one group leaves every other group as it was."""
    board.delete()
    assert list(RecipientGroup.objects.values_list("name", flat=True)) == ["Marin friends"]


def test_removing_a_member_from_a_live_group_is_refused(
    ann: User, marin_friends: RecipientGroup
) -> None:
    """A live group has no list of people to take somebody out of."""
    with pytest.raises(DomainError, match="Only a fixed group lists its people"):
        groups.remove_member(marin_friends, ann.pk)


# --------------------------------------------------------------------------
# Who may
# --------------------------------------------------------------------------
@pytest.mark.parametrize(("role", "allowed"), role_matrix(MANAGEMENT, SYSTEM_ADMIN))
@pytest.mark.parametrize(
    ("method", "path", "payload", "code"),
    [
        ("get", "", None, 200),
        ("post", "", {"name": "Fresh", "kind": "fixed"}, 201),
        ("get", "/people?search=able", None, 200),
        ("get", "/{id}", None, 200),
        ("patch", "/{id}", {"name": "Renamed"}, 200),
        ("delete", "/{id}", None, 204),
        ("get", "/{id}/members", None, 200),
        ("get", "/{id}/members.csv", None, 200),
        ("post", "/{id}/members", {"user": "{cal}"}, 201),
        ("delete", "/{id}/members/{ann}", None, 204),
    ],
    ids=[
        "list",
        "create",
        "people",
        "read",
        "update",
        "delete",
        "members",
        "csv",
        "add-member",
        "remove-member",
    ],
)
def test_only_management_reaches_the_groups(
    api_client: APIClient,
    all_role_users: dict[str, User],
    ann: User,
    board: RecipientGroup,
    role: str,
    allowed: bool,
    method: str,
    path: str,
    payload: dict[str, str] | None,
    code: int,
) -> None:
    """Recipient groups are CalDART management's and the system administrator's alone."""
    cal = make_person("cal@example.test")
    if payload is not None:
        payload = {key: value.format(cal=cal.pk) for key, value in payload.items()}
    api_client.force_login(all_role_users[role])
    url = f"{GROUPS_URL}{path.format(id=board.pk, ann=ann.pk)}"
    response = getattr(api_client, method)(url, payload, format="json")
    assert response.status_code == (code if allowed else 403)


@pytest.mark.parametrize(("role", "allowed"), role_matrix(MANAGEMENT, SYSTEM_ADMIN))
@pytest.mark.parametrize(
    ("method", "path", "payload", "code"),
    [
        ("post", "/{id}/filters", {}, 201),
        ("delete", "/{id}/filters/{fid}", None, 204),
    ],
    ids=["add-filters", "remove-filters"],
)
def test_only_management_changes_a_live_groups_filters(
    api_client: APIClient,
    all_role_users: dict[str, User],
    marin_friends: RecipientGroup,
    role: str,
    allowed: bool,
    method: str,
    path: str,
    payload: dict[str, str] | None,
    code: int,
) -> None:
    """A live group's filters are CalDART management's and the system administrator's."""
    filter_set = marin_friends.filter_sets.get()
    api_client.force_login(all_role_users[role])
    url = f"{GROUPS_URL}{path.format(id=marin_friends.pk, fid=filter_set.pk)}"
    response = getattr(api_client, method)(url, payload, format="json")
    assert response.status_code == (code if allowed else 403)


@pytest.mark.parametrize(("role", "allowed"), role_matrix(MANAGEMENT, SYSTEM_ADMIN))
@pytest.mark.parametrize(
    ("path", "payload", "code"),
    [
        ("/batch/add-group", {"group": "{group}"}, 200),
        ("/save-group", {"name": "Saved", "kind": "fixed"}, 201),
    ],
    ids=["add-group", "save-group"],
)
def test_only_management_adds_or_saves_a_group_from_a_batch(
    api_client: APIClient,
    all_role_users: dict[str, User],
    bulk: BulkEmail,
    ann: User,
    board: RecipientGroup,
    role: str,
    allowed: bool,
    path: str,
    payload: dict[str, str],
    code: int,
) -> None:
    """Adding and saving a group is management's and the system administrator's."""
    add_to_batch(bulk, ann)
    body = {key: value.format(group=board.pk) for key, value in payload.items()}
    api_client.force_login(all_role_users[role])
    response = api_client.post(f"/api/v1/bulk-email/{bulk.pk}{path}", body, format="json")
    assert response.status_code == (code if allowed else 403)
