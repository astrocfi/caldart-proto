"""Put every stored phone number into ``XXX-XXX-XXXX`` form.

The three phone fields were free text until now, so a database may hold
``(415) 555-0100``, ``415.555.0100`` and ``4155550100`` side by side.  Each is
rewritten to the one shape every screen, export and search now expects.  A
value that cannot be read as ten digits is left exactly as it was: it is
somebody's note to themselves, and the next edit refuses it at the boundary
rather than this migration guessing.
"""

from django.apps.registry import Apps
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor

from apps.members.models import normalize_phone

FIELDS = ("phone", "phone_alt", "emergency_contact_phone")


def normalize(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Rewrite every readable number, leaving the rest untouched."""
    profile_model = apps.get_model("members", "MemberProfile")
    changed = []
    for profile in profile_model.objects.all().iterator():
        dirty = False
        for field in FIELDS:
            before = getattr(profile, field)
            after = normalize_phone(before)
            if after != before:
                setattr(profile, field, after)
                dirty = True
        if dirty:
            changed.append(profile)
    profile_model.objects.bulk_update(changed, FIELDS, batch_size=500)


class Migration(migrations.Migration):
    dependencies = [("members", "0004_profile_validation_fields")]

    operations = [migrations.RunPython(normalize, migrations.RunPython.noop)]
