"""Gifts through the public donation page, from people who never sign in.

A gift made on the public site belongs to a **donor**: an account found or made by
email address, with no role and no usable password, so it can never sign in and
appears in no member list.  :func:`donor_for` finds or makes that account and writes
what the giver told us onto its profile; :func:`start_donation` then starts a
contribution for it through the same :func:`~apps.payments.services.create_checkout`
a member's own checkout uses.

The caller is anonymous, so what proves that the browser finishing a payment is the
one that started it is a signed token over the payment's id
(:func:`donation_token`), good for an hour and checked by :func:`payment_for_token`.
"""

from __future__ import annotations

import logging
from typing import Any, TypedDict

from django.core import signing
from django.db import transaction

from apps.accounts.models import AccountKind, User
from apps.accounts.services import create_account
from apps.darts.models import Dart
from apps.members.models import MemberProfile
from apps.members.services import touch_profile
from apps.payments.models import Payment
from apps.payments.services import create_checkout
from caldart.exceptions import DomainValidationError

log = logging.getLogger(__name__)

#: The salt that keeps a donation token from reading as any other signed value.
DONATION_TOKEN_SALT = "payments.donation"  # noqa: S105 - a signing salt name, not a secret

#: How long a donation token stays good, in seconds: an hour, which is longer than any
#: provider takes to hand a browser back.
DONATION_TOKEN_MAX_AGE = 3_600

#: What an address that already signs in to the portal is told.
HAS_ACCOUNT_MESSAGE = "An account already uses that email address. Sign in to donate."

#: The ``code`` that travels with :data:`HAS_ACCOUNT_MESSAGE`.
HAS_ACCOUNT_CODE = "has_account"

#: What a caller without a good token is told: the same words an unknown id earns.
NO_SUCH_PAYMENT = "No such payment."

#: The optional profile fields a giver may fill in, each written onto the donor's
#: ``MemberProfile`` under the same name.
DONOR_PROFILE_FIELDS: tuple[str, ...] = (
    "address_line1",
    "address_line2",
    "city",
    "state",
    "postal_code",
    "county",
    "home_airport_identifier",
    "home_airport_city",
    "dart",
    "air_care_alliance_number",
    "pilot_certificate_type",
    "ifr_rated",
    "vol_mission_pilot",
    "vol_ground_team",
    "vol_exercise_training",
    "vol_member_support",
    "vol_fundraising",
    "vol_social_media",
    "vol_newsletter",
)


class DonorFields(TypedDict, total=False):
    """What a giver tells us: the four required fields, then the optional profile.

    ``first_name``, ``last_name``, ``email`` and ``phone`` are always present; the
    rest are :data:`DONOR_PROFILE_FIELDS`, as the donation form collects them.
    """

    first_name: str
    last_name: str
    email: str
    phone: str
    address_line1: str
    address_line2: str
    city: str
    state: str
    postal_code: str
    county: str
    home_airport_identifier: str
    home_airport_city: str
    dart: Dart | None
    air_care_alliance_number: str
    pilot_certificate_type: str
    ifr_rated: str
    vol_mission_pilot: bool
    vol_ground_team: bool
    vol_exercise_training: bool
    vol_member_support: bool
    vol_fundraising: bool
    vol_social_media: bool
    vol_newsletter: bool


class HasAccountError(DomainValidationError):
    """The address a giver typed belongs to a member or a friend.

    Keyed by ``email`` and carrying :data:`HAS_ACCOUNT_MESSAGE`; the endpoint answers
    it with the ``has_account`` code, so the page can send the person to sign in.
    """

    def __init__(self) -> None:
        """Key the refusal by ``email`` with :data:`HAS_ACCOUNT_MESSAGE`."""
        super().__init__("email", HAS_ACCOUNT_MESSAGE)


class DonationTokenError(Exception):
    """The token does not prove the payment: forged, expired, or for another payment."""

    def __init__(self) -> None:
        """Carry :data:`NO_SUCH_PAYMENT`, the words an unknown payment id earns."""
        super().__init__(NO_SUCH_PAYMENT)


@transaction.atomic
def donor_for(fields: DonorFields) -> User:
    """The donor account for ``fields["email"]``, found or made, with the giver's details.

    The address is matched case-insensitively.  An existing donor has its names and
    its profile's phone replaced by what was given, and each optional profile field
    the giver filled in (a non-blank value, a DART, or a ticked box) written over the
    stored one; an optional field left blank or unticked keeps what an earlier gift
    told us.  A new address becomes a donor (``create_account`` with the ``donor``
    kind: no role, an unusable password, the address unverified) with a profile
    holding everything given, stamped as written.  Nothing is mailed either way.

    Raises :class:`HasAccountError` when the address belongs to a member or a friend,
    whether their account is active or deactivated: that person gives from the portal.
    """
    email = fields["email"].strip()
    user = User.objects.filter(email__iexact=email).first()
    if user is not None and user.kind != AccountKind.DONOR:
        raise HasAccountError
    if user is None:
        user = create_account(
            email=email,
            first_name=fields["first_name"],
            last_name=fields["last_name"],
            kind=AccountKind.DONOR,
        )
        log.info("Donor account %s created for a gift on the public site", user.pk)
    else:
        user.first_name = fields["first_name"].strip()
        user.last_name = fields["last_name"].strip()
        user.save(update_fields=["first_name", "last_name", "updated_at"])

    profile, _ = MemberProfile.objects.get_or_create(user=user)
    profile.phone = fields["phone"]
    for name in DONOR_PROFILE_FIELDS:
        value: Any = fields.get(name)
        if value not in (None, "", False):
            setattr(profile, name, value)
    profile.save()
    touch_profile(profile)
    return user


@transaction.atomic
def start_donation(fields: DonorFields, contribution_cents: int, provider: str) -> Payment:
    """A ``pending`` gift of ``contribution_cents`` from the giver behind ``fields``.

    The donor comes from :func:`donor_for` and the payment from ``create_checkout`` with
    no plan, so the amount is the contribution alone and a gift of nothing is refused
    there.  Raises what either raises, and writes nothing when it does.
    """
    donor = donor_for(fields)
    return create_checkout(donor, None, contribution_cents, provider)


def donation_token(payment: Payment) -> str:
    """The signed token that proves the caller holding it started ``payment``.

    ``signing.dumps({"payment": <id>})`` under :data:`DONATION_TOKEN_SALT`, readable
    for :data:`DONATION_TOKEN_MAX_AGE` seconds by :func:`payment_for_token`.
    """
    return signing.dumps({"payment": payment.pk}, salt=DONATION_TOKEN_SALT)


def payment_for_token(payment_id: int, token: str) -> Payment:
    """The payment ``payment_id`` names, once ``token`` proves the caller started it.

    Raises :class:`DonationTokenError` when the token is forged, older than an hour,
    or was minted for another payment, and when no such payment exists: every one of
    those reads the same to the caller.
    """
    try:
        claim = signing.loads(token, salt=DONATION_TOKEN_SALT, max_age=DONATION_TOKEN_MAX_AGE)
    except signing.BadSignature as exc:
        raise DonationTokenError from exc
    if not isinstance(claim, dict) or claim.get("payment") != payment_id:
        raise DonationTokenError
    payment = Payment.objects.select_related("user", "plan").filter(pk=payment_id).first()
    if payment is None:
        raise DonationTokenError
    return payment
