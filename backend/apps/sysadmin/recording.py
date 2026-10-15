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
"""

from __future__ import annotations

import io
import logging
import shlex
import sys
import traceback
from collections.abc import Iterator, Sequence
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from datetime import datetime, timedelta
from typing import TextIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError
from django.utils import timezone

from apps.accounts.models import User
from apps.sysadmin.jobs import Job
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

    It reports itself as no terminal, so Django's commands write no color codes into
    the record (or, while it is in place, onto the terminal).
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
        """Return ``False``, so no command colors its output."""
        return False


class _CaptureHandler(logging.Handler):
    """Copies each record a console handler prints into the run's capture."""

    def __init__(self, capture: OutputCapture, console: logging.Handler) -> None:
        """Format and filter as ``console`` does, writing into ``capture``."""
        super().__init__(level=console.level)
        self.setFormatter(console.formatter)
        self.filters = list(console.filters)
        self._capture = capture

    def emit(self, record: logging.LogRecord) -> None:
        """Add the formatted record and a newline to the capture."""
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
    journal shows, in order with the rest of the output.  The console handlers are not
    touched, and the copies are removed on the way out.
    """
    loggers = [logging.getLogger()]
    loggers += [
        logger
        for logger in logging.Logger.manager.loggerDict.values()
        if isinstance(logger, logging.Logger)
    ]
    added: list[tuple[logging.Logger, _CaptureHandler]] = []
    for logger in loggers:
        for console in [handler for handler in logger.handlers if _is_console(handler)]:
            mirror = _CaptureHandler(capture, console)
            logger.addHandler(mirror)
            added.append((logger, mirror))
    try:
        yield
    finally:
        for logger, mirror in added:
            logger.removeHandler(mirror)


def _prune(now_moment: datetime) -> None:
    """Delete the run records older than :data:`RETENTION`."""
    JobRun.objects.filter(started_at__lt=now_moment - RETENTION).delete()


def start_run(job: Job, arguments: Sequence[str], started_by: User | None) -> JobRun:
    """Write the unfinished record of a run of ``job`` and prune the old ones."""
    started_at = timezone.now()
    _prune(started_at)
    line = shlex.join(arguments)
    return JobRun.objects.create(
        job=job.key,
        arguments=line[:ARGUMENTS_LIMIT],
        started_at=started_at,
        started_by=started_by,
    )


def _finish(
    run: JobRun,
    capture: OutputCapture,
    *,
    exit_status: int,
    error: str = "",
    trace: str = "",
) -> None:
    """Fill in how ``run`` ended; a database that refuses the write is logged, not raised.

    The command's own exception matters more than its record, so a failure to save
    never hides it.
    """
    run.finished_at = timezone.now()
    run.exit_status = exit_status
    run.outcome = JobRun.Outcome.SUCCEEDED if exit_status == 0 else JobRun.Outcome.FAILED
    run.output = capture.text()
    run.output_truncated = capture.truncated
    run.error = error
    run.traceback = trace
    try:
        run.save()
    except DatabaseError:
        log.warning("the record of job run %s could not be saved", run.pk, exc_info=True)


def _exit_status(exc: SystemExit) -> int:
    """The status a process exits with for ``exc``: its code, 0 for none, 1 for text."""
    if exc.code is None:
        return 0
    if isinstance(exc.code, int):
        return exc.code
    return 1


def run_recorded(job: Job, arguments: Sequence[str], *, started_by: User | None = None) -> None:
    """Run ``job``'s command with ``arguments`` and record the run.

    The record is written before the command starts, with ``started_by`` (``None``
    for the server), and filled in when it ends:

    - a clean return is ``succeeded`` with exit status 0;
    - a ``CommandError`` is ``failed`` with the error's ``returncode`` and its text as
      ``error``, and is raised again, so ``manage.py`` prints it and exits with that
      status as it would for the command alone;
    - a ``SystemExit`` keeps its code, ``succeeded`` only when that is 0, with a text
      code as ``error``, and is raised again;
    - any other exception is ``failed`` with exit status 1 (130 for a
      ``KeyboardInterrupt``), ``"<type>: <message>"`` as ``error`` and its traceback,
      and is raised again.

    When the record cannot be written at all, such as with the database unreachable,
    the command runs anyway, unrecorded, and the reason is logged.
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
    tee_out, tee_err = TeeStream(sys.stdout, capture), TeeStream(sys.stderr, capture)
    try:
        with (
            redirect_stdout(tee_out),
            redirect_stderr(tee_err),
            _logging_into(capture),
        ):
            call_command(job.command, *arguments, stdout=tee_out, stderr=tee_err)
    except CommandError as exc:
        _finish(run, capture, exit_status=exc.returncode, error=str(exc))
        raise
    except SystemExit as exc:
        message = exc.code if isinstance(exc.code, str) else ""
        _finish(run, capture, exit_status=_exit_status(exc), error=message)
        raise
    except BaseException as exc:
        status = INTERRUPTED_STATUS if isinstance(exc, KeyboardInterrupt) else 1
        _finish(
            run,
            capture,
            exit_status=status,
            error=f"{type(exc).__name__}: {exc}",
            trace=traceback.format_exc(),
        )
        raise
    _finish(run, capture, exit_status=0)
