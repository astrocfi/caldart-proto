"""Two-factor sign-in: authenticator devices, backup codes, and the session's marks.

An account signs in with a second factor when a role it holds requires one
(:data:`apps.accounts.roles.MFA_REQUIRED_ROLES`, or the Django superuser flag) or when
its owner has turned two-factor sign-in on.  No role requires it of a seeded demo
account (``User.is_demo``) while ``settings.DEMO_ACCOUNTS_SKIP_TWO_FACTOR`` is on.
The second factor is a six-digit code from an authenticator app (RFC 6238: SHA-1,
30-second steps, one step of drift either way), or one of ten single-use backup codes
in its place.

Signing in is two steps.  A right password for an account that needs a second factor
does not start a session: it stores a *pending sign-in* in the anonymous session,
bound to the account and to its password, which the code step then completes
(:func:`begin_pending`, :func:`pending_sign_in`).  A session that has passed the
second factor carries a mark (:func:`mark_session`); ``MfaSessionMiddleware`` ends
any signed-in session of an account that needs a second factor and lacks the mark.

Neither a secret nor a code is ever logged or written to the audit log.
"""

from __future__ import annotations

import base64
import hmac
import secrets
import time
from dataclasses import dataclass
from enum import StrEnum

import pyotp
import segno
from django.conf import settings
from django.contrib.sessions.backends.base import SessionBase
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from apps.accounts.history import record_account_change
from apps.accounts.models import AccountChangeKind, RecoveryCode, TotpDevice, User
from apps.accounts.roles import MFA_REQUIRED_ROLES, SYSTEM_ADMIN
from apps.accounts.services import effective_roles, is_donor
from apps.accounts.status import end_sessions
from caldart import audit
from caldart.exceptions import DomainError, DomainPermissionError, DomainValidationError
from caldart.mail import contact_email, org_name, send_on_commit, send_templated

# -- the authenticator code -------------------------------------------------
#: Digits in an authenticator code.
TOTP_DIGITS = 6
#: Seconds in one time step.
TOTP_INTERVAL = 30
#: Steps either side of the present one whose code is still accepted, for a phone
#: whose clock has drifted or a code typed as it rolled over.
TOTP_DRIFT_STEPS = 1
#: Random bytes in a new device's shared secret: 160 bits, as RFC 4226 recommends.
SECRET_BYTES = 20

# -- the backup codes -------------------------------------------------------
#: Backup codes in one set.
RECOVERY_CODE_COUNT = 10
#: The characters a backup code is drawn from: lowercase letters and digits without
#: the ones a reader confuses (``0``/``o``, ``1``/``i``/``l``).
RECOVERY_CODE_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"
#: Characters in each of a backup code's two groups, shown joined by a hyphen.
RECOVERY_CODE_GROUP = 5
RECOVERY_CODE_GROUPS = 2
#: The ``salted_hmac`` purpose a backup code's hash is keyed with.
RECOVERY_HASH_PURPOSE = "caldart.accounts.recovery-code"

# -- the session ------------------------------------------------------------
#: The session key holding a sign-in that has passed the password and awaits a code.
PENDING_SESSION_KEY = "_caldart_mfa_pending"
#: The session key marking a signed-in session that has passed the second factor.
VERIFIED_SESSION_KEY = "_caldart_mfa_verified"
#: Seconds a pending sign-in waits for its code before the password is asked again.
PENDING_SECONDS = 300
#: Wrong codes a pending sign-in takes before it is thrown away.
PENDING_ATTEMPTS = 5
#: The session key holding the secret a browser is enrolling, until a code confirms it.
ENROLLMENT_SESSION_KEY = "_caldart_mfa_enrollment"
#: Seconds a secret waits in the session for the code that confirms it.
ENROLLMENT_SECONDS = 600

# -- what a person is told --------------------------------------------------
CODE_REFUSED = "That code is not right. Enter the current code from your app, or a backup code."
CODE_MISSING = "Enter the code from your authenticator app, or a backup code."
ALREADY_ON = "Two-factor sign-in is already on for this account."
NOT_STARTED = "Start setting up two-factor sign-in first."
NOT_ON = "Two-factor sign-in is not on for this account."
REQUIRED_REFUSED = (
    "Your role requires two-factor sign-in, so it cannot be turned off. "
    "If you have lost your phone, ask a user administrator to reset it."
)
SELF_RESET_REFUSED = "You cannot reset your own two-factor sign-in. Turn it off or on yourself."
RESET_REFUSED = "Only a system administrator can reset a system administrator's two-factor sign-in."
DONOR_RESET_REFUSED = "A donor has no portal account to reset."


class SignInStep(StrEnum):
    """What a pending sign-in still needs: a code, or a device enrolled first."""

    VERIFY = "verify"
    ENROLL = "enroll"


class CodeKind(StrEnum):
    """Which kind of code was accepted."""

    TOTP = "totp"
    RECOVERY = "recovery"


@dataclass(frozen=True)
class Enrollment:
    """What the person needs to add the account to an authenticator app.

    ``secret`` is the base32 shared secret for typing in by hand, ``otpauth_uri`` the
    ``otpauth://`` address the QR code carries, and ``qr_svg`` that QR code drawn as an
    SVG document.
    """

    secret: str
    otpauth_uri: str
    qr_svg: str


@dataclass(frozen=True)
class PendingSignIn:
    """A sign-in that has passed the password and awaits the second factor.

    ``reactivate`` is true for one ``POST /auth/reactivate`` started: the account is
    still deactivated, and is reactivated only once the second factor is passed.
    """

    user: User
    step: SignInStep
    reactivate: bool = False


# --------------------------------------------------------------------------
# Who needs a second factor
# --------------------------------------------------------------------------
def mfa_required(user: User) -> bool:
    """True when a role ``user`` holds requires two-factor sign-in.

    Effective roles are read (``accounts.services.effective_roles``), so a Django
    superuser counts as a system administrator and is required too.  A seeded demo
    account (``user.is_demo``) is never required while
    ``settings.DEMO_ACCOUNTS_SKIP_TWO_FACTOR`` is on, whatever roles it holds; it may
    still turn two-factor sign-in on, and off again, as any account a role does not
    require it of.
    """
    if user.is_demo and settings.DEMO_ACCOUNTS_SKIP_TWO_FACTOR:
        return False
    return bool(effective_roles(user) & set(MFA_REQUIRED_ROLES))


def confirmed_device(user: User) -> TotpDevice | None:
    """``user``'s confirmed authenticator device, or ``None`` without one."""
    return TotpDevice.objects.filter(user=user, confirmed_at__isnull=False).first()


def has_two_factor(user: User) -> bool:
    """True when ``user`` has a confirmed authenticator device."""
    return TotpDevice.objects.filter(user=user, confirmed_at__isnull=False).exists()


def needs_second_factor(user: User) -> bool:
    """True when signing in as ``user`` takes a code: :func:`mfa_required`, or a device.

    A confirmed device asks for a code whether or not a role requires one, so a demo
    account that turned two-factor sign-in on is asked for it like anybody else.
    """
    return mfa_required(user) or has_two_factor(user)


def recovery_codes_remaining(user: User) -> int:
    """How many of ``user``'s backup codes are still unused."""
    return RecoveryCode.objects.filter(user=user, used_at__isnull=True).count()


# --------------------------------------------------------------------------
# Enrollment
# --------------------------------------------------------------------------
def totp_generator(secret: str) -> pyotp.TOTP:
    """The RFC 6238 generator for ``secret``: SHA-1, six digits, 30-second steps."""
    return pyotp.TOTP(secret, digits=TOTP_DIGITS, interval=TOTP_INTERVAL)


def new_secret() -> str:
    """A fresh base32 secret of :data:`SECRET_BYTES` random bytes, without padding."""
    return base64.b32encode(secrets.token_bytes(SECRET_BYTES)).decode("ascii").rstrip("=")


def start_enrollment(session: SessionBase, user: User) -> Enrollment:
    """Draw a secret for ``user``, keep it in ``session``, and say what the app needs.

    Nothing is written to the database: the secret waits in the session that asked for
    it (:data:`ENROLLMENT_SESSION_KEY`) until :func:`confirm_enrollment` checks a code
    from it, so each browser confirms only the secret it was shown and nobody can
    replace the secret another browser is confirming.  Starting again replaces the
    secret this session holds.  The issuer the app shows is the organization's name and
    the account name is the email address.  Raises ``DomainError`` with
    :data:`ALREADY_ON` when ``user`` already has a confirmed device.
    """
    if has_two_factor(user):
        raise DomainError(ALREADY_ON)
    secret = new_secret()
    session[ENROLLMENT_SESSION_KEY] = {
        "user": user.pk,
        "secret": secret,
        "started": int(time.time()),
    }
    uri = totp_generator(secret).provisioning_uri(name=user.email, issuer_name=org_name())
    svg = segno.make_qr(uri, error="m").svg_inline(scale=4, border=2)
    return Enrollment(secret=secret, otpauth_uri=uri, qr_svg=svg)


def _enrolling_secret(session: SessionBase, user: User) -> str | None:
    """The secret ``session`` is enrolling for ``user``, while it is fresh enough."""
    stored = session.get(ENROLLMENT_SESSION_KEY)
    if not isinstance(stored, dict) or stored.get("user") != user.pk:
        return None
    started, secret = stored.get("started"), stored.get("secret")
    if not isinstance(started, int) or not isinstance(secret, str):
        return None
    if time.time() - started > ENROLLMENT_SECONDS:
        return None
    return secret


def confirm_enrollment(session: SessionBase, user: User, code: str) -> list[str]:
    """Confirm the secret ``session`` holds for ``user`` with ``code``; the backup codes.

    The code must be the secret's current code (one step of drift either way).  Once it
    is accepted the account's device is stored, confirmed, with that secret, a fresh set
    of :data:`RECOVERY_CODE_COUNT` backup codes replaces any earlier one, the session
    forgets the secret, and the list is returned, grouped for display, the only time
    anybody sees it.  The account is mailed that two-factor sign-in is on, once the
    transaction commits, and ``account.mfa_enable`` is recorded.  The account's row is
    locked for the confirmation, so two browsers confirming at once take turns and the
    second finds two-factor sign-in on.

    Raises ``DomainError`` with :data:`NOT_STARTED` when the session holds no fresh
    secret for ``user``, :data:`ALREADY_ON` when a device is confirmed already, and
    ``DomainValidationError`` on ``otp`` with :data:`CODE_REFUSED` for any other code;
    nothing changes then.
    """
    secret = _enrolling_secret(session, user)
    if secret is None:
        raise DomainError(NOT_STARTED)
    with transaction.atomic():
        User.objects.select_for_update().filter(pk=user.pk).first()
        if has_two_factor(user):
            raise DomainError(ALREADY_ON)
        step = _matching_step(secret, None, code)
        if step is None:
            raise DomainValidationError("otp", CODE_REFUSED)
        TotpDevice.objects.update_or_create(
            user=user,
            defaults={"secret": secret, "confirmed_at": timezone.now(), "last_used_step": step},
        )
        codes = replace_recovery_codes(user)
        audit.record(audit.ACCOUNT_MFA_ENABLE, actor=user, target=user)
        mail_notice(user, "mfa_enabled", "two-factor sign-in is on")
    session.pop(ENROLLMENT_SESSION_KEY, None)
    return codes


# --------------------------------------------------------------------------
# Checking a code
# --------------------------------------------------------------------------
def normalized_code(code: str) -> str:
    """``code`` lowercased, with every space and hyphen taken out."""
    return "".join(code.split()).replace("-", "").lower()


def _matching_step(secret: str, last_used_step: int | None, code: str) -> int | None:
    """The time step whose code under ``secret`` is ``code``, or ``None``.

    The present step and :data:`TOTP_DRIFT_STEPS` either side are tried, and a step at
    or before ``last_used_step`` never matches, so a code is accepted once and an older
    code is refused after a newer one.  Each candidate is compared in constant time.
    """
    candidate = normalized_code(code)
    if len(candidate) != TOTP_DIGITS or not candidate.isdigit():
        return None
    totp = totp_generator(secret)
    now = totp.timecode(timezone.now())
    matched: int | None = None
    for step in range(now - TOTP_DRIFT_STEPS, now + TOTP_DRIFT_STEPS + 1):
        is_fresh = last_used_step is None or step > last_used_step
        if constant_time_compare(totp.generate_otp(step), candidate) and is_fresh:
            matched = step
    return matched


def _recovery_hash(salt: str, code: str, secret_key: str) -> str:
    """The keyed hash a backup code is stored as.

    A backup code carries about 50 bits drawn by ``secrets``, far beyond guessing one
    attempt at a time, so a fast keyed hash is enough and no slow password hash is
    needed: keying it with the site's secret key means a copy of the table alone
    cannot be searched offline, and the per-code ``salt`` makes two equal codes hash
    differently.
    """
    return salted_hmac(
        RECOVERY_HASH_PURPOSE, f"{salt}:{code}", secret=secret_key, algorithm="sha256"
    ).hexdigest()


def _secret_keys() -> list[str]:
    """The site's secret key and its fallbacks, so rotating the key keeps the codes."""
    return [settings.SECRET_KEY, *settings.SECRET_KEY_FALLBACKS]


def _spend_recovery_code(user: User, code: str) -> bool:
    """Spend the unused backup code ``code`` of ``user``'s; False when none matches.

    Every unused code is compared in constant time.  The matching row is marked used
    with a conditional update, so of two requests spending one code at once only one
    succeeds.
    """
    candidate = normalized_code(code)
    if len(candidate) != RECOVERY_CODE_GROUP * RECOVERY_CODE_GROUPS:
        return False
    keys = _secret_keys()
    matched: RecoveryCode | None = None
    for row in RecoveryCode.objects.filter(user=user, used_at__isnull=True):
        for key in keys:
            if hmac.compare_digest(_recovery_hash(row.salt, candidate, key), row.code_hash):
                matched = row
    if matched is None:
        return False
    spent = RecoveryCode.objects.filter(pk=matched.pk, used_at__isnull=True).update(
        used_at=timezone.now()
    )
    return spent == 1


@transaction.atomic
def check_code(user: User, code: str) -> CodeKind | None:
    """Accept ``code`` as ``user``'s second factor, or answer ``None``.

    A six-digit code is checked against the confirmed device and, once accepted,
    records its step so it is never accepted again.  Anything else is tried as a backup
    code, which is spent: the account is then mailed that a backup code was used and
    how many remain.  An account with no confirmed device accepts nothing.  The device
    row is locked for the check, so two requests with one code take turns.
    """
    device = (
        TotpDevice.objects.select_for_update().filter(user=user, confirmed_at__isnull=False).first()
    )
    if device is None:
        return None
    step = _matching_step(device.secret, device.last_used_step, code)
    if step is not None:
        device.last_used_step = step
        device.save(update_fields=["last_used_step", "updated_at"])
        return CodeKind.TOTP
    if not _spend_recovery_code(user, code):
        return None
    audit.record(audit.ACCOUNT_MFA_RECOVERY_USED, actor=user, target=user)
    remaining = recovery_codes_remaining(user)
    mail_notice(
        user, "mfa_recovery_code_used", "a backup code was used", extra={"remaining": remaining}
    )
    return CodeKind.RECOVERY


def require_code(user: User, code: str) -> CodeKind:
    """:func:`check_code`, raising ``DomainValidationError`` on ``otp`` when refused."""
    kind = check_code(user, code)
    if kind is None:
        raise DomainValidationError("otp", CODE_REFUSED)
    return kind


# --------------------------------------------------------------------------
# Backup codes
# --------------------------------------------------------------------------
def _new_recovery_code() -> str:
    """One backup code: two groups of five characters drawn by ``secrets``."""
    groups = [
        "".join(secrets.choice(RECOVERY_CODE_ALPHABET) for _ in range(RECOVERY_CODE_GROUP))
        for _ in range(RECOVERY_CODE_GROUPS)
    ]
    return "-".join(groups)


def replace_recovery_codes(user: User) -> list[str]:
    """Delete every backup code of ``user``'s, store a fresh set, and return it."""
    RecoveryCode.objects.filter(user=user).delete()
    codes = [_new_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
    rows = []
    for code in codes:
        salt = secrets.token_hex(16)
        digest = _recovery_hash(salt, normalized_code(code), settings.SECRET_KEY)
        rows.append(RecoveryCode(user=user, salt=salt, code_hash=digest))
    RecoveryCode.objects.bulk_create(rows)
    return codes


@transaction.atomic
def regenerate_recovery_codes(user: User, code: str) -> list[str]:
    """Replace ``user``'s backup codes, given a current ``code``, and return the new set.

    ``code`` is an authenticator code or one of the backup codes being replaced.  The
    account is mailed that its backup codes were replaced, and
    ``account.mfa_recovery_codes`` is recorded.  Raises ``DomainError`` with
    :data:`NOT_ON` without a confirmed device, and ``DomainValidationError`` on ``otp``
    when the code is refused; nothing changes then.
    """
    if not has_two_factor(user):
        raise DomainError(NOT_ON)
    require_code(user, code)
    codes = replace_recovery_codes(user)
    audit.record(audit.ACCOUNT_MFA_RECOVERY_CODES, actor=user, target=user)
    mail_notice(user, "mfa_recovery_codes_regenerated", "new backup codes")
    return codes


# --------------------------------------------------------------------------
# Turning it off, and an administrator's reset
# --------------------------------------------------------------------------
def remove_two_factor(user: User) -> bool:
    """Delete ``user``'s device and every backup code; True when there was a device.

    ``create_admin`` calls it when it takes an account back, so a device somebody else
    set up on the account cannot keep the real owner out.
    """
    had_device = TotpDevice.objects.filter(user=user).exists()
    TotpDevice.objects.filter(user=user).delete()
    RecoveryCode.objects.filter(user=user).delete()
    return had_device


def refuse_if_required(user: User) -> None:
    """Refuse turning ``user``'s two-factor sign-in off when a role requires it.

    Raises ``DomainPermissionError`` with :data:`REQUIRED_REFUSED`, recorded at WARNING
    as ``account.mfa_disable`` with the reason ``mfa_required``; returns ``None`` for
    anybody else.
    """
    if mfa_required(user):
        audit.refuse(
            audit.ACCOUNT_MFA_DISABLE, actor=user, target=user, reason=audit.REASON_MFA_REQUIRED
        )
        raise DomainPermissionError(REQUIRED_REFUSED)


@transaction.atomic
def disable_two_factor(user: User, code: str) -> None:
    """Turn ``user``'s two-factor sign-in off, given a current ``code``.

    The caller checks the password.  Raises what :func:`refuse_if_required` raises,
    ``DomainError`` with :data:`NOT_ON` without a confirmed device, and
    ``DomainValidationError`` on ``otp`` when the code is refused; nothing changes
    then.  Otherwise the device and the backup codes are deleted,
    ``account.mfa_disable`` is recorded, and the account is mailed that two-factor
    sign-in is off.
    """
    refuse_if_required(user)
    if not has_two_factor(user):
        raise DomainError(NOT_ON)
    require_code(user, code)
    remove_two_factor(user)
    audit.record(audit.ACCOUNT_MFA_DISABLE, actor=user, target=user)
    mail_notice(user, "mfa_disabled", "two-factor sign-in is off")


def reset_two_factor(actor: User | str, target: User) -> None:
    """Take ``target``'s two-factor sign-in away on ``actor``'s behalf, for a lost phone.

    ``actor`` is the administrator's account, or the audit log's command actor for
    ``manage.py reset_two_factor``, which counts as a system administrator.  Who may
    call it at all is the endpoint's rule.  Refused with ``DomainError``, in this order
    and changing nothing: a donor (:data:`DONOR_RESET_REFUSED`), the actor's own
    account (:data:`SELF_RESET_REFUSED`), and a system administrator's account -- the
    role, or a Django superuser -- when the actor is not one
    (:data:`RESET_REFUSED`); each is recorded at WARNING as ``account.mfa_reset``.
    Otherwise the device and every backup code are deleted, every session signed in to
    the account is ended, the reset is recorded as ``account.mfa_reset`` and in the
    account's history, and the account is mailed a notice once the transaction
    commits.  The person sets two-factor sign-in up again at their next sign-in, which
    insists on it when a role requires it.  Resetting an account with nothing set up
    still ends its sessions and records the reset.  The caller holds the transaction.
    """
    refusal = reset_refusal(actor, target)
    if refusal is not None:
        reason, message = refusal
        audit.refuse(audit.ACCOUNT_MFA_RESET, actor=actor, target=target, reason=reason)
        raise DomainError(message)
    remove_two_factor(target)
    end_sessions(target)
    audit.record(audit.ACCOUNT_MFA_RESET, actor=actor, target=target)
    record_account_change(AccountChangeKind.MFA_RESET, actor=actor, target=target)
    mail_notice(target, "mfa_reset", "two-factor sign-in was reset")


def reset_refusal(
    actor: User | str, target: User, *, actor_roles: set[str] | None = None
) -> tuple[str, str] | None:
    """Why ``actor`` may not reset ``target``'s two-factor sign-in, or ``None`` if it may.

    The answer is the audit reason and the sentence, for a donor, the actor's own
    account, and a system administrator's account -- the role or a Django superuser --
    when the actor is not one.  Nothing is recorded; :func:`reset_two_factor` records a
    refusal, and the user record reads this to gray its button out.  ``actor_roles``
    is the actor's effective roles when the caller already has them, which a list of
    many accounts asks for once.
    """
    if is_donor(target):
        return audit.REASON_DONOR_ACCOUNT, DONOR_RESET_REFUSED
    if isinstance(actor, User) and target.pk == actor.pk:
        return audit.REASON_SELF_DEACTIVATION, SELF_RESET_REFUSED
    is_admin_target = SYSTEM_ADMIN in effective_roles(target)
    held = actor_roles if actor_roles is not None else effective_roles(actor)
    if is_admin_target and SYSTEM_ADMIN not in held:
        return audit.REASON_SYSTEM_ADMIN_TARGET, RESET_REFUSED
    return None


def mail_notice(
    user: User, template: str, subject: str, *, extra: dict[str, object] | None = None
) -> None:
    """Mail ``user`` the notice ``emails/<template>.{txt,html}`` once the change commits.

    Outside a transaction it is sent at once.

    The subject is ``"<organization name>: <subject>"``.  A refused send is logged and
    the change stands (``caldart.mail.send_on_commit``).
    """
    name = org_name()
    context: dict[str, object] = {
        "first_name": user.first_name or user.display_name,
        "email": user.email,
        "org_name": name,
        "contact_email": contact_email(),
        "site_url": settings.SITE_URL.rstrip("/"),
        **(extra or {}),
    }
    send_on_commit(
        lambda: send_templated(
            to=user.email,
            subject=f"{name}: {subject}",
            template=template,
            context=context,
            user_id=user.pk,
        ),
        what=f"the {template} notice for account {user.pk}",
    )


# --------------------------------------------------------------------------
# The session
# --------------------------------------------------------------------------
def mark_session(session: SessionBase, user: User) -> None:
    """Mark ``session`` as having passed ``user``'s second factor, now.

    The mark names the account, so it never vouches for another one, and lives in the
    server-side session, where no client can write it.  ``login`` keeps a session's
    data when it changes the key, so call this after ``login``.
    """
    session[VERIFIED_SESSION_KEY] = {"user": str(user.pk), "at": int(time.time())}


def unmark_session(session: SessionBase) -> None:
    """Take the second factor's mark off ``session``, the device behind it being gone."""
    session.pop(VERIFIED_SESSION_KEY, None)


def session_passed(session: SessionBase, user: User) -> bool:
    """True when ``session`` carries the mark for ``user``."""
    mark = session.get(VERIFIED_SESSION_KEY)
    return isinstance(mark, dict) and mark.get("user") == str(user.pk)


def begin_pending(session: SessionBase, user: User, *, reactivate: bool = False) -> SignInStep:
    """Store a pending sign-in for ``user`` in ``session`` and say what it needs next.

    The pending sign-in holds the account's id, a fingerprint of its password (the
    session auth hash, so a password change voids it), when it started, a count of
    wrong codes, whether its owner has been warned of one, and ``reactivate`` for a
    deactivated account that is to come back once the second factor is passed.  It
    needs ``enroll`` when the account has no confirmed device, and ``verify``
    otherwise.  Any earlier pending sign-in in the session is replaced.

    The session's key is changed first, so a key somebody planted in the browser before
    the password was typed never carries the pending sign-in: whoever holds the old key
    cannot finish it, nor enroll a device on it.
    """
    session.cycle_key()
    session[PENDING_SESSION_KEY] = {
        "user": user.pk,
        "auth_hash": user.get_session_auth_hash(),
        "started": int(time.time()),
        "attempts": 0,
        "warned": False,
        "reactivate": reactivate,
    }
    return SignInStep.VERIFY if has_two_factor(user) else SignInStep.ENROLL


def clear_pending(session: SessionBase) -> None:
    """Remove any pending sign-in from ``session``."""
    session.pop(PENDING_SESSION_KEY, None)


def pending_sign_in(session: SessionBase) -> PendingSignIn | None:
    """The pending sign-in ``session`` holds, or ``None`` when there is none to finish.

    ``None`` -- and the pending sign-in is cleared -- once it is older than
    :data:`PENDING_SECONDS`, when the account is gone, can no longer sign in (a donor,
    deactivated without the pending sign-in's ``reactivate``, or blocked from
    reactivating), or has changed its password since, and when it has taken
    :data:`PENDING_ATTEMPTS` wrong codes.  The step is worked out afresh: ``verify``
    once the account has a confirmed device, ``enroll`` before.
    """
    pending = session.get(PENDING_SESSION_KEY)
    if not isinstance(pending, dict):
        return None
    user = _pending_user(pending)
    if user is None:
        clear_pending(session)
        return None
    step = SignInStep.VERIFY if has_two_factor(user) else SignInStep.ENROLL
    return PendingSignIn(user=user, step=step, reactivate=pending.get("reactivate") is True)


def _pending_user(pending: dict[str, object]) -> User | None:
    """The account a stored pending sign-in names, if it may still be finished."""
    user_id = pending.get("user")
    started = pending.get("started")
    attempts = pending.get("attempts")
    if not isinstance(user_id, int):
        return None
    if not isinstance(started, int) or not isinstance(attempts, int):
        return None
    if time.time() - started > PENDING_SECONDS or attempts >= PENDING_ATTEMPTS:
        return None
    user = User.objects.filter(pk=user_id).first()
    if user is None or is_donor(user) or user.reactivation_blocked:
        return None
    if not user.is_active and pending.get("reactivate") is not True:
        return None
    auth_hash = pending.get("auth_hash")
    if not isinstance(auth_hash, str):
        return None
    if not constant_time_compare(auth_hash, user.get_session_auth_hash()):
        return None
    return user


def count_wrong_code(session: SessionBase, user: User) -> bool:
    """Count one wrong code against the pending sign-in; True when that used them up.

    The first wrong code of a pending sign-in mails ``user`` a warning, since only
    somebody who knows the password reaches the code step; later ones do not mail
    again.  The pending sign-in is cleared on the :data:`PENDING_ATTEMPTS`-th wrong
    code, and the person starts again with the password.
    """
    pending = session.get(PENDING_SESSION_KEY)
    if not isinstance(pending, dict):
        return True
    if pending.get("warned") is not True:
        mail_notice(user, "mfa_wrong_code", "a wrong two-factor code was entered")
    attempts = int(pending.get("attempts", 0)) + 1
    if attempts >= PENDING_ATTEMPTS:
        clear_pending(session)
        return True
    session[PENDING_SESSION_KEY] = {**pending, "attempts": attempts, "warned": True}
    return False
