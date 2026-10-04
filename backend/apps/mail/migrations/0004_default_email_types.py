"""Create the three email types every installation starts with.

Operational, Fundraising, and Mission, all of which recipients may turn off.  They are
created only when the table holds no type at all: once any type exists the list belongs
to the system administrator, so running the migration again after a rollback neither
brings back a deleted type nor adds a second copy of one that was renamed (a type's slug
follows its name).  Reversing the migration leaves the rows alone: by then a system
administrator may have edited them, and a bulk email may name them.
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
    """Create the default types when there is no type yet; otherwise change nothing."""
    email_type = apps.get_model("mail", "EmailType")
    if email_type.objects.exists():
        return
    email_type.objects.bulk_create(
        email_type(
            slug=slug,
            name=name,
            description=description,
            allow_opt_out=True,
            sender_roles=roles,
            position=position,
        )
        for slug, name, description, roles, position in DEFAULT_TYPES
    )


class Migration(migrations.Migration):
    """Create Operational, Fundraising, and Mission."""

    dependencies = [
        ("mail", "0003_email_types"),
    ]

    operations = [
        migrations.RunPython(create_default_types, migrations.RunPython.noop),
    ]
