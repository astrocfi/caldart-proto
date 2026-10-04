"""An account's history: the changes to its roles and status that the user record lists.

The audit log is a journal line per privileged action and cannot be read back by a
screen, so each change the user record's **History** card shows is also kept as an
``AccountChange`` row, written beside its audit line by :func:`record_account_change`.
"""

from __future__ import annotations

from collections.abc import Sequence

from apps.accounts.models import AccountChange, AccountChangeKind, User


def record_account_change(
    kind: AccountChangeKind,
    *,
    actor: User | str,
    target: User,
    added: Sequence[str] = (),
    removed: Sequence[str] = (),
) -> AccountChange:
    """Store one entry of ``target``'s history, and return it.

    ``actor`` is the account that acted, or the audit log's command actor (any string),
    which is stored as no account.  ``added`` and ``removed`` are the role slugs a
    ``roles`` change granted and took away, in the order given; every other kind
    leaves them empty.  The entry is stamped with the present moment.
    """
    return AccountChange.objects.create(
        user=target,
        changed_by=actor if isinstance(actor, User) else None,
        kind=kind,
        added=list(added),
        removed=list(removed),
    )
