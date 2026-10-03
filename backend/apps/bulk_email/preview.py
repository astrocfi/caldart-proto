"""The preview of a bulk email: one person's copy, as it will go or as it went.

The **Check and send** card shows the message filled in for one person in the batch at
a time, starting with the first, and steps through the rest.  :func:`preview` builds
that copy with :func:`apps.bulk_email.render.render_message`, and says where the
person stands among the people who receive it.
"""

from __future__ import annotations

from dataclasses import dataclass

from apps.accounts.models import User
from apps.bulk_email.batch import BatchRow, batch_rows
from apps.bulk_email.models import BulkEmail
from apps.bulk_email.render import (
    RenderedCopy,
    check_message,
    fill_values,
    message_tokens,
    render_message,
)
from caldart.exceptions import DomainValidationError

#: Why a preview for somebody not in the batch is refused.
NOT_IN_BATCH_MESSAGE = "That person is not in the batch."


@dataclass(frozen=True)
class Preview:
    """One person's copy, and where they stand among the people it goes to.

    ``recipient_id`` is the batch row's id, null when the batch holds nobody who
    receives a copy and the copy is the sender's own.  ``name`` and ``email`` are the
    person's.  ``position`` is the person's place, from 1, among the ``count`` people
    who receive a copy, 0 for the sender's own; ``previous_id`` and ``next_id`` are
    the rows either side, null at either end.
    """

    copy: RenderedCopy
    recipient_id: int | None
    name: str
    email: str
    position: int
    count: int
    previous_id: int | None
    next_id: int | None


def preview(bulk: BulkEmail, *, recipient_id: int | None, viewer: User) -> Preview:
    """The copy of ``bulk`` for the batch row ``recipient_id``, or the first person's.

    The people stepped through are those who receive a copy, in the order the send
    goes.  ``recipient_id`` may name any row of the batch, a skipped one included; a
    row that is not in it raises ``DomainValidationError`` keyed ``recipient_id``.
    Left out, the copy is the first receiving person's, or, when nobody receives one,
    ``viewer``'s own.  A copy already tried is filled in with the values it went out
    with; any other with the account's values as they are now, or empty ones for an
    account since deleted.  A message that cannot be filled in raises
    ``DomainValidationError`` keyed ``subject`` or ``body``, as a send would.
    """
    problems = check_message(bulk.subject, bulk.body)
    if len(problems) > 0:
        name, problem = next(iter(problems.items()))
        raise DomainValidationError(name, problem)
    rows = batch_rows(bulk)
    receiving = [row for row in rows if row.will_receive]
    if recipient_id is None and len(receiving) == 0:
        return Preview(
            copy=render_message(bulk.subject, bulk.body, fill_values(bulk, viewer)),
            recipient_id=None,
            name=viewer.display_name,
            email=viewer.email,
            position=0,
            count=0,
            previous_id=None,
            next_id=None,
        )
    chosen = _chosen(rows, receiving, recipient_id)
    ids = [row.recipient.pk for row in receiving]
    place = ids.index(chosen.recipient.pk) if chosen.recipient.pk in ids else -1
    return Preview(
        copy=render_message(bulk.subject, bulk.body, _values(bulk, chosen)),
        recipient_id=chosen.recipient.pk,
        name=chosen.recipient.name,
        email=chosen.recipient.email,
        position=place + 1,
        count=len(receiving),
        previous_id=ids[place - 1] if place > 0 else None,
        next_id=ids[place + 1] if 0 <= place < len(ids) - 1 else None,
    )


def _chosen(rows: list[BatchRow], receiving: list[BatchRow], recipient_id: int | None) -> BatchRow:
    """The row ``recipient_id`` names, or the first receiving one when it is ``None``.

    Raises ``DomainValidationError`` keyed ``recipient_id`` for an id not in ``rows``.
    """
    if recipient_id is None:
        return receiving[0]
    for row in rows:
        if row.recipient.pk == recipient_id:
            return row
    raise DomainValidationError("recipient_id", NOT_IN_BATCH_MESSAGE)


def _values(bulk: BulkEmail, row: BatchRow) -> dict[str, str]:
    """The values ``row``'s copy is filled in with: as it went, or as they are now."""
    if row.recipient.tried_at is not None:
        return {name: row.recipient.values.get(name, "") for name in message_tokens(bulk)}
    return fill_values(bulk, row.account)
