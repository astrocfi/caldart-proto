"""A live renewal scan started from the portal runs outside the request.

``docs/developer/api-renewals.rst`` (running the scan) is the contract.  The process
launcher is replaced by a recorder, so no test starts a real process; the command the
launcher would start is driven directly with ``call_command``.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, timedelta
from io import StringIO

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.management import CommandError, call_command
from django.utils import timezone
from pytest_django.fixtures import Settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import SYSTEM_ADMIN
from apps.members.models import MembershipPlan, MembershipStatusChoices
from apps.payments.management.commands import run_auto_renewals as command_module
from apps.payments.models import Payment, RenewalScan
from apps.payments.renewals import background
from apps.payments.renewals import scan as scan_module
from apps.payments.renewals.scan import RenewalRun, run_auto_renewals
from caldart import audit
from tests.conftest import audit_messages, role_matrix
from tests.factories import MembershipFactory, RenewalMandateFactory

pytestmark = pytest.mark.django_db

RUN = "/api/v1/system/renewals/run"

#: Minutes after which an unfinished scan is taken to have died, in these tests.
STALE_MINUTES = 60


def scan_url(scan_id: int) -> str:
    """Where the Scheduled tasks page reads a live scan back."""
    return f"/api/v1/system/renewals/runs/{scan_id}"


@pytest.fixture
def launched(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> list[int]:
    """The ids of the scan rows handed to the launcher, which doesn't start anything."""
    settings.RENEWAL_STALE_MINUTES = STALE_MINUTES
    started: list[int] = []
    monkeypatch.setattr(background, "launch_scan", lambda scan: started.append(scan.pk))
    return started


def renewal_due_today(user: User, plan: MembershipPlan, today: date) -> None:
    """A mock-provider renewal whose term, and so whose charge, falls on ``today``."""
    MembershipFactory(
        user=user,
        plan=plan,
        starts_on=today - timedelta(days=364),
        ends_on=today,
        status=MembershipStatusChoices.ACTIVE,
    )
    RenewalMandateFactory(user=user, plan=plan, next_charge_on=today)


# --------------------------------------------------------------------------
# Starting a live scan
# --------------------------------------------------------------------------
def test_a_live_run_answers_202_with_the_unfinished_scan(
    system_admin_client: APIClient, launched: list[int]
) -> None:
    """The row is written before the answer: started, unfinished, without a result yet."""
    response = system_admin_client.post(RUN, {"dry_run": False}, format="json")
    body = response.json()
    assert response.status_code == 202
    assert body["finished_at"] is None
    assert body["result"] is None


def test_a_run_without_a_body_is_a_live_run(
    system_admin_client: APIClient, launched: list[int]
) -> None:
    """``dry_run`` defaults to false, so an empty body starts a live scan."""
    response = system_admin_client.post(RUN, {}, format="json")
    assert response.status_code == 202


def test_a_live_run_launches_the_scan_it_recorded(
    system_admin_client: APIClient, launched: list[int]
) -> None:
    """The launcher is handed the row the answer describes."""
    system_admin_client.post(RUN, {"dry_run": False}, format="json")
    assert launched == [RenewalScan.objects.get().pk]


def test_a_live_run_records_who_started_it(
    system_admin_client: APIClient, system_admin: User, launched: list[int]
) -> None:
    """The row names the system administrator who pressed the button."""
    system_admin_client.post(RUN, {"dry_run": False}, format="json")
    assert RenewalScan.objects.get().started_by == system_admin


def test_a_live_run_does_not_charge_anything_inside_the_request(
    system_admin_client: APIClient,
    launched: list[int],
    member: User,
    annual_plan: MembershipPlan,
    today: date,
) -> None:
    """The charge belongs to the scan's own process, not to the request."""
    renewal_due_today(member, annual_plan, today)

    system_admin_client.post(RUN, {"dry_run": False}, format="json")

    assert Payment.objects.count() == 0


def test_a_scan_that_cannot_start_is_closed_at_once(
    monkeypatch: pytest.MonkeyPatch, system_admin: User
) -> None:
    """A process that never started does not leave a row that reads as running."""

    def refuse(scan: RenewalScan) -> None:
        raise OSError("no such file")

    monkeypatch.setattr(background, "launch_scan", refuse)
    with pytest.raises(OSError, match="no such file"):
        background.start_scan(system_admin)

    assert RenewalScan.objects.get().error == background.COULD_NOT_START


def test_the_launcher_starts_the_command_in_its_own_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``launch_scan`` runs ``run_auto_renewals --scan-id <id>`` detached."""
    calls: list[tuple[list[str], bool]] = []

    def record(argv: list[str], *, start_new_session: bool) -> None:
        calls.append((argv, start_new_session))

    monkeypatch.setattr(subprocess, "Popen", record)
    scan = RenewalScan.objects.create()
    background.launch_scan(scan)
    argv, detached = calls[0]
    assert argv[-3:] == ["run_auto_renewals", "--scan-id", str(scan.pk)]
    assert argv[1].endswith("manage.py")
    assert detached is True


def test_the_launcher_records_the_run_as_the_administrators(
    monkeypatch: pytest.MonkeyPatch, system_admin: User
) -> None:
    """The scan runs through ``run_job``, naming who pressed **Run now**."""
    calls: list[list[str]] = []

    def record(argv: list[str], *, start_new_session: bool) -> None:
        calls.append(argv)

    monkeypatch.setattr(subprocess, "Popen", record)
    scan = RenewalScan.objects.create(started_by=system_admin)
    background.launch_scan(scan)
    assert calls[0][2:5] == ["run_job", "--started-by", str(system_admin.pk)]


# --------------------------------------------------------------------------
# Reading a scan back
# --------------------------------------------------------------------------
@pytest.mark.parametrize(("role", "allowed"), role_matrix(SYSTEM_ADMIN))
def test_only_a_system_administrator_reads_a_scan(
    api_client: APIClient, all_role_users: dict[str, User], role: str, allowed: bool
) -> None:
    """The scan's actions name members, so only the role that runs it reads it."""
    scan = RenewalScan.objects.create()
    api_client.force_login(all_role_users[role])
    expected = 200 if allowed else 403
    assert api_client.get(scan_url(scan.pk)).status_code == expected


def test_a_finished_scan_reads_back_its_counts(
    system_admin_client: APIClient, launched: list[int]
) -> None:
    """What the scan reported is answered in the shape a dry run answers with."""
    scan = RenewalScan.objects.create()
    background.finish_scan(scan, RenewalRun(today=timezone.localdate(), dry_run=False, charged=2))

    body = system_admin_client.get(scan_url(scan.pk)).json()

    assert body["result"]["charged"] == 2


def test_an_unknown_scan_is_a_404(system_admin_client: APIClient, launched: list[int]) -> None:
    """A scan id nobody wrote is not found, and says so."""
    response = system_admin_client.get(scan_url(999_999))
    assert response.status_code == 404
    assert response.json() == {"detail": "No such renewal run."}


def test_a_scan_inside_the_limit_still_reads_as_running(
    system_admin_client: APIClient, launched: list[int]
) -> None:
    """A scan younger than ``RENEWAL_STALE_MINUTES`` is left unfinished."""
    scan = RenewalScan.objects.create(
        started_at=timezone.now() - timedelta(minutes=STALE_MINUTES - 1)
    )
    assert system_admin_client.get(scan_url(scan.pk)).json()["finished_at"] is None


def test_a_scan_past_the_limit_reads_as_did_not_finish(
    system_admin_client: APIClient, launched: list[int]
) -> None:
    """A scan that outlived ``RENEWAL_STALE_MINUTES`` lost its process, and says so."""
    scan = RenewalScan.objects.create(
        started_at=timezone.now() - timedelta(minutes=STALE_MINUTES + 1)
    )
    body = system_admin_client.get(scan_url(scan.pk)).json()
    assert body["ok"] is False
    assert body["error"] == background.DID_NOT_FINISH


# --------------------------------------------------------------------------
# The command the launcher starts
# --------------------------------------------------------------------------
def test_the_command_fills_in_the_scan_it_was_given(
    system_admin: User, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """The row ends finished, ok, and carrying the charge the scan took."""
    renewal_due_today(member, annual_plan, today)
    scan = RenewalScan.objects.create(started_by=system_admin)

    call_command("run_auto_renewals", scan_id=scan.pk, stdout=StringIO())

    scan.refresh_from_db()
    assert scan.ok is True
    assert scan.result is not None
    assert scan.result["charged"] == 1


def test_the_command_names_whoever_started_the_scan_in_the_audit_log(
    system_admin: User, audit_log: pytest.LogCaptureFixture
) -> None:
    """The run's audit record names the system administrator, not the command."""
    scan = RenewalScan.objects.create(started_by=system_admin)

    call_command("run_auto_renewals", scan_id=scan.pk, stdout=StringIO())

    (line,) = [m for m in audit_messages(audit_log) if f"action={audit.RENEWALS_RUN} " in m]
    assert f"actor={system_admin.pk} " in line


def test_the_command_refuses_a_scan_nobody_wrote() -> None:
    """A ``--scan-id`` that doesn't name a row stops before scanning anything."""
    with pytest.raises(CommandError, match="No renewal scan 999999"):
        call_command("run_auto_renewals", scan_id=999_999, stdout=StringIO())


def test_a_scan_that_raises_is_closed_with_an_error(
    monkeypatch: pytest.MonkeyPatch, system_admin: User
) -> None:
    """The row says the run stopped, and the exception still reaches the operator."""

    def explode(**kwargs: object) -> RenewalRun:
        raise RuntimeError("database went away")

    monkeypatch.setattr(command_module, "run_auto_renewals", explode)
    scan = RenewalScan.objects.create(started_by=system_admin)

    with pytest.raises(RuntimeError, match="database went away"):
        call_command("run_auto_renewals", scan_id=scan.pk, stdout=StringIO())

    scan.refresh_from_db()
    assert scan.error == background.STOPPED_WITH_AN_ERROR


# --------------------------------------------------------------------------
# One live scan at a time
# --------------------------------------------------------------------------
def test_a_second_live_run_while_one_runs_is_a_409(
    system_admin_client: APIClient, launched: list[int]
) -> None:
    """A scan still inside the stale window is running, so nothing more is started."""
    system_admin_client.post(RUN, {"dry_run": False}, format="json")

    response = system_admin_client.post(RUN, {"dry_run": False}, format="json")

    assert response.status_code == 409
    assert response.json() == {"detail": background.ALREADY_RUNNING}
    assert len(launched) == 1


def test_a_refused_live_run_is_recorded_in_the_audit_log(
    system_admin_client: APIClient,
    system_admin: User,
    launched: list[int],
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """The refusal is a WARNING naming the caller and the reason."""
    system_admin_client.post(RUN, {"dry_run": False}, format="json")

    system_admin_client.post(RUN, {"dry_run": False}, format="json")

    assert (
        f"action={audit.RENEWALS_RUN} actor={system_admin.pk} target=- reason=run_in_progress"
        in audit_messages(audit_log)
    )


def test_a_scan_past_the_limit_does_not_block_a_new_one(
    system_admin_client: APIClient, launched: list[int]
) -> None:
    """The old row is closed as not finished, and a new scan starts."""
    old = RenewalScan.objects.create(
        started_at=timezone.now() - timedelta(minutes=STALE_MINUTES + 1)
    )

    response = system_admin_client.post(RUN, {"dry_run": False}, format="json")

    old.refresh_from_db()
    assert response.status_code == 202
    assert old.error == background.DID_NOT_FINISH


def test_a_live_scan_that_finds_another_running_does_not_do_anything(
    monkeypatch: pytest.MonkeyPatch,
    member: User,
    annual_plan: MembershipPlan,
    today: date,
) -> None:
    """A scan that cannot take the lock doesn't charge anyone and exits cleanly."""
    renewal_due_today(member, annual_plan, today)
    monkeypatch.setattr(scan_module, "scan_lock", held_elsewhere)

    call_command("run_auto_renewals", stdout=StringIO())

    assert Payment.objects.count() == 0


def test_a_live_scan_that_finds_another_running_records_why(
    monkeypatch: pytest.MonkeyPatch, system_admin: User, audit_log: pytest.LogCaptureFixture
) -> None:
    """Its row says another run was under way, and the audit log says it was refused."""
    monkeypatch.setattr(scan_module, "scan_lock", held_elsewhere)
    scan = RenewalScan.objects.create(started_by=system_admin)

    call_command("run_auto_renewals", scan_id=scan.pk, stdout=StringIO())

    scan.refresh_from_db()
    assert scan.error == scan_module.ALREADY_RUNNING_MESSAGE
    assert (
        f"action={audit.RENEWALS_RUN} actor={system_admin.pk} target=- reason=run_in_progress"
        in audit_messages(audit_log)
    )


@contextmanager
def held_elsewhere() -> Iterator[bool]:
    """The scan lock as another live scan leaves it: not to be had."""
    yield False


# --------------------------------------------------------------------------
# The stale window
# --------------------------------------------------------------------------
def test_a_stale_window_under_fifteen_minutes_refuses_a_live_scan(settings: Settings) -> None:
    """A claim taken over that soon could still be charging, so no scan starts."""
    settings.RENEWAL_STALE_MINUTES = 14

    with pytest.raises(ImproperlyConfigured, match="RENEWAL_STALE_MINUTES must be at least 15"):
        run_auto_renewals(today=timezone.localdate())


def test_a_stale_window_under_fifteen_minutes_refuses_run_now(
    settings: Settings, system_admin: User
) -> None:
    """Run now refuses to start a scan the setting would let another take over."""
    settings.RENEWAL_STALE_MINUTES = 14

    with pytest.raises(ImproperlyConfigured, match="at least 15"):
        background.start_scan(system_admin)


def test_a_scan_that_finishes_after_reading_as_lost_clears_the_error() -> None:
    """A slow scan closed as not finished, that then finishes, reads as finished."""
    scan = RenewalScan.objects.create(error=background.DID_NOT_FINISH)

    background.finish_scan(scan, RenewalRun(today=timezone.localdate(), dry_run=False))

    scan.refresh_from_db()
    assert scan.error == ""
