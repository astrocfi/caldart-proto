"""The unsubscribe headers and footer of a bulk email copy; transactional mail has none.

The behavior is documented in ``docs/developer/email.rst``.
"""

from __future__ import annotations

import re

import pytest
from django.core import mail
from pytest_django import Settings

from apps.accounts.models import User
from apps.mail.models import EmailType
from apps.mail.unsubscribe import Footer, footer_for, headers_for, read_token
from caldart.mail import send_templated
from tests.factories import EmailTypeFactory, make_site_settings

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("no_email_types")]

#: ``List-Unsubscribe`` with the HTTPS link and a ``mailto:``, capturing the token.
LIST_UNSUBSCRIBE_RE = re.compile(
    r"<https://caldart\.example\.org/mail/unsubscribe/(?P<token>[^>]+)>, "
    r"<mailto:contact@caldart\.example\.org\?subject=unsubscribe>"
)


@pytest.fixture
def site(settings: Settings) -> None:
    """Serve the site at ``https://caldart.example.org`` with a contact address set."""
    settings.SITE_URL = "https://caldart.example.org"
    make_site_settings(org_name="CalDART", contact_email="contact@caldart.example.org")


@pytest.fixture
def mission(no_email_types: None) -> EmailType:
    """Mission email, which a person may turn off."""
    return EmailTypeFactory(name="Mission")


@pytest.fixture
def operational(no_email_types: None) -> EmailType:
    """Operational email, which nobody may turn off."""
    return EmailTypeFactory(name="Operational", allow_opt_out=False)


@pytest.mark.usefixtures("site")
def test_a_type_that_may_be_turned_off_carries_both_headers(
    member: User, mission: EmailType
) -> None:
    """``List-Unsubscribe`` holds the link and the ``mailto:``; one-click is offered."""
    headers = headers_for(member, mission)

    assert LIST_UNSUBSCRIBE_RE.fullmatch(headers["List-Unsubscribe"]) is not None
    assert headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"


@pytest.mark.usefixtures("site")
def test_the_header_link_names_the_recipient_and_the_type(member: User, mission: EmailType) -> None:
    """The token in the header reads back as this copy's recipient and type."""
    match = LIST_UNSUBSCRIBE_RE.fullmatch(headers_for(member, mission)["List-Unsubscribe"])
    assert match is not None

    assert read_token(match["token"]) == (member, mission)


def test_without_a_contact_address_only_the_link_is_given(
    member: User, mission: EmailType, settings: Settings
) -> None:
    """No contact address means no ``mailto:``."""
    settings.SITE_URL = "https://caldart.example.org"
    make_site_settings(contact_email="")

    header = headers_for(member, mission)["List-Unsubscribe"]

    assert re.fullmatch(r"<https://caldart\.example\.org/mail/unsubscribe/[^>]+>", header)


def test_a_non_ascii_site_host_reaches_the_header_in_its_ascii_form(
    member: User, mission: EmailType, settings: Settings
) -> None:
    """Each host is IDNA-encoded, so the header stays the ASCII a mail program reads."""
    settings.SITE_URL = "https://caldärt.example.org:8443/caldart"
    make_site_settings(contact_email="contact@caldärt.example.org")

    header = headers_for(member, mission)["List-Unsubscribe"]

    assert re.fullmatch(
        r"<https://xn--caldrt-eua\.example\.org:8443/caldart/mail/unsubscribe/[^>]+>, "
        r"<mailto:contact@xn--caldrt-eua\.example\.org\?subject=unsubscribe>",
        header,
    )


@pytest.mark.usefixtures("site")
def test_a_type_that_cannot_be_turned_off_carries_no_headers(
    member: User, operational: EmailType
) -> None:
    """Neither header is given for a type that does not allow opting out."""
    assert headers_for(member, operational) == {}


@pytest.mark.usefixtures("site")
def test_the_footer_offers_the_link(member: User, mission: EmailType) -> None:
    """The footer says why the email came and links to turn it off."""
    footer = footer_for(member, mission)

    assert footer.text == (
        "You receive Mission email from CalDART because you have not turned it off. "
        "To stop it, unsubscribe here:"
    )
    assert footer.url.startswith("https://caldart.example.org/mail/unsubscribe/")


@pytest.mark.usefixtures("site")
def test_the_footer_says_why_a_type_cannot_be_turned_off(
    member: User, operational: EmailType
) -> None:
    """A type that does not allow opting out explains itself and links nowhere."""
    assert footer_for(member, operational) == Footer(
        text=(
            "CalDART sends Operational email to everyone it writes to, so it cannot be turned off."
        ),
        url="",
    )


@pytest.mark.usefixtures("site")
def test_transactional_mail_carries_no_unsubscribe_headers(
    member: User, email_template: str
) -> None:
    """A receipt, a reminder, or a password link is never unsubscribed from."""
    send_templated(to=member.email, subject="Your receipt", template=email_template)

    message = mail.outbox[0].message()
    assert message["List-Unsubscribe"] is None
    assert message["List-Unsubscribe-Post"] is None
