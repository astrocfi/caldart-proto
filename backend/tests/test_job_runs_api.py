"""The scheduled jobs' records over the API -- ``system_admin`` only.

``GET /system/jobs`` says how each job stands, ``GET /system/jobs/{job}/runs`` lists a
job's runs, and ``GET /system/jobs/runs/{id}`` reads one run with its output.  The
health payload carries the same states for its **Scheduled jobs** check.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from django.db import connection
from django.utils import timezone
from pytest_django import Settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import SYSTEM_ADMIN
from apps.mail.bounces import IMAP_URL_FORM
from apps.sysadmin.jobs import JOBS, JOBS_BY_KEY
from apps.sysadmin.models import JobRun
from tests.conftest import role_matrix

pytestmark = pytest.mark.django_db

JOBS_URL = "/api/v1/system/jobs"
HEALTH_URL = "/api/v1/system/health"


def runs_url(job: str) -> str:
    """The list of ``job``'s runs."""
    return f"{JOBS_URL}/{job}/runs"


def run_url(run_id: int) -> str:
    """One run's record."""
    return f"{JOBS_URL}/runs/{run_id}"


@pytest.fixture
def a_failed_run(system_admin: User) -> JobRun:
    """A finished, failed renewal run that wrote some output."""
    started = timezone.now() - timedelta(minutes=5)
    return JobRun.objects.create(
        job="renewals",
        arguments="--scan-id 4",
        started_at=started,
        finished_at=started + timedelta(minutes=2),
        outcome=JobRun.Outcome.FAILED,
        exit_status=1,
        started_by=system_admin,
        output="noticed 2, charged 1\n",
        error="2 renewal charges need checking; settle them on the finance Renewals tab",
    )


@pytest.fixture
def admin_client(api_client: APIClient, system_admin: User) -> APIClient:
    """The API client signed in as a system administrator."""
    api_client.force_login(system_admin)
    return api_client


# ---------------------------------------------------------------- role matrix
@pytest.mark.parametrize(("role", "allowed"), role_matrix(SYSTEM_ADMIN))
def test_job_list_role_matrix(
    api_client: APIClient, all_role_users: dict[str, User], role: str, allowed: bool
) -> None:
    """Only ``system_admin`` reads the jobs; everyone else gets 403."""
    api_client.force_login(all_role_users[role])
    assert api_client.get(JOBS_URL).status_code == (200 if allowed else 403)


@pytest.mark.parametrize(("role", "allowed"), role_matrix(SYSTEM_ADMIN))
def test_job_runs_role_matrix(
    api_client: APIClient, all_role_users: dict[str, User], role: str, allowed: bool
) -> None:
    """Only ``system_admin`` reads a job's runs; everyone else gets 403."""
    api_client.force_login(all_role_users[role])
    assert api_client.get(runs_url("renewals")).status_code == (200 if allowed else 403)


@pytest.mark.parametrize(("role", "allowed"), role_matrix(SYSTEM_ADMIN))
def test_job_run_role_matrix(
    api_client: APIClient,
    all_role_users: dict[str, User],
    a_failed_run: JobRun,
    role: str,
    allowed: bool,
) -> None:
    """Only ``system_admin`` reads a run's output; everyone else gets 403."""
    api_client.force_login(all_role_users[role])
    assert api_client.get(run_url(a_failed_run.pk)).status_code == (200 if allowed else 403)


@pytest.mark.parametrize("url", [JOBS_URL, runs_url("renewals"), run_url(1)])
def test_the_job_endpoints_need_a_session(api_client: APIClient, url: str) -> None:
    """An anonymous caller gets a 401."""
    assert api_client.get(url).status_code == 401


# ------------------------------------------------------------------- the jobs
def test_the_job_list_names_every_job_in_order(admin_client: APIClient) -> None:
    """Every job in the table, in its order."""
    body = admin_client.get(JOBS_URL).json()
    assert [row["job"] for row in body] == [job.key for job in JOBS]


def test_the_job_list_names_each_job(admin_client: APIClient) -> None:
    """Each row carries the job's name on the System pages."""
    body = admin_client.get(JOBS_URL).json()
    assert body[0]["name"] == JOBS[0].label


def test_the_job_list_reports_a_failure(admin_client: APIClient, a_failed_run: JobRun) -> None:
    """A job whose latest run failed reads ``failed``, with that run."""
    row = next(row for row in admin_client.get(JOBS_URL).json() if row["job"] == "renewals")
    assert (row["state"], row["last_run"]["id"]) == ("failed", a_failed_run.pk)


def test_a_job_that_has_not_run_reads_a_null_last_run(admin_client: APIClient) -> None:
    """``last_run`` is null for a job that hasn't run."""
    row = admin_client.get(JOBS_URL).json()[0]
    assert row["last_run"] is None


# ------------------------------------------------------------------- the runs
def test_the_runs_list_is_paginated_newest_first(admin_client: APIClient) -> None:
    """The runs come newest first, inside the standard page."""
    now = timezone.now()
    older = JobRun.objects.create(job="bounces", started_at=now - timedelta(hours=2))
    newer = JobRun.objects.create(job="bounces", started_at=now - timedelta(hours=1))
    body = admin_client.get(runs_url("bounces")).json()
    assert [row["id"] for row in body["results"]] == [newer.pk, older.pk]


def test_the_runs_list_holds_only_its_jobs_runs(
    admin_client: APIClient, a_failed_run: JobRun
) -> None:
    """Another job's runs are left out."""
    body = admin_client.get(runs_url("bounces")).json()
    assert body["count"] == 0


def test_a_listed_run_leaves_its_output_out(admin_client: APIClient, a_failed_run: JobRun) -> None:
    """The list answers each run without its output."""
    row = admin_client.get(runs_url("renewals")).json()["results"][0]
    assert "output" not in row


def test_a_listed_run_names_who_started_it(
    admin_client: APIClient, a_failed_run: JobRun, system_admin: User
) -> None:
    """``started_by_name`` is the administrator who pressed **Run now**."""
    row = admin_client.get(runs_url("renewals")).json()["results"][0]
    assert row["started_by_name"] == system_admin.display_name


def test_a_server_run_leaves_the_starter_blank(admin_client: APIClient) -> None:
    """A run the server started has a blank ``started_by_name``."""
    JobRun.objects.create(job="bounces")
    row = admin_client.get(runs_url("bounces")).json()["results"][0]
    assert row["started_by_name"] == ""


def test_a_stale_run_reads_as_stopped(admin_client: APIClient) -> None:
    """An unfinished run older than its job's stale limit is listed as ``stopped``."""
    stale = JOBS_BY_KEY["bounces"].stale_after
    JobRun.objects.create(job="bounces", started_at=timezone.now() - stale - timedelta(minutes=1))
    row = admin_client.get(runs_url("bounces")).json()["results"][0]
    assert row["outcome"] == "stopped"


def test_a_young_unfinished_run_reads_as_running(admin_client: APIClient) -> None:
    """An unfinished run inside its stale limit is ``running``."""
    JobRun.objects.create(job="bounces")
    row = admin_client.get(runs_url("bounces")).json()["results"][0]
    assert row["outcome"] == "running"


def test_an_unknown_job_is_not_found(admin_client: APIClient) -> None:
    """A job key the table does not have answers 404."""
    response = admin_client.get(runs_url("nonsense"))
    assert (response.status_code, response.json()) == (404, {"detail": "No such scheduled job."})


# -------------------------------------------------------------------- one run
def test_one_run_carries_its_output(admin_client: APIClient, a_failed_run: JobRun) -> None:
    """The run's own page has its output, its error, and its traceback."""
    body = admin_client.get(run_url(a_failed_run.pk)).json()
    expected: dict[str, Any] = {
        "id": a_failed_run.pk,
        "job": "renewals",
        "name": "Automatic renewal charges",
        "arguments": "--scan-id 4",
        "outcome": "failed",
        "exit_status": 1,
        "output": "noticed 2, charged 1\n",
        "output_truncated": False,
        "error": a_failed_run.error,
        "traceback": "",
    }
    assert {key: body[key] for key in expected} == expected


def test_a_missing_run_is_not_found(admin_client: APIClient) -> None:
    """An id that isn't a run's answers 404."""
    assert admin_client.get(run_url(999_999)).status_code == 404


# ------------------------------------------------------------------ the health
def test_health_carries_the_jobs(admin_client: APIClient, backup_dir: Path) -> None:
    """``scheduled_jobs`` in the health payload lists every job."""
    body = admin_client.get(HEALTH_URL).json()
    assert [row["job"] for row in body["scheduled_jobs"]] == [job.key for job in JOBS]


def test_health_reports_a_failed_job(
    admin_client: APIClient, backup_dir: Path, a_failed_run: JobRun
) -> None:
    """The failed renewal run reaches the health payload with its error."""
    body = admin_client.get(HEALTH_URL).json()
    row = next(row for row in body["scheduled_jobs"] if row["job"] == "renewals")
    assert row["last_run"]["error"] == a_failed_run.error


def test_health_reads_the_jobs_as_unknown_while_their_table_is_missing(
    admin_client: APIClient, backup_dir: Path
) -> None:
    """Before the record's migration is applied, health answers, with the jobs unknown."""
    with connection.schema_editor() as editor:
        editor.delete_model(JobRun)
    response = admin_client.get(HEALTH_URL)
    assert (response.status_code, response.json()["scheduled_jobs"]) == (200, None)


# ----------------------------------------------------------- the outcome filter
def test_the_failed_filter_keeps_failed_and_stopped_runs(
    admin_client: APIClient, a_failed_run: JobRun
) -> None:
    """``?outcome=failed`` lists the failed run and the stopped one, newest first."""
    stale = JOBS_BY_KEY["renewals"].stale_after
    stopped = JobRun.objects.create(
        job="renewals", started_at=timezone.now() - stale - timedelta(minutes=1)
    )
    JobRun.objects.create(job="renewals", outcome=JobRun.Outcome.SUCCEEDED, exit_status=0)
    JobRun.objects.create(job="renewals")
    body = admin_client.get(runs_url("renewals"), {"outcome": "failed"}).json()
    assert [row["id"] for row in body["results"]] == [a_failed_run.pk, stopped.pk]


def test_another_outcome_filter_is_refused(admin_client: APIClient) -> None:
    """Any other ``outcome`` answers 400 naming the one it takes."""
    response = admin_client.get(runs_url("renewals"), {"outcome": "succeeded"})
    assert (response.status_code, response.json()) == (
        400,
        {"outcome": ["Choose failed, or leave it out."]},
    )


# ----------------------------------------------- a real Run now in the request
REMINDERS_RUN_URL = "/api/v1/system/reminders/run"
STATEMENTS_RUN_URL = "/api/v1/system/statements/run"
BOUNCES_RUN_URL = "/api/v1/system/bounces/run"
BULK_RUN_URL = "/api/v1/system/bulk-email/run"


def _only_run() -> JobRun:
    """The one run recorded."""
    runs = list(JobRun.objects.all())
    assert len(runs) == 1
    return runs[0]


def test_a_real_reminder_run_now_is_recorded_under_the_caller(
    admin_client: APIClient, system_admin: User
) -> None:
    """A real **Run now** of the reminders is recorded, started by the caller."""
    admin_client.post(REMINDERS_RUN_URL, {"dry_run": False}, format="json")
    run = _only_run()
    assert (run.job, run.started_by, run.outcome) == (
        "reminders",
        system_admin,
        JobRun.Outcome.SUCCEEDED,
    )


def test_a_practice_run_now_does_not_leave_a_record(admin_client: APIClient) -> None:
    """A practice run doesn't change anything, so it isn't recorded."""
    admin_client.post(REMINDERS_RUN_URL, {"dry_run": True}, format="json")
    assert JobRun.objects.count() == 0


def test_a_real_run_now_keeps_what_the_run_reports(admin_client: APIClient) -> None:
    """The record's output is the lines the command would print."""
    admin_client.post(STATEMENTS_RUN_URL, {"dry_run": False, "year": 2025}, format="json")
    assert "2025" in _only_run().output


def test_a_statements_run_now_records_its_year(admin_client: APIClient) -> None:
    """The year a statements run sent for is its ``--year`` option."""
    admin_client.post(STATEMENTS_RUN_URL, {"dry_run": False, "year": 2025}, format="json")
    assert _only_run().arguments == "--year 2025"


def test_a_failing_bounce_run_now_is_recorded_failed(
    admin_client: APIClient, settings: Settings
) -> None:
    """A mailbox the check can't read fails the run with the check's own sentence."""
    settings.BOUNCE_IMAP_URL = "not-a-url"
    settings.BOUNCE_ADDRESS = "bounces@caldart.example.org"
    response = admin_client.post(BOUNCES_RUN_URL, {"dry_run": False}, format="json")
    run = _only_run()
    assert response.status_code == 400
    assert (run.outcome, run.exit_status, run.error) == (
        JobRun.Outcome.FAILED,
        1,
        IMAP_URL_FORM,
    )


def test_a_quiet_bulk_run_now_is_recorded_idle(admin_client: APIClient) -> None:
    """A **Run now** of the bulk sender without anything to send keeps one idle record."""
    admin_client.post(BULK_RUN_URL)
    admin_client.post(BULK_RUN_URL)
    assert list(JobRun.objects.values_list("job", "idle")) == [("bulk-email", True)]


def test_a_real_run_now_clears_a_failed_job(admin_client: APIClient, system_admin: User) -> None:
    """After a failed statements run, a real Run now that succeeds reads the job well."""
    JobRun.objects.create(
        job="statements",
        started_at=timezone.now() - timedelta(hours=1),
        outcome=JobRun.Outcome.FAILED,
        exit_status=1,
        error="1 statement email could not be sent",
    )
    admin_client.post(STATEMENTS_RUN_URL, {"dry_run": False, "year": 2025}, format="json")
    row = next(row for row in admin_client.get(JOBS_URL).json() if row["job"] == "statements")
    assert row["last_run"]["outcome"] == "succeeded"
