"""Wagtail page types, blocks, navigation and the members-only wall.

The page builders live in ``tests.factories`` so every ``test_cms_*`` module can
reach them without depending on another test module.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.template.loader import render_to_string
from django.test import Client
from django.utils import timezone

from apps.accounts.models import User
from apps.cms.context_processors import PORTAL_TITLE, build_nav
from apps.cms.models import SiteSettings, StandardPage
from apps.members.models import Dart, MembershipPlan
from tests.factories import (
    expire_membership,
    grant_membership,
    make_contact_page,
    make_dart_index,
    make_dart_page,
    make_news_index,
    make_news_page,
    make_standard_page,
)

pytestmark = pytest.mark.django_db


ALL_BLOCKS = [
    ("heading", {"text": "First section", "level": "h2"}),
    ("paragraph", "<p>Body copy that a reader can actually read.</p>"),
    ("quote", {"quote": "Organize before the disaster.", "attribution": "A volunteer"}),
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
def test_home_page_renders_the_welcome_box(client: Client, site_settings: SiteSettings) -> None:
    """The home page renders its welcome box: lede, mission and tax status copy."""
    home = site_settings.site.root_page.specific
    home.hero_heading = "Welcome to CalDART"
    home.hero_lede = "Relief supplies keep moving."
    home.mission_statement = "<p>Our mission is preparation.</p>"
    home.welcome_body = "<p>Twelve teams around the state.</p>"
    home.tax_status = "<p>CalDART is a 501(c)(3).</p>"
    home.save()
    home.save_revision().publish()
    MembershipPlan.objects.create(name="Annual", slug="annual", price_cents=4500)

    body = client.get("/").content.decode()
    assert "Welcome to CalDART" in body
    assert "Relief supplies keep moving." in body
    assert "Our mission is preparation." in body
    assert "Twelve teams around the state." in body
    assert "CalDART is a 501(c)(3)." in body
    assert 'class="skip-link"' in body
    assert "data-site-nav" in body


def test_home_page_lists_the_missions_flown(client: Client, site_settings: SiteSettings) -> None:
    """Each mission block renders as a row of year and description."""
    home = site_settings.site.root_page.specific
    home.missions_flown = [
        ("mission", {"year": "2023", "text": "Food and medicine to the mountains."}),
        ("mission", {"year": "2021", "text": "Masks to firefighters in Oregon."}),
    ]
    home.save()
    home.save_revision().publish()

    body = client.get("/").content.decode()
    assert 'class="flown"' in body
    assert "2023" in body
    assert "Food and medicine to the mountains." in body
    assert "Masks to firefighters in Oregon." in body


def test_home_page_sidebar_lists_the_next_three_events(
    client: Client, site_settings: SiteSettings
) -> None:
    """The events box shows the three soonest events still ahead, in date order."""
    home = site_settings.site.root_page.specific
    today = timezone.localdate()
    home.upcoming_events = [
        ("event", {"date": today + timedelta(days=60), "title": "Leaders meeting"}),
        ("event", {"date": today - timedelta(days=1), "title": "Yesterday's drill"}),
        ("event", {"date": today + timedelta(days=5), "title": "Ground crew workshop"}),
        ("event", {"date": today + timedelta(days=30), "title": "Radio drill"}),
        ("event", {"date": today + timedelta(days=90), "title": "Spring exercise"}),
    ]
    home.save()
    home.save_revision().publish()

    assert [block.value["title"] for block in home.events_soon] == [
        "Ground crew workshop",
        "Radio drill",
        "Leaders meeting",
    ]

    body = client.get("/").content.decode()
    assert "Upcoming events" in body
    assert "Ground crew workshop" in body
    assert "Yesterday's drill" not in body
    assert "Spring exercise" not in body


def test_home_page_hides_the_events_box_when_every_event_has_passed(
    client: Client, site_settings: SiteSettings
) -> None:
    """With nothing ahead the box disappears rather than standing empty."""
    home = site_settings.site.root_page.specific
    yesterday = timezone.localdate() - timedelta(days=1)
    home.upcoming_events = [("event", {"date": yesterday, "title": "Last year's drill"})]
    home.save()
    home.save_revision().publish()

    assert home.events_soon == []
    assert "Upcoming events" not in client.get("/").content.decode()


def test_home_page_sidebar_prices_every_active_plan(
    client: Client, site_settings: SiteSettings
) -> None:
    """The membership box lists the active plans and offers the join button."""
    MembershipPlan.objects.create(name="Annual", slug="annual", price_cents=4500)
    MembershipPlan.objects.create(name="Life", slug="life", price_cents=65000)
    MembershipPlan.objects.create(name="Retired", slug="retired", price_cents=100, is_active=False)

    body = client.get("/").content.decode()
    assert "$45.00" in body
    assert "$650.00" in body
    assert "Retired" not in body
    assert 'href="/portal/join"' in body


def test_home_page_sidebar_offers_every_active_dart(
    client: Client, site_settings: SiteSettings
) -> None:
    """The team finder offers the active DARTs and posts to the lookup route."""
    Dart.objects.create(name="Reid-Hillview DART", airport_identifier="KRHV")
    Dart.objects.create(name="Retired DART", airport_identifier="XXX", is_active=False)

    body = client.get("/").content.decode()
    assert 'action="/find-dart/"' in body
    assert "Reid-Hillview DART (KRHV)" in body
    assert "Retired DART" not in body


def test_home_page_features_the_three_latest_news_posts(
    client: Client, site_settings: SiteSettings
) -> None:
    """The home page lists only the three most recent public news posts."""
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
    assert "Post 0" in body
    assert "Post 2" in body
    assert "Post 4" not in body


def test_home_page_hides_members_only_posts_from_the_featured_list(
    client: Client, site_settings: SiteSettings
) -> None:
    """A members-only post never appears in the home page's featured news list."""
    home = site_settings.site.root_page.specific
    index = make_news_index(home)
    make_news_page(index, "secret", "Members briefing", days_ago=0, members_only=True)
    make_news_page(index, "public", "Public exercise report", days_ago=1)

    assert [p.title for p in home.featured_news] == ["Public exercise report"]


# --------------------------------------------------------- standard page
def test_standard_page_renders_every_block_type(
    client: Client, site_settings: SiteSettings
) -> None:
    """A standard page renders the intro and every StreamField block type it holds."""
    home = site_settings.site.root_page.specific
    page = make_standard_page(home, "blocks", "Blocks", intro="An intro", body=ALL_BLOCKS)

    response = client.get(page.url)
    assert response.status_code == 200
    body = response.content.decode()

    assert "An intro" in body
    assert '<h2 class="block-heading" id="first-section">First section</h2>' in body
    assert "Body copy that a reader can actually read." in body
    assert 'class="pullquote"' in body
    assert "A volunteer" in body
    assert 'href="/portal/join"' in body
    assert "$45 a year" in body
    assert 'class="columns"' in body
    assert "Left column." in body
    assert "Right column." in body
    assert 'class="block-heading block-heading--sub" id="a-sub-heading"' in body
    assert "<aside data-raw>Raw markup</aside>" in body


def test_standard_page_shows_the_on_this_page_rail_only_when_it_earns_it(
    client: Client, site_settings: SiteSettings
) -> None:
    """The "On this page" rail appears only once a page has more than one heading."""
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


def test_standard_page_lists_its_children_in_the_aside(
    client: Client, site_settings: SiteSettings
) -> None:
    """A standard page with children lists them under an "In this section" heading."""
    home = site_settings.site.root_page.specific
    about = make_standard_page(home, "about", "About Us")
    make_standard_page(about, "history", "History")

    body = client.get(about.url).content.decode()
    assert "In this section" in body
    assert 'href="/about/history/"' in body


# ------------------------------------------------------------------ news
def test_news_index_lists_and_paginates(client: Client, site_settings: SiteSettings) -> None:
    """Ten news posts fill two pages, the newest posts on the first."""
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
    client: Client, site_settings: SiteSettings, member: User, annual_plan: MembershipPlan
) -> None:
    """A members-only news post appears in the index only once the visitor is a member."""
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


def test_news_page_renders(client: Client, site_settings: SiteSettings) -> None:
    """A news post renders its intro, body and a link back to the news index."""
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
def test_dart_index_renders_a_table_of_teams(
    client: Client, site_settings: SiteSettings, dart: Dart
) -> None:
    """The DART index renders a table row with each team's airport, name and leader."""
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


def test_dart_page_renders_its_facts(
    client: Client, site_settings: SiteSettings, dart: Dart
) -> None:
    """A DART page exposes the team's airport identifier, city and leader mail link."""
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
    assert "\u00ab All DARTs" in body


def test_dart_page_leader_href_handles_a_phone_number(
    site_settings: SiteSettings, dart: Dart
) -> None:
    """A leader contact that is a phone number becomes a ``tel:`` link, digits only."""
    home = site_settings.site.root_page.specific
    index = make_dart_index(home)
    page = make_dart_page(index, dart, leader_contact="(650) 555-0143")
    assert page.leader_href == "tel:6505550143"

    page.leader_contact = ""
    assert page.leader_href == ""


# --------------------------------------------------------------- contact
def test_contact_page_pulls_details_from_site_settings(
    client: Client, site_settings: SiteSettings
) -> None:
    """The contact page renders the email, duty number, mailing address and EIN."""
    site_settings.contact_email = "info@caldart.example.org"
    site_settings.duty_phone = "(408) 713-0646"
    site_settings.mailing_address = "PO Box 606\nSan Martin, CA 95046"
    site_settings.ein = "47-0000000"
    site_settings.save()

    home = site_settings.site.root_page.specific
    page = make_contact_page(home, intro="<p>Email is fastest.</p>")

    body = client.get(page.url).content.decode()
    assert "Email is fastest." in body
    assert "mailto:info@caldart.example.org" in body
    assert "(408) 713-0646" in body
    assert "San Martin, CA 95046" in body
    assert "47-0000000" in body


# ---------------------------------------------------- members-only wall
@pytest.fixture
def walled_page(site_settings: SiteSettings) -> StandardPage:
    """A published, members-only standard page holding one secret paragraph."""
    home = site_settings.site.root_page.specific
    return make_standard_page(
        home,
        "members",
        "Members",
        members_only=True,
        intro="Handbooks and forms.",
        body=[("paragraph", "<p>The secret handbook.</p>")],
    )


def test_wall_blocks_anonymous_visitors_with_a_sign_in_cta(
    client: Client, walled_page: StandardPage
) -> None:
    """An anonymous visitor gets the members-only wall with a sign-in and join link."""
    response = client.get(walled_page.url)
    assert response.status_code == 403
    body = response.content.decode()
    assert "The secret handbook." not in body
    assert "Members only" in body
    assert "Sign in" in body
    assert "/portal/login?next=" in body
    assert "/portal/join" in body


def test_wall_offers_renewal_to_an_expired_member(
    client: Client, walled_page: StandardPage, member: User, annual_plan: MembershipPlan
) -> None:
    """A member whose term lapsed sees the wall with a renewal link, not the page."""
    expire_membership(member, annual_plan)
    client.force_login(member)

    response = client.get(walled_page.url)
    assert response.status_code == 403
    body = response.content.decode()
    assert "lapsed" in body
    assert "/portal/renew" in body
    assert "The secret handbook." not in body


def test_wall_offers_joining_to_a_member_who_never_paid(
    client: Client, walled_page: StandardPage, member: User
) -> None:
    """A signed-in user with no membership at all sees the wall with a join link."""
    client.force_login(member)

    response = client.get(walled_page.url)
    assert response.status_code == 403
    body = response.content.decode()
    assert "no current membership" in body
    assert "/portal/join" in body


def test_current_member_reads_the_page(
    client: Client, walled_page: StandardPage, member: User, annual_plan: MembershipPlan
) -> None:
    """A member with a current term reads the walled page's content."""
    grant_membership(member, annual_plan)
    client.force_login(member)

    response = client.get(walled_page.url)
    assert response.status_code == 200
    assert "The secret handbook." in response.content.decode()


def test_dart_leader_without_a_membership_reads_the_page(
    client: Client, walled_page: StandardPage, dart_leader: User
) -> None:
    """A DART leader with no membership of their own still reads the walled page."""
    assert dart_leader.membership_status["status"] == "none"
    client.force_login(dart_leader)

    response = client.get(walled_page.url)
    assert response.status_code == 200
    assert "The secret handbook." in response.content.decode()


def test_superuser_reads_the_page(
    client: Client, walled_page: StandardPage, superuser: User
) -> None:
    """A superuser reads the walled page regardless of membership."""
    client.force_login(superuser)
    assert client.get(walled_page.url).status_code == 200


def test_a_page_that_is_not_walled_is_public(client: Client, site_settings: SiteSettings) -> None:
    """A page with ``members_only`` unset stays reachable by an anonymous visitor."""
    home = site_settings.site.root_page.specific
    page = make_standard_page(home, "open", "Open", body=[("paragraph", "<p>Public.</p>")])
    response = client.get(page.url)
    assert response.status_code == 200
    assert "Public." in response.content.decode()


def test_members_only_news_post_is_walled(
    client: Client, site_settings: SiteSettings, member: User
) -> None:
    """A members-only news post is walled off even for a member with no term."""
    home = site_settings.site.root_page.specific
    index = make_news_index(home)
    post = make_news_page(index, "closed", "Briefing", members_only=True)

    assert client.get(post.url).status_code == 403
    client.force_login(member)
    assert client.get(post.url).status_code == 403


# --------------------------------------------------------------- the nav
def test_nav_lists_menu_pages_then_the_portal_actions(
    client: Client, site_settings: SiteSettings
) -> None:
    """The nav opens with Home, lists the menu pages, then the portal link."""
    home = site_settings.site.root_page.specific
    about = make_standard_page(home, "about", "About Us", show_in_menus=True)
    make_standard_page(about, "history", "History", show_in_menus=True)
    make_standard_page(home, "hidden", "Hidden", show_in_menus=False)

    request = client.get("/").wsgi_request
    entries = build_nav(request)

    assert [e["title"] for e in entries] == ["Home", "About Us", "Log in"]
    assert [e["kind"] for e in entries] == ["page", "page", "portal"]
    assert entries[0]["url"] == "/"
    assert [child["title"] for child in entries[1]["children"]] == ["History"]

    body = client.get("/").content.decode()
    assert 'href="/about/"' in body
    assert 'href="/about/history/"' in body
    assert "Hidden" not in body


def test_a_members_only_page_sits_beside_the_portal_link(
    client: Client, site_settings: SiteSettings
) -> None:
    """A menu page behind the wall is grouped with the portal, not with the sections."""
    home = site_settings.site.root_page.specific
    make_standard_page(home, "about", "About Us", show_in_menus=True)
    make_standard_page(home, "members", "Members Only", show_in_menus=True, members_only=True)

    entries = build_nav(client.get("/").wsgi_request)

    assert [e["title"] for e in entries] == ["Home", "About Us", "Members Only", "Log in"]
    assert [e["kind"] for e in entries] == ["page", "page", "portal", "portal"]


def test_the_nav_greets_a_signed_in_visitor_by_name(
    client: Client, site_settings: SiteSettings, member: User
) -> None:
    """A signed-in reader is greeted in the bar, by first name."""
    member.first_name = "Marta"
    member.save(update_fields=["first_name"])
    client.force_login(member)

    body = client.get("/").content.decode()

    assert "Welcome, Marta" in body


def test_nav_shows_the_portal_instead_of_log_in_when_signed_in(
    client: Client, site_settings: SiteSettings, member: User
) -> None:
    """A signed-in visitor sees the portal link in place of "Log in"."""
    client.force_login(member)
    body = client.get("/").content.decode()
    assert f">{PORTAL_TITLE}</a>" in body
    assert 'href="/portal/"' in body
    assert ">Log in</a>" not in body


def test_nav_marks_the_current_section(client: Client, site_settings: SiteSettings) -> None:
    """The nav marks the top-level ancestor of the current page as current."""
    home = site_settings.site.root_page.specific
    about = make_standard_page(home, "about", "About Us", show_in_menus=True)
    history = make_standard_page(about, "history", "History")

    body = client.get(history.url).content.decode()
    assert 'href="/about/" aria-current="page"' in body


def test_nav_skips_unpublished_pages(client: Client, site_settings: SiteSettings) -> None:
    """An unpublished page never appears in the server-rendered nav or home page."""
    home = site_settings.site.root_page.specific
    draft = make_standard_page(home, "draft", "Draft page", show_in_menus=True)
    draft.unpublish()

    assert "Draft page" not in client.get("/").content.decode()


# ---------------------------------------------------------------- theme
def test_theme_comes_from_site_settings(client: Client, site_settings: SiteSettings) -> None:
    """The rendered page carries the ``data-theme`` attribute from site settings."""
    site_settings.theme = "pacific"
    site_settings.save(update_fields=["theme"])
    assert 'data-theme="pacific"' in client.get("/").content.decode()


def test_theme_preview_is_only_offered_to_administrators(
    client: Client, site_settings: SiteSettings, member: User, website_admin: User
) -> None:
    """Only a website administrator's page carries the theme-preview marker."""
    assert "data-theme-preview" not in client.get("/").content.decode()

    client.force_login(member)
    assert "data-theme-preview" not in client.get("/").content.decode()

    client.force_login(website_admin)
    assert 'data-theme-preview="allowed"' in client.get("/").content.decode()


# ----------------------------------------------------------- error pages
def test_404_page_uses_the_site_chrome(client: Client, site_settings: SiteSettings) -> None:
    """A missing URL renders the 404 page inside the normal site chrome."""
    response = client.get("/no-such-page/")
    assert response.status_code == 404
    body = response.content.decode()
    assert "That page is not here" in body
    assert 'class="skip-link"' in body


def test_500_template_renders_without_a_request_or_context() -> None:
    """Django's 500 handler renders with no request, so no context processor runs."""
    body = render_to_string("500.html")
    assert "Something went wrong at our end" in body
    assert "CalDART" in body
