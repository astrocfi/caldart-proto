"""A live renewal scan started from the portal, run outside the request that asked.

A live scan charges every renewal that is due, and each charge waits on a provider
that may take seconds to answer, so a scan run inside a web request can outlast the
proxy and worker timeouts and be cut off mid-charge.  ``POST /system/renewals/run``
therefore writes a :class:`~apps.payments.models.RenewalScan` row, starts
``manage.py run_auto_renewals --scan-id <row>`` in its own process, and answers at
once; the command fills the row in when the scan ends, and the Scheduled tasks page
reads it back with ``GET /system/renewals/runs/{id}``.  A dry run charges nobody and
calls no provider, so it still runs inside the request.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.payments.models import RenewalScan
from apps.payments.renewals.charge import stale_after
from apps.payments.renewals.scan import RenewalRun

log = logging.getLogger(__name__)

#: The error a scan row is closed with when it ran longer than
#: ``RENEWAL_STALE_MINUTES`` without finishing: its process died or was killed.
DID_NOT_FINISH = "Did not finish."

#: The error a scan row is closed with when its process could not be started.
COULD_NOT_START = "Could not start."

#: What a second **Run now** is told while a live scan is still running.
ALREADY_RUNNING = "An automatic renewal run is already under way."

#: Sets the check for a running scan apart from every other advisory lock.
START_LOCK_KEY = 0x0C4A_26E6

#: The error a scan row is closed with when the scan itself raised.  The exception is
#: in the server's log; the page is told only that it happened.
STOPPED_WITH_AN_ERROR = "Stopped with an error; the server log has the details."


class ScanAlreadyRunningError(RuntimeError):
    """A live renewal scan started from the portal has not finished yet."""


def start_scan(actor: User) -> RenewalScan:
    """Start a live renewal scan in its own process on behalf of ``actor``.

    Writes the :class:`~apps.payments.models.RenewalScan` row (started now by
    ``actor``, not finished) and hands it to :func:`launch_scan`.  Raises
    :class:`ScanAlreadyRunningError` reading :data:`ALREADY_RUNNING` while another
    row is unfinished and younger than ``RENEWAL_STALE_MINUTES``; an unfinished row
    older than that is closed as :data:`DID_NOT_FINISH` and does not block.  Two
    presses at once are serialized by an advisory lock, so only one of them starts a
    scan.  Raises
    ``ImproperlyConfigured`` when ``RENEWAL_STALE_MINUTES`` is too small to run a
    scan at all.  When the process cannot be started (an ``OSError``) the row is
    closed at once as failed with :data:`COULD_NOT_START`, and the exception is
    raised again.
    """
    stale = stale_after()
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [START_LOCK_KEY])
        now = timezone.now()
        unfinished = RenewalScan.objects.filter(finished_at__isnull=True)
        if unfinished.filter(started_at__gte=now - stale).exists():
            raise ScanAlreadyRunningError(ALREADY_RUNNING)
        unfinished.update(ok=False, error=DID_NOT_FINISH, finished_at=now)
        scan = RenewalScan.objects.create(started_by=actor)
    try:
        launch_scan(scan)
    except OSError:
        close_scan(scan, error=COULD_NOT_START)
        log.error("renewal scan %s could not start: %s", scan.pk, COULD_NOT_START)
        raise
    return scan


def launch_scan(scan: RenewalScan) -> None:
    """Start ``manage.py run_auto_renewals --scan-id <scan>`` and return at once.

    The command runs in its own session under the server's Python, so it outlives
    the request, and writes to the server's own output.  The child is never waited
    on; the row it was given is the only trace of it, and the stale rule
    (:func:`close_if_stale`) is what notices a child that never finishes.  Raises
    ``OSError`` when the subprocess itself cannot be started.
    """
    manage = Path(settings.BASE_DIR) / "manage.py"
    subprocess.Popen(  # noqa: S603 - the server's own Python running the project's manage.py
        [sys.executable, str(manage), "run_auto_renewals", "--scan-id", str(scan.pk)],
        start_new_session=True,
    )


def finish_scan(scan: RenewalScan, run: RenewalRun) -> None:
    """Record that ``scan`` ran to its end, with the counts and actions of ``run``.

    Any error the row carried -- a *Did not finish.* written while the scan was
    still running -- is cleared, since the scan did finish.
    """
    scan.result = run.as_dict()
    scan.ok = True
    scan.error = ""
    scan.finished_at = timezone.now()
    scan.save(update_fields=["result", "ok", "error", "finished_at"])


def close_scan(scan: RenewalScan, *, error: str) -> None:
    """Record that ``scan`` ended without finishing, and why."""
    scan.ok = False
    scan.error = error
    scan.finished_at = timezone.now()
    scan.save(update_fields=["ok", "error", "finished_at"])


def close_if_stale(scan: RenewalScan) -> RenewalScan:
    """Close ``scan`` as :data:`DID_NOT_FINISH` when it has run too long, and return it.

    A scan still unfinished ``RENEWAL_STALE_MINUTES`` after it started has lost its
    process; any charge it claimed is settled by a later scan once its claim is as
    old.  A finished scan, and one still inside the limit, is returned unchanged.
    """
    if scan.finished_at is not None:
        return scan
    if timezone.now() - scan.started_at < stale_after():
        return scan
    close_scan(scan, error=DID_NOT_FINISH)
    return scan
