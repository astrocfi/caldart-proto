"""Gunicorn configuration for the CalDART application server (PLAN.rst §13).

The deploy path is ``/srv/caldart`` -- a checkout of this repository with its
``uv``-managed virtualenv at ``/srv/caldart/.venv``.  Loaded by the systemd
unit in ``deploy/systemd/caldart-web.service``::

    /srv/caldart/.venv/bin/gunicorn --config /srv/caldart/deploy/gunicorn.conf.py

Gunicorn listens on loopback only; Apache (``deploy/apache/caldart.conf``) or
nginx (``deploy/nginx/caldart.conf``) terminates TLS and proxies to it.
Runtime configuration -- database, secret key, allowed hosts, payment keys --
comes from ``/etc/caldart/caldart.env`` via the unit's ``EnvironmentFile``, not
from this file.
"""

import multiprocessing

# --- Application ------------------------------------------------------------

# Django project root.  manage.py, the caldart package, media/ and
# staticfiles/ all live here, and relative paths in settings resolve from it.
chdir = "/srv/caldart/backend"

# The WSGI callable, resolved relative to ``chdir``.
wsgi_app = "caldart.wsgi:application"

# Shows up in ``ps`` and in systemd's cgroup listing.
proc_name = "caldart-web"

# --- Socket -----------------------------------------------------------------

# Loopback only: the reverse proxy is the sole entry point, so the app server
# is never reachable from outside the machine.
bind = "127.0.0.1:8001"

# Kernel-side accept queue for bursts while workers are busy.
backlog = 2048

# --- Worker processes -------------------------------------------------------

# The usual (2 x cores) + 1 heuristic for synchronous workers, computed at
# start-up so the same file suits a 2-core VM and a 16-core box.
workers = multiprocessing.cpu_count() * 2 + 1

# Plain prefork workers.  Django here is synchronous (psycopg 3, httpx calls to
# Stripe/PayPal made inline during checkout), so sync workers are the right
# default; revisit only if a request path becomes genuinely I/O-bound.
worker_class = "sync"

# A couple of threads per worker absorbs slow upstream payment API calls
# without multiplying process memory.
threads = 2

# Ceiling on concurrent connections per worker.
worker_connections = 1000

# Recycle workers periodically to bound memory growth; the jitter keeps them
# from all restarting on the same request count.
max_requests = 1000
max_requests_jitter = 100

# Load the app before forking: workers share the parsed code and Django app
# registry, which cuts memory use and start-up time.  Costs the ability to
# reload code with SIGHUP alone -- deploys restart the unit anyway.
preload_app = True

# --- Timeouts ---------------------------------------------------------------

# Kill and replace a worker silent for this long.  Generous enough for a PDF
# report over a large filtered member list, tight enough to shed a wedged
# worker quickly.
timeout = 60

# Grace period for in-flight requests to finish on restart or shutdown.
graceful_timeout = 30

# Hold idle keep-alive connections briefly; the proxy is local, so this only
# needs to cover the next request on the same connection.
keepalive = 5

# --- Proxy awareness --------------------------------------------------------

# Trust X-Forwarded-* only from the local reverse proxy.  This is what lets
# Django see the original scheme via SECURE_PROXY_SSL_HEADER (PLAN §13) and
# stops a client from spoofing "already HTTPS" through a forged header.
forwarded_allow_ips = "127.0.0.1"
proxy_allow_ips = "127.0.0.1"

# Cap request-line and header sizes to blunt trivially malformed requests.
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# --- Logging ----------------------------------------------------------------

# "-" means stdout for access logs and stderr for error logs, so journald
# captures everything: ``journalctl -u caldart-web``.  No log files to rotate.
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Log the real client address from the proxy rather than 127.0.0.1, plus the
# response time in seconds, which is what makes slow report endpoints visible.
access_log_format = (
    '%({x-forwarded-for}i)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(L)s'
)

# Send gunicorn's own diagnostics through the same handlers as the access log.
capture_output = True
