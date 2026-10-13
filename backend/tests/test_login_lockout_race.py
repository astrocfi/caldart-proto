"""The sign-in lockout's counts under concurrent failures.

Each failure updates its count under a row lock, so failures recorded at the same
instant from several requests are all counted.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from django.db import connection
from pytest_django import Settings

from apps.accounts import lockout
from apps.accounts.models import SignInFailureCount

pytestmark = pytest.mark.django_db(transaction=True)

#: Failures recorded at once, more than the limit so a lost one would show.
FAILURES = 24
ADDRESS = "racer@example.test"


def _fail_once(_: int) -> None:
    """Record one failure from a thread of its own, closing its connection after."""
    try:
        lockout.record_failure(ADDRESS)
    finally:
        connection.close()


def test_concurrent_failures_are_all_counted(settings: Settings) -> None:
    """Every failure from every thread lands in the count."""
    settings.LOGIN_LOCKOUT_ATTEMPTS = 1000
    settings.LOGIN_LOCKOUT_SECONDS = 900
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(_fail_once, range(FAILURES)))
    assert [row.count for row in SignInFailureCount.objects.all()] == [FAILURES]
