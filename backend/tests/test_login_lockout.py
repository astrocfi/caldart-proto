"""The per-address sign-in lockout.

Ten failed attempts for one email address within fifteen minutes refuse every further
attempt for it, from anywhere, until the window has passed.  Unknown addresses are
counted the same way, so the answers never say which addresses are registered.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from django.core.cache import cache
from django.core.mail import EmailMessage
from freezegun import freeze_time
from pytest_django import Settings
from rest_framework.test import APIClient

from apps.accounts import lockout
from apps.accounts.models import User
from apps.accounts.roles import MEMBER, USER_ADMIN
from tests.conftest import LOGIN_URL, audit_messages, totp_code
from tests.factories import DEFAULT_PASSWORD, UserFactory, confirmed_device

if TYPE_CHECKING:
    from rest_framework.response import _MonkeyPatchedResponse as ApiResponse

pytestmark = pytest.mark.django_db

ATTEMPTS = 10
CODE_ATTEMPTS = 30
WRONG = "not-the-password"
MFA_URL = "/api/v1/auth/login/mfa"
REACTIVATE_URL = "/api/v1/auth/reactivate"


@pytest.fixture(autouse=True)
def lockout_on(settings: Settings) -> Iterator[None]:
    """Turn the lockout on at its defaults, with nothing counted before or after."""
    settings.LOGIN_LOCKOUT_ATTEMPTS = ATTEMPTS
    settings.LOGIN_LOCKOUT_SECONDS = 15 * 60
    settings.LOGIN_LOCKOUT_CODE_ATTEMPTS = CODE_ATTEMPTS
    settings.LOGIN_LOCKOUT_CODE_SECONDS = 24 * 60 * 60
    cache.clear()
    yield
    cache.clear()


def attempt(email: str, password: str = WRONG, *, address: str = "198.51.100.7") -> ApiResponse:
    """One sign-in from a fresh browser at client ``address``."""
    return APIClient(REMOTE_ADDR=address).post(
        LOGIN_URL, {"email": email, "password": password}, format="json"
    )


def fail(email: str, times: int) -> list[int]:
    """Make ``times`` wrong attempts for ``email``; their statuses."""
    return [attempt(email).status_code for _ in range(times)]


def test_the_eleventh_attempt_is_refused(member: User) -> None:
    """Ten wrong passwords are answered; the next is a 429."""
    assert fail(member.email, ATTEMPTS + 1) == [400] * ATTEMPTS + [429]


def test_a_locked_out_address_refuses_the_right_password(member: User) -> None:
    """The lockout holds whatever the password."""
    fail(member.email, ATTEMPTS)
    assert attempt(member.email, DEFAULT_PASSWORD).status_code == 429


def test_the_refusal_says_when_to_try_again(member: User) -> None:
    """A ``Retry-After`` header in whole seconds, within the window."""
    fail(member.email, ATTEMPTS)
    assert 0 < int(attempt(member.email)["Retry-After"]) <= 15 * 60


def test_the_refusal_says_what_happened(member: User) -> None:
    """A sentence, then DRF's wait."""
    fail(member.email, ATTEMPTS)
    assert attempt(member.email).json()["detail"].startswith(lockout.LOCKED_OUT)


def test_the_lockout_ignores_the_client_address(member: User) -> None:
    """Spreading guesses over many addresses does not help."""
    statuses = [attempt(member.email, address=f"203.0.113.{n}").status_code for n in range(11)]
    assert statuses[-1] == 429


def test_an_unknown_address_locks_out_the_same_way() -> None:
    """The answers for nobody match the answers for somebody."""
    assert fail("nobody@example.test", ATTEMPTS + 1) == [400] * ATTEMPTS + [429]


def test_the_lockout_counts_every_spelling_of_an_address(member: User) -> None:
    """Capitals and spaces are the same address."""
    fail(member.email.upper(), ATTEMPTS)
    assert attempt(f" {member.email} ", DEFAULT_PASSWORD).status_code == 429


def test_another_address_is_not_locked_out(member: User) -> None:
    """Only the address that was guessed at is refused."""
    fail("nobody@example.test", ATTEMPTS)
    assert attempt(member.email, DEFAULT_PASSWORD).status_code == 200


def test_a_successful_sign_in_clears_the_count(member: User) -> None:
    """Nine failures, a success, and nine more do not lock anybody out."""
    fail(member.email, ATTEMPTS - 1)
    attempt(member.email, DEFAULT_PASSWORD)
    assert fail(member.email, ATTEMPTS - 1) == [400] * (ATTEMPTS - 1)


def test_the_window_passing_lifts_the_lockout(member: User) -> None:
    """Once the window that began with the first failure closes, the address is open."""
    fail(member.email, ATTEMPTS)
    with freeze_time(timedelta(seconds=15 * 60 + 1)):
        status = attempt(member.email, DEFAULT_PASSWORD).status_code
    assert status == 200


def test_the_lockout_is_audited(member: User, audit_log: pytest.LogCaptureFixture) -> None:
    """One WARNING line, naming the account, never the address or a password."""
    fail(member.email, ATTEMPTS)
    assert audit_messages(audit_log) == [
        f"action=account.lockout actor=anonymous target={member.pk} "
        f"attempts={ATTEMPTS} reason=too_many_failures"
    ]


def test_an_unknown_address_is_audited_without_a_target(
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """No account holds the address, so the line names none."""
    fail("nobody@example.test", ATTEMPTS)
    assert audit_messages(audit_log) == [
        f"action=account.lockout actor=anonymous target=- "
        f"attempts={ATTEMPTS} reason=too_many_failures"
    ]


def sign_in_with_password(client: APIClient, user: User) -> ApiResponse:
    """Post ``user``'s address and right password from ``client``."""
    return client.post(
        LOGIN_URL, {"email": user.email, "password": DEFAULT_PASSWORD}, format="json"
    )


def test_wrong_codes_count_against_the_address() -> None:
    """A right password with ten wrong codes locks the address out too."""
    admin = UserFactory(roles=[MEMBER, USER_ADMIN])
    confirmed_device(admin)
    client = APIClient()
    for _ in range(2):
        sign_in_with_password(client, admin)
        for _ in range(5):
            client.post(MFA_URL, {"otp": "000000"}, format="json")
    assert sign_in_with_password(client, admin).status_code == 429


def test_the_code_step_is_refused_once_the_address_is_locked_out() -> None:
    """A lockout reached while a code is awaited refuses even the right code."""
    admin = UserFactory(roles=[MEMBER, USER_ADMIN])
    device = confirmed_device(admin)
    fail(admin.email, ATTEMPTS - 1)
    client = APIClient()
    sign_in_with_password(client, admin)
    client.post(MFA_URL, {"otp": "000000"}, format="json")
    assert client.post(MFA_URL, {"otp": totp_code(device)}, format="json").status_code == 429


def test_wrong_reactivation_passwords_count(member: User) -> None:
    """Reactivation takes a password, so it is counted like a sign-in."""
    client = APIClient()
    for _ in range(ATTEMPTS):
        client.post(REACTIVATE_URL, {"email": member.email, "password": WRONG}, format="json")
    assert attempt(member.email, DEFAULT_PASSWORD).status_code == 429


def test_the_lockout_can_be_switched_off(member: User, settings: Settings) -> None:
    """``LOGIN_LOCKOUT_ATTEMPTS = 0`` counts nothing."""
    settings.LOGIN_LOCKOUT_ATTEMPTS = 0
    fail(member.email, ATTEMPTS)
    assert attempt(member.email, DEFAULT_PASSWORD).status_code == 200


@pytest.mark.parametrize(
    "spelling",
    [
        "member@example.test".replace("st", "\u017ft"),
        "MEMBER@EXAMPLE.TEST",
        " member@example.test ",
    ],
    ids=["long s", "capitals", "spaces"],
)
def test_every_spelling_that_signs_in_shares_the_count(member: User, spelling: str) -> None:
    """An address the database matches to the account is counted as the account."""
    fail(member.email, ATTEMPTS)
    assert attempt(spelling, DEFAULT_PASSWORD).status_code == 429


def test_wrong_codes_lock_out_over_a_day() -> None:
    """Thirty wrong codes in a day lock the address out, even between good sign-ins."""
    admin = UserFactory(roles=[MEMBER, USER_ADMIN])
    for attempt_number in range(1, CODE_ATTEMPTS + 1):
        lockout.record_failure(admin.email, code=True)
        if attempt_number % 5 == 0:
            lockout.clear_failures(admin.email)
    assert sign_in_with_password(APIClient(), admin).status_code == 429


def test_a_lockout_mails_the_owner(
    member: User,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: object,
) -> None:
    """The owner hears once, when the limit is reached."""
    with django_capture_on_commit_callbacks(execute=True):  # type: ignore[operator]
        fail(member.email, ATTEMPTS + 2)
    assert [message.subject for message in mailoutbox] == [
        "CalDART: sign-in paused after failed attempts"
    ]


def test_the_lockout_notice_is_mailed_once_a_day(
    member: User,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: object,
) -> None:
    """A second lockout the same day mails nothing more."""
    with django_capture_on_commit_callbacks(execute=True):  # type: ignore[operator]
        fail(member.email, ATTEMPTS)
        with freeze_time(timedelta(seconds=15 * 60 + 1)):
            fail(member.email, ATTEMPTS)
    assert len(mailoutbox) == 1


def test_counts_survive_a_full_cache(member: User) -> None:
    """The counts live in the database, so a cache that forgets lets no guess through."""
    fail(member.email, ATTEMPTS)
    cache.set_many({f"filler-{n}": n for n in range(2000)})
    cache.clear()
    assert attempt(member.email, DEFAULT_PASSWORD).status_code == 429


def test_an_unknown_address_is_counted_as_the_database_compares_it() -> None:
    """A dotless-i spelling of an unknown address shares its count."""
    fail("p\u0131lot@example.test", ATTEMPTS)
    assert attempt("pilot@example.test").status_code == 429
