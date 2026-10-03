"""The email types every installation starts with, and the demo seed that leans on them.

The behavior is documented in ``docs/developer/data-model.rst``.
"""

from __future__ import annotations

import pytest

from apps.accounts.models import User
from apps.accounts.roles import DART_LEADER, MANAGEMENT
from apps.mail import seed
from apps.mail.models import EmailOptOut, EmailType, OptOutSource

pytestmark = pytest.mark.django_db


def test_a_fresh_database_holds_the_three_default_types() -> None:
    """Operational, Fundraising, and Mission exist from the start, with their senders."""
    rows = [
        (row.slug, row.name, row.sender_roles, row.allow_opt_out, row.position)
        for row in EmailType.objects.all()
    ]

    assert rows == [
        ("operational", "Operational", [DART_LEADER, MANAGEMENT], True, 1),
        ("fundraising", "Fundraising", [MANAGEMENT], True, 2),
        ("mission", "Mission", [DART_LEADER, MANAGEMENT], True, 3),
    ]


def test_the_seed_turns_fundraising_off_for_the_demo_friend(friend: User) -> None:
    """The seed records one opt-out from the friend's own preferences."""
    seed.run({"demo_users": {"friend": friend}})

    opt_out = EmailOptOut.objects.get(user=friend)
    assert (opt_out.email_type.slug, opt_out.source) == ("fundraising", OptOutSource.PROFILE)


def test_the_seed_creates_no_type_and_runs_twice_safely(friend: User) -> None:
    """The seed adds no type of its own, and a second run adds nothing."""
    seed.run({"demo_users": {"friend": friend}})
    seed.run({"demo_users": {"friend": friend}})

    assert EmailType.objects.count() == 3
    assert EmailOptOut.objects.filter(user=friend).count() == 1


def test_the_seed_records_nothing_once_fundraising_is_deleted(friend: User) -> None:
    """A site whose administrator deleted Fundraising seeds no opt-out."""
    EmailType.objects.filter(slug="fundraising").delete()

    seed.run({"demo_users": {"friend": friend}})

    assert not EmailOptOut.objects.filter(user=friend).exists()
