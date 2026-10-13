"""Changing the sign-in address: the request, the link that completes it, and undo.

A change of address waits for its new owner: the account keeps signing in with the
address it has until the link mailed to the new one is followed, and the address it had
is told, with a link that undoes the change.  ``docs/developer/api-auth.rst`` describes
the endpoints and ``docs/user/member/change-email.rst`` what a member sees.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from io import StringIO
from typing import cast

import freezegun
import pytest
from django.core import mail, signing
from django.core.cache import cache
from django.core.mail import EmailMultiAlternatives
from django.core.management import call_command
from django.utils import timezone
from pytest_django import Settings
from rest_framework.test import APIClient

from apps.accounts.email_change import (
    ADDRESS_TAKEN,
    EMAIL_CHANGE_UNDO_SALT,
    UNDO_INVALID,
    make_undo_token,
    recent_change_refused,
    request_email_change,
)
from apps.accounts.models import AccountChange, AccountChangeKind, AccountKind, User
from apps.accounts.services import make_reset_token, replace_password
from apps.cms.models import SiteSettings
from apps.payments.donations import DonorFields, donor_for
from tests.conftest import (
    CHANGE_URL as PASSWORD_CHANGE_URL,
)
from tests.conftest import (
    GOOD_PASSWORD,
    LOGIN_URL,
    ME_URL,
    REGISTER_URL,
    RESET_CONFIRM_URL,
    audit_messages,
    register_payload,
)
from tests.factories import DEFAULT_PASSWORD, UserFactory

pytestmark = pytest.mark.django_db

CHANGE_URL = "/api/v1/auth/email/change"
VERIFY_URL = "/api/v1/auth/email/verify"
UNDO_URL = "/api/v1/auth/email/undo"
RESEND_URL = "/api/v1/auth/email/resend"
MEMBERS_URL = "/api/v1/admin/members"

OLD = "vera@example.test"
NEW = "vera.new@example.test"
INVALID_LINK = "That verification link is invalid or has expired."


@pytest.fixture
def vera(db: None) -> User:
    """A member whose address was verified a week ago."""
    user = UserFactory(email=OLD, first_name="Vera", last_name="Quill", roles=["member"])
    user.email_verified_at = timezone.now() - timedelta(days=7)
    user.save(update_fields=["email_verified_at"])
    return user


@pytest.fixture
def signed_in(api_client: APIClient) -> Callable[[User], APIClient]:
    """Sign ``user`` in on the shared API client and return the client."""

    def sign_in(user: User) -> APIClient:
        api_client.force_login(user)
        return api_client

    return sign_in


def ask(client: APIClient, email: str = NEW) -> int:
    """Post a change of address to ``email`` with the right password; the status."""
    response = client.post(CHANGE_URL, {"email": email, "current_password": DEFAULT_PASSWORD})
    return response.status_code


def mails_to(address: str) -> list[EmailMultiAlternatives]:
    """Every message in the outbox addressed to ``address``, oldest first."""
    return [
        cast(EmailMultiAlternatives, message) for message in mail.outbox if message.to == [address]
    ]


def link_token(message: EmailMultiAlternatives, path: str) -> str:
    """The ``token`` of the link to ``path`` in ``message``'s text body."""
    match = re.search(rf"{re.escape(path)}\?token=(\S+)", str(message.body))
    assert match, f"no {path} link in:\n{message.body}"
    return match.group(1)


def confirm_token(address: str = NEW) -> str:
    """The token of the newest link that completes a change, mailed to ``address``."""
    return link_token(mails_to(address)[-1], "/portal/verify-email")


def undo_token(address: str = OLD) -> str:
    """The token of the newest undo link mailed to ``address``."""
    return link_token(mails_to(address)[-1], "/portal/undo-email-change")


def change_and_confirm(vera: User, client: APIClient) -> None:
    """Ask to move ``vera`` to :data:`NEW` and follow the link mailed there."""
    ask(client)
    client.post(VERIFY_URL, {"token": confirm_token()})


# --------------------------------------------------------------------------
# Asking
# --------------------------------------------------------------------------
def test_asking_keeps_the_address(
    vera: User, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """The answer's ``email`` is the address the account still signs in with."""
    response = signed_in(vera).post(
        CHANGE_URL, {"email": NEW, "current_password": DEFAULT_PASSWORD}
    )

    assert (response.status_code, response.json()["email"]) == (200, OLD)


def test_asking_records_the_pending_address(
    vera: User, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """The answer and the account carry the address the change waits for."""
    response = signed_in(vera).post(
        CHANGE_URL, {"email": NEW, "current_password": DEFAULT_PASSWORD}
    )

    assert response.json()["pending_email"] == NEW


def test_asking_keeps_the_address_verified(
    vera: User, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """Nothing about the current address changes, its verification included."""
    ask(signed_in(vera))

    vera.refresh_from_db()
    assert vera.email_verified is True


def test_the_old_address_still_signs_in(
    vera: User, api_client: APIClient, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """Until the link is followed, signing in takes the old address."""
    ask(signed_in(vera))
    api_client.logout()

    response = api_client.post(LOGIN_URL, {"email": OLD, "password": DEFAULT_PASSWORD})

    assert response.status_code == 200


def test_the_new_address_does_not_sign_in_yet(
    vera: User, api_client: APIClient, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """The pending address is nobody's login."""
    ask(signed_in(vera))
    api_client.logout()

    response = api_client.post(LOGIN_URL, {"email": NEW, "password": DEFAULT_PASSWORD})

    assert response.status_code == 400


def test_asking_mails_the_new_address_a_link(
    vera: User,
    signed_in: Callable[[User], APIClient],
    site_settings: SiteSettings,
    run_on_commit: None,
) -> None:
    """The new address is mailed the link that completes the change."""
    ask(signed_in(vera))

    assert [m.subject for m in mails_to(NEW)] == ["CalDART: confirm your new email address"]


def test_asking_tells_the_old_address(
    vera: User,
    signed_in: Callable[[User], APIClient],
    site_settings: SiteSettings,
    run_on_commit: None,
) -> None:
    """A verified old address is told the change is coming, with a link to undo it."""
    ask(signed_in(vera))

    assert [m.subject for m in mails_to(OLD)] == ["CalDART: your email address is changing"]


def test_the_notice_names_the_new_address(
    vera: User, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """The old address reads where the account is moving to."""
    ask(signed_in(vera))

    assert NEW in str(mails_to(OLD)[0].body)


def test_an_unverified_old_address_is_not_told(
    signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """An address nobody has proved may be somebody else's, so it gets no undo link."""
    joiner = UserFactory(email=OLD, roles=["member"], email_verified_at=None)

    ask(signed_in(joiner))

    assert mails_to(OLD) == []


def test_asking_records_the_audit_line(
    vera: User,
    signed_in: Callable[[User], APIClient],
    audit_log: pytest.LogCaptureFixture,
    run_on_commit: None,
) -> None:
    """The request is the member's own ``account.email_change_request``."""
    ask(signed_in(vera))

    assert audit_messages(audit_log, logging.INFO) == [
        f"action=account.email_change_request actor={vera.pk} target={vera.pk}"
    ]


def test_asking_needs_a_session(api_client: APIClient) -> None:
    """An anonymous caller is answered 401."""
    assert ask(api_client) == 401


def test_asking_refuses_a_wrong_password(
    vera: User, signed_in: Callable[[User], APIClient]
) -> None:
    """A wrong current password is a 400 under ``current_password``, checked first."""
    response = signed_in(vera).post(CHANGE_URL, {"email": OLD, "current_password": "wrong"})

    assert (response.status_code, response.json()) == (
        400,
        {"current_password": ["That is not your current password."]},
    )


def test_asking_refuses_the_current_address(
    vera: User, signed_in: Callable[[User], APIClient]
) -> None:
    """The address the account already has, in any case, is a 400 under ``email``."""
    response = signed_in(vera).post(
        CHANGE_URL, {"email": OLD.upper(), "current_password": DEFAULT_PASSWORD}
    )

    assert (response.status_code, response.json()) == (
        400,
        {"email": ["That is already your email address."]},
    )


def test_a_taken_address_is_answered_like_a_free_one(
    vera: User, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """Asking for another account's address reads exactly as asking for a free one."""
    client = signed_in(vera)
    free = client.post(CHANGE_URL, {"email": NEW, "current_password": DEFAULT_PASSWORD})
    User.objects.filter(pk=vera.pk).update(pending_email="")
    UserFactory(email="taken@example.test")

    taken = client.post(
        CHANGE_URL, {"email": "taken@example.test", "current_password": DEFAULT_PASSWORD}
    )

    assert (taken.status_code, taken.json()) == (
        free.status_code,
        {**free.json(), "pending_email": "taken@example.test"},
    )


def test_a_taken_address_is_not_stored(
    vera: User, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """Nothing waits for an address another account holds."""
    UserFactory(email=NEW)

    ask(signed_in(vera))

    vera.refresh_from_db()
    assert vera.pending_email == ""


def test_a_taken_address_mails_nobody(
    vera: User, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """Neither the address's holder nor the requester's address is sent anything."""
    UserFactory(email=NEW)

    ask(signed_in(vera))

    assert mail.outbox == []


def test_asking_is_throttled_when_a_rate_is_configured(
    vera: User,
    signed_in: Callable[[User], APIClient],
    settings: Settings,
    run_on_commit: None,
) -> None:
    """Past the ``auth_email_change`` rate the endpoint answers 429."""
    cache.clear()
    settings.AUTH_THROTTLE_RATES = {"auth_email_change": "2/hour"}
    client = signed_in(vera)

    statuses = [ask(client, f"try{index}@example.test") for index in range(3)]

    cache.clear()
    assert statuses == [200, 200, 429]


# --------------------------------------------------------------------------
# Following the link
# --------------------------------------------------------------------------
def test_the_link_moves_the_account(
    vera: User, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """Following the link makes the new address the account's own."""
    change_and_confirm(vera, signed_in(vera))

    vera.refresh_from_db()
    assert (vera.email, vera.pending_email) == (NEW, "")


def test_the_link_answers_the_changed_address(
    vera: User, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """The verify endpoint answers the new address with ``changed`` true."""
    client = signed_in(vera)
    ask(client)

    response = client.post(VERIFY_URL, {"token": confirm_token()})

    assert (response.status_code, response.json()) == (200, {"email": NEW, "changed": True})


def test_the_link_leaves_the_new_address_verified(
    vera: User, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """Following the link proves the new address."""
    change_and_confirm(vera, signed_in(vera))

    vera.refresh_from_db()
    assert vera.email_verified is True


def test_the_new_address_signs_in_once_the_link_is_followed(
    vera: User, api_client: APIClient, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """Signing in takes the new address from then on."""
    change_and_confirm(vera, signed_in(vera))
    api_client.logout()

    response = api_client.post(LOGIN_URL, {"email": NEW, "password": DEFAULT_PASSWORD})

    assert response.status_code == 200


def test_completing_tells_the_old_address(
    vera: User,
    signed_in: Callable[[User], APIClient],
    site_settings: SiteSettings,
    run_on_commit: None,
) -> None:
    """The old address is told again once the change is made, with an undo link."""
    change_and_confirm(vera, signed_in(vera))

    assert [m.subject for m in mails_to(OLD)] == [
        "CalDART: your email address is changing",
        "CalDART: your email address has changed",
    ]


def test_completing_is_recorded_in_the_history(
    vera: User, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """The account's history reads the change under the account that asked for it."""
    change_and_confirm(vera, signed_in(vera))

    entry = AccountChange.objects.get(user=vera)
    assert (entry.kind, entry.changed_by) == (AccountChangeKind.EMAIL_CHANGED, vera)


def test_completing_records_the_audit_lines(
    vera: User,
    signed_in: Callable[[User], APIClient],
    audit_log: pytest.LogCaptureFixture,
    run_on_commit: None,
) -> None:
    """Completing is the account's own ``account.update`` of ``email``, then verified."""
    client = signed_in(vera)
    ask(client)
    audit_log.clear()

    client.post(VERIFY_URL, {"token": confirm_token()})

    assert audit_messages(audit_log, logging.INFO) == [
        f"action=account.update actor={vera.pk} target={vera.pk} fields=email",
        f"action=account.email_verified actor={vera.pk} target={vera.pk}",
    ]


def test_completing_clears_a_bounce(
    vera: User, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """A bounce recorded against the old address does not follow the account."""
    User.objects.filter(pk=vera.pk).update(
        email_bounced_at=timezone.now(), email_bounce_detail="550 5.1.1"
    )
    change_and_confirm(vera, signed_in(vera))

    vera.refresh_from_db()
    assert vera.email_bounced_at is None


def test_following_the_link_twice_changes_nothing_more(
    vera: User, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """A second visit answers as the first did."""
    client = signed_in(vera)
    ask(client)
    token = confirm_token()
    client.post(VERIFY_URL, {"token": token})

    response = client.post(VERIFY_URL, {"token": token})

    assert (response.status_code, response.json()) == (200, {"email": NEW, "changed": True})


def test_a_later_request_spends_the_earlier_link(
    vera: User, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """Asking for another address makes the first link do nothing."""
    client = signed_in(vera)
    ask(client)
    first = confirm_token()
    ask(client, "vera.other@example.test")

    response = client.post(VERIFY_URL, {"token": first})

    assert (response.status_code, response.json()) == (400, {"token": [INVALID_LINK]})


def test_the_later_link_still_works(
    vera: User, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """The newest request is the one that completes."""
    client = signed_in(vera)
    ask(client)
    ask(client, "vera.other@example.test")

    client.post(VERIFY_URL, {"token": confirm_token("vera.other@example.test")})

    vera.refresh_from_db()
    assert vera.email == "vera.other@example.test"


def test_a_link_is_refused_once_the_address_was_taken(
    vera: User, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """An address another account took meanwhile is refused, and nothing changes."""
    client = signed_in(vera)
    ask(client)
    UserFactory(email=NEW)

    response = client.post(VERIFY_URL, {"token": confirm_token()})

    assert (response.status_code, response.json()) == (400, {"token": [ADDRESS_TAKEN]})


def test_a_link_is_refused_after_an_undo(
    vera: User, api_client: APIClient, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """Undoing a waiting change spends the link that would complete it."""
    ask(signed_in(vera))
    token = confirm_token()
    api_client.post(UNDO_URL, {"token": undo_token()})

    response = api_client.post(VERIFY_URL, {"token": token})

    assert (response.status_code, response.json()) == (400, {"token": [INVALID_LINK]})


def test_resend_mails_the_pending_address(
    vera: User, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """While a change waits, a resend mails the link that completes it."""
    client = signed_in(vera)
    ask(client)

    response = client.post(RESEND_URL)

    assert (response.status_code, response.json()) == (
        202,
        {"detail": f"Verification message sent to {NEW}."},
    )


def test_the_resent_link_completes_the_change(
    vera: User, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """The resent link is as good as the first."""
    client = signed_in(vera)
    ask(client)
    client.post(RESEND_URL)

    client.post(VERIFY_URL, {"token": confirm_token()})

    vera.refresh_from_db()
    assert vera.email == NEW


# --------------------------------------------------------------------------
# An administrator's change
# --------------------------------------------------------------------------
def test_an_administrators_change_waits_for_the_owner(
    account_admin: User, vera: User, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """The member record keeps the address and shows the one waiting."""
    response = signed_in(account_admin).patch(
        f"{MEMBERS_URL}/{vera.pk}", {"email": NEW}, format="json"
    )

    assert (response.json()["email"], response.json()["pending_email"]) == (OLD, NEW)


def test_an_administrators_change_mails_the_new_address(
    account_admin: User, vera: User, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """The new address is mailed the link that completes the change."""
    signed_in(account_admin).patch(f"{MEMBERS_URL}/{vera.pk}", {"email": NEW}, format="json")

    assert len(mails_to(NEW)) == 1


def test_an_administrators_change_is_audited_under_the_administrator(
    account_admin: User,
    vera: User,
    signed_in: Callable[[User], APIClient],
    audit_log: pytest.LogCaptureFixture,
    run_on_commit: None,
) -> None:
    """The request names the administrator who asked."""
    signed_in(account_admin).patch(f"{MEMBERS_URL}/{vera.pk}", {"email": NEW}, format="json")

    assert (
        f"action=account.email_change_request actor={account_admin.pk} target={vera.pk}"
        in audit_messages(audit_log, logging.INFO)
    )


def test_an_administrators_change_is_recorded_under_the_administrator(
    account_admin: User,
    vera: User,
    api_client: APIClient,
    signed_in: Callable[[User], APIClient],
    run_on_commit: None,
) -> None:
    """Once its owner follows the link, the history names the administrator."""
    signed_in(account_admin).patch(f"{MEMBERS_URL}/{vera.pk}", {"email": NEW}, format="json")

    api_client.post(VERIFY_URL, {"token": confirm_token()})

    assert AccountChange.objects.get(user=vera).changed_by == account_admin


def test_a_donors_address_changes_at_once(account_admin: User, run_on_commit: None) -> None:
    """A donor cannot sign in, so the address is only where receipts go."""
    donor = UserFactory(email=OLD, kind=AccountKind.DONOR, email_verified_at=None)

    request_email_change(account_admin, donor, NEW)

    donor.refresh_from_db()
    assert (donor.email, donor.pending_email) == (NEW, "")


def test_a_donors_change_mails_nothing(account_admin: User, run_on_commit: None) -> None:
    """Nothing is sent for a donor's change of address."""
    donor = UserFactory(email=OLD, kind=AccountKind.DONOR, email_verified_at=None)

    request_email_change(account_admin, donor, NEW)

    assert mail.outbox == []


def test_the_same_address_in_another_case_is_no_change(vera: User, run_on_commit: None) -> None:
    """Resending the address in other capitals writes and mails nothing."""
    request_email_change(vera, vera, OLD.upper())

    vera.refresh_from_db()
    assert (vera.email, vera.pending_email, mail.outbox) == (OLD, "", [])


# --------------------------------------------------------------------------
# Undo
# --------------------------------------------------------------------------
def test_undo_puts_the_old_address_back(
    vera: User, api_client: APIClient, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """After the change, the undo link restores the address it was mailed to."""
    change_and_confirm(vera, signed_in(vera))

    response = api_client.post(UNDO_URL, {"token": undo_token()})

    vera.refresh_from_db()
    assert (response.status_code, response.json(), vera.email) == (
        200,
        {"email": OLD, "taken": False},
        OLD,
    )


def test_undo_drops_a_waiting_change(
    vera: User, api_client: APIClient, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """Before the change, the undo link drops it and the address stays."""
    ask(signed_in(vera))

    api_client.post(UNDO_URL, {"token": undo_token()})

    vera.refresh_from_db()
    assert (vera.email, vera.pending_email) == (OLD, "")


def test_undo_ends_every_session(
    vera: User, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """Whoever asked for the change is signed out."""
    client = signed_in(vera)
    ask(client)
    token = undo_token()

    APIClient().post(UNDO_URL, {"token": token})

    assert client.get(ME_URL).status_code == 401


def test_undo_stops_the_password_working(
    vera: User, api_client: APIClient, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """The password that asked for the change no longer signs in."""
    ask(signed_in(vera))
    api_client.post(UNDO_URL, {"token": undo_token()})

    vera.refresh_from_db()
    assert vera.has_usable_password() is False


def test_undo_mails_a_reset_link_to_the_old_address(
    vera: User,
    api_client: APIClient,
    signed_in: Callable[[User], APIClient],
    site_settings: SiteSettings,
    run_on_commit: None,
) -> None:
    """The owner chooses a new password from the address put back."""
    change_and_confirm(vera, signed_in(vera))

    api_client.post(UNDO_URL, {"token": undo_token()})

    assert mails_to(OLD)[-1].subject == "CalDART: reset your password"


def test_undo_is_recorded_in_the_history(
    vera: User, api_client: APIClient, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """The history reads the undo under the account itself."""
    ask(signed_in(vera))

    api_client.post(UNDO_URL, {"token": undo_token()})

    entry = AccountChange.objects.get(user=vera, kind=AccountChangeKind.EMAIL_CHANGE_UNDONE)
    assert entry.changed_by == vera


def test_undo_records_the_audit_line(
    vera: User,
    api_client: APIClient,
    signed_in: Callable[[User], APIClient],
    audit_log: pytest.LogCaptureFixture,
    run_on_commit: None,
) -> None:
    """An undo that put an address back says so."""
    change_and_confirm(vera, signed_in(vera))
    audit_log.clear()

    api_client.post(UNDO_URL, {"token": undo_token()})

    assert audit_messages(audit_log, logging.INFO) == [
        f"action=account.email_change_undo actor={vera.pk} target={vera.pk} restored=true"
    ]


def test_an_undo_link_works_once(
    vera: User, api_client: APIClient, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """Following the same link again is refused."""
    change_and_confirm(vera, signed_in(vera))
    token = undo_token()
    api_client.post(UNDO_URL, {"token": token})

    response = api_client.post(UNDO_URL, {"token": token})

    assert (response.status_code, response.json()) == (400, {"token": [UNDO_INVALID]})


def test_an_undo_spends_the_earlier_undo_links(
    vera: User, api_client: APIClient, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """The notice sent at the request is spent by following the one sent at completion."""
    change_and_confirm(vera, signed_in(vera))
    first, second = (link_token(m, "/portal/undo-email-change") for m in mails_to(OLD))
    api_client.post(UNDO_URL, {"token": second})

    response = api_client.post(UNDO_URL, {"token": first})

    assert response.status_code == 400


# --------------------------------------------------------------------------
# The recovery address
# --------------------------------------------------------------------------
def test_a_completed_change_keeps_the_old_address_for_recovery(
    vera: User, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """The verified address the account left is kept as its recovery address."""
    change_and_confirm(vera, signed_in(vera))

    vera.refresh_from_db()
    assert vera.recovery_email == OLD


def test_the_recovery_address_is_kept_for_seven_days(
    vera: User, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """It is kept as long as the undo links last."""
    with freezegun.freeze_time("2026-10-12 12:00:00"):
        change_and_confirm(vera, signed_in(vera))

    vera.refresh_from_db()
    assert vera.recovery_until == timezone.make_aware(datetime(2026, 10, 19, 12, 0, 0), UTC)


def test_the_account_cannot_change_its_address_again_meanwhile(
    vera: User, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """A second self-service change during the window is refused, saying until when."""
    client = signed_in(vera)
    change_and_confirm(vera, client)
    vera.refresh_from_db()
    assert vera.recovery_until is not None

    response = client.post(
        CHANGE_URL, {"email": "third@example.test", "current_password": DEFAULT_PASSWORD}
    )

    assert (response.status_code, response.json()) == (
        400,
        {"email": [recent_change_refused(vera.recovery_until)]},
    )


def test_whoever_moved_the_account_cannot_spend_the_owners_undo_links(
    vera: User, api_client: APIClient, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """The reviewer's sequence: change and confirm, ask again, undo from the new address.

    The second request is refused, and an undo link made out to the new address is
    refused too, so the owner's links still work.
    """
    client = signed_in(vera)
    change_and_confirm(vera, client)
    owners = [link_token(m, "/portal/undo-email-change") for m in mails_to(OLD)]
    ask(client, "third@example.test")
    vera.refresh_from_db()
    attackers = make_undo_token(vera, previous_email=NEW, new_email="third@example.test")
    APIClient().post(UNDO_URL, {"token": attackers})

    responses = [APIClient().post(UNDO_URL, {"token": token}).status_code for token in owners]

    assert responses == [200, 400]


def test_an_undo_link_to_the_new_address_is_refused_meanwhile(
    vera: User, api_client: APIClient, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """Only a link mailed to the recovery address counts while it is kept."""
    change_and_confirm(vera, signed_in(vera))
    vera.refresh_from_db()
    token = make_undo_token(vera, previous_email=NEW, new_email="third@example.test")

    response = api_client.post(UNDO_URL, {"token": token})

    assert (response.status_code, response.json()) == (400, {"token": [UNDO_INVALID]})


def test_an_administrators_change_meanwhile_tells_the_recovery_address(
    account_admin: User,
    vera: User,
    signed_in: Callable[[User], APIClient],
    run_on_commit: None,
) -> None:
    """An administrator may still change the address, and the owner hears of it."""
    change_and_confirm(vera, signed_in(vera))
    mail.outbox.clear()

    signed_in(account_admin).patch(
        f"{MEMBERS_URL}/{vera.pk}", {"email": "third@example.test"}, format="json"
    )

    assert [m.subject for m in mails_to(OLD)] == ["CalDART: your email address is changing"]


def test_the_recovery_address_cannot_be_registered(
    vera: User, api_client: APIClient, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """Registering the address the account left opens no second account."""
    change_and_confirm(vera, signed_in(vera))
    api_client.logout()

    api_client.post(REGISTER_URL, register_payload(email=OLD))

    assert User.objects.filter(email__iexact=OLD).exists() is False


def test_registering_the_recovery_address_tells_its_owner(
    vera: User, api_client: APIClient, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """The address is told it already has an account, as any taken address is."""
    change_and_confirm(vera, signed_in(vera))
    api_client.logout()
    mail.outbox.clear()

    api_client.post(REGISTER_URL, register_payload(email=OLD))

    assert [m.subject for m in mails_to(OLD)] == ["CalDART: you already have an account"]


def test_a_gift_from_the_recovery_address_goes_to_the_account(
    vera: User, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """A public gift makes no donor of the address the account left."""
    change_and_confirm(vera, signed_in(vera))

    donor = donor_for(cast(DonorFields, {"first_name": "A", "last_name": "B", "email": OLD}))

    assert donor == vera


def test_another_account_cannot_move_to_the_recovery_address(
    account_admin: User,
    vera: User,
    signed_in: Callable[[User], APIClient],
    run_on_commit: None,
) -> None:
    """The member record refuses the address while it is kept."""
    change_and_confirm(vera, signed_in(vera))
    other = UserFactory(email="other@example.test", roles=["member"])

    response = signed_in(account_admin).patch(
        f"{MEMBERS_URL}/{other.pk}", {"email": OLD}, format="json"
    )

    assert (response.status_code, response.json()) == (
        400,
        {"email": ["An account with that email address already exists."]},
    )


def test_undo_forgets_the_recovery_address(
    vera: User, api_client: APIClient, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """Once the address is back, nothing is kept for recovery."""
    change_and_confirm(vera, signed_in(vera))

    api_client.post(UNDO_URL, {"token": undo_token()})

    vera.refresh_from_db()
    assert (vera.recovery_email, vera.recovery_until) == ("", None)


# --------------------------------------------------------------------------
# A new password spends a waiting change
# --------------------------------------------------------------------------
def test_a_password_change_drops_a_waiting_change(
    vera: User, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """Changing the password empties ``pending_email``."""
    client = signed_in(vera)
    ask(client)

    client.post(
        PASSWORD_CHANGE_URL,
        {"current_password": DEFAULT_PASSWORD, "new_password": GOOD_PASSWORD},
    )

    vera.refresh_from_db()
    assert vera.pending_email == ""


def test_a_reset_spends_the_change_link(
    vera: User, api_client: APIClient, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """A link made before a password reset no longer completes the change."""
    ask(signed_in(vera))
    token = confirm_token()
    vera.refresh_from_db()
    uid, reset = make_reset_token(vera)
    api_client.post(RESET_CONFIRM_URL, {"uid": uid, "token": reset, "new_password": GOOD_PASSWORD})

    response = api_client.post(VERIFY_URL, {"token": token})

    assert (response.status_code, response.json()) == (400, {"token": [INVALID_LINK]})


def test_a_new_password_spends_the_link_even_with_the_change_asked_again(
    vera: User, api_client: APIClient, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """The link is signed over the password, so a later request cannot revive it."""
    client = signed_in(vera)
    ask(client)
    token = confirm_token()
    vera.refresh_from_db()
    assert replace_password(vera, GOOD_PASSWORD) is True
    User.objects.filter(pk=vera.pk).update(pending_email=NEW)

    response = api_client.post(VERIFY_URL, {"token": token})

    assert response.status_code == 400


def test_create_admin_taking_the_account_back_drops_a_waiting_change(
    vera: User, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """Clearing the password on promotion clears the change asked under it too."""
    ask(signed_in(vera))

    call_command("create_admin", email=OLD, stdout=StringIO(), stderr=StringIO())

    vera.refresh_from_db()
    assert vera.pending_email == ""


def test_requiring_a_new_password_drops_a_waiting_change(
    user_admin: User, vera: User, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """A user administrator's **Require a new password** clears the change asked for."""
    ask(signed_in(vera))

    signed_in(user_admin).post(f"/api/v1/admin/users/{vera.pk}/require-new-password")

    vera.refresh_from_db()
    assert vera.pending_email == ""


def test_a_change_completed_meanwhile_answers_the_documented_refusal(
    vera: User,
    api_client: APIClient,
    signed_in: Callable[[User], APIClient],
    monkeypatch: pytest.MonkeyPatch,
    run_on_commit: None,
) -> None:
    """Another account taking the address between the check and the write is a 400."""
    ask(signed_in(vera))
    token = confirm_token()
    UserFactory(email=NEW)
    monkeypatch.setattr("apps.accounts.email_change.address_taken", lambda *_a, **_k: False)

    response = api_client.post(VERIFY_URL, {"token": token})

    assert (response.status_code, response.json()) == (400, {"token": [ADDRESS_TAKEN]})


def test_an_undo_link_expires_after_seven_days(
    vera: User, api_client: APIClient, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """A link older than the timeout is refused and nothing changes."""
    change_and_confirm(vera, signed_in(vera))
    token = undo_token()

    with freezegun.freeze_time(timezone.now() + timedelta(days=7, seconds=1)):
        response = api_client.post(UNDO_URL, {"token": token})

    assert (response.status_code, response.json()) == (400, {"token": [UNDO_INVALID]})


def test_an_undo_link_works_on_its_last_day(
    vera: User, api_client: APIClient, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """A link inside the timeout still works."""
    change_and_confirm(vera, signed_in(vera))
    token = undo_token()

    with freezegun.freeze_time(timezone.now() + timedelta(days=6, hours=23)):
        response = api_client.post(UNDO_URL, {"token": token})

    assert response.status_code == 200


def test_a_forged_undo_link_is_refused(api_client: APIClient, vera: User) -> None:
    """A token signed under another salt proves nothing."""
    token = signing.dumps({"user": vera.pk, "from": "x@example.test", "to": OLD, "at": 0.0})

    response = api_client.post(UNDO_URL, {"token": token})

    assert (response.status_code, response.json()) == (400, {"token": [UNDO_INVALID]})


def test_an_undo_link_for_a_donor_is_refused(api_client: APIClient) -> None:
    """A donor has no sign-in address to protect."""
    donor = UserFactory(email=OLD, kind=AccountKind.DONOR)
    token = signing.dumps(
        {"user": donor.pk, "from": "x@example.test", "to": OLD, "at": timezone.now().timestamp()},
        salt=EMAIL_CHANGE_UNDO_SALT,
    )

    response = api_client.post(UNDO_URL, {"token": token})

    assert response.status_code == 400


def _taken_undo(vera: User, client: APIClient) -> dict[str, object]:
    """Change ``vera``'s address, let another account take the old one, then undo."""
    change_and_confirm(vera, client)
    token = undo_token()
    # Made directly, past the reservation, as an account that held it all along would.
    UserFactory(email=OLD)
    body: dict[str, object] = APIClient().post(UNDO_URL, {"token": token}).json()
    vera.refresh_from_db()
    return body


def test_undo_says_when_the_old_address_is_taken(
    vera: User, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """The address stays as it is, and the answer says why."""
    assert _taken_undo(vera, signed_in(vera)) == {"email": NEW, "taken": True}


def test_undo_secures_the_account_when_the_old_address_is_taken(
    vera: User, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """The password stops working all the same."""
    _taken_undo(vera, signed_in(vera))

    assert vera.has_usable_password() is False


def test_undo_mails_the_reset_link_to_the_old_address_when_it_is_taken(
    vera: User, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """The reset link goes where the undo link went, not to the account's address."""
    _taken_undo(vera, signed_in(vera))

    assert mails_to(OLD)[-1].subject == "CalDART: reset your password"
