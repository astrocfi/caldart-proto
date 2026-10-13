"""Who may use the aircraft register and keep aircraft on their profile.

Aircraft are for current members.  A friend of CalDART pays no dues and has no aircraft;
a member who has joined and not yet paid their first dues has none until they pay; and
a member whose membership has expired keeps the aircraft on their profile but cannot
see or change them until they renew.  The roles that check members and aircraft
(``VERIFY_ROLES``, and ``system_admin``) use the register whatever their own
membership.

Every aircraft endpoint a member reaches checks :class:`CanUseAircraft`, the profile
lists aircraft only for an account :func:`may_use_aircraft` admits, and the ``user``
payload carries the same answer so the portal hides what the server refuses.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.auth.models import AnonymousUser
from rest_framework.permissions import BasePermission

from apps.accounts.models import User
from apps.accounts.permissions import user_has_any_role
from apps.accounts.roles import VERIFY_ROLES
from apps.members.models import MembershipState
from apps.members.services import membership_of

if TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework.views import APIView

#: The membership states whose holder uses aircraft without a checking role.
AIRCRAFT_STATES: frozenset[str] = frozenset({MembershipState.CURRENT})

#: What a caller the rule refuses is told.
AIRCRAFT_REFUSED = "Aircraft are for members with a current membership."


def may_use_aircraft(user: User | AnonymousUser | None) -> bool:
    """True when ``user`` may use the aircraft register and their own aircraft.

    False for an anonymous caller.  True for any holder of a ``VERIFY_ROLES`` role or
    ``system_admin``.  Otherwise true only when the account's membership, by
    :func:`apps.members.services.membership_of`, is current; a friend (by kind, or by a
    ``friend_on`` date that has arrived), a member who has not yet paid, an expired
    member, and a donor are refused.
    """
    if user is None or not user.is_authenticated:
        return False
    if user_has_any_role(user, VERIFY_ROLES):
        return True
    return membership_of(user)["status"] in AIRCRAFT_STATES


class CanUseAircraft(BasePermission):
    """The DRF permission for :func:`may_use_aircraft`, refusing with its sentence.

    An anonymous caller is refused too, which DRF answers with 401.
    """

    message = AIRCRAFT_REFUSED

    def has_permission(self, request: Request, view: APIView) -> bool:
        """Return whether the caller may use aircraft."""
        return may_use_aircraft(request.user)
