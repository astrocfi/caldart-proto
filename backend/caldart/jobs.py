"""The command line that runs a scheduled job's command in a process of its own.

A **Run now** that cannot finish inside the request, such as a live renewal scan or an
FAA registry import, starts the job's command in a child process.  It goes through
``manage.py run_job`` (``apps.sysadmin``), so the run is recorded as the timer's runs
are, naming the system administrator who pressed the button.  This module names no app,
so an app on any layer may build the command line.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

from django.conf import settings


def run_job_argv(command: str, arguments: Sequence[str], *, started_by_id: int | None) -> list[str]:
    """The argv that runs ``command`` with ``arguments`` through ``manage.py run_job``.

    It runs under the server's own Python and the project's ``manage.py``, with
    ``--started-by <id>`` before the command when ``started_by_id`` is given, so the
    record names that user; without it the run reads as the server's.
    """
    manage = Path(settings.BASE_DIR) / "manage.py"
    who = [] if started_by_id is None else ["--started-by", str(started_by_id)]
    return [sys.executable, str(manage), "run_job", *who, command, *arguments]
