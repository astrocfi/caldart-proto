"""Create the role groups as part of ``migrate``."""

from django.db import migrations

from apps.accounts.roles import ROLE_SLUGS


def create_roles(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for slug in ROLE_SLUGS:
        Group.objects.get_or_create(name=slug)


def drop_roles(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=ROLE_SLUGS).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(create_roles, drop_roles),
    ]
