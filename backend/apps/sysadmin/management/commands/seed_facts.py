"""``manage.py seed_facts`` -- describe the demo data set as JSON.

The end-to-end specs need the values ``seed_demo`` builds its demo accounts
from: the shared password, the address of each named account, and what each
membership plan costs. Reading them from a JSON document keeps them in one
place -- the seed modules -- instead of being copied into a spec that then
drifts when the seed changes.
"""

from __future__ import annotations

import json
from typing import Any

from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.accounts.seed import DEMO_ACCOUNTS, DEMO_PASSWORD
from apps.aircraft.models import Aircraft
from apps.members.models import MembershipPlan, MembershipState
from apps.members.services import membership_status
from apps.payments.models import Payment, PaymentProvider


def _has_lapsed_insurance(aircraft: Aircraft) -> bool:
    """True when ``aircraft`` carries an expiration date that is already past.

    An airframe with no expiration date on file is not lapsed: it has nothing on
    file at all, which the portal says in those words rather than calling the
    cover expired.
    """
    if aircraft.insurance_expiration is None:
        return False
    return not aircraft.insurance_is_current


def _subject(*, insured: bool | None, current_member: bool) -> dict[str, str]:
    """A seeded member the leader check can be demonstrated on.

    ``insured`` picks somebody who lists an aircraft whose insurance is current
    (``True``) or carries an expiration date that has passed (``False``), or
    anybody at all (``None``);
    ``current_member`` picks somebody whose membership is current or is not.
    Returns ``{"name", "nNumber"}``, with an empty ``nNumber`` when the member
    lists no aircraft, and empty strings when nobody in the seed fits -- the
    specs then fail on the name they were given, which says what is missing.
    """
    for user in User.objects.filter(profile__isnull=False).select_related("profile"):
        is_current = membership_status(user)["status"] == MembershipState.CURRENT
        if is_current is not current_member:
            continue
        for aircraft in user.profile.aircraft.all():
            if insured is None:
                return {"name": user.display_name, "nNumber": aircraft.n_number}
            matches = aircraft.insurance_is_current if insured else _has_lapsed_insurance(aircraft)
            if matches:
                return {"name": user.display_name, "nNumber": aircraft.n_number}
        if insured is None:
            return {"name": user.display_name, "nNumber": ""}
    return {"name": "", "nNumber": ""}


def seed_facts() -> dict[str, Any]:
    """Return the demo data set's facts, ready to serialize as JSON.

    ``demoPassword`` is the password every seeded demo account shares, and
    ``accounts`` maps each demo key (``member``, ``leader``, ``sysadmin``, and the
    rest) to that account's address. ``planPricesCents`` maps each membership
    plan's slug to its price in cents, read from the database so it reflects the
    plans that are actually there.  ``leaderCheck`` names three members the
    leader check reads differently -- an insured pilot, one whose aircraft
    insurance has lapsed, and one whose membership has -- so the specs assert on
    the seed rather than on names typed into them, which drift.
    ``manualPaymentCount`` is how many payments the seed recorded by hand, which
    is what a finance spec filtering the list to checks expects to find.
    """
    return {
        "demoPassword": DEMO_PASSWORD,
        "accounts": {key: email for key, email, *_rest in DEMO_ACCOUNTS},
        "planPricesCents": {
            plan.slug: plan.price_cents for plan in MembershipPlan.objects.order_by("slug")
        },
        "leaderCheck": {
            "insuredPilot": _subject(insured=True, current_member=True),
            "lapsedInsurance": _subject(insured=False, current_member=True),
            "expiredMember": _subject(insured=None, current_member=False),
        },
        "manualPaymentCount": Payment.objects.filter(provider=PaymentProvider.MANUAL).count(),
    }


class Command(BaseCommand):
    """``manage.py seed_facts`` -- print the demo data set's facts as JSON."""

    help = "Print the demo data set's facts as JSON, for the end-to-end specs."

    def handle(self, *args: Any, **options: Any) -> None:
        """Write the facts to stdout as a JSON object, sorted, and indented."""
        self.stdout.write(json.dumps(seed_facts(), indent=2, sort_keys=True))
