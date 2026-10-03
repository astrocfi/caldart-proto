"""Create the three email types every installation starts with.

Operational, Fundraising, and Mission, all of which recipients may turn off.  Each is
found or created by its slug, so a database that already holds one keeps it as it is.
Reversing the migration leaves the rows alone: by then a system administrator may have
edited them, and a bulk email may name them.
"""

from django.apps.registry import Apps
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor

#: ``(slug, name, description, sender roles, position)`` for each default type.
DEFAULT_TYPES: tuple[tuple[str, str, str, list[str], int], ...] = (
    (
        "operational",
        "Operational",
        "News about how CalDART runs: meetings, training, exercises, and changes that "
        "affect members.",
        ["dart_leader", "management"],
        1,
    ),
    (
        "fundraising",
        "Fundraising",
        "Appeals for donations and news about CalDART's fundraising events.",
        ["management"],
        2,
    ),
    (
        "mission",
        "Mission",
        "Requests for pilots and aircraft when a disaster or an exercise needs them.",
        ["dart_leader", "management"],
        3,
    ),
)


def create_default_types(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Find or create each default type by its slug, leaving an existing one as it is."""
    email_type = apps.get_model("mail", "EmailType")
    for slug, name, description, roles, position in DEFAULT_TYPES:
        email_type.objects.get_or_create(
            slug=slug,
            defaults={
                "name": name,
                "description": description,
                "allow_opt_out": True,
                "sender_roles": roles,
                "position": position,
            },
        )


class Migration(migrations.Migration):
    """Create Operational, Fundraising, and Mission."""

    dependencies = [
        ("mail", "0003_email_types"),
    ]

    operations = [
        migrations.RunPython(create_default_types, migrations.RunPython.noop),
    ]
