"""Changing the sign-in address: the recovery address, and a new password's effect.

A change of address waits for its new owner: the account keeps signing in with the
address it has until the link mailed to the new one is followed, and the address it had
is told, with a link that undoes the change.  ``docs/developer/api-auth.rst`` describes
the endpoints and ``docs/user/member/change-email.rst`` what a member sees.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from io import StringIO
from typing import cast

import freezegun
import pytest
from django.contrib.admin import site
from django.core import mail, signing
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import RequestFactory
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.admin import UserAdmin
from apps.accounts.email_change import (
    ADDRESS_TAKEN,
    EMAIL_CHANGE_UNDO_SALT,
    UNDO_INVALID,
    make_undo_token,
    recent_change_refused,
)
from apps.accounts.models import AccountKind, User
from apps.accounts.services import make_reset_token, replace_password
from apps.payments.donations import DonorFields, donor_for
from apps.payments.models import MandateStatus
from tests.conftest import (
    CHANGE_URL as PASSWORD_CHANGE_URL,
)
from tests.conftest import (
    EMAIL_CHANGE_URL,
    EMAIL_RESEND_URL,
    EMAIL_UNDO_URL,
    EMAIL_VERIFY_URL,
    GOOD_PASSWORD,
    REGISTER_URL,
    RESET_CONFIRM_URL,
    VERA_NEW,
    VERA_OLD,
    ask,
    change_and_confirm,
    confirm_token,
    link_token,
    mails_to,
    register_payload,
    undo_token,
)
from tests.factories import DEFAULT_PASSWORD, RenewalMandateFactory, UserFactory

pytestmark = pytest.mark.django_db

CHANGE_URL = EMAIL_CHANGE_URL
VERIFY_URL = EMAIL_VERIFY_URL
UNDO_URL = EMAIL_UNDO_URL
RESEND_URL = EMAIL_RESEND_URL
MEMBERS_URL = "/api/v1/admin/members"

OLD = VERA_OLD
NEW = VERA_NEW
INVALID_LINK = "That verification link is invalid or has expired."


@pytest.fixture
def signed_in(signed_in_client: Callable[[User], APIClient]) -> Callable[[User], APIClient]:
    """Sign ``user`` in on the shared API client and return the client."""
    return signed_in_client


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


def test_undo_closes_the_account_when_the_old_address_is_taken(
    vera: User, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """Whoever holds the address the account was moved to cannot reset their way in."""
    _taken_undo(vera, signed_in(vera))

    assert (vera.is_active, vera.reactivation_blocked) == (False, True)


def test_closing_the_account_cancels_its_standing_authorities(
    vera: User, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """A closed account is charged nothing further, as after any deactivation."""
    mandate = RenewalMandateFactory(user=vera)

    _taken_undo(vera, signed_in(vera))

    mandate.refresh_from_db()
    assert mandate.status == MandateStatus.CANCELED


def test_undo_mails_no_reset_link_when_the_old_address_is_taken(
    vera: User, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """The account is closed, so there is nothing to reset; the owner asks the office."""
    mail.outbox.clear()
    _taken_undo(vera, signed_in(vera))

    assert [m.subject for m in mail.outbox if "reset" in str(m.subject)] == []


def test_a_closed_account_cannot_be_reset_by_whoever_holds_its_address(
    vera: User, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """A reset request for the address the account was moved to mails nothing."""
    _taken_undo(vera, signed_in(vera))
    mail.outbox.clear()

    APIClient().post("/api/v1/auth/password/reset", {"email": NEW})

    assert mails_to(NEW) == []


# --------------------------------------------------------------------------
# Notices during the window, and the reserved address elsewhere
# --------------------------------------------------------------------------
def test_a_password_change_meanwhile_tells_the_recovery_address(
    vera: User, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """The notice also goes to the address the account left, with an undo link."""
    client = signed_in(vera)
    change_and_confirm(vera, client)
    mail.outbox.clear()

    client.post(
        PASSWORD_CHANGE_URL,
        {"current_password": DEFAULT_PASSWORD, "new_password": GOOD_PASSWORD},
    )

    assert "/portal/undo-email-change?token=" in str(mails_to(OLD)[-1].body)


def test_registering_the_recovery_address_points_to_the_undo(
    vera: User, api_client: APIClient, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """The notice for a reserved address does not offer a sign-in it cannot do."""
    change_and_confirm(vera, signed_in(vera))
    api_client.logout()
    mail.outbox.clear()

    api_client.post(REGISTER_URL, register_payload(email=OLD))

    assert "/portal/login" not in str(mails_to(OLD)[-1].body)


def test_a_gift_from_the_recovery_address_is_receipted_there(
    vera: User, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """The receipt goes to the address the gift was made with."""
    change_and_confirm(vera, signed_in(vera))
    cache.clear()
    mail.outbox.clear()
    gift = (
        APIClient()
        .post(
            "/api/v1/donations/checkout",
            {
                "first_name": "Vera",
                "last_name": "Quill",
                "email": OLD,
                "contribution_cents": 2_000,
                "provider": "mock",
            },
            format="json",
        )
        .json()
    )

    APIClient().post(
        "/api/v1/donations/mock/complete",
        {"payment_id": gift["payment_id"], "token": gift["token"]},
        format="json",
    )

    assert [m.to for m in mail.outbox if "receipt" in str(m.subject)] == [[OLD]]


def test_create_admin_refuses_the_recovery_address(
    vera: User, signed_in: Callable[[User], APIClient], run_on_commit: None
) -> None:
    """The command cannot make an account out of an address kept for recovery."""
    change_and_confirm(vera, signed_in(vera))

    with pytest.raises(CommandError, match="kept for its owner to undo the change"):
        call_command("create_admin", email=OLD, stdout=StringIO(), stderr=StringIO())


def test_the_django_admin_shows_the_address_read_only(vera: User, rf: RequestFactory) -> None:
    """A change of address cannot bypass its link from the Django admin."""
    model_admin = UserAdmin(User, site)

    assert "email" in model_admin.get_readonly_fields(rf.get("/"), vera)
