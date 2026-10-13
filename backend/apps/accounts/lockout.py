"""The per-account sign-in lockout.

The ``auth_login`` throttle counts attempts by client address, which a guesser spread
over many addresses never exhausts.  This counts failed attempts by the account signed
in *to*: after ``LOGIN_LOCKOUT_ATTEMPTS`` failures within ``LOGIN_LOCKOUT_SECONDS``,
every further attempt for it is refused, whoever makes it and from wherever, until the
window that began with the first failure has passed.  A wrong password and a wrong
second-factor code both count.  Wrong codes are also counted over a longer window,
``LOGIN_LOCKOUT_CODE_ATTEMPTS`` within ``LOGIN_LOCKOUT_CODE_SECONDS``, since only
somebody who already holds the password reaches them.

An address is counted under the account it resolves to, found as sign-in finds it
(``email__iexact``), so every spelling the database matches to the account shares one
count.  An address no account holds is counted under the database's own ``UPPER()`` of
it, the comparison ``email__iexact`` makes, so a spelling cannot be counted apart from
the account it would sign in to; the answers never tell a caller which addresses are
registered.

The counts are rows of ``SignInFailureCount``, keyed by a SHA-256 digest, so no
address is stored.  They live in the database rather than the cache, which may forget
any entry under pressure, and each is read and written under a row lock, so two
failures at the same instant are both counted.  A row past its window reads as empty;
rows past their window are deleted as failures are counted.
"""

from __future__ import annotations

import hashlib
import math
from datetime import datetime, timedelta
from typing import TypedDict

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

from apps.accounts.mfa import mail_notice
from apps.accounts.models import SignInFailureCount, User
from caldart import audit

#: What a locked-out address is told, ahead of DRF's "Expected available in N seconds."
LOCKED_OUT = "Too many failed sign-in attempts for this email address. Try again later."

#: The counts a subject has, each the prefix of its key.
SHORT_COUNT = "failures"
CODE_COUNT = "code-failures"
NOTICE_MARK = "notice"

#: How long one lockout notice keeps another from being mailed to the same account.
NOTICE_SECONDS = 24 * 60 * 60


class _Limit(TypedDict):
    """One count's name and its settings."""

    name: str
    attempts: int
    seconds: int


def account_for(email: str) -> User | None:
    """The account ``email`` resolves to, as sign-in resolves it, or ``None``."""
    return User.objects.filter(email__iexact=email.strip()).first()


def _upper(email: str) -> str:
    """``email`` stripped and upper-cased by the database, as ``email__iexact`` does."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT UPPER(%s)", [email.strip()])
        row = cursor.fetchone()
    return str(row[0]) if row is not None else email.strip().upper()


def _subject(email: str) -> tuple[str, User | None]:
    """What ``email``'s failures are counted under, and the account it names."""
    account = account_for(email)
    if account is not None:
        return f"account:{account.pk}", account
    return f"address:{_upper(email)}", None


def _key(name: str, subject: str) -> str:
    """The digest a count ``name`` of ``subject`` is stored under."""
    return hashlib.sha256(f"{name}:{subject}".encode()).hexdigest()


def _limits(*, code: bool) -> list[_Limit]:
    """The counts a failure goes into: the short one always, the code one for a code."""
    limits: list[_Limit] = [
        {
            "name": SHORT_COUNT,
            "attempts": settings.LOGIN_LOCKOUT_ATTEMPTS,
            "seconds": settings.LOGIN_LOCKOUT_SECONDS,
        }
    ]
    if code:
        limits.append(
            {
                "name": CODE_COUNT,
                "attempts": settings.LOGIN_LOCKOUT_CODE_ATTEMPTS,
                "seconds": settings.LOGIN_LOCKOUT_CODE_SECONDS,
            }
        )
    return [limit for limit in limits if limit["attempts"] > 0 and limit["seconds"] > 0]


def lockout_wait(email: str) -> int | None:
    """Whole seconds until ``email`` may be tried again, or ``None`` if it may be now."""
    subject, _ = _subject(email)
    now = timezone.now()
    waits = []
    for limit in _limits(code=True):
        row = SignInFailureCount.objects.filter(
            key=_key(limit["name"], subject), until__gt=now
        ).first()
        if row is not None and row.count >= limit["attempts"]:
            waits.append(max(1, math.ceil((row.until - now).total_seconds())))
    return max(waits) if waits else None


def _count_one(key: str, seconds: int, now: datetime) -> int:
    """Add one to the count under ``key`` and return it, opening a window when needed.

    The row is locked for the update, so concurrent failures are all counted.
    """
    with transaction.atomic():
        row, _ = SignInFailureCount.objects.select_for_update().get_or_create(
            key=key, defaults={"count": 0, "until": now + timedelta(seconds=seconds)}
        )
        if row.until <= now:
            row.count = 0
            row.until = now + timedelta(seconds=seconds)
        row.count += 1
        row.save(update_fields=["count", "until"])
        return row.count


def record_failure(email: str, *, code: bool = False) -> None:
    """Count one failed attempt to sign in to ``email``; ``code`` for a wrong code.

    The first failure opens a window; the failure that reaches the limit within it
    locks the address out until it closes, and is recorded at WARNING as
    ``account.lockout`` under the anonymous actor, with the account's id as the target
    when an account holds the address and ``-`` otherwise.  The account is mailed
    then, at most once a day.  Rows whose windows ended a day ago are deleted.
    """
    subject, account = _subject(email)
    now = timezone.now()
    for limit in _limits(code=code):
        count = _count_one(_key(limit["name"], subject), limit["seconds"], now)
        if count == limit["attempts"]:
            _locked_out(subject, account, count, now)
    SignInFailureCount.objects.filter(until__lt=now - timedelta(days=1)).delete()


def _locked_out(subject: str, account: User | None, attempts: int, now: datetime) -> None:
    """Record the lockout, and tell the account's owner unless told within the day."""
    audit.refuse(
        audit.ACCOUNT_LOCKOUT,
        actor=audit.ANONYMOUS_ACTOR,
        target=account,
        reason=audit.REASON_TOO_MANY_FAILURES,
        attempts=attempts,
    )
    if account is None:
        return
    if _count_one(_key(NOTICE_MARK, subject), NOTICE_SECONDS, now) == 1:
        mail_notice(account, "sign_in_locked", "sign-in paused after failed attempts")


def clear_failures(email: str) -> None:
    """Forget the short count of failed attempts against ``email``.

    The longer count of wrong codes is kept: it is what stops somebody who holds the
    password from trying codes all day, a few at a time between sign-ins of the owner's.
    """
    subject, _ = _subject(email)
    SignInFailureCount.objects.filter(key=_key(SHORT_COUNT, subject)).delete()


def clear_all_failures(email: str) -> None:
    """Forget every count against ``email``, the longer count of wrong codes included."""
    subject, _ = _subject(email)
    keys = [_key(name, subject) for name in (SHORT_COUNT, CODE_COUNT)]
    SignInFailureCount.objects.filter(key__in=keys).delete()
