"""What every message carries so a bounce can be traced back to it.

``caldart.mail.send_templated`` gives each message a ``Message-ID`` stored on its email
log row, and, when ``BOUNCE_ADDRESS`` is set, sends it on the envelope from that address
signed with the row's id, while the ``From`` header stays ``DEFAULT_FROM_EMAIL``.  See
``docs/developer/email.rst``.
"""

from __future__ import annotations

import smtplib

import pytest
from django.core.mail import EmailMessage
from django.core.mail.backends.locmem import EmailBackend
from pytest_django import Settings

from apps.mail.models import EmailLog, EmailStatus
from caldart.mail import MailRefusedError, bounce_tag, send_templated, signed_bounce_address

pytestmark = pytest.mark.django_db

FROM = "CalDART <noreply@caldart.example.org>"
BOUNCES = "bounces@caldart.example.org"


@pytest.fixture
def sender(settings: Settings) -> Settings:
    """``DEFAULT_FROM_EMAIL`` fixed to :data:`FROM`, without a bounce address."""
    settings.DEFAULT_FROM_EMAIL = FROM
    settings.BOUNCE_ADDRESS = ""
    return settings


def _send(template: str) -> EmailMessage:
    """Send ``template`` to one address and return the message."""
    return send_templated(to="marta@example.org", subject="CalDART: a test", template=template)


def test_every_message_carries_a_message_id_on_the_senders_domain(
    sender: Settings, email_template: str
) -> None:
    """The ``Message-ID`` is generated on the domain of ``DEFAULT_FROM_EMAIL``."""
    message = _send(email_template)

    assert message.message()["Message-ID"].endswith("@caldart.example.org>")


def test_the_log_row_records_the_message_id_the_message_carried(
    sender: Settings, email_template: str
) -> None:
    """The row's ``message_id`` is exactly the header the message went out with."""
    message = _send(email_template)

    assert EmailLog.objects.get().message_id == message.message()["Message-ID"]


def test_two_messages_carry_different_message_ids(sender: Settings, email_template: str) -> None:
    """Each send has its own id, so a report matches one row."""
    _send(email_template)
    _send(email_template)

    assert len(set(EmailLog.objects.values_list("message_id", flat=True))) == 2


@pytest.mark.usefixtures("refusing_mail_server")
def test_a_refused_message_records_its_message_id(sender: Settings, email_template: str) -> None:
    """A send the server refuses still leaves the id it was given on its failed row."""
    with pytest.raises(MailRefusedError, match=r"^SMTPException$"):
        _send(email_template)

    assert EmailLog.objects.get().message_id.endswith("@caldart.example.org>")


def test_without_a_bounce_address_the_envelope_is_the_from_address(
    sender: Settings, email_template: str
) -> None:
    """With ``BOUNCE_ADDRESS`` empty the envelope is ``DEFAULT_FROM_EMAIL``, as before."""
    message = _send(email_template)

    assert message.from_email == FROM


def test_a_bounce_address_is_the_envelope_sender_signed_with_the_log_row(
    sender: Settings, email_template: str
) -> None:
    """With ``BOUNCE_ADDRESS`` set, the envelope is it, signed for the row."""
    sender.BOUNCE_ADDRESS = BOUNCES

    message = _send(email_template)

    row = EmailLog.objects.get()
    assert message.from_email == signed_bounce_address(row.pk, row.message_id)


def test_two_messages_go_from_different_signed_addresses(
    sender: Settings, email_template: str
) -> None:
    """Each send's envelope names its own row, so a report names one message."""
    sender.BOUNCE_ADDRESS = BOUNCES

    first = _send(email_template)
    second = _send(email_template)

    assert bounce_tag(first.from_email) != bounce_tag(second.from_email)


def test_a_refused_message_went_from_its_failed_rows_address(
    sender: Settings, email_template: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The envelope a refused message was handed over with names the failed row."""
    sender.BOUNCE_ADDRESS = BOUNCES
    envelopes: list[str] = []

    def refuse(self: EmailBackend, email_messages: list[EmailMessage]) -> int:
        envelopes.extend(message.from_email for message in email_messages)
        raise smtplib.SMTPException("Mailbox unavailable")

    monkeypatch.setattr(EmailBackend, "send_messages", refuse)
    with pytest.raises(MailRefusedError, match=r"^SMTPException$"):
        _send(email_template)

    failed = EmailLog.objects.get(status=EmailStatus.FAILED)
    assert envelopes == [signed_bounce_address(failed.pk, failed.message_id)]


def test_a_bounce_address_leaves_the_from_header_alone(
    sender: Settings, email_template: str
) -> None:
    """The reader still sees ``DEFAULT_FROM_EMAIL`` as sender, and replies go there."""
    sender.BOUNCE_ADDRESS = BOUNCES

    message = _send(email_template)

    assert message.message()["From"] == FROM
