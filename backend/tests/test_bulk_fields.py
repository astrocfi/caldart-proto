"""Recipient fields: the catalog, finding tokens, each person's values, and filling in.

``apps.bulk_email.fields`` reads ``{name}`` and ``{name|fallback}`` tokens, refuses a
name the catalog does not have, reads each person's values, and fills them in by a
plain lookup, HTML-escaping each value for the HTML part.  ``GET /bulk-email/fields``
lists the catalog for the **Insert field** menu.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import AccountKind
from apps.accounts.roles import DART_LEADER, MANAGEMENT, SYSTEM_ADMIN
from apps.bulk_email.fields import (
    FIELDS,
    Token,
    find_tokens,
    is_in_address,
    substitute,
    unknown_token_message,
    unknown_tokens,
    values_for,
)
from apps.members.models import MembershipPlan
from tests.conftest import role_matrix
from tests.factories import (
    DartFactory,
    MemberProfileFactory,
    UserFactory,
    expire_membership,
    grant_membership,
)

if TYPE_CHECKING:
    from apps.accounts.models import User

pytestmark = pytest.mark.django_db

FIELDS_URL = "/api/v1/bulk-email/fields"

#: Every token the catalog offers, in the menu's order.
CATALOG = [
    "first_name",
    "last_name",
    "full_name",
    "email",
    "dart_name",
    "plan",
    "membership_status",
    "expiration",
    "home_airport",
]


@pytest.fixture
def pat(annual_plan: MembershipPlan, today: date) -> User:
    """A current member, Pat Lee, of the Marin DART at LVK, renewing in 200 days."""
    user = UserFactory(email="pat@example.test", first_name="Pat", last_name="Lee")
    MemberProfileFactory(user=user, dart=DartFactory(name="Marin"), home_airport_identifier="LVK")
    grant_membership(user, annual_plan, days_left=200)
    return user


@pytest.fixture
def blank() -> User:
    """A friend with no name, no profile, and no membership."""
    return UserFactory(
        email="blank@example.test", first_name="", last_name="", kind=AccountKind.FRIEND
    )


# --------------------------------------------------------------------------
# The catalog and its endpoint
# --------------------------------------------------------------------------
def test_the_catalog_offers_every_field_in_order() -> None:
    """The catalog's tokens are the nine fields, in the menu's order."""
    assert [field.token for field in FIELDS] == CATALOG


@pytest.mark.parametrize(("role", "allowed"), role_matrix(DART_LEADER, MANAGEMENT, SYSTEM_ADMIN))
def test_only_bulk_senders_read_the_fields(
    api_client: APIClient, all_role_users: dict[str, User], role: str, allowed: bool
) -> None:
    """``GET /bulk-email/fields`` is for DART leaders, CalDART management, and admins."""
    api_client.force_login(all_role_users[role])
    assert api_client.get(FIELDS_URL).status_code == (200 if allowed else 403)


def test_an_anonymous_caller_cannot_read_the_fields(api_client: APIClient) -> None:
    """A caller who is not signed in is a 401."""
    assert api_client.get(FIELDS_URL).status_code == 401


def test_the_fields_endpoint_lists_the_catalog(api_client: APIClient, management: User) -> None:
    """Each field comes with its token, its label, and its description."""
    api_client.force_login(management)
    body = api_client.get(FIELDS_URL).json()
    assert body == [
        {"token": field.token, "label": field.label, "description": field.description}
        for field in FIELDS
    ]


# --------------------------------------------------------------------------
# Finding tokens
# --------------------------------------------------------------------------
def test_tokens_are_found_in_order_with_their_fallbacks() -> None:
    """``{name}`` and ``{name|fallback}`` are tokens, repeats included."""
    text = "Hi {first_name|friend}, {dart_name} misses you, {first_name}."
    assert find_tokens(text) == [
        Token("first_name", "friend"),
        Token("dart_name", ""),
        Token("first_name", ""),
    ]


@pytest.mark.parametrize(
    "text",
    [
        "{{ first_name }}",
        "{{first_name}}",
        "{% if first_name %}yes{% endif %}",
        "{First_Name}",
        "{ first_name }",
        "{first name}",
        "{1st}",
        "{}",
        "{first_name|a<b>c}",
    ],
    ids=[
        "django-variable",
        "django-variable-unspaced",
        "django-tag",
        "capitals",
        "spaces",
        "two-words",
        "leading-digit",
        "empty",
        "fallback-with-markup",
    ],
)
def test_anything_else_in_braces_is_not_a_token(text: str) -> None:
    """Template syntax and other braced text are not tokens."""
    assert find_tokens(text) == []


def test_unknown_tokens_are_named_once_each_in_order() -> None:
    """Every name the catalog lacks is listed once, in the order first written."""
    text = "{nickname} {first_name} {shoe_size|9} {nickname}"
    assert unknown_tokens(text) == ["nickname", "shoe_size"]


def test_a_message_of_known_tokens_has_no_unknown_ones() -> None:
    """Text using only catalog fields, and template syntax, has nothing unknown."""
    assert unknown_tokens("{first_name} {{ nickname }} {% now %}") == []


# --------------------------------------------------------------------------
# Each person's values
# --------------------------------------------------------------------------
def test_each_field_reads_the_persons_value(pat: User, today: date) -> None:
    """Every catalog field reads Pat's own detail."""
    expiration = (today + timedelta(days=200)).strftime("%m/%d/%Y")
    assert values_for(pat, CATALOG) == {
        "first_name": "Pat",
        "last_name": "Lee",
        "full_name": "Pat Lee",
        "email": "pat@example.test",
        "dart_name": "Marin",
        "plan": "Annual",
        "membership_status": "Current",
        "expiration": expiration,
        "home_airport": "LVK",
    }


def test_a_person_without_details_reads_empty_values(blank: User) -> None:
    """A friend with no name, profile, or membership reads blank but for two fields."""
    assert values_for(blank, CATALOG) == {
        "first_name": "",
        "last_name": "",
        "full_name": "",
        "email": "blank@example.test",
        "dart_name": "",
        "plan": "",
        "membership_status": "Friend",
        "expiration": "",
        "home_airport": "",
    }


def test_a_lapsed_member_reads_expired_with_the_date_it_ran_out(
    annual_plan: MembershipPlan, today: date
) -> None:
    """An expired member's status is *Expired* and the expiration the day it lapsed."""
    user = UserFactory(email="gone@example.test")
    expire_membership(user, annual_plan, days_ago=30)
    ended = (today - timedelta(days=30)).strftime("%m/%d/%Y")
    assert values_for(user, ["membership_status", "expiration"]) == {
        "membership_status": "Expired",
        "expiration": ended,
    }


def test_a_lifetime_member_has_no_expiration(life_plan: MembershipPlan) -> None:
    """A lifetime term never runs out, so the expiration is empty."""
    user = UserFactory(email="life@example.test")
    grant_membership(user, life_plan)
    user.memberships.update(ends_on=None)
    assert values_for(user, ["plan", "expiration"]) == {"plan": "Life", "expiration": ""}


def test_a_profile_without_a_dart_reads_an_empty_dart_name() -> None:
    """A member whose profile names no DART has an empty ``dart_name``."""
    user = UserFactory(email="nodart@example.test")
    MemberProfileFactory(user=user, dart=None)
    assert values_for(user, ["dart_name"]) == {"dart_name": ""}


def test_values_are_read_only_for_the_tokens_asked_once_each(pat: User) -> None:
    """A repeated name appears once, and fields not asked for are not read."""
    assert values_for(pat, ["first_name", "first_name"]) == {"first_name": "Pat"}


def test_reading_an_unknown_field_raises(pat: User) -> None:
    """A name the catalog lacks is a ``KeyError`` naming it."""
    with pytest.raises(KeyError, match="nickname"):
        values_for(pat, ["nickname"])


# --------------------------------------------------------------------------
# Filling in
# --------------------------------------------------------------------------
@pytest.mark.parametrize("token", CATALOG)
def test_each_field_fills_in_the_subject(pat: User, token: str) -> None:
    """Every field's token in a subject is replaced by the person's value."""
    values = values_for(pat, [token])
    assert substitute(f"For {{{token}}}", values, escape=False) == f"For {values[token]}"


@pytest.mark.parametrize("token", CATALOG)
def test_each_field_fills_in_the_html_body(pat: User, token: str) -> None:
    """Every field's token in the HTML body is replaced by the person's value."""
    values = values_for(pat, [token])
    assert substitute(f"<p>{{{token}}}</p>", values, escape=True) == f"<p>{values[token]}</p>"


def test_the_fallback_stands_in_for_an_empty_value() -> None:
    """An empty value is replaced by the token's fallback."""
    assert substitute("Hi {first_name|friend}!", {"first_name": ""}, escape=False) == ("Hi friend!")


def test_the_fallback_is_unused_when_there_is_a_value() -> None:
    """A value wins over the fallback."""
    assert substitute("Hi {first_name|friend}!", {"first_name": "Pat"}, escape=False) == ("Hi Pat!")


def test_an_empty_value_with_no_fallback_leaves_nothing() -> None:
    """With no fallback, an empty value is an empty string."""
    assert substitute("DART: {dart_name}.", {"dart_name": ""}, escape=False) == "DART: ."


def test_values_are_html_escaped_in_the_html_part() -> None:
    """A name holding markup arrives as text in the HTML part."""
    values = {"first_name": '<b>Pat</b> & "Co"'}
    assert substitute("<p>Hi {first_name}</p>", values, escape=True) == (
        "<p>Hi &lt;b&gt;Pat&lt;/b&gt; &amp; &quot;Co&quot;</p>"
    )


def test_values_are_left_as_they_are_in_the_text_part() -> None:
    """Without escaping, for the text part and the subject, a value is put in as it is."""
    values = {"first_name": "<b>Pat</b> & Co"}
    assert substitute("Hi {first_name}", values, escape=False) == "Hi <b>Pat</b> & Co"


def test_template_syntax_arrives_literally() -> None:
    """``{{ }}`` and ``{% %}`` are never evaluated, and stay exactly as written."""
    text = "{{ first_name }} {% if x %}{{x}}{% endif %} {first_name}"
    assert substitute(text, {"first_name": "Pat"}, escape=True) == (
        "{{ first_name }} {% if x %}{{x}}{% endif %} Pat"
    )


def test_a_token_without_a_value_is_left_as_written() -> None:
    """A token whose name has no value given is not touched."""
    assert substitute("{nickname} {first_name}", {"first_name": "Pat"}, escape=False) == (
        "{nickname} Pat"
    )


def test_a_value_that_looks_like_a_token_is_not_filled_in_again() -> None:
    """Filling in is one pass: a value holding a token is put in literally."""
    values = {"first_name": "{email}", "email": "pat@example.test"}
    assert substitute("{first_name}", values, escape=False) == "{email}"


@pytest.mark.parametrize(
    ("html", "values", "expected"),
    [
        (
            '<p><a href="https://caldart.org/darts?name={dart_name}">{dart_name}</a></p>',
            {"dart_name": "Marin & Napa"},
            '<p><a href="https://caldart.org/darts?name=Marin%20%26%20Napa">'
            "Marin &amp; Napa</a></p>",
        ),
        (
            '<p><a href="mailto:{email}">Write</a></p>',
            {"email": "pat+dart@example.test"},
            '<p><a href="mailto:pat%2Bdart@example.test">Write</a></p>',
        ),
        (
            '<img src="https://caldart.org/badge/{first_name}.png" alt="{first_name}">',
            {"first_name": 'Pat "Ace"'},
            '<img src="https://caldart.org/badge/Pat%20%22Ace%22.png" alt="Pat &quot;Ace&quot;">',
        ),
    ],
    ids=["href-query", "mailto", "img-src-but-not-alt"],
)
def test_a_value_inside_an_address_is_percent_encoded(
    html: str, values: dict[str, str], expected: str
) -> None:
    """In an ``href`` or ``src`` a value is URL-encoded; elsewhere only HTML-escaped."""
    assert substitute(html, values, escape=True) == expected


def test_text_that_reads_like_an_address_is_not_percent_encoded() -> None:
    """Outside a tag, ``href="..."`` is plain text and its value is only escaped."""
    assert substitute('<p>href="{first_name}"</p>', {"first_name": "A B"}, escape=True) == (
        '<p>href="A B"</p>'
    )


def test_doubled_braces_in_an_address_are_left_as_written() -> None:
    """``{{`` and ``}}`` are never tokens, inside an address or out."""
    html = '<p><a href="https://example.org/{{id}}">x</a></p>'
    assert (unknown_tokens(html), substitute(html, {}, escape=True)) == ([], html)


def test_the_unknown_token_message_says_how_to_avoid_it() -> None:
    """The refusal names the token and offers the menu or taking the braces out."""
    assert unknown_token_message("nickname") == (
        "{nickname} is not one of the fields. Pick a field from Insert field, or take out "
        "the braces."
    )


def test_the_unknown_token_message_in_an_address_says_how_to_write_braces() -> None:
    """Inside a web address, the refusal offers percent-encoded braces instead."""
    assert unknown_token_message("id", in_address=True) == (
        "{id} is not one of the fields. Pick a field from Insert field, or, if the "
        "braces belong in the web address, write them as %7B and %7D: %7Bid%7D."
    )


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ('<p><a href="https://example.org/{id}">x</a></p>', True),
        ('<p><img src="https://example.org/{id}.png" alt="x"></p>', True),
        ("<p>Order {id}</p>", False),
        ('<p><a href="https://example.org/">{id}</a></p>', False),
    ],
    ids=["link", "picture", "text", "link-words"],
)
def test_a_token_is_in_an_address_only_inside_href_or_src(html: str, expected: bool) -> None:
    """``is_in_address`` answers True only for a token inside an address."""
    assert is_in_address(html, "id") is expected


def test_a_fallback_inside_an_address_is_percent_encoded() -> None:
    """With an empty value, the fallback inside an ``href`` is percent-encoded."""
    html = '<p><a href="https://e.org/?d={dart_name|Bay Area}">{dart_name|Bay Area}</a></p>'
    assert substitute(html, {"dart_name": ""}, escape=True) == (
        '<p><a href="https://e.org/?d=Bay%20Area">Bay Area</a></p>'
    )
