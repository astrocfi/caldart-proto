"""What a request that sends mail answers when the mail server refuses the message.

A request a member makes for themselves, and a change an administrator saves that
mails somebody as a side effect, answer exactly as they do when the message goes out:
the failed send is in the email log, and the refusal is logged on ``caldart.mail``,
which production mails to ``ADMIN_EMAILS``.  A send the user administrator asks for in
so many words answers 503, so they know it did not go.  ``docs/developer/email.rst``
and ``docs/developer/api-auth.rst`` describe the rule.
"""

from __future__ import annotations

import logging
import smtplib
import sys
from collections.abc import Callable
from dataclasses import dataclass

import pytest
from django.core import mail
from django.core.mail import EmailMessage
from django.core.mail.backends.locmem import EmailBackend
from django.template import TemplateDoesNotExist
from pytest_django import Settings
from pytest_django.fixtures import DjangoCaptureOnCommitCallbacks
from rest_framework.test import APIClient

from apps.accounts.api.views import MAIL_REFUSED
from apps.accounts.models import AccountKind, User
from apps.accounts.roles import ACCOUNT_ADMIN, MEMBER, SYSTEM_ADMIN, USER_ADMIN
from apps.mail.models import EmailLog, EmailStatus
from caldart.error_reports import QuietAdminEmailHandler
from caldart.mail import MailRefusedError, error_name, send_logging_refusal, send_templated
from tests.conftest import (
    ME_URL,
    REGISTER_URL,
    RESET_URL,
    audit_messages,
    register_payload,
    role_matrix,
)
from tests.factories import DEFAULT_PASSWORD, UserFactory

pytestmark = pytest.mark.django_db

RESEND_URL = "/api/v1/auth/email/resend"
CHANGE_EMAIL_URL = "/api/v1/auth/email/change"
REACTIVATE_URL = "/api/v1/auth/reactivate"
USERS_URL = "/api/v1/admin/users"
MEMBERS_URL = "/api/v1/admin/members"

#: The two mail servers every answer is checked against.
ACCEPTS = "accepts"
REFUSES = "refuses"

#: The roles that may ask for a send on the user record.
SENDING_ROLES = [slug for slug, allowed in role_matrix(USER_ADMIN, SYSTEM_ADMIN) if allowed]


@dataclass(frozen=True)
class Exchange:
    """One request: what it answered, what it answers with the mail delivered, and why.

    ``body`` is the parsed answer, or ``None`` for an empty one.  ``expected_status``
    and ``expected_body`` are the answer the request gives when the mail server takes
    the message.  ``account`` is the account the message was for, and ``purpose`` the
    email log purpose it is recorded under.
    """

    status: int
    body: object
    expected_status: int
    expected_body: object
    account: User
    purpose: str


type Flow = Callable[[APIClient], Exchange]


def parsed(content: bytes, client_json: Callable[[], object]) -> object:
    """``None`` for an empty answer, the parsed JSON otherwise."""
    return None if len(content) == 0 else client_json()


def signed_in_admin(client: APIClient, role: str) -> User:
    """Sign a fresh holder of ``role`` in on ``client`` and return the account."""
    admin = UserFactory(email=f"{role}.actor@example.test", roles=[MEMBER, role])
    client.force_login(admin)
    return admin


# --------------------------------------------------------------------------
# The requests that answer whatever the mail server does
# --------------------------------------------------------------------------
def password_reset(client: APIClient) -> Exchange:
    """Ask for a reset for a registered address."""
    account = UserFactory(email="pat.reset@example.test", roles=[MEMBER])
    response = client.post(RESET_URL, {"email": account.email})
    return Exchange(
        response.status_code,
        parsed(response.content, response.json),
        204,
        None,
        account,
        "password_reset",
    )


def registration(client: APIClient) -> Exchange:
    """Register a new member, who is signed in and mailed a verification link."""
    response = client.post(REGISTER_URL, register_payload())
    account = User.objects.get(email=register_payload()["email"])
    return Exchange(
        response.status_code,
        response.json(),
        201,
        client.get(ME_URL).json(),
        account,
        "email_verification",
    )


def donor_registration(client: APIClient) -> Exchange:
    """Register with a donor's address, which mails the link that upgrades the donor."""
    donor = UserFactory(
        email=register_payload()["email"], kind=AccountKind.DONOR, email_verified_at=None
    )
    response = client.post(REGISTER_URL, register_payload())
    return Exchange(
        response.status_code,
        response.json(),
        202,
        {"detail": f"Verification message sent to {donor.email}."},
        donor,
        "email_verification",
    )


def verification_resend(client: APIClient) -> Exchange:
    """Ask for a fresh verification link for one's own unverified address."""
    account = UserFactory(email="uma.resend@example.test", roles=[MEMBER], email_verified_at=None)
    client.force_login(account)
    response = client.post(RESEND_URL)
    return Exchange(
        response.status_code,
        response.json(),
        202,
        {"detail": f"Verification message sent to {account.email}."},
        account,
        "email_verification",
    )


def email_change(client: APIClient) -> Exchange:
    """Move one's own account to another address, which is mailed a verification link."""
    account = UserFactory(email="cal.change@example.test", roles=[MEMBER])
    client.force_login(account)
    response = client.post(
        CHANGE_EMAIL_URL,
        {"email": "cal.moved@example.test", "current_password": DEFAULT_PASSWORD},
    )
    return Exchange(
        response.status_code,
        response.json(),
        200,
        client.get(ME_URL).json(),
        account,
        "email_verification",
    )


def reactivation(client: APIClient) -> Exchange:
    """Reactivate one's own unverified account, which mails a verification link."""
    account = UserFactory(
        email="ria.back@example.test", roles=[MEMBER], is_active=False, email_verified_at=None
    )
    response = client.post(REACTIVATE_URL, {"email": account.email, "password": DEFAULT_PASSWORD})
    return Exchange(
        response.status_code,
        response.json(),
        200,
        client.get(ME_URL).json(),
        account,
        "email_verification",
    )


def admin_user_edit(client: APIClient) -> Exchange:
    """A user administrator changes an address, which is mailed a verification link."""
    signed_in_admin(client, USER_ADMIN)
    account = UserFactory(email="eli.edit@example.test", roles=[MEMBER])
    url = f"{USERS_URL}/{account.pk}"
    response = client.patch(url, {"email": "eli.moved@example.test"}, format="json")
    return Exchange(
        response.status_code,
        response.json(),
        200,
        client.get(url).json(),
        account,
        "email_verification",
    )


def admin_user_reactivation(client: APIClient) -> Exchange:
    """A user administrator reactivates an unverified account, which mails a link."""
    signed_in_admin(client, USER_ADMIN)
    account = UserFactory(
        email="ada.back@example.test", roles=[MEMBER], is_active=False, email_verified_at=None
    )
    url = f"{USERS_URL}/{account.pk}"
    response = client.post(f"{url}/reactivate")
    return Exchange(
        response.status_code,
        response.json(),
        200,
        client.get(url).json(),
        account,
        "email_verification",
    )


def admin_member_creation(client: APIClient) -> Exchange:
    """An account administrator adds a member without a password, who is invited."""
    signed_in_admin(client, ACCOUNT_ADMIN)
    response = client.post(MEMBERS_URL, {"email": "ivy.invited@example.test"}, format="json")
    account = User.objects.get(email="ivy.invited@example.test")
    return Exchange(
        response.status_code,
        response.json(),
        201,
        client.get(f"{MEMBERS_URL}/{account.pk}").json(),
        account,
        "member_invitation",
    )


def admin_member_edit(client: APIClient) -> Exchange:
    """An account administrator changes an address on the member record."""
    signed_in_admin(client, ACCOUNT_ADMIN)
    account = UserFactory(email="max.edit@example.test", roles=[MEMBER])
    url = f"{MEMBERS_URL}/{account.pk}"
    response = client.patch(url, {"email": "max.moved@example.test"}, format="json")
    return Exchange(
        response.status_code,
        response.json(),
        200,
        client.get(url).json(),
        account,
        "email_verification",
    )


def admin_member_reactivation(client: APIClient) -> Exchange:
    """An account administrator reactivates an unverified member from the record."""
    signed_in_admin(client, ACCOUNT_ADMIN)
    account = UserFactory(
        email="mo.back@example.test", roles=[MEMBER], is_active=False, email_verified_at=None
    )
    url = f"{MEMBERS_URL}/{account.pk}"
    response = client.post(f"{url}/reactivate")
    return Exchange(
        response.status_code,
        response.json(),
        200,
        client.get(url).json(),
        account,
        "email_verification",
    )


FLOWS: list[Flow] = [
    password_reset,
    registration,
    donor_registration,
    verification_resend,
    email_change,
    reactivation,
    admin_user_edit,
    admin_user_reactivation,
    admin_member_creation,
    admin_member_edit,
    admin_member_reactivation,
]
FLOW_IDS = [flow.__name__ for flow in FLOWS]


@pytest.fixture(params=[ACCEPTS, REFUSES])
def mail_server(request: pytest.FixtureRequest) -> str:
    """Run the test once with a mail server that takes the message, and once refusing."""
    if request.param == REFUSES:
        request.getfixturevalue("refusing_mail_server")
    return str(request.param)


@pytest.fixture
def exchange(
    request: pytest.FixtureRequest,
    api_client: APIClient,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> Exchange:
    """Make the parametrized flow's request, running the sends queued for its commit."""
    flow: Flow = request.param
    with django_capture_on_commit_callbacks(execute=True):
        return flow(api_client)


@pytest.mark.usefixtures("mail_server")
@pytest.mark.parametrize("exchange", FLOWS, ids=FLOW_IDS, indirect=True)
def test_the_status_does_not_depend_on_the_mail_server(exchange: Exchange) -> None:
    """The request answers the status it answers when the message goes out."""
    assert exchange.status == exchange.expected_status


@pytest.mark.usefixtures("mail_server")
@pytest.mark.parametrize("exchange", FLOWS, ids=FLOW_IDS, indirect=True)
def test_the_body_does_not_depend_on_the_mail_server(exchange: Exchange) -> None:
    """The request answers the body it answers when the message goes out."""
    assert exchange.body == exchange.expected_body


@pytest.mark.parametrize("exchange", FLOWS, ids=FLOW_IDS, indirect=True)
def test_the_email_log_records_whether_the_message_went(
    mail_server: str, exchange: Exchange
) -> None:
    """The row reads ``sent`` when the server took the message, ``failed`` if refused."""
    row = EmailLog.objects.get(user=exchange.account, purpose=exchange.purpose)

    assert row.status == (EmailStatus.FAILED if mail_server == REFUSES else EmailStatus.SENT)


@pytest.fixture
def mail_errors(caplog: pytest.LogCaptureFixture) -> pytest.LogCaptureFixture:
    """Capture what ``caldart.mail`` logs at ERROR, the records production mails.

    The request is made by a fixture, so its records are the setup phase's.
    """
    caplog.set_level(logging.ERROR, logger="caldart.mail")
    return caplog


def mail_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """The ``caldart.mail`` records the request fixture's setup logged."""
    return [record for record in caplog.get_records("setup") if record.name == "caldart.mail"]


@pytest.mark.usefixtures("refusing_mail_server")
@pytest.mark.parametrize("exchange", FLOWS, ids=FLOW_IDS, indirect=True)
def test_a_refusal_is_logged_by_its_class(
    mail_errors: pytest.LogCaptureFixture, exchange: Exchange
) -> None:
    """One ERROR record on ``caldart.mail`` names the refusal's class, for error mail."""
    assert [
        record.getMessage().endswith("(SMTPException)") for record in mail_records(mail_errors)
    ] == [True]


@pytest.mark.usefixtures("refusing_mail_server")
@pytest.mark.parametrize("exchange", FLOWS, ids=FLOW_IDS, indirect=True)
def test_a_refusal_is_logged_without_a_traceback(
    mail_errors: pytest.LogCaptureFixture, exchange: Exchange
) -> None:
    """The record carries no traceback, whose exception text can name an address."""
    assert [record.exc_info for record in mail_records(mail_errors)] == [None]


#: An address the refused recipient's server named in its reply.
REFUSED_ADDRESS = "pat.reset@example.test"


@pytest.fixture
def recipient_refusing_mail_server(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every send raise ``SMTPRecipientsRefused``, whose text names the address."""

    def refuse(self: EmailBackend, email_messages: list[EmailMessage]) -> int:
        reply = (550, f"5.1.1 <{REFUSED_ADDRESS}>: Recipient address rejected".encode())
        raise smtplib.SMTPRecipientsRefused({REFUSED_ADDRESS: reply})

    monkeypatch.setattr(EmailBackend, "send_messages", refuse)


@pytest.mark.usefixtures("recipient_refusing_mail_server")
def test_a_refused_recipient_leaves_no_address_in_the_log(
    caplog: pytest.LogCaptureFixture, api_client: APIClient
) -> None:
    """The record names the class and the SMTP code, and no address."""
    caplog.set_level(logging.ERROR, logger="caldart.mail")
    UserFactory(email=REFUSED_ADDRESS, roles=[MEMBER])

    api_client.post(RESET_URL, {"email": REFUSED_ADDRESS})

    assert [record.getMessage() for record in caplog.records] == [
        "Could not send the password reset for account "
        f"{User.objects.get(email=REFUSED_ADDRESS).pk}: the mail server refused it or "
        "could not be reached (SMTPRecipientsRefused (550))"
    ]


@pytest.mark.usefixtures("recipient_refusing_mail_server")
def test_a_refused_recipient_leaves_no_traceback_in_the_log(
    caplog: pytest.LogCaptureFixture, api_client: APIClient
) -> None:
    """No record carries the exception, whose text names the address."""
    caplog.set_level(logging.ERROR, logger="caldart.mail")
    UserFactory(email=REFUSED_ADDRESS, roles=[MEMBER])

    api_client.post(RESET_URL, {"email": REFUSED_ADDRESS})

    assert [record.exc_info for record in caplog.records] == [None]


@pytest.fixture
def unrenderable_templates(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make rendering any email fail with ``PermissionError``, an ``OSError``."""

    def unreadable(template_name: str, context: object = None) -> str:
        raise PermissionError(f"cannot read {template_name}")

    monkeypatch.setattr("caldart.mail.render_to_string", unreadable)


@pytest.mark.usefixtures("unrenderable_templates")
@pytest.mark.parametrize(
    ("role", "path"),
    [(MEMBER, None), (USER_ADMIN, "send-password-reset"), (USER_ADMIN, "send-email-verification")],
    ids=["self-service reset", "admin reset", "admin verification"],
)
def test_a_template_that_does_not_render_answers_500(
    api_client: APIClient, role: str, path: str | None
) -> None:
    """An ``OSError`` while rendering is a bug, not a refusal, so the request fails."""
    api_client.raise_request_exception = False
    account = UserFactory(email="ren.der@example.test", roles=[MEMBER], email_verified_at=None)
    if path is None:
        response = api_client.post(RESET_URL, {"email": account.email})
    else:
        signed_in_admin(api_client, role)
        response = api_client.post(f"{USERS_URL}/{account.pk}/{path}")

    assert response.status_code == 500


@pytest.mark.usefixtures("refusing_mail_server")
def test_a_refused_reset_reads_as_a_reset_for_an_unknown_address(api_client: APIClient) -> None:
    """A refused reset for a registered address answers as one for an unknown address."""
    UserFactory(email="pat.reset@example.test", roles=[MEMBER])

    known = api_client.post(RESET_URL, {"email": "pat.reset@example.test"})
    unknown = api_client.post(RESET_URL, {"email": "nobody.here@example.test"})

    assert known.status_code == unknown.status_code
    assert known.content == unknown.content


# --------------------------------------------------------------------------
# The sends a user administrator asks for: 503
# --------------------------------------------------------------------------
ADMIN_SENDS = {
    "send-password-reset": "password_reset",
    "send-email-verification": "email_verification",
}


@pytest.fixture
def admin_send(
    request: pytest.FixtureRequest, api_client: APIClient, role: str
) -> tuple[int, object, User]:
    """Ask, as a holder of ``role``, for the parametrized send to an unverified member.

    Answers the status, the parsed body, and the member.
    """
    action: str = request.param
    signed_in_admin(api_client, role)
    account = UserFactory(email="una.mailed@example.test", roles=[MEMBER], email_verified_at=None)
    response = api_client.post(f"{USERS_URL}/{account.pk}/{action}")
    return response.status_code, response.json(), account


@pytest.mark.usefixtures("refusing_mail_server")
@pytest.mark.parametrize("role", SENDING_ROLES)
@pytest.mark.parametrize("admin_send", list(ADMIN_SENDS), indirect=True)
def test_a_refused_admin_send_answers_503(admin_send: tuple[int, object, User]) -> None:
    """The administrator is told the mail server refused, with a 503."""
    status, _body, _account = admin_send

    assert status == 503


@pytest.mark.usefixtures("refusing_mail_server")
@pytest.mark.parametrize("role", SENDING_ROLES)
@pytest.mark.parametrize("admin_send", list(ADMIN_SENDS), indirect=True)
def test_a_refused_admin_send_says_where_the_attempt_is(
    admin_send: tuple[int, object, User],
) -> None:
    """The ``detail`` says the message did not go and points at the Sent Emails page."""
    _status, body, _account = admin_send

    assert body == {"detail": MAIL_REFUSED}


@pytest.mark.usefixtures("refusing_mail_server")
@pytest.mark.parametrize("role", [USER_ADMIN])
@pytest.mark.parametrize(
    ("admin_send", "purpose"), list(ADMIN_SENDS.items()), indirect=["admin_send"]
)
def test_a_refused_admin_send_is_in_the_email_log(
    admin_send: tuple[int, object, User], purpose: str
) -> None:
    """The attempt is on the Sent Emails page as a failed send."""
    _status, _body, account = admin_send

    assert EmailLog.objects.get(user=account, purpose=purpose).status == EmailStatus.FAILED


@pytest.mark.usefixtures("refusing_mail_server")
@pytest.mark.parametrize("role", [USER_ADMIN])
@pytest.mark.parametrize("admin_send", list(ADMIN_SENDS), indirect=True)
def test_a_refused_admin_send_is_not_audited_as_sent(
    audit_log: pytest.LogCaptureFixture, admin_send: tuple[int, object, User]
) -> None:
    """No ``admin_sent`` audit line claims a message the server refused."""
    assert [line for line in audit_messages(audit_log) if "admin_sent" in line] == []


@pytest.mark.usefixtures("refusing_mail_server")
@pytest.mark.parametrize("role", [USER_ADMIN])
@pytest.mark.parametrize("admin_send", list(ADMIN_SENDS), indirect=True)
def test_a_refused_admin_send_is_logged_by_its_class(
    mail_errors: pytest.LogCaptureFixture, admin_send: tuple[int, object, User]
) -> None:
    """The refusal reaches the operators through ``caldart.mail``, with no traceback."""
    records = mail_records(mail_errors)

    assert [record.getMessage().endswith("(SMTPException)") for record in records] == [True]
    assert [record.exc_info for record in records] == [None]


# --------------------------------------------------------------------------
# The helper and the error mail
# --------------------------------------------------------------------------
@pytest.mark.usefixtures("refusing_mail_server")
def test_send_logging_refusal_answers_false_for_a_refusal(email_template: str) -> None:
    """A refused send is reported as not sent rather than raised."""
    sent = send_logging_refusal(
        lambda: send_templated(to="ops@example.org", subject="Hi", template=email_template),
        what="a test message",
    )

    assert sent is False


def test_send_logging_refusal_answers_true_once_the_message_goes(email_template: str) -> None:
    """A send the server takes is reported as sent."""
    sent = send_logging_refusal(
        lambda: send_templated(to="ops@example.org", subject="Hi", template=email_template),
        what="a test message",
    )

    assert sent is True


def test_send_logging_refusal_lets_any_other_error_through() -> None:
    """A template that does not exist is a bug, not a refusal, and still raises."""
    with pytest.raises(TemplateDoesNotExist, match=r"emails/no_such_template\.txt"):
        send_logging_refusal(
            lambda: send_templated(to="ops@example.org", subject="Hi", template="no_such_template"),
            what="a test message",
        )


@pytest.mark.parametrize(
    ("transport", "message"),
    [
        (
            smtplib.SMTPAuthenticationError(535, b"5.7.8 authentication failed"),
            "SMTPAuthenticationError (535)",
        ),
        (
            smtplib.SMTPRecipientsRefused(
                {"pat@example.test": (550, b"<pat@example.test> unknown")}
            ),
            "SMTPRecipientsRefused (550)",
        ),
        (ConnectionRefusedError(111, "Connection refused"), "ConnectionRefusedError"),
    ],
    ids=["authentication", "recipient", "connection"],
)
def test_a_refusal_reads_as_its_class_and_code(transport: OSError, message: str) -> None:
    """``MailRefusedError`` says the transport's class and SMTP code, and nothing else."""
    assert str(MailRefusedError.from_transport(transport)) == message


def test_a_job_logs_a_refusal_under_the_transport_class() -> None:
    """``error_name`` gives the class the email log records, not ``MailRefusedError``."""
    refusal = MailRefusedError.from_transport(smtplib.SMTPServerDisconnected("gone"))

    assert error_name(refusal) == "SMTPServerDisconnected"


def error_record() -> logging.LogRecord:
    """An ERROR record carrying a refusal's traceback, as ``log_refusal`` writes one."""
    try:
        raise smtplib.SMTPException("Mailbox unavailable")
    except smtplib.SMTPException:
        exc_info = sys.exc_info()
    return logging.LogRecord(
        "caldart.mail", logging.ERROR, __file__, 1, "Could not send %s", ("a test",), exc_info
    )


@pytest.fixture
def admins(settings: Settings) -> None:
    """Give the error mail somebody to go to."""
    settings.ADMINS = ["ops@example.org"]


@pytest.mark.usefixtures("admins")
def test_the_quiet_handler_mails_the_report() -> None:
    """With a mail server that takes it, the report reaches ``ADMINS``."""
    QuietAdminEmailHandler().emit(error_record())

    assert [message.to for message in mail.outbox] == [["ops@example.org"]]


@pytest.mark.usefixtures("admins", "refusing_mail_server")
def test_the_quiet_handler_survives_a_refusing_mail_server(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A report the server refuses goes to standard error instead of raising."""
    QuietAdminEmailHandler().emit(error_record())

    assert "SMTPException: Mailbox unavailable" in capsys.readouterr().err
