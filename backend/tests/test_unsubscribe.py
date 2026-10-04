"""The unsubscribe link a bulk email carries, and the page it opens.

The behavior is documented in ``docs/developer/email.rst``.
"""

from __future__ import annotations

import pytest
from django.core import signing
from django.test import Client
from freezegun import freeze_time
from pytest_django import Settings

from apps.accounts.models import User
from apps.mail.models import EmailOptOut, EmailType, OptOutSource
from apps.mail.unsubscribe import UNSUBSCRIBE_SALT, make_token, unsubscribe_url
from tests.conftest import audit_messages
from tests.factories import EmailOptOutFactory, EmailTypeFactory, UserFactory

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("no_email_types")]

#: What a mail program posts for a one-click unsubscribe (RFC 8058).
ONE_CLICK_BODY = "List-Unsubscribe=One-Click"


def page_url(token: str) -> str:
    """The unsubscribe page's path for ``token``."""
    return f"/mail/unsubscribe/{token}"


@pytest.fixture
def mission(no_email_types: None) -> EmailType:
    """Mission email, which a person may turn off."""
    return EmailTypeFactory(name="Mission")


@pytest.fixture
def link(member: User, mission: EmailType) -> str:
    """The path of ``member``'s unsubscribe link for Mission."""
    return page_url(make_token(member, mission))


# -- the page a link opens ----------------------------------------------------
def test_opening_the_link_records_nothing(client: Client, link: str, member: User) -> None:
    """A mail scanner that follows the link unsubscribes nobody."""
    response = client.get(link)

    assert response.status_code == 200
    assert not EmailOptOut.objects.filter(user=member).exists()


def test_the_page_names_the_type_and_offers_one_button(client: Client, link: str) -> None:
    """The confirmation names the type and posts back to the link."""
    response = client.get(link)

    assert response.context["state"] == "confirm"
    assert "Unsubscribe from Mission email" in response.content.decode()


@pytest.mark.parametrize("method", ["get", "post"])
def test_the_page_names_the_address_it_unsubscribes(
    client: Client, link: str, member: User, method: str
) -> None:
    """Before and after the press, the page says which address it is for."""
    response = client.generic(method.upper(), link)

    assert f"<strong>{member.email}</strong>." in response.content.decode()


def test_the_page_says_when_the_type_is_already_off(
    client: Client, link: str, member: User, mission: EmailType
) -> None:
    """Somebody who has already turned the type off is told so."""
    EmailOptOutFactory(user=member, email_type=mission)

    response = client.get(link)

    assert response.context["state"] == "already"
    assert "You have already unsubscribed from Mission email for" in response.content.decode()


def test_pressing_the_button_records_the_opt_out(
    client: Client, link: str, member: User, mission: EmailType
) -> None:
    """The POST records the opt-out from the unsubscribe link and says so."""
    response = client.post(link)

    assert response.status_code == 200
    assert EmailOptOut.objects.get(user=member, email_type=mission).source == (
        OptOutSource.UNSUBSCRIBE
    )
    assert "You will no longer receive Mission email" in response.content.decode()


def test_a_one_click_post_needs_no_csrf_token(link: str, member: User) -> None:
    """A mail program's own unsubscribe button posts with no session and no token."""
    client = Client(enforce_csrf_checks=True)

    response = client.post(link, ONE_CLICK_BODY, content_type="application/x-www-form-urlencoded")

    assert response.status_code == 200
    assert EmailOptOut.objects.filter(user=member).count() == 1


def test_unsubscribing_twice_records_one_opt_out(client: Client, link: str, member: User) -> None:
    """The second press finds the opt-out already there."""
    client.post(link)
    response = client.post(link)

    assert response.status_code == 200
    assert EmailOptOut.objects.filter(user=member).count() == 1


def test_unsubscribing_is_audited_as_the_person(
    client: Client,
    link: str,
    member: User,
    mission: EmailType,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """The person the link names is the actor, and the source is the link."""
    client.post(link)

    assert audit_messages(audit_log) == [
        f"action=email.opt_out actor={member.pk} target={member.pk} "
        f"email_type={mission.pk} source=unsubscribe"
    ]


def test_the_page_offers_the_email_preferences_screen(client: Client, link: str) -> None:
    """Every state links to the portal's Email preferences."""
    response = client.post(link)

    assert 'href="/portal/email-preferences"' in response.content.decode()


def test_other_methods_are_refused(client: Client, link: str) -> None:
    """Only GET and POST are served."""
    assert client.put(link).status_code == 405


# -- a type that cannot be turned off ----------------------------------------
@pytest.mark.parametrize("method", ["get", "post"])
def test_a_type_that_cannot_be_turned_off_records_nothing(
    client: Client, member: User, method: str
) -> None:
    """A link to a type that stopped allowing opt-out changes nothing and says so."""
    operational = EmailTypeFactory(name="Operational", allow_opt_out=False)
    link = page_url(make_token(member, operational))

    response = client.generic(method.upper(), link)

    assert response.status_code == 200
    assert response.context["state"] == "not_allowed"
    assert not EmailOptOut.objects.filter(user=member).exists()


# -- a link that no longer works ---------------------------------------------
def test_a_tampered_token_is_refused(client: Client, member: User, mission: EmailType) -> None:
    """A token whose signature does not match records nothing and answers 400."""
    token = make_token(member, mission)
    tampered = f"{token[:-1]}{'A' if token[-1] != 'A' else 'B'}"

    response = client.post(page_url(tampered))

    assert response.status_code == 400
    assert response.context["state"] == "expired"
    assert not EmailOptOut.objects.filter(user=member).exists()


def test_a_token_for_another_purpose_is_refused(
    client: Client, member: User, mission: EmailType
) -> None:
    """A value signed with any other salt is not an unsubscribe token."""
    token = signing.dumps({"u": member.pk, "t": mission.pk}, salt="accounts.email_verification")

    assert client.post(page_url(token)).status_code == 400


def test_a_token_carrying_the_wrong_shape_is_refused(client: Client) -> None:
    """A signed payload that names no account and type is refused."""
    token = signing.dumps(["not", "a", "payload"], salt=UNSUBSCRIBE_SALT)

    assert client.get(page_url(token)).status_code == 400


def test_an_expired_token_is_refused(
    client: Client, member: User, mission: EmailType, settings: Settings
) -> None:
    """A link older than ``UNSUBSCRIBE_TOKEN_MAX_AGE`` records nothing."""
    settings.UNSUBSCRIBE_TOKEN_MAX_AGE = 60
    with freeze_time("2026-10-01 12:00:00"):
        token = make_token(member, mission)
    with freeze_time("2026-10-01 12:01:01"):
        response = client.post(page_url(token))

    assert response.status_code == 400
    assert not EmailOptOut.objects.filter(user=member).exists()


def test_a_token_just_inside_its_age_still_works(
    client: Client, member: User, mission: EmailType, settings: Settings
) -> None:
    """A link exactly as old as the limit is honored."""
    settings.UNSUBSCRIBE_TOKEN_MAX_AGE = 60
    with freeze_time("2026-10-01 12:00:00"):
        token = make_token(member, mission)
    with freeze_time("2026-10-01 12:01:00"):
        response = client.post(page_url(token))

    assert response.status_code == 200


def test_a_token_for_a_deleted_type_is_refused(
    client: Client, member: User, mission: EmailType
) -> None:
    """A link to a type that has since been deleted no longer works."""
    token = make_token(member, mission)
    mission.delete()

    assert client.post(page_url(token)).status_code == 400


def test_a_token_for_a_deleted_account_is_refused(
    client: Client, mission: EmailType, audit_log: pytest.LogCaptureFixture
) -> None:
    """A link for an account since deleted records nothing and answers 400."""
    person = UserFactory(email="gone@example.test")
    token = make_token(person, mission)
    person.delete()

    response = client.post(page_url(token))

    assert response.status_code == 400
    assert response.context["state"] == "expired"
    assert EmailOptOut.objects.count() == 0
    assert audit_messages(audit_log) == []


# -- the link itself -----------------------------------------------------------
def test_the_link_is_built_on_the_site_url_and_its_prefix(
    member: User, mission: EmailType, settings: Settings
) -> None:
    """A site served under a path keeps that path in the link."""
    settings.SITE_URL = "https://example.org/caldart/"

    url = unsubscribe_url(member, mission)

    assert url.startswith("https://example.org/caldart/mail/unsubscribe/")
