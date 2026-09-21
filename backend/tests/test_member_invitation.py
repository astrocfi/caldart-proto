"""The "set your password" email an administrator-created account receives.

``POST /admin/members`` with no password gives the account an unusable password
and mails an invitation.  The link is the same password-reset link
``/auth/password/reset/confirm`` accepts, so the two are tested together here.
"""

from __future__ import annotations

import re
from typing import cast

import pytest
from django.core import mail
from django.core.mail import EmailMultiAlternatives
from django.test import override_settings
from pytest_django.fixtures import DjangoCaptureOnCommitCallbacks
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.services import send_password_invitation
from apps.cms.models import SiteSettings
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

MEMBERS_URL = "/api/v1/admin/members"
RESET_CONFIRM = "/api/v1/auth/password/reset/confirm"
GOOD_PASSWORD = "correct-horse-battery"  # noqa: S105 - test fixture

#: The ``SiteSettings`` defaults the ``site_settings`` fixture writes.
ORG_NAME = "The California DART Network"
CONTACT_EMAIL = "info@caldart.example.org"


def _sent(index: int = 0) -> EmailMultiAlternatives:
    """The message ``mail.outbox[index]``, typed as the multipart mail it always is.

    ``send_password_invitation`` always attaches an HTML alternative, but Django's
    stubs type ``mail.outbox`` as the plain ``EmailMessage`` base class, which has
    no ``alternatives`` attribute.
    """
    return cast(EmailMultiAlternatives, mail.outbox[index])


def _html_alternative(message: EmailMultiAlternatives) -> str:
    """The HTML body of ``message``'s first alternative, coerced to plain text."""
    content, _mimetype = message.alternatives[0]
    return str(content)


@pytest.fixture
def admin_client(api_client: APIClient, account_admin: User) -> APIClient:
    """An API client signed in as an account administrator."""
    api_client.force_login(account_admin)
    return api_client


@pytest.fixture
def invitee(db: None) -> User:
    """An account created without a password, waiting to be invited."""
    user = UserFactory(email="invited@example.test", first_name="Nova", last_name="Ito")
    user.set_unusable_password()
    user.save(update_fields=["password"])
    return user


def invitation_link() -> str:
    """The reset link in the text body of the most recent email."""
    body = str(mail.outbox[-1].body)
    match = re.search(r"https?://\S*/portal/reset-password\?uid=[^&\s]+&token=[^\s&\"<]+", body)
    assert match, f"no invitation link in:\n{body}"
    return match.group(0)


def uid_and_token() -> tuple[str, str]:
    """The ``uid`` and ``token`` query parameters of the mailed link."""
    match = re.search(r"\?uid=([^&\s]+)&token=([^\s&\"<]+)", invitation_link())
    assert match, "the invitation link carries no uid and token"
    return match.group(1), match.group(2)


# --------------------------------------------------------------------------
# The link
# --------------------------------------------------------------------------
@override_settings(SITE_URL="https://caldart.example.org")
def test_the_link_is_built_from_site_url(invitee: User, site_settings: SiteSettings) -> None:
    """The mailed link is built from the ``SITE_URL`` setting."""
    send_password_invitation(invitee)
    assert invitation_link().startswith("https://caldart.example.org/portal/reset-password?uid=")


@override_settings(SITE_URL="https://caldart.example.org/")
def test_a_trailing_slash_on_site_url_gives_no_double_slash(
    invitee: User, site_settings: SiteSettings
) -> None:
    """A ``SITE_URL`` ending in a slash does not produce a doubled slash in the link."""
    send_password_invitation(invitee)
    assert invitation_link().startswith("https://caldart.example.org/portal/reset-password?uid=")


@override_settings(SITE_URL="https://caldart.example.org/")
def test_the_html_link_drops_the_trailing_slash_too(
    invitee: User, site_settings: SiteSettings
) -> None:
    """The HTML alternative's link also avoids a doubled slash."""
    send_password_invitation(invitee)
    assert "https://caldart.example.org//portal" not in _html_alternative(_sent(0))


# --------------------------------------------------------------------------
# The message
# --------------------------------------------------------------------------
def test_the_subject_asks_the_member_to_set_a_password(
    invitee: User, site_settings: SiteSettings
) -> None:
    """The subject line asks the member to set a password, named for the organization."""
    send_password_invitation(invitee)
    assert mail.outbox[0].subject == f"{ORG_NAME}: set your password"


def test_the_subject_follows_the_organization_name(
    invitee: User, site_settings: SiteSettings
) -> None:
    """The subject line follows a change to the configured organization name."""
    site_settings.org_name = "Bay Area DART"
    site_settings.save(update_fields=["org_name"])
    send_password_invitation(invitee)
    assert mail.outbox[0].subject == "Bay Area DART: set your password"


def test_the_message_goes_to_the_invited_address(
    invitee: User, site_settings: SiteSettings
) -> None:
    """The message is addressed to the invited account's email."""
    send_password_invitation(invitee)
    assert mail.outbox[0].to == ["invited@example.test"]


def test_the_text_body_greets_the_member_by_first_name(
    invitee: User, site_settings: SiteSettings
) -> None:
    """The text body greets the member by first name."""
    send_password_invitation(invitee)
    assert "Hello Nova," in mail.outbox[0].body


def test_the_text_body_names_the_organization_and_the_address(
    invitee: User, site_settings: SiteSettings
) -> None:
    """The text body names the organization and the email address the account is under."""
    send_password_invitation(invitee)
    expected = f"An account has been created for you at {ORG_NAME}, registered to"
    assert expected in mail.outbox[0].body


def test_the_text_body_states_how_long_the_link_lasts(
    invitee: User, site_settings: SiteSettings
) -> None:
    """The text body states that the link expires in three days."""
    send_password_invitation(invitee)
    assert "The link can be used once and expires in 3 days." in mail.outbox[0].body


def test_the_text_body_gives_the_contact_address(
    invitee: User, site_settings: SiteSettings
) -> None:
    """The text body gives the configured contact address."""
    send_password_invitation(invitee)
    assert f"write to {CONTACT_EMAIL}." in mail.outbox[0].body


def test_the_message_carries_one_alternative(invitee: User, site_settings: SiteSettings) -> None:
    """The message carries exactly one alternative body."""
    send_password_invitation(invitee)
    assert len(_sent(0).alternatives) == 1


def test_the_alternative_is_html(invitee: User, site_settings: SiteSettings) -> None:
    """The alternative body is HTML."""
    send_password_invitation(invitee)
    _html, mimetype = _sent(0).alternatives[0]
    assert mimetype == "text/html"


def test_the_html_part_carries_the_link(invitee: User, site_settings: SiteSettings) -> None:
    """The HTML alternative carries the reset link."""
    send_password_invitation(invitee)
    assert "/portal/reset-password?uid=" in _html_alternative(_sent(0))


def test_the_html_part_names_the_organization(invitee: User, site_settings: SiteSettings) -> None:
    """The HTML alternative names the organization."""
    send_password_invitation(invitee)
    assert ORG_NAME in _html_alternative(_sent(0))


# --------------------------------------------------------------------------
# The link works
# --------------------------------------------------------------------------
def test_the_mailed_link_is_accepted_by_the_reset_confirm(
    api_client: APIClient, invitee: User, site_settings: SiteSettings
) -> None:
    """The mailed uid and token are accepted by the password-reset confirm endpoint."""
    send_password_invitation(invitee)
    uid, token = uid_and_token()

    response = api_client.post(
        RESET_CONFIRM, {"uid": uid, "token": token, "new_password": GOOD_PASSWORD}
    )

    assert response.status_code == 204


def test_the_mailed_link_sets_the_password(
    api_client: APIClient, invitee: User, site_settings: SiteSettings
) -> None:
    """Confirming the mailed link sets the account's password."""
    send_password_invitation(invitee)
    uid, token = uid_and_token()
    api_client.post(RESET_CONFIRM, {"uid": uid, "token": token, "new_password": GOOD_PASSWORD})

    invitee.refresh_from_db()
    assert invitee.check_password(GOOD_PASSWORD)


# --------------------------------------------------------------------------
# When it is sent
# --------------------------------------------------------------------------
def test_creating_a_member_without_a_password_sends_the_invitation(
    admin_client: APIClient,
    site_settings: SiteSettings,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """Creating a member with no password mails an invitation once the commit fires."""
    with django_capture_on_commit_callbacks(execute=True):
        admin_client.post(MEMBERS_URL, {"email": "newbie@example.test"}, format="json")
    assert mail.outbox[0].subject == f"{ORG_NAME}: set your password"


def test_creating_a_member_with_a_password_sends_nothing(
    admin_client: APIClient,
    site_settings: SiteSettings,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """Creating a member with a password given sends no invitation email."""
    with django_capture_on_commit_callbacks(execute=True):
        admin_client.post(
            MEMBERS_URL,
            {"email": "newbie@example.test", "password": GOOD_PASSWORD},
            format="json",
        )
    assert mail.outbox == []
