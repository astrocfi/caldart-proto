"""The catalog of events an address can subscribe to.

Each event names what happened, in the words the screen and the email log use,
the category it is listed under, and the roles whose holders may hear about it.
A system administrator and a superuser may hear about every event; a DART leader hears
of a callout answer only for a callout they may open.  The slugs
are exactly those of ``caldart.events.EVENT_SLUGS``, in the same order.
"""

from __future__ import annotations

from dataclasses import dataclass

from apps.accounts.roles import ACCOUNT_ADMIN, DART_LEADER, MANAGEMENT, TREASURER, USER_ADMIN

#: The categories, in the order the screen groups them.
CATEGORIES: tuple[str, ...] = ("Membership", "Money", "Accounts", "Aircraft", "Callouts")

_MEMBERSHIP_ROLES = (ACCOUNT_ADMIN, USER_ADMIN)
_MONEY_ROLES = (TREASURER, ACCOUNT_ADMIN)
_ACCOUNT_ROLES = (USER_ADMIN, ACCOUNT_ADMIN)
_AIRCRAFT_ROLES = (ACCOUNT_ADMIN,)
# The roles that send and read mission callouts; a DART leader hears only of the
# callouts they may open (``apps.notifications.dispatch``).
_CALLOUT_ROLES = (MANAGEMENT, DART_LEADER)


@dataclass(frozen=True)
class Event:
    """One event: its slug, its label, its category, its description, and its roles."""

    slug: str
    label: str
    category: str
    description: str
    roles: tuple[str, ...]

    @property
    def purpose(self) -> str:
        """The email log purpose of the notification this event sends."""
        return f"notification_{self.slug}"


_EVENTS: tuple[Event, ...] = (
    Event(
        "signed_up",
        "Sign-up",
        "Membership",
        "Somebody registered on the site, as a member or as a friend.",
        _MEMBERSHIP_ROLES,
    ),
    Event(
        "member_added",
        "Member added by an administrator",
        "Membership",
        "An administrator created a member or friend by hand.",
        _MEMBERSHIP_ROLES,
    ),
    Event(
        "became_friend",
        "Member became a friend",
        "Membership",
        "A member chose to be a friend, lapsed into one, or was made one by an administrator.",
        _MEMBERSHIP_ROLES,
    ),
    Event(
        "became_member",
        "Friend became a member",
        "Membership",
        "A friend paid for membership, was granted it, or was made a member by an administrator.",
        _MEMBERSHIP_ROLES,
    ),
    Event(
        "membership_paid",
        "Membership paid",
        "Membership",
        "A payment started or extended a membership, by hand or automatically.",
        _MEMBERSHIP_ROLES,
    ),
    Event(
        "membership_granted",
        "Membership granted by an administrator",
        "Membership",
        "An administrator granted or extended a membership without a payment.",
        _MEMBERSHIP_ROLES,
    ),
    Event(
        "membership_expired",
        "Membership expired",
        "Membership",
        "A membership ran out.",
        _MEMBERSHIP_ROLES,
    ),
    Event(
        "auto_renewal_on",
        "Automatic payment turned on",
        "Money",
        "Somebody set up automatic renewal or a recurring donation.",
        _MONEY_ROLES,
    ),
    Event(
        "auto_renewal_off",
        "Automatic payment turned off",
        "Money",
        "An automatic renewal or recurring donation was turned off, by the person, "
        "an administrator, a lapse, or a deactivation.",
        _MONEY_ROLES,
    ),
    Event(
        "auto_renewal_declined",
        "Automatic payment declined",
        "Money",
        "An automatic charge was declined and will be tried again.",
        _MONEY_ROLES,
    ),
    Event(
        "donation_received",
        "Donation received",
        "Money",
        "A gift arrived: a public donation, a contribution, or a recurring donation.",
        _MONEY_ROLES,
    ),
    Event(
        "payment_recorded",
        "Payment recorded by hand",
        "Money",
        "The treasurer recorded a check or cash payment.",
        _MONEY_ROLES,
    ),
    Event(
        "payment_refunded",
        "Payment refunded",
        "Money",
        "A payment was refunded, in whole or in part.",
        _MONEY_ROLES,
    ),
    Event(
        "account_deactivated",
        "Account deactivated",
        "Accounts",
        "An account was deactivated, by the person or by an administrator.",
        _ACCOUNT_ROLES,
    ),
    Event(
        "account_reactivated",
        "Account reactivated",
        "Accounts",
        "A deactivated account was brought back.",
        _ACCOUNT_ROLES,
    ),
    Event(
        "roles_changed",
        "Roles changed",
        "Accounts",
        "An administrator granted or took away a role.",
        _ACCOUNT_ROLES,
    ),
    Event(
        "email_changed",
        "Email address changed",
        "Accounts",
        "Somebody changed the address on their account and confirmed the new one.",
        _ACCOUNT_ROLES,
    ),
    Event(
        "profile_changed",
        "Profile changed",
        "Accounts",
        "A profile was edited, by the person or by an administrator.",
        _ACCOUNT_ROLES,
    ),
    Event(
        "verification_changed",
        "Verification recorded",
        "Accounts",
        "A verifier verified or cleared a member's certificate, medical, or photo ID, "
        "or an aircraft's insurance.",
        (USER_ADMIN, ACCOUNT_ADMIN),
    ),
    Event(
        "aircraft_added",
        "Aircraft added",
        "Aircraft",
        "An aircraft was added to a member's list.",
        _AIRCRAFT_ROLES,
    ),
    Event(
        "aircraft_changed",
        "Aircraft changed",
        "Aircraft",
        "An aircraft's details or insurance changed.",
        _AIRCRAFT_ROLES,
    ),
    Event(
        "aircraft_removed",
        "Aircraft removed",
        "Aircraft",
        "An aircraft was taken off a member's list.",
        _AIRCRAFT_ROLES,
    ),
    Event(
        "callout_answer",
        "Callout answer",
        "Callouts",
        "Somebody answered a mission callout, or changed their answer.",
        _CALLOUT_ROLES,
    ),
)

#: Every event by slug, in the order the screen lists them.
EVENTS: dict[str, Event] = {event.slug: event for event in _EVENTS}
