"""The email types every installation starts with, and the demo seed that leans on them.

The behavior is documented in ``docs/developer/data-model.rst``.
"""

from __future__ import annotations

from importlib import import_module

import pytest
from django.apps import apps as django_apps

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


#: The migration that creates the default types, imported by path since its name starts
#: with a digit.
DEFAULT_TYPES_MIGRATION = import_module("apps.mail.migrations.0004_default_email_types")


def test_running_the_migration_again_adds_no_copy_of_a_renamed_type() -> None:
    """After a rollback, a renamed Operational is not joined by a second Operational."""
    operational = EmailType.objects.get(slug="operational")
    operational.name = "Club news"
    operational.save()

    DEFAULT_TYPES_MIGRATION.create_default_types(django_apps, None)

    assert sorted(EmailType.objects.values_list("slug", flat=True)) == [
        "club-news",
        "fundraising",
        "mission",
    ]


def test_running_the_migration_again_does_not_bring_back_a_deleted_type() -> None:
    """A type the system administrator deleted stays deleted."""
    EmailType.objects.filter(slug="fundraising").delete()

    DEFAULT_TYPES_MIGRATION.create_default_types(django_apps, None)

    assert sorted(EmailType.objects.values_list("slug", flat=True)) == ["mission", "operational"]


def test_the_migration_creates_the_three_types_in_an_empty_table() -> None:
    """With no type at all, the three defaults are created again in their order."""
    EmailType.objects.all().delete()

    DEFAULT_TYPES_MIGRATION.create_default_types(django_apps, None)

    assert list(EmailType.objects.values_list("slug", flat=True)) == [
        "operational",
        "fundraising",
        "mission",
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
