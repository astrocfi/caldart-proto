"""Run a scheduled job's command and keep a record of the run.

``manage.py run_job`` calls :func:`run_recorded`, which writes a
:class:`~apps.sysadmin.models.JobRun` row, runs the command with ``call_command``, and
fills the row in when it ends.  Everything the command writes, to its own
``self.stdout`` and ``self.stderr`` or to ``sys.stdout`` and ``sys.stderr``, still
reaches the real streams, so the journal keeps all of it, and so does every line a
console logging handler prints; the row keeps a copy of all of it, interleaved in the
order it was written and cut to its last :data:`OUTPUT_LIMIT` characters.  The
command's exception, if any, is raised again, so the process exits with the status the
command alone would have.

A **Run now** that runs a job inside the web request records it through
:func:`recorded_request_run` instead, under the administrator who pressed it.
"""

from __future__ import annotations

import io
import logging
import os
import shlex
import signal
import sys
import threading
import traceback
from collections.abc import Iterator, Sequence
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import FrameType
from typing import TextIO

from django.core.management import call_command, get_commands, load_command_class
from django.core.management.base import CommandError
from django.db import DatabaseError, connection
from django.utils import timezone

from apps.accounts.models import User
from apps.sysadmin.jobs import JOBS_BY_KEY, Job
from apps.sysadmin.models import JobRun

log = logging.getLogger(__name__)

#: How much of a run's output its record keeps, in characters: the last this many.
OUTPUT_LIMIT = 64 * 1024

#: How long a run's record is kept.  Older records are deleted whenever a run starts.
RETENTION = timedelta(days=90)

#: The longest ``JobRun.arguments`` holds; a longer command line is cut.
ARGUMENTS_LIMIT = 500

#: The exit status a shell reports for a process stopped by Ctrl-C.
INTERRUPTED_STATUS = 130

#: The exit status a shell reports for a process stopped by ``SIGTERM``.
TERMINATED_STATUS = 128 + signal.SIGTERM

#: The exit status ``manage.py`` gives a command line its parser refuses.
USAGE_STATUS = 2

#: The error a run stopped by ``SIGTERM`` is recorded with.
STOPPED_BY_THE_SERVER = "Stopped by the server before it finished."


@dataclass
class RunFlags:
    """What the command running now has said about its own run.

    ``skip`` asks that the run not be recorded, and ``idle`` says it didn't find
    anything to do, so only the newest such run of the job is kept.
    """

    skip: bool = False
    idle: bool = False


#: The flags of the run under way in this context, or ``None`` outside one.
_CURRENT: ContextVar[RunFlags | None] = ContextVar("job_run_flags", default=None)


def skip_record() -> None:
    """Ask that the run under way not be recorded; outside one, the call is ignored.

    A command calls it when it found another run of its job already under way and so
    didn't do anything itself, which the other run's record covers.
    """
    flags = _CURRENT.get()
    if flags is not None:
        flags.skip = True


def mark_idle() -> None:
    """Say the run under way didn't find anything to do; outside one, it is ignored.

    When such a run succeeds, the previous idle record of the same job is deleted, so a
    job that runs every minute keeps one record of its quiet runs and every record of
    the runs that did something.
    """
    flags = _CURRENT.get()
    if flags is not None:
        flags.idle = True


class OutputCapture:
    """The tail of everything written to it, at most ``limit`` characters.

    ``truncated`` turns true once more than ``limit`` characters have been written.
    Memory stays near twice the limit however long the run.
    """

    def __init__(self, limit: int = OUTPUT_LIMIT) -> None:
        """Start empty, keeping at most ``limit`` characters."""
        self._limit = limit
        self._chunks: list[str] = []
        self._held = 0
        self._written = 0

    def add(self, text: str) -> None:
        """Append ``text``, dropping the oldest characters once well past the limit."""
        self._chunks.append(text)
        self._held += len(text)
        self._written += len(text)
        if self._held > 2 * self._limit:
            kept = "".join(self._chunks)[-self._limit :]
            self._chunks = [kept]
            self._held = len(kept)

    @property
    def truncated(self) -> bool:
        """Whether more was written than the capture keeps."""
        return self._written > self._limit

    def text(self) -> str:
        """The last ``limit`` characters written, in the order they were written."""
        return "".join(self._chunks)[-self._limit :]


class TeeStream(io.TextIOBase):
    """A text stream that writes to ``real`` and copies every write into ``capture``.

    It reports itself as a stream other than a terminal, so Django's commands write
    plain text into the record (and, while it is in place, onto the terminal).
    """

    def __init__(self, real: TextIO, capture: OutputCapture) -> None:
        """Write through to ``real`` and copy into ``capture``."""
        super().__init__()
        self._real = real
        self._capture = capture

    def writable(self) -> bool:
        """Return ``True``: the stream takes writes."""
        return True

    def write(self, text: str) -> int:
        """Write ``text`` to the real stream and to the capture; return its length."""
        self._real.write(text)
        self._capture.add(text)
        return len(text)

    def flush(self) -> None:
        """Flush the real stream."""
        self._real.flush()

    def isatty(self) -> bool:
        """Return ``False``, so the command writes plain text."""
        return False


class _CaptureHandler(logging.Handler):
    """Copies each record a console handler prints, on one thread, into a capture."""

    def __init__(self, capture: OutputCapture, console: logging.Handler, thread: int) -> None:
        """Format and filter as ``console`` does, for records ``thread`` logs."""
        super().__init__(level=console.level)
        self.setFormatter(console.formatter)
        self.filters = list(console.filters)
        self._capture = capture
        self._thread = thread

    def emit(self, record: logging.LogRecord) -> None:
        """Add the formatted record and a newline, when the run's own thread logged it."""
        if record.thread == self._thread:
            self._capture.add(f"{self.format(record)}\n")


def _is_console(handler: logging.Handler) -> bool:
    """Whether ``handler`` prints to a stream, as the journal's console handler does."""
    return isinstance(handler, logging.StreamHandler) and not isinstance(
        handler, logging.FileHandler
    )


@contextmanager
def _logging_into(capture: OutputCapture) -> Iterator[None]:
    """Copy every line a console logging handler prints into ``capture`` while inside.

    Beside each console handler, on the same logger, sits a handler that formats and
    filters as it does and writes into the capture, so the record shows the lines the
    journal shows, in order with the rest of the output.  Only the lines the current
    thread logs are copied, so a web worker's other requests stay out of the record.
    The console handlers are left as they are, and the copies are removed on the way
    out.
    """
    thread = threading.get_ident()
    loggers = [logging.getLogger()]
    loggers += [
        logger
        for logger in logging.Logger.manager.loggerDict.values()
        if isinstance(logger, logging.Logger)
    ]
    added: list[tuple[logging.Logger, _CaptureHandler]] = []
    for logger in loggers:
        for console in [handler for handler in logger.handlers if _is_console(handler)]:
            mirror = _CaptureHandler(capture, console, thread)
            logger.addHandler(mirror)
            added.append((logger, mirror))
    try:
        yield
    finally:
        for logger, mirror in added:
            logger.removeHandler(mirror)


class _TerminatedError(BaseException):
    """``SIGTERM`` arrived while the command ran: systemd is stopping the unit."""


def _raise_terminated(signum: int, frame: FrameType | None) -> None:
    """The ``SIGTERM`` handler while a command runs: stop it where it stands."""
    raise _TerminatedError


@contextmanager
def _terminate_as_error() -> Iterator[None]:
    """Turn ``SIGTERM`` into :class:`_TerminatedError` while inside, on the main thread.

    The previous handler is put back on the way out.  Off the main thread, where a
    handler cannot be installed, nothing changes.
    """
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    previous = signal.signal(signal.SIGTERM, _raise_terminated)
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, previous)


def _die_of_sigterm() -> None:
    """End the process as ``SIGTERM`` would have, so its exit status stays 143.

    The default handler goes back in and the signal is sent again; should the process
    somehow survive it, ``SystemExit`` carries the same status.
    """
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    os.kill(os.getpid(), signal.SIGTERM)
    raise SystemExit(TERMINATED_STATUS)


def _prune(now_moment: datetime) -> None:
    """Delete the run records older than :data:`RETENTION`."""
    JobRun.objects.filter(started_at__lt=now_moment - RETENTION).delete()


def _clean(text: str) -> str:
    """``text`` without NUL characters, which a Postgres text column refuses."""
    return text.replace("\x00", "")


def start_run(job: Job, arguments: Sequence[str], started_by: User | None) -> JobRun:
    """Write the unfinished record of a run of ``job`` and prune the old ones."""
    started_at = timezone.now()
    _prune(started_at)
    line = _clean(shlex.join(arguments))
    return JobRun.objects.create(
        job=job.key,
        arguments=line[:ARGUMENTS_LIMIT],
        started_at=started_at,
        started_by=started_by,
    )


def _finish(
    run: JobRun,
    capture: OutputCapture,
    flags: RunFlags,
    *,
    exit_status: int,
    error: str = "",
    trace: str = "",
) -> None:
    """Fill in how ``run`` ended; a database that refuses the write is logged, not raised.

    A run whose command asked for it with :func:`skip_record` is deleted instead.  An
    idle run that succeeded replaces the job's previous idle record.  The command's own
    exception matters more than its record, so a failure to save never hides it.  A
    long run may have outlived its database connection, so a broken or expired one is
    replaced first.
    """
    run.finished_at = timezone.now()
    run.exit_status = exit_status
    run.outcome = JobRun.Outcome.SUCCEEDED if exit_status == 0 else JobRun.Outcome.FAILED
    run.output = _clean(capture.text())
    run.output_truncated = capture.truncated
    run.error = _clean(error)
    run.traceback = _clean(trace)
    run.idle = flags.idle and exit_status == 0
    try:
        if not connection.in_atomic_block:
            connection.close_if_unusable_or_obsolete()
        if flags.skip:
            run.delete()
            return
        run.save()
        if run.idle:
            JobRun.objects.filter(job=run.job, idle=True).exclude(pk=run.pk).delete()
    except DatabaseError:
        log.warning("the record of job run %s could not be saved", run.pk, exc_info=True)


def _exit_status(exc: SystemExit) -> int:
    """The status a process exits with for ``exc``: its code, 0 for ``None``, else 1."""
    if exc.code is None:
        return 0
    if isinstance(exc.code, int):
        return exc.code
    return 1


def _check_arguments(command: str, arguments: Sequence[str]) -> None:
    """Parse ``arguments`` as ``command``'s parser would, without running it.

    Raises ``CommandError`` with the parser's message and ``returncode`` 2, the status
    ``manage.py`` exits with when it refuses a command line itself.
    """
    parser = load_command_class(get_commands()[command], command).create_parser(
        "manage.py", command
    )
    try:
        parser.parse_args(list(arguments))
    except CommandError as exc:
        raise CommandError(str(exc), returncode=USAGE_STATUS) from exc


def run_recorded(job: Job, arguments: Sequence[str], *, started_by: User | None = None) -> None:
    """Run ``job``'s command with ``arguments`` and record the run.

    The record is written before the command starts, with ``started_by`` (``None``
    for the server), and filled in when it ends:

    - a clean return is ``succeeded`` with exit status 0;
    - options the command's parser refuses are ``failed`` with exit status 2, the
      parser's message as ``error``, raised again as a ``CommandError`` with that
      status;
    - a ``CommandError`` is ``failed`` with the error's ``returncode`` and its text as
      ``error``, and is raised again, so ``manage.py`` prints it and exits with that
      status as it would for the command alone;
    - a ``SystemExit`` keeps its code, ``succeeded`` only when that is 0, with a text
      code as ``error``, and is raised again;
    - ``SIGTERM``, as when systemd stops the unit at its timeout, is ``failed`` with
      exit status 143 and :data:`STOPPED_BY_THE_SERVER`, and the process then ends of
      the same signal;
    - any other exception is ``failed`` with exit status 1 (130 for a
      ``KeyboardInterrupt``), ``"<type>: <message>"`` as ``error`` and its traceback,
      and is raised again.

    A command may ask that its run not be recorded (:func:`skip_record`) or say it
    didn't find anything to do (:func:`mark_idle`).  When the record cannot be written
    at all, such as with the database unreachable, the command runs anyway, unrecorded,
    and the reason is logged.
    """
    try:
        run = start_run(job, arguments, started_by)
    except DatabaseError:
        log.warning(
            "job %s runs unrecorded: its record could not be written", job.key, exc_info=True
        )
        call_command(job.command, *arguments)
        return

    capture = OutputCapture()
    flags = RunFlags()
    token = _CURRENT.set(flags)
    tee_out, tee_err = TeeStream(sys.stdout, capture), TeeStream(sys.stderr, capture)
    try:
        with (
            redirect_stdout(tee_out),
            redirect_stderr(tee_err),
            _logging_into(capture),
            _terminate_as_error(),
        ):
            _check_arguments(job.command, arguments)
            call_command(job.command, *arguments, stdout=tee_out, stderr=tee_err)
    except CommandError as exc:
        _finish(run, capture, flags, exit_status=exc.returncode, error=str(exc))
        raise
    except SystemExit as exc:
        message = exc.code if isinstance(exc.code, str) else ""
        _finish(run, capture, flags, exit_status=_exit_status(exc), error=message)
        raise
    except _TerminatedError:
        _finish(run, capture, flags, exit_status=TERMINATED_STATUS, error=STOPPED_BY_THE_SERVER)
        _die_of_sigterm()
    except BaseException as exc:
        status = INTERRUPTED_STATUS if isinstance(exc, KeyboardInterrupt) else 1
        _finish(
            run,
            capture,
            flags,
            exit_status=status,
            error=f"{type(exc).__name__}: {exc}",
            trace=traceback.format_exc(),
        )
        raise
    else:
        _finish(run, capture, flags, exit_status=0)
    finally:
        _CURRENT.reset(token)


class RequestRun:
    """A **Run now** under way inside the web request, from :func:`recorded_request_run`.

    The view adds what the run printed with :meth:`write`, and says it failed with
    :meth:`fail`.
    """

    def __init__(self, capture: OutputCapture) -> None:
        """Start with an empty ``problem``, writing into ``capture``."""
        self._capture = capture
        self.problem = ""

    def write(self, lines: Sequence[str]) -> None:
        """Add ``lines`` to the output, one to a line, as the command would print them."""
        for line in lines:
            self._capture.add(f"{line}\n")

    def fail(self, problem: str) -> None:
        """Record the run as failed with ``problem``; a blank ``problem`` is a success."""
        self.problem = problem


@contextmanager
def recorded_request_run(
    job_key: str, *, started_by: User, arguments: Sequence[str] = ()
) -> Iterator[RequestRun]:
    """Record a real **Run now** of ``job_key`` that runs inside the request.

    The record is written on the way in under ``started_by``, and filled in on the way
    out: ``failed`` with exit status 1 and the problem given to :meth:`RequestRun.fail`,
    ``failed`` with the exception and its traceback when one escapes (it is raised
    again), and ``succeeded`` with exit status 0 otherwise.  The output is every line
    a console logging handler printed on the request's thread, then the lines given to
    :meth:`RequestRun.write`.  :func:`skip_record` and :func:`mark_idle` work as in a
    command.  When the record cannot be written the run goes ahead unrecorded.
    """
    job = JOBS_BY_KEY[job_key]
    capture = OutputCapture()
    request_run = RequestRun(capture)
    try:
        run = start_run(job, arguments, started_by)
    except DatabaseError:
        log.warning("job %s runs unrecorded: its record could not be written", job.key)
        yield request_run
        return

    flags = RunFlags()
    token = _CURRENT.set(flags)
    try:
        with _logging_into(capture):
            yield request_run
    except BaseException as exc:
        _finish(
            run,
            capture,
            flags,
            exit_status=1,
            error=f"{type(exc).__name__}: {exc}",
            trace=traceback.format_exc(),
        )
        raise
    else:
        if request_run.problem:
            _finish(run, capture, flags, exit_status=1, error=request_run.problem)
        else:
            _finish(run, capture, flags, exit_status=0)
    finally:
        _CURRENT.reset(token)
