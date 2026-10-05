"""Drop the fixed dates an emailed report no longer offers.

A contributions subscription chooses its year relative to the day it is sent (blank for
this year, ``last_year`` for the one before), and a reconciliation subscription its
**Period**; a fixed ``year``, or fixed ``from`` and ``to`` dates, would send the same
rows every time.  A subscription saved before the form stopped offering them keeps them
until somebody edits it, so this clears them: a contributions subscription loses its
``year``, leaving it on this year, and a reconciliation one its ``from`` and ``to``.  A
reconciliation subscription that had fixed dates and no period is set to last month, the
period a monthly reconciliation means, rather than left on every date.  Reversing it
changes nothing, since the dates are gone.
"""

from django.apps.registry import Apps
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor

#: The filters each report's subscriptions no longer keep, by the report's slug.
DROPPED_FILTERS: dict[str, tuple[str, ...]] = {
    "contributions": ("year",),
    "reconciliation": ("from", "to"),
}

#: The period a reconciliation subscription that loses its fixed dates is given when it
#: names none.
RECONCILIATION_PERIOD = "last_month"


def drop_fixed_dates(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Remove the dropped filters from every subscription to their report."""
    subscription = apps.get_model("reports", "ReportSubscription")
    for report, keys in DROPPED_FILTERS.items():
        for row in subscription.objects.filter(report=report):
            kept = {key: value for key, value in row.filters.items() if key not in keys}
            if kept == row.filters:
                continue
            if report == "reconciliation" and not kept.get("period"):
                kept["period"] = RECONCILIATION_PERIOD
            row.filters = kept
            row.save(update_fields=["filters"])


class Migration(migrations.Migration):
    """Clears the fixed dates of the contributions and reconciliation subscriptions."""

    dependencies = [
        ("reports", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(drop_fixed_dates, migrations.RunPython.noop),
    ]
