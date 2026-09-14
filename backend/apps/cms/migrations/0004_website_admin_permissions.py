"""Give the ``website_admin`` group its Wagtail editing rights.

The grant itself lives in ``apps.cms.permissions`` so ``manage.py seed_content``
can re-apply it after the page tree changes.
"""

from django.db import migrations


def grant(apps, schema_editor):
    from apps.cms.permissions import grant_website_admin_permissions

    grant_website_admin_permissions(apps)


def revoke(apps, schema_editor):
    from apps.accounts.roles import WEBSITE_ADMIN

    Group = apps.get_model("auth", "Group")
    group = Group.objects.filter(name=WEBSITE_ADMIN).first()
    if group is None:
        return
    group.permissions.clear()
    group.page_permissions.all().delete()
    group.collection_permissions.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("cms", "0003_page_types"),
        ("accounts", "0002_seed_roles"),
        ("wagtailcore", "0098_apitoken"),
        ("wagtailimages", "0027_image_description"),
        ("wagtaildocs", "0014_alter_document_file_size"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(grant, revoke),
    ]
