"""Seed the demo accounts.

Idempotent: re-running updates the existing rows rather than duplicating them.
Every seeded account uses the password ``caldart-demo``.
"""

from __future__ import annotations

import re

from django.contrib.auth import get_user_model

from apps.accounts.roles import (
    ACCOUNT_ADMIN,
    DART_LEADER,
    MEMBER,
    SYSTEM_ADMIN,
    USER_ADMIN,
    WEBSITE_ADMIN,
)

User = get_user_model()

DEMO_PASSWORD = "caldart-demo"  # noqa: S105 - demo data, documented in the README

#: key -> (email, first, last, roles, is_superuser)
DEMO_ACCOUNTS: tuple[tuple[str, str, str, str, tuple[str, ...], bool], ...] = (
    ("member", "member@example.org", "Marta", "Reyes", (MEMBER,), False),
    ("expired", "expired@example.org", "Owen", "Delgado", (MEMBER,), False),
    ("leader", "leader@example.org", "Priya", "Raman", (MEMBER, DART_LEADER), False),
    ("useradmin", "useradmin@example.org", "Nina", "Kowalski", (MEMBER, USER_ADMIN), False),
    (
        "accountadmin",
        "accountadmin@example.org",
        "Curtis",
        "Whitfield",
        (MEMBER, ACCOUNT_ADMIN),
        False,
    ),
    ("webadmin", "webadmin@example.org", "Ada", "Lindqvist", (MEMBER, WEBSITE_ADMIN), False),
    (
        "sysadmin",
        "sysadmin@example.org",
        "Rafael",
        "Ibarra",
        (MEMBER, SYSTEM_ADMIN),
        True,
    ),
)

#: How many synthetic members to generate on top of the named demo accounts.
GENERATED_MEMBER_COUNT = 40

_SLUG_RE = re.compile(r"[^a-z]")


def _email_for(first: str, last: str, index: int) -> str:
    first = _SLUG_RE.sub("", first.lower()) or "member"
    last = _SLUG_RE.sub("", last.lower()) or "caldart"
    return f"{first}.{last}{index:02d}@example.org"


def upsert_user(
    email: str,
    first_name: str,
    last_name: str,
    roles: tuple[str, ...] | list[str],
    *,
    is_superuser: bool = False,
    password: str = DEMO_PASSWORD,
) -> tuple[User, bool]:
    """Create or refresh a demo user, returning ``(user, created)``."""
    user, created = User.objects.get_or_create(
        email=email,
        defaults={"first_name": first_name, "last_name": last_name},
    )
    user.first_name = first_name
    user.last_name = last_name
    user.is_active = True
    user.is_superuser = is_superuser
    user.is_staff = is_superuser
    user.set_password(password)
    user.save()
    user.set_roles(list(roles))
    return user, created


def run(ctx: dict, stdout=None) -> dict:
    """Create the named demo accounts plus ``GENERATED_MEMBER_COUNT`` members."""
    faker = ctx["faker"]

    demo: dict[str, User] = {}
    for key, email, first, last, roles, is_superuser in DEMO_ACCOUNTS:
        user, _ = upsert_user(email, first, last, roles, is_superuser=is_superuser)
        demo[key] = user

    generated: list[User] = []
    for index in range(1, GENERATED_MEMBER_COUNT + 1):
        first = faker.first_name()
        last = faker.last_name()
        user, _ = upsert_user(_email_for(first, last, index), first, last, (MEMBER,))
        generated.append(user)

    ctx["demo_users"] = demo
    ctx["generated_users"] = generated
    ctx["users"] = [*demo.values(), *generated]

    if stdout is not None:
        stdout.write(f"  accounts: {len(demo)} demo + {len(generated)} generated")
    return ctx
