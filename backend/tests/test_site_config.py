"""``GET /api/v1/site/config`` (PLAN §6.10).

The one endpoint the portal calls before it has a user, so it must answer
anonymously — and it must not leak the members-only page list to callers who
could not open those pages anyway.
"""

from __future__ import annotations

import pytest

from tests.test_cms_pages import (
    expire_membership,
    grant_membership,
    make_news_index,
    make_news_page,
    make_standard_page,
)

pytestmark = pytest.mark.django_db

URL = "/api/v1/site/config"


@pytest.fixture
def site_tree(site_settings):
    """A home page with one menu page and a two-page members-only area."""
    home = site_settings.site.root_page.specific
    make_standard_page(home, "about", "About Us", show_in_menus=True)
    members = make_standard_page(home, "members", "Members", show_in_menus=True, members_only=True)
    make_standard_page(members, "docs-and-links", "Documents and Links", members_only=True)
    index = make_news_index(home, show_in_menus=True)
    make_news_page(index, "briefing", "Members briefing", members_only=True)
    return home


def test_anonymous_callers_get_the_chrome(api_client, site_settings, site_tree):
    site_settings.org_name = "The California DART Network"
    site_settings.contact_email = "info@caldart.example.org"
    site_settings.theme = "pacific"
    site_settings.save()

    response = api_client.get(URL)
    assert response.status_code == 200

    data = response.json()
    assert data["org_name"] == "The California DART Network"
    assert data["contact_email"] == "info@caldart.example.org"
    assert data["theme"] == "pacific"
    assert data["members_pages"] == []


def test_the_nav_matches_the_server_rendered_site(api_client, site_tree):
    data = api_client.get(URL).json()
    titles = [entry["title"] for entry in data["nav"]]
    assert titles == ["About Us", "Members", "News", "Join", "Log in"]
    assert [entry["kind"] for entry in data["nav"][-2:]] == ["portal", "portal"]
    assert data["nav"][-2]["url"] == "/portal/join"


def test_signed_in_callers_see_the_members_entry_in_the_nav(api_client, site_tree, member):
    api_client.force_login(member)
    titles = [entry["title"] for entry in api_client.get(URL).json()["nav"]]
    assert titles[-1] == "Members"


def test_a_current_member_gets_the_members_pages(api_client, site_tree, member, annual_plan):
    grant_membership(member, annual_plan)
    api_client.force_login(member)

    data = api_client.get(URL).json()
    assert {p["title"] for p in data["members_pages"]} == {
        "Members",
        "Documents and Links",
        "Members briefing",
    }
    assert {p["url"] for p in data["members_pages"]} >= {"/members/", "/members/docs-and-links/"}


def test_an_expired_member_gets_no_members_pages(api_client, site_tree, member, annual_plan):
    expire_membership(member, annual_plan)
    api_client.force_login(member)
    assert api_client.get(URL).json()["members_pages"] == []


def test_a_member_who_never_paid_gets_no_members_pages(api_client, site_tree, member):
    api_client.force_login(member)
    assert api_client.get(URL).json()["members_pages"] == []


def test_a_dart_leader_without_a_membership_gets_the_members_pages(api_client, site_tree, leader):
    assert leader.membership_status["status"] == "none"
    api_client.force_login(leader)
    assert api_client.get(URL).json()["members_pages"]


def test_a_superuser_gets_the_members_pages(api_client, site_tree, superuser):
    api_client.force_login(superuser)
    assert api_client.get(URL).json()["members_pages"]


def test_unpublished_members_pages_are_not_listed(api_client, site_tree, leader):
    from apps.cms.models import StandardPage

    StandardPage.objects.get(slug="docs-and-links").unpublish()
    api_client.force_login(leader)

    titles = {p["title"] for p in api_client.get(URL).json()["members_pages"]}
    assert "Documents and Links" not in titles


def test_config_falls_back_when_there_is_no_site_settings_row(api_client, db):
    """The endpoint must answer before ``seed`` has run."""
    from apps.cms.models import SiteSettings

    SiteSettings.objects.all().delete()

    data = api_client.get(URL).json()
    assert data["org_name"] == "CalDART"
    assert data["theme"] == "sierra"
    assert data["contact_email"] == ""
