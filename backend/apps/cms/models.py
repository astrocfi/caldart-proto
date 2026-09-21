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

from django.db import models
from django.template.response import TemplateResponse
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.contrib.settings.models import BaseSiteSetting, register_setting
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Collection, Page
from wagtail.search import index

from apps.cms.blocks import (
    RICH_TEXT_FEATURES,
    ConceptStreamBlock,
    ContentStreamBlock,
    stream_headings,
)
from apps.cms.forms import RestrictedBlocksPageForm
from apps.members.models import MembershipState

#: Themes shipped in ``frontend/src/styles/themes/``.
THEME_CHOICES: tuple[tuple[str, str], ...] = (
    ("sierra", "Sierra (default, warm paper)"),
    ("pacific", "Pacific (cool paper)"),
    ("night", "Night (dark)"),
)
DEFAULT_THEME = "sierra"

#: Theme slugs, for validating ``?theme=`` previews and the settings choice.
THEME_SLUGS: tuple[str, ...] = tuple(slug for slug, _ in THEME_CHOICES)

#: How many news posts the home page features.
FEATURED_NEWS_COUNT = 3

#: How many posts a news index page shows before paginating.
NEWS_PAGE_SIZE = 8

#: A body needs at least this many H2 headings before the "on this page" rail
#: earns its place.
ON_THIS_PAGE_MIN_HEADINGS = 3

#: Documents in this collection, and in every collection beneath it, are served
#: only to readers who pass ``user_can_access_members_content``.
MEMBERS_ONLY_COLLECTION_NAME = "Members only"


def user_can_access_members_content(user) -> bool:
    """``True`` when ``user`` may read members-only pages."""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    return bool(getattr(user, "can_access_members_content", False))


def members_wall_state(user) -> str:
    """Which call to action the wall shows: ``anonymous``/``expired``/``none``."""
    if user is None or not getattr(user, "is_authenticated", False):
        return "anonymous"
    status = user.membership_status["status"]
    return "expired" if status == MembershipState.EXPIRED else "none"


def members_wall_context(user) -> dict:
    """The wall's own context for ``user``: ``wall_state`` and ``membership``.

    ``membership`` is the signed-in account's membership status dictionary, and
    ``None`` for an anonymous visitor.
    """
    is_authenticated = getattr(user, "is_authenticated", False)
    return {
        "wall_state": members_wall_state(user),
        "membership": user.membership_status if is_authenticated else None,
    }


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


def collection_is_members_only(collection) -> bool:
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
    def body_headings(self) -> list[dict]:
        """H2 headings in ``body``, for the "on this page" rail."""
        return stream_headings(getattr(self, "body", None))

    @property
    def show_on_this_page(self) -> bool:
        return len(self.body_headings) >= ON_THIS_PAGE_MIN_HEADINGS


class MembersOnlyMixin(models.Model):
    """Adds ``members_only`` and the wall that enforces it."""

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

    def serve(self, request, *args, **kwargs):
        if self.members_only and not user_can_access_members_content(request.user):
            return self.serve_members_only_wall(request)
        return super().serve(request, *args, **kwargs)

    def serve_members_only_wall(self, request) -> TemplateResponse:
        """The wall itself: the page chrome, a reason, and one clear next step."""
        request.is_preview = getattr(request, "is_preview", False)
        context = self.get_context(request)
        context.update(members_wall_context(request.user))
        return TemplateResponse(request, "cms/members_only_wall.html", context, status=403)


class HomePage(BasePage):
    """The site root: hero, mission, concept of operations, tax status, news."""

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
    primary_cta_label = models.CharField(max_length=60, blank=True, default="Join CalDART")
    primary_cta_url = models.CharField(max_length=200, blank=True, default="/portal/join")
    secondary_cta_label = models.CharField(max_length=60, blank=True)
    secondary_cta_url = models.CharField(max_length=200, blank=True)

    mission_statement = RichTextField(
        blank=True,
        features=RICH_TEXT_FEATURES,
        help_text="Shown as a pull-quote directly under the hero.",
    )
    concept_heading = models.CharField(
        max_length=200, blank=True, default="How an activation works"
    )
    concept_of_operations = StreamField(
        ConceptStreamBlock(),
        blank=True,
        help_text="Numbered steps describing how CalDART operates.",
    )
    tax_status = RichTextField(
        blank=True,
        features=["bold", "italic", "link"],
        help_text="The 501(c)(3) note shown beside the concept of operations.",
    )

    content_panels = [
        *Page.content_panels,
        MultiFieldPanel(
            [
                FieldPanel("hero_heading"),
                FieldPanel("hero_lede"),
                FieldPanel("hero_image"),
                FieldPanel("hero_image_caption"),
                FieldPanel("primary_cta_label"),
                FieldPanel("primary_cta_url"),
                FieldPanel("secondary_cta_label"),
                FieldPanel("secondary_cta_url"),
            ],
            heading="Hero",
        ),
        FieldPanel("mission_statement"),
        MultiFieldPanel(
            [FieldPanel("concept_heading"), FieldPanel("concept_of_operations")],
            heading="Concept of operations",
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
        return self.title

    @property
    def featured_news(self):
        """The three most recent live news posts."""
        return list(
            NewsPage.objects.live()
            .public()
            .filter(members_only=False)
            .order_by("-date", "-pk")[:FEATURED_NEWS_COUNT]
        )

    @property
    def news_index(self):
        return NewsIndexPage.objects.live().first()

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        context["featured_news"] = self.featured_news
        context["news_index"] = self.news_index
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
        return self.title


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

    def posts(self, request):
        """Live child posts, less any members-only post the visitor cannot read."""
        queryset = NewsPage.objects.child_of(self).live().public().order_by("-date", "-pk")
        if not user_can_access_members_content(getattr(request, "user", None)):
            queryset = queryset.filter(members_only=False)
        return queryset

    def get_context(self, request, *args, **kwargs):
        from django.core.paginator import Paginator

        context = super().get_context(request, *args, **kwargs)
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
        return self.title


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
    def dart_pages(self):
        return (
            DartPage.objects.child_of(self)
            .live()
            .public()
            .select_related("dart")
            .order_by("dart__sort_order", "title")
        )

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        context["dart_pages"] = list(self.dart_pages)
        return context


class DartPage(BasePage):
    """One local Disaster Airlift Response Team."""

    dart = models.ForeignKey(
        "members.Dart",
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
    def airport_identifier(self) -> str:
        return self.dart.airport_identifier if self.dart else ""

    @property
    def city(self) -> str:
        return self.dart.city if self.dart else ""

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
    contact_phone = models.CharField(max_length=32, blank=True)
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
                FieldPanel("contact_phone"),
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
        return f"Settings for {self.site}"

    @classmethod
    def get_theme(cls, request=None) -> str:
        """The active theme slug, falling back to the default when unset."""
        settings_obj = get_site_settings(request)
        if settings_obj is None:
            return DEFAULT_THEME
        return settings_obj.theme or DEFAULT_THEME


def get_site_settings(request=None) -> SiteSettings | None:
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
    return SiteSettings.objects.filter(site=site).first()


def members_only_pages(request=None) -> list:
    """Live pages flagged ``members_only``, for the portal's quick links.

    Scoped to the requested site when there is one, so a second Wagtail site
    would never leak its members' area into another site's config.
    """
    from wagtail.models import Site

    site = Site.find_for_request(request) if request is not None else None
    root = site.root_page if site else None

    pages: list = []
    for model in (StandardPage, NewsPage):
        queryset = model.objects.live().public().filter(members_only=True)
        if root is not None:
            queryset = queryset.descendant_of(root, inclusive=True)
        pages.extend(queryset.order_by("path"))
    return pages
