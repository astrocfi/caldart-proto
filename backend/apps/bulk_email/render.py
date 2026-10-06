"""One recipient's copy of a bulk email: its subject, its two bodies, and its headers.

:func:`render_copy` is the one place a copy is built, for the background sender and for
anything that shows a copy as it went, through :func:`render_for`, which builds one
person's whole copy, footer and headers included, for the preview and a test copy too;
:func:`render_message` builds one from a subject, a message, and the field values to
fill in.  The message is HTML,
sanitized afresh every time (``apps.bulk_email.richtext.sanitize``), and each
recipient's values are filled into it HTML-escaped; the plain-text body is derived
from the filled-in message (``html_to_text``), so it reads each value as it is.  The
bodies come from ``emails/bulk_email.{txt,html}``: the plain-text body is the message
followed by the house footer, and the HTML one puts the message inside the house email
layout, and every copy's footer links to the message on the recipient's **Email to me**
page (:func:`browser_url`).  A mission callout's copy carries its three answer buttons
above the footer, and its footer link opens the answer page instead
(``apps.bulk_email.callout_links``).  The sender hands the finished bodies to
``caldart.mail.send_templated`` through the pass-through pair
``emails/bulk_email_copy.{txt,html}`` (:data:`COPY_TEMPLATE`), so the email log
records the copy like any other message.  The email's type decides the footer line
and the unsubscribe headers (``apps.mail.unsubscribe``).

:func:`check_message` is what a save, a preview, and a send refuse a message for: a
token the field catalog does not have, one whose HTML and plain text would not be
filled in alike, or tags nested too deeply to read.
"""

from __future__ import annotations

import html as html_lib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace

from django.conf import settings
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

from apps.accounts.models import User
from apps.bulk_email.callout_links import (
    AnswerLink,
    answer_links,
    answer_url,
    at_words,
    link_token,
)
from apps.bulk_email.fields import (
    FIELDS_BY_TOKEN,
    TOKEN_RE,
    Token,
    find_tokens,
    is_in_address,
    substitute,
    unknown_token_message,
    unknown_tokens,
    values_for,
)
from apps.bulk_email.models import BulkEmail, BulkEmailRecipient, Callout
from apps.bulk_email.richtext import MAX_NESTING_DEPTH, html_to_text, nesting_depth, sanitize
from apps.mail.unsubscribe import UNSUBSCRIBE_PATH, Footer, footer_for, headers_for
from caldart.mail import contact_email, org_name

#: The template pair a copy is built from.
TEMPLATE = "bulk_email"

#: The pass-through template pair a built copy is sent through: each renders the
#: ``text`` or ``html`` it is given, unchanged.
COPY_TEMPLATE = "bulk_email_copy"

#: The email log's purpose for every copy.
PURPOSE = "bulk_email"

#: What stands in a preview's unsubscribe link where a copy's signed token goes: the
#: link reads as a copy's does, but unsubscribes nobody.
PREVIEW_STAND_IN = "preview"

#: Where the portal shows a sent bulk email to the people who received it.
MESSAGES_PATH = "/portal/messages/"

#: The longest preheader, the line a mail program shows beside the subject.
PREHEADER_LENGTH = 90

#: Why a token whose HTML and plain text differ is refused: its braces hold
#: formatting, such as bold applied to half of it, or a character a field cannot.
RETYPE_MESSAGE = (
    "{written} has formatting or an angle bracket inside its braces, so it cannot be "
    "filled in. Delete it and put it in again with Insert field."
)

#: Why a message whose tags nest too deeply is refused.
TOO_DEEP_MESSAGE = (
    "This message has formatting nested too deeply to send. Take out some of the "
    "lists, quotations, or styles inside one another."
)

#: One tag of the sanitized message, so the text between tags can be told apart.
_TAG_RE = re.compile(r"<[^>]*>")


@dataclass(frozen=True)
class RenderedCopy:
    """One recipient's copy of a bulk email.

    ``subject`` is the subject line, ``text`` and ``html`` the two bodies, and
    ``headers`` any extra headers the copy carries.
    """

    subject: str
    text: str
    html: str
    headers: dict[str, str] = field(default_factory=dict)


def render_copy(
    bulk: BulkEmail, recipient: BulkEmailRecipient, *, inert: bool = False
) -> RenderedCopy:
    """``recipient``'s copy of ``bulk``, filled in with the values stored on the row.

    The row's ``values`` are the ones the copy went out with (:func:`fill_values`), so
    a copy rebuilt after the person's profile changed reads as it was sent.  A token
    whose value the row does not hold is filled in as empty, so its fallback stands.
    The footer and the headers are :func:`render_for`'s for the row's account; with
    ``inert``, for a copy shown to somebody other than its recipient, such as the sender
    on the delivery report, the unsubscribe link carries no token and there is no header.
    A callout's answer buttons are the recipient's own, signed for them, unless ``inert``.
    """
    values = stored_values(bulk, recipient)
    return render_for(bulk, recipient.user, values, inert=inert, live_answers=not inert)


def render_for(
    bulk: BulkEmail,
    user: User | None,
    values: Mapping[str, str],
    *,
    inert: bool = False,
    view_url: str | None = None,
    live_answers: bool = False,
) -> RenderedCopy:
    """``user``'s copy of ``bulk``, filled in with ``values``: one person's whole copy.

    This is the copy the sender sends, the preview shows, and a test copy carries.
    With ``inert`` (the preview) the footer reads as the copy's does, but its
    unsubscribe link carries :data:`PREVIEW_STAND_IN` instead of a signed token, and the
    copy carries no header, so showing a person's copy to a sender never hands over
    a link that turns that person's email off.
    The footer and the headers follow the email's type (``apps.mail.unsubscribe``):
    for a type recipients may turn off, the footer says so with ``user``'s own
    unsubscribe link and the copy carries the ``List-Unsubscribe`` and
    ``List-Unsubscribe-Post`` headers; for one they may not, the footer says why they
    receive it and there is no header.  A copy of an email with no type, or for an
    account that is gone (``None``), carries no header and the general line *You
    receive this email as a member or a friend of <organization>.*
    Above the footer the copy links to the email on the reader's **Email to me** page,
    :func:`browser_url`; ``view_url`` given replaces that link, and ``""`` leaves it
    out, as a test copy does.

    A mission callout's copy carries the three answer buttons above the footer, and its
    link to read the email opens the answer page.  With ``live_answers``, which only a
    recipient's own copy passes (``render_copy``), the buttons and that link carry a
    token signed for ``user``; otherwise, and always with ``inert``, they carry
    ``callout_links.STAND_IN`` and answer for nobody, as in the preview, a test copy, and
    every copy shown to a sender.
    """
    footer: Footer | None = None
    headers: dict[str, str] = {}
    if bulk.email_type is not None and user is not None:
        footer = footer_for(user, bulk.email_type)
        headers = headers_for(user, bulk.email_type)
    if inert and footer is not None:
        footer = Footer(text=footer.text, url=inert_unsubscribe_url() if footer.url else "")
        headers = {}
    answers = callout_answers(bulk, user, live=live_answers and not inert)
    default_view = browser_url(bulk) if answers is None else answers.page_url
    copy = render_message(
        bulk.subject,
        bulk.body,
        values,
        footer=footer,
        type_name=bulk.email_type.name if bulk.email_type is not None else "",
        view_url=default_view if view_url is None else view_url,
        answers=answers,
    )
    return replace(copy, headers=headers)


@dataclass(frozen=True)
class CalloutButtons:
    """A callout copy's answer block: the three buttons, its page, and the close time.

    ``closes`` is when answers close, in words (``callout_links.at_words``).
    """

    links: Sequence[AnswerLink]
    page_url: str
    closes: str


def callout_answers(bulk: BulkEmail, user: User | None, *, live: bool) -> CalloutButtons | None:
    """``user``'s answer buttons for the callout ``bulk``; ``None`` for any other email.

    With ``live`` each link carries a token signed for ``user``; without it, or for an
    account that is gone, the stand-in.
    """
    if not bulk.is_callout:
        return None
    callout = Callout.objects.filter(bulk_email=bulk).first()
    if callout is None:
        return None
    token = link_token(callout, user, live=live)
    return CalloutButtons(
        links=answer_links(token), page_url=answer_url(token), closes=at_words(callout.closes_at)
    )


def inert_unsubscribe_url() -> str:
    """The unsubscribe link a preview shows: the page's address with no signed token."""
    return f"{settings.SITE_URL.rstrip('/')}{UNSUBSCRIBE_PATH}{PREVIEW_STAND_IN}"


def browser_url(bulk: BulkEmail) -> str:
    """Where ``bulk`` reads in the browser: its page under the portal's **Email to me**.

    Built on ``SITE_URL``, which carries the path the site is served under:
    ``<SITE_URL>/portal/messages/<id>``.  The page asks the reader to sign in and shows
    their own copy (``apps.bulk_email.archive``).
    """
    return f"{settings.SITE_URL.rstrip('/')}{MESSAGES_PATH}{bulk.pk}"


def render_message(
    subject: str,
    body: str,
    values: Mapping[str, str] | None,
    *,
    footer: Footer | None = None,
    type_name: str = "",
    view_url: str = "",
    answers: CalloutButtons | None = None,
) -> RenderedCopy:
    """A copy of the message ``subject`` and ``body`` with ``values`` filled in.

    ``body`` is sanitized first.  The HTML body takes each value HTML-escaped, and
    each value and fallback percent-encoded inside a link's or an image's address.  The
    plain-text body is derived from that filled-in HTML, so it reads each value as it
    is, and a link's address in it, ``text (url)``, carries the value percent-encoded
    as the link does.  The subject takes each value as it is, with a line break in a
    value read as a space.  ``values`` of ``None`` leaves every token as written,
    which is how the history shows a message.  Both bodies carry the organization's
    name and contact address as they are now, and end with ``footer`` (its line, and
    its link to unsubscribe from ``type_name`` email when it has one), or the general
    line when it is ``None``.  A ``view_url`` puts a line linking to the message in the
    browser above the footer's own lines.  ``answers`` puts a callout's three answer
    buttons, and when answers close, below the message.  The copy carries no header.
    """
    clean = sanitize(body)
    if values is not None:
        subject = fill_subject(subject, values)
        clean = substitute(clean, values, escape=True)
    # Derived from the filled-in HTML, so a value reads as itself in the text and a
    # link's address carries it percent-encoded, exactly as the HTML's link does.
    text = html_to_text(clean)
    context: dict[str, object] = {
        "org_name": org_name(),
        "contact_email": contact_email(),
        "subject": subject,
        "body_text": text,
        # Sanitized above, and every value in it escaped: safe to put in as it is.
        "body_html": mark_safe(clean),  # noqa: S308 - sanitized by nh3 just above
        "preheader": " ".join(text.split())[:PREHEADER_LENGTH],
        "type_name": type_name,
        "footer_text": footer.text if footer is not None else "",
        "footer_url": footer.url if footer is not None else "",
        "view_url": view_url,
        "answers": answers,
    }
    return RenderedCopy(
        subject=subject,
        text=render_to_string(f"emails/{TEMPLATE}.txt", context),
        html=render_to_string(f"emails/{TEMPLATE}.html", context),
    )


def stored_values(bulk: BulkEmail, recipient: BulkEmailRecipient) -> dict[str, str]:
    """The values ``recipient``'s copy of ``bulk`` went out with, for each field it uses.

    Read from the row's ``values``, stored when the copy was tried; a field the row does
    not hold is empty, so its token's fallback stands.
    """
    return {name: recipient.values.get(name, "") for name in message_tokens(bulk)}


def fill_subject(subject: str, values: Mapping[str, str]) -> str:
    """``subject`` with ``values`` filled in as they are, a line break read as a space."""
    flat = {name: " ".join(value.splitlines()) for name, value in values.items()}
    return substitute(subject, flat, escape=False)


def message_tokens(bulk: BulkEmail) -> list[str]:
    """The fields ``bulk``'s subject and message use, each once, in catalog order.

    Only fields the catalog has are named; :func:`check_message` refuses the rest
    before a message is saved or sent.
    """
    used = {token.name for token in find_tokens(bulk.subject)}
    used |= {token.name for token in find_tokens(sanitize(bulk.body))}
    return [name for name in FIELDS_BY_TOKEN if name in used]


def fill_values(bulk: BulkEmail, user: User | None) -> dict[str, str]:
    """``user``'s value for each field ``bulk`` uses: what one copy is filled in with.

    A deleted account (``None``) has an empty value for every field, so each token's
    fallback stands.  Only the fields the message uses are read and answered.
    """
    names = message_tokens(bulk)
    if user is None:
        return dict.fromkeys(names, "")
    return values_for(user, names)


def check_message(subject: str, body: str) -> dict[str, str]:
    """Why the message ``subject`` and ``body`` cannot be saved or sent, by field.

    The answer is empty for a message that can be filled in, and otherwise holds
    :func:`subject_problem` under ``subject`` and :func:`body_problem` under
    ``body``, each only when there is one.
    """
    problems = {"subject": subject_problem(subject), "body": body_problem(body)}
    return {name: problem for name, problem in problems.items() if problem is not None}


def subject_problem(subject: str) -> str | None:
    """Why ``subject`` cannot be filled in: its first unknown token; else ``None``."""
    unknown = unknown_tokens(subject)
    return unknown_token_message(unknown[0]) if len(unknown) > 0 else None


def body_problem(body: str) -> str | None:
    """Why the message ``body`` cannot be filled in, or ``None`` when it can.

    ``body`` is sanitized first.  It is refused with :data:`TOO_DEEP_MESSAGE` when its
    tags nest deeper than ``richtext.MAX_NESTING_DEPTH``.  It is refused for its first
    token the catalog does not have, in the HTML or in the plain text derived from it,
    with :func:`apps.bulk_email.fields.unknown_token_message`, which says how to write
    braces in a web address only when the token sits in a link's or a picture's
    address; and for a token the two parts would not fill in alike, with
    :func:`retype_message`: a token the plain text holds but the HTML does not, because
    formatting splits it (``<strong>{first</strong>_name}``), or a token in the HTML's
    text the plain text
    does not hold, because its fallback holds an angle bracket.
    """
    clean = sanitize(body)
    if nesting_depth(clean) > MAX_NESTING_DEPTH:
        return TOO_DEEP_MESSAGE
    text = html_to_text(clean)
    unknown = unknown_tokens(clean) or unknown_tokens(text)
    if len(unknown) > 0:
        return unknown_token_message(unknown[0], in_address=is_in_address(clean, unknown[0]))
    mismatched = _mismatched_token(clean, text)
    return None if mismatched is None else retype_message(mismatched)


def retype_message(written: str) -> str:
    """Why the token ``written`` (as the message writes it) is refused: retype it."""
    return RETYPE_MESSAGE.format(written=written)


def _mismatched_token(clean: str, text: str) -> str | None:
    """The first token the HTML ``clean`` and its plain ``text`` would fill in apart.

    Answers the token as the plain text or the HTML writes it, or ``None`` when every
    token appears in both.  Tokens in the HTML's attributes count for the first
    direction, since the plain text writes a link's address and an image's
    description out; only the HTML's text counts for the second.
    """
    in_html = {_unescaped(token) for token in find_tokens(clean)}
    for match in TOKEN_RE.finditer(text):
        if _unescaped(Token(match.group(1), match.group(2) or "")) not in in_html:
            return match.group(0)
    in_text = set(find_tokens(text))
    outside_tags = _TAG_RE.sub(" ", clean)
    for match in TOKEN_RE.finditer(outside_tags):
        if _unescaped(Token(match.group(1), match.group(2) or "")) not in in_text:
            return html_lib.unescape(match.group(0))
    return None


def _unescaped(token: Token) -> Token:
    """``token`` with its fallback's HTML entities read, as the plain text writes it."""
    return Token(token.name, html_lib.unescape(token.fallback))
