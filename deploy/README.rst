=======================================
Installing and running a CalDART server
=======================================

This directory holds everything that puts CalDART on a single Debian or
Ubuntu server and keeps it running there: an installer, an upgrader, an
uninstaller, two helpers for running commands against the installed site, and
the configuration files they install (systemd units, Apache and nginx
configuration, the gunicorn settings, and the production environment
template).  This page is the operator's runbook: what to type, in what order,
and what to do when a script refuses.

.. contents:: On this page
   :local:
   :depth: 1


What the scripts do
===================

The installer builds one server with Postgres 16 in a Docker container,
the Django application under gunicorn as a systemd service, Apache or nginx
in front terminating TLS, and six systemd timers for the scheduled jobs.
Every step is idempotent: running a script again repairs or re-applies what
it did, and never destroys data or overwrites a secret.  Every script prints
one ``==>`` line per stage, accepts ``--help`` (which prints its header) and
``--dry-run`` (which prints every command that would change the machine,
prefixed ``+``, instead of running it), and must run as root except in a dry
run.

The files:

``bootstrap.sh``
   The one file a server needs before the repository is on it.  Installs
   ``git`` when it is missing, clones the repository into the deploy root
   (``/opt/caldart`` by default), and runs ``install.sh`` from the checkout.
``install.sh``
   Installs the site: runs every step under ``steps/`` in order.
``upgrade.sh``
   Backs up the database, brings the checkout up to date, and re-runs the
   steps that depend on the code.
``uninstall.sh``
   Removes the services and the web server configuration; with ``--purge``,
   also the configuration, the database, and the deploy root.
``manage.sh``
   Runs a Django management command the way the web service runs the site.
``compose.sh``
   Runs ``docker compose`` against the database container with the recorded
   port.
``lib.sh``
   Functions every script shares; sourced, never run.
``steps/``
   One script per install step, each runnable alone:
   ``packages.sh``, ``user.sh``, ``postgres.sh``, ``configure.sh``,
   ``build.sh``, ``database.sh``, ``web-service.sh``, ``web-server.sh``,
   ``timers.sh``, ``backup.sh``, and ``check.sh``.
``caldart.env.example``
   The production template for ``/etc/caldart/caldart.env``.
``gunicorn.conf.py``
   The gunicorn settings the web service reads in place.
``systemd/``
   ``caldart-web.service`` and six service and timer pairs.
``apache/``, ``nginx/``
   The vhost for a site with a hostname of its own (``caldart.conf``), and the
   snippet for a site under a path of an existing HTTPS site
   (``caldart-attach.conf``; nginx also has ``caldart-upstream.conf``).

Every shipped file names ``/opt/caldart``; the scripts replace it with the real
deploy root as they copy each file, so a checkout anywhere else works.


Before you start
================

You need:

- **A server running Debian 13 (trixie) or Ubuntu 24.04 (noble).**  The
  packages step reads ``ID`` from ``/etc/os-release`` and refuses any
  distribution other than Debian or Ubuntu.  Every package comes from the
  distribution's own archive, apart from Node 22 (from NodeSource, when the
  installed Node is missing or older) and ``uv`` (installed into
  ``/usr/local/bin`` when it is missing).
- **Root**, through ``sudo``.
- **A hostname whose DNS points at the server**, such as
  ``caldart.example.org``: an ``A`` record (and ``AAAA`` for IPv6).  With the
  default ``--www``, ``www.caldart.example.org`` must resolve to the server as
  well, since the certificate covers both names; give ``--no-www`` otherwise.
  A self-signed install (``--tls self-signed``) needs no public DNS.
- **Ports 80 and 443 open** to the internet.  Let's Encrypt checks port 80
  before it issues a certificate, and certbot renews through it.  Behind an
  existing site (``--tls existing``) the site's own web server already holds
  them.
- **Outbound HTTPS**, to the distribution's archive, NodeSource, PyPI, npm,
  Docker Hub, Let's Encrypt, and ``registry.faa.gov`` (the nightly FAA
  registry import).
- **An SMTP relay** (its URL, with credentials) or a postfix already running
  on the machine.  `Mail`_ below says which to pick.
- **Disk for the dumps.**  The backups live on the same disk as the site, and
  the health panel of the portal's System screen warns when that filesystem
  has less than 2 GB free.

Docker does not need to be installed: the packages step installs
``docker.io`` and the distribution's Compose v2 package when ``docker`` and
``docker compose`` do not work.  A Docker that is already there is kept as it
is (see `Sharing the machine`_).

Postgres listens on ``127.0.0.1:5432`` by default and gunicorn on
``127.0.0.1:8001``; neither is reachable from outside the machine.  Port 8001
must be free.  When another Postgres already uses 5432, give ``--db-port``.


Installing
==========

Step 1: bootstrap
-----------------

On the server, one command fetches the code and installs everything::

  curl -fsSL https://raw.githubusercontent.com/astrocfi/caldart-proto/main/deploy/bootstrap.sh \
      | sudo bash -s -- --hostname caldart.example.org \
          --certbot-email ops@example.org \
          --email-url 'smtp+tls://user:password@smtp.example.org:587' \
          --admin-email you@example.org

``bootstrap.sh`` takes three options of its own and passes every other one to
``install.sh`` untouched:

``--repo URL-OR-PATH``
   What to clone.  Default ``https://github.com/astrocfi/caldart-proto.git``.
``--ref REF``
   The branch, tag, or commit to install.  Default ``main``.
``--dry-run``
   Print the clone and the install instead of running them (also passed on
   to ``install.sh``).

``CALDART_ROOT`` in its environment picks the deploy root; the default is
``/opt/caldart``.  Because ``sudo`` drops the caller's environment, set it
after ``sudo``::

  curl -fsSL https://raw.githubusercontent.com/astrocfi/caldart-proto/main/deploy/bootstrap.sh \
      | sudo env CALDART_ROOT=/srv/caldart bash -s -- --hostname caldart.example.org ...

When the deploy root is already a checkout, ``bootstrap.sh`` fetches, checks
out ``--ref``, and pulls it (when it is a branch) instead of cloning.  When the
directory exists, is not empty, and is not a checkout, it stops.

On a server that already has the checkout, run the installer directly, with
the same flags::

  sudo /opt/caldart/deploy/install.sh --hostname caldart.example.org ...

The commands on this page name ``/opt/caldart``; with another deploy root,
run the scripts from there instead.

Step 2: the install flags
-------------------------

These are every option ``install.sh`` accepts (``sudo deploy/install.sh
--help`` prints the same list).

``--hostname HOST``
   The public hostname, a DNS name of at least two labels such as
   ``caldart.example.org``.  Required on the first run.
``--www``, ``--no-www``
   Also answer for ``www.HOST``: the vhost, the certificate, ``ALLOWED_HOSTS``,
   and ``CSRF_TRUSTED_ORIGINS`` all name both.  Default ``--www``.
``--web-server apache|nginx``
   Which web server to install and configure.  Default ``apache``.  The other
   server's configuration is never touched, and the web server step refuses
   to run while ``apache2`` and ``nginx`` are both active.
``--tls certbot|self-signed|existing``
   How the site gets its certificate.  Default ``certbot``.

   ``certbot``
      A Let's Encrypt certificate for the hostname (and ``www.HOST``),
      obtained over port 80 and renewed by certbot's own timer.  Needs
      ``--certbot-email``.
   ``self-signed``
      An ``openssl`` certificate, valid ten years, in ``/etc/caldart/tls/``.
      Browsers warn.  For a trial or staging box without a public hostname.
      The environment file gets ``SECURE_HSTS_SECONDS=0`` so no browser
      remembers HSTS for a name the box does not own.
   ``existing``
      A web server on this machine already serves the hostname over HTTPS.
      The installer obtains no certificate, installs no certbot, and writes no
      vhost of its own: it writes a snippet that the existing site's vhost
      includes.  Usually paired with ``--url-prefix`` and ``--attach-to``.

   There is no plain-HTTP mode: the production settings insist on secure
   cookies and redirect HTTP to HTTPS.
``--certbot-email ADDRESS``
   The Let's Encrypt account address, which receives expiry warnings.
   Required with ``--tls certbot``.
``--certbot-staging``
   Use Let's Encrypt's staging directory: a certificate browsers do not trust,
   without the production rate limits.  For a trial run of certbot itself.
``--url-prefix PREFIX``
   Serve the site under a path of the host, such as ``/caldart-proto``, so
   the site is ``https://HOST/caldart-proto/``.  One leading and one trailing
   slash are optional; each segment is letters, digits, ``.``, ``_``, ``~``, or
   ``-``.  Default: the root of the host (``/`` names it too).  Once the
   environment file exists this must match its ``URL_PREFIX``.
``--attach-to FILE``
   With ``--tls existing`` only: the absolute path of the existing site's
   vhost file to insert the include line into.  Without it the installer
   prints the line and where it goes, for you to add by hand.
``--db-port PORT``
   The host port the Postgres container is published on, from 1024 to 65535.
   Default ``5432``.  Once the environment file exists this must match the
   port in its ``DATABASE_URL``.
``--email-url URL``
   The SMTP relay, written as ``EMAIL_URL``: ``smtp+tls://`` for STARTTLS
   (usually port 587), ``smtp+ssl://`` for implicit TLS (port 465), or
   ``smtp://`` plain, with the credentials URL-encoded (an ``@`` in the user
   name is ``%40``).  Quote it: it holds a password.
``--email local``
   Send mail through the postfix on this machine: ``EMAIL_URL`` becomes
   ``smtp://localhost:25``.  ``local`` is the only value ``--email`` takes.
   Give either this or ``--email-url``, not both; one of them is required
   until the environment file exists.
``--from-email ADDRESS``
   ``DEFAULT_FROM_EMAIL``, the ``From`` of every message.  Default
   ``CalDART <noreply@HOST>``.  Quote it when it has a display name.
``--admin-email ADDRESS``
   Create the first administrator with this address (or give an existing
   account with that address the administrator's roles).
``--seed-content``
   Load the example pages into the public site.  The installer never loads the
   demo accounts.
``--dry-run``
   Print every state-changing command instead of running it.
``--help``
   Print the options.

The hostname, ``www``, the web server, the TLS mode, the certbot address and
staging switch, the database port, the URL prefix, and the attached vhost file
are kept in the install record (see `What the installer writes`_), so a later
run needs no flags, and a flag given later updates the record.  The mail
flags, ``--from-email``, ``--admin-email``, and ``--seed-content`` are used by
the run that writes the environment file or creates the administrator, and
are not recorded.

Step 3: try it with a dry run
-----------------------------

``--dry-run``, or ``CALDART_DRY_RUN=1`` in the environment, prints what a run
would do without doing it, and needs no root.  It reads the machine as it is,
so on a fresh box it prints the whole sequence in order; the generated
secrets appear as ``<generated>``, and a file the dry run never wrote (the
environment file, the install record) is treated as absent, with a note on
standard error.  A dry run is the quickest way to check a set of flags::

  sudo /opt/caldart/deploy/install.sh --dry-run --hostname caldart.example.org \
      --certbot-email ops@example.org --email local
  CALDART_DRY_RUN=1 /opt/caldart/deploy/install.sh --hostname caldart.example.org ...

Step 4: what the run prints
---------------------------

The install takes a few minutes, most of them the package installs and the
build.  It runs these stages, each announced by an ``==>`` line:

1. the operating system packages, Node, ``uv``, and Docker;
2. the ``caldart`` system user and its directories;
3. the install record;
4. Postgres in Docker, and, on the first run, a generated database password;
5. the environment file, on the first run only;
6. the build: the Python packages from ``uv.lock``, the frontend, and the user
   guide;
7. the database: migrations, the cache table, the roles, the example pages
   with ``--seed-content``, the static files, and the administrator with
   ``--admin-email``;
8. gunicorn under systemd, waiting up to 30 seconds for it to answer;
9. the web server and the certificate, or the snippet behind an existing
   site;
10. the scheduled jobs, and a first FAA registry import in the background;
11. a first database backup;
12. the checks, and the summary.

When a command fails, its own output is followed by an ``error:`` line naming
the stage and the command.  Fix what it names and run ``install.sh`` again.

The summary at the end looks like this::

  CalDART is running at https://caldart.example.org/
  Settings: /etc/caldart/caldart.env (edit with sudoedit, then systemctl restart caldart-web)
  Set the administrator's password at: https://caldart.example.org/portal/reset-password?uid=...&token=...
  Still empty in the settings: STRIPE_PUBLISHABLE_KEY STRIPE_SECRET_KEY ...

``--admin-email`` runs ``create_admin``, which makes the account a superuser
with the ``member``, ``system_admin``, and ``website_admin`` roles and no
usable password, and prints one line: a one-time password-reset link.  Open it,
signed out, to set the administrator's password.  It expires with any
password-reset link, after ``PASSWORD_RESET_TIMEOUT`` (three days by default).
To make another link later::

  sudo /opt/caldart/deploy/manage.sh create_admin --email you@example.org

With a self-signed certificate the summary adds that browsers warn until a
real certificate replaces it.


Worked examples
===============

A site with a hostname of its own
---------------------------------

``caldart.example.org`` and ``www.caldart.example.org`` point at a fresh
Ubuntu 24.04 server; Apache and a Let's Encrypt certificate; mail through the
organization's relay::

  curl -fsSL https://raw.githubusercontent.com/astrocfi/caldart-proto/main/deploy/bootstrap.sh \
      | sudo bash -s -- --hostname caldart.example.org \
          --certbot-email ops@example.org \
          --email-url 'smtp+tls://caldart%40example.org:app-password@smtp.example.org:587' \
          --from-email 'CalDART <noreply@example.org>' \
          --admin-email you@example.org

The site is at ``https://caldart.example.org/``, the portal at
``/portal/``, the Wagtail admin at ``/admin/``, and the user guide at
``/docs/``.  Add ``--web-server nginx`` for nginx instead of Apache.

A sub-path behind an existing Apache site, with local postfix
--------------------------------------------------------------

The machine already serves ``https://example.org/`` with Apache, set up with
certbot's Apache plugin, and runs postfix.  CalDART goes at
``https://example.org/caldart-proto/`` without touching the rest of the
site::

  curl -fsSL https://raw.githubusercontent.com/astrocfi/caldart-proto/main/deploy/bootstrap.sh \
      | sudo bash -s -- --hostname example.org \
          --url-prefix /caldart-proto \
          --tls existing \
          --attach-to /etc/apache2/sites-available/example.org-le-ssl.conf \
          --email local \
          --from-email 'CalDART <caldart@example.org>' \
          --admin-email you@example.org

``--attach-to`` names the file that holds the site's ``<VirtualHost *:443>``
block.  On a site set up with certbot's Apache plugin that is
``<name>-le-ssl.conf``, since certbot leaves only the plain-HTTP redirect in
``<name>.conf``.  For nginx, add ``--web-server nginx`` and name the file in
``/etc/nginx/sites-available/`` whose ``server`` block listens on 443.

What the installer does behind an existing site:

- It writes the snippet: for Apache ``/etc/apache2/conf-available/caldart.conf``
  (after ``a2enmod proxy proxy_http headers expires``; it is not enabled with
  ``a2enconf``, which would load it for every host), and for nginx
  ``/etc/nginx/snippets/caldart.conf`` plus the upstream it proxies to,
  ``/etc/nginx/conf.d/caldart-upstream.conf``.
- It copies the attached file to ``FILE.caldart.bak`` (once, before the first
  insertion), then inserts one line before the end of every block in it that
  serves HTTPS::

    Include conf-available/caldart.conf     # Apache
    include snippets/caldart.conf;          # nginx

  A file that already carries the line is left alone.
- It checks the configuration (``apachectl configtest`` or ``nginx -t``).  If
  the check fails it takes the line back out, so the existing site is as it
  was, and stops.  Otherwise it reloads the server.

Without ``--attach-to`` it prints the line and where it goes; add it by hand,
reload the web server, and run ``sudo /opt/caldart/deploy/steps/check.sh``,
whose checks fail until the line is there.

The environment file gets ``SITE_URL=https://example.org/caldart-proto`` and
``URL_PREFIX=/caldart-proto``, so every link Django writes, emails included,
carries the prefix.  The portal is at ``/caldart-proto/portal/``, the Wagtail
admin at ``/caldart-proto/admin/``, and the user guide at
``/caldart-proto/docs/``.  One host serves one CalDART: the session and CSRF
cookies use the path ``/``.  HSTS stays with the existing site.

Without ``--url-prefix``, ``--tls existing`` gives CalDART the whole of the
existing host.  On nginx that snippet holds ``location ^~ /``, so the existing
``server`` block must have no ``location /`` of its own.

With ``--email local`` the installer prints a note, not an error, when
nothing listens on port 25: mail fails until postfix is installed and
listening on localhost.  See `Mail`_.

A self-signed staging box
-------------------------

A trial server on a private network, reachable as
``caldart-staging.example.org`` from inside it only, with nginx, the example
pages, and a relay::

  curl -fsSL https://raw.githubusercontent.com/astrocfi/caldart-proto/main/deploy/bootstrap.sh \
      | sudo bash -s -- --hostname caldart-staging.example.org \
          --no-www \
          --web-server nginx \
          --tls self-signed \
          --email-url 'smtp+tls://user:password@smtp.example.org:587' \
          --admin-email you@example.org \
          --seed-content

Browsers warn about the certificate; accept it once.  To move the box to a
real certificate when its hostname becomes public, point the DNS at it and
run::

  sudo /opt/caldart/deploy/install.sh --tls certbot --certbot-email ops@example.org

then remove ``SECURE_HSTS_SECONDS=0`` from ``/etc/caldart/caldart.env`` and
``sudo systemctl restart caldart-web`` to turn HSTS on.  To try certbot
itself without using up Let's Encrypt's rate limits, add
``--certbot-staging``.


What the installer writes
=========================

The install record: ``/etc/caldart/install.conf``
-------------------------------------------------

``root:root``, mode ``0644``, one ``KEY=value`` per line, and no secret.
Every script reads it; it is never executed.

``CALDART_ROOT``
   The deploy root the installer ran from.  Written for reference; the scripts
   find the root from their own location.
``CALDART_HOSTNAME``
   ``--hostname``.
``CALDART_WWW``
   ``yes`` or ``no``: ``--www`` or ``--no-www``.
``CALDART_WEB_SERVER``
   ``apache`` or ``nginx``.
``CALDART_TLS``
   ``certbot``, ``self-signed``, or ``existing``.
``CALDART_CERTBOT_EMAIL``
   ``--certbot-email``, or empty.
``CALDART_CERTBOT_STAGING``
   ``yes`` or ``no``.
``CALDART_DB_PORT``
   The Postgres host port, ``5432`` unless ``--db-port`` said otherwise.
``CALDART_URL_PREFIX``
   The normalized prefix, such as ``/caldart-proto``, or empty.
``CALDART_ATTACH_TO``
   ``--attach-to``, or empty.

To change one, run ``install.sh`` with the flag rather than editing the file.

The environment file: ``/etc/caldart/caldart.env``
--------------------------------------------------

Every runtime setting, read by the web service and every job service.
``root:caldart``, mode ``0640``: it holds the database password, Django's
secret key, and the payment keys.  The first run writes it from
``caldart.env.example`` and fills in:

- ``SECRET_KEY``, generated;
- ``ALLOWED_HOSTS`` and ``CSRF_TRUSTED_ORIGINS``, from the hostname and its
  ``www.`` form;
- ``SITE_URL``, ``https://HOST`` plus the prefix, and ``URL_PREFIX`` when
  there is one;
- ``EMAIL_URL``, from ``--email-url`` or ``--email local``;
- ``DEFAULT_FROM_EMAIL``, from ``--from-email``;
- ``DATABASE_URL``, with the generated database password and the recorded
  port;
- ``BACKUP_DIR`` (the deploy root's ``backups``), ``DB_BACKUP_VIA_DOCKER=false``,
  ``BACKUP_RETENTION_DAYS=30``, and ``USER_GUIDE_ROOT`` (the deploy root's
  ``docs/_build/guide``);
- ``SECURE_HSTS_SECONDS=0`` with a self-signed certificate.

Everything else, comments included, stays as the template has it, so the file
explains itself.  Once it exists no script rewrites it: a later
``--email-url``, ``--email local``, or ``--from-email`` is reported as ignored.
Change it by hand, then restart the web service::

  sudoedit /etc/caldart/caldart.env
  sudo systemctl restart caldart-web

The job services read the file afresh on every run, so they need no restart.

The systemd units
-----------------

Installed into ``/etc/systemd/system/`` from ``systemd/``, with the deploy
root written in.  Every service runs as the ``caldart`` user with
``UMask=0027``, reads the environment file, and runs under the same systemd
sandbox (``ProtectSystem=strict``, no capabilities).

.. list-table::
   :header-rows: 1

   * - Unit
     - Runs
     - When
   * - ``caldart-web.service``
     - gunicorn on ``127.0.0.1:8001``
     - always; restarted on failure
   * - ``caldart-backup.timer``
     - ``manage.py db_backup``, then deletes the dumps older than ``BACKUP_RETENTION_DAYS``
     - daily at 03:30
   * - ``caldart-registry.timer``
     - ``manage.py import_faa_registry``
     - daily at 04:30
   * - ``caldart-reports.timer``
     - ``manage.py send_scheduled_reports``
     - daily at 06:00
   * - ``caldart-renewals.timer``
     - ``manage.py run_auto_renewals``
     - daily at 06:30
   * - ``caldart-reminders.timer``
     - ``manage.py send_renewal_reminders``
     - daily at 07:00
   * - ``caldart-statements.timer``
     - ``manage.py send_year_statements``
     - yearly, January 15 at 06:45

Each timer starts the service of the same name (``caldart-backup.service``
and so on), which runs its command and exits.  Every timer has
``Persistent=true``, so a run missed while the machine was off happens when it
comes back, and up to five minutes of random delay.  See them all with::

  systemctl list-timers 'caldart-*'

The web server
--------------

With ``certbot`` or ``self-signed``:

- Apache: ``/etc/apache2/sites-available/caldart.conf``, enabled with
  ``a2ensite``, after ``a2enmod proxy proxy_http headers ssl rewrite deflate
  expires http2``.
- nginx: ``/etc/nginx/sites-available/caldart``, linked from
  ``sites-enabled``.

Each holds a port-80 host, which answers Let's Encrypt's challenges and
redirects everything else to HTTPS, and a port-443 host, which terminates TLS,
serves ``/media/`` off disk, and proxies the rest to gunicorn.  While a
certbot certificate does not exist yet, a bootstrap host (``caldart-acme``)
answers the challenge alone; it is removed once the certificate is there.
The certificate is in ``/etc/letsencrypt/live/HOST/`` with certbot, or
``/etc/caldart/tls/`` when self-signed.  With certbot the installer also adds
``/etc/letsencrypt/renewal-hooks/deploy/reload-web-server``, which reloads the
web server after each renewal.  Rehearse a renewal with
``sudo certbot renew --dry-run``.

With ``existing``, the snippet and the include line described under
`Worked examples`_.

The database container
----------------------

The ``db`` service of the repository's ``docker-compose.yml``, in the Compose
project ``caldart``: container ``caldart-db-1``, volume
``caldart_caldart_pgdata``, network ``caldart_default``.  It is published on
``127.0.0.1`` at the recorded port and restarts with Docker after a reboot.
Run ``docker compose`` against it through ``compose.sh``, which exports the
recorded port first; a plain ``docker compose up`` on a box that moved the
port would publish the container on 5432 again::

  sudo /opt/caldart/deploy/compose.sh ps
  sudo /opt/caldart/deploy/compose.sh logs -f db
  sudo /opt/caldart/deploy/compose.sh exec -T db psql -U caldart -d caldart

Directories in the deploy root
------------------------------

The checkout is root-owned and world-readable.  The service user owns the
three directories it writes, all ignored by git so an upgrade never touches
them:

``backend/media/``
   Wagtail's uploads: images and documents.
``backend/staticfiles/``
   What ``collectstatic`` writes.
``backups/``
   The database dumps (``BACKUP_DIR``).

The build also writes ``.venv/`` (the Python packages), ``frontend/dist/``
(the portal), and ``docs/_build/guide/`` (the user guide), and ``uv`` keeps
any Python it downloads in ``/opt/uv/python``.


After the install
=================

Fill in the remaining settings
------------------------------

The site runs without payment or address keys: checkout offers no payment
provider, and the profile form offers no address suggestions, until they are
set.  The summary lists the ones still empty.  Add them with
``sudoedit /etc/caldart/caldart.env``, then
``sudo systemctl restart caldart-web``:

- **Stripe**: ``STRIPE_PUBLISHABLE_KEY``, ``STRIPE_SECRET_KEY``,
  ``STRIPE_WEBHOOK_SECRET``, and, for Apple Pay,
  ``STRIPE_APPLE_PAY_DOMAIN_ASSOCIATION``.  The webhook endpoint to register
  with Stripe is ``SITE_URL`` followed by ``/api/v1/payments/stripe/webhook``.
- **PayPal**: ``PAYPAL_CLIENT_ID``, ``PAYPAL_CLIENT_SECRET``, ``PAYPAL_ENV``
  (``live`` in the template), and, to have PayPal's notifications verified,
  ``PAYPAL_WEBHOOK_ID``; the webhook endpoint is ``SITE_URL`` followed by
  ``/api/v1/payments/paypal/webhook``.
- **Geoapify**: ``GEOAPIFY_API_KEY``, the key behind the address suggestions.
- **The from address**: ``DEFAULT_FROM_EMAIL``, if ``--from-email`` was not
  given.  It must be on a domain the relay (or this machine's postfix) may
  send as.
- ``ADMIN_EMAILS``, optionally: addresses that receive a mail for every
  unhandled server error.

``docs/developer/payments-setup.rst`` walks through the Stripe and PayPal
dashboards, and ``docs/developer/configuration.rst`` documents every variable
in the file.

Mail
----

With ``--email-url`` the site hands every message to the relay.  With
``--email local`` it hands them to the postfix on this machine, which the
installer does not install or configure.  Postfix accepts mail from
localhost in its default configuration; then either the domain's SPF record
names this machine (and DKIM signing is set up in postfix if the domain's
DMARC expects it), or postfix forwards everything to the organization's relay
(``relayhost`` and the relay's credentials in ``main.cf``).  Either way, point
the mail domain's SPF, DKIM, and DMARC records at whatever sends the mail
before relying on it.

Send a test message through the configured path::

  sudo /opt/caldart/deploy/manage.sh sendtestemail you@example.org

and read ``journalctl -u postfix`` (or the relay's logs) for its delivery.
``docs/developer/email.rst`` covers the DNS records and the email log.

Check the site
--------------

The install ends with the checks, and any time later ``steps/check.sh`` runs
them again::

  sudo /opt/caldart/deploy/steps/check.sh

It checks that ``caldart-web`` and the six timers are active, that the
database container is healthy, that ``https://HOST/`` (under the prefix, when
there is one), the sign-in page, and the portal script the sign-in page names
all answer ``200`` from this machine, and that ``manage.py health`` reports
``DEBUG`` off and no pending migration.  It prints an ``error: check failed:``
line for every miss and exits non-zero; when every check passes it prints the
summary.

Then, in a browser: the public site loads and is styled, ``/portal/`` signs
you in, ``/admin/`` opens Wagtail, every check on the health panel of the
portal's System screen (``/portal/system``) is green, and the **User guide**
link at the foot of the portal's menu opens the user guide.  The guide is
served at ``/docs/`` (under the prefix, when there is one), to signed-in users
only.

Run management commands
-----------------------

``manage.sh`` runs a Django management command as the web service runs the
site: as the ``caldart`` user, from ``backend/``, with the environment file,
the production settings, and ``UMask=0027``, as a transient systemd unit.
Options for ``manage.sh`` itself (``--dry-run``, ``--help``) go before the
command; everything from the command on goes to ``manage.py``.  Its exit
status is the command's::

  sudo /opt/caldart/deploy/manage.sh sendtestemail you@example.org
  sudo /opt/caldart/deploy/manage.sh health --json
  sudo /opt/caldart/deploy/manage.sh db_backup
  sudo /opt/caldart/deploy/manage.sh send_renewal_reminders --dry-run
  sudo /opt/caldart/deploy/manage.sh --dry-run migrate

Never source the environment file into a shell to run ``manage.py`` by hand:
a shell splits a value with spaces in it, such as ``DEFAULT_FROM_EMAIL``, and
never run ``seed_demo`` on a server, which creates demo accounts with a
password published in the repository.

Logs
----

Everything goes to the journal:

- the site: ``journalctl -u caldart-web -f``;
- a job: ``journalctl -u caldart-backup -n 20`` (or ``caldart-registry``,
  ``caldart-reports``, ``caldart-renewals``, ``caldart-reminders``,
  ``caldart-statements``);
- Apache: ``/var/log/apache2/caldart-access.log`` and ``caldart-error.log``
  (the port-80 host logs to ``caldart-http-access.log`` and
  ``caldart-http-error.log``);
- nginx: ``/var/log/nginx/caldart-access.log`` and ``caldart-error.log``;
- Postgres: ``sudo /opt/caldart/deploy/compose.sh logs -f db``.

Behind an existing site, the web server's requests are in that site's logs.


Upgrading
=========

::

  sudo /opt/caldart/deploy/upgrade.sh                  # pull the current branch
  sudo /opt/caldart/deploy/upgrade.sh --ref v1.4       # or check out a branch, tag, or commit
  sudo /opt/caldart/deploy/upgrade.sh --dry-run        # print what it would do

``upgrade.sh`` takes ``--ref REF``, ``--dry-run``, and ``--help``.  In order,
it:

1. takes a database backup (``manage.sh db_backup``);
2. refuses to go on when the checkout has local changes;
3. runs ``git pull --ff-only``, or with ``--ref`` fetches and checks out
   ``REF`` (and pulls it when it is a branch);
4. rebuilds (``steps/build.sh``): the Python packages, the frontend, and the
   user guide;
5. prepares the database (``steps/database.sh``): migrations, the cache
   table, the roles, and the static files;
6. reinstalls and restarts ``caldart-web`` and waits for it to answer
   (``steps/web-service.sh``);
7. reinstalls the job units (``steps/timers.sh``);
8. runs the checks (``steps/check.sh``), and prints the commit it upgraded to.

Each step runs as the freshly checked-out script, so an upgrade that changes
the installer runs the changed one.  It is safe to run again: an upgrade with
nothing to pull still backs up, rebuilds, restarts, and passes the checks.
It never touches the environment file, the install record, or the web
server's configuration.

``install.sh`` with no flags is safe to run at any time too: it reads
everything from the install record, re-applies every step, and leaves the
environment file and the install record byte for byte as they were.  Run it to
repair an install; run ``install.sh`` with a flag to change what the record
says (a vhost, for example, is rewritten from the shipped file on every run of
the web server step).

**Rolling back.**  Run ``upgrade.sh --ref`` with the previous commit::

  sudo /opt/caldart/deploy/upgrade.sh --ref 1a2b3c4

When the migrations of the upgrade changed the schema, also restore the dump
the upgrade took first (see `Restoring`_).  A rollback leaves
the checkout on a detached ``HEAD``, where a plain ``upgrade.sh`` stops and
asks for a branch: name it on the next upgrade, ``--ref main``.


Backups and restoring
=====================

Backups
-------

``caldart-backup.timer`` takes a dump every night at 03:30 into
``/opt/caldart/backups/`` as ``caldart-YYYYMMDD-HHMMSS.sql.gz``, then deletes
the generated dumps older than ``BACKUP_RETENTION_DAYS`` days (30 as
installed).  Change the number in the environment file; the next run prunes by
it.  A dump given its own name is never pruned.  The install takes one dump
straight away, and every upgrade takes one before it changes anything.

Take one by hand, or check on the timer::

  sudo /opt/caldart/deploy/manage.sh db_backup
  sudo /opt/caldart/deploy/manage.sh db_backup --name before-the-change.sql.gz
  systemctl list-timers caldart-backup.timer
  journalctl -u caldart-backup -n 20

A system administrator can also take and download one from the portal's
System screen, under **Backups**.

A dump leaves out the rows of the FAA registry's registrations (some 317,000
rows, most of a dump's size): it creates the table empty.  The
aircraft types, and everything else, are dumped whole.  The registry comes
back from the FAA's own file on the next import: ``caldart-registry.timer``
runs one daily at 04:30, and **Run now** on the *FAA registry import* row of
the System screen runs one at once, as does::

  sudo systemctl start caldart-registry.service

A dump on the same disk as the database is not a backup.  Copy the dumps, and
the uploads in ``/opt/caldart/backend/media/``, to another machine, for
example::

  sudo rsync -a /opt/caldart/backups/ backup-host:/backups/caldart/dumps/
  sudo rsync -a --delete /opt/caldart/backend/media/ backup-host:/backups/caldart/media/

Treat both as sensitive: the dumps hold every member record, and the uploads
hold the members-only documents.  The health panel warns when the newest dump
is more than a week old.

Restoring
---------

A restore replaces the whole database with the dump.  Stop the site and the
jobs that write, restore, and migrate::

  sudo systemctl stop caldart-web caldart-renewals.timer caldart-reminders.timer \
      caldart-reports.timer caldart-statements.timer caldart-backup.timer
  sudo /opt/caldart/deploy/manage.sh db_restore /opt/caldart/backups/caldart-20260601-033000.sql.gz
  sudo /opt/caldart/deploy/manage.sh migrate

``db_restore`` asks for confirmation (``--yes`` skips the question) and takes
a path or a bare file name in ``BACKUP_DIR``.  It reads the whole file before
it drops anything, so a damaged dump leaves the database as it was.  The
``migrate`` brings a dump from an older release up to the running code.

Before starting anything again, check that the restore is the site you meant
to bring back: ``sudo /opt/caldart/deploy/manage.sh health`` reports no
pending migrations, and the member list and payments look as expected.  A
dump older than the last automatic renewal makes that renewal look due again,
so check what the renewal job would charge before restarting the timers::

  sudo /opt/caldart/deploy/manage.sh run_auto_renewals --dry-run
  sudo systemctl start caldart-web caldart-renewals.timer caldart-reminders.timer \
      caldart-reports.timer caldart-statements.timer caldart-backup.timer

The registrations table is empty after a restore until the next registry
import; start one as above.  ``docs/developer/backup-restore.rst`` covers
restoring onto a fresh machine, putting the uploads back, rehearsing a
restore into a scratch database, and recording a payment the provider took
after the dump.


Sharing the machine
===================

CalDART can share a server with other sites and other Docker projects.

**Another Postgres.**  The container is published on ``127.0.0.1:5432`` unless
``--db-port`` says otherwise.  On the run that creates the container, the
Postgres step stops when something already listens on that port, so a clash is
reported before anything is half-installed.  Pick a free port::

  ss -ltn 'sport = :5433'           # prints only its header when the port is free
  sudo /opt/caldart/deploy/install.sh --db-port 5433

To move the port on an installed box, first change the port in
``DATABASE_URL`` in ``/etc/caldart/caldart.env`` to the same number, then run
``install.sh --db-port PORT``: it recreates the container on that port,
records it, and restarts the site.  The installer refuses the flag while the
two disagree.

**Other Docker projects.**  Everything Compose creates is namespaced by the
project name ``caldart``: the container ``caldart-db-1``, the volume
``caldart_caldart_pgdata``, and the network ``caldart_default``.  None can
collide with another project's, and ``uninstall.sh --purge`` removes only
these.

**An existing Docker.**  The packages step installs ``docker.io`` only when
``docker --version`` fails, and the Compose package only when ``docker compose
version`` fails, so a Docker from Docker's own repository (``docker-ce``) is
kept, and the containers other projects run keep running.  Such a Docker
without its Compose plugin gets the distribution's Compose package, which may
want ``docker.io``; install ``docker-compose-plugin`` from Docker's repository
first instead.

**An existing web server.**  With ``--tls certbot`` or ``self-signed``,
CalDART adds its own vhost for its hostname beside the others.  With
``--tls existing`` it adds a snippet to one existing vhost and nothing else.
Only one of Apache and nginx may be running.

**Gunicorn's port.**  Gunicorn binds ``127.0.0.1:8001``, which must be free.


Uninstalling
============

::

  sudo /opt/caldart/deploy/uninstall.sh --yes              # the services and the vhost
  sudo /opt/caldart/deploy/uninstall.sh --yes --purge      # ... and every piece of data
  sudo /opt/caldart/deploy/uninstall.sh --yes --dry-run    # print what it would remove

Without ``--yes`` it refuses to run.  It:

- stops and disables ``caldart-web`` and the six timers, removes their unit
  files, and reloads systemd;
- removes the CalDART vhost and any bootstrap host from the web server the
  install record names;
- behind an existing site, removes the snippet (and nginx's upstream file) and
  takes the include line out of the attached file (or, when none was
  recorded, out of every file under the server's ``sites-available`` that
  carries it), leaving the rest of that file, and ``FILE.caldart.bak``, as they
  are;
- reloads the web server, and removes the certbot renewal hook.

It keeps ``/etc/caldart`` (the environment file, the install record, and a
self-signed certificate), the database container, which keeps running, and its
data, and the deploy root with its uploads and dumps.

``--purge`` also removes ``/etc/caldart``, runs ``docker compose down -v``
from the deploy root, which deletes the container and the
``caldart_caldart_pgdata`` volume with every row in it, and removes the deploy
root, uploads and dumps included.  Copy off what you want to keep first.

Both leave alone the certificates under ``/etc/letsencrypt``, the operating
system packages (Docker, the web server, certbot, Node, ``uv``), the
``caldart`` user, and ``/opt/uv/python``.  Each removal prints what it
removed; anything already absent is skipped.


Rehearsing an install (for developers)
======================================

A change to anything in this directory is tried out in a throwaway container
before a server sees it.  On a development machine with Docker::

  make rehearse-deploy                                       # with Apache
  make rehearse-deploy REHEARSE_WEB_SERVER=nginx             # with nginx
  make rehearse-deploy REHEARSE_URL_PREFIX=/caldart-proto    # behind an existing site
  make rehearse-deploy REHEARSE_KEEP=1                       # keep the container afterwards

The target starts a privileged ``jrei/systemd-ubuntu:24.04`` container, in
which systemd runs as on a server, and drives the scripts through a whole life:
``bootstrap.sh`` against the checkout (``--hostname caldart.test
--admin-email admin@caldart.test``, with ``--tls self-signed --email-url
smtp://localhost:25``), every other job service started once, ``upgrade.sh`` with
nothing to pull, ``install.sh`` with no flags (which must leave the
environment file and the install record byte-identical), and ``uninstall.sh
--yes --purge``.  Any failure stops the run and the target exits non-zero.

``REHEARSE_WEB_SERVER``
   ``apache`` (the default) or ``nginx``.
``REHEARSE_URL_PREFIX``
   A prefix such as ``/caldart-proto``: the target first stands up a stand-in
   HTTPS site for ``caldart.test`` and installs behind it with ``--tls
   existing --url-prefix PREFIX --attach-to <its vhost> --email local``, then
   checks that the stand-in page still answers, that the bare prefix
   redirects, and that the uninstall takes the include line out again.
``REHEARSE_KEEP``
   A switch (``1``, ``yes``, or ``true``): keep the container and its volumes
   afterwards, and open a shell in it with ``docker exec -it
   caldart-rehearsal-apache bash`` (``-nginx`` for nginx, with ``-prefix``
   appended under a prefix).

It installs the commit ``HEAD`` names, not the working tree: commit first.  A
run takes a few minutes and needs the network.  ``docs/developer/testing.rst``
describes the container in detail.


Troubleshooting
===============

The scripts refuse with an ``error:`` line on standard error.  A usage error
(exit status 2) is printed before anything changes; the others stop the run
where they happen.  Every step is idempotent, so the fix is always: do what
the message says, then run the same command again.

``error: port 5432 is already in use on this machine; run install.sh --db-port PORT to put CalDART's Postgres on another port``
   Something, most often another Postgres, already listens on the port.  Run
   the installer again with a free port, ``--db-port 5433`` for example; the
   record keeps it for every later run (`Sharing the machine`_).

``error: --email-url or --email local is required until /etc/caldart/caldart.env exists``
   The first run writes the environment file and needs a mail setting for it.
   Add ``--email-url 'smtp+tls://...'`` or ``--email local``.  Giving both is
   refused too (``give --email local or --email-url, not both``), and so is
   any ``--email`` value but ``local``.

``error: --db-port 5433 differs from the port in DATABASE_URL in /etc/caldart/caldart.env (5432); ...``
   The environment file is never rewritten, so the port cannot move under it.
   Change the port in ``DATABASE_URL`` with ``sudoedit`` first, then run the
   installer with ``--db-port`` again.

``error: the URL prefix /other differs from URL_PREFIX in /etc/caldart/caldart.env (/caldart-proto); ...``
   The same for the prefix.  Set ``URL_PREFIX`` and the path of ``SITE_URL``
   in the environment file to the prefix you want, then run the installer with
   ``--url-prefix`` again.

``error: FILE holds no <VirtualHost> block to include the snippet in`` (``server block`` on nginx)
   ``--attach-to`` names a file with no vhost in it at all, such as a file of
   global settings.  Point it at the file holding the site's HTTPS block.  A
   file whose blocks all serve plain HTTP gets the line in every block, which
   is not what you want: behind certbot's Apache plugin, name
   ``<name>-le-ssl.conf``, not ``<name>.conf``.

``error: FILE does not exist; --attach-to names the vhost file of the existing site``
   The path is wrong.  ``ls /etc/apache2/sites-enabled/`` (or
   ``/etc/nginx/sites-enabled/``) shows the files the web server loads.

``error: web-server step: the configuration check failed with the snippet included; FILE is back as it was before this run``
   The existing site's configuration does not accept the snippet; the
   installer took its line out again.  Run ``apachectl configtest`` or
   ``nginx -t`` with the line added by hand to see why.  On nginx without a
   prefix, the existing ``server`` block must have no ``location /``.

``error: --attach-to is used only with --tls existing``, ``error: --attach-to must be an absolute path, not ...``
   Give ``--tls existing`` with it, and a full path.

``error: --certbot-email is required with --tls certbot``
   Give ``--certbot-email ADDRESS``, or pick ``--tls self-signed`` or
   ``--tls existing``.

``error: --hostname is required on the first run``
   No install record exists yet.  Give ``--hostname``.

``error: apache2 and nginx are both running; stop the one CalDART does not use``
   Stop and disable the other server, or install with ``--web-server`` naming
   the one that runs.

``error: ... is not supported; use Debian or Ubuntu``
   The packages step runs only on Debian and Ubuntu.

``error: /opt/caldart exists and is not a checkout; move it aside first``
   ``bootstrap.sh`` cannot clone into a directory that already has something
   in it.  Move it aside and run ``bootstrap.sh`` again.

``error: the checkout at /opt/caldart has local changes; commit, stash, or discard them first``
   ``upgrade.sh`` refuses to pull over edits to the checkout.  ``git -C
   /opt/caldart status`` shows them; ``git -C /opt/caldart stash`` sets them
   aside.

``error: the checkout is on a detached HEAD; run upgrade.sh --ref <branch>``
   A rollback left the checkout on a commit.  Upgrade with ``--ref main``.

``error: --yes is required: this removes the site``
   ``uninstall.sh`` needs ``--yes``.

``error: caldart-web did not answer 200 on http://127.0.0.1:8001/ within 30 seconds``
   The web service did not start.  The installer prints the unit's last 30
   journal lines above the error; ``journalctl -u caldart-web -n 50`` shows
   more.  After fixing the cause, ``sudo /opt/caldart/deploy/steps/web-service.sh``
   restarts it and waits again.  A ``status=226/NAMESPACE`` there means a
   directory the unit writes is missing: ``sudo /opt/caldart/deploy/steps/user.sh``
   creates them.

``error: check failed: ...``
   ``steps/check.sh`` names every check that missed.  Behind an existing site
   installed without ``--attach-to``, the site does not answer under the
   prefix until the include line is in place.  Fix the cause, then run
   ``sudo /opt/caldart/deploy/steps/check.sh``.

**certbot says the challenge failed.**  The hostname (or ``www.HOST``) does
not resolve to this server, or port 80 is closed.  From another machine,
``curl -I http://caldart.example.org/.well-known/acme-challenge/x`` should
reach this server and answer 404.  Fix the DNS or the firewall, or give
``--no-www``, then run ``sudo /opt/caldart/deploy/steps/web-server.sh``.  Let's
Encrypt limits failed attempts per hour, so check with ``curl`` first.

**No mail arrives.**  Run ``sendtestemail`` as under `Mail`_, and read
``journalctl -u caldart-web`` for the error.
With ``--email local`` and the note that nothing listens on port 25, install
postfix.  Many providers want ``smtp+tls://`` on port 587 with an app password.

**One step needs running again.**  Every step runs alone and reads the install
record::

  sudo /opt/caldart/deploy/steps/web-server.sh
  sudo /opt/caldart/deploy/steps/build.sh --dry-run

``steps/database.sh`` also takes ``--admin-email`` and ``--seed-content``, and
``steps/configure.sh`` the environment file's flags (it does nothing once the
file exists).


For the design behind these scripts, and every command each step runs, read
the Deployment chapter of the developer guide, ``docs/developer/deployment.rst``.
