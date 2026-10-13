"""Changing the sign-in address: the request, the link that completes it, and undo.

A change of address waits for its new owner: the account keeps signing in with the
address it has until the link mailed to the new one is followed, and the address it had
is told, with a link that undoes the change.  ``docs/developer/api-auth.rst`` describes
the endpoints and ``docs/user/member/change-email.rst`` what a member sees.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

import pytest
from django.core import mail
from django.core.cache import cache
from django.utils import timezone
from pytest_django import Settings
from rest_framework.test import APIClient

from apps.accounts.email_change import (
    ADDRESS_TAKEN,
    UNDO_INVALID,
    Mailing,
    request_email_change,
)
from apps.accounts.models import AccountChange, AccountChangeKind, AccountKind, User
from apps.cms.models import SiteSettings
from apps.members.services import OWN_ADDRESS_ON_RECORD_REFUSED
from tests.conftest import (
    EMAIL_CHANGE_URL,
    EMAIL_RESEND_URL,
    EMAIL_UNDO_URL,
    EMAIL_VERIFY_URL,
    LOGIN_URL,
    ME_URL,
    VERA_NEW,
    VERA_OLD,
    ask,
    audit_messages,
    change_and_confirm,
    confirm_token,
    link_token,
    mails_to,
    undo_token,
)
from tests.factories import DEFAULT_PASSWORD, UserFactory

pytestmark = pytest.mark.django_db

CHANGE_URL = EMAIL_CHANGE_URL
VERIFY_URL = EMAIL_VERIFY_URL
UNDO_URL = EMAIL_UNDO_URL
RESEND_URL = EMAIL_RESEND_URL
MEMBERS_URL = "/api/v1/admin/members"
DEACTIVATE_URL = "/api/v1/auth/deactivate"

OLD = VERA_OLD
NEW = VERA_NEW
INVALID_LINK = "That verification link is invalid or has expired."


@pytest.fixture
def signed_in(signed_in_client: Callable[[User], APIClient]) -> Callable[[User], APIClient]:
    """Sign ``user`` in on the shared API client and return the client."""
    return signed_in_client


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


def _after_asking(email: str, *, taken: bool) -> dict[str, object]:
    """Ask, as a fresh member, for ``email``, held by another account when ``taken``.

    Returns what the member can see afterwards: the answer, ``/auth/me``, and a resend.
    """
    if taken:
        UserFactory(email=email)
    member = UserFactory(email=f"asker.{taken}@example.test", roles=["member"])
    client = APIClient()
    client.force_login(member)
    change = client.post(CHANGE_URL, {"email": email, "current_password": DEFAULT_PASSWORD})
    resend = client.post(RESEND_URL)
    me = client.get(ME_URL).json()
    return {
        "change": (change.status_code, change.json()["pending_email"]),
        "me": me["pending_email"],
        "resend": (resend.status_code, resend.json()),
    }


@pytest.mark.parametrize("taken", [False, True], ids=["free", "taken"])
def test_a_taken_address_is_answered_like_a_free_one_everywhere(
    taken: bool, run_on_commit: None
) -> None:
    """The answer, ``/auth/me`` and a resend read the same whoever holds the address."""
    seen = _after_asking("wanted@example.test", taken=taken)

    assert seen == {
        "change": (200, "wanted@example.test"),
        "me": "wanted@example.test",
        "resend": (202, {"detail": "Verification message sent to wanted@example.test."}),
    }


def test_a_taken_address_is_sent_no_link(
    vera: User, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """The address's holder never asked for anything, so is mailed nothing."""
    UserFactory(email=NEW)
    client = signed_in(vera)

    ask(client)
    client.post(RESEND_URL)

    assert mails_to(NEW) == []


def test_a_taken_address_still_tells_the_old_address(
    vera: User, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """The account's own address hears of the request as for any other."""
    UserFactory(email=NEW)

    ask(signed_in(vera))

    assert [m.subject for m in mails_to(OLD)] == ["CalDART: your email address is changing"]


def test_a_failure_after_the_pending_address_is_saved_rolls_it_back(
    vera: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The request is one transaction: a failure once the address is saved leaves none."""

    def explode(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("audit exploded")

    monkeypatch.setattr("apps.accounts.email_change.audit.record", explode)
    with pytest.raises(RuntimeError, match="audit exploded"):
        request_email_change(vera, vera, NEW)

    vera.refresh_from_db()
    assert vera.pending_email == ""


def test_the_change_mails_wait_for_the_caller(vera: User, run_on_commit: None) -> None:
    """Given a list, the request queues its two messages there rather than sending."""
    mailings: list[Mailing] = []

    request_email_change(vera, vera, NEW, mailings=mailings)

    assert (len(mailings), mail.outbox) == (2, [])


def test_an_administrator_cannot_change_their_own_address_on_the_record(
    account_admin: User, signed_in: Callable[[User], APIClient]
) -> None:
    """The member record asks for no password, so one's own address changes elsewhere."""
    response = signed_in(account_admin).patch(
        f"{MEMBERS_URL}/{account_admin.pk}", {"email": "mine@example.test"}, format="json"
    )

    assert (response.status_code, response.json()) == (
        400,
        {"email": [OWN_ADDRESS_ON_RECORD_REFUSED]},
    )


def test_deactivating_drops_a_waiting_change(
    vera: User, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """An account switched off waits for no new address."""
    client = signed_in(vera)
    ask(client)

    client.post(DEACTIVATE_URL, {"current_password": DEFAULT_PASSWORD})

    vera.refresh_from_db()
    assert vera.pending_email == ""


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
