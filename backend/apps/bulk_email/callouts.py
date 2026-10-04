"""Mission callouts: a bulk email that asks each recipient whether they can fly.

When CalDART activates for a mission it needs to know quickly who can fly.  A callout is
a bulk email with ``is_callout`` set and a :class:`~apps.bulk_email.models.Callout` row.
Every recipient's own copy carries three buttons, **Available**, **Available with
limits**, and **Not available**, each a link to the answer page with a token signed for
that callout and that person (``apps.bulk_email.callout_links``).  The page shows the
choice and a note field, and only its ``POST`` records the answer
(:func:`record_answer`), so a mail scanner that follows every link records nothing.  A
person may change their answer until the callout closes: at ``closes_at``, or sooner
with **Close now** (:func:`close`).  The token has no age limit of its own; the close
time rules.

The copy a sender sees (the preview, a test copy, a copy on the delivery report) carries
the buttons inert, pointing at ``callout_links.STAND_IN`` rather than a signed token, so
showing a person's copy to somebody else never hands over a link that answers for them.

The Callouts screen reads :func:`callout_rows`: one row per person the callout reached,
with their answer and the member check's go/no-go (``apps.aircraft.services``).
**Remind non-responders** (:func:`remind`) adds a round of rows for everybody in the
batch who has not answered, refreshed and checked as a retry is, and queues the email
for the background sender, which fills each copy with the person's values as they are
then.  Each new or changed answer raises the ``callout_answer`` event for the
notifications app.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.db import transaction
from django.db.models import Max, QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.permissions import user_has_any_role
from apps.accounts.roles import DART_LEADER, MANAGEMENT
from apps.aircraft.services import search_result
from apps.bulk_email.batch import (
    SKIP_DUPLICATE,
    skip_reason,
    snapshot,
    type_opt_outs,
)
from apps.bulk_email.fields import substitute
from apps.bulk_email.models import (
    BulkEmail,
    BulkEmailRecipient,
    BulkEmailStatus,
    Callout,
    CalloutAnswer,
    CalloutAnswerKind,
    RecipientStatus,
)
from apps.bulk_email.render import fill_subject, fill_values, message_tokens
from apps.bulk_email.richtext import sanitize
from apps.bulk_email.senders import dart_limit, readable_by
from apps.mail.models import EmailType
from apps.mail.types import sendable_types
from apps.members.models import MemberProfile
from apps.members.services import with_membership
from caldart import audit, events
from caldart.dates import format_display_datetime
from caldart.exceptions import DomainError, DomainValidationError
from caldart.reports import CSV_DOCUMENT_TYPE, ReportDocument, csv_rows

log = logging.getLogger(__name__)

#: How long a callout takes answers when the sender chooses no time: two days.
DEFAULT_OPEN_HOURS = 48

#: The default close time is rounded up to the next whole multiple of this many minutes.
ROUND_TO_MINUTES = 30

#: The slug of the email type a callout starts as, when its sender may send it.
MISSION_SLUG = "mission"

#: The longest note an answer keeps.
NOTE_MAX_LENGTH = 500

#: The longest reason a recipient row holds.
REASON_MAX_LENGTH = 200

#: The notification event each new or changed answer raises.
ANSWER_EVENT = "callout_answer"

#: Why a time for answers to close is refused.
CLOSES_PAST_MESSAGE = "Choose a time in the future."
CLOSES_BEFORE_SEND_MESSAGE = (
    "Answers would close before the email goes out. Choose a later time under Answers close."
)

#: Why an answer, a reminder, or a close is refused.
CLOSED_MESSAGE = "This callout has closed."
INACTIVE_MESSAGE = "This link no longer works."

#: Why a copy of a callout is not sent once its answers have closed.
CLOSED_REASON = "Callout closed"
NOT_SENT_MESSAGE = "This callout has not been sent."
STILL_SENDING_MESSAGE = "This callout is still sending. Remind the others once it has finished."
STOPPED_MESSAGE = "This callout was stopped. Send the rest first, then remind the others."
EVERYBODY_ANSWERED_MESSAGE = "Everybody has answered, so there is nobody to remind."
NOBODY_TO_REMIND_MESSAGE = (
    "Nobody who has not answered can be sent a reminder now: each would be skipped, "
    "as the delivery report shows why."
)

#: The statuses of a copy that reached the mail server for its reader.
REACHED_STATUSES: frozenset[str] = frozenset({RecipientStatus.SENT, RecipientStatus.BOUNCED})

#: The answers CSV's columns, in order.
ANSWERS_CSV_HEADER: tuple[str, ...] = (
    "Name",
    "Email",
    "Answer",
    "Note",
    "Answered at",
    "DART",
    "Home airport",
    "Aircraft",
    "Go/no-go",
)


@dataclass(frozen=True)
class CalloutRow:
    """One person a callout reached, with their answer and what the member check shows.

    ``account`` is the person's account with its membership annotations.  ``answer`` is
    their answer, ``None`` while they have given none.  ``go`` is the member check's
    three verdicts, ``membership``, ``medical``, and ``verified``
    (``apps.aircraft.services.search_result``); the person is a go when all three hold.
    ``aircraft`` holds the N-numbers on their profile.
    """

    account: User
    answer: CalloutAnswer | None
    dart_name: str
    home_airport: str
    aircraft: tuple[str, ...]
    go: dict[str, bool]

    @property
    def is_go(self) -> bool:
        """True when the member check reads GO: every one of its verdicts holds."""
        return all(self.go.values())


@dataclass(frozen=True)
class CalloutCounts:
    """How many people a callout reached, and how many gave each answer or none."""

    reached: int
    available: int
    limited: int
    unavailable: int
    no_answer: int


@dataclass(frozen=True)
class Reminder:
    """One round of **Remind non-responders**: its number, when, and how many it queued.

    ``count`` counts the reminders that were to go, leaving out the people the round
    skipped.
    """

    round: int
    requested_at: datetime
    count: int


@dataclass(frozen=True)
class AnswerPage:
    """What the answer page shows one recipient: the callout, their copy, their answer.

    ``subject`` and ``body_html`` are the message as the person's copy had it, filled in
    from the values stored on their latest row; ``body_html`` is sanitized.  ``answer`` is
    their current answer, ``None`` before the first.
    """

    callout: Callout
    user: User
    subject: str
    body_html: str
    answer: CalloutAnswer | None

    @property
    def is_open(self) -> bool:
        """True while the callout takes answers."""
        return is_open(self.callout)


def callout_of(bulk: BulkEmail) -> Callout | None:
    """``bulk``'s :class:`Callout` row, or ``None`` when it is not a callout."""
    if not bulk.is_callout:
        return None
    return Callout.objects.filter(bulk_email=bulk).first()


# -- when answers close ----------------------------------------------------------------
def is_open(callout: Callout, now: datetime | None = None) -> bool:
    """True while ``callout`` takes answers: until ``closes_at``, unless closed sooner."""
    moment = now if now is not None else timezone.now()
    return callout.closed_at is None and moment < callout.closes_at


def closed_moment(callout: Callout) -> datetime:
    """When ``callout`` stops taking answers: **Close now**'s time, else ``closes_at``."""
    return callout.closed_at if callout.closed_at is not None else callout.closes_at


def default_closes_at(now: datetime | None = None) -> datetime:
    """:data:`DEFAULT_OPEN_HOURS` from ``now``, rounded up to the next half hour."""
    moment = (now if now is not None else timezone.now()) + timedelta(hours=DEFAULT_OPEN_HOURS)
    step = ROUND_TO_MINUTES * 60
    seconds = math.ceil(moment.timestamp() / step) * step
    return datetime.fromtimestamp(seconds, tz=moment.tzinfo)


def mission_type(user: User) -> EmailType | None:
    """The Mission type when ``user`` may send it, else ``None``."""
    return next((kind for kind in sendable_types(user) if kind.slug == MISSION_SLUG), None)


# -- the compose screen ----------------------------------------------------------------
def apply_settings(
    locked: BulkEmail,
    *,
    is_callout: bool | None,
    closes_at: datetime | None,
    actor: User | None,
    now: datetime | None = None,
) -> list[str]:
    """Make the editable ``locked`` a callout or not, and set when its answers close.

    ``is_callout`` true makes the email a callout: its :class:`Callout` row is made with
    ``closes_at``, or :func:`default_closes_at` when none is given, and its type becomes
    Mission when ``actor`` is given and may send that (:func:`mission_type`).  False
    makes it an ordinary email again and deletes the row, which holds no answer before a
    send.
    ``closes_at`` alone moves the close time of an email that is a callout already; it
    must be after ``now``, or ``DomainValidationError`` keyed ``closes_at`` with
    :data:`CLOSES_PAST_MESSAGE` is raised, and it is ignored for an email that is not
    a callout.  Answers the names of the email's own fields that changed; the caller
    saves them.  The caller holds the email's row lock.
    """
    moment = now if now is not None else timezone.now()
    if closes_at is not None and closes_at <= moment:
        raise DomainValidationError("closes_at", CLOSES_PAST_MESSAGE)
    changed: list[str] = []
    if is_callout is True and not locked.is_callout:
        locked.is_callout = True
        changed.append("is_callout")
        Callout.objects.update_or_create(
            bulk_email=locked,
            defaults={"closes_at": closes_at if closes_at is not None else default_closes_at()},
        )
        mission = None if actor is None else mission_type(actor)
        if mission is not None and locked.email_type_id != mission.pk:
            locked.email_type = mission
            changed.append("email_type")
        return changed
    if is_callout is False and locked.is_callout:
        locked.is_callout = False
        changed.append("is_callout")
        Callout.objects.filter(bulk_email=locked).delete()
        return changed
    if closes_at is not None and locked.is_callout:
        Callout.objects.filter(bulk_email=locked).update(closes_at=closes_at)
    return changed


def check_for_send(bulk: BulkEmail, start_at: datetime) -> None:
    """Refuse a callout whose answers would close at or before ``start_at``.

    Raises ``DomainValidationError`` keyed ``closes_at`` with
    :data:`CLOSES_BEFORE_SEND_MESSAGE`.  An email that is not a callout passes.
    """
    callout = callout_of(bulk)
    if callout is not None and callout.closes_at <= start_at:
        raise DomainValidationError("closes_at", CLOSES_BEFORE_SEND_MESSAGE)


# -- answering -------------------------------------------------------------------------
def answer_page(callout: Callout, user: User) -> AnswerPage:
    """What the answer page shows ``user`` for ``callout``.

    The message is filled in from the values stored on the person's latest row that was
    tried, so it reads as their copy did; a person never tried reads it with every
    field empty, so each fallback stands.
    """
    bulk = callout.bulk_email
    row = (
        bulk.recipients.filter(user=user, tried_at__isnull=False)
        .order_by("-tried_at", "-pk")
        .first()
    )
    values: dict[str, str] = {} if row is None else {str(k): str(v) for k, v in row.values.items()}
    filled = {**dict.fromkeys(message_tokens(bulk), ""), **values}
    return AnswerPage(
        callout=callout,
        user=user,
        subject=substitute(bulk.subject, filled, escape=False),
        body_html=substitute(sanitize(bulk.body), filled, escape=True),
        answer=CalloutAnswer.objects.filter(callout=callout, user=user).first(),
    )


def record_answer(
    callout: Callout, user: User, *, answer: str, note: str, now: datetime | None = None
) -> CalloutAnswer:
    """Record ``user``'s ``answer`` to ``callout``, with ``note``; return it as saved.

    ``answer`` is one of :class:`~apps.bulk_email.models.CalloutAnswerKind`'s values and
    ``note`` is trimmed and cut to :data:`NOTE_MAX_LENGTH`.  A person's earlier answer is
    replaced, and ``answered_at`` set to ``now``.  A new answer, or one whose answer
    changed, raises the :data:`ANSWER_EVENT` event (:func:`_raise_answer`) and writes one
    ``callout.answer`` audit line; a change to the note alone is saved without either,
    so editing a note emails nobody, and the same answer and note sent again changes
    nothing.  Raises ``DomainError`` with :data:`INACTIVE_MESSAGE` for a deactivated
    account, :data:`CLOSED_MESSAGE` once the callout has closed, and ``ValueError`` for
    an answer that is not one of the kinds; nothing is recorded then.
    """
    if answer not in CalloutAnswerKind.values:
        raise ValueError(f"Not a callout answer: {answer!r}")
    if not user.is_active:
        raise DomainError(INACTIVE_MESSAGE)
    moment = now if now is not None else timezone.now()
    clean_note = note.strip()[:NOTE_MAX_LENGTH]
    with transaction.atomic():
        locked = Callout.objects.select_for_update().get(pk=callout.pk)
        if not is_open(locked, moment):
            raise DomainError(CLOSED_MESSAGE)
        existing = CalloutAnswer.objects.filter(callout=locked, user=user).first()
        if existing is not None and (existing.answer, existing.note) == (answer, clean_note):
            return existing
        saved, _created = CalloutAnswer.objects.update_or_create(
            callout=locked,
            user=user,
            defaults={"answer": answer, "note": clean_note, "answered_at": moment},
        )
        if existing is None or existing.answer != answer:
            audit.record(audit.CALLOUT_ANSWER, actor=user, target=locked.bulk_email, answer=answer)
            _raise_answer(locked.bulk_email, user, answer=answer, note=clean_note)
    return saved


def _raise_answer(bulk: BulkEmail, user: User, *, answer: str, note: str) -> None:
    """Raise :data:`ANSWER_EVENT` for ``user``'s ``answer`` to the callout ``bulk``.

    The payload carries plain values, so the notifications app, which sits beside this
    one, needs nothing of it: ``user``; ``answer``, the answer in words; ``note``;
    ``subject``, the callout's subject as the sender's own copy would read
    (:func:`display_subject`); ``callout_id``, the bulk email's id;
    and ``audience``, a function that answers whether an account may open the callout
    (:func:`can_see`), so a DART leader hears only of the callouts they may read.
    """
    events.emit(
        ANSWER_EVENT,
        user=user,
        answer=CalloutAnswerKind(answer).label,
        note=note,
        subject=display_subject(bulk),
        callout_id=bulk.pk,
        audience=lambda account: can_see(account, bulk),
    )


def display_subject(bulk: BulkEmail) -> str:
    """``bulk``'s subject filled in with its sender's own values, as the screens show it.

    A recipient field such as ``{first_name}`` reads as the sender's own value, or its
    fallback once the sender's account is gone, so no screen or notification shows a
    token in braces.
    """
    return fill_subject(bulk.subject, fill_values(bulk, bulk.sender))


# -- the sender's actions --------------------------------------------------------------
def close(bulk: BulkEmail, *, actor: User, now: datetime | None = None) -> Callout:
    """**Close now**: stop ``bulk``'s callout taking answers from ``now``.

    A round of copies queued and not yet started, a round of reminders or the rest of a
    stopped send, is called off: each of its ``pending`` copies becomes ``skipped`` with
    :data:`CLOSED_REASON`, ``skipped_count`` grows, and the email reads ``sent`` again
    (its ``sent_at`` set now when it never had one).  A round the sender is sending
    stops before its next copy (:func:`closed_reason`).  Raises ``DomainError`` with
    :data:`NOT_SENT_MESSAGE` for a callout that has not started sending, and
    :data:`CLOSED_MESSAGE` for one already closed.  One ``callout.close`` audit line
    names ``actor``.
    """
    moment = now if now is not None else timezone.now()
    with transaction.atomic():
        locked = BulkEmail.objects.select_for_update().get(pk=bulk.pk)
        callout = Callout.objects.select_for_update().get(bulk_email=locked)
        if locked.started_at is None:
            raise DomainError(NOT_SENT_MESSAGE)
        if not is_open(callout, moment):
            raise DomainError(CLOSED_MESSAGE)
        callout.closed_at = moment
        callout.closed_by = actor
        callout.save(update_fields=["closed_at", "closed_by"])
        if locked.status == BulkEmailStatus.QUEUED:
            locked.skipped_count += skip_pending(locked, moment)
            locked.status = BulkEmailStatus.SENT
            locked.sent_at = locked.sent_at if locked.sent_at is not None else moment
            locked.save(update_fields=["skipped_count", "status", "sent_at", "updated_at"])
    audit.record(audit.CALLOUT_CLOSE, actor=actor, target=locked)
    return callout


def closed_reason(bulk: BulkEmail, now: datetime | None = None) -> str:
    """:data:`CLOSED_REASON` when ``bulk`` is a callout that has closed; else ``""``.

    The background sender asks this when it starts the email and before every copy, so
    nobody is sent a callout, or a reminder, that can no longer be answered.
    """
    callout = callout_of(bulk)
    if callout is None or is_open(callout, now):
        return ""
    return CLOSED_REASON


def skip_pending(bulk: BulkEmail, now: datetime | None = None) -> int:
    """Mark every ``pending`` copy of ``bulk`` skipped with :data:`CLOSED_REASON`.

    Answers how many; the caller adds them to ``skipped_count`` and saves the email.
    """
    moment = now if now is not None else timezone.now()
    return bulk.recipients.filter(status=RecipientStatus.PENDING).update(
        status=RecipientStatus.SKIPPED, reason=CLOSED_REASON, updated_at=moment
    )


def remind(bulk: BulkEmail, *, actor: User, now: datetime | None = None) -> Reminder:
    """**Remind non-responders**: queue the callout again for everybody yet to answer.

    Everybody the callout reached who has not answered, the people :func:`callout_rows`
    lists with no answer, gets a row of a fresh round, one more than the highest so
    far, taking the account's name, address, kind, and DART
    as they are now and asked ``batch.skip_reason`` afresh, as **Retry failed** asks
    it: with the DART a DART leader's email is limited to, the type's opt-outs, and the
    addresses of this round and of everybody who has answered, so an address shared
    with somebody who answered is not reminded.  A row that passes is ``pending``, the
    rest ``skipped`` with the reason, and ``skipped_count`` grows.  The email is queued
    to start at ``now``; the background sender sends the round with the same message,
    each copy filled in with the person's values as they are then, and checks once more
    that the sender may send the type and that nobody has turned it off.
    ``Callout.reminded_at`` is set.  Returns the round as a :class:`Reminder`.

    Raises ``DomainError``, changing nothing, with :data:`NOT_SENT_MESSAGE` for a callout
    that never started, :data:`STOPPED_MESSAGE` for a stopped one,
    :data:`STILL_SENDING_MESSAGE` for one queued or sending, :data:`CLOSED_MESSAGE` once
    it has closed, :data:`EVERYBODY_ANSWERED_MESSAGE` when nobody is left, and
    :data:`NOBODY_TO_REMIND_MESSAGE` when everybody left would be skipped.  One
    ``callout.remind`` audit line names ``actor``, the round, the reminders queued, and
    the people skipped.
    """
    moment = now if now is not None else timezone.now()
    with transaction.atomic():
        locked = BulkEmail.objects.select_for_update().get(pk=bulk.pk)
        callout = Callout.objects.select_for_update().get(bulk_email=locked)
        _check_remind(locked, callout, moment)
        answered = set(callout.answers.values_list("user_id", flat=True))
        waiting = list(
            User.objects.filter(pk__in=_reached_ids(locked), is_active=True)
            .exclude(pk__in=answered)
            .select_related("profile", "profile__dart")
            .order_by("last_name", "first_name", "email", "pk")
        )
        if len(waiting) == 0:
            raise DomainError(EVERYBODY_ANSWERED_MESSAGE)
        number = (locked.recipients.aggregate(top=Max("round"))["top"] or 0) + 1
        rows = _reminder_rows(locked, waiting, number, answered)
        queued = sum(1 for row in rows if row.status == RecipientStatus.PENDING)
        if queued == 0:
            raise DomainError(NOBODY_TO_REMIND_MESSAGE)
        BulkEmailRecipient.objects.bulk_create(rows)
        skipped = len(rows) - queued
        locked.skipped_count += skipped
        locked.status = BulkEmailStatus.QUEUED
        locked.start_at = moment
        locked.scheduled = False
        locked.save(
            update_fields=["skipped_count", "status", "start_at", "scheduled", "updated_at"]
        )
        callout.reminded_at = moment
        callout.save(update_fields=["reminded_at"])
    audit.record(
        audit.CALLOUT_REMIND,
        actor=actor,
        target=locked,
        round=number,
        recipients=queued,
        skipped=skipped,
    )
    return Reminder(round=number, requested_at=moment, count=queued)


def is_reminder_finish(bulk: BulkEmail) -> bool:
    """True when the copies ``bulk`` just finished were a reminder round, not a retry.

    That is a callout reminded more recently than its latest **Retry failed**, or
    reminded with no retry at all.
    """
    callout = callout_of(bulk)
    if callout is None or callout.reminded_at is None:
        return False
    retry = bulk.retries.order_by("-requested_at", "-pk").first()
    return retry is None or retry.requested_at < callout.reminded_at


def reminder_finished(bulk: BulkEmail) -> None:
    """Write the ``callout.remind_finished`` line of ``bulk``'s latest reminder round.

    It names the email's sender (or the ``command`` actor once that account is gone),
    the round, and how many of its copies went and failed.
    """
    number = bulk.recipients.aggregate(top=Max("round"))["top"] or 0
    tried = bulk.recipients.filter(round=number)
    audit.record(
        audit.CALLOUT_REMIND_FINISHED,
        actor=bulk.sender if bulk.sender is not None else audit.COMMAND_ACTOR,
        target=bulk,
        round=number,
        sent=tried.filter(status__in=list(REACHED_STATUSES)).count(),
        failed=tried.filter(status=RecipientStatus.FAILED).count(),
    )


# -- who sees a callout, and what they see ---------------------------------------------
def visible_callouts(user: User) -> QuerySet[BulkEmail]:
    """The callouts ``user`` may open: every one for CalDART management.

    CalDART management and a system administrator see every callout that has started
    sending.  A DART leader sees the ones they sent, and the ones sent to the DART on
    their own profile as it is now (``apps.bulk_email.senders.readable_by``); anybody
    else sees none.
    """
    if not user_has_any_role(user, (MANAGEMENT, DART_LEADER)):
        return BulkEmail.objects.none()
    return (
        readable_by(user)
        .filter(is_callout=True, started_at__isnull=False)
        .select_related("callout", "callout__closed_by")
    )


def can_see(user: User, bulk: BulkEmail) -> bool:
    """True when ``user`` may open the callout ``bulk`` (:func:`visible_callouts`)."""
    return visible_callouts(user).filter(pk=bulk.pk).exists()


def callout_rows(bulk: BulkEmail) -> list[CalloutRow]:
    """One row per person ``bulk``'s callout reached, in surname order.

    A person is reached once a copy of any round went to the mail server for them
    (``sent``, or ``bounced`` afterwards); a person who answered is listed too.  Each
    row reads the account as it is now: its DART, home airport, aircraft, and the member
    check's go/no-go.  An account since deleted or deactivated is not listed, and neither
    is its answer.
    """
    callout = callout_of(bulk)
    answers: dict[int, CalloutAnswer] = (
        {}
        if callout is None
        else {answer.user_id: answer for answer in callout.answers.filter(user__is_active=True)}
    )
    accounts = with_membership(
        User.objects.filter(pk__in=set(_reached_ids(bulk)) | set(answers), is_active=True)
        .select_related("profile", "profile__dart")
        .prefetch_related("profile__aircraft")
        .order_by("last_name", "first_name", "email", "pk")
    )
    return [_row(account, answers.get(account.pk)) for account in accounts]


def counts_for(bulk: BulkEmail) -> CalloutCounts:
    """How many people ``bulk``'s callout reached, and how many gave each answer or none.

    The people are those :func:`callout_rows` lists, counted without reading their
    profiles, so a list of callouts costs a few queries each.
    """
    callout = callout_of(bulk)
    given: dict[int, str] = (
        {}
        if callout is None
        else dict(callout.answers.filter(user__is_active=True).values_list("user_id", "answer"))
    )
    reached = set(_reached_ids(bulk)) | set(given)
    kinds = list(given.values())
    return CalloutCounts(
        reached=len(reached),
        available=kinds.count(CalloutAnswerKind.AVAILABLE),
        limited=kinds.count(CalloutAnswerKind.LIMITED),
        unavailable=kinds.count(CalloutAnswerKind.UNAVAILABLE),
        no_answer=len(reached) - len(given),
    )


def reminders(bulk: BulkEmail) -> list[Reminder]:
    """Each round of reminders ``bulk`` has had, oldest first.

    A round's time is when its rows were made, and its count the rows that were to go,
    leaving out those it skipped.
    """
    rounds: dict[int, Reminder] = {}
    for row in bulk.recipients.filter(round__gt=0).order_by("round", "created_at"):
        counted = 0 if row.status == RecipientStatus.SKIPPED else 1
        known = rounds.get(row.round)
        rounds[row.round] = Reminder(
            round=row.round,
            requested_at=row.created_at if known is None else known.requested_at,
            count=counted if known is None else known.count + counted,
        )
    return list(rounds.values())


def answers_document(bulk: BulkEmail) -> ReportDocument:
    """The callout's answers as a CSV, one row per person in :func:`callout_rows` order.

    The columns are :data:`ANSWERS_CSV_HEADER`: the name and address, the answer in
    words (blank for none), the note, when it was given (``MM/DD/YYYY at h:mm AM`` in
    the site's time zone, blank for none), the DART, the home airport, the aircraft
    (N-numbers separated by commas), and ``GO`` or ``NO-GO``.  The file is named
    ``caldart-callout-<id>-answers.csv``.
    """
    rows = [
        (
            row.account.display_name,
            row.account.email,
            "" if row.answer is None else CalloutAnswerKind(row.answer.answer).label,
            "" if row.answer is None else row.answer.note,
            "" if row.answer is None else format_display_datetime(row.answer.answered_at),
            row.dart_name,
            row.home_airport,
            ", ".join(row.aircraft),
            "GO" if row.is_go else "NO-GO",
        )
        for row in callout_rows(bulk)
    ]
    return ReportDocument(
        filename=f"caldart-callout-{bulk.pk}-answers.csv",
        media_type=CSV_DOCUMENT_TYPE,
        content="".join(csv_rows(ANSWERS_CSV_HEADER, rows)).encode(),
    )


# -- helpers ---------------------------------------------------------------------------
def _check_remind(bulk: BulkEmail, callout: Callout, now: datetime) -> None:
    """Refuse **Remind non-responders** unless ``bulk`` has finished and is still open."""
    if bulk.started_at is None:
        raise DomainError(NOT_SENT_MESSAGE)
    if bulk.status == BulkEmailStatus.STOPPED:
        raise DomainError(STOPPED_MESSAGE)
    if bulk.status != BulkEmailStatus.SENT:
        raise DomainError(STILL_SENDING_MESSAGE)
    if not is_open(callout, now):
        raise DomainError(CLOSED_MESSAGE)


def _reminder_rows(
    bulk: BulkEmail, waiting: list[User], number: int, answered: set[int]
) -> list[BulkEmailRecipient]:
    """Unsaved rows of round ``number`` for the accounts of ``waiting``, each sorted.

    Each row takes its account as it is now (``batch.snapshot``) and
    ``batch.skip_reason``'s answer, with ``seen`` holding the addresses of the people
    who ``answered`` and of the rows already made.
    """
    opt_outs = type_opt_outs(bulk)
    limit = dart_limit(bulk)
    seen = {
        _folded(address)
        for address in User.objects.filter(pk__in=answered).values_list("email", flat=True)
    }
    made: list[BulkEmailRecipient] = []
    for account in waiting:
        reason = skip_reason(account, seen, opt_outs=opt_outs, limit=limit)
        row = BulkEmailRecipient(bulk_email=bulk, user=account, round=number)
        snapshot(row, account)
        row.reason = reason[:REASON_MAX_LENGTH]
        row.status = RecipientStatus.PENDING if reason == "" else RecipientStatus.SKIPPED
        if reason == "" or reason == SKIP_DUPLICATE:
            seen.add(_folded(account.email))
        made.append(row)
    return made


def _reached_ids(bulk: BulkEmail) -> QuerySet[BulkEmailRecipient, int]:
    """The account ids of the people a copy of ``bulk``, of any round, went to."""
    return bulk.recipients.filter(
        status__in=list(REACHED_STATUSES), user__isnull=False, user__is_active=True
    ).values_list("user_id", flat=True)


def _row(account: User, answer: CalloutAnswer | None) -> CalloutRow:
    """``account``'s :class:`CalloutRow`, with the member check's verdicts."""
    profile: MemberProfile | None = getattr(account, "profile", None)
    result = search_result(account)
    return CalloutRow(
        account=account,
        answer=answer,
        dart_name="" if result["dart"] is None else str(result["dart"]),
        home_airport="" if profile is None else profile.home_airport_identifier,
        aircraft=()
        if profile is None
        else tuple(sorted(plane.n_number for plane in profile.aircraft.all())),
        go={name: bool(value) for name, value in result["go_no_go"].items()},
    )


def _folded(address: str) -> str:
    """``address`` trimmed and case-folded, as the batch compares addresses."""
    return address.strip().casefold()
