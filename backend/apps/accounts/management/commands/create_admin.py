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
    is_donor,
    send_password_invitation,
    update_account,
)
from apps.accounts.status import end_sessions
from apps.notifications.dispatch import suspended
from caldart import audit
from caldart.mail import send_on_commit

#: The roles this command grants: the ``member`` role for portal access, plus the
#: two roles a fresh installation needs to finish setting itself up.
ADMIN_ROLES: tuple[str, ...] = (MEMBER, SYSTEM_ADMIN, WEBSITE_ADMIN)

#: Raised when ``--email`` already names a donor, who holds no role and cannot sign in.
DONOR_ADMIN_REFUSED = "'{email}' is a donor account, which holds no role and cannot sign in."

#: Written to standard error when ``--email`` names an account that already existed.
PROMOTED_NOTICE = (
    "'{email}' already had an account: its password was cleared, its sessions were "
    "ended, and a set-password link was mailed to it."
)


class Command(BaseCommand):
    """Create the account ``--email`` names as a system administrator, or promote it.

    Without an account at that address, one is created: active, staff, a Django
    superuser, holding an unusable password, its email address marked verified (the
    same way following a verification link would), and holding the ``member``,
    ``system_admin``, and ``website_admin`` roles.  ``--first-name`` and
    ``--last-name`` name the new account; left out, both stay blank.

    With an account at that address already, it is made a superuser and given
    whatever of those three roles it lacks; every other role it holds is kept, and
    its names are left exactly as they were (``--first-name`` and ``--last-name``
    are ignored).  Since anybody can register any address, the account is first
    taken back from whoever set its password: the password is made unusable, every
    session signed in to the account is ended
    (:func:`apps.accounts.status.end_sessions`), the address is marked verified as
    for a new account, the audit log records ``account.password_cleared`` with
    ``actor=command`` and ``sessions`` (how many were ended), and once the
    transaction commits the address is mailed the set-password invitation
    (:func:`apps.accounts.services.send_password_invitation`), carrying the same
    link the command prints.  A mail server that refuses it is logged, and the
    command still succeeds.  :data:`PROMOTED_NOTICE` on standard error says so.
    This happens on every run for an existing address, an administrator's own
    included.  An existing account that is a donor is refused with
    ``CommandError``: a donor holds no role and cannot sign in, so it cannot be
    made an administrator.

    Either way the role write goes through
    :func:`apps.accounts.services.update_account`, the same service an
    administration screen uses, under the command actor
    (:data:`caldart.audit.COMMAND_ACTOR`), so the audit log records ``account.roles``
    with ``actor=command``; the notification an interactive role change would raise
    is suspended, since there is nobody signed in for it to name.  Running the
    command again for an address that already holds all three roles grants nothing
    further and records no ``account.roles`` line.

    The only line this command writes to standard output is the password-reset link
    from :func:`apps.accounts.services.build_reset_url`: open it, signed out, to set
    a password.  The link is usable for ``PASSWORD_RESET_TIMEOUT``.

    Raises ``CommandError`` when ``--email`` is not a valid email address, or when
    it already names a donor.
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
        address, or when it already names a donor.
        """
        email = options["email"].strip()
        try:
            validate_email(email)
        except ValidationError as exc:
            raise CommandError(f"'{email}' is not a valid email address.") from exc

        with transaction.atomic():
            user = User.objects.filter(email__iexact=email).first()
            promoted = user is not None
            if user is None:
                user = create_account(
                    email=email,
                    first_name=options["first_name"],
                    last_name=options["last_name"],
                    kind=AccountKind.MEMBER,
                )
            elif is_donor(user):
                raise CommandError(DONOR_ADMIN_REFUSED.format(email=email))
            else:
                self._take_back(user)
            confirm_email_address(user)

            wanted = [slug for slug in ROLE_SLUGS if slug in set(user.roles) | set(ADMIN_ROLES)]
            with suspended():
                update_account(audit.COMMAND_ACTOR, user, {"roles": wanted})

        self.stdout.write(build_reset_url(user))
        if promoted:
            self.stderr.write(PROMOTED_NOTICE.format(email=user.email), self.style.WARNING)

    def _take_back(self, user: User) -> None:
        """Clear ``user``'s password and sessions, and mail it the set-password link.

        Runs inside the caller's transaction; the mail goes once it commits.
        """
        user.set_unusable_password()
        user.save(update_fields=["password", "updated_at"])
        ended = end_sessions(user)
        audit.record(
            audit.ACCOUNT_CREDENTIALS_CLEARED,
            actor=audit.COMMAND_ACTOR,
            target=user,
            sessions=ended,
        )
        send_on_commit(
            lambda: send_password_invitation(user),
            what=f"the set-password link for account {user.pk}",
        )
