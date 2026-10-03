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
sending is refused.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import cast

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import F, QuerySet

from apps.accounts.models import User
from apps.accounts.roles import ROLE_LABELS
from apps.bulk_email.models import (
    BatchAdd,
    BulkEmail,
    BulkEmailRecipient,
    RecipientKind,
    RecipientStatus,
)
from apps.darts.models import Dart
from apps.members.filters import EXPORT_FILTER_PARAMS, MemberAdminFilterSet, member_admin_queryset
from apps.members.models import MemberProfile, MembershipState
from apps.members.services import membership_of, with_membership
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

#: An add with no filter chose every member and friend.
EVERYBODY_LABEL = "Everybody"

#: Why a person in the batch is sent no copy, in the order :func:`skip_reason` asks.
SKIP_DELETED = "Account deleted"
SKIP_DEACTIVATED = "Account deactivated"
SKIP_NO_ADDRESS = "No email address"
SKIP_INVALID = "Invalid email address"
SKIP_BOUNCED = "Address bounced"
SKIP_DUPLICATE = "Duplicate address"

#: The refusal of any change to an email that has started sending.
NOT_EDITABLE_MESSAGE = "This email has been sent and cannot be changed."

#: The columns of a send's results CSV.
RESULTS_CSV_HEADER: tuple[str, ...] = ("Name", "Email", "Kind", "DART", "Result", "Reason")

#: The columns of the batch CSV.
BATCH_CSV_HEADER: tuple[str, ...] = (
    "Name",
    "Email",
    "Kind",
    "DART",
    "Membership status",
    "Added by",
    "Will receive",
    "Reason",
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
    draft or queued.
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
    whoever builds it.

    Raises ``DomainError`` when the email has started sending, and DRF's
    ``ValidationError`` for a filter value the member list refuses; nothing is stored
    then.
    """
    with transaction.atomic():
        locked = locked_for_edit(bulk)
        present = set(
            locked.recipients.filter(round=0, user__isnull=False).values_list("user_id", flat=True)
        )
        chosen = list(selected_accounts(filters))
        joining = [account for account in chosen if account.pk not in present]
        add = BatchAdd.objects.create(
            bulk_email=locked,
            filters=given_filters(filters),
            added_count=len(joining),
            already_count=len(chosen) - len(joining),
        )
        BulkEmailRecipient.objects.bulk_create(
            [_new_row(locked, account, add) for account in joining]
        )
        locked.save(update_fields=["updated_at"])
    return AddResult(
        added=add.added_count,
        already_present=add.already_count,
        count=batch_queryset(bulk).count(),
    )


def remove(bulk: BulkEmail, recipient_id: int) -> None:
    """Take one person out of ``bulk``'s batch.

    Raises ``BulkEmailRecipient.DoesNotExist`` when ``recipient_id`` is not a row of
    this batch, and ``DomainError`` when the email has started sending.
    """
    with transaction.atomic():
        locked = locked_for_edit(bulk)
        row = batch_queryset(locked).get(pk=recipient_id)
        row.delete()
        locked.save(update_fields=["updated_at"])


def clear(bulk: BulkEmail) -> int:
    """Empty ``bulk``'s batch, its adds included; return how many people were in it.

    Raises ``DomainError`` when the email has started sending.
    """
    with transaction.atomic():
        locked = locked_for_edit(bulk)
        removed, _by_model = batch_queryset(locked).delete()
        locked.adds.all().delete()
        locked.save(update_fields=["updated_at"])
    return removed


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
    now, so an address that bounced since the person was added is skipped, and two
    accounts sharing an address are sent one copy, to the first in that order.  A
    row the send has frozen keeps its stored status and reason.
    """
    rows = list(surname_order(batch_queryset(bulk)).select_related("added_by"))
    accounts = _accounts_by_id(row.user_id for row in rows)
    seen: set[str] = set()
    answered: list[BatchRow] = []
    for row in rows:
        account = accounts.get(row.user_id) if row.user_id is not None else None
        if row.status == RecipientStatus.BATCHED:
            reason = skip_reason(account, seen)
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


def skip_reason(account: User | None, seen: set[str]) -> str:
    """Why ``account`` is sent no copy, or ``""`` when it is sent one.

    The reasons are asked in this order: :data:`SKIP_DELETED` when there is no
    account any more, :data:`SKIP_DEACTIVATED` when it is deactivated,
    :data:`SKIP_NO_ADDRESS` when its address is blank, :data:`SKIP_INVALID` when the
    address is not one a mail server could take, :data:`SKIP_BOUNCED` when the bounce
    check has marked the address (``email_bounced_at`` is set, until a user
    administrator clears it or the address changes), and :data:`SKIP_DUPLICATE` when
    ``seen``, the trimmed and case-folded addresses already sent a copy, holds it.
    """
    if account is None:
        return SKIP_DELETED
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
    if _folded(address) in seen:
        return SKIP_DUPLICATE
    return ""


def add_label(filters: Mapping[str, str]) -> str:
    """An add's filters in words, as the compose screen and the CSV name the add.

    Each filter reads as its name on the member list's filter bar and its value in
    words, such as ``"Kind: Friend, County: Marin, Napa"``: a DART by its name, a role
    by its label, and a choice by the label the filter gives it.  An add with no filter
    reads :data:`EVERYBODY_LABEL`.
    """
    if len(filters) == 0:
        return EVERYBODY_LABEL
    return ", ".join(
        f"{FILTER_LABELS.get(key, key)}: {_value_label(key, value)}"
        for key, value in filters.items()
    )


def batch_document(bulk: BulkEmail) -> ReportDocument:
    """The batch as a CSV, one row per person in the order :func:`batch_rows` gives.

    The columns are :data:`BATCH_CSV_HEADER`: the name, address, kind, and DART the row
    holds, the account's membership status now (blank once it is deleted), the label
    of the add that brought the person in, ``Yes`` or ``No``, and the reason.  The file
    is named ``caldart-bulk-email-<id>-batch.csv``.
    """
    labels = {add.pk: add_label(add.filters) for add in bulk.adds.all()}
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
        )
        for row in batch_rows(bulk)
    ]
    content = "".join(csv_rows(BATCH_CSV_HEADER, rows)).encode()
    return ReportDocument(
        filename=f"caldart-bulk-email-{bulk.pk}-batch.csv",
        media_type=CSV_DOCUMENT_TYPE,
        content=content,
    )


def results_document(bulk: BulkEmail) -> ReportDocument:
    """A send's results as a CSV, one row per person in the order the send went.

    The columns are :data:`RESULTS_CSV_HEADER`: the name, address, kind, and DART the
    copy went to, the result in words (such as ``Sent``, ``Failed``, ``Skipped``, or
    ``Not sent (stopped)``), and the reason.  The file is named
    ``caldart-bulk-email-<id>-recipients.csv``.
    """
    rows = [
        (
            row.name,
            row.email,
            _kind_label(row.kind),
            row.dart_name,
            RecipientStatus(row.status).label,
            row.reason,
        )
        for row in surname_order(batch_queryset(bulk))
    ]
    content = "".join(csv_rows(RESULTS_CSV_HEADER, rows)).encode()
    return ReportDocument(
        filename=f"caldart-bulk-email-{bulk.pk}-recipients.csv",
        media_type=CSV_DOCUMENT_TYPE,
        content=content,
    )


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

    An account counts as a friend exactly when its membership status is ``friend``:
    a friend by kind, a member whose friend date has come, or one who holds no term.
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
