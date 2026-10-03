"""Whether the web links in a bulk email load, checked without reaching inside.

:func:`check_links` fetches each link from the server and answers, for each, the
:class:`Problem` with it or ``None`` when it loads.  The links are fetched at once, at
most :data:`LINK_WORKERS` together, on an event loop of their own, so every deadline is
real: each link has :data:`LINK_BUDGET_SECONDS` in all, its name lookups, redirects,
and second try included, however slowly a server answers, and the whole run
:data:`RUN_BUDGET_SECONDS`, after which a link not yet answered is
:attr:`Problem.NOT_IN_TIME`.  A request that runs out of time is canceled, never left
running in a thread nobody waits for; a name lookup, which cannot be canceled, runs in
a pool the run abandons rather than waits for.

The check must never become a way into the server's own network.  It resolves each
host itself and refuses the link (:attr:`Problem.PRIVATE`) when any address the host
resolves to is not on the public internet (:func:`is_public`) or is one of this
server's own addresses (:func:`own_addresses`); it fetches only ports 80 and 443
(any other is :attr:`Problem.PORT`); and it then connects to the address it checked,
never resolving the name again, so a name that changes its answer between the two
cannot lead the request inside.  Redirects are followed by hand, each hop checked the
same way, and no proxy is read from the environment.  What it reports is coarse on
purpose (the status class, not the code), so it cannot serve as a port scanner.
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from enum import StrEnum
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
from django.conf import settings

log = logging.getLogger(__name__)


class Problem(StrEnum):
    """What is wrong with one link."""

    CLIENT_ERROR = "client_error"
    SERVER_ERROR = "server_error"
    TIMEOUT = "timeout"
    UNREACHABLE = "unreachable"
    PRIVATE = "private"
    PORT = "port"
    NOT_IN_TIME = "not_in_time"


#: The seconds one request may take to connect, and to read each part of the answer.
LINK_TIMEOUT_SECONDS = 5

#: The seconds one link's check may take in all.
LINK_BUDGET_SECONDS = 12

#: The seconds a whole run of link checks may take; a link not answered by then is
#: reported as not checked in time.
RUN_BUDGET_SECONDS = 30

#: The redirects a link check follows before it gives up on the link.
MAX_REDIRECTS = 5

#: How many links are checked at once.
LINK_WORKERS = 10

#: The only ports a link check connects to.
WEB_PORTS = frozenset({80, 443})

#: What a link check calls itself to the sites it asks.
USER_AGENT = "CalDART link check"

#: The schemes a link check fetches; ``mailto:`` and the rest are not checked.
WEB_SCHEMES = frozenset({"http", "https"})


class PrivateAddressError(Exception):
    """A link's host resolves to an address the link check will not connect to."""


class PortNotCheckedError(Exception):
    """A link names a port other than 80 or 443."""


class TooManyRedirectsError(Exception):
    """A link redirected more than :data:`MAX_REDIRECTS` times."""


def check_links(urls: list[str]) -> list[Problem | None]:
    """The problem with each of ``urls``, in order, or ``None`` for one that loads.

    Each link is asked with ``HEAD``, and with ``GET`` when that answers 400 or more,
    since some sites refuse ``HEAD`` alone; the body is never read.  An answer of 400
    to 499 is :attr:`Problem.CLIENT_ERROR` and of 500 or more
    :attr:`Problem.SERVER_ERROR`; a link whose check outlasts
    :data:`LINK_BUDGET_SECONDS`, or one of whose requests times out, is
    :attr:`Problem.TIMEOUT`; one that cannot be found, connected to, or followed past
    :data:`MAX_REDIRECTS` redirects is :attr:`Problem.UNREACHABLE`.  A host inside a
    private network or on this server is :attr:`Problem.PRIVATE` and a port other
    than 80 or 443 :attr:`Problem.PORT`, neither fetched at all.  Every link not
    answered within :data:`RUN_BUDGET_SECONDS` is :attr:`Problem.NOT_IN_TIME`.
    """
    if len(urls) == 0:
        return []
    lookups = ThreadPoolExecutor(max_workers=LINK_WORKERS, thread_name_prefix="link-check")
    try:
        return asyncio.run(_check_all(urls, lookups))
    finally:
        # A name lookup cannot be canceled: the run leaves a stuck one behind rather
        # than wait for it.
        lookups.shutdown(wait=False, cancel_futures=True)


def resolve(host: str, port: int) -> list[str]:
    """Every address ``host`` resolves to for a connection on ``port``, each once.

    An address literal answers itself.  Raises ``OSError`` (``socket.gaierror``) for a
    host that does not resolve.
    """
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return list(dict.fromkeys(str(info[4][0]) for info in infos))


def own_addresses() -> frozenset[str]:
    """This server's own addresses, as far as name lookups reveal them.

    The addresses of ``SITE_URL``'s host and of this machine's host name and fully
    qualified name; a name that does not resolve adds nothing.
    """
    names = {urlsplit(str(settings.SITE_URL)).hostname, socket.gethostname(), socket.getfqdn()}
    addresses: set[str] = set()
    for name in names:
        if name is None or name == "":
            continue
        try:
            addresses.update(resolve(name, 443))
        except OSError:
            continue
    return frozenset(addresses)


def is_public(address: str) -> bool:
    """True when ``address`` is on the public internet, where a link check may connect.

    False for a private, loopback, link-local, multicast, reserved, unspecified,
    shared, or IPv6 site-local (``fec0::/10``) address, and for an IPv6 address that
    maps an IPv4 one which is any of those.
    """
    ip = ipaddress.ip_address(address)
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.is_site_local:
            return False
        if ip.ipv4_mapped is not None:
            ip = ip.ipv4_mapped
    is_special = (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )
    return ip.is_global and not is_special


async def _check_all(urls: list[str], lookups: ThreadPoolExecutor) -> list[Problem | None]:
    """Check ``urls`` at most :data:`LINK_WORKERS` at once, within the run's budget."""
    gate = asyncio.Semaphore(LINK_WORKERS)
    own = await _own_addresses(lookups)

    async def one(url: str) -> Problem | None:
        async with gate:
            return await _check_one(url, lookups, own)

    tasks = [asyncio.create_task(one(url)) for url in urls]
    _done, pending = await asyncio.wait(tasks, timeout=RUN_BUDGET_SECONDS)
    for task in pending:
        task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)
    return [Problem.NOT_IN_TIME if task in pending else task.result() for task in tasks]


async def _own_addresses(lookups: ThreadPoolExecutor) -> frozenset[str]:
    """:func:`own_addresses`, given at most :data:`LINK_TIMEOUT_SECONDS`; else none."""
    loop = asyncio.get_running_loop()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(lookups, own_addresses), LINK_TIMEOUT_SECONDS
        )
    except TimeoutError:
        log.warning("link check could not look up this server's own addresses in time")
        return frozenset()


async def _check_one(url: str, lookups: ThreadPoolExecutor, own: frozenset[str]) -> Problem | None:
    """The problem with ``url``, its whole check held to :data:`LINK_BUDGET_SECONDS`."""
    try:
        return await asyncio.wait_for(_problem(url, lookups, own), LINK_BUDGET_SECONDS)
    except TimeoutError:
        return Problem.TIMEOUT


async def _problem(url: str, lookups: ThreadPoolExecutor, own: frozenset[str]) -> Problem | None:
    """The problem with ``url``, with no deadline of its own: see :func:`check_links`."""
    try:
        status = await _link_status(url, lookups, own)
    except PrivateAddressError:
        return Problem.PRIVATE
    except PortNotCheckedError:
        return Problem.PORT
    except httpx.TimeoutException:
        return Problem.TIMEOUT
    except (
        TooManyRedirectsError,
        httpx.HTTPError,
        httpx.InvalidURL,
        OSError,
        ValueError,
        UnicodeError,
    ) as error:
        log.info("link check could not reach a link: %s", type(error).__name__)
        return Problem.UNREACHABLE
    if status >= httpx.codes.INTERNAL_SERVER_ERROR:
        return Problem.SERVER_ERROR
    if status >= httpx.codes.BAD_REQUEST:
        return Problem.CLIENT_ERROR
    return None


async def _link_status(url: str, lookups: ThreadPoolExecutor, own: frozenset[str]) -> int:
    """The status ``url`` answers, ``HEAD`` first and ``GET`` when that fails."""
    timeout = httpx.Timeout(LINK_TIMEOUT_SECONDS)
    async with httpx.AsyncClient(
        timeout=timeout, trust_env=False, follow_redirects=False
    ) as client:
        status = await _final_status(client, "HEAD", url, lookups, own)
        if status >= httpx.codes.BAD_REQUEST:
            status = await _final_status(client, "GET", url, lookups, own)
    return status


async def _final_status(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    lookups: ThreadPoolExecutor,
    own: frozenset[str],
) -> int:
    """The status ``url`` answers ``method`` with, after following its redirects.

    Raises :class:`TooManyRedirectsError` past :data:`MAX_REDIRECTS`, and whatever
    :func:`_request` raises.
    """
    current = url
    for _hop in range(MAX_REDIRECTS + 1):
        response = await _request(client, method, current, lookups, own)
        location = response.headers.get("location")
        if not response.is_redirect or location is None:
            return response.status_code
        current = urljoin(current, location)
    raise TooManyRedirectsError(url)


async def _request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    lookups: ThreadPoolExecutor,
    own: frozenset[str],
) -> httpx.Response:
    """Ask ``url`` with ``method`` at the address :func:`_pinned_address` checked.

    The request goes to that address, with the link's host in the ``Host`` header and,
    for ``https``, as the name TLS sends and verifies the certificate against, so the
    host is never resolved again.  The body is not read.  Raises ``ValueError`` for an
    address that is not an ``http`` or ``https`` one with a host, or whose port is not
    a number; :class:`PortNotCheckedError` for a port other than 80 or 443; what
    :func:`_pinned_address` raises; and ``httpx.HTTPError`` for a request that fails.
    """
    parts = urlsplit(url)
    host = parts.hostname
    if parts.scheme not in WEB_SCHEMES or host is None:
        raise ValueError("Not a web address.")
    is_https = parts.scheme == "https"
    port = parts.port if parts.port is not None else (443 if is_https else 80)
    if port not in WEB_PORTS:
        raise PortNotCheckedError(url)
    address = await _pinned_address(host, port, lookups, own)
    literal = f"[{address}]" if ":" in address else address
    target = urlunsplit((parts.scheme, f"{literal}:{port}", parts.path or "/", parts.query, ""))
    headers = {"Host": parts.netloc.rpartition("@")[2], "User-Agent": USER_AGENT}
    extensions = {"sni_hostname": host} if is_https else {}
    async with client.stream(method, target, headers=headers, extensions=extensions) as response:
        return response


async def _pinned_address(
    host: str, port: int, lookups: ThreadPoolExecutor, own: Iterable[str]
) -> str:
    """The address a link check connects to for ``host``: the first it resolves to.

    The name is looked up in ``lookups``, under the link's own deadline.  Raises
    :class:`PrivateAddressError` when any address ``host`` resolves to is not public
    (:func:`is_public`) or is one of ``own``, since a host answering with one public
    and one private address could be sent to either, and ``OSError`` when it resolves
    to none.
    """
    loop = asyncio.get_running_loop()
    addresses = await loop.run_in_executor(lookups, resolve, host, port)
    if len(addresses) == 0:
        raise OSError("The host resolved to no address.")
    inside = set(own)
    if any(not is_public(address) or address in inside for address in addresses):
        raise PrivateAddressError(host)
    return addresses[0]
