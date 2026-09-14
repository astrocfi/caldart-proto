"""Wagtail page types, blocks, navigation and the members-only wall.

The helpers at the top build small page trees; the other ``test_cms_*`` modules
import them rather than repeating the boilerplate.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.template.loader import render_to_string
from django.utils import timezone

from apps.cms.models import (
    ContactPage,
    DartIndexPage,
    DartPage,
    NewsIndexPage,
    NewsPage,
    StandardPage,
)
from apps.members.models import MembershipStatusChoices
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------- helpers
def publish(parent, page):
    """Add ``page`` under ``parent``, publish it, and return it fresh."""
    parent.add_child(instance=page)
    page.save_revision().publish()
    return type(page).objects.get(pk=page.pk)


def make_standard_page(parent, slug="a-page", title="A page", **fields):
    return publish(parent, StandardPage(title=title, slug=slug, **fields))


def make_news_index(parent, slug="news", title="News", **fields):
    return publish(parent, NewsIndexPage(title=title, slug=slug, **fields))


def make_news_page(parent, slug, title, *, days_ago=0, **fields):
    fields.setdefault("date", timezone.localdate() - timedelta(days=days_ago))
    return publish(parent, NewsPage(title=title, slug=slug, **fields))


def make_dart_index(parent, slug="darts", title="DARTs", **fields):
    return publish(parent, DartIndexPage(title=title, slug=slug, **fields))


def make_dart_page(parent, dart, **fields):
    fields.setdefault("leader_name", "Helen Marchetti")
    fields.setdefault("leader_contact", "helen@example.org")
    slug = dart.airport_identifier.lower() or "team"
    return publish(parent, DartPage(title=dart.name, slug=slug, dart=dart, **fields))


def make_contact_page(parent, slug="contact", title="Contact Us", **fields):
    return publish(parent, ContactPage(title=title, slug=slug, **fields))


def grant_membership(user, plan, *, days_left=200):
    """Give ``user`` a term that is current for ``days_left`` more days."""
    today = timezone.localdate()
    return MembershipFactory(
        user=user,
        plan=plan,
        starts_on=today - timedelta(days=30),
        ends_on=today + timedelta(days=days_left),
    )


def expire_membership(user, plan, *, days_ago=30):
    today = timezone.localdate()
    return MembershipFactory(
        user=user,
        plan=plan,
        starts_on=today - timedelta(days=days_ago + 365),
        ends_on=today - timedelta(days=days_ago),
        status=MembershipStatusChoices.EXPIRED,
    )


ALL_BLOCKS = [
    ("heading", {"text": "First section", "level": "h2"}),
    ("paragraph", "<p>Body copy that a reader can actually read.</p>"),
    ("quote", {"quote": "Organise before the disaster.", "attribution": "A volunteer"}),
    ("cta", {"label": "Join now", "url": "/portal/join", "style": "primary", "note": "$45 a year"}),
    ("heading", {"text": "Second section", "level": "h2"}),
    (
        "two_columns",
        {
            "left": [("paragraph", "<p>Left column.</p>")],
            "right": [("paragraph", "<p>Right column.</p>")],
        },
    ),
    ("heading", {"text": "Third section", "level": "h2"}),
    ("heading", {"text": "A sub heading", "level": "h3"}),
    ("raw_html", "<aside data-raw>Raw markup</aside>"),
]


# ------------------------------------------------------------- home page
def test_home_page_renders_the_editorial_layout(client, site_settings):
    home = site_settings.site.root_page.specific
    home.hero_heading = "Volunteer air transportation"
    home.hero_lede = "Relief supplies keep moving."
    home.mission_statement = "<p>Our mission is preparation.</p>"
    home.concept_heading = "How an activation works"
    home.concept_of_operations = [
        ("step", {"title": "Teams form", "text": "Around an airport."}),
        ("step", {"title": "Members stay current", "text": "All year round."}),
    ]
    home.tax_status = "<p>CalDART is a 501(c)(3).</p>"
    home.save()
    home.save_revision().publish()

    body = client.get("/").content.decode()
    assert "Volunteer air transportation" in body
    assert "Relief supplies keep moving." in body
    assert "Our mission is preparation." in body
    assert 'class="steps"' in body
    assert "Teams form" in body
    assert "CalDART is a 501(c)(3)." in body
    assert 'class="skip-link"' in body
    assert "data-site-nav" in body


def test_home_page_features_the_three_latest_news_posts(client, site_settings):
    home = site_settings.site.root_page.specific
    index = make_news_index(home)
    for position in range(5):
        make_news_page(
            index,
            slug=f"post-{position}",
            title=f"Post {position}",
            days_ago=position,
            intro=f"Intro {position}",
        )

    assert [p.title for p in home.featured_news] == ["Post 0", "Post 1", "Post 2"]

    body = client.get("/").content.decode()
    assert "Post 0" in body and "Post 2" in body
    assert "Post 4" not in body


def test_home_page_hides_members_only_posts_from_the_featured_list(client, site_settings):
    home = site_settings.site.root_page.specific
    index = make_news_index(home)
    make_news_page(index, "secret", "Members briefing", days_ago=0, members_only=True)
    make_news_page(index, "public", "Public exercise report", days_ago=1)

    assert [p.title for p in home.featured_news] == ["Public exercise report"]


# --------------------------------------------------------- standard page
def test_standard_page_renders_every_block_type(client, site_settings):
    home = site_settings.site.root_page.specific
    page = make_standard_page(home, "blocks", "Blocks", intro="An intro", body=ALL_BLOCKS)

    response = client.get(page.url)
    assert response.status_code == 200
    body = response.content.decode()

    assert "An intro" in body
    assert '<h2 class="block-heading" id="first-section">First section</h2>' in body
    assert "Body copy that a reader can actually read." in body
    assert 'class="pullquote"' in body and "A volunteer" in body
    assert 'href="/portal/join"' in body and "$45 a year" in body
    assert 'class="columns"' in body and "Left column." in body and "Right column." in body
    assert 'class="block-heading block-heading--sub" id="a-sub-heading"' in body
    assert "<aside data-raw>Raw markup</aside>" in body


def test_standard_page_shows_the_on_this_page_rail_only_when_it_earns_it(client, site_settings):
    home = site_settings.site.root_page.specific
    long_page = make_standard_page(home, "long", "Long", body=ALL_BLOCKS)
    short_page = make_standard_page(
        home,
        "short",
        "Short",
        body=[("heading", {"text": "Only one", "level": "h2"})],
    )

    assert long_page.show_on_this_page is True
    assert [h["anchor"] for h in long_page.body_headings] == [
        "first-section",
        "second-section",
        "third-section",
    ]
    assert short_page.show_on_this_page is False

    assert "On this page" in client.get(long_page.url).content.decode()
    assert "On this page" not in client.get(short_page.url).content.decode()


def test_standard_page_lists_its_children_in_the_aside(client, site_settings):
    home = site_settings.site.root_page.specific
    about = make_standard_page(home, "about", "About Us")
    make_standard_page(about, "history", "History")

    body = client.get(about.url).content.decode()
    assert "In this section" in body
    assert 'href="/about/history/"' in body


# ------------------------------------------------------------------ news
def test_news_index_lists_and_paginates(client, site_settings):
    home = site_settings.site.root_page.specific
    index = make_news_index(home, intro="What we have been doing.")
    for position in range(10):
        make_news_page(index, f"post-{position}", f"Post {position}", days_ago=position)

    first = client.get(index.url)
    assert first.status_code == 200
    first_body = first.content.decode()
    assert "What we have been doing." in first_body
    assert "Post 0" in first_body
    assert "Post 9" not in first_body
    assert "Page 1 of 2" in first_body

    second_body = client.get(index.url, {"page": 2}).content.decode()
    assert "Post 9" in second_body


def test_news_index_hides_members_only_posts_from_visitors(
    client, site_settings, member, annual_plan
):
    home = site_settings.site.root_page.specific
    index = make_news_index(home)
    make_news_page(index, "open", "Open post", days_ago=1)
    make_news_page(index, "closed", "Members briefing", days_ago=0, members_only=True)

    anonymous_body = client.get(index.url).content.decode()
    assert "Open post" in anonymous_body
    assert "Members briefing" not in anonymous_body

    grant_membership(member, annual_plan)
    client.force_login(member)
    member_body = client.get(index.url).content.decode()
    assert "Members briefing" in member_body


def test_news_page_renders(client, site_settings):
    home = site_settings.site.root_page.specific
    index = make_news_index(home)
    post = make_news_page(
        index,
        "exercise",
        "Statewide exercise",
        days_ago=3,
        intro="Twenty-eight aircraft took part.",
        body=[("paragraph", "<p>The scenario assumed two closed highways.</p>")],
    )

    body = client.get(post.url).content.decode()
    assert "Statewide exercise" in body
    assert "Twenty-eight aircraft took part." in body
    assert "The scenario assumed two closed highways." in body
    assert 'href="/news/"' in body


# ------------------------------------------------------------------ dart
def test_dart_index_renders_a_table_of_teams(client, site_settings, dart):
    home = site_settings.site.root_page.specific
    about = make_standard_page(home, "about", "About Us")
    index = make_dart_index(about, intro="Find the team nearest you.")
    make_dart_page(index, dart)

    response = client.get(index.url)
    assert response.status_code == 200
    body = response.content.decode()
    assert '<th scope="col">Airport</th>' in body
    assert "Palo Alto" in body
    assert "PAO" in body
    assert "Helen Marchetti" in body


def test_dart_page_renders_its_facts(client, site_settings, dart):
    home = site_settings.site.root_page.specific
    about = make_standard_page(home, "about", "About Us")
    index = make_dart_index(about)
    page = make_dart_page(index, dart, body=[("paragraph", "<p>We meet monthly.</p>")])

    assert page.airport_identifier == "PAO"
    assert page.city == "Palo Alto"
    assert page.leader_href == "mailto:helen@example.org"

    body = client.get(page.url).content.decode()
    assert "We meet monthly." in body
    assert "mailto:helen@example.org" in body
    assert "← All DARTs" in body


def test_dart_page_leader_href_handles_a_phone_number(site_settings, dart):
    home = site_settings.site.root_page.specific
    index = make_dart_index(home)
    page = make_dart_page(index, dart, leader_contact="(650) 555-0143")
    assert page.leader_href == "tel:6505550143"

    page.leader_contact = ""
    assert page.leader_href == ""


# --------------------------------------------------------------- contact
def test_contact_page_pulls_details_from_site_settings(client, site_settings):
    site_settings.contact_email = "info@caldart.example.org"
    site_settings.contact_phone = "(650) 555-0143"
    site_settings.mailing_address = "PO Box 1180\nSan Carlos, CA 94070"
    site_settings.ein = "47-0000000"
    site_settings.save()

    home = site_settings.site.root_page.specific
    page = make_contact_page(home, intro="<p>Email is fastest.</p>")

    body = client.get(page.url).content.decode()
    assert "Email is fastest." in body
    assert "mailto:info@caldart.example.org" in body
    assert "(650) 555-0143" in body
    assert "San Carlos, CA 94070" in body
    assert "47-0000000" in body


# ---------------------------------------------------- members-only wall
@pytest.fixture
def walled_page(site_settings):
    home = site_settings.site.root_page.specific
    return make_standard_page(
        home,
        "members",
        "Members",
        members_only=True,
        intro="Handbooks and forms.",
        body=[("paragraph", "<p>The secret handbook.</p>")],
    )


def test_wall_blocks_anonymous_visitors_with_a_sign_in_cta(client, walled_page):
    response = client.get(walled_page.url)
    assert response.status_code == 403
    body = response.content.decode()
    assert "The secret handbook." not in body
    assert "Members only" in body
    assert "Sign in" in body
    assert "/portal/login?next=" in body
    assert "/portal/join" in body


def test_wall_offers_renewal_to_an_expired_member(client, walled_page, member, annual_plan):
    expire_membership(member, annual_plan)
    client.force_login(member)

    response = client.get(walled_page.url)
    assert response.status_code == 403
    body = response.content.decode()
    assert "lapsed" in body
    assert "/portal/renew" in body
    assert "The secret handbook." not in body


def test_wall_offers_joining_to_a_member_who_never_paid(client, walled_page, member):
    client.force_login(member)

    response = client.get(walled_page.url)
    assert response.status_code == 403
    body = response.content.decode()
    assert "no current membership" in body
    assert "/portal/join" in body


def test_current_member_reads_the_page(client, walled_page, member, annual_plan):
    grant_membership(member, annual_plan)
    client.force_login(member)

    response = client.get(walled_page.url)
    assert response.status_code == 200
    assert "The secret handbook." in response.content.decode()


def test_dart_leader_without_a_membership_reads_the_page(client, walled_page, leader):
    assert leader.membership_status["status"] == "none"
    client.force_login(leader)

    response = client.get(walled_page.url)
    assert response.status_code == 200
    assert "The secret handbook." in response.content.decode()


def test_superuser_reads_the_page(client, walled_page, superuser):
    client.force_login(superuser)
    assert client.get(walled_page.url).status_code == 200


def test_a_page_that_is_not_walled_is_public(client, site_settings):
    home = site_settings.site.root_page.specific
    page = make_standard_page(home, "open", "Open", body=[("paragraph", "<p>Public.</p>")])
    response = client.get(page.url)
    assert response.status_code == 200
    assert "Public." in response.content.decode()


def test_members_only_news_post_is_walled(client, site_settings, member):
    home = site_settings.site.root_page.specific
    index = make_news_index(home)
    post = make_news_page(index, "closed", "Briefing", members_only=True)

    assert client.get(post.url).status_code == 403
    client.force_login(member)
    assert client.get(post.url).status_code == 403


# --------------------------------------------------------------- the nav
def test_nav_lists_menu_pages_then_the_portal_actions(client, site_settings):
    home = site_settings.site.root_page.specific
    make_standard_page(home, "about", "About Us", show_in_menus=True)
    make_standard_page(home, "hidden", "Hidden", show_in_menus=False)

    from apps.cms.context_processors import build_nav

    request = client.get("/").wsgi_request
    entries = build_nav(request)

    assert [e["title"] for e in entries] == ["About Us", "Join", "Log in"]
    assert [e["kind"] for e in entries] == ["page", "portal", "portal"]
    assert entries[1]["url"] == "/portal/join"

    body = client.get("/").content.decode()
    assert 'href="/about/"' in body
    assert "Hidden" not in body


def test_nav_shows_members_instead_of_log_in_when_signed_in(client, site_settings, member):
    client.force_login(member)
    body = client.get("/").content.decode()
    assert ">Members</a>" in body
    assert 'href="/portal/"' in body
    assert ">Log in</a>" not in body


def test_nav_marks_the_current_section(client, site_settings):
    home = site_settings.site.root_page.specific
    about = make_standard_page(home, "about", "About Us", show_in_menus=True)
    history = make_standard_page(about, "history", "History")

    body = client.get(history.url).content.decode()
    assert 'href="/about/" aria-current="page"' in body


def test_nav_skips_unpublished_pages(client, site_settings):
    home = site_settings.site.root_page.specific
    draft = make_standard_page(home, "draft", "Draft page", show_in_menus=True)
    draft.unpublish()

    assert "Draft page" not in client.get("/").content.decode()


# ---------------------------------------------------------------- theme
def test_theme_comes_from_site_settings(client, site_settings):
    site_settings.theme = "pacific"
    site_settings.save(update_fields=["theme"])
    assert 'data-theme="pacific"' in client.get("/").content.decode()


def test_theme_preview_is_only_offered_to_administrators(
    client, site_settings, member, website_admin
):
    assert "data-theme-preview" not in client.get("/").content.decode()

    client.force_login(member)
    assert "data-theme-preview" not in client.get("/").content.decode()

    client.force_login(website_admin)
    assert 'data-theme-preview="allowed"' in client.get("/").content.decode()


# ----------------------------------------------------------- error pages
def test_404_page_uses_the_site_chrome(client, site_settings):
    response = client.get("/no-such-page/")
    assert response.status_code == 404
    body = response.content.decode()
    assert "That page is not here" in body
    assert 'class="skip-link"' in body


def test_500_template_renders_without_a_request_or_context():
    """Django's 500 handler renders with no request, so no context processor runs."""
    body = render_to_string("500.html")
    assert "Something went wrong at our end" in body
    assert "CalDART" in body
