"""Mail delivery check: do the DNS records that make receiving servers trust us exist?

A receiving mail server (Gmail, Outlook, a member's own provider) decides whether a
message from CalDART is real by looking at three records kept with the From address's
domain in the Domain Name System:

* **SPF**, a list of the servers allowed to send for the domain;
* **DKIM**, the public half of the key the mail server signs every message with;
* **DMARC**, what the domain asks receivers to do with a message that fails the other
  two, and where to send reports about it.

:func:`check_mail_dns` reads all three over the network and answers a
:class:`DnsReport` with one :class:`DnsFinding` per line: SPF, DKIM, DMARC, and whether
the bounce address (``BOUNCE_ADDRESS``) is on the From address's domain.  Each finding
carries ``detail`` (what the record is for and what was found, in words a person who has
never heard of the record can follow) and ``fix`` (what to ask for when it is not
``pass``).

The records are looked up at the domain of ``DEFAULT_FROM_EMAIL``.  Only DMARC falls back
to a parent: with no policy of its own, the From domain is judged by its organizational
domain's (found on the public suffix list bundled with ``tldextract``), as RFC 7489
says.  The SPF check authorizes the host named by the default mailer's
``host`` option (``EMAIL_URL``): it follows ``include:``, ``a``, ``mx``, ``ip4``, and
``ip6`` terms, with at most ``SPF_LOOKUP_LIMIT`` lookups as the SPF standard allows.  A
host that resolves only to a loopback address (a mail server on the same machine) cannot
be matched to the address mail really leaves from, so the check warns instead.

The SPF record is judged at the domain of ``BOUNCE_ADDRESS`` when that is set, because a
receiving server checks SPF against the envelope sender, and at the From domain
otherwise.  Terms are evaluated in order and the first one that matches decides, as
RFC 7208 says.

Every lookup waits at most ``DNS_TIMEOUT_SECONDS``, and the whole check at most
``CHECK_BUDGET_SECONDS``.  A report is cached for
``CACHE_SECONDS`` per combination of the settings it reads, so opening the page again
does not query anybody; ``refresh=True`` skips the cache.  Tests patch
``dns.resolver.Resolver``: the suite never makes a real query.
"""

from __future__ import annotations

import hashlib
import ipaddress
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime
from email.utils import parseaddr
from enum import StrEnum
from typing import NamedTuple

import dns.exception
import dns.rdata
import dns.rdtypes.IN.A
import dns.rdtypes.IN.AAAA
import dns.rdtypes.mxbase
import dns.rdtypes.txtbase
import dns.resolver
import tldextract
from django.conf import settings
from django.core.cache import cache

log = logging.getLogger(__name__)

#: How long one lookup may take, in seconds.
DNS_TIMEOUT_SECONDS = 3.0

#: How long the whole check may take, in seconds; later lookups fail once it is spent.
CHECK_BUDGET_SECONDS = 15.0

#: The most mail servers one SPF ``mx`` term may name before receivers refuse it.
SPF_MX_LIMIT = 10

#: How long a report stays in the cache, in seconds.
CACHE_SECONDS = 300

#: The most DNS-querying terms an SPF record may need (``include``, ``a``, ``mx``,
#: ``redirect``) before a receiver gives up on it.
SPF_LOOKUP_LIMIT = 10

#: The public suffix list, from the snapshot bundled with ``tldextract``: no list is
#: fetched over the network and nothing is cached on disk.
_PUBLIC_SUFFIXES = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None)

#: The cache key's prefix; the settings the check reads are hashed onto the end.
CACHE_KEY_PREFIX = "mail.dns_report."

#: The version tags that open an SPF, DKIM, and DMARC record.
SPF_VERSION = "v=spf1"
DMARC_VERSION = "v=dmarc1"

#: The DMARC policies, as the standard spells them.
DMARC_POLICIES = ("none", "quarantine", "reject")

#: One SPF term: an optional qualifier, a mechanism or modifier name, an optional
#: ``:argument`` or ``=argument``, and an optional ``/prefix`` length.
SPF_TERM = re.compile(
    r"^(?P<qualifier>[+\-~?])?(?P<name>[a-z0-9]+)"
    r"(?:[:=](?P<argument>[^/]+))?(?P<prefix>(?:/\d{1,3})?(?://\d{1,3})?)$",
    re.IGNORECASE,
)

#: The widest prefix length each address family allows.
MAX_PREFIX_V4 = 32
MAX_PREFIX_V6 = 128

#: The SPF mechanisms and modifiers this check understands.
SPF_MECHANISMS = frozenset({"all", "include", "a", "mx", "ip4", "ip6", "ptr", "exists"})
SPF_MODIFIERS = frozenset({"redirect", "exp"})

#: What each finding's name reads as on the page.
SPF_NAME = "Approved senders (SPF)"
DKIM_NAME = "Message signature (DKIM)"
DMARC_NAME = "Handling of forged mail (DMARC)"
ALIGNMENT_NAME = "Bounce address"

#: What to do when a lookup timed out, or did not finish within the check's time budget.
_FIX_RETRY = (
    "Check again in a few minutes; if it keeps failing, ask whoever manages the domain's DNS."
)

#: What to do when every name server refused or could not answer.
_FIX_NAME_SERVERS = (
    "Ask whoever manages the DNS for the domain to check that its name servers are "
    "running and answer for it."
)

#: One sentence on what each record does, which opens every finding's detail.
SPF_PURPOSE = (
    "SPF is a list, kept with your domain name, of the servers allowed to send email "
    "that claims to come from CalDART."
)
DKIM_PURPOSE = (
    "DKIM is a digital signature the mail server puts on every message, which a "
    "receiving server checks against a public key published with your domain name."
)
DMARC_PURPOSE = (
    "DMARC tells receiving servers what to do with a message that claims to come from "
    "CalDART but fails the other checks, and where to send reports about such messages."
)
ALIGNMENT_PURPOSE = (
    "The bounce address is where a receiving server returns a message it cannot "
    "deliver; some servers trust a message more when that address is on the same "
    "domain as the From address."
)


class DnsStatus(StrEnum):
    """How one finding turned out: ``pass`` is good, ``warn`` works but is weak."""

    PASS = "pass"  # noqa: S105 - a status word, not a password
    WARN = "warn"
    FAIL = "fail"


@dataclass(frozen=True)
class DnsFinding:
    """One line of the report.

    ``name`` is the line's title, ``status`` how it turned out, ``detail`` what the
    record is for and what was found, and ``fix`` what to ask for when ``status`` is not
    ``pass`` (blank when it is).
    """

    name: str
    status: DnsStatus
    detail: str
    fix: str = ""


@dataclass(frozen=True)
class DnsReport:
    """The whole check: ``domain`` it ran for, its ``findings`` in page order, and when.

    ``checked_at`` is the ``now`` the caller gave the run that produced the report, so a
    cached report keeps the time it was really made.
    """

    domain: str
    findings: tuple[DnsFinding, ...]
    checked_at: datetime


class DnsLookupError(Exception):
    """A lookup that could not be answered, with a sentence and a fix for the reader.

    ``str()`` is the sentence: that the name servers did not answer in time, could not
    answer at all, or that the check ran out of time.  ``fix`` is what to do about it.
    An answer of "no such record" is not an error and comes back as an empty list.
    """

    def __init__(self, message: str, fix: str) -> None:
        """Record the sentence and the fix."""
        super().__init__(message)
        self.fix = fix

    @classmethod
    def from_resolver(cls, name: str, error: dns.exception.DNSException) -> DnsLookupError:
        """The error for a lookup of ``name`` that raised the resolver's ``error``."""
        if isinstance(error, dns.exception.Timeout):
            return cls(f"Looking up {name} did not get an answer in time.", _FIX_RETRY)
        if isinstance(error, dns.resolver.NoNameservers):
            return cls(
                f"No name server could answer a lookup of {name}, which points to a problem "
                "with the DNS setup of the domain.",
                _FIX_NAME_SERVERS,
            )
        return cls(f"Looking up {name} failed.", _FIX_RETRY)

    @classmethod
    def out_of_time(cls) -> DnsLookupError:
        """The error for a lookup attempted after the check's time budget was spent."""
        return cls(
            "The check took too long and was stopped before this lookup finished.", _FIX_RETRY
        )


class SpfSyntaxError(Exception):
    """An SPF record a receiving server would reject; ``str()`` says what is wrong."""


@dataclass(frozen=True)
class _SpfTerm:
    """One parsed SPF term: its qualifier, name, argument, and prefix length."""

    qualifier: str
    name: str
    argument: str
    prefix: str


class _Problem(NamedTuple):
    """Something wrong with the SPF list: how bad, what was found, and what to ask for."""

    status: DnsStatus
    result: str
    fix: str


@dataclass(frozen=True)
class _Inputs:
    """The settings the check reads, resolved once per run."""

    from_domain: str
    host: str
    selector: str
    bounce_domain: str

    @property
    def spf_domain(self) -> str:
        """The domain the SPF record is judged at: the bounce address's, else From's."""
        return self.bounce_domain if self.bounce_domain != "" else self.from_domain

    def cache_key(self) -> str:
        """The cache key for a report made from these inputs."""
        digest = hashlib.sha256(repr(self).encode()).hexdigest()
        return f"{CACHE_KEY_PREFIX}{digest[:24]}"


def check_mail_dns(*, now: datetime, refresh: bool = False) -> DnsReport:
    """Run the delivery check and answer its report.

    A report cached in the last five minutes for the same ``DEFAULT_FROM_EMAIL``,
    ``DKIM_SELECTOR``, ``BOUNCE_ADDRESS``, and mail host is answered as it was, with its
    original ``checked_at``; ``refresh=True`` runs the lookups again and replaces it.
    ``now`` stamps a new report's ``checked_at``.  A ``DEFAULT_FROM_EMAIL`` with no
    domain gives a report with the single failing finding that says so.
    """
    inputs = _read_inputs()
    key = inputs.cache_key()
    if not refresh:
        cached = cache.get(key)
        if isinstance(cached, DnsReport):
            return cached
    report = _build_report(inputs, now)
    cache.set(key, report, CACHE_SECONDS)
    return report


def _read_inputs() -> _Inputs:
    """Read the From domain, mail host, DKIM selector, and bounce domain from settings."""
    from_domain = _domain_of(settings.DEFAULT_FROM_EMAIL)
    bounce = settings.BOUNCE_ADDRESS
    options = settings.MAILERS["default"].get("OPTIONS", {})
    return _Inputs(
        from_domain=from_domain,
        host=str(options.get("host", "")).strip().lower(),
        selector=settings.DKIM_SELECTOR.strip(),
        bounce_domain=_domain_of(bounce) if bounce != "" else from_domain,
    )


def _domain_of(address: str) -> str:
    """The lowercase domain of ``CalDART <noreply@example.org>``; blank for no ``@``."""
    _, separator, domain = parseaddr(address)[1].rpartition("@")
    return domain.strip().lower() if separator == "@" else ""


def _build_report(inputs: _Inputs, now: datetime) -> DnsReport:
    """Make every finding for ``inputs`` and wrap them in a report stamped ``now``."""
    if inputs.from_domain == "":
        finding = DnsFinding(
            name=SPF_NAME,
            status=DnsStatus.FAIL,
            detail="The From address the site sends mail as has no domain, so there is "
            "nothing to look up.",
            fix="Ask the person who runs the server to set the site's From address to a "
            "full address such as noreply@yourdomain.org.",
        )
        return DnsReport(domain="", findings=(finding,), checked_at=now)
    resolver = _Resolver()
    findings = (
        _check_spf(resolver, inputs),
        _check_dkim(resolver, inputs),
        _check_dmarc(resolver, inputs),
        _check_alignment(inputs),
    )
    return DnsReport(domain=inputs.from_domain, findings=findings, checked_at=now)


# --------------------------------------------------------------------------
# Lookups
# --------------------------------------------------------------------------
class _Resolver:
    """The real resolver, held to the per-lookup timeout and the whole check's budget."""

    def __init__(self) -> None:
        """Start the clock and make the resolver the lookups go through."""
        self._deadline = time.monotonic() + CHECK_BUDGET_SECONDS
        self._resolver = dns.resolver.Resolver()
        self._resolver.timeout = DNS_TIMEOUT_SECONDS
        self._resolver.lifetime = DNS_TIMEOUT_SECONDS

    def query(self, name: str, rdtype: str) -> list[dns.rdata.Rdata]:
        """Every record of type ``rdtype`` at ``name``; none at all is an empty list.

        Raises ``DnsLookupError`` for a timeout, a refusal, any other resolver error, or
        a lookup begun after the check's time budget was spent.
        """
        if time.monotonic() >= self._deadline:
            raise DnsLookupError.out_of_time()
        try:
            return list(self._resolver.resolve(name, rdtype))
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            return []
        except dns.exception.DNSException as exc:
            log.warning("DNS lookup of %s %s failed: %s", rdtype, name, type(exc).__name__)
            raise DnsLookupError.from_resolver(name, exc) from exc


def _txt_records(resolver: _Resolver, name: str) -> list[str]:
    """The TXT records at ``name``, each with its strings joined into one."""
    return [
        b"".join(record.strings).decode("utf-8", errors="replace")
        for record in resolver.query(name, "TXT")
        if isinstance(record, dns.rdtypes.txtbase.TXTBase)
    ]


def _spf_records(resolver: _Resolver, domain: str) -> list[str]:
    """The TXT records at ``domain`` that are SPF records (they start with ``v=spf1``)."""
    return [
        text
        for text in _txt_records(resolver, domain)
        if text.lower().split(maxsplit=1)[:1] == [SPF_VERSION]
    ]


def _addresses(resolver: _Resolver, name: str) -> list[str]:
    """The IPv4 and IPv6 addresses of ``name``, or ``name`` itself if it is an address."""
    if _is_ip(name):
        return [name]
    return [
        record.address
        for rdtype in ("A", "AAAA")
        for record in resolver.query(name, rdtype)
        if isinstance(record, (dns.rdtypes.IN.A.A, dns.rdtypes.IN.AAAA.AAAA))
    ]


def _is_ip(text: str) -> bool:
    """True when ``text`` is an IPv4 or IPv6 address."""
    try:
        ipaddress.ip_address(text)
    except ValueError:
        return False
    return True


# --------------------------------------------------------------------------
# SPF
# --------------------------------------------------------------------------
def _check_spf(resolver: _Resolver, inputs: _Inputs) -> DnsFinding:
    """The SPF finding: a record exists, parses, lists the mail host, ends strictly."""
    domain = inputs.spf_domain
    try:
        records = _spf_records(resolver, domain)
    except DnsLookupError as exc:
        return _spf_finding(inputs, DnsStatus.FAIL, str(exc), exc.fix)
    if len(records) == 0:
        return _spf_finding(
            inputs,
            DnsStatus.FAIL,
            f"No approved-sender list was found for {domain}.",
            _spf_fix_publish(resolver, inputs),
        )
    if len(records) > 1:
        return _spf_finding(
            inputs,
            DnsStatus.FAIL,
            f"{domain} publishes {len(records)} approved-sender lists; receiving servers "
            "ignore all of them when there is more than one.",
            f"Ask whoever manages the DNS for {domain} to merge them into a single TXT "
            "record that starts with v=spf1.",
        )
    return _spf_judge(resolver, inputs, records[0])


def _spf_judge(resolver: _Resolver, inputs: _Inputs, record: str) -> DnsFinding:
    """Judge the one SPF ``record``: its syntax, the host, then its closing policy."""
    domain = inputs.spf_domain
    try:
        terms = _parse_spf(record)
        host_problem = _spf_host_problem(resolver, inputs, terms)
    except DnsLookupError as exc:
        return _spf_finding(inputs, DnsStatus.FAIL, str(exc), exc.fix)
    except (SpfSyntaxError, ValueError) as exc:
        reason = str(exc) if isinstance(exc, SpfSyntaxError) else "an entry cannot be read."
        return _spf_finding(
            inputs,
            DnsStatus.FAIL,
            f"The approved-sender list for {domain} is malformed: {reason}",
            f"Ask whoever manages the DNS for {domain} to correct the TXT record that "
            "starts with v=spf1.",
        )
    if host_problem is not None and host_problem.status == DnsStatus.FAIL:
        return _spf_finding(inputs, *host_problem)
    problems = [
        problem for problem in (host_problem, _spf_policy_problem(terms)) if problem is not None
    ]
    if len(problems) > 0:
        return _spf_finding(
            inputs,
            DnsStatus.WARN,
            " ".join(problem.result for problem in problems),
            " ".join(problem.fix for problem in problems),
        )
    return _spf_finding(
        inputs,
        DnsStatus.PASS,
        f"The list for {domain} includes the mail server ({inputs.host}) and "
        "tells receivers to treat mail from anywhere else as suspect.",
    )


def _spf_finding(inputs: _Inputs, status: DnsStatus, result: str, fix: str = "") -> DnsFinding:
    """An SPF finding: the SPF explanation, where receivers look, then ``result``."""
    where = ""
    if inputs.spf_domain != inputs.from_domain:
        where = (
            f"Receivers check this list at {inputs.spf_domain}, the domain of the bounce "
            "address, because that is the address a message is sent from on the wire. "
        )
    return DnsFinding(SPF_NAME, status, f"{SPF_PURPOSE} {where}{result}", fix)


def _spf_fix_publish(resolver: _Resolver, inputs: _Inputs) -> str:
    """What to publish when there is no SPF record, naming the host's address if known."""
    where = f"Ask whoever manages the DNS for {inputs.spf_domain} to add a TXT record "
    try:
        addresses = [a for a in _addresses(resolver, inputs.host) if _is_public_candidate(a)]
    except DnsLookupError:
        addresses = []
    if inputs.host == "" or len(addresses) == 0:
        return (
            where + "that starts with v=spf1 and lists the server that sends CalDART's mail "
            "(the person who runs the server can say which address), ending in ~all."
        )
    term = "ip6" if ":" in addresses[0] else "ip4"
    return where + f"that reads: v=spf1 {term}:{addresses[0]} ~all"


def _is_public_candidate(address: str) -> bool:
    """True when ``address`` could be the address mail leaves from: not loopback."""
    return not ipaddress.ip_address(address).is_loopback


def _parse_spf(record: str) -> list[_SpfTerm]:
    """Split an SPF ``record`` into terms, raising ``SpfSyntaxError`` on a bad one."""
    terms: list[_SpfTerm] = []
    for text in record.split()[1:]:
        match = SPF_TERM.match(text)
        if match is None:
            raise SpfSyntaxError(f"{text!r} is not a valid entry.")
        name = match.group("name").lower()
        if name not in SPF_MECHANISMS and name not in SPF_MODIFIERS:
            raise SpfSyntaxError(f"{text!r} is not a valid entry.")
        term = _SpfTerm(
            qualifier=match.group("qualifier") or "+",
            name=name,
            argument=match.group("argument") or "",
            prefix=match.group("prefix") or "",
        )
        _validate_term(term, text)
        terms.append(term)
    return terms


def _validate_term(term: _SpfTerm, text: str) -> None:
    """Raise ``SpfSyntaxError`` when ``term`` lacks or mangles what it needs."""
    if term.name in {"include", "redirect", "exists"} and term.argument == "":
        raise SpfSyntaxError(f"{text!r} needs a domain name.")
    if term.name in {"ip4", "ip6"}:
        try:
            network = ipaddress.ip_network(term.argument + term.prefix, strict=False)
        except ValueError as exc:
            raise SpfSyntaxError(f"{text!r} is not a valid address.") from exc
        if network.version != (4 if term.name == "ip4" else 6):
            raise SpfSyntaxError(f"{text!r} is not a valid address.")
    if term.name in {"a", "mx"}:
        lengths = _prefix_lengths(term.prefix)
        if lengths[0] > MAX_PREFIX_V4 or lengths[1] > MAX_PREFIX_V6:
            raise SpfSyntaxError(f"{text!r} has a prefix length that is too large.")


def _prefix_lengths(prefix: str) -> tuple[int, int]:
    """The IPv4 and IPv6 prefix lengths of an ``a`` or ``mx`` prefix such as ``/24//64``.

    A length the prefix leaves out is the full address: 32 for IPv4 and 128 for IPv6.
    """
    v4_text, _, v6_text = prefix.partition("//")
    v4 = int(v4_text.lstrip("/")) if v4_text != "" else MAX_PREFIX_V4
    v6 = int(v6_text) if v6_text != "" else MAX_PREFIX_V6
    return v4, v6


def _spf_host_problem(
    resolver: _Resolver, inputs: _Inputs, terms: list[_SpfTerm]
) -> _Problem | None:
    """What is wrong with the list's coverage of the mail host, or ``None`` when nothing.

    Raises ``DnsLookupError`` and ``SpfSyntaxError`` from the lookups and the followed
    ``include:`` records.
    """
    if inputs.host == "":
        return _Problem(
            DnsStatus.WARN,
            "The site is not set up to send through an outside mail server, so there is "
            "no server to look for in the list.",
            "Nothing to do unless the site is meant to send through a mail server; then "
            "ask the person who runs it to set the mail server address.",
        )
    addresses = [ipaddress.ip_address(a) for a in _addresses(resolver, inputs.host)]
    if len(addresses) == 0:
        return _Problem(
            DnsStatus.FAIL,
            f"The mail server's name ({inputs.host}) does not resolve to an address.",
            "Ask the person who runs the server to check the mail server setting.",
        )
    if all(address.is_loopback for address in addresses):
        return _Problem(
            DnsStatus.WARN,
            f"The site hands its mail to a server on the same machine ({inputs.host}), so "
            "this check cannot tell which public address the mail leaves from.",
            "Ask the person who runs the server to confirm the list names the server's "
            "public address.",
        )
    match = _SpfEvaluator(resolver, addresses).evaluate(inputs.spf_domain, terms)
    return _verdict_problem(inputs, match, addresses[0])


def _verdict_problem(
    inputs: _Inputs,
    match: _Match | None,
    address: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> _Problem | None:
    """What the first matching SPF term says about the mail host, or ``None`` if fine.

    A ``+`` match is fine.  An entry that names the host with ``-`` refuses it, and one
    with ``~`` or ``?`` only half approves it.  The closing ``all`` (or no match at all)
    means the host is not listed.
    """
    domain, host = inputs.spf_domain, inputs.host
    if match is not None and match.qualifier == "+":
        return None
    if match is not None and not match.via_all and match.qualifier == "-":
        return _Problem(
            DnsStatus.FAIL,
            f"The list for {domain} names the mail server ({host}) and tells receivers to "
            "reject mail from it.",
            f"Ask whoever manages the DNS for {domain} to change the minus sign in front "
            f"of the entry for {host} (or {address}) to a plus, or remove the entry.",
        )
    if match is not None and not match.via_all:
        return _Problem(
            DnsStatus.WARN,
            f"The list for {domain} names the mail server ({host}) but does not fully "
            "approve it, so receivers may mark CalDART mail as suspicious.",
            f"Ask whoever manages the DNS for {domain} to remove the ~ or ? in front of the "
            f"entry for {host} (or {address}).",
        )
    return _Problem(
        DnsStatus.FAIL,
        f"The list for {domain} does not include the mail server "
        f"({host}), so receivers may treat CalDART mail as forged.",
        f"Ask whoever manages the DNS for {domain} to add "
        f"{host} (or its address, {address}) to the TXT record that starts "
        "with v=spf1.",
    )


def _spf_policy_problem(terms: list[_SpfTerm]) -> _Problem | None:
    """The warning for a list that does not reject other senders, or ``None``."""
    closing = next((term for term in terms if term.name == "all"), None)
    redirects = any(term.name == "redirect" for term in terms)
    if closing is None and redirects:
        return None
    if closing is not None and closing.qualifier in {"-", "~"}:
        return None
    if closing is None:
        result = (
            "The list does not say what to do with mail from servers that are not on it, "
            "so a forger is not turned away."
        )
    elif closing.qualifier == "?":
        result = (
            "The list ends with ?all, which tells receivers to make no judgment about "
            "mail from servers that are not on it, so it does not stop a forger."
        )
    else:
        result = "The list ends by accepting mail from any server, so it does not stop a forger."
    return _Problem(
        DnsStatus.WARN,
        result,
        "Ask whoever manages the DNS to end the v=spf1 record with ~all (or -all).",
    )


class _Match(NamedTuple):
    """The first SPF term that matched: its qualifier, and whether it was ``all``."""

    qualifier: str
    via_all: bool


class _SpfEvaluator:
    """Evaluates an SPF record for a set of IP addresses, as RFC 7208 orders it."""

    def __init__(
        self,
        resolver: _Resolver,
        addresses: list[ipaddress.IPv4Address | ipaddress.IPv6Address],
    ) -> None:
        """Hold the ``resolver`` and the ``addresses`` to look for."""
        self._resolver = resolver
        self._addresses = addresses
        self._lookups = 0

    def evaluate(self, domain: str, terms: list[_SpfTerm]) -> _Match | None:
        """The first term of ``terms`` (``domain``'s record) that matches, or ``None``.

        Terms are tried in order and the first match decides, whatever its qualifier;
        ``all`` always matches.  With no match, a ``redirect`` modifier hands the
        decision to the record it names.  An ``include`` matches only when the included
        record's own first match carries ``+``.

        Raises ``SpfSyntaxError`` past ``SPF_LOOKUP_LIMIT`` lookups, for an ``mx`` naming
        more than ``SPF_MX_LIMIT`` servers, or for a malformed included record, and
        ``DnsLookupError`` when a lookup fails outright.
        """
        for term in terms:
            if term.name not in SPF_MODIFIERS and self._matches(domain, term):
                return _Match(term.qualifier, term.name == "all")
        redirect = next((term for term in terms if term.name == "redirect"), None)
        if redirect is None:
            return None
        return self._follow(redirect.argument)

    def _matches(self, domain: str, term: _SpfTerm) -> bool:
        """True when the mechanism ``term`` covers one of the addresses."""
        match term.name:
            case "all":
                return True
            case "ip4" | "ip6":
                network = ipaddress.ip_network(term.argument + term.prefix, strict=False)
                return self._in_network(network)
            case "a":
                self._count_lookup()
                return self._hosts_cover(term, [term.argument or domain])
            case "mx":
                self._count_lookup()
                return self._hosts_cover(term, self._mail_exchangers(term.argument or domain))
            case "include":
                inner = self._follow(term.argument)
                return inner is not None and inner.qualifier == "+"
            case _:
                # ``ptr`` and ``exists`` cost a lookup each but are not evaluated.
                self._count_lookup()
                return False

    def _count_lookup(self) -> None:
        """Count one DNS-querying term, raising ``SpfSyntaxError`` past the limit."""
        self._lookups += 1
        if self._lookups > SPF_LOOKUP_LIMIT:
            raise SpfSyntaxError(
                f"it needs more than {SPF_LOOKUP_LIMIT} lookups, which receivers refuse."
            )

    def _follow(self, domain: str) -> _Match | None:
        """The first match of the SPF record published at ``domain``, or ``None``."""
        self._count_lookup()
        records = _spf_records(self._resolver, domain)
        if len(records) != 1:
            return None
        return self.evaluate(domain, _parse_spf(records[0]))

    def _mail_exchangers(self, domain: str) -> list[str]:
        """The mail exchanger host names of ``domain``; at most ``SPF_MX_LIMIT``."""
        hosts = [
            record.exchange.to_text().rstrip(".")
            for record in self._resolver.query(domain, "MX")
            if isinstance(record, dns.rdtypes.mxbase.MXBase)
        ]
        if len(hosts) > SPF_MX_LIMIT:
            raise SpfSyntaxError(
                f"an mx entry names more than {SPF_MX_LIMIT} mail servers, which receivers refuse."
            )
        return hosts

    def _hosts_cover(self, term: _SpfTerm, hosts: list[str]) -> bool:
        """True when an address of one of ``hosts``, widened by the prefix, is covered."""
        lengths = _prefix_lengths(term.prefix)
        return any(
            self._in_network(self._widen(ipaddress.ip_address(text), lengths))
            for host in hosts
            for text in _addresses(self._resolver, host)
        )

    @staticmethod
    def _widen(
        address: ipaddress.IPv4Address | ipaddress.IPv6Address, lengths: tuple[int, int]
    ) -> ipaddress.IPv4Network | ipaddress.IPv6Network:
        """The network ``address`` belongs to under the term's IPv4 and IPv6 lengths."""
        length = lengths[0] if address.version == 4 else lengths[1]
        return ipaddress.ip_network(f"{address}/{length}", strict=False)

    def _in_network(self, network: ipaddress.IPv4Network | ipaddress.IPv6Network) -> bool:
        """True when any address being looked for lies inside ``network``."""
        return any(
            address.version == network.version and address in network for address in self._addresses
        )


# --------------------------------------------------------------------------
# DKIM
# --------------------------------------------------------------------------
def _check_dkim(resolver: _Resolver, inputs: _Inputs) -> DnsFinding:
    """The DKIM finding: a selector is set and its public key is published."""
    if inputs.selector == "":
        return DnsFinding(
            DKIM_NAME,
            DnsStatus.WARN,
            f"{DKIM_PURPOSE} No DKIM selector is configured, so this check has no "
            "signature record to look for.",
            "Ask the person who runs the server for the name (the selector) the mail "
            "server signs with, and have them set it as DKIM_SELECTOR.",
        )
    name = f"{inputs.selector}._domainkey.{inputs.from_domain}"
    try:
        records = _txt_records(resolver, name)
    except DnsLookupError as exc:
        return DnsFinding(DKIM_NAME, DnsStatus.FAIL, f"{DKIM_PURPOSE} {exc}", exc.fix)
    if len(records) == 0:
        return DnsFinding(
            DKIM_NAME,
            DnsStatus.FAIL,
            f"{DKIM_PURPOSE} No public key was found at {name}.",
            f"Ask whoever manages the DNS for {inputs.from_domain} to publish the public "
            f"key as a TXT record named {name}; the mail server's administrator or mail "
            "provider supplies the text.",
        )
    keys = [_dkim_key(text) for text in records]
    if any(key != "" for key in keys):
        return DnsFinding(
            DKIM_NAME,
            DnsStatus.PASS,
            f"{DKIM_PURPOSE} A public key is published at {name}.",
        )
    return DnsFinding(
        DKIM_NAME,
        DnsStatus.FAIL,
        f"{DKIM_PURPOSE} The record at {name} has no usable key in it.",
        "Ask the person who runs the server for the key's TXT record (it contains "
        "p= followed by a long string) and have the DNS manager republish it.",
    )


def _dkim_key(record: str) -> str:
    """The ``p=`` public key in a DKIM TXT ``record``; blank when it has none."""
    for tag in record.split(";"):
        name, _, value = tag.strip().partition("=")
        if name.strip().lower() == "p":
            return "".join(value.split())
    return ""


# --------------------------------------------------------------------------
# DMARC
# --------------------------------------------------------------------------
def _check_dmarc(resolver: _Resolver, inputs: _Inputs) -> DnsFinding:
    """The DMARC finding: a policy is published, and it does something about forgeries.

    The policy is read at ``_dmarc.<From domain>``.  When no record there starts with
    ``v=DMARC1``, it is read at the organizational domain's ``_dmarc`` name instead, as
    RFC 7489 section 6.6.3 has a receiver do, and that record's ``sp=`` (or its ``p=``
    when there is no valid ``sp=``) is the policy judged; the detail then says where it
    was found, and a fix names that record.
    """
    domain = inputs.from_domain
    name = f"_dmarc.{domain}"
    try:
        records = _dmarc_records(resolver, name)
        org_domain = _organizational_domain(domain)
        if len(records) == 0 and org_domain not in ("", domain):
            name, domain = f"_dmarc.{org_domain}", org_domain
            records = _dmarc_records(resolver, name)
    except DnsLookupError as exc:
        return DnsFinding(DMARC_NAME, DnsStatus.FAIL, f"{DMARC_PURPOSE} {exc}", exc.fix)
    if len(records) == 0:
        name = f"_dmarc.{inputs.from_domain}"
        return DnsFinding(
            DMARC_NAME,
            DnsStatus.FAIL,
            f"{DMARC_PURPOSE} No policy was found at {name}.",
            f"Ask whoever manages the DNS for {inputs.from_domain} to add a TXT record "
            f"named {name} that reads: v=DMARC1; p=quarantine; rua=mailto:"
            f"dmarc-reports@{inputs.from_domain}",
        )
    purpose = DMARC_PURPOSE
    if domain != inputs.from_domain:
        purpose += f" The policy for {inputs.from_domain} is published at {name}."
    if len(records) > 1:
        return DnsFinding(
            DMARC_NAME,
            DnsStatus.FAIL,
            f"{purpose} {name} publishes {len(records)} policies; receiving servers "
            "apply none of them when there is more than one.",
            f"Ask whoever manages the DNS for {domain} to keep one TXT record "
            f"at {name} that starts with v=DMARC1 and remove the others.",
        )
    tags = _dmarc_tags(records[0])
    policy = tags.get("p", "").lower()
    if policy not in DMARC_POLICIES:
        return DnsFinding(
            DMARC_NAME,
            DnsStatus.FAIL,
            f"{purpose} The policy at {name} is malformed: it has no valid p= setting.",
            f"Ask whoever manages the DNS for {domain} to correct the "
            f"record at {name} so it contains p=none, p=quarantine, or p=reject.",
        )
    tag = "p"
    if domain != inputs.from_domain and tags.get("sp", "").lower() in DMARC_POLICIES:
        tag, policy = "sp", tags["sp"].lower()
    reports = _dmarc_reports(tags)
    if policy == "none":
        return DnsFinding(
            DMARC_NAME,
            DnsStatus.WARN,
            f"{purpose} The policy is monitor-only ({tag}=none), so receivers are not "
            f"asked to do anything about forged mail.{reports}",
            f"Once the reports show real CalDART mail passing, ask whoever manages the DNS "
            f"for {domain} to change {tag}=none to {tag}=quarantine"
            + ("." if domain == inputs.from_domain else f" in the record at {name}."),
        )
    return DnsFinding(
        DMARC_NAME,
        DnsStatus.PASS,
        f"{purpose} The policy is {policy}, so forged mail is "
        f"{'sent to spam' if policy == 'quarantine' else 'refused'}.{reports}",
    )


def _dmarc_records(resolver: _Resolver, name: str) -> list[str]:
    """The TXT records at ``name`` that are DMARC policies: they start with v=DMARC1."""
    return [
        text
        for text in _txt_records(resolver, name)
        if text.strip().lower().startswith(DMARC_VERSION)
    ]


def _organizational_domain(domain: str) -> str:
    """``domain``'s registrable domain on the public suffix list; blank when it has none.

    ``caldart.example.co.uk`` gives ``example.co.uk``.  The list is the snapshot bundled
    with ``tldextract``: nothing is fetched over the network.
    """
    return _PUBLIC_SUFFIXES(domain).top_domain_under_public_suffix


def _dmarc_tags(record: str) -> dict[str, str]:
    """The ``tag=value`` pairs of a DMARC ``record``, tags lowercased."""
    tags: dict[str, str] = {}
    for part in record.split(";"):
        name, separator, value = part.strip().partition("=")
        if separator == "=":
            tags[name.strip().lower()] = value.strip()
    return tags


def _dmarc_reports(tags: dict[str, str]) -> str:
    """A sentence listing where the DMARC reports go, or blank when they go nowhere.

    Each ``rua`` and ``ruf`` value is a comma-separated list of report addresses; each is
    shown as the bare address, without its ``mailto:`` scheme or a ``!`` size limit, and
    several read as a list joined with "and".
    """
    parts = [
        f"{label} {_dmarc_addresses(tags[tag])}"
        for tag, label in (("rua", "Summary reports go to"), ("ruf", "Failure reports go to"))
        if tag in tags
    ]
    return "" if len(parts) == 0 else " " + " ".join(f"{part}." for part in parts)


def _dmarc_addresses(value: str) -> str:
    """The report addresses in one ``rua`` or ``ruf`` ``value``, as a person writes them.

    ``mailto:a@example.org!10m, mailto:b@example.org`` reads as
    ``a@example.org and b@example.org``; a URI that is not ``mailto:`` is kept as given.
    """
    addresses = []
    for uri in value.split(","):
        address = uri.strip().partition("!")[0]
        if address.lower().startswith("mailto:"):
            address = address[len("mailto:") :]
        if address != "":
            addresses.append(address)
    if len(addresses) <= 2:
        return " and ".join(addresses)
    return f"{', '.join(addresses[:-1])}, and {addresses[-1]}"


# --------------------------------------------------------------------------
# Envelope alignment
# --------------------------------------------------------------------------
def _check_alignment(inputs: _Inputs) -> DnsFinding:
    """The bounce-address finding: it is on the From domain or a subdomain of it."""
    bounce, origin = inputs.bounce_domain, inputs.from_domain
    if bounce == "":
        return DnsFinding(
            ALIGNMENT_NAME,
            DnsStatus.FAIL,
            f"{ALIGNMENT_PURPOSE} The bounce address the site is set to use is not a valid "
            "address: it has no domain.",
            f"Ask the person who runs the server to set the bounce address to a full "
            f"address such as bounces@{origin}.",
        )
    if bounce == origin:
        return DnsFinding(
            ALIGNMENT_NAME,
            DnsStatus.PASS,
            f"{ALIGNMENT_PURPOSE} Bounces come back to {origin}, the same domain as the "
            "From address.",
        )
    if bounce.endswith(f".{origin}"):
        return DnsFinding(
            ALIGNMENT_NAME,
            DnsStatus.PASS,
            f"{ALIGNMENT_PURPOSE} Bounces come back to {bounce}, a part of {origin}.",
        )
    return DnsFinding(
        ALIGNMENT_NAME,
        DnsStatus.WARN,
        f"{ALIGNMENT_PURPOSE} Bounces come back to {bounce}, which is not part of {origin}.",
        f"Ask the person who runs the server to use a bounce address at {origin} (or a "
        "subdomain of it), or accept that some receivers may trust CalDART mail less.",
    )
