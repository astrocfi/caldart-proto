"""Wagtail admin guards for accounts that hold payments.

``Payment.user`` is ``PROTECT``, so deleting an account that has paid raises
``ProtectedError``.  Wagtail's user admin has no handler for that, so both of the
surfaces it offers -- the delete view at ``/admin/users/delete/<id>/`` and the
``Delete`` bulk action on the users listing -- would answer a protected account
with a server error.  These hooks turn the operation back at the door instead,
with the same sentence the API answers with, and write nothing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.db.models import Model
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from wagtail import hooks
from wagtail.admin import messages

from apps.accounts.models import User
from apps.payments.models import payment_deletion_refusal

if TYPE_CHECKING:
    from wagtail.admin.views.bulk_action import BulkAction

#: Where a refused delete sends the operator back to.
USERS_INDEX_URL_NAME = "wagtailusers_users:index"

#: How many protected accounts a refused bulk delete names before it counts the rest.
MAX_REFUSALS_SHOWN = 5


# wagtail's hooks.register is untyped, which would otherwise make the hook untyped.
@hooks.register("before_delete_user")  # type: ignore[untyped-decorator]
def refuse_to_delete_a_user_with_payments(request: HttpRequest, user: User) -> HttpResponse | None:
    """Send a protected account's delete back to the users listing with the reason.

    Returns ``None`` -- letting the delete proceed -- for an account that has no
    payment.  Wagtail runs this before it renders the confirmation page as well as
    before the delete itself, so a protected account never offers a delete button.
    """
    refusal = payment_deletion_refusal(user)
    if refusal is None:
        return None
    messages.error(request, refusal)
    return redirect(USERS_INDEX_URL_NAME)


# wagtail's hooks.register is untyped, which would otherwise make the hook untyped.
@hooks.register("before_bulk_action")  # type: ignore[untyped-decorator]
def refuse_to_bulk_delete_users_with_payments(
    request: HttpRequest, action_type: str, objects: list[Model], _action: BulkAction
) -> HttpResponse | None:
    """Refuse a bulk ``Delete`` that would take an account holding payments with it.

    Returns ``None`` for any other action, for a batch of anything but accounts, and
    for a batch in which no account holds a payment.  One protected account refuses
    the whole batch, because the delete is a single query that cannot succeed in
    part.  The first ``MAX_REFUSALS_SHOWN`` protected accounts are each named in
    their own message; a batch holding more than that gets one further message
    counting the ones it did not name, so selecting the whole listing cannot bury
    the admin in banners.
    """
    if action_type != "delete":
        return None
    user_model = get_user_model()
    refusals = [payment_deletion_refusal(obj) for obj in objects if isinstance(obj, user_model)]
    blocked = [refusal for refusal in refusals if refusal is not None]
    if len(blocked) == 0:
        return None
    for refusal in blocked[:MAX_REFUSALS_SHOWN]:
        messages.error(request, refusal)
    unnamed = len(blocked) - MAX_REFUSALS_SHOWN
    if unnamed > 0:
        subject = "account holds" if unnamed == 1 else "accounts hold"
        messages.error(
            request,
            f"{unnamed} further selected {subject} payment records, which must be kept. "
            "Deactivate the accounts instead.",
        )
    return redirect(USERS_INDEX_URL_NAME)
