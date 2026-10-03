=============
Configuration
=============

Every runtime setting comes from the environment.  There are two templates:

``.env.example``
   The development reference, at the repository root, with working defaults for
   every variable.  ``make setup`` copies it to ``.env`` if you do not have one.

``deploy/caldart.env.example``
   The production template, installed as ``/etc/caldart/caldart.env`` and read
   by the systemd units.  The five variables a deployment must decide for
   itself — ``SECRET_KEY``, ``ALLOWED_HOSTS``, ``SITE_URL``, ``EMAIL_URL``, and
   ``DATABASE_URL`` — are commented out, so an unedited copy refuses to start
   instead of serving with a guessed value.  It also lists the hardening and
   logging variables that only ``prod.py`` reads.

Never install ``.env.example`` on a server: it carries the published
development ``SECRET_KEY`` and turns the mock payment provider on.  This page
is the complete list of variables either way.

.. note::

   Nothing re-reads the environment while the application is running.  After
   editing ``/etc/caldart/caldart.env``, ``systemctl restart caldart-web``.


Where settings are read
=======================

``backend/caldart/settings/`` has five modules:

``_dotenv.py``
   Reads ``.env`` from the repository root into the process environment, so a
   bare checkout runs with no exported variables at all.  Real environment
   variables win over the file.  Only ``dev.py`` and ``test.py`` import it, and
   they import it before ``base``.

``base.py``
   Reads every variable listed below with ``django-environ``, each with a
   development default.  Everything else imports from here.  It never reads
   ``.env`` itself.

``dev.py``
   ``DEBUG`` on, unhashed static storage, and ``ALLOWED_HOSTS`` defaulting to
   ``["*"]`` — but only when the variable is *absent*, and ``.env.example``
   sets it, so a standard checkout gets the list from ``.env``.  The default
   ``manage.py`` reaches for when nothing sets ``DJANGO_SETTINGS_MODULE``.

``prod.py``
   ``DEBUG`` off, TLS, and cookie hardening, hashed static manifest, logging to
   stdout, persistent database connections, a database-backed cache.  It reads
   the environment alone — no ``.env`` anywhere in its import chain — so a
   missing variable cannot be filled in from a file that happens to sit beside
   the code.  Four variables have **no default** and a missing one is a
   start-up error: ``SECRET_KEY``, ``ALLOWED_HOSTS``, ``SITE_URL``, and
   ``EMAIL_URL``.  A ``SECRET_KEY`` equal to the published development key is a
   start-up error too, and so is a ``SITE_URL`` whose path is not the
   ``URL_PREFIX``.  Selected by
   ``Environment=DJANGO_SETTINGS_MODULE=caldart.settings.prod`` in all nine
   systemd services: ``caldart-web`` and the eight scheduled jobs
   (``caldart-registry``, ``caldart-reports``, ``caldart-renewals``,
   ``caldart-reminders``, ``caldart-statements``, ``caldart-bounces``,
   ``caldart-bulk-email``, and ``caldart-backup``).

``test.py``
   ``DEBUG`` off, MD5 password hashing, in-memory email and file storage, mock
   payments on.  It reads ``.env`` so a worktree's own ``DATABASE_URL`` reaches
   the test database name.  Selected by ``pytest.ini_options`` in
   ``pyproject.toml``; you never set it by hand.

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
      ``prod.py`` refuses to start with the development key: it is published in
      the repository, so anyone could forge sessions and password-reset links.

``DEBUG``
   Django's debug mode: tracebacks in the browser, no template caching.

   :Development: ``true``
   :Production: ``false``.  ``prod.py`` forces it off regardless, and
      ``/system/health`` reports it so a mistake is visible.

``ALLOWED_HOSTS``
   Comma-separated hostnames Django will answer for.  A request with any other
   ``Host`` header gets a ``DisallowedHost`` error.

   :Development: ``localhost,127.0.0.1,[::1]``, from ``.env.example``.
      ``dev.py`` falls back to ``*`` only when the variable is not set at all,
      so to reach the dev server from a phone on the LAN either add the
      machine's address to the list or comment the line out.
   :Production: **required**; every hostname the vhost serves, including the
      ``www.`` form.

``CSRF_TRUSTED_ORIGINS``
   Comma-separated origins, *with scheme*, allowed to post to the site.
   Needed behind TLS termination.

   :Development: defaults to the scheme and host of ``SITE_URL``: a browser's
      ``Origin`` header never carries a path, so a ``SITE_URL`` under a
      ``URL_PREFIX`` still yields ``https://caldart.example.org``.
   :Production: ``https://caldart.example.org,https://www.caldart.example.org``.

``SITE_URL``
   The public base URL.  Used for links in emails — including the renewal
   reminders' ``/portal/renew`` link — and as ``WAGTAILADMIN_BASE_URL``.  Its
   path is the ``URL_PREFIX``: ``https://paloaltodart.org/caldart-proto`` for a
   site under ``/caldart-proto``, and no path at all for a site at the root of
   its host.  ``prod.py`` refuses to start when the two disagree, since the
   emails would then link somewhere the pages do not.

   :Development: ``http://localhost:8000``
   :Production: **required**, ``https://caldart.example.org``, no trailing
      slash.

``URL_PREFIX``
   The path the site is served under when it shares its host with another
   site, such as ``/caldart-proto``; empty when it owns the whole host.  Any
   spelling with or without a leading or trailing slash reads the same, so
   ``caldart-proto`` and ``/caldart-proto/`` both mean ``/caldart-proto``.
   Each segment is letters, digits, ``.``, ``_``, ``~``, or ``-``; an empty
   segment (``//x//``), a ``.`` or ``..`` segment, or any other character is an
   ``ImproperlyConfigured`` error at start-up.

   The web server in front strips the prefix before it proxies a request, and
   ``base.py`` sets ``FORCE_SCRIPT_NAME`` to the prefix, so Django routes on the
   path below it and writes it back onto every URL it builds: ``reverse()``,
   ``{% url %}``, ``static()`` and the media URL.  ``STATIC_URL`` and
   ``MEDIA_URL`` are built from it too, ``<prefix>/static/`` and
   ``<prefix>/media/``: Django would prefix a relative value with the script
   name only once a request has set it, and gunicorn loads the application,
   whose storages keep the URL, before its first request.  whitenoise strips
   the prefix from ``STATIC_URL`` before it matches a request.  ``LOGIN_URL`` (``<prefix>/portal/login``),
   ``LOGIN_REDIRECT_URL`` (``<prefix>/portal/``) and ``LOGOUT_REDIRECT_URL``
   (``<prefix>/``) are built from it.  The session and CSRF cookies keep the
   path ``/``: a host runs one CalDART, and the public pages and the portal
   share the same cookies.

   Both HTML shells, ``base.html`` and ``portal.html``, carry the prefix as
   ``data-url-prefix`` on ``<html>`` (from the ``url_prefix`` the
   ``apps.cms`` context processor supplies), which is where the portal and the
   public site's script read it.  The templates write every link with
   ``{% url %}``.  ``seed_content``, and the home page ``migrate`` publishes,
   store their links with the prefix already on them, so run them with the
   same ``URL_PREFIX`` the site is served under.

   :Development: empty.
   :Production: empty, or the prefix the site is served under;
      ``SITE_URL`` must end in the same path.


Authentication rate limits
==========================

Five groups of auth endpoints, and the start of a gift on the public donation
page, are throttled per client address, signed in or not, counted as described
below.  Each takes a DRF rate as ``<count>/<period>``, where the
period is ``second``, ``minute``, ``hour``, or ``day`` (or their initials).
Setting one to an empty value turns that throttle **off**.  A value that is
neither empty nor a readable rate — ``AUTH_THROTTLE_LOGIN=lots``, say —
raises ``ImproperlyConfigured`` naming the variable, so a typo stops start-up
rather than turning the endpoint into a 500 on every request.  Exceeding a
rate is a **429**.

``caldart.settings.test`` ignores the environment and maps every scope to
``None`` in Python, so no test races a shared counter.

``AUTH_THROTTLE_LOGIN``
   ``POST /auth/login``.

   :Development: ``20/min``
   :Production: ``20/min``.  Generous enough for a household behind one
      address, tight enough that guessing is hopeless.

``AUTH_THROTTLE_REGISTER``
   ``POST /auth/register``.  Counted by address even though registration signs
   the new account in, so a script cannot escape the counter by using the
   session it just created.

   :Development: ``10/hour``
   :Production: ``10/hour``

``AUTH_THROTTLE_PASSWORD_RESET``
   ``POST /auth/password/reset`` and ``POST /auth/password/reset/confirm``.

   :Development: ``10/hour``
   :Production: ``10/hour``

``AUTH_THROTTLE_VERIFY``
   ``POST /auth/email/verify``, which follows a verification link.  Open to
   anonymous callers, so the rate is what keeps a token from being guessed.

   :Development: ``30/hour``
   :Production: ``30/hour``

``AUTH_THROTTLE_VERIFY_RESEND``
   ``POST /auth/email/resend``, which mails the signed-in account a fresh
   verification link.  Kept low because every request sends an email.

   :Development: ``5/hour``
   :Production: ``5/hour``

``AUTH_THROTTLE_DONATE``
   ``POST /donations/checkout``, which starts a gift on the public donation page
   and may make a donor account for a caller nobody has signed in.  Reading the
   form's config and finishing a payment are not counted.

   :Development: ``10/hour``
   :Production: ``10/hour``.  Plenty for a household giving more than once,
      tight enough that a script cannot fill the books with donors.

The rates land in the ``AUTH_THROTTLE_RATES`` setting, one key per scope, and
are read by ``apps.accounts.throttling``.  A scope mapped to ``None``, mapped
to an empty string, or missing from that dict is off, so an
``override_settings`` in a test can switch one on or off without knowing how
the environment was set.  There is no project-wide throttle: apart from these
and the per-account limit on :ref:`address suggestions
<configuration-address-suggestions>`, every endpoint is unlimited.  See
:doc:`api-reference`.

Which address is counted
------------------------

The client address is the **last** entry of ``X-Forwarded-For``, the one the
proxy wrote.  ``prod.py`` sets DRF's ``NUM_PROXIES`` to ``1``, a constant
rather than a variable, because that is a fact about the shipped deployment:
Apache and nginx both pass a client's own header through and append the address
they saw, and gunicorn accepts ``X-Forwarded-*`` only from loopback.  Reading
any earlier entry would count an address the client chose, and a caller that
varied it would never be throttled at all.

Put a CDN or a second load balancer in front and that count is wrong: each
extra hop appends another address, so ``NUM_PROXIES`` must rise to match the
number of proxies that are guaranteed to append one.  Set it too high and
callers share a budget; too low and they escape it.

The counters live in the default cache.  ``prod.py`` configures a
``DatabaseCache`` in the ``caldart_cache`` table, because Django's fallback
cache is per-process: gunicorn runs up to twelve workers and recycles each
after about a thousand requests, so an attacker would otherwise get a fresh
budget from every worker.  ``manage.py createcachetable`` creates the table and
is part of both the first deploy and every upgrade; see :doc:`deployment`.
Development and tests keep the local-memory cache.


Email verification
==================

``EMAIL_VERIFICATION_TIMEOUT``
   How long a verification link stays usable, in seconds.  The link carries
   the account and the address it was sent to, signed with ``SECRET_KEY``, so
   changing the address also retires every earlier link.  The verification
   message states the lifetime in whole days.

   :Development: ``259200`` (three days)
   :Production: ``259200``


.. _configuration-address-suggestions:

Address suggestions
===================

As a member types their street address on the profile form, the form offers
matching US addresses, and a pick fills the street, city, state, ZIP code, and
county at once.  The suggestions come from Geoapify's autocomplete endpoint,
called by the server through ``GET /addresses/suggest`` (see
:doc:`api-profile`), so the key stays on the server and the
Content-Security-Policy needs no Geoapify origin.

``GEOAPIFY_API_KEY``
   The Geoapify API key.  Blank turns suggestions off: the endpoint answers an
   empty list without calling anyone, and the Address box behaves as a plain
   text box.  Geoapify's free tier needs no card and covers a membership
   register's traffic; create a project at https://myprojects.geoapify.com and
   copy its key.  ``caldart.settings.test`` blanks it whatever the environment
   says, so a key in a developer's ``.env`` never sends a request from the
   suite.

   :Development: blank, or a key of your own to try the suggestions.
   :Production: the project's key.

``GEOAPIFY_URL``
   The autocomplete endpoint the server calls.  Only the end-to-end run changes
   it, pointing it at a local stub that answers a recorded response (see
   :doc:`testing`).

   :Both: ``https://api.geoapify.com/v1/geocode/autocomplete``

``ADDRESS_SUGGEST_THROTTLE_RATE``
   How many suggestions one signed-in account may ask for, as a DRF rate
   (``<count>/<period>``), read and checked exactly like the authentication
   rates above: empty turns the limit off, and an unreadable value stops
   start-up.  Each account has its own budget, counted in the default cache;
   the limit protects the Geoapify quota the whole site shares.  The form asks
   once the typing pauses, so a member typing an address spends a handful.
   Read by ``apps.members.throttling``; ``caldart.settings.test`` sets it to
   ``None``.

   :Development: ``60/min``
   :Production: ``60/min``


The FAA registry
================

The aircraft types and the registry lookup come from the FAA's Releasable
Aircraft Database, imported daily by ``manage.py import_faa_registry`` (see
:doc:`aircraft-registry`).

``FAA_REGISTRY_URL``
   Where the import reads the registry from when it is given no ``--source``:
   an ``http`` or ``https`` URL of the zip, which is downloaded, or a local zip
   or a directory holding ``ACFTREF.txt`` and ``MASTER.txt``, as a path or a
   ``file://`` URL.  The end-to-end run points it at the fixture directory,
   ``backend/apps/aircraft/fixtures/faa``, so **Run now** on the Health & Database page
   imports the fixture rather than downloading.

   :Both: ``https://registry.faa.gov/database/ReleasableAircraft.zip``

``REGISTRY_IMPORT_STALE_MINUTES``
   How many minutes an import started from the Health & Database page may run unfinished
   before it stops counting as running: the next **Run now** records it as
   failed, with the error *Did not finish.*, and starts another.  A full import
   takes well under a minute once the file is down, so the default leaves room
   for a slow download.

   :Both: ``30``


Email
=====

``EMAIL_URL``
   SMTP connection URL.  ``smtp://`` plain, ``smtp+tls://`` for STARTTLS,
   ``smtp+ssl://`` for implicit TLS.  Credentials are URL-encoded, so an ``@``
   in the username becomes ``%40``.  ``consolemail://`` prints each message
   instead of sending it, and ``filemail:////abs/path`` writes each one to a
   file in that directory, which is what the end-to-end run uses
   (``frontend/e2e/.mail/``), so a spec can read the link an email carries.
   :doc:`email` covers every backend and what a production domain needs.

   The settings modules translate it into the one entry in Django's ``MAILERS``
   setting, so the host, port, and credentials are options of that mailer rather
   than settings of their own.  ``caldart.settings.mailers`` knows which options
   each backend takes; a URL scheme naming a backend it does not list raises
   ``ImproperlyConfigured`` at startup rather than dropping the connection
   details silently.

   :Development: ``smtp://localhost:1025`` — Mailpit, whose web UI at
      http://localhost:8025 catches everything and delivers nothing.
   :Production: **required**,
      ``smtp+tls://user:password@smtp.example.org:587``.  Many providers want
      an app password rather than the account password.  ``smtp://localhost:25``
      hands mail to the machine's own postfix instead
      (:ref:`email-local-postfix`).

``DEFAULT_FROM_EMAIL``
   The ``From`` on every message, and ``SERVER_EMAIL`` for error mail.

   :Both: ``CalDART <noreply@caldart.example.org>``.  In production it must be
      a domain the SMTP relay is allowed to send as, or SPF and DMARC will
      bounce it.

``BOUNCE_ADDRESS``
   The envelope sender (the ``Return-Path``) of every message, which is where a
   receiving server returns a message it cannot deliver; the ``From`` stays
   ``DEFAULT_FROM_EMAIL``.  Set it to the address of the bounce mailbox
   ``BOUNCE_IMAP_URL`` reads (:ref:`email-bounces`).

   :Both: empty, which sends the envelope from ``DEFAULT_FROM_EMAIL`` as well.
   :Production: ``bounces@caldart.example.org``, on the same domain as
      ``DEFAULT_FROM_EMAIL`` so the relay's SPF covers it.

``BOUNCE_IMAP_URL``
   The mailbox ``manage.py check_bounces`` reads the returned reports from, as
   ``imaps://user:password@host[:port]/MAILBOX``, with the user name and password
   percent-encoded (an ``@`` becomes ``%40``).  The port defaults to 993 and the
   mailbox to ``INBOX``.  Only IMAP over TLS is accepted.

   :Both: empty, which turns bounce checking off: the hourly run and **Run now**
      on the Scheduled page say so and read nothing.
   :Production: ``imaps://bounces%40caldart.example.org:app-password@imap.example.org/INBOX``.

``DKIM_SELECTOR``
   The selector the mail server signs messages with (DKIM), the first label of the
   DNS name that holds the signing key's public half:
   ``<selector>._domainkey.<domain of DEFAULT_FROM_EMAIL>``.  The mail delivery check
   (:ref:`email-delivery-check`) looks the record up there.  The site itself never
   signs anything; the mail server or relay does.

   :Both: empty, which makes the check warn that no selector is configured.
   :Production: the selector the relay or the local mail server was set up with, such
      as ``mail``.

``EMAIL_TIMEOUT`` *(prod only)*
   Seconds to wait on the SMTP server.  Default ``20``.  Keeps a wedged relay
   from hanging a request.

``ADMIN_EMAILS`` *(prod only)*
   Comma-separated addresses that receive unhandled-500 mail, and the report of a
   message the mail server refused while a request answered anyway
   (:ref:`email-refused`).  ``prod.py`` sets both ``ADMINS`` and ``MANAGERS`` to
   this list of address strings, the shape Django expects.  Django deprecates
   ``(name, address)`` pairs there and warns of them only when it sends, so
   ``backend/tests/test_sysadmin_settings.py`` sends through both settings, and loads
   ``caldart.settings.prod`` through Django's own settings loader, with warnings as
   errors.  Default empty, which is fine — the traceback is in the
   journal either way.  A report the mail server refuses too is written to the
   journal and never fails the request.  The report lists
   the settings through ``DEFAULT_EXCEPTION_REPORTER_FILTER``, set in ``base.py`` to
   ``caldart.error_reports.CredentialSafeExceptionReporterFilter``: Django's own
   masking of the settings whose names look secret, plus the password of every URL a
   setting holds, so ``BOUNCE_IMAP_URL`` reads ``imaps://user:********************@host/INBOX``.


Bulk email
==========

The background sender and the compose screen read these (:doc:`bulk-email`).

``BULK_EMAIL_RATE_PER_MINUTE``
   The most copies the bulk email sender sends a minute.  It sleeps out the rest of
   each 60 / rate seconds after a copy begins, so the mail provider's own limit is
   never reached.  Keep it under that limit, with room for the site's other mail.

   :Both: ``30``.

``BULK_EMAIL_BATCH_SIZE``
   The copies sent over one mail connection before the sender closes it and opens a
   fresh one.

   :Both: ``50``.

``BULK_EMAIL_UNDO_SECONDS``
   The undo window: the seconds between pressing **Send** and the first copy, during
   which the send can be canceled.  ``0`` makes a send ready for the sender's next
   run at once, which is what ``make e2e`` sets.

   :Both: ``120``.

``BULK_EMAIL_CONFIRM_ABOVE``
   Above this many recipients, **Send** asks the sender to type the count before it
   sends, and the server checks the count again.

   :Both: ``50``.


Payments
========

Covered in full, with test cards and account setup, in :doc:`payments-setup`,
whose "Testing against the sandboxes" section walks every flow end to end
against Stripe test mode and the PayPal sandbox. ``make sandbox-check``
verifies whichever of the keys below are set before you open a browser.

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

``PAYPAL_WEBHOOK_ID``
   Optional.  Set it and ``POST /payments/paypal/webhook`` verifies each
   notification's signature with PayPal before acting on it; leave it blank and
   the webhook files the payload against the payment and changes nothing.
   Either way the *capture* call is what activates a membership, so a missing
   webhook id costs you a safety net rather than the flow.

   :Development: blank
   :Production: the webhook id from the PayPal dashboard

``PAYMENTS_MOCK_ENABLED``
   Enables the mock provider, which renders "Succeed" and "Fail" buttons
   instead of taking money.  The e2e tests use it, and so does anyone without
   payment keys.  ``prod.py`` does not read it at all, so an environment file
   copied from a development machine cannot switch payments off on a live site.

   :Development: ``true``
   :Production: ignored.

``PAYMENTS_MOCK_ENABLED_IN_PRODUCTION`` *(prod only)*
   The only way to enable the mock provider under ``prod.py``.  The
   production template lists it commented out, so turning it on is a deliberate
   uncomment: on a public site it lets
   anyone who can sign in grant themselves a membership.  Set it only to
   demonstrate the checkout flow on a box with no payment keys.

   :Production: ``false``


Frontend assets
===============

``DJANGO_VITE_DEV_MODE``
   ``true`` makes Django load assets from the Vite dev server on :5173, for hot
   module reload while running ``make dev-frontend``.  ``false`` makes it read
   ``frontend/dist/.vite/manifest.json`` from ``npm run build``.

   :Development: ``false`` normally; ``true`` while doing frontend work.
   :Production: ``false``.  ``prod.py`` forces it off.

``DJANGO_VITE_MANIFEST_PATH`` *(production and test only)*
   Override the manifest location.  Defaults to
   ``frontend/dist/.vite/manifest.json`` under the repository root, which is
   right for the standard deploy layout.  ``dev.py`` ignores it.

   ``test.py`` reads it as well, and the test settings load ``.env``, so a
   value set there applies to ``uv run pytest`` too: it names the bundle the
   tests marked ``needs_frontend_build`` assert against, which is how CI's
   backend job runs them against a real build.  When it names a file that does
   not exist, the suite falls back to the stub manifest it builds outside the
   checkout and skips those tests, naming the missing path in the skip reason
   (:ref:`testing-vite-manifest`).

   :Development: unset.
   :Production: unset unless the deploy puts the bundle elsewhere.


User guide
==========

``USER_GUIDE_ROOT``
   The directory holding the built user guide, which ``caldart.views.user_guide``
   serves at ``/docs/`` to signed-in users.  ``make guide`` (on a server, the
   ``sphinx-build`` line of the deployment guide's build step) writes it.  A
   directory with no ``index.html`` makes every ``/docs/`` page answer 404 and
   logs a warning.

   :Development: ``docs/_build/guide``, under the repository root.
   :Production: ``/opt/caldart/caldart/docs/_build/guide``, the checkout's
      ``docs/_build/guide``, as the installer writes it; set it elsewhere only
      when the guide is built somewhere else.


Uploads
=======

``MEDIA_ROOT``
   The directory Wagtail writes image and document uploads into, and the one
   Django's document view reads a members-only document from.  The bulk email
   editor's images go in its ``bulk-email/`` directory (:doc:`api-bulk-email`).
   The web server serves ``/media/`` straight from it to anybody, signed in or
   not, except ``media/documents/``, which only Django serves; a bulk email's
   images must stay that way, since a mail program fetches them with no session.
   In development Django serves ``/media/`` itself while ``DEBUG`` is on.

   :Development: unset: ``backend/media`` in the checkout, gitignored.
   :Production: ``/opt/caldart/media``, the deploy root's ``media`` beside the
      checkout, as the installer writes it: owned by the service user, listed
      in ``ReadWritePaths`` in ``caldart-web.service``, and named by the
      vhost's ``/media/`` alias.  Moving it means changing all three.

``BULK_EMAIL_IMAGE_MAX_BYTES``
   The largest image file, in bytes, a bulk email's sender may upload into a
   message (``POST /bulk-email/images``); a larger one is refused with the limit
   named in MB.  Keep it well under the web server's request limit (25 MB in the
   shipped vhosts).

   :Development: unset: ``5242880``, 5 MB.
   :Production: unset, the same.

``BULK_EMAIL_IMAGE_MAX_WIDTH``
   The widest, in pixels, a bulk email's image is stored; a wider upload is
   scaled down to it, its proportions kept.  The editor shows an image at most
   600 pixels wide in the message, so the default leaves room for a screen that
   draws two pixels to each one.

   :Development: unset: ``1200``.
   :Production: unset, the same.


Backups
=======

``BACKUP_DIR``
   Where ``db_backup`` writes and ``/system/backups`` reads.  A relative path is
   resolved against the repository root; an absolute one is used as given.  It
   is also the filesystem ``/system/health`` measures free space on.

   :Development: ``backups`` — gitignored.
   :Production: ``/opt/caldart/backups``, the deploy root's ``backups`` beside
      the checkout, as the installer writes it: owned by the service user and
      listed in ``ReadWritePaths`` in ``caldart-web.service`` and
      ``caldart-backup.service``.

``DB_BACKUP_VIA_DOCKER``
   ``true`` runs ``pg_dump``/``psql`` through ``docker compose exec -T db``.
   ``false`` prefers the local binaries and falls back to the container only if
   they are missing.

   :Development: ``true`` — most dev machines have Docker but not
      ``postgresql-client``.
   :Production: ``false``, with ``postgresql-client`` installed.

``BACKUP_RETENTION_DAYS``
   Read by ``deploy/systemd/caldart-backup.service``, not by Django: after each
   nightly dump the unit deletes the generated ``caldart-*.sql.gz`` files in
   ``BACKUP_DIR`` older than this many days.  systemd expands it from the
   environment file, so a changed value applies from the next run
   (:doc:`backup-restore`).

   :Development: unused; nothing prunes a development ``backups/``.
   :Production: ``30``, as the template and the installer write it.


Production hardening
====================

These take effect only in production and all have sensible defaults, so none
of them is set in a template.  ``.env.example`` lists each one commented out,
and ``deploy/caldart.env.example`` is the template a server starts from.  All but the last two are read by ``prod.py``;
``WEB_CONCURRENCY`` and ``CALDART_GUNICORN_PORT`` are read by gunicorn's own
configuration file and never by Django at all.

``SECURE_SSL_REDIRECT``
   Redirect plain HTTP to HTTPS.  Default ``true``.  Only turn it off if
   something in front is already doing it, and never as a way to fix a redirect
   loop — that is a missing ``X-Forwarded-Proto``, not a Django problem.

``SECURE_HSTS_SECONDS``
   ``Strict-Transport-Security`` max-age.  Default ``31536000`` (one year).
   Set it to ``0`` for the first deploy of a new hostname: browsers honor the
   header for its whole duration and there is no way to retract it early.
   Django is the only thing that sends this header — neither shipped vhost sets
   it — so this setting is exactly what a browser receives.

``SECURE_HSTS_INCLUDE_SUBDOMAINS``
   Default ``true``.  Turn it off if other services run on subdomains without
   TLS, or browsers will refuse to reach them for the whole ``max-age``.

``SECURE_HSTS_PRELOAD``
   Default ``false``.  Setting it true adds ``preload`` to the header, which
   tells the world the site consents to the browser preload list: anyone may
   then submit the domain, and browsers ship the entry hard-coded.  Removal
   takes months and reaches users only as they upgrade, so turn it on only once
   every current and future subdomain will serve HTTPS indefinitely.  While it
   is off, ``manage.py check --deploy`` would report ``security.W021``;
   ``prod.py`` silences that one check deliberately.

``LOG_LEVEL``
   Root logger level; everything goes to stdout and so to the journal.
   Default ``INFO``.  The ``caldart.audit`` logger keeps its own level and
   handler and does not pass records to the root logger, so raising this to
   ``WARNING`` quiets the application without silencing the audit trail
   (:ref:`deploy-audit-log`).

``DB_CONN_MAX_AGE``
   Seconds to keep a database connection open between requests.  Default
   ``60``; gunicorn workers are long-lived, so reconnecting per request is pure
   latency.

``WEB_CONCURRENCY``
   Read by ``deploy/gunicorn.conf.py``, not by Django: how many worker
   processes to run.  Defaults to ``2 × cores + 1`` capped at 12, because every
   worker preloads Django and Wagtail.  Set it lower on a small VM.

``CALDART_GUNICORN_PORT``
   Read by ``deploy/gunicorn.conf.py``, not by Django: the port on
   ``127.0.0.1`` gunicorn listens on, where the web server's proxy reaches it.
   It is not the site's port, which is 80 and 443 on the web server.  Default
   ``8001``.  ``install.sh --gunicorn-port`` writes it into
   ``/etc/caldart/caldart.env`` and writes the same port into the vhost, so
   change it with that flag rather than by hand: the two must agree
   (:ref:`deploy-sharing`).


.. _configuration-csp:

Content-Security-Policy
=======================

Every response carries an enforced ``Content-Security-Policy`` header — not
``Content-Security-Policy-Report-Only``, so a browser refuses a resource the
policy does not name.  django-csp builds it from the
``CONTENT_SECURITY_POLICY`` setting in ``backend/caldart/settings/base.py``,
which no environment variable touches: widening the policy means editing that
dictionary and shipping the change.

Each vendor's entries are copied from that vendor's own published policy
requirements — Stripe's at https://docs.stripe.com/security/guide (the
"Stripe.js" and "Link" entries of its Content Security Policy section) and
PayPal's at https://developer.paypal.com/sdk/js/csp/ — narrowed to the products
the checkout uses: the Stripe Payment Element with the Apple Pay, Google Pay and
Link wallets, and PayPal's buttons.  PayPal names the same three hosts for four
directives, written below as ``PAYPAL`` for brevity:

.. code-block:: text

   PAYPAL = https://*.paypal.com https://*.paypalobjects.com https://*.venmo.com

The wildcards cover the live and the sandbox SDK alike, so ``PAYPAL_ENV`` can
pick between them at run time while the header stays fixed at start-up.  PayPal
writes those hosts without a scheme; ``base.py`` pins ``https`` so the policy
cannot admit a plaintext copy of an SDK.

``default-src 'self'``
   Everything the following directives do not cover comes from CalDART's own
   origin.

``script-src 'self' https://js.stripe.com https://*.js.stripe.com PAYPAL``
   The portal's own bundles plus the two payment vendors' browser SDKs.
   Stripe asks for the wildcard beside the bare host so Stripe.js can start
   frames on other origins.  No template carries an inline script.  Two
   responses replace this directive with ``'self' 'unsafe-inline'``: the
   Wagtail admin, whose templates inline scripts, and the user guide at
   ``/docs/``, whose Sphinx pages inline the theme's mode switch.  Every other
   directive holds on both.

``frame-src 'self' https://js.stripe.com https://*.js.stripe.com https://hooks.stripe.com https://link.com https://*.link.com PAYPAL``
   Stripe's Payment Element and PayPal's buttons render in vendor frames.
   ``https://hooks.stripe.com`` is where a payment method that redirects — 3-D
   Secure among them — lands, and the ``link.com`` hosts serve Link's
   authentication UI.  ``'self'`` is there for Wagtail, whose admin previews a
   page in a same-origin frame.

``connect-src 'self' https://api.stripe.com https://link.com https://*.link.com PAYPAL``
   The portal's own API calls, plus the calls those SDKs make from the browser
   to authorize and capture a payment.

``img-src 'self' data: https://*.link.com PAYPAL``
   ``data:`` carries the inline SVG icons the portal and the Wagtail admin
   draw, and the vendor hosts carry the wallet and funding-source artwork the
   Payment Element and the PayPal buttons draw inside their own frames.  CalDART
   itself serves every other image, so ``base.py`` sets
   ``WAGTAIL_GRAVATAR_PROVIDER_URL = None``: the admin draws an account's
   avatar from its own static files rather than from Gravatar, and an account's
   email address stays out of a third-party request.

``font-src 'self' data:``
   The production bundle inlines the Fraunces font faces as ``data:`` URLs (Vite
   inlines assets under its size limit), which ``default-src`` alone refuses.

``style-src 'self' 'unsafe-inline'``
   Stripe's Payment Element and Wagtail's admin both set styles from
   JavaScript, which a browser attributes to this directive.

``caldart.middleware.WagtailAdminCspMiddleware`` makes the one exception:
under the path Wagtail's admin is mounted at, ``script-src`` is replaced with
``'self' 'unsafe-inline'``, because Wagtail's admin templates — the inline
panel and the date and time widgets among them — write scripts into the page.
The exception follows the path, so it covers the admin's own login page and
reaches nothing else: the public site, the portal and the API keep the policy
above.  Every other directive stays as it is even inside the admin.

``caldart.settings.dev`` widens four directives so the pages work against the
Vite dev server (``make dev-frontend``, ``DJANGO_VITE_DEV_MODE=true``): it adds
``http://localhost:5173`` to ``default-src``, ``script-src``, ``connect-src``,
and ``img-src``, ``ws://localhost:5173`` to ``connect-src`` for the hot-reload
socket, and ``'unsafe-inline'`` to ``script-src`` for React Fast Refresh's
preamble.  It edits a copy, so the policy ``caldart.settings.prod`` serves is
the one above.

Adding a payment provider, an analytics script, a web font or an embedded
video means adding its origin to the right directive, and
``backend/tests/test_csp.py`` asserts the whole header directive by directive,
so a change that widens the policy has to say so.


Settings that are not environment variables
===========================================

``DJANGO_SETTINGS_MODULE``
   Which settings module to load.  Not read from ``.env`` — it has to be set
   before Django starts.  ``manage.py`` falls back to ``caldart.settings.dev``
   so a local command needs no ceremony.  The application servers do not:
   ``wsgi.py`` and ``asgi.py`` raise ``ImproperlyConfigured`` naming this
   variable when it is unset, because a web server that has not been told which
   settings to load has been misconfigured.  All five systemd services set
   ``caldart.settings.prod``, and ``pyproject.toml`` sets
   ``caldart.settings.test`` for ``pytest``.

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
