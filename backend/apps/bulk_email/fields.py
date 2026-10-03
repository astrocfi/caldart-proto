"""Recipient fields: the details of each person a bulk email fills into their copy.

A sender writes a field into the subject or the message as a token, ``{first_name}``,
and each person's copy carries that person's value.  A token may name a fallback
for a person with no value, ``{first_name|friend}``.  :data:`FIELDS` is the whole
catalog; a token naming anything else is unknown, and :func:`unknown_tokens` finds
it so a save, a preview, or a send can refuse it by name.

Filling a token in is a lookup in the catalog, never template rendering: text that
looks like Django's template syntax, ``{{ x }}`` or ``{% y %}``, is not a token and
arrives as written.
"""

from __future__ import annotations

import html
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from urllib.parse import quote

from apps.accounts.models import User
from apps.members.models import MemberProfile, MembershipState
from apps.members.services import membership_of
from caldart.dates import format_display_date

#: A token: a lower-case name of letters, digits, and underscores in braces,
#: optionally followed by ``|`` and a fallback.  The fallback is plain text: no
#: brace, bar, angle bracket, or line break.  A brace doubled on either side is not a
#: token, so ``{{x}}`` stays as written.
TOKEN_RE = re.compile(r"(?<!\{)\{([a-z][a-z0-9_]*)(?:\|([^{}|<>\n]*))?\}(?!\})")

#: One tag of sanitized HTML, its attribute values in double quotes as nh3 writes them.
TAG_RE = re.compile(r'<[a-z][a-z0-9]*(?:\s+[a-z-]+(?:="[^"]*")?)*\s*/?>')

#: A link's or an image's address within a tag: the value is group 1.
URL_ATTRIBUTE_RE = re.compile(r'\s(?:href|src)="([^"]*)"')

#: The characters a value keeps as they are inside an address: ``@`` reads better
#: than ``%40`` in a ``mailto:`` link and means the same.
URL_SAFE = "@"

#: How an unknown token is refused: what it is, and the two ways out.
UNKNOWN_FIELD_MESSAGE = (
    "{token} is not a recipient field. Choose a field from Insert field, or, if "
    "the braces belong in a web address, write them as %7B and %7D: {encoded}."
)


@dataclass(frozen=True)
class Token:
    """One token written in a subject or a message.

    ``name`` is the field it names and ``fallback`` the text that stands in for an
    empty value, ``""`` when the token gives none.
    """

    name: str
    fallback: str


@dataclass(frozen=True)
class Field:
    """One recipient field a sender can fill into a bulk email.

    ``token`` is the name written in braces, ``label`` what the **Insert field** menu
    calls it, ``description`` a sentence saying what it holds, and ``value`` reads
    one person's value, ``""`` when they have none.
    """

    token: str
    label: str
    description: str
    value: Callable[[User], str]


def _profile(user: User) -> MemberProfile | None:
    """Return ``user``'s member profile, or ``None`` for an account without one."""
    try:
        return user.profile
    except MemberProfile.DoesNotExist:
        return None


def _dart_name(user: User) -> str:
    """Return the name of the DART on ``user``'s profile, ``""`` when there is none."""
    profile = _profile(user)
    if profile is None or profile.dart is None:
        return ""
    return profile.dart.name


def _home_airport(user: User) -> str:
    """Return the home airport identifier on ``user``'s profile, ``""`` for none."""
    profile = _profile(user)
    return "" if profile is None else profile.home_airport_identifier


def _plan(user: User) -> str:
    """Return the name of the plan behind ``user``'s membership, ``""`` for none."""
    plan = membership_of(user)["plan"]
    return "" if plan is None else plan


def _membership_status(user: User) -> str:
    """Return ``user``'s membership status as the member list shows it, ``Current``."""
    return MembershipState(membership_of(user)["status"]).label


def _expiration(user: User) -> str:
    """Return when ``user``'s membership runs out, ``MM/DD/YYYY``.

    ``""`` for a lifetime member, a friend, and a donor, none of whom has a date.
    """
    expires_on = membership_of(user)["expires_on"]
    return "" if expires_on is None else format_display_date(expires_on)


#: Every field a bulk email can fill in, in the order the **Insert field** menu lists
#: them.
FIELDS: tuple[Field, ...] = (
    Field("first_name", "First name", "The person's first name.", lambda user: user.first_name),
    Field("last_name", "Last name", "The person's last name.", lambda user: user.last_name),
    Field(
        "full_name",
        "Full name",
        "The person's first and last name together.",
        lambda user: user.get_full_name(),
    ),
    Field("email", "Email address", "The address this copy is sent to.", lambda user: user.email),
    Field("dart_name", "DART", "The name of the person's DART.", _dart_name),
    Field("plan", "Membership plan", "The plan of the person's membership.", _plan),
    Field(
        "membership_status",
        "Membership status",
        "Current, Expired, Friend, or Donor.",
        _membership_status,
    ),
    Field(
        "expiration",
        "Expiration date",
        "When the person's membership runs out, as MM/DD/YYYY.",
        _expiration,
    ),
    Field(
        "home_airport",
        "Home airport",
        "The identifier of the person's home airport, such as LVK.",
        _home_airport,
    ),
)

#: The catalog by token.
FIELDS_BY_TOKEN: dict[str, Field] = {field.token: field for field in FIELDS}


def find_tokens(text: str) -> list[Token]:
    """Return every token written in ``text``, in order, repeats included.

    A token is ``{name}`` or ``{name|fallback}``, the name lower-case letters,
    digits, and underscores, starting with a letter.  The names are not checked
    against the catalog; :func:`unknown_tokens` does that.  Anything else in braces
    -- ``{First Name}``, ``{ name }``, ``{{ name }}``, ``{% if %}`` -- is not a token.
    """
    return [Token(match.group(1), match.group(2) or "") for match in TOKEN_RE.finditer(text)]


def unknown_tokens(text: str) -> list[str]:
    """Return the name of every token in ``text`` the catalog does not have.

    Each name appears once, in the order it is first written.  An empty list means
    every token can be filled in.
    """
    names = [token.name for token in find_tokens(text) if token.name not in FIELDS_BY_TOKEN]
    return list(dict.fromkeys(names))


def unknown_token_message(name: str) -> str:
    """Return why the token ``{name}`` is refused, for a sender to read.

    The message names the token and says how to avoid it: pick a field from the
    menu, or, where braces belong in a web address, percent-encode them, since a
    doubled brace (``{{`` or ``}}``) is left exactly as written and never stands
    for one.
    """
    return UNKNOWN_FIELD_MESSAGE.format(token=f"{{{name}}}", encoded=f"%7B{name}%7D")


def values_for(user: User, tokens: Iterable[str]) -> dict[str, str]:
    """Return ``user``'s value for each field named in ``tokens``, token to value.

    Each name appears once in the answer however often it is given, and a person
    with no value for a field gets ``""``.  A name the catalog does not have raises
    ``KeyError``: check the text with :func:`unknown_tokens` first.  The membership
    fields read the person's terms, so a caller filling in many people passes rows
    that came through ``apps.members.services.with_membership``, with the profile and
    its DART selected, and spends no query per person.
    """
    return {name: FIELDS_BY_TOKEN[name].value(user) for name in dict.fromkeys(tokens)}


def substitute(text: str, values: Mapping[str, str], *, escape: bool) -> str:
    """Return ``text`` with every token replaced by its value from ``values``.

    A token whose value is empty is replaced by its fallback, which is ``""`` when
    it names none.  With ``escape`` true, for the HTML part, each value is
    HTML-escaped, so a name holding ``<b>`` arrives as text, and a value inside a
    link's ``href`` or an image's ``src`` is percent-encoded as well (all but
    ``@``), so ``{dart_name}`` holding a space or ``{email}`` holding a ``+`` makes
    a working address.  The fallback is part of the message and is put in as
    written, except that inside such an address it is percent-encoded too.  A token
    whose name is not in ``values`` is left as written.  Nothing else in ``text`` is
    touched: substitution is a lookup, so template syntax such as ``{{ x }}`` is never
    evaluated.
    """
    in_address = _address_spans(text) if escape else []

    def replace(match: re.Match[str]) -> str:
        """Return the value, or the fallback, that stands in for one token."""
        name = match.group(1)
        if name not in values:
            return match.group(0)
        value = values[name]
        in_url = escape and any(start <= match.start() < end for start, end in in_address)
        if value == "":
            fallback = match.group(2) or ""
            # The fallback is the message's own HTML, entities and all.
            return (
                html.escape(quote(html.unescape(fallback), safe=URL_SAFE)) if in_url else fallback
            )
        if not escape:
            return value
        return html.escape(quote(value, safe=URL_SAFE) if in_url else value)

    return TOKEN_RE.sub(replace, text)


def _address_spans(html_text: str) -> list[tuple[int, int]]:
    """Return where each ``href`` and ``src`` value sits in ``html_text``, start to end.

    Only attributes inside a tag count: text that merely reads ``href="..."`` is
    escaped by the sanitizer and never inside one.
    """
    return [
        (tag.start() + address.start(1), tag.start() + address.end(1))
        for tag in TAG_RE.finditer(html_text)
        for address in URL_ATTRIBUTE_RE.finditer(tag.group(0))
    ]
