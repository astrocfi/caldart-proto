"""Create the membership plans as part of ``migrate``."""

from django.db import migrations

from apps.members.plans import PLANS


def create_plans(apps, schema_editor):
    MembershipPlan = apps.get_model("members", "MembershipPlan")
    for spec in PLANS:
        MembershipPlan.objects.update_or_create(
            slug=spec["slug"],
            defaults={
                "name": spec["name"],
                "price_cents": spec["price_cents"],
                "duration_days": spec["duration_days"],
                "sort_order": spec["sort_order"],
                "description": spec["description"],
                "is_active": True,
            },
        )


def drop_plans(apps, schema_editor):
    MembershipPlan = apps.get_model("members", "MembershipPlan")
    MembershipPlan.objects.filter(slug__in=[spec["slug"] for spec in PLANS]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("members", "0003_verification"),
    ]

    operations = [
        migrations.RunPython(create_plans, drop_plans),
    ]
