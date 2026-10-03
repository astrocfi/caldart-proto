"""Saved recipient groups: people CalDART management mails again and again.

A group is saved under a name, from a batch (:func:`save_group`) or from the Recipient
groups screen, and is shared by everybody in CalDART management.  It is one of two
kinds (``apps.bulk_email.models.GroupKind``):

- a **fixed** group is a list of accounts.  It holds exactly the people it was saved
  with, until somebody adds or removes one (:func:`add_member`, :func:`remove_member`);
- a **live** group is a list of member list filter sets.  Each use runs them afresh
  (:func:`group_accounts`), so the group follows membership as it changes
  (:func:`add_filter_set`, :func:`remove_filter_set`).

**Add a saved group** puts a group's people into a batch as one add
(:func:`add_group`), with the same handling of people already there as any add, and
the add is named after the group.  Deleting a group leaves every batch it was added to
as it is: the add keeps its name and the people it brought in.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from functools import reduce
from operator import or_

from django.db import transaction
from django.db.models import Max, Q, QuerySet
from rest_framework.exceptions import ValidationError

from apps.accounts.models import User
from apps.bulk_email.batch import (
    AddResult,
    add_accounts,
    batch_queryset,
    given_filters,
    selected_accounts,
    snapshot,
)
from apps.bulk_email.models import (
    BatchAdd,
    BulkEmail,
    BulkEmailRecipient,
    GroupKind,
    RecipientGroup,
    RecipientGroupFilter,
    RecipientGroupMember,
)
from apps.members.filters import member_admin_queryset
from caldart.exceptions import DomainError, DomainValidationError
from caldart.reports import CSV_DOCUMENT_TYPE, ReportDocument, csv_rows

#: How a group's add is named in the batch; ``{name}`` is the group's name.
GROUP_LABEL = "Group: {name}"

#: The refusal of saving a batch with nobody in it.
EMPTY_BATCH_MESSAGE = "The batch is empty. Add people to it before you save it as a group."

#: The refusal of saving a batch as a live group when some of it has no filters behind it.
NO_FILTERS_MESSAGE = (
    "Some people in this batch came from a fixed group or were copied from another "
    "email, so there are no filters to save for them. Save it as a fixed group instead."
)

#: The refusal of saving a batch as a live group when an add's group has since been
#: deleted; ``{name}`` is the group's name as the add recorded it.
DELETED_GROUP_MESSAGE = (
    'The group "{name}" was deleted, so its filters are gone. '
    "Save this batch as a fixed group instead."
)

#: What a live group whose stored filters the member list no longer accepts says, in
#: place of its people, and as the refusal of adding it to a batch.
FILTERS_NEED_FIXING_MESSAGE = "This group's filters need fixing."

#: The refusal of a filter set a live group has already.
SAME_FILTERS_MESSAGE = "This group has these filters already."

#: The refusals of changing the wrong kind of group.
NOT_FIXED_MESSAGE = "Only a fixed group lists its people. Change a live group by its filters."
NOT_LIVE_MESSAGE = "Only a live group has filters. Change a fixed group by its people."

#: The refusal of adding somebody to a fixed group twice; ``{name}`` is the person.
ALREADY_MEMBER_MESSAGE = "{name} is in this group already."

#: The refusal of adding an account that is not a member or a friend.
NOT_A_PERSON_MESSAGE = "Choose a member or a friend."

#: The columns of a group's CSV.
GROUP_CSV_HEADER: tuple[str, ...] = ("Name", "Email", "Kind", "DART")

#: The start of every group add's label, :data:`GROUP_LABEL` before the name.
GROUP_LABEL_PREFIX = GROUP_LABEL.format(name="")

#: The most people the search for a fixed group's next member answers.
PEOPLE_SEARCH_LIMIT = 10


class GroupFiltersError(DomainError):
    """A live group holds a stored filter the member list no longer accepts.

    A filter's choices can change after a group saved it, such as a DART that is
    deleted.  The message is :data:`FILTERS_NEED_FIXING_MESSAGE`.
    """

    def __init__(self) -> None:
        """Carry :data:`FILTERS_NEED_FIXING_MESSAGE`."""
        super().__init__(FILTERS_NEED_FIXING_MESSAGE)


@dataclass(frozen=True)
class GroupPerson:
    """One person in a group as the group's page lists them, as they are now.

    ``kind`` is ``member`` or ``friend`` and ``dart_name`` the DART on the profile,
    blank without one; ``is_active`` is false for a deactivated account, which a send
    would skip.
    """

    user_id: int
    name: str
    email: str
    kind: str
    dart_name: str
    is_active: bool


def group_accounts(group: RecipientGroup) -> QuerySet[User]:
    """Everybody in ``group`` now, in surname order, then first name, then address.

    A fixed group's are its accounts; a live group's are everybody any of its filter
    sets choose on the member list (``apps.bulk_email.batch.selected_accounts``),
    deactivated accounts included, as **Add to batch** chooses them, and nobody while
    it has no filter set.  Each account carries the member list's annotations, and a
    donor is never there.  Raises :class:`GroupFiltersError` when the member list
    refuses one of a live group's stored filters.
    """
    people = member_admin_queryset()
    if group.kind == GroupKind.FIXED:
        people = people.filter(pk__in=group.members.values("user_id"))
    else:
        try:
            sets = [
                Q(pk__in=selected_accounts(filter_set.filters).values("pk"))
                for filter_set in group.filter_sets.all()
            ]
        except ValidationError as refused:
            raise GroupFiltersError from refused
        people = people.filter(reduce(or_, sets)) if len(sets) > 0 else people.none()
    return people.order_by("last_name", "first_name", "email", "pk")


def group_people(group: RecipientGroup) -> list[GroupPerson]:
    """Everybody in ``group`` now (:func:`group_accounts`), as its page lists them.

    Raises :class:`GroupFiltersError` as :func:`group_accounts` does.
    """
    return [person_of(account) for account in group_accounts(group)]


def group_count(group: RecipientGroup) -> int | None:
    """How many people ``group`` holds now, or ``None`` when its filters need fixing."""
    try:
        return group_accounts(group).count()
    except GroupFiltersError:
        return None


def filters_work(filters: Mapping[str, str]) -> bool:
    """True when the member list accepts every filter of ``filters`` as stored."""
    try:
        selected_accounts(filters)
    except ValidationError:
        return False
    return True


def add_group(bulk: BulkEmail, group: RecipientGroup, *, actor: User) -> AddResult:
    """Add everybody in ``group`` now to ``bulk``'s batch; say how many joined.

    The group's people (:func:`group_accounts`) join as any add's do: everybody not in
    the batch yet becomes a ``batched`` row, the rest are counted as already there,
    and one add records the counts, links ``group``, and is named
    :data:`GROUP_LABEL` after it, a name it keeps if the group is renamed or deleted.
    A queued email goes back to a draft.  Raises ``DomainValidationError`` keyed
    ``group`` with :data:`FILTERS_NEED_FIXING_MESSAGE` when a live group's stored
    filters need fixing, and ``DomainError`` when the email has started sending;
    nothing is added then.
    """
    try:
        accounts = group_accounts(group)
    except GroupFiltersError as broken:
        raise DomainValidationError("group", broken.message) from broken
    return add_accounts(
        bulk,
        accounts,
        actor=actor,
        group=group,
        label=GROUP_LABEL.format(name=group.name),
    )


def save_group(bulk: BulkEmail, *, name: str, kind: str, actor: User) -> RecipientGroup:
    """Save ``bulk``'s batch as a group called ``name``, made by ``actor``.

    A ``fixed`` group holds every account in the batch now, whether or not each will
    receive this email; a person whose account is deleted is left out.  A ``live``
    group holds the filters behind the batch, once each, in the order they were added:
    the filters of every add made with filters, and the filter sets, as they are now,
    of every live group added.  People taken out of the batch one by one are not
    remembered by a live group.

    ``name`` must not be taken (the API checks it).  Raises ``DomainValidationError``
    keyed ``batch`` with :data:`EMPTY_BATCH_MESSAGE` when the batch is empty, and with
    :data:`NO_FILTERS_MESSAGE` for a live group when an add has no filters behind it,
    a fixed group's or people copied from another email, and with
    :data:`DELETED_GROUP_MESSAGE` when an add's group has since been deleted.
    """
    if not batch_queryset(bulk).exists():
        raise DomainValidationError("batch", EMPTY_BATCH_MESSAGE)
    with transaction.atomic():
        if kind == GroupKind.FIXED:
            group = RecipientGroup.objects.create(name=name, kind=kind, created_by=actor)
            accounts = (
                batch_queryset(bulk).filter(user__isnull=False).values_list("user_id", flat=True)
            )
            RecipientGroupMember.objects.bulk_create(
                [RecipientGroupMember(group=group, user_id=pk) for pk in accounts]
            )
            return group
        filter_sets = _batch_filter_sets(bulk)
        group = RecipientGroup.objects.create(name=name, kind=kind, created_by=actor)
        RecipientGroupFilter.objects.bulk_create(
            [
                RecipientGroupFilter(group=group, filters=filters, position=position)
                for position, filters in enumerate(filter_sets)
            ]
        )
    return group


def add_member(group: RecipientGroup, user_id: int) -> User:
    """Put the account ``user_id`` into the fixed ``group``; return the account.

    Raises ``DomainError`` with :data:`NOT_FIXED_MESSAGE` for a live group, and
    ``DomainValidationError`` keyed ``user`` with :data:`NOT_A_PERSON_MESSAGE` when the
    account is not a member or a friend (a donor, or no account at all), or with
    :data:`ALREADY_MEMBER_MESSAGE` when it is in the group already.
    """
    if group.kind != GroupKind.FIXED:
        raise DomainError(NOT_FIXED_MESSAGE)
    account = member_admin_queryset().filter(pk=user_id).first()
    if account is None:
        raise DomainValidationError("user", NOT_A_PERSON_MESSAGE)
    with transaction.atomic():
        _, created = RecipientGroupMember.objects.get_or_create(group=group, user=account)
        if not created:
            raise DomainValidationError(
                "user", ALREADY_MEMBER_MESSAGE.format(name=account.display_name)
            )
        group.save(update_fields=["updated_at"])
    return account


def remove_member(group: RecipientGroup, user_id: int) -> None:
    """Take the account ``user_id`` out of the fixed ``group``.

    Raises ``DomainError`` with :data:`NOT_FIXED_MESSAGE` for a live group, and
    ``RecipientGroupMember.DoesNotExist`` when the account is not in the group.
    """
    if group.kind != GroupKind.FIXED:
        raise DomainError(NOT_FIXED_MESSAGE)
    with transaction.atomic():
        group.members.get(user_id=user_id).delete()
        group.save(update_fields=["updated_at"])


def add_filter_set(group: RecipientGroup, filters: Mapping[str, str]) -> RecipientGroupFilter:
    """Add one set of member list filters to the live ``group``, after its others.

    ``filters`` are kept as an add keeps them, the blank ones dropped; an empty set
    chooses every member and friend.  Raises ``DomainError`` with
    :data:`NOT_LIVE_MESSAGE` for a fixed group, and ``DomainValidationError`` keyed
    ``filters`` with :data:`SAME_FILTERS_MESSAGE` when the group has the same set
    already.
    """
    if group.kind != GroupKind.LIVE:
        raise DomainError(NOT_LIVE_MESSAGE)
    given = given_filters(filters)
    if any(filter_set.filters == given for filter_set in group.filter_sets.all()):
        raise DomainValidationError("filters", SAME_FILTERS_MESSAGE)
    with transaction.atomic():
        last = group.filter_sets.aggregate(last=Max("position"))["last"]
        filter_set = RecipientGroupFilter.objects.create(
            group=group,
            filters=given,
            position=0 if last is None else last + 1,
        )
        group.save(update_fields=["updated_at"])
    return filter_set


def remove_filter_set(group: RecipientGroup, filter_set_id: int) -> None:
    """Take one filter set out of the live ``group``.

    Raises ``DomainError`` with :data:`NOT_LIVE_MESSAGE` for a fixed group, and
    ``RecipientGroupFilter.DoesNotExist`` when the set is not the group's.
    """
    if group.kind != GroupKind.LIVE:
        raise DomainError(NOT_LIVE_MESSAGE)
    with transaction.atomic():
        group.filter_sets.get(pk=filter_set_id).delete()
        group.save(update_fields=["updated_at"])


def people_matching(search: str) -> QuerySet[User]:
    """The first members and friends the member list's search finds for ``search``.

    At most :data:`PEOPLE_SEARCH_LIMIT`, in surname order, deactivated accounts
    included; nobody for a blank search.
    """
    if search.strip() == "":
        return User.objects.none()
    return selected_accounts({"search": search.strip()})[:PEOPLE_SEARCH_LIMIT]


def group_document(group: RecipientGroup) -> ReportDocument:
    """Everybody in ``group`` now as a CSV, in surname order.

    The columns are :data:`GROUP_CSV_HEADER`: each person's name, address, kind
    (``Member`` or ``Friend``), and DART.  The file is named
    ``caldart-recipient-group-<id>.csv``.  Raises :class:`GroupFiltersError` when a
    live group's stored filters need fixing.
    """
    rows = [
        (person.name, person.email, person.kind.capitalize(), person.dart_name)
        for person in group_people(group)
    ]
    return ReportDocument(
        filename=f"caldart-recipient-group-{group.pk}.csv",
        media_type=CSV_DOCUMENT_TYPE,
        content="".join(csv_rows(GROUP_CSV_HEADER, rows)).encode(),
    )


def _batch_filter_sets(bulk: BulkEmail) -> list[dict[str, str]]:
    """The filter sets behind ``bulk``'s adds, once each, in the order they were added.

    Raises ``DomainValidationError`` keyed ``batch`` when an add has none: with
    :data:`DELETED_GROUP_MESSAGE` for a group add whose group has since been deleted,
    and with :data:`NO_FILTERS_MESSAGE` for any other add with a label of its own that
    is not a live group still on file.
    """
    found: list[dict[str, str]] = []
    for add in bulk.adds.select_related("group").order_by("id"):
        if add.label == "":
            sets = [dict(add.filters)]
        elif add.group is not None and add.group.kind == GroupKind.LIVE:
            sets = [dict(filter_set.filters) for filter_set in add.group.filter_sets.all()]
        else:
            raise DomainValidationError("batch", _no_filters_message(add))
        for filters in sets:
            if filters not in found:
                found.append(filters)
    return found


def person_of(account: User) -> GroupPerson:
    """``account`` as a group's page lists it, its kind and DART as a batch row has."""
    row = BulkEmailRecipient()
    snapshot(row, account)
    return GroupPerson(
        user_id=account.pk,
        name=row.name,
        email=row.email,
        kind=row.kind,
        dart_name=row.dart_name,
        is_active=account.is_active,
    )


def _no_filters_message(add: BatchAdd) -> str:
    """Why ``add``, which has no filters behind it, cannot be kept in a live group."""
    if add.group_id is None and add.label.startswith(GROUP_LABEL_PREFIX):
        return DELETED_GROUP_MESSAGE.format(name=add.label.removeprefix(GROUP_LABEL_PREFIX))
    return NO_FILTERS_MESSAGE
