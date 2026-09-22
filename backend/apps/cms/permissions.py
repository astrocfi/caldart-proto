"""Wagtail editor permissions for the ``website_admin`` role.

The role is a plain Django ``Group``, so granting website
administrators their editing rights is just a matter of hanging the right
permission rows off that group:

* ``wagtailadmin.access_admin`` -- lets them reach ``/admin/`` at all;
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

from typing import TYPE_CHECKING, Any, Protocol

from django.apps import apps as django_apps
from django.contrib.auth.models import Group, Permission

from apps.accounts.roles import WEBSITE_ADMIN

if TYPE_CHECKING:
    from django.apps.registry import Apps
    from django.core.management.base import OutputWrapper


class ModelGetter(Protocol):
    """How a registry hands over a model class: ``get_model(app_label, model_name)``.

    Both the live app registry and the historical one a data migration carries
    answer this call, which is why the functions below take a registry rather than
    importing the models directly.  A historical model class is built at migration
    time and has no static type, so the class comes back unchecked.
    """

    def __call__(self, app_label: str, model_name: str) -> type[Any]:
        """Return the model class registered as ``app_label.model_name``."""
        ...


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


def _permission(models: ModelGetter, app_label: str, model: str, codename: str) -> Permission:
    """Fetch (or create) one ``auth.Permission`` row.

    The row is looked up by content type and ``codename``; a row created here is
    named from :data:`PERMISSION_NAMES`, falling back to the codename with its
    underscores turned into spaces.  The content type is created too when it is
    missing.

    ``get_or_create`` rather than ``get`` because this also runs from a data
    migration, and Django only creates the permission rows in a ``post_migrate``
    handler that has not fired yet.  Django's own creation step skips codenames
    that already exist, so pre-creating them here is safe.
    """
    permission_model = models("auth", "Permission")
    content_type_model = models("contenttypes", "ContentType")

    content_type, _ = content_type_model.objects.get_or_create(app_label=app_label, model=model)
    permission: Permission = permission_model.objects.get_or_create(
        content_type=content_type,
        codename=codename,
        defaults={"name": PERMISSION_NAMES.get(codename, codename.replace("_", " ").capitalize())},
    )[0]
    return permission


def grant_website_admin_permissions(
    apps: Apps | None = None, *, stdout: OutputWrapper | None = None
) -> Group:
    """Give the ``website_admin`` group its Wagtail rights.  Idempotent.

    Returns the group, creating it if it does not exist yet.  It gains the model
    permissions in :data:`MODEL_PERMISSIONS`, the page permissions in
    :data:`PAGE_PERMISSION_TYPES` on the tree root, and the collection permissions
    in :data:`COLLECTION_PERMISSIONS` on the root collection.  A missing tree root
    or root collection simply skips that half of the grant, so the call still
    succeeds on an empty database.  Permissions the group already holds are left
    as they are, and none is ever taken away.

    ``apps`` is a historical app registry, which a data migration passes so the
    grant runs against the models of its own moment; the live registry is used
    without one.  With ``stdout``, one line confirming the grant is written to it.
    """
    registry = apps or django_apps
    models: ModelGetter = registry.get_model

    group_model = models("auth", "Group")
    page_model = models("wagtailcore", "Page")
    collection_model = models("wagtailcore", "Collection")
    group_page_permission_model = models("wagtailcore", "GroupPagePermission")
    group_collection_permission_model = models("wagtailcore", "GroupCollectionPermission")

    group: Group = group_model.objects.get_or_create(name=WEBSITE_ADMIN)[0]

    for app_label, model, codename in MODEL_PERMISSIONS:
        group.permissions.add(_permission(models, app_label, model, codename))

    # The tree root, so the grant covers every current and future page.
    root_page = page_model.objects.filter(depth=1).order_by("path").first()
    if root_page is not None:
        for permission_type in PAGE_PERMISSION_TYPES:
            group_page_permission_model.objects.get_or_create(
                group=group,
                page=root_page,
                permission=_permission(models, "wagtailcore", "page", f"{permission_type}_page"),
            )

    root_collection = collection_model.objects.order_by("path").first()
    if root_collection is not None:
        for app_label, model, codename in COLLECTION_PERMISSIONS:
            group_collection_permission_model.objects.get_or_create(
                group=group,
                collection=root_collection,
                permission=_permission(models, app_label, model, codename),
            )

    if stdout is not None:
        stdout.write(f"  cms: '{WEBSITE_ADMIN}' group has Wagtail editor permissions")
    return group
