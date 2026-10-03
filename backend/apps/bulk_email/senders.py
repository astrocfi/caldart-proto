"""Who may send bulk email, and to whom: everyone, or the members of one DART.

CalDART management (and a system administrator, who passes for every role) sends to any
member or friend.  A DART leader sends only to the DART on their own member profile: the
``dart_leader`` role names no DART of its own, so a leader whose profile names none has
nobody to send to.  :func:`sender_context` answers that for one account, and is what
``GET /bulk-email/sender`` serves the compose screen.

A bulk email's limit is its sender's, whoever is working on it: :func:`dart_limit` reads
the sender's profile as it is at that moment, so when a leader's profile DART changes,
the people their emails reach change with it from then on.  The batch (``batch.py``)
forces every add of a limited email to its DART and skips anybody outside it, and the
background sender (``job.py``) checks the limit once more when it starts the send.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from apps.accounts.models import User
from apps.accounts.permissions import user_has_any_role
from apps.accounts.roles import DART_LEADER, MANAGEMENT
from apps.bulk_email.models import BulkEmail
from apps.darts.models import Dart
from apps.members.models import MemberProfile

#: Why a DART leader whose profile names no DART cannot send.
NO_DART_MESSAGE = (
    "Your profile names no DART, so there is nobody to send to. Set your DART on My profile."
)

#: The refusal of an add that names a DART other than the email's own.
NOT_YOUR_DART_MESSAGE = "You can only send to your own DART."

#: Why a person outside a DART leader's DART is sent no copy.
SKIP_NOT_IN_DART = "Not in your DART"


@dataclass(frozen=True)
class SenderContext:
    """What ``user`` may send to: everyone for CalDART management, else one DART.

    ``is_management`` is true for CalDART management and a system administrator, who
    send to any member or friend.  For anybody else ``dart`` is the DART they may send
    to: their profile's DART when they are a DART leader, ``None`` when they are not or
    their profile names none.  ``user`` is ``None`` for an email whose sender's account
    is gone.
    """

    user: User | None
    is_management: bool
    dart: Dart | None

    @property
    def can_send(self) -> bool:
        """True when there is anybody this sender may send to."""
        return self.is_management or self.dart is not None

    @property
    def reason(self) -> str:
        """Why the sender cannot send, :data:`NO_DART_MESSAGE`; ``""`` when they can."""
        return "" if self.can_send else NO_DART_MESSAGE


@dataclass(frozen=True)
class DartLimit:
    """The one DART a bulk email may go to.

    ``dart`` is ``None`` when the email's sender is a DART leader whose profile names no
    DART, or holds neither bulk email role any more: then nobody may be sent a copy.
    """

    dart: Dart | None

    def allows(self, account: User) -> bool:
        """True when ``account``'s profile names this DART."""
        if self.dart is None:
            return False
        return _profile_dart_id(account) == self.dart.pk


def sender_context(user: User | None) -> SenderContext:
    """What ``user`` may send to, from their roles and their profile as they are now.

    CalDART management and a system administrator may send to everyone.  A DART leader
    may send to the DART on their profile, and to nobody when it names none.  Any other
    account, and ``None`` (a deleted sender), may send to nobody.
    """
    if user is None:
        return SenderContext(user=None, is_management=False, dart=None)
    if user_has_any_role(user, (MANAGEMENT,)):
        return SenderContext(user=user, is_management=True, dart=None)
    if not user_has_any_role(user, (DART_LEADER,)):
        return SenderContext(user=user, is_management=False, dart=None)
    profile = MemberProfile.objects.filter(user=user).select_related("dart").first()
    return SenderContext(
        user=user, is_management=False, dart=profile.dart if profile is not None else None
    )


def dart_limit(bulk: BulkEmail) -> DartLimit | None:
    """The DART ``bulk`` may go to, or ``None`` when it may go to anybody.

    The limit is the sender's (:func:`sender_context`), whoever is working on the email:
    none for CalDART management's email, the sender's DART for a DART leader's.  An email
    whose sender's account is gone has no limit here, since the background sender
    refuses it for that alone.
    """
    if bulk.sender is None:
        return None
    context = sender_context(bulk.sender)
    if context.is_management:
        return None
    return DartLimit(dart=context.dart)


def limited_filters(dart: Dart, filters: Mapping[str, str]) -> dict[str, str]:
    """``filters`` with the ``dart`` filter forced to ``dart``, for a limited email.

    A ``dart`` left out or blank becomes the DART's id, and so does one already naming
    it by id.  Raises ``ValueError`` with :data:`NOT_YOUR_DART_MESSAGE` for any other
    ``dart`` value, the DART's own name included: only its id is taken.
    """
    wanted = str(dart.pk)
    given = filters.get("dart", "").strip()
    if given not in ("", wanted):
        raise ValueError(NOT_YOUR_DART_MESSAGE)
    return {**filters, "dart": wanted}


def limit_dart(limit: DartLimit | None) -> Dart | None:
    """The DART an email with ``limit`` is recorded as going to: ``None`` without one."""
    return limit.dart if limit is not None else None


def email_dart_name(bulk: BulkEmail) -> str:
    """The name of the DART ``bulk`` goes to, or ``""`` when it may go to anybody.

    While the email can still change this is its sender's DART as it is now
    (:func:`dart_limit`), blank as well for a DART leader whose profile names none; once
    it has started sending it is the DART it was recorded as going to.
    """
    dart = bulk.dart if not bulk.can_edit else limit_dart(dart_limit(bulk))
    return str(dart.name) if dart is not None else ""


def _profile_dart_id(account: User) -> int | None:
    """The id of the DART on ``account``'s profile, or ``None`` without one."""
    profile: MemberProfile | None = getattr(account, "profile", None)
    return profile.dart_id if profile is not None else None
