"""Changing when a mission callout's answers close, after it has gone out.

``POST /bulk-email/callouts/{id}/closes-at`` goes through
``apps.bulk_email.callouts.move_close``.  A deployment that runs longer than planned
keeps taking answers on the links already sent; a callout whose time ran out takes
them again; one closed with **Close now** stays closed.  The contract is
``docs/developer/api-bulk-email.rst``.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import DART_LEADER, MANAGEMENT, SYSTEM_ADMIN
from apps.bulk_email import job
from apps.bulk_email.callouts import (
    CLOSED_BY_HAND_MESSAGE,
    NOT_SENT_MESSAGE,
    is_open,
    move_close,
    record_answer,
)
from apps.bulk_email.models import BulkEmail, Callout
from apps.darts.models import Dart
from apps.members.models import MemberProfile
from caldart.exceptions import DomainError
from tests.conftest import audit_messages, role_matrix
from tests.factories import BulkEmailFactory, DartFactory, make_person, sent_callout

pytestmark = pytest.mark.django_db

API = "/api/v1/bulk-email/callouts"


@pytest.fixture(autouse=True)
def _no_pause(monkeypatch: pytest.MonkeyPatch) -> None:
    """Take the pacing's pause out, so a run sends at once."""
    monkeypatch.setattr(job, "sleep", lambda seconds: None)


@pytest.fixture
def marin(db: None) -> Dart:
    """The Marin DART."""
    return DartFactory(name="Marin")


@pytest.fixture
def ann(marin: Dart) -> User:
    """Ann Able, a Marin member."""
    return make_person("ann@example.test", "Ann", "Able", dart=marin)


@pytest.fixture
def callout(management: User, ann: User) -> BulkEmail:
    """A callout from CalDART management to Ann, whose answers close in a day."""
    return sent_callout(management, ann)


def _url(bulk: BulkEmail) -> str:
    """The close-time endpoint of ``bulk``."""
    return f"{API}/{bulk.pk}/closes-at"


def _later(hours: int) -> str:
    """``hours`` from now, as an ISO date and time."""
    return (timezone.now() + timedelta(hours=hours)).isoformat()


def test_a_later_close_time_is_stored_and_answered(
    management_client: APIClient, callout: BulkEmail
) -> None:
    """The callout answers its new close time, and stays open."""
    new = timezone.now() + timedelta(days=3)
    body = management_client.post(_url(callout), {"closes_at": new.isoformat()}).json()
    callout.callout.refresh_from_db()
    assert (body["is_open"], callout.callout.closes_at) == (True, new)


def test_an_answer_is_taken_until_the_new_close_time(
    management_client: APIClient, callout: BulkEmail, ann: User
) -> None:
    """The link already sent records an answer after the old time, before the new one."""
    management_client.post(_url(callout), {"closes_at": _later(72)})
    after_the_old_time = timezone.now() + timedelta(days=2)
    record_answer(callout.callout, ann, answer="available", note="", now=after_the_old_time)
    assert callout.callout.answers.get(user=ann).answer == "available"


def test_a_callout_whose_time_ran_out_takes_answers_again(
    management_client: APIClient, callout: BulkEmail
) -> None:
    """Moving the time after it passed reopens the callout."""
    Callout.objects.filter(bulk_email=callout).update(closes_at=timezone.now() - timedelta(hours=1))
    management_client.post(_url(callout), {"closes_at": _later(24)})
    callout.callout.refresh_from_db()
    assert is_open(callout.callout) is True


def test_a_callout_closed_with_close_now_stays_closed(
    management_client: APIClient, callout: BulkEmail
) -> None:
    """**Close now** can't be undone by moving the close time: 409."""
    management_client.post(f"{API}/{callout.pk}/close")
    response = management_client.post(_url(callout), {"closes_at": _later(24)})
    assert (response.status_code, response.json()) == (409, {"detail": CLOSED_BY_HAND_MESSAGE})


def test_a_time_in_the_past_is_refused(management_client: APIClient, callout: BulkEmail) -> None:
    """The new time must be in the future: 400 keyed ``closes_at``."""
    response = management_client.post(_url(callout), {"closes_at": _later(-1)})
    assert (response.status_code, response.json()) == (
        400,
        {"closes_at": ["Choose a time in the future."]},
    )


def test_a_missing_time_is_refused(management_client: APIClient, callout: BulkEmail) -> None:
    """A body without ``closes_at`` is a 400 naming it."""
    response = management_client.post(_url(callout), {})
    assert (response.status_code, list(response.json())) == (400, ["closes_at"])


def test_a_callout_never_sent_is_refused(management: User) -> None:
    """A draft's close time is set on the compose screen, not by moving it."""
    draft = BulkEmailFactory(sender=management, is_callout=True)
    Callout.objects.create(bulk_email=draft, closes_at=timezone.now() + timedelta(days=1))
    with pytest.raises(DomainError, match=NOT_SENT_MESSAGE):
        move_close(draft, actor=management, closes_at=timezone.now() + timedelta(days=2))


def test_moving_the_close_time_is_audited(
    management_client: APIClient,
    management: User,
    callout: BulkEmail,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """One ``callout.move_close`` line names who moved it."""
    management_client.post(_url(callout), {"closes_at": _later(48)})
    assert [line for line in audit_messages(audit_log) if "callout.move_close" in line] == [
        f"action=callout.move_close actor={management.pk} target={callout.pk}"
    ]


@pytest.mark.parametrize(("role", "allowed"), role_matrix(DART_LEADER, MANAGEMENT, SYSTEM_ADMIN))
def test_every_sender_moves_the_close_time_of_their_own_callout(
    api_client: APIClient,
    all_role_users: dict[str, User],
    marin: Dart,
    ann: User,
    role: str,
    allowed: bool,
) -> None:
    """The people who can close a callout can move its close time; nobody else can."""
    user = all_role_users[role]
    MemberProfile.objects.create(user=user, dart=marin)
    bulk = sent_callout(user, ann)
    api_client.force_login(user)
    response = api_client.post(_url(bulk), {"closes_at": _later(48)})
    assert response.status_code == (200 if allowed else 403)
