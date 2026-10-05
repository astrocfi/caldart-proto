"""A bulk email's batch: adds by filter, the union, skip reasons, removal, and the CSV.

Each press of **Add to batch** runs the member list's filters and adds everybody they
choose who is not in the batch yet.  Whether each person receives a copy is worked out
from the account as it is when the batch is read, and once more when the send starts.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import AccountKind
from apps.accounts.roles import DART_LEADER, MANAGEMENT, MEMBER, SYSTEM_ADMIN
from apps.bulk_email import batch
from apps.bulk_email.drafts import visible_to
from apps.bulk_email.job import run_sender
from apps.bulk_email.models import BatchAdd, BulkEmail, BulkEmailStatus, RecipientStatus
from caldart.exceptions import DomainError
from tests.conftest import audit_messages, read_csv, role_matrix
from tests.factories import (
    BulkEmailFactory,
    DartFactory,
    UserFactory,
    add_to_batch,
    grant_membership,
    make_person,
)

if TYPE_CHECKING:
    from apps.accounts.models import User
    from apps.members.models import MembershipPlan

pytestmark = pytest.mark.django_db

MARIN = {"county": "Marin"}
FRIENDS_IN_MARIN = {"kind": "friend", "county": "Marin"}
# Every account without a paid term is a friend, the role fixtures among them, so a
# filter on kind alone would choose them too; the county keeps it to a test's people.
FRIENDS_IN_MARIN_AND_NAPA = {"kind": "friend", "county": "Marin,Napa"}


def base_url(bulk: BulkEmail) -> str:
    """``/api/v1/bulk-email/{id}`` for ``bulk``."""
    return f"/api/v1/bulk-email/{bulk.pk}"


def receiving(bulk: BulkEmail) -> list[str]:
    """The addresses in ``bulk``'s batch that receive a copy, in send order."""
    return [row.recipient.email for row in batch.batch_rows(bulk) if row.will_receive]


def reasons(bulk: BulkEmail) -> list[tuple[str, str]]:
    """Each person in ``bulk``'s batch who is skipped, with the reason, in send order."""
    return [
        (row.recipient.email, row.reason) for row in batch.batch_rows(bulk) if not row.will_receive
    ]


@pytest.fixture
def bulk(management: User) -> BulkEmail:
    """A draft from CalDART management with an empty batch."""
    return BulkEmailFactory(sender=management)


# --------------------------------------------------------------------------
# Adding
# --------------------------------------------------------------------------
def test_an_add_puts_everybody_the_filters_choose_in_the_batch(
    bulk: BulkEmail, management: User
) -> None:
    """The member list's filters choose the people, in surname order."""
    make_person("zed@example.test", "Zed", "Young")
    make_person("amy@example.test", "Amy", "Abbott")
    make_person("fresno@example.test", county="Fresno")
    batch.add_filters(bulk, MARIN, actor=management)
    assert receiving(bulk) == ["amy@example.test", "zed@example.test"]


def test_two_overlapping_adds_make_their_union_without_duplicates(
    bulk: BulkEmail, management: User
) -> None:
    """Somebody both adds choose is in the batch once."""
    make_person("member@example.test", "Max", "Able")
    make_person("friend@example.test", "Fay", "Moss", kind=AccountKind.FRIEND)
    make_person("napa@example.test", "Neil", "Cole", county="Napa", kind=AccountKind.FRIEND)
    batch.add_filters(bulk, MARIN, actor=management)
    batch.add_filters(bulk, FRIENDS_IN_MARIN_AND_NAPA, actor=management)
    assert [row.recipient.email for row in batch.batch_rows(bulk)] == [
        "member@example.test",
        "napa@example.test",
        "friend@example.test",
    ]


def test_an_add_says_how_many_joined_and_how_many_were_there(
    bulk: BulkEmail, management: User, annual_plan: MembershipPlan
) -> None:
    """The second add counts the friend it shares with the first as already present."""
    grant_membership(make_person("member@example.test"), annual_plan)
    make_person("friend@example.test", kind=AccountKind.FRIEND)
    make_person("napa@example.test", county="Napa", kind=AccountKind.FRIEND)
    batch.add_filters(bulk, MARIN, actor=management)
    assert batch.add_filters(bulk, FRIENDS_IN_MARIN_AND_NAPA, actor=management) == batch.AddResult(
        added=1, already_present=1, count=3
    )


def test_an_add_records_its_filters_and_counts(bulk: BulkEmail, management: User) -> None:
    """Each add is kept with the filters that carried a value and its two counts."""
    make_person("friend@example.test", kind=AccountKind.FRIEND)
    batch.add_filters(bulk, {**FRIENDS_IN_MARIN, "search": ""}, actor=management)
    add = BatchAdd.objects.get(bulk_email=bulk)
    assert (add.filters, add.added_count, add.already_count) == (FRIENDS_IN_MARIN, 1, 0)


def test_each_row_names_the_add_that_brought_the_person_in(
    bulk: BulkEmail, management: User
) -> None:
    """A row's ``added_by`` is its add."""
    make_person("friend@example.test", kind=AccountKind.FRIEND)
    batch.add_filters(bulk, FRIENDS_IN_MARIN, actor=management)
    add = BatchAdd.objects.get(bulk_email=bulk)
    assert bulk.recipients.get().added_by == add


def test_a_row_keeps_the_name_address_kind_and_dart_at_the_add(
    bulk: BulkEmail, management: User
) -> None:
    """The row carries the person as they were when they joined the batch."""
    make_person(
        "fay@example.test",
        "Fay",
        "Moss",
        kind=AccountKind.FRIEND,
        dart=DartFactory(name="Marin DART"),
    )
    batch.add_filters(bulk, MARIN, actor=management)
    row = bulk.recipients.get()
    assert (row.name, row.email, row.kind, row.dart_name, row.status) == (
        "Fay Moss",
        "fay@example.test",
        "friend",
        "Marin DART",
        RecipientStatus.BATCHED,
    )


def test_a_member_with_no_term_is_kept_as_a_friend(bulk: BulkEmail, management: User) -> None:
    """A member who has not paid, whose membership reads none, is targeted as a friend."""
    make_person("unpaid@example.test", "Una", "Paid")
    batch.add_filters(bulk, MARIN, actor=management)
    assert bulk.recipients.get().kind == "friend"


def test_a_donor_is_never_added(bulk: BulkEmail, management: User) -> None:
    """A donor is in no member list, so no add chooses one."""
    make_person("member@example.test")
    UserFactory(email="donor@example.test", kind=AccountKind.DONOR)
    batch.add_filters(bulk, {}, actor=management)
    assert "donor@example.test" not in [row.email for row in bulk.recipients.all()]


@pytest.mark.parametrize(
    ("filters", "label"),
    [
        ({}, "Everybody"),
        ({"kind": "friend"}, "Kind: Friends only"),
        ({"county": "Marin,Napa"}, "County: Marin, Napa"),
        ({"role": "treasurer", "search": "ann"}, 'Search: "ann", Role: Treasurer'),
    ],
    ids=["none", "kind", "counties", "search-and-role"],
)
def test_an_add_reads_as_its_filters_in_words(filters: dict[str, str], label: str) -> None:
    """The compose screen and the CSV name an add by its filters."""
    assert batch.add_label(batch.given_filters(filters)) == label


def test_an_add_names_a_dart_by_its_name() -> None:
    """A DART filter given as an id reads as the DART's name."""
    team = DartFactory(name="Bay Area DART")
    assert batch.add_label({"dart": str(team.pk)}) == "DART: Bay Area DART"


# --------------------------------------------------------------------------
# Skip reasons
# --------------------------------------------------------------------------
def test_a_deactivated_account_is_listed_as_skipped(bulk: BulkEmail, management: User) -> None:
    """A deactivated account the filters choose joins the batch and is skipped."""
    make_person("gone@example.test", is_active=False)
    batch.add_filters(bulk, MARIN, actor=management)
    assert reasons(bulk) == [("gone@example.test", batch.SKIP_DEACTIVATED)]


def test_a_blank_address_is_listed_as_skipped(bulk: BulkEmail, management: User) -> None:
    """An account with no address on file has nowhere to send to."""
    account = make_person("blank@example.test")
    batch.add_filters(bulk, MARIN, actor=management)
    type(account).objects.filter(pk=account.pk).update(email="")
    assert [row.reason for row in batch.batch_rows(bulk)] == [batch.SKIP_NO_ADDRESS]


def test_an_invalid_address_is_listed_as_skipped(bulk: BulkEmail, management: User) -> None:
    """An address a mail server could never take is skipped as invalid."""
    make_person("not-an-address")
    batch.add_filters(bulk, MARIN, actor=management)
    assert reasons(bulk) == [("not-an-address", batch.SKIP_INVALID)]


def test_an_address_that_bounces_after_the_add_is_listed_as_skipped(
    bulk: BulkEmail, management: User
) -> None:
    """The reason is worked out when the batch is read, not when the person was added."""
    account = make_person("gone@example.test")
    batch.add_filters(bulk, MARIN, actor=management)
    account.email_bounced_at = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
    account.save(update_fields=["email_bounced_at"])
    assert reasons(bulk) == [("gone@example.test", batch.SKIP_BOUNCED)]


def test_a_deleted_account_is_listed_as_skipped(bulk: BulkEmail, management: User) -> None:
    """A row whose account is gone keeps its name and address and is skipped."""
    account = make_person("gone@example.test")
    batch.add_filters(bulk, MARIN, actor=management)
    account.delete()
    assert reasons(bulk) == [("gone@example.test", batch.SKIP_DELETED)]


def test_addresses_equal_but_for_case_receive_one_copy(bulk: BulkEmail, management: User) -> None:
    """Two accounts on one address, in different case and spacing, are sent one copy.

    The account table refuses two addresses equal but for case, so the second one here
    differs by a leading space as well.
    """
    make_person("pat@example.test", "Pat", "Able")
    second = make_person("other@example.test", "Pat", "Baker")
    type(second).objects.filter(pk=second.pk).update(email=" PAT@Example.test")
    batch.add_filters(bulk, MARIN, actor=management)
    assert reasons(bulk) == [(" PAT@Example.test", batch.SKIP_DUPLICATE)]


def test_the_counts_say_who_receives_and_who_is_skipped(bulk: BulkEmail, management: User) -> None:
    """Two receive a copy and one is skipped."""
    make_person("one@example.test")
    make_person("two@example.test")
    make_person("gone@example.test", is_active=False)
    batch.add_filters(bulk, MARIN, actor=management)
    assert batch.batch_counts(batch.batch_rows(bulk)) == batch.BatchCounts(
        count=3, receiving=2, skipped=1
    )


# --------------------------------------------------------------------------
# Removing and clearing
# --------------------------------------------------------------------------
def test_removing_one_person_leaves_the_rest(bulk: BulkEmail, management: User) -> None:
    """One row goes; the others stay."""
    make_person("amy@example.test", "Amy", "Abbott")
    make_person("zed@example.test", "Zed", "Young")
    batch.add_filters(bulk, MARIN, actor=management)
    batch.remove(bulk, bulk.recipients.get(email="amy@example.test").pk, actor=management)
    assert receiving(bulk) == ["zed@example.test"]


def test_clearing_empties_the_batch_and_its_adds(bulk: BulkEmail, management: User) -> None:
    """Nobody and no add is left."""
    make_person("amy@example.test")
    batch.add_filters(bulk, MARIN, actor=management)
    batch.clear(bulk, actor=management)
    assert (bulk.recipients.count(), bulk.adds.count()) == (0, 0)


def test_a_person_removed_can_be_added_again(bulk: BulkEmail, management: User) -> None:
    """A later add brings back somebody removed."""
    make_person("amy@example.test")
    batch.add_filters(bulk, MARIN, actor=management)
    batch.remove(bulk, bulk.recipients.get().pk, actor=management)
    assert batch.add_filters(bulk, MARIN, actor=management).added == 1


@pytest.mark.parametrize(
    "status", [BulkEmailStatus.SENDING, BulkEmailStatus.SENT, BulkEmailStatus.STOPPED]
)
def test_a_started_email_s_batch_cannot_change(
    bulk: BulkEmail, management: User, status: BulkEmailStatus
) -> None:
    """Once the send has started, an add is refused with the edit rule's sentence."""
    BulkEmail.objects.filter(pk=bulk.pk).update(status=status)
    with pytest.raises(DomainError, match="has been sent and cannot be changed"):
        batch.add_filters(bulk, MARIN, actor=management)


def test_a_queued_email_s_batch_can_still_change(bulk: BulkEmail, management: User) -> None:
    """An email waiting for its start time can still gain people."""
    make_person("amy@example.test")
    BulkEmail.objects.filter(pk=bulk.pk).update(status=BulkEmailStatus.QUEUED)
    assert batch.add_filters(bulk, MARIN, actor=management).added == 1


@pytest.mark.parametrize("change", ["add", "remove", "clear"])
def test_a_batch_change_takes_a_queued_email_back_to_a_draft(
    bulk: BulkEmail, management: User, change: str
) -> None:
    """The count the sender confirmed no longer holds, so the schedule is cleared."""
    make_person("amy@example.test")
    batch.add_filters(bulk, MARIN, actor=management)
    BulkEmail.objects.filter(pk=bulk.pk).update(
        status=BulkEmailStatus.QUEUED,
        start_at=datetime(2027, 1, 1, tzinfo=UTC),
        scheduled=True,
        confirm_count=1,
    )
    if change == "add":
        batch.add_filters(bulk, MARIN, actor=management)
    elif change == "remove":
        batch.remove(bulk, bulk.recipients.get().pk, actor=management)
    else:
        batch.clear(bulk, actor=management)
    bulk.refresh_from_db()
    assert (bulk.status, bulk.start_at, bulk.scheduled, bulk.confirm_count) == (
        BulkEmailStatus.DRAFT,
        None,
        False,
        None,
    )


def test_a_batch_change_on_a_queued_email_is_audited_as_a_cancel(
    bulk: BulkEmail, management: User, audit_log: pytest.LogCaptureFixture
) -> None:
    """One ``bulk_email.cancel`` line names the reason."""
    make_person("amy@example.test")
    BulkEmail.objects.filter(pk=bulk.pk).update(status=BulkEmailStatus.QUEUED)
    batch.add_filters(bulk, MARIN, actor=management)
    assert audit_messages(audit_log) == [
        f"action=bulk_email.cancel actor={management.pk} target={bulk.pk} reason=batch_changed"
    ]


def test_a_started_email_queued_again_cannot_change_its_batch(
    bulk: BulkEmail, management: User
) -> None:
    """Send the rest queues an email that has copies out; its batch stays as it was."""
    BulkEmail.objects.filter(pk=bulk.pk).update(
        status=BulkEmailStatus.QUEUED, started_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    with pytest.raises(DomainError, match="has been sent and cannot be changed"):
        batch.add_filters(bulk, MARIN, actor=management)


# --------------------------------------------------------------------------
# The frozen batch
# --------------------------------------------------------------------------
def test_the_send_goes_to_the_batch_not_to_the_filters_run_again(
    bulk: BulkEmail, management: User
) -> None:
    """Somebody who moved out of the county after the add is still sent a copy."""
    account = make_person("moved@example.test")
    batch.add_filters(bulk, MARIN, actor=management)
    account.profile.county = "Napa"
    account.profile.save(update_fields=["county"])
    make_person("late@example.test", "Lee", "Late")
    BulkEmail.objects.filter(pk=bulk.pk).update(
        status=BulkEmailStatus.QUEUED, start_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    run_sender()
    assert [(row.email, row.status) for row in bulk.recipients.all()] == [
        ("moved@example.test", RecipientStatus.SENT)
    ]


def test_freezing_skips_an_address_that_bounced_after_the_add(
    bulk: BulkEmail, management: User
) -> None:
    """The skip reasons are applied as the send starts."""
    account = make_person("gone@example.test")
    batch.add_filters(bulk, MARIN, actor=management)
    account.email_bounced_at = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
    account.save(update_fields=["email_bounced_at"])
    BulkEmail.objects.filter(pk=bulk.pk).update(
        status=BulkEmailStatus.QUEUED, start_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    run_sender()
    row = bulk.recipients.get()
    assert (row.status, row.reason) == (RecipientStatus.SKIPPED, batch.SKIP_BOUNCED)


def test_freezing_takes_the_address_as_it_is_then(bulk: BulkEmail, management: User) -> None:
    """A changed address is the one the copy goes to."""
    account = make_person("old@example.test")
    batch.add_filters(bulk, MARIN, actor=management)
    account.email = "new@example.test"
    account.save(update_fields=["email"])
    BulkEmail.objects.filter(pk=bulk.pk).update(
        status=BulkEmailStatus.QUEUED, start_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    run_sender()
    assert bulk.recipients.get().email == "new@example.test"


# --------------------------------------------------------------------------
# Privacy
# --------------------------------------------------------------------------
def test_management_sees_every_sender_s_emails(management: User) -> None:
    """CalDART management opens the drafts of every sender."""
    other = BulkEmailFactory(sender=UserFactory(email="other@example.test"))
    assert list(visible_to(management)) == [other]


def test_anybody_else_sees_only_their_own_emails(member: User) -> None:
    """A sender without the management role sees their own drafts alone."""
    own = BulkEmailFactory(sender=member)
    BulkEmailFactory(sender=UserFactory(email="other@example.test", roles=[MEMBER]))
    assert list(visible_to(member)) == [own]


# --------------------------------------------------------------------------
# The CSV
# --------------------------------------------------------------------------
def test_the_batch_csv_holds_exactly_the_batch(
    management_client: APIClient,
    bulk: BulkEmail,
    management: User,
    annual_plan: MembershipPlan,
) -> None:
    """One line per person: the add's label, who gets it, why not, and the type."""
    team = DartFactory(name="Marin DART")
    grant_membership(make_person("amy@example.test", "Amy", "Abbott", dart=team), annual_plan)
    make_person(
        "gil@example.test", "Gil", "Gone", dart=team, is_active=False, kind=AccountKind.FRIEND
    )
    make_person("napa@example.test", county="Napa")
    batch.add_filters(bulk, MARIN, actor=management)
    rows = read_csv(management_client.get(f"{base_url(bulk)}/batch.csv"))
    assert rows == [
        list(batch.BATCH_CSV_HEADER),
        [
            "Amy Abbott",
            "amy@example.test",
            "Member",
            "Marin DART",
            "Current",
            "County: Marin",
            "Yes",
            "",
            "Operational",
        ],
        [
            "Gil Gone",
            "gil@example.test",
            "Friend",
            "Marin DART",
            "Friend",
            "County: Marin",
            "No",
            batch.SKIP_DEACTIVATED,
            "Operational",
        ],
    ]


def test_the_batch_csv_is_named_for_the_email(
    management_client: APIClient, bulk: BulkEmail
) -> None:
    """The download is named ``caldart-bulk-email-<id>-recipient-list.csv``."""
    response = management_client.get(f"{base_url(bulk)}/batch.csv")
    assert response["Content-Disposition"] == (
        f'attachment; filename="caldart-bulk-email-{bulk.pk}-recipient-list.csv"'
    )


# --------------------------------------------------------------------------
# The endpoints
# --------------------------------------------------------------------------
def test_adding_through_the_api_answers_the_counts(
    management_client: APIClient, bulk: BulkEmail
) -> None:
    """``POST .../batch/add`` answers what the add did."""
    make_person("amy@example.test")
    response = management_client.post(
        f"{base_url(bulk)}/batch/add", {"filters": MARIN}, format="json"
    )
    assert response.json() == {"added": 1, "already_present": 0, "count": 1}


def test_an_unknown_filter_is_refused(management_client: APIClient, bulk: BulkEmail) -> None:
    """A name the member list does not take is a 400 under ``filters``."""
    response = management_client.post(
        f"{base_url(bulk)}/batch/add", {"filters": {"ordering": "name"}}, format="json"
    )
    assert (response.status_code, response.json()) == (
        400,
        {"filters": {"ordering": ["Not a filter of the member list."]}},
    )


def test_a_refused_filter_value_is_refused(management_client: APIClient, bulk: BulkEmail) -> None:
    """A value the member list refuses is a 400 naming the filter."""
    response = management_client.post(
        f"{base_url(bulk)}/batch/add", {"filters": {"kind": "donor"}}, format="json"
    )
    assert list(response.json()["filters"]) == ["kind"]


def test_the_batch_lists_every_person_with_the_counts_and_the_adds(
    management_client: APIClient, bulk: BulkEmail, management: User
) -> None:
    """``GET .../batch`` answers the counts, the adds, and the rows."""
    amy = make_person(
        "amy@example.test", "Amy", "Abbott", dart=DartFactory(name="Marin DART"), kind="friend"
    )
    batch.add_filters(bulk, MARIN, actor=management)
    add = bulk.adds.get()
    row = bulk.recipients.get()
    assert management_client.get(f"{base_url(bulk)}/batch").json() == {
        "count": 1,
        "receiving": 1,
        "skipped": 0,
        "adds": [
            {
                "id": add.pk,
                "label": "County: Marin",
                "filters": MARIN,
                "group": None,
                "added_count": 1,
                "already_count": 0,
                "created_at": add.created_at.astimezone().isoformat(),
            }
        ],
        "rows": [
            {
                "id": row.pk,
                "user_id": amy.pk,
                "name": "Amy Abbott",
                "email": "amy@example.test",
                "kind": "friend",
                "dart_name": "Marin DART",
                "added_by": add.pk,
                "status": "batched",
                "will_receive": True,
                "reason": "",
                "tried_at": None,
            }
        ],
    }


def test_removing_through_the_api_answers_no_content(
    management_client: APIClient, bulk: BulkEmail, management: User
) -> None:
    """``DELETE .../batch/{rid}`` is a 204."""
    make_person("amy@example.test")
    batch.add_filters(bulk, MARIN, actor=management)
    response = management_client.delete(f"{base_url(bulk)}/batch/{bulk.recipients.get().pk}")
    assert response.status_code == 204


def test_removing_a_row_of_another_batch_is_not_found(
    management_client: APIClient, bulk: BulkEmail, management: User
) -> None:
    """A row id from another email's batch is a 404."""
    other = BulkEmailFactory(sender=management)
    make_person("amy@example.test")
    batch.add_filters(other, MARIN, actor=management)
    response = management_client.delete(f"{base_url(bulk)}/batch/{other.recipients.get().pk}")
    assert response.status_code == 404


def test_clearing_through_the_api_answers_the_empty_batch(
    management_client: APIClient, bulk: BulkEmail, management: User
) -> None:
    """``DELETE .../batch`` answers the batch, now empty."""
    make_person("amy@example.test")
    batch.add_filters(bulk, MARIN, actor=management)
    assert management_client.delete(f"{base_url(bulk)}/batch").json()["count"] == 0


def test_changing_a_sent_email_s_batch_is_a_conflict(
    management_client: APIClient, bulk: BulkEmail
) -> None:
    """A change to an email that has started sending is a 409 with the sentence."""
    BulkEmail.objects.filter(pk=bulk.pk).update(status=BulkEmailStatus.SENT)
    response = management_client.post(f"{base_url(bulk)}/batch/add", {}, format="json")
    assert (response.status_code, response.json()) == (
        409,
        {"detail": "This email has been sent and cannot be changed."},
    )


@pytest.mark.parametrize(("role", "allowed"), role_matrix(MANAGEMENT, SYSTEM_ADMIN))
@pytest.mark.parametrize(
    ("method", "path", "code"),
    [
        ("get", "/batch", 200),
        ("get", "/batch.csv", 200),
        ("post", "/batch/add", 200),
        ("delete", "/batch", 200),
        ("delete", "/batch/{rid}", 204),
    ],
)
def test_only_management_reaches_the_batch(
    api_client: APIClient,
    all_role_users: dict[str, User],
    bulk: BulkEmail,
    role: str,
    allowed: bool,
    method: str,
    path: str,
    code: int,
) -> None:
    """A manager's batch answers CalDART management and the system administrator.

    A DART leader reaches the endpoints but not another sender's email, a 404.
    """
    row = add_to_batch(bulk, make_person("amy@example.test"))[0]
    api_client.force_login(all_role_users[role])
    response = getattr(api_client, method)(
        f"{base_url(bulk)}{path.format(rid=row.pk)}", {}, format="json"
    )
    assert response.status_code == (code if allowed else (404 if role == DART_LEADER else 403))
