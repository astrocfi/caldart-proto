"""The project's authentication backend.

Every way into a session -- the portal's ``/auth/login``, the Wagtail admin's login
form, the Django admin's, and the session middleware reloading a signed-in user on
each request -- asks the backends in ``AUTHENTICATION_BACKENDS`` whether the account
may authenticate.  Answering that once, here, keeps every login surface in step.
"""

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import AnonymousUser

from apps.accounts.models import AccountKind, User


class AccountBackend(ModelBackend):
    """Django's model backend, refusing donors as well as deactivated accounts.

    A donor has no portal account, so no password or session may sign one in: the
    account cannot authenticate by any login form, and a session that names a donor
    reads as anonymous.  Permissions are checked exactly as Django's backend checks
    them.
    """

    def user_can_authenticate(self, user: User | AnonymousUser | None) -> bool:
        """True for an active account that is not a donor."""
        if isinstance(user, User) and user.kind == AccountKind.DONOR:
            return False
        return super().user_can_authenticate(user)
