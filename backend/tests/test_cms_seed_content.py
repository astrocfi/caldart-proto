"""``manage.py seed_content`` builds the example site and is safe to repeat."""

from __future__ import annotations

from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.test import Client
from django.utils import timezone
from rest_framework.test import APIClient
from wagtail.models import Page

from apps.cms.management.commands import seed_content_data as content

#: Every test here runs `seed_content`, which builds the whole example site.
from apps.cms.models import (
    ContactPage,
    DartIndexPage,
    DartPage,
    HomePage,
    NewsIndexPage,
    NewsPage,
    StandardPage,
    get_site_settings,
)
from apps.members.models import Dart
from tests.factories import MemberProfileFactory, MembershipFactory

pytestmark = [pytest.mark.django_db, pytest.mark.slow]


def seed() -> None:
    """Run the ``seed_content`` management command, discarding its stdout."""
    call_command("seed_content", stdout=StringIO())


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
    assert [p.slug for p in pages if p.leader_name == ""] == []
    assert [p.slug for p in pages if p.leader_contact == ""] == []

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
    assert [post.slug for post in posts if not post.live] == []
    assert [post.slug for post in posts if post.intro == ""] == []
    dates = [post.date for post in posts]
    assert dates == sorted(dates, reverse=True)
    assert len(set(dates)) == 3


def test_seed_content_flags_the_members_area() -> None:
    """``seed_content`` marks exactly the members area pages ``members_only``."""
    seed()
    walled = StandardPage.objects.filter(members_only=True)
    assert {p.slug for p in walled} == {"members", "members-only", "docs-and-links"}


def test_seed_content_home_page_carries_the_missions_flown() -> None:
    """``seed_content`` fills in the home page's welcome, mission and flown missions."""
    seed()
    home = HomePage.objects.get()
    assert home.hero_heading == content.HERO_HEADING
    assert home.mission_statement == content.MISSION
    assert len(home.missions_flown) == len(content.MISSIONS_FLOWN)
    assert [block.block_type for block in home.missions_flown] == [
        "mission" for _mission in content.MISSIONS_FLOWN
    ]
    assert "501(c)(3)" in home.tax_status
    assert home.primary_cta_url == "/portal/join"


def test_seed_content_dates_every_event_ahead_of_today() -> None:
    """``seed_content`` seeds the calendar so nothing in it has already happened."""
    seed()
    home = HomePage.objects.get()
    today = timezone.localdate()

    assert len(home.upcoming_events) == len(content.UPCOMING_EVENTS)
    assert all(block.value["date"] > today for block in home.upcoming_events)


def test_seed_content_gives_the_home_page_its_photograph() -> None:
    """``seed_content`` attaches the example photograph and its caption."""
    seed()
    home = HomePage.objects.get()
    assert home.hero_image is not None
    assert home.hero_image_caption == content.HERO_IMAGE_CAPTION


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
    """``seed_content`` fills in the EIN, mailing address, duty phone and theme."""
    seed()
    settings_obj = get_site_settings()
    assert settings_obj is not None
    assert settings_obj.ein
    assert settings_obj.mailing_address
    assert settings_obj.duty_phone
    assert settings_obj.theme == "duty"


def test_seed_content_does_not_overwrite_edited_settings() -> None:
    """Running ``seed_content`` again leaves a manually edited setting untouched."""
    seed()
    settings_obj = get_site_settings()
    assert settings_obj is not None
    settings_obj.duty_phone = "(415) 555-0100"
    settings_obj.save(update_fields=["duty_phone"])

    seed()
    reloaded = get_site_settings()
    assert reloaded is not None
    assert reloaded.duty_phone == "(415) 555-0100"


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


# ------------------------------------------------------------ the copy module
STANDARD_PAGE_SPECS = (
    content.ABOUT,
    content.HISTORY,
    content.DIRECTORS,
    content.JOIN,
    content.DONATE,
    content.SPONSORS,
    content.MEMBERS,
    content.MEMBERS_ONLY,
    content.DOCS_AND_LINKS,
)


def test_every_standard_page_is_seeded_from_its_spec() -> None:
    """The standard pages are exactly the specs, each with its title and intro."""
    seed()

    seeded = {page.slug: (page.title, page.intro) for page in StandardPage.objects.all()}

    assert seeded == {spec.slug: (spec.title, spec.intro) for spec in STANDARD_PAGE_SPECS}


def test_a_page_body_is_the_block_specs_its_page_spec_lists() -> None:
    """The join page's body holds the join spec's blocks, in the order given."""
    seed()

    page = StandardPage.objects.get(slug=content.JOIN.slug)

    assert [block.block_type for block in page.body] == [
        spec.block_type for spec in content.JOIN.body
    ]


def test_definition_list_renders_one_bold_item_per_row() -> None:
    """Each ``(term, text)`` pair becomes a list item with the term in bold."""
    rows = [("2011", "The first exercise."), ("2013", "Two more airports.")]

    assert content.definition_list(rows) == (
        "<ul><li><b>2011</b> \u2014 The first exercise.</li>"
        "<li><b>2013</b> \u2014 Two more airports.</li></ul>"
    )


def test_definition_list_of_no_rows_is_an_empty_list() -> None:
    """No rows give an empty ``<ul>`` rather than any item markup."""
    assert content.definition_list([]) == "<ul></ul>"


def test_seed_content_publishes_members_only_pages(api_client: APIClient) -> None:
    """Once the seed has run, a member's site config names at least one members-only page.

    The same config carries the organization name the seed sets, so a member reads back
    a configured site rather than an empty one.
    """
    call_command("seed_content", stdout=StringIO(), verbosity=0)

    member = MemberProfileFactory().user
    MembershipFactory(user=member, ends_on=timezone.localdate() + timedelta(days=30))
    api_client.force_login(member)

    config = api_client.get("/api/v1/site/config")

    assert config.status_code == 200
    assert config.json()["org_name"] != ""
    assert len(config.json()["members_pages"]) > 0
