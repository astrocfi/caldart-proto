==========
Deployment
==========

How to put CalDART on a single Linux server: Postgres in Docker, gunicorn under
systemd, Apache in front terminating TLS.  Apache is the primary target because
the machines this is aimed at already run it; an nginx configuration ships as
the alternative and is called out where the two differ.

Every path below assumes the deploy root
``/srv/caldart``.  If you use another, change it in all six files that name it:
``deploy/gunicorn.conf.py``, ``deploy/apache/caldart.conf``,
``deploy/nginx/caldart.conf`` and all three units under ``deploy/systemd/``.
``grep -rn /srv/caldart deploy/`` finds every occurrence.


What you are deploying
======================

::

  browser ──HTTPS──▶ Apache :443 ──HTTP──▶ gunicorn 127.0.0.1:8001
                       │                      │
                       ├─ /media/  from disk  ├─ Django + Wagtail
                       └─ ACME challenges     ├─ /static/ via whitenoise
                                              └─ Postgres in Docker :5432

Three things run continuously: the Docker Postgres container, the
``caldart-web`` gunicorn unit, and Apache.  One thing runs daily: the
``caldart-reminders`` timer.

``/static/`` is deliberately **not** aliased in the web server.  whitenoise
serves it through the proxy so that the hashed filenames ``collectstatic``
produces stay authoritative and get far-future cache headers.  Only
``/media/`` — Wagtail's user uploads, which keep their filenames — is served
straight off disk.


1. Operating system packages
============================

On Debian or Ubuntu::

  sudo apt update
  sudo apt install -y \
      apache2 \
      docker.io docker-compose-plugin \
      git curl ca-certificates \
      postgresql-client

  # Node 20+ for the frontend build, and uv for the Python side.
  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
  sudo apt install -y nodejs
  curl -LsSf https://astral.sh/uv/install.sh | sudo sh

``postgresql-client`` is optional but recommended: ``db_backup`` and
``db_restore`` prefer a local ``pg_dump``/``psql`` and fall back to running them
inside the container.  Set ``DB_BACKUP_VIA_DOCKER=false`` once the client is
installed.

uv installs its own Python 3.12 if the system has none, so no ``python3.12``
package is needed.


2. Service user and directories
===============================

::

  sudo useradd --system --home-dir /srv/caldart --shell /usr/sbin/nologin caldart
  sudo usermod -aG docker caldart          # only if the app must talk to compose
  sudo install -d -o root -g caldart -m 0755 /srv/caldart
  sudo install -d -o root -g caldart -m 0750 /etc/caldart

The checkout is owned by root and readable by the service user; the unit file
mounts everything read-only except three directories, which the service user
owns::

  sudo install -d -o caldart -g caldart \
      /srv/caldart/backend/media \
      /srv/caldart/backend/staticfiles \
      /srv/caldart/backups


3. The checkout
===============

::

  sudo git clone https://github.com/astrocfi/caldart-proto.git /srv/caldart
  cd /srv/caldart


4. Postgres in Docker
=====================

``docker-compose.yml`` at the repository root defines the ``db`` service with a
named volume, ``caldart_pgdata``, so the data survives ``docker compose down``
and container upgrades::

  sudo docker compose up -d db
  sudo docker compose ps

.. warning::

   ``docker-compose.yml`` publishes the database as ``"5432:5432"``, which
   binds **every** interface, not just loopback.  That is right for a
   development machine and wrong for a server.  Before this box is reachable
   from anywhere, either change the mapping to ``"127.0.0.1:5432:5432"`` or
   block 5432 at the firewall — and change the password either way.

Change the password from the development default before anything real goes
in::

  sudo docker compose exec -T db psql -U caldart -d postgres \
      -c "ALTER USER caldart WITH PASSWORD 'a-long-random-password';"

and put the same password in ``DATABASE_URL`` in the next step.

Create the production database if it is not the default ``caldart``::

  sudo docker compose exec -T db createdb -U caldart -O caldart caldart


5. Configuration
================

``/etc/caldart/caldart.env`` holds every runtime setting.  Start from the
checked-in example and edit it::

  sudo install -m 0640 -o root -g caldart .env.example /etc/caldart/caldart.env
  sudoedit /etc/caldart/caldart.env

At minimum, production needs these, and four of them have no default at all —
``prod.py`` refuses to start without ``SECRET_KEY``, ``ALLOWED_HOSTS``,
``SITE_URL`` and ``EMAIL_URL``::

  DATABASE_URL=postgres://caldart:a-long-random-password@localhost:5432/caldart
  SECRET_KEY=<50+ random characters>
  DEBUG=false
  ALLOWED_HOSTS=caldart.example.org,www.caldart.example.org
  SITE_URL=https://caldart.example.org
  CSRF_TRUSTED_ORIGINS=https://caldart.example.org,https://www.caldart.example.org
  EMAIL_URL=smtp+tls://user:password@smtp.example.org:587
  DEFAULT_FROM_EMAIL=CalDART <noreply@caldart.example.org>
  PAYMENTS_MOCK_ENABLED=false
  DJANGO_VITE_DEV_MODE=false
  BACKUP_DIR=/srv/caldart/backups
  DB_BACKUP_VIA_DOCKER=false

Generate a secret key with::

  python3 -c "import secrets; print(secrets.token_urlsafe(64))"

:doc:`configuration` documents every variable, what reads it, and its
development and production values.  The Stripe and PayPal keys are covered in
:doc:`payments-setup`.

The file is root-owned, mode 0640, group ``caldart``.  It contains the database
password, the Django secret key and the payment provider secrets; it should
never be world-readable and never be committed.


6. Build
========

::

  cd /srv/caldart
  sudo uv sync --frozen --no-dev
  cd frontend && sudo npm ci && sudo npm run build && cd ..

``npm run build`` writes ``frontend/dist`` including
``.vite/manifest.json``, which django-vite reads to find the hashed asset
names.  Without it every page raises at render time.


7. Database and static files
============================

Run these as the service user with the production settings::

  cd /srv/caldart/backend
  sudo -u caldart env $(grep -v '^#' /etc/caldart/caldart.env | xargs) \
      DJANGO_SETTINGS_MODULE=caldart.settings.prod \
      /srv/caldart/.venv/bin/python manage.py migrate

  sudo -u caldart ... manage.py seed_roles
  sudo -u caldart ... manage.py seed_content     # example pages; optional
  sudo -u caldart ... manage.py collectstatic --noinput

Do **not** run ``seed_demo`` on a production box: it creates demo accounts with
a published password.

Create the first real administrator::

  sudo -u caldart ... manage.py createsuperuser

then sign in at ``/admin/`` and give the account its roles, or from a shell::

  sudo -u caldart ... manage.py shell -c "
  from django.contrib.auth import get_user_model
  u = get_user_model().objects.get(email='you@example.org')
  for role in ['member','system_admin','website_admin']:
      u.add_role(role)
  "

``system_admin`` plus ``is_superuser`` is what unlocks ``/portal/system`` and
the Wagtail admin.


8. gunicorn under systemd
=========================

::

  sudo cp deploy/systemd/caldart-web.service /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable --now caldart-web.service
  systemctl status caldart-web
  curl -sI http://127.0.0.1:8001/ | head -1

The unit runs ``/srv/caldart/.venv/bin/gunicorn --config
/srv/caldart/deploy/gunicorn.conf.py`` as ``caldart``, with
``DJANGO_SETTINGS_MODULE=caldart.settings.prod`` and the environment file from
step 5.  ``deploy/gunicorn.conf.py`` binds loopback only, sizes the worker pool
at ``2 × cores + 1`` **capped at 12** — every worker preloads Django and
Wagtail, so a large machine would otherwise spend its memory on idle processes
— sets a 60 second worker timeout, logs to stdout, and trusts
``X-Forwarded-*`` only from ``127.0.0.1``.  Set ``WEB_CONCURRENCY`` in the
environment file to override the count outright.

It is hardened with the usual systemd sandbox — ``ProtectSystem=strict``,
``NoNewPrivileges``, an empty capability set — so the only writable paths are
``media/``, ``staticfiles/`` and ``backups/``.  If you move ``BACKUP_DIR``, add
the new path to ``ReadWritePaths`` or backups will fail with a permission
error.


9. Apache
=========

Enable the modules the vhost needs, install it, and check the syntax::

  sudo a2enmod proxy proxy_http headers ssl rewrite deflate expires http2
  sudo cp deploy/apache/caldart.conf /etc/apache2/sites-available/caldart.conf
  sudoedit /etc/apache2/sites-available/caldart.conf   # set ServerName
  sudo a2ensite caldart
  sudo apachectl configtest
  sudo systemctl reload apache2

The vhost:

* redirects port 80 to HTTPS, except ``/.well-known/acme-challenge/``;
* proxies everything to ``http://127.0.0.1:8001/`` with
  ``ProxyPreserveHost On``;
* sets ``X-Forwarded-Proto: https`` — this is what ``SECURE_PROXY_SSL_HEADER``
  in ``prod.py`` reads, and gunicorn only accepts it from loopback, so a client
  cannot forge it;
* serves ``/media/`` from ``/srv/caldart/backend/media/`` with a one-week cache
  and ``X-Content-Type-Options: nosniff``, and excludes it from the proxy;
* sets HSTS, ``nosniff`` and a referrer policy, and leaves ``X-Frame-Options``
  to Django so Wagtail's page previews keep working;
* caps request bodies at 25 MB, matching ``DATA_UPLOAD_MAX_MEMORY_SIZE``.

TLS with certbot::

  sudo apt install -y certbot
  sudo install -d /var/www/certbot
  sudo certbot certonly --webroot -w /var/www/certbot \
       -d caldart.example.org -d www.caldart.example.org
  sudo systemctl reload apache2

Renewal is handled by certbot's own timer; the port-80 vhost keeps the ACME
path reachable, so nothing else is needed.  Check it with
``sudo certbot renew --dry-run``.

Turn HSTS off for the first deploy of a new hostname — set
``SECURE_HSTS_SECONDS=0`` and comment out the ``Strict-Transport-Security``
header — until HTTPS is known good.  Browsers honour the header for its full
duration and there is no way to take it back early.

nginx instead
-------------

Use one or the other, never both on the same host::

  sudo cp deploy/nginx/caldart.conf /etc/nginx/sites-available/caldart
  sudo ln -s /etc/nginx/sites-available/caldart /etc/nginx/sites-enabled/
  sudo nginx -t && sudo systemctl reload nginx

It is the same shape: ACME on port 80, TLS and proxying on 443,
``proxy_set_header X-Forwarded-Proto $scheme``, ``/media/`` from disk,
``client_max_body_size 25m``.


10. Renewal reminders
=====================

::

  sudo cp deploy/systemd/caldart-reminders.service \
          deploy/systemd/caldart-reminders.timer /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable --now caldart-reminders.timer
  systemctl list-timers caldart-reminders.timer

Daily at 07:00, with catch-up if the machine was off.  See :doc:`reminders` for
the kinds, the templates and how to change the cadence.


11. Backups
===========

Take one now and schedule them::

  cd /srv/caldart/backend
  sudo -u caldart ... manage.py db_backup

:doc:`backup-restore` covers the commands, the timer, retention and restoring.


Checking it worked
==================

::

  systemctl status caldart-web caldart-reminders.timer
  sudo docker compose ps
  curl -sI https://caldart.example.org/ | head -1
  cd /srv/caldart/backend && sudo -u caldart ... manage.py health --json

The ``health`` command prints the same report as ``GET /system/health`` and the
health panel of ``/portal/system``: database connectivity, pending migrations,
free space on the backup filesystem, the last backup, the version from
``pyproject.toml``, and whether ``DEBUG`` is on.  On a healthy production box
``debug`` is ``false`` and ``pending_migrations`` is ``0``.

Then, in a browser: the public site loads and is styled, ``/portal/`` signs you
in, ``/admin/`` opens Wagtail, and ``/portal/system`` shows three green panels.


Logs
====

Everything goes to the journal; there are no application log files to rotate.

===========================  =================================================
What                         Where
===========================  =================================================
Application, gunicorn        ``journalctl -u caldart-web -f``
Reminder runs                ``journalctl -u caldart-reminders -n 50``
Apache :443 access / error   ``/var/log/apache2/caldart-{access,error}.log``
Apache :80 access / error    ``/var/log/apache2/caldart-http-{access,error}.log``
                             — the redirect vhost, and therefore where a
                             failing ACME challenge shows up
nginx access / error         ``/var/log/nginx/caldart-{access,error}.log``
Postgres                     ``sudo docker compose logs -f db``
===========================  =================================================

``LOG_LEVEL`` in the environment file sets Django's root level; ``INFO`` is the
default and ``WARNING`` is reasonable once things are quiet.


Upgrading
=========

Take a backup first, always::

  cd /srv/caldart/backend
  sudo -u caldart ... manage.py db_backup

  cd /srv/caldart
  sudo git pull
  sudo uv sync --frozen --no-dev
  cd frontend && sudo npm ci && sudo npm run build && cd ..

  cd backend
  sudo -u caldart ... manage.py migrate
  sudo -u caldart ... manage.py collectstatic --noinput

  sudo systemctl restart caldart-web
  journalctl -u caldart-web -n 30

Order matters: build the frontend before ``collectstatic``, and restart the web
unit last.  ``preload_app`` is on, so a restart — not a reload — is what picks
up new code.

Rolling back is the same sequence against the previous commit, plus a
``db_restore`` if the migration was not backwards compatible.


Troubleshooting
===============

**502 from Apache.**  gunicorn is not running or not on 8001.  ``systemctl
status caldart-web``, then ``journalctl -u caldart-web -n 50``.

**``DisallowedHost`` in the log.**  The hostname is missing from
``ALLOWED_HOSTS``.  Add it and restart.

**CSRF failures when signing in.**  ``CSRF_TRUSTED_ORIGINS`` must list the
``https://`` origin, and the proxy must set ``X-Forwarded-Proto``.  Both are in
this document; check the vhost was actually reloaded.

**Unstyled pages, or ``Manifest file not found``.**  ``npm run build`` did not
run, or ``collectstatic`` did not.  Run both, then restart the unit.

**``ValueError: Missing staticfiles manifest entry``.**  ``collectstatic`` ran
before the frontend build.  Run them in that order and restart.

**Backups fail with a permission error.**  ``BACKUP_DIR`` is outside the
``ReadWritePaths`` in ``caldart-web.service``, or is not owned by ``caldart``.

**Redirect loop.**  ``SECURE_SSL_REDIRECT`` is on but the proxy is not sending
``X-Forwarded-Proto: https``, so Django redirects a request it thinks is plain
HTTP, forever.  Fix the header rather than turning the redirect off.

**No email.**  Check ``EMAIL_URL`` and try
``manage.py send_renewal_reminders --dry-run``; then send one for real and read
``journalctl -u caldart-web``.  Many providers need
``smtp+tls://`` on port 587 with an app password rather than the account one.
