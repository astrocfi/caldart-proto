"""Signing in with a second factor: the password step, the code step, and enrolling.

``docs/developer/api-auth.rst`` describes the flow: a right password for an account
that needs a second factor answers ``{"mfa": "verify"}`` or ``{"mfa": "enroll"}`` and
starts no session; the code step, bound to that browser's session and to the password,
finishes it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.core.mail import EmailMessage
from rest_framework.test import APIClient

from apps.accounts import mfa
from apps.accounts.models import AccountKind, TotpDevice, User
from apps.accounts.roles import MEMBER, USER_ADMIN
from tests.conftest import LOGIN_URL, ME_URL, totp_code
from tests.factories import DEFAULT_PASSWORD, UserFactory, confirmed_device

if TYPE_CHECKING:
    from rest_framework.response import _MonkeyPatchedResponse as ApiResponse

pytestmark = pytest.mark.django_db

MFA_URL = "/api/v1/auth/login/mfa"
ENROLL_URL = "/api/v1/auth/login/mfa/enroll"
ENROLL_CONFIRM_URL = "/api/v1/auth/login/mfa/enroll/confirm"
REACTIVATE_URL = "/api/v1/auth/reactivate"
EXPIRED = {
    "detail": "Your sign-in has expired. Enter your email address and password again.",
    "code": "mfa_expired",
}
WRONG_CODE = {"otp": [mfa.CODE_REFUSED]}
WRONG_CREDENTIALS = {"detail": "Incorrect email address or password."}


@pytest.fixture
def admin() -> User:
    """A user administrator, whose role requires a second factor, with no device yet."""
    return UserFactory(email="ursula.admin@example.test", roles=[MEMBER, USER_ADMIN])


@pytest.fixture
def device(admin: User) -> TotpDevice:
    """``admin``'s confirmed authenticator device."""
    return confirmed_device(admin)


def password_step(client: APIClient, user: User, password: str = DEFAULT_PASSWORD) -> ApiResponse:
    """Post ``user``'s address and ``password`` to the sign-in."""
    return client.post(LOGIN_URL, {"email": user.email, "password": password}, format="json")


def code_step(client: APIClient, otp: str) -> ApiResponse:
    """Post ``otp`` to the code step."""
    return client.post(MFA_URL, {"otp": otp}, format="json")


# -- the password step -------------------------------------------------------


def test_a_required_role_without_a_device_is_asked_to_enroll(
    api_client: APIClient, admin: User
) -> None:
    """The answer names the next step and nothing about the account."""
    assert password_step(api_client, admin).json() == {"mfa": "enroll"}


def test_an_account_with_a_device_is_asked_for_a_code(
    api_client: APIClient, device: TotpDevice
) -> None:
    """The answer names the next step and nothing about the account."""
    assert password_step(api_client, device.user).json() == {"mfa": "verify"}


def test_the_password_step_starts_no_session(api_client: APIClient, device: TotpDevice) -> None:
    """Until the code step, the browser is not signed in."""
    password_step(api_client, device.user)
    assert api_client.get(ME_URL).status_code == 401


def test_a_member_without_two_factor_signs_in_with_the_password(
    api_client: APIClient, member: User
) -> None:
    """Nothing changes for an account that needs no second factor."""
    assert password_step(api_client, member).json()["email"] == member.email


def test_a_voluntary_device_is_asked_for_a_code(api_client: APIClient, member: User) -> None:
    """A member who turned two-factor sign-in on is asked for a code too."""
    confirmed_device(member)
    assert password_step(api_client, member).json() == {"mfa": "verify"}


def test_a_superuser_is_asked_to_enroll(api_client: APIClient) -> None:
    """The superuser flag requires a second factor like the system administrator role."""
    root = UserFactory(is_superuser=True, is_staff=True)
    assert password_step(api_client, root).json() == {"mfa": "enroll"}


def test_a_wrong_password_reads_as_for_an_unknown_address(
    api_client: APIClient, device: TotpDevice
) -> None:
    """A wrong password for a two-factor account says nothing more than for nobody."""
    wrong = password_step(api_client, device.user, "not-the-password").json()
    unknown = api_client.post(
        LOGIN_URL, {"email": "nobody@example.test", "password": "x"}, format="json"
    ).json()
    assert wrong == unknown


# -- the code step -----------------------------------------------------------


def test_a_right_code_signs_in(api_client: APIClient, device: TotpDevice) -> None:
    """The answer is the user payload, and the session is signed in."""
    password_step(api_client, device.user)
    assert code_step(api_client, totp_code(device)).json()["email"] == device.user.email
    assert api_client.get(ME_URL).status_code == 200


def test_a_right_code_marks_the_session(api_client: APIClient, device: TotpDevice) -> None:
    """The mark names the account the code was for."""
    password_step(api_client, device.user)
    code_step(api_client, totp_code(device))
    assert mfa.session_passed(api_client.session, device.user) is True


def test_signing_in_changes_the_session_key(api_client: APIClient, device: TotpDevice) -> None:
    """The pending session's key is not the signed-in one, so it cannot be fixed."""
    password_step(api_client, device.user)
    pending_key = api_client.cookies["sessionid"].value
    code_step(api_client, totp_code(device))
    assert api_client.cookies["sessionid"].value != pending_key


def test_a_backup_code_signs_in(api_client: APIClient, device: TotpDevice) -> None:
    """A backup code is accepted at the code step."""
    code = mfa.replace_recovery_codes(device.user)[0]
    password_step(api_client, device.user)
    assert code_step(api_client, code).status_code == 200


def test_a_wrong_code_is_refused(api_client: APIClient, device: TotpDevice) -> None:
    """The refusal names the ``otp`` field."""
    password_step(api_client, device.user)
    assert code_step(api_client, "000000").json() == WRONG_CODE


def test_a_wrong_code_starts_no_session(api_client: APIClient, device: TotpDevice) -> None:
    """Nobody is signed in after a refused code."""
    password_step(api_client, device.user)
    code_step(api_client, "000000")
    assert api_client.get(ME_URL).status_code == 401


def test_the_fifth_wrong_code_ends_the_sign_in(api_client: APIClient, device: TotpDevice) -> None:
    """After five wrong codes even the right one is refused: start with the password."""
    password_step(api_client, device.user)
    answers = [code_step(api_client, "000000").json() for _ in range(5)]
    assert answers[-1] == EXPIRED
    assert code_step(api_client, totp_code(device)).json() == EXPIRED


def test_a_used_code_is_refused_at_the_next_sign_in(
    api_client: APIClient, device: TotpDevice
) -> None:
    """A code that signed somebody in cannot sign anybody in again."""
    code = totp_code(device)
    password_step(api_client, device.user)
    code_step(api_client, code)
    other = APIClient()
    password_step(other, device.user)
    assert code_step(other, code).json() == WRONG_CODE


def test_the_code_step_needs_the_password_steps_session(
    api_client: APIClient, device: TotpDevice
) -> None:
    """A code posted from another browser finishes nothing."""
    password_step(api_client, device.user)
    assert code_step(APIClient(), totp_code(device)).json() == EXPIRED


def test_the_code_step_without_a_password_step_is_refused(
    api_client: APIClient, device: TotpDevice
) -> None:
    """There is no sign-in to finish."""
    assert code_step(api_client, totp_code(device)).json() == EXPIRED


def test_a_password_change_voids_the_waiting_sign_in(
    api_client: APIClient, device: TotpDevice
) -> None:
    """A sign-in started with the old password cannot be finished."""
    password_step(api_client, device.user)
    device.user.set_password("A-new-password-for-2027")
    device.user.save()
    assert code_step(api_client, totp_code(device)).json() == EXPIRED


def test_a_waiting_sign_in_expires(api_client: APIClient, device: TotpDevice) -> None:
    """Five minutes after the password step the code is no longer taken."""
    password_step(api_client, device.user)
    session = api_client.session
    pending = session[mfa.PENDING_SESSION_KEY]
    session[mfa.PENDING_SESSION_KEY] = {**pending, "started": pending["started"] - 301}
    session.save()
    assert code_step(api_client, totp_code(device)).json() == EXPIRED


def test_a_missing_code_is_asked_for(api_client: APIClient, device: TotpDevice) -> None:
    """An empty box says what to enter."""
    password_step(api_client, device.user)
    response = api_client.post(MFA_URL, {"otp": ""}, format="json")
    assert response.json() == {"otp": [mfa.CODE_MISSING]}


def test_the_code_step_refuses_a_sign_in_that_must_enroll(
    api_client: APIClient, admin: User
) -> None:
    """An account with no device has no code to give."""
    password_step(api_client, admin)
    assert code_step(api_client, "123456").json() == EXPIRED


# -- enrolling while signing in ----------------------------------------------


def start_enrolling(client: APIClient, user: User) -> str:
    """Pass the password step for ``user`` and start enrollment; the secret shown."""
    password_step(client, user)
    secret: str = client.post(ENROLL_URL).json()["secret"]
    return secret


def test_enrolling_answers_what_the_app_needs(api_client: APIClient, admin: User) -> None:
    """The secret, its ``otpauth://`` address, and the QR code."""
    password_step(api_client, admin)
    body = api_client.post(ENROLL_URL).json()
    assert sorted(body) == ["otpauth_uri", "qr_svg", "secret"]


def test_confirming_enrollment_signs_in_and_shows_the_codes(
    api_client: APIClient, admin: User
) -> None:
    """The answer is the user and ten backup codes, and the session is signed in."""
    secret = start_enrolling(api_client, admin)
    body = api_client.post(ENROLL_CONFIRM_URL, {"otp": totp_code(secret)}, format="json").json()
    assert body["user"]["email"] == admin.email
    assert len(body["recovery_codes"]) == 10
    assert api_client.get(ME_URL).status_code == 200


def test_confirming_enrollment_marks_the_session(api_client: APIClient, admin: User) -> None:
    """Enrolling counts as passing the second factor."""
    secret = start_enrolling(api_client, admin)
    api_client.post(ENROLL_CONFIRM_URL, {"otp": totp_code(secret)}, format="json")
    assert mfa.session_passed(api_client.session, admin) is True


def test_a_wrong_enrollment_code_is_refused(api_client: APIClient, admin: User) -> None:
    """No device is stored and nobody is signed in."""
    start_enrolling(api_client, admin)
    response = api_client.post(ENROLL_CONFIRM_URL, {"otp": "000000"}, format="json")
    assert response.json() == WRONG_CODE
    assert api_client.get(ME_URL).status_code == 401


def test_enrolling_is_refused_once_a_device_is_confirmed(
    api_client: APIClient, device: TotpDevice
) -> None:
    """A password alone can never replace a working device."""
    password_step(api_client, device.user)
    assert api_client.post(ENROLL_URL).json() == EXPIRED
    assert TotpDevice.objects.get(user=device.user).secret == device.secret


def test_enrolling_needs_a_waiting_sign_in(api_client: APIClient) -> None:
    """Nobody can enroll a device without having passed the password step."""
    assert api_client.post(ENROLL_URL).json() == EXPIRED


def test_confirming_without_starting_is_refused(api_client: APIClient, admin: User) -> None:
    """The enrollment step must come first."""
    password_step(api_client, admin)
    response = api_client.post(ENROLL_CONFIRM_URL, {"otp": "123456"}, format="json")
    assert response.json() == EXPIRED


def test_enrolling_at_sign_in_mails_the_account(
    api_client: APIClient,
    admin: User,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: object,
) -> None:
    """Turning two-factor sign-in on is announced to the address."""
    secret = start_enrolling(api_client, admin)
    with django_capture_on_commit_callbacks(execute=True):  # type: ignore[operator]
        api_client.post(ENROLL_CONFIRM_URL, {"otp": totp_code(secret)}, format="json")
    assert [message.to for message in mailoutbox] == [[admin.email]]


def test_enrolling_in_another_browser_does_not_break_this_one(
    api_client: APIClient, admin: User
) -> None:
    """A second sign-in at the enroll step cannot replace the secret this one confirms."""
    secret = start_enrolling(api_client, admin)
    start_enrolling(APIClient(), admin)
    response = api_client.post(ENROLL_CONFIRM_URL, {"otp": totp_code(secret)}, format="json")
    assert response.status_code == 200


# -- other ways in -----------------------------------------------------------


@pytest.fixture
def deactivated_admin() -> TotpDevice:
    """A deactivated user administrator's confirmed device."""
    return confirmed_device(UserFactory(roles=[MEMBER, USER_ADMIN], is_active=False))


def reactivate_step(client: APIClient, user: User) -> ApiResponse:
    """Post ``user``'s address and password to reactivate."""
    return client.post(
        REACTIVATE_URL, {"email": user.email, "password": DEFAULT_PASSWORD}, format="json"
    )


def test_reactivating_an_account_that_needs_a_code_asks_for_it(
    api_client: APIClient, deactivated_admin: TotpDevice
) -> None:
    """Reactivation signs in the one way every endpoint does."""
    assert reactivate_step(api_client, deactivated_admin.user).json() == {"mfa": "verify"}


def test_the_password_alone_does_not_reactivate(
    api_client: APIClient, deactivated_admin: TotpDevice
) -> None:
    """The account stays deactivated until the second factor is given."""
    reactivate_step(api_client, deactivated_admin.user)
    deactivated_admin.user.refresh_from_db()
    assert deactivated_admin.user.is_active is False


def test_the_code_reactivates_and_signs_in(
    api_client: APIClient, deactivated_admin: TotpDevice
) -> None:
    """A right code brings the account back and signs it in."""
    reactivate_step(api_client, deactivated_admin.user)
    code_step(api_client, totp_code(deactivated_admin))
    deactivated_admin.user.refresh_from_db()
    assert deactivated_admin.user.is_active is True
    assert api_client.get(ME_URL).status_code == 200


def test_a_sign_in_cannot_finish_a_deactivated_account(
    api_client: APIClient, deactivated_admin: TotpDevice
) -> None:
    """Only a pending sign-in that reactivation started may name a deactivated account."""
    password_step(api_client, deactivated_admin.user)
    assert code_step(api_client, totp_code(deactivated_admin)).status_code == 400


def test_a_block_set_before_the_code_keeps_the_account_closed(
    api_client: APIClient, deactivated_admin: TotpDevice
) -> None:
    """A user administrator's block wins over a reactivation waiting for its code."""
    reactivate_step(api_client, deactivated_admin.user)
    User.objects.filter(pk=deactivated_admin.user.pk).update(reactivation_blocked=True)
    code_step(api_client, totp_code(deactivated_admin))
    deactivated_admin.user.refresh_from_db()
    assert deactivated_admin.user.is_active is False


def test_a_blocked_account_is_refused_before_any_code(api_client: APIClient) -> None:
    """The closed answer comes first, as for an account with no second factor."""
    admin = UserFactory(roles=[MEMBER, USER_ADMIN], is_active=False, reactivation_blocked=True)
    confirmed_device(admin)
    assert reactivate_step(api_client, admin).status_code == 403


def test_a_donor_never_reaches_the_code_step(api_client: APIClient) -> None:
    """A donor is refused at the password, however it is set up."""
    donor = UserFactory(kind=AccountKind.DONOR)
    confirmed_device(donor)
    assert password_step(api_client, donor).json() == WRONG_CREDENTIALS


def test_an_unverified_address_may_finish_signing_in(api_client: APIClient) -> None:
    """The code steps are open to a session the verification gate holds back."""
    admin = UserFactory(roles=[MEMBER, USER_ADMIN], email_verified_at=None)
    device = confirmed_device(admin)
    password_step(api_client, admin)
    assert code_step(api_client, totp_code(device)).status_code == 200


# -- the session key ---------------------------------------------------------


def test_the_password_step_changes_the_session_key(
    api_client: APIClient, device: TotpDevice
) -> None:
    """A key planted in the browser before the password does not carry the sign-in."""
    api_client.get("/api/v1/auth/csrf")
    api_client.session.save()
    planted = api_client.session.session_key
    password_step(api_client, device.user)
    assert api_client.cookies["sessionid"].value != planted


def test_a_planted_key_cannot_finish_the_sign_in(api_client: APIClient, device: TotpDevice) -> None:
    """Whoever holds the key from before the password step cannot give the code."""
    session = api_client.session
    session["planted"] = True
    session.save()
    planted = session.session_key
    assert planted is not None
    password_step(api_client, device.user)
    attacker = APIClient()
    attacker.cookies["sessionid"] = planted
    assert code_step(attacker, totp_code(device)).json() == EXPIRED


def test_a_planted_key_cannot_enroll_a_device(api_client: APIClient, admin: User) -> None:
    """Nor can it set up its own phone on the account."""
    session = api_client.session
    session["planted"] = True
    session.save()
    planted = session.session_key
    assert planted is not None
    password_step(api_client, admin)
    attacker = APIClient()
    attacker.cookies["sessionid"] = planted
    assert attacker.post(ENROLL_URL).json() == EXPIRED
