"""Extensions on the other two numbers, and a three-character home airport."""

from django.db import migrations, models


def shorten_home_airports(apps, schema_editor):
    """Bring every stored identifier to the three-character form: K prefix off."""
    MemberProfile = apps.get_model("members", "MemberProfile")
    for profile in MemberProfile.objects.exclude(home_airport_identifier="").iterator():
        identifier = profile.home_airport_identifier.upper().lstrip("K")[:3]
        if identifier != profile.home_airport_identifier:
            profile.home_airport_identifier = identifier
            profile.save(update_fields=["home_airport_identifier"])


class Migration(migrations.Migration):

    dependencies = [
        ('members', '0005_normalize_stored_phones'),
    ]

    operations = [
        migrations.RunPython(shorten_home_airports, migrations.RunPython.noop),
        migrations.AddField(
            model_name='memberprofile',
            name='emergency_contact_phone_extension',
            field=models.CharField(blank=True, max_length=6),
        ),
        migrations.AddField(
            model_name='memberprofile',
            name='phone_alt_extension',
            field=models.CharField(blank=True, max_length=6),
        ),
        migrations.AlterField(
            model_name='memberprofile',
            name='home_airport_identifier',
            field=models.CharField(blank=True, max_length=3),
        ),
    ]
