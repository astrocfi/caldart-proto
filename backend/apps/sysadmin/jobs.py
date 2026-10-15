"""The jobs the server runs on a schedule, and whether each is running as it should.

:data:`JOBS` is the one table of them: each job's key (the ``<key>`` of its
``deploy/systemd/caldart-<key>.timer``), the management command its unit runs through
``manage.py run_job``, the name the website gives it, the timer's ``OnCalendar=``
expression, how late a run may start before the job counts as overdue, and how long
a run may go on before it counts as stopped.  A test holds the table to the timer
and service files, so the two cannot drift apart.  Every timer names the site's time
zone, ``TIME_ZONE``, so a timer fires at the same moment the table expects whatever
time zone the server itself is set to.

:func:`job_statuses` reads each job's latest :class:`~apps.sysadmin.models.JobRun`
against its schedule, for the **Scheduled jobs** health check and ``GET /system/jobs``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db.migrations.recorder import MigrationRecorder
from django.utils import timezone

from apps.sysadmin.models import JobRun


@dataclass(frozen=True)
class Job:
    """One scheduled job: what runs, what it is called, and when it is due."""

    key: str
    command: str
    label: str
    on_calendar: str
    grace: timedelta
    stale_after: timedelta


#: Every scheduled job, in the order the server runs them through a day.  ``grace``
#: covers the timer's randomized delay and a late start; ``stale_after`` is at least the
#: unit's ``TimeoutStartSec``, after which systemd has stopped the run anyway.
JOBS: tuple[Job, ...] = (
    Job(
        key="backup",
        command="db_backup",
        label="Nightly backup",
        on_calendar="*-*-* 03:30:00 America/Los_Angeles",
        grace=timedelta(hours=2),
        stale_after=timedelta(hours=2),
    ),
    Job(
        key="registry",
        command="import_faa_registry",
        label="FAA aircraft data load",
        on_calendar="*-*-* 04:30:00 America/Los_Angeles",
        grace=timedelta(hours=2),
        stale_after=timedelta(hours=1),
    ),
    Job(
        key="reports",
        command="send_scheduled_reports",
        label="Scheduled reports",
        on_calendar="*-*-* 06:00:00 America/Los_Angeles",
        grace=timedelta(hours=2),
        stale_after=timedelta(hours=1),
    ),
    Job(
        key="renewals",
        command="run_auto_renewals",
        label="Automatic renewal charges",
        on_calendar="*-*-* 06:30:00 America/Los_Angeles",
        grace=timedelta(hours=2),
        stale_after=timedelta(hours=1),
    ),
    Job(
        key="statements",
        command="send_year_statements",
        label="Year-end statements",
        on_calendar="*-01-15 06:45:00 America/Los_Angeles",
        grace=timedelta(hours=2),
        stale_after=timedelta(hours=1),
    ),
    Job(
        key="reminders",
        command="send_renewal_reminders",
        label="Renewal reminder emails",
        on_calendar="*-*-* 07:00:00 America/Los_Angeles",
        grace=timedelta(hours=2),
        stale_after=timedelta(hours=1),
    ),
    Job(
        key="bounces",
        command="check_bounces",
        label="Bounce check",
        on_calendar="*-*-* *:20:00 America/Los_Angeles",
        grace=timedelta(minutes=30),
        stale_after=timedelta(minutes=30),
    ),
    Job(
        key="bulk-email",
        command="send_bulk_emails",
        label="Bulk email sender",
        on_calendar="*-*-* *:*:00 America/Los_Angeles",
        grace=timedelta(minutes=10),
        # The unit doesn't set a timeout: a large send runs as long as its pacing takes.
        stale_after=timedelta(hours=12),
    ),
)

#: Each job by its key.
JOBS_BY_KEY: dict[str, Job] = {job.key: job for job in JOBS}

#: Each job by the management command its unit runs.
JOBS_BY_COMMAND: dict[str, Job] = {job.command: job for job in JOBS}

#: A timer starts a run at or after its trigger, but the two clocks are read by
#: different processes, so a run that starts this much before a trigger still counts.
CLOCK_SLACK = timedelta(minutes=1)

#: The ``OnCalendar=`` forms the table uses: ``*-MM-DD hh:mm:ss`` with any field ``*``,
#: then the time zone the timer fires in.
ON_CALENDAR = re.compile(
    r"^(\*)-(\*|\d{2})-(\*|\d{2}) (\*|\d{2}):(\*|\d{2}):(\d{2})(?: ([A-Za-z_/+-]+))?$"
)

#: How far back :func:`previous_trigger` looks: a little over the longest interval.
LOOKBACK_DAYS = 400


class JobState(StrEnum):
    """How a job stands, judged from its latest run and its schedule."""

    #: The latest run succeeded and none is overdue.
    OK = "ok"
    #: A run is under way and younger than the job's stale limit.
    RUNNING = "running"
    #: Nothing has run yet, and nothing was due since runs began to be recorded.
    WAITING = "waiting"
    #: The latest run failed.
    FAILED = "failed"
    #: The latest run is still unfinished past the job's stale limit.
    STOPPED = "stopped"
    #: The latest run succeeded, but no run started since a later trigger.
    OVERDUE = "overdue"
    #: Nothing has run, though a trigger has passed since runs began to be recorded.
    NEVER_RUN = "never_run"


#: Every state :func:`job_statuses` reports, as the API spells them.
JOB_STATES: tuple[str, ...] = tuple(state.value for state in JobState)


@dataclass(frozen=True)
class JobStatus:
    """One job's state, its latest run, and the trigger it missed when overdue."""

    job: Job
    state: JobState
    last_run: JobRun | None
    missed_at: datetime | None


#: A run unfinished past its job's ``stale_after``, as the API reads it: the process
#: that ran it is gone, so it will not finish.
STOPPED = "stopped"

#: Every outcome the API reports for a run: the stored ones and :data:`STOPPED`.
RUN_OUTCOMES: tuple[str, ...] = (*JobRun.Outcome.values, STOPPED)


def run_outcome(run: JobRun, now: datetime | None = None) -> str:
    """``run``'s outcome as of ``now``: its stored one, or :data:`STOPPED`.

    A run still marked ``running`` longer than its job's ``stale_after`` reads as
    stopped; the row itself is left as it is, so a run that does finish late is
    recorded as it ended.
    """
    if run.outcome != JobRun.Outcome.RUNNING:
        return run.outcome
    job = JOBS_BY_KEY.get(run.job)
    if job is not None and (now or timezone.now()) - run.started_at > job.stale_after:
        return STOPPED
    return run.outcome


def _calendar_fields(on_calendar: str) -> tuple[list[int | None], ZoneInfo]:
    """The month, day, hour, minute, and second of an ``OnCalendar=`` value, and its zone.

    ``None`` stands for a ``*``.  The zone is the one the value names, or the site's
    ``TIME_ZONE`` when it doesn't name one.  Raises ``ValueError`` for any other form,
    so a table entry the schedule cannot read fails at once.
    """
    match = ON_CALENDAR.fullmatch(on_calendar)
    if match is None:
        raise ValueError(f"Not an OnCalendar form this table reads: {on_calendar!r}")
    *parts, zone = match.groups()[1:]
    fields = [None if part == "*" else int(part) for part in parts]
    return fields, ZoneInfo(zone or settings.TIME_ZONE)


def _latest_at_or_before(options: list[list[int]], limit: list[int]) -> list[int] | None:
    """The greatest tuple, one value from each option list, not after ``limit``.

    The lists are compared field by field from the first, as a clock's hour, minute,
    and second are; ``None`` when every combination is later than ``limit``.
    """
    if not options:
        return []
    head, rest = options[0], options[1:]
    for value in sorted(head, reverse=True):
        if value > limit[0]:
            continue
        if value < limit[0]:
            return [value, *(max(field) for field in rest)]
        tail = _latest_at_or_before(rest, limit[1:])
        if tail is not None:
            return [value, *tail]
    return None


def previous_trigger(on_calendar: str, moment: datetime) -> datetime | None:
    """The last time at or before ``moment`` that the ``OnCalendar=`` value fires.

    The wall clock is read in the time zone the value names, as systemd reads it, and
    the answer is an aware time in UTC.  ``None`` when the value has not fired in the
    last :data:`LOOKBACK_DAYS` days.
    """
    (month, day, hour, minute, second), zone = _calendar_fields(on_calendar)
    wall = moment.astimezone(zone).replace(tzinfo=None)
    times = [
        list(range(24)) if hour is None else [hour],
        list(range(60)) if minute is None else [minute],
        [second if second is not None else 0],
    ]
    for back in range(LOOKBACK_DAYS):
        date = (wall - timedelta(days=back)).date()
        if month is not None and date.month != month:
            continue
        if day is not None and date.day != day:
            continue
        limit = [wall.hour, wall.minute, wall.second] if back == 0 else [23, 59, 59]
        clock = _latest_at_or_before(times, limit)
        if clock is None:
            continue
        hour_, minute_, second_ = clock[0], clock[1], clock[2]
        local = datetime(date.year, date.month, date.day, hour_, minute_, second_, tzinfo=zone)
        return local.astimezone(UTC)
    return None


def recording_since() -> datetime | None:
    """When the site began to record scheduled runs, or ``None`` if it cannot tell.

    That is when this app's first migration was applied: on a fresh install the
    moment it was installed, and on an older site the upgrade that brought the
    record in.  A job is only expected to have run once a trigger has passed since.
    """
    return (
        MigrationRecorder.Migration.objects.filter(app="sysadmin")
        .order_by("applied")
        .values_list("applied", flat=True)
        .first()
    )


def _job_status(
    job: Job, last_run: JobRun | None, now: datetime, since: datetime | None
) -> JobStatus:
    """Judge ``job`` from its latest run, ``now``, and when recording began."""
    due = previous_trigger(job.on_calendar, now - job.grace)
    if last_run is None:
        if due is None or since is None or due < since:
            return JobStatus(job, JobState.WAITING, None, None)
        return JobStatus(job, JobState.NEVER_RUN, None, due)
    if last_run.outcome == JobRun.Outcome.FAILED:
        return JobStatus(job, JobState.FAILED, last_run, None)
    if last_run.outcome == JobRun.Outcome.RUNNING:
        if run_outcome(last_run, now) == STOPPED:
            return JobStatus(job, JobState.STOPPED, last_run, None)
        return JobStatus(job, JobState.RUNNING, last_run, None)
    if due is not None and last_run.started_at < due - CLOCK_SLACK:
        return JobStatus(job, JobState.OVERDUE, last_run, due)
    return JobStatus(job, JobState.OK, last_run, None)


def job_statuses(now: datetime | None = None) -> list[JobStatus]:
    """Every job in :data:`JOBS` order, judged as of ``now`` (the current time).

    A job whose latest run failed is ``failed``; one whose latest run is unfinished
    after its ``stale_after`` is ``stopped``; one still inside it is ``running``.  A
    job whose latest run succeeded is ``overdue`` when its timer fired at least
    ``grace`` ago and no run started since, naming that trigger as ``missed_at``, and
    ``ok`` otherwise.  A job that hasn't run at all is ``never_run``, with
    ``missed_at``, when such a trigger falls after :func:`recording_since`, and
    ``waiting`` before.  A run started with **Run now** counts the same as one the
    timer started.  Each job's latest run is one lookup on the job's index, without
    its output.
    """
    moment = now or timezone.now()
    since = recording_since()
    return [_job_status(job, latest_run(job.key), moment, since) for job in JOBS]


def latest_run(key: str) -> JobRun | None:
    """The job ``key``'s newest run, without its output and traceback, or ``None``."""
    return (
        JobRun.objects.filter(job=key)
        .select_related("started_by")
        .defer("output", "traceback")
        .order_by("-started_at", "-id")
        .first()
    )
