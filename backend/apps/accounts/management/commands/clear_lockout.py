"""``manage.py clear_lockout`` -- lift the sign-in lockout on one email address."""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from apps.accounts import lockout


class Command(BaseCommand):
    """Forget every failed sign-in counted against ``--email``.

    For an owner locked out by somebody else's guesses (``apps.accounts.lockout``): the
    fifteen-minute count of wrong passwords and codes and the day's count of wrong
    codes are both cleared, so the next sign-in is judged afresh.  The address is
    resolved as sign-in resolves it, so any spelling of an account's address clears
    that account's counts; an address no account holds clears its own.  Doesn't
    change anything else, and prints one line naming the address.
    """

    help = "Forget the failed sign-in attempts counted against --email."

    def add_arguments(self, parser: CommandParser) -> None:
        """Declare ``--email`` (required)."""
        parser.add_argument("--email", required=True, help="The address to clear.")

    def handle(self, *args: Any, **options: Any) -> None:
        """Clear the counts and say so on standard output."""
        email: str = options["email"].strip()
        lockout.clear_all_failures(email)
        self.stdout.write(f"Failed sign-in attempts cleared for {email}.")
