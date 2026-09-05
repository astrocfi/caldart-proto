=============
Configuration
=============

Every runtime setting comes from the environment.  ``.env.example`` at the
repository root is the reference copy with working development defaults;
``make setup`` copies it to ``.env`` if you do not have one, and a production
box keeps the same variables in ``/etc/caldart/caldart.env``, read by the
systemd units.

Specified in PLAN §14.


Where settings are read
=======================

``backend/caldart/settings/`` has four modules:

``base.py``
   Reads every variable listed below with ``django-environ``, and calls
   ``environ.Env.read_env(REPO_ROOT / ".env")`` so a bare checkout runs with no
   exported variables at all.  Everything else imports from here.

``dev.py``
   ``DEBUG`` on, ``ALLOWED_HOSTS=["*"]``, unhashed static storage.  The default:
   ``manage.py`` and ``wsgi.py`` both set
   ``DJANGO_SETTINGS_MODULE=caldart.settings.dev`` when nothing else is set.

``prod.py``
   ``DEBUG`` off, TLS and cookie hardening, hashed static manifest, logging to
   stdout, persistent database connections.  Four variables have **no default**
   here and a missing one is a start-up error: ``SECRET_KEY``,
   ``ALLOWED_HOSTS``, ``SITE_URL`` and ``EMAIL_URL``.  Selected by
   ``Environment=DJANGO_SETTINGS_MODULE=caldart.settings.prod`` in both systemd
   units.

``test.py``
   ``DEBUG`` off, MD5 password hashing, in-memory email and file storage, mock
   payments on.  Selected by ``pytest.ini_options`` in ``pyproject.toml``; you
   never set it by hand.

Values are read once, at import.  Changing the environment file means
restarting the service.


Core
====

``DATABASE_URL``
   Postgres connection URL, parsed by ``django-environ``.  The database is
   created by ``make up`` if it does not exist.

   :Development: ``postgres://caldart:caldart@localhost:5432/caldart``
   :Parallel branches: ``…/caldart_<branch-slug>``, so simultaneous test runs
      never collide.  Django names the test database
      ``test_caldart_<branch-slug>``.
   :Production: the same shape with a real password, pointing at the Docker
      container on ``localhost:5432``.

``SECRET_KEY``
   Django's signing key: sessions, password-reset tokens, CSRF.  Changing it
   logs everyone out and invalidates outstanding reset links.

   :Development: the checked-in ``dev-insecure-secret-key-change-me``.
   :Production: **required**, 50+ random characters, unique per deployment.
      ``python3 -c "import secrets; print(secrets.token_urlsafe(64))"``.

``DEBUG``
   Django's debug mode: tracebacks in the browser, no template caching.

   :Development: ``true``
   :Production: ``false``.  ``prod.py`` forces it off regardless, and
      ``/system/health`` reports it so a mistake is visible.

``ALLOWED_HOSTS``
   Comma-separated hostnames Django will answer for.  A request with any other
   ``Host`` header gets a ``DisallowedHost`` error.

   :Development: ``localhost,127.0.0.1,[::1]`` — ``dev.py`` widens this to
      ``*`` so a phone on the LAN can reach the dev server.
   :Production: **required**; every hostname the vhost serves, including the
      ``www.`` form.

``CSRF_TRUSTED_ORIGINS``
   Comma-separated origins, *with scheme*, allowed to post to the site.
   Needed behind TLS termination.

   :Development: defaults to ``[SITE_URL]``.
   :Production: ``https://caldart.example.org,https://www.caldart.example.org``.

``SITE_URL``
   The public base URL.  Used for links in emails — including the renewal
   reminders' ``/portal/renew`` link — and as ``WAGTAILADMIN_BASE_URL``.

   :Development: ``http://localhost:8000``
   :Production: **required**, ``https://caldart.example.org``, no trailing
      slash.


Email
=====

``EMAIL_URL``
   SMTP connection URL.  ``smtp://`` plain, ``smtp+tls://`` for STARTTLS,
   ``smtp+ssl://`` for implicit TLS.  Credentials are URL-encoded, so an ``@``
   in the username becomes ``%40``.

   :Development: ``smtp://localhost:1025`` — Mailpit, whose web UI at
      http://localhost:8025 catches everything and delivers nothing.
   :Production: **required**,
      ``smtp+tls://user:password@smtp.example.org:587``.  Many providers want
      an app password rather than the account password.

``DEFAULT_FROM_EMAIL``
   The ``From`` on every message, and ``SERVER_EMAIL`` for error mail.

   :Both: ``CalDART <noreply@caldart.example.org>``.  In production it must be
      a domain the SMTP relay is allowed to send as, or SPF and DMARC will
      bounce it.

``EMAIL_TIMEOUT`` *(prod only)*
   Seconds to wait on the SMTP server.  Default ``20``.  Keeps a wedged relay
   from hanging a request.

``ADMIN_EMAILS`` *(prod only)*
   Comma-separated addresses that receive unhandled-500 mail.  Default empty,
   which is fine — the traceback is in the journal either way.


Payments
========

Covered in full, with test cards and account setup, in :doc:`payments-setup`.

``STRIPE_PUBLISHABLE_KEY``, ``STRIPE_SECRET_KEY``
   The Stripe API key pair.  Blank hides Stripe from the checkout provider
   list, which is what lets the prototype run with no Stripe account at all.

   :Development: blank, or ``pk_test_…`` / ``sk_test_…``.
   :Production: the live pair, ``pk_live_…`` / ``sk_live_…``.

``STRIPE_WEBHOOK_SECRET``
   ``whsec_…``, used to verify the signature on
   ``POST /payments/stripe/webhook``.  Without it the webhook rejects
   everything, which is the safe failure.

``STRIPE_APPLE_PAY_DOMAIN_ASSOCIATION``
   Absolute path to the file Stripe issues for Apple Pay domain verification.
   Served at ``/.well-known/apple-developer-merchantid-domain-association``.
   Only needed for Apple Pay.

``PAYPAL_CLIENT_ID``, ``PAYPAL_CLIENT_SECRET``
   PayPal REST credentials.  Blank hides PayPal from the provider list.

``PAYPAL_ENV``
   ``sandbox`` or ``live``.  Chooses which PayPal API host is called.

   :Development: ``sandbox``
   :Production: ``live``

``PAYMENTS_MOCK_ENABLED``
   Enables the mock provider, which renders "Succeed" and "Fail" buttons
   instead of taking money.  The e2e tests use it, and so does anyone without
   payment keys.

   :Development: ``true``
   :Production: ``false``.  ``prod.py`` defaults it to false; setting it true
      on a public site would let anyone grant themselves a membership.


Frontend assets
===============

``DJANGO_VITE_DEV_MODE``
   ``true`` makes Django load assets from the Vite dev server on :5173, for hot
   module reload while running ``make dev-frontend``.  ``false`` makes it read
   ``frontend/dist/.vite/manifest.json`` from ``npm run build``.

   :Development: ``false`` normally; ``true`` while doing frontend work.
   :Production: ``false``.  ``prod.py`` forces it off.

``DJANGO_VITE_MANIFEST_PATH`` *(prod only)*
   Override the manifest location.  Defaults to
   ``frontend/dist/.vite/manifest.json`` under the repository root, which is
   right for the standard deploy layout.


Backups
=======

``BACKUP_DIR``
   Where ``db_backup`` writes and ``/system/backups`` reads.  A relative path is
   resolved against the repository root; an absolute one is used as given.  It
   is also the filesystem ``/system/health`` measures free space on.

   :Development: ``backups`` — gitignored.
   :Production: ``/srv/caldart/backups``, owned by the service user and listed
      in ``ReadWritePaths`` in ``caldart-web.service``.

``DB_BACKUP_VIA_DOCKER``
   ``true`` runs ``pg_dump``/``psql`` through ``docker compose exec -T db``.
   ``false`` prefers the local binaries and falls back to the container only if
   they are missing.

   :Development: ``true`` — most dev machines have Docker but not
      ``postgresql-client``.
   :Production: ``false``, with ``postgresql-client`` installed.


Production hardening
====================

All of these are read only by ``prod.py`` and all have sensible defaults.

``SECURE_SSL_REDIRECT``
   Redirect plain HTTP to HTTPS.  Default ``true``.  Only turn it off if
   something in front is already doing it, and never as a way to fix a redirect
   loop — that is a missing ``X-Forwarded-Proto``, not a Django problem.

``SECURE_HSTS_SECONDS``
   ``Strict-Transport-Security`` max-age.  Default ``31536000`` (one year).
   Set it to ``0`` for the first deploy of a new hostname: browsers honour the
   header for its whole duration and there is no way to retract it early.

``SECURE_HSTS_INCLUDE_SUBDOMAINS``, ``SECURE_HSTS_PRELOAD``
   Both default ``true``.  Turn the first off if other services run on
   subdomains without TLS.

``LOG_LEVEL``
   Root logger level; everything goes to stdout and so to the journal.
   Default ``INFO``.

``DB_CONN_MAX_AGE``
   Seconds to keep a database connection open between requests.  Default
   ``60``; gunicorn workers are long-lived, so reconnecting per request is pure
   latency.

``WEB_CONCURRENCY``
   Read by ``deploy/gunicorn.conf.py``, not by Django: how many worker
   processes to run.  Defaults to ``2 × cores + 1`` capped at 12, because every
   worker preloads Django and Wagtail.  Set it lower on a small VM.


Settings that are not environment variables
===========================================

``DJANGO_SETTINGS_MODULE``
   Which settings module to load.  Not read from ``.env`` — it has to be set
   before Django starts.  ``caldart.settings.dev`` by default,
   ``caldart.settings.prod`` in both systemd units, ``caldart.settings.test``
   from ``pyproject.toml``.

``CALDART_VERSION``
   A constant in ``base.py``, used only as the fallback when
   ``pyproject.toml`` cannot be read.  ``/system/health`` reports the version
   from ``pyproject.toml`` itself.


Checking what is loaded
=======================

::

  uv run backend/manage.py diffsettings          # everything, vs Django's defaults
  uv run backend/manage.py health --json         # db, migrations, disk, version, debug
  uv run backend/manage.py check --deploy        # Django's own production audit

``check --deploy`` should be clean under ``caldart.settings.prod``.  Run it
against the real environment file, not the development one, or it will
complain about settings that are correct for development.
