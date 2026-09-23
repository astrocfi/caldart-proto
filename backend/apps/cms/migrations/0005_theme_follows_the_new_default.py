"""Move a site still carrying the old default theme onto the new one.

The theme field's default only reaches a row being created, so a site seeded
before ``duty`` existed would keep rendering ``sierra`` -- the palette nobody
chose, on a layout built for the new one.  Rows on ``pacific`` or ``night``
were picked deliberately and are left alone.
"""

from django.apps.registry import Apps
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor

OLD_DEFAULT = "sierra"
NEW_DEFAULT = "duty"


def adopt_new_default(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Rewrite every settings row still set to the old default theme."""
    site_settings = apps.get_model("cms", "SiteSettings")
    site_settings.objects.filter(theme=OLD_DEFAULT).update(theme=NEW_DEFAULT)


def restore_old_default(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Put those rows back on the old default theme."""
    site_settings = apps.get_model("cms", "SiteSettings")
    site_settings.objects.filter(theme=NEW_DEFAULT).update(theme=OLD_DEFAULT)


class Migration(migrations.Migration):
    dependencies = [("cms", "0004_home_page_boxes")]

    operations = [migrations.RunPython(adopt_new_default, restore_old_default)]
