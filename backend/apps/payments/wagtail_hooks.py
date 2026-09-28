"""Wagtail admin hooks that keep an account's payments when the account is deleted.

``Payment.user`` is ``PROTECT``, so deleting an account that has paid would raise
``ProtectedError``, which Wagtail's user admin has no handler for.  Both of the
surfaces it offers -- the delete view at ``/admin/users/delete/<id>/`` and the
``Delete`` bulk action on the users listing -- therefore hand each account's
payments to a tombstone account first, exactly as ``DELETE /admin/members/{id}``
does (see ``apps.members.services.hand_over_payments``), and let the delete go
ahead.  Each deleted account is recorded as a ``member.delete`` audit line, naming
the tombstone when payments moved; the delete view writes it only once the account
is gone, so a delete that fails after the handover leaves no such line.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from weakref import WeakKeyDictionary

from django.contrib.auth import get_user_model
from django.db.models import Model
from django.http import HttpRequest, HttpResponse
from wagtail import hooks

from apps.accounts.models import User
from apps.members.services import hand_over_payments
from caldart import audit

if TYPE_CHECKING:
    from wagtail.admin.views.bulk_action import BulkAction

#: The ``member.delete`` line a confirmed delete view owes, held from the handover
#: until Wagtail reports the account deleted: the account id and the handover fields.
_PENDING_DELETE_LINES: WeakKeyDictionary[HttpRequest, tuple[int, dict[str, int]]] = (
    WeakKeyDictionary()
)


# wagtail's hooks.register is untyped, which would otherwise make the hook untyped.
@hooks.register("before_delete_user")  # type: ignore[untyped-decorator]
def keep_the_payments_of_a_deleted_user(request: HttpRequest, user: User) -> HttpResponse | None:
    """Hand ``user``'s payments to a tombstone as the delete is confirmed.

    Wagtail runs this before it renders the confirmation page as well as before the
    delete itself, so only the confirming ``POST`` moves anything; opening the page
    changes nothing.  The ``member.delete`` line waits for
    :func:`record_a_deleted_user`.  Always returns ``None``, letting Wagtail carry on.
    """
    if request.method == "POST":
        _PENDING_DELETE_LINES[request] = (user.pk, _hand_over(request, user))
    return None


# wagtail's hooks.register is untyped, which would otherwise make the hook untyped.
@hooks.register("after_delete_user")  # type: ignore[untyped-decorator]
def record_a_deleted_user(request: HttpRequest, _user: User) -> HttpResponse | None:
    """Write the ``member.delete`` line of the account the delete view just deleted.

    Always returns ``None``, letting Wagtail carry on.
    """
    target_id, fields = _PENDING_DELETE_LINES.pop(request)
    audit.record(audit.MEMBER_DELETE, actor=_actor(request), target=target_id, **fields)
    return None


# wagtail's hooks.register is untyped, which would otherwise make the hook untyped.
@hooks.register("before_bulk_action")  # type: ignore[untyped-decorator]
def keep_the_payments_of_bulk_deleted_users(
    request: HttpRequest, action_type: str, objects: list[Model], _action: BulkAction
) -> HttpResponse | None:
    """Hand the payments of every account in a bulk ``Delete`` to its own tombstone.

    Does nothing for any other action or for anything but accounts.  Wagtail runs the
    hook and the delete in one transaction, so a batch is handed over and deleted
    whole or not at all.  Always returns ``None``, letting Wagtail carry on.
    """
    if action_type != "delete":
        return None
    user_model = get_user_model()
    for obj in objects:
        if isinstance(obj, user_model):
            fields = _hand_over(request, obj)
            audit.record(audit.MEMBER_DELETE, actor=_actor(request), target=obj.pk, **fields)
    return None


def _hand_over(request: HttpRequest, user: User) -> dict[str, int]:
    """Move ``user``'s payments to a tombstone; return the ``member.delete`` fields."""
    handover = hand_over_payments(_actor(request), user)
    return {} if handover is None else handover.audit_fields()


def _actor(request: HttpRequest) -> User:
    """The signed-in account behind a Wagtail delete; ``TypeError`` when there is none."""
    actor = request.user
    if not isinstance(actor, User):
        raise TypeError("A Wagtail delete needs a signed-in account")
    return actor
