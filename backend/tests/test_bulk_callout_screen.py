"""The Callouts screen: every callout's answers, the CSV, reminders, and closing.

CalDART management sees every callout and a DART leader the ones they sent or that went
to their own DART.  One row per person the callout reached carries their answer and the
member check's go/no-go.  **Remind non-responders** sends the same message again, as a
new round of copies, only to the people who have not answered; **Close now** stops the
answers.  See ``docs/developer/api-bulk-email.rst``.
"""

from __future__ import annotations

import re
from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from django.core import mail
from django.utils import timezone
from freezegun import freeze_time
from rest_framework.test import APIClient

from apps.accounts.models import User as UserModel
from apps.accounts.roles import DART_LEADER, MANAGEMENT, SYSTEM_ADMIN
from apps.aircraft.services import search_result
from apps.bulk_email import callouts, drafts, job
from apps.bulk_email.callouts import (
    CLOSED_MESSAGE,
    CLOSED_REASON,
    EVERYBODY_ANSWERED_MESSAGE,
    NOBODY_TO_REMIND_MESSAGE,
    NOT_SENT_MESSAGE,
    STILL_SENDING_MESSAGE,
    STOPPED_MESSAGE,
    record_answer,
)
from apps.bulk_email.delivery import SKIP_ANSWERED, SKIP_LATER_COPY
from apps.bulk_email.models import (
    BulkEmail,
    BulkEmailRecipient,
    BulkEmailStatus,
    Callout,
    RecipientStatus,
)
from apps.mail.models import EmailOptOut, EmailType, OptOutSource
from apps.members.models import MemberProfile
from apps.members.services import with_membership
from caldart.dates import format_display_datetime
from caldart.exceptions import DomainError
from tests.conftest import audit_messages, read_csv, role_matrix
from tests.factories import (
    AircraftFactory,
    BulkEmailFactory,
    DartFactory,
    add_to_batch,
    make_dart_leader,
    make_person,
    sent_callout,
)

if TYPE_CHECKING:
    from apps.accounts.models import User
    from apps.darts.models import Dart

pytestmark = pytest.mark.django_db

API = "/api/v1/bulk-email/callouts"


@pytest.fixture(autouse=True)
def _no_pause(monkeypatch: pytest.MonkeyPatch) -> None:
    """Take the pacing's pause out, so a run sends at once."""
    monkeypatch.setattr(job, "sleep", lambda seconds: None)


@pytest.fixture
def marin(db: None) -> Dart:
    """The Marin DART."""
    return DartFactory(name="Marin DART")


@pytest.fixture
def ann(marin: Dart) -> User:
    """Ann Able, a Marin member who flies N123AB from LVK."""
    person = make_person("ann@example.test", "Ann", "Able", dart=marin)
    MemberProfile.objects.filter(user=person).update(home_airport_identifier="LVK")
    person.profile.aircraft.add(AircraftFactory(n_number="N123AB"))
    return person


@pytest.fixture
def bea(marin: Dart) -> User:
    """Bea Bell, a Marin member."""
    return make_person("bea@example.test", "Bea", "Bell", dart=marin)


@pytest.fixture
def cy(marin: Dart) -> User:
    """Cy Cole, a Marin member."""
    return make_person("cy@example.test", "Cy", "Cole", dart=marin)


@pytest.fixture
def callout(management: User, ann: User, bea: User, cy: User) -> BulkEmail:
    """A callout from CalDART management to Ann, Bea, and Cy; Ann has answered."""
    bulk = sent_callout(management, ann, bea, cy)
    record_answer(bulk.callout, ann, answer="limited", note="Saturday only")
    mail.outbox.clear()
    return bulk


def url(bulk: BulkEmail, action: str = "") -> str:
    """The address of ``bulk`` on the Callouts screen, or of one of its actions."""
    return f"{API}/{bulk.pk}" + (f"/{action}" if action else "")


def addresses() -> list[str]:
    """Every address mailed since the outbox was last cleared, in order."""
    return sorted(address for message in mail.outbox for address in message.to)


# --------------------------------------------------------------------------
# The list and the detail
# --------------------------------------------------------------------------
def test_the_list_counts_the_answers_by_kind(
    management_client: APIClient, callout: BulkEmail
) -> None:
    """One row per callout, with the people it reached counted by answer."""
    (row,) = management_client.get(API).json()
    assert (row["id"], row["subject"], row["is_open"], row["counts"]) == (
        callout.pk,
        "Fire near Paradise for Hollis",
        True,
        {"reached": 3, "available": 0, "limited": 1, "unavailable": 0, "no_answer": 2},
    )


def test_the_list_leaves_out_ordinary_emails_and_unsent_callouts(
    management_client: APIClient, management: User, callout: BulkEmail
) -> None:
    """A draft callout and a sent newsletter are not callouts to read answers from."""
    draft = BulkEmailFactory(sender=management, is_callout=True)
    Callout.objects.create(bulk_email=draft, closes_at=timezone.now() + timedelta(days=1))
    assert [row["id"] for row in management_client.get(API).json()] == [callout.pk]


def test_the_detail_has_one_row_per_person_with_what_the_member_check_shows(
    management_client: APIClient, callout: BulkEmail, ann: User
) -> None:
    """Ann's row carries her answer, her DART, her home airport, and her aircraft."""
    rows = management_client.get(url(callout)).json()["recipients"]
    ann_row = next(row for row in rows if row["user_id"] == ann.pk)
    assert {key: ann_row[key] for key in ann_row if key != "answered_at"} == {
        "user_id": ann.pk,
        "name": "Ann Able",
        "email": "ann@example.test",
        "answer": "limited",
        "note": "Saturday only",
        "dart_name": "Marin DART",
        "home_airport": "LVK",
        "aircraft": ["N123AB"],
        "go_no_go": {"membership": False, "medical": True, "verified": False},
    }


def test_the_detail_lists_people_in_surname_order_with_no_answer_blank(
    management_client: APIClient, callout: BulkEmail
) -> None:
    """Bea and Cy have not answered: null, with no note and no time."""
    rows = management_client.get(url(callout)).json()["recipients"]
    assert [(row["name"], row["answer"], row["note"], row["answered_at"]) for row in rows] == [
        ("Ann Able", "limited", "Saturday only", rows[0]["answered_at"]),
        ("Bea Bell", None, "", None),
        ("Cy Cole", None, "", None),
    ]


def test_the_go_no_go_is_the_member_checks(
    management_client: APIClient, callout: BulkEmail, bea: User
) -> None:
    """The verdicts come from the same rule as the member check's search."""
    rows = management_client.get(url(callout)).json()["recipients"]
    bea_row = next(row for row in rows if row["user_id"] == bea.pk)
    expected = search_result(with_membership(UserModel.objects.filter(pk=bea.pk)).get())
    assert bea_row["go_no_go"] == expected["go_no_go"]


def test_a_person_whose_copy_was_skipped_is_not_listed(
    management_client: APIClient, management: User, ann: User, marin: Dart
) -> None:
    """Somebody the callout never reached cannot be waited on for an answer."""
    gone = make_person("gil@example.test", "Gil", "Gone", dart=marin, is_active=False)
    bulk = sent_callout(management, ann, gone)
    rows = management_client.get(url(bulk)).json()["recipients"]
    assert [row["name"] for row in rows] == ["Ann Able"]


def test_the_answers_download_as_a_csv(
    management_client: APIClient, callout: BulkEmail, ann: User
) -> None:
    """One line per person, the answer in words, and GO or NO-GO."""
    answered = timezone.localtime(callout.callout.answers.get().answered_at)
    response = management_client.get(url(callout, "answers.csv"))
    assert read_csv(response) == [
        [
            "Name",
            "Email",
            "Answer",
            "Note",
            "Answered at",
            "DART",
            "Home airport",
            "Aircraft",
            "Go/no-go",
        ],
        [
            "Ann Able",
            "ann@example.test",
            "Available with limits",
            "Saturday only",
            format_display_datetime(answered),
            "Marin DART",
            "LVK",
            "N123AB",
            "NO-GO",
        ],
        ["Bea Bell", "bea@example.test", "", "", "", "Marin DART", "", "", "NO-GO"],
        ["Cy Cole", "cy@example.test", "", "", "", "Marin DART", "", "", "NO-GO"],
    ]


def test_the_csv_is_named_for_its_callout(management_client: APIClient, callout: BulkEmail) -> None:
    """The download is ``caldart-callout-<id>-answers.csv``."""
    response = management_client.get(url(callout, "answers.csv"))
    assert response["Content-Disposition"] == (
        f'attachment; filename="caldart-callout-{callout.pk}-answers.csv"'
    )


# --------------------------------------------------------------------------
# Remind non-responders
# --------------------------------------------------------------------------
def test_a_reminder_reaches_only_the_people_who_have_not_answered(
    management_client: APIClient, callout: BulkEmail
) -> None:
    """Ann answered; Bea and Cy are sent the callout again."""
    management_client.post(url(callout, "remind"))
    job.run_sender()
    assert addresses() == ["bea@example.test", "cy@example.test"]


def test_a_reminder_is_a_new_round_of_copies(
    management_client: APIClient, callout: BulkEmail
) -> None:
    """The reminders are rows of round 1, sent, beside the first round's rows."""
    management_client.post(url(callout, "remind"))
    job.run_sender()
    rounds = sorted(callout.recipients.values_list("round", "email", "status"))
    assert rounds == [
        (0, "ann@example.test", RecipientStatus.SENT),
        (0, "bea@example.test", RecipientStatus.SENT),
        (0, "cy@example.test", RecipientStatus.SENT),
        (1, "bea@example.test", RecipientStatus.SENT),
        (1, "cy@example.test", RecipientStatus.SENT),
    ]


def test_a_reminder_is_filled_in_with_fresh_values(
    management_client: APIClient, callout: BulkEmail, bea: User
) -> None:
    """Bea renamed herself after the first copy; the reminder uses her name now."""
    bea.first_name = "Beatrice"
    bea.save()
    management_client.post(url(callout, "remind"))
    job.run_sender()
    assert [message.subject for message in mail.outbox if bea.email in message.to] == [
        "Fire near Paradise for Beatrice"
    ]


def test_a_reminder_skips_a_person_who_has_opted_out_since(
    management_client: APIClient, callout: BulkEmail, cy: User
) -> None:
    """Cy turned Mission email off: the reminder's row is skipped, saying why."""
    EmailOptOut.objects.create(
        user=cy, email_type=EmailType.objects.get(slug="mission"), source=OptOutSource.PROFILE
    )
    management_client.post(url(callout, "remind"))
    row = callout.recipients.get(round=1, user=cy)
    assert (row.status, row.reason) == (RecipientStatus.SKIPPED, "Opted out of Mission")


def test_a_reminder_takes_a_corrected_address(
    management_client: APIClient, callout: BulkEmail, cy: User
) -> None:
    """An address changed since the first copy is the one the reminder goes to."""
    cy.email = "cy.cole@example.test"
    cy.save()
    management_client.post(url(callout, "remind"))
    job.run_sender()
    assert addresses() == ["bea@example.test", "cy.cole@example.test"]


def test_a_reminder_keeps_the_first_sent_time_and_audits_its_round(
    management_client: APIClient, callout: BulkEmail, audit_log: pytest.LogCaptureFixture
) -> None:
    """The round's own lines are written, not a second send or a retry's."""
    sent_at = callout.sent_at
    management_client.post(url(callout, "remind"))
    job.run_sender()
    callout.refresh_from_db()
    lines = [line for line in audit_messages(audit_log) if "callout.remind" in line]
    assert (callout.status, callout.sent_at, [line.split()[0] for line in lines]) == (
        BulkEmailStatus.SENT,
        sent_at,
        ["action=callout.remind", "action=callout.remind_finished"],
    )


def test_the_detail_lists_each_round_of_reminders(
    management_client: APIClient, callout: BulkEmail
) -> None:
    """Round 1 queued two reminders."""
    management_client.post(url(callout, "remind"))
    reminders = management_client.get(url(callout)).json()["reminders"]
    assert [(entry["round"], entry["count"]) for entry in reminders] == [(1, 2)]


def test_a_failed_reminder_can_be_retried(management_client: APIClient, callout: BulkEmail) -> None:
    """A refused reminder is retried, not taken for a duplicate of the first copy."""
    management_client.post(url(callout, "remind"))
    callout.recipients.filter(round=1).update(status=RecipientStatus.FAILED)
    BulkEmail.objects.filter(pk=callout.pk).update(status=BulkEmailStatus.SENT)
    response = management_client.post(f"/api/v1/bulk-email/{callout.pk}/retry")
    statuses = set(callout.recipients.filter(round=1).values_list("status", flat=True))
    assert (response.status_code, statuses) == (200, {RecipientStatus.PENDING})


@pytest.fixture
def stopped_reminders(management_client: APIClient, callout: BulkEmail) -> BulkEmail:
    """``callout`` reminded, and the reminder round stopped before any copy went."""
    management_client.post(url(callout, "remind"))
    callout.recipients.filter(round=1).update(status=RecipientStatus.STOPPED)
    BulkEmail.objects.filter(pk=callout.pk).update(status=BulkEmailStatus.STOPPED)
    callout.refresh_from_db()
    return callout


def test_send_the_rest_of_a_reminder_round_skips_a_person_who_answered_since(
    stopped_reminders: BulkEmail, management: User, bea: User
) -> None:
    """Bea answered after the stop, so her reminder is skipped, saying why."""
    record_answer(stopped_reminders.callout, bea, answer="available", note="")
    drafts.resume(stopped_reminders, actor=management)
    job.run_sender()
    assert sorted(
        stopped_reminders.recipients.filter(round=1).values_list("email", "status", "reason")
    ) == [
        ("bea@example.test", RecipientStatus.SKIPPED, SKIP_ANSWERED),
        ("cy@example.test", RecipientStatus.SENT, ""),
    ]


def test_send_the_rest_of_a_reminder_round_sends_nothing_to_a_person_who_answered(
    stopped_reminders: BulkEmail, management: User, bea: User
) -> None:
    """Only Cy, who has still not answered, is sent the rest."""
    record_answer(stopped_reminders.callout, bea, answer="available", note="")
    drafts.resume(stopped_reminders, actor=management)
    job.run_sender()
    assert addresses() == ["cy@example.test"]


def test_retrying_a_failed_reminder_skips_a_person_who_answered_since(
    management_client: APIClient, callout: BulkEmail, bea: User
) -> None:
    """A failed reminder is not retried to somebody who has answered meanwhile."""
    management_client.post(url(callout, "remind"))
    callout.recipients.filter(round=1).update(status=RecipientStatus.FAILED)
    BulkEmail.objects.filter(pk=callout.pk).update(status=BulkEmailStatus.SENT)
    record_answer(callout.callout, bea, answer="unavailable", note="")
    management_client.post(f"/api/v1/bulk-email/{callout.pk}/retry")
    bea_row = callout.recipients.get(round=1, email="bea@example.test")
    assert (bea_row.status, bea_row.reason) == (RecipientStatus.SKIPPED, SKIP_ANSWERED)


@pytest.mark.parametrize(
    ("state", "message"),
    [
        (BulkEmailStatus.SENDING, STILL_SENDING_MESSAGE),
        (BulkEmailStatus.QUEUED, STILL_SENDING_MESSAGE),
        (BulkEmailStatus.STOPPED, STOPPED_MESSAGE),
    ],
    ids=["sending", "queued", "stopped"],
)
def test_a_callout_still_sending_is_not_reminded(
    management_client: APIClient, callout: BulkEmail, state: str, message: str
) -> None:
    """Only a callout that has finished sending is reminded."""
    BulkEmail.objects.filter(pk=callout.pk).update(status=state)
    response = management_client.post(url(callout, "remind"))
    assert (response.status_code, response.json()) == (409, {"detail": message})


def test_a_closed_callout_is_not_reminded(management_client: APIClient, callout: BulkEmail) -> None:
    """Nobody can answer a closed callout, so nobody is reminded."""
    Callout.objects.filter(bulk_email=callout).update(closed_at=timezone.now())
    response = management_client.post(url(callout, "remind"))
    assert (response.status_code, response.json()) == (409, {"detail": CLOSED_MESSAGE})


def test_nobody_is_reminded_once_everybody_has_answered(
    management_client: APIClient, callout: BulkEmail, bea: User, cy: User
) -> None:
    """With every answer in, the reminder is refused."""
    for person in (bea, cy):
        record_answer(callout.callout, person, answer="available", note="")
    response = management_client.post(url(callout, "remind"))
    assert (response.status_code, response.json()) == (
        409,
        {"detail": EVERYBODY_ANSWERED_MESSAGE},
    )


def test_a_reminder_everybody_would_skip_changes_nothing(
    management_client: APIClient, callout: BulkEmail, bea: User, cy: User
) -> None:
    """When nobody left can be sent one, no round is made and nothing is queued.

    Bea and Cy have both turned Mission email off since the first copy.
    """
    for person in (bea, cy):
        EmailOptOut.objects.create(
            user=person,
            email_type=EmailType.objects.get(slug="mission"),
            source=OptOutSource.PROFILE,
        )
    response = management_client.post(url(callout, "remind"))
    callout.refresh_from_db()
    assert (
        response.status_code,
        response.json(),
        callout.recipients.filter(round=1).count(),
        callout.status,
    ) == (409, {"detail": NOBODY_TO_REMIND_MESSAGE}, 0, BulkEmailStatus.SENT)


def test_a_callout_never_sent_is_not_reminded(management: User) -> None:
    """The service refuses a draft callout."""
    draft = BulkEmailFactory(sender=management, is_callout=True)
    Callout.objects.create(bulk_email=draft, closes_at=timezone.now() + timedelta(days=1))
    with pytest.raises(DomainError, match=re.escape(NOT_SENT_MESSAGE)):
        callouts.remind(draft, actor=management)


# --------------------------------------------------------------------------
# Close now
# --------------------------------------------------------------------------
def test_close_now_closes_the_callout(
    management_client: APIClient, management: User, callout: BulkEmail
) -> None:
    """**Close now** names who closed it, and the callout takes no more answers."""
    with freeze_time("2026-04-07T15:00:00Z"):
        body = management_client.post(url(callout, "close")).json()
    assert (body["is_open"], body["closed_at"], body["closed_by"]) == (
        False,
        "2026-04-07T08:00:00-07:00",
        "Hollis Grant",
    )


def test_a_closed_callout_cannot_be_closed_again(
    management_client: APIClient, callout: BulkEmail
) -> None:
    """The second **Close now** is refused."""
    management_client.post(url(callout, "close"))
    response = management_client.post(url(callout, "close"))
    assert (response.status_code, response.json()) == (409, {"detail": CLOSED_MESSAGE})


def test_closing_is_audited(
    management_client: APIClient,
    management: User,
    callout: BulkEmail,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """One ``callout.close`` line names who closed it."""
    management_client.post(url(callout, "close"))
    assert [line for line in audit_messages(audit_log) if "callout.close" in line] == [
        f"action=callout.close actor={management.pk} target={callout.pk}"
    ]


# --------------------------------------------------------------------------
# Who may call what
# --------------------------------------------------------------------------
@pytest.mark.parametrize(("role", "allowed"), role_matrix(DART_LEADER, MANAGEMENT, SYSTEM_ADMIN))
def test_the_list_answers_every_bulk_sender(
    api_client: APIClient, all_role_users: dict[str, User], role: str, allowed: bool
) -> None:
    """The Callouts list answers each sender's role, and refuses every other."""
    api_client.force_login(all_role_users[role])
    assert api_client.get(API).status_code == (200 if allowed else 403)


@pytest.mark.parametrize(("role", "allowed"), role_matrix(DART_LEADER, MANAGEMENT, SYSTEM_ADMIN))
@pytest.mark.parametrize(
    ("method", "action"),
    [("get", ""), ("get", "answers.csv"), ("post", "remind"), ("post", "close")],
    ids=["detail", "csv", "remind", "close"],
)
def test_every_sender_reaches_their_own_callout(
    api_client: APIClient,
    all_role_users: dict[str, User],
    marin: Dart,
    bea: User,
    role: str,
    allowed: bool,
    method: str,
    action: str,
) -> None:
    """Each endpoint of one callout answers its own sender, if that sender may send."""
    user = all_role_users[role]
    MemberProfile.objects.create(user=user, dart=marin)
    bulk = sent_callout(user, bea)
    api_client.force_login(user)
    response = getattr(api_client, method)(url(bulk, action))
    assert response.status_code == (200 if allowed else 403)


@pytest.mark.parametrize("action", ["", "answers.csv", "remind", "close"])
def test_an_anonymous_caller_is_refused(callout: BulkEmail, action: str) -> None:
    """Signing in comes first."""
    method = "get" if action in ("", "answers.csv") else "post"
    assert getattr(APIClient(), method)(url(callout, action)).status_code == 401


def test_a_leader_sees_the_callouts_of_their_own_dart(
    api_client: APIClient, marin: Dart, bea: User
) -> None:
    """Lane leads Marin and sees Lou's Marin callout as well as her own."""
    lane = make_dart_leader("lane@example.test", marin)
    lou = make_dart_leader("lou@example.test", marin, first="Lou", last="Lee")
    own = sent_callout(lane, bea)
    colleagues = sent_callout(lou, bea)
    api_client.force_login(lane)
    assert sorted(row["id"] for row in api_client.get(API).json()) == sorted(
        [own.pk, colleagues.pk]
    )


def test_a_leader_does_not_see_another_darts_callout_or_managements(
    api_client: APIClient, management: User, marin: Dart, bea: User
) -> None:
    """Napa's callout and management's callout are not Lane's to read."""
    lane = make_dart_leader("lane@example.test", marin)
    napa = DartFactory(name="Napa DART")
    nell = make_dart_leader("nell@example.test", napa, first="Nell", last="North")
    sent_callout(nell, make_person("nat@example.test", "Nat", "Napa", dart=napa))
    sent_callout(management, bea)
    api_client.force_login(lane)
    assert api_client.get(API).json() == []


@pytest.mark.parametrize(
    ("method", "action"),
    [("get", ""), ("get", "answers.csv"), ("post", "remind"), ("post", "close")],
    ids=["detail", "csv", "remind", "close"],
)
def test_a_leader_cannot_reach_another_darts_callout_by_its_id(
    api_client: APIClient, marin: Dart, method: str, action: str
) -> None:
    """A crafted id of a Napa callout is a 404 for Marin's leader, and nothing changes."""
    lane = make_dart_leader("lane@example.test", marin)
    napa = DartFactory(name="Napa DART")
    nell = make_dart_leader("nell@example.test", napa, first="Nell", last="North")
    bulk = sent_callout(nell, make_person("nat@example.test", "Nat", "Napa", dart=napa))
    api_client.force_login(lane)
    response = getattr(api_client, method)(url(bulk, action))
    assert (response.status_code, Callout.objects.get(bulk_email=bulk).closed_at) == (404, None)


def test_a_callout_answer_raised_for_a_leaders_callout_counts_on_the_screen(
    api_client: APIClient, marin: Dart, bea: User, cy: User
) -> None:
    """The leader's own screen counts the answers to their callout."""
    lane = make_dart_leader("lane@example.test", marin)
    bulk = sent_callout(lane, bea, cy)
    record_answer(bulk.callout, bea, answer="unavailable", note="")
    api_client.force_login(lane)
    (row,) = api_client.get(API).json()
    assert row["counts"] == {
        "reached": 2,
        "available": 0,
        "limited": 0,
        "unavailable": 1,
        "no_answer": 1,
    }


# --------------------------------------------------------------------------
# Retrying failed copies across rounds
# --------------------------------------------------------------------------
def reminder_row(bulk: BulkEmail, person: User, status: str) -> BulkEmailRecipient:
    """A reminder (round 1) row of ``bulk`` for ``person`` in ``status``, tried now."""
    return BulkEmailRecipient.objects.create(
        bulk_email=bulk,
        user=person,
        name=person.display_name,
        email=person.email,
        round=1,
        status=status,
        tried_at=timezone.now(),
    )


def test_a_retry_sends_one_copy_when_the_first_and_the_reminder_both_failed(
    management_client: APIClient, management: User, bea: User
) -> None:
    """Only the reminder goes again; the first copy is skipped for it."""
    bulk = sent_callout(management, bea)
    bulk.recipients.filter(round=0).update(status=RecipientStatus.FAILED)
    reminder_row(bulk, bea, RecipientStatus.FAILED)
    mail.outbox.clear()
    management_client.post(f"/api/v1/bulk-email/{bulk.pk}/retry")
    job.run_sender()
    rows = sorted(bulk.recipients.values_list("round", "status", "reason"))
    assert (rows, [message.to for message in mail.outbox]) == (
        [
            (0, RecipientStatus.SKIPPED, SKIP_LATER_COPY),
            (1, RecipientStatus.SENT, ""),
        ],
        [["bea@example.test"]],
    )


def test_a_retry_does_not_resend_a_first_copy_once_the_reminder_went(
    management_client: APIClient, management: User, bea: User
) -> None:
    """Bea's reminder reached her, so her failed first copy is not sent again."""
    bulk = sent_callout(management, bea)
    bulk.recipients.filter(round=0).update(status=RecipientStatus.FAILED)
    reminder_row(bulk, bea, RecipientStatus.SENT)
    response = management_client.post(f"/api/v1/bulk-email/{bulk.pk}/retry")
    first = bulk.recipients.get(round=0)
    assert (response.status_code, first.status, first.reason) == (
        409,
        RecipientStatus.SKIPPED,
        SKIP_LATER_COPY,
    )


# --------------------------------------------------------------------------
# Closing stops every copy still to go
# --------------------------------------------------------------------------
def test_close_now_calls_off_a_queued_round_of_reminders(
    management_client: APIClient, callout: BulkEmail
) -> None:
    """The queued reminders are skipped as *Callout closed*, and nothing is sent."""
    management_client.post(url(callout, "remind"))
    management_client.post(url(callout, "close"))
    job.run_sender()
    callout.refresh_from_db()
    reminders = set(callout.recipients.filter(round=1).values_list("status", "reason"))
    assert (callout.status, reminders, mail.outbox) == (
        BulkEmailStatus.SENT,
        {(RecipientStatus.SKIPPED, CLOSED_REASON)},
        [],
    )


def test_send_the_rest_of_a_closed_callout_sends_nothing(
    management_client: APIClient, management: User, bea: User, cy: User
) -> None:
    """A stopped callout closed meanwhile skips the rest as *Callout closed*."""
    bulk = sent_callout(management, bea, cy)
    bulk.recipients.filter(user=cy).update(status=RecipientStatus.STOPPED)
    BulkEmail.objects.filter(pk=bulk.pk).update(status=BulkEmailStatus.STOPPED)
    management_client.post(url(bulk, "close"))
    mail.outbox.clear()
    management_client.post(f"/api/v1/bulk-email/{bulk.pk}/resume")
    job.run_sender()
    row = bulk.recipients.get(user=cy)
    assert (row.status, row.reason, mail.outbox) == (RecipientStatus.SKIPPED, CLOSED_REASON, [])


def test_a_late_run_sends_no_copy_of_a_callout_already_closed(
    management_client: APIClient, management: User, bea: User
) -> None:
    """The timer came after ``closes_at``: no copy goes, and the detail says so."""
    bulk = BulkEmailFactory(
        sender=management,
        email_type=EmailType.objects.get(slug="mission"),
        is_callout=True,
        status=BulkEmailStatus.QUEUED,
        start_at=timezone.now() - timedelta(hours=2),
    )
    Callout.objects.create(bulk_email=bulk, closes_at=timezone.now() - timedelta(hours=1))
    add_to_batch(bulk, bea)
    job.run_sender()
    body = management_client.get(url(bulk)).json()
    assert (mail.outbox, body["closed_skipped"]) == ([], 1)


def test_a_callout_closing_during_a_paced_send_sends_no_more_copies(
    management: User, bea: User, cy: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The answers close while the sender waits between copies: Cy is skipped."""

    def close_while_waiting(seconds: float) -> None:
        Callout.objects.update(closed_at=timezone.now())

    monkeypatch.setattr(job, "sleep", close_while_waiting)
    monkeypatch.setattr(job, "monotonic", lambda: 0.0)
    bulk = sent_callout(management, bea, cy)
    statuses = dict(bulk.recipients.values_list("email", "status"))
    assert statuses == {
        "bea@example.test": RecipientStatus.SENT,
        "cy@example.test": RecipientStatus.SKIPPED,
    }


# --------------------------------------------------------------------------
# Who a reminder goes to
# --------------------------------------------------------------------------
def test_a_reminder_goes_to_exactly_the_people_the_detail_lists_without_an_answer(
    management_client: APIClient, management: User, ann: User, bea: User, cy: User
) -> None:
    """Cy's first copy failed, so the callout never reached him: no reminder either."""
    bulk = sent_callout(management, ann, bea, cy)
    bulk.recipients.filter(user=cy).update(status=RecipientStatus.FAILED)
    detail = management_client.get(url(bulk)).json()
    waiting = sorted(row["user_id"] for row in detail["recipients"] if row["answer"] is None)
    management_client.post(url(bulk, "remind"))
    reminded = sorted(bulk.recipients.filter(round=1).values_list("user_id", flat=True))
    assert (reminded, detail["counts"]["no_answer"]) == (waiting, len(waiting))


# --------------------------------------------------------------------------
# A co-leader of the callout's DART
# --------------------------------------------------------------------------
@pytest.fixture
def lou_callout(marin: Dart, bea: User) -> BulkEmail:
    """A callout Lou, a Marin DART leader, sent to Bea."""
    lou = make_dart_leader("lou@example.test", marin, first="Lou", last="Lee")
    return sent_callout(lou, bea)


@pytest.mark.parametrize(
    "action",
    ["", "batch", "batch.csv", "recipients.csv"],
    ids=["detail", "batch", "csv", "results"],
)
def test_a_co_leader_reads_the_callouts_sent_detail(
    api_client: APIClient, marin: Dart, lou_callout: BulkEmail, action: str
) -> None:
    """Lane leads Marin too, and reads Lou's callout as it went."""
    api_client.force_login(make_dart_leader("lane@example.test", marin))
    path = f"/api/v1/bulk-email/{lou_callout.pk}" + (f"/{action}" if action else "")
    assert api_client.get(path).status_code == 200


@pytest.mark.parametrize(
    ("method", "action"),
    [("patch", ""), ("delete", ""), ("post", "retry"), ("post", "resume"), ("post", "duplicate")],
    ids=["edit", "delete", "retry", "resume", "duplicate"],
)
def test_a_co_leader_cannot_act_on_anothers_email(
    api_client: APIClient,
    marin: Dart,
    lou_callout: BulkEmail,
    method: str,
    action: str,
) -> None:
    """Reading is all Lane may do with Lou's email, but for the callout's own actions."""
    api_client.force_login(make_dart_leader("lane@example.test", marin))
    path = f"/api/v1/bulk-email/{lou_callout.pk}" + (f"/{action}" if action else "")
    assert getattr(api_client, method)(path, {}, format="json").status_code == 404


def test_a_co_leader_can_stop_a_callouts_reminders(
    api_client: APIClient, marin: Dart, lou_callout: BulkEmail
) -> None:
    """Lane reminded the rest of Lou's callout, and can stop that round."""
    lane = make_dart_leader("lane@example.test", marin)
    api_client.force_login(lane)
    api_client.post(url(lou_callout, "remind"))
    response = api_client.post(f"/api/v1/bulk-email/{lou_callout.pk}/stop")
    assert (response.status_code, response.json()["status"]) == (200, BulkEmailStatus.STOPPED)


def test_a_co_leader_cannot_stop_anothers_ordinary_email(
    api_client: APIClient, marin: Dart, bea: User
) -> None:
    """**Stop** on another leader's email is the callout's alone."""
    lou = make_dart_leader("lou@example.test", marin, first="Lou", last="Lee")
    plain = sent_callout(lou, bea)
    BulkEmail.objects.filter(pk=plain.pk).update(is_callout=False, status=BulkEmailStatus.SENDING)
    api_client.force_login(make_dart_leader("lane@example.test", marin))
    assert api_client.post(f"/api/v1/bulk-email/{plain.pk}/stop").status_code == 404


def test_a_leader_of_another_dart_cannot_read_the_email(
    api_client: APIClient, lou_callout: BulkEmail
) -> None:
    """Nell leads Napa: Lou's Marin email is a 404 for her."""
    api_client.force_login(make_dart_leader("nell@example.test", DartFactory(name="Napa DART")))
    assert api_client.get(f"/api/v1/bulk-email/{lou_callout.pk}").status_code == 404
