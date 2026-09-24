"""The shared templated-email sender and the organization details it reads."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
from django.core.mail import EmailMessage
from pytest_django import Settings

from caldart.mail import contact_email, org_name, send_templated
from caldart.org import org_details
from tests.factories import make_site_settings

pytestmark = pytest.mark.django_db

#: The bodies the fixture below writes, so no test here depends on a template
#: some other app owns.
TEXT_TEMPLATE = "Dear {{ first_name }}, your total is {{ total }}.\n"
HTML_TEMPLATE = "<p>Dear {{ first_name }}, your total is {{ total }}.</p>\n"

#: The context both bodies render.
CONTEXT: dict[str, object] = {"first_name": "Marta", "total": "$95.00"}


@pytest.fixture
def email_template(tmp_path: Path, settings: Settings) -> str:
    """Write ``emails/statement_of_fact.{txt,html}`` into a template directory.

    Returns the template name to hand to ``send_templated``.  The directory is
    added to the template search path for the test alone.
    """
    directory = tmp_path / "emails"
    directory.mkdir()
    (directory / "statement_of_fact.txt").write_text(TEXT_TEMPLATE)
    (directory / "statement_of_fact.html").write_text(HTML_TEMPLATE)
    templates = copy.deepcopy(settings.TEMPLATES)
    templates[0]["DIRS"] = [*templates[0]["DIRS"], tmp_path]
    settings.TEMPLATES = templates
    return "statement_of_fact"


def test_send_templated_sends_the_text_body_of_the_named_template(
    email_template: str, mailoutbox: list[EmailMessage]
) -> None:
    """The rendered ``.txt`` body is the message proper."""
    send_templated(
        to="marta@example.org",
        subject="CalDART: your receipt",
        template=email_template,
        context=CONTEXT,
    )

    assert mailoutbox[0].body == "Dear Marta, your total is $95.00.\n"


def test_send_templated_attaches_the_html_body_as_an_alternative(
    email_template: str, mailoutbox: list[EmailMessage]
) -> None:
    """The rendered ``.html`` body rides along as the ``text/html`` alternative."""
    send_templated(
        to="marta@example.org",
        subject="CalDART: your receipt",
        template=email_template,
        context=CONTEXT,
    )

    html, mimetype = mailoutbox[0].alternatives[0]
    assert html == "<p>Dear Marta, your total is $95.00.</p>\n"
    assert mimetype == "text/html"


def test_send_templated_sends_exactly_one_message(
    email_template: str, mailoutbox: list[EmailMessage]
) -> None:
    """One call is one email, to the one address given."""
    send_templated(
        to="marta@example.org",
        subject="CalDART: your receipt",
        template=email_template,
        context=CONTEXT,
    )

    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == ["marta@example.org"]


def test_send_templated_carries_the_subject_it_is_given(
    email_template: str, mailoutbox: list[EmailMessage]
) -> None:
    """The subject is the caller's, untouched: nothing is prefixed here."""
    send_templated(
        to="marta@example.org",
        subject="CalDART: your receipt",
        template=email_template,
        context=CONTEXT,
    )

    assert mailoutbox[0].subject == "CalDART: your receipt"


def test_send_templated_attaches_what_it_is_given(
    email_template: str, mailoutbox: list[EmailMessage]
) -> None:
    """An attachment arrives with its filename, its bytes and its media type."""
    send_templated(
        to="marta@example.org",
        subject="CalDART: your receipt",
        template=email_template,
        context=CONTEXT,
        attachments=[("receipt.pdf", b"%PDF-1.4 fake", "application/pdf")],
    )

    attachment = mailoutbox[0].attachments[0]
    assert attachment.filename == "receipt.pdf"
    assert attachment.content == b"%PDF-1.4 fake"
    assert attachment.mimetype == "application/pdf"


def test_send_templated_returns_the_message_it_sent(
    email_template: str, mailoutbox: list[EmailMessage]
) -> None:
    """The caller gets the message back, so it can record what went out."""
    message = send_templated(
        to="marta@example.org",
        subject="CalDART: your receipt",
        template=email_template,
        context=CONTEXT,
    )

    assert message.to == ["marta@example.org"]


def test_org_name_falls_back_when_there_is_no_site_settings_row() -> None:
    """Before a website administrator fills the settings in, the name is CalDART."""
    assert org_name() == "CalDART"


def test_contact_email_is_empty_when_there_is_no_site_settings_row() -> None:
    """An absent settings row leaves the contact address blank, not missing."""
    assert contact_email() == ""


def test_org_name_comes_from_the_site_settings() -> None:
    """A filled-in settings row names the organization."""
    make_site_settings(org_name="The California DART Network")

    assert org_name() == "The California DART Network"


def test_contact_email_comes_from_the_site_settings() -> None:
    """A filled-in settings row carries the address members write to."""
    make_site_settings(contact_email="info@caldart.example.org")

    assert contact_email() == "info@caldart.example.org"


def test_org_details_names_the_organization() -> None:
    """The letterhead's name is the settings row's ``org_name``."""
    make_site_settings(org_name="The California DART Network")

    assert org_details().name == "The California DART Network"


def test_org_details_carries_the_mailing_address() -> None:
    """A receipt has to print somewhere to write to, so the address comes along."""
    make_site_settings(mailing_address="PO Box 41\nPalo Alto, CA 94301")

    assert org_details().mailing_address == "PO Box 41\nPalo Alto, CA 94301"


def test_org_details_carries_the_ein() -> None:
    """A 501(c)(3) receipt names the EIN, so it is part of the letterhead."""
    make_site_settings(ein="94-1234567")

    assert org_details().ein == "94-1234567"


def test_org_details_leaves_the_letterhead_blank_without_a_settings_row() -> None:
    """With no settings row the address and the EIN are empty, and nothing raises."""
    details = org_details()

    assert details.mailing_address == ""
    assert details.ein == ""


def test_org_details_carries_the_site_url_without_a_trailing_slash(
    settings: Settings,
) -> None:
    """Every link an email builds hangs off this, so the slash is stripped once."""
    settings.SITE_URL = "https://caldart.example.org/"

    assert org_details().site_url == "https://caldart.example.org"
