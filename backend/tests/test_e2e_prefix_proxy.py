"""The reverse proxy ``make e2e E2E_URL_PREFIX=...`` puts in front of ``runserver``.

``frontend/e2e/prefix_proxy.py`` stands in for the web server that serves CalDART
under a URL prefix: it redirects the bare prefix to the prefix with a slash, strips
the prefix from every request under it, forwards the request to the upstream with
its ``Host`` kept and ``X-Forwarded-*`` headers added, streams the answer back
untouched, and answers ``404`` for any path outside the prefix.  These tests run it
on loopback against a small recording upstream.
"""

from __future__ import annotations

import http.client
import importlib.util
import json
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import ModuleType

import pytest

PROXY_SOURCE = Path(__file__).resolve().parents[2] / "frontend" / "e2e" / "prefix_proxy.py"

PREFIX = "/caldart-proto"

#: How often a test server checks for shutdown, in seconds; the default half second
#: would dominate every test's teardown.
POLL_INTERVAL = 0.01


def _load_proxy() -> ModuleType:
    """Import ``prefix_proxy.py`` from its path, since ``frontend/e2e`` is no package."""
    spec = importlib.util.spec_from_file_location("caldart_prefix_proxy", PROXY_SOURCE)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


proxy_module = _load_proxy()


class _RecordingHandler(BaseHTTPRequestHandler):
    """An upstream that answers every request with a JSON echo of what it received."""

    def _echo(self) -> None:
        """Answer with the method, path, headers and body this request carried."""
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode() if length > 0 else ""
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", f"{PREFIX}/portal/login")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        payload = json.dumps(
            {
                "method": self.command,
                "path": self.path,
                "headers": {key.lower(): value for key, value in self.headers.items()},
                "body": body,
            }
        ).encode()
        self.send_response(201)
        self.send_header("Content-Type", "application/json")
        self.send_header("Set-Cookie", "sessionid=abc; Path=/")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        """Echo a GET."""
        self._echo()

    def do_POST(self) -> None:
        """Echo a POST."""
        self._echo()

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - the stdlib's name
        """Keep the test output quiet."""


@dataclass
class _Running:
    """A proxy on loopback in front of the recording upstream."""

    port: int
    upstream_port: int


def _serve(server: ThreadingHTTPServer) -> threading.Thread:
    """Run ``server`` on a daemon thread and return the thread."""
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": POLL_INTERVAL}, daemon=True
    )
    thread.start()
    return thread


@pytest.fixture
def running() -> Iterator[_Running]:
    """Start the recording upstream and the proxy in front of it; stop both afterwards."""
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), _RecordingHandler)
    upstream_port = upstream.server_address[1]
    proxy = proxy_module.build_server(port=0, upstream_port=upstream_port, prefix=PREFIX)
    _serve(upstream)
    _serve(proxy)
    try:
        yield _Running(port=proxy.server_address[1], upstream_port=upstream_port)
    finally:
        proxy.shutdown()
        upstream.shutdown()
        proxy.server_close()
        upstream.server_close()


def _request(
    running: _Running,
    method: str,
    path: str,
    *,
    body: str | None = None,
    headers: dict[str, str] | None = None,
) -> http.client.HTTPResponse:
    """Send one request to the proxy and return its response, body unread."""
    connection = http.client.HTTPConnection("127.0.0.1", running.port, timeout=5)
    connection.request(method, path, body=body, headers=headers or {})
    return connection.getresponse()


def _echoed(response: http.client.HTTPResponse) -> dict[str, object]:
    """The upstream's JSON echo carried in a proxied response."""
    echoed: dict[str, object] = json.loads(response.read())
    return echoed


def _echoed_headers(response: http.client.HTTPResponse) -> dict[str, str]:
    """The request headers the upstream saw, lower-cased."""
    headers = _echoed(response)["headers"]
    assert isinstance(headers, dict)
    return headers


def test_a_path_under_the_prefix_reaches_the_upstream_without_it(running: _Running) -> None:
    """The prefix is stripped and the query string kept."""
    response = _request(running, "GET", f"{PREFIX}/portal/login?next=%2Fprofile")

    assert _echoed(response)["path"] == "/portal/login?next=%2Fprofile"


def test_the_prefix_with_a_slash_reaches_the_upstream_root(running: _Running) -> None:
    """``/caldart-proto/`` is the site's home page, ``/`` upstream."""
    response = _request(running, "GET", f"{PREFIX}/")

    assert _echoed(response)["path"] == "/"


def test_the_bare_prefix_redirects_to_the_prefix_with_a_slash(running: _Running) -> None:
    """``/caldart-proto`` answers a redirect to ``/caldart-proto/``."""
    response = _request(running, "GET", PREFIX)

    assert (response.status, response.getheader("Location")) == (301, f"{PREFIX}/")


def test_the_bare_prefix_keeps_its_query_string_through_the_redirect(running: _Running) -> None:
    """A query on the bare prefix follows it to the prefix with a slash."""
    response = _request(running, "GET", f"{PREFIX}?a=1")

    assert response.getheader("Location") == f"{PREFIX}/?a=1"


@pytest.mark.parametrize(
    "path",
    ["/", "/portal/login", "/caldart-protox/", "/static/app.js"],
    ids=["root", "unprefixed-portal", "longer-segment", "unprefixed-static"],
)
def test_a_path_outside_the_prefix_is_not_found(running: _Running, path: str) -> None:
    """Nothing outside the prefix reaches the upstream."""
    response = _request(running, "GET", path)

    assert response.status == 404


def test_the_upstream_status_and_headers_come_back(running: _Running) -> None:
    """The upstream's status line and its headers reach the client unchanged."""
    response = _request(running, "GET", f"{PREFIX}/x")
    response.read()

    assert (response.status, response.getheader("Set-Cookie")) == (201, "sessionid=abc; Path=/")


def test_an_upstream_redirect_is_passed_through_unchanged(running: _Running) -> None:
    """Django writes the prefix into ``Location`` itself, so the proxy leaves it alone."""
    response = _request(running, "GET", f"{PREFIX}/redirect")

    assert (response.status, response.getheader("Location")) == (302, f"{PREFIX}/portal/login")


def test_a_request_body_reaches_the_upstream(running: _Running) -> None:
    """A POST's body and method are forwarded."""
    response = _request(
        running,
        "POST",
        f"{PREFIX}/api/v1/auth/login",
        body='{"email": "a@b.test"}',
        headers={"Content-Type": "application/json"},
    )

    assert _echoed(response)["body"] == '{"email": "a@b.test"}'


def test_the_host_header_is_kept(running: _Running) -> None:
    """The upstream sees the host the browser asked for, as ``ProxyPreserveHost`` does."""
    response = _request(running, "GET", f"{PREFIX}/", headers={"Host": "localhost:8281"})

    assert _echoed_headers(response)["host"] == "localhost:8281"


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("x-forwarded-for", "127.0.0.1"),
        ("x-forwarded-host", "localhost:8281"),
        ("x-forwarded-proto", "http"),
        ("x-forwarded-prefix", PREFIX),
    ],
)
def test_the_forwarded_headers_describe_the_original_request(
    running: _Running, header: str, expected: str
) -> None:
    """The upstream learns the client, the host, the scheme and the stripped prefix."""
    response = _request(running, "GET", f"{PREFIX}/", headers={"Host": "localhost:8281"})

    assert _echoed_headers(response)[header] == expected


def test_an_unreachable_upstream_answers_bad_gateway() -> None:
    """With nothing listening upstream the proxy answers ``502``, not a hung request."""
    closed = ThreadingHTTPServer(("127.0.0.1", 0), _RecordingHandler)
    upstream_port = closed.server_address[1]
    closed.server_close()
    proxy = proxy_module.build_server(port=0, upstream_port=upstream_port, prefix=PREFIX)
    _serve(proxy)
    try:
        response = _request(
            _Running(port=proxy.server_address[1], upstream_port=upstream_port), "GET", f"{PREFIX}/"
        )
        status = response.status
    finally:
        proxy.shutdown()
        proxy.server_close()

    assert status == 502


@pytest.mark.parametrize(
    "prefix",
    ["", "/", "caldart-proto", "/caldart-proto/"],
    ids=["empty", "slash", "no-leading-slash", "trailing-slash"],
)
def test_a_prefix_that_is_not_a_bare_path_is_refused(prefix: str) -> None:
    """The prefix must start with a slash and not end with one."""
    with pytest.raises(ValueError, match="prefix"):
        proxy_module.build_server(port=0, upstream_port=1, prefix=prefix)
