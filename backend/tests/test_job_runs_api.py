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
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import SYSTEM_ADMIN
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
    """An id no run has answers 404."""
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
