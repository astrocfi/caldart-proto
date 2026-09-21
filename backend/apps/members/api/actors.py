"""The account behind a members API request.

Every view in this app is gated by a permission class that already refuses
anonymous callers, so the account is there by the time a handler runs.
:func:`acting_user` is how a handler says so: it hands back the ``User``, which
carries the profile, memberships and payments the handlers reach for, rather
than the "a user or an anonymous visitor" the request alone promises.
"""

from __future__ import annotations

from rest_framework.exceptions import NotAuthenticated
from rest_framework.request import Request

from apps.accounts.models import User


def acting_user(request: Request) -> User:
    """The signed-in account that made ``request``.

    Raises ``NotAuthenticated``, which the API renders as 401, if it is ever
    called on a request no permission class refused first.  A handler therefore
    never sees an anonymous visitor as a half-usable member record.
    """
    user = request.user
    if not isinstance(user, User):
        raise NotAuthenticated
    return user
