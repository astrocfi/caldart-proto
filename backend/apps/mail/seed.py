"""Seed one demo opt-out from the email types every installation starts with.

Operational, Fundraising, and Mission are created by the migration
``mail/0004_default_email_types``, so the seed creates no type.  It turns Fundraising
off for the demo friend, so a bulk email shows a skipped recipient.  Idempotent: a
second run finds the opt-out already there.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import OutputWrapper

from apps.accounts.models import User
from apps.mail.models import EmailOptOut, EmailType, OptOutSource

#: The demo account, keyed as in ``apps.accounts.seed.DEMO_ACCOUNTS``, that has turned
#: Fundraising off.
OPTED_OUT_ACCOUNT = "friend"

#: The slug of the type the demo friend has turned off.
OPTED_OUT_TYPE = "fundraising"


def run(ctx: dict[str, Any], stdout: OutputWrapper | None = None) -> dict[str, Any]:
    """Turn Fundraising off for the demo friend, from their own Email preferences.

    Nothing is recorded when a system administrator has deleted Fundraising.  Reads
    ``demo_users`` from ``ctx`` and returns ``ctx`` unchanged.  When ``stdout`` is
    given, one summary line is written to it.
    """
    fundraising = EmailType.objects.filter(slug=OPTED_OUT_TYPE).first()
    count = 0
    if fundraising is not None:
        demo: dict[str, User] = ctx["demo_users"]
        EmailOptOut.objects.get_or_create(
            user=demo[OPTED_OUT_ACCOUNT],
            email_type=fundraising,
            defaults={"source": OptOutSource.PROFILE},
        )
        count = 1
    if stdout is not None:
        stdout.write(f"  mail: {count} opt-out")
    return ctx
