"""The notification endpoints: the event catalog and the subscriptions.

``/notifications/*`` is the account administrator's own; a system administrator passes
as always.  A recipient with an account is bound to it and every event chosen must be
one a role of that account may receive; an address outside CalDART needs the caller's
confirmation.  One address holds one subscription.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import ACCOUNT_ADMIN, MEMBER, SYSTEM_ADMIN, TREASURER
from apps.notifications.api.serializers import NotificationSubscriptionCreateSerializer
from apps.notifications.events import EVENTS
from apps.notifications.models import NotificationSubscription
from tests.conftest import role_matrix
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

EVENTS_URL = "/api/v1/notifications/events"
SUBSCRIPTIONS_URL = "/api/v1/notifications/subscriptions"

#: What an address outside CalDART is refused with until the caller confirms it.
CONFIRM_MESSAGE = "Check the box to confirm this address may receive these notifications."


def subscription_url(subscription: NotificationSubscription) -> str:
    """The detail endpoint of ``subscription``."""
    return f"{SUBSCRIPTIONS_URL}/{subscription.pk}"


def subscribe(email: str, events: list[str], **fields: object) -> NotificationSubscription:
    """A saved subscription of ``email`` to ``events``, with any other ``fields``."""
    return NotificationSubscription.objects.create(recipient_email=email, events=events, **fields)


@pytest.fixture
def cashier() -> User:
    """A treasurer named Cass Till, who may hear about money and nothing else."""
    return UserFactory(
        email="cashier@example.test",
        first_name="Cass",
        last_name="Till",
        roles=[MEMBER, TREASURER],
    )


# -- who may call them ------------------------------------------------------------
@pytest.mark.parametrize(("role", "allowed"), role_matrix(ACCOUNT_ADMIN, SYSTEM_ADMIN))
@pytest.mark.parametrize("url", [EVENTS_URL, SUBSCRIPTIONS_URL])
def test_the_notification_endpoints_are_the_account_administrators(
    api_client: APIClient, all_role_users: dict[str, User], role: str, allowed: bool, url: str
) -> None:
    """An account administrator and a system administrator may read them; nobody else."""
    api_client.force_login(all_role_users[role])

    response = api_client.get(url)

    assert response.status_code == (200 if allowed else 403)


@pytest.mark.parametrize(("role", "allowed"), role_matrix(ACCOUNT_ADMIN, SYSTEM_ADMIN))
@pytest.mark.parametrize(("method", "success"), [("post", 201), ("patch", 200), ("delete", 204)])
def test_only_the_account_administrators_may_change_a_subscription(
    api_client: APIClient,
    all_role_users: dict[str, User],
    role: str,
    allowed: bool,
    method: str,
    success: int,
) -> None:
    """Setting one up, editing it, and deleting it are refused to every other role."""
    subscription = subscribe("outside@example.test", ["signed_up"])
    url, body = {
        "post": (
            SUBSCRIPTIONS_URL,
            {"recipient_email": "new@example.test", "events": ["signed_up"], "confirmed": True},
        ),
        "patch": (subscription_url(subscription), {"is_active": False}),
        "delete": (subscription_url(subscription), None),
    }[method]
    api_client.force_login(all_role_users[role])

    response = getattr(api_client, method)(url, body, format="json")

    assert response.status_code == (success if allowed else 403)


@pytest.mark.parametrize("url", [EVENTS_URL, SUBSCRIPTIONS_URL])
def test_an_anonymous_caller_is_refused(api_client: APIClient, url: str) -> None:
    """Without a session the answer is 401."""
    assert api_client.get(url).status_code == 401


def test_a_treasurer_may_not_open_a_subscription(api_client: APIClient, treasurer: User) -> None:
    """The detail endpoint is the account administrator's too."""
    subscription = subscribe("outside@example.test", ["donation_received"])
    api_client.force_login(treasurer)

    assert api_client.get(subscription_url(subscription)).status_code == 403


# -- the catalog ---------------------------------------------------------------------
def test_the_events_are_listed_in_catalog_order(account_admin_client: APIClient) -> None:
    """``GET /notifications/events`` lists every event's slug, in catalog order."""
    rows = account_admin_client.get(EVENTS_URL).json()

    assert [row["slug"] for row in rows] == list(EVENTS)


def test_an_event_carries_its_label_category_description_and_roles(
    account_admin_client: APIClient,
) -> None:
    """Each entry is ``{slug, label, category, description, roles}``."""
    first = account_admin_client.get(EVENTS_URL).json()[0]

    assert first == {
        "slug": "signed_up",
        "label": "Sign-up",
        "category": "Membership",
        "description": "Somebody registered on the site, as a member or as a friend.",
        "roles": ["account_admin", "user_admin"],
    }


# -- listing and reading ---------------------------------------------------------------
def test_the_list_is_every_subscription_by_address(account_admin_client: APIClient) -> None:
    """Every subscription is listed, unpaginated, in address order."""
    zed = subscribe("zed@example.test", ["signed_up"])
    amy = subscribe("amy@example.test", ["signed_up"])

    rows = account_admin_client.get(SUBSCRIPTIONS_URL).json()

    assert [row["id"] for row in rows] == [amy.pk, zed.pk]


def test_a_subscription_reads_as_its_documented_body(
    account_admin_client: APIClient, account_admin: User, cashier: User
) -> None:
    """The body names the recipient, the events, the state, and who set it up."""
    subscription = subscribe(
        cashier.email,
        ["donation_received"],
        recipient_user=cashier,
        created_by=account_admin,
    )

    body = account_admin_client.get(subscription_url(subscription)).json()

    assert body == {
        "id": subscription.pk,
        "recipient_user": cashier.pk,
        "recipient_name": "Cass Till",
        "recipient_email": "cashier@example.test",
        "events": ["donation_received"],
        "is_active": True,
        "created_by_name": "Zoe Yeager",
        "created_at": body["created_at"],
        "updated_at": body["updated_at"],
    }


def test_a_bare_address_reads_with_no_name(account_admin_client: APIClient) -> None:
    """An address outside CalDART has a blank ``recipient_name`` and no account."""
    subscription = subscribe("outside@example.test", ["signed_up"])

    body = account_admin_client.get(subscription_url(subscription)).json()

    assert (body["recipient_user"], body["recipient_name"]) == (None, "")


# -- setting one up ----------------------------------------------------------------------
def test_an_outside_address_needs_confirming(account_admin_client: APIClient) -> None:
    """An address no account holds is refused under ``confirmed`` until checked."""
    response = account_admin_client.post(
        SUBSCRIPTIONS_URL,
        {"recipient_email": "outside@example.test", "events": ["signed_up"]},
        format="json",
    )

    assert (response.status_code, response.json()) == (400, {"confirmed": [CONFIRM_MESSAGE]})


def test_a_confirmed_outside_address_is_subscribed(
    account_admin_client: APIClient, account_admin: User
) -> None:
    """With ``confirmed`` it is set up by the caller, unbound, and active."""
    response = account_admin_client.post(
        SUBSCRIPTIONS_URL,
        {
            "recipient_email": "Outside@Example.test",
            "events": ["signed_up"],
            "confirmed": True,
        },
        format="json",
    )

    body = response.json()
    assert response.status_code == 201
    assert (
        body["recipient_email"],
        body["recipient_user"],
        body["is_active"],
        body["created_by_name"],
    ) == ("outside@example.test", None, True, account_admin.display_name)


def test_the_events_are_kept_in_catalog_order_once_each(account_admin_client: APIClient) -> None:
    """The chosen events are stored in the catalog's order, each once."""
    response = account_admin_client.post(
        SUBSCRIPTIONS_URL,
        {
            "recipient_email": "outside@example.test",
            "events": ["aircraft_added", "signed_up", "aircraft_added"],
            "confirmed": True,
        },
        format="json",
    )

    assert response.json()["events"] == ["signed_up", "aircraft_added"]


def test_an_address_an_account_holds_is_bound_to_it(
    account_admin_client: APIClient, cashier: User
) -> None:
    """An account's address, in any case, binds the subscription with no confirmation."""
    response = account_admin_client.post(
        SUBSCRIPTIONS_URL,
        {"recipient_email": "CASHIER@example.test", "events": ["donation_received"]},
        format="json",
    )

    body = response.json()
    assert (response.status_code, body["recipient_user"], body["recipient_email"]) == (
        201,
        cashier.pk,
        "cashier@example.test",
    )


def test_an_account_is_refused_an_event_its_roles_do_not_allow(
    account_admin_client: APIClient, cashier: User
) -> None:
    """The first refused event, in catalog order, is named under ``events``."""
    response = account_admin_client.post(
        SUBSCRIPTIONS_URL,
        {
            "recipient_email": cashier.email,
            "events": ["donation_received", "aircraft_added", "signed_up"],
        },
        format="json",
    )

    assert (response.status_code, response.json()) == (
        400,
        {"events": ["Cass Till does not hold a role that may receive Sign-up."]},
    )


def test_an_address_already_subscribed_is_refused(account_admin_client: APIClient) -> None:
    """One address holds one subscription, compared without regard to case."""
    subscribe("outside@example.test", ["signed_up"])

    response = account_admin_client.post(
        SUBSCRIPTIONS_URL,
        {"recipient_email": "OUTSIDE@example.test", "events": ["became_member"], "confirmed": True},
        format="json",
    )

    assert (response.status_code, response.json()) == (
        400,
        {"recipient_email": ["This address already has a subscription."]},
    )


@pytest.mark.parametrize(
    ("events", "message"),
    [
        ([], "Choose at least one event."),
        (["signed_up", "sky_fell"], "Unknown event 'sky_fell'."),
    ],
    ids=["empty", "unknown"],
)
def test_the_events_must_be_real_and_at_least_one(
    account_admin_client: APIClient, events: list[str], message: str
) -> None:
    """An empty list and an unknown slug are refused under ``events``."""
    response = account_admin_client.post(
        SUBSCRIPTIONS_URL,
        {"recipient_email": "outside@example.test", "events": events, "confirmed": True},
        format="json",
    )

    assert (response.status_code, response.json()) == (400, {"events": [message]})


def test_an_address_subscribed_while_the_post_was_checked_is_refused(
    account_admin_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second request that passed the check first still answers 400, not a crash."""
    monkeypatch.setattr(
        NotificationSubscriptionCreateSerializer,
        "validate_recipient_email",
        lambda self, value: value.strip(),
    )
    subscribe("outside@example.test", ["signed_up"])

    response = account_admin_client.post(
        SUBSCRIPTIONS_URL,
        {"recipient_email": "outside@example.test", "events": ["signed_up"], "confirmed": True},
        format="json",
    )

    assert (response.status_code, response.json()) == (
        400,
        {"recipient_email": ["This address already has a subscription."]},
    )


def test_an_invalid_address_is_refused(account_admin_client: APIClient) -> None:
    """A string that is not an address is refused under ``recipient_email``."""
    response = account_admin_client.post(
        SUBSCRIPTIONS_URL,
        {"recipient_email": "not-an-address", "events": ["signed_up"], "confirmed": True},
        format="json",
    )

    assert (response.status_code, list(response.json())) == (400, ["recipient_email"])


# -- changing one ------------------------------------------------------------------------
def test_a_patch_changes_the_events(account_admin_client: APIClient) -> None:
    """``PATCH`` replaces the events, kept in catalog order."""
    subscription = subscribe("outside@example.test", ["signed_up"])

    response = account_admin_client.patch(
        subscription_url(subscription),
        {"events": ["became_member", "signed_up"]},
        format="json",
    )

    subscription.refresh_from_db()
    assert (response.status_code, subscription.events) == (200, ["signed_up", "became_member"])


def test_a_patch_pauses_a_subscription(account_admin_client: APIClient) -> None:
    """``is_active`` false pauses it."""
    subscription = subscribe("outside@example.test", ["signed_up"])

    response = account_admin_client.patch(
        subscription_url(subscription), {"is_active": False}, format="json"
    )

    subscription.refresh_from_db()
    assert (response.status_code, subscription.is_active) == (200, False)


def test_a_patch_cannot_move_the_subscription_to_another_address(
    account_admin_client: APIClient,
) -> None:
    """The recipient is read-only once set up."""
    subscription = subscribe("outside@example.test", ["signed_up"])

    response = account_admin_client.patch(
        subscription_url(subscription), {"recipient_email": "else@example.test"}, format="json"
    )

    subscription.refresh_from_db()
    assert (response.status_code, subscription.recipient_email) == (200, "outside@example.test")


def test_a_patch_cannot_add_an_event_the_account_may_not_receive(
    account_admin_client: APIClient, cashier: User
) -> None:
    """Adding an event the account's roles do not allow is refused under ``events``."""
    subscription = subscribe(cashier.email, ["donation_received"], recipient_user=cashier)

    response = account_admin_client.patch(
        subscription_url(subscription),
        {"events": ["donation_received", "roles_changed"]},
        format="json",
    )

    assert (response.status_code, response.json()) == (
        400,
        {"events": ["Cass Till does not hold a role that may receive Roles changed."]},
    )


def test_a_patch_may_drop_events_from_an_account_that_lost_a_role(
    account_admin_client: APIClient, cashier: User
) -> None:
    """Removing events never needs the roles the remaining ones would."""
    subscription = subscribe(
        cashier.email, ["signed_up", "donation_received"], recipient_user=cashier
    )

    response = account_admin_client.patch(
        subscription_url(subscription), {"events": ["signed_up"]}, format="json"
    )

    assert response.status_code == 200


def test_resuming_for_an_account_that_may_not_receive_an_event_is_refused(
    account_admin_client: APIClient, cashier: User
) -> None:
    """Resuming checks every event the subscription lists."""
    subscription = subscribe(cashier.email, ["signed_up"], recipient_user=cashier, is_active=False)

    response = account_admin_client.patch(
        subscription_url(subscription), {"is_active": True}, format="json"
    )

    assert (response.status_code, response.json()) == (
        400,
        {"events": ["Cass Till does not hold a role that may receive Sign-up."]},
    )


def test_a_patch_binds_a_bare_address_an_account_has_since_taken(
    account_admin_client: APIClient,
) -> None:
    """The account that took the address is bound, under its own address in lower case."""
    subscription = subscribe("taken@example.test", ["donation_received"])
    taker = UserFactory(email="Taken@example.test", roles=[MEMBER, TREASURER])

    response = account_admin_client.patch(
        subscription_url(subscription), {"is_active": False}, format="json"
    )

    subscription.refresh_from_db()
    assert (response.status_code, subscription.recipient_user, subscription.recipient_email) == (
        200,
        taker,
        "taken@example.test",
    )


def test_a_patch_checks_the_roles_of_the_account_that_took_a_bare_address(
    account_admin_client: APIClient,
) -> None:
    """Once bound, adding an event the new account's roles refuse answers 400."""
    subscription = subscribe("taken@example.test", ["donation_received"])
    UserFactory(
        email="Taken@example.test", first_name="Tam", last_name="Ken", roles=[MEMBER, TREASURER]
    )

    response = account_admin_client.patch(
        subscription_url(subscription),
        {"events": ["donation_received", "signed_up"]},
        format="json",
    )

    assert (response.status_code, response.json()) == (
        400,
        {"events": ["Tam Ken does not hold a role that may receive Sign-up."]},
    )


def test_a_patch_keeps_the_stored_address_when_another_subscription_holds_the_new_one(
    account_admin_client: APIClient, cashier: User
) -> None:
    """An account moved to an address with its own subscription leaves this one be."""
    bound = subscribe(cashier.email, ["donation_received"], recipient_user=cashier)
    subscribe("moved@example.test", ["donation_received"])
    cashier.email = "moved@example.test"
    cashier.save(update_fields=["email"])

    response = account_admin_client.patch(
        subscription_url(bound), {"is_active": False}, format="json"
    )

    bound.refresh_from_db()
    assert (response.status_code, bound.recipient_email, bound.is_active) == (
        200,
        "cashier@example.test",
        False,
    )


def test_a_patch_to_no_events_is_refused(account_admin_client: APIClient) -> None:
    """A subscription keeps at least one event."""
    subscription = subscribe("outside@example.test", ["signed_up"])

    response = account_admin_client.patch(
        subscription_url(subscription), {"events": []}, format="json"
    )

    assert (response.status_code, response.json()) == (
        400,
        {"events": ["Choose at least one event."]},
    )


def test_a_put_is_not_allowed(account_admin_client: APIClient) -> None:
    """The detail endpoint takes ``GET``, ``PATCH`` and ``DELETE`` only."""
    subscription = subscribe("outside@example.test", ["signed_up"])

    response = account_admin_client.put(
        subscription_url(subscription), {"events": ["signed_up"]}, format="json"
    )

    assert response.status_code == 405


def test_a_delete_removes_the_subscription(account_admin_client: APIClient) -> None:
    """``DELETE`` answers 204 and the row is gone."""
    subscription = subscribe("outside@example.test", ["signed_up"])

    response = account_admin_client.delete(subscription_url(subscription))

    assert (response.status_code, NotificationSubscription.objects.count()) == (204, 0)


def test_a_missing_subscription_is_404(account_admin_client: APIClient) -> None:
    """An id no subscription carries answers 404."""
    assert account_admin_client.get(f"{SUBSCRIPTIONS_URL}/999999").status_code == 404
