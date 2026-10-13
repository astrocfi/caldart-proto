"""Registering: one answer for every address, and a message that tells the owner the rest.

``POST /auth/register`` answers 202 with the same body whoever holds the address, and
signs nobody in; the address's owner learns the next step from the message mailed once
the answer has gone.  ``docs/developer/api-auth.rst`` describes the endpoint and
``docs/user/member/join.rst`` what a joiner sees.
"""

from __future__ import annotations

from typing import cast

import pytest
from django.core import mail
from django.core.mail import EmailMultiAlternatives
from rest_framework.test import APIClient

from apps.accounts.models import AccountKind, User
from apps.accounts.services import address_holder
from apps.cms.models import SiteSettings
from tests.conftest import ME_URL, REGISTER_URL, register_payload
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

ADDRESS = "new.member@example.test"
SENT = {"detail": f"We sent a message to {ADDRESS}. Follow the link in it to continue."}

#: A password the common-password validator refuses.
COMMON_PASSWORD = "password1"  # noqa: S105 - a password the validators reject

#: Who may hold the address a registration names.
HOLDERS = ["nobody", "donor", "member", "friend", "unverified", "deactivated", "closed"]


def hold(holder: str) -> User | None:
    """Give :data:`ADDRESS` to an account of the ``holder`` kind, or to nobody."""
    if holder == "nobody":
        return None
    if holder == "donor":
        return UserFactory(email=ADDRESS, kind=AccountKind.DONOR, roles=[])
    if holder == "friend":
        return UserFactory(email=ADDRESS, kind=AccountKind.FRIEND, roles=["member"])
    if holder == "unverified":
        return UserFactory(email=ADDRESS, roles=["member"], email_verified_at=None)
    if holder == "deactivated":
        return UserFactory(email=ADDRESS, roles=["member"], is_active=False)
    if holder == "closed":
        return UserFactory(
            email=ADDRESS, roles=["member"], is_active=False, reactivation_blocked=True
        )
    return UserFactory(email=ADDRESS, roles=["member"])


def only_mail() -> EmailMultiAlternatives:
    """The one message in the outbox."""
    assert len(mail.outbox) == 1, [m.subject for m in mail.outbox]
    return cast(EmailMultiAlternatives, mail.outbox[0])


# --------------------------------------------------------------------------
# One answer
# --------------------------------------------------------------------------
@pytest.mark.parametrize("holder", HOLDERS)
def test_every_address_is_answered_alike(api_client: APIClient, holder: str) -> None:
    """The status and the body are the same whoever holds the address."""
    hold(holder)

    response = api_client.post(REGISTER_URL, register_payload())

    assert (response.status_code, response.json()) == (202, SENT)


@pytest.mark.parametrize("holder", HOLDERS)
def test_registering_signs_nobody_in(api_client: APIClient, holder: str) -> None:
    """No session comes back, so no cookie tells a new account from an old one."""
    hold(holder)
    api_client.post(REGISTER_URL, register_payload())

    assert api_client.get(ME_URL).status_code == 401


@pytest.mark.parametrize("holder", HOLDERS)
def test_a_weak_password_is_refused_alike(api_client: APIClient, holder: str) -> None:
    """A refused password reads the same whoever holds the address."""
    hold(holder)

    response = api_client.post(REGISTER_URL, register_payload(password=COMMON_PASSWORD))

    assert (response.status_code, response.json()) == (
        400,
        {"password": ["This password is too common."]},
    )


@pytest.mark.parametrize("holder", HOLDERS)
def test_a_missing_name_is_refused_alike(api_client: APIClient, holder: str) -> None:
    """A missing first name reads the same whoever holds the address."""
    hold(holder)

    response = api_client.post(REGISTER_URL, register_payload(first_name=""))

    assert (response.status_code, response.json()) == (
        400,
        {"first_name": ["Enter your first name."]},
    )


@pytest.mark.parametrize("holder", ["member", "deactivated", "closed"])
def test_an_existing_account_is_left_as_it_was(api_client: APIClient, holder: str) -> None:
    """Registering an address that has an account writes nothing to it."""
    account = hold(holder)
    assert account is not None

    api_client.post(REGISTER_URL, register_payload(first_name="Mallory"))

    account.refresh_from_db()
    assert account.first_name != "Mallory"


def test_an_existing_account_keeps_its_password(api_client: APIClient, member: User) -> None:
    """The password typed is never written to an account that already exists."""
    before = member.password

    api_client.post(REGISTER_URL, register_payload(email=member.email))

    member.refresh_from_db()
    assert member.password == before


def test_a_new_address_opens_an_account_with_the_password(api_client: APIClient) -> None:
    """A brand-new address opens an account that signs in with the password given."""
    api_client.post(REGISTER_URL, register_payload())

    assert User.objects.get(email=ADDRESS).check_password(register_payload()["password"])


def test_a_new_address_opens_the_kind_asked_for(api_client: APIClient) -> None:
    """``kind`` is stored as given."""
    api_client.post(REGISTER_URL, {**register_payload(), "kind": "friend"})

    assert User.objects.get(email=ADDRESS).kind == AccountKind.FRIEND


# --------------------------------------------------------------------------
# The message
# --------------------------------------------------------------------------
def test_a_new_address_is_mailed_a_verification_link(
    api_client: APIClient, site_settings: SiteSettings
) -> None:
    """A brand-new address gets the verification message."""
    api_client.post(REGISTER_URL, register_payload())

    assert only_mail().subject == "CalDART: verify your email address"


def test_a_donors_address_is_mailed_the_upgrade_link(
    api_client: APIClient, site_settings: SiteSettings
) -> None:
    """A donor's address gets the link that opens the donor's portal account."""
    hold("donor")

    api_client.post(REGISTER_URL, register_payload())

    assert "asked to open a portal account" in " ".join(str(only_mail().body).split())


@pytest.mark.parametrize("holder", ["member", "friend", "unverified"])
def test_an_existing_account_is_told_to_sign_in(
    api_client: APIClient, site_settings: SiteSettings, holder: str
) -> None:
    """An address that already signs in is told so, and nothing else is sent."""
    hold(holder)

    api_client.post(REGISTER_URL, register_payload())

    assert only_mail().subject == "CalDART: you already have an account"


def test_the_sign_in_message_links_to_the_sign_in_page(api_client: APIClient, member: User) -> None:
    """The message carries the sign-in page with the address filled in."""
    api_client.post(REGISTER_URL, register_payload(email=member.email))

    assert "/portal/login?email=member%40example.test" in str(only_mail().body)


def test_the_sign_in_message_links_to_the_reset_form(api_client: APIClient, member: User) -> None:
    """The message carries the forgot-password page for a password not remembered."""
    api_client.post(REGISTER_URL, register_payload(email=member.email))

    assert "/portal/forgot-password" in str(only_mail().body)


def test_a_deactivated_account_is_told_how_to_come_back(api_client: APIClient) -> None:
    """A deactivated account's address reads how to reactivate it."""
    hold("deactivated")

    api_client.post(REGISTER_URL, register_payload())

    assert "Reactivate my account" in str(only_mail().body)


def test_a_closed_account_is_told_to_ask(api_client: APIClient) -> None:
    """A closed account's address reads that it was closed, and nothing to follow."""
    hold("closed")

    api_client.post(REGISTER_URL, register_payload())

    body = " ".join(str(only_mail().body).split())
    assert "has been closed. Contact CalDART to reopen it." in body


def test_a_closed_account_is_offered_no_sign_in(api_client: APIClient) -> None:
    """The closed account's message carries no sign-in link."""
    hold("closed")

    api_client.post(REGISTER_URL, register_payload())

    assert "/portal/login" not in str(only_mail().body)


def test_an_address_taken_while_registering_is_answered_alike(
    api_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An account made between the lookup and the write is answered as a taken address."""
    hold("member")
    found = iter([None])
    monkeypatch.setattr(
        "apps.members.services.address_holder",
        lambda address: next(found, address_holder(address)),
    )

    response = api_client.post(REGISTER_URL, register_payload())

    assert (response.status_code, response.json()) == (202, SENT)


def test_an_address_taken_while_registering_is_told_it_has_an_account(
    api_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The holder of the address is mailed the notice, not a verification link."""
    hold("member")
    found = iter([None])
    monkeypatch.setattr(
        "apps.members.services.address_holder",
        lambda address: next(found, address_holder(address)),
    )

    api_client.post(REGISTER_URL, register_payload())

    assert only_mail().subject == "CalDART: you already have an account"
