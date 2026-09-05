"""Wagtail editing rights for the ``website_admin`` role (PLAN §4.6).

The grant is applied by the ``cms.0004_website_admin_permissions`` data
migration, so it is already in place for every test — these check that it
actually lets a website administrator work, and that nobody else gets in.
"""

from __future__ import annotations

import pytest
from django.contrib.auth.models import Group
from wagtail.models import Collection, GroupCollectionPermission, GroupPagePermission, Page

from apps.accounts.roles import WEBSITE_ADMIN
from apps.cms.forms import RestrictedBlocksPageForm, can_use_raw_html
from apps.cms.models import StandardPage
from apps.cms.permissions import grant_website_admin_permissions
from tests.test_cms_pages import make_standard_page

pytestmark = pytest.mark.django_db


@pytest.fixture
def about(site_settings):
    home = site_settings.site.root_page.specific
    return make_standard_page(
        home,
        "about",
        "About Us",
        intro="Who we are.",
        body=[("paragraph", "<p>Original copy.</p>")],
    )


# ------------------------------------------------------------ the grant
def test_migration_granted_the_website_admin_group_its_permissions():
    group = Group.objects.get(name=WEBSITE_ADMIN)
    codenames = set(group.permissions.values_list("codename", flat=True))
    assert {"access_admin", "change_sitesettings"} <= codenames

    root_page = Page.objects.filter(depth=1).first()
    page_perms = set(
        GroupPagePermission.objects.filter(group=group, page=root_page).values_list(
            "permission__codename", flat=True
        )
    )
    assert {"add_page", "change_page", "publish_page", "bulk_delete_page"} <= page_perms

    root_collection = Collection.objects.order_by("path").first()
    collection_perms = set(
        GroupCollectionPermission.objects.filter(
            group=group, collection=root_collection
        ).values_list("permission__codename", flat=True)
    )
    assert {"add_image", "change_image", "add_document", "change_document"} <= collection_perms


def test_granting_twice_adds_nothing(db):
    before = (
        GroupPagePermission.objects.count(),
        GroupCollectionPermission.objects.count(),
    )
    grant_website_admin_permissions()
    grant_website_admin_permissions()
    assert (
        GroupPagePermission.objects.count(),
        GroupCollectionPermission.objects.count(),
    ) == before


# --------------------------------------------------- reaching the admin
def test_website_admin_reaches_the_wagtail_admin(client, website_admin):
    client.force_login(website_admin)
    response = client.get("/admin/")
    assert response.status_code == 200


def test_plain_member_is_bounced_from_the_wagtail_admin(client, member):
    client.force_login(member)
    response = client.get("/admin/")
    assert response.status_code == 302
    assert "/admin/login/" in response["Location"]


def test_dart_leader_is_bounced_from_the_wagtail_admin(client, leader):
    client.force_login(leader)
    assert client.get("/admin/").status_code == 302


def test_system_admin_is_a_superuser_and_reaches_the_admin(client, superuser):
    client.force_login(superuser)
    assert client.get("/admin/").status_code == 200


# --------------------------------------------------------- editing pages
def test_website_admin_can_open_the_page_editor(client, website_admin, about):
    client.force_login(website_admin)
    response = client.get(f"/admin/pages/{about.pk}/edit/")
    assert response.status_code == 200
    assert "About Us" in response.content.decode()


def test_member_cannot_open_the_page_editor(client, member, about):
    client.force_login(member)
    response = client.get(f"/admin/pages/{about.pk}/edit/")
    assert response.status_code == 302


def test_website_admin_can_edit_and_publish_a_page(client, website_admin, about):
    client.force_login(website_admin)
    response = client.post(
        f"/admin/pages/{about.pk}/edit/",
        {
            "title": "About CalDART",
            "slug": "about",
            "seo_title": "",
            "search_description": "",
            "go_live_at": "",
            "expire_at": "",
            "intro": "Rewritten by the website administrator.",
            "members_only": "",
            "body-count": "0",
            "action-publish": "Publish",
            "comments-TOTAL_FORMS": "0",
            "comments-INITIAL_FORMS": "0",
            "comments-MIN_NUM_FORMS": "0",
            "comments-MAX_NUM_FORMS": "1000",
        },
    )
    assert response.status_code == 302, response.context["form"].errors if response.context else ""

    about.refresh_from_db()
    published = StandardPage.objects.get(pk=about.pk)
    assert published.title == "About CalDART"
    assert published.intro == "Rewritten by the website administrator."
    assert published.live is True


def test_website_admin_can_delete_a_page(client, website_admin, about, site_settings):
    home = site_settings.site.root_page.specific
    doomed = make_standard_page(home, "doomed", "Doomed")
    client.force_login(website_admin)

    response = client.post(f"/admin/pages/{doomed.pk}/delete/")
    assert response.status_code == 302
    assert not StandardPage.objects.filter(pk=doomed.pk).exists()


def test_website_admin_can_open_the_site_settings_form(client, website_admin):
    client.force_login(website_admin)
    response = client.get("/admin/settings/cms/sitesettings/")
    assert response.status_code in (200, 302)
    if response.status_code == 302:  # Wagtail redirects to the per-site URL
        response = client.get(response["Location"])
    assert response.status_code == 200
    assert "theme" in response.content.decode().lower()


# ------------------------------------------------------- raw HTML block
def test_only_website_admins_may_use_the_raw_html_block(
    website_admin, superuser, member, account_admin
):
    assert can_use_raw_html(website_admin) is True
    assert can_use_raw_html(superuser) is True
    assert can_use_raw_html(member) is False
    assert can_use_raw_html(account_admin) is False
    assert can_use_raw_html(None) is False


def test_the_page_form_hides_raw_html_from_users_who_may_not_use_it(
    website_admin, account_admin, about
):
    form_class = StandardPage.get_edit_handler().get_form_class()
    assert issubclass(form_class, RestrictedBlocksPageForm)

    allowed = form_class(instance=about, for_user=website_admin)
    assert "raw_html" in allowed.fields["body"].block.child_blocks
    assert "paragraph" in allowed.fields["body"].block.child_blocks

    denied = form_class(instance=about, for_user=account_admin)
    assert "raw_html" not in denied.fields["body"].block.child_blocks
    assert "paragraph" in denied.fields["body"].block.child_blocks

    # Stripping is per form instance: the shared block definition is untouched.
    assert "raw_html" in StandardPage._meta.get_field("body").stream_block.child_blocks
