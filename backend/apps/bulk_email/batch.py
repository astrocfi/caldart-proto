"""A bulk email's batch: the people it goes to, built from several filtered adds.

The sender chooses people with the member list's own filters
(``apps.members.filters.MemberAdminFilterSet``), so a filter that works on the member
list chooses the same people here, friends included through ``kind``.  Each press of
**Add to batch** runs the filters and adds everybody they choose who is not in the batch
yet, as a ``batched`` :class:`~apps.bulk_email.models.BulkEmailRecipient` row with the
account's name, address, kind, and DART as they are now; :func:`add_filters` answers how
many joined and how many were there already.

Whether each person will receive a copy is worked out afresh whenever the batch is read
(:func:`batch_rows`), from the account as it is then: :func:`skip_reason` names why a
copy is skipped, in a fixed order.  The background sender asks the same question once
more when it starts the send, and stores the answer (``apps.bulk_email.job``).

Every change to the batch takes the email's row lock first (:func:`locked_for_edit`), so
a change and the sender's start never overlap, and a change to an email that has started
sending is refused.  A change to the batch of a queued email takes it back to a draft
(:func:`back_to_draft`): the count the sender confirmed no longer holds, so the email
must be sent again.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import cast

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import F, QuerySet
from rest_framework.exceptions import ValidationError

from apps.accounts.models import User
from apps.accounts.roles import ROLE_LABELS
from apps.bulk_email.models import (
    BatchAdd,
    BulkEmail,
    BulkEmailRecipient,
    BulkEmailStatus,
    RecipientGroup,
    RecipientKind,
    RecipientStatus,
)
from apps.bulk_email.senders import (
    OWNER_NO_DART_MESSAGE,
    SKIP_NOT_IN_DART,
    DartLimit,
    dart_limit,
    limit_dart,
    limited_filters,
)
from apps.darts.models import Dart
from apps.mail.types import opted_out_user_ids
from apps.members.filters import EXPORT_FILTER_PARAMS, MemberAdminFilterSet, member_admin_queryset
from apps.members.models import MemberProfile, MembershipState
from apps.members.services import membership_of, with_membership
from caldart import audit
from caldart.dates import format_display_datetime
from caldart.exceptions import DomainError
from caldart.reports import (
    CSV_DOCUMENT_TYPE,
    ReportDocument,
    apply_filterset,
    csv_rows,
    given_params,
)

#: The member list's filters a batch may be built with, in the order the list names
#: them.  The list's own **Include deactivated** switch is not one: a deactivated
#: account is always added and listed as skipped.  Nor is ``ordering``, which sorts the
#: list and chooses nobody.
FILTER_KEYS: tuple[str, ...] = tuple(key for key in EXPORT_FILTER_PARAMS if key != "ordering")

#: What each filter is called on the member list's filter bar, for an add's label.
FILTER_LABELS: dict[str, str] = {
    "kind": "Kind",
    "search": "Search",
    "status": "Membership",
    "certificate": "Certificate",
    "medical": "Medical",
    "dart": "DART",
    "county": "County",
    "role": "Role",
    "expiring_within": "Expiring within (days)",
}

#: What the member list's filter bar calls each kind, which an add's label repeats.
KIND_FILTER_LABELS: dict[str, str] = {"member": "Members only", "friend": "Friends only"}

#: An add with no filter chose every member and friend.
EVERYBODY_LABEL = "Everybody"

#: Why a person in the batch is sent no copy, in the order :func:`skip_reason` asks.
SKIP_DELETED = "Account deleted"
SKIP_DEACTIVATED = "Account deactivated"
SKIP_NO_ADDRESS = "No email address"
SKIP_INVALID = "Invalid email address"
SKIP_BOUNCED = "Address bounced"
SKIP_DUPLICATE = "Duplicate address"
#: Why a person who has turned the email's type off is sent no copy; ``{type}`` is the
#: type's name.
SKIP_OPTED_OUT = "Opted out of {type}"

#: The audit reasons a queued email goes back to a draft for: its batch changed, or its
#: type did, either of which changes the count the sender confirmed.
BATCH_CHANGED = "batch_changed"
TYPE_CHANGED = "type_changed"

#: The refusal of any change to an email that has started sending.
NOT_EDITABLE_MESSAGE = "This email has been sent and cannot be changed."

#: The columns of a send's results CSV.
RESULTS_CSV_HEADER: tuple[str, ...] = (
    "Name",
    "Email",
    "Kind",
    "DART",
    "Result",
    "Reason",
    "Tried at",
    "Email type",
)

#: The columns of the batch CSV.
BATCH_CSV_HEADER: tuple[str, ...] = (
    "Name",
    "Email",
    "Kind",
    "DART",
    "Membership status",
    "Chosen by",
    "Will receive",
    "Reason",
    "Email type",
)


@dataclass(frozen=True)
class AddResult:
    """What one add did.

    ``added`` people joined the batch, ``already_present`` were in it already, and the
    batch now holds ``count``.
    """

    added: int
    already_present: int
    count: int


@dataclass(frozen=True)
class TypeOptOuts:
    """Who has turned a bulk email's type off: the type's ``name`` and their account ids.

    ``user_ids`` is empty for a type that does not allow opting out.
    """

    name: str
    user_ids: frozenset[int]


@dataclass(frozen=True)
class BatchRow:
    """One row of the batch, with the account behind it as it is now.

    ``account`` is null once the account is deleted; it carries the membership
    annotations, so its status reads without a further query.  ``reason`` is why the
    person is sent no copy, blank for one who will receive it: worked out now for a
    ``batched`` row, and the stored reason for a row the send has already frozen.
    """

    recipient: BulkEmailRecipient
    account: User | None
    reason: str

    @property
    def will_receive(self) -> bool:
        """True when the person is sent a copy (or was, once the send has started)."""
        return self.reason == ""


@dataclass(frozen=True)
class BatchCounts:
    """How many people are in the batch, how many receive a copy, and how many not."""

    count: int
    receiving: int
    skipped: int


def unknown_filters(filters: Mapping[str, str]) -> list[str]:
    """The keys of ``filters`` that are not filters of the member list, in order."""
    return [key for key in filters if key not in FILTER_KEYS]


def given_filters(filters: Mapping[str, str]) -> dict[str, str]:
    """The filters of ``filters`` that carry a value, in :data:`FILTER_KEYS` order.

    A blank value narrows nothing, and a key that is not a member list filter is
    dropped.
    """
    return given_params(filters, FILTER_KEYS)


def selected_accounts(filters: Mapping[str, str]) -> QuerySet[User]:
    """Every member and friend ``filters`` select, deactivated ones included.

    The filters narrow the member list's queryset exactly as on the member list, with
    **Include deactivated** on.  A donor is never there.  The accounts come in surname
    order, then first name, then address.  A filter value the member list refuses
    raises DRF's ``ValidationError`` keyed by that filter.
    """
    params = {**given_filters(filters), "include_inactive": "true"}
    accounts = apply_filterset(MemberAdminFilterSet, params, member_admin_queryset())
    # Each row carries the membership annotations, which ``membership_of`` reads.
    return cast("QuerySet[User]", accounts.order_by("last_name", "first_name", "email", "pk"))


def locked_for_edit(bulk: BulkEmail) -> BulkEmail:
    """``bulk`` read afresh under its row lock, once it may still be changed.

    Call it inside a transaction: the lock is held until that commits, so the
    background sender cannot start the email half way through a change.  Raises
    ``DomainError`` with :data:`NOT_EDITABLE_MESSAGE` once the email is no longer a
    draft or queued, or has ever started sending (:attr:`BulkEmail.can_edit`).
    """
    locked = BulkEmail.objects.select_for_update().get(pk=bulk.pk)
    if not locked.can_edit:
        raise DomainError(NOT_EDITABLE_MESSAGE)
    return locked


def add_filters(bulk: BulkEmail, filters: Mapping[str, str], *, actor: User) -> AddResult:
    """Add everybody ``filters`` choose to ``bulk``'s batch; say how many joined.

    The filters are the member list's (:func:`selected_accounts`).  Every account they
    choose that is not in the batch yet (by account, not by address) joins it as a
    ``batched`` row carrying the account's name, address, kind, and DART as they are
    now, and one :class:`~apps.bulk_email.models.BatchAdd` records the given filters
    and the two counts.  Accounts already in the batch are counted and left alone.
    ``actor`` is the account pressing **Add to batch**; the batch belongs to the email,
    whoever builds it.  A queued email goes back to a draft (:func:`back_to_draft`).

    A DART leader's email is limited to the sender's DART
    (``apps.bulk_email.senders.dart_limit``), whoever adds to it: the ``dart`` filter is
    forced to that DART, and the email records it as its ``dart``.

    Raises ``DomainError`` when the email has started sending, DRF's
    ``ValidationError`` for a filter value the member list refuses and, keyed
    ``filters`` then ``dart``, for a limited email's add naming another DART (by id or
    by name), and ``DomainError`` with ``OWNER_NO_DART_MESSAGE`` naming the sender when
    the email is limited to no DART at all; nothing is stored then.
    """
    with transaction.atomic():
        locked = locked_for_edit(bulk)
        forced = _within_limit(locked, filters)
        return add_accounts(
            locked, selected_accounts(forced), actor=actor, filters=given_filters(forced)
        )


def add_accounts(
    bulk: BulkEmail,
    accounts: Iterable[User],
    *,
    actor: User,
    filters: Mapping[str, str] | None = None,
    group: RecipientGroup | None = None,
    label: str = "",
) -> AddResult:
    """Add ``accounts`` to ``bulk``'s batch as one add; say how many joined.

    Every account not in the batch yet (by account) joins it as a ``batched`` row
    carrying the account's name, address, kind, and DART as they are now; the others
    are counted and left alone.  One :class:`~apps.bulk_email.models.BatchAdd` records
    the two counts with ``filters`` (the member list filters behind it, empty for
    none), ``group`` (the saved group it brought in, if any), and ``label`` (its name
    when it was not made with filters).  ``accounts`` is read inside the email's row
    lock.  A queued email goes back to a draft (:func:`back_to_draft`), naming
    ``actor``.

    A DART leader's email (``apps.bulk_email.senders.dart_limit``) records its DART,
    as an add by filters does; anybody added from outside it is skipped as
    ``Not in your DART`` whenever the batch is read (:func:`skip_reason`).  Raises
    ``DomainError`` when the email has started sending, and with
    ``OWNER_NO_DART_MESSAGE`` naming the sender when the email is limited to no DART at
    all; nothing is stored then.
    """
    with transaction.atomic():
        locked = locked_for_edit(bulk)
        _record_limit(locked)
        present = set(
            locked.recipients.filter(round=0, user__isnull=False).values_list("user_id", flat=True)
        )
        chosen = list(accounts)
        joining = [account for account in chosen if account.pk not in present]
        add = BatchAdd.objects.create(
            bulk_email=locked,
            filters=dict(filters) if filters is not None else {},
            group=group,
            label=label,
            added_count=len(joining),
            already_count=len(chosen) - len(joining),
        )
        BulkEmailRecipient.objects.bulk_create(
            [_new_row(locked, account, add) for account in joining]
        )
        back_to_draft(locked, actor=actor)
    return AddResult(
        added=add.added_count,
        already_present=add.already_count,
        count=batch_queryset(bulk).count(),
    )


def _within_limit(locked: BulkEmail, filters: Mapping[str, str]) -> dict[str, str]:
    """``filters`` forced to ``locked``'s DART limit, which ``locked`` records.

    An email with no limit takes the filters as they are.  Raises ``DomainError`` for an
    email limited to no DART, and DRF's
    ``ValidationError`` keyed ``filters`` then ``dart`` for an add naming another DART.
    """
    limit = _record_limit(locked)
    if limit is None or limit.dart is None:
        return dict(filters)
    try:
        return limited_filters(limit.dart, filters)
    except ValueError as refused:
        raise ValidationError({"filters": {"dart": [str(refused)]}}) from refused


def _record_limit(locked: BulkEmail) -> DartLimit | None:
    """``locked``'s DART limit, recorded as its ``dart``; ``None`` for no limit.

    Raises ``DomainError`` with ``OWNER_NO_DART_MESSAGE`` for an email limited to no
    DART, to which nobody may be added.
    """
    limit = dart_limit(locked)
    if limit is None:
        return None
    if limit.dart is None:
        raise DomainError(OWNER_NO_DART_MESSAGE.format(name=_sender_name(locked)))
    if locked.dart_id != limit.dart.pk:
        locked.dart = limit_dart(limit)
        locked.save(update_fields=["dart"])
    return limit


def _sender_name(bulk: BulkEmail) -> str:
    """The display name of ``bulk``'s sender, or ``""`` once the account is gone."""
    return bulk.sender.display_name if bulk.sender is not None else ""


def remove(bulk: BulkEmail, recipient_id: int, *, actor: User) -> None:
    """Take one person out of ``bulk``'s batch, as ``actor``.

    A queued email goes back to a draft (:func:`back_to_draft`).  Raises
    ``BulkEmailRecipient.DoesNotExist`` when ``recipient_id`` is not a row of this
    batch, and ``DomainError`` when the email has started sending.
    """
    with transaction.atomic():
        locked = locked_for_edit(bulk)
        row = batch_queryset(locked).get(pk=recipient_id)
        row.delete()
        back_to_draft(locked, actor=actor)


def clear(bulk: BulkEmail, *, actor: User) -> int:
    """Empty ``bulk``'s batch, its adds included; return how many people were in it.

    A queued email goes back to a draft (:func:`back_to_draft`).  Raises
    ``DomainError`` when the email has started sending.
    """
    with transaction.atomic():
        locked = locked_for_edit(bulk)
        removed, _by_model = batch_queryset(locked).delete()
        locked.adds.all().delete()
        back_to_draft(locked, actor=actor)
    return removed


def back_to_draft(locked: BulkEmail, *, actor: User, reason: str = BATCH_CHANGED) -> None:
    """Save a change to who ``locked`` reaches; a queued email goes back to a draft.

    ``locked`` is the email :func:`locked_for_edit` gave, inside the same transaction.
    Its ``updated_at`` moves on.  A queued email loses its ``start_at``, ``scheduled``,
    and ``confirm_count``, since the people the sender confirmed are no longer the
    ones it would reach, and one ``bulk_email.cancel`` audit line names ``actor`` with
    ``reason``: :data:`BATCH_CHANGED` for a change to the batch, :data:`TYPE_CHANGED`
    for a change of type, which changes who is skipped as opted out.
    """
    if locked.status != BulkEmailStatus.QUEUED:
        locked.save(update_fields=["updated_at"])
        return
    locked.status = BulkEmailStatus.DRAFT
    locked.start_at = None
    locked.scheduled = False
    locked.confirm_count = None
    locked.save(update_fields=["status", "start_at", "scheduled", "confirm_count", "updated_at"])
    audit.record(audit.BULK_EMAIL_CANCEL, actor=actor, target=locked, reason=reason)


def batch_queryset(bulk: BulkEmail) -> QuerySet[BulkEmailRecipient]:
    """Every row of ``bulk``'s batch: its original round, whatever each row's status."""
    return BulkEmailRecipient.objects.filter(bulk_email=bulk, round=0)


def surname_order(rows: QuerySet[BulkEmailRecipient]) -> QuerySet[BulkEmailRecipient]:
    """``rows`` in the order a send goes: surname, first name, then name and address.

    The rows of a deleted account come last, in name order.
    """
    return rows.order_by(
        F("user__last_name").asc(nulls_last=True),
        F("user__first_name").asc(nulls_last=True),
        "name",
        "email",
        "pk",
    )


def batch_rows(bulk: BulkEmail) -> list[BatchRow]:
    """The batch in surname order, each row with its account and its reason.

    The rows come in the account's surname order, then first name, then address,
    with the rows of deleted accounts last in name order: the order the send goes
    in.  A ``batched`` row's reason is :func:`skip_reason` for its account as it is
    now, with the opt-outs of the email's type as they are now, so an address that
    bounced or a person who opted out since being added is skipped, and two
    accounts sharing an address are sent one copy, to the first in that order.  A
    DART leader's email skips anybody whose profile is not in the sender's DART as it
    is now (``apps.bulk_email.senders.dart_limit``).  A row the send has frozen keeps
    its stored status and reason.
    """
    rows = list(surname_order(batch_queryset(bulk)).select_related("added_by"))
    accounts = _accounts_by_id(row.user_id for row in rows)
    opt_outs = type_opt_outs(bulk)
    limit = dart_limit(bulk)
    seen: set[str] = set()
    answered: list[BatchRow] = []
    for row in rows:
        account = accounts.get(row.user_id) if row.user_id is not None else None
        if row.status == RecipientStatus.BATCHED:
            reason = skip_reason(account, seen, opt_outs=opt_outs, limit=limit)
            if reason == "" and account is not None:
                seen.add(_folded(account.email))
        else:
            reason = row.reason if row.status in _NOT_RECEIVING else ""
        answered.append(BatchRow(recipient=row, account=account, reason=reason))
    return answered


def batch_counts(rows: list[BatchRow]) -> BatchCounts:
    """How many of ``rows`` there are, how many receive a copy, and how many not."""
    receiving = sum(1 for row in rows if row.will_receive)
    return BatchCounts(count=len(rows), receiving=receiving, skipped=len(rows) - receiving)


def type_opt_outs(bulk: BulkEmail) -> TypeOptOuts | None:
    """Who has turned ``bulk``'s type off, or ``None`` while it has no type."""
    if bulk.email_type is None:
        return None
    return TypeOptOuts(name=bulk.email_type.name, user_ids=opted_out_user_ids(bulk.email_type))


def skip_reason(
    account: User | None,
    seen: set[str],
    *,
    opt_outs: TypeOptOuts | None = None,
    limit: DartLimit | None = None,
) -> str:
    """Why ``account`` is sent no copy, or ``""`` when it is sent one.

    The reasons are asked in this order: :data:`SKIP_DELETED` when there is no
    account any more, ``apps.bulk_email.senders.SKIP_NOT_IN_DART`` when ``limit`` is
    given and the account's profile is not in its DART, :data:`SKIP_DEACTIVATED` when
    it is deactivated, :data:`SKIP_NO_ADDRESS` when its address is blank,
    :data:`SKIP_INVALID` when the address is not one a mail server could take,
    :data:`SKIP_BOUNCED` when the bounce check has marked the address
    (``email_bounced_at`` is set, until a user administrator clears it or the address
    changes), :data:`SKIP_OPTED_OUT` naming the type when ``opt_outs`` holds the
    account, and :data:`SKIP_DUPLICATE` when ``seen``, the trimmed and case-folded
    addresses already sent a copy, holds it.  Without ``opt_outs``, as for an email
    with no type yet, nobody is skipped as opted out; without ``limit``, as for CalDART
    management's email, nobody is skipped for their DART.
    """
    if account is None:
        return SKIP_DELETED
    if limit is not None and not limit.allows(account):
        return SKIP_NOT_IN_DART
    if not account.is_active:
        return SKIP_DEACTIVATED
    address = account.email.strip()
    if address == "":
        return SKIP_NO_ADDRESS
    try:
        validate_email(address)
    except DjangoValidationError:
        return SKIP_INVALID
    if account.email_bounced_at is not None:
        return SKIP_BOUNCED
    if opt_outs is not None and account.pk in opt_outs.user_ids:
        return SKIP_OPTED_OUT.format(type=opt_outs.name)
    if _folded(address) in seen:
        return SKIP_DUPLICATE
    return ""


def add_label(filters: Mapping[str, str]) -> str:
    """An add's filters in words, as the compose screen and the CSV name the add.

    Each filter reads as its name on the member list's filter bar and its value in
    words, such as ``"Kind: Friends only, County: Marin, Napa"``: a kind as the filter
    bar offers it, a DART by its name, a role by its label, and any other choice by the
    label the filter gives it.  An add with no filter
    reads :data:`EVERYBODY_LABEL`.
    """
    if len(filters) == 0:
        return EVERYBODY_LABEL
    return ", ".join(
        f"{FILTER_LABELS.get(key, key)}: {_value_label(key, value)}"
        for key, value in filters.items()
    )


def add_name(add: BatchAdd) -> str:
    """What the compose screen and the CSV call ``add``: its own label, or its filters.

    An add made with filters is named by them (:func:`add_label`); one that was not,
    such as a saved group's, keeps the label it was given when it was made.
    """
    return add.label if add.label != "" else add_label(add.filters)


def batch_document(bulk: BulkEmail) -> ReportDocument:
    """The batch as a CSV, one row per person in the order :func:`batch_rows` gives.

    The columns are :data:`BATCH_CSV_HEADER`: the name, address, kind, and DART the row
    holds, the account's membership status now (blank once it is deleted), the label
    of the add that chose the person, ``Yes`` or ``No``, the reason, and the email's
    type (blank while it has none).  The file is named
    ``caldart-bulk-email-<id>-recipient-list.csv``.
    """
    labels = {add.pk: add_name(add) for add in bulk.adds.all()}
    type_name = email_type_name(bulk)
    rows = [
        (
            row.recipient.name,
            row.recipient.email,
            _kind_label(row.recipient.kind),
            row.recipient.dart_name,
            _membership_label(row.account),
            labels.get(row.recipient.added_by_id or 0, ""),
            "Yes" if row.will_receive else "No",
            row.reason,
            type_name,
        )
        for row in batch_rows(bulk)
    ]
    content = "".join(csv_rows(BATCH_CSV_HEADER, rows)).encode()
    return ReportDocument(
        filename=f"caldart-bulk-email-{bulk.pk}-recipient-list.csv",
        media_type=CSV_DOCUMENT_TYPE,
        content=content,
    )


def results_document(bulk: BulkEmail) -> ReportDocument:
    """A send's results as a CSV, one row per person in the order the send went.

    The columns are :data:`RESULTS_CSV_HEADER`: the name, address, kind, and DART the
    copy went to, the result in words (such as ``Sent``, ``Failed``, ``Skipped``,
    ``Bounced``, or ``Not sent (stopped)``), the reason, when the copy was last tried
    (``MM/DD/YYYY at h:mm AM`` in the site's time zone, blank when never), and the
    email's type.  The file is named ``caldart-bulk-email-<id>-recipients.csv``.
    """
    type_name = email_type_name(bulk)
    rows = [
        (
            row.name,
            row.email,
            _kind_label(row.kind),
            row.dart_name,
            RecipientStatus(row.status).label,
            row.reason,
            format_display_datetime(row.tried_at) if row.tried_at is not None else "",
            type_name,
        )
        for row in surname_order(batch_queryset(bulk))
    ]
    content = "".join(csv_rows(RESULTS_CSV_HEADER, rows)).encode()
    return ReportDocument(
        filename=f"caldart-bulk-email-{bulk.pk}-recipients.csv",
        media_type=CSV_DOCUMENT_TYPE,
        content=content,
    )


def email_type_name(bulk: BulkEmail) -> str:
    """The name of ``bulk``'s type, or ``""`` while it has none."""
    return bulk.email_type.name if bulk.email_type is not None else ""


def snapshot(row: BulkEmailRecipient, account: User) -> None:
    """Copy ``account``'s name, address, kind, and DART onto ``row``, unsaved."""
    row.name = account.display_name
    row.email = account.email
    row.kind = _account_kind(account)
    row.dart_name = _dart_name(account)


#: The statuses a frozen row was not sent a copy in, whose stored reason says why.
_NOT_RECEIVING = frozenset(
    {
        RecipientStatus.SKIPPED,
        RecipientStatus.FAILED,
        RecipientStatus.STOPPED,
        RecipientStatus.BOUNCED,
    }
)


def _new_row(bulk: BulkEmail, account: User, add: BatchAdd) -> BulkEmailRecipient:
    """An unsaved ``batched`` row of ``bulk`` for ``account``, brought in by ``add``."""
    row = BulkEmailRecipient(bulk_email=bulk, user=account, added_by=add)
    snapshot(row, account)
    return row


def _accounts_by_id(ids: Iterable[int | None]) -> dict[int, User]:
    """The accounts of ``ids`` with their membership annotations, by primary key."""
    wanted = {pk for pk in ids if pk is not None}
    accounts = with_membership(
        User.objects.filter(pk__in=wanted).select_related("profile", "profile__dart")
    )
    by_id: dict[int, User] = {account.pk: account for account in accounts}
    return by_id


def _folded(address: str) -> str:
    """``address`` trimmed and case-folded, as duplicates are compared."""
    return address.strip().casefold()


def _account_kind(account: User) -> str:
    """``member`` or ``friend``: the account's kind as worked out for today.

    An account counts as a friend exactly when its membership status is ``friend``: a
    friend by kind, or a member whose friend date has come.  A member who holds no term
    yet (``none``) is a member, the kind the member list and the report show, so a
    *Members only* add takes them and a *Friends only* add does not.
    """
    if membership_of(account)["status"] == MembershipState.FRIEND:
        return RecipientKind.FRIEND
    return RecipientKind.MEMBER


def _dart_name(account: User) -> str:
    """The name of the DART on the account's profile, or ``""`` without one."""
    profile: MemberProfile | None = getattr(account, "profile", None)
    if profile is None or profile.dart is None:
        return ""
    return str(profile.dart.name)


def _kind_label(kind: str) -> str:
    """A stored kind in words, or ``""`` for none."""
    return RecipientKind(kind).label if kind in RecipientKind.values else ""


def _membership_label(account: User | None) -> str:
    """The account's membership status in words, or ``""`` once it is deleted."""
    if account is None:
        return ""
    return str(MembershipState(membership_of(account)["status"]).label)


def _value_label(key: str, value: str) -> str:
    """One filter's value in words, for :func:`add_label`."""
    if key == "dart" and value.isdigit():
        name = Dart.objects.filter(pk=int(value)).values_list("name", flat=True).first()
        return name if name is not None else value
    if key == "kind":
        return KIND_FILTER_LABELS.get(value, value)
    if key == "role":
        return ROLE_LABELS.get(value, value)
    if key == "county":
        return ", ".join(county.strip() for county in value.split(",") if county.strip())
    if key == "search":
        return f'"{value}"'
    choices = dict(_filter_choices(key))
    return str(choices.get(value, value))


def _filter_choices(key: str) -> list[tuple[str, str]]:
    """The ``(value, label)`` choices the member list filter ``key`` declares, if any."""
    declared = MemberAdminFilterSet.base_filters[key].extra.get("choices", [])
    return [(str(value), str(label)) for value, label in declared]
