"""A bulk email's message as HTML: the server's allow-list, and the plain-text part.

The portal's editor writes the message as HTML, and the server never trusts it.
:func:`sanitize` keeps only the tags and attributes an email needs, and only links a
mail program can follow safely; everything else goes, the text inside a dropped tag
excepted.  :func:`html_to_text` derives the plain-text part every copy also carries
from the same HTML, so the two parts always say the same thing.
"""

from __future__ import annotations

import re

import nh3
from bs4 import BeautifulSoup
from bs4.element import NavigableString, PreformattedString, Tag

#: The tags a message may use.  Any other tag is dropped and its text kept.
ALLOWED_TAGS: frozenset[str] = frozenset(
    {
        "a",
        "b",
        "blockquote",
        "br",
        "em",
        "h1",
        "h2",
        "h3",
        "hr",
        "i",
        "img",
        "li",
        "ol",
        "p",
        "s",
        "strong",
        "u",
        "ul",
    }
)

#: The tags dropped together with everything inside them.
DROPPED_WITH_CONTENT: frozenset[str] = frozenset({"script", "style"})

#: The attributes each tag may carry.  Every other attribute -- ``style``, ``class``,
#: ``id``, and every event handler such as ``onclick`` -- is stripped.
ALLOWED_ATTRIBUTES: dict[str, set[str]] = {
    "a": {"href", "title"},
    "img": {"src", "alt", "width", "height"},
}

#: The URL schemes a link (``href``) may use.
LINK_SCHEMES: frozenset[str] = frozenset({"http", "https", "mailto"})

#: The URL schemes an image (``src``) may use: an image is fetched from the web.
IMAGE_SCHEMES: frozenset[str] = frozenset({"http", "https"})

#: What an image's ``width`` and ``height`` may hold: a whole number of pixels.
PIXELS_RE = re.compile(r"\d{1,5}")

#: A URL's scheme, as :func:`_scheme` reads it.
SCHEME_RE = re.compile(r"([A-Za-z][A-Za-z0-9+.-]*):")

#: How a horizontal rule reads in the plain-text part.
TEXT_RULE = "----"

#: The tags whose content stands as a paragraph of its own in the plain-text part.
_PARAGRAPH_TAGS = frozenset({"p", "h1", "h2", "h3"})

#: The list tags, which the plain-text part writes one item to a line.
_LIST_TAGS = frozenset({"ul", "ol"})

#: Every tag that starts a block of its own in the plain-text part.
_BLOCK_TAGS = _PARAGRAPH_TAGS | _LIST_TAGS | {"blockquote", "hr", "li"}

#: A run of whitespace, which HTML reads as one space.
_WHITESPACE_RE = re.compile(r"\s+")


def _scheme(url: str) -> str:
    """Return the lower-cased scheme ``url`` starts with, or ``""`` when it has none."""
    match = SCHEME_RE.match(url.strip())
    return "" if match is None else match.group(1).lower()


def _filter_attribute(element: str, attribute: str, value: str) -> str | None:
    """Keep or drop one attribute nh3 has already allowed by name.

    A link's ``href`` must use one of :data:`LINK_SCHEMES` and an image's ``src``
    one of :data:`IMAGE_SCHEMES`; an image's ``width`` and ``height`` must be a whole
    number of pixels.  Answers ``value`` to keep the attribute and ``None`` to drop it.
    """
    if attribute == "href":
        return value if _scheme(value) in LINK_SCHEMES else None
    if attribute == "src":
        return value if _scheme(value) in IMAGE_SCHEMES else None
    if attribute in {"width", "height"}:
        return value if PIXELS_RE.fullmatch(value.strip()) else None
    return value


_CLEANER = nh3.Cleaner(
    tags=set(ALLOWED_TAGS),
    clean_content_tags=set(DROPPED_WITH_CONTENT),
    attributes=ALLOWED_ATTRIBUTES,
    attribute_filter=_filter_attribute,
    url_schemes=set(LINK_SCHEMES),
    # A relative URL means nothing in a mail program, so it is dropped rather than
    # sent as a link that goes nowhere.
    url_relative="deny",
    link_rel=None,
    strip_comments=True,
)


def sanitize(html: str) -> str:
    """Return ``html`` reduced to what a bulk email may carry.

    The tags kept are :data:`ALLOWED_TAGS`; any other tag is removed and the text
    inside it kept, except ``script`` and ``style``, which go with their content.
    A link keeps ``href`` and ``title`` and an image ``src``, ``alt``, ``width``, and
    ``height``; every other attribute (``style``, ``class``, ``id``, ``onclick`` and
    every other event handler) is stripped.  A link's address must be absolute and
    use ``http``, ``https``, or ``mailto``, and an image's ``http`` or ``https``;
    an address that does not, such as ``javascript:alert(1)`` or a relative path, is
    removed and leaves the tag without it.  ``width`` and ``height`` must be whole
    numbers.  Comments are removed.  The answer is well formed: every tag kept is
    closed.  Sanitizing an already sanitized message changes nothing.
    """
    return _CLEANER.clean(html)


def html_to_text(html: str) -> str:
    """Return the plain-text part of the message ``html``.

    Each paragraph and heading is a block of its own, and blocks are separated by
    one blank line.  A line break (``br``) starts a new line within its block.
    Each item of a bulleted list starts ``- ``, and each item of a numbered list its
    number (``1. ``, ``2. ``), one item to a line, a nested list indented two spaces
    under its item.  A quotation's lines start ``> ``, and a horizontal rule reads
    ``----``.  A link reads ``text (url)``, or the address alone when the text is
    the address (with ``mailto:`` ignored); an image reads as its alt text.  Bold,
    italic, and the other inline styles leave plain text.  Runs of whitespace read as
    one space, as in HTML, and the answer has no blank lines at either end.
    """
    soup = BeautifulSoup(html, "html.parser")
    return "\n\n".join(_blocks(soup))


def _blocks(node: Tag) -> list[str]:
    """Return the text blocks inside ``node``, a container of inline and block content.

    Inline content between block tags is gathered into one block, so loose text
    next to a paragraph still reads as a paragraph of its own.
    """
    blocks: list[str] = []
    run: list[str] = []

    def flush() -> None:
        """Add the inline content gathered so far as a block, if it has any text."""
        text = _tidy("".join(run))
        if text != "":
            blocks.append(text)
        run.clear()

    for child in node.children:
        if isinstance(child, Tag) and child.name in _BLOCK_TAGS:
            flush()
            blocks.extend(_block(child))
        else:
            run.append(_inline(child))
    flush()
    return blocks


def _block(tag: Tag) -> list[str]:
    """Return the text blocks one block tag, ``tag``, stands for."""
    if tag.name == "hr":
        return [TEXT_RULE]
    if tag.name in _LIST_TAGS:
        return [_list_text(tag)]
    if tag.name == "blockquote":
        quoted = "\n\n".join(_blocks(tag))
        return ["\n".join(f"> {line}".rstrip() for line in quoted.split("\n"))]
    if tag.name == "li":
        # An item outside any list reads as one inside a bulleted list.
        return [_item_text(tag, "- ")]
    text = _tidy(_inline_children(tag))
    return [text] if text != "" else []


def _list_text(tag: Tag) -> str:
    """Return a list, ``tag``, as one line per item, each item marked as its list is."""
    items = [child for child in tag.children if isinstance(child, Tag) and child.name == "li"]
    numbered = tag.name == "ol"
    return "\n".join(
        _item_text(item, f"{number}. " if numbered else "- ")
        for number, item in enumerate(items, start=1)
    )


def _item_text(item: Tag, marker: str) -> str:
    """Return one list item, ``item``, starting with ``marker``.

    The editor wraps an item's text in a paragraph, and an item may hold a nested
    list: every line after the first is indented two spaces, so a nested list sits
    under its item.
    """
    lines = "\n".join(_blocks(item)).split("\n")
    rest = [f"  {line}" if line != "" else "" for line in lines[1:]]
    return "\n".join([f"{marker}{lines[0]}", *rest])


def _inline_children(tag: Tag) -> str:
    """Return the inline text of every child of ``tag``, joined."""
    return "".join(_inline(child) for child in tag.children)


def _inline(node: object) -> str:
    """Return the text one inline node stands for, its whitespace not yet tidied.

    A line break is a newline, an image its alt text, and a link ``text (url)``;
    any other tag is the text inside it, and a nested block tag reads as its own
    line.
    """
    if isinstance(node, PreformattedString):
        # A comment, a CDATA section, or a declaration: nothing a reader sees.
        return ""
    if isinstance(node, NavigableString):
        return _WHITESPACE_RE.sub(" ", str(node))
    if not isinstance(node, Tag):
        return ""
    if node.name == "br":
        return "\n"
    if node.name == "img":
        return _attribute(node, "alt")
    if node.name == "a":
        return _link_text(node)
    if node.name in _BLOCK_TAGS:
        return "\n" + "\n\n".join(_block(node)) + "\n"
    return _inline_children(node)


def _link_text(link: Tag) -> str:
    """Return a link as ``text (url)``, or one of the two when the other says nothing.

    The address alone stands when the text is the address, ignoring a ``mailto:``
    in front of it, or when the link has no text; the text alone stands when the
    link has no address.
    """
    text = _tidy(_inline_children(link))
    href = _attribute(link, "href").strip()
    if href == "":
        return text
    shown = href.removeprefix("mailto:") if _scheme(href) == "mailto" else href
    if text in {"", href, shown}:
        return shown
    return f"{text} ({shown})"


def _attribute(tag: Tag, name: str) -> str:
    """Return the attribute ``name`` of ``tag`` as one string, ``""`` when absent."""
    value = tag.get(name)
    if value is None:
        return ""
    return value if isinstance(value, str) else " ".join(value)


def _tidy(text: str) -> str:
    """Return ``text`` with each line's runs of spaces collapsed and its ends trimmed.

    Blank lines at either end go; one blank line inside, which separates two blocks
    a list item or a quotation holds, stays.
    """
    lines = [_WHITESPACE_RE.sub(" ", line).strip() for line in text.split("\n")]
    joined = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", joined).strip("\n")
