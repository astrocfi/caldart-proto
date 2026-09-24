"""StreamField blocks for the public site.

Every block renders through its own template under ``templates/cms/blocks/`` so
the design system owns the markup, not the editor.  ``raw_html`` is the one
restricted block: :func:`apps.cms.forms.can_use_raw_html` decides who is
offered it and :class:`apps.cms.forms.RestrictedBlocksPageForm` removes it from
the editor for everybody else.
"""

from __future__ import annotations

from typing import Any

from django.utils.text import slugify
from wagtail import blocks
from wagtail.documents.blocks import DocumentChooserBlock
from wagtail.embeds.blocks import EmbedBlock
from wagtail.images.blocks import ImageChooserBlock

#: Rich-text features offered in body copy.  Headings above H3 belong to the
#: page title and the ``heading`` block, so they are deliberately absent.
RICH_TEXT_FEATURES: list[str] = [
    "h3",
    "h4",
    "bold",
    "italic",
    "link",
    "document-link",
    "ol",
    "ul",
    "hr",
    "blockquote",
]

#: Block types only a website administrator may add.
RESTRICTED_BLOCK_TYPES: tuple[str, ...] = ("raw_html",)


def heading_anchor(text: str) -> str:
    """The ``id`` a heading block renders with, and its "on this page" link.

    The heading text slugified and cut to 60 characters, so "Who we need" becomes
    ``who-we-need``.  Text that slugifies to nothing, such as punctuation alone,
    gives ``section``.
    """
    return slugify(text)[:60] or "section"


class HeadingBlock(blocks.StructBlock):
    """A section heading.  Anchored, so long pages get an "on this page" rail."""

    text = blocks.CharBlock(max_length=120)
    level = blocks.ChoiceBlock(
        choices=[("h2", "Section (H2)"), ("h3", "Sub-section (H3)")],
        default="h2",
        help_text='H2 headings appear in the "on this page" list.',
    )

    class Meta:
        icon = "title"
        label = "Heading"
        template = "cms/blocks/heading.html"

    def get_context(
        self, value: blocks.StructValue, parent_context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """The block's template context plus ``anchor``, the heading's ``id``."""
        context: dict[str, Any] = super().get_context(value, parent_context=parent_context)
        context["anchor"] = heading_anchor(value["text"])
        return context


class ParagraphBlock(blocks.RichTextBlock):
    """Body copy, held to a readable measure by the template."""

    def __init__(self, **kwargs: Any) -> None:
        """Build the block, defaulting its rich-text features to the body set.

        A caller that passes ``features`` keeps it; every other keyword argument
        goes straight to Wagtail's rich-text block.
        """
        kwargs.setdefault("features", RICH_TEXT_FEATURES)
        super().__init__(**kwargs)

    class Meta:
        icon = "pilcrow"
        label = "Paragraph"
        template = "cms/blocks/paragraph.html"


class CaptionedImageBlock(blocks.StructBlock):
    """An uploaded image with an optional caption and credit."""

    image = ImageChooserBlock()
    alt_text = blocks.CharBlock(
        required=False,
        max_length=180,
        help_text="Describe the image for screen readers. Leave blank if decorative.",
    )
    caption = blocks.CharBlock(required=False, max_length=250)
    credit = blocks.CharBlock(required=False, max_length=120)
    full_width = blocks.BooleanBlock(
        required=False,
        default=False,
        help_text="Let the image run past the text column.",
    )

    class Meta:
        icon = "image"
        label = "Image"
        template = "cms/blocks/image.html"


class QuoteBlock(blocks.StructBlock):
    """A pull-quote."""

    quote = blocks.TextBlock(rows=3)
    attribution = blocks.CharBlock(required=False, max_length=120)

    class Meta:
        icon = "openquote"
        label = "Quote"
        template = "cms/blocks/quote.html"


class CTABlock(blocks.StructBlock):
    """A call to action pointing at either a page in the tree or a URL."""

    label = blocks.CharBlock(max_length=60)
    page = blocks.PageChooserBlock(required=False)
    url = blocks.CharBlock(
        required=False,
        max_length=250,
        help_text="An external URL, or a path such as /portal/join.",
    )
    style = blocks.ChoiceBlock(
        choices=[("primary", "Primary"), ("secondary", "Secondary"), ("quiet", "Quiet")],
        default="primary",
    )
    note = blocks.CharBlock(
        required=False, max_length=160, help_text="Small print under the button."
    )

    class Meta:
        icon = "link"
        label = "Call to action"
        template = "cms/blocks/cta.html"

    def clean(self, value: blocks.StructValue) -> blocks.StructValue:
        """Validate the block, requiring a destination.

        Raises ``StructBlockValidationError`` with the message "Choose a page or
        enter a URL." when neither ``page`` nor ``url`` is filled in.  Returns the
        cleaned value when either one is.
        """
        value = super().clean(value)
        if not value.get("page") and not value.get("url"):
            raise blocks.StructBlockValidationError(
                non_block_errors=["Choose a page or enter a URL."]
            )
        return value

    def get_context(
        self, value: blocks.StructValue, parent_context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """The block's template context plus ``href``, where the button points.

        The chosen page's own URL wins.  The typed URL is used when no page is
        chosen or the chosen page has no URL of its own, and ``#`` stands in when
        neither yields an address.
        """
        context: dict[str, Any] = super().get_context(value, parent_context=parent_context)
        page = value.get("page")
        context["href"] = (page.url if page is not None else "") or value.get("url") or "#"
        return context


class DocumentLinkBlock(blocks.StructBlock):
    """A download: the document plus the label the reader sees."""

    document = DocumentChooserBlock()
    label = blocks.CharBlock(required=False, max_length=120)
    description = blocks.CharBlock(required=False, max_length=250)

    class Meta:
        icon = "doc-full-inverse"
        label = "Document"
        template = "cms/blocks/document.html"


class ColumnStreamBlock(blocks.StreamBlock):
    """What may sit inside one half of a ``two_columns`` block."""

    heading = HeadingBlock()
    paragraph = ParagraphBlock()
    image = CaptionedImageBlock()
    quote = QuoteBlock()
    cta = CTABlock()
    document = DocumentLinkBlock()

    class Meta:
        icon = "list-ul"
        required = False


class TwoColumnsBlock(blocks.StructBlock):
    """Two columns of content, side by side on wide screens, stacked on a phone."""

    left = ColumnStreamBlock()
    right = ColumnStreamBlock()

    class Meta:
        icon = "grip"
        label = "Two columns"
        template = "cms/blocks/two_columns.html"


class ContentStreamBlock(blocks.StreamBlock):
    """The body StreamField offered on every editable page."""

    heading = HeadingBlock()
    paragraph = ParagraphBlock()
    image = CaptionedImageBlock()
    quote = QuoteBlock()
    cta = CTABlock()
    document = DocumentLinkBlock()
    two_columns = TwoColumnsBlock()
    embed = EmbedBlock(
        label="Embed",
        icon="media",
        template="cms/blocks/embed.html",
        help_text="Paste a YouTube, Vimeo, or other oEmbed URL.",
    )
    raw_html = blocks.RawHTMLBlock(
        label="Raw HTML",
        icon="code",
        help_text="Unescaped HTML. Website administrators only.",
    )

    class Meta:
        required = False


class MissionBlock(blocks.StructBlock):
    """One flown mission: when it happened, and what CalDART carried."""

    year = blocks.CharBlock(max_length=9, help_text="The year, or a range such as 2020-2021.")
    text = blocks.TextBlock(rows=3, help_text="What was flown, from where, to whom.")

    class Meta:
        icon = "site"
        label = "Mission"
        template = "cms/blocks/mission.html"


class MissionStreamBlock(blocks.StreamBlock):
    """The home page's record of missions flown, newest first."""

    mission = MissionBlock()

    class Meta:
        required = False


def stream_headings(value: blocks.StreamValue | None) -> list[dict[str, str]]:
    """Top-level H2 ``heading`` blocks of ``value``, for the "on this page" rail.

    Each entry is ``{"text", "anchor"}``, in the order the blocks appear.  Blocks
    of any other type, H3 headings, and headings nested inside another block are
    all skipped, and ``None`` gives an empty list.
    """
    found: list[dict[str, str]] = []
    for child in value or []:
        if child.block_type != "heading" or child.value.get("level") != "h2":
            continue
        text = child.value["text"]
        found.append({"text": text, "anchor": heading_anchor(text)})
    return found
