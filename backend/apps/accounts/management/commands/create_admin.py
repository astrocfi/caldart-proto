"""``manage.py create_admin`` -- create or promote the first administrator."""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.core.validators import validate_email
from django.db import transaction

from apps.accounts.models import AccountKind, User
from apps.accounts.roles import MEMBER, ROLE_SLUGS, SYSTEM_ADMIN, WEBSITE_ADMIN
from apps.accounts.services import (
    build_reset_url,
    confirm_email_address,
    create_account,
    update_account,
)
from apps.notifications.dispatch import suspended
from caldart import audit

#: The roles this command grants: the ``member`` role for portal access, plus the
#: two roles a fresh installation needs to finish setting itself up.
ADMIN_ROLES: tuple[str, ...] = (MEMBER, SYSTEM_ADMIN, WEBSITE_ADMIN)


class Command(BaseCommand):
    """Create the account ``--email`` names as a system administrator, or promote it.

    Without an account at that address, one is created: active, staff, a Django
    superuser, holding an unusable password, its email address marked verified (the
    same way following a verification link would), and holding the ``member``,
    ``system_admin``, and ``website_admin`` roles.  ``--first-name`` and
    ``--last-name`` name the new account; left out, both stay blank.

    With an account at that address already, it is made a superuser and given
    whatever of those three roles it lacks; every other role it holds is kept, and
    its password and names are left exactly as they were.  ``--first-name`` and
    ``--last-name`` are ignored in that case.

    Either way the role write goes through
    :func:`apps.accounts.services.update_account`, the same service an
    administration screen uses, under the command actor
    (:data:`caldart.audit.COMMAND_ACTOR`), so the audit log records ``account.roles``
    with ``actor=command``; the notification an interactive role change would raise
    is suspended, since there is nobody signed in for it to name.  Running the
    command again for an address that already holds all three roles changes nothing.

    The only line this command writes to standard output is the password-reset link
    from :func:`apps.accounts.services.build_reset_url`: open it, signed out, to set
    a password.  The link is usable for ``PASSWORD_RESET_TIMEOUT``.

    Raises ``CommandError`` when ``--email`` is not a valid email address.
    """

    help = "Create or promote the account at --email to a system administrator."

    def add_arguments(self, parser: CommandParser) -> None:
        """Declare ``--email`` (required), ``--first-name``, and ``--last-name``."""
        parser.add_argument("--email", required=True, help="The address to create or promote.")
        parser.add_argument(
            "--first-name", default="", help="First name, for a newly created account."
        )
        parser.add_argument(
            "--last-name", default="", help="Last name, for a newly created account."
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Create or promote the account named by ``--email``, and print its link.

        Raises ``CommandError`` naming the address when it is not a valid email
        address.
        """
        email = options["email"].strip()
        try:
            validate_email(email)
        except ValidationError as exc:
            raise CommandError(f"'{email}' is not a valid email address.") from exc

        with transaction.atomic():
            user = User.objects.filter(email__iexact=email).first()
            if user is None:
                user = create_account(
                    email=email,
                    first_name=options["first_name"],
                    last_name=options["last_name"],
                    kind=AccountKind.MEMBER,
                )
                confirm_email_address(user)

            wanted = [slug for slug in ROLE_SLUGS if slug in set(user.roles) | set(ADMIN_ROLES)]
            with suspended():
                update_account(audit.COMMAND_ACTOR, user, {"roles": wanted})

        self.stdout.write(build_reset_url(user))
