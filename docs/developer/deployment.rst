==========
Deployment
==========

How to put CalDART on a single Linux server: Postgres in Docker, gunicorn under
systemd, Apache in front terminating TLS.  Apache is the primary target because
the machines this is aimed at already run it; an nginx configuration ships as
the alternative and is called out where the two differ.

Every path below assumes the deploy root
``/srv/caldart``.  If you use another, change it in all six files that name it:
``deploy/gunicorn.conf.py``, ``deploy/apache/caldart.conf``
, ``deploy/nginx/caldart.conf``, and all three units under ``deploy/systemd/``.
``grep -rn /srv/caldart deploy/`` finds every occurrence.


What you are deploying
======================

.. only:: graphviz

   .. graphviz::
      :caption: One server, from the outside in: the web request path.  A
                **solid arrow** is a request, labeled with the protocol and the
                port it arrives on; a **dashed arrow** is an outbound call the
                application makes; a **dotted arrow** is a file read straight
                off disk.  The **dashed box** is the one machine.  ``nginx``
                (``deploy/nginx/caldart.conf``) takes Apache's place unchanged
                when you deploy it instead.
      :alt: Topology of a CalDART production server: Apache, gunicorn,
            Django, Postgres in Docker, the media directory, and the
            environment file, with the browser, the payment providers, and
            the SMTP server outside it

      digraph caldart_web {
          rankdir=TB;
          bgcolor="transparent";
          nodesep=0.35;
          ranksep=0.45;
          node [shape=box, style="rounded", fontname="Helvetica", fontsize=11];
          edge [fontname="Helvetica", fontsize=11];

          Browser [label="Browser\l  member portal, public site,\l  Wagtail admin\l"];
          Stripe [label="Stripe and PayPal\l  api.stripe.com,\l  api-m.paypal.com\l"];
          Smtp [label="SMTP server\l  from EMAIL_URL\l"];

          subgraph cluster_server {
              label="One Linux server, deploy root /srv/caldart";
              fontname="Helvetica";
              fontsize=11;
              style=dashed;
              color="gray";

              Apache [label="Apache 2.4 :80 and :443\l  deploy/apache/caldart.conf\l  terminates TLS (certbot)\l  :80 -> :443, except ACME\l  ProxyTimeout 60\l"];
              Gunicorn [label="gunicorn 127.0.0.1:8001\l  caldart-web.service\l  deploy/gunicorn.conf.py\l  2 x CPU + 1 workers, max 12\l  timeout 60, preload\l"];
              Django [label="Django 6 + Wagtail 8\l  caldart.settings.prod\l  /static/ via whitenoise\l"];
              Postgres [label="Postgres in Docker :5432\l  compose service db\l"];
              Media [label="backend/media/\l  Wagtail uploads;\l  documents/ denied to\l  the web server\l", shape=folder, style=""];
              Env [label="/etc/caldart/caldart.env\l  root:caldart 0640\l  EnvironmentFile for\l  all five services\l", shape=note, style=""];

              Apache -> Gunicorn [label="HTTP 127.0.0.1:8001\lX-Forwarded-Proto: https\l"];
              Gunicorn -> Django [label="WSGI\lcaldart.wsgi:application\l", arrowhead=none];
              Django -> Postgres [label="DATABASE_URL\l"];
              Apache -> Media [label="/media/ off disk\l", style=dotted];
              Django -> Media [label="/documents/<id>/<name>\lafter the members-only\lcheck\l", style=dotted];
              Env -> Gunicorn [label="settings\l", style=dashed, arrowhead=none];
          }

          Browser -> Apache [label="HTTPS :443\lHTTP :80 redirected\l"];
          Django -> Stripe [label="checkout and\lconfirm\l", style=dashed];
          Stripe -> Apache [label="webhooks,\lHTTPS :443\l"];
          Django -> Smtp [label="password resets,\linvitations\l", style=dashed];
      }

   .. graphviz::
      :caption: The same server's four scheduled jobs.  Each timer starts its
                service, which runs one management command and exits.  A
                **solid arrow** is the job reading and writing the database; a
                **dashed arrow** is an outbound call.  Every job service reads
                its settings from the same environment file as
                ``caldart-web.service``, so the server runs five services in
                all.
      :alt: The four CalDART timers and their services, each writing to
            Postgres and sending mail, with the renewals job also charging
            through Stripe and PayPal

      digraph caldart_jobs {
          rankdir=LR;
          bgcolor="transparent";
          nodesep=0.35;
          ranksep=0.9;
          node [shape=box, style="rounded", fontname="Helvetica", fontsize=11];
          edge [fontname="Helvetica", fontsize=11];

          Env [label="/etc/caldart/caldart.env\l  EnvironmentFile for\l  every job service\l", shape=note, style=""];
          Reports [label="caldart-reports.timer\l  daily 06:00 ->\l  caldart-reports.service\l  manage.py send_scheduled_reports\l"];
          Renewals [label="caldart-renewals.timer\l  daily 06:30 ->\l  caldart-renewals.service\l  manage.py run_auto_renewals\l"];
          Reminders [label="caldart-reminders.timer\l  daily 07:00 ->\l  caldart-reminders.service\l  manage.py send_renewal_reminders\l"];
          Statements [label="caldart-statements.timer\l  yearly Jan 15, 06:45 ->\l  caldart-statements.service\l  manage.py send_year_statements\l"];
          Stripe [label="Stripe and PayPal\l  off-session charges\l"];
          Postgres [label="Postgres in Docker :5432\l"];
          Smtp [label="SMTP server\l  from EMAIL_URL\l"];

          {rank=same; Stripe; Postgres; Smtp;}
          {rank=same; Reports; Renewals; Reminders; Statements;}
          Stripe -> Postgres -> Smtp [style=invis];
          Reports -> Renewals -> Reminders -> Statements [style=invis];

          Env -> {Reports Renewals Reminders Statements} [style=dashed, arrowhead=none];
          Renewals -> Stripe [style=dashed];
          Reports -> Postgres;
          Renewals -> Postgres;
          Reminders -> Postgres;
          Statements -> Postgres;
          Reports -> Smtp [style=dashed];
          Renewals -> Smtp [style=dashed];
          Reminders -> Smtp [style=dashed];
          Statements -> Smtp [style=dashed];
      }

.. only:: not graphviz

   Install Graphviz and rebuild for drawn versions of these diagrams.  The two
   drawings and the sketch below carry the same pieces and the same traffic.

   .. code-block:: text

      browser --HTTPS :443--> Apache 2.4 --HTTP--> gunicorn 127.0.0.1:8001
      (:80 redirects              |                   |
       except ACME)               |                   |  caldart-web.service
                                  |                   |  2 x CPU + 1 workers,
            serves /media/ -------'                   |  max 12, timeout 60
            off disk; documents/ is denied,           v
            because Django's members-only       Django 6 + Wagtail 8
            check is the only way in            caldart.settings.prod
                                                /static/ via whitenoise
      Stripe / PayPal webhooks arrive                 |
      through Apache like any other request           v
                                                Postgres in Docker :5432
      caldart-reports.timer, daily 06:00              ^
        -> caldart-reports.service                    |
           manage.py send_scheduled_reports ----------|
           -> the SMTP server, for the report         |
              subscriptions and the DART rosters      |
                                                      |
      caldart-renewals.timer, daily 06:30             |
        -> caldart-renewals.service                   |
           manage.py run_auto_renewals ---------------|
           -> Stripe / PayPal for the off-session     |
              charges, and the SMTP server for the    |
              renewal notices and receipts            |
                                                      |
      caldart-reminders.timer, daily 07:00            |
        -> caldart-reminders.service                  |
           manage.py send_renewal_reminders ----------|
           -> the SMTP server from EMAIL_URL          |
                                                      |
      caldart-statements.timer, yearly Jan 15, 06:45  |
        -> caldart-statements.service                 |
           manage.py send_year_statements ------------'
           -> the SMTP server, for the contribution statements

   Apache, gunicorn, Postgres, and the four timers run on one Linux server with
   the deploy root ``/srv/caldart``, and all five services (``caldart-web`` and
   the four job services) read their settings from ``/etc/caldart/caldart.env``
   (``root:caldart``, mode ``0640``).  Django calls out to ``api.stripe.com``
   and ``api-m.paypal.com`` during a checkout, and to the same SMTP server for
   password resets and invitations.  ``nginx`` (``deploy/nginx/caldart.conf``)
   takes Apache's place unchanged when you deploy it instead.

Three things run continuously: the Docker Postgres container, the
``caldart-web`` gunicorn unit, and Apache.  Four jobs run on a schedule: the
``caldart-reports`` timer daily at 06:00, the ``caldart-renewals`` timer daily
at 06:30, the ``caldart-reminders`` timer daily at 07:00, and the
``caldart-statements`` timer yearly at 06:45 on January 15th.

The application is a **Django 6** project with Wagtail 8 on top, and step 6
installs it with ``uv sync --frozen``, so the box runs the exact versions
``uv.lock`` pins and the ones the test suite ran against.  Django 6 configures
outgoing mail through its ``MAILERS`` setting, which ``prod.py`` builds from
``EMAIL_URL`` and ``EMAIL_TIMEOUT``; both are in the environment file written
in step 5 and documented in :doc:`configuration`.

``/static/`` is deliberately **not** aliased in the web server.  whitenoise
serves it through the proxy so that the hashed filenames ``collectstatic``
produces stay authoritative and get far-future cache headers.  The user guide
at ``/docs/`` is not aliased either: Django serves it from ``USER_GUIDE_ROOT``
and asks the reader to sign in first, so it stays behind the same login as the
portal and needs nothing from the web server (:doc:`configuration`).  Only
``/media/`` — Wagtail's user uploads, which keep their filenames — is served
straight off disk, and ``/media/documents/`` is carved back out of it: a
document may belong to the members-only collection, and Django's document view
is what enforces that (:doc:`cms`).  Both vhosts refuse that prefix, so a
document is only ever reachable at ``/documents/<id>/<filename>``.


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

``docker-compose.yml`` publishes the database as ``"127.0.0.1:5432:5432"``, so
it listens on loopback only and nothing off the box can reach port 5432.

.. warning::

   The password is still the development default.  Change it before anything
   real goes in.

Change it with::

  sudo docker compose exec -T db psql -U caldart -d postgres \
      -c "ALTER USER caldart WITH PASSWORD 'a-long-random-password';"

and put the same password in ``DATABASE_URL`` in the next step.

Create the production database if it is not the default ``caldart``::

  sudo docker compose exec -T db createdb -U caldart -O caldart caldart


5. Configuration
================

``/etc/caldart/caldart.env`` holds every runtime setting.  Start from the
**production** template and edit it::

  sudo install -m 0640 -o root -g caldart \
       deploy/caldart.env.example /etc/caldart/caldart.env
  sudoedit /etc/caldart/caldart.env

.. warning::

   Do not install the repository's ``.env.example``.  That one is the
   development template: it ships the published ``SECRET_KEY`` and sets
   ``PAYMENTS_MOCK_ENABLED=true``, which renders "Succeed" and "Fail" buttons
   at checkout and would hand out memberships for free.

The five variables at the top of the template are commented out, so an
unedited copy refuses to start rather than serving with a guessed value.
Uncomment and set every one::

  SECRET_KEY=<50+ random characters>
  ALLOWED_HOSTS=caldart.example.org,www.caldart.example.org
  SITE_URL=https://caldart.example.org
  EMAIL_URL=smtp+tls://user:password@smtp.example.org:587
  DATABASE_URL=postgres://caldart:a-long-random-password@localhost:5432/caldart

Four of them have no default at all — ``prod.py`` refuses to start without
``SECRET_KEY``, ``ALLOWED_HOSTS``, ``SITE_URL``, or ``EMAIL_URL``, and refuses
the published development ``SECRET_KEY`` as well.  Nothing in the production
settings reads a ``.env`` file, so a stray one in the checkout cannot fill in a
variable you missed.

Generate a secret key with::

  python3 -c "import secrets; print(secrets.token_urlsafe(64))"

Then work down the rest of the template: ``CSRF_TRUSTED_ORIGINS``,
``DEFAULT_FROM_EMAIL``, the Stripe and PayPal keys, ``BACKUP_DIR``, and
``DB_BACKUP_VIA_DOCKER``.  :doc:`configuration` documents every variable, what
reads it, and its development and production values.  The Stripe and PayPal
keys are covered in :doc:`payments-setup`.

The file is root-owned, mode 0640, group ``caldart``.  It contains the database
password, the Django secret key and the payment provider secrets; it should
never be world-readable and never be committed.


.. _deploy-build:

6. Build
========

::

  cd /srv/caldart
  sudo uv sync --frozen --no-dev --group docs
  cd frontend && sudo npm ci && sudo npm run build && cd ..
  sudo uv run sphinx-build -n -W -b dirhtml -t guide -c docs docs/user docs/_build/guide

``npm run build`` writes ``frontend/dist`` including
``.vite/manifest.json``, which django-vite reads to find the hashed asset
names.  Without it every page raises at render time.

``--group docs`` installs Sphinx and its theme, which the last line uses to
build the user guide into ``docs/_build/guide``, the directory Django serves at
``/docs/`` to signed-in users (it is ``make guide`` on a checkout).  The
developer guide is not published: the build reads ``docs/user`` alone.  Without
this step ``/docs/`` answers 404 and the journal says the guide has not been
built.  A deployment that keeps the guide elsewhere sets ``USER_GUIDE_ROOT``.


7. Database and static files
============================

.. _deploy-manage-commands:

Running management commands
---------------------------

A management command needs the same five things ``caldart-web.service`` gives
gunicorn: the ``caldart`` user, ``/srv/caldart/backend`` as the working
directory, ``/etc/caldart/caldart.env``,
``DJANGO_SETTINGS_MODULE=caldart.settings.prod``, and ``UMask=0027``.  Let
systemd assemble them again, as a transient unit, instead of loading the
environment file from a shell.  systemd keeps interior whitespace in an
unquoted value, so ``DEFAULT_FROM_EMAIL=CalDART <noreply@caldart.example.org>``
reaches the command intact; a shell splits it at the spaces and the command
never starts.

Define this function once in the shell you are deploying from.  Every
production command in this document and in :doc:`backup-restore` is written as
a call to it::

  caldart_manage() {
      sudo systemd-run --quiet --wait --collect --pty --pipe \
          --uid=caldart --gid=caldart \
          --working-directory=/srv/caldart/backend \
          --property=EnvironmentFile=/etc/caldart/caldart.env \
          --property=UMask=0027 \
          --setenv=DJANGO_SETTINGS_MODULE=caldart.settings.prod \
          /srv/caldart/.venv/bin/python manage.py "$@"
  }

``--wait`` blocks until the command finishes and hands its exit status back, so
``caldart_manage`` can be tested in a script.  ``--collect`` unloads the
transient unit afterwards, including when it failed.  Given both ``--pty`` and
``--pipe``, systemd allocates a terminal when one is attached — which
``createsuperuser`` and the ``db_restore`` prompt need — and passes plain pipes
through when the output is redirected.

``UMask=0027`` is the one property with nothing to do with finding the code or
the settings, and it is not optional: a transient unit otherwise takes
systemd's system default of ``0022``, and ``caldart_manage db_backup`` would
write a full dump of the database — member records, password hashes, payment
history — world-readable at mode 0644.  ``caldart-web.service``
, ``caldart-reminders.service``, and the ``caldart-backup.service`` in
:doc:`backup-restore` set the same mask, so every path that writes a dump
writes it readable by the ``caldart`` group and no wider.

Confirm the environment file is being read before relying on it::

  sudo systemd-run --quiet --wait --pipe \
      --property=EnvironmentFile=/etc/caldart/caldart.env \
      /usr/bin/printenv DEFAULT_FROM_EMAIL

That prints the value exactly as the file spells it, spaces included.

Preparing the database
----------------------

::

  caldart_manage migrate
  caldart_manage createcachetable
  caldart_manage seed_roles
  caldart_manage seed_content     # example pages; optional
  caldart_manage collectstatic --noinput

``createcachetable`` builds ``caldart_cache``, the table the default cache
uses.  The anonymous auth throttles count in that cache, and every gunicorn
worker has to see the same counters; the PayPal access token sits there too,
so one fetch serves every worker (see :ref:`paypal-token-cache`).  The command
is idempotent, so running it again costs nothing.

Do **not** run ``seed_demo`` on a production box: it creates demo accounts with
a published password.

Create the first real administrator::

  caldart_manage createsuperuser

then sign in at ``/admin/`` and give the account its roles, or from a shell::

  caldart_manage shell -c "
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
``media/``, ``staticfiles/``, and ``backups/``.  If you move ``BACKUP_DIR``, add
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
* denies ``/srv/caldart/backend/media/documents``, the directory Wagtail writes
  document uploads to, with ``Require all denied``.  The deeper ``<Directory>``
  section is applied after the one above it, so it wins;
* sets **no** security headers of its own on proxied responses.  HSTS,
  ``X-Content-Type-Options``, ``Referrer-Policy``, and ``X-Frame-Options`` all
  come from ``prod.py``, where they are configurable per deployment.  A second
  copy from the vhost would both duplicate the header and override the
  settings.  ``/media/`` is the one exception, because Apache serves it without
  asking Django;
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

Turn HSTS off for the first deploy of a new hostname: set
``SECURE_HSTS_SECONDS=0`` in ``/etc/caldart/caldart.env`` and restart
``caldart-web``, until HTTPS is known good.  That one setting is the whole
switch — the vhost sets no ``Strict-Transport-Security`` header of its own.
Browsers honor the header for its full duration and there is no way to take it
back early.  ``SECURE_HSTS_PRELOAD`` stays off unless you mean to join the
browser preload list; :doc:`configuration` explains what that commits the site
to.

nginx instead
-------------

Use one or the other, never both on the same host::

  sudo cp deploy/nginx/caldart.conf /etc/nginx/sites-available/caldart
  sudo ln -s /etc/nginx/sites-available/caldart /etc/nginx/sites-enabled/
  sudo nginx -t && sudo systemctl reload nginx

It is the same shape: ACME on port 80, TLS, and proxying on 443,
``proxy_set_header X-Forwarded-Proto $scheme``, ``/media/`` from disk,
``client_max_body_size 25m``, and the security headers left to Django.  nginx's
``add_header`` does not replace what the upstream sent, so a copy here would
reach the browser alongside Django's.  ``/media/documents/`` gets a
``return 404;`` of its own; it is the longer prefix, so nginx matches it ahead
of ``/media/``.


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

.. _deploy-renewals:

11. Automatic renewals
======================

::

  sudo cp deploy/systemd/caldart-renewals.service \
          deploy/systemd/caldart-renewals.timer /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable --now caldart-renewals.timer
  systemctl list-timers caldart-renewals.timer

Daily at 06:30, with catch-up if the machine was off.  It runs half an hour
before the reminder scan deliberately: a membership this scan renews is then
never also sent a reminder about running out on the same morning.  Unlike the
reminder scan it calls Stripe and PayPal, so the unit needs the same payment
keys the web service has; they come from the same ``/etc/caldart/caldart.env``.
See :doc:`renewals` for what it charges, when, and how to change the cadence.


.. _deploy-reports:

12. Scheduled reports
=====================

::

  sudo cp deploy/systemd/caldart-reports.service \
          deploy/systemd/caldart-reports.timer /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable --now caldart-reports.timer
  systemctl list-timers caldart-reports.timer

Daily at 06:00, with catch-up if the machine was off: whatever was due is still
due, and the next run sends it.  It sends the report subscriptions that are due
and each DART's monthly roster; it needs the database and the SMTP server, from
the same ``/etc/caldart/caldart.env``.  Rehearse the first of next month with
``caldart_manage send_scheduled_reports --dry-run --today <YYYY-MM-01>``.  See
:doc:`scheduled-reports` for what it sends, and when.


.. _deploy-statements:

13. Year-end statements
========================

::

  sudo cp deploy/systemd/caldart-statements.service \
          deploy/systemd/caldart-statements.timer /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable --now caldart-statements.timer
  systemctl list-timers caldart-statements.timer

Yearly at 06:45 on January 15th, with catch-up if the machine was off: a year
already sent reaches nobody again, so a late run costs nothing.  It emails
every active account -- a member, a friend, or a donor -- that made a settled
contribution the year before, with that year's statement PDF attached; it
needs the database and the SMTP server, from the same
``/etc/caldart/caldart.env``.  Rehearse it any time with
``caldart_manage send_year_statements --dry-run --today <YYYY-01-15>``.  See
:doc:`statements` for who is sent one, and when.


14. Backups
===========

Take one now and schedule them::

  caldart_manage db_backup

:doc:`backup-restore` covers the commands, the timer, retention, and restoring.


Checking it worked
==================

::

  systemctl status caldart-web caldart-reminders.timer caldart-renewals.timer \
      caldart-reports.timer caldart-statements.timer
  sudo docker compose ps
  curl -sI https://caldart.example.org/ | head -1
  caldart_manage health --json

The ``health`` command prints the same report as ``GET /system/health`` and the
health panel of ``/portal/system``: database connectivity, pending migrations,
free space on the backup filesystem, the last backup, the version from
``pyproject.toml``, and whether ``DEBUG`` is on.  On a healthy production box
``debug`` is ``false`` and ``pending_migrations`` is ``0``.

Then, in a browser: the public site loads and is styled, ``/portal/`` signs you
in, ``/admin/`` opens Wagtail, ``/portal/system`` shows three green panels, and
the **User guide** link at the foot of the portal's menu opens your role's
page of the guide.


Deployment checks
=================

``make check-deploy`` runs ``manage.py check --deploy`` against
``caldart.settings.prod``, so the production settings are audited before every
change reaches ``main`` and whenever you want to audit them on a checkout.
``--deploy`` adds Django's deployment-only checks to the default set, and those
carry four tags — ``security``, ``caches``, ``async_support``, and ``mail``.
The recipe names all four, which runs every deployment-only check while leaving
out the default checks ``make check-backend`` already runs, one of which needs
a built ``frontend/dist``.

The recipe supplies a throwaway environment inline rather than reading
``/etc/caldart/caldart.env``.  That environment carries only what
``caldart.settings.prod`` requires outright — a dummy ``SECRET_KEY``,
``ALLOWED_HOSTS``, ``DATABASE_URL``, ``SITE_URL``, and ``EMAIL_URL`` — and pins
no secure flag, so each one comes from the module's own default and the check
exercises what a real box gets, without touching a real secret or a real
database.

``caldart.settings.prod`` silences two of Django's deployment warnings
deliberately, both in ``SILENCED_SYSTEM_CHECKS``:

``security.W021``
   Reported while ``SECURE_HSTS_PRELOAD`` is off.  :doc:`configuration`
   explains why that is the default.

``security.W019``
   Reported because ``X_FRAME_OPTIONS`` is ``"SAMEORIGIN"`` rather than
   ``"DENY"``.  Wagtail's admin previews pages in a same-origin frame, and
   ``DENY`` would break that preview; framing by other origins is still
   refused.

A real finding still fails the check, since only these two are silenced: turn
``SECURE_SSL_REDIRECT`` off — in the environment, or by changing its default in
``caldart.settings.prod`` — and the gate stops on ``security.W008``.
:doc:`testing` lists it alongside the other gates.


Security headers
================

Django sends every security header the site relies on:
``Strict-Transport-Security``, ``X-Content-Type-Options``, ``Referrer-Policy``
, ``X-Frame-Options``, and ``Content-Security-Policy``.  Every response that
reaches gunicorn — the public site, the portal, the API and the Wagtail admin —
therefore carries exactly what the settings say, which is why
:ref:`configuration-csp` is the only place the policy is written down.

The shipped vhosts set one header of their own, and only on the responses they
answer without asking Django: the ``/media/`` block in
``deploy/nginx/caldart.conf`` and the matching ``<Directory>`` section in
``deploy/apache/caldart.conf`` each add ``X-Content-Type-Options: nosniff`` to
the uploads they serve straight off disk, so an upload cannot be sniffed into
another content type.  Neither vhost touches any other security header, on any
response.

Check the policy on a running box::

  curl -sI https://caldart.example.org/ | grep -i content-security-policy

Do not add a ``Content-Security-Policy`` header in Apache or nginx.  The
application leaves a header the response already carries alone, so a vhost
that sets its own silently replaces the policy — including the relaxation the
Wagtail admin needs, which would leave ``/admin/`` unable to run its own
scripts.


Logs
====

Everything goes to the journal; there are no application log files to rotate.

===========================  =================================================
What                         Where
===========================  =================================================
Application, gunicorn        ``journalctl -u caldart-web -f``
Reminder runs                ``journalctl -u caldart-reminders -n 50``
Renewal runs                 ``journalctl -u caldart-renewals -n 50``
Scheduled report runs        ``journalctl -u caldart-reports -n 50``
Year-end statement runs      ``journalctl -u caldart-statements -n 50``
Apache :443 access / error   ``/var/log/apache2/caldart-{access,error}.log``
Apache :80 access / error    ``/var/log/apache2/caldart-http-{access,error}.log``
                             — the redirect vhost, and therefore where a
                             failing ACME challenge shows up
nginx access / error         ``/var/log/nginx/caldart-{access,error}.log``
Postgres                     ``sudo docker compose logs -f db``
===========================  =================================================

``LOG_LEVEL`` in the environment file sets Django's root level; ``INFO`` is the
default and ``WARNING`` is reasonable once things are quiet.

.. _deploy-audit-log:

The audit log
-------------

Every privileged action writes one line to the ``caldart.audit`` logger, which
has its own level and its own handler and does not pass records to the root
logger.  ``LOG_LEVEL`` therefore never silences it: the audit trail is there
whatever the rest of the application is set to.

The lines go to the journal with everything else, so a filter picks them out::

  journalctl -u caldart-web | grep caldart.audit
  journalctl -u caldart-web | grep 'action=member.delete'
  journalctl -u caldart-web -p warning | grep caldart.audit   # refused attempts
  journalctl -u caldart-reminders | grep 'action=reminders.run'
  journalctl -u caldart-renewals | grep 'action=renewals.run'
  journalctl -u caldart-reports | grep 'action=reports.run'
  journalctl -u caldart-statements | grep 'action=statements.run'

Each line is ``key=value`` pairs in a fixed order::

  INFO  2026-09-14 09:31:02,144 caldart.audit action=account.roles actor=12 target=34 added=account_admin removed=-

``actor`` is the id of the account that acted, or ``command`` for a management
command and for the daily timers.  ``target`` is the id of the account or
record acted on, or ``-``.  The actions:

============================= ===============================================
Action                        Fields beyond actor and target
============================= ===============================================
``account.update``            ``fields`` -- the account columns changed
``account.roles``             ``added``, ``removed`` -- role slugs
``account.activate``          --
``account.deactivate``        --
``member.create``             ``invited`` -- whether an invitation was mailed
``member.delete``             --
``dart.create``               --
``dart.update``               --
``dart.delete``               ``members``, ``pages`` -- the members the
                              delete unaffiliated and the website pages it
                              unlinked
``aircraft.create``           --
``aircraft.update``           ``fields`` -- the register columns changed
``aircraft.delete``           --
``membership.grant``          ``plan``, ``term``
``membership.correct``        ``term``, ``fields``
``password_reset.admin_sent`` --
``backup.create``             ``file``, ``size``
``backup.download``           ``file``
``backup.restore``            ``file``
``db.reset``                  ``database``, ``seeded``
``reminders.run``             ``dry_run``, ``sent``, ``skipped``, ``failed``,
                              ``expired_flipped``
``payment.record``            ``provider``, ``wallet``, ``amount_cents``,
                              ``plan``
``payment.refund``            ``amount_cents``, ``reason``, ``term_canceled``
``payment.reconcile``         ``reconciled`` -- whether it is now matched
``payment.receipt_resend``    --
``payment.note``              --
``renewal.enable``            ``provider``, ``plan`` -- ``-`` for a
                              recurring donation, which renews nothing
``renewal.cancel``            ``provider``, ``self_service`` -- whether the
                              member turned it off themselves
``renewal.change``            ``contribution_cents``, ``removed_cents`` -- the
                              contribution taken off a renewal to make room
                              for a recurring donation
``renewals.run``              ``dry_run``, ``noticed``, ``charged``,
                              ``failed``, ``paused``, ``skipped``
``reports.run``               ``dry_run``, ``sent``, ``skipped``, ``failed``
``report.send``               ``kind`` -- ``subscription`` (the target is the
                              subscription) or ``roster`` (the target is the
                              DART), then ``dry_run``, ``sent``, ``skipped``,
                              ``failed``; one line per **Send now**, and per
                              DART when the rosters are sent by hand
============================= ===============================================

An account edit is recorded only when it really alters the record.  The admin
account form resends every field on each save, so ``account.update`` names just
the columns whose stored value changed, and a save that changes nothing at all
is not a line.  A register edit is recorded whatever it changes, because the
history behind it is a record of who wrote to the airframe; ``aircraft.update``
names the columns that moved, and ``fields=-`` when none did.

A privileged attempt a rule turns away is logged at WARNING under the same
action, with a ``reason`` slug saying which rule refused it: ``self_deactivation``,
``roles_not_held``, ``system_admin_role``, ``self_delete``,
``system_admin_target``, ``has_payments``, ``inactive_account``, or
``no_such_backup``.

A record carries ids, counts, flags, and slugs and nothing else.  Email
addresses, names, passwords, tokens, and database contents are not values the
helper accepts, so a line can never carry them; reading it back therefore means
looking the ids up.  A richer trail, held in the database and readable from the
portal, is the ``AuditEntry`` model in :doc:`roadmap`.


Upgrading
=========

Take a backup first, always.  ``caldart_manage`` is the function from
:ref:`deploy-manage-commands`::

  caldart_manage db_backup

  cd /srv/caldart
  sudo git pull
  sudo uv sync --frozen --no-dev --group docs
  cd frontend && sudo npm ci && sudo npm run build && cd ..
  sudo uv run sphinx-build -n -W -b dirhtml -t guide -c docs docs/user docs/_build/guide

  caldart_manage migrate
  caldart_manage createcachetable
  caldart_manage collectstatic --noinput

  sudo systemctl restart caldart-web
  journalctl -u caldart-web -n 30

Order matters: build the frontend before ``collectstatic``, and restart the web
unit last.  The guide is rebuilt in the same sequence, so the copy at ``/docs/``
is always the one the running code describes; Django reads it off disk on every
request, so it needs no restart of its own.  ``createcachetable`` is idempotent: it does nothing when
``caldart_cache`` is already there, and it is in the list so that no upgrade
can leave a box without it.  ``preload_app`` is on, so a restart — not a reload — is what picks
up new code.

Rolling back is the same sequence against the previous commit, plus a
``db_restore`` if the schema the previous commit expects differs from the
one currently applied.


.. _deploy-troubleshooting:

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

**``/docs/`` answers 404 and the journal says the user guide has not been
built.**  The Sphinx step of :ref:`the build <deploy-build>` did not run, or
``USER_GUIDE_ROOT`` names a directory with no ``index.html``.  Run it, or point
the variable at the directory it wrote to.

**``ValueError: Missing staticfiles manifest entry``.**  ``collectstatic`` ran
before the frontend build.  Run them in that order and restart.

**Backups fail with a permission error.**  ``BACKUP_DIR`` is outside the
``ReadWritePaths`` in ``caldart-web.service``, or is not owned by ``caldart``.

**Redirect loop.**  ``SECURE_SSL_REDIRECT`` is on but the proxy is not sending
``X-Forwarded-Proto: https``, so Django redirects a request it thinks is plain
HTTP, forever.  Fix the header rather than turning the redirect off.

**No email.**  Check ``EMAIL_URL`` and try ``caldart_manage
send_renewal_reminders --dry-run``; then send one for real and read
``journalctl -u caldart-web``.  Many providers need
``smtp+tls://`` on port 587 with an app password rather than the account one.
