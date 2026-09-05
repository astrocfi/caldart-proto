"""StreamField blocks for the public site (PLAN §4.6).

Every block renders through its own template under ``templates/cms/blocks/`` so
the design system owns the markup, not the editor.  ``raw_html`` is the one
restricted block: :func:`apps.cms.forms.can_use_raw_html` decides who is
offered it and :class:`apps.cms.forms.RestrictedBlocksPageForm` removes it from
the editor for everybody else.
"""

from __future__ import annotations

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

#: Block types only a website administrator may add (PLAN §4.6).
RESTRICTED_BLOCK_TYPES: tuple[str, ...] = ("raw_html",)


def heading_anchor(text: str) -> str:
    """The ``id`` a heading block renders with, and its "on this page" link."""
    return slugify(text)[:60] or "section"


class HeadingBlock(blocks.StructBlock):
    """A section heading.  Anchored, so long pages get an "on this page" rail."""

    text = blocks.CharBlock(max_length=120)
    level = blocks.ChoiceBlock(
        choices=[("h2", "Section (H2)"), ("h3", "Sub-section (H3)")],
        default="h2",
        help_text="H2 headings appear in the “on this page” list.",
    )

    class Meta:
        icon = "title"
        label = "Heading"
        template = "cms/blocks/heading.html"

    def get_context(self, value, parent_context=None):
        context = super().get_context(value, parent_context=parent_context)
        context["anchor"] = heading_anchor(value["text"])
        return context


class ParagraphBlock(blocks.RichTextBlock):
    """Body copy, held to a readable measure by the template."""

    def __init__(self, **kwargs):
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

    def clean(self, value):
        value = super().clean(value)
        if not value.get("page") and not value.get("url"):
            raise blocks.StructBlockValidationError(
                non_block_errors=["Choose a page or enter a URL."]
            )
        return value

    def get_context(self, value, parent_context=None):
        context = super().get_context(value, parent_context=parent_context)
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
    """The body StreamField offered on every editable page (PLAN §4.6)."""

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
        help_text="Paste a YouTube, Vimeo or other oEmbed URL.",
    )
    raw_html = blocks.RawHTMLBlock(
        label="Raw HTML",
        icon="code",
        help_text="Unescaped HTML. Website administrators only.",
    )

    class Meta:
        required = False


class StepBlock(blocks.StructBlock):
    """One numbered step of the concept of operations."""

    title = blocks.CharBlock(max_length=120)
    text = blocks.TextBlock(rows=3)

    class Meta:
        icon = "list-ol"
        label = "Step"
        template = "cms/blocks/step.html"


class ConceptStreamBlock(blocks.StreamBlock):
    """The home page's "concept of operations": an ordered list of steps."""

    step = StepBlock()

    class Meta:
        required = False


def stream_headings(value) -> list[dict]:
    """Top-level H2 ``heading`` blocks of ``value``, for the "on this page" rail."""
    found: list[dict] = []
    for child in value or []:
        if child.block_type != "heading" or child.value.get("level") != "h2":
            continue
        text = child.value["text"]
        found.append({"text": text, "anchor": heading_anchor(text)})
    return found
