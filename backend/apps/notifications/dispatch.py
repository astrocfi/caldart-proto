"""Where a raised event becomes the emails the subscribed addresses receive.

:func:`handle` is registered with :func:`caldart.events.subscribe` when the app starts,
so it runs inside the transaction of whatever raised the event.  It builds the email
there, while the objects the event names are in hand, and sends it once that
transaction commits, so a request that rolls back sends nothing.  Each recipient is
sent through :func:`caldart.mail.send_templated`, which records every send in the
email log under the purpose ``notification_<slug>``.  A refused send is logged and the
next recipient is still tried: nothing a notification does can fail the request that
raised the event.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass

from django.db import IntegrityError, transaction

from apps.accounts.models import User
from apps.bulk_email.callouts import can_see
from apps.bulk_email.models import Callout
from apps.darts.models import Dart
from apps.notifications.events import EVENTS
from apps.notifications.messages import Message, build_message
from apps.notifications.models import NotificationSubscription
from apps.notifications.services import recipient_may_receive, refresh_recipient
from caldart import events
from caldart.mail import contact_email, error_name, org_name, send_templated

log = logging.getLogger(__name__)

#: The template pair every notification is rendered from.
TEMPLATE = "notification"

#: The event whose email also goes to the chosen DART's roster contacts.
SIGNED_UP = "signed_up"

#: The event whose email reaches an account only when it may open the callout.
CALLOUT_ANSWER = "callout_answer"

#: Whether one bound account may be sent one raised event, beyond its roles.
type Audience = Callable[[User], bool]


@dataclass(frozen=True)
class Recipient:
    """One address an event's email goes to, and how the email log records it.

    ``user_id`` is the bound account, or ``None`` for an address with no account;
    ``name`` is the name the log records; ``why`` is the footer line saying why the
    address hears about the event.
    """

    email: str
    user_id: int | None
    name: str
    why: str


def handle(slug: str, payload: Mapping[str, object]) -> None:
    """Build the email for the event ``slug`` now, and send it once the caller commits.

    ``payload`` holds the objects the event was raised with.  The DART roster contacts
    a sign-up also goes to are read now as well; the subscriptions are read when the
    transaction commits (:func:`send`).

    Nothing here raises into the caller: a payload the email cannot be built from is
    logged with its traceback and sends nothing, and a failure while sending is logged
    by Django's robust ``on_commit`` handling.
    """
    try:
        message = build_message(slug, payload)
        extra = roster_recipients(payload.get("dart")) if slug == SIGNED_UP else []
        audience = audience_for(slug, payload)
    # Broad on purpose: whatever went wrong, the service that raised the event has
    # already done its work, and a notification must never undo or fail it.
    except Exception:
        log.exception("notification not built: event=%s", slug)
        return
    transaction.on_commit(lambda: send(slug, message, extra, audience), robust=True)


def audience_for(slug: str, payload: Mapping[str, object]) -> Audience | None:
    """Who among the bound accounts the event may reach, beyond its roles; ``None``: all.

    A ``callout_answer`` reaches an account only when it may open the callout
    (``apps.bulk_email.callouts.can_see``): CalDART management every callout, and a DART
    leader the ones they sent or that went to their own DART.
    """
    callout = payload.get("callout")
    if slug != CALLOUT_ANSWER or not isinstance(callout, Callout):
        return None
    bulk = callout.bulk_email
    return lambda user: can_see(user, bulk)


@contextmanager
def suspended() -> Iterator[None]:
    """Stop the dispatcher from hearing events for the length of the block.

    Seeding raises the same events a real change would -- an already-lapsed term,
    a friend switch -- and would otherwise mail whatever subscriptions exist by the
    time its transaction commits, which includes the ones the seed itself just
    created.  ``seed_demo`` runs inside this to seed without mailing anybody.
    :func:`handle` is resubscribed once the block ends, even if it raised.
    """
    events.unsubscribe(handle)
    try:
        yield
    finally:
        events.subscribe(handle)


def roster_recipients(dart: object) -> list[Recipient]:
    """The contacts ticked to receive ``dart``'s roster; nobody when ``dart`` is none."""
    if not isinstance(dart, Dart):
        return []
    why = f"You are receiving this because the {dart.name} lists you to receive its roster."
    return [
        Recipient(email=contact.email, user_id=None, name=contact.name, why=why)
        for contact in dart.roster_recipients()
    ]


def subscribed_recipients(slug: str, audience: Audience | None = None) -> list[Recipient]:
    """Every active subscription to ``slug`` whose recipient may receive it, by address.

    Each subscription's recipient is brought up to date first (a bare address an account
    has taken is bound to it, a bound one takes the account's current address) and the
    change saved, unless another subscription already holds that address.  A recipient
    who may not receive the event is left out, and its subscription is left as it is;
    so is a bound account ``audience``, when given, turns away.
    """
    label = EVENTS[slug].label
    why = f"You are receiving this because this address is subscribed to the {label} notification."
    found: list[Recipient] = []
    rows = NotificationSubscription.objects.filter(is_active=True, events__contains=[slug])
    for subscription in rows.select_related("recipient_user"):
        if refresh_recipient(subscription):
            _save_recipient(subscription)
        if not recipient_may_receive(subscription, slug):
            continue
        user = subscription.recipient_user
        if audience is not None and user is not None and not audience(user):
            continue
        found.append(
            Recipient(
                email=subscription.recipient_email,
                user_id=None if user is None else user.pk,
                name="" if user is None else user.display_name,
                why=why,
            )
        )
    return found


def send(
    slug: str, message: Message, extra: list[Recipient], audience: Audience | None = None
) -> None:
    """Send ``message`` once to every subscribed recipient, then to each of ``extra``.

    ``audience``, when given, narrows the subscribed accounts (:func:`audience_for`).

    An address is sent the event once however many ways it qualifies, compared without
    regard to case, and a subscriber's footer wins over a roster contact's.  A send that
    fails, whatever it raises, is logged here and in the email log, and the next
    recipient is tried.
    """
    event = EVENTS[slug]
    seen: set[str] = set()
    for recipient in [*subscribed_recipients(slug, audience), *extra]:
        address = recipient.email.lower()
        if address in seen:
            continue
        seen.add(address)
        context: dict[str, object] = {
            "org_name": org_name(),
            "contact_email": contact_email(),
            "event_label": event.label,
            "headline": message.headline,
            "lines": message.lines,
            "link": message.link,
            "why": recipient.why,
        }
        try:
            send_templated(
                to=recipient.email,
                subject=message.subject,
                template=TEMPLATE,
                context=context,
                purpose=event.purpose,
                user_id=recipient.user_id,
                to_name=recipient.name,
            )
        # Broad on purpose: a refusal, a dropped connection, or a header Django will
        # not send must not cost the remaining recipients their email.
        except Exception as exc:
            # The event and the exception class only: the email log already names
            # the refused address, and this log is no place to collect addresses.
            log.error("notification send failed: event=%s error=%s", slug, error_name(exc))


def _save_recipient(subscription: NotificationSubscription) -> None:
    """Save ``subscription``'s refreshed recipient, unless another row holds the address.

    Two subscriptions can come to name one address when an account moves to an address
    that already has its own subscription; the refreshed recipient is then used for this
    send alone.
    """
    try:
        with transaction.atomic():
            subscription.save(update_fields=["recipient_user", "recipient_email", "updated_at"])
    except IntegrityError:
        log.warning("notification subscription %s shares its address", subscription.pk)
