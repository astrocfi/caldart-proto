"""A person's own two-factor sign-in: its status, turning it on and off, and codes."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.core.mail import EmailMessage
from rest_framework.test import APIClient

from apps.accounts import mfa
from apps.accounts.models import TotpDevice, User
from apps.accounts.roles import MEMBER, TREASURER
from tests.conftest import ME_URL, totp_code
from tests.factories import DEFAULT_PASSWORD, UserFactory, confirmed_device

if TYPE_CHECKING:
    from rest_framework.response import _MonkeyPatchedResponse as ApiResponse

pytestmark = pytest.mark.django_db

WRONG_PASSWORD = "not-the-password"  # noqa: S105 - a guess the server refuses

STATUS_URL = "/api/v1/auth/mfa"
ENROLL_URL = "/api/v1/auth/mfa/enroll"
CONFIRM_URL = "/api/v1/auth/mfa/enroll/confirm"
CODES_URL = "/api/v1/auth/mfa/recovery-codes"
DISABLE_URL = "/api/v1/auth/mfa/disable"


@pytest.fixture
def signed_in(api_client: APIClient, member: User) -> APIClient:
    """``api_client`` signed in as a plain member."""
    api_client.force_login(member)
    return api_client


@pytest.fixture
def device(member: User) -> TotpDevice:
    """``member``'s confirmed device, turned on voluntarily."""
    return confirmed_device(member)


def enroll(client: APIClient, user: User) -> str:
    """Start enrollment as ``client``'s account; the unconfirmed device it made."""
    response = client.post(ENROLL_URL, {"current_password": DEFAULT_PASSWORD}, format="json")
    secret: str = response.json()["secret"]
    return secret


# -- status ------------------------------------------------------------------


def test_a_member_starts_with_it_off(signed_in: APIClient) -> None:
    """Off, not required, and without backup codes."""
    assert signed_in.get(STATUS_URL).json() == {
        "enabled": False,
        "required_by_role": False,
        "recovery_codes_remaining": 0,
    }


def test_a_treasurer_is_told_it_is_required(api_client: APIClient) -> None:
    """The role requires it, so the Security card doesn't offer a way to turn it off."""
    treasurer = UserFactory(roles=[MEMBER, TREASURER])
    confirmed_device(treasurer)
    api_client.force_login(treasurer)
    assert api_client.get(STATUS_URL).json()["required_by_role"] is True


@pytest.mark.parametrize(
    ("method", "url"),
    [
        ("get", STATUS_URL),
        ("post", ENROLL_URL),
        ("post", CONFIRM_URL),
        ("post", CODES_URL),
        ("post", DISABLE_URL),
    ],
)
def test_anonymous_callers_are_refused(api_client: APIClient, method: str, url: str) -> None:
    """Every Security endpoint needs a session."""
    assert getattr(api_client, method)(url).status_code == 401


# -- turning it on -----------------------------------------------------------


def test_turning_it_on_answers_ten_codes(signed_in: APIClient, member: User) -> None:
    """Confirming with a code from the new device shows the backup codes once."""
    secret = enroll(signed_in, member)
    body = signed_in.post(CONFIRM_URL, {"otp": totp_code(secret)}, format="json").json()
    assert len(body["recovery_codes"]) == 10


def test_turning_it_on_keeps_the_session(signed_in: APIClient, member: User) -> None:
    """The browser that turned it on stays signed in."""
    secret = enroll(signed_in, member)
    signed_in.post(CONFIRM_URL, {"otp": totp_code(secret)}, format="json")
    assert signed_in.get(ME_URL).status_code == 200


def test_turning_it_on_reads_as_on(signed_in: APIClient, member: User) -> None:
    """The status says so, with ten codes left."""
    secret = enroll(signed_in, member)
    signed_in.post(CONFIRM_URL, {"otp": totp_code(secret)}, format="json")
    status = signed_in.get(STATUS_URL).json()
    assert status == {"enabled": True, "required_by_role": False, "recovery_codes_remaining": 10}


def test_a_wrong_code_does_not_turn_it_on(signed_in: APIClient, member: User) -> None:
    """The refusal names the ``otp`` field."""
    enroll(signed_in, member)
    response = signed_in.post(CONFIRM_URL, {"otp": "000000"}, format="json")
    assert response.json() == {"otp": [mfa.CODE_REFUSED]}


def test_starting_again_while_on_is_refused(signed_in: APIClient, device: TotpDevice) -> None:
    """A working device is never replaced by starting over."""
    response = signed_in.post(ENROLL_URL, {"current_password": DEFAULT_PASSWORD}, format="json")
    assert response.json() == {"detail": mfa.ALREADY_ON}


def test_confirming_before_starting_is_refused(signed_in: APIClient) -> None:
    """There isn't anything to confirm."""
    response = signed_in.post(CONFIRM_URL, {"otp": "123456"}, format="json")
    assert response.json() == {"detail": mfa.NOT_STARTED}


# -- backup codes ------------------------------------------------------------


def test_new_backup_codes_need_a_code(signed_in: APIClient, device: TotpDevice) -> None:
    """A right code answers a fresh set of ten."""
    response = signed_in.post(CODES_URL, {"otp": totp_code(device)}, format="json")
    assert len(response.json()["recovery_codes"]) == 10


def test_a_backup_code_may_ask_for_new_ones(signed_in: APIClient, device: TotpDevice) -> None:
    """A backup code is accepted wherever a code is."""
    old = mfa.replace_recovery_codes(device.user)
    response = signed_in.post(CODES_URL, {"otp": old[0]}, format="json")
    assert response.status_code == 200


def test_new_backup_codes_refuse_a_wrong_code(signed_in: APIClient, device: TotpDevice) -> None:
    """Nothing is replaced."""
    response = signed_in.post(CODES_URL, {"otp": "000000"}, format="json")
    assert response.json() == {"otp": [mfa.CODE_REFUSED]}


def test_new_backup_codes_need_two_factor_on(signed_in: APIClient) -> None:
    """There aren't any codes to replace without a device."""
    response = signed_in.post(CODES_URL, {"otp": "123456"}, format="json")
    assert response.json() == {"detail": mfa.NOT_ON}


def test_new_backup_codes_are_mailed_about(
    signed_in: APIClient,
    device: TotpDevice,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: object,
) -> None:
    """The account is told its backup codes were replaced."""
    with django_capture_on_commit_callbacks(execute=True):  # type: ignore[operator]
        signed_in.post(CODES_URL, {"otp": totp_code(device)}, format="json")
    assert [message.subject for message in mailoutbox] == ["CalDART: new backup codes"]


# -- turning it off ----------------------------------------------------------


def disable(client: APIClient, otp: str, password: str = DEFAULT_PASSWORD) -> ApiResponse:
    """Post the password and ``otp`` to turn two-factor sign-in off; the response."""
    return client.post(DISABLE_URL, {"current_password": password, "otp": otp}, format="json")


def test_turning_it_off_with_the_password_and_a_code(
    signed_in: APIClient, device: TotpDevice
) -> None:
    """The device is gone and the status reads off."""
    response = disable(signed_in, totp_code(device))
    assert response.status_code == 204
    assert signed_in.get(STATUS_URL).json()["enabled"] is False


def test_turning_it_off_refuses_a_wrong_password(signed_in: APIClient, device: TotpDevice) -> None:
    """The refusal names ``current_password``."""
    response = disable(signed_in, totp_code(device), password=WRONG_PASSWORD)
    assert response.json() == {"current_password": ["That is not your current password."]}


def test_turning_it_off_refuses_a_wrong_code(signed_in: APIClient, device: TotpDevice) -> None:
    """The refusal names ``otp``, and the device stays."""
    response = disable(signed_in, "000000")
    assert response.json() == {"otp": [mfa.CODE_REFUSED]}
    assert mfa.has_two_factor(device.user) is True


def test_a_required_role_cannot_turn_it_off(api_client: APIClient) -> None:
    """The server answers 403 with the sentence, whatever the body says."""
    treasurer = UserFactory(roles=[MEMBER, TREASURER])
    device = confirmed_device(treasurer)
    api_client.force_login(treasurer)
    response = disable(api_client, totp_code(device))
    assert response.status_code == 403
    assert response.json() == {"detail": mfa.REQUIRED_REFUSED}


def test_turning_it_off_is_mailed_about(
    signed_in: APIClient,
    device: TotpDevice,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: object,
) -> None:
    """The account is told, in case it was not its owner."""
    with django_capture_on_commit_callbacks(execute=True):  # type: ignore[operator]
        disable(signed_in, totp_code(device))
    assert [message.subject for message in mailoutbox] == ["CalDART: two-factor sign-in is off"]


def test_starting_needs_the_password(signed_in: APIClient) -> None:
    """A session left open on somebody's screen cannot attach a stranger's phone."""
    response = signed_in.post(ENROLL_URL, {"current_password": WRONG_PASSWORD}, format="json")
    assert response.json() == {"current_password": ["That is not your current password."]}


def test_turning_it_off_takes_the_sessions_mark_away(
    signed_in: APIClient, device: TotpDevice
) -> None:
    """A role granted later asks this session for the second factor again."""
    disable(signed_in, totp_code(device))
    assert mfa.VERIFIED_SESSION_KEY not in signed_in.session
