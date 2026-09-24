=================
Development setup
=================

From a clean machine to a running CalDART, then the everyday commands you will
use while working on it.  Configuration is covered separately in
:doc:`configuration`, and what the resulting application actually does is in
the :doc:`/demo-walkthrough`.

Prerequisites
=============

.. list-table::
   :header-rows: 1
   :widths: 22 20 58

   * - Tool
     - Version
     - Why
   * - Python
     - 3.12
     - ``requires-python = ">=3.12"``; ``.python-version`` pins 3.12
   * - ``uv``
     - recent
     - installs Python dependencies from ``uv.lock`` and runs everything
   * - Node.js and npm
     - Node 20+
     - builds the frontend (CI uses Node 22)
   * - Docker with Compose
     - recent
     - PostgreSQL 16 and Mailpit
   * - ``make``
     - any
     - every task in this project is a Make target

You do **not** need a local PostgreSQL server or client: the compose stack
provides both, and the backup commands fall back to running ``pg_dump`` inside
the container when it is not on your ``PATH``.

Nothing in the table is a framework: ``uv sync`` installs those from
``uv.lock``.  The backend runs on **Django 6** with Wagtail 8 and Django REST
Framework 3, and ``pyproject.toml`` states the minimum version of each.  The
full stack is in :doc:`architecture`.

Install ``uv`` from https://docs.astral.sh/uv/ if you do not have it.  It
manages the Python toolchain itself, so a system Python older than 3.12 is not
a problem.

First run
=========

.. code-block:: console

   $ git clone <the repository>
   $ cd caldart-proto
   $ make setup
   $ make up
   $ make migrate
   $ make seed
   $ make build
   $ make run

Step by step:

1. **``make setup``** runs ``uv sync`` (Python dependencies, from the committed
   ``uv.lock``), ``npm ci`` in ``frontend/`` (Node dependencies, from
   ``package-lock.json``), and copies ``.env.example`` to ``.env`` if you do
   not already have one.  It never overwrites an existing ``.env``.

2. **``make up``** starts the two containers, waits for Postgres to answer
   ``pg_isready``, and creates the database named in ``DATABASE_URL`` if it
   does not exist.

   .. list-table::
      :header-rows: 1
      :widths: 20 20 60

      * - Service
        - Port
        - What
      * - ``db``
        - 5432
        - PostgreSQL 16, user/password ``caldart``/``caldart``
      * - ``mailpit``
        - 8025, 1025
        - web inbox on 8025, SMTP on 1025

   The compose project is named ``caldart`` in ``docker-compose.yml``, so every
   checkout on the machine shares one pair of containers.  Data lives in the
   ``caldart_pgdata`` volume and survives ``make down``.

3. **``make migrate``** applies the migrations.  Each app has one initial
   migration describing its tables as they are: this is a prototype with no
   installation to upgrade, so a schema change is made by editing the model and
   regenerating that migration rather than by stacking a fix-up on top of it.
   Three migrations carry data rather than schema.
   ``accounts.0002_seed_roles`` creates one group per role, so a migrated
   database already knows what a ``dart_leader`` is, ``cms.0002_site_root``
   makes a ``HomePage`` the Wagtail site root, and
   ``cms.0003_website_admin_permissions`` gives the ``website_admin`` group its
   editing rights.

4. **``make seed``** runs ``seed_roles``, then ``seed_demo`` (demo accounts,
   about forty generated members, twenty-five aircraft, two years of
   payments), then ``seed_content`` (the example Wagtail site).  All three are
   idempotent — running ``make seed`` twice changes nothing.

5. **``make build``** compiles the frontend into ``frontend/dist`` and writes
   ``frontend/dist/.vite/manifest.json``.  **This step is not optional.**  With
   ``DJANGO_VITE_DEV_MODE=false`` — the default — Django reads that manifest to
   find the hashed asset names, and every HTML page raises
   ``Cannot find src/site/main.ts ... in Vite manifest`` until it exists.

6. **``make run``** starts Django on port 8000 and prints the URLs below.

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - URL
     - What it is
   * - http://localhost:8000/
     - the public website, served by Wagtail
   * - http://localhost:8000/portal/
     - the member portal (React SPA)
   * - http://localhost:8000/admin/
     - the Wagtail admin
   * - http://localhost:8000/django-admin/
     - the Django admin
   * - http://localhost:8000/api/v1/
     - the JSON API (see :doc:`api-reference`)
   * - http://localhost:8025/
     - Mailpit — every email development sends

Sign in with any of the demo accounts, all of which use the password
``caldart-demo``:

.. list-table::
   :header-rows: 1
   :widths: 44 56

   * - Email
     - Roles
   * - ``member@example.org``
     - ``member`` — membership current
   * - ``expired@example.org``
     - ``member`` — membership expired
   * - ``leader@example.org``
     - ``member``, ``dart_leader``
   * - ``useradmin@example.org``
     - ``member``, ``user_admin``
   * - ``treasurer@example.org``
     - ``member``, ``treasurer`` — no membership term
   * - ``accountadmin@example.org``
     - ``member``, ``account_admin``
   * - ``webadmin@example.org``
     - ``member``, ``website_admin``
   * - ``sysadmin@example.org``
     - ``member``, ``system_admin``, Django superuser

The list, the names attached to it and the password all live in
``backend/apps/accounts/seed.py``.

Smoke test
==========

With ``make run`` still running in one terminal, check the four surfaces
from another:

.. code-block:: console

   $ curl -sI http://localhost:8000/ | head -1
   HTTP/1.1 200 OK
   $ curl -sI http://localhost:8000/portal/ | head -1
   HTTP/1.1 200 OK
   $ curl -sI http://localhost:8000/api/v1/system/health | head -1
   HTTP/1.1 401 Unauthorized
   $ curl -sI http://localhost:8000/admin/ | head -1
   HTTP/1.1 302 Found

The public site and the portal shell both answer ``200``; the API rejects the
signed-out health check (``401``) rather than 404ing, proving the URL is
wired up; the Wagtail admin redirects (``302``) to its sign-in page for a
signed-out request.  Sign in to
``/portal/`` with a demo account from the table above to confirm the whole
stack — Postgres, the seed data, and the built frontend bundle — is wired up
end to end.  Anything other than these responses means one of the six setup
steps above did not finish: check ``make migrate`` and ``make seed`` ran
against the database named in ``.env``, and that ``make build`` produced
``frontend/dist/.vite/manifest.json``.

Working on the frontend
=======================

``make build`` produces production assets; it does not watch for changes.  For
hot module reload:

1. Set ``DJANGO_VITE_DEV_MODE=true`` in ``.env``.
2. Run ``make dev-frontend`` in a second terminal — Vite serves on port 5173.
3. Leave ``make run`` going in the first.

Django then loads modules from the Vite dev server instead of the manifest, and
edits to ``frontend/src`` appear without a rebuild.  Set the variable back to
``false`` (and re-run ``make build``) when you are finished, or every page will
fail as soon as the Vite server stops.

React Fast Refresh needs a preamble installed on the page before any component
module runs.  Vite injects it into its own ``index.html``, which Django never
serves, so ``backend/templates/portal.html`` emits it with django-vite's
``{% vite_react_refresh %}`` tag, ahead of ``{% vite_hmr_client %}`` and the
entry module.  The tag renders nothing unless ``DJANGO_VITE_DEV_MODE`` is
``true``, so the built assets carry no refresh runtime.
``backend/templates/base.html`` needs no such tag: ``src/site/main.ts`` is plain
TypeScript with no React in it.

.. note::

   Both halves of the front end go through Vite: ``src/site/main.ts`` for the
   server-rendered public pages and ``src/portal/main.tsx`` for the SPA.  Both
   are declared as Rollup inputs in ``frontend/vite.config.ts``, and both must
   appear in the manifest for the site to render.

Per-worker databases
====================

Several branches are often in flight at once in separate git worktrees, all
sharing the one pair of containers.  They must not share a database.  The
convention is one database per branch, named after the branch slug:

.. code-block:: text

   DATABASE_URL=postgres://caldart:caldart@localhost:5432/caldart_<branch-slug>

So ``feature/payments`` uses ``caldart_payments`` and ``feature/docs`` uses
``caldart_docs``.  Set it in that worktree's ``.env``; ``make up`` creates the
database if it is missing, and every other target picks it up because the
Makefile exports ``DATABASE_URL`` after reading it from ``.env``.

Test runs stay isolated for free: Django names the test database
``test_<the name in DATABASE_URL>``, so ``pytest`` on two branches at once
works on ``test_caldart_payments`` and ``test_caldart_docs``.

You can also override it per command without touching ``.env``:

.. code-block:: console

   $ make test DATABASE_URL=postgres://caldart:caldart@localhost:5432/caldart_scratch

If you run two Django servers at once, give them different ports
(``uv run backend/manage.py runserver 0.0.0.0:8021``) and set ``SITE_URL`` to
match, so password-reset and reminder emails link back to the right one.

.. warning::

   The containers are shared.  ``docker compose down`` stops the database out
   from under every other worktree on the machine — use ``make down`` only when
   you know nothing else is running, and never during parallel work.

Make targets
============

``make help`` lists every target with a one-line description.  The same
list, in full:

.. list-table::
   :header-rows: 1
   :widths: 26 74

   * - Target
     - What it does
   * - ``help``
     - the everyday targets, one line each
   * - ``setup``
     - ``uv sync``, ``npm ci``, create ``.env`` from ``.env.example`` if absent
   * - ``up``
     - start the ``db`` and ``mailpit`` containers, wait for Postgres, create
       the database in ``DATABASE_URL``
   * - ``down``
     - stop the containers (the ``caldart_pgdata`` volume survives)
   * - ``wait-db``
     - block until Postgres accepts connections; a step of ``up``
   * - ``createdb``
     - create the database named in ``DATABASE_URL`` if it does not exist
   * - ``migrate``
     - ``manage.py migrate``
   * - ``makemigrations``
     - ``manage.py makemigrations``
   * - ``seed``
     - ``seed_roles``, ``seed_demo``, ``seed_content``
   * - ``reset``
     - ``db_reset --seed --noinput`` — **destroys** the database, then
       migrates and re-seeds
   * - ``run``
     - Django on :8000
   * - ``dev-frontend``
     - the Vite dev server on :5173 (needs ``DJANGO_VITE_DEV_MODE=true``)
   * - ``build``
     - production frontend assets into ``frontend/dist``
   * - ``collectstatic``
     - ``manage.py collectstatic --noinput`` into ``backend/staticfiles``
   * - ``shell``
     - the Django shell
   * - ``superuser``
     - ``manage.py createsuperuser``
   * - ``test``
     - ``test-backend`` then ``test-frontend``
   * - ``test-backend``
     - ``uv run pytest``
   * - ``test-frontend``
     - ``npm run test`` (vitest)
   * - ``e2e``
     - ``npm run e2e`` (Playwright)
   * - ``lint``
     - ``lint-backend``, ``lint-frontend``, then ``lint-spelling``
   * - ``lint-backend``
     - ``ruff check``, ``ruff format --check`` and ``mypy backend``
   * - ``lint-frontend``
     - ``tsc --noEmit``, ``eslint``, ``prettier --check``
   * - ``lint-spelling``
     - ``codespell`` — American spelling and common typos
   * - ``format``
     - ``ruff format``, ``ruff check --fix``, ``prettier --write``
   * - ``check``
     - ``check-backend``, ``check-deploy``, then ``check-frontend``
   * - ``check-backend``
     - ``manage.py check --fail-level WARNING``,
       ``manage.py makemigrations --check --dry-run`` and
       ``manage.py spectacular``, all under ``caldart.settings.test``
   * - ``check-deploy``
     - ``manage.py check --deploy --fail-level WARNING`` under
       ``caldart.settings.prod``, in a throwaway environment — see
       :doc:`deployment`
   * - ``check-frontend``
     - ``npm run typecheck`` against the generated schema, then
       ``npm run build`` — the production frontend build
   * - ``audit``
     - ``audit-backend`` then ``audit-frontend``
   * - ``audit-backend``
     - ``uv audit`` — the versions in ``uv.lock`` against the OSV database
   * - ``audit-frontend``
     - ``npm audit`` — the versions in ``package-lock.json``
   * - ``backup``
     - ``db_backup`` — a gzipped ``pg_dump`` into ``backups/``
   * - ``restore``
     - ``db_restore`` — ``make restore FILE=backups/caldart-….sql.gz [YES=1]``
   * - ``reminders``
     - ``send_renewal_reminders`` — ``make reminders [TODAY=2027-01-01] [DRY_RUN=1]``
   * - ``docs``
     - ``sphinx-build -n -W`` into ``docs/_build/html``
   * - ``clean``
     - remove ``docs/_build``, ``frontend/dist``, ``backend/staticfiles``, and
       ``__pycache__``

Every target runs from the repository root, and every one of them honors
``DATABASE_URL``.

.. _make-switches:

Switch variables
================

``YES`` on ``make restore`` and ``DRY_RUN`` on ``make reminders`` are switches:
``1``, ``yes``, or ``true`` turns the option on; ``0``, ``no``, ``false``, an
empty value or leaving the variable unset leaves it off; any other value stops
``make`` with an error naming the variable, before a single line of the recipe
runs.  The comparison is case-sensitive, so ``YES=True`` is an error rather
than a switch that is on.

``FILE`` on ``make restore`` and ``TODAY`` on ``make reminders`` are not
switches: they carry a value straight through to the command.

Management commands
===================

Beyond Django's and Wagtail's own, this project adds:

.. list-table::
   :header-rows: 1
   :widths: 34 66

   * - Command
     - What it does
   * - ``seed_roles``
     - create one group per role slug; idempotent, also run by a data migration
   * - ``seed_demo [--seed N]``
     - the demo data set; ``--seed`` is the *random* seed, default ``20260904``
   * - ``seed_content``
     - the example Wagtail site, and the ``website_admin`` permission grant
   * - ``seed_facts``
     - print the demo password, accounts, and plan prices as JSON, which
       ``make e2e`` saves for the end-to-end specs (:doc:`testing`)
   * - ``db_backup``
     - write ``backups/caldart-<timestamp>.sql.gz``
   * - ``db_restore <file> [--yes]``
     - drop the schema and replay a dump into it
   * - ``db_reset [--seed] [--noinput]``
     - drop and recreate the schema, migrate, seed roles, optionally seed data
   * - ``health``
     - print database connectivity, pending migrations, free disk, last backup
   * - ``send_renewal_reminders [--dry-run] [--today=YYYY-MM-DD]``
     - the renewal scan
   * - ``payments_sandbox_check``
     - check the configured Stripe and PayPal credentials without moving money

Run any of them with ``uv run backend/manage.py <command>``.  See
:doc:`backup-restore` and :doc:`reminders` for the operational detail.

Payments sandbox
=================

Working on Stripe or PayPal against their real sandboxes, rather than the
mock provider, needs API keys in ``.env`` (:doc:`configuration`).  Once they
are there, check that they actually work before opening a browser:

.. code-block:: console

   $ make sandbox-check

It reports the Stripe balance and enabled payment methods, the PayPal
sandbox account's configured webhooks, and which webhook secrets are set,
without moving any money.
:doc:`payments-setup` has the full recipe — creating the accounts, the test
cards, and a drill through every fee, receipt, refund and automatic renewal
path end to end.

Before you open a pull request
==============================

Five commands must be green, and CI runs all five on every pull request:

.. code-block:: console

   $ make test     # pytest + vitest; a warning fails the run
   $ make lint     # ruff, mypy, tsc, eslint (no warnings), prettier, codespell
   $ make check    # manage.py check, makemigrations --check, npm run build
   $ make docs     # sphinx-build -n -W: nitpicky, warnings are errors
   $ make audit    # uv audit + npm audit: known vulnerabilities

``make check`` catches a model change without its migration and a frontend
that type-checks but does not build. See
:doc:`testing` for how the suites are organized.

To read the documentation you just built, ``make read-docs`` builds it and
opens ``docs/_build/html/index.html`` in your browser.  It runs
``scripts/read-docs.sh``, which takes ``--open`` to open the built pages
without rebuilding and ``--build`` to rebuild without opening, and honors
``BROWSER`` when you would rather not use the platform default.

Troubleshooting
===============

**Every page 500s with "Cannot find src/site/main.ts … in Vite manifest".**
You have not run ``make build``, or you built after starting Django — the
manifest is read once at start-up.  Build, then restart the server.  If you are
using the dev server, check that ``DJANGO_VITE_DEV_MODE=true`` and that
``make dev-frontend`` is actually running.

**The portal is blank and the console says "@vitejs/plugin-react can't detect
preamble".**  A React module loaded before Fast Refresh was installed.  Check
that ``{% vite_react_refresh %}`` is still the first of the three Vite tags in
``backend/templates/portal.html``, and that the page you are on is served from
that template rather than a copy.

**``make up`` says Postgres did not become ready.**  The container is up but
not answering.  ``docker compose logs db`` will say why; a port 5432 already
bound by a system PostgreSQL is the usual cause.

**``psql: database "caldart_something" does not exist``.**  Run ``make up``,
which creates the database named in ``DATABASE_URL``.  It is only created at
``make up`` time, so a fresh ``DATABASE_URL`` needs another ``make up``.

**Migrations conflict after a rebase.**  This prototype keeps no backwards
compatibility: delete the offending migration, re-run ``makemigrations``, and
``make reset`` your development database rather than stacking fix-ups.

**No email arrives.**  Development mail goes to Mailpit, not to the internet.
Open http://localhost:8025/.  If it is empty, check ``EMAIL_URL`` in ``.env``
and that the ``mailpit`` container is running.

**Tests pass alone and fail together.**  Two branches are probably sharing a
database.  Give each worktree its own ``DATABASE_URL``.
