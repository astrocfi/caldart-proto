"""``manage.py seed_content`` builds the example site and is safe to repeat."""

from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import call_command
from django.test import Client
from wagtail.models import Page

from apps.cms.models import (
    ContactPage,
    DartIndexPage,
    DartPage,
    HomePage,
    NewsIndexPage,
    NewsPage,
    StandardPage,
)
from apps.members.models import Dart

pytestmark = pytest.mark.django_db


def seed() -> None:
    """Run the ``seed_content`` management command, discarding its stdout."""
    call_command("seed_content", stdout=StringIO())


def page_map() -> dict[str, Page]:
    """Every live page keyed by its URL path, for assertions on the tree."""
    return {page.url_path: page for page in Page.objects.live()}


def test_seed_content_builds_the_documented_tree() -> None:
    """``seed_content`` creates every documented slug, correctly nested."""
    seed()

    slugs = set(Page.objects.live().values_list("slug", flat=True))
    for expected in (
        "about",
        "history",
        "darts",
        "directors",
        "news",
        "join",
        "donate",
        "sponsors",
        "contact",
        "members",
        "members-only",
        "docs-and-links",
    ):
        assert expected in slugs, f"{expected} missing from the seeded tree"

    about = StandardPage.objects.get(slug="about")
    assert about.get_parent().specific_class is HomePage
    assert {p.slug for p in about.get_children()} == {"history", "darts", "directors"}

    members = StandardPage.objects.get(slug="members")
    assert {p.slug for p in members.get_children()} == {"members-only", "docs-and-links"}


def test_seed_content_creates_one_page_per_dart() -> None:
    """``seed_content`` creates one ``DartPage`` for every seeded ``Dart``."""
    seed()
    index = DartIndexPage.objects.get(slug="darts")
    pages = DartPage.objects.child_of(index)

    assert Dart.objects.count() == 16
    assert pages.count() == 16
    assert {p.dart_id for p in pages} == set(Dart.objects.values_list("pk", flat=True))
    assert all(p.leader_name and p.leader_contact for p in pages)

    # Airport identifiers make the slugs, and appear on the index table.
    palo_alto = pages.get(dart__name="Palo Alto")
    assert palo_alto.slug == "pao"
    assert palo_alto.airport_identifier == "PAO"


def test_seed_content_creates_three_news_posts() -> None:
    """``seed_content`` creates three live news posts, one per date, newest first."""
    seed()
    index = NewsIndexPage.objects.get(slug="news")
    posts = NewsPage.objects.child_of(index).order_by("-date")
    assert posts.count() == 3
    assert all(post.live and post.intro for post in posts)
    dates = [post.date for post in posts]
    assert dates == sorted(dates, reverse=True)
    assert len(set(dates)) == 3


def test_seed_content_flags_the_members_area() -> None:
    """``seed_content`` marks exactly the members area pages ``members_only``."""
    seed()
    walled = StandardPage.objects.filter(members_only=True)
    assert {p.slug for p in walled} == {"members", "members-only", "docs-and-links"}


def test_seed_content_home_page_carries_the_concept_of_operations() -> None:
    """``seed_content`` fills in the home page's hero, mission and concept steps."""
    seed()
    home = HomePage.objects.get()
    assert home.hero_heading
    assert home.mission_statement
    assert len(home.concept_of_operations) >= 4
    assert all(block.block_type == "step" for block in home.concept_of_operations)
    assert "501(c)(3)" in home.tax_status
    assert home.primary_cta_url == "/portal/join"


def test_join_page_states_the_dues_and_eligibility_rules(client: Client) -> None:
    """The seeded join page states the dues amounts and eligibility rules."""
    seed()
    page = StandardPage.objects.get(slug="join")
    body = client.get(page.url).content.decode()
    assert "$45" in body
    assert "$650" in body
    assert "medical" in body.lower()
    assert "insurance" in body.lower()
    assert 'href="/portal/join"' in body


def test_donate_page_lists_the_contribution_tiers(client: Client) -> None:
    """The seeded donate page lists every contribution tier, including Platinum."""
    seed()
    page = StandardPage.objects.get(slug="donate")
    body = client.get(page.url).content.decode()
    for tier in ("$20", "$100", "$300", "$1,000", "$3,000", "$10,000"):
        assert tier in body
    assert "Platinum" in body


def test_history_page_covers_2011_to_2022(client: Client) -> None:
    """The seeded history page mentions each of its milestone years."""
    seed()
    page = StandardPage.objects.get(slug="history")
    body = client.get(page.url).content.decode()
    for year in ("2011", "2015", "2017", "2022"):
        assert year in body


def test_seed_content_fills_in_the_site_settings() -> None:
    """``seed_content`` fills in the EIN, mailing address, phone and theme."""
    seed()
    from apps.cms.models import get_site_settings

    settings_obj = get_site_settings()
    assert settings_obj is not None
    assert settings_obj.ein
    assert settings_obj.mailing_address
    assert settings_obj.contact_phone
    assert settings_obj.theme == "sierra"


def test_seed_content_does_not_overwrite_edited_settings() -> None:
    """Running ``seed_content`` again leaves a manually edited setting untouched."""
    seed()
    from apps.cms.models import get_site_settings

    settings_obj = get_site_settings()
    assert settings_obj is not None
    settings_obj.contact_phone = "(415) 555-0100"
    settings_obj.save(update_fields=["contact_phone"])

    seed()
    reloaded = get_site_settings()
    assert reloaded is not None
    assert reloaded.contact_phone == "(415) 555-0100"


def test_every_seeded_page_renders(client: Client) -> None:
    """Every seeded page renders 200, or 403 when it is flagged ``members_only``."""
    seed()
    for page in Page.objects.live().specific():
        url = page.url
        if not url:
            continue
        response = client.get(url)
        expected = 403 if getattr(page, "members_only", False) else 200
        assert response.status_code == expected, f"{url} returned {response.status_code}"


def test_seed_content_runs_twice_cleanly() -> None:
    """Running ``seed_content`` twice leaves the page counts and URL paths unchanged."""
    seed()
    first = {
        "pages": Page.objects.count(),
        "live": Page.objects.live().count(),
        "standard": StandardPage.objects.count(),
        "news": NewsPage.objects.count(),
        "darts": DartPage.objects.count(),
        "contact": ContactPage.objects.count(),
        "paths": sorted(Page.objects.values_list("url_path", flat=True)),
    }

    seed()
    second = {
        "pages": Page.objects.count(),
        "live": Page.objects.live().count(),
        "standard": StandardPage.objects.count(),
        "news": NewsPage.objects.count(),
        "darts": DartPage.objects.count(),
        "contact": ContactPage.objects.count(),
        "paths": sorted(Page.objects.values_list("url_path", flat=True)),
    }

    assert first == second
    assert first["pages"] == 33  # 32 site pages plus the invisible tree root


def test_seed_content_is_safe_after_seed_demo() -> None:
    """``make seed`` runs ``seed_demo`` first; the two must not fight."""
    call_command("seed_demo", stdout=StringIO())
    seed()
    assert DartPage.objects.count() == 16
    assert Page.objects.live().filter(slug="about").exists()
