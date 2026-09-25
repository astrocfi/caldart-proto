"""Wagtail content models for the public site.

The page tree is deliberately small: a home page, a general-purpose standard
page, a news index plus posts, a DART index plus one page per team, and a
contact page.  Anything an editor needs beyond that they build with the
StreamField blocks in :mod:`apps.cms.blocks`.

``MembersOnlyMixin`` is the members-only wall: a page flagged ``members_only``
is served to anyone whose ``can_access_members_content`` is true and answered
with ``cms/members_only_wall.html`` and HTTP 403 for everybody else.  Wagtail's
own page privacy still works on top of it.  The same wall guards downloads from
the ``Members only`` document collection, through the hook in
:mod:`apps.cms.wagtail_hooks`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Literal, TypedDict

from django.contrib.auth.models import AnonymousUser
from django.db import models
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.template.response import TemplateResponse
from django.utils import timezone
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.contrib.settings.models import BaseSiteSetting, register_setting
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Collection, Page, PageManager
from wagtail.query import PageQuerySet
from wagtail.search import index

from apps.accounts.models import User
from apps.cms.blocks import (
    RICH_TEXT_FEATURES,
    ContentStreamBlock,
    MissionStreamBlock,
    stream_headings,
)
from apps.cms.forms import RestrictedBlocksPageForm
from apps.darts.models import Dart
from apps.members.models import MembershipPlan, MembershipState
from apps.members.services import MembershipStatusDict

if TYPE_CHECKING:
    from rest_framework.request import Request

    #: Either kind of request the site is served from: Django's own, or the
    #: Django one wrapped by Django REST Framework for the portal's API.
    type RequestLike = HttpRequest | Request

#: Themes shipped in ``frontend/src/styles/themes/``.
THEME_CHOICES: tuple[tuple[str, str], ...] = (
    ("duty", "Duty (default, blue and red)"),
    ("sierra", "Sierra (warm paper)"),
    ("pacific", "Pacific (cool paper)"),
    ("night", "Night (dark)"),
    ("squadron", "Squadron (logo blue on white)"),
    ("flight-deck", "Flight deck (logo blue, dark)"),
    ("contrail", "Contrail (logo blue, sky paper)"),
    ("sectional", "Sectional (aeronautical chart)"),
    ("tarmac", "Tarmac (concrete and asphalt)"),
    ("coastal", "Coastal (fog and ocean teal)"),
    ("slate", "Slate (cool corporate)"),
    ("meridian", "Meridian (high-contrast civic)"),
    ("monterey-night", "Monterey night (charcoal dark)"),
    ("granite", "Granite (near-monochrome)"),
)
DEFAULT_THEME = "duty"

#: Theme slugs, for validating ``?theme=`` previews and the settings choice.
THEME_SLUGS: tuple[str, ...] = tuple(slug for slug, _ in THEME_CHOICES)

#: How many news posts the home page features.
FEATURED_NEWS_COUNT = 3

#: How many upcoming events the home page's sidebar lists.
UPCOMING_EVENTS_COUNT = 3

#: How many posts a news index page shows before paginating.
NEWS_PAGE_SIZE = 8

#: How many events an event index page shows before paginating.
EVENT_PAGE_SIZE = 20

#: A body needs at least this many H2 headings before the "on this page" rail
#: earns its place.
ON_THIS_PAGE_MIN_HEADINGS = 3

#: Documents in this collection, and in every collection beneath it, are served
#: only to readers who pass ``user_can_access_members_content``.
MEMBERS_ONLY_COLLECTION_NAME = "Members only"

#: Which call to action the members-only wall offers the reader.
WallState = Literal["anonymous", "expired", "none"]


class MembersWallContext(TypedDict):
    """The extra template context the members-only wall renders from."""

    wall_state: WallState
    membership: MembershipStatusDict | None


def user_can_access_members_content(user: User | AnonymousUser | None) -> bool:
    """``True`` when ``user`` may read members-only pages.

    ``None`` and anonymous visitors are always refused.  A signed-in account is
    admitted exactly when its ``can_access_members_content`` is true: a current
    membership, a staff role, or a superuser.
    """
    if user is None or not user.is_authenticated:
        return False
    return user.can_access_members_content


def members_wall_state(user: User | AnonymousUser | None) -> WallState:
    """Which call to action the wall shows ``user``.

    ``anonymous`` for ``None`` and for a visitor who is not signed in, so the wall
    invites them to sign in; ``expired`` for a signed-in account whose membership
    status is ``expired``, so it invites a renewal; ``none`` for every other
    signed-in account, whatever its status, so it invites them to join.
    """
    if user is None or not user.is_authenticated:
        return "anonymous"
    status = user.membership_status["status"]
    return "expired" if status == MembershipState.EXPIRED else "none"


def members_wall_context(user: User | AnonymousUser | None) -> MembersWallContext:
    """The wall's own context for ``user``: ``wall_state`` and ``membership``.

    ``membership`` is the signed-in account's membership status dictionary, and
    ``None`` for ``None`` and for an anonymous visitor.
    """
    if user is None or not user.is_authenticated:
        return {"wall_state": members_wall_state(user), "membership": None}
    return {"wall_state": members_wall_state(user), "membership": user.membership_status}


def ensure_members_only_collection() -> Collection:
    """Return the ``Members only`` collection, creating it under the root if absent.

    Safe to call repeatedly: a second call returns the collection the first one
    created.
    """
    existing = Collection.objects.filter(name=MEMBERS_ONLY_COLLECTION_NAME).order_by("path")
    first = existing.first()
    if first is not None:
        return first
    return Collection.get_first_root_node().add_child(name=MEMBERS_ONLY_COLLECTION_NAME)


def collection_is_members_only(collection: Collection | None) -> bool:
    """``True`` for the ``Members only`` collection and every collection beneath it.

    ``None`` -- a document with no collection -- is public.
    """
    if collection is None:
        return False
    # A descendant's materialized path starts with its ancestor's, so one prefix
    # test covers the collection itself and the whole subtree under it.
    paths = Collection.objects.filter(name=MEMBERS_ONLY_COLLECTION_NAME).values_list(
        "path", flat=True
    )
    return any(collection.path.startswith(path) for path in paths)


class BasePage(Page):
    """Shared behavior: the restricted-block form and a body-headings helper."""

    base_form_class = RestrictedBlocksPageForm

    class Meta:
        abstract = True

    @property
    def body_headings(self) -> list[dict[str, str]]:
        """H2 headings in ``body``, for the "on this page" rail.

        Each entry is ``{"text", "anchor"}``.  A page type with no ``body`` field,
        and a body with no H2 heading block, both give an empty list.
        """
        return stream_headings(getattr(self, "body", None))

    @property
    def show_on_this_page(self) -> bool:
        """``True`` once the body carries at least three H2 headings."""
        return len(self.body_headings) >= ON_THIS_PAGE_MIN_HEADINGS


if TYPE_CHECKING:
    # Wagtail ships no type information, so ``Page`` is untyped and a mixin that
    # calls into it has nothing to check against.  The mixin is only ever combined
    # with ``BasePage``, and these are the two page methods it reaches through.
    class _MembersOnlyBase(models.Model):
        """Typing stand-in for the page class the mixin is combined with."""

        class Meta:
            abstract = True

        def get_context(
            self, request: HttpRequest, *args: Any, **kwargs: Any
        ) -> dict[str, Any]: ...

        def serve(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse: ...

else:
    _MembersOnlyBase = models.Model


class MembersOnlyMixin(_MembersOnlyBase):
    """Adds ``members_only`` and the wall that enforces it."""

    #: Wagtail's own manager, which it ships without type information; naming it
    #: keeps the page classes below resolvable as Django models.
    objects: ClassVar[PageManager]

    members_only = models.BooleanField(
        default=False,
        verbose_name="members only",
        help_text=(
            "Serve this page only to signed-in members with a current membership "
            "(or to DART leaders and administrators). Everyone else sees the "
            "join / renew / sign-in wall."
        ),
    )

    members_only_panels = [FieldPanel("members_only")]

    class Meta:
        abstract = True

    def serve(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        """Render the page, or the wall when the reader may not read it.

        A page whose ``members_only`` is false is served exactly as Wagtail would
        serve it.  A members-only page is served the same way to a reader who
        passes ``user_can_access_members_content``, and answered with the wall and
        HTTP 403 for everybody else.
        """
        if self.members_only and not user_can_access_members_content(request.user):
            return self.serve_members_only_wall(request)
        return super().serve(request, *args, **kwargs)

    def serve_members_only_wall(self, request: HttpRequest) -> TemplateResponse:
        """The wall itself: the page chrome, a reason, and one clear next step.

        Renders ``cms/members_only_wall.html`` with HTTP 403, from the page's own
        context plus ``wall_state`` and ``membership``.  Sets ``request.is_preview``
        when Wagtail has not, since the page templates read it.
        """
        # Wagtail decorates the request with ``is_preview`` when it serves a page,
        # and ships no type information for that.
        request.is_preview = getattr(request, "is_preview", False)  # type: ignore[attr-defined]
        context = self.get_context(request)
        context.update(members_wall_context(request.user))
        return TemplateResponse(request, "cms/members_only_wall.html", context, status=403)


class HomePage(BasePage):
    """The site root: welcome box, featured news, missions flown, and the sidebar."""

    hero_heading = models.CharField(max_length=200, blank=True)
    hero_lede = models.TextField(blank=True)
    hero_image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    hero_image_caption = models.CharField(max_length=200, blank=True)
    urgent_cta_label = models.CharField(
        max_length=60,
        blank=True,
        default="Request air support",
        help_text="The first button, shown in the alert color.",
    )
    urgent_cta_url = models.CharField(max_length=200, blank=True)
    primary_cta_label = models.CharField(max_length=60, blank=True, default="Join CalDART")
    primary_cta_url = models.CharField(max_length=200, blank=True, default="/portal/join")
    secondary_cta_label = models.CharField(max_length=60, blank=True)
    secondary_cta_url = models.CharField(max_length=200, blank=True)

    mission_statement = RichTextField(
        blank=True,
        features=RICH_TEXT_FEATURES,
        help_text="The mission statement, set off inside the welcome box.",
    )
    welcome_body = RichTextField(
        blank=True,
        features=RICH_TEXT_FEATURES,
        help_text="The paragraphs under the mission statement.",
    )
    missions_heading = models.CharField(max_length=200, blank=True, default="Missions flown")
    missions_flown = StreamField(
        MissionStreamBlock(),
        blank=True,
        help_text="What CalDART has carried, newest first.",
    )
    tax_status = RichTextField(
        blank=True,
        features=["bold", "italic", "link"],
        help_text="The 501(c)(3) note shown in the membership box.",
    )

    content_panels = [
        *Page.content_panels,
        MultiFieldPanel(
            [
                FieldPanel("hero_heading"),
                FieldPanel("hero_lede"),
                FieldPanel("hero_image"),
                FieldPanel("hero_image_caption"),
                FieldPanel("urgent_cta_label"),
                FieldPanel("urgent_cta_url"),
                FieldPanel("primary_cta_label"),
                FieldPanel("primary_cta_url"),
                FieldPanel("secondary_cta_label"),
                FieldPanel("secondary_cta_url"),
            ],
            heading="Hero",
        ),
        FieldPanel("mission_statement"),
        FieldPanel("welcome_body"),
        MultiFieldPanel(
            [FieldPanel("missions_heading"), FieldPanel("missions_flown")],
            heading="Missions flown",
        ),
        FieldPanel("tax_status"),
    ]

    search_fields = [
        *Page.search_fields,
        index.SearchField("hero_heading"),
        index.SearchField("hero_lede"),
        index.SearchField("mission_statement"),
    ]

    template = "cms/home_page.html"
    parent_page_types = ["wagtailcore.Page"]

    class Meta:
        verbose_name = "home page"

    def __str__(self) -> str:
        """The page title, which is how Wagtail lists and chooses the page."""
        return str(self.title)

    @property
    def featured_news(self) -> list[NewsPage]:
        """The three most recent live public news posts, newest first.

        Members-only posts are left out whoever is reading, because the home page
        is public.  Ties on the post date are broken by the newer primary key.
        """
        return list(
            NewsPage.objects.live()
            .public()
            .filter(members_only=False)
            .order_by("-date", "-pk")[:FEATURED_NEWS_COUNT]
        )

    @property
    def news_index(self) -> NewsIndexPage | None:
        """The live news index the featured posts link to, or ``None`` if unpublished."""
        index_page: NewsIndexPage | None = NewsIndexPage.objects.live().first()
        return index_page

    @property
    def events_soon(self) -> list[EventPage]:
        """The next few live public events, soonest first.

        An event dated today still counts: it has not happened until the day is
        over.  Anything earlier is left out, and so is anything unpublished or
        private, because the home page is public.  No events at all gives an
        empty list, so the sidebar box disappears rather than standing empty.
        """
        return list(EventPage.objects.upcoming()[:UPCOMING_EVENTS_COUNT])

    @property
    def event_index(self) -> EventIndexPage | None:
        """The live event calendar the sidebar links to, or ``None`` if unpublished."""
        index_page: EventIndexPage | None = EventIndexPage.objects.live().first()
        return index_page

    @property
    def dart_index(self) -> DartIndexPage | None:
        """The live DART directory the sidebar's team finder posts to, or ``None``."""
        index_page: DartIndexPage | None = DartIndexPage.objects.live().first()
        return index_page

    @property
    def darts(self) -> list[Dart]:
        """Active DARTs in display order, for the sidebar's team finder."""
        return list(Dart.objects.filter(is_active=True))

    @property
    def plans(self) -> list[MembershipPlan]:
        """Active membership plans in display order, for the sidebar's price list."""
        return list(MembershipPlan.objects.filter(is_active=True))

    def get_context(self, request: HttpRequest, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Wagtail's page context plus the news, DART and membership the sidebar reads."""
        context: dict[str, Any] = super().get_context(request, *args, **kwargs)
        context["featured_news"] = self.featured_news
        context["events_soon"] = self.events_soon
        context["event_index"] = self.event_index
        context["news_index"] = self.news_index
        context["dart_index"] = self.dart_index
        context["darts"] = self.darts
        context["plans"] = self.plans
        return context


class StandardPage(MembersOnlyMixin, BasePage):
    """A general content page: intro plus a StreamField body."""

    intro = models.TextField(blank=True, help_text="One or two sentences under the title.")
    body = StreamField(ContentStreamBlock(), blank=True)

    content_panels = [
        *Page.content_panels,
        FieldPanel("intro"),
        FieldPanel("body"),
        MultiFieldPanel(MembersOnlyMixin.members_only_panels, heading="Access"),
    ]

    search_fields = [
        *Page.search_fields,
        index.SearchField("intro"),
        index.SearchField("body"),
        index.FilterField("members_only"),
    ]

    template = "cms/standard_page.html"

    class Meta:
        verbose_name = "standard page"

    def __str__(self) -> str:
        """The page title, which is how Wagtail lists and chooses the page."""
        return str(self.title)


class NewsIndexPage(BasePage):
    """Lists the news posts below it, newest first, paginated."""

    intro = models.TextField(blank=True)

    content_panels = [*Page.content_panels, FieldPanel("intro")]
    search_fields = [*Page.search_fields, index.SearchField("intro")]

    template = "cms/news_index_page.html"
    subpage_types = ["cms.NewsPage"]

    class Meta:
        verbose_name = "news index"
        verbose_name_plural = "news indexes"

    def posts(self, request: HttpRequest) -> QuerySet[NewsPage]:
        """Live child posts, newest first, less any the visitor cannot read.

        A members-only post is included only for a reader who passes
        ``user_can_access_members_content``; a request that carries no user at all
        is treated as anonymous.  Ties on the post date are broken by the newer
        primary key.
        """
        queryset: QuerySet[NewsPage] = (
            NewsPage.objects.child_of(self).live().public().order_by("-date", "-pk")
        )
        if not user_can_access_members_content(getattr(request, "user", None)):
            queryset = queryset.filter(members_only=False)
        return queryset

    def get_context(self, request: HttpRequest, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Wagtail's page context plus ``paginator`` and one page of ``posts``.

        Eight posts fill a page.  ``?page=`` selects which one; anything that is
        not a page number falls back to the first page, and a number past the end
        to the last, because Django's paginator is asked for the page with
        ``get_page``.
        """
        from django.core.paginator import Paginator

        context: dict[str, Any] = super().get_context(request, *args, **kwargs)
        paginator = Paginator(self.posts(request), NEWS_PAGE_SIZE)
        page_number = request.GET.get("page") or 1
        context["paginator"] = paginator
        context["posts"] = paginator.get_page(page_number)
        return context


class NewsPage(MembersOnlyMixin, BasePage):
    """One news post."""

    date = models.DateField("post date")
    intro = models.TextField(blank=True)
    image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    body = StreamField(ContentStreamBlock(), blank=True)

    content_panels = [
        *Page.content_panels,
        FieldPanel("date"),
        FieldPanel("intro"),
        FieldPanel("image"),
        FieldPanel("body"),
        MultiFieldPanel(MembersOnlyMixin.members_only_panels, heading="Access"),
    ]

    search_fields = [
        *Page.search_fields,
        index.SearchField("intro"),
        index.SearchField("body"),
        index.FilterField("date"),
        index.FilterField("members_only"),
    ]

    template = "cms/news_page.html"
    parent_page_types = ["cms.NewsIndexPage"]
    subpage_types: list[str] = []

    class Meta:
        verbose_name = "news post"
        ordering = ["-date"]

    def __str__(self) -> str:
        """The page title, which is how Wagtail lists and chooses the page."""
        return str(self.title)


class EventPageManager(PageManager):
    """Adds the two orderings every event screen wants."""

    def upcoming(self) -> PageQuerySet[EventPage]:
        """Live public events from today on, soonest first.

        An event dated today is still upcoming: it has not happened until the
        day is over.  Ties on the date are broken by the earlier primary key, so
        two events on one day keep the order they were created in.
        """
        events: PageQuerySet[EventPage] = self.get_queryset()
        return events.live().public().filter(date__gte=timezone.localdate()).order_by("date", "pk")

    def past(self) -> PageQuerySet[EventPage]:
        """Live public events before today, most recent first."""
        events: PageQuerySet[EventPage] = self.get_queryset()
        return events.live().public().filter(date__lt=timezone.localdate()).order_by("-date", "-pk")


class EventIndexPage(BasePage):
    """The calendar: what is coming up, and what has already happened."""

    intro = models.TextField(blank=True)

    content_panels = [*Page.content_panels, FieldPanel("intro")]
    search_fields = [*Page.search_fields, index.SearchField("intro")]

    template = "cms/event_index_page.html"
    subpage_types = ["cms.EventPage"]

    class Meta:
        verbose_name = "event index"
        verbose_name_plural = "event indexes"

    def upcoming(self) -> PageQuerySet[EventPage]:
        """This calendar's own live events from today on, soonest first."""
        return EventPage.objects.upcoming().child_of(self)

    def past(self) -> PageQuerySet[EventPage]:
        """This calendar's own live events before today, most recent first."""
        return EventPage.objects.past().child_of(self)

    def get_context(self, request: HttpRequest, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Wagtail's page context plus ``upcoming`` and one page of ``past`` events.

        Everything still ahead is listed in full -- a calendar that hid the
        fourth event would be no use -- and what has already happened is
        paginated, ``EVENT_PAGE_SIZE`` to a page, with ``?page=`` choosing
        which.  Anything that is not a page number falls back to the first page
        and a number past the end to the last, because Django's paginator is
        asked with ``get_page``.
        """
        from django.core.paginator import Paginator

        context: dict[str, Any] = super().get_context(request, *args, **kwargs)
        paginator = Paginator(self.past(), EVENT_PAGE_SIZE)
        context["upcoming"] = self.upcoming()
        context["paginator"] = paginator
        context["past"] = paginator.get_page(request.GET.get("page") or 1)
        return context


class EventPage(BasePage):
    """One dated event: an exercise, a workshop, a drill, or a meeting."""

    date = models.DateField("event date")
    time = models.CharField(max_length=60, blank=True, help_text="When it runs, e.g. 9 am to 1 pm.")
    location = models.CharField(
        max_length=160, blank=True, help_text="Airport and town, or who it is for."
    )
    intro = models.TextField(blank=True, help_text="One line, shown in the calendar.")
    body = StreamField(ContentStreamBlock(), blank=True)

    content_panels = [
        *Page.content_panels,
        FieldPanel("date"),
        FieldPanel("time"),
        FieldPanel("location"),
        FieldPanel("intro"),
        FieldPanel("body"),
    ]

    search_fields = [
        *Page.search_fields,
        index.SearchField("intro"),
        index.SearchField("location"),
        index.SearchField("body"),
        index.FilterField("date"),
    ]

    template = "cms/event_page.html"
    parent_page_types = ["cms.EventIndexPage"]
    subpage_types: list[str] = []

    objects: EventPageManager = EventPageManager()

    class Meta:
        verbose_name = "event"

    def __str__(self) -> str:
        """The page title, which is how Wagtail lists and chooses the page."""
        return str(self.title)

    @property
    def is_past(self) -> bool:
        """Whether the event's day is over."""
        return bool(self.date < timezone.localdate())

    @property
    def when_and_where(self) -> str:
        """The time and the place as one line, with whichever of them is set.

        ``"9 am to 1 pm"`` and ``"Reid-Hillview (KRHV)"`` read as
        ``"Reid-Hillview (KRHV), 9 am to 1 pm"``; either alone reads as itself,
        and neither gives an empty string.
        """
        return ", ".join(part for part in (self.location, self.time) if part)


class DartIndexPage(BasePage):
    """The DART directory: one table row per team, linking to its page."""

    intro = models.TextField(blank=True)
    body = StreamField(ContentStreamBlock(), blank=True)

    content_panels = [*Page.content_panels, FieldPanel("intro"), FieldPanel("body")]
    search_fields = [*Page.search_fields, index.SearchField("intro")]

    template = "cms/dart_index_page.html"
    subpage_types = ["cms.DartPage"]

    class Meta:
        verbose_name = "DART index"
        verbose_name_plural = "DART indexes"

    @property
    def dart_pages(self) -> QuerySet[DartPage]:
        """The live public DART pages below this index, by page title.

        The title is the team's name, so the directory reads alphabetically,
        which is how somebody looks for their own field.
        """
        pages: QuerySet[DartPage] = (
            DartPage.objects.child_of(self).live().public().select_related("dart").order_by("title")
        )
        return pages

    def get_context(self, request: HttpRequest, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Wagtail's page context plus ``dart_pages``, the rows of the directory."""
        context: dict[str, Any] = super().get_context(request, *args, **kwargs)
        context["dart_pages"] = list(self.dart_pages)
        return context


class DartPage(BasePage):
    """One local Disaster Airlift Response Team."""

    dart = models.ForeignKey(
        "darts.Dart",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pages",
        help_text="Links this page to the DART members can join.",
    )
    leader_name = models.CharField(max_length=120, blank=True)
    leader_contact = models.CharField(
        max_length=200, blank=True, help_text="Email address or phone number."
    )
    body = StreamField(ContentStreamBlock(), blank=True)

    content_panels = [
        *Page.content_panels,
        FieldPanel("dart"),
        MultiFieldPanel(
            [FieldPanel("leader_name"), FieldPanel("leader_contact")],
            heading="DART leader",
        ),
        FieldPanel("body"),
    ]

    search_fields = [
        *Page.search_fields,
        index.SearchField("leader_name"),
        index.SearchField("body"),
    ]

    template = "cms/dart_page.html"
    parent_page_types = ["cms.DartIndexPage"]
    subpage_types: list[str] = []

    class Meta:
        verbose_name = "DART page"

    @property
    def airport_identifiers(self) -> str:
        """The linked DART's airport identifier, or an empty string when unlinked."""
        return self.dart.airport_identifiers if self.dart else ""

    @property
    def leader_href(self) -> str:
        """``mailto:``/``tel:`` for the leader contact, or an empty string."""
        contact = self.leader_contact.strip()
        if not contact:
            return ""
        if "@" in contact:
            return f"mailto:{contact}"
        digits = "".join(c for c in contact if c.isdigit() or c == "+")
        return f"tel:{digits}" if digits else ""


class ContactPage(BasePage):
    """Contact details, pulled from Site Settings so they are edited once."""

    intro = RichTextField(blank=True, features=RICH_TEXT_FEATURES)
    body = StreamField(ContentStreamBlock(), blank=True)

    content_panels = [*Page.content_panels, FieldPanel("intro"), FieldPanel("body")]
    search_fields = [*Page.search_fields, index.SearchField("intro")]

    template = "cms/contact_page.html"

    class Meta:
        verbose_name = "contact page"


# Allowed children.  Declared after the classes so the names resolve.
HomePage.subpage_types = [
    "cms.StandardPage",
    "cms.NewsIndexPage",
    "cms.DartIndexPage",
    "cms.ContactPage",
]
StandardPage.subpage_types = [
    "cms.StandardPage",
    "cms.NewsIndexPage",
    "cms.DartIndexPage",
    "cms.ContactPage",
]
ContactPage.subpage_types = []


@register_setting
class SiteSettings(BaseSiteSetting):
    """Organization details and the active theme."""

    org_name = models.CharField(max_length=120, default="The California DART Network")
    tagline = models.CharField(
        max_length=200, blank=True, default="Volunteer disaster air transportation for California"
    )
    contact_email = models.EmailField(blank=True, default="info@caldart.example.org")
    duty_phone = models.CharField(
        "duty officer phone",
        max_length=32,
        blank=True,
        help_text="Shown in the masthead as the number to call about a mission.",
    )
    mailing_address = models.TextField(blank=True)
    ein = models.CharField("EIN", max_length=20, blank=True)
    donate_url = models.CharField(max_length=200, blank=True)
    facebook_url = models.URLField(blank=True)
    twitter_url = models.URLField(blank=True)
    theme = models.CharField(max_length=20, choices=THEME_CHOICES, default=DEFAULT_THEME)
    footer_text = models.TextField(
        blank=True,
        default="CalDART is a 501(c)(3) non-profit. Contributions are tax deductible.",
    )

    panels = [
        MultiFieldPanel(
            [
                FieldPanel("org_name"),
                FieldPanel("tagline"),
                FieldPanel("ein"),
            ],
            heading="Organization",
        ),
        MultiFieldPanel(
            [
                FieldPanel("contact_email"),
                FieldPanel("duty_phone"),
                FieldPanel("mailing_address"),
            ],
            heading="Contact",
        ),
        MultiFieldPanel(
            [
                FieldPanel("donate_url"),
                FieldPanel("facebook_url"),
                FieldPanel("twitter_url"),
            ],
            heading="Links",
        ),
        MultiFieldPanel(
            [
                FieldPanel("theme"),
                FieldPanel("footer_text"),
            ],
            heading="Appearance",
        ),
    ]

    class Meta:
        verbose_name = "site settings"

    def __str__(self) -> str:
        """``Settings for <site>``, naming the Wagtail site the row belongs to."""
        return f"Settings for {self.site}"

    @classmethod
    def get_theme(cls, request: RequestLike | None = None) -> str:
        """The active theme slug for ``request``'s site, one of ``THEME_SLUGS``.

        Falls back to ``duty`` when the theme is blank and when there is no
        settings row yet.  Without a request, the default site's theme is used.
        """
        settings_obj = get_site_settings(request)
        if settings_obj is None:
            return DEFAULT_THEME
        return settings_obj.theme or DEFAULT_THEME


def get_site_settings(request: RequestLike | None = None) -> SiteSettings | None:
    """The ``SiteSettings`` row for ``request``'s site, or ``None``.

    Read-only on purpose: ``SiteSettings.for_request`` would create the row,
    and a GET should not write.  Returns ``None`` before ``migrate`` has set up
    the site, which is the only case the callers have to handle.
    """
    from wagtail.models import Site

    if request is not None:
        site = Site.find_for_request(request)
    else:
        site = Site.objects.filter(is_default_site=True).first()
    if site is None:
        return None
    settings_obj: SiteSettings | None = SiteSettings.objects.filter(site=site).first()
    return settings_obj


def members_only_pages(request: RequestLike | None = None) -> list[StandardPage | NewsPage]:
    """Live pages flagged ``members_only``, for the portal's quick links.

    Standard pages come first, then news posts, each group in tree order.  Scoped
    to the requested site when there is one, so a second Wagtail site would never
    leak its members' area into another site's config.  Draft and privacy-
    restricted pages are left out; the list is empty when there are none.
    """
    from wagtail.models import Site

    site = Site.find_for_request(request) if request is not None else None
    root = site.root_page if site else None

    pages: list[StandardPage | NewsPage] = []
    for model in (StandardPage, NewsPage):
        queryset = model.objects.live().public().filter(members_only=True)
        if root is not None:
            queryset = queryset.descendant_of(root, inclusive=True)
        pages.extend(queryset.order_by("path"))
    return pages
