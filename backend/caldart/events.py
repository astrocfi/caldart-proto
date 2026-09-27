"""The one way an app announces that something happened.

An app raises an event with :func:`emit` at the point the thing has definitively
happened, inside its own transaction, and never needs to know who listens.  A
listener registers with :func:`subscribe`; the notifications app does so when it
starts, and a test does so to record what a service raised.  This module imports
no app, so an app on any layer may import it.

:data:`EVENT_SLUGS` is the closed list of events; ``emit`` refuses any other slug,
so a misspelled event fails a test instead of quietly reaching nobody.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

#: A listener: it receives the event's slug and its payload, and returns nothing.
type Handler = Callable[[str, Mapping[str, object]], None]

#: Every event, in the order the screens list them.
EVENT_SLUGS: tuple[str, ...] = (
    "signed_up",
    "member_added",
    "became_friend",
    "became_member",
    "membership_paid",
    "membership_granted",
    "membership_expired",
    "auto_renewal_on",
    "auto_renewal_off",
    "auto_renewal_declined",
    "donation_received",
    "payment_recorded",
    "payment_refunded",
    "account_deactivated",
    "account_reactivated",
    "roles_changed",
    "email_changed",
    "profile_changed",
    "verification_changed",
    "aircraft_added",
    "aircraft_changed",
    "aircraft_removed",
)

_handlers: list[Handler] = []


def subscribe(handler: Handler) -> None:
    """Register ``handler`` to receive every event raised from now on.

    Handlers run in the order they were registered.  Registering the same handler
    twice registers it once.
    """
    if handler not in _handlers:
        _handlers.append(handler)


def unsubscribe(handler: Handler) -> None:
    """Remove ``handler``; removing one that is not registered does nothing."""
    if handler in _handlers:
        _handlers.remove(handler)


def emit(slug: str, **payload: object) -> None:
    """Raise the event ``slug`` with ``payload``, calling every handler at once.

    Handlers run synchronously, in registration order, inside the caller's
    transaction; a handler that wants to act only once the transaction commits
    arranges that itself.  A slug outside :data:`EVENT_SLUGS` raises ``ValueError``
    reading ``Unknown event '<slug>'`` before any handler runs.
    """
    if slug not in EVENT_SLUGS:
        raise ValueError(f"Unknown event '{slug}'")
    # A copy, so a handler that unsubscribes itself does not skip its neighbor.
    for handler in tuple(_handlers):
        handler(slug, payload)
