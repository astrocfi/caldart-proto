==========
Deployment
==========

How to put CalDART on a single Linux server: Postgres in Docker, gunicorn under
systemd, Apache in front terminating TLS.  Apache is the primary target because
the machines this is aimed at already run it; an nginx configuration ships as
the alternative and is called out where the two differ.  The site either has a
hostname of its own or lives under a path, such as ``/caldart-proto``, of a
site the machine already serves over HTTPS (:ref:`deploy-prefix`).

Scripts under ``deploy/`` do all of it.  ``deploy/bootstrap.sh`` clones the
repository and runs ``deploy/install.sh``, which runs the steps under
``deploy/steps/`` in order; ``deploy/upgrade.sh`` upgrades a running server and
``deploy/uninstall.sh`` takes it off again; ``deploy/manage.sh`` and
``deploy/compose.sh`` run a management command and a ``docker compose``
command against the installed site.  The numbered sections below are
the steps, each titled with the script that runs it and showing the commands
that script runs, so the page reads both as the description of the installer
and as what to do by hand when one step needs attention.


.. _deploy-layout:

The deploy root
===============

The deploy root is ``/opt/caldart``, which is what the shipped files say.  It
holds the checkout and, beside it, everything the site writes that must outlive
the code, so a dump or an upload is never inside the git checkout:

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Path
     - What it holds
   * - ``/opt/caldart/caldart``
     - the checkout of this repository, owned by root and readable by the
       ``caldart`` service user, with the build output inside it: the
       virtualenv in ``.venv``, the frontend in ``frontend/dist``, the static
       files in ``backend/staticfiles``, and the user guide in ``docs/_build``
   * - ``/opt/caldart/backups``
     - the database dumps (``BACKUP_DIR``), owned by the service user
   * - ``/opt/caldart/media``
     - Wagtail's image and document uploads (``MEDIA_ROOT``), owned by the
       service user

Every script finds the checkout from its own location, and the deploy root as
the checkout's parent, so a clone anywhere else works as well: every unit,
vhost, and snippet the scripts install has ``/opt/caldart/caldart`` replaced by
the real checkout and ``/opt/caldart`` by the real deploy root as it is copied,
and ``deploy/gunicorn.conf.py`` finds the checkout from its own location.  The
install record's ``CALDART_ROOT`` names the deploy root for the operator;
nothing reads it back.


.. _deploy-install-scripts:

Installing with the scripts
===========================

On a fresh Debian 13 (trixie) or Ubuntu 24.04 (noble) server, with the
hostname's DNS ``A`` (and ``AAAA``) records already pointing at it and ports 80
and 443 open, one command installs everything::

  curl -fsSL https://raw.githubusercontent.com/astrocfi/caldart-proto/main/deploy/bootstrap.sh \
      | sudo bash -s -- --hostname caldart.example.org \
          --certbot-email ops@example.org \
          --email-url smtp+tls://user:password@smtp.example.org:587 \
          --admin-email you@example.org

``bootstrap.sh`` installs ``git`` if the box has none, creates the deploy root
``/opt/caldart`` when it is missing, clones
``https://github.com/astrocfi/caldart-proto.git`` into ``/opt/caldart/caldart``
(or, when a checkout is already there, fetches and checks out the ref), and
runs ``deploy/install.sh`` from it with every other flag passed through
untouched.  ``CALDART_ROOT`` in its environment names another deploy root; the
checkout always goes in its ``caldart`` directory.  On a server that already
has the checkout, run the installer directly::

  sudo /opt/caldart/caldart/deploy/install.sh --hostname caldart.example.org ...

The flags:

.. list-table::
   :header-rows: 1
   :widths: 30 45 25

   * - Flag
     - Meaning
     - Default
   * - ``--hostname HOST``
     - the public hostname, a DNS name such as ``caldart.example.org``
     - required on the first run
   * - ``--www`` / ``--no-www``
     - also answer for ``www.HOST``
     - ``--www``
   * - ``--web-server apache|nginx``
     - which web server to install
     - ``apache``
   * - ``--tls certbot|self-signed|existing``
     - how the certificate is obtained; ``existing`` means a web server on this
       machine already serves the hostname over HTTPS, and CalDART is included
       in its vhost (:ref:`deploy-prefix`)
     - ``certbot``
   * - ``--certbot-email ADDRESS``
     - the Let's Encrypt account address
     - required with ``--tls certbot``
   * - ``--url-prefix PREFIX``
     - serve the site under this path, such as ``/caldart-proto``; ``/`` names
       the root of the host (:ref:`deploy-prefix`)
     - the root of the host
   * - ``--attach-to FILE``
     - with ``--tls existing``, the existing site's vhost file to include
       CalDART's snippet in
     - print the line to add
   * - ``--certbot-staging``
     - use Let's Encrypt's staging directory, for a trial run
     - off
   * - ``--db-port PORT``
     - the host port Postgres is published on, 1024 to 65535
       (:ref:`deploy-sharing`)
     - ``5432``
   * - ``--gunicorn-port PORT``
     - the port on ``127.0.0.1`` where the web server's proxy reaches
       gunicorn, 1024 to 65535; not the site's port, which is 80 and 443 on the
       web server (:ref:`deploy-sharing`)
     - ``8001``
   * - ``--email-url URL``
     - ``EMAIL_URL`` for the environment file (:doc:`email`)
     - this or ``--email local`` on the first run
   * - ``--email local``
     - send mail through the postfix on this machine:
       ``EMAIL_URL=smtp://localhost:25`` (:ref:`email-local-postfix`)
     - this or ``--email-url`` on the first run
   * - ``--from-email ADDRESS``
     - ``DEFAULT_FROM_EMAIL``
     - ``CalDART <noreply@HOST>``
   * - ``--admin-email ADDRESS``
     - create the first administrator
     - none
   * - ``--seed-demo``
     - load the demo accounts alone, sharing the password ``README.rst``
       documents (:ref:`deploy-database`)
     - off
   * - ``--seed-content``
     - load the example website alone, with no accounts
     - off
   * - ``--repo URL-OR-PATH``
     - ``bootstrap.sh`` only: what to clone
     - ``https://github.com/astrocfi/caldart-proto.git``
   * - ``--ref REF``
     - ``bootstrap.sh`` and ``upgrade.sh``: the branch, tag, or commit
     - ``main``, or the current branch
   * - ``--dry-run``
     - print every command that changes the machine instead of running it
     - off
   * - ``--help``
     - print the script's header, which lists its options
     -

``--tls self-signed`` is for a box without a public hostname, such as a trial
server on a private network: the certificate is made with ``openssl`` in
``/etc/caldart/tls/``, browsers warn until a real one replaces it, and the
environment file sets ``SECURE_HSTS_SECONDS=0`` so no browser remembers HSTS
for a name the box does not own.  There is no plain-HTTP mode:
``caldart.settings.prod`` insists on secure cookies and redirects HTTP to HTTPS.

**The install record.**  The values that describe the box (the deploy root, the
hostname, ``www``, the web server, the TLS mode, the certbot address, staging,
the database port, the gunicorn port, the URL prefix, and the attached vhost file) are written to ``/etc/caldart/install.conf``,
``root:root``, mode ``0644``, holding no secret.  Every step reads it, so a
later run needs no flags, and a flag given on a later run updates the record.
``--email-url``, ``--email``, ``--from-email``, ``--admin-email``,
``--seed-demo``, and ``--seed-content`` are used by the run that writes the
environment file or creates the administrator, and are not recorded.  The
first run stops with a
usage error naming ``--hostname`` when no record exists, ``--email-url`` and
``--email local`` while no environment file exists, and ``--certbot-email``
with certbot.  Giving both ``--email-url`` and ``--email local`` is a usage
error too, and so is ``--attach-to`` without ``--tls existing`` or with a
relative path.

**Running it again.**  Every step is idempotent: a user that exists, a unit
already enabled, a certificate already issued, and a database already migrated
are all left as they are, so a second run repairs or re-applies an install and
never destroys data or overwrites a secret.  Each step also runs alone, reading
what it needs from the record::

  sudo /opt/caldart/caldart/deploy/steps/web-server.sh

``--dry-run`` on any script (or ``CALDART_DRY_RUN=1`` in its environment) prints
every command that would change the machine, prefixed ``+``, instead of running
it, and needs no root.  The reads still happen, so a dry run on a fresh box
prints the whole sequence a real run would, in order.  A file the dry run never
wrote, such as the environment file or the record, is treated as absent, with a
note on standard error; the generated database password appears as
``<generated>``, and the environment file's contents are never printed.

**What it prints.**  One ``==>`` line per stage; when a command fails, its own
output and an ``error:`` line naming the stage and the command; and at the end the checks of :ref:`deploy-check` and a summary: the
site's address, the environment file, the administrator's one-time link when
``--admin-email`` created one, the Stripe, PayPal, and Geoapify settings still
empty in the environment file, a caution naming the shared demo password when
``--seed-demo`` ran, and, with a self-signed certificate, the browser warning.
Open the administrator's link to set a password; it lasts as long as any
password-reset link (``PASSWORD_RESET_TIMEOUT``).

**Afterwards.**  The site runs without payment or address keys: checkout
offers no provider and the profile form offers no address suggestions until
they are set.  Add them with ``sudoedit /etc/caldart/caldart.env``, then
``sudo systemctl restart caldart-web``: the Stripe and PayPal keys as
:doc:`payments-setup` describes, and ``GEOAPIFY_API_KEY`` (:doc:`configuration`).
A changed SMTP relay is edited the same way.  No script ever rewrites the
environment file once it exists.  Point the mail domain's SPF, DKIM, and DMARC
records at the relay before relying on the mail (:doc:`email`).


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
              label="One Linux server, deploy root /opt/caldart,\lcheckout /opt/caldart/caldart\l";
              fontname="Helvetica";
              fontsize=11;
              style=dashed;
              color="gray";

              Apache [label="Apache 2.4 :80 and :443\l  deploy/apache/caldart.conf\l  terminates TLS (certbot)\l  :80 -> :443, except ACME\l  ProxyTimeout 60\l"];
              Gunicorn [label="gunicorn 127.0.0.1\l  :CALDART_GUNICORN_PORT, 8001 by default\l  caldart-web.service\l  deploy/gunicorn.conf.py\l  2 x CPU + 1 workers, max 12\l  timeout 60, preload\l"];
              Django [label="Django 6 + Wagtail 8\l  caldart.settings.prod\l  /static/ via whitenoise\l"];
              Postgres [label="Postgres in Docker\l  :CALDART_DB_PORT, 5432 by default\l  compose service db\l"];
              Media [label="/opt/caldart/media/\l  MEDIA_ROOT, Wagtail uploads;\l  documents/ denied to\l  the web server\l", shape=folder, style=""];
              Env [label="/etc/caldart/caldart.env\l  root:caldart 0640\l  EnvironmentFile for\l  all seven services\l", shape=note, style=""];

              Apache -> Gunicorn [label="HTTP 127.0.0.1:CALDART_GUNICORN_PORT\lX-Forwarded-Proto: https\l"];
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
      :caption: The same server's six scheduled jobs.  Each timer starts its
                service, which runs a management command and exits.  A
                **solid arrow** is the job reading and writing the database; a
                **dashed arrow** is an outbound call; a **dotted arrow** is a
                file written to disk.  Every job service reads its settings
                from the same environment file as ``caldart-web.service``, so
                the server runs seven services in all.
      :alt: The six CalDART timers and their services, each using
            Postgres; four send mail, the renewals job also charges through
            Stripe and PayPal, the registry job downloads the FAA registry,
            and the backup job writes dumps to the backup directory

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
          Registry [label="caldart-registry.timer\l  daily 04:30 ->\l  caldart-registry.service\l  manage.py import_faa_registry\l"];
          Backup [label="caldart-backup.timer\l  daily 03:30 ->\l  caldart-backup.service\l  manage.py db_backup,\l  then prunes old dumps\l"];
          Dumps [label="/opt/caldart/backups/\l  BACKUP_DIR, kept for\l  BACKUP_RETENTION_DAYS\l", shape=folder, style=""];
          Faa [label="registry.faa.gov\l  ReleasableAircraft.zip\l"];
          Stripe [label="Stripe and PayPal\l  off-session charges\l"];
          Postgres [label="Postgres in Docker\l  :CALDART_DB_PORT, 5432 by default\l"];
          Smtp [label="SMTP server\l  from EMAIL_URL\l"];

          {rank=same; Dumps; Faa; Stripe; Postgres; Smtp;}
          {rank=same; Backup; Registry; Reports; Renewals; Reminders; Statements;}
          Dumps -> Faa -> Stripe -> Postgres -> Smtp [style=invis];
          Backup -> Registry -> Reports -> Renewals -> Reminders -> Statements [style=invis];

          Env -> {Backup Registry Reports Renewals Reminders Statements} [style=dashed, arrowhead=none];
          Backup -> Postgres;
          Backup -> Dumps [style=dotted];
          Registry -> Faa [style=dashed];
          Registry -> Postgres;
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

      browser --HTTPS :443--> Apache 2.4 --HTTP--> gunicorn 127.0.0.1
      (:80 redirects              |                   |  :CALDART_GUNICORN_PORT,
       except ACME)               |                   |  8001 by default
                                  |                   |  caldart-web.service
                                  |                   |  2 x CPU + 1 workers,
            serves /media/ -------'                   |  max 12, timeout 60
            off /opt/caldart/media;                   |
            documents/ is denied,                     v
            because Django's members-only       Django 6 + Wagtail 8
            check is the only way in            caldart.settings.prod
                                                /static/ via whitenoise
      Stripe / PayPal webhooks arrive                 |
      through Apache like any other request           v
                                                Postgres in Docker
                                                :CALDART_DB_PORT, 5432 by default
      caldart-backup.timer, daily 03:30               ^
        -> caldart-backup.service                     |
           manage.py db_backup -----------------------|
           -> /opt/caldart/backups (BACKUP_DIR),      |
              then deletes                            |
              dumps older than BACKUP_RETENTION_DAYS  |
                                                      |
      caldart-registry.timer, daily 04:30             |
        -> caldart-registry.service                   |
           manage.py import_faa_registry -------------|
           -> registry.faa.gov, for the FAA's         |
              Releasable Aircraft Database            |
                                                      |
      caldart-reports.timer, daily 06:00              |
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

   Apache, gunicorn, Postgres, and the six timers run on one Linux server with
   the deploy root ``/opt/caldart`` and the checkout in
   ``/opt/caldart/caldart``, and all seven services (``caldart-web`` and
   the six job services) read their settings from ``/etc/caldart/caldart.env``
   (``root:caldart``, mode ``0640``).  Django calls out to ``api.stripe.com``
   and ``api-m.paypal.com`` during a checkout, and to the same SMTP server for
   password resets and invitations.  ``nginx`` (``deploy/nginx/caldart.conf``)
   takes Apache's place unchanged when you deploy it instead.

Three things run continuously: the Docker Postgres container, the
``caldart-web`` gunicorn unit, and Apache.  Six jobs run on a schedule: the
``caldart-backup`` timer daily at 03:30, the ``caldart-registry`` timer daily at
04:30, the ``caldart-reports`` timer daily
at 06:00, the ``caldart-renewals`` timer daily at 06:30, the
``caldart-reminders`` timer daily at 07:00, and the ``caldart-statements`` timer
yearly at 06:45 on January 15th.

The application is a **Django 6** project with Wagtail 8 on top, and step 6
(``deploy/steps/build.sh``) installs it with ``uv sync --frozen``, so the box runs the exact versions
``uv.lock`` pins, the ones the test suite ran against.  Django 6 configures
outgoing mail through its ``MAILERS`` setting, which ``prod.py`` builds from
``EMAIL_URL`` and ``EMAIL_TIMEOUT``; both are in the environment file written
in step 5 and documented in :doc:`configuration`.

``/static/`` is deliberately **not** aliased in the web server.  whitenoise
serves it through the proxy so that the hashed filenames stay authoritative
and get far-future cache headers: ``collectstatic`` hashes every file's name
except Vite's build output under ``assets/``, which Vite has hashed already
(:doc:`architecture`).  The user guide
at ``/docs/`` is not aliased either: Django serves it from ``USER_GUIDE_ROOT``
and asks the reader to sign in first, so it stays behind the same login as the
portal and needs nothing from the web server (:doc:`configuration`).  Only
``/media/`` — Wagtail's user uploads, which keep their filenames — is served
straight off disk, and ``/media/documents/`` is carved back out of it: a
document may belong to the members-only collection, and Django's document view
is what enforces that (:doc:`cms`).  Both vhosts refuse that prefix, so a
document is only ever reachable at ``/documents/<id>/<filename>``.


1. Operating system packages (``steps/packages.sh``)
====================================================

The steps are written for Debian 13 (trixie) and Ubuntu 24.04 (noble), and
every package they name comes from those distributions' own archives.  The
script reads ``ID`` from ``/etc/os-release`` and stops on any other
distribution, naming the two it supports.  ``apt-get`` runs with
``DEBIAN_FRONTEND=noninteractive`` and ``-y``.  What it runs::

  sudo apt-get update
  sudo apt-get install -y git curl ca-certificates openssl postgresql-client docker.io

  # Debian 13: the Compose v2 plugin is the docker-compose package
  sudo apt-get install -y docker-compose
  # Ubuntu 24.04: it is docker-compose-v2 (docker-compose there is the old v1)
  sudo apt-get install -y docker-compose-v2

  # The web server the record names, certbot, and certbot's plugin for that
  # server.  The plugin is what writes the TLS options file the vhost includes
  # (step 9).
  sudo apt-get install -y apache2 certbot python3-certbot-apache
  # ... or, with --web-server nginx:
  sudo apt-get install -y nginx certbot python3-certbot-nginx
  # ... or, with --tls existing, the web server alone: the existing site holds
  # the certificate, and the package is already there, which apt-get leaves be.
  sudo apt-get install -y apache2

  # Node 22 for the frontend build, from NodeSource, only when node is missing
  # or older: Debian and Ubuntu ship older releases than the build needs.
  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo bash -
  sudo apt-get install -y nodejs

  # uv, only when /usr/local/bin/uv is missing, installed where sudo finds it.
  curl -LsSf https://astral.sh/uv/install.sh \
      | sudo env UV_INSTALL_DIR=/usr/local/bin UV_NO_MODIFY_PATH=1 sh

  sudo systemctl enable --now docker

The script installs one Compose package and one web server; ``docker compose
version`` then prints a v2 version.  A Docker the machine already has is kept:
``docker.io`` is left out of the list when ``docker --version`` works, and the
Compose package too when ``docker compose version`` does (:ref:`deploy-sharing`).

``uv`` goes to ``/usr/local/bin`` because ``sudo`` resets ``PATH`` to a
fixed list that does not include root's ``~/.local/bin``, where the installer
puts it by default.

``postgresql-client`` gives ``db_backup`` and ``db_restore`` a local
``pg_dump``/``psql``, which they prefer over running them inside the container;
the environment file of step 5 sets ``DB_BACKUP_VIA_DOCKER=false`` to match.

The project pins Python 3.12, and uv downloads that interpreter itself when
the system has another version.  Step 6 tells it to put the download in
``/opt/uv/python``, where the service user can read it, instead of under
``/root``.


2. Service user (``steps/user.sh``)
===================================

::

  sudo useradd --system --create-home --home-dir /home/caldart \
      --shell /usr/sbin/nologin caldart
  sudo install -d -o root -g caldart -m 0750 /etc/caldart
  sudo install -d -o caldart -g caldart \
      /opt/caldart/backups \
      /opt/caldart/media \
      /opt/caldart/caldart/backend/staticfiles
  sudo find /opt/caldart/media -type d -exec chmod 0755 {} +
  sudo find /opt/caldart/media -type f -exec chmod 0644 {} +

``useradd`` runs only when the user is missing.  The two ``find`` commands make
every upload readable by the web server, which serves ``/media/`` off disk as
its own user: the site writes uploads ``0644`` in ``0755`` directories, and
these repair any an earlier run wrote under the service's ``UMask=0027``.  The
upgrade runs this step too.  Its home is ``/home/caldart``,
its own directory and never the checkout; nothing is ever written there,
because the units keep ``/home`` out of reach (``ProtectHome=true``) and the
services write only the three directories above.  An existing user whose home is
somewhere else (an earlier install put it at the checkout) is given the
directory and pointed at it with ``usermod --home``; the old home is left as
it is.  The user is not in the ``docker`` group: nothing the services run
talks to Docker, since the backups use the local ``pg_dump``.

The checkout is owned by root and readable by the service user.  The web unit
mounts everything read-only except the three directories above, which the
service user owns, and ``caldart-web.service`` refuses to start when a
directory it lists in ``ReadWritePaths`` is missing.  ``backups`` in the deploy
root holds the database dumps and ``media`` beside it Wagtail's uploads, both
outside the checkout (:ref:`deploy-layout`), so neither git nor an upgrade
ever sees them, and a reinstall keeps whatever they hold.
``backend/staticfiles`` in the checkout holds what ``collectstatic`` writes;
it is build output, and gitignored.


.. _deploy-checkout:

3. The checkout (``bootstrap.sh``)
==================================

``bootstrap.sh`` makes the checkout before ``install.sh`` starts, so on a
scripted install this step runs first::

  sudo install -d /opt/caldart
  sudo git clone https://github.com/astrocfi/caldart-proto.git /opt/caldart/caldart
  sudo git -C /opt/caldart/caldart checkout main

``git clone`` refuses a directory with anything in it, so ``bootstrap.sh``
stops when ``/opt/caldart/caldart`` exists, is not empty, and is not a
checkout.  The deploy root around it may hold anything: a ``backups`` or
``media`` directory from an earlier install stays as it is.  When
``/opt/caldart/caldart`` is a checkout, ``bootstrap.sh`` fetches, checks out
``--ref``, and pulls a branch instead of cloning.  ``--repo`` clones from
another URL or a local path.

Every command from here on runs from the checkout, ``/opt/caldart/caldart``.


4. Postgres in Docker (``steps/postgres.sh``)
=============================================

``docker-compose.yml`` at the repository root defines the ``db`` service with a
named volume, ``caldart_pgdata``, so the data survives ``docker compose down``
and container upgrades.  The step starts that service alone (Mailpit is a
development container and never starts on a server) and waits up to 60
seconds for it::

  sudo deploy/compose.sh up -d db
  sudo deploy/compose.sh exec -T db pg_isready -U caldart -d caldart

``docker-compose.yml`` publishes the database as
``"127.0.0.1:${CALDART_DB_PORT:-5432}:5432"``, so it listens on loopback only
and nothing off the box can reach it.  ``CALDART_DB_PORT`` is the port
``--db-port`` recorded, ``5432`` unless it said otherwise; every script
exports it from the install record before it runs ``docker compose``.  The
container has ``restart: unless-stopped``, so Docker starts it again after a
reboot.

Before it creates the container (no ``caldart-db-1`` container exists yet),
the step asks ``ss -ltnH "sport = :PORT"`` whether anything already listens on
the port, such as a Postgres installed from the distribution or running in
another container, and stops if something does::

  error: port 5432 is already in use on this machine; run install.sh --db-port PORT to put CalDART's Postgres on another port

A later run finds its own container holding the port and skips the check.
:ref:`deploy-sharing` covers what else the install shares with the machine.

**deploy/compose.sh.**  Run ``docker compose`` on the server through
``deploy/compose.sh``, which loads the install record, exports
``CALDART_DB_PORT``, changes to the checkout, and hands its arguments to
``docker compose``::

  sudo deploy/compose.sh ps
  sudo deploy/compose.sh logs -f db
  sudo deploy/compose.sh exec -T db psql -U caldart -d caldart

A plain ``sudo docker compose up`` in the checkout works on a box that kept
port 5432, but on one that moved it the missing variable publishes the
container on 5432 again.  ``--dry-run`` before the command prints it instead,
with the port it would use.

The container starts with the development password.  On the first run of
``install.sh``, before the environment file exists, the step replaces it with a
generated one and hands the password to step 5 in a shell variable, never in a
file.  The statement reaches ``psql`` on standard input, so the password never
appears on a command line or in the process list::

  echo "ALTER USER caldart WITH PASSWORD '<generated>';" \
      | sudo deploy/compose.sh exec -T db psql -q -v ON_ERROR_STOP=1 -U caldart -d postgres

Once the environment file exists the password is whatever ``DATABASE_URL``
there says, and the step only starts the service and waits.  Run alone, it
never changes the password.

The container creates a database named ``caldart`` on its first start, which
is the name the environment file uses.


.. _deploy-sharing:

Sharing the machine
-------------------

The install leaves another Postgres on the machine, native or in another
Docker container, alone.  Everything Compose creates is namespaced by the
project name ``caldart`` that ``docker-compose.yml`` pins: the container
``caldart-db-1``, the volume ``caldart_caldart_pgdata``, and the network
``caldart_default``.  None of them can collide with another project's.  The
one thing the container shares with the rest of the machine is the host port
it is published on, and ``--db-port`` moves it::

  sudo deploy/install.sh --db-port 5433 ...

The step above stops before it creates the container when the port is taken,
so a clash is reported rather than half-installed.  A Docker that is already
installed is left as it is, and the containers other projects run keep
running.  The packages step installs ``docker.io`` only when ``docker
--version`` fails, and the Compose package only when ``docker compose
version`` fails, so a Docker from Docker's own apt repository (``docker-ce``
and ``containerd.io``, which ``docker.io`` conflicts with) is never replaced.
Such a Docker without its Compose plugin gets the distribution's Compose
package, which may want ``docker.io``; install ``docker-compose-plugin`` from
Docker's repository first instead.

**Moving the port on an installed box.**  The install leaves an existing
environment file alone, so ``--db-port`` alone would move the container while
``DATABASE_URL`` still named the old port.  The installer refuses that before
it changes anything::

  error: --db-port 5433 differs from the port in DATABASE_URL in /etc/caldart/caldart.env (5432); edit DATABASE_URL to use port 5433 first, then run install.sh again

Check that nothing listens on the new port (``ss -ltn "sport = :5433"``
prints only its header), since the step's own check runs only before the
container exists.  Then change the port in ``DATABASE_URL`` in
``/etc/caldart/caldart.env`` and run the installer with the flag; it recreates
the container on the new port, records it, and restarts ``caldart-web``::

  sudo deploy/install.sh --db-port 5433

**The gunicorn port.**  The web server reaches gunicorn on ``127.0.0.1`` at a
port of its own, 8001 by default, and ``--gunicorn-port`` moves it when another
program on the machine holds 8001::

  sudo deploy/install.sh --gunicorn-port 8101 ...

It is the port of the hop from the web server's proxy to gunicorn, never the
port the site is served on: browsers still reach the web server on 80 and 443.
The record keeps it as ``CALDART_GUNICORN_PORT``, and a record without that key
means 8001.  gunicorn reads it from ``CALDART_GUNICORN_PORT`` in the environment
file, and every shipped file that names gunicorn's address (both vhosts, both
snippets, and the nginx upstream) is copied with the port written in, as the
checkout and the deploy root are.  The gunicorn step stops before it installs the unit when the
port is taken (:ref:`deploy-web-service`).

**Moving gunicorn's port on an installed box.**  Run the installer with the
flag.  It records the port, writes it into the environment file, restarts
``caldart-web`` on it, and then rewrites the vhost (or the snippet and the
upstream) and reloads the web server with ``reload-or-restart``, in that order::

  sudo deploy/install.sh --gunicorn-port 8101

The step's own check runs only before the unit is installed, so first check
that nothing listens on the new port (``ss -ltn "sport = :8101"`` prints only
its header).  ``upgrade.sh`` takes no such flag and keeps the recorded port.


5. Configuration (``steps/configure.sh``)
=========================================

``/etc/caldart/caldart.env`` holds every runtime setting.  The step writes it
once, ``root:caldart``, mode ``0640``, from the **production** template
``deploy/caldart.env.example``, and afterwards changes only the gunicorn port
in it.

.. warning::

   The repository's ``.env.example`` is the development template: it ships the
   published ``SECRET_KEY`` and sets ``PAYMENTS_MOCK_ENABLED=true``, which
   renders "Succeed" and "Fail" buttons at checkout and would hand out
   memberships for free.  Nothing installs it on a server.

The five variables at the top of the template are commented out, so an
unedited copy refuses to start rather than serving with a guessed value.  The
step uncomments and sets every one::

  SECRET_KEY=<python3 -c "import secrets; print(secrets.token_urlsafe(64))">
  ALLOWED_HOSTS=caldart.example.org,www.caldart.example.org
  SITE_URL=https://caldart.example.org<--url-prefix>
  EMAIL_URL=<--email-url, or smtp://localhost:25 with --email local>
  DATABASE_URL=postgres://caldart:<the password from step 4>@localhost:<--db-port>/caldart

Four of them have no default at all: ``prod.py`` refuses to start without
``SECRET_KEY``, ``ALLOWED_HOSTS``, ``SITE_URL``, or ``EMAIL_URL``, and refuses
the published development ``SECRET_KEY`` as well.  Nothing in the production
settings reads a ``.env`` file, so a stray one in the checkout cannot fill in a
variable that is missing.

``install.sh`` runs this step right after the Postgres one, in the same
process, so the password reaches ``DATABASE_URL`` the way the block above
shows; the port is the one the install record names.  Run ``steps/configure.sh`` on its own before the Postgres step has
handed it a password, and it warns on standard error and writes a generated
password of its own instead, which the database does not have; run the
Postgres step (or the whole installer) first, or edit ``DATABASE_URL`` in the
file by hand afterwards.

It also sets ``CSRF_TRUSTED_ORIGINS`` to the ``https://`` form of the same
hosts, ``DEFAULT_FROM_EMAIL`` from ``--from-email`` (``CalDART
<noreply@HOST>`` by default), ``BACKUP_DIR`` and ``MEDIA_ROOT`` to the deploy
root's ``backups`` and ``media`` (beside the checkout, :ref:`deploy-layout`),
``USER_GUIDE_ROOT`` to the checkout's ``docs/_build/guide``,
``DB_BACKUP_VIA_DOCKER=false``, ``BACKUP_RETENTION_DAYS=30``, and
``CALDART_GUNICORN_PORT`` to the gunicorn port the record names (8001 unless
``--gunicorn-port`` says otherwise), printing that one line under its stage
line, a dry run included; with ``--url-prefix``, ``URL_PREFIX`` (``SITE_URL`` must end in it, and
``prod.py`` refuses a file where it does not); with ``--tls self-signed``,
``SECURE_HSTS_SECONDS=0`` too.  With ``--tls existing`` the HSTS default is
left as the template has it: the existing site owns HSTS for its host.

With ``--email local`` the step checks with ``ss -ltnH "sport = :25"`` that
something listens on port 25, and, when nothing does, prints a note on standard
error (not an error: the install carries on) that mail fails until postfix is
installed and listening on localhost.  The installer installs no mail server;
:ref:`email-local-postfix` describes what the machine's postfix needs.  Everything else,
comments included, stays as the template has it, so the file still explains
itself: the throttle rates, ``GEOAPIFY_API_KEY`` (the key behind the profile
form's address suggestions, which stay off while it is blank), and the Stripe
and PayPal keys.  :doc:`configuration` documents every variable, what reads
it, and its development and production values.  The Stripe and PayPal keys are
covered in :doc:`payments-setup`, and what the mail domain needs before
``EMAIL_URL`` delivers anything in :doc:`email`.

When the file exists the step leaves it alone but for one line: when
``CALDART_GUNICORN_PORT`` names another port than the record, or the file has
no such line, it sets the line to the recorded port and writes the file back
with the same owner and mode, every other line as it was.  Otherwise it says it
is leaving the file alone.  Either way it reports any ``--email-url``,
``--email local``, or ``--from-email`` given on that run as ignored.  Change
anything else in the file by hand, then restart the web unit::

  sudoedit /etc/caldart/caldart.env
  sudo systemctl restart caldart-web

The file contains the database password, the Django secret key and the payment
provider secrets; it is never world-readable and never committed.


.. _deploy-build:

6. Build (``steps/build.sh``)
=============================

::

  cd /opt/caldart/caldart
  sudo env UV_PYTHON_INSTALL_DIR=/opt/uv/python uv sync --frozen --no-dev --group docs
  cd frontend && sudo npm ci && sudo npm run build && cd ..
  sudo .venv/bin/sphinx-build -n -W -b dirhtml -t guide -c docs docs/user docs/_build/guide

``uv sync --frozen`` installs the exact versions ``uv.lock`` pins, the ones the
test suite ran against, into ``/opt/caldart/caldart/.venv``.  ``--no-dev`` leaves out
the test and lint tools, and ``--group docs`` adds Sphinx and its theme for the
last line.  ``UV_PYTHON_INSTALL_DIR`` matters only when uv has to download
Python 3.12: the virtualenv links to that interpreter, and under ``/root`` the
service user could not reach it.

``npm run build`` writes ``frontend/dist`` including
``.vite/manifest.json``, which django-vite reads to find the hashed asset
names.  Without it every page raises at render time.

The last line builds the user guide into ``docs/_build/guide``, the directory
Django serves at ``/docs/`` to signed-in users (it is ``make guide`` on a
checkout).  It calls the virtualenv's ``sphinx-build`` directly: ``uv run``
would first sync the default dependency groups, development tools included.
The developer guide is not published: the build reads ``docs/user`` alone.
Without this step ``/docs/`` answers 404 and the journal says the guide has not
been built.  A deployment that keeps the guide elsewhere sets
``USER_GUIDE_ROOT``.

The checkout stays root-owned and world-readable.


.. _deploy-database:

7. Database and static files (``steps/database.sh``)
====================================================

.. _deploy-manage-commands:

Running management commands
---------------------------

``deploy/manage.sh`` runs a management command on the server, and every
production command in this document and in :doc:`backup-restore` is written as
a call to it::

  sudo deploy/manage.sh migrate
  sudo deploy/manage.sh health --json

A management command needs the same five things ``caldart-web.service`` gives
gunicorn: the ``caldart`` user, ``/opt/caldart/caldart/backend`` as the working
directory, ``/etc/caldart/caldart.env``,
``DJANGO_SETTINGS_MODULE=caldart.settings.prod``, and ``UMask=0027``.  The
script lets systemd assemble them again, as a transient unit, instead of
loading the environment file from a shell.  systemd keeps interior whitespace
in an unquoted value, so ``DEFAULT_FROM_EMAIL=CalDART <noreply@caldart.example.org>``
reaches the command intact; a shell splits it at the spaces and the command
never starts.  What it runs::

  sudo systemd-run --quiet --wait --collect --pty --pipe \
      --uid=caldart --gid=caldart \
      --working-directory=/opt/caldart/caldart/backend \
      --property=EnvironmentFile=/etc/caldart/caldart.env \
      --property=UMask=0027 \
      --setenv=DJANGO_SETTINGS_MODULE=caldart.settings.prod \
      /opt/caldart/caldart/.venv/bin/python manage.py "$@"

``--wait`` blocks until the command finishes and hands its exit status back,
which the script passes on, so ``deploy/manage.sh`` can be tested in a script.
``--collect`` unloads the transient unit afterwards, including when it failed.
Given both ``--pty`` and ``--pipe``, systemd allocates a terminal when one is
attached (which the ``db_restore`` prompt needs) and passes plain pipes
through when the output is redirected.  ``--dry-run`` before the command name
prints the ``systemd-run`` line instead of running it.

``UMask=0027`` is the one property with nothing to do with finding the code or
the settings, and it is not optional: a transient unit otherwise takes
systemd's system default of ``0022``, and ``deploy/manage.sh db_backup`` would
write a full dump of the database (member records, password hashes, payment
history) world-readable at mode 0644.  All seven shipped services set the same
mask, so every path that writes a dump writes it readable by the ``caldart``
group and no wider.

Confirm the environment file is being read before relying on it::

  sudo systemd-run --quiet --wait --pipe \
      --property=EnvironmentFile=/etc/caldart/caldart.env \
      /usr/bin/printenv DEFAULT_FROM_EMAIL

That prints the value exactly as the file spells it, spaces included.

Preparing the database
----------------------

::

  sudo deploy/manage.sh migrate
  sudo deploy/manage.sh createcachetable
  sudo deploy/manage.sh seed_roles
  sudo deploy/manage.sh seed_plans
  sudo deploy/manage.sh seed_demo        # with --seed-demo: demo accounts
  sudo deploy/manage.sh seed_content     # with --seed-content: example pages
  sudo deploy/manage.sh collectstatic --noinput

``createcachetable`` builds ``caldart_cache``, the table the default cache
uses.  The anonymous auth throttles count in that cache, and every gunicorn
worker has to see the same counters; the PayPal access token sits there too,
so one fetch serves every worker (see :ref:`paypal-token-cache`).  The command
is idempotent, so running it again costs nothing.

``seed_demo`` and ``seed_content`` are idempotent too, ``get_or_create`` and
``update_or_create`` throughout: running either again on an installed server
updates the existing rows rather than duplicating them, and both run under
``caldart.settings.prod`` like every other management command ``manage.sh``
runs.  **Caution:** the demo accounts ``seed_demo`` creates share the password
``README.rst`` documents, so a server seeded with them is a demonstration
server, never one holding real member data.

``seed_demo``'s renewal mandates use the mock payment provider, so
``caldart-renewals`` has real work to do; production leaves that provider
off, so it fails against the seeded mandates on a server until
``PAYMENTS_MOCK_ENABLED_IN_PRODUCTION=true`` is set in the environment file.
That switch also shows every visitor a **Test payment** tab with *Succeed*
and *Fail* buttons, a way for anyone to grant themselves a membership with no
money changing hands, as :doc:`payments-setup` describes.

With ``--admin-email`` the step creates the first real administrator::

  sudo deploy/manage.sh create_admin --email you@example.org

``create_admin`` makes the account a superuser with the ``member``,
``system_admin``, and ``website_admin`` roles and no usable password (an
existing account with that address gains what it lacks), and prints one line:
a password-reset link, which the installer's summary repeats.  Open it to set
the password.  ``system_admin`` plus ``is_superuser`` is what unlocks
``/portal/system/`` and the Wagtail admin.


.. _deploy-web-service:

8. gunicorn under systemd (``steps/web-service.sh``)
====================================================

::

  sudo install -m 0644 deploy/systemd/caldart-web.service /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable caldart-web.service
  sudo systemctl restart caldart-web.service
  curl -sI -H 'Host: caldart.example.org' -H 'X-Forwarded-Proto: https' \
      http://127.0.0.1:$PORT/ | head -1

``$PORT`` is the gunicorn port, 8001 unless ``--gunicorn-port`` says otherwise.
The unit is copied with ``/opt/caldart/caldart`` replaced by the checkout and
``/opt/caldart`` by the deploy root, and
``restart`` both starts a stopped unit and picks up new code on an upgrade, or
a new port on a later install.  The step then waits up to 30 seconds for the
``curl`` to answer ``200``, and on a timeout prints the unit's last 30 journal
lines and fails.

Before it installs the unit (no ``caldart-web.service`` in
``/etc/systemd/system`` yet), the step asks ``ss -ltnH "sport = :PORT"``
whether anything already listens on the gunicorn port, and stops if something
does::

  error: port 8001 is already in use on this machine; run install.sh --gunicorn-port PORT to put gunicorn on another port

A later run finds the unit installed, and gunicorn itself holding the port, and
skips the check.

The unit runs ``/opt/caldart/caldart/.venv/bin/gunicorn --config
/opt/caldart/caldart/deploy/gunicorn.conf.py`` as ``caldart``, from
``/opt/caldart/caldart/backend``, with
``DJANGO_SETTINGS_MODULE=caldart.settings.prod`` and the environment file from
step 5.  ``deploy/gunicorn.conf.py`` is read in place and finds the Django
project from its own location.  It binds loopback only, on
``CALDART_GUNICORN_PORT`` from the environment file (8001 when the variable is
unset; Django itself ignores it), sizes the worker pool
at ``2 × cores + 1`` **capped at 12** (every worker preloads Django and
Wagtail, so a large machine would otherwise spend its memory on idle
processes), sets a 60 second worker timeout, logs to stdout, and trusts
``X-Forwarded-*`` only from ``127.0.0.1``.  Set ``WEB_CONCURRENCY`` in the
environment file to override the count outright.

It is hardened with the usual systemd sandbox (``ProtectSystem=strict``,
``NoNewPrivileges``, an empty capability set), so the only writable paths are
``media/``, ``staticfiles/``, and ``backups/``.  If you move ``BACKUP_DIR``, add
the new path to ``ReadWritePaths`` or backups will fail with a permission
error.

The ``curl`` stands in for the web server of step 9, which is not there yet.
It needs both headers.  Without the ``Host`` of a name in ``ALLOWED_HOSTS``
Django answers ``400 Bad Request``, and without ``X-Forwarded-Proto: https``
``SECURE_SSL_REDIRECT`` answers ``301`` with a redirect to ``https://``.


.. _deploy-web-server:

9. The web server and TLS (``steps/web-server.sh``)
====================================================

The shipped vhosts, ``deploy/apache/caldart.conf`` and
``deploy/nginx/caldart.conf``, each hold two hosts: one on port 80 that
answers certbot's challenges and redirects everything else to HTTPS, and one
on port 443 that terminates TLS and proxies to gunicorn.  The port-443 host
names the certificate files and certbot's TLS options file, and neither
server loads a configuration that names a file that does not exist.  So the
order is fixed, and the step follows it for whichever server the install record
names:

1. serve the challenge directory over plain HTTP with a small bootstrap host;
2. obtain the certificate with ``certbot certonly --webroot``;
3. have certbot's plugin write its options file;
4. replace the bootstrap host with the shipped vhost.

The first two are skipped once ``/etc/letsencrypt/live/HOST/fullchain.pem``
exists, so a second run never asks Let's Encrypt again.  The fourth runs every
time: the vhost is configuration, not data, and the step rewrites it from the
shipped file.  With ``--tls self-signed`` the first two become one ``openssl``
command (:ref:`deploy-self-signed`).  With certbot the step also installs the
renewal hook of :ref:`deploy-renewal-hsts`.  With ``--tls existing`` none of
the four runs: the step writes a snippet for the existing site's vhost instead
(:ref:`deploy-prefix`).

Use Apache or nginx, never both on the same host: the step leaves the other
server's configuration alone and refuses to run while both ``apache2`` and
``nginx`` are active.  The shipped files name ``caldart.example.org``, and the
step writes the real hostname in its place, drops the ``www.`` alias under
``--no-www``, and replaces ``/opt/caldart/caldart`` with the checkout and
``/opt/caldart`` with the deploy root, as the
commands below show by hand.  The hostname is also in ``ALLOWED_HOSTS``, and
its ``https://`` form in ``CSRF_TRUSTED_ORIGINS`` (step 5).  Its DNS ``A`` (and
``AAAA``) records must already point at this server, and ports 80 and 443 must
be open, or the certificate step fails.

Apache
------

The modules the vhost needs, which the step enables just before it installs
the vhost::

  sudo a2enmod proxy proxy_http headers ssl rewrite deflate expires http2

**The bootstrap host.**  Write a port-80 host that serves nothing but the
challenge directory, enable it, and check the syntax::

  sudo install -d /var/www/certbot
  sudo tee /etc/apache2/sites-available/caldart-acme.conf >/dev/null <<'EOF'
  <VirtualHost *:80>
      ServerName caldart.example.org
      ServerAlias www.caldart.example.org
      Alias /.well-known/acme-challenge/ /var/www/certbot/.well-known/acme-challenge/
      <Directory "/var/www/certbot/.well-known/acme-challenge">
          Require all granted
      </Directory>
  </VirtualHost>
  EOF
  sudo a2ensite caldart-acme
  sudo apachectl configtest
  sudo systemctl reload-or-restart apache2

**The certificate.**  certbot writes a token under ``/var/www/certbot``, the
certificate authority fetches it over port 80, and the certificate lands in
``/etc/letsencrypt/live/caldart.example.org/``::

  sudo certbot certonly --webroot -w /var/www/certbot \
       -d caldart.example.org -d www.caldart.example.org \
       --non-interactive --agree-tos -m ops@example.org

``--certbot-email`` supplies the address, and ``--certbot-staging`` adds
``--staging``.

**The TLS options file.**  The port-443 host includes
``/etc/letsencrypt/options-ssl-apache.conf``, certbot's recommended protocols
and ciphers.  ``python3-certbot-apache`` ships that file and copies it into
``/etc/letsencrypt/`` when its Apache plugin is prepared, which
``certonly --webroot`` never does.  Prepare it once, and check the file is
there::

  sudo certbot plugins --init --prepare --installers
  ls /etc/letsencrypt/options-ssl-apache.conf

**The vhost.**  Swap the bootstrap host for the shipped one with the hostname,
the checkout, the deploy root, and the gunicorn port written in, and check the
syntax before reloading::

  sudo a2dissite caldart-acme
  sudo rm /etc/apache2/sites-available/caldart-acme.conf
  sed -e "s#/opt/caldart/caldart#__CALDART_CHECKOUT__#g" -e "s#/opt/caldart#$ROOT#g" \
      -e "s#__CALDART_CHECKOUT__#$CHECKOUT#g" -e "s#127.0.0.1:8001#127.0.0.1:$PORT#g" \
      -e "s/caldart\.example\.org/$HOST/g" \
      deploy/apache/caldart.conf \
      | sudo install -m 0644 /dev/stdin /etc/apache2/sites-available/caldart.conf
  sudo a2ensite caldart
  sudo apachectl configtest
  sudo systemctl reload-or-restart apache2

``$CHECKOUT`` is the checkout, ``$ROOT`` the deploy root, ``$PORT`` the
gunicorn port, and ``$HOST`` the hostname.  The checkout goes through a stand-in
while the deploy root is written, so a checkout whose own path contains
``/opt/caldart`` is not rewritten twice.  The dry run of the
step prints the command with the real values.  ``reload-or-restart`` rather
than ``reload``, because it also starts a web server that is stopped, where a
plain reload fails.  Under ``--no-www`` a third
expression drops the ``ServerAlias`` line.

The vhost:

* keeps port 80 answering ``/.well-known/acme-challenge/`` from
  ``/var/www/certbot`` and redirects everything else to HTTPS with a 301;
* speaks HTTP/2 and HTTP/1.1 on port 443, with the certbot certificate and
  ``options-ssl-apache.conf``;
* proxies everything to gunicorn on ``http://127.0.0.1:$PORT/`` with
  ``ProxyPreserveHost On`` and a 60-second ``ProxyTimeout``, matching
  gunicorn's worker timeout;
* sets ``X-Forwarded-Proto: https`` and ``X-Forwarded-Port: 443`` and drops any
  inbound ``X-Forwarded-Ssl``.  ``X-Forwarded-Proto`` is what
  ``SECURE_PROXY_SSL_HEADER`` in ``prod.py`` reads, and gunicorn only accepts
  it from loopback, so a client cannot forge it;
* serves ``/media/`` from ``/opt/caldart/media/``, the deploy root's uploads
  (``MEDIA_ROOT``), as its own user: the site writes every upload ``0644`` and
  every directory under it ``0755`` (``FILE_UPLOAD_PERMISSIONS`` and
  ``FILE_UPLOAD_DIRECTORY_PERMISSIONS`` in ``base.py``), whatever umask it runs
  under, and the user step (which every install and upgrade runs) repairs any
  directory or file an earlier run left ``0750`` or ``0640``; with a one-week cache
  and ``X-Content-Type-Options: nosniff``, never runs a script from there, and
  excludes it from the proxy;
* denies ``/opt/caldart/media/documents``, the directory Wagtail writes
  document uploads to, with ``Require all denied``.  The deeper ``<Directory>``
  section is applied after the one above it, so it wins;
* sets **no** security headers of its own on proxied responses.  HSTS,
  ``X-Content-Type-Options``, ``Referrer-Policy``, and ``X-Frame-Options`` all
  come from ``prod.py``, where they are configurable per deployment.  A second
  copy from the vhost would both duplicate the header and override the
  settings.  ``/media/`` is the one exception, because Apache serves it without
  asking Django;
* caps request bodies at 25 MB, matching ``DATA_UPLOAD_MAX_MEMORY_SIZE``;
* compresses HTML, JSON, and the other text responses gunicorn returns;
* logs to ``/var/log/apache2/caldart-access.log`` and ``caldart-error.log``,
  and the port-80 host to ``caldart-http-access.log`` and
  ``caldart-http-error.log``.

nginx instead
-------------

The same four steps, with nginx's own file layout.

**The bootstrap host.**  Debian's stock ``default`` site also listens on
port 80; it can stay, because a request for the CalDART hostname matches the
``server_name`` below first::

  sudo install -d /var/www/certbot
  sudo tee /etc/nginx/sites-available/caldart-acme >/dev/null <<'EOF'
  server {
      listen 80;
      listen [::]:80;
      server_name caldart.example.org www.caldart.example.org;
      location /.well-known/acme-challenge/ {
          root /var/www/certbot;
      }
      location / {
          return 404;
      }
  }
  EOF
  sudo ln -sfn /etc/nginx/sites-available/caldart-acme /etc/nginx/sites-enabled/caldart-acme
  sudo nginx -t
  sudo systemctl reload-or-restart nginx

**The certificate.**  Exactly as for Apache::

  sudo certbot certonly --webroot -w /var/www/certbot \
       -d caldart.example.org -d www.caldart.example.org \
       --non-interactive --agree-tos -m ops@example.org

**The TLS options files.**  The port-443 server includes
``/etc/letsencrypt/options-ssl-nginx.conf`` and reads
``/etc/letsencrypt/ssl-dhparams.pem``.  ``python3-certbot-nginx`` ships the
first and writes both into ``/etc/letsencrypt/`` when its nginx plugin is
prepared, which ``certonly --webroot`` never does.  Prepare it once, and check
both files are there::

  sudo certbot plugins --init --prepare --installers
  ls /etc/letsencrypt/options-ssl-nginx.conf /etc/letsencrypt/ssl-dhparams.pem

**The vhost.**  Swap the bootstrap server for the shipped one::

  sudo rm /etc/nginx/sites-enabled/caldart-acme /etc/nginx/sites-available/caldart-acme
  sed -e "s#/opt/caldart/caldart#__CALDART_CHECKOUT__#g" -e "s#/opt/caldart#$ROOT#g" \
      -e "s#__CALDART_CHECKOUT__#$CHECKOUT#g" -e "s#127.0.0.1:8001#127.0.0.1:$PORT#g" \
      -e "s/caldart\.example\.org/$HOST/g" \
      deploy/nginx/caldart.conf \
      | sudo install -m 0644 /dev/stdin /etc/nginx/sites-available/caldart
  sudo ln -sfn /etc/nginx/sites-available/caldart /etc/nginx/sites-enabled/caldart
  sudo nginx -t
  sudo systemctl reload-or-restart nginx

The file turns HTTP/2 on with ``http2 on;``, a directive nginx has had since
1.25.1; Debian 13 ships 1.26.  Ubuntu 24.04 ships 1.24, where ``nginx -t``
stops on ``unknown directive "http2"``.  When ``nginx -v`` reports a version
older than 1.25.1, the step moves HTTP/2 onto the two ``listen 443`` lines
after writing the file and before ``nginx -t``::

  sudo sed -i -e '/^ *http2 *on;/d' \
      -e 's/listen\( *\)443 ssl;/listen\1443 ssl http2;/' \
      -e 's/listen\( *\)\[::\]:443 ssl;/listen\1[::]:443 ssl http2;/' \
      /etc/nginx/sites-available/caldart

The shipped file:

* keeps port 80 answering ``/.well-known/acme-challenge/`` from
  ``/var/www/certbot`` and redirects everything else to HTTPS with a 301;
* speaks HTTP/2 and HTTP/1.1 on port 443, IPv4 and IPv6, with the certbot
  certificate, ``options-ssl-nginx.conf``, and ``ssl-dhparams.pem``;
* proxies everything to gunicorn on ``http://127.0.0.1:$PORT`` over HTTP/1.1, passing
  ``Host``, ``X-Real-IP``, ``X-Forwarded-For``, ``X-Forwarded-Proto``,
  ``X-Forwarded-Host``, and ``X-Forwarded-Port``.  ``X-Forwarded-Proto`` is
  ``$scheme``, which is ``https`` on this server; gunicorn only accepts it
  from loopback, so a client cannot forge it.  ``$proxy_add_x_forwarded_for``
  appends the address nginx saw to whatever the client sent, which is why the
  auth throttles count the last entry (:doc:`configuration`);
* allows 10 seconds to connect and 60 seconds to send or read, matching
  gunicorn's worker timeout, and buffers the responses;
* serves ``/media/`` from ``/opt/caldart/media/``, the deploy root's uploads
  (``MEDIA_ROOT``), with a one-week
  cache, ``Cache-Control: public``, and ``X-Content-Type-Options: nosniff``,
  without directory listings or access logging;
* answers ``/media/documents/`` with ``return 404;``.  It is the longer prefix,
  so nginx matches it ahead of ``/media/``, and a document is only reachable
  through Django's members-only check;
* sets no security header on proxied responses.  nginx's ``add_header`` does
  not replace what the upstream sent, so a copy here would reach the browser
  alongside Django's;
* caps request bodies at 25 MB (``client_max_body_size 25m``) with a 60-second
  body timeout;
* logs to ``/var/log/nginx/caldart-access.log`` and ``caldart-error.log``,
  and the port-80 server to ``caldart-http-access.log`` and
  ``caldart-http-error.log``.

The file leaves compression to the ``http`` block of ``/etc/nginx/nginx.conf``,
where Debian's stock configuration already turns ``gzip`` on for HTML; its
header comment lists the lines that extend it to JSON, CSS, and JavaScript.

.. _deploy-self-signed:

Self-signed instead
-------------------

With ``--tls self-signed`` there is no bootstrap host and no request to Let's
Encrypt.  The certificate is made once, for each name the site answers for,
and kept for ten years::

  sudo install -d -m 0750 -o root -g root /etc/caldart/tls
  sudo openssl req -x509 -newkey rsa:2048 -nodes -days 3650 \
      -subj /CN=caldart.example.org \
      -addext subjectAltName=DNS:caldart.example.org,DNS:www.caldart.example.org \
      -keyout /etc/caldart/tls/privkey.pem -out /etc/caldart/tls/fullchain.pem
  sudo chmod 0640 /etc/caldart/tls/privkey.pem

The TLS options step still runs, since the vhost includes certbot's options
file in both modes, and the vhost is written with its two certificate paths
pointing at ``/etc/caldart/tls/``.  To move to a real certificate later, run
``sudo deploy/install.sh --tls certbot --certbot-email ADDRESS`` once the
hostname's DNS points at the box: the record changes and step 9 requests one.
Remove ``SECURE_HSTS_SECONDS=0`` from the environment file afterwards to turn
HSTS on.

.. _deploy-renewal-hsts:

Renewal and HSTS
----------------

certbot's own systemd timer renews the certificate twice a day when it is
within 30 days of expiry, over the same webroot, which the port-80 host keeps
reachable.  Rehearse a renewal with::

  sudo certbot renew --dry-run

The certificate files are replaced in place, but the web server reads them
only at start-up, so it has to be reloaded after a renewal.  certbot runs every
script in ``/etc/letsencrypt/renewal-hooks/deploy/`` after a successful
renewal, and with certbot the step installs this one, naming the web server the
install record holds (``nginx`` with ``--web-server nginx``)::

  sudo tee /etc/letsencrypt/renewal-hooks/deploy/reload-web-server >/dev/null <<'EOF'
  #!/bin/sh
  systemctl reload-or-restart apache2
  EOF
  sudo chmod 0755 /etc/letsencrypt/renewal-hooks/deploy/reload-web-server

``SECURE_HSTS_SECONDS`` in ``/etc/caldart/caldart.env`` is the whole HSTS
switch: neither vhost sets a ``Strict-Transport-Security`` header of its own.
With certbot the installer leaves the template's one-year default in place,
because it confirms HTTPS answers before it finishes (:ref:`deploy-check`); with a
self-signed certificate it writes ``0``.  To be more cautious on a new
hostname, set ``0`` and restart ``caldart-web`` until HTTPS is known good.
Browsers honor the header for its full duration and there is no way to take it
back early.  ``SECURE_HSTS_PRELOAD`` stays off unless you mean to join the
browser preload list; :doc:`configuration` explains what that commits the site
to.


.. _deploy-prefix:

Under a URL prefix, behind an existing site
-------------------------------------------

A machine that already serves a site over HTTPS, such as
``https://paloaltodart.org/``, can serve CalDART under a path of it, such as
``https://paloaltodart.org/caldart-proto/``, without touching the rest of that
site.  One command installs it::

  curl -fsSL https://raw.githubusercontent.com/astrocfi/caldart-proto/main/deploy/bootstrap.sh \
      | sudo bash -s -- --hostname paloaltodart.org --url-prefix /caldart-proto \
          --tls existing --attach-to /etc/apache2/sites-available/paloaltodart.conf \
          --email local --admin-email you@example.org

``--attach-to`` names the file that holds the site's ``<VirtualHost *:443>``
block; on a site set up with certbot's Apache plugin that is
``<name>-le-ssl.conf`` (here ``paloaltodart-le-ssl.conf``), since certbot
leaves only the plain-HTTP redirect in ``<name>.conf``.

``--tls existing`` says a web server on this machine already serves the
hostname over HTTPS.  The installer then obtains no certificate, installs no
certbot package, and writes no vhost of its own: the existing site's
certificate is the one browsers see, and the hop from its web server to
gunicorn stays on loopback.  ``--url-prefix`` is the path, written as the
settings read ``URL_PREFIX``: one leading and one trailing slash are optional,
and each segment is letters, digits, ``.``, ``_``, ``~``, or ``-``.  Without
it the site takes the whole of the existing host; on nginx that snippet holds
``location ^~ /``, so the existing server block must have no ``location /`` of
its own, or ``nginx -t`` refuses the pair and the step puts the vhost back.  ``--email local`` sends
mail through the postfix the machine already runs (:ref:`email-local-postfix`).

**The snippet.**  Step 9 writes one file for the web server the record names,
with the prefix and the deploy root written in:

- Apache: ``deploy/apache/caldart-attach.conf`` to
  ``/etc/apache2/conf-available/caldart.conf``, after ``a2enmod proxy
  proxy_http headers expires``.  It is not enabled with ``a2enconf``, which
  would load it for every host.
- nginx: ``deploy/nginx/caldart-attach.conf`` to
  ``/etc/nginx/snippets/caldart.conf``, and the ``caldart_app`` upstream it
  proxies to, ``deploy/nginx/caldart-upstream.conf``, to
  ``/etc/nginx/conf.d/caldart-upstream.conf``, which ``nginx.conf`` loads once
  into its ``http`` block: a snippet included in two server blocks must not
  define the upstream twice.

For the prefix ``/caldart-proto`` the snippet redirects ``/caldart-proto`` to
``/caldart-proto/``; refuses ``/caldart-proto/media/documents/`` (a document
may belong to the members-only collection, and Django's document view is what
checks that); serves ``/caldart-proto/media/`` off disk with the same headers
as the full vhost; and proxies everything else under ``/caldart-proto/`` to
gunicorn on ``127.0.0.1`` at the gunicorn port, 8001 unless ``--gunicorn-port``
says otherwise, with the ``Host`` header preserved,
``X-Forwarded-Proto: https``, ``X-Forwarded-Port: 443``, and any inbound
``X-Forwarded-Ssl`` or ``X-Forwarded-Protocol`` dropped (gunicorn reads both as
the scheme too).  The proxy strips the prefix, and Django puts it
back on every URL it writes, because ``URL_PREFIX`` sets ``FORCE_SCRIPT_NAME``
(:doc:`configuration`).  The nginx snippet uses ``^~`` locations, so a
regular-expression location of the existing site (``location ~ \.php$``, say)
never takes a request under the prefix.  Static files need nothing: whitenoise
serves them under the prefix through the proxy.

**The include line.**  The existing site's vhost pulls the snippet in with one
line inside its HTTPS block::

  Include conf-available/caldart.conf     # Apache, inside <VirtualHost *:443>
  include snippets/caldart.conf;          # nginx, inside the listen 443 ssl server

``--attach-to FILE`` names the file that holds that block, and it must already
exist: a real run that cannot find it stops without touching anything, and a
dry run only notes that it would have inserted the line, since there is
nothing there yet to back up or edit.  The step inserts
the line before the closing ``</VirtualHost>`` or ``}`` of every block in the
file that terminates TLS, or of every block when none does, indented one
level deeper than the closing line.  An Apache block terminates TLS when its
``<VirtualHost>`` line names port 443 or it holds ``SSLEngine on`` or an
``SSLCertificateFile``; an nginx block, when a ``listen`` names port 443 or
``ssl``, or it holds an ``ssl_certificate``.  The plain-HTTP block that
redirects to HTTPS never gets the line: the snippet tells Django every request
arrived over HTTPS, so a plain-HTTP request proxied from there would pass for a
secure one.  It keeps the file as it was before the first insertion at
``FILE.caldart.bak``, leaves a file that already carries the line alone, and
edits the file a symbolic link points at rather than replacing the link.  Then
it runs ``apachectl configtest`` or ``nginx -t`` and ``systemctl
reload-or-restart``.  When the check fails, the step takes the line it inserted
back out, so the existing site's vhost is as it was before the run and still
passes its check, and stops saying so.  Without ``--attach-to`` it writes the snippet, prints the
line and where it goes, and reloads; the checks then fail, since the site does
not answer under the prefix until the line is in place, and a second run of
``sudo deploy/steps/check.sh`` passes once it is.

**What changes for the operator.**  The environment file carries
``SITE_URL=https://paloaltodart.org/caldart-proto`` and
``URL_PREFIX=/caldart-proto``; ``ALLOWED_HOSTS`` and ``CSRF_TRUSTED_ORIGINS``
name the host alone, as always.  The public site is at ``/caldart-proto/``, the
portal at ``/caldart-proto/portal/``, the Wagtail admin at
``/caldart-proto/admin/``, and the user guide at ``/caldart-proto/docs/``.
Every link in an email is built on ``SITE_URL``, so it carries the prefix too.
The session and CSRF cookies keep the path ``/``, so one host serves one
CalDART.  The install leaves the environment file alone once it exists, so a
later ``--url-prefix`` that differs from its ``URL_PREFIX`` is refused, naming
the file, until ``URL_PREFIX`` and the path of ``SITE_URL`` there are changed
to match.  An earlier CalDART vhost for the hostname, from a certbot or
self-signed install, is disabled and removed, since the existing site answers
for the hostname.

"Don't need SSL" means the installer need not obtain a certificate, not that
the site runs over plain HTTP: ``caldart.settings.prod`` keeps secure cookies
and the redirect to HTTPS, so a site the browser reaches over plain HTTP is not
a deployment this project supports.


10. Renewal reminders (``steps/timers.sh``)
===========================================

Steps 10 to 14, and the backup timer of step 15, are one script:
``steps/timers.sh`` copies the six service and timer pairs into
``/etc/systemd/system`` with ``/opt/caldart/caldart`` replaced by the checkout
and ``/opt/caldart`` by the deploy root, runs
``systemctl daemon-reload`` once, enables and starts every timer, and starts
the first registry import.  Each section shows the commands for its own pair.
Reinstalling the units is how an upgrade picks up a changed one.

::

  sudo install -m 0644 deploy/systemd/caldart-reminders.service \
      deploy/systemd/caldart-reminders.timer /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable --now caldart-reminders.timer
  systemctl list-timers caldart-reminders.timer

Daily at 07:00, with catch-up if the machine was off.  See :doc:`reminders` for
the kinds, the templates and how to change the cadence.

.. _deploy-renewals:

11. Automatic renewals (``steps/timers.sh``)
============================================

::

  sudo install -m 0644 deploy/systemd/caldart-renewals.service \
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

12. Scheduled reports (``steps/timers.sh``)
===========================================

::

  sudo install -m 0644 deploy/systemd/caldart-reports.service \
      deploy/systemd/caldart-reports.timer /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable --now caldart-reports.timer
  systemctl list-timers caldart-reports.timer

Daily at 06:00, with catch-up if the machine was off: whatever was due is still
due, and the next run sends it.  It sends the report subscriptions that are due
and each DART's monthly roster; it needs the database and the SMTP server, from
the same ``/etc/caldart/caldart.env``.  Rehearse the first of next month with
``sudo deploy/manage.sh send_scheduled_reports --dry-run --today <YYYY-MM-01>``.  See
:doc:`scheduled-reports` for what it sends, and when.


.. _deploy-statements:

13. Year-end statements (``steps/timers.sh``)
=============================================

::

  sudo install -m 0644 deploy/systemd/caldart-statements.service \
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
``sudo deploy/manage.sh send_year_statements --dry-run --today <YYYY-01-15>``.  See
:doc:`statements` for who is sent one, and when.


.. _deploy-registry:

14. The FAA registry (``steps/timers.sh``)
==========================================

::

  sudo install -m 0644 deploy/systemd/caldart-registry.service \
      deploy/systemd/caldart-registry.timer /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable --now caldart-registry.timer
  sudo systemctl start --no-block caldart-registry.service
  systemctl list-timers caldart-registry.timer

Daily at 04:30, with catch-up if the machine was off: every run replaces the
registry with the FAA's current copy, so a late one costs nothing.  It downloads
the FAA's Releasable Aircraft Database (about 70 MB) from ``FAA_REGISTRY_URL``
into the unit's private ``/tmp`` and imports the aircraft types and the
registrations, which takes well under a minute once the file is down; it needs
the database and an outbound HTTPS connection to ``registry.faa.gov``.  The
``systemctl start`` above runs the first import straight away, so the aircraft
type picker has its vocabulary before anybody opens it.  A system administrator
can also start an import from the Health & Database page (**Run now** on the
*Aircraft database* panel); that import runs as a child of ``caldart-web``, so
restarting the web service while one is under way stops it, and the next press
after ``REGISTRY_IMPORT_STALE_MINUTES`` records it as *Did not finish.* and
starts another.  See :doc:`aircraft-registry` for what the import reads and
writes.


15. Backups (``steps/timers.sh``, ``steps/backup.sh``)
======================================================

The backup timer is installed with the other scheduled jobs::

  sudo install -m 0644 deploy/systemd/caldart-backup.service \
      deploy/systemd/caldart-backup.timer /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable --now caldart-backup.timer
  systemctl list-timers caldart-backup.timer

Daily at 03:30, with catch-up if the machine was off.  Each run writes a dump
to ``BACKUP_DIR`` and deletes the generated dumps older than
``BACKUP_RETENTION_DAYS`` (30 in the environment file the installer writes).
Then ``steps/backup.sh`` takes one straight away, so a fresh install has a dump
before anything else happens::

  sudo deploy/manage.sh db_backup

:doc:`backup-restore` covers the commands, the timer, retention, copying dumps
off the machine, and restoring.


.. _deploy-check:

Checking it worked (``steps/check.sh``)
=======================================

The last step checks what the others built, and fails naming every check that
missed.  For a site at the root of its host it runs::

  systemctl is-active caldart-web.service caldart-backup.timer \
      caldart-registry.timer caldart-reports.timer caldart-renewals.timer \
      caldart-reminders.timer caldart-statements.timer
  sudo deploy/compose.sh ps --format '{{.Health}}' db     # healthy
  curl -sI -H 'Host: caldart.example.org' -H 'X-Forwarded-Proto: https' \
      http://127.0.0.1:$PORT/
  curl -sk --resolve caldart.example.org:443:127.0.0.1 https://caldart.example.org/
  curl -sk --resolve caldart.example.org:443:127.0.0.1 \
      https://caldart.example.org/portal/login
  sudo deploy/manage.sh health --json

``$PORT`` is the gunicorn port, 8001 unless ``--gunicorn-port`` says
otherwise, and the first ``curl`` asks gunicorn itself with the request step 8
waits on; a miss is ``gunicorn did not answer 200 on 127.0.0.1:PORT``.  The
database check reaches the container through ``CALDART_DB_PORT`` from the
record, as ``deploy/compose.sh`` does, and its failure names the port:
``the compose db service on 127.0.0.1:PORT is not healthy``.

The two ``curl`` requests through the web server must answer ``200``, and so
must a third: the portal
script the sign-in page names (the ``src`` of its ``<script>`` under
``/static/``), which proves the static files resolve.  Under a URL prefix
every path carries it: ``https://HOST/caldart-proto/``,
``/caldart-proto/portal/login``, and the script under
``/caldart-proto/static/``.  ``--resolve`` sends the requests to this
machine whatever the DNS says, which holds behind an existing site too, since
that site's web server is on this machine; ``-k`` accepts a self-signed
certificate.
With gunicorn answering on its port and the site answering through the web
server, the vhost proxies to the right port.  The ``health`` command prints the
same report as ``GET /system/health`` and the health panel of
``/portal/system/health``, and depends on neither port: it reaches the database
through ``DATABASE_URL``, which step 5 wrote with the recorded database port.  It
reports database connectivity, pending
migrations, free space on the backup filesystem, the last backup, the version
from ``pyproject.toml``, and whether ``DEBUG`` is on.  The step requires
``debug`` to be ``false`` and ``pending_migrations`` to be ``0``.  Then it
prints the summary described under :ref:`deploy-install-scripts`.

Then, in a browser: the public site loads and is styled, ``/portal/`` signs you
in, ``/admin/`` opens Wagtail, every check on the health panel of
``/portal/system/health`` is green, and the **User guide** link at the foot of the
portal's menu opens the user guide.


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
Nightly backups              ``journalctl -u caldart-backup -n 20``
FAA registry imports         ``journalctl -u caldart-registry -n 50``; an
                             import started with **Run now** logs to
                             ``journalctl -u caldart-web``
Apache :443 access / error   ``/var/log/apache2/caldart-{access,error}.log``
Apache :80 access / error    ``/var/log/apache2/caldart-http-{access,error}.log``
                             — the redirect vhost, and therefore where a
                             failing ACME challenge shows up
nginx access / error         ``/var/log/nginx/caldart-{access,error}.log``
Postgres                     ``sudo deploy/compose.sh logs -f db``
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
  journalctl -u caldart-web | grep 'action=system.registry_import'

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
``member.delete``             ``payments``, ``owner`` -- when the member had
                              paid, how many payments moved and the
                              tombstone account that holds them; from the
                              API and from the Wagtail users admin
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
                              member turned it off themselves; ``reason``
                              ``member.delete`` when the member's account
                              is being deleted
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
``system.registry_import``    -- (the target is the ``RegistryImport`` row);
                              one line per **Run now** on Health & Database
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
``system_admin_target``, ``inactive_account``, ``no_such_backup``, or ``import_running`` (a **Run now** pressed while an
import is under way).

A record carries ids, counts, flags, and slugs and nothing else.  Email
addresses, names, passwords, tokens, and database contents are not values the
helper accepts, so a line can never carry them; reading it back therefore means
looking the ids up.  A richer trail, held in the database and readable from the
portal, is the ``AuditEntry`` model in :doc:`roadmap`.


.. _deploy-rehearsal:

Rehearsing an install
=====================

``make rehearse-deploy``, run on a development machine with Docker, puts these
scripts through a whole life on a throwaway Ubuntu 24.04 container running
systemd: ``bootstrap.sh`` with ``--tls self-signed``, an ``upgrade.sh`` with
nothing to pull, ``install.sh`` again with no flags, and ``uninstall.sh --yes
--purge``, with Apache by default or nginx with
``REHEARSE_WEB_SERVER=nginx``.  ``REHEARSE_URL_PREFIX=/caldart-proto``
rehearses :ref:`deploy-prefix` instead, behind a stand-in for the existing
site; ``REHEARSE_GUNICORN_PORT=8101`` installs with ``--gunicorn-port
8101``, ``REHEARSE_DB_PORT=5433`` with ``--db-port 5433``, and
``REHEARSE_SEED=content``, ``demo``, or ``all`` with ``--seed-content``,
``--seed-demo``, or both.  After the install it checks the layout of
:ref:`deploy-layout`, and with a moved port it checks the port after the
install, after the upgrade, and after the second install.  It is the way to try
a change to anything under ``deploy/`` before a server sees it;
:ref:`testing-rehearsal` describes what it runs and how the container is set
up.


Upgrading
=========

::

  sudo deploy/upgrade.sh                 # pull the current branch
  sudo deploy/upgrade.sh --ref v1.4      # or check out a branch, tag, or commit

``upgrade.sh`` runs, in order:

1. a backup, ``sudo deploy/manage.sh db_backup``, always first, unless a
   plain upgrade finds the checkout on a detached ``HEAD`` (as a rollback with
   ``--ref`` leaves it), where it stops before anything runs and asks for
   ``--ref <branch>``;
2. a refusal if ``git status --porcelain`` shows local changes in the checkout;
3. ``git pull --ff-only``, or with ``--ref`` a ``git fetch origin`` and ``git
   checkout REF`` (then ``git pull --ff-only`` when the ref is a branch);
4. step 2, the service user and its directories (``steps/user.sh``), which also
   makes every upload readable by the web server again;
5. step 6, the build (``steps/build.sh``);
6. step 7's database commands (``steps/database.sh``): ``migrate``,
   ``createcachetable``, ``seed_roles``, ``seed_plans``, and ``collectstatic``, with no
   administrator and no example content;
7. step 8 (``steps/web-service.sh``), which reinstalls the web unit and
   restarts it, then waits for gunicorn to answer;
8. ``steps/timers.sh``, which reinstalls the job units and reloads systemd;
9. the checks (``steps/check.sh``).

Each step runs as the freshly checked-out script, so an upgrade that changes
the installer runs the changed one.  Order matters: the frontend is built
before ``collectstatic``, and the web unit restarts after both.  The guide is
rebuilt in the same sequence, so the copy at ``/docs/`` is always the one the
running code describes; Django reads it off disk on every request, so it needs
no restart of its own.  ``createcachetable`` is idempotent, and it is in the
list so that no upgrade can leave a box without ``caldart_cache``.
``preload_app`` is on, so a restart, and not a reload, is what picks up new
code.  The timers start a fresh process on every run, so they pick up the new
code by themselves; reinstalling their units carries any change to a unit file.

An upgrade never touches the environment file, the vhost, or the snippet.  It
keeps the recorded gunicorn and Postgres ports: each step it runs reads the
install record, so gunicorn restarts on the recorded ``CALDART_GUNICORN_PORT``,
the readiness check asks it there, and every ``docker compose`` command runs
with the recorded ``CALDART_DB_PORT`` exported.  It takes no
``--gunicorn-port`` or ``--db-port``; either is a usage error naming
``install.sh``, whose ``--gunicorn-port`` and ``--db-port`` are the way to move
a port (:ref:`deploy-sharing`).  A change to the environment file is made by
hand (``sudoedit`` and a restart), or, for the vhost
or the snippet, by running ``sudo deploy/steps/web-server.sh``, which rewrites
it from the shipped file.

Rolling back is ``sudo deploy/upgrade.sh --ref <the previous commit>``, plus,
when the schema the previous commit expects differs from the one applied,
a ``sudo deploy/manage.sh db_restore`` of the dump the upgrade took first.
The rollback leaves the checkout on a detached ``HEAD``, so the next upgrade
names the branch again (``--ref main``).  The restore stays a command run by hand, because it drops the database
(:doc:`backup-restore`).


Moving to the current layout
----------------------------

An install whose checkout is the deploy root itself, ``/opt/caldart``, with the
dumps in ``/opt/caldart/backups`` and the uploads in
``/opt/caldart/backend/media`` inside it, is moved by reinstalling; no script
moves it.  Do it before any upgrade: sourcing ``deploy/lib.sh`` stops when the
install record's ``CALDART_ROOT`` is the checkout itself, so ``install.sh``,
``upgrade.sh``, and every step refuse such an install, naming this section of
the runbook, and ``bootstrap.sh`` refuses a deploy root that is a checkout.
``uninstall.sh``, ``manage.sh``, and ``compose.sh`` set
``CALDART_ANY_LAYOUT=1`` and still run, so the backup and the purge below work.
With the same flags the first install was given:

1. take a backup: ``sudo /opt/caldart/deploy/manage.sh db_backup``;
2. copy the dumps and the uploads aside::

     sudo cp -a /opt/caldart/backups /root/caldart-backups
     sudo cp -a /opt/caldart/backend/media /root/caldart-media

3. ``sudo /opt/caldart/deploy/uninstall.sh --yes --purge``, which removes
   the checkout ``/opt/caldart`` and the database, and nothing else under
   ``/opt``;
4. run ``bootstrap.sh`` with the same flags, which clones into
   ``/opt/caldart/caldart`` and installs an empty site;
5. put the dumps and the uploads back beside the checkout::

     sudo cp -a /root/caldart-backups/. /opt/caldart/backups/
     sudo cp -a /root/caldart-media/. /opt/caldart/media/
     sudo chown -R caldart:caldart /opt/caldart/backups /opt/caldart/media

6. restore the dump from step 1 (:doc:`backup-restore`):
   ``sudo /opt/caldart/caldart/deploy/manage.sh db_restore
   /opt/caldart/backups/<the dump> --yes``.


Uninstalling
============

::

  sudo deploy/uninstall.sh --yes              # the services, the units, the vhost
  sudo deploy/uninstall.sh --yes --purge      # ... and every piece of data

``uninstall.sh`` refuses to run without ``--yes``.  It stops and disables
``caldart-web`` and the six timers, removes their unit files and reloads
systemd, removes the vhost and any bootstrap host from the web server the
install record names, and, behind an existing site, the snippet (and nginx's
upstream file) and the include line, then reloads that server and removes the
certbot renewal hook.  The include line comes out of the file ``--attach-to``
named, or, when none was recorded, out of every file under the server's
``sites-available`` that carries it; the rest of the existing site's vhost is
left as it is, and so is ``FILE.caldart.bak``.  ``--purge`` also removes ``/etc/caldart`` (the environment file, the
install record, and a self-signed certificate), runs ``docker compose down
-v`` from the checkout, which deletes the ``caldart_pgdata`` volume and every
row in it, and removes what the install made in the deploy root: the checkout,
the dumps in ``backups``, and the uploads in ``media``, as its stage line says.
It then runs ``rmdir`` on the deploy root, and only when nothing else is in it,
so a checkout cloned into a directory that holds more (``/home/admin`` or
``/srv``) never takes that directory with it; the purge says it kept the root.
When the record's ``CALDART_ROOT`` is the checkout itself, the purge removes
the checkout alone.  Without ``--purge`` all three stay.  Copy off what you want to keep first.  Each removal prints what it removed, and anything
already absent is skipped.  Certificates under ``/etc/letsencrypt`` and the
operating system packages stay in both modes.


.. _deploy-troubleshooting:

Troubleshooting
===============

**Port 5432 is already in use.**  The Postgres step found something listening
on the port before it created CalDART's container, most often a Postgres
installed from the distribution or run by another project in Docker.  Run the
installer again with a free port, ``sudo deploy/install.sh --db-port 5433``;
the record keeps it for every later run (:ref:`deploy-sharing`).

**The site does not answer under its prefix.**  ``check.sh`` reports
``https://HOST/caldart-proto/`` answering ``404`` (or the existing site's own
page): the existing vhost does not include the snippet.  Add the line
:ref:`deploy-prefix` shows inside its HTTPS block, or run the installer again
with ``--attach-to``, then ``sudo deploy/steps/check.sh``.

**Port 8001 is already in use.**  The gunicorn step found something listening
on the gunicorn port before it installed ``caldart-web.service``, such as
another application server.  Run the installer again with a free port, ``sudo
deploy/install.sh --gunicorn-port 8101``; the record keeps it for every later
run (:ref:`deploy-sharing`).

**502 from Apache.**  gunicorn is not running or not on the port the vhost
proxies to: the gunicorn port, 8001 unless ``--gunicorn-port`` says otherwise.
``CALDART_GUNICORN_PORT`` in ``/etc/caldart/caldart.env`` and the address in the
vhost must name the same port; ``sudo deploy/install.sh`` writes both from the
record.  ``systemctl
status caldart-web``, then ``journalctl -u caldart-web -n 50``; once the cause
is fixed, ``sudo deploy/steps/web-service.sh`` restarts it and waits for it to
answer.

``caldart-web`` **fails with** ``status=226/NAMESPACE``.  A directory named in
``ReadWritePaths`` does not exist.  ``sudo deploy/steps/user.sh`` creates the
deploy root's ``backups`` and ``media`` and the checkout's
``backend/staticfiles``, owned by ``caldart``; then ``sudo deploy/steps/web-service.sh`` starts the unit again.

``bootstrap.sh`` **says** ``/opt/caldart/caldart`` **exists and is not a
checkout.**  Something created the checkout's directory before the clone
(:ref:`step 3 <deploy-checkout>`).  Move it aside and run ``bootstrap.sh``
again; the rest of the deploy root can stay.

``apachectl configtest`` **or** ``nginx -t`` **says a certificate or**
``options-ssl`` **file does not exist.**  The shipped vhost went in before its
files did.  Disable the shipped vhost and run ``sudo deploy/steps/web-server.sh``,
which puts the bootstrap host back while the certificate is missing and runs
the certificate and options-file steps of :ref:`step 9 <deploy-web-server>` in
order.

**certbot says the challenge failed, or reports a 404.**  The hostname's DNS
does not point at this server, port 80 is closed, or the bootstrap host is not
the one answering.  ``curl -I http://caldart.example.org/.well-known/acme-challenge/x``
from another machine should reach this server and answer 404 from the
bootstrap host; the port-80 error log names the path it looked for.  Once the
DNS or the firewall is fixed, run ``sudo deploy/steps/web-server.sh`` again;
Let's Encrypt limits failed attempts per hour, so check the ``curl`` first.

``DisallowedHost`` **in the log.**  The hostname is missing from
``ALLOWED_HOSTS``.  Add it with ``sudoedit /etc/caldart/caldart.env`` and
restart ``caldart-web``.

**The install stops at a step.**  Every step is idempotent: fix what its
error names and run ``sudo deploy/install.sh`` again, with no flags once the
install record exists, or run that step alone as
``sudo deploy/steps/<step>.sh``.  ``--dry-run`` shows what a run would do.

**The checks fail.**  ``steps/check.sh`` names each check that missed.  Run it
alone as ``sudo deploy/steps/check.sh`` after fixing the cause.

**CSRF failures when signing in.**  ``CSRF_TRUSTED_ORIGINS`` must list the
``https://`` origin, and the proxy must set ``X-Forwarded-Proto``.  Both are in
this document; check the vhost was actually reloaded.

**Unstyled pages, or** ``Manifest file not found``.  ``npm run build`` did not
run, or ``collectstatic`` did not.  Run ``sudo deploy/steps/build.sh``, then
``sudo deploy/steps/database.sh``, then ``sudo deploy/steps/web-service.sh``.

``/docs/`` **answers 404 and the journal says the user guide has not been
built.**  The Sphinx step of :ref:`the build <deploy-build>` did not run, or
``USER_GUIDE_ROOT`` names a directory with no ``index.html``.  Run
``sudo deploy/steps/build.sh``, or point the variable at the directory it
wrote to.

``ValueError: Missing staticfiles manifest entry``.  ``collectstatic`` ran
before the frontend build.  Run ``sudo deploy/steps/build.sh``, then
``sudo deploy/steps/database.sh``, then ``sudo deploy/steps/web-service.sh``.

**Backups fail with a permission error.**  ``BACKUP_DIR`` is outside the
``ReadWritePaths`` in ``caldart-web.service`` and ``caldart-backup.service``, or
is not owned by ``caldart``; ``sudo deploy/steps/user.sh`` restores the
ownership of the deploy root's ``backups``.

**Redirect loop.**  ``SECURE_SSL_REDIRECT`` is on but the proxy is not sending
``X-Forwarded-Proto: https``, so Django redirects a request it thinks is plain
HTTP, forever.  Fix the header rather than turning the redirect off.

**No email.**  Check ``EMAIL_URL`` and try ``sudo deploy/manage.sh
send_renewal_reminders --dry-run``; then send one for real and read
``journalctl -u caldart-web``.  Many providers need
``smtp+tls://`` on port 587 with an app password rather than the account one.
See :doc:`email` for reading the email log's error column and checking the
domain's SPF, DKIM, and DMARC records.
