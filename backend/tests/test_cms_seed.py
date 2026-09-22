"""The CMS seed's site-root repair.

``apps.cms.seed`` guarantees the chrome the rest of the system reads: a
published ``HomePage``, a default ``Site`` pointing at it, and a ``SiteSettings``
row carrying a theme.  It has to reach that state from any of the states a
database can be in -- empty, half-built, or pointed at the wrong page -- without
undoing an administrator's edits, and running it twice must change nothing.
"""

from __future__ import annotations

from io import StringIO

import pytest
from django.core.management.base import OutputWrapper
from wagtail.models import Page, Site

from apps.cms.models import DEFAULT_THEME, HomePage, SiteSettings, StandardPage
from apps.cms.seed import ensure_site_root, run

pytestmark = pytest.mark.django_db


@pytest.fixture
def empty_tree() -> Page:
    """Wagtail's root page with no home page and no site under it."""
    Site.objects.all().delete()
    HomePage.objects.all().delete()
    return Page.get_first_root_node()


def test_an_empty_tree_gets_a_published_home_page(empty_tree: Page) -> None:
    """With no home page at all, the seed creates one and publishes it."""
    ensure_site_root()

    home = HomePage.objects.get()
    assert home.title == "Home"
    assert home.slug == "home"
    assert home.live is True


def test_an_empty_tree_gets_a_default_site_on_localhost(empty_tree: Page) -> None:
    """The site the seed creates is the default one, on ``localhost:80``."""
    site = ensure_site_root()

    assert (site.hostname, site.port) == ("localhost", 80)
    assert site.is_default_site is True
    assert site.root_page_id == HomePage.objects.get().pk


def test_the_home_page_carries_the_hero_copy(empty_tree: Page) -> None:
    """The created home page arrives with its hero heading and its join call to action."""
    ensure_site_root()

    home = HomePage.objects.get()
    assert home.hero_heading == "Volunteer air transportation when California needs it"
    assert home.primary_cta_label == "Join CalDART"
    assert home.primary_cta_url == "/portal/join"


def test_a_site_pointed_at_the_wrong_page_is_repaired(home_page: HomePage) -> None:
    """A default site rooted at some other page is pointed back at the home page."""
    stray = StandardPage(title="Stray", slug="stray", intro="")
    home_page.add_child(instance=stray)
    site = Site.objects.get(is_default_site=True)
    site.root_page = stray
    site.save(update_fields=["root_page"])

    repaired = ensure_site_root()

    assert repaired.root_page_id == home_page.pk
    assert Site.objects.count() == 1


def test_a_site_already_pointed_at_the_home_page_is_left_alone(home_page: HomePage) -> None:
    """A correct site is returned unchanged rather than rewritten."""
    before = Site.objects.get(is_default_site=True)

    after = ensure_site_root()

    assert after.pk == before.pk
    assert after.root_page_id == home_page.pk


def test_repairing_twice_leaves_one_home_page(empty_tree: Page) -> None:
    """Two runs against the same tree build one home page and one site, not two."""
    ensure_site_root()
    ensure_site_root()

    assert HomePage.objects.count() == 1
    assert Site.objects.count() == 1


# --------------------------------------------------------------------------
# run(): the settings row and the line it reports
# --------------------------------------------------------------------------
def test_run_creates_the_settings_row_with_the_default_theme(empty_tree: Page) -> None:
    """A tree with no settings row gets one carrying the default theme."""
    ctx = run({})

    settings_row = SiteSettings.objects.get()
    assert settings_row.theme == DEFAULT_THEME
    assert ctx["site_settings"] == settings_row


def test_run_fills_in_a_blank_theme(home_page: HomePage) -> None:
    """A settings row whose theme was emptied is filled back in with the default."""
    site = Site.objects.get(is_default_site=True)
    SiteSettings.objects.create(site=site, theme="")

    run({})

    assert SiteSettings.objects.get().theme == DEFAULT_THEME


def test_run_keeps_an_administrators_theme(home_page: HomePage) -> None:
    """A theme an administrator chose survives a re-seed."""
    site = Site.objects.get(is_default_site=True)
    SiteSettings.objects.create(site=site, theme="night")

    run({})

    assert SiteSettings.objects.get().theme == "night"


def test_run_records_the_site_and_settings_in_the_context(empty_tree: Page) -> None:
    """``run`` returns the context it was given, with the site and its settings added."""
    ctx = run({"seeded": ["accounts"]})

    assert ctx["seeded"] == ["accounts"]
    assert ctx["site"] == Site.objects.get(is_default_site=True)


def test_run_reports_the_root_page_it_created(empty_tree: Page) -> None:
    """The first run names the root page it made and says the settings were created."""
    out = StringIO()

    run({}, OutputWrapper(out))

    assert out.getvalue() == "  cms: site root 'Home' and settings created\n"


def test_run_reports_settings_that_were_already_there(empty_tree: Page) -> None:
    """A second run names the same root page and says the settings were present."""
    run({})
    out = StringIO()

    run({}, OutputWrapper(out))

    assert out.getvalue() == "  cms: site root 'Home' and settings present\n"
