"""The links a mission callout's copy carries: three answer buttons and its own page.

Each recipient's copy of a callout carries **Available**, **Available with limits**, and
**Not available**, each a link to the answer page, ``<SITE_URL>/mail/callout/<token>``,
with ``?answer=<kind>`` choosing the button's answer.  The token is
``django.core.signing`` with the salt :data:`ANSWER_SALT` over the callout's id and the
account's id, and carries no age limit: whether a link still records an answer is the
callout's close time's to say (``apps.bulk_email.callouts``).  A copy a sender sees
carries :data:`STAND_IN` where the token goes, so it answers for nobody.

This module reads no other part of the bulk email app but its models, so the copy's
renderer and the callouts module can both use it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from django.conf import settings
from django.core import signing
from django.utils import timezone

from apps.accounts.models import User
from apps.bulk_email.models import Callout, CalloutAnswerKind

#: Keeps a callout token from being read as any other signed value.
ANSWER_SALT = "bulk_email.callout"

#: The answer page's path, before the token, below the site's own root.
CALLOUT_PATH = "/mail/callout/"

#: What stands where a signed token goes in a link a sender sees: the link reads as a
#: recipient's does, but answers for nobody.
STAND_IN = "preview"

#: The answers in the order the email, the page, and the screen offer them.
ANSWER_ORDER: tuple[str, ...] = (
    CalloutAnswerKind.AVAILABLE,
    CalloutAnswerKind.LIMITED,
    CalloutAnswerKind.UNAVAILABLE,
)


class CalloutLinkError(Exception):
    """A callout token that was tampered with, or names a callout or account now gone.

    The message is for the log; the page the visitor sees says only that the link does
    not work.
    """


@dataclass(frozen=True)
class AnswerLink:
    """One answer button of a callout copy: its answer, its words, and its link."""

    kind: str
    label: str
    url: str


def make_token(callout: Callout, user: User) -> str:
    """A signed token naming ``callout`` and ``user``, with no time limit of its own."""
    return signing.dumps({"c": callout.pk, "u": user.pk}, salt=ANSWER_SALT)


def read_token(token: str) -> tuple[Callout, User]:
    """The callout and the account ``token`` names.

    Raises :class:`CalloutLinkError` when the signature does not match, when the payload
    is not the shape :func:`make_token` writes, or when the callout or the account has
    since been deleted.  A token never expires: whether it still records an answer is
    the callout's close time's to say (:func:`is_open`).
    """
    try:
        payload = signing.loads(token, salt=ANSWER_SALT)
    except signing.BadSignature as error:
        raise CalloutLinkError("The callout token is not one this site signed.") from error
    if not isinstance(payload, dict):
        raise CalloutLinkError("The callout token carries no callout and account.")
    callout_id = payload.get("c")
    user_id = payload.get("u")
    if not isinstance(callout_id, int) or not isinstance(user_id, int):
        raise CalloutLinkError("The callout token carries no callout and account.")
    callout = (
        Callout.objects.select_related("bulk_email", "bulk_email__sender")
        .filter(pk=callout_id)
        .first()
    )
    user = User.objects.filter(pk=user_id).first()
    if callout is None or user is None:
        raise CalloutLinkError("The callout token names a callout or account now gone.")
    return callout, user


def answer_url(token: str, kind: str | None = None) -> str:
    """The absolute link of the answer page for ``token``, choosing ``kind`` when given.

    Built on ``SITE_URL``, which carries the path the site is served under:
    ``<SITE_URL>/mail/callout/<token>?answer=<kind>``.  ``token`` is a signed token, or
    :data:`STAND_IN` for a link that answers for nobody.
    """
    base = f"{settings.SITE_URL.rstrip('/')}{CALLOUT_PATH}{token}"
    return base if kind is None else f"{base}?answer={kind}"


def link_token(callout: Callout | None, user: User | None, *, live: bool) -> str:
    """The token a copy's links carry: signed for ``user`` when ``live``, else a stand-in.

    A copy with no callout row, or for an account that is gone, carries the stand-in.
    """
    if not live or callout is None or user is None:
        return STAND_IN
    return make_token(callout, user)


def answer_links(token: str) -> list[AnswerLink]:
    """The three answer buttons of a callout copy, each a link carrying ``token``."""
    return [
        AnswerLink(kind=kind, label=CalloutAnswerKind(kind).label, url=answer_url(token, kind))
        for kind in ANSWER_ORDER
    ]


def at_words(moment: datetime) -> str:
    """``moment`` in the site's time zone, as a reader says it: ``10/05/2026 at 2:00 PM``.

    The hour is on the 12-hour clock with ``AM`` or ``PM``.
    """
    local = timezone.localtime(moment)
    hour = local.hour % 12 or 12
    period = "AM" if local.hour < 12 else "PM"
    return f"{local:%m/%d/%Y} at {hour}:{local:%M} {period}"
