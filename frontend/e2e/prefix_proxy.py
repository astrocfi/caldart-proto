"""Serve the end-to-end server under a URL prefix, as a web server in front of it would.

``make e2e E2E_URL_PREFIX=/caldart-proto`` starts this proxy on ``E2E_PORT`` and
``runserver`` on ``E2E_PORT + 2``.  The proxy behaves like the Apache or nginx snippet
that attaches CalDART to an existing site:

* the bare prefix (``/caldart-proto``) answers ``301`` to the prefix with a slash;
* a path under the prefix loses the prefix and is forwarded to the upstream with the
  ``Host`` header kept and ``X-Forwarded-For``, ``X-Forwarded-Host``,
  ``X-Forwarded-Proto`` and ``X-Forwarded-Prefix`` added, and the upstream's answer
  is streamed back unchanged (Django writes the prefix into its own URLs, because
  ``URL_PREFIX`` sets ``FORCE_SCRIPT_NAME``);
* any other path answers ``404``, so a URL the site builds without its prefix fails
  the run instead of reaching Django by accident;
* an upstream that cannot be reached answers ``502``.

It uses the standard library alone and answers each request on its own thread, closing
the connection afterwards.

Usage: python frontend/e2e/prefix_proxy.py --port PORT --upstream-port PORT --prefix PATH
"""

from __future__ import annotations

import argparse
import http.client
import logging
import shutil
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

log = logging.getLogger(__name__)

#: Where the proxy listens and where the upstream is.
LOOPBACK = "127.0.0.1"

#: Headers that describe one connection rather than the message, never forwarded.
HOP_BY_HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",  # codespell:ignore te
        "trailer",
        "transfer-encoding",
        "upgrade",
    }
)

#: ``send_response`` already writes these for the proxy's own hop to the client, so the
#: upstream's own copies are dropped rather than sent twice.
SELF_WRITTEN_ON_RESPONSE = frozenset({"server", "date"})

#: The headers the proxy writes itself, so a client's own copies are dropped.
FORWARDED = frozenset(
    {"x-forwarded-for", "x-forwarded-host", "x-forwarded-proto", "x-forwarded-prefix"}
)

#: How long to wait on the upstream before giving up, in seconds.
UPSTREAM_TIMEOUT = 120

#: The size of each piece of a response body copied to the client, in bytes.
CHUNK_SIZE = 64 * 1024


class PrefixProxyHandler(BaseHTTPRequestHandler):
    """Answer one request: redirect, forward under the prefix, or refuse.

    The server it runs in carries ``prefix`` and ``upstream_port``.
    """

    server: PrefixProxyServer

    def do_GET(self) -> None:
        """Handle a GET."""
        self._handle()

    def do_HEAD(self) -> None:
        """Handle a HEAD."""
        self._handle()

    def do_POST(self) -> None:
        """Handle a POST."""
        self._handle()

    def do_PUT(self) -> None:
        """Handle a PUT."""
        self._handle()

    def do_PATCH(self) -> None:
        """Handle a PATCH."""
        self._handle()

    def do_DELETE(self) -> None:
        """Handle a DELETE."""
        self._handle()

    def do_OPTIONS(self) -> None:
        """Handle an OPTIONS."""
        self._handle()

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - the stdlib's name
        """Log each request through ``logging`` instead of writing to stderr."""
        log.info("%s %s", self.address_string(), format % args)

    def _handle(self) -> None:
        """Route the request by its path."""
        prefix = self.server.prefix
        path, question, query = self.path.partition("?")
        if path == prefix:
            self._answer(301, location=f"{prefix}/{question}{query}")
            return
        if not path.startswith(f"{prefix}/"):
            self._answer(404)
            return
        self._forward(self.path[len(prefix) :])

    def _answer(self, status: int, *, location: str | None = None) -> None:
        """Send an empty response with ``status`` and, for a redirect, ``location``."""
        self.send_response(status)
        if location is not None:
            self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _forward(self, upstream_path: str) -> None:
        """Send the request to the upstream at ``upstream_path`` and relay its answer."""
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length > 0 else None
        connection = http.client.HTTPConnection(
            LOOPBACK, self.server.upstream_port, timeout=UPSTREAM_TIMEOUT
        )
        try:
            connection.request(self.command, upstream_path, body=body, headers=self._headers())
            response = connection.getresponse()
        except OSError as error:
            log.warning("upstream %s unreachable: %s", self.server.upstream_port, error)
            self._answer(502)
            connection.close()
            return
        try:
            self._relay(response)
        finally:
            connection.close()

    def _headers(self) -> dict[str, str]:
        """The request's end-to-end headers plus the ``X-Forwarded-*`` set."""
        kept = {
            name: value
            for name, value in self.headers.items()
            if name.lower() not in HOP_BY_HOP | FORWARDED
        }
        host = self.headers.get("Host", f"{LOOPBACK}:{self.server.server_address[1]}")
        return {
            **kept,
            "X-Forwarded-For": self.client_address[0],
            "X-Forwarded-Host": host,
            "X-Forwarded-Proto": "http",
            "X-Forwarded-Prefix": self.server.prefix,
            "Connection": "close",
        }

    def _relay(self, response: http.client.HTTPResponse) -> None:
        """Copy the upstream's status, headers and body to the client as they arrive."""
        self.send_response(response.status, response.reason)
        for name, value in response.getheaders():
            if name.lower() not in HOP_BY_HOP | SELF_WRITTEN_ON_RESPONSE:
                self.send_header(name, value)
        self.end_headers()
        if self.command != "HEAD":
            shutil.copyfileobj(response, self.wfile, CHUNK_SIZE)


class PrefixProxyServer(ThreadingHTTPServer):
    """A threaded HTTP server that knows its prefix and its upstream's port."""

    daemon_threads = True

    def __init__(self, port: int, *, upstream_port: int, prefix: str) -> None:
        """Bind to ``port`` on loopback (``0`` picks a free one) for ``prefix``."""
        self.prefix = prefix
        self.upstream_port = upstream_port
        super().__init__((LOOPBACK, port), PrefixProxyHandler)


def build_server(*, port: int, upstream_port: int, prefix: str) -> PrefixProxyServer:
    """Build, but do not start, a proxy for ``prefix`` in front of ``upstream_port``.

    ``prefix`` must start with a slash, not end with one, and not be the slash alone
    (``/caldart-proto``); anything else raises ``ValueError`` naming the prefix.
    """
    if not prefix.startswith("/") or prefix.endswith("/"):
        raise ValueError(f"prefix {prefix!r} is not a path such as /caldart-proto")
    return PrefixProxyServer(port, upstream_port=upstream_port, prefix=prefix)


def main() -> None:
    """Parse the command line and serve until interrupted."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, required=True, help="the port to listen on")
    parser.add_argument("--upstream-port", type=int, required=True, help="the server's port")
    parser.add_argument("--prefix", required=True, help="the URL prefix, such as /caldart-proto")
    options = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    try:
        server = build_server(
            port=options.port, upstream_port=options.upstream_port, prefix=options.prefix
        )
    except ValueError as error:
        parser.error(str(error))
    log.info(
        "serving %s on port %s in front of port %s",
        options.prefix,
        options.port,
        options.upstream_port,
    )
    with server:
        server.serve_forever()


if __name__ == "__main__":
    main()
