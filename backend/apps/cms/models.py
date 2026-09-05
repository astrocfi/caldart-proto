"""Minimal Wagtail content models so the site boots (PLAN §4.6).

``feat/cms-site`` owns this app and adds the full page-type set, StreamField
blocks, the members-only wall and ``seed_content``.  Foundation ships only what
the rest of the system needs: a home page and the site settings that carry the
theme.
"""

from __future__ import annotations

from django.db import models
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.contrib.settings.models import BaseSiteSetting, register_setting
from wagtail.fields import RichTextField
from wagtail.models import Page

#: Themes shipped in ``frontend/src/styles/themes/`` (PLAN §9).
THEME_CHOICES: tuple[tuple[str, str], ...] = (
    ("sierra", "Sierra (default, warm paper)"),
    ("pacific", "Pacific (cool paper)"),
    ("night", "Night (dark)"),
)
DEFAULT_THEME = "sierra"


class HomePage(Page):
    """The site root page."""

    hero_heading = models.CharField(max_length=200, blank=True)
    hero_lede = models.TextField(blank=True)
    hero_image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    primary_cta_label = models.CharField(max_length=60, blank=True, default="Join CalDART")
    primary_cta_url = models.CharField(max_length=200, blank=True, default="/portal/join")
    secondary_cta_label = models.CharField(max_length=60, blank=True)
    secondary_cta_url = models.CharField(max_length=200, blank=True)
    mission_statement = RichTextField(blank=True)

    content_panels = [
        *Page.content_panels,
        MultiFieldPanel(
            [
                FieldPanel("hero_heading"),
                FieldPanel("hero_lede"),
                FieldPanel("hero_image"),
                FieldPanel("primary_cta_label"),
                FieldPanel("primary_cta_url"),
                FieldPanel("secondary_cta_label"),
                FieldPanel("secondary_cta_url"),
            ],
            heading="Hero",
        ),
        FieldPanel("mission_statement"),
    ]

    template = "cms/home_page.html"

    class Meta:
        verbose_name = "home page"

    def __str__(self) -> str:
        return self.title


@register_setting
class SiteSettings(BaseSiteSetting):
    """Organisation details and the active theme."""

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
            heading="Organisation",
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
        try:
            settings_obj = cls.load(request_or_site=request) if request else cls.objects.first()
        except Exception:  # pragma: no cover - no site configured yet
            return DEFAULT_THEME
        if settings_obj is None:
            return DEFAULT_THEME
        return settings_obj.theme or DEFAULT_THEME
