"""``manage.py seed_content`` -- the example CalDART site.

Builds this page tree::

    Home
      About Us
        History
        DARTs                (index + one page per DART)
        Directors and Officers
      News                   (index + three posts)
      Join CalDART
      Donate
      Sponsors
      Contact Us
      Members                (members only)
        Members Only
        Documents and Links

It also creates the ``Members only`` document collection, which the members-area
copy tells editors to upload handbooks and forms into.

Idempotent: every page is looked up by slug under its parent and updated in
place, so running the command twice leaves exactly the same tree.  Every word of
copy comes from ``seed_content_data``; this module only builds the tree.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta
from pathlib import Path
from typing import Any

from django.core.files.images import ImageFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
from wagtail.images.models import Image
from wagtail.models import Page, Site

from apps.cms.management.commands import seed_content_data as content
from apps.cms.management.commands.seed_content_data import BlockSpec, PageSpec
from apps.cms.models import (
    ContactPage,
    DartIndexPage,
    DartPage,
    EventIndexPage,
    EventPage,
    HomePage,
    NewsIndexPage,
    NewsPage,
    StandardPage,
    ensure_members_only_collection,
)
from apps.cms.permissions import grant_website_admin_permissions
from apps.cms.seed import ensure_site_root
from apps.darts.models import Dart
from apps.members.seed import seed_darts

#: One entry of a page body: the block type, then either rich text or the block's
#: own field values.
type StreamItem = tuple[str, str | dict[str, str]]


# ---------------------------------------------------------------------------
# Page helpers
# ---------------------------------------------------------------------------


def stream(body: Sequence[BlockSpec]) -> list[StreamItem]:
    """The block specs of a page body as the value a ``StreamField`` takes."""
    return [(block.block_type, block.value) for block in body]


def upsert_page[PageT: Page](
    parent: Page,
    model: type[PageT],
    slug: str,
    *,
    title: str,
    show_in_menus: bool = False,
    **fields: Any,
) -> PageT:
    """Create or update ``slug`` under ``parent`` and publish it.

    A page of ``model`` with that slug below ``parent`` is updated in place, and
    one is created when there is none; either way ``title``, ``show_in_menus``, and
    every keyword in ``fields`` are written, a revision is saved and published, and
    the page is returned freshly loaded from the database.  Fields the caller does
    not name keep whatever they held.
    """
    page = model.objects.child_of(parent).filter(slug=slug).first()
    if page is None:
        page = model(title=title, slug=slug, show_in_menus=show_in_menus)
        for key, value in fields.items():
            setattr(page, key, value)
        parent.add_child(instance=page)
    else:
        page.title = title
        page.show_in_menus = show_in_menus
        for key, value in fields.items():
            setattr(page, key, value)
        page.save()
    page.save_revision().publish()
    saved: PageT = model.objects.get(pk=page.pk)
    return saved


def upsert_spec[PageT: Page](
    parent: Page,
    model: type[PageT],
    spec: PageSpec,
    **fields: Any,
) -> PageT:
    """Create or update the page ``spec`` describes below ``parent``.

    The spec's intro, body, and menu flag are written, and any further keyword goes
    through to :func:`upsert_page` for the fields only that page model has.
    ``members_only`` is written only where the spec sets it, because only the page
    models that carry the wall have the field.  Returns the published page.
    """
    wall: dict[str, Any] = {"members_only": True} if spec.members_only else {}
    return upsert_page(
        parent,
        model,
        spec.slug,
        title=spec.title,
        show_in_menus=spec.show_in_menus,
        intro=spec.intro,
        body=stream(spec.body),
        **wall,
        **fields,
    )


# ---------------------------------------------------------------------------
# The tree
# ---------------------------------------------------------------------------


#: The example photograph the home page opens with, kept beside the code so the
#: seeded site has a picture without an editor uploading one.
HERO_IMAGE_PATH = Path(__file__).resolve().parent.parent.parent / "seed_assets" / "airlift-krhv.jpg"
HERO_IMAGE_TITLE = "Food aid at Reid-Hillview"


def seed_hero_image() -> Image:
    """Return the home page's photograph, uploading it on first use.

    Looked up by title, so re-seeding reuses the image already in the library
    rather than filling it with copies.
    """
    existing = Image.objects.filter(title=HERO_IMAGE_TITLE).first()
    if existing is not None:
        return existing
    with HERO_IMAGE_PATH.open("rb") as handle:
        return Image.objects.create(
            title=HERO_IMAGE_TITLE,
            file=ImageFile(handle, name=HERO_IMAGE_PATH.name),
        )


def seed_home(
    home: HomePage,
    *,
    darts_url: str = "/about/darts/",
    contact_url: str = "/contact-us/",
) -> HomePage:
    """Fill in the home page: welcome, mission, events, missions flown, tax note.

    Overwrites those fields every time, attaches the example photograph, dates the
    events from the day it runs so they are always still ahead, publishes a
    revision, and returns the page reloaded from the database.  ``darts_url`` is
    where the "find your DART" button points, and ``contact_url`` both where the
    request for air support goes and what the welcome paragraph links to.
    """
    home.hero_heading = content.HERO_HEADING
    home.hero_lede = content.HERO_LEDE
    home.hero_image = seed_hero_image()
    home.hero_image_caption = content.HERO_IMAGE_CAPTION
    home.urgent_cta_label = content.URGENT_CTA_LABEL
    home.urgent_cta_url = contact_url
    home.primary_cta_label = content.PRIMARY_CTA_LABEL
    home.primary_cta_url = content.PRIMARY_CTA_URL
    home.secondary_cta_label = content.SECONDARY_CTA_LABEL
    home.secondary_cta_url = darts_url
    home.mission_statement = content.MISSION
    home.welcome_body = content.WELCOME_BODY.format(contact=contact_url)
    home.missions_heading = content.MISSIONS_HEADING
    home.missions_flown = [
        ("mission", {"year": year, "text": text}) for year, text in content.MISSIONS_FLOWN
    ]
    home.tax_status = content.TAX_STATUS
    home.save()
    home.save_revision().publish()
    saved: HomePage = HomePage.objects.get(pk=home.pk)
    return saved


def seed_about(home: HomePage) -> StandardPage:
    """Create or update ``/about/``, the About Us page, in the menu."""
    return upsert_spec(home, StandardPage, content.ABOUT)


def seed_how_it_works(about: StandardPage) -> StandardPage:
    """Create or update ``/about/how-it-works/``, in the About Us menu."""
    return upsert_spec(about, StandardPage, content.HOW_IT_WORKS)


def seed_history(about: StandardPage) -> StandardPage:
    """Create or update ``/about/history/``, which is not in the menu."""
    return upsert_spec(about, StandardPage, content.HISTORY)


def dart_page_body(dart: Dart) -> list[StreamItem]:
    """The body of one DART's page: its own summary, then the shared blocks.

    The summary names every airport the team flies from, so a page for a
    two-field team reads as one.
    """
    summary = content.DART_SUMMARY.format(
        name=dart.name,
        where=dart.airport_identifiers,
        county="their",
    )
    return [*stream([content.rich(summary)]), *stream(content.DART_PAGE_BODY)]


def seed_darts_section(about: StandardPage) -> DartIndexPage:
    """Create or update ``/about/darts/`` and one DART page below it per team.

    Each page is slugged by the first airport the team flies from, and carries a
    leader name and a generated example contact address.
    A page whose team no longer exists is deleted, so re-seeding converges on
    exactly one page per DART.  Returns the index page.
    """
    index = upsert_spec(about, DartIndexPage, content.DART_INDEX)

    darts = list(Dart.objects.order_by("name"))
    wanted: set[str] = set()
    for position, dart in enumerate(darts):
        leader = content.DART_LEADERS[position % len(content.DART_LEADERS)]
        mailbox = leader.lower().replace(" ", ".").replace("'", "")
        slug = dart.home_airport.lower() if dart.home_airport else slugify(dart.name)
        wanted.add(slug)
        upsert_page(
            index,
            DartPage,
            slug,
            title=dart.name,
            dart=dart,
            leader_name=leader,
            leader_contact=f"{mailbox}@{content.DART_CONTACT_DOMAIN}",
            body=dart_page_body(dart),
        )

    # A DART that has been renamed or removed leaves a page behind; drop it so
    # re-seeding converges on exactly one page per team.
    for stale in DartPage.objects.child_of(index).exclude(slug__in=wanted):
        stale.delete()

    return index


def seed_directors(about: StandardPage) -> StandardPage:
    """Create or update ``/about/directors/``, the board listing."""
    return upsert_spec(about, StandardPage, content.DIRECTORS)


def seed_news(home: HomePage) -> NewsIndexPage:
    """Create or update ``/news/`` and its example posts, and return the index.

    Each post is dated relative to today, so the newest is always recent.
    """
    index = upsert_page(
        home,
        NewsIndexPage,
        content.NEWS_INDEX.slug,
        title=content.NEWS_INDEX.title,
        show_in_menus=content.NEWS_INDEX.show_in_menus,
        intro=content.NEWS_INDEX.intro,
    )
    today = timezone.localdate()
    for post in content.NEWS_POSTS:
        upsert_page(
            index,
            NewsPage,
            post.page.slug,
            title=post.page.title,
            date=today - timedelta(days=post.days_ago),
            intro=post.page.intro,
            body=stream(post.page.body),
        )
    return index


def seed_events(home: HomePage) -> EventIndexPage:
    """Create or update ``/events/`` and its example events, and return the index.

    Each event is dated relative to today -- four still ahead and one already
    past -- so the calendar always has something on it and the sidebar always
    has something to show.
    """
    index = upsert_page(
        home,
        EventIndexPage,
        content.EVENT_INDEX.slug,
        title=content.EVENT_INDEX.title,
        show_in_menus=content.EVENT_INDEX.show_in_menus,
        intro=content.EVENT_INDEX.intro,
    )
    today = timezone.localdate()
    for event in content.EVENTS:
        upsert_page(
            index,
            EventPage,
            event.page.slug,
            title=event.page.title,
            date=today + timedelta(days=event.days_ahead),
            time=event.time,
            location=event.location,
            intro=event.page.intro,
            body=stream(event.page.body),
        )
    return index


def seed_join(home: HomePage) -> StandardPage:
    """Create or update ``/join/``, the dues and eligibility page, in the menu."""
    return upsert_spec(home, StandardPage, content.JOIN)


def seed_donate(home: HomePage) -> StandardPage:
    """Create or update ``/donate/``, the contribution page, in the menu."""
    return upsert_spec(home, StandardPage, content.DONATE)


def seed_sponsors(about: StandardPage) -> StandardPage:
    """Create or update the sponsors page under About Us, in the About menu."""
    return upsert_spec(about, StandardPage, content.SPONSORS)


def seed_contact(home: HomePage) -> ContactPage:
    """Create or update ``/contact/``, the contact page, in the menu."""
    return upsert_spec(home, ContactPage, content.CONTACT)


def seed_members_area(home: HomePage) -> StandardPage:
    """Create or update ``/members/`` and the two pages below it.

    All three are flagged members-only, so a reader without members-only access is
    answered with the wall.  The ``Members only`` document collection is created
    first, because the copy tells editors to upload into it.  Returns the top page.
    """
    # The pages tell editors to upload handbooks and forms into this collection,
    # so the collection has to exist before anyone reads that instruction.
    ensure_members_only_collection()

    members = upsert_spec(home, StandardPage, content.MEMBERS)
    upsert_spec(members, StandardPage, content.MEMBERS_ONLY)
    upsert_spec(members, StandardPage, content.DOCS_AND_LINKS)
    return members


def seed_settings(site: Site) -> None:
    """Fill in the site settings the example content refers to.

    The duty officer number, mailing address, EIN, donate URL and the two social
    links are written where the field is empty, and where it still holds one of
    the placeholder values an earlier version of the seed wrote, so anything an
    administrator chose survives but a placeholder nobody chose does not.  The
    settings row is created if it is missing.
    """
    from apps.cms.models import SiteSettings

    settings_obj, _ = SiteSettings.objects.get_or_create(site=site)
    changed = [
        field
        for field in content.SITE_SETTINGS
        if not getattr(settings_obj, field)
        or getattr(settings_obj, field) in content.SUPERSEDED_SETTINGS.get(field, ())
    ]
    for field in changed:
        setattr(settings_obj, field, content.SITE_SETTINGS[field])
    if changed:
        settings_obj.save(update_fields=changed)


class Command(BaseCommand):
    """``manage.py seed_content``, which builds the example site."""

    help = "Create the CalDART example website content (idempotent)."

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        """Build the whole example tree in one transaction, then report its size.

        Takes no arguments.  Seeds the DARTs first, because the DART pages link to
        them, then every page from the home page down, then the site settings and
        the ``website_admin`` Wagtail permissions.  Writes one progress line per
        step and a final count of the pages below the home page.  Running it again
        updates the same pages rather than adding more.
        """
        self.stdout.write("Seeding site content:")

        seed_darts()
        site = ensure_site_root()
        home = HomePage.objects.get(pk=site.root_page_id)

        about = seed_about(home)
        seed_how_it_works(about)
        seed_history(about)
        darts = seed_darts_section(about)
        seed_directors(about)
        seed_news(home)
        seed_events(home)
        seed_join(home)
        seed_donate(home)
        seed_sponsors(about)
        contact = seed_contact(home)
        seed_members_area(home)
        seed_home(
            home,
            darts_url=darts.url or "/about/darts/",
            contact_url=contact.url or "/contact-us/",
        )
        seed_settings(site)

        grant_website_admin_permissions(stdout=self.stdout)

        total = Page.objects.descendant_of(home, inclusive=True).count()
        self.stdout.write(self.style.SUCCESS(f"Example site ready: {total} pages."))
