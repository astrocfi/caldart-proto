"""Notices about the account: a changed password, and mail sent after the answer.

A password changed by its owner, or replaced through a reset link, is reported to the
account's address, so an owner who did not make the change can take the account back.
The anonymous requests whose answer must not say whether an address has an account
send their mail only once the answer has gone (``caldart.mail.send_after_response``).
``docs/developer/api-auth.rst`` describes both.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

import pytest
from django.core import mail
from django.http import HttpResponse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.services import make_reset_token
from apps.cms.models import SiteSettings
from caldart.mail import send_after_response
from tests.conftest import (
    CHANGE_URL,
    GOOD_PASSWORD,
    RESET_CONFIRM_URL,
    RESET_URL,
    audit_messages,
)
from tests.factories import DEFAULT_PASSWORD, UserFactory

pytestmark = pytest.mark.django_db

CHANGED_SUBJECT = "CalDART: your password was changed"


def subjects() -> list[str]:
    """The subject of every message in the outbox, oldest first."""
    return [str(message.subject) for message in mail.outbox]


def confirm_reset(client: APIClient, user_pk: int) -> int:
    """Spend a fresh reset link for the account ``user_pk``; the status."""
    user = User.objects.get(pk=user_pk)
    uid, token = make_reset_token(user)
    response = client.post(
        RESET_CONFIRM_URL, {"uid": uid, "token": token, "new_password": GOOD_PASSWORD}
    )
    return response.status_code


# --------------------------------------------------------------------------
# A changed password
# --------------------------------------------------------------------------
def test_changing_the_password_mails_a_notice(
    api_client: APIClient, member: User, site_settings: SiteSettings
) -> None:
    """The owner's own change is reported to the account's address."""
    api_client.force_login(member)

    api_client.post(
        CHANGE_URL, {"current_password": DEFAULT_PASSWORD, "new_password": GOOD_PASSWORD}
    )

    assert subjects() == [CHANGED_SUBJECT]


def test_the_notice_goes_to_the_account(api_client: APIClient, member: User) -> None:
    """The notice is addressed to the account's own address."""
    api_client.force_login(member)

    api_client.post(
        CHANGE_URL, {"current_password": DEFAULT_PASSWORD, "new_password": GOOD_PASSWORD}
    )

    assert mail.outbox[0].to == ["member@example.test"]


def test_the_notice_points_to_the_reset_form(api_client: APIClient, member: User) -> None:
    """An owner who did not make the change is sent to the forgot-password page."""
    api_client.force_login(member)

    api_client.post(
        CHANGE_URL, {"current_password": DEFAULT_PASSWORD, "new_password": GOOD_PASSWORD}
    )

    assert "/portal/forgot-password" in str(mail.outbox[0].body)


def test_a_refused_change_mails_nothing(api_client: APIClient, member: User) -> None:
    """A wrong current password changes nothing and reports nothing."""
    api_client.force_login(member)

    api_client.post(CHANGE_URL, {"current_password": "wrong", "new_password": GOOD_PASSWORD})

    assert mail.outbox == []


def test_changing_the_password_records_the_audit_line(
    api_client: APIClient, member: User, audit_log: pytest.LogCaptureFixture
) -> None:
    """The change is the account's own ``account.password_change``."""
    api_client.force_login(member)
    pk = member.pk

    api_client.post(
        CHANGE_URL, {"current_password": DEFAULT_PASSWORD, "new_password": GOOD_PASSWORD}
    )

    assert audit_messages(audit_log, logging.INFO) == [
        f"action=account.password_change actor={pk} target={pk} reset=false"
    ]


def test_a_reset_that_replaces_a_password_mails_a_notice(
    api_client: APIClient, site_settings: SiteSettings, run_on_commit: None
) -> None:
    """Spending a reset link on an account that had a password reports the change."""
    user = UserFactory(email="reset.me@example.test")

    confirm_reset(api_client, user.pk)

    assert subjects() == [CHANGED_SUBJECT]


def test_a_reset_records_the_audit_line(
    api_client: APIClient, audit_log: pytest.LogCaptureFixture
) -> None:
    """The reset is ``account.password_change`` with ``reset=true``."""
    user = UserFactory(email="reset.me@example.test")

    confirm_reset(api_client, user.pk)

    assert (
        f"action=account.password_change actor={user.pk} target={user.pk} reset=true"
        in audit_messages(audit_log, logging.INFO)
    )


def test_a_first_password_mails_no_notice(api_client: APIClient, run_on_commit: None) -> None:
    """Setting the first password of an invited account is not a change to report."""
    user = UserFactory(email="invited@example.test")
    user.set_unusable_password()
    user.save(update_fields=["password"])

    status = confirm_reset(api_client, user.pk)

    assert (status, mail.outbox) == (204, [])


# --------------------------------------------------------------------------
# Mail after the answer
# --------------------------------------------------------------------------
def test_a_reset_request_mails_the_account(
    api_client: APIClient, site_settings: SiteSettings
) -> None:
    """The reset link still reaches an account's address, once the answer has gone."""
    UserFactory(email="someone@example.test")

    api_client.post(RESET_URL, {"email": "someone@example.test"})

    assert subjects() == ["CalDART: reset your password"]


@pytest.mark.parametrize("known", [True, False], ids=["registered", "unknown"])
def test_a_reset_request_is_answered_alike(api_client: APIClient, known: bool) -> None:
    """A registered and an unknown address get the same answer."""
    if known:
        UserFactory(email="someone@example.test")

    response = api_client.post(RESET_URL, {"email": "someone@example.test"})

    assert (response.status_code, response.content) == (204, b"")


def test_nothing_is_sent_before_the_response_closes() -> None:
    """The send waits for the server to close the response."""
    sent: list[str] = []
    response = HttpResponse()

    send_after_response(response, lambda: sent.append("sent"), what="a test message")

    assert sent == []


def test_the_send_runs_when_the_response_closes() -> None:
    """Closing the response, as the WSGI server does, sends."""
    sent: list[str] = []
    response = HttpResponse()
    send_after_response(response, lambda: sent.append("sent"), what="a test message")

    response.close()

    assert sent == ["sent"]


def test_a_failing_send_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    """A send that raises is logged at ERROR rather than lost."""
    response = HttpResponse()
    boom: Callable[[], object] = lambda: 1 / 0  # noqa: E731 - a send that raises

    send_after_response(response, boom, what="a test message")
    with caplog.at_level(logging.ERROR, logger="caldart.mail"):
        response.close()

    assert [record.getMessage() for record in caplog.records] == [
        "Could not send a test message after the response"
    ]
