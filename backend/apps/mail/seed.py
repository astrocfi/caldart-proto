"""Seed the three demo email types, and one demo opt-out.

Idempotent: re-running updates the three types by name rather than adding more, and
leaves the opt-out as it is.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import OutputWrapper

from apps.accounts.models import User
from apps.accounts.roles import DART_LEADER, MANAGEMENT
from apps.mail.models import EmailOptOut, EmailType, OptOutSource

#: ``(name, description, sender roles)`` for each type, in the screens' order.  Every
#: one allows opting out.
DEMO_TYPES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "Operational",
        "News about how CalDART runs: meetings, training, exercises, and changes that "
        "affect members.",
        (DART_LEADER, MANAGEMENT),
    ),
    (
        "Fundraising",
        "Appeals for donations and news about CalDART's fundraising events.",
        (MANAGEMENT,),
    ),
    (
        "Mission",
        "Requests for pilots and aircraft when a disaster or an exercise needs them.",
        (DART_LEADER, MANAGEMENT),
    ),
)

#: The demo account, keyed as in ``apps.accounts.seed.DEMO_ACCOUNTS``, that has turned
#: Fundraising off, so a bulk email shows a skipped recipient.
OPTED_OUT_ACCOUNT = "friend"


def run(ctx: dict[str, Any], stdout: OutputWrapper | None = None) -> dict[str, Any]:
    """Create or update Operational, Fundraising, and Mission, and one opt-out.

    Operational and Mission are sent by CalDART management and DART leaders, and
    Fundraising by CalDART management alone; all three allow opting out, at positions 1
    to 3.  The demo friend has turned Fundraising off from their own Email preferences.
    Reads ``demo_users`` from ``ctx`` and returns ``ctx`` unchanged.  When ``stdout`` is
    given, one summary line is written to it.
    """
    types: dict[str, EmailType] = {}
    for position, (name, description, roles) in enumerate(DEMO_TYPES, start=1):
        email_type, _created = EmailType.objects.update_or_create(
            name=name,
            defaults={
                "description": description,
                "allow_opt_out": True,
                "sender_roles": list(roles),
                "position": position,
            },
        )
        types[name] = email_type
    demo: dict[str, User] = ctx["demo_users"]
    EmailOptOut.objects.get_or_create(
        user=demo[OPTED_OUT_ACCOUNT],
        email_type=types["Fundraising"],
        defaults={"source": OptOutSource.PROFILE},
    )
    if stdout is not None:
        stdout.write(f"  mail: {len(DEMO_TYPES)} email types, 1 opt-out")
    return ctx
