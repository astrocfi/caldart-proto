==============================================
CalDART — website and member management system
==============================================

A prototype for **The California DART Network**: a Wagtail-managed public
website plus a React member portal with roles, profiles, an aircraft
register, online join/renew, renewal reminders and admin reporting.

The documentation in ``docs/`` is the specification. If the code and the docs
disagree, one of them is wrong — fix it in the same pull request.


Quick start
===========

Requirements: Python 3.12, `uv <https://docs.astral.sh/uv/>`_, Node 20+ and
npm, Docker with Compose, and ``make``. No local PostgreSQL client is needed;
the compose stack provides one.

.. code-block:: console

   $ make setup     # uv sync, npm ci, copy .env.example to .env
   $ make up        # start Postgres (:5432) and Mailpit (:8025 / :1025)
   $ make migrate   # create the schema and the role groups
   $ make seed      # demo accounts, members, aircraft, payments
   $ make build     # build the frontend into frontend/dist
   $ make run       # Django on http://localhost:8000

Then open:

===================================  ========================================
URL                                  What it is
===================================  ========================================
http://localhost:8000/               public site (Wagtail)
http://localhost:8000/portal/        member portal (React SPA)
http://localhost:8000/admin/         Wagtail admin
http://localhost:8000/django-admin/  Django admin
http://localhost:8025/               Mailpit — every email sent in development
===================================  ========================================

For hot module reload while working on the frontend, set
``DJANGO_VITE_DEV_MODE=true`` in ``.env`` and run ``make dev-frontend`` in a
second terminal.


Demo accounts
=============

``make seed`` creates these, all with the password ``caldart-demo``:

=============================  ====================================
Email                          Roles
=============================  ====================================
member@example.org             member (current membership)
expired@example.org            member (expired membership)
leader@example.org             member, dart_leader
useradmin@example.org          member, user_admin
accountadmin@example.org       member, account_admin
webadmin@example.org           member, website_admin
sysadmin@example.org           member, system_admin (superuser)
=============================  ====================================

Plus about 40 generated members with mixed membership, certificate and
medical states, 25 aircraft with varied insurance currency, and two years of
payment history.


Everyday commands
=================

.. code-block:: console

   $ make test           # pytest + vitest
   $ make e2e            # Playwright, end to end (see below)
   $ make lint           # ruff + mypy + tsc + eslint + prettier + codespell
   $ make check          # system checks, migrations, deploy security, build
   $ make docs           # Sphinx, nitpicky, warnings are errors
   $ make audit          # known vulnerabilities in Python and npm dependencies
   $ make reset          # destroy and re-seed the dev database
   $ make backup         # gzipped pg_dump into backups/
   $ make help           # the everyday targets

``make help`` covers the everyday targets. The Make targets table in
``docs/developer/setup.rst`` lists every target the Makefile defines, halves
and helpers included.


End-to-end tests
================

``frontend/e2e`` holds Playwright specs for the five flows of the demo
walkthrough (``docs/demo-walkthrough.rst``), driven through a real browser
against a real server, paying with the mock
provider. Install the browser once:

.. code-block:: console

   $ cd frontend && npx playwright install chromium

Then, from the repository root:

.. code-block:: console

   $ make e2e

That creates and seeds its own ``caldart_e2e`` database, builds the frontend,
collects the static files, starts Django on :8021, runs the specs and stops the
server again — your development database is never touched. Add ``E2E_PORT=…``
or ``E2E_DB=…`` to move either. The target pins every setting the run needs
(``DEBUG``, ``SECRET_KEY``, ``ALLOWED_HOSTS``, ``SITE_URL``, the mock provider,
the login throttle), so it behaves the same with your ``.env`` and without one
— which is what CI has. To watch a run, or to work on one spec:

.. code-block:: console

   $ cd frontend && E2E_BASE_URL=http://localhost:8000 npx playwright test --headed leader

against a server you started yourself with ``make run``.

If Chromium will not start for want of system libraries, install them with
``npx playwright install-deps chromium``, which needs ``sudo``:

.. code-block:: console

   $ sudo $(which npx) playwright install-deps chromium

CI installs them itself (``playwright install --with-deps chromium`` on
``ubuntu-latest``), so nothing there needs a privileged step.


Layout
======

::

   backend/     Django + Wagtail (caldart project, apps/, templates/, tests/)
   frontend/    Vite + React + TypeScript (public-site JS and the portal SPA)
   docs/        Sphinx documentation (user/ and developer/)
   deploy/      gunicorn, systemd, Apache and nginx configuration
   plans/       implementation plans; archive/ holds finished ones
   critiques/   dated review reports
   CLAUDE.md    conventions for working in this repository


License
=======

Prototype code for CalDART. Not yet licensed for redistribution.
