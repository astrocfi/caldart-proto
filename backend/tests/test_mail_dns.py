"""The mail delivery check: SPF, DKIM, DMARC, and the bounce address's alignment.

``apps.mail.dns_check.check_mail_dns`` reads the records over DNS; these tests replace
``dns.resolver.Resolver`` with a fake that answers from a dictionary, so the suite
never makes a real query.  ``GET /mail/delivery-check`` serves the report to CalDART
management and system administrators, and ``manage.py check_mail_dns`` prints it.  See
``docs/developer/api-system.rst`` and ``docs/developer/deployment.rst``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from io import StringIO
from typing import Any

import dns.exception
import dns.rdata
import dns.resolver
import pytest
from django.core.cache import cache
from django.core.management import CommandError, call_command
from freezegun import freeze_time
from pytest_django import Settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import MANAGEMENT, SYSTEM_ADMIN
from apps.mail import dns_check
from apps.mail.dns_check import (
    ALIGNMENT_NAME,
    DKIM_NAME,
    DMARC_NAME,
    SPF_NAME,
    DnsFinding,
    DnsReport,
    DnsStatus,
    check_mail_dns,
)
from tests.conftest import role_matrix

pytestmark = pytest.mark.django_db

URL = "/api/v1/mail/delivery-check"
NOW = datetime(2026, 10, 3, 15, 0, tzinfo=UTC)
SMTP_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

#: A zone entry: the record texts at one name and type, or the error a lookup raises.
type Zone = dict[tuple[str, str], list[str] | Exception]

GOOD_ZONE: Zone = {
    ("example.org", "TXT"): ["v=spf1 include:_spf.relay.net ~all"],
    ("_spf.relay.net", "TXT"): ["v=spf1 ip4:192.0.2.0/24 -all"],
    ("smtp.relay.net", "A"): ["192.0.2.25"],
    ("mail._domainkey.example.org", "TXT"): ["v=DKIM1; k=rsa; p=MIGfMA0GCSqGSIb3DQEBAQUAA4"],
    ("_dmarc.example.org", "TXT"): ["v=DMARC1; p=reject; rua=mailto:dmarc@example.org"],
}


def _rdata_text(rdtype: str, text: str) -> str:
    """``text`` as zone-file rdata: a TXT value is quoted in 255-character strings."""
    if rdtype != "TXT":
        return text
    return " ".join(f'"{text[i : i + 255]}"' for i in range(0, len(text), 255))


class FakeResolver:
    """Answers ``resolve`` from ``zone``; a name or type not in it does not exist."""

    zone: Zone = {}
    queries: list[tuple[str, str]] = []
    instances: list[FakeResolver] = []

    def __init__(self) -> None:
        """Start with no timeout set, as the real resolver's defaults are replaced."""
        self.timeout = 0.0
        self.lifetime = 0.0
        type(self).instances.append(self)

    def resolve(self, qname: str, rdtype: str = "A", **_: Any) -> list[dns.rdata.Rdata]:
        """Answer from the zone, or raise the error it holds for ``qname``."""
        name = qname.rstrip(".").lower()
        type(self).queries.append((name, rdtype))
        answer = type(self).zone.get((name, rdtype))
        if answer is None:
            raise dns.resolver.NXDOMAIN
        if isinstance(answer, Exception):
            raise answer
        return [dns.rdata.from_text("IN", rdtype, _rdata_text(rdtype, text)) for text in answer]


@pytest.fixture
def dns_zone(monkeypatch: pytest.MonkeyPatch) -> Zone:
    """The zone the patched resolver answers from, starting as ``GOOD_ZONE``.

    Replaces ``dns.resolver.Resolver`` for the test and clears the report cache; the
    lookups made are in ``FakeResolver.queries``.
    """
    zone: Zone = dict(GOOD_ZONE)
    FakeResolver.zone = zone
    FakeResolver.queries = []
    FakeResolver.instances = []
    monkeypatch.setattr(dns.resolver, "Resolver", FakeResolver)
    cache.clear()
    return zone


@pytest.fixture
def management_client(api_client: APIClient, management: User) -> APIClient:
    """``api_client`` signed in as a member of CalDART management."""
    api_client.force_login(management)
    return api_client


@pytest.fixture(autouse=True)
def mail_settings(settings: Settings) -> None:
    """Send from ``example.org`` through ``smtp.relay.net``, signing with ``mail``."""
    settings.DEFAULT_FROM_EMAIL = "CalDART <noreply@example.org>"
    settings.BOUNCE_ADDRESS = ""
    settings.DKIM_SELECTOR = "mail"
    settings.MAILERS = {"default": {"BACKEND": SMTP_BACKEND, "OPTIONS": {"host": "smtp.relay.net"}}}


def finding(report: DnsReport, name: str) -> DnsFinding:
    """The one finding of ``report`` named ``name``."""
    (match,) = [f for f in report.findings if f.name == name]
    return match


def run(**kwargs: Any) -> DnsReport:
    """Run the check as of ``NOW``."""
    return check_mail_dns(now=NOW, **kwargs)


# --------------------------------------------------------------------------
# The whole report
# --------------------------------------------------------------------------
def test_a_domain_with_every_record_in_place_passes_every_line(dns_zone: Zone) -> None:
    """SPF, DKIM, DMARC, and the bounce address all pass, with nothing to fix."""
    report = run()

    assert [(f.name, f.status, f.fix) for f in report.findings] == [
        (SPF_NAME, DnsStatus.PASS, ""),
        (DKIM_NAME, DnsStatus.PASS, ""),
        (DMARC_NAME, DnsStatus.PASS, ""),
        (ALIGNMENT_NAME, DnsStatus.PASS, ""),
    ]


def test_the_report_names_its_domain_and_when_it_was_made(dns_zone: Zone) -> None:
    """``domain`` is the From address's domain and ``checked_at`` the ``now`` given."""
    report = run()

    assert (report.domain, report.checked_at) == ("example.org", NOW)


def test_every_lookup_waits_at_most_three_seconds(dns_zone: Zone) -> None:
    """The resolver's per-try timeout and total lifetime are both three seconds."""
    run()

    assert [(r.timeout, r.lifetime) for r in FakeResolver.instances] == [(3.0, 3.0)]


def test_a_from_address_without_a_domain_is_one_failing_line(
    dns_zone: Zone, settings: Settings
) -> None:
    """There is nothing to look up, and no lookup is made."""
    settings.DEFAULT_FROM_EMAIL = "noreply"

    report = run()

    assert [(f.status, f.detail[:34]) for f in report.findings] == [
        (DnsStatus.FAIL, "The From address the site sends ma")
    ]
    assert FakeResolver.queries == []


# --------------------------------------------------------------------------
# SPF
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "record",
    [
        "v=spf1 ip4:192.0.2.25 ~all",
        "v=spf1 ip4:192.0.2.0/24 ~all",
        "v=spf1 a:smtp.relay.net ~all",
        "v=spf1 mx:relay.net ~all",
        "v=spf1 include:_spf.relay.net ~all",
        "v=spf1 include:_spf.relay.net include:_spf.other.net -all",
        "v=spf1 redirect=_spf.relay.net",
    ],
    ids=["ip4", "ip4-range", "a", "mx", "include", "second-include", "redirect"],
)
def test_spf_passes_when_a_term_covers_the_mail_server(dns_zone: Zone, record: str) -> None:
    """``ip4``, ``a``, ``mx``, ``include``, and ``redirect`` each authorize the host."""
    dns_zone[("example.org", "TXT")] = [record]
    dns_zone[("relay.net", "MX")] = ["10 smtp.relay.net."]
    dns_zone[("_spf.other.net", "TXT")] = ["v=spf1 ip4:198.51.100.1 -all"]
    dns_zone[("_spf.relay.net", "TXT")] = ["v=spf1 ip4:192.0.2.0/24 -all"]

    assert finding(run(), SPF_NAME).status == DnsStatus.PASS


def test_spf_authorizes_an_ipv6_mail_server(dns_zone: Zone) -> None:
    """An ``ip6`` term with a prefix covers an address of the host's AAAA record."""
    dns_zone[("example.org", "TXT")] = ["v=spf1 ip6:2001:db8::/32 ~all"]
    dns_zone[("smtp.relay.net", "A")] = []
    dns_zone[("smtp.relay.net", "AAAA")] = ["2001:db8::25"]

    assert finding(run(), SPF_NAME).status == DnsStatus.PASS


def test_spf_authorizes_a_mail_server_given_as_an_address(
    dns_zone: Zone, settings: Settings
) -> None:
    """A host that is an IP literal is matched without a lookup."""
    settings.MAILERS = {"default": {"BACKEND": SMTP_BACKEND, "OPTIONS": {"host": "192.0.2.25"}}}
    dns_zone[("example.org", "TXT")] = ["v=spf1 ip4:192.0.2.25 -all"]

    assert finding(run(), SPF_NAME).status == DnsStatus.PASS
    assert ("192.0.2.25", "A") not in FakeResolver.queries


def test_spf_passes_for_a_hard_fail_policy(dns_zone: Zone) -> None:
    """``-all`` is as strict as the standard gets, and says what to do with strangers."""
    dns_zone[("example.org", "TXT")] = ["v=spf1 ip4:192.0.2.25 -all"]

    result = finding(run(), SPF_NAME)

    assert (result.status, result.fix) == (DnsStatus.PASS, "")


def test_a_missing_spf_record_fails_and_says_what_to_publish(dns_zone: Zone) -> None:
    """With no TXT record at the domain the fix names the mail server's address."""
    del dns_zone[("example.org", "TXT")]

    result = finding(run(), SPF_NAME)

    assert result.status == DnsStatus.FAIL
    assert "No approved-sender list was found for example.org." in result.detail
    assert result.fix == (
        "Ask whoever manages the DNS for example.org to add a TXT record that reads: "
        "v=spf1 ip4:192.0.2.25 ~all"
    )


def test_txt_records_that_are_not_spf_do_not_count(dns_zone: Zone) -> None:
    """A domain's verification strings are not an SPF record."""
    dns_zone[("example.org", "TXT")] = ["google-site-verification=abc"]

    assert finding(run(), SPF_NAME).status == DnsStatus.FAIL


def test_two_spf_records_fail(dns_zone: Zone) -> None:
    """A receiver ignores every record when there is more than one."""
    dns_zone[("example.org", "TXT")] = ["v=spf1 ip4:192.0.2.25 ~all", "v=spf1 mx ~all"]

    result = finding(run(), SPF_NAME)

    assert result.status == DnsStatus.FAIL
    assert "publishes 2 approved-sender lists" in result.detail


@pytest.mark.parametrize(
    "record",
    [
        "v=spf1 ip4:not-an-address ~all",
        "v=spf1 ip4:2001:db8::1 ~all",
        "v=spf1 frobnicate:example.org ~all",
        "v=spf1 include ~all",
        "v=spf1 ip6:192.0.2.1 ~all",
    ],
    ids=["bad-ip", "ipv6-in-ip4", "unknown-term", "include-without-domain", "ipv4-in-ip6"],
)
def test_a_malformed_spf_record_fails(dns_zone: Zone, record: str) -> None:
    """A term no receiver can read is a failure, whatever else the record says."""
    dns_zone[("example.org", "TXT")] = [record]

    result = finding(run(), SPF_NAME)

    assert result.status == DnsStatus.FAIL
    assert "is malformed" in result.detail


def test_an_spf_record_that_leaves_out_the_mail_server_fails(dns_zone: Zone) -> None:
    """The record is fine but lists other servers only, so the host is not authorized."""
    dns_zone[("example.org", "TXT")] = ["v=spf1 ip4:198.51.100.7 -all"]

    result = finding(run(), SPF_NAME)

    assert result.status == DnsStatus.FAIL
    assert "does not include the mail server (smtp.relay.net)" in result.detail
    assert "192.0.2.25" in result.fix


def test_an_authorizing_term_after_all_is_never_reached(dns_zone: Zone) -> None:
    """Terms after ``all`` are ignored, as a receiver ignores them."""
    dns_zone[("example.org", "TXT")] = ["v=spf1 -all ip4:192.0.2.25"]

    assert finding(run(), SPF_NAME).status == DnsStatus.FAIL


def test_a_negated_term_does_not_authorize(dns_zone: Zone) -> None:
    """``-ip4:`` names a server that is refused, not one that is allowed."""
    dns_zone[("example.org", "TXT")] = ["v=spf1 -ip4:192.0.2.25 ~all"]

    assert finding(run(), SPF_NAME).status == DnsStatus.FAIL


@pytest.mark.parametrize(
    ("record", "words"),
    [
        ("v=spf1 +all", "accepting mail from any server"),
        ("v=spf1 all", "accepting mail from any server"),
        ("v=spf1 ip4:192.0.2.25 ?all", "accepting mail from any server"),
        ("v=spf1 ip4:192.0.2.25", "does not say what to do"),
    ],
    ids=["plus-all", "bare-all", "neutral-all", "no-all"],
)
def test_an_spf_record_that_does_not_turn_strangers_away_warns(
    dns_zone: Zone, record: str, words: str
) -> None:
    """``+all``, ``?all``, and no ``all`` each warn and name the stricter ending."""
    dns_zone[("example.org", "TXT")] = [record]

    result = finding(run(), SPF_NAME)

    assert result.status == DnsStatus.WARN
    assert words in result.detail
    assert result.fix == "Ask whoever manages the DNS to end the v=spf1 record with ~all (or -all)."


@pytest.mark.parametrize(
    "record",
    [
        "v=spf1 a/33 -all",
        "v=spf1 mx/40 -all",
        "v=spf1 a//129 -all",
        "v=spf1 include:inc.example.net -all",
    ],
    ids=["a-v4", "mx-v4", "a-v6", "include-with-a-v4"],
)
def test_an_out_of_range_prefix_length_is_a_malformed_record_not_an_error(
    dns_zone: Zone, record: str
) -> None:
    """``a/33``, ``mx/40``, and an included record carrying one fail the line cleanly."""
    dns_zone[("example.org", "TXT")] = [record]
    dns_zone[("inc.example.net", "TXT")] = ["v=spf1 a/33 -all"]
    dns_zone[("example.org", "MX")] = ["10 smtp.relay.net."]

    result = finding(run(), SPF_NAME)

    assert result.status == DnsStatus.FAIL
    assert "is malformed" in result.detail


def test_the_endpoint_answers_200_for_an_out_of_range_prefix_length(
    management_client: APIClient, dns_zone: Zone
) -> None:
    """A bad prefix length in the domain's record is a finding, never a 500."""
    dns_zone[("example.org", "TXT")] = ["v=spf1 a/33 -all"]

    response = management_client.get(URL)

    assert response.status_code == 200
    assert response.json()["findings"][0]["status"] == "fail"


@pytest.mark.parametrize(
    ("record", "status", "words"),
    [
        ("v=spf1 -ip4:192.0.2.25 ip4:192.0.2.0/24 -all", DnsStatus.FAIL, "reject mail from it"),
        ("v=spf1 ~ip4:192.0.2.25 ip4:192.0.2.25 -all", DnsStatus.WARN, "does not fully approve"),
        ("v=spf1 ?ip4:192.0.2.25 ip4:192.0.2.25 -all", DnsStatus.WARN, "does not fully approve"),
        ("v=spf1 ip4:198.51.100.1 ~all", DnsStatus.FAIL, "does not include the mail server"),
    ],
    ids=["minus-first", "softfail-first", "neutral-first", "all-last"],
)
def test_the_first_term_that_matches_decides_whatever_its_qualifier(
    dns_zone: Zone, record: str, status: DnsStatus, words: str
) -> None:
    """A negated or softfail entry that names the host stops the evaluation."""
    dns_zone[("example.org", "TXT")] = [record]

    result = finding(run(), SPF_NAME)

    assert (result.status, words in result.detail) == (status, True)


def test_an_included_list_that_allows_everything_authorizes_the_host(dns_zone: Zone) -> None:
    """``include:`` matches when the included record's first match is a plus."""
    dns_zone[("example.org", "TXT")] = ["v=spf1 include:open.example.net -all"]
    dns_zone[("open.example.net", "TXT")] = ["v=spf1 +all"]

    assert finding(run(), SPF_NAME).status == DnsStatus.PASS


def test_an_included_list_that_refuses_the_host_does_not_match(dns_zone: Zone) -> None:
    """A fail inside the included record is no match, so the outer ``all`` decides."""
    dns_zone[("example.org", "TXT")] = ["v=spf1 include:inc.example.net -all"]
    dns_zone[("inc.example.net", "TXT")] = ["v=spf1 -ip4:192.0.2.25 +all"]

    assert finding(run(), SPF_NAME).status == DnsStatus.FAIL


def test_an_ipv4_only_prefix_does_not_widen_an_ipv6_address(
    dns_zone: Zone,
) -> None:
    """``a:other.net/24`` covers IPv6 addresses of ``other.net`` exactly, not as a /24."""
    dns_zone[("smtp.relay.net", "A")] = []
    dns_zone[("smtp.relay.net", "AAAA")] = ["2001:db8::25"]
    dns_zone[("other.net", "AAAA")] = ["2001:db8:ffff::1"]
    dns_zone[("example.org", "TXT")] = ["v=spf1 a:other.net/24 -all"]

    assert finding(run(), SPF_NAME).status == DnsStatus.FAIL


@pytest.mark.parametrize("term", ["a//64", "mx//64", "a/24//64"])
def test_an_ipv6_prefix_length_is_valid_and_widens_an_ipv6_host(dns_zone: Zone, term: str) -> None:
    """``a//64``, ``mx//64``, and ``a/24//64`` parse, and the /64 covers the host."""
    dns_zone[("smtp.relay.net", "A")] = []
    dns_zone[("smtp.relay.net", "AAAA")] = ["2001:db8::25"]
    dns_zone[("example.org", "AAAA")] = ["2001:db8::1"]
    dns_zone[("example.org", "MX")] = ["10 example.org."]
    dns_zone[("example.org", "TXT")] = [f"v=spf1 {term} -all"]

    assert finding(run(), SPF_NAME).status == DnsStatus.PASS


def test_an_mx_term_naming_more_than_ten_servers_fails(dns_zone: Zone) -> None:
    """Receivers refuse an ``mx`` that names more than ten mail servers."""
    dns_zone[("example.org", "MX")] = [f"10 h{n}.example.org." for n in range(11)]
    dns_zone[("example.org", "TXT")] = ["v=spf1 mx ip4:192.0.2.25 -all"]

    result = finding(run(), SPF_NAME)

    assert result.status == DnsStatus.FAIL
    assert "more than 10 mail servers" in result.detail


def test_every_lookup_causing_term_counts_toward_the_limit_whatever_its_qualifier(
    dns_zone: Zone,
) -> None:
    """Eleven negated ``a`` terms that match nothing still cost eleven lookups."""
    terms = " ".join(f"-a:h{n}.example.net" for n in range(11))
    dns_zone[("example.org", "TXT")] = [f"v=spf1 {terms} ip4:192.0.2.25 -all"]

    result = finding(run(), SPF_NAME)

    assert result.status == DnsStatus.FAIL
    assert "more than 10 lookups" in result.detail


def test_spf_is_judged_at_the_bounce_addresss_domain_and_says_so(
    dns_zone: Zone, settings: Settings
) -> None:
    """Receivers check SPF at the envelope sender's domain, so that is where we look."""
    settings.BOUNCE_ADDRESS = "bounces@mail.example.org"
    dns_zone[("mail.example.org", "TXT")] = ["v=spf1 ip4:192.0.2.25 -all"]
    del dns_zone[("example.org", "TXT")]

    result = finding(run(), SPF_NAME)

    assert result.status == DnsStatus.PASS
    assert (
        "Receivers check this list at mail.example.org, the domain of the bounce" in result.detail
    )
    assert ("example.org", "TXT") not in FakeResolver.queries


def test_a_missing_spf_record_names_the_bounce_domain_when_that_is_where_it_belongs(
    dns_zone: Zone, settings: Settings
) -> None:
    """The failure and its fix both name the domain the record must be published at."""
    settings.BOUNCE_ADDRESS = "bounces@mail.example.org"

    result = finding(run(), SPF_NAME)

    assert result.status == DnsStatus.FAIL
    assert "No approved-sender list was found for mail.example.org." in result.detail
    assert result.fix.startswith("Ask whoever manages the DNS for mail.example.org to add")


def test_a_bounce_address_without_a_domain_fails_as_not_valid(
    dns_zone: Zone, settings: Settings
) -> None:
    """The line says the address is not valid, and SPF falls back to the From domain."""
    settings.BOUNCE_ADDRESS = "bounces"

    report = run()

    assert finding(report, ALIGNMENT_NAME).status == DnsStatus.FAIL
    assert "is not a valid address: it has no domain." in finding(report, ALIGNMENT_NAME).detail
    assert finding(report, SPF_NAME).status == DnsStatus.PASS


def test_an_spf_record_needing_more_than_ten_lookups_fails(dns_zone: Zone) -> None:
    """Receivers refuse a record that chains past ten DNS-querying terms."""
    dns_zone[("example.org", "TXT")] = [
        "v=spf1 " + " ".join(f"include:s{n}.example.net" for n in range(11)) + " -all"
    ]
    for n in range(11):
        dns_zone[(f"s{n}.example.net", "TXT")] = ["v=spf1 ip4:198.51.100.1 -all"]

    result = finding(run(), SPF_NAME)

    assert result.status == DnsStatus.FAIL
    assert "more than 10 lookups" in result.detail


def test_a_mail_server_on_the_same_machine_warns_instead_of_failing(
    dns_zone: Zone, settings: Settings
) -> None:
    """A loopback host says nothing about the public address, so the check warns."""
    settings.MAILERS = {"default": {"BACKEND": SMTP_BACKEND, "OPTIONS": {"host": "localhost"}}}
    dns_zone[("localhost", "A")] = ["127.0.0.1"]
    dns_zone[("example.org", "TXT")] = ["v=spf1 ip4:192.0.2.25 ~all"]

    result = finding(run(), SPF_NAME)

    assert result.status == DnsStatus.WARN
    assert "same machine (localhost)" in result.detail


def test_a_site_with_no_mail_server_setting_warns(dns_zone: Zone, settings: Settings) -> None:
    """With no SMTP host (console or file mail) there is no server to look for."""
    settings.MAILERS = {"default": {"BACKEND": "django.core.mail.backends.console.EmailBackend"}}

    result = finding(run(), SPF_NAME)

    assert result.status == DnsStatus.WARN
    assert "not set up to send through an outside mail server" in result.detail


def test_a_mail_server_that_does_not_resolve_fails(dns_zone: Zone) -> None:
    """A host with no address cannot be on any list."""
    del dns_zone[("smtp.relay.net", "A")]

    result = finding(run(), SPF_NAME)

    assert result.status == DnsStatus.FAIL
    assert "does not resolve to an address" in result.detail


@pytest.mark.parametrize(
    ("name", "label"),
    [
        (("example.org", "TXT"), SPF_NAME),
        (("smtp.relay.net", "A"), SPF_NAME),
        (("mail._domainkey.example.org", "TXT"), DKIM_NAME),
        (("_dmarc.example.org", "TXT"), DMARC_NAME),
    ],
    ids=["spf-record", "spf-host", "dkim", "dmarc"],
)
def test_a_lookup_that_times_out_fails_the_line_in_plain_words(
    dns_zone: Zone, name: tuple[str, str], label: str
) -> None:
    """A timeout is a failing line saying no answer came in time, never an exception."""
    dns_zone[name] = dns.exception.Timeout()  # type: ignore[no-untyped-call]  # dnspython

    result = finding(run(), label)

    assert result.status == DnsStatus.FAIL
    assert f"Looking up {name[0]} did not get an answer in time." in result.detail
    assert "Timeout" not in result.detail


def test_a_lookup_no_name_server_can_answer_points_at_the_domains_dns(dns_zone: Zone) -> None:
    """``NoNameservers`` is a problem with the domain's DNS; the fix says who to ask."""
    no_servers = dns.resolver.NoNameservers()  # type: ignore[no-untyped-call]  # dnspython
    dns_zone[("_dmarc.example.org", "TXT")] = no_servers

    result = finding(run(), DMARC_NAME)

    assert result.status == DnsStatus.FAIL
    assert (
        "No name server could answer a lookup of _dmarc.example.org, which points to a "
        "problem with the DNS setup of the domain."
    ) in result.detail
    assert "NoNameservers" not in result.detail
    assert result.fix.startswith("Ask whoever manages the DNS for the domain to check")


def test_a_check_that_runs_out_of_time_fails_the_lookups_left(
    dns_zone: Zone, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Once the time budget is spent each later lookup is a failing line that says so."""
    monkeypatch.setattr(dns_check, "CHECK_BUDGET_SECONDS", 0.0)

    report = run()

    assert [(f.name, f.status) for f in report.findings if f.name != ALIGNMENT_NAME] == [
        (SPF_NAME, DnsStatus.FAIL),
        (DKIM_NAME, DnsStatus.FAIL),
        (DMARC_NAME, DnsStatus.FAIL),
    ]
    assert "The check took too long" in finding(report, DKIM_NAME).detail
    assert FakeResolver.queries == []


# --------------------------------------------------------------------------
# DKIM
# --------------------------------------------------------------------------
def test_dkim_passes_when_the_selectors_key_is_published(dns_zone: Zone) -> None:
    """The record at ``<selector>._domainkey.<domain>`` carries a ``p=`` key."""
    result = finding(run(), DKIM_NAME)

    assert (result.status, result.fix) == (DnsStatus.PASS, "")
    assert ("mail._domainkey.example.org", "TXT") in FakeResolver.queries


def test_dkim_without_a_selector_warns_and_looks_nothing_up(
    dns_zone: Zone, settings: Settings
) -> None:
    """No ``DKIM_SELECTOR`` is a warning that says so."""
    settings.DKIM_SELECTOR = ""

    result = finding(run(), DKIM_NAME)

    assert result.status == DnsStatus.WARN
    assert "No DKIM selector is configured" in result.detail
    assert [q for q in FakeResolver.queries if "_domainkey" in q[0]] == []


def test_a_missing_dkim_record_fails_and_names_where_it_belongs(dns_zone: Zone) -> None:
    """The fix gives the exact name to publish the key at."""
    del dns_zone[("mail._domainkey.example.org", "TXT")]

    result = finding(run(), DKIM_NAME)

    assert result.status == DnsStatus.FAIL
    assert "No public key was found at mail._domainkey.example.org." in result.detail
    assert "TXT record named mail._domainkey.example.org" in result.fix


@pytest.mark.parametrize(
    "record",
    ["v=DKIM1; k=rsa", "v=DKIM1; k=rsa; p=", "something else entirely"],
    ids=["no-key", "revoked-key", "not-dkim"],
)
def test_a_dkim_record_without_a_key_fails(dns_zone: Zone, record: str) -> None:
    """A record with no ``p=`` value (or an empty, revoked one) is not a usable key."""
    dns_zone[("mail._domainkey.example.org", "TXT")] = [record]

    result = finding(run(), DKIM_NAME)

    assert result.status == DnsStatus.FAIL
    assert "has no usable key" in result.detail


# --------------------------------------------------------------------------
# DMARC
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("policy", "outcome"),
    [("quarantine", "sent to spam"), ("reject", "refused")],
)
def test_dmarc_passes_for_a_policy_that_acts_on_forgeries(
    dns_zone: Zone, policy: str, outcome: str
) -> None:
    """``quarantine`` and ``reject`` pass, and the detail says what each does."""
    dns_zone[("_dmarc.example.org", "TXT")] = [f"v=DMARC1; p={policy}"]

    result = finding(run(), DMARC_NAME)

    assert result.status == DnsStatus.PASS
    assert f"The policy is {policy}, so forged mail is {outcome}." in result.detail


def test_a_monitor_only_dmarc_policy_warns(dns_zone: Zone) -> None:
    """``p=none`` publishes a policy that asks receivers to do nothing."""
    dns_zone[("_dmarc.example.org", "TXT")] = ["v=DMARC1; p=none"]

    result = finding(run(), DMARC_NAME)

    assert result.status == DnsStatus.WARN
    assert "monitor-only (p=none)" in result.detail
    assert "p=quarantine" in result.fix


def test_dmarc_lists_where_its_reports_go(dns_zone: Zone) -> None:
    """Both the ``rua`` and the ``ruf`` addresses appear in the detail."""
    dns_zone[("_dmarc.example.org", "TXT")] = [
        "v=DMARC1; p=reject; rua=mailto:a@example.org; ruf=mailto:f@example.org"
    ]

    detail = finding(run(), DMARC_NAME).detail

    assert "Summary reports go to mailto:a@example.org." in detail
    assert "Failure reports go to mailto:f@example.org." in detail


def test_a_missing_dmarc_record_fails_with_a_record_to_publish(dns_zone: Zone) -> None:
    """The fix is a complete starting record."""
    del dns_zone[("_dmarc.example.org", "TXT")]

    result = finding(run(), DMARC_NAME)

    assert result.status == DnsStatus.FAIL
    assert result.fix == (
        "Ask whoever manages the DNS for example.org to add a TXT record named "
        "_dmarc.example.org that reads: v=DMARC1; p=quarantine; "
        "rua=mailto:dmarc-reports@example.org"
    )


@pytest.mark.parametrize(
    "record", ["v=DMARC1", "v=DMARC1; p=maybe"], ids=["no-policy", "bad-policy"]
)
def test_a_malformed_dmarc_policy_fails(dns_zone: Zone, record: str) -> None:
    """A record with no valid ``p=`` is no policy."""
    dns_zone[("_dmarc.example.org", "TXT")] = [record]

    result = finding(run(), DMARC_NAME)

    assert result.status == DnsStatus.FAIL
    assert "is malformed" in result.detail


# --------------------------------------------------------------------------
# Envelope alignment
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("bounce", "status"),
    [
        ("", DnsStatus.PASS),
        ("bounces@example.org", DnsStatus.PASS),
        ("bounces@mail.example.org", DnsStatus.PASS),
        ("bounces@other.net", DnsStatus.WARN),
        ("bounces@notexample.org", DnsStatus.WARN),
    ],
    ids=["blank", "same-domain", "subdomain", "other-domain", "lookalike-domain"],
)
def test_the_bounce_address_is_judged_against_the_from_domain(
    dns_zone: Zone, settings: Settings, bounce: str, status: DnsStatus
) -> None:
    """Blank, the same domain, or a subdomain pass; any other domain warns."""
    settings.BOUNCE_ADDRESS = bounce

    assert finding(run(), ALIGNMENT_NAME).status == status


# --------------------------------------------------------------------------
# The cache
# --------------------------------------------------------------------------
def test_a_second_run_reads_the_cache_and_queries_nothing(dns_zone: Zone) -> None:
    """The cached report keeps its original ``checked_at``."""
    first = run()
    queries = len(FakeResolver.queries)

    second = check_mail_dns(now=NOW + timedelta(minutes=1))

    assert (second, len(FakeResolver.queries)) == (first, queries)


def test_refresh_looks_the_records_up_again(dns_zone: Zone) -> None:
    """``refresh=True`` bypasses the cache and replaces what it held."""
    run()
    dns_zone[("_dmarc.example.org", "TXT")] = ["v=DMARC1; p=none"]

    later = check_mail_dns(now=NOW + timedelta(minutes=1), refresh=True)

    assert (finding(later, DMARC_NAME).status, later.checked_at) == (
        DnsStatus.WARN,
        NOW + timedelta(minutes=1),
    )
    assert finding(run(), DMARC_NAME).status == DnsStatus.WARN


def test_a_cached_report_expires_after_five_minutes(dns_zone: Zone) -> None:
    """Six minutes on, the lookups run again."""
    with freeze_time(NOW):
        run()
        queries = len(FakeResolver.queries)
    with freeze_time(NOW + timedelta(minutes=6)):
        run()

    assert len(FakeResolver.queries) > queries


def test_changing_a_setting_the_check_reads_is_not_answered_from_the_cache(
    dns_zone: Zone, settings: Settings
) -> None:
    """A different selector is a different report."""
    run()
    settings.DKIM_SELECTOR = ""

    assert finding(run(), DKIM_NAME).status == DnsStatus.WARN


# --------------------------------------------------------------------------
# GET /mail/delivery-check
# --------------------------------------------------------------------------
@pytest.mark.parametrize(("role", "allowed"), role_matrix(MANAGEMENT, SYSTEM_ADMIN))
def test_management_and_system_administrators_read_the_delivery_check(
    api_client: APIClient,
    all_role_users: dict[str, User],
    dns_zone: Zone,
    role: str,
    allowed: bool,
) -> None:
    """Every other role is refused."""
    api_client.force_login(all_role_users[role])

    response = api_client.get(URL)

    assert response.status_code == (200 if allowed else 403)


def test_an_anonymous_visitor_is_refused(api_client: APIClient, dns_zone: Zone) -> None:
    """The check needs a signed-in user."""
    assert api_client.get(URL).status_code == 401


def test_the_endpoint_answers_the_report(management_client: APIClient, dns_zone: Zone) -> None:
    """The body is ``{domain, checked_at, findings}`` with every finding's four fields."""
    with freeze_time(NOW):
        body = management_client.get(URL).json()

    assert body["domain"] == "example.org"
    assert body["checked_at"] == "2026-10-03T08:00:00-07:00"
    assert [(f["name"], f["status"], f["fix"]) for f in body["findings"]] == [
        (SPF_NAME, "pass", ""),
        (DKIM_NAME, "pass", ""),
        (DMARC_NAME, "pass", ""),
        (ALIGNMENT_NAME, "pass", ""),
    ]
    assert all(f["detail"] != "" for f in body["findings"])


def test_the_endpoint_serves_the_cache_until_refresh_is_asked_for(
    management_client: APIClient, dns_zone: Zone
) -> None:
    """``?refresh=true`` looks again; a plain request does not."""
    management_client.get(URL)
    dns_zone[("_dmarc.example.org", "TXT")] = ["v=DMARC1; p=none"]

    cached = management_client.get(URL).json()["findings"][2]["status"]
    fresh = management_client.get(URL, {"refresh": "true"}).json()["findings"][2]["status"]

    assert (cached, fresh) == ("pass", "warn")


# --------------------------------------------------------------------------
# manage.py check_mail_dns
# --------------------------------------------------------------------------
def test_the_command_prints_every_finding_and_exits_cleanly_when_all_pass(dns_zone: Zone) -> None:
    """One heading and one block per line; no ``CommandError``."""
    out = StringIO()

    call_command("check_mail_dns", stdout=out)

    lines = out.getvalue().splitlines()
    assert lines[0] == "Mail delivery for example.org"
    assert [line for line in lines if line.startswith("[")] == [
        f"[PASS] {SPF_NAME}",
        f"[PASS] {DKIM_NAME}",
        f"[PASS] {DMARC_NAME}",
        f"[PASS] {ALIGNMENT_NAME}",
    ]


def test_the_command_exits_zero_on_a_warning(dns_zone: Zone, settings: Settings) -> None:
    """A warning is printed with its fix and is not a failure."""
    settings.DKIM_SELECTOR = ""
    out = StringIO()

    call_command("check_mail_dns", stdout=out)

    assert f"[WARN] {DKIM_NAME}" in out.getvalue()
    assert "  Fix: Ask the person who runs the server for the name" in out.getvalue()


def test_the_command_exits_non_zero_on_a_failure_after_printing_the_report(
    dns_zone: Zone,
) -> None:
    """A missing DMARC record fails the command with the count of failures."""
    del dns_zone[("_dmarc.example.org", "TXT")]
    out = StringIO()

    with pytest.raises(CommandError, match=r"1 mail delivery check\(s\) failed\."):
        call_command("check_mail_dns", stdout=out)

    assert f"[FAIL] {DMARC_NAME}" in out.getvalue()


def test_the_command_ignores_the_cache(dns_zone: Zone) -> None:
    """It always looks the records up afresh."""
    run()
    dns_zone[("_dmarc.example.org", "TXT")] = ["v=DMARC1; p=none"]
    out = StringIO()

    call_command("check_mail_dns", stdout=out)

    assert f"[WARN] {DMARC_NAME}" in out.getvalue()
