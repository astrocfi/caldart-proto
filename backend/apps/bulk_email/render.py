"""One recipient's copy of a bulk email: its subject, its two bodies, and its headers.

:func:`render_copy` is the one place a copy is built, for the background sender and for
anything that shows a copy as it went; :func:`render_message` builds one from a subject,
a message, and the field values to fill in, for the preview too.  The message is HTML,
sanitized afresh every time (``apps.bulk_email.richtext.sanitize``), and each
recipient's values are filled into it HTML-escaped; the plain-text body is derived
from the same sanitized message (``html_to_text``) with the values filled in as they
are.  The bodies come from ``emails/bulk_email.{txt,html}``: the plain-text body is
the message followed by the house footer, and the HTML one puts the message inside
the house email layout.  The sender hands the finished bodies to
``caldart.mail.send_templated`` through the pass-through pair
``emails/bulk_email_copy.{txt,html}`` (:data:`COPY_TEMPLATE`), so the email log
records the copy like any other message.

:func:`check_message` is what a save, a preview, and a send refuse a message for: a
token the field catalog does not have, or one whose HTML and plain text would not be
filled in alike.
"""

from __future__ import annotations

import html as html_lib
import re
from collections.abc import Mapping
from dataclasses import dataclass, field

from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

from apps.accounts.models import User
from apps.bulk_email.fields import (
    FIELDS_BY_TOKEN,
    TOKEN_RE,
    Token,
    find_tokens,
    substitute,
    unknown_token_message,
    unknown_tokens,
    values_for,
)
from apps.bulk_email.models import BulkEmail, BulkEmailRecipient
from apps.bulk_email.richtext import html_to_text, sanitize
from caldart.mail import contact_email, org_name

#: The template pair a copy is built from.
TEMPLATE = "bulk_email"

#: The pass-through template pair a built copy is sent through: each renders the
#: ``text`` or ``html`` it is given, unchanged.
COPY_TEMPLATE = "bulk_email_copy"

#: The email log's purpose for every copy.
PURPOSE = "bulk_email"

#: The longest preheader, the line a mail program shows beside the subject.
PREHEADER_LENGTH = 90

#: Why a token whose HTML and plain text differ is refused: its braces hold
#: formatting, such as bold applied to half of it, or a character a field cannot.
RETYPE_MESSAGE = (
    "{written} has formatting or an angle bracket inside its braces, so it cannot be "
    "filled in. Delete it and put it in again with Insert field."
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


def render_copy(bulk: BulkEmail, recipient: BulkEmailRecipient) -> RenderedCopy:
    """``recipient``'s copy of ``bulk``, filled in with the values stored on the row.

    The row's ``values`` are the ones the copy went out with (:func:`fill_values`), so
    a copy rebuilt after the person's profile changed reads as it was sent.  A token
    whose value the row does not hold is filled in as empty, so its fallback stands.
    """
    values = {name: recipient.values.get(name, "") for name in message_tokens(bulk)}
    return render_message(bulk.subject, bulk.body, values)


def render_message(subject: str, body: str, values: Mapping[str, str] | None) -> RenderedCopy:
    """A copy of the message ``subject`` and ``body`` with ``values`` filled in.

    ``body`` is sanitized first.  The HTML body takes each value HTML-escaped, and
    percent-encoded inside a link's or an image's address; the plain-text body and the
    subject take each value as it is, with a line break in a subject value read as a
    space.  ``values`` of ``None`` leaves every token as written, which is how the
    history shows a message.  Both bodies carry the organization's name and contact
    address as they are now.
    """
    clean = sanitize(body)
    text = html_to_text(clean)
    if values is not None:
        flat = {name: " ".join(value.splitlines()) for name, value in values.items()}
        subject = substitute(subject, flat, escape=False)
        text = substitute(text, values, escape=False)
        clean = substitute(clean, values, escape=True)
    context: dict[str, object] = {
        "org_name": org_name(),
        "contact_email": contact_email(),
        "subject": subject,
        "body_text": text,
        # Sanitized above, and every value in it escaped: safe to put in as it is.
        "body_html": mark_safe(clean),  # noqa: S308 - sanitized by nh3 just above
        "preheader": " ".join(text.split())[:PREHEADER_LENGTH],
    }
    return RenderedCopy(
        subject=subject,
        text=render_to_string(f"emails/{TEMPLATE}.txt", context),
        html=render_to_string(f"emails/{TEMPLATE}.html", context),
    )


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

    ``body`` is sanitized first.  It is refused for its first token the catalog does
    not have, in the HTML or in the plain text derived from it, with
    :func:`apps.bulk_email.fields.unknown_token_message`; and for a token the two
    parts would not fill in alike, with :func:`retype_message`: a token the plain
    text holds but the HTML does not, because formatting splits it
    (``<strong>{first</strong>_name}``), or a token in the HTML's text the plain text
    does not hold, because its fallback holds an angle bracket.
    """
    clean = sanitize(body)
    text = html_to_text(clean)
    unknown = unknown_tokens(clean) or unknown_tokens(text)
    if len(unknown) > 0:
        return unknown_token_message(unknown[0])
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
