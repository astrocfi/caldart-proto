"""Who may hear about an event: the recipient rule every send and every edit applies.

A subscription bound to an account is sent an event only while that account is active
and holds a role the event allows; a system administrator and a Django superuser may
hear about every event.  A subscription to an address no account holds was confirmed
by the account administrator who set it up, and always may.  A bare address is bound
to whichever account later takes it, the next time it is sent something.
"""

from __future__ import annotations

from apps.accounts.models import User
from apps.accounts.permissions import user_has_any_role
from apps.notifications.events import EVENTS
from apps.notifications.models import NotificationSubscription


def account_may_receive(user: User, slug: str) -> bool:
    """Whether ``user``'s roles admit the event ``slug``, whether or not it is active.

    True for a Django superuser and a system administrator whatever the event; for
    anybody else, one of the event's roles must be among the account's own.
    """
    return user_has_any_role(user, EVENTS[slug].roles)


def recipient_may_receive(subscription: NotificationSubscription, slug: str) -> bool:
    """Whether ``subscription``'s recipient may be sent the event ``slug`` now.

    A bare address always may.  A bound account must be active and its roles must
    admit the event (:func:`account_may_receive`).
    """
    user = subscription.recipient_user
    if user is None:
        return True
    return user.is_active and account_may_receive(user, slug)


def refused_event(user: User, slugs: list[str]) -> str | None:
    """The first of ``slugs``, in the order given, that ``user``'s roles do not admit.

    ``None`` when the account may receive every one of them.
    """
    return next((slug for slug in slugs if not account_may_receive(user, slug)), None)


def refresh_recipient(subscription: NotificationSubscription) -> bool:
    """Bring ``subscription``'s recipient up to date, in memory; True when it changed.

    A bound subscription takes its account's current address, in lower case.  A bare
    address an account has since taken (compared without regard to case) is bound to
    that account, so the account's roles decide from then on what it may be sent.
    """
    user = subscription.recipient_user
    if user is None:
        user = User.objects.filter(email__iexact=subscription.recipient_email).first()
        if user is None:
            return False
        subscription.recipient_user = user
        subscription.recipient_email = user.email.lower()
        return True
    if subscription.recipient_email == user.email.lower():
        return False
    subscription.recipient_email = user.email.lower()
    return True
