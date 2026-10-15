"""``manage.py run_job``: every scheduled run leaves a record the System pages read.

The wrapper runs a real job's command through ``call_command``; where a test needs the
command to print, log, or fail in a particular way, the service the command calls is
replaced, so the command's own output and error handling still run.
"""

from __future__ import annotations

import io
import logging
import os
import sys
from collections.abc import Callable, Iterator
from datetime import date, timedelta
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError
from django.utils import timezone

from apps.accounts.models import User
from apps.mail.bounces import DISABLED_MESSAGE, BounceRun
from apps.mail.management.commands import check_bounces as check_bounces_command
from apps.sysadmin import recording
from apps.sysadmin.models import JobRun
from apps.sysadmin.recording import OUTPUT_LIMIT, RETENTION, OutputCapture
from apps.sysadmin.services import BackupFile, prune_backups

pytestmark = pytest.mark.django_db

#: What the bounce check's command prints when bounce checking is off.
BOUNCES_OFF = DISABLED_MESSAGE

#: The logger the fake bounce check writes through.
FAKE_LOGGER = "tests.job_runs"


def _writes(stdout: str = "", stderr: str = "") -> Callable[[], None]:
    """A bounce check body that writes ``stdout``, then ``stderr``, to the streams."""

    def body() -> None:
        sys.stdout.write(stdout)
        sys.stderr.write(stderr)

    return body


def _raises(message: str) -> Callable[[], None]:
    """A bounce check body that raises ``RuntimeError(message)``."""

    def body() -> None:
        raise RuntimeError(message)

    return body


def _only_run() -> JobRun:
    """The one run recorded."""
    runs = list(JobRun.objects.all())
    assert len(runs) == 1
    return runs[0]


@pytest.fixture
def fake_bounces(monkeypatch: pytest.MonkeyPatch) -> Callable[[Callable[[], None]], None]:
    """Replace the bounce check's service with one that runs ``body``; nothing is found.

    The command then prints its *bounce checking is off* line after whatever ``body``
    wrote, or never reaches it when ``body`` raises.
    """

    def install(body: Callable[[], None]) -> None:
        def fake(*, dry_run: bool = False) -> BounceRun:
            body()
            return BounceRun(today=date(2026, 10, 15), dry_run=dry_run, enabled=False)

        monkeypatch.setattr(check_bounces_command, "check_bounces", fake)

    return install


@pytest.fixture
def console() -> io.StringIO:
    """The stream the console logger prints to, standing in for the journal."""
    return io.StringIO()


@pytest.fixture
def console_logger(console: io.StringIO) -> Iterator[logging.Logger]:
    """A logger with its own console handler, as production's loggers have."""
    logger = logging.getLogger(FAKE_LOGGER)
    handler = logging.StreamHandler(console)
    handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    yield logger
    logger.removeHandler(handler)
    logger.propagate = True


# ------------------------------------------------------------------ a clean run
def test_a_clean_run_is_recorded_as_succeeded() -> None:
    """A command that returns normally leaves a ``succeeded`` record."""
    call_command("run_job", "check_bounces")
    assert _only_run().outcome == JobRun.Outcome.SUCCEEDED


def test_a_clean_run_exits_zero() -> None:
    """A clean run's exit status is 0."""
    call_command("run_job", "check_bounces")
    assert _only_run().exit_status == 0


def test_a_run_is_recorded_under_its_job_key() -> None:
    """The record names the job by its key, not its command."""
    call_command("run_job", "send_bulk_emails")
    assert _only_run().job == "bulk-email"


def test_a_run_records_the_options_it_was_given() -> None:
    """The options after the command's name are kept as a command line."""
    call_command("run_job", "check_bounces", "--dry-run")
    assert _only_run().arguments == "--dry-run"


def test_a_finished_run_has_a_finish_time() -> None:
    """``finished_at`` is filled in, no earlier than ``started_at``."""
    call_command("run_job", "check_bounces")
    run = _only_run()
    assert run.finished_at is not None
    assert run.finished_at >= run.started_at


def test_a_run_the_server_started_leaves_started_by_empty() -> None:
    """Without ``--started-by`` the run belongs to the server."""
    call_command("run_job", "check_bounces")
    assert _only_run().started_by is None


def test_started_by_names_the_administrator(system_admin: User) -> None:
    """``--started-by`` records the system administrator who pressed **Run now**."""
    call_command("run_job", "--started-by", str(system_admin.pk), "check_bounces")
    assert _only_run().started_by == system_admin


def test_started_by_an_unknown_user_is_refused_unrecorded() -> None:
    """A ``--started-by`` naming nobody is an error, and nothing is recorded."""
    with pytest.raises(CommandError, match="No user 999999"):
        call_command("run_job", "--started-by", "999999", "check_bounces")
    assert JobRun.objects.count() == 0


def test_a_command_that_is_not_a_job_is_refused_unrecorded() -> None:
    """Only the scheduled jobs' commands run through the wrapper."""
    with pytest.raises(CommandError, match="'migrate' is not a scheduled job"):
        call_command("run_job", "migrate")
    assert JobRun.objects.count() == 0


# --------------------------------------------------------------------- output
def test_the_record_keeps_what_the_command_wrote() -> None:
    """The command's ``self.stdout`` lines are in the record."""
    call_command("run_job", "check_bounces")
    assert BOUNCES_OFF in _only_run().output


def test_the_journal_still_gets_what_the_command_wrote(capsys: pytest.CaptureFixture[str]) -> None:
    """The output reaches the real standard output too."""
    call_command("run_job", "check_bounces")
    assert BOUNCES_OFF in capsys.readouterr().out


def test_stdout_and_stderr_are_interleaved_in_the_order_written(
    fake_bounces: Callable[[Callable[[], None]], None],
) -> None:
    """Writes to ``sys.stdout`` and ``sys.stderr`` land in the record in order."""
    fake_bounces(_writes("first to stdout\n", "second to stderr\n"))
    call_command("run_job", "check_bounces")
    output = _only_run().output
    assert output.index("first to stdout") < output.index("second to stderr")
    assert output.index("second to stderr") < output.index(BOUNCES_OFF)


def test_stderr_still_reaches_the_journal(
    fake_bounces: Callable[[Callable[[], None]], None], capsys: pytest.CaptureFixture[str]
) -> None:
    """A write to ``sys.stderr`` reaches the real standard error as well as the record."""
    fake_bounces(_writes(stderr="to stderr\n"))
    call_command("run_job", "check_bounces")
    assert "to stderr" in capsys.readouterr().err


def test_a_console_log_line_is_in_the_record(
    fake_bounces: Callable[[Callable[[], None]], None], console_logger: logging.Logger
) -> None:
    """A logging handler writing to standard error is copied into the record."""
    fake_bounces(lambda: console_logger.warning("a logged warning"))
    call_command("run_job", "check_bounces")
    assert "WARNING a logged warning" in _only_run().output


def test_a_console_log_line_still_reaches_the_journal(
    fake_bounces: Callable[[Callable[[], None]], None],
    console_logger: logging.Logger,
    console: io.StringIO,
) -> None:
    """The console handler prints the line once, as it would without the wrapper."""
    fake_bounces(lambda: console_logger.warning("a logged warning"))
    call_command("run_job", "check_bounces")
    assert console.getvalue() == "WARNING a logged warning\n"


def test_a_log_line_is_in_order_with_the_output(
    fake_bounces: Callable[[Callable[[], None]], None], console_logger: logging.Logger
) -> None:
    """A logged line sits between the writes made before and after it."""

    def body() -> None:
        sys.stdout.write("before the log\n")
        console_logger.warning("a logged warning")
        sys.stderr.write("after the log\n")

    fake_bounces(body)
    call_command("run_job", "check_bounces")
    output = _only_run().output
    assert output.index("before the log") < output.index("a logged warning")
    assert output.index("a logged warning") < output.index("after the log")


def test_the_loggers_handlers_are_as_they_were_after_the_run(
    fake_bounces: Callable[[Callable[[], None]], None], console_logger: logging.Logger
) -> None:
    """The copy of the console handler is gone once the run ends."""
    before = list(console_logger.handlers)
    fake_bounces(lambda: None)
    call_command("run_job", "check_bounces")
    assert console_logger.handlers == before


def test_no_color_codes_reach_the_record() -> None:
    """The command's stream isn't a terminal, so it doesn't write escape codes."""
    call_command("run_job", "send_bulk_emails")
    assert "\x1b[" not in _only_run().output


def test_a_long_output_keeps_its_tail(fake_bounces: Callable[[Callable[[], None]], None]) -> None:
    """Output past the limit is cut from the front: the last characters are kept."""
    fake_bounces(_writes("x" * (OUTPUT_LIMIT * 3) + "THE END\n"))
    call_command("run_job", "check_bounces")
    assert _only_run().output.endswith(f"THE END\n{BOUNCES_OFF}\n")


def test_a_long_output_is_cut_to_the_limit(
    fake_bounces: Callable[[Callable[[], None]], None],
) -> None:
    """The record holds exactly the limit's worth of characters."""
    fake_bounces(_writes("x" * (OUTPUT_LIMIT * 3)))
    call_command("run_job", "check_bounces")
    assert len(_only_run().output) == OUTPUT_LIMIT


def test_a_long_output_says_it_was_cut(fake_bounces: Callable[[Callable[[], None]], None]) -> None:
    """``output_truncated`` is set when the output ran past the limit."""
    fake_bounces(_writes("x" * (OUTPUT_LIMIT + 1)))
    call_command("run_job", "check_bounces")
    assert _only_run().output_truncated is True


def test_a_short_output_is_not_marked_cut() -> None:
    """``output_truncated`` stays false for a run inside the limit."""
    call_command("run_job", "check_bounces")
    assert _only_run().output_truncated is False


@pytest.mark.parametrize(
    ("writes", "expected"),
    [
        (["abc", "def"], "abcdef"),
        (["abcdef", "gh"], "cdefgh"),
        (["ab", "cd", "efgh", "ij", "kl", "mnop"], "klmnop"),
        (["abcdefghijklmnopq"], "lmnopq"),
    ],
    ids=["inside-the-limit", "one-write-past", "many-small-writes", "one-long-write"],
)
def test_the_capture_keeps_the_last_characters(writes: list[str], expected: str) -> None:
    """``OutputCapture`` keeps the last ``limit`` characters whatever the write sizes."""
    capture = OutputCapture(limit=6)
    for text in writes:
        capture.add(text)
    assert capture.text() == expected


# ------------------------------------------------------------------- failures
def test_a_command_error_is_raised_again() -> None:
    """The command's ``CommandError`` reaches ``manage.py``, which exits non-zero."""
    with pytest.raises(CommandError, match="--today must be YYYY-MM-DD, not 'bogus'"):
        call_command("run_job", "send_renewal_reminders", "--today", "bogus")


def test_a_command_error_is_recorded_as_failed() -> None:
    """A ``CommandError`` leaves a ``failed`` record."""
    with pytest.raises(CommandError):
        call_command("run_job", "send_renewal_reminders", "--today", "bogus")
    assert _only_run().outcome == JobRun.Outcome.FAILED


def test_a_command_error_keeps_its_exit_status() -> None:
    """The record keeps the error's ``returncode``, which ``manage.py`` exits with."""
    with pytest.raises(CommandError) as raised:
        call_command("run_job", "send_renewal_reminders", "--today", "bogus")
    assert _only_run().exit_status == raised.value.returncode


def test_a_command_error_keeps_its_message() -> None:
    """The error's text is the record's ``error``, with no traceback."""
    with pytest.raises(CommandError):
        call_command("run_job", "send_renewal_reminders", "--today", "bogus")
    run = _only_run()
    assert run.error == "--today must be YYYY-MM-DD, not 'bogus'"
    assert run.traceback == ""


def test_a_failure_keeps_the_output_written_before_it(
    fake_bounces: Callable[[Callable[[], None]], None],
) -> None:
    """What the command wrote before it failed is in the record."""

    def body() -> None:
        sys.stdout.write("reading the mailbox\n")
        raise RuntimeError("the mailbox went away")

    fake_bounces(body)
    with pytest.raises(RuntimeError):
        call_command("run_job", "check_bounces")
    assert "reading the mailbox" in _only_run().output


def test_an_unexpected_exception_is_raised_again(
    fake_bounces: Callable[[Callable[[], None]], None],
) -> None:
    """Any other exception propagates, so Python prints it and exits 1."""
    fake_bounces(_raises("the mailbox went away"))
    with pytest.raises(RuntimeError, match="the mailbox went away"):
        call_command("run_job", "check_bounces")


def test_an_unexpected_exception_is_recorded_with_status_one(
    fake_bounces: Callable[[Callable[[], None]], None],
) -> None:
    """The record reads ``failed`` with exit status 1."""
    fake_bounces(_raises("the mailbox went away"))
    with pytest.raises(RuntimeError):
        call_command("run_job", "check_bounces")
    run = _only_run()
    assert run.outcome == JobRun.Outcome.FAILED
    assert run.exit_status == 1


def test_an_unexpected_exception_keeps_its_type_and_message(
    fake_bounces: Callable[[Callable[[], None]], None],
) -> None:
    """``error`` names the exception's type and message."""
    fake_bounces(_raises("the mailbox went away"))
    with pytest.raises(RuntimeError):
        call_command("run_job", "check_bounces")
    assert _only_run().error == "RuntimeError: the mailbox went away"


def test_an_unexpected_exception_keeps_its_traceback(
    fake_bounces: Callable[[Callable[[], None]], None],
) -> None:
    """``traceback`` holds the traceback, down to the line that raised."""
    fake_bounces(_raises("the mailbox went away"))
    with pytest.raises(RuntimeError):
        call_command("run_job", "check_bounces")
    trace = _only_run().traceback
    assert trace.startswith("Traceback (most recent call last):")
    assert trace.rstrip().endswith("RuntimeError: the mailbox went away")


def test_a_record_that_cannot_be_saved_does_not_hide_the_error(
    fake_bounces: Callable[[Callable[[], None]], None], monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the finished record cannot be written, the command's own error still rises."""

    def refuse(self: JobRun, *args: object, **kwargs: object) -> None:
        raise DatabaseError("the database went away")

    fake_bounces(_raises("the mailbox went away"))
    monkeypatch.setattr(JobRun, "save", refuse)
    with pytest.raises(RuntimeError, match="the mailbox went away"):
        call_command("run_job", "check_bounces")


# -------------------------------------------------------------------- pruning
def test_a_run_prunes_the_records_older_than_the_retention() -> None:
    """Starting a run deletes every record started more than the retention ago."""
    old = JobRun.objects.create(
        job="bounces", started_at=timezone.now() - RETENTION - timedelta(minutes=1)
    )
    call_command("run_job", "check_bounces")
    assert not JobRun.objects.filter(pk=old.pk).exists()


def test_a_run_keeps_the_records_inside_the_retention() -> None:
    """A record younger than the retention survives the prune."""
    recent = JobRun.objects.create(
        job="bounces", started_at=timezone.now() - RETENTION + timedelta(hours=1)
    )
    call_command("run_job", "check_bounces")
    assert JobRun.objects.filter(pk=recent.pk).exists()


def test_the_retention_is_ninety_days() -> None:
    """Records are kept for 90 days."""
    assert timedelta(days=90) == RETENTION


def test_the_output_limit_is_64_kib() -> None:
    """A record keeps the last 65,536 characters of its output."""
    assert recording.OUTPUT_LIMIT == 64 * 1024


# ----------------------------------------------------------------- the backup
def _dump(backup_dir: Path, name: str, age: timedelta) -> Path:
    """A dump called ``name`` in ``backup_dir``, last modified ``age`` ago."""
    path = backup_dir / name
    path.write_bytes(b"")
    stamp = (timezone.now() - age).timestamp()
    os.utime(path, (stamp, stamp))
    return path


def test_the_backup_prune_deletes_the_old_generated_dumps(backup_dir: Path) -> None:
    """``prune_backups`` deletes a generated dump more than the days given old."""
    old = _dump(backup_dir, "caldart-20260101-033000.sql.gz", timedelta(days=31))
    assert prune_backups(30) == [old.name]


def test_the_backup_prune_keeps_the_recent_dumps(backup_dir: Path) -> None:
    """A generated dump younger than the days given stays."""
    recent = _dump(backup_dir, "caldart-20261001-033000.sql.gz", timedelta(days=29))
    prune_backups(30)
    assert recent.exists()


def test_the_backup_prune_keeps_a_named_dump(backup_dir: Path) -> None:
    """A dump given its own name is never pruned, however old."""
    named = _dump(backup_dir, "before-upgrade.sql.gz", timedelta(days=400))
    prune_backups(30)
    assert named.exists()


def test_db_backup_prunes_after_the_dump(
    backup_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``db_backup --prune-days`` names each dump it deleted."""
    old = _dump(backup_dir, "caldart-20260101-033000.sql.gz", timedelta(days=31))
    monkeypatch.setattr(
        "apps.sysadmin.management.commands.db_backup.create_backup",
        lambda name: _fresh_backup(backup_dir),
    )
    call_command("db_backup", "--prune-days", "30")
    assert f"Deleted {old.name}, more than 30 days old" in capsys.readouterr().out


def test_db_backup_refuses_negative_prune_days(backup_dir: Path) -> None:
    """A negative ``--prune-days`` is an error before any dump is taken."""
    with pytest.raises(CommandError, match="--prune-days must be zero or more, not -1"):
        call_command("db_backup", "--prune-days", "-1")


def test_the_backup_job_records_its_prune(
    backup_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The backup's prune is part of its recorded run, so the log shows it."""
    old = _dump(backup_dir, "caldart-20260101-033000.sql.gz", timedelta(days=31))
    monkeypatch.setattr(
        "apps.sysadmin.management.commands.db_backup.create_backup",
        lambda name: _fresh_backup(backup_dir),
    )
    call_command("run_job", "db_backup", "--prune-days", "30")
    assert f"Deleted {old.name}" in _only_run().output


def _fresh_backup(backup_dir: Path) -> BackupFile:
    """A fresh dump in ``backup_dir``, standing in for ``create_backup``."""
    path = _dump(backup_dir, "caldart-20261015-033000.sql.gz", timedelta(0))
    return BackupFile(name=path.name, path=path, size_bytes=0, created_at=timezone.now())
