"""The public donation page: its endpoints, the donor account behind a gift, and the page.

A visitor who is not signed in gives through ``/donate/``.  The gift makes (or
finds) a donor account by email address, and the anonymous caller proves it started
the payment with a signed token.  The docs page is ``docs/developer/api-payments.rst``
("Public donations") and ``docs/user/member/public-website.rst``.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Generator
from types import SimpleNamespace
from typing import Any, cast

import httpx
import pytest
import respx
import stripe
from django.core import mail, signing
from django.core.cache import cache
from django.core.mail import EmailMultiAlternatives
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from freezegun import freeze_time
from pytest_django import Settings
from rest_framework.test import APIClient

from apps.accounts.models import AccountKind, User
from apps.cms.models import DonatePage, HomePage, StandardPage
from apps.darts.models import Dart
from apps.members.models import CALIFORNIA_COUNTIES, US_STATE_CHOICES, MemberProfile
from apps.payments.donations import (
    DONATION_TOKEN_MAX_AGE,
    DONATION_TOKEN_SALT,
    HAS_ACCOUNT_MESSAGE,
    NO_SUCH_PAYMENT,
    DonationTokenError,
    DonorFields,
    HasAccountError,
    donation_token,
    donor_for,
    payment_for_token,
    start_donation,
)
from apps.payments.models import CONTRIBUTION_TIERS, Payment, PaymentProvider, PaymentStatus
from apps.payments.providers import stripe as stripe_provider
from tests.factories import DartFactory, PaymentFactory, UserFactory

pytestmark = pytest.mark.django_db

CONFIG_URL = "/api/v1/donations/config"
CHECKOUT_URL = "/api/v1/donations/checkout"
MOCK_COMPLETE_URL = "/api/v1/donations/mock/complete"
STRIPE_CONFIRM_URL = "/api/v1/donations/stripe/confirm"
PAYPAL_CAPTURE_URL = "/api/v1/donations/paypal/capture"

DONOR_EMAIL = "pat.giver@example.test"

#: What every lookup that the token does not prove answers.
NOT_FOUND = {"detail": "No such payment."}

PAYPAL_SANDBOX = "https://api-m.sandbox.paypal.com"
PAYPAL_ORDERS_URL = f"{PAYPAL_SANDBOX}/v2/checkout/orders"
PAYPAL_OAUTH_URL = f"{PAYPAL_SANDBOX}/v1/oauth2/token"


def status_url(payment_id: int) -> str:
    """The URL of ``GET /donations/{id}`` for ``payment_id``."""
    return f"/api/v1/donations/{payment_id}"


def donor_fields(**overrides: Any) -> DonorFields:
    """The four fields every gift needs, with ``overrides`` applied."""
    fields = {
        "first_name": "Pat",
        "last_name": "Giver",
        "email": DONOR_EMAIL,
        "phone": "(415) 555-0100",
        **overrides,
    }
    return cast(DonorFields, fields)


def gift(**overrides: Any) -> dict[str, Any]:
    """A ``POST /donations/checkout`` body for a $100 mock gift, with ``overrides``."""
    return {**donor_fields(), "contribution_cents": 10_000, "provider": "mock", **overrides}


@pytest.fixture(autouse=True)
def empty_throttle_cache() -> Generator[None]:
    """The throttle counters are shared state; no test may inherit them."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def give(api_client: APIClient) -> Callable[..., dict[str, Any]]:
    """``give(**overrides)`` starts a mock gift and returns the 201 body."""

    def start(**overrides: Any) -> dict[str, Any]:
        response = api_client.post(CHECKOUT_URL, gift(**overrides), format="json")
        assert response.status_code == 201, response.content
        body: dict[str, Any] = response.json()
        return body

    return start


def complete(api_client: APIClient, body: dict[str, Any]) -> None:
    """Settle the mock gift ``give`` started, ignoring the response body."""
    response = api_client.post(
        MOCK_COMPLETE_URL,
        {"payment_id": body["payment_id"], "token": body["token"]},
        format="json",
    )
    assert response.status_code == 200, response.content


# ---------------------------------------------------------------- donor_for
def test_donor_for_creates_a_donor_with_no_role_and_no_password() -> None:
    """A new address becomes a donor account that holds no role and cannot sign in."""
    donor = donor_for(donor_fields())

    assert (donor.kind, donor.roles, donor.has_usable_password()) == (
        AccountKind.DONOR,
        [],
        False,
    )


def test_donor_for_leaves_the_new_donor_unverified() -> None:
    """A donor's address is never verified: nothing is mailed to prove it."""
    donor = donor_for(donor_fields())

    assert donor.email_verified_at is None


def test_donor_for_sends_the_new_donor_no_email() -> None:
    """Making a donor sends nothing: no verification, no invitation."""
    donor_for(donor_fields())

    assert mail.outbox == []


def test_donor_for_leaves_a_new_donor_unnamed() -> None:
    """A new donor's names are not written until a gift naming them settles.

    ``donor_for`` only finds or makes the account: it is not the unauthenticated
    caller's word alone that should ever land on the account, so the names wait
    for :func:`apps.payments.donations.apply_donor_fields`.
    """
    donor = donor_for(donor_fields())

    assert (donor.first_name, donor.last_name) == ("", "")


def test_donor_for_writes_no_profile_yet() -> None:
    """A new donor gets no profile row until a gift naming them settles."""
    donor = donor_for(donor_fields())

    assert MemberProfile.objects.filter(user=donor).exists() is False


def test_donor_for_finds_an_existing_donor_whatever_the_case_of_the_address() -> None:
    """A second gift from the same address, in any case, reuses the donor."""
    first = donor_for(donor_fields())
    second = donor_for(donor_fields(email=DONOR_EMAIL.upper()))

    assert (second.pk, User.objects.count()) == (first.pk, 1)


def advisory_locks(captured: CaptureQueriesContext) -> list[str]:
    """The advisory-lock statements among ``captured``, as sent to the database."""
    return [query["sql"] for query in captured if "pg_advisory_xact_lock" in query["sql"]]


def test_gifts_from_one_address_in_any_case_wait_on_one_lock() -> None:
    """Two first gifts from one address are serialized, whatever the case of each.

    Each call takes the same transaction-scoped advisory lock before it looks the
    address up, so a second gift racing the first finds the donor the first made
    instead of making another or failing on the unique address.
    """
    with CaptureQueriesContext(connection) as first:
        donor_for(donor_fields(email="Rosa@Example.test"))
    with CaptureQueriesContext(connection) as second:
        donor_for(donor_fields(email="rosa@example.test"))

    assert (len(advisory_locks(first)), advisory_locks(first)) == (1, advisory_locks(second))


def test_donor_for_does_not_touch_an_existing_donors_stored_details() -> None:
    """Finding an existing donor writes nothing: it takes no details to be found.

    An unauthenticated caller who only knows a donor's address must not be able to
    overwrite what an earlier, completed gift recorded merely by starting a new
    checkout; see the settle-time tests below for when the new details do land.
    """
    first = donor_for(donor_fields())
    first.first_name = "Patricia"
    first.save(update_fields=["first_name"])
    MemberProfile.objects.create(user=first, phone="415-555-0100", city="Petaluma")

    donor_for(donor_fields(first_name="Someone Else", phone="707-555-0199", city=""))

    first.refresh_from_db()
    profile = MemberProfile.objects.get(user=first)
    assert (first.first_name, profile.phone, profile.city) == (
        "Patricia",
        "415-555-0100",
        "Petaluma",
    )


@pytest.mark.parametrize("kind", [AccountKind.MEMBER, AccountKind.FRIEND])
@pytest.mark.parametrize("is_active", [True, False], ids=["active", "deactivated"])
def test_donor_for_refuses_the_address_of_a_member_or_a_friend(
    kind: AccountKind, is_active: bool
) -> None:
    """An address that already signs in to the portal, active or not, is refused."""
    UserFactory(email=DONOR_EMAIL, kind=kind, is_active=is_active)

    with pytest.raises(HasAccountError, match=re.escape(HAS_ACCOUNT_MESSAGE)):
        donor_for(donor_fields(email=DONOR_EMAIL.upper()))


# ------------------------------------------------------------------- tokens
def test_a_donation_token_names_its_payment() -> None:
    """``payment_for_token`` answers the payment the token was minted for."""
    payment = PaymentFactory()

    assert payment_for_token(payment.pk, donation_token(payment)) == payment


def test_a_token_for_another_payment_is_refused() -> None:
    """A good token is no proof for a payment it was not minted for."""
    mine, theirs = PaymentFactory(), PaymentFactory()

    with pytest.raises(DonationTokenError, match=re.escape(NO_SUCH_PAYMENT)):
        payment_for_token(theirs.pk, donation_token(mine))


def test_a_tampered_token_is_refused() -> None:
    """A token whose signature does not match is refused."""
    payment = PaymentFactory()

    with pytest.raises(DonationTokenError, match=re.escape(NO_SUCH_PAYMENT)):
        payment_for_token(payment.pk, donation_token(payment) + "x")


def test_an_expired_token_is_refused() -> None:
    """A token older than an hour is refused."""
    payment = PaymentFactory()
    with freeze_time("2026-09-25 12:00:00") as clock:
        token = donation_token(payment)
        clock.tick(DONATION_TOKEN_MAX_AGE + 1)
        with pytest.raises(DonationTokenError, match=re.escape(NO_SUCH_PAYMENT)):
            payment_for_token(payment.pk, token)


def test_a_token_is_signed_with_the_donation_salt() -> None:
    """The token reads back under ``payments.donation`` and names the payment."""
    payment = PaymentFactory()

    assert signing.loads(donation_token(payment), salt=DONATION_TOKEN_SALT) == {
        "payment": payment.pk
    }


# ------------------------------------------------------------------- config
def test_the_config_is_open_to_anyone(api_client: APIClient) -> None:
    """``GET /donations/config`` answers a visitor who is not signed in."""
    assert api_client.get(CONFIG_URL).status_code == 200


def test_the_config_names_the_providers_and_the_amounts(api_client: APIClient) -> None:
    """The config carries the providers, keys, tiers and the largest gift."""
    body = api_client.get(CONFIG_URL).json()

    assert {key: body[key] for key in ("providers", "max_contribution_cents")} == {
        "providers": ["mock"],
        "max_contribution_cents": 9_999_900,
    }


def test_the_config_offers_every_tier(api_client: APIClient) -> None:
    """The tiers are the checkout's own, in order."""
    body = api_client.get(CONFIG_URL).json()

    assert body["contribution_tiers"] == [dict(tier) for tier in CONTRIBUTION_TIERS]


def test_the_config_lists_the_counties_and_the_states(api_client: APIClient) -> None:
    """Counties arrive as names and states as ``{value, label}`` pairs."""
    body = api_client.get(CONFIG_URL).json()

    assert (body["counties"], body["states"][0], len(body["states"])) == (
        list(CALIFORNIA_COUNTIES),
        {"value": "AL", "label": "Alabama"},
        len(US_STATE_CHOICES),
    )


def test_the_config_lists_only_active_darts(api_client: APIClient) -> None:
    """Only the DARTs a profile may name are offered."""
    active = DartFactory(name="Bay Area")
    closed = DartFactory(name="Closed", is_active=False)

    offered = api_client.get(CONFIG_URL).json()["darts"]

    assert (
        {"id": active.pk, "name": "Bay Area"} in offered,
        {"id": closed.pk, "name": "Closed"} in offered,
    ) == (True, False)


# ----------------------------------------------------------------- checkout
def test_a_gift_makes_a_pending_contribution_for_the_donor(
    give: Callable[..., dict[str, Any]],
) -> None:
    """The checkout starts a pending payment of the gift alone, with no plan."""
    body = give()

    payment = Payment.objects.get(pk=body["payment_id"])
    assert (
        payment.user.email,
        payment.plan,
        payment.amount_cents,
        payment.contribution_cents,
        payment.status,
    ) == (DONOR_EMAIL, None, 10_000, 10_000, PaymentStatus.PENDING)


def test_a_gift_answers_the_provider_and_a_token_for_its_payment(
    give: Callable[..., dict[str, Any]],
) -> None:
    """The 201 carries the provider's start, plus a token that proves the payment."""
    body = give()

    assert (
        body["provider"],
        body["client"],
        signing.loads(body["token"], salt="payments.donation"),
    ) == (
        "mock",
        {},
        {"payment": body["payment_id"]},
    )


def test_a_second_gift_from_the_same_address_reuses_the_donor(
    give: Callable[..., dict[str, Any]],
) -> None:
    """Two gifts from one address make one donor with two payments."""
    give()
    give(email=DONOR_EMAIL.upper())

    assert (User.objects.count(), Payment.objects.count()) == (1, 2)


def test_a_gift_from_a_members_address_is_refused(api_client: APIClient, member: User) -> None:
    """An address that belongs to a member answers 400 with the ``has_account`` code."""
    response = api_client.post(CHECKOUT_URL, gift(email=member.email), format="json")

    assert (response.status_code, response.json()) == (
        400,
        {
            "email": ["An account already uses that email address. Sign in to donate."],
            "code": "has_account",
        },
    )


def test_a_refused_gift_writes_nothing(api_client: APIClient, friend: User) -> None:
    """A gift refused for a friend's address leaves no payment behind."""
    api_client.post(CHECKOUT_URL, gift(email=friend.email), format="json")

    assert Payment.objects.count() == 0


@pytest.mark.parametrize("field", ["first_name", "last_name", "email", "phone"])
def test_each_required_field_is_required(api_client: APIClient, field: str) -> None:
    """A gift without a name, an email address or a phone number is refused."""
    body = gift()
    del body[field]

    response = api_client.post(CHECKOUT_URL, body, format="json")

    assert (response.status_code, list(response.json())) == (400, [field])


def test_a_gift_of_nothing_is_refused(api_client: APIClient) -> None:
    """A gift needs an amount, and the refusal says so against ``contribution_cents``."""
    response = api_client.post(CHECKOUT_URL, gift(contribution_cents=0), format="json")

    assert (response.status_code, response.json()) == (
        400,
        {"contribution_cents": ["Choose an amount to give."]},
    )


def test_a_gift_above_the_ceiling_is_refused(api_client: APIClient) -> None:
    """A gift larger than the checkout accepts is refused by field."""
    response = api_client.post(CHECKOUT_URL, gift(contribution_cents=10_000_000), format="json")

    assert (response.status_code, response.json()) == (
        400,
        {"contribution_cents": ["Ensure this value is less than or equal to 9999900."]},
    )


def test_a_phone_that_is_not_ten_digits_is_refused(api_client: APIClient) -> None:
    """The phone rule is the profile's own."""
    response = api_client.post(CHECKOUT_URL, gift(phone="555-0100"), format="json")

    assert response.json() == {"phone": ["Use a ten-digit number like 415-555-0100."]}


def test_a_pilot_certificate_needs_no_number_from_a_donor(
    api_client: APIClient, give: Callable[..., dict[str, Any]]
) -> None:
    """A donor may name their certificate without giving its number."""
    body = give(pilot_certificate_type="private")
    complete(api_client, body)

    donor = Payment.objects.get(pk=body["payment_id"]).user
    assert MemberProfile.objects.get(user=donor).pilot_certificate_type == "private"


def test_a_gift_names_its_dart_by_id(
    api_client: APIClient, give: Callable[..., dict[str, Any]]
) -> None:
    """``dart_id`` puts the donor on a DART, once the gift that named it settles."""
    dart = DartFactory()
    body = give(dart_id=dart.pk)
    complete(api_client, body)

    donor = Payment.objects.get(pk=body["payment_id"]).user
    assert MemberProfile.objects.get(user=donor).dart == dart


def test_an_unconfigured_provider_is_refused(api_client: APIClient) -> None:
    """A provider this deployment has no keys for is refused by field."""
    response = api_client.post(CHECKOUT_URL, gift(provider="stripe"), format="json")

    assert (response.status_code, response.json()) == (
        400,
        {"provider": "'stripe' is not configured."},
    )


def test_the_checkout_enforces_csrf(csrf_client: APIClient) -> None:
    """An anonymous POST without the CSRF token is refused, as a browser's would be."""
    response = csrf_client.post(CHECKOUT_URL, gift(), format="json")

    assert (response.status_code, response.json()["detail"].startswith("CSRF Failed")) == (
        403,
        True,
    )


def test_the_checkout_accepts_a_csrf_token(
    csrf_client: APIClient, csrf_headers: Callable[[APIClient], dict[str, str]]
) -> None:
    """With the token the portal's fetch wrapper sends, the gift is started."""
    token = csrf_headers(csrf_client)["HTTP_X_CSRFTOKEN"]
    response = csrf_client.post(CHECKOUT_URL, gift(), format="json", HTTP_X_CSRFTOKEN=token)

    assert response.status_code == 201


def test_the_checkout_is_throttled(api_client: APIClient, settings: Settings) -> None:
    """The ``donate`` rate limits how many gifts one address starts."""
    settings.AUTH_THROTTLE_RATES = {"donate": "1/hour"}
    with freeze_time("2026-09-25 12:00:00"):
        api_client.post(CHECKOUT_URL, gift(), format="json")
        response = api_client.post(CHECKOUT_URL, gift(), format="json")

    assert (response.status_code, response.json()) == (
        429,
        {"detail": "Request was throttled. Expected available in 3600 seconds."},
    )


def test_the_config_is_not_throttled(api_client: APIClient, settings: Settings) -> None:
    """Reading the config costs nothing against the ``donate`` rate."""
    settings.AUTH_THROTTLE_RATES = {"donate": "1/hour"}

    statuses = {api_client.get(CONFIG_URL).status_code for _ in range(3)}

    assert statuses == {200}


# ------------------------------------------------------------ confirmation
def test_completing_a_mock_gift_succeeds(
    api_client: APIClient, give: Callable[..., dict[str, Any]]
) -> None:
    """The mock completion with the token settles the payment."""
    body = give()

    response = api_client.post(
        MOCK_COMPLETE_URL,
        {"payment_id": body["payment_id"], "token": body["token"]},
        format="json",
    )

    assert (response.status_code, response.json()["status"]) == (200, "succeeded")


def test_a_pending_gift_leaves_the_new_donors_account_unwritten(
    api_client: APIClient, give: Callable[..., dict[str, Any]]
) -> None:
    """Starting a gift makes the donor account, but writes no name or profile yet."""
    give()

    donor = User.objects.get(email=DONOR_EMAIL)
    assert (donor.first_name, MemberProfile.objects.filter(user=donor).exists()) == ("", False)


def test_completing_a_gift_writes_the_new_donors_name_and_profile(
    api_client: APIClient, give: Callable[..., dict[str, Any]]
) -> None:
    """Settling the gift writes the name and the optional profile fields it named."""
    dart = DartFactory()
    body = give(city="Petaluma", dart_id=dart.pk)

    complete(api_client, body)

    donor = User.objects.get(email=DONOR_EMAIL)
    profile = MemberProfile.objects.get(user=donor)
    assert (donor.first_name, donor.last_name, profile.phone, profile.city, profile.dart) == (
        "Pat",
        "Giver",
        "415-555-0100",
        "Petaluma",
        dart,
    )


def test_completing_a_second_gift_updates_an_existing_donors_details(
    api_client: APIClient, give: Callable[..., dict[str, Any]]
) -> None:
    """A second, completed gift replaces the names and the phone the first gave."""
    complete(api_client, give())

    second = give(email=DONOR_EMAIL.upper(), first_name="Patricia", phone="707-555-0199")
    complete(api_client, second)

    donor = User.objects.get(email=DONOR_EMAIL)
    assert (donor.first_name, MemberProfile.objects.get(user=donor).phone) == (
        "Patricia",
        "707-555-0199",
    )


def test_completing_a_gift_keeps_an_optional_field_the_giver_left_blank(
    api_client: APIClient, give: Callable[..., dict[str, Any]]
) -> None:
    """A returning donor who skips the optional section keeps what they told us before."""
    complete(api_client, give(city="Petaluma", vol_newsletter=True))

    complete(api_client, give(email=DONOR_EMAIL.upper(), city="", vol_newsletter=False))

    profile = MemberProfile.objects.get(user__email=DONOR_EMAIL)
    assert (profile.city, profile.vol_newsletter) == ("Petaluma", True)


def test_an_existing_donors_stored_details_stay_put_until_a_new_gift_settles(
    api_client: APIClient, give: Callable[..., dict[str, Any]]
) -> None:
    """Starting, but not completing, a second gift cannot overwrite a donor's record.

    Anyone who knows a donor's email address can start a checkout in their name;
    until that checkout is actually paid, it must not be able to change what an
    earlier, completed gift recorded.
    """
    complete(api_client, give())

    give(email=DONOR_EMAIL.upper(), first_name="Someone Else", phone="707-555-0199")

    donor = User.objects.get(email=DONOR_EMAIL)
    assert (donor.first_name, MemberProfile.objects.get(user=donor).phone) == (
        "Pat",
        "415-555-0100",
    )


def test_a_completed_gift_reads_no_membership(
    api_client: APIClient, give: Callable[..., dict[str, Any]]
) -> None:
    """A donor holds no membership, so the answer's ``membership`` reads ``none``."""
    body = give()

    response = api_client.post(
        MOCK_COMPLETE_URL, {"payment_id": body["payment_id"], "token": body["token"]}, format="json"
    )

    assert response.json()["membership"]["status"] == "none"


def test_a_completed_gift_emails_the_donor_a_receipt(
    api_client: APIClient, give: Callable[..., dict[str, Any]]
) -> None:
    """The receipt goes to the donor's address."""
    body = give()
    api_client.post(
        MOCK_COMPLETE_URL, {"payment_id": body["payment_id"], "token": body["token"]}, format="json"
    )

    assert [message.to for message in mail.outbox] == [[DONOR_EMAIL]]


def test_a_donors_receipt_has_no_payments_link(
    api_client: APIClient, give: Callable[..., dict[str, Any]]
) -> None:
    """A donor cannot sign in, so their receipt does not point them at the portal."""
    body = give()
    api_client.post(
        MOCK_COMPLETE_URL, {"payment_id": body["payment_id"], "token": body["token"]}, format="json"
    )

    # Django's stubs type the outbox as plain messages; every receipt is multipart.
    message = cast(EmailMultiAlternatives, mail.outbox[0])
    content, _mimetype = message.alternatives[0]
    html = str(content)
    assert ("/portal/payments" in message.body, "/portal/payments" in html) == (False, False)


def test_a_members_receipt_keeps_its_payments_link(api_client: APIClient, member: User) -> None:
    """The portal's own contribution receipt still links to Payments."""
    api_client.force_login(member)
    started = api_client.post(
        "/api/v1/payments/checkout",
        {"contribution_cents": 2_000, "provider": "mock"},
        format="json",
    ).json()
    api_client.post(
        "/api/v1/payments/mock/complete", {"payment_id": started["payment_id"]}, format="json"
    )

    assert "/portal/payments" in mail.outbox[-1].body


def test_completing_without_the_right_token_is_not_found(
    api_client: APIClient, give: Callable[..., dict[str, Any]]
) -> None:
    """Another gift's token cannot complete this one."""
    mine = give()
    theirs = give(email="someone.else@example.test")

    response = api_client.post(
        MOCK_COMPLETE_URL,
        {"payment_id": theirs["payment_id"], "token": mine["token"]},
        format="json",
    )

    assert (response.status_code, response.json()) == (404, NOT_FOUND)


def test_the_mock_completion_is_not_found_when_the_mock_is_off(
    api_client: APIClient, give: Callable[..., dict[str, Any]], settings: Settings
) -> None:
    """Production does not advertise a way to settle a gift for free."""
    body = give()
    settings.PAYMENTS_MOCK_ENABLED = False

    response = api_client.post(
        MOCK_COMPLETE_URL, {"payment_id": body["payment_id"], "token": body["token"]}, format="json"
    )

    assert (response.status_code, response.json()) == (
        404,
        {"detail": "The mock payment provider is disabled."},
    )


@pytest.mark.parametrize(
    ("url", "provider"),
    [(STRIPE_CONFIRM_URL, "stripe"), (PAYPAL_CAPTURE_URL, "paypal")],
    ids=["stripe", "paypal"],
)
def test_a_provider_confirmation_refuses_another_providers_gift(
    api_client: APIClient, give: Callable[..., dict[str, Any]], url: str, provider: str
) -> None:
    """A mock gift cannot be confirmed through Stripe or captured through PayPal."""
    body = give()

    response = api_client.post(
        url, {"payment_id": body["payment_id"], "token": body["token"]}, format="json"
    )

    assert (response.status_code, response.json()) == (
        400,
        {"payment_id": f"That payment is not a {provider} payment."},
    )


@pytest.mark.parametrize("url", [STRIPE_CONFIRM_URL, PAYPAL_CAPTURE_URL], ids=["stripe", "paypal"])
def test_a_provider_confirmation_needs_the_token(
    api_client: APIClient, give: Callable[..., dict[str, Any]], url: str
) -> None:
    """Without a good token the confirmation answers 404."""
    body = give()

    response = api_client.post(
        url, {"payment_id": body["payment_id"], "token": "forged"}, format="json"
    )

    assert (response.status_code, response.json()) == (404, NOT_FOUND)


def pending_gift(provider: str, provider_ref: str) -> Payment:
    """A pending $100 gift from :data:`DONOR_EMAIL` through ``provider``, already started.

    The provider's own start is skipped: ``provider_ref`` is what it would have recorded.
    """
    payment = start_donation(donor_fields(), 10_000, provider)
    payment.provider_ref = provider_ref
    payment.save(update_fields=["provider_ref"])
    return payment


@pytest.fixture
def stripe_intent(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Configure Stripe and answer every intent lookup with the returned payload.

    The test fills the payload in; no call reaches Stripe.
    """
    settings.STRIPE_SECRET_KEY = "sk_test_123"  # noqa: S105 - test fixture
    settings.STRIPE_PUBLISHABLE_KEY = "pk_test_123"
    payload: dict[str, Any] = {}

    def retrieve(intent_id: str, *args: Any, **kwargs: Any) -> stripe.PaymentIntent:
        return stripe.PaymentIntent.construct_from(payload, "sk_test_123")

    def client() -> SimpleNamespace:
        return SimpleNamespace(
            v1=SimpleNamespace(payment_intents=SimpleNamespace(retrieve=retrieve))
        )

    monkeypatch.setattr(stripe_provider, "stripe_client", client)
    return payload


def test_a_stripe_gift_is_confirmed_with_its_token(
    api_client: APIClient, stripe_intent: dict[str, Any]
) -> None:
    """A succeeded intent settles the gift, reads no membership, and mails the receipt."""
    payment = pending_gift(PaymentProvider.STRIPE, "pi_gift")
    stripe_intent.update(
        {
            "id": "pi_gift",
            "object": "payment_intent",
            "status": "succeeded",
            "amount": payment.amount_cents,
            "currency": payment.currency,
            "metadata": {"payment_id": str(payment.pk), "user_id": str(payment.user_id)},
            "latest_charge": {
                "id": "ch_gift",
                "object": "charge",
                "payment_method_details": {"type": "card", "card": {"brand": "visa"}},
            },
        }
    )

    response = api_client.post(
        STRIPE_CONFIRM_URL,
        {
            "payment_id": payment.pk,
            "token": donation_token(payment),
            "payment_intent_id": "pi_gift",
        },
        format="json",
    )

    assert (
        response.status_code,
        response.json()["status"],
        response.json()["membership"]["status"],
        [message.to for message in mail.outbox],
    ) == (200, "succeeded", "none", [[DONOR_EMAIL]])


@respx.mock
def test_a_paypal_gift_is_captured_with_its_token(
    api_client: APIClient, settings: Settings
) -> None:
    """A completed capture settles the gift, reads no membership, and mails a receipt."""
    settings.PAYPAL_CLIENT_ID = "client-id"
    settings.PAYPAL_CLIENT_SECRET = "client-secret"  # noqa: S105 - test fixture
    settings.PAYPAL_ENV = "sandbox"
    payment = pending_gift(PaymentProvider.PAYPAL, "ORDER-GIFT")
    respx.post(PAYPAL_OAUTH_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "token", "expires_in": 3_600})
    )
    capture = {
        "id": "CAPTURE-GIFT",
        "status": "COMPLETED",
        "custom_id": str(payment.pk),
        "amount": {"currency_code": "USD", "value": "100.00"},
    }
    respx.post(f"{PAYPAL_ORDERS_URL}/ORDER-GIFT/capture").mock(
        return_value=httpx.Response(
            201,
            json={
                "id": "ORDER-GIFT",
                "status": "COMPLETED",
                "purchase_units": [{"payments": {"captures": [capture]}}],
            },
        )
    )

    response = api_client.post(
        PAYPAL_CAPTURE_URL,
        {"payment_id": payment.pk, "token": donation_token(payment), "order_id": "ORDER-GIFT"},
        format="json",
    )

    assert (
        response.status_code,
        response.json()["status"],
        response.json()["membership"]["status"],
        [message.to for message in mail.outbox],
    ) == (200, "succeeded", "none", [[DONOR_EMAIL]])


# --------------------------------------------------------------------------
# The details survive the provider's own start() call, which replaces `raw`
# --------------------------------------------------------------------------
class _FakeIntents:
    """Stand-in for ``v1.payment_intents``: records ``create``, then reports success.

    Unlike :func:`stripe_intent`, this exercises ``StripeProvider.start`` for real,
    which is what overwrites ``payment.raw`` with the created intent -- the exact
    step a donor's own details must survive on their own column.
    """

    def __init__(self) -> None:
        """Start having created nothing."""
        self.created: dict[str, Any] = {}

    def create(
        self, params: dict[str, Any], options: dict[str, Any] | None = None
    ) -> stripe.PaymentIntent:
        """Record ``params`` and answer a fresh, unconfirmed intent."""
        self.created = params
        return stripe.PaymentIntent.construct_from(
            {
                "id": "pi_full_checkout",
                "object": "payment_intent",
                "client_secret": "pi_full_checkout_secret",
                "status": "requires_payment_method",
                "amount": params["amount"],
                "currency": params["currency"],
                "metadata": params["metadata"],
            },
            "sk_test_123",
        )

    def retrieve(
        self,
        intent_id: str,
        params: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
    ) -> stripe.PaymentIntent:
        """Answer the intent :meth:`create` made, reported as succeeded."""
        return stripe.PaymentIntent.construct_from(
            {
                "id": intent_id,
                "object": "payment_intent",
                "status": "succeeded",
                "amount": self.created["amount"],
                "currency": self.created["currency"],
                "metadata": self.created["metadata"],
                "latest_charge": {
                    "id": "ch_full_checkout",
                    "object": "charge",
                    "payment_method_details": {"type": "card", "card": {"brand": "visa"}},
                },
            },
            "sk_test_123",
        )


@pytest.fixture
def fake_stripe_intents(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> _FakeIntents:
    """Configure Stripe and replace ``stripe_client`` with a recording fake."""
    settings.STRIPE_SECRET_KEY = "sk_test_123"  # noqa: S105 - test fixture
    settings.STRIPE_PUBLISHABLE_KEY = "pk_test_123"
    fake = _FakeIntents()

    def client() -> SimpleNamespace:
        return SimpleNamespace(v1=SimpleNamespace(payment_intents=fake))

    monkeypatch.setattr(stripe_provider, "stripe_client", client)
    return fake


def test_a_full_stripe_checkout_writes_the_donors_details_after_confirm(
    api_client: APIClient, fake_stripe_intents: _FakeIntents
) -> None:
    """A gift started through checkout, Stripe's own start() included, still settles.

    ``StripeProvider.start`` overwrites ``payment.raw`` with the created intent
    before the giver's details would ever be read back from it; keeping them on
    ``donor_fields`` instead is what lets this settle correctly.
    """
    started = api_client.post(CHECKOUT_URL, gift(provider="stripe", city="Petaluma"), format="json")
    assert started.status_code == 201, started.content
    body = started.json()

    response = api_client.post(
        STRIPE_CONFIRM_URL,
        {
            "payment_id": body["payment_id"],
            "token": body["token"],
            "payment_intent_id": "pi_full_checkout",
        },
        format="json",
    )

    assert response.status_code == 200, response.content
    donor = User.objects.get(email=DONOR_EMAIL)
    profile = MemberProfile.objects.get(user=donor)
    assert (donor.first_name, donor.last_name, profile.phone, profile.city) == (
        "Pat",
        "Giver",
        "415-555-0100",
        "Petaluma",
    )


@respx.mock
def test_a_full_paypal_checkout_writes_the_donors_details_after_capture(
    api_client: APIClient, settings: Settings
) -> None:
    """A gift started through checkout, PayPal's own start() included, still settles.

    ``PayPalProvider.start`` overwrites ``payment.raw`` with the created order
    before the giver's details would ever be read back from it; keeping them on
    ``donor_fields`` instead is what lets this settle correctly.
    """
    settings.PAYPAL_CLIENT_ID = "client-id"
    settings.PAYPAL_CLIENT_SECRET = "client-secret"  # noqa: S105 - test fixture
    settings.PAYPAL_ENV = "sandbox"
    respx.post(PAYPAL_OAUTH_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "token", "expires_in": 3_600})
    )
    respx.post(PAYPAL_ORDERS_URL).mock(
        return_value=httpx.Response(
            201, json={"id": "ORDER-FULL-CHECKOUT", "status": "CREATED", "links": []}
        )
    )

    started = api_client.post(CHECKOUT_URL, gift(provider="paypal", city="Petaluma"), format="json")
    assert started.status_code == 201, started.content
    body = started.json()
    payment = Payment.objects.get(pk=body["payment_id"])

    respx.post(f"{PAYPAL_ORDERS_URL}/ORDER-FULL-CHECKOUT/capture").mock(
        return_value=httpx.Response(
            201,
            json={
                "id": "ORDER-FULL-CHECKOUT",
                "status": "COMPLETED",
                "purchase_units": [
                    {
                        "payments": {
                            "captures": [
                                {
                                    "id": "CAPTURE-FULL-CHECKOUT",
                                    "status": "COMPLETED",
                                    "custom_id": str(payment.pk),
                                    "amount": {
                                        "currency_code": "USD",
                                        "value": f"{payment.amount_cents / 100:.2f}",
                                    },
                                }
                            ]
                        }
                    }
                ],
            },
        )
    )

    response = api_client.post(
        PAYPAL_CAPTURE_URL,
        {"payment_id": payment.pk, "token": body["token"], "order_id": "ORDER-FULL-CHECKOUT"},
        format="json",
    )

    assert response.status_code == 200, response.content
    donor = User.objects.get(email=DONOR_EMAIL)
    profile = MemberProfile.objects.get(user=donor)
    assert (donor.first_name, donor.last_name, profile.phone, profile.city) == (
        "Pat",
        "Giver",
        "415-555-0100",
        "Petaluma",
    )


def test_completing_a_gift_stamps_the_donors_profile(
    api_client: APIClient, give: Callable[..., dict[str, Any]]
) -> None:
    """Settling a gift stamps ``profile_updated_at`` on the donor's new profile."""
    complete(api_client, give())

    profile = MemberProfile.objects.get(user__email=DONOR_EMAIL)
    assert profile.profile_updated_at is not None


def test_the_status_reads_back_with_the_token(
    api_client: APIClient, give: Callable[..., dict[str, Any]]
) -> None:
    """``GET /donations/{id}?token=`` answers the payment's status."""
    body = give()

    response = api_client.get(status_url(body["payment_id"]), {"token": body["token"]})

    assert (response.status_code, response.json()["status"]) == (200, "pending")


def test_the_status_is_not_found_without_the_token(
    api_client: APIClient, give: Callable[..., dict[str, Any]]
) -> None:
    """Nobody reads a gift's status without the token that started it."""
    body = give()

    response = api_client.get(status_url(body["payment_id"]))

    assert (response.status_code, response.json()) == (404, NOT_FOUND)


def test_a_member_cannot_read_a_gift_without_its_token(
    api_client: APIClient, give: Callable[..., dict[str, Any]], member: User
) -> None:
    """Being signed in grants nothing here: the token is the only proof."""
    body = give()
    api_client.force_login(member)

    response = api_client.get(status_url(body["payment_id"]), {"token": "x"})

    assert (response.status_code, response.json()) == (404, NOT_FOUND)


def test_a_donation_uses_the_mock_provider_when_asked(give: Callable[..., dict[str, Any]]) -> None:
    """The provider named in the body is the one the payment is started with."""
    body = give()

    assert Payment.objects.get(pk=body["payment_id"]).provider == PaymentProvider.MOCK


# --------------------------------------------------------------------- page
@pytest.fixture
def donate_page(home_page: HomePage) -> DonatePage:
    """A published ``DonatePage`` at ``/donate/`` with an intro and a thanks text."""
    page = DonatePage(
        title="Donate",
        slug="donate",
        intro="<p>Every gift flies.</p>",
        thanks="<p>Thank you for giving.</p>",
    )
    home_page.add_child(instance=page)
    page.save_revision().publish()
    return page


def test_the_donate_page_renders_the_island_mount(client: Client, donate_page: DonatePage) -> None:
    """The page carries the mount point with its config and return addresses."""
    body = client.get(donate_page.url).content.decode()

    assert (
        '<div id="donate-app" data-config-url="/api/v1/donations/config" '
        'data-return-url="/donate/"></div>'
    ) in body


def test_the_donate_page_renders_its_intro(client: Client, donate_page: DonatePage) -> None:
    """The editor's intro is on the page."""
    assert "Every gift flies." in client.get(donate_page.url).content.decode()


def test_the_donate_page_holds_the_thanks_hidden(client: Client, donate_page: DonatePage) -> None:
    """The thanks text is on the page, hidden until a gift succeeds."""
    body = client.get(donate_page.url).content.decode()

    assert '<div class="richtext donate__thanks" data-donate-thanks hidden>' in body


def test_the_donate_page_loads_the_donation_script(client: Client, donate_page: DonatePage) -> None:
    """The page asks Vite for its own entry, not inline script."""
    body = client.get(donate_page.url).content.decode()

    # The stub manifest names ``donate-stub.js``; a real build names a hashed file.
    assert re.search(r'<script type="module" [^>]*src="/static/assets/donate-[^"]+\.js"', body)


@pytest.mark.parametrize("parent_model", [HomePage, StandardPage])
def test_a_donate_page_may_sit_below_home_and_standard_pages(
    parent_model: type[HomePage] | type[StandardPage],
) -> None:
    """Editors can add a donate page below the home page or a standard page."""
    assert DonatePage in parent_model.allowed_subpage_models()


def test_a_donate_page_takes_no_children() -> None:
    """A donate page is a leaf."""
    assert DonatePage.allowed_subpage_models() == []


def test_a_donate_page_is_its_title() -> None:
    """Wagtail lists and chooses the page by its title."""
    assert str(DonatePage(title="Give")) == "Give"


def test_the_donate_page_is_open_to_anyone(client: Client, donate_page: DonatePage) -> None:
    """A visitor who is not signed in gets the page, not a wall."""
    assert client.get(donate_page.url).status_code == 200


def test_the_config_offers_the_darts_in_name_order(api_client: APIClient) -> None:
    """The DARTs arrive in name order."""
    Dart.objects.all().delete()
    DartFactory(name="Sonoma")
    DartFactory(name="Alameda")

    names = [row["name"] for row in api_client.get(CONFIG_URL).json()["darts"]]

    assert names == ["Alameda", "Sonoma"]
