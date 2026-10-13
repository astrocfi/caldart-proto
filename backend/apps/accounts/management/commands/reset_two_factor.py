"""``manage.py reset_two_factor`` -- take an account's two-factor sign-in away."""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction

from apps.accounts import lockout, mfa
from apps.accounts.models import User
from caldart import audit
from caldart.exceptions import DomainError


class Command(BaseCommand):
    """Reset the two-factor sign-in of the account ``--email`` names, from the server.

    For the administrator who has lost both their phone and their backup codes when no
    other administrator can reset it from the user record.  It does exactly what the
    user record's **Reset two-factor** does (:func:`apps.accounts.mfa.reset_two_factor`)
    under the command actor (:data:`caldart.audit.COMMAND_ACTOR`): the device and the
    backup codes are deleted, every session signed in to the account is ended, the
    reset is recorded as ``account.mfa_reset`` with ``actor=command`` and in the
    account's history as *The system*, and the account is mailed a notice.  Every
    failed sign-in counted against the address is forgotten too
    (:func:`apps.accounts.lockout.clear_all_failures`), so a lockout does not outlast
    the reset.  The person sets two-factor sign-in up again at their next sign-in.
    Prints one line naming the address.

    Raises ``CommandError`` when no account has that address (compared
    case-insensitively), and with the refusal's sentence for a donor.
    """

    help = "Reset the two-factor sign-in of the account at --email."

    def add_arguments(self, parser: CommandParser) -> None:
        """Declare ``--email`` (required)."""
        parser.add_argument("--email", required=True, help="The account's email address.")

    def handle(self, *args: Any, **options: Any) -> None:
        """Reset the account's two-factor sign-in and say so on standard output."""
        email: str = options["email"].strip()
        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            raise CommandError(f"No account has the address '{email}'.")
        try:
            with transaction.atomic():
                mfa.reset_two_factor(audit.COMMAND_ACTOR, user)
            lockout.clear_all_failures(user.email)
        except DomainError as error:
            raise CommandError(error.message) from error
        self.stdout.write(f"Two-factor sign-in reset for {user.email}.")
