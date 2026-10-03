"""A bulk email's HTML message: what the sanitizer keeps, and the plain-text part.

``apps.bulk_email.richtext.sanitize`` keeps an allow-list of tags and attributes and
only links a mail program can follow safely; ``html_to_text`` writes the same
message as the plain-text part every copy carries.
"""

from __future__ import annotations

import pytest

from apps.bulk_email.richtext import MAX_NESTING_DEPTH, html_to_text, nesting_depth, sanitize


# --------------------------------------------------------------------------
# sanitize
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "html",
    [
        "<p>Hello <strong>Ann</strong>, <em>welcome</em>.</p>",
        "<h1>One</h1><h2>Two</h2><h3>Three</h3>",
        "<ul><li><p>one</p></li></ul><ol><li><p>two</p></li></ol>",
        "<p><b>b</b> <i>i</i> <u>u</u> <s>s</s><br>next</p>",
        "<blockquote><p>Quoted</p></blockquote><hr>",
        '<p><a href="https://caldart.example.org/join" title="Join">Join</a></p>',
        '<p><a href="http://example.org">plain http</a></p>',
        '<p><a href="mailto:ops@caldart.example.org">Write to us</a></p>',
        '<img src="https://caldart.example.org/media/a.png" alt="A plane" width="600" '
        'height="400">',
    ],
    ids=[
        "inline-styles",
        "headings",
        "lists",
        "more-inline",
        "quote-and-rule",
        "https-link",
        "http-link",
        "mailto-link",
        "image",
    ],
)
def test_allowed_markup_passes_unchanged(html: str) -> None:
    """Every allowed tag and attribute survives sanitizing exactly as written."""
    assert sanitize(html) == html


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ("<p>Hi</p><script>alert(1)</script>", "<p>Hi</p>"),
        ("<p>Hi</p><style>p { color: red }</style>", "<p>Hi</p>"),
        ("<p>Hi<script>document.cookie</script> there</p>", "<p>Hi there</p>"),
    ],
    ids=["script", "style", "inline-script"],
)
def test_scripts_and_styles_go_with_their_content(html: str, expected: str) -> None:
    """``script`` and ``style`` are removed together with everything inside them."""
    assert sanitize(html) == expected


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ('<p onclick="steal()">Hi</p>', "<p>Hi</p>"),
        (
            '<img src="https://x.example/a.png" alt="A" onerror="steal()">',
            '<img src="https://x.example/a.png" alt="A">',
        ),
        (
            '<a href="https://x.example" onmouseover="steal()">x</a>',
            '<a href="https://x.example">x</a>',
        ),
    ],
    ids=["onclick", "onerror", "onmouseover"],
)
def test_event_handler_attributes_are_stripped(html: str, expected: str) -> None:
    """Every ``on*`` event handler attribute is removed, and the tag kept."""
    assert sanitize(html) == expected


@pytest.mark.parametrize(
    "href",
    [
        "javascript:alert(1)",
        "JavaScript:alert(1)",
        " javascript:alert(1)",
        "java&#x09;script:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "vbscript:msgbox(1)",
        "/portal/payments",
        "ftp://example.org/file",
    ],
    ids=[
        "javascript",
        "mixed-case",
        "leading-space",
        "entity-tab",
        "data",
        "vbscript",
        "relative",
        "ftp",
    ],
)
def test_a_link_to_anything_but_http_https_or_mailto_loses_its_address(href: str) -> None:
    """A link whose scheme is not allowed, or which is relative, keeps its text only."""
    assert sanitize(f'<p><a href="{href}">click</a></p>') == "<p><a>click</a></p>"


@pytest.mark.parametrize(
    "src",
    ["mailto:ops@example.org", "javascript:alert(1)", "data:image/png;base64,AAAA", "/media/a.png"],
    ids=["mailto", "javascript", "data", "relative"],
)
def test_an_image_from_anything_but_http_or_https_loses_its_source(src: str) -> None:
    """An image's ``src`` must be an absolute ``http`` or ``https`` address."""
    assert sanitize(f'<img src="{src}" alt="A">') == '<img alt="A">'


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ("<div><p>In a div</p></div>", "<p>In a div</p>"),
        ("<table><tr><td>cell</td></tr></table>", "cell"),
        ('<p><span class="x">span</span></p>', "<p>span</p>"),
        ('<iframe src="https://evil.example"></iframe><p>after</p>', "<p>after</p>"),
        ("<p>a<!-- hidden -->b</p>", "<p>ab</p>"),
        ("<form><input value='x'><button>Go</button></form>", "Go"),
    ],
    ids=["div", "table", "span", "iframe", "comment", "form"],
)
def test_disallowed_tags_are_dropped_and_their_text_kept(html: str, expected: str) -> None:
    """A tag outside the allow-list goes, and the text inside it stays."""
    assert sanitize(html) == expected


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ('<p style="color: red">Red</p>', "<p>Red</p>"),
        ('<p class="lead" id="intro">Lead</p>', "<p>Lead</p>"),
        ('<strong style="font-size: 40px">Big</strong>', "<strong>Big</strong>"),
        (
            '<a href="https://x.example" target="_blank" rel="opener">x</a>',
            '<a href="https://x.example">x</a>',
        ),
    ],
    ids=["style", "class-and-id", "inline-style", "target-and-rel"],
)
def test_styles_classes_ids_and_other_attributes_are_stripped(html: str, expected: str) -> None:
    """No ``style``, ``class``, ``id``, or other attribute off the allow-list survives."""
    assert sanitize(html) == expected


def test_an_image_size_must_be_a_whole_number_of_pixels() -> None:
    """A ``width`` or ``height`` that is not digits is removed."""
    html = '<img src="https://x.example/a.png" alt="A" width="100%" height="expression(1)">'
    assert sanitize(html) == '<img src="https://x.example/a.png" alt="A">'


def test_sanitizing_closes_every_tag() -> None:
    """The answer is well formed even when the input left a tag open."""
    assert sanitize("<p><strong>open") == "<p><strong>open</strong></p>"


def test_sanitizing_twice_changes_nothing() -> None:
    """A sanitized message passes through the sanitizer unchanged."""
    once = sanitize('<p onclick="x()">Hi <a href="javascript:x()">a</a><script>s</script></p>')
    assert sanitize(once) == once


def test_tokens_survive_sanitizing() -> None:
    """Recipient field tokens are plain text, and the sanitizer leaves them as written."""
    html = "<p>Dear {first_name|friend}, your DART is {dart_name}.</p>"
    assert sanitize(html) == html


# --------------------------------------------------------------------------
# html_to_text
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ("<p>One</p><p>Two</p>", "One\n\nTwo"),
        ("<p>Line one<br>line two</p>", "Line one\nline two"),
        ("<h2>News</h2><p>Body</p>", "News\n\nBody"),
        ("<p>Read <strong>this</strong> and <em>that</em>.</p>", "Read this and that."),
        (
            "<ul><li><p>Logbook</p></li><li><p>Headset</p></li></ul>",
            "- Logbook\n- Headset",
        ),
        (
            "<ol><li><p>Check in</p></li><li><p>Brief</p></li></ol>",
            "1. Check in\n2. Brief",
        ),
        (
            "<ul><li><p>Pack</p><ul><li><p>Water</p></li></ul></li></ul>",
            "- Pack\n  - Water",
        ),
        (
            '<p>See <a href="https://caldart.example.org/events">the events</a>.</p>',
            "See the events (https://caldart.example.org/events).",
        ),
        (
            '<p><a href="https://caldart.example.org">https://caldart.example.org</a></p>',
            "https://caldart.example.org",
        ),
        (
            '<p><a href="mailto:ops@caldart.example.org">ops@caldart.example.org</a></p>',
            "ops@caldart.example.org",
        ),
        (
            '<p><a href="mailto:ops@caldart.example.org">Write to us</a></p>',
            "Write to us (ops@caldart.example.org)",
        ),
        (
            '<p>Before</p><img src="https://x.example/a.png" alt="A Cessna 182"><p>After</p>',
            "Before\n\nA Cessna 182\n\nAfter",
        ),
        ("<blockquote><p>First</p><p>Second</p></blockquote>", "> First\n>\n> Second"),
        ("<p>Above</p><hr><p>Below</p>", "Above\n\n----\n\nBelow"),
        ("<p>  lots   of\n   space  </p>", "lots of space"),
        ("<p>Tom &amp; Jerry &lt;3</p>", "Tom & Jerry <3"),
        ("", ""),
    ],
    ids=[
        "paragraphs",
        "line-break",
        "heading",
        "inline-styles",
        "bulleted-list",
        "numbered-list",
        "nested-list",
        "link",
        "link-whose-text-is-the-address",
        "mailto-whose-text-is-the-address",
        "mailto-with-text",
        "image",
        "quotation",
        "rule",
        "whitespace",
        "entities",
        "empty",
    ],
)
def test_the_text_part_is_derived_from_the_html(html: str, expected: str) -> None:
    """Each piece of HTML reads as its plain-text equivalent."""
    assert html_to_text(html) == expected


def test_the_text_part_keeps_tokens_for_substitution() -> None:
    """Tokens pass into the text part as written, to be filled in for each person."""
    assert html_to_text("<p>Dear <strong>{first_name|friend}</strong>,</p>") == (
        "Dear {first_name|friend},"
    )


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ("plain words", 0),
        ("<p>One</p><p>Two</p>", 1),
        ("<ul><li><p>a<br>b</p></li></ul>", 3),
        ('<p>x<img src="https://x.example/a.png" alt="A"><hr></p>', 1),
        ("<b>" * 400 + "x", 400),
    ],
    ids=["text", "paragraphs", "list", "empty-tags", "deep"],
)
def test_nesting_depth(html: str, expected: int) -> None:
    """The depth counts tags that hold something, however deep they go."""
    assert nesting_depth(html) == expected


def test_the_text_part_reads_any_message_within_the_depth_limit() -> None:
    """A message nested close to the limit is read without running out of stack."""
    html = "<blockquote><ul><li>" * (MAX_NESTING_DEPTH // 3) + "deep"
    assert html_to_text(sanitize(html)).endswith("deep")
