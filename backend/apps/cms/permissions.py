"""Wagtail editor permissions for the ``website_admin`` role.

The role is a plain Django ``Group``, so granting website
administrators their editing rights is just a matter of hanging the right
permission rows off that group:

* ``wagtailadmin.access_admin`` — lets them reach ``/admin/`` at all;
* add / change / publish / bulk-delete / lock on the **root page**, which
  cascades to every page in the tree;
* add / change / choose on the **root collection** for images and documents;
* add / change / delete on ``wagtailredirects.Redirect``, so an editor who
  renames a page can point the old address at the new one themselves;
* ``cms.change_sitesettings`` for the Site Settings form.

:func:`grant_website_admin_permissions` is called from a cms data migration and
again from ``manage.py seed_content``, and is safe to run any number of times.
It takes an optional ``apps`` registry so the migration can pass its historical
models; every query is written against plain fields for that reason.
"""

from __future__ import annotations

from django.apps import apps as django_apps

from apps.accounts.roles import WEBSITE_ADMIN

#: Page permissions granted on the tree root, in Wagtail's own naming.
PAGE_PERMISSION_TYPES: tuple[str, ...] = (
    "add",
    "change",
    "publish",
    "bulk_delete",
    "lock",
)

#: ``(app_label, model, codename)`` for the image and document collections.
COLLECTION_PERMISSIONS: tuple[tuple[str, str, str], ...] = (
    ("wagtailimages", "image", "add_image"),
    ("wagtailimages", "image", "change_image"),
    ("wagtailimages", "image", "choose_image"),
    ("wagtaildocs", "document", "add_document"),
    ("wagtaildocs", "document", "change_document"),
    ("wagtaildocs", "document", "choose_document"),
)

#: Model permissions granted directly to the group.  Deliberately not
#: ``wagtailcore.change_site``: editing hostnames is a system administrator's
#: job, and Site Settings only needs ``change_sitesettings``.
MODEL_PERMISSIONS: tuple[tuple[str, str, str], ...] = (
    ("wagtailadmin", "admin", "access_admin"),
    ("cms", "sitesettings", "change_sitesettings"),
    # Renaming a page changes its URL; without these the editor who did it
    # cannot fix the 404 they just made.
    ("wagtailredirects", "redirect", "add_redirect"),
    ("wagtailredirects", "redirect", "change_redirect"),
    ("wagtailredirects", "redirect", "delete_redirect"),
)

#: Human names, so a freshly created permission row is not blank in the admin.
PERMISSION_NAMES: dict[str, str] = {
    "access_admin": "Can access Wagtail admin",
    "change_sitesettings": "Can change site settings",
    "add_image": "Can add image",
    "change_image": "Can change image",
    "choose_image": "Can choose image",
    "add_document": "Can add document",
    "change_document": "Can change document",
    "choose_document": "Can choose document",
    "add_redirect": "Can add redirect",
    "change_redirect": "Can change redirect",
    "delete_redirect": "Can delete redirect",
}


def _permission(models, app_label: str, model: str, codename: str):
    """Fetch (or create) one ``auth.Permission`` row.

    ``get_or_create`` rather than ``get`` because this also runs from a data
    migration, and Django only creates the permission rows in a ``post_migrate``
    handler that has not fired yet.  Django's own creation step skips codenames
    that already exist, so pre-creating them here is safe.
    """
    Permission = models("auth", "Permission")
    ContentType = models("contenttypes", "ContentType")

    content_type, _ = ContentType.objects.get_or_create(app_label=app_label, model=model)
    permission, _ = Permission.objects.get_or_create(
        content_type=content_type,
        codename=codename,
        defaults={"name": PERMISSION_NAMES.get(codename, codename.replace("_", " ").capitalize())},
    )
    return permission


def grant_website_admin_permissions(apps=None, *, stdout=None):
    """Give the ``website_admin`` group its Wagtail rights.  Idempotent."""
    registry = apps or django_apps
    models = registry.get_model

    Group = models("auth", "Group")
    Page = models("wagtailcore", "Page")
    Collection = models("wagtailcore", "Collection")
    GroupPagePermission = models("wagtailcore", "GroupPagePermission")
    GroupCollectionPermission = models("wagtailcore", "GroupCollectionPermission")

    group, _ = Group.objects.get_or_create(name=WEBSITE_ADMIN)

    for app_label, model, codename in MODEL_PERMISSIONS:
        group.permissions.add(_permission(models, app_label, model, codename))

    # The tree root, so the grant covers every current and future page.
    root_page = Page.objects.filter(depth=1).order_by("path").first()
    if root_page is not None:
        for permission_type in PAGE_PERMISSION_TYPES:
            GroupPagePermission.objects.get_or_create(
                group=group,
                page=root_page,
                permission=_permission(models, "wagtailcore", "page", f"{permission_type}_page"),
            )

    root_collection = Collection.objects.order_by("path").first()
    if root_collection is not None:
        for app_label, model, codename in COLLECTION_PERMISSIONS:
            GroupCollectionPermission.objects.get_or_create(
                group=group,
                collection=root_collection,
                permission=_permission(models, app_label, model, codename),
            )

    if stdout is not None:
        stdout.write(f"  cms: '{WEBSITE_ADMIN}' group has Wagtail editor permissions")
    return group
