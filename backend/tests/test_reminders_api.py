"""The reminder log and manual-run endpoints.

Role matrix first — the log is for ``account_admin`` and ``system_admin``, the
run button for ``system_admin`` alone — then filters and payloads.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.roles import (
    ACCOUNT_ADMIN,
    DART_LEADER,
    MEMBER,
    SYSTEM_ADMIN,
    USER_ADMIN,
    WEBSITE_ADMIN,
)
from apps.reminders.models import ReminderKind, ReminderLog
from tests.factories import MembershipFactory, ReminderLogFactory, UserFactory

pytestmark = pytest.mark.django_db

LOG_URL = "/api/v1/admin/reminders/log"
RUN_URL = "/api/v1/system/reminders/run"


@pytest.fixture
def log_entries(db, annual_plan):
    """Three entries by three members, on three days and of three kinds."""
    entries = []
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
def test_log_role_matrix(api_client, all_role_users, log_entries, role, allowed):
    api_client.force_login(all_role_users[role])
    response = api_client.get(LOG_URL)
    assert response.status_code == (200 if allowed else 403)


def test_log_requires_a_session(api_client):
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
def test_run_role_matrix(api_client, all_role_users, role, allowed):
    api_client.force_login(all_role_users[role])
    response = api_client.post(RUN_URL, {"dry_run": True})
    assert response.status_code == (200 if allowed else 403)


def test_run_requires_a_session(api_client):
    assert api_client.post(RUN_URL, {"dry_run": True}).status_code == 401


# ------------------------------------------------------------------- the list
def test_log_payload_shape(api_client, system_admin, log_entries):
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


def test_log_is_newest_first(api_client, system_admin, log_entries):
    api_client.force_login(system_admin)

    kinds = [row["kind"] for row in api_client.get(LOG_URL).json()["results"]]

    assert kinds == [ReminderKind.T60, ReminderKind.T30, ReminderKind.T7]


def test_log_filters_by_kind(api_client, system_admin, log_entries):
    api_client.force_login(system_admin)

    body = api_client.get(LOG_URL, {"kind": ReminderKind.T30}).json()

    assert body["count"] == 1
    assert body["results"][0]["kind"] == ReminderKind.T30


def test_log_rejects_an_unknown_kind(api_client, system_admin, log_entries):
    api_client.force_login(system_admin)
    assert api_client.get(LOG_URL, {"kind": "t99"}).status_code == 400


def test_log_filters_by_date_range(api_client, system_admin, log_entries):
    api_client.force_login(system_admin)
    yesterday = (timezone.localdate() - timedelta(days=1)).isoformat()

    since = api_client.get(LOG_URL, {"from": yesterday}).json()
    until = api_client.get(LOG_URL, {"to": yesterday}).json()

    assert since["count"] == 2
    assert until["count"] == 2


def test_log_searches_by_email(api_client, system_admin, log_entries):
    api_client.force_login(system_admin)

    body = api_client.get(LOG_URL, {"search": "t7@example.test"}).json()

    assert body["count"] == 1


# -------------------------------------------------------------------- the run
def test_run_dry_run_reports_without_writing(api_client, system_admin, annual_plan, mailoutbox):
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


def test_run_sends_for_real(api_client, system_admin, annual_plan, mailoutbox):
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


def test_run_is_idempotent(api_client, system_admin, annual_plan, mailoutbox):
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


def test_run_with_no_one_due_is_still_a_200(api_client, system_admin):
    api_client.force_login(system_admin)

    response = api_client.post(RUN_URL, {"dry_run": False})

    assert response.status_code == 200
    assert response.json() == {"sent": 0, "skipped": 0}


def test_run_rejects_a_non_boolean_dry_run(api_client, system_admin):
    api_client.force_login(system_admin)
    assert api_client.post(RUN_URL, {"dry_run": "perhaps"}).status_code == 400


def test_log_records_survive_a_membership_being_read_back(
    api_client, system_admin, annual_plan, mailoutbox
):
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
