"""The checks a bulk email gets before it goes, and how a send treats them.

``apps.bulk_email.checks.run_checks`` lists errors (no subject, no message, a token that
cannot be filled in, a ``Reply-To`` that is not an address) and warnings (a field empty
for most of the batch, placeholder text, pictures without a description or too wide, and
links that do not load or do not use ``https``).  Links are fetched with ``httpx``,
mocked here with ``respx``, and the host is resolved by the check itself, faked here, so
a link into a private network is refused before anything connects.  ``POST
/bulk-email/{id}/checks`` answers the findings, and **Send** refuses errors but not
warnings.
"""

from __future__ import annotations

import asyncio
import socket
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import httpx
import pytest
import respx
from django.core.cache import cache
from pytest_django import Settings
from rest_framework.test import APIClient

from apps.accounts.roles import DART_LEADER, MANAGEMENT, SYSTEM_ADMIN
from apps.bulk_email import checks, links
from apps.bulk_email.checks import (
    EMPTY_FIELD,
    IMAGE_ALT,
    IMAGE_WIDE,
    LINK_BROKEN,
    LINK_INSECURE,
    LINK_PRIVATE,
    LINK_UNCHECKED,
    LINKS_SKIPPED,
    NO_BODY,
    NO_SUBJECT,
    PLACEHOLDER,
    REPLY_TO,
    UNFILLABLE,
    Finding,
    Level,
    run_checks,
)
from apps.bulk_email.links import Problem
from apps.bulk_email.models import BulkEmail, BulkEmailImage, BulkEmailStatus
from apps.members.models import MemberProfile
from tests.conftest import role_matrix
from tests.factories import (
    BulkEmailFactory,
    DartFactory,
    add_to_batch,
    make_dart_leader,
    make_person,
)

if TYPE_CHECKING:
    from apps.accounts.models import User

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 4, 6, 17, 0, tzinfo=UTC)

#: The address every public host here resolves to, and the one ``example.org`` does.
PUBLIC = "93.184.216.34"

#: This server's own public address, which ``caldart.example.org`` resolves to.
SITE_ADDRESS = "93.184.216.50"

#: What each host the tests link to resolves to.
HOSTS: dict[str, list[str]] = {
    "example.org": [PUBLIC],
    "plain.example.org": [PUBLIC],
    "internal.test": ["10.0.0.5"],
    "both.example.org": [PUBLIC, "127.0.0.1"],
    "caldart.example.org": [SITE_ADDRESS],
    "alias.example.org": [SITE_ADDRESS],
}


def message(*paragraphs: str) -> str:
    """A message of ``paragraphs``, each its own ``<p>``."""
    return "".join(f"<p>{paragraph}</p>" for paragraph in paragraphs)


def codes(findings: list[Finding]) -> list[str]:
    """The code of each finding, in order."""
    return [finding.code for finding in findings]


def findings_for(body: str, subject: str = "Spring safety seminar") -> list[Finding]:
    """What the checks find in a draft of ``subject`` and ``body`` with an empty batch."""
    bulk = BulkEmailFactory(subject=subject, body=body, reply_to="pat@example.org")
    return run_checks(bulk)


@pytest.fixture(autouse=True)
def dns(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[str]]:
    """Resolve the hosts of :data:`HOSTS` without the network; any other is unknown."""
    table = dict(HOSTS)

    def resolve(host: str, port: int) -> list[str]:
        if host in table:
            return table[host]
        raise socket.gaierror(socket.EAI_NONAME, "Name or service not known")

    monkeypatch.setattr(links, "resolve", resolve)
    return table


@pytest.fixture
def web() -> Iterator[respx.Router]:
    """Every web request mocked; one nobody mocked fails the test."""
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        yield router


# -- errors -----------------------------------------------------------------------
def test_a_complete_email_has_no_findings(web: respx.Router) -> None:
    """A subject, a message, and a valid ``Reply-To``, with no links: nothing to say."""
    assert findings_for(message("Join us at Livermore.")) == []


def test_an_empty_subject_is_an_error() -> None:
    """A blank subject stops the send."""
    assert findings_for(message("Hello."), subject="  ") == [
        Finding(NO_SUBJECT, Level.ERROR, checks.NO_SUBJECT_MESSAGE)
    ]


def test_a_message_of_empty_paragraphs_is_an_error() -> None:
    """A message that reads as no text stops the send."""
    assert findings_for("<p> </p><p></p>") == [
        Finding(NO_BODY, Level.ERROR, checks.NO_BODY_MESSAGE)
    ]


def test_an_unknown_token_is_an_error() -> None:
    """A field the catalog lacks is refused as a save words it."""
    found = findings_for(message("Dear {nickname},"))
    assert (codes(found), found[0].message.startswith("{nickname} is not a recipient field")) == (
        [UNFILLABLE],
        True,
    )


def test_a_reply_to_that_is_not_an_address_is_an_error(management: User) -> None:
    """The address replies would go to must be one."""
    bulk = BulkEmailFactory(sender=management, reply_to="")
    BulkEmail.objects.filter(pk=bulk.pk).update(reply_to="not an address")
    bulk.refresh_from_db()
    assert codes(run_checks(bulk)) == [REPLY_TO]


def test_errors_come_before_warnings() -> None:
    """The findings that stop the send lead the list."""
    found = findings_for(message("TODO: write this."), subject="")
    assert [finding.level for finding in found] == [Level.ERROR, Level.WARNING]


# -- a field empty for most of the batch ---------------------------------------------
@pytest.fixture
def three_people(management: User) -> BulkEmail:
    """A draft greeting by ``{dart_name}`` three people, two of them with no DART."""
    bulk = BulkEmailFactory(
        sender=management, body=message("Your DART is {dart_name}."), reply_to=""
    )
    people = [make_person(f"p{index}@example.test", f"P{index}") for index in range(3)]
    MemberProfile.objects.filter(user__in=people[:2]).update(dart=None)
    add_to_batch(bulk, *people)
    return bulk


def test_a_field_empty_for_most_of_the_batch_is_a_warning(three_people: BulkEmail) -> None:
    """Two of three people have no DART: the warning says so with the counts."""
    assert run_checks(three_people) == [
        Finding(
            EMPTY_FIELD,
            Level.WARNING,
            "{dart_name} is empty for 2 of 3 people who receive this email, so their "
            "copies show nothing there. Add words to show instead, as in "
            "{dart_name|other words}, or take it out.",
        )
    ]


def test_a_field_empty_for_half_the_batch_is_not_a_warning(three_people: BulkEmail) -> None:
    """Exactly half is not most: one of two people without a DART passes."""
    three_people.recipients.filter(email="p0@example.test").delete()
    assert run_checks(three_people) == []


def test_a_field_with_a_fallback_is_not_a_warning(three_people: BulkEmail) -> None:
    """A fallback fills the gap, so an empty value does not matter."""
    BulkEmail.objects.filter(pk=three_people.pk).update(
        body=message("Your DART is {dart_name|not chosen yet}.")
    )
    three_people.refresh_from_db()
    assert run_checks(three_people) == []


def test_only_people_who_receive_a_copy_count(three_people: BulkEmail) -> None:
    """Somebody skipped is not counted: two receive it and one of them lacks a DART."""
    skipped = three_people.recipients.get(email="p0@example.test").user
    assert skipped is not None
    skipped.is_active = False
    skipped.save(update_fields=["is_active"])
    assert run_checks(three_people) == []


# -- placeholders ---------------------------------------------------------------------
@pytest.mark.parametrize(
    ("text", "found"),
    [
        ("TODO: the date.", "TODO"),
        ("Meet at xxx on Saturday.", "xxx"),
        ("Lorem ipsum dolor sit amet.", "Lorem ipsum"),
        ("Bring [Insert item here].", "[Insert"),
    ],
    ids=["todo", "xxx", "lorem-ipsum", "insert"],
)
def test_placeholder_text_is_a_warning(text: str, found: str) -> None:
    """Each placeholder is named as written, case ignored when finding it."""
    assert findings_for(message(text)) == [
        Finding(PLACEHOLDER, Level.WARNING, checks.PLACEHOLDER_MESSAGE.format(found=found))
    ]


def test_a_placeholder_in_the_subject_is_a_warning() -> None:
    """The subject is read too."""
    assert codes(findings_for(message("Hello."), subject="TODO subject")) == [PLACEHOLDER]


def test_words_that_only_contain_a_placeholder_pass() -> None:
    """``todos`` and ``XXXL`` are words of their own, not placeholders."""
    assert findings_for(message("Todos los pilotos need XXXL shirts.")) == []


# -- pictures -------------------------------------------------------------------------
def test_a_picture_without_a_description_is_a_warning() -> None:
    """A picture pasted in with no ``alt`` is caught, though the editor took it."""
    found = findings_for(message("The ramp:", '<img src="https://example.org/a.png">'))
    assert found == [
        Finding(
            IMAGE_ALT,
            Level.WARNING,
            "1 picture has no description for people who cannot see pictures. Delete it "
            "and put it in again with the Image button, which asks for one.",
        )
    ]


def test_pictures_with_blank_descriptions_are_counted_together() -> None:
    """Two pictures, one with a blank ``alt``, make one warning naming both."""
    found = findings_for(
        message(
            "Two pictures:",
            '<img src="https://example.org/a.png" alt=" ">',
            '<img src="https://example.org/b.png">',
        )
    )
    assert found[0].message.startswith("2 pictures have no description")


def test_a_picture_with_a_description_passes() -> None:
    """A described picture of a modest width says nothing."""
    assert findings_for(message('<img src="https://example.org/a.png" alt="A Cessna 172">')) == []


def test_a_picture_given_too_wide_a_width_is_a_warning(settings: Settings) -> None:
    """A ``width`` past ``BULK_EMAIL_IMAGE_MAX_WIDTH`` is too wide for an email."""
    settings.BULK_EMAIL_IMAGE_MAX_WIDTH = 1200
    found = findings_for(message('<img src="https://example.org/a.png" alt="Ramp" width="1500">'))
    assert found == [
        Finding(
            IMAGE_WIDE,
            Level.WARNING,
            "1 picture is wider than 1200 pixels, too wide for many mail programs. "
            "Replace it with a smaller one.",
        )
    ]


def test_an_uploaded_picture_stored_too_wide_is_a_warning(settings: Settings) -> None:
    """A picture the editor uploaded is measured by the width it was stored at."""
    settings.BULK_EMAIL_IMAGE_MAX_WIDTH = 100
    BulkEmailImage.objects.create(file="bulk-email/ramp.png", width=200, height=100)
    src = f"{settings.SITE_URL}/media/bulk-email/ramp.png"
    assert codes(findings_for(message(f'<img src="{src}" alt="Ramp" width="80">'))) == [IMAGE_WIDE]


# -- links ----------------------------------------------------------------------------
def test_a_link_that_loads_passes(web: respx.Router) -> None:
    """A ``HEAD`` answered 200 says nothing."""
    web.head(host=PUBLIC, path="/ok").respond(200)
    assert findings_for(message('<a href="https://example.org/ok">Go</a>')) == []


def test_a_link_is_fetched_at_the_address_checked(web: respx.Router) -> None:
    """The request goes to the resolved address, with the link's host as Host and SNI."""
    route = web.head(host=PUBLIC, path="/ok").respond(200)
    findings_for(message('<a href="https://example.org/ok">Go</a>'))
    request = route.calls.last.request
    assert (request.headers["host"], request.extensions["sni_hostname"]) == (
        "example.org",
        "example.org",
    )


def test_a_link_refusing_head_is_tried_with_get(web: respx.Router) -> None:
    """A site that refuses ``HEAD`` but serves ``GET`` passes."""
    web.head(host=PUBLIC, path="/page").respond(405)
    web.get(host=PUBLIC, path="/page").respond(200)
    assert findings_for(message('<a href="https://example.org/page">Go</a>')) == []


def test_a_link_that_answers_404_is_a_warning(web: respx.Router) -> None:
    """A page that is gone is reported by the class of the site's answer, not its code."""
    web.head(host=PUBLIC, path="/gone").respond(404)
    web.get(host=PUBLIC, path="/gone").respond(404)
    assert findings_for(message('<a href="https://example.org/gone">Go</a>')) == [
        Finding(
            LINK_BROKEN,
            Level.WARNING,
            "This link does not load (the site answered with a 4xx error): "
            "https://example.org/gone",
        )
    ]


def test_a_link_that_answers_500_is_a_warning(web: respx.Router) -> None:
    """A server error is a link that does not load."""
    web.head(host=PUBLIC, path="/error").respond(500)
    web.get(host=PUBLIC, path="/error").respond(503)
    found = findings_for(message('<a href="https://example.org/error">Go</a>'))
    assert found[0].message == (
        "This link does not load (the site answered with a 5xx error): https://example.org/error"
    )


def test_a_link_that_times_out_is_a_warning(web: respx.Router) -> None:
    """A site that does not answer in time is reported as such."""
    web.head(host=PUBLIC, path="/slow").mock(side_effect=httpx.ConnectTimeout("slow"))
    assert findings_for(message('<a href="https://example.org/slow">Go</a>')) == [
        Finding(
            LINK_BROKEN,
            Level.WARNING,
            "This link timed out. Check that it works: https://example.org/slow",
        )
    ]


async def _drip(request: httpx.Request) -> httpx.Response:
    """Answer only after the link's budget has long run out, as a dripping server does."""
    await asyncio.sleep(5)
    return httpx.Response(200)


def test_a_slow_answer_is_cut_off_at_the_link_s_budget(
    web: respx.Router, monkeypatch: pytest.MonkeyPatch
) -> None:
    """However slowly a server answers, the link is dropped at ``LINK_BUDGET_SECONDS``."""
    monkeypatch.setattr(links, "LINK_BUDGET_SECONDS", 0.2)
    web.head(host=PUBLIC, path="/drip").mock(side_effect=_drip)
    started = time.monotonic()
    found = links.check_links(["https://example.org/drip"])
    assert (found, time.monotonic() - started < 2) == ([Problem.TIMEOUT], True)


def test_a_slow_name_lookup_is_cut_off_at_the_link_s_budget(
    monkeypatch: pytest.MonkeyPatch, dns: dict[str, list[str]]
) -> None:
    """A lookup that hangs does not hold the check: it is abandoned at the budget."""
    monkeypatch.setattr(links, "LINK_BUDGET_SECONDS", 0.2)

    def stuck(host: str, port: int) -> list[str]:
        time.sleep(1)
        return [PUBLIC]

    monkeypatch.setattr(links, "resolve", stuck)
    monkeypatch.setattr(links, "own_addresses", frozenset)
    started = time.monotonic()
    found = links.check_links(["https://example.org/"])
    assert (found, time.monotonic() - started < 0.9) == ([Problem.TIMEOUT], True)


def test_links_past_the_run_s_budget_are_not_checked_in_time(
    web: respx.Router, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Once ``RUN_BUDGET_SECONDS`` is spent, every link still out says so."""
    monkeypatch.setattr(links, "RUN_BUDGET_SECONDS", 0.2)
    web.head(host=PUBLIC).mock(side_effect=_drip)
    found = findings_for(message('<a href="https://example.org/a">A</a>'))
    assert found == [
        Finding(
            LINK_UNCHECKED,
            Level.WARNING,
            "This link was not checked in time: https://example.org/a",
        )
    ]


def test_a_link_to_an_unknown_host_is_a_warning(web: respx.Router) -> None:
    """A host that does not resolve cannot be reached."""
    assert findings_for(message('<a href="https://nowhere.example/">Go</a>')) == [
        Finding(
            LINK_BROKEN,
            Level.WARNING,
            "This link does not load: https://nowhere.example/",
        )
    ]


def test_a_link_without_https_is_a_warning_even_when_it_loads(web: respx.Router) -> None:
    """``http`` is reported as not secure, and still checked."""
    web.head(host=PUBLIC, path="/").respond(200)
    assert findings_for(message('<a href="http://plain.example.org/">Go</a>')) == [
        Finding(
            LINK_INSECURE,
            Level.WARNING,
            "This link does not use https, so it is not secure: http://plain.example.org/",
        )
    ]


def test_a_redirect_is_followed(web: respx.Router) -> None:
    """A link that moved, to a page that loads, passes."""
    web.head(host=PUBLIC, path="/old").respond(301, headers={"Location": "/new"})
    web.head(host=PUBLIC, path="/new").respond(200)
    assert findings_for(message('<a href="https://example.org/old">Go</a>')) == []


def test_endless_redirects_are_a_warning(web: respx.Router) -> None:
    """A link that redirects to itself gives up and says so."""
    web.route(host=PUBLIC, path="/loop").respond(302, headers={"Location": "/loop"})
    found = findings_for(message('<a href="https://example.org/loop">Go</a>'))
    assert found[0].message == "This link does not load: https://example.org/loop"


def test_a_malformed_link_is_reported_rather_than_raised(web: respx.Router) -> None:
    """An address the URL parser refuses reads as a link that could not be reached."""
    assert links.check_links(["https://[::1/"]) == [Problem.UNREACHABLE]


# -- links into a private network ------------------------------------------------------
PRIVATE_FINDING = Finding(
    LINK_PRIVATE,
    Level.WARNING,
    "Links into a private network are not checked: https://internal.test/admin",
)


def test_a_link_into_a_private_network_is_not_fetched(web: respx.Router) -> None:
    """A host resolving to a private address is refused before anything connects."""
    route = web.route().respond(200)
    found = findings_for(message('<a href="https://internal.test/admin">Go</a>'))
    assert (found, route.called) == ([PRIVATE_FINDING], False)


def test_a_host_with_any_private_address_is_refused(web: respx.Router) -> None:
    """One public and one loopback address could reach either: refused."""
    route = web.route().respond(200)
    found = findings_for(message('<a href="https://both.example.org/">Go</a>'))
    assert (codes(found), route.called) == ([LINK_PRIVATE], False)


def test_a_redirect_into_a_private_network_is_refused(web: respx.Router) -> None:
    """Every hop is checked: a public page sending the check inside is stopped there."""
    web.head(host=PUBLIC, path="/hop").respond(
        302, headers={"Location": "https://internal.test/admin"}
    )
    inside = web.route(host="10.0.0.5").respond(200)
    found = findings_for(message('<a href="https://example.org/hop">Go</a>'))
    assert (codes(found), inside.called) == ([LINK_PRIVATE], False)


def test_a_host_resolving_to_this_server_is_refused(web: respx.Router, settings: Settings) -> None:
    """Another name for this server is refused like a private address, never fetched."""
    settings.SITE_URL = "https://caldart.example.org"
    route = web.route().respond(200)
    found = findings_for(message('<a href="https://alias.example.org/admin">Go</a>'))
    assert (codes(found), route.called) == ([LINK_PRIVATE], False)


@pytest.mark.parametrize(
    "url",
    ["https://example.org:8443/", "http://example.org:22/", "https://example.org:6379/"],
    ids=["8443", "22", "6379"],
)
def test_a_port_other_than_80_or_443_is_not_fetched(web: respx.Router, url: str) -> None:
    """Only the web's own ports are tried, so the check cannot probe other services."""
    route = web.route().respond(200)
    found = findings_for(message(f'<a href="{url}">Go</a>'))
    assert (found[-1].message, route.called) == (
        f"Links to a port other than 80 or 443 are not checked: {url}",
        False,
    )


def test_a_redirect_to_another_port_is_not_followed(web: respx.Router) -> None:
    """Every hop keeps to ports 80 and 443."""
    web.head(host=PUBLIC, path="/hop").respond(
        302, headers={"Location": "https://example.org:8443/"}
    )
    found = findings_for(message('<a href="https://example.org/hop">Go</a>'))
    assert codes(found) == [LINK_UNCHECKED]


@pytest.mark.parametrize(
    ("address", "expected"),
    [
        (PUBLIC, True),
        ("2606:4700:4700::1111", True),
        ("10.1.2.3", False),
        ("172.16.0.1", False),
        ("192.168.1.1", False),
        ("127.0.0.1", False),
        ("169.254.169.254", False),
        ("100.64.0.1", False),
        ("0.0.0.0", False),  # noqa: S104 - an address under test, not one bound to
        ("224.0.0.1", False),
        ("240.0.0.1", False),
        ("::1", False),
        ("fe80::1", False),
        ("fc00::1", False),
        ("::ffff:127.0.0.1", False),
        ("fec0::1", False),
    ],
    ids=[
        "public",
        "public-v6",
        "private-10",
        "private-172",
        "private-192",
        "loopback",
        "link-local-metadata",
        "shared",
        "unspecified",
        "multicast",
        "reserved",
        "loopback-v6",
        "link-local-v6",
        "unique-local-v6",
        "mapped-loopback",
        "site-local-v6",
    ],
)
def test_only_public_addresses_are_fetched(address: str, expected: bool) -> None:
    """``is_public`` admits the public internet alone."""
    assert links.is_public(address) is expected


# -- links that are not checked --------------------------------------------------------
def test_links_not_on_the_web_are_not_checked(web: respx.Router, settings: Settings) -> None:
    """``mailto:``, this site's own pages, and a link carrying a field are left alone."""
    route = web.route().respond(404)
    found = findings_for(
        message(
            '<a href="mailto:ops@example.org">Write</a>',
            f'<a href="{settings.SITE_URL}/portal/">Sign in</a>',
            '<a href="https://example.org/darts?name={dart_name}">Your DART</a>',
        )
    )
    assert (found, route.called) == ([], False)


def test_each_link_is_checked_once(web: respx.Router) -> None:
    """The same address twice is one check and at most one finding."""
    route = web.head(host=PUBLIC, path="/ok").respond(200)
    findings_for(
        message('<a href="https://example.org/ok">A</a> <a href="https://example.org/ok">B</a>')
    )
    assert route.call_count == 1


def test_links_past_the_limit_are_not_checked(
    web: respx.Router, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Past ``MAX_LINKS`` the rest are skipped, and the findings say so."""
    monkeypatch.setattr(checks, "MAX_LINKS", 1)
    web.head(host=PUBLIC, path="/one").respond(200)
    found = findings_for(
        message('<a href="https://example.org/one">1</a> <a href="https://example.org/two">2</a>')
    )
    assert found == [Finding(LINKS_SKIPPED, Level.WARNING, "Only the first 1 links were checked.")]


# -- the endpoint, and the send --------------------------------------------------------
@pytest.mark.parametrize(("role", "allowed"), role_matrix(MANAGEMENT, SYSTEM_ADMIN))
def test_only_management_runs_the_checks(
    api_client: APIClient,
    all_role_users: dict[str, User],
    management: User,
    role: str,
    allowed: bool,
) -> None:
    """``POST /bulk-email/{id}/checks`` of a manager's email is for CalDART management.

    A DART leader gets a 404 for another sender's email.
    """
    bulk = BulkEmailFactory(sender=management)
    api_client.force_login(all_role_users[role])
    response = api_client.post(f"/api/v1/bulk-email/{bulk.pk}/checks")
    assert response.status_code == (200 if allowed else (404 if role == DART_LEADER else 403))


def test_a_leader_runs_the_checks_on_their_own_draft(api_client: APIClient) -> None:
    """A DART leader is a sender: their own email's checks answer 200."""
    leader = make_dart_leader("lane@example.test", DartFactory(name="Marin"))
    bulk = BulkEmailFactory(sender=leader, dart=leader.profile.dart, reply_to="")
    api_client.force_login(leader)
    assert api_client.post(f"/api/v1/bulk-email/{bulk.pk}/checks").status_code == 200


def test_a_leader_cannot_check_another_leader_s_draft(api_client: APIClient) -> None:
    """Another leader's email is a 404, as every bulk email endpoint answers."""
    lane = make_dart_leader("lane@example.test", DartFactory(name="Marin"))
    nell = make_dart_leader("nell@example.test", DartFactory(name="Napa"))
    bulk = BulkEmailFactory(sender=nell, dart=nell.profile.dart)
    api_client.force_login(lane)
    assert api_client.post(f"/api/v1/bulk-email/{bulk.pk}/checks").status_code == 404


def test_people_outside_a_leader_s_dart_are_not_counted_for_empty_fields() -> None:
    """People the DART limit skips receive nothing, so their empty fields do not count."""
    marin = DartFactory(name="Marin")
    leader = make_dart_leader("lane@example.test", marin)
    bulk = BulkEmailFactory(
        sender=leader, dart=marin, body=message("Your airport is {home_airport}."), reply_to=""
    )
    inside = make_person("ann@example.test", "Ann", dart=marin)
    outside = [make_person(f"o{n}@example.test", "Out", dart=DartFactory()) for n in range(3)]
    MemberProfile.objects.filter(user=inside).update(home_airport_identifier="DVO")
    MemberProfile.objects.filter(user__in=outside).update(home_airport_identifier="")
    add_to_batch(bulk, inside, *outside)
    assert run_checks(bulk) == []


@pytest.fixture
def empty_throttle_cache() -> Iterator[None]:
    """The throttle counters are shared state; no test may inherit them."""
    cache.clear()
    yield
    cache.clear()


@pytest.mark.usefixtures("empty_throttle_cache")
def test_the_checks_are_throttled_per_account(
    management_client: APIClient, management: User, settings: Settings
) -> None:
    """Past ``BULK_EMAIL_CHECKS_THROTTLE_RATE`` a caller is answered 429."""
    settings.BULK_EMAIL_CHECKS_THROTTLE_RATE = "2/min"
    bulk = BulkEmailFactory(sender=management)
    statuses = [
        management_client.post(f"/api/v1/bulk-email/{bulk.pk}/checks").status_code for _ in range(3)
    ]
    assert statuses == [200, 200, 429]


def test_the_endpoint_answers_the_findings(management_client: APIClient, management: User) -> None:
    """Each finding as its code, its level, and its sentence."""
    bulk = BulkEmailFactory(sender=management, body=message("TODO"), reply_to="")
    response = management_client.post(f"/api/v1/bulk-email/{bulk.pk}/checks")
    assert response.json() == [
        {
            "code": PLACEHOLDER,
            "level": "warning",
            "message": checks.PLACEHOLDER_MESSAGE.format(found="TODO"),
        }
    ]


def test_warnings_do_not_stop_a_send(
    management_client: APIClient, management: User, web: respx.Router
) -> None:
    """An email with only warnings queues, and the send fetches no link."""
    route = web.route().respond(404)
    bulk = BulkEmailFactory(
        sender=management,
        body=message("TODO", '<a href="https://example.org/gone">Go</a>'),
        reply_to="",
    )
    add_to_batch(bulk, make_person("ann@example.test"))
    response = management_client.post(f"/api/v1/bulk-email/{bulk.pk}/send", {}, format="json")
    assert (response.json()["status"], route.called) == (BulkEmailStatus.QUEUED, False)


def test_errors_stop_a_send(
    management_client: APIClient, management: User, settings: Settings
) -> None:
    """An error the fields do not already refuse is listed under ``checks``."""
    settings.BULK_EMAIL_REPLY_TO = ""
    bulk = BulkEmailFactory(sender=None, reply_to="")
    add_to_batch(bulk, make_person("ann@example.test"))
    response = management_client.post(f"/api/v1/bulk-email/{bulk.pk}/send", {}, format="json")
    assert (response.status_code, codes_of(response.json()["checks"])) == (400, [REPLY_TO])


def codes_of(findings: list[dict[str, str]]) -> list[str]:
    """The ``code`` of each finding the API answered."""
    return [finding["code"] for finding in findings]
