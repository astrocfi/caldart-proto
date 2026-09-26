"""Email verification: the signed link, what sends it, and the endpoints around it.

A new account, a member an administrator creates with a password, and every
change of address are mailed a link to ``/portal/verify-email``.  The link signs
the account and the address it was sent to, so a later change of address makes
every earlier link useless.  ``docs/developer/api-auth.rst`` describes the
endpoints and ``docs/user/getting-started.rst`` what a member sees.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import cast

import freezegun
import pytest
from django.core import mail, signing
from django.core.cache import cache
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone
from pytest_django import Settings
from pytest_django.fixtures import DjangoCaptureOnCommitCallbacks
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.services import (
    EMAIL_VERIFICATION_SALT,
    EmailVerificationError,
    build_email_verification_url,
    change_own_email,
    make_email_verification_token,
    send_email_verification,
    verify_email,
)
from apps.cms.models import SiteSettings
from apps.mail.models import EmailLog
from apps.mail.purposes import purpose_label
from apps.members.services import create_member
from tests.conftest import GOOD_PASSWORD, ME_URL, REGISTER_URL, audit_messages, register_payload
from tests.factories import DEFAULT_PASSWORD, UserFactory

pytestmark = pytest.mark.django_db

VERIFY_URL = "/api/v1/auth/email/verify"
RESEND_URL = "/api/v1/auth/email/resend"
CHANGE_EMAIL_URL = "/api/v1/auth/email/change"
USERS_URL = "/api/v1/admin/users"
MEMBERS_URL = "/api/v1/admin/members"

INVALID_LINK = "That verification link is invalid or has expired."

#: The ``SiteSettings`` defaults the ``site_settings`` fixture writes.
ORG_NAME = "The California DART Network"
CONTACT_EMAIL = "info@caldart.example.org"

type OnCommit = DjangoCaptureOnCommitCallbacks


@pytest.fixture
def verified(db: None) -> User:
    """A member whose address was verified a week ago."""
    user = UserFactory(
        email="verified@example.test", first_name="Vera", last_name="Quill", roles=["member"]
    )
    user.email_verified_at = timezone.now() - timedelta(days=7)
    user.save(update_fields=["email_verified_at"])
    return user


@pytest.fixture
def unverified(db: None) -> User:
    """A member who has never clicked a verification link."""
    return UserFactory(
        email="unverified@example.test", first_name="Uma", last_name="Pike", roles=["member"]
    )


@pytest.fixture
def signed_in(api_client: APIClient) -> Callable[[User], APIClient]:
    """Sign ``user`` in on the shared API client and return the client."""

    def sign_in(user: User) -> APIClient:
        api_client.force_login(user)
        return api_client

    return sign_in


@pytest.fixture
def clear_throttle_cache() -> None:
    """Empty the throttle counters, which live in the shared cache."""
    cache.clear()


def verification_mails() -> list[EmailMultiAlternatives]:
    """Every verification message in the outbox, oldest first."""
    return [
        cast(EmailMultiAlternatives, message)
        for message in mail.outbox
        if "verify your email address" in str(message.subject)
    ]


def token_from(message: EmailMultiAlternatives) -> str:
    """The ``token`` of the verification link in ``message``'s text body."""
    match = re.search(r"/portal/verify-email\?token=(\S+)", str(message.body))
    assert match, f"no verification link in:\n{message.body}"
    return match.group(1)


# --------------------------------------------------------------------------
# The token
# --------------------------------------------------------------------------
def test_a_fresh_token_verifies_the_account(unverified: User) -> None:
    """``verify_email`` returns the account the token names and stamps it verified."""
    user = verify_email(make_email_verification_token(unverified))

    unverified.refresh_from_db()
    assert user.pk == unverified.pk
    assert unverified.email_verified is True


def test_verifying_records_the_audit_event(
    unverified: User, audit_log: pytest.LogCaptureFixture
) -> None:
    """A successful verification writes one ``account.email_verified`` audit line."""
    verify_email(make_email_verification_token(unverified))

    assert audit_messages(audit_log) == [
        f"action=account.email_verified actor={unverified.pk} target={unverified.pk}"
    ]


def test_a_second_click_on_the_same_link_changes_nothing(unverified: User) -> None:
    """Using a link twice succeeds both times and keeps the first verification time."""
    token = make_email_verification_token(unverified)
    verify_email(token)
    unverified.refresh_from_db()
    first = unverified.email_verified_at

    verify_email(token)

    unverified.refresh_from_db()
    assert unverified.email_verified_at == first


def test_a_tampered_token_is_refused(unverified: User) -> None:
    """A token whose signature does not match is refused with the one message."""
    token = make_email_verification_token(unverified)

    with pytest.raises(EmailVerificationError, match=INVALID_LINK):
        verify_email(token[:-2] + "xx")


def test_a_token_signed_under_another_salt_is_refused(unverified: User) -> None:
    """A payload signed for a different purpose is not a verification token."""
    token = signing.dumps({"user": unverified.pk, "email": unverified.email}, salt="other")

    with pytest.raises(EmailVerificationError, match=INVALID_LINK):
        verify_email(token)


def test_an_expired_token_is_refused(unverified: User, settings: Settings) -> None:
    """A token older than ``EMAIL_VERIFICATION_TIMEOUT`` seconds is refused."""
    settings.EMAIL_VERIFICATION_TIMEOUT = 3600
    issued = timezone.now()
    with freezegun.freeze_time(issued):
        token = make_email_verification_token(unverified)

    with (
        freezegun.freeze_time(issued + timedelta(seconds=3601)),
        pytest.raises(EmailVerificationError, match=INVALID_LINK),
    ):
        verify_email(token)


def test_a_token_inside_the_timeout_is_accepted(unverified: User, settings: Settings) -> None:
    """A token used just before the timeout runs out still verifies."""
    settings.EMAIL_VERIFICATION_TIMEOUT = 3600
    issued = timezone.now()
    with freezegun.freeze_time(issued):
        token = make_email_verification_token(unverified)

    with freezegun.freeze_time(issued + timedelta(seconds=3500)):
        verify_email(token)

    unverified.refresh_from_db()
    assert unverified.email_verified is True


def test_a_token_for_an_inactive_account_is_refused(unverified: User) -> None:
    """A deactivated account cannot be verified."""
    token = make_email_verification_token(unverified)
    unverified.is_active = False
    unverified.save(update_fields=["is_active"])

    with pytest.raises(EmailVerificationError, match=INVALID_LINK):
        verify_email(token)


def test_a_token_for_a_deleted_account_is_refused(unverified: User) -> None:
    """A token naming an account that no longer exists is refused."""
    token = make_email_verification_token(unverified)
    unverified.delete()

    with pytest.raises(EmailVerificationError, match=INVALID_LINK):
        verify_email(token)


def test_a_token_for_a_previous_address_is_refused(unverified: User) -> None:
    """Changing the address makes every link sent to the old one useless."""
    token = make_email_verification_token(unverified)
    unverified.email = "moved@example.test"
    unverified.save(update_fields=["email"])

    with pytest.raises(EmailVerificationError, match=INVALID_LINK):
        verify_email(token)

    unverified.refresh_from_db()
    assert unverified.email_verified is False


def test_a_token_survives_a_change_of_case_only(unverified: User) -> None:
    """The token signs the normalized address, so a change of case keeps it valid."""
    token = make_email_verification_token(unverified)
    unverified.email = "Unverified@Example.test"
    unverified.save(update_fields=["email"])

    verify_email(token)

    unverified.refresh_from_db()
    assert unverified.email_verified is True


def test_a_malformed_payload_is_refused(unverified: User) -> None:
    """A correctly signed value that is not the expected payload is still refused."""
    token = signing.dumps(["not", "a", "dict"], salt=EMAIL_VERIFICATION_SALT)

    with pytest.raises(EmailVerificationError, match=INVALID_LINK):
        verify_email(token)


def test_the_link_is_built_from_site_url(unverified: User, settings: Settings) -> None:
    """The link points at the portal's verify page on ``SITE_URL``."""
    settings.SITE_URL = "https://caldart.example.org/"

    url = build_email_verification_url(unverified)

    assert url.startswith("https://caldart.example.org/portal/verify-email?token=")


# --------------------------------------------------------------------------
# The message
# --------------------------------------------------------------------------
def test_the_message_goes_to_the_account_address(
    unverified: User, site_settings: SiteSettings
) -> None:
    """The verification message is addressed to the account's email."""
    send_email_verification(unverified)

    assert mail.outbox[0].to == ["unverified@example.test"]


def test_the_subject_names_the_organization(unverified: User, site_settings: SiteSettings) -> None:
    """The subject is the organization's name, then "verify your email address"."""
    send_email_verification(unverified)

    assert mail.outbox[0].subject == f"{ORG_NAME}: verify your email address"


def test_the_text_body_greets_the_member_by_first_name(
    unverified: User, site_settings: SiteSettings
) -> None:
    """The text body greets the member by first name."""
    send_email_verification(unverified)

    assert "Hello Uma," in mail.outbox[0].body


def test_the_text_body_carries_a_working_link(
    unverified: User, site_settings: SiteSettings
) -> None:
    """The link in the text body verifies the account it was sent to."""
    send_email_verification(unverified)

    verify_email(token_from(verification_mails()[0]))

    unverified.refresh_from_db()
    assert unverified.email_verified is True


def test_the_text_body_states_how_long_the_link_lasts(
    unverified: User, site_settings: SiteSettings
) -> None:
    """The text body states the link's lifetime in whole days."""
    send_email_verification(unverified)

    assert "The link expires in 3 days." in mail.outbox[0].body


def test_the_text_body_gives_the_contact_address(
    unverified: User, site_settings: SiteSettings
) -> None:
    """The text body gives the configured contact address."""
    send_email_verification(unverified)

    assert f"write to {CONTACT_EMAIL}." in mail.outbox[0].body


def test_the_html_alternative_carries_the_link(
    unverified: User, site_settings: SiteSettings
) -> None:
    """The HTML alternative carries the same verification link."""
    send_email_verification(unverified)
    html, _mimetype = verification_mails()[0].alternatives[0]

    assert "/portal/verify-email?token=" in str(html)


def test_the_send_is_logged_as_an_email_verification(
    unverified: User, site_settings: SiteSettings
) -> None:
    """The email log records the send under the ``email_verification`` purpose."""
    send_email_verification(unverified)

    row = EmailLog.objects.get()
    assert row.purpose == "email_verification"
    assert row.user_id == unverified.pk


def test_the_purpose_reads_as_email_verification() -> None:
    """The email log shows the purpose as "Email verification"."""
    assert purpose_label("email_verification") == "Email verification"


# --------------------------------------------------------------------------
# What sends it
# --------------------------------------------------------------------------
def test_registration_sends_the_message(
    api_client: APIClient, site_settings: SiteSettings, django_capture_on_commit_callbacks: OnCommit
) -> None:
    """Registering mails a verification message to the new address once it commits."""
    with django_capture_on_commit_callbacks(execute=True):
        api_client.post(REGISTER_URL, register_payload())

    assert [m.to for m in verification_mails()] == [["new.member@example.test"]]


def test_registration_answers_unverified(api_client: APIClient) -> None:
    """The payload a new account receives says its address is unverified."""
    response = api_client.post(REGISTER_URL, register_payload())

    assert response.json()["email_verified"] is False


def test_the_user_payload_says_verified(api_client: APIClient, verified: User) -> None:
    """``/auth/me`` answers ``email_verified: true`` for a verified account."""
    api_client.force_login(verified)

    assert api_client.get(ME_URL).json()["email_verified"] is True


def test_creating_a_member_with_a_password_sends_the_message(
    account_admin: User, site_settings: SiteSettings, django_capture_on_commit_callbacks: OnCommit
) -> None:
    """A member created with a password is mailed a verification message."""
    with django_capture_on_commit_callbacks(execute=True):
        create_member(account_admin, email="walkin@example.test", password=GOOD_PASSWORD)

    assert [m.to for m in verification_mails()] == [["walkin@example.test"]]


def test_creating_a_member_without_a_password_sends_no_verification(
    account_admin: User, site_settings: SiteSettings, django_capture_on_commit_callbacks: OnCommit
) -> None:
    """A member created without a password is sent the invitation alone."""
    with django_capture_on_commit_callbacks(execute=True):
        create_member(account_admin, email="invitee@example.test")

    assert verification_mails() == []


def test_a_user_administrator_changing_an_address_unverifies_it(
    user_admin: User,
    verified: User,
    signed_in: Callable[[User], APIClient],
    site_settings: SiteSettings,
    django_capture_on_commit_callbacks: OnCommit,
) -> None:
    """``PATCH /admin/users/{id}`` with a new address marks it unverified and mails it."""
    client = signed_in(user_admin)
    with django_capture_on_commit_callbacks(execute=True):
        response = client.patch(
            f"{USERS_URL}/{verified.pk}", {"email": "fresh@example.test"}, format="json"
        )

    assert response.json()["email_verified_at"] is None
    assert [m.to for m in verification_mails()] == [["fresh@example.test"]]


def test_an_account_administrator_changing_an_address_unverifies_it(
    account_admin: User,
    verified: User,
    signed_in: Callable[[User], APIClient],
    site_settings: SiteSettings,
    django_capture_on_commit_callbacks: OnCommit,
) -> None:
    """An account administrator's change of address marks it unverified and mails it."""
    client = signed_in(account_admin)
    with django_capture_on_commit_callbacks(execute=True):
        response = client.patch(
            f"{MEMBERS_URL}/{verified.pk}", {"email": "fresh@example.test"}, format="json"
        )

    assert response.status_code == 200
    verified.refresh_from_db()
    assert verified.email_verified is False
    assert [m.to for m in verification_mails()] == [["fresh@example.test"]]


def test_changing_your_own_address_unverifies_it(
    verified: User, site_settings: SiteSettings, django_capture_on_commit_callbacks: OnCommit
) -> None:
    """``change_own_email`` marks the new address unverified and mails it."""
    with django_capture_on_commit_callbacks(execute=True):
        change_own_email(verified, email="fresh@example.test")

    verified.refresh_from_db()
    assert verified.email_verified is False
    assert [m.to for m in verification_mails()] == [["fresh@example.test"]]


def test_a_change_of_case_only_keeps_the_address_verified(
    user_admin: User,
    verified: User,
    signed_in: Callable[[User], APIClient],
    django_capture_on_commit_callbacks: OnCommit,
) -> None:
    """Resending the same address in another case is not a change of address."""
    client = signed_in(user_admin)
    with django_capture_on_commit_callbacks(execute=True):
        client.patch(
            f"{USERS_URL}/{verified.pk}", {"email": "VERIFIED@example.test"}, format="json"
        )

    verified.refresh_from_db()
    assert verified.email_verified is True
    assert verification_mails() == []


def test_a_change_of_name_keeps_the_address_verified(
    user_admin: User,
    verified: User,
    signed_in: Callable[[User], APIClient],
    django_capture_on_commit_callbacks: OnCommit,
) -> None:
    """Editing a name leaves the verification alone and mails nothing."""
    client = signed_in(user_admin)
    with django_capture_on_commit_callbacks(execute=True):
        client.patch(f"{USERS_URL}/{verified.pk}", {"first_name": "Veronica"}, format="json")

    verified.refresh_from_db()
    assert verified.email_verified is True
    assert verification_mails() == []


# --------------------------------------------------------------------------
# POST /auth/email/verify
# --------------------------------------------------------------------------
def test_the_verify_endpoint_answers_the_verified_address(
    api_client: APIClient, unverified: User
) -> None:
    """An anonymous caller with a good token gets 200 and the address it verified."""
    token = make_email_verification_token(unverified)

    response = api_client.post(VERIFY_URL, {"token": token})

    assert response.status_code == 200
    assert response.json() == {"email": "unverified@example.test"}


def test_the_verify_endpoint_refuses_a_bad_token(api_client: APIClient) -> None:
    """A token that does not verify is a 400 under ``token``."""
    response = api_client.post(VERIFY_URL, {"token": "nonsense"})

    assert response.status_code == 400
    assert response.json() == {"token": [INVALID_LINK]}


def test_the_verify_endpoint_is_throttled_when_a_rate_is_configured(
    api_client: APIClient, settings: Settings, clear_throttle_cache: None
) -> None:
    """Past the ``auth_verify`` rate the endpoint answers 429."""
    settings.AUTH_THROTTLE_RATES = {"auth_verify": "2/hour"}
    statuses = [api_client.post(VERIFY_URL, {"token": "x"}).status_code for _ in range(3)]

    assert statuses == [400, 400, 429]


# --------------------------------------------------------------------------
# POST /auth/email/resend
# --------------------------------------------------------------------------
def test_resend_mails_an_unverified_address(
    unverified: User, signed_in: Callable[[User], APIClient], site_settings: SiteSettings
) -> None:
    """An unverified member asking again gets 202 and a fresh message."""
    response = signed_in(unverified).post(RESEND_URL)

    assert response.status_code == 202
    assert response.json() == {"detail": "Verification message sent to unverified@example.test."}
    assert [m.to for m in verification_mails()] == [["unverified@example.test"]]


def test_resend_refuses_a_verified_address(
    verified: User, signed_in: Callable[[User], APIClient]
) -> None:
    """A member whose address is already verified gets 400 and no message."""
    response = signed_in(verified).post(RESEND_URL)

    assert response.status_code == 400
    assert response.json() == {"detail": "Your email address is already verified."}
    assert mail.outbox == []


def test_resend_needs_a_session(api_client: APIClient) -> None:
    """An anonymous caller is answered 401."""
    assert api_client.post(RESEND_URL).status_code == 401


def test_resend_is_throttled_when_a_rate_is_configured(
    unverified: User,
    signed_in: Callable[[User], APIClient],
    settings: Settings,
    site_settings: SiteSettings,
    clear_throttle_cache: None,
) -> None:
    """Past the ``auth_verify_resend`` rate the endpoint answers 429."""
    settings.AUTH_THROTTLE_RATES = {"auth_verify_resend": "2/hour"}
    client = signed_in(unverified)
    statuses = [client.post(RESEND_URL).status_code for _ in range(3)]

    assert statuses == [202, 202, 429]


# --------------------------------------------------------------------------
# POST /auth/email/change
# --------------------------------------------------------------------------
def test_change_answers_the_user_payload(
    verified: User, signed_in: Callable[[User], APIClient]
) -> None:
    """A good change answers 200 with the payload carrying the new, unverified address."""
    response = signed_in(verified).post(
        CHANGE_EMAIL_URL,
        {"email": "fresh@example.test", "current_password": DEFAULT_PASSWORD},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "fresh@example.test"
    assert body["email_verified"] is False


def test_change_keeps_the_session(verified: User, signed_in: Callable[[User], APIClient]) -> None:
    """The member is still signed in after changing the address they sign in with."""
    client = signed_in(verified)
    client.post(
        CHANGE_EMAIL_URL, {"email": "fresh@example.test", "current_password": DEFAULT_PASSWORD}
    )

    assert client.get(ME_URL).json()["email"] == "fresh@example.test"


def test_change_refuses_a_wrong_password(
    verified: User, signed_in: Callable[[User], APIClient]
) -> None:
    """A wrong current password is a 400 under ``current_password``, checked first."""
    response = signed_in(verified).post(
        CHANGE_EMAIL_URL, {"email": verified.email, "current_password": "wrong"}
    )

    assert response.status_code == 400
    assert response.json() == {"current_password": ["That is not your current password."]}


def test_change_refuses_the_current_address(
    verified: User, signed_in: Callable[[User], APIClient]
) -> None:
    """The address the account already has, in any case, is a 400 under ``email``."""
    response = signed_in(verified).post(
        CHANGE_EMAIL_URL,
        {"email": "Verified@Example.test", "current_password": DEFAULT_PASSWORD},
    )

    assert response.status_code == 400
    assert response.json() == {"email": ["That is already your email address."]}


def test_change_refuses_an_address_another_account_uses(
    verified: User, unverified: User, signed_in: Callable[[User], APIClient]
) -> None:
    """Another account's address, in any case, is a 400 under ``email``."""
    response = signed_in(verified).post(
        CHANGE_EMAIL_URL,
        {"email": "UNVERIFIED@example.test", "current_password": DEFAULT_PASSWORD},
    )

    assert response.status_code == 400
    assert response.json() == {"email": ["Another account already uses that email address."]}


def test_change_records_the_audit_line(
    verified: User, signed_in: Callable[[User], APIClient], audit_log: pytest.LogCaptureFixture
) -> None:
    """The change is recorded as the member's own ``account.update`` of ``email``."""
    signed_in(verified).post(
        CHANGE_EMAIL_URL, {"email": "fresh@example.test", "current_password": DEFAULT_PASSWORD}
    )

    assert audit_messages(audit_log, logging.INFO) == [
        f"action=account.update actor={verified.pk} target={verified.pk} fields=email"
    ]


def test_change_needs_a_session(api_client: APIClient) -> None:
    """An anonymous caller is answered 401."""
    response = api_client.post(
        CHANGE_EMAIL_URL, {"email": "x@example.test", "current_password": "x"}
    )

    assert response.status_code == 401


# --------------------------------------------------------------------------
# The administrator resend, send-email-verification
# --------------------------------------------------------------------------
def admin_resend_url(user: User) -> str:
    """``/admin/users/{id}/send-email-verification`` for ``user``."""
    return f"{USERS_URL}/{user.pk}/send-email-verification"


def test_admin_resend_mails_an_unverified_address(
    user_admin: User,
    unverified: User,
    signed_in: Callable[[User], APIClient],
    site_settings: SiteSettings,
) -> None:
    """A user administrator's resend answers 202 and mails the member."""
    response = signed_in(user_admin).post(admin_resend_url(unverified))

    assert response.status_code == 202
    assert response.json() == {"detail": "Verification message sent to unverified@example.test."}
    assert [m.to for m in verification_mails()] == [["unverified@example.test"]]


def test_admin_resend_records_the_audit_line(
    user_admin: User,
    unverified: User,
    signed_in: Callable[[User], APIClient],
    site_settings: SiteSettings,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """The administrator's resend is recorded as ``email_verification.admin_sent``."""
    signed_in(user_admin).post(admin_resend_url(unverified))

    assert audit_messages(audit_log) == [
        f"action=email_verification.admin_sent actor={user_admin.pk} target={unverified.pk}"
    ]


def test_admin_resend_refuses_a_verified_address(
    user_admin: User, verified: User, signed_in: Callable[[User], APIClient]
) -> None:
    """An address that is already verified is a 400 and nothing is mailed."""
    response = signed_in(user_admin).post(admin_resend_url(verified))

    assert response.status_code == 400
    assert response.json() == {"detail": "That address is already verified."}
    assert mail.outbox == []


def test_admin_resend_refuses_a_deactivated_account(
    user_admin: User, unverified: User, signed_in: Callable[[User], APIClient]
) -> None:
    """A deactivated account is a 400: its link could never be used."""
    unverified.is_active = False
    unverified.save(update_fields=["is_active"])

    response = signed_in(user_admin).post(admin_resend_url(unverified))

    assert response.status_code == 400
    assert response.json() == {
        "detail": "That account is deactivated, so no verification message was sent."
    }


def test_admin_resend_answers_404_for_an_unknown_account(
    user_admin: User, signed_in: Callable[[User], APIClient]
) -> None:
    """An id no account has is a 404."""
    response = signed_in(user_admin).post(f"{USERS_URL}/99999/send-email-verification")

    assert response.status_code == 404


# --------------------------------------------------------------------------
# The administrator payloads
# --------------------------------------------------------------------------
def test_the_admin_user_payload_carries_the_verification_time(
    user_admin: User, verified: User, signed_in: Callable[[User], APIClient]
) -> None:
    """``GET /admin/users/{id}`` carries ``email_verified_at`` as an ISO datetime."""
    body = signed_in(user_admin).get(f"{USERS_URL}/{verified.pk}").json()

    assert datetime.fromisoformat(body["email_verified_at"]) == verified.email_verified_at


def test_the_member_record_carries_the_verification_time(
    account_admin: User, unverified: User, signed_in: Callable[[User], APIClient]
) -> None:
    """``GET /admin/members/{id}`` carries ``email_verified_at``, null when unverified."""
    body = signed_in(account_admin).get(f"{MEMBERS_URL}/{unverified.pk}").json()

    assert body["email_verified_at"] is None
