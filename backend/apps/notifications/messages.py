"""What each event's email says: a headline, a few labeled lines, and one link.

:func:`build_message` turns an event's slug and the payload it was raised with into a
:class:`Message`, while the objects the payload names are still in hand.  Every email
reads the same way: the subject is ``<org name>: <headline>``, the lines are
``(label, value)`` pairs, and the link opens the record the event is about in the
portal (the member record, the user record, the payment, or the aircraft), or is blank
when there is nothing left to open.  Names are the account's display name, money is
printed as dollars, and a date is ``MM/DD/YYYY`` (``caldart.dates``).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import date

from django.conf import settings

from apps.accounts.models import AccountKind, User
from apps.accounts.roles import ROLE_LABELS
from apps.aircraft.models import Aircraft
from apps.darts.models import Dart
from apps.members.models import MemberProfile, Membership
from apps.members.services import account_kind
from apps.payments.models import Payment, PaymentKind, RenewalMandate
from caldart.dates import format_display_date
from caldart.mail import org_name
from caldart.reports import money_label

#: One labeled line of an email: the label, then its value.
type Line = tuple[str, str]

#: What a line with nothing to name reads.
NONE = "None"

#: How somebody became a friend, as the ``How`` line says it.
BECAME_FRIEND_HOW: dict[str, str] = {
    "chose": "Chose to be a friend",
    "lapsed": "Membership lapsed",
    "administrator": "Changed by an administrator",
}

#: How somebody became a member, as the ``How`` line says it.
BECAME_MEMBER_HOW: dict[str, str] = {
    "paid": "Paid for membership",
    "granted": "Granted by an administrator",
    "administrator": "Changed by an administrator",
}

#: How an automatic payment was turned off, as the ``How`` line says it.
AUTO_RENEWAL_OFF_HOW: dict[str, str] = {
    "member": "Turned off by the member",
    "administrator": "Turned off by an administrator",
    "lapsed": "Membership lapsed",
    "deactivated": "Account deactivated",
}

#: Who gave a refund when no account did.
DASHBOARD_ACTOR = "The payment provider's dashboard"


@dataclass(frozen=True)
class Message:
    """One event's email, ready to send to every recipient alike.

    ``subject`` is ``<org name>: <headline>``; ``lines`` are the labeled facts in the
    order the email prints them; ``link`` is the absolute address of the record the
    event is about, or blank when there is none.
    """

    subject: str
    headline: str
    lines: tuple[Line, ...]
    link: str


def build_message(slug: str, payload: Mapping[str, object]) -> Message:
    """The email the event ``slug``, raised with ``payload``, is sent as.

    ``payload`` holds the keyword arguments the event was raised with.  A payload
    missing an object its event needs, or holding the wrong kind of object, raises
    ``TypeError`` naming the key.  An unknown ``slug`` raises ``KeyError``.
    """
    headline, lines, link = _BUILDERS[slug](payload)
    return Message(
        subject=f"{org_name()}: {headline}",
        headline=headline,
        lines=tuple(lines),
        link=link,
    )


# -- reading a payload -------------------------------------------------------------
def _required[T](payload: Mapping[str, object], key: str, kind: type[T]) -> T:
    """``payload[key]`` when it is a ``kind``; ``TypeError`` naming ``key`` otherwise."""
    value = payload.get(key)
    if not isinstance(value, kind):
        raise TypeError(
            f"The event payload's '{key}' must be {kind.__name__}, not {type(value).__name__}."
        )
    return value


def _optional[T](payload: Mapping[str, object], key: str, kind: type[T]) -> T | None:
    """``payload[key]``, which may be missing or ``None``, or else must be a ``kind``."""
    if payload.get(key) is None:
        return None
    return _required(payload, key, kind)


def _words(payload: Mapping[str, object], key: str) -> list[str]:
    """``payload[key]`` as a list of strings; missing or ``None`` is an empty list."""
    value = payload.get(key)
    if value is None:
        return []
    if isinstance(value, str) or not isinstance(value, Iterable):
        raise TypeError(f"The event payload's '{key}' must be a list of strings.")
    return [str(item) for item in value]


# -- words -------------------------------------------------------------------------
def _through(term: Membership) -> str:
    """The last day ``term`` covers, or ``Lifetime`` for a term with no end."""
    return "Lifetime" if term.ends_on is None else format_display_date(term.ends_on)


def _actor(actor: User | None, subject: User) -> str:
    """Who did it: the actor's name, or the subject themselves when no actor is named."""
    if actor is None:
        return f"{subject.display_name} themselves"
    return actor.display_name


def _owner(owner: object) -> str:
    """An aircraft owner's name, whether given as an account or as text."""
    if isinstance(owner, User):
        return owner.display_name
    return "" if owner is None else str(owner)


def _labels(names: Iterable[str]) -> str:
    """``names`` joined with commas, or ``None`` when there are none."""
    joined = ", ".join(names)
    return joined or NONE


def _role_labels(slugs: Iterable[str]) -> str:
    """Role slugs as the screens name the roles, joined with commas."""
    return _labels(ROLE_LABELS.get(slug, slug) for slug in slugs)


def _aircraft_field_label(name: str) -> str:
    """A register column's label (``insurance_carrier`` reads ``Insurance carrier``).

    A name that is not a column is taken to be a label already and kept as given.
    """
    columns = {field.name: str(field.verbose_name) for field in Aircraft._meta.concrete_fields}
    if name not in columns:
        return name
    label = columns[name]
    return label[:1].upper() + label[1:]


def _in_a_sentence(label: str) -> str:
    """An item's label as it reads mid-sentence: ``Photo ID`` reads ``photo ID``."""
    return label[:1].lower() + label[1:]


def _series(words: list[str]) -> str:
    """``words`` as a sentence lists them, with a serial comma: ``a, b, and c``."""
    if len(words) <= 2:
        return " and ".join(words)
    return f"{', '.join(words[:-1])}, and {words[-1]}"


def _mandate_kind(mandate: RenewalMandate) -> str:
    """``renewal`` for a mandate that renews a plan, ``donation`` for a recurring gift."""
    return "renewal" if mandate.plan is not None else "donation"


def _dart_of(user: User) -> str:
    """The name of the DART on ``user``'s profile, or ``None``."""
    profile = MemberProfile.objects.filter(user=user).select_related("dart").first()
    if profile is None or profile.dart is None:
        return NONE
    return profile.dart.name


# -- links -------------------------------------------------------------------------
def _portal(path: str) -> str:
    """The absolute address of the portal route ``path``."""
    return f"{settings.SITE_URL.rstrip('/')}/portal{path}"


def _member_link(user: User) -> str:
    """The member record of ``user``."""
    return _portal(f"/admin/members/{user.pk}")


def _user_link(user: User) -> str:
    """The user record of ``user``."""
    return _portal(f"/admin/users/{user.pk}")


def _payment_link(payment: Payment) -> str:
    """The payment's own record."""
    return _portal(f"/admin/payments/{payment.pk}")


# -- one builder per event ---------------------------------------------------------
#: What a builder returns: the headline, the lines, and the link.
type Built = tuple[str, list[Line], str]


def _signed_up(payload: Mapping[str, object]) -> Built:
    """``signed_up``: who joined, as what, and on which DART."""
    user = _required(payload, "user", User)
    dart = _optional(payload, "dart", Dart)
    kind = AccountKind(user.kind).label
    return (
        f"{user.display_name} signed up as a {kind.lower()}",
        [("Email", user.email), ("DART", NONE if dart is None else dart.name), ("Joined as", kind)],
        _member_link(user),
    )


def _member_added(payload: Mapping[str, object]) -> Built:
    """``member_added``: who an administrator created by hand."""
    user = _required(payload, "user", User)
    actor = _required(payload, "actor", User)
    return (
        f"{user.display_name} was added by {actor.display_name}",
        [("Email", user.email), ("Kind", AccountKind(user.kind).label), ("DART", _dart_of(user))],
        _member_link(user),
    )


def _became_friend(payload: Mapping[str, object]) -> Built:
    """``became_friend``: who is a friend now, and how that came about."""
    user = _required(payload, "user", User)
    how = _required(payload, "how", str)
    return (
        f"{user.display_name} is now a friend",
        [("Email", user.email), ("How", BECAME_FRIEND_HOW.get(how, how))],
        _member_link(user),
    )


def _became_member(payload: Mapping[str, object]) -> Built:
    """``became_member``: who is a member now, and how that came about."""
    user = _required(payload, "user", User)
    how = _required(payload, "how", str)
    return (
        f"{user.display_name} is now a member",
        [("Email", user.email), ("How", BECAME_MEMBER_HOW.get(how, how))],
        _member_link(user),
    )


def _membership_paid(payload: Mapping[str, object]) -> Built:
    """``membership_paid``: a payment that started or extended a term."""
    payment = _required(payload, "payment", Payment)
    term = _required(payload, "term", Membership)
    automatic = payload.get("automatic") is True
    name = payment.user.display_name
    through = _through(term)
    if automatic:
        headline = f"{name} renewed automatically through {through}"
    elif term.ends_on is None:
        headline = f"{name} paid for a lifetime membership"
    else:
        headline = f"{name} paid for membership through {through}"
    lines: list[Line] = [
        ("Plan", term.plan.name),
        ("Amount", money_label(payment.amount_cents)),
        ("Paid through", through),
    ]
    if payment.contribution_cents > 0:
        lines.append(("Contribution", money_label(payment.contribution_cents)))
    return headline, lines, _payment_link(payment)


def _membership_granted(payload: Mapping[str, object]) -> Built:
    """``membership_granted``: a term an administrator gave without a payment."""
    user = _required(payload, "user", User)
    term = _required(payload, "term", Membership)
    actor = _required(payload, "actor", User)
    through = _through(term)
    return (
        f"{actor.display_name} granted {user.display_name} membership through {through}",
        [("Plan", term.plan.name), ("Through", through)],
        _member_link(user),
    )


def _membership_expired(payload: Mapping[str, object]) -> Built:
    """``membership_expired``: a term that ran out, and what the person is now."""
    user = _required(payload, "user", User)
    term = _required(payload, "term", Membership)
    ended = _through(term)
    return (
        f"{user.display_name}'s membership expired on {ended}",
        [("Email", user.email), ("Kind now", account_kind(user).label)],
        _member_link(user),
    )


def _auto_renewal_on(payload: Mapping[str, object]) -> Built:
    """``auto_renewal_on``: a renewal or a recurring donation, set up."""
    mandate = _required(payload, "mandate", RenewalMandate)
    what: Line = (
        ("Plan", mandate.plan.name)
        if mandate.plan is not None
        else ("Amount", money_label(mandate.contribution_cents))
    )
    return (
        f"{mandate.user.display_name} turned on automatic {_mandate_kind(mandate)}",
        [
            what,
            ("Cadence", mandate.get_cadence_display()),
            ("Next charge", format_display_date(mandate.next_charge_on)),
        ],
        _member_link(mandate.user),
    )


def _auto_renewal_off(payload: Mapping[str, object]) -> Built:
    """``auto_renewal_off``: a renewal or a recurring donation, stopped, and how."""
    mandate = _required(payload, "mandate", RenewalMandate)
    how = _required(payload, "how", str)
    return (
        f"{mandate.user.display_name}'s automatic {_mandate_kind(mandate)} is off",
        [("How", AUTO_RENEWAL_OFF_HOW.get(how, how))],
        _member_link(mandate.user),
    )


def _next_try(mandate: RenewalMandate, next_on: date | None) -> str:
    """When a declined charge is tried again, or that none is left, from ``next_on``.

    ``next_on`` is the day the retry run scheduled the next attempt for, or ``None``
    once the mandate's retries are spent and it is paused; the caller names the day,
    so this never recomputes it from today's date.
    """
    if next_on is None:
        return f"None: automatic {_mandate_kind(mandate)} is paused"
    return format_display_date(next_on)


def _auto_renewal_declined(payload: Mapping[str, object]) -> Built:
    """``auto_renewal_declined``: a charge the provider refused, and the next try."""
    mandate = _required(payload, "mandate", RenewalMandate)
    reason = _required(payload, "reason", str)
    next_on = _optional(payload, "next_on", date)
    return (
        f"{mandate.user.display_name}'s automatic {_mandate_kind(mandate)} was declined",
        [("Reason", reason), ("Next try", _next_try(mandate, next_on))],
        _member_link(mandate.user),
    )


def _donation_received(payload: Mapping[str, object]) -> Built:
    """``donation_received``: a gift, once or from a recurring donation."""
    payment = _required(payload, "payment", Payment)
    name = payment.user.display_name
    amount = money_label(payment.amount_cents)
    recurring = payment.renewal_attempts.exists()
    return (
        f"{name} gave {amount}",
        [("From", name), ("Amount", amount), ("Kind", "Recurring" if recurring else "One-time")],
        _payment_link(payment),
    )


def _payment_recorded(payload: Mapping[str, object]) -> Built:
    """``payment_recorded``: a check or cash payment the treasurer entered by hand."""
    payment = _required(payload, "payment", Payment)
    actor = _required(payload, "actor", User)
    amount = money_label(payment.amount_cents)
    return (
        f"{actor.display_name} recorded a payment of {amount} for {payment.user.display_name}",
        [("Method", payment.get_wallet_display()), ("For", PaymentKind(payment.kind).label)],
        _payment_link(payment),
    )


def _payment_refunded(payload: Mapping[str, object]) -> Built:
    """``payment_refunded``: money given back, by whom, and whether it canceled a term."""
    payment = _required(payload, "payment", Payment)
    refund_cents = _required(payload, "refund_cents", int)
    actor = _optional(payload, "actor", User)
    term_canceled = payload.get("term_canceled") is True
    lines: list[Line] = [
        ("Of", money_label(payment.amount_cents)),
        ("By", DASHBOARD_ACTOR if actor is None else actor.display_name),
    ]
    if term_canceled:
        lines.append(("Membership canceled", "Yes"))
    return (
        f"{money_label(refund_cents)} refunded to {payment.user.display_name}",
        lines,
        _payment_link(payment),
    )


def _account_active(verb: str) -> Callable[[Mapping[str, object]], Built]:
    """The builder of ``account_<verb>``: whose account, and who did it."""

    def build(payload: Mapping[str, object]) -> Built:
        """``account_deactivated`` or ``account_reactivated``."""
        user = _required(payload, "user", User)
        actor = _optional(payload, "actor", User)
        return (
            f"{user.display_name}'s account was {verb}",
            [("By", _actor(actor, user))],
            _user_link(user),
        )

    return build


def _roles_changed(payload: Mapping[str, object]) -> Built:
    """``roles_changed``: the roles given, the roles taken, and the roles held now."""
    user = _required(payload, "user", User)
    actor = _required(payload, "actor", User)
    return (
        f"{actor.display_name} changed {user.display_name}'s roles",
        [
            ("Added", _role_labels(_words(payload, "added"))),
            ("Removed", _role_labels(_words(payload, "removed"))),
            ("Now", _role_labels(user.roles)),
        ],
        _user_link(user),
    )


def _email_changed(payload: Mapping[str, object]) -> Built:
    """``email_changed``: the address a person left and the one they confirmed."""
    user = _required(payload, "user", User)
    old_email = _required(payload, "old_email", str)
    return (
        f"{user.display_name} changed their email address",
        [("From", old_email), ("To", user.email)],
        _user_link(user),
    )


def _profile_changed(payload: Mapping[str, object]) -> Built:
    """``profile_changed``: the labels of the fields that changed, and by whom."""
    user = _required(payload, "user", User)
    actor = _optional(payload, "actor", User)
    return (
        f"{user.display_name}'s profile changed",
        [("Changed", _labels(_words(payload, "fields"))), ("By", _actor(actor, user))],
        _member_link(user),
    )


def _verification_changed(payload: Mapping[str, object]) -> Built:
    """``verification_changed``: which items a verifier verified and cleared.

    The payload names the ``actor``, the labels of the items ``verified`` and
    ``cleared``, and either the ``aircraft`` whose insurance it was or, failing that,
    the ``user`` whose certificate, medical, or photo ID it was.  The headline says
    the items were verified, or cleared, or otherwise (both, or neither) that the
    verification of the person's or the aircraft's details changed.
    """
    actor = _required(payload, "actor", User)
    verified = _words(payload, "verified")
    cleared = _words(payload, "cleared")
    aircraft = _optional(payload, "aircraft", Aircraft)
    if aircraft is not None:
        owner, link = aircraft.n_number, _portal(f"/admin/aircraft/{aircraft.pk}")
    else:
        user = _required(payload, "user", User)
        owner, link = user.display_name, _member_link(user)
    if verified and not cleared:
        items = _series([_in_a_sentence(label) for label in verified])
        headline = f"{actor.display_name} verified {owner}'s {items}"
    elif cleared and not verified:
        items = _series([_in_a_sentence(label) for label in cleared])
        headline = f"{actor.display_name} cleared the verification of {owner}'s {items}"
    else:
        headline = f"{actor.display_name} changed the verification of {owner}'s details"
    lines: list[Line] = [
        ("Verified", _labels(verified)),
        ("Cleared", _labels(cleared)),
        ("By", actor.display_name),
    ]
    return headline, lines, link


def _aircraft_event(verb: str) -> Callable[[Mapping[str, object]], Built]:
    """The builder of ``aircraft_<verb>``: which aircraft, what changed, and by whom.

    A removed aircraft is named by ``n_number`` and ``owner`` alone, since the record
    is gone, and its email links nowhere.
    """

    def build(payload: Mapping[str, object]) -> Built:
        """``aircraft_added``, ``aircraft_changed`` or ``aircraft_removed``."""
        actor = _optional(payload, "actor", User)
        lines: list[Line] = []
        link = ""
        if verb == "removed":
            n_number = _required(payload, "n_number", str)
            owner = _owner(payload.get("owner"))
        else:
            aircraft = _required(payload, "aircraft", Aircraft)
            n_number, owner = aircraft.n_number, aircraft.owner_name
            make_model = " ".join(part for part in (aircraft.make, aircraft.model) if part)
            lines.append(("Make and model", make_model or NONE))
            link = _portal(f"/admin/aircraft/{aircraft.pk}")
        if verb == "changed":
            fields = [_aircraft_field_label(name) for name in _words(payload, "fields")]
            lines.append(("Changed", _labels(fields)))
        if actor is not None:
            lines.append(("By", actor.display_name))
        headline = f"{n_number} {verb} for {owner}" if owner else f"{n_number} {verb}"
        return headline, lines, link

    return build


_BUILDERS: dict[str, Callable[[Mapping[str, object]], Built]] = {
    "signed_up": _signed_up,
    "member_added": _member_added,
    "became_friend": _became_friend,
    "became_member": _became_member,
    "membership_paid": _membership_paid,
    "membership_granted": _membership_granted,
    "membership_expired": _membership_expired,
    "auto_renewal_on": _auto_renewal_on,
    "auto_renewal_off": _auto_renewal_off,
    "auto_renewal_declined": _auto_renewal_declined,
    "donation_received": _donation_received,
    "payment_recorded": _payment_recorded,
    "payment_refunded": _payment_refunded,
    "account_deactivated": _account_active("deactivated"),
    "account_reactivated": _account_active("reactivated"),
    "roles_changed": _roles_changed,
    "email_changed": _email_changed,
    "profile_changed": _profile_changed,
    "verification_changed": _verification_changed,
    "aircraft_added": _aircraft_event("added"),
    "aircraft_changed": _aircraft_event("changed"),
    "aircraft_removed": _aircraft_event("removed"),
}
