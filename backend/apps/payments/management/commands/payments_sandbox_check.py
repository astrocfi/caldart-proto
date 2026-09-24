"""``manage.py payments_sandbox_check`` -- verify Stripe and PayPal credentials.

Makes one read-only call to each configured provider -- Stripe's account balance
and payment method configuration, PayPal's OAuth token and its configured
webhooks -- so a developer can tell their ``.env`` is wired up correctly before
opening a browser and working through a checkout by hand.  Nothing is charged,
captured, or refunded.

Exits non-zero, through ``CommandError``, when no provider is usable: neither
is configured, or a configured one could not be reached.  A provider that is
simply not configured is reported but does not by itself fail the command,
since a developer working on one provider need not have the other's sandbox
keys.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import stripe
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.payments.providers import paypal as paypal_provider
from apps.payments.providers import stripe as stripe_provider
from apps.payments.providers.base import PaymentError, get_provider
from caldart.reports import money_label

log = logging.getLogger(__name__)

#: The Webhooks Management API's list endpoint.  It creates and moves nothing,
#: and -- unlike the OpenID Connect identity endpoint, which needs a token from
#: a user login and would report a perfectly working REST app key as
#: unreachable -- it is a call any client-credentials token is entitled to,
#: which is why it is the standard way to prove a REST app's keys are live.
#: Listing the account's webhooks also lets the command confirm the configured
#: ``PAYPAL_WEBHOOK_ID`` actually names one of them.
PAYPAL_WEBHOOKS_PATH = "/v1/notifications/webhooks"


@dataclass
class _ProviderReport:
    """What ``payments_sandbox_check`` found out about one provider.

    ``configured`` is whether the settings the provider needs are present at
    all; ``ok`` is whether the check call actually succeeded, which is always
    ``False`` when ``configured`` is ``False``.  ``lines`` are the report's
    body, one fact or capability per line, already written for a terminal.
    """

    slug: str
    configured: bool
    ok: bool
    lines: list[str] = field(default_factory=list)


def _webhook_line(name: str, value: str) -> str:
    """Report whether the environment variable ``name`` naming a webhook secret is set.

    Never prints ``value`` itself: only its presence, since a secret belongs in
    logs and terminals as little as anywhere else.
    """
    return f"{name}: set" if value else f"{name}: not set"


def _format_balance(balance: dict[str, Any]) -> str:
    """The account's available balance as a reader sees it, from a Stripe ``Balance``.

    ``balance`` is ``client.v1.balance.retrieve().to_dict()``.  Reads
    ``balance["available"]``, a list of ``{"amount", "currency"}`` entries --
    Stripe reports one per settlement currency it holds a balance in, which for
    a fresh test account is one, showing zero.  Joins more than one currency
    with a comma, and answers ``"none reported"`` for an empty list, which
    ``to_dict()`` will not normally produce but a stub or a future API change
    might.
    """
    entries = balance.get("available") or []
    if not entries:
        return "none reported"
    return ", ".join(f"{money_label(entry['amount'])} {entry['currency']}" for entry in entries)


def _enabled_payment_method_types(configurations: list[dict[str, Any]]) -> list[str]:
    """The payment method types the account's default configuration allows.

    ``configurations`` is
    ``[c.to_dict() for c in client.v1.payment_method_configurations.list().data]``.
    Reads the one configuration whose ``is_default`` is true -- the one the
    Payment Element uses when the server does not name one explicitly, which is
    how CalDART's checkout creates every PaymentIntent -- and returns the sorted
    keys of every payment-method field on it (``card``, ``link``,
    ``us_bank_account``, and so on, whichever the account and Stripe's API
    version offer) whose ``available`` is true. Answers an empty list when
    there is no default configuration, which is unusual but not an error: the
    Payment Element then falls back to card only.
    """
    for configuration in configurations:
        if not configuration.get("is_default"):
            continue
        return sorted(
            key
            for key, value in configuration.items()
            if isinstance(value, dict) and value.get("available") is True
        )
    return []


def _check_stripe() -> _ProviderReport:
    """Retrieve the Stripe balance and the enabled payment methods.

    Answers ``configured=False`` when ``STRIPE_SECRET_KEY`` or
    ``STRIPE_PUBLISHABLE_KEY`` is empty, without making a call.  Otherwise calls
    the account balance and the payment method configuration list; a call
    Stripe refuses (a revoked key, an account in a bad state) or cannot be
    reached comes back as ``ok=False`` with the SDK's own message, logged at
    warning level with nothing but the exception's class, since a
    ``StripeError`` can quote request data.  Fees, refunds, and off-session
    (automatic renewal) charges need nothing beyond a valid secret key, so a
    reachable account is reported able to do all three.
    """
    if not get_provider("stripe").is_configured():
        return _ProviderReport(
            slug="stripe",
            configured=False,
            ok=False,
            lines=["not configured: STRIPE_SECRET_KEY / STRIPE_PUBLISHABLE_KEY are empty"],
        )

    try:
        client = stripe_provider.stripe_client()
        balance = client.v1.balance.retrieve().to_dict()
        configurations = [
            configuration.to_dict()
            for configuration in client.v1.payment_method_configurations.list().data
        ]
    except stripe.StripeError as exc:
        log.warning("payments_sandbox_check: Stripe call failed: %s", type(exc).__name__)
        return _ProviderReport(
            slug="stripe", configured=True, ok=False, lines=[f"could not reach Stripe: {exc}"]
        )

    methods = _enabled_payment_method_types(configurations)
    lines = [
        f"balance: {_format_balance(balance)}",
        f"enabled payment methods: {', '.join(methods) if methods else 'none enabled'}",
        _webhook_line("STRIPE_WEBHOOK_SECRET", settings.STRIPE_WEBHOOK_SECRET),
        "fees: available -- the balance transaction on every succeeded charge",
        "refunds: available -- refunds.create",
        "off-session charges (automatic renewal): available -- setup_future_usage "
        "plus an off_session confirm",
    ]
    return _ProviderReport(slug="stripe", configured=True, ok=True, lines=lines)


def _paypal_webhook_id_line(webhook_ids: list[str]) -> str:
    """Report whether ``PAYPAL_WEBHOOK_ID`` names one of the account's webhooks.

    Never echoes the configured id itself, so misreading the report can never
    be mistaken for reading the id out of ``.env``.
    """
    webhook_id = settings.PAYPAL_WEBHOOK_ID
    if not webhook_id:
        return "PAYPAL_WEBHOOK_ID: not set"
    if webhook_id in webhook_ids:
        return "PAYPAL_WEBHOOK_ID: set and found among the account's webhooks"
    return "PAYPAL_WEBHOOK_ID: set but not found among the account's webhooks"


def _check_paypal() -> _ProviderReport:
    """Fetch a PayPal token and list the account's configured webhooks.

    Answers ``configured=False`` when ``PAYPAL_CLIENT_ID`` or
    ``PAYPAL_CLIENT_SECRET`` is empty, without making a call. Otherwise fetches
    an OAuth token and calls :data:`PAYPAL_WEBHOOKS_PATH`, which proves the
    credentials are live and lets :func:`_paypal_webhook_id_line` confirm the
    configured ``PAYPAL_WEBHOOK_ID`` actually names one of the account's
    webhooks, without creating or moving anything. A call PayPal refuses or
    that cannot be reached comes back as ``ok=False`` with the raised
    :class:`~apps.payments.providers.base.PaymentError`'s message, logged at
    warning level with nothing but the exception's class. Fees and refunds
    need nothing beyond working credentials; vault (automatic renewal) is a
    REST app setting this command cannot read through the API, so it is
    reported as something to check by hand.
    """
    if not get_provider("paypal").is_configured():
        return _ProviderReport(
            slug="paypal",
            configured=False,
            ok=False,
            lines=["not configured: PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET are empty"],
        )

    try:
        paypal_provider.access_token()
        response = paypal_provider.call("GET", PAYPAL_WEBHOOKS_PATH)
    except PaymentError as exc:
        log.warning("payments_sandbox_check: PayPal call failed: %s", type(exc).__name__)
        return _ProviderReport(
            slug="paypal", configured=True, ok=False, lines=[f"could not reach PayPal: {exc}"]
        )

    webhook_ids = [webhook["id"] for webhook in response.get("webhooks") or []]
    lines = [
        f"token: fetched (PAYPAL_ENV={settings.PAYPAL_ENV})",
        f"webhooks configured on this account: {len(webhook_ids)}",
        _paypal_webhook_id_line(webhook_ids),
        "fees: available -- seller_receivable_breakdown on every capture",
        "refunds: available -- POST /v2/payments/captures/{id}/refund",
        "vault (automatic renewal): enable by hand under the REST app's Vault feature; "
        "this command cannot check it without creating a setup token",
    ]
    return _ProviderReport(slug="paypal", configured=True, ok=True, lines=lines)


def _mock_line() -> str:
    """Report the mock provider's availability, which follows ``PAYMENTS_MOCK_ENABLED``.

    A developer who turned the switch off in their own ``.env`` -- or a
    checkout running against ``prod.py``, which defaults it to ``False`` -- sees
    ``disabled`` rather than a claim that the mock tab is there when the
    checkout will not offer it.
    """
    if settings.PAYMENTS_MOCK_ENABLED:
        return "mock: available"
    return f"mock: disabled (PAYMENTS_MOCK_ENABLED={settings.PAYMENTS_MOCK_ENABLED})"


class Command(BaseCommand):
    """Checks that the configured Stripe and PayPal credentials actually work."""

    help = "Verify Stripe and PayPal sandbox credentials before testing a payment in the browser."

    def handle(self, *args: Any, **options: Any) -> None:
        """Print each provider's report, then the mock provider's status.

        Raises ``CommandError`` -- so the command exits non-zero -- when a
        configured provider could not be reached, naming it, or, failing that,
        when no provider is usable at all. A provider that is simply not
        configured does not by itself raise, since a developer working on one
        provider need not have the other's keys.
        """
        reports = [_check_stripe(), _check_paypal()]
        for report in reports:
            self.stdout.write(f"{report.slug}:")
            for line in report.lines:
                self.stdout.write(f"  {line}")
            self.stdout.write("")

        self.stdout.write(_mock_line())

        usable = [report.slug for report in reports if report.ok]
        broken = [report.slug for report in reports if report.configured and not report.ok]
        if broken:
            raise CommandError(f"configured but not reachable: {', '.join(broken)}")
        if not usable:
            raise CommandError(
                "no provider is usable: configure at least one of Stripe or PayPal "
                "(see docs/developer/payments-setup.rst)"
            )

        self.stdout.write(self.style.SUCCESS(f"usable: {', '.join(usable)}"))
