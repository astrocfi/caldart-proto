"""The reminder log and manual-run endpoints.

Role matrix first — the log is for ``account_admin`` and ``system_admin``, the
run button for ``system_admin`` alone — then filters and payloads.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.core.mail import EmailMessage
from django.utils import timezone
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
from apps.members.models import MembershipPlan
from apps.reminders.models import ReminderKind, ReminderLog
from tests.factories import MembershipFactory, ReminderLogFactory, UserFactory

pytestmark = pytest.mark.django_db

LOG_URL = "/api/v1/admin/reminders/log"
RUN_URL = "/api/v1/system/reminders/run"


@pytest.fixture
def log_entries(db: None, annual_plan: MembershipPlan) -> list[ReminderLog]:
    """Three entries by three members, on three days and of three kinds."""
    entries: list[ReminderLog] = []
    for offset, kind in enumerate([ReminderKind.T60, ReminderKind.T30, ReminderKind.T7]):
        user = UserFactory(email=f"{kind}@example.test", first_name="Ada", last_name="Byron")
        membership = MembershipFactory(user=user, plan=annual_plan)
        entries.append(
            ReminderLogFactory(
                user=user,
                membership=membership,
                kind=kind,
                sent_at=timezone.now() - timedelta(days=offset),
            )
        )
    return entries


# ---------------------------------------------------------------- role matrix
@pytest.mark.parametrize(
    ("role", "allowed"),
    [
        (MEMBER, False),
        (DART_LEADER, False),
        (USER_ADMIN, False),
        (ACCOUNT_ADMIN, True),
        (WEBSITE_ADMIN, False),
        (SYSTEM_ADMIN, True),
    ],
)
def test_log_role_matrix(
    api_client: APIClient,
    all_role_users: dict[str, User],
    log_entries: list[ReminderLog],
    role: str,
    allowed: bool,
) -> None:
    """Only ``account_admin`` and ``system_admin`` may read the reminder log."""
    api_client.force_login(all_role_users[role])
    response = api_client.get(LOG_URL)
    assert response.status_code == (200 if allowed else 403)


def test_log_requires_a_session(api_client: APIClient) -> None:
    """An anonymous request to the log endpoint is rejected."""
    assert api_client.get(LOG_URL).status_code == 401


@pytest.mark.parametrize(
    ("role", "allowed"),
    [
        (MEMBER, False),
        (DART_LEADER, False),
        (USER_ADMIN, False),
        (ACCOUNT_ADMIN, False),
        (WEBSITE_ADMIN, False),
        (SYSTEM_ADMIN, True),
    ],
)
def test_run_role_matrix(
    api_client: APIClient, all_role_users: dict[str, User], role: str, allowed: bool
) -> None:
    """Only ``system_admin`` may trigger a manual run."""
    api_client.force_login(all_role_users[role])
    response = api_client.post(RUN_URL, {"dry_run": True})
    assert response.status_code == (200 if allowed else 403)


def test_run_requires_a_session(api_client: APIClient) -> None:
    """An anonymous request to the run endpoint is rejected."""
    assert api_client.post(RUN_URL, {"dry_run": True}).status_code == 401


# ------------------------------------------------------------------- the list
def test_log_payload_shape(
    api_client: APIClient, system_admin: User, log_entries: list[ReminderLog]
) -> None:
    """A log row carries exactly the documented fields, with the user's full name."""
    api_client.force_login(system_admin)

    body = api_client.get(LOG_URL).json()

    assert body["count"] == 3
    row = body["results"][0]
    assert set(row) == {
        "id",
        "user_id",
        "user_name",
        "membership_id",
        "kind",
        "sent_at",
        "to_email",
    }
    assert row["user_name"] == "Ada Byron"


def test_log_is_newest_first(
    api_client: APIClient, system_admin: User, log_entries: list[ReminderLog]
) -> None:
    """The log lists entries ordered by ``sent_at`` descending."""
    api_client.force_login(system_admin)

    kinds = [row["kind"] for row in api_client.get(LOG_URL).json()["results"]]

    assert kinds == [ReminderKind.T60, ReminderKind.T30, ReminderKind.T7]


def test_log_filters_by_kind(
    api_client: APIClient, system_admin: User, log_entries: list[ReminderLog]
) -> None:
    """``?kind=`` narrows the log to entries of that kind."""
    api_client.force_login(system_admin)

    body = api_client.get(LOG_URL, {"kind": ReminderKind.T30}).json()

    assert body["count"] == 1
    assert body["results"][0]["kind"] == ReminderKind.T30


def test_log_rejects_an_unknown_kind(
    api_client: APIClient, system_admin: User, log_entries: list[ReminderLog]
) -> None:
    """A ``kind`` value that is not one of the five reminder kinds is a 400."""
    api_client.force_login(system_admin)
    assert api_client.get(LOG_URL, {"kind": "t99"}).status_code == 400


def test_log_filters_by_date_range(
    api_client: APIClient, system_admin: User, log_entries: list[ReminderLog]
) -> None:
    """``?from=`` and ``?to=`` narrow the log to entries sent on or after/before it."""
    api_client.force_login(system_admin)
    yesterday = (timezone.localdate() - timedelta(days=1)).isoformat()

    since = api_client.get(LOG_URL, {"from": yesterday}).json()
    until = api_client.get(LOG_URL, {"to": yesterday}).json()

    assert since["count"] == 2
    assert until["count"] == 2


def test_log_searches_by_email(
    api_client: APIClient, system_admin: User, log_entries: list[ReminderLog]
) -> None:
    """``?search=`` narrows the log to entries whose recipient address matches."""
    api_client.force_login(system_admin)

    body = api_client.get(LOG_URL, {"search": "t7@example.test"}).json()

    assert body["count"] == 1


# -------------------------------------------------------------------- the run
def test_run_dry_run_reports_without_writing(
    api_client: APIClient,
    system_admin: User,
    annual_plan: MembershipPlan,
    mailoutbox: list[EmailMessage],
) -> None:
    """A dry run through the endpoint reports what it would send but sends nothing."""
    user = UserFactory(email="expiring@example.test")
    MembershipFactory(
        user=user,
        plan=annual_plan,
        starts_on=timezone.localdate() - timedelta(days=335),
        ends_on=timezone.localdate() + timedelta(days=30),
    )
    api_client.force_login(system_admin)

    body = api_client.post(RUN_URL, {"dry_run": True}).json()

    assert body == {"sent": 1, "skipped": 0}
    assert mailoutbox == []
    assert ReminderLog.objects.count() == 0


def test_run_sends_for_real(
    api_client: APIClient,
    system_admin: User,
    annual_plan: MembershipPlan,
    mailoutbox: list[EmailMessage],
) -> None:
    """A live run through the endpoint sends the email and logs it."""
    user = UserFactory(email="lastweek@example.test")
    MembershipFactory(
        user=user,
        plan=annual_plan,
        starts_on=timezone.localdate() - timedelta(days=358),
        ends_on=timezone.localdate() + timedelta(days=7),
    )
    api_client.force_login(system_admin)

    body = api_client.post(RUN_URL, {}).json()

    assert body == {"sent": 1, "skipped": 0}
    assert len(mailoutbox) == 1
    assert ReminderLog.objects.get().kind == ReminderKind.T7


def test_run_is_idempotent(
    api_client: APIClient,
    system_admin: User,
    annual_plan: MembershipPlan,
    mailoutbox: list[EmailMessage],
) -> None:
    """A second live run the same day sends nothing and reports the skip."""
    user = UserFactory(email="twice@example.test")
    MembershipFactory(
        user=user,
        plan=annual_plan,
        starts_on=timezone.localdate() - timedelta(days=358),
        ends_on=timezone.localdate() + timedelta(days=7),
    )
    api_client.force_login(system_admin)

    api_client.post(RUN_URL, {})
    body = api_client.post(RUN_URL, {}).json()

    assert body == {"sent": 0, "skipped": 1}
    assert len(mailoutbox) == 1


def test_run_with_no_one_due_is_still_a_200(api_client: APIClient, system_admin: User) -> None:
    """A run with no membership due reports zero sent and zero skipped, not an error."""
    api_client.force_login(system_admin)

    response = api_client.post(RUN_URL, {"dry_run": False})

    assert response.status_code == 200
    assert response.json() == {"sent": 0, "skipped": 0}


def test_run_rejects_a_non_boolean_dry_run(api_client: APIClient, system_admin: User) -> None:
    """A ``dry_run`` value that is not a boolean is a 400."""
    api_client.force_login(system_admin)
    assert api_client.post(RUN_URL, {"dry_run": "perhaps"}).status_code == 400


def test_log_records_survive_a_membership_being_read_back(
    api_client: APIClient,
    system_admin: User,
    annual_plan: MembershipPlan,
    mailoutbox: list[EmailMessage],
) -> None:
    """The log row points at the term it was sent about."""
    user = UserFactory(email="linked@example.test")
    membership = MembershipFactory(
        user=user,
        plan=annual_plan,
        starts_on=timezone.localdate() - timedelta(days=358),
        ends_on=timezone.localdate() + timedelta(days=7),
    )
    api_client.force_login(system_admin)

    api_client.post(RUN_URL, {})
    row = api_client.get(LOG_URL).json()["results"][0]

    assert row["membership_id"] == membership.id
    assert row["user_id"] == user.id
    assert row["to_email"] == "linked@example.test"
