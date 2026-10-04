"""``manage.py seed_facts`` -- describe the demo data set as JSON.

The end-to-end specs need the values ``seed_demo`` builds its demo accounts
from: the shared password, the address of each named account, and what each
membership plan costs. Reading them from a JSON document keeps them in one
place -- the seed modules -- instead of being copied into a spec that then
drifts when the seed changes.
"""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.seed import DEMO_ACCOUNTS, DEMO_PASSWORD
from apps.aircraft.models import (
    Aircraft,
    RegistrantType,
    Registration,
    RegistrationStatus,
)
from apps.aircraft.registry import as_of
from apps.members.models import MembershipPlan, MembershipState
from apps.members.services import membership_status
from apps.members.verification import ITEMS, is_fully_verified, is_held, verified_items
from apps.payments.models import (
    MandateStatus,
    Payment,
    PaymentProvider,
    PaymentStatus,
    RenewalMandate,
)
from caldart.dates import format_display_date


def _has_lapsed_insurance(aircraft: Aircraft) -> bool:
    """True when ``aircraft`` carries an expiration date that is already past.

    An airframe with no expiration date on file is not lapsed: it has nothing on
    file at all, which the portal says in those words rather than calling the
    cover expired.
    """
    if aircraft.insurance_expiration is None:
        return False
    return not aircraft.insurance_is_current


#: How many days ahead the portal starts warning that a policy runs out, which is
#: ``EXPIRING_WINDOW_DAYS`` in ``frontend/src/portal/components/StatusDot.tsx``.
#: An insured pilot's policies all run past it, so the card says "Insured".
INSURANCE_WARNING_DAYS = 30


def _is_comfortably_insured(aircraft: Aircraft) -> bool:
    """True when ``aircraft``'s insurance runs past the portal's warning window."""
    expires_on = aircraft.insurance_expiration
    if expires_on is None:
        return False
    return expires_on > timezone.localdate() + timedelta(days=INSURANCE_WARNING_DAYS)


def _is_insured_and_verified(aircraft: Aircraft) -> bool:
    """True when ``aircraft`` is comfortably insured and its insurance is verified."""
    return _is_comfortably_insured(aircraft) and aircraft.insurance_is_verified


def _unverified_pilot() -> dict[str, str]:
    """A current member with a current medical, holding all three items, none verified.

    The member check reads such a member as not verified on all three items: each is
    held, so none is left out as having nothing to verify.  Returns ``{"name"}``, and
    an empty name when nobody in the seed fits.
    """
    for user in User.objects.filter(profile__isnull=False).select_related("profile"):
        if membership_status(user)["status"] != MembershipState.CURRENT:
            continue
        if not user.profile.medical_is_current:
            continue
        if not all(is_held(user.profile, item.slug) for item in ITEMS):
            continue
        if len(verified_items(user.profile)) == 0:
            return {"name": user.display_name}
    return {"name": ""}


def _subject(*, insured: bool | None, status: MembershipState) -> dict[str, str]:
    """A seeded member the leader check can be demonstrated on.

    ``status`` is the membership state the member must be in.  ``insured`` picks
    somebody whose medical is current, whose pilot certificate, medical, and photo ID
    are all verified, and whose every listed aircraft is insured past the portal's
    warning window with its insurance verified (``True``), so the card is a GO showing
    nothing but insured airplanes; somebody who lists an aircraft whose expiration
    date has passed (``False``); or anybody at all (``None``).
    Returns ``{"name", "nNumber"}``, with an empty ``nNumber`` when the member
    lists no aircraft, and empty strings when nobody in the seed fits -- the
    specs then fail on the name they were given, which says what is missing.
    """
    for user in User.objects.filter(profile__isnull=False).select_related("profile"):
        if membership_status(user)["status"] != status:
            continue
        listed = list(user.profile.aircraft.all())
        if insured and not user.profile.medical_is_current:
            continue
        if insured and not is_fully_verified(user.profile):
            continue
        if insured and not all(_is_insured_and_verified(aircraft) for aircraft in listed):
            continue
        for aircraft in listed:
            if insured is None:
                return {"name": user.display_name, "nNumber": aircraft.n_number}
            matches = insured or _has_lapsed_insurance(aircraft)
            if matches:
                return {"name": user.display_name, "nNumber": aircraft.n_number}
        if insured is None:
            return {"name": user.display_name, "nNumber": ""}
    return {"name": "", "nNumber": ""}


def _auto_renewing_member() -> dict[str, str]:
    """A seeded member whose membership renews itself, for the renewal specs.

    Returns ``{"name", "email", "methodLabel"}`` for the first member holding an
    active mandate whose next charge is still ahead of today, and empty strings
    when the seed has none -- the specs then fail on the name they were given,
    which says what is missing.  A mandate already due today or overdue is
    skipped, so a renewal spec is never handed a member the daily scan is about
    to charge out from under it.
    """
    mandate = (
        RenewalMandate.objects.filter(
            status=MandateStatus.ACTIVE,
            plan__isnull=False,
            next_charge_on__gt=timezone.localdate(),
        )
        .select_related("user")
        .order_by("pk")
        .first()
    )
    if mandate is None:
        return {"name": "", "email": "", "methodLabel": ""}
    return {
        "name": mandate.user.display_name,
        "email": mandate.user.email,
        "methodLabel": mandate.method_label,
    }


def _paused_renewal_member() -> dict[str, str]:
    """A seeded member whose automatic renewal was paused after its retries ran out.

    Returns ``{"name", "email"}``, and empty strings when the seed has no paused
    mandate.
    """
    mandate = (
        RenewalMandate.objects.filter(status=MandateStatus.PAUSED)
        .select_related("user")
        .order_by("pk")
        .first()
    )
    if mandate is None:
        return {"name": "", "email": ""}
    return {"name": mandate.user.display_name, "email": mandate.user.email}


def _contribution_mandate_member() -> dict[str, str]:
    """A seeded life member whose standing authority charges a contribution alone.

    Returns ``{"name", "email"}`` for the first active mandate that names no
    plan, and empty strings when the seed has none -- the specs then fail on the
    name they were given, which says what is missing.
    """
    mandate = (
        RenewalMandate.objects.filter(status=MandateStatus.ACTIVE, plan__isnull=True)
        .select_related("user")
        .order_by("pk")
        .first()
    )
    if mandate is None:
        return {"name": "", "email": ""}
    return {"name": mandate.user.display_name, "email": mandate.user.email}


def _refunded_payment_member() -> dict[str, str]:
    """A seeded member whose payment was refunded in part, for the finance specs.

    Returns ``{"name", "email", "receiptNumber"}`` for the first partially
    refunded payment, and empty strings when the seed refunded nothing -- the
    specs then fail on the name they were given, which says what is missing.
    """
    payment = (
        Payment.objects.filter(status=PaymentStatus.PARTIALLY_REFUNDED)
        .select_related("user")
        .order_by("pk")
        .first()
    )
    if payment is None:
        return {"name": "", "email": "", "receiptNumber": ""}
    return {
        "name": payment.user.display_name,
        "email": payment.user.email,
        "receiptNumber": payment.receipt_number,
    }


#: The registrant types :func:`_registry` prefers for the known registration: a company
#: rather than a private person, when the registry holds one.
COMPANY_REGISTRANTS = (RegistrantType.CORPORATION, RegistrantType.LLC)


def _registry() -> dict[str, Any]:
    """The registration the end-to-end spec picks by N-number, and the registry date.

    ``knownNNumber`` is the first valid registration, by N-number, that carries a year
    and is on no register record, preferring one a corporation or an LLC holds;
    ``knownType``, ``knownYear``, and ``knownOwner`` are its type (``<make> <model>``),
    year, and registrant, which is what picking it fills in.  ``asOf`` is the local
    day the newest successful import finished, written ``MM/DD/YYYY`` as the screens
    print it.  Each is empty (``knownYear`` ``null``) when the registry holds nothing
    that fits.
    """
    candidates = (
        Registration.objects.filter(status=RegistrationStatus.VALID, year__isnull=False)
        .exclude(n_number__in=Aircraft.objects.values("n_number"))
        .select_related("type")
        .order_by("n_number")
    )
    known = candidates.filter(registrant_type__in=COMPANY_REGISTRANTS).first() or candidates.first()
    finished = as_of()
    return {
        "knownNNumber": "" if known is None else known.n_number,
        "knownType": "" if known is None else str(known.type),
        "knownYear": None if known is None else known.year,
        "knownOwner": "" if known is None else known.registrant_name,
        "asOf": "" if finished is None else format_display_date(timezone.localdate(finished)),
    }


def seed_facts() -> dict[str, Any]:
    """Return the demo data set's facts, ready to serialize as JSON.

    ``demoPassword`` is the password every seeded demo account shares, and
    ``accounts`` maps each demo key (``member``, ``leader``, ``sysadmin``, and the
    rest) to that account's address. ``planPricesCents`` maps each membership
    plan's slug to its price in cents, read from the database so it reflects the
    plans that are actually there.  ``leaderCheck`` names four members the
    leader check reads differently -- an insured pilot verified on every count, one
    whose aircraft insurance has lapsed, one whose membership has, and a current
    pilot with a current medical and nothing verified (``unverifiedPilot``, a name
    alone) -- so the specs assert on the seed rather than on names typed into them,
    which drift.
    ``manualPaymentCount`` is how many payments the seed recorded by hand, which
    is what a finance spec filtering the list to checks expects to find.
    ``autoRenewal`` names one member whose membership renews itself, one whose
    renewal was paused after every retry was refused, and one life member whose
    standing authority charges a contribution alone.  ``refundedPayment`` names a
    member whose payment was refunded in part, and the receipt number that payment
    carries, which is how a finance spec finds it in the list.  ``registry`` names a
    registration on no register record, for the spec that picks it from the N-number
    box, and the date the registry is as of (see :func:`_registry`).
    """
    return {
        "demoPassword": DEMO_PASSWORD,
        "accounts": {key: email for key, email, *_rest in DEMO_ACCOUNTS},
        "planPricesCents": {
            plan.slug: plan.price_cents for plan in MembershipPlan.objects.order_by("slug")
        },
        "leaderCheck": {
            "insuredPilot": _subject(insured=True, status=MembershipState.CURRENT),
            "lapsedInsurance": _subject(insured=False, status=MembershipState.CURRENT),
            "expiredMember": _subject(insured=None, status=MembershipState.EXPIRED),
            "unverifiedPilot": _unverified_pilot(),
        },
        "manualPaymentCount": Payment.objects.filter(provider=PaymentProvider.MANUAL).count(),
        "refundedPayment": _refunded_payment_member(),
        "autoRenewal": {
            "activeMandate": _auto_renewing_member(),
            "pausedMandate": _paused_renewal_member(),
            "contributionMandate": _contribution_mandate_member(),
        },
        "registry": _registry(),
    }


class Command(BaseCommand):
    """``manage.py seed_facts`` -- print the demo data set's facts as JSON."""

    help = "Print the demo data set's facts as JSON, for the end-to-end specs."

    def handle(self, *args: Any, **options: Any) -> None:
        """Write the facts to stdout as a JSON object, sorted, and indented."""
        self.stdout.write(json.dumps(seed_facts(), indent=2, sort_keys=True))
