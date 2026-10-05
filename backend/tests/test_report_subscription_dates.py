"""The data migration that drops the fixed dates an emailed report no longer offers.

A contributions subscription that stored a fixed ``year``, or a reconciliation one fixed
``from`` and ``to`` dates, kept sending those rows until edited; the migration clears
them and leaves every other filter, and every other report's subscriptions, as they were.
"""

from __future__ import annotations

import importlib

import pytest
from django.apps import apps
from django.db import connection

from apps.reports.models import ReportSubscription
from tests.factories import ReportSubscriptionFactory

pytestmark = pytest.mark.django_db

MIGRATION = importlib.import_module("apps.reports.migrations.0002_drop_fixed_dates")


def _run_migration() -> None:
    """Run the migration's forward function against the current models."""
    with connection.schema_editor() as editor:
        MIGRATION.drop_fixed_dates(apps, editor)


def _filters(subscription: ReportSubscription) -> dict[str, object]:
    """The subscription's filters as the database holds them after the migration."""
    subscription.refresh_from_db()
    return dict(subscription.filters)


def test_a_contributions_subscription_loses_its_fixed_year() -> None:
    """``year`` goes, so the email follows the day it is sent; ``period`` stays."""
    subscription = ReportSubscriptionFactory(
        report="contributions", filters={"year": "2024", "period": "last_year"}
    )
    _run_migration()
    assert _filters(subscription) == {"period": "last_year"}


def test_a_reconciliation_subscription_loses_its_fixed_dates() -> None:
    """``from`` and ``to`` go; the provider and the period stay."""
    subscription = ReportSubscriptionFactory(
        report="reconciliation",
        filters={"from": "2026-01-01", "to": "2026-03-31", "provider": "stripe"},
    )
    _run_migration()
    assert _filters(subscription) == {"provider": "stripe"}


def test_another_report_keeps_a_filter_of_the_same_name() -> None:
    """Only the two reports are touched: a payments subscription keeps its dates."""
    subscription = ReportSubscriptionFactory(
        report="payments", filters={"from": "2026-01-01", "status": "succeeded"}
    )
    _run_migration()
    assert _filters(subscription) == {"from": "2026-01-01", "status": "succeeded"}
