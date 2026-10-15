"""Whether each scheduled job runs as it should, and the table that says when it should.

Every timer names the site's time zone, so the schedule is read in that zone whatever
the server's own is; one test runs with the process's local time zone set to UTC.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from io import StringIO
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from django.core.management import call_command
from django.db.migrations.recorder import MigrationRecorder
from pytest_django import Settings

from apps.accounts.models import User
from apps.sysadmin.jobs import JOBS, JOBS_BY_KEY, Job, JobState, job_statuses, previous_trigger
from apps.sysadmin.models import JobRun
from tests.conftest import DEPLOY_DIR

pytestmark = pytest.mark.django_db

PACIFIC = ZoneInfo("America/Los_Angeles")

#: The units under ``deploy/systemd/`` that run a scheduled job.
SYSTEMD_DIR = DEPLOY_DIR / "systemd"

#: ``OnCalendar=`` and ``TimeoutStartSec=`` lines in a unit file.
ON_CALENDAR_LINE = re.compile(r"^OnCalendar=(.+)$", re.MULTILINE)
TIMEOUT_LINE = re.compile(r"^TimeoutStartSec=(\d+)$", re.MULTILINE)
EXEC_START_LINE = re.compile(r"^ExecStart=(.+)$", re.MULTILINE)


@pytest.fixture
def utc_server() -> Iterator[None]:
    """Run the test with the process's local time zone set to UTC, as many servers are."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("TZ", "UTC")
        time.tzset()
        yield
    # The context has put TZ back; read it again so later tests see the original zone.
    time.tzset()


def pacific(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    """An aware time on the Pacific wall clock."""
    return datetime(year, month, day, hour, minute, tzinfo=PACIFIC)


def recording_began(moment: datetime) -> None:
    """Make the record of runs appear to have begun at ``moment``."""
    MigrationRecorder.Migration.objects.filter(app="sysadmin").update(applied=moment)


def a_run(job: str, started_at: datetime, outcome: str = JobRun.Outcome.SUCCEEDED) -> JobRun:
    """A recorded run of ``job`` started at ``started_at``, ended as ``outcome``."""
    finished = None if outcome == JobRun.Outcome.RUNNING else started_at + timedelta(minutes=1)
    return JobRun.objects.create(
        job=job,
        started_at=started_at,
        finished_at=finished,
        outcome=outcome,
        exit_status=None if finished is None else (0 if outcome == "succeeded" else 1),
    )


def state_of(key: str, now: datetime) -> JobState:
    """``key``'s state as of ``now``."""
    return next(status for status in job_statuses(now) if status.job.key == key).state


# --------------------------------------------------------------- the schedule
@pytest.mark.parametrize(
    ("on_calendar", "moment", "expected"),
    [
        ("*-*-* 06:30:00", pacific(2026, 10, 15, 9), pacific(2026, 10, 15, 6, 30)),
        ("*-*-* 06:30:00", pacific(2026, 10, 15, 6, 29), pacific(2026, 10, 14, 6, 30)),
        ("*-*-* 06:30:00", pacific(2026, 10, 15, 6, 30), pacific(2026, 10, 15, 6, 30)),
        ("*-*-* *:20:00", pacific(2026, 10, 15, 9, 19), pacific(2026, 10, 15, 8, 20)),
        ("*-*-* *:20:00", pacific(2026, 10, 15, 0, 5), pacific(2026, 10, 14, 23, 20)),
        ("*-*-* *:*:00", pacific(2026, 10, 15, 9, 41), pacific(2026, 10, 15, 9, 41)),
        ("*-01-15 06:45:00", pacific(2026, 10, 15), pacific(2026, 1, 15, 6, 45)),
        ("*-01-15 06:45:00", pacific(2026, 1, 15, 6, 44), pacific(2025, 1, 15, 6, 45)),
        (
            "*-*-* 06:30:00 UTC",
            pacific(2026, 10, 15, 9),
            datetime(2026, 10, 15, 6, 30, tzinfo=UTC),
        ),
    ],
    ids=[
        "daily-later-that-day",
        "daily-a-minute-before",
        "daily-on-the-dot",
        "hourly-before-the-minute",
        "hourly-across-midnight",
        "every-minute",
        "yearly-later-that-year",
        "yearly-a-minute-before",
        "a-zone-of-its-own",
    ],
)
def test_the_previous_trigger_is_the_latest_firing_at_or_before(
    on_calendar: str, moment: datetime, expected: datetime
) -> None:
    """``previous_trigger`` reads the wall clock the timer reads."""
    assert previous_trigger(on_calendar, moment) == expected


@pytest.mark.usefixtures("utc_server")
def test_a_utc_server_reads_the_schedule_on_the_sites_clock() -> None:
    """On a server set to UTC, the daily trigger is still 06:30 Pacific time."""
    trigger = previous_trigger(JOBS_BY_KEY["renewals"].on_calendar, pacific(2026, 10, 15, 9))
    assert trigger == pacific(2026, 10, 15, 6, 30)


@pytest.mark.usefixtures("utc_server")
def test_a_utc_server_judges_a_morning_run_on_time() -> None:
    """A run at 06:31 Pacific is on time at 10:00 Pacific, on a server set to UTC."""
    a_run("renewals", pacific(2026, 10, 15, 6, 31))
    assert state_of("renewals", NOW) == JobState.OK


def test_the_previous_trigger_follows_daylight_saving() -> None:
    """The morning after the clocks change, a daily trigger is still at 06:30 local."""
    after_the_change = pacific(2026, 11, 2, 9)
    assert previous_trigger("*-*-* 06:30:00", after_the_change) == pacific(2026, 11, 2, 6, 30)


def test_the_previous_trigger_is_utc() -> None:
    """The answer is an aware time in UTC."""
    trigger = previous_trigger("*-*-* 06:30:00", pacific(2026, 10, 15, 9))
    assert trigger is not None
    assert trigger.tzinfo is UTC


def test_an_unreadable_on_calendar_is_refused() -> None:
    """A form the table cannot read fails at once rather than never matching."""
    with pytest.raises(ValueError, match="Not an OnCalendar form this table reads: 'daily'"):
        previous_trigger("daily", pacific(2026, 10, 15))


# ----------------------------------------------- the table and the unit files
def _timer(job: Job) -> str:
    """The text of ``job``'s timer unit."""
    return (SYSTEMD_DIR / f"caldart-{job.key}.timer").read_text()


def _service(job: Job) -> str:
    """The text of ``job``'s service unit."""
    return (SYSTEMD_DIR / f"caldart-{job.key}.service").read_text()


def test_every_timer_has_a_job() -> None:
    """Each ``caldart-<key>.timer`` shipped is a job in the table, and the other way."""
    timers = {path.stem.removeprefix("caldart-") for path in SYSTEMD_DIR.glob("*.timer")}
    assert timers == {job.key for job in JOBS}


@pytest.mark.parametrize("job", JOBS, ids=[job.key for job in JOBS])
def test_the_table_matches_the_timer(job: Job) -> None:
    """The table's ``on_calendar`` is the timer's ``OnCalendar=`` value."""
    assert ON_CALENDAR_LINE.findall(_timer(job)) == [job.on_calendar]


@pytest.mark.parametrize("job", JOBS, ids=[job.key for job in JOBS])
def test_every_timer_fires_in_the_sites_time_zone(job: Job, settings: Settings) -> None:
    """Each ``OnCalendar=`` names ``TIME_ZONE``, so it fires on the site's clock."""
    (value,) = ON_CALENDAR_LINE.findall(_timer(job))
    assert value.endswith(f" {settings.TIME_ZONE}")


@pytest.mark.parametrize("job", JOBS, ids=[job.key for job in JOBS])
def test_the_service_runs_the_command_through_run_job(job: Job) -> None:
    """The service's one ``ExecStart=`` runs the job's command through ``run_job``."""
    (line,) = EXEC_START_LINE.findall(_service(job))
    assert f"/manage.py run_job {job.command}" in line


@pytest.mark.parametrize("job", JOBS, ids=[job.key for job in JOBS])
def test_a_run_reads_as_stopped_only_after_systemd_would_stop_it(job: Job) -> None:
    """``stale_after`` is at least as long as the unit's ``TimeoutStartSec=``."""
    timeouts = [int(value) for value in TIMEOUT_LINE.findall(_service(job))]
    assert timeouts
    assert timedelta(seconds=timeouts[0]) <= job.stale_after


# ------------------------------------------------------------------ the states
NOW = pacific(2026, 10, 15, 10)


def test_a_recent_success_is_ok() -> None:
    """A job whose latest run succeeded after its last trigger is ``ok``."""
    a_run("renewals", pacific(2026, 10, 15, 6, 31))
    assert state_of("renewals", NOW) == JobState.OK


def test_a_failure_is_failed() -> None:
    """A job whose latest run failed is ``failed``, however recent."""
    a_run("renewals", pacific(2026, 10, 15, 6, 31), JobRun.Outcome.FAILED)
    assert state_of("renewals", NOW) == JobState.FAILED


def test_only_the_latest_run_counts() -> None:
    """A failure followed by a success is ``ok``."""
    a_run("renewals", pacific(2026, 10, 15, 6, 31), JobRun.Outcome.FAILED)
    a_run("renewals", pacific(2026, 10, 15, 8))
    assert state_of("renewals", NOW) == JobState.OK


def test_a_run_inside_its_stale_limit_is_running() -> None:
    """An unfinished run younger than ``stale_after`` is ``running``."""
    a_run("renewals", NOW - timedelta(minutes=10), JobRun.Outcome.RUNNING)
    assert state_of("renewals", NOW) == JobState.RUNNING


def test_a_run_past_its_stale_limit_is_stopped() -> None:
    """An unfinished run older than ``stale_after`` reads as stopped."""
    stale = JOBS_BY_KEY["renewals"].stale_after
    a_run("renewals", NOW - stale - timedelta(minutes=1), JobRun.Outcome.RUNNING)
    assert state_of("renewals", NOW) == JobState.STOPPED


def test_a_success_before_the_last_trigger_is_overdue() -> None:
    """Yesterday's success, with today's trigger long past, is ``overdue``."""
    a_run("renewals", pacific(2026, 10, 14, 6, 31))
    assert state_of("renewals", NOW) == JobState.OVERDUE


def test_an_overdue_job_names_the_trigger_it_missed() -> None:
    """``missed_at`` is the trigger no run followed."""
    a_run("renewals", pacific(2026, 10, 14, 6, 31))
    status = next(s for s in job_statuses(NOW) if s.job.key == "renewals")
    assert status.missed_at == pacific(2026, 10, 15, 6, 30)


def test_a_late_run_inside_the_grace_is_not_overdue() -> None:
    """Shortly after the trigger, yesterday's run still stands."""
    a_run("renewals", pacific(2026, 10, 14, 6, 31))
    assert state_of("renewals", pacific(2026, 10, 15, 7)) == JobState.OK


def test_an_hourly_job_an_hour_behind_is_overdue() -> None:
    """The bounce check, last run two triggers ago, is ``overdue``."""
    a_run("bounces", pacific(2026, 10, 15, 8, 21))
    assert state_of("bounces", NOW) == JobState.OVERDUE


def test_a_job_never_run_since_recording_began_is_never_run() -> None:
    """A trigger past since recording began, without a run since, reads ``never_run``."""
    recording_began(pacific(2026, 10, 13))
    assert state_of("renewals", NOW) == JobState.NEVER_RUN


def test_a_fresh_install_is_waiting() -> None:
    """Installed this morning before the trigger, a job without a run is ``waiting``."""
    recording_began(pacific(2026, 10, 15, 6))
    assert state_of("renewals", pacific(2026, 10, 15, 6, 45)) == JobState.WAITING


def test_a_fresh_install_just_after_a_trigger_is_waiting() -> None:
    """Installed after this morning's trigger, the job waits for tomorrow's."""
    recording_began(pacific(2026, 10, 15, 9))
    assert state_of("renewals", NOW) == JobState.WAITING


def test_the_yearly_job_waits_for_its_first_january() -> None:
    """Installed in March, the statements aren't due until the next January."""
    recording_began(pacific(2026, 3, 1))
    assert state_of("statements", NOW) == JobState.WAITING


def test_a_run_now_run_counts_as_a_run(system_admin: User) -> None:
    """A run started by an administrator keeps the job from reading overdue."""
    run = a_run("renewals", pacific(2026, 10, 15, 9))
    run.started_by = system_admin
    run.save()
    assert state_of("renewals", NOW) == JobState.OK


def test_every_job_has_a_status_in_table_order() -> None:
    """``job_statuses`` answers every job, in the table's order."""
    assert [status.job.key for status in job_statuses(NOW)] == [job.key for job in JOBS]


# --------------------------------------------------------- the health command
def test_the_health_command_lists_each_job(backup_dir: Path) -> None:
    """``manage.py health`` ends with one line per job, naming it and its state."""
    out = StringIO()
    call_command("health", stdout=out)
    lines = out.getvalue().splitlines()[-len(JOBS) :]
    assert [line.split()[0] for line in lines] == [job.label.split()[0] for job in JOBS]


def test_the_health_command_writes_the_jobs_as_json(backup_dir: Path) -> None:
    """``manage.py health --json`` carries ``scheduled_jobs`` as the API answers it."""
    a_run("bounces", datetime.now(tz=UTC), JobRun.Outcome.FAILED)
    out = StringIO()
    call_command("health", "--json", stdout=out)
    rows = json.loads(out.getvalue())["scheduled_jobs"]
    assert next(row for row in rows if row["job"] == "bounces")["state"] == "failed"
