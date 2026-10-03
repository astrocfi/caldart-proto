"""The checks a bulk email gets before it goes: mistakes a machine can catch.

:func:`run_checks` lists every finding for one email, each a :class:`Finding` with a
level.  An **error** keeps the email from being sent: a missing subject or message, a
recipient field token that cannot be filled in, or a ``Reply-To`` address that is not
an address.  A **warning** is worth a look but the sender may send anyway: a field
most of the batch has no value for, placeholder text left in, a picture with no
description or too wide for an email, and a link that does not load or does not use
``https``.  **Send** refuses an email with any error (:func:`refuse_on_errors`, which
``apps.bulk_email.drafts.queue`` calls); only warnings come from the network, so the
send runs the error checks alone.

The links are fetched by ``apps.bulk_email.links``, which holds every link and the
whole run to a deadline and never reaches into a private network or this server.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from bs4 import BeautifulSoup
from bs4.element import Tag
from django.conf import settings
from django.db import models

from apps.bulk_email.batch import batch_rows
from apps.bulk_email.fields import TOKEN_RE, find_tokens, values_for
from apps.bulk_email.links import WEB_SCHEMES, Problem, check_links
from apps.bulk_email.models import IMAGE_DIRECTORY, BulkEmail, BulkEmailImage
from apps.bulk_email.render import check_message, message_tokens
from apps.bulk_email.reply_to import reply_to_for, reply_to_problem
from apps.bulk_email.richtext import html_to_text, sanitize
from caldart.exceptions import DomainError

log = logging.getLogger(__name__)


class Level(models.TextChoices):
    """How much a finding matters: an ``error`` stops the send, a ``warning`` does not."""

    ERROR = "error", "Error"
    WARNING = "warning", "Warning"


#: The code of each kind of finding, which the portal may key on.
NO_SUBJECT = "no_subject"
NO_BODY = "no_body"
UNFILLABLE = "unfillable"
REPLY_TO = "reply_to"
EMPTY_FIELD = "empty_field"
PLACEHOLDER = "placeholder"
IMAGE_ALT = "image_alt"
IMAGE_WIDE = "image_wide"
LINK_INSECURE = "link_insecure"
LINK_BROKEN = "link_broken"
LINK_PRIVATE = "link_private"
LINK_UNCHECKED = "link_unchecked"
LINKS_SKIPPED = "links_skipped"

#: Why an email with no subject, or no message, cannot be sent.
NO_SUBJECT_MESSAGE = "Write a subject."
NO_BODY_MESSAGE = "Write the message."

#: A field most of the batch has no value for.
EMPTY_FIELD_MESSAGE = (
    "{token} is empty for {empty} of {people} who receive this email, so their copies "
    "show nothing there. Add words to show instead, as in {example}, or take it out."
)

#: Placeholder text left in the email.
PLACEHOLDER_MESSAGE = 'The email still says "{found}". Replace it before you send.'

#: Pictures with no description, and pictures too wide for an email.
IMAGE_ALT_MESSAGE = (
    "{count} {verb} no description for people who cannot see pictures. Delete {it} and "
    "put {it} in again with the Image button, which asks for one."
)
IMAGE_WIDE_MESSAGE = (
    "{count} {verb} wider than {limit} pixels, too wide for many mail programs. "
    "Replace {it} with {smaller}."
)

#: The link findings; ``{url}`` is the link's address.  They say no more than whether
#: a link loads and the class of a site's refusal, so the check reveals nothing about a
#: host it could be pointed at.
LINK_INSECURE_MESSAGE = "This link does not use https, so it is not secure: {url}"
LINK_MESSAGES: dict[Problem, tuple[str, str]] = {
    Problem.CLIENT_ERROR: (
        LINK_BROKEN,
        "This link does not load (the site answered with a 4xx error): {url}",
    ),
    Problem.SERVER_ERROR: (
        LINK_BROKEN,
        "This link does not load (the site answered with a 5xx error): {url}",
    ),
    Problem.TIMEOUT: (LINK_BROKEN, "This link timed out. Check that it works: {url}"),
    Problem.UNREACHABLE: (LINK_BROKEN, "This link does not load: {url}"),
    Problem.PRIVATE: (LINK_PRIVATE, "Links into a private network are not checked: {url}"),
    Problem.PORT: (
        LINK_UNCHECKED,
        "Links to a port other than 80 or 443 are not checked: {url}",
    ),
    Problem.NOT_IN_TIME: (LINK_UNCHECKED, "This link was not checked in time: {url}"),
}
LINKS_SKIPPED_MESSAGE = "Only the first {limit} links were checked."

#: The most links one run checks.
MAX_LINKS = 20

#: Words that mean somebody meant to come back to the text, each with how it is found:
#: whole words for the short ones, case ignored throughout.
PLACEHOLDER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bTODO\b", re.IGNORECASE),
    re.compile(r"\bXXX\b", re.IGNORECASE),
    re.compile(r"lorem ipsum", re.IGNORECASE),
    re.compile(r"\[insert", re.IGNORECASE),
)


@dataclass(frozen=True)
class Finding:
    """One thing the checks found: its ``code``, its ``level``, and a sentence to read."""

    code: str
    level: Level
    message: str


class ChecksFailedError(DomainError):
    """An email the checks found errors in, which therefore cannot be sent.

    ``findings`` are the errors, in the order :func:`run_checks` lists them; the
    message is the first one's.
    """

    def __init__(self, findings: list[Finding]) -> None:
        """Keep ``findings`` and take the first one's message as the exception's."""
        super().__init__(findings[0].message)
        self.findings = findings


def run_checks(bulk: BulkEmail) -> list[Finding]:
    """Every finding for ``bulk`` as it is saved: its errors first, then its warnings.

    The errors are :func:`error_findings`'.  The warnings follow in this order: each
    recipient field that is empty for more than half the people who receive the email
    (only a field written without a fallback anywhere counts), each placeholder left
    in the subject or the message, the pictures without a description and those wider
    than ``BULK_EMAIL_IMAGE_MAX_WIDTH``, and then each link, in the order written:
    one that does not use ``https``, and one that does not load
    (:func:`check_link`).  The empty-field check is skipped while a token cannot be
    filled in, since the errors already say so.
    """
    errors = error_findings(bulk)
    has_token_error = any(finding.code == UNFILLABLE for finding in errors)
    clean = sanitize(bulk.body)
    warnings = [
        *([] if has_token_error else _empty_field_findings(bulk)),
        *_placeholder_findings(bulk.subject, clean),
        *_image_findings(clean),
        *_link_findings(clean),
    ]
    return [*errors, *warnings]


def error_findings(bulk: BulkEmail) -> list[Finding]:
    """The findings that keep ``bulk`` from being sent, in the order a reader fixes them.

    A blank subject (:data:`NO_SUBJECT_MESSAGE`); a message that reads as no text at
    all once sanitized (:data:`NO_BODY_MESSAGE`); the refusal of a token in the
    subject and then in the message, as ``apps.bulk_email.render.check_message`` words
    it; and a ``Reply-To`` address, the one the copies would carry, that is missing or
    not valid (``apps.bulk_email.reply_to.reply_to_problem``).
    """
    findings: list[Finding] = []
    if bulk.subject.strip() == "":
        findings.append(Finding(NO_SUBJECT, Level.ERROR, NO_SUBJECT_MESSAGE))
    if html_to_text(sanitize(bulk.body)).strip() == "":
        findings.append(Finding(NO_BODY, Level.ERROR, NO_BODY_MESSAGE))
    findings.extend(
        Finding(UNFILLABLE, Level.ERROR, problem)
        for problem in check_message(bulk.subject, bulk.body).values()
    )
    problem = reply_to_problem(reply_to_for(bulk))
    if problem is not None:
        findings.append(Finding(REPLY_TO, Level.ERROR, problem))
    return findings


def refuse_on_errors(bulk: BulkEmail) -> None:
    """Raise :class:`ChecksFailedError` when ``bulk`` has any :func:`error_findings`."""
    errors = error_findings(bulk)
    if len(errors) > 0:
        raise ChecksFailedError(errors)


def _empty_field_findings(bulk: BulkEmail) -> list[Finding]:
    """An :data:`EMPTY_FIELD` warning for each field empty for over half the batch.

    Only the people who receive a copy count, with their values as they are now, and
    only a field written at least once without a fallback, since a fallback fills the
    gap.  Nothing is found while nobody receives a copy.
    """
    tokens = [*find_tokens(bulk.subject), *find_tokens(sanitize(bulk.body))]
    bare = {token.name for token in tokens if token.fallback == ""}
    names = [name for name in message_tokens(bulk) if name in bare]
    if len(names) == 0:
        return []
    accounts = [
        row.account for row in batch_rows(bulk) if row.will_receive and row.account is not None
    ]
    if len(accounts) == 0:
        return []
    empty = dict.fromkeys(names, 0)
    for account in accounts:
        for name, value in values_for(account, names).items():
            if value.strip() == "":
                empty[name] += 1
    people = "1 person" if len(accounts) == 1 else f"{len(accounts)} people"
    return [
        Finding(
            EMPTY_FIELD,
            Level.WARNING,
            EMPTY_FIELD_MESSAGE.format(
                token=f"{{{name}}}",
                empty=count,
                people=people,
                example=f"{{{name}|other words}}",
            ),
        )
        for name, count in empty.items()
        if count * 2 > len(accounts)
    ]


def _placeholder_findings(subject: str, clean: str) -> list[Finding]:
    """A :data:`PLACEHOLDER` warning for each placeholder in ``subject`` or ``clean``.

    ``clean`` is the sanitized message, read as its plain text.  Each pattern of
    :data:`PLACEHOLDER_PATTERNS` is reported once, as first written.
    """
    text = f"{subject}\n{html_to_text(clean)}"
    found = [pattern.search(text) for pattern in PLACEHOLDER_PATTERNS]
    return [
        Finding(PLACEHOLDER, Level.WARNING, PLACEHOLDER_MESSAGE.format(found=match.group(0)))
        for match in found
        if match is not None
    ]


def _image_findings(clean: str) -> list[Finding]:
    """The warnings for the pictures in the sanitized message ``clean``.

    One :data:`IMAGE_ALT` warning counts the pictures whose ``alt`` is missing or
    blank, and one :data:`IMAGE_WIDE` warning the pictures wider than
    ``BULK_EMAIL_IMAGE_MAX_WIDTH``: by the ``width`` the message gives a picture, or,
    for one uploaded through the editor, by the width it was stored at.
    """
    images = list(BeautifulSoup(clean, "html.parser").find_all("img"))
    limit = int(settings.BULK_EMAIL_IMAGE_MAX_WIDTH)
    without_alt = sum(1 for image in images if _attribute(image, "alt").strip() == "")
    too_wide = sum(1 for image in images if _image_width(image) > limit)
    findings: list[Finding] = []
    if without_alt > 0:
        message = IMAGE_ALT_MESSAGE.format(
            count=_pictures(without_alt),
            verb="has" if without_alt == 1 else "have",
            it="it" if without_alt == 1 else "them",
        )
        findings.append(Finding(IMAGE_ALT, Level.WARNING, message))
    if too_wide > 0:
        message = IMAGE_WIDE_MESSAGE.format(
            count=_pictures(too_wide),
            verb="is" if too_wide == 1 else "are",
            limit=limit,
            it="it" if too_wide == 1 else "them",
            smaller="a smaller one" if too_wide == 1 else "smaller ones",
        )
        findings.append(Finding(IMAGE_WIDE, Level.WARNING, message))
    return findings


def _pictures(count: int) -> str:
    """``count`` pictures in words: ``1 picture``, ``3 pictures``."""
    return "1 picture" if count == 1 else f"{count} pictures"


def _image_width(image: Tag) -> int:
    """How wide ``image`` is, in pixels, or 0 when nothing says.

    The larger of the ``width`` the message gives it and, for a picture uploaded
    through the editor, the width ``BulkEmailImage`` stored it at.
    """
    given = _attribute(image, "width")
    width = int(given) if given.isdigit() else 0
    path = urlsplit(_attribute(image, "src")).path
    marker = f"/{IMAGE_DIRECTORY}/"
    if marker in path:
        name = f"{IMAGE_DIRECTORY}/{path.rpartition(marker)[2]}"
        stored = BulkEmailImage.objects.filter(file=name).values_list("width", flat=True).first()
        if stored is not None:
            width = max(width, stored)
    return width


def _attribute(tag: Tag, name: str) -> str:
    """``tag``'s attribute ``name`` as one string, ``""`` when it has none."""
    value = tag.get(name)
    if value is None:
        return ""
    return value if isinstance(value, str) else " ".join(value)


def _link_findings(clean: str) -> list[Finding]:
    """The warnings for the web links in the sanitized message ``clean``.

    Each distinct ``http`` or ``https`` link is checked once, in the order written:
    a :data:`LINK_INSECURE` warning when it does not use ``https``, then the problem
    ``apps.bulk_email.links.check_links`` finds with it, worded by
    :data:`LINK_MESSAGES`.  A link to this site itself (``SITE_URL``'s host and port)
    is not checked, nor one whose address holds a recipient field, since each
    person's copy reads it differently.  At most :data:`MAX_LINKS` are checked, with a
    :data:`LINKS_SKIPPED` warning when there were more.
    """
    links = [
        url
        for url in dict.fromkeys(
            _attribute(tag, "href") for tag in BeautifulSoup(clean, "html.parser").find_all("a")
        )
        if urlsplit(url).scheme in WEB_SCHEMES
        and TOKEN_RE.search(url) is None
        and not _is_own_site(url)
    ]
    checked = links[:MAX_LINKS]
    findings: list[Finding] = []
    for url, problem in zip(checked, check_links(checked), strict=True):
        if urlsplit(url).scheme != "https":
            message = LINK_INSECURE_MESSAGE.format(url=url)
            findings.append(Finding(LINK_INSECURE, Level.WARNING, message))
        if problem is not None:
            code, message = LINK_MESSAGES[problem]
            findings.append(Finding(code, Level.WARNING, message.format(url=url)))
    if len(links) > MAX_LINKS:
        message = LINKS_SKIPPED_MESSAGE.format(limit=MAX_LINKS)
        findings.append(Finding(LINKS_SKIPPED, Level.WARNING, message))
    return findings


def _is_own_site(url: str) -> bool:
    """True when ``url`` points at this site: ``SITE_URL``'s host and port."""
    own = urlsplit(str(settings.SITE_URL))
    parts = urlsplit(url)
    try:
        return (parts.hostname, parts.port or _default_port(parts.scheme)) == (
            own.hostname,
            own.port or _default_port(own.scheme),
        )
    except ValueError:
        return False


def _default_port(scheme: str) -> int:
    """The port a web address with no port of its own uses: 443 for https, else 80."""
    return 443 if scheme == "https" else 80
