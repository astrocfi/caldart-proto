"""Django's own system checks, run against the settings the suite uses.

``make check`` runs ``manage.py check --fail-level WARNING``, so a check that starts
reporting is a deployment that refuses to start.  Running the same checks here puts
that failure in the test suite, where the message says which setting is at fault.
"""

from __future__ import annotations

from django.conf import settings
from django.core.checks import run_checks


def test_the_system_checks_report_nothing() -> None:
    """No check reports an issue beyond the two ``SILENCED_SYSTEM_CHECKS`` ids.

    Those two only report that ``frontend/dist`` has not been built, which the
    backend test job never builds.
    """
    reported = [
        message for message in run_checks() if message.id not in settings.SILENCED_SYSTEM_CHECKS
    ]

    assert reported == []
