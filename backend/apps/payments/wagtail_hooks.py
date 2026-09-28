"""Wagtail admin hooks that keep an account's payments when the account is deleted.

``Payment.user`` is ``PROTECT``, so deleting an account that has paid would raise
``ProtectedError``, which Wagtail's user admin has no handler for.  Both of the
surfaces it offers -- the delete view at ``/admin/users/delete/<id>/`` and the
``Delete`` bulk action on the users listing -- therefore hand each account's
payments to a tombstone account first, exactly as ``DELETE /admin/members/{id}``
does (see ``apps.members.services.hand_over_payments``), and let the delete go
ahead.  Each deleted account is recorded as a ``member.delete`` audit line, naming
the tombstone when payments moved.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.db.models import Model
from django.http import HttpRequest, HttpResponse
from wagtail import hooks

from apps.accounts.models import User
from apps.members.services import hand_over_payments
from caldart import audit

if TYPE_CHECKING:
    from wagtail.admin.views.bulk_action import BulkAction


# wagtail's hooks.register is untyped, which would otherwise make the hook untyped.
@hooks.register("before_delete_user")  # type: ignore[untyped-decorator]
def keep_the_payments_of_a_deleted_user(request: HttpRequest, user: User) -> HttpResponse | None:
    """Hand ``user``'s payments to a tombstone as the delete is confirmed.

    Wagtail runs this before it renders the confirmation page as well as before the
    delete itself, so only the confirming ``POST`` moves anything; opening the page
    changes nothing.  Always returns ``None``, letting Wagtail carry on.
    """
    if request.method == "POST":
        _hand_over_and_record(request, user)
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
            _hand_over_and_record(request, obj)
    return None


def _hand_over_and_record(request: HttpRequest, user: User) -> None:
    """Move ``user``'s payments to a tombstone and write the ``member.delete`` line."""
    actor = request.user
    if not isinstance(actor, User):
        raise TypeError("A Wagtail delete needs a signed-in account")
    handover = hand_over_payments(actor, user)
    fields = {} if handover is None else handover.audit_fields()
    audit.record(audit.MEMBER_DELETE, actor=actor, target=user.pk, **fields)
