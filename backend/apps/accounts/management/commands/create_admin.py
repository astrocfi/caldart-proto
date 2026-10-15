"""``manage.py create_admin`` -- create or promote the first administrator."""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.core.validators import validate_email
from django.db import transaction

from apps.accounts import lockout
from apps.accounts.mfa import remove_two_factor
from apps.accounts.models import AccountKind, User
from apps.accounts.roles import MEMBER, ROLE_SLUGS, SYSTEM_ADMIN, WEBSITE_ADMIN
from apps.accounts.services import (
    AccountChanges,
    address_holder,
    build_reset_url,
    confirm_email_address,
    create_account,
    is_donor,
    lock_address,
    send_password_invitation,
    update_account,
)
from apps.accounts.status import clear_password_and_end_sessions
from caldart import audit
from caldart.mail import send_logging_refusal

#: The roles this command grants: the ``member`` role for portal access, plus the
#: two roles a fresh installation needs to finish setting itself up.
ADMIN_ROLES: tuple[str, ...] = (MEMBER, SYSTEM_ADMIN, WEBSITE_ADMIN)

#: Raised when ``--email`` already names a donor, who holds no role and cannot sign in.
DONOR_ADMIN_REFUSED = "'{email}' is a donor account, which holds no role and cannot sign in."

#: Raised when ``--email`` is an address another account keeps for recovery.
RESERVED_ADDRESS_REFUSED = (
    "'{email}' was moved off another account in the last seven days and is kept for its "
    "owner to undo the change. Use another address, or try again once it is released."
)

#: Written to standard error when ``--email`` names an account that already existed and
#: the set-password link was mailed to it.
PROMOTED_NOTICE = (
    "'{email}' already had an account: its password was cleared, its sessions were "
    "ended, and a set-password link was mailed to it."
)

#: Written to standard error in place of :data:`PROMOTED_NOTICE` when the mail server
#: refused the set-password email.
PROMOTED_UNMAILED_NOTICE = (
    "'{email}' already had an account: its password was cleared and its sessions were "
    "ended, but the mail server refused the set-password email; use the link above."
)


class Command(BaseCommand):
    """Create the account ``--email`` names as a system administrator, or promote it.

    Without an account at that address, one is created: active, staff, a Django
    superuser, holding an unusable password, its email address marked verified, and
    holding the ``member``,
    ``system_admin``, and ``website_admin`` roles.  ``--first-name`` and
    ``--last-name`` name the new account; left out, both stay blank.

    With an account at that address already, it is made a superuser and given
    whatever of those three roles it lacks; every other role it holds is kept.  Since
    anybody can register any address, the account is first taken back from whoever
    set its password, with its row locked for the length of the command: the password
    is made unusable, any block on reactivating it is lifted (so the link can reopen a
    deactivated account, as a password reset does), its demo mark (``User.is_demo``) is
    cleared, so a seeded demo account made a real administrator's is never exempt from
    two-factor sign-in, every session signed in to the
    account is ended (:func:`apps.accounts.status.clear_password_and_end_sessions`), and
    the audit log
    records ``account.password_cleared`` with ``actor=command``, ``sessions`` (how many
    were ended), and ``unblocked``.  ``--first-name`` and ``--last-name``, when given,
    replace the account's names (recorded as ``account.update``); left out, the names
    stay as they were.  Once the transaction commits, the address is mailed the
    set-password invitation in its take-back wording
    (:func:`apps.accounts.services.send_password_invitation`), carrying a link as
    valid as the one the command prints.  :data:`PROMOTED_NOTICE` on standard error
    says so, or :data:`PROMOTED_UNMAILED_NOTICE` when the mail server refused the
    email, which is logged and does not fail the command.  This happens on every run
    for an existing address, an administrator's own included.  An existing account
    that is a donor is refused with ``CommandError`` and left untouched: a donor holds
    no role and cannot sign in, so it cannot be made an administrator.

    Either way the address is marked verified, recorded as ``account.email_verified``
    under the command actor when it was not already.

    Either way the role write goes through
    :func:`apps.accounts.services.update_account`, the same service an
    administration screen uses, under the command actor
    (:data:`caldart.audit.COMMAND_ACTOR`), so the audit log records ``account.roles``
    with ``actor=command`` and raises ``roles_changed`` naming the command actor, so
    every address subscribed to role changes hears of it.  Running the
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
        parser.add_argument("--first-name", default="", help="First name, when given.")
        parser.add_argument("--last-name", default="", help="Last name, when given.")

    def handle(self, *args: Any, **options: Any) -> None:
        """Create or promote the account named by ``--email``, and print its link.

        Raises ``CommandError`` naming the address when it is not a valid email
        address, when it already names a donor, and when another account keeps it as
        its recovery address after a change of address
        (``apps.accounts.services.address_holder``): the address is reserved for that
        account's owner to undo the change with.
        """
        email = options["email"].strip()
        try:
            validate_email(email)
        except ValidationError as exc:
            raise CommandError(f"'{email}' is not a valid email address.") from exc

        with transaction.atomic():
            lock_address(email)
            user = User.objects.select_for_update().filter(email__iexact=email).first()
            if user is None and address_holder(email) is not None:
                raise CommandError(RESERVED_ADDRESS_REFUSED.format(email=email))
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
                _take_back(user)
            confirm_email_address(user, actor=audit.COMMAND_ACTOR)

            wanted = [slug for slug in ROLE_SLUGS if slug in set(user.roles) | set(ADMIN_ROLES)]
            changes: AccountChanges = {"roles": wanted}
            if promoted and options["first_name"] != "":
                changes["first_name"] = options["first_name"]
            if promoted and options["last_name"] != "":
                changes["last_name"] = options["last_name"]
            update_account(audit.COMMAND_ACTOR, user, changes)

        if not promoted:
            self.stdout.write(build_reset_url(user))
            return
        is_mailed = send_logging_refusal(
            lambda: send_password_invitation(user, taken_back=True),
            what=f"the set-password link for account {user.pk}",
        )
        self.stdout.write(build_reset_url(user))
        notice = PROMOTED_NOTICE if is_mailed else PROMOTED_UNMAILED_NOTICE
        self.stderr.write(notice.format(email=user.email), self.style.WARNING)


def _take_back(user: User) -> None:
    """Clear ``user``'s password, block, demo mark, and two-factor; end its sessions.

    Any change of address waiting for its link is dropped with the password
    (``clear_password_and_end_sessions``): whoever asked for it may be whoever set the
    password being cleared.  The authenticator device and backup codes go too, so one
    somebody else set up on the account cannot keep the real owner out, and so do the
    address's counted failed sign-ins.  The demo mark (``User.is_demo``) is cleared, so
    the account is required to use two-factor sign-in by its roles whatever
    ``DEMO_ACCOUNTS_SKIP_TWO_FACTOR`` says.  Runs inside the caller's transaction, on a
    row it has locked.
    """
    is_blocked = user.reactivation_blocked
    user.reactivation_blocked = False
    user.is_demo = False
    user.save(update_fields=["reactivation_blocked", "is_demo", "updated_at"])
    ended = clear_password_and_end_sessions(user)
    had_device = remove_two_factor(user)
    lockout.clear_all_failures(user.email)
    audit.record(
        audit.ACCOUNT_CREDENTIALS_CLEARED,
        actor=audit.COMMAND_ACTOR,
        target=user,
        sessions=ended,
        unblocked=is_blocked,
        two_factor_removed=had_device,
    )
