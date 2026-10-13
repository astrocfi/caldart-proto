"""Two-factor sign-in as a service: who needs it, enrolling, codes, and backup codes.

The rules are ``docs/developer/api-auth.rst``'s two-factor section: an authenticator
code is RFC 6238 (SHA-1, six digits, 30-second steps, one step of drift either way)
and is accepted once; a backup code is accepted once, in any case, with or without its
hyphen and spaces; and only a keyed hash of a backup code is stored.
"""

from __future__ import annotations

import logging
import re

import pytest
from django.contrib.sessions.backends.db import SessionStore
from django.core.mail import EmailMessage
from pytest_django import Settings

from apps.accounts import mfa
from apps.accounts.models import AccountKind, RecoveryCode, TotpDevice, User
from apps.accounts.roles import (
    ACCOUNT_ADMIN,
    DART_LEADER,
    MANAGEMENT,
    MEMBER,
    SYSTEM_ADMIN,
    TREASURER,
    USER_ADMIN,
    VERIFIER,
    WEBSITE_ADMIN,
)
from caldart.exceptions import DomainError, DomainPermissionError, DomainValidationError
from tests.conftest import totp_code
from tests.factories import UserFactory, confirmed_device

pytestmark = pytest.mark.django_db

#: What a backup code looks like as it is shown: two groups of five, hyphenated.
CODE_SHAPE = re.compile(r"[a-z2-9]{5}-[a-z2-9]{5}")


@pytest.fixture
def person() -> User:
    """A plain member with no second factor."""
    return UserFactory(email="pat.person@example.test", roles=[MEMBER])


@pytest.fixture
def enrolled(person: User) -> TotpDevice:
    """``person`` with a confirmed device and no backup codes yet."""
    return confirmed_device(person)


@pytest.fixture
def session() -> SessionStore:
    """An empty, unsaved session, which is all the session helpers touch."""
    return SessionStore()


def fresh_codes(user: User) -> list[str]:
    """Give ``user`` a fresh set of backup codes and return them."""
    return mfa.replace_recovery_codes(user)


# -- who needs a second factor -----------------------------------------------


@pytest.mark.parametrize(
    "role", [USER_ADMIN, TREASURER, ACCOUNT_ADMIN, MANAGEMENT, WEBSITE_ADMIN, SYSTEM_ADMIN]
)
def test_a_staff_role_requires_two_factor(role: str) -> None:
    """Each role that can reach other people's accounts or money requires it."""
    assert mfa.mfa_required(UserFactory(roles=[MEMBER, role])) is True


@pytest.mark.parametrize("role", [MEMBER, VERIFIER, DART_LEADER])
def test_other_roles_do_not_require_two_factor(role: str) -> None:
    """A member, a verifier, and a DART leader may choose it but need not."""
    assert mfa.mfa_required(UserFactory(roles=[role])) is False


def test_a_superuser_without_the_role_group_requires_two_factor() -> None:
    """``createsuperuser`` sets the flag alone, which counts as a system administrator."""
    assert mfa.mfa_required(UserFactory(is_superuser=True, is_staff=True)) is True


def test_a_confirmed_device_means_a_second_factor_is_needed(enrolled: TotpDevice) -> None:
    """Somebody who turned it on voluntarily is asked for a code."""
    assert mfa.needs_second_factor(enrolled.user) is True


def test_starting_enrollment_writes_no_device(person: User, session: SessionStore) -> None:
    """The secret waits in the session; sign-in asks for nothing until it is confirmed."""
    mfa.start_enrollment(session, person)
    assert TotpDevice.objects.filter(user=person).exists() is False


# -- enrolling ---------------------------------------------------------------


def test_starting_enrollment_names_the_issuer_and_the_account(
    person: User, session: SessionStore
) -> None:
    """The ``otpauth://`` address carries the organization and the email address."""
    enrollment = mfa.start_enrollment(session, person)
    assert enrollment.otpauth_uri.startswith(
        "otpauth://totp/CalDART:pat.person%40example.test?secret="
    )


def test_starting_enrollment_draws_the_qr_code_as_svg(person: User, session: SessionStore) -> None:
    """The QR code is an inline SVG element the portal can show as an image."""
    assert mfa.start_enrollment(session, person).qr_svg.startswith("<svg")


def test_starting_enrollment_again_replaces_the_secret(person: User, session: SessionStore) -> None:
    """A QR code shown earlier stops working once enrollment starts over."""
    first = mfa.start_enrollment(session, person).secret
    mfa.start_enrollment(session, person)
    with pytest.raises(DomainValidationError):
        mfa.confirm_enrollment(session, person, totp_code(first))


def test_another_session_cannot_replace_the_secret(person: User, session: SessionStore) -> None:
    """Each browser confirms the secret it was shown, whatever another one starts."""
    secret = mfa.start_enrollment(session, person).secret
    mfa.start_enrollment(SessionStore(), person)
    assert len(mfa.confirm_enrollment(session, person, totp_code(secret))) == 10


def test_a_secret_carries_160_bits(person: User, session: SessionStore) -> None:
    """Twenty random bytes are 32 base32 characters."""
    assert len(mfa.start_enrollment(session, person).secret) == 32


def test_enrollment_cannot_start_over_a_confirmed_device(
    enrolled: TotpDevice, session: SessionStore
) -> None:
    """A password alone must never replace a working device."""
    with pytest.raises(DomainError, match="already on"):
        mfa.start_enrollment(session, enrolled.user)


def test_confirming_with_the_current_code_confirms_the_device(
    person: User, session: SessionStore
) -> None:
    """The first accepted code stores the device, confirmed."""
    secret = mfa.start_enrollment(session, person).secret
    mfa.confirm_enrollment(session, person, totp_code(secret))
    assert TotpDevice.objects.get(user=person).confirmed_at is not None


def test_confirming_returns_ten_backup_codes_shown_in_two_groups(
    person: User, session: SessionStore
) -> None:
    """The codes come back once, grouped like ``abcde-fghjk``."""
    secret = mfa.start_enrollment(session, person).secret
    codes = mfa.confirm_enrollment(session, person, totp_code(secret))
    assert [bool(CODE_SHAPE.fullmatch(code)) for code in codes] == [True] * 10


def test_confirming_with_a_wrong_code_confirms_nothing(person: User, session: SessionStore) -> None:
    """A wrong code is refused on the ``otp`` field and no device is stored."""
    mfa.start_enrollment(session, person)
    with pytest.raises(DomainValidationError, match="not right"):
        mfa.confirm_enrollment(session, person, "000000")
    assert mfa.has_two_factor(person) is False


def test_confirming_before_starting_is_refused(person: User, session: SessionStore) -> None:
    """There is no secret to check a code against."""
    with pytest.raises(DomainError, match="Start setting up"):
        mfa.confirm_enrollment(session, person, "123456")


def test_confirming_twice_is_refused(person: User, session: SessionStore) -> None:
    """The secret is forgotten once confirmed."""
    secret = mfa.start_enrollment(session, person).secret
    mfa.confirm_enrollment(session, person, totp_code(secret))
    with pytest.raises(DomainError, match="Start setting up"):
        mfa.confirm_enrollment(session, person, totp_code(secret, offset=1))


def test_confirming_mails_that_two_factor_is_on(
    person: User,
    session: SessionStore,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: object,
) -> None:
    """The account is told, in case somebody else turned it on."""
    secret = mfa.start_enrollment(session, person).secret
    with django_capture_on_commit_callbacks(execute=True):  # type: ignore[operator]
        mfa.confirm_enrollment(session, person, totp_code(secret))
    assert [message.subject for message in mailoutbox] == ["CalDART: two-factor sign-in is on"]


# -- authenticator codes -----------------------------------------------------


def test_the_current_code_is_accepted(enrolled: TotpDevice) -> None:
    """A code from the present step passes as an authenticator code."""
    assert mfa.check_code(enrolled.user, totp_code(enrolled)) == mfa.CodeKind.TOTP


@pytest.mark.parametrize("offset", [-1, 1], ids=["previous step", "next step"])
def test_one_step_of_drift_is_accepted(enrolled: TotpDevice, offset: int) -> None:
    """A phone a little ahead or behind still signs in."""
    assert mfa.check_code(enrolled.user, totp_code(enrolled, offset=offset)) == mfa.CodeKind.TOTP


@pytest.mark.parametrize("offset", [-2, 2], ids=["two steps behind", "two steps ahead"])
def test_two_steps_of_drift_are_refused(enrolled: TotpDevice, offset: int) -> None:
    """Anything further out is not accepted."""
    assert mfa.check_code(enrolled.user, totp_code(enrolled, offset=offset)) is None


def test_a_code_is_accepted_only_once(enrolled: TotpDevice) -> None:
    """Replaying the code that just signed somebody in is refused."""
    code = totp_code(enrolled)
    mfa.check_code(enrolled.user, code)
    assert mfa.check_code(enrolled.user, code) is None


def test_an_older_code_is_refused_after_a_newer_one(enrolled: TotpDevice) -> None:
    """Once the next step's code is used, the present step's is spent too."""
    mfa.check_code(enrolled.user, totp_code(enrolled, offset=1))
    assert mfa.check_code(enrolled.user, totp_code(enrolled)) is None


def test_the_next_step_is_accepted_after_the_current_one(enrolled: TotpDevice) -> None:
    """A later step's code still works after the present step's was used."""
    mfa.check_code(enrolled.user, totp_code(enrolled))
    assert mfa.check_code(enrolled.user, totp_code(enrolled, offset=1)) == mfa.CodeKind.TOTP


def test_a_code_with_spaces_is_accepted(enrolled: TotpDevice) -> None:
    """``123 456``, as some apps show it, is read as ``123456``."""
    code = totp_code(enrolled)
    assert mfa.check_code(enrolled.user, f"{code[:3]} {code[3:]}") == mfa.CodeKind.TOTP


def test_another_accounts_code_is_refused(enrolled: TotpDevice) -> None:
    """A code is checked against the account's own secret."""
    other = confirmed_device(UserFactory())
    assert mfa.check_code(enrolled.user, totp_code(other)) is None


# -- backup codes ------------------------------------------------------------


def test_a_backup_code_is_accepted_in_place_of_a_code(enrolled: TotpDevice) -> None:
    """Every place that takes a code takes a backup code."""
    code = fresh_codes(enrolled.user)[0]
    assert mfa.check_code(enrolled.user, code) == mfa.CodeKind.RECOVERY


def test_a_backup_code_works_once(enrolled: TotpDevice) -> None:
    """A spent backup code is refused."""
    code = fresh_codes(enrolled.user)[0]
    mfa.check_code(enrolled.user, code)
    assert mfa.check_code(enrolled.user, code) is None


@pytest.mark.parametrize(
    "spelling",
    [str.upper, lambda code: code.replace("-", ""), lambda code: code.replace("-", " - ")],
    ids=["capitals", "no hyphen", "spaces"],
)
def test_a_backup_code_is_read_however_it_is_typed(enrolled: TotpDevice, spelling: object) -> None:
    """Case, the hyphen, and spaces do not matter."""
    code = fresh_codes(enrolled.user)[0]
    typed = spelling(code)  # type: ignore[operator]
    assert mfa.check_code(enrolled.user, typed) == mfa.CodeKind.RECOVERY


def test_only_a_hash_of_a_backup_code_is_stored(enrolled: TotpDevice) -> None:
    """No row holds the code itself, with or without its hyphen."""
    codes = fresh_codes(enrolled.user)
    stored = " ".join(f"{row.salt} {row.code_hash}" for row in RecoveryCode.objects.all())
    assert [code for code in codes if code.replace("-", "") in stored or code in stored] == []


def test_using_a_backup_code_mails_how_many_remain(
    enrolled: TotpDevice,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: object,
) -> None:
    """The account is told a code was spent and that nine are left."""
    code = fresh_codes(enrolled.user)[0]
    with django_capture_on_commit_callbacks(execute=True):  # type: ignore[operator]
        mfa.check_code(enrolled.user, code)
    assert "You have 9 unused backup codes left." in str(mailoutbox[0].body)


def test_regenerating_replaces_the_whole_set(enrolled: TotpDevice) -> None:
    """Every earlier code stops working."""
    old = fresh_codes(enrolled.user)
    mfa.regenerate_recovery_codes(enrolled.user, totp_code(enrolled))
    assert [mfa.check_code(enrolled.user, code) for code in old[1:4]] == [None, None, None]


def test_regenerating_returns_ten_fresh_codes(enrolled: TotpDevice) -> None:
    """The new set is ten codes, all unused."""
    fresh_codes(enrolled.user)
    mfa.regenerate_recovery_codes(enrolled.user, totp_code(enrolled))
    assert mfa.recovery_codes_remaining(enrolled.user) == 10


def test_regenerating_needs_a_right_code(enrolled: TotpDevice) -> None:
    """A wrong code changes nothing."""
    old = fresh_codes(enrolled.user)
    with pytest.raises(DomainValidationError):
        mfa.regenerate_recovery_codes(enrolled.user, "000000")
    assert mfa.check_code(enrolled.user, old[0]) == mfa.CodeKind.RECOVERY


def test_a_backup_code_survives_a_rotated_secret_key(
    enrolled: TotpDevice, settings: Settings
) -> None:
    """A code hashed under the old key is still read while the key is a fallback."""
    code = fresh_codes(enrolled.user)[0]
    old_key = settings.SECRET_KEY
    settings.SECRET_KEY = "a-rotated-key-for-this-test-only"  # noqa: S105 - a test fixture
    settings.SECRET_KEY_FALLBACKS = [old_key]
    assert mfa.check_code(enrolled.user, code) == mfa.CodeKind.RECOVERY


# -- turning it off ----------------------------------------------------------


def test_turning_it_off_removes_the_device_and_the_codes(enrolled: TotpDevice) -> None:
    """Nothing is left to ask for at the next sign-in."""
    fresh_codes(enrolled.user)
    mfa.disable_two_factor(enrolled.user, totp_code(enrolled))
    assert RecoveryCode.objects.filter(user=enrolled.user).exists() is False
    assert mfa.needs_second_factor(enrolled.user) is False


def test_a_required_role_cannot_turn_it_off() -> None:
    """The server refuses, whatever the code."""
    admin = UserFactory(roles=[USER_ADMIN])
    device = confirmed_device(admin)
    with pytest.raises(DomainPermissionError, match="requires two-factor"):
        mfa.disable_two_factor(admin, totp_code(device))
    assert mfa.has_two_factor(admin) is True


def test_turning_it_off_needs_a_right_code(enrolled: TotpDevice) -> None:
    """A wrong code leaves the device in place."""
    with pytest.raises(DomainValidationError):
        mfa.disable_two_factor(enrolled.user, "000000")
    assert mfa.has_two_factor(enrolled.user) is True


# -- an administrator's reset -------------------------------------------------


def test_a_reset_removes_the_device_and_the_codes(enrolled: TotpDevice) -> None:
    """The person enrolls again at the next sign-in."""
    fresh_codes(enrolled.user)
    mfa.reset_two_factor(UserFactory(roles=[MEMBER, USER_ADMIN]), enrolled.user)
    assert TotpDevice.objects.filter(user=enrolled.user).exists() is False
    assert RecoveryCode.objects.filter(user=enrolled.user).exists() is False


def test_nobody_resets_their_own() -> None:
    """The reset is for somebody else's lost phone."""
    admin = UserFactory(roles=[USER_ADMIN])
    with pytest.raises(DomainError, match="your own"):
        mfa.reset_two_factor(admin, admin)


def test_a_donor_is_not_reset() -> None:
    """A donor has no portal account."""
    donor = UserFactory(kind=AccountKind.DONOR)
    with pytest.raises(DomainError, match="donor"):
        mfa.reset_two_factor(UserFactory(roles=[USER_ADMIN]), donor)


def test_a_user_administrator_cannot_reset_a_system_administrator() -> None:
    """Only a system administrator resets a system administrator's second factor."""
    target = UserFactory(roles=[SYSTEM_ADMIN])
    confirmed_device(target)
    with pytest.raises(DomainError, match="Only a system administrator"):
        mfa.reset_two_factor(UserFactory(roles=[USER_ADMIN]), target)
    assert mfa.has_two_factor(target) is True


def test_a_user_administrator_cannot_reset_a_superuser() -> None:
    """The superuser flag counts as a system administrator."""
    target = UserFactory(is_superuser=True, is_staff=True)
    confirmed_device(target)
    with pytest.raises(DomainError, match="Only a system administrator"):
        mfa.reset_two_factor(UserFactory(roles=[USER_ADMIN]), target)


def test_a_user_administrator_resets_a_role_they_do_not_hold() -> None:
    """A treasurer's lost phone is a user administrator's to reset."""
    target = UserFactory(roles=[MEMBER, TREASURER])
    confirmed_device(target)
    mfa.reset_two_factor(UserFactory(roles=[USER_ADMIN]), target)
    assert mfa.has_two_factor(target) is False


def test_a_system_administrator_resets_another() -> None:
    """One system administrator may reset another's."""
    target = UserFactory(roles=[SYSTEM_ADMIN])
    confirmed_device(target)
    mfa.reset_two_factor(UserFactory(roles=[SYSTEM_ADMIN]), target)
    assert mfa.has_two_factor(target) is False


# -- the pending sign-in -----------------------------------------------------


def test_a_pending_sign_in_names_its_account(enrolled: TotpDevice, session: SessionStore) -> None:
    """The code step finds the account the password step stored."""
    mfa.begin_pending(session, enrolled.user)
    pending = mfa.pending_sign_in(session)
    assert pending is not None
    assert pending.user == enrolled.user


def test_a_pending_sign_in_without_a_device_needs_enrollment(
    person: User, session: SessionStore
) -> None:
    """An account that must use a second factor but has none enrolls first."""
    assert mfa.begin_pending(session, person) == mfa.SignInStep.ENROLL


def test_a_pending_sign_in_expires_after_five_minutes(
    enrolled: TotpDevice, session: SessionStore
) -> None:
    """After that the password is asked again."""
    mfa.begin_pending(session, enrolled.user)
    pending = session[mfa.PENDING_SESSION_KEY]
    assert isinstance(pending, dict)
    pending["started"] -= mfa.PENDING_SECONDS + 1
    assert mfa.pending_sign_in(session) is None


def test_a_password_change_voids_a_pending_sign_in(
    enrolled: TotpDevice, session: SessionStore
) -> None:
    """The pending sign-in is bound to the password that started it."""
    mfa.begin_pending(session, enrolled.user)
    enrolled.user.set_password("A-different-password-2027")
    enrolled.user.save()
    assert mfa.pending_sign_in(session) is None


def test_a_deactivated_account_voids_a_pending_sign_in(
    enrolled: TotpDevice, session: SessionStore
) -> None:
    """An account deactivated meanwhile cannot finish signing in."""
    mfa.begin_pending(session, enrolled.user)
    User.objects.filter(pk=enrolled.user.pk).update(is_active=False)
    assert mfa.pending_sign_in(session) is None


def test_five_wrong_codes_end_a_pending_sign_in(
    enrolled: TotpDevice, session: SessionStore
) -> None:
    """The fifth wrong code clears it."""
    mfa.begin_pending(session, enrolled.user)
    spent = [mfa.count_wrong_code(session, enrolled.user) for _ in range(5)]
    assert spent == [False, False, False, False, True]
    assert mfa.pending_sign_in(session) is None


def test_the_mark_names_its_account(enrolled: TotpDevice, session: SessionStore) -> None:
    """A mark left for one account does not vouch for another."""
    mfa.mark_session(session, enrolled.user)
    assert mfa.session_passed(session, UserFactory()) is False


# -- nothing secret is logged ------------------------------------------------


def test_no_secret_or_code_reaches_a_log(
    person: User, session: SessionStore, caplog: pytest.LogCaptureFixture
) -> None:
    """Enrolling and using a code logs neither the secret nor any code."""
    logging.getLogger("caldart.audit").addHandler(caplog.handler)
    try:
        with caplog.at_level(logging.DEBUG):
            secret = mfa.start_enrollment(session, person).secret
            first = totp_code(secret)
            codes = mfa.confirm_enrollment(session, person, first)
            mfa.check_code(person, codes[0])
    finally:
        logging.getLogger("caldart.audit").removeHandler(caplog.handler)
    logged = caplog.text
    assert [value for value in [secret, first, *codes] if value in logged] == []


def test_a_reactivating_sign_in_may_name_a_deactivated_account(
    enrolled: TotpDevice, session: SessionStore
) -> None:
    """``/auth/reactivate`` leaves the account deactivated until the code is given."""
    User.objects.filter(pk=enrolled.user.pk).update(is_active=False)
    mfa.begin_pending(session, User.objects.get(pk=enrolled.user.pk), reactivate=True)
    pending = mfa.pending_sign_in(session)
    assert pending is not None
    assert pending.reactivate is True


def test_a_blocked_account_voids_a_reactivating_sign_in(
    enrolled: TotpDevice, session: SessionStore
) -> None:
    """A block set while the code is awaited ends the pending sign-in."""
    User.objects.filter(pk=enrolled.user.pk).update(is_active=False)
    mfa.begin_pending(session, User.objects.get(pk=enrolled.user.pk), reactivate=True)
    User.objects.filter(pk=enrolled.user.pk).update(reactivation_blocked=True)
    assert mfa.pending_sign_in(session) is None


def test_the_first_wrong_code_warns_the_owner_once(
    enrolled: TotpDevice,
    session: SessionStore,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: object,
) -> None:
    """Only somebody holding the password reaches the code step, so its owner hears."""
    mfa.begin_pending(session, enrolled.user)
    with django_capture_on_commit_callbacks(execute=True):  # type: ignore[operator]
        mfa.count_wrong_code(session, enrolled.user)
        mfa.count_wrong_code(session, enrolled.user)
    assert [message.subject for message in mailoutbox] == [
        "CalDART: a wrong two-factor code was entered"
    ]


def test_removing_two_factor_says_whether_there_was_a_device(enrolled: TotpDevice) -> None:
    """``create_admin`` records whether its take-back removed one."""
    assert [mfa.remove_two_factor(enrolled.user), mfa.remove_two_factor(enrolled.user)] == [
        True,
        False,
    ]
