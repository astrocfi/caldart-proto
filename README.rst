========
CalDART
========

CalDART is the website and member management system for The California DART
Network, a 501(c)(3) that organizes California pilots and ground personnel to
provide volunteer disaster air transportation. It is a prototype: a
Wagtail-managed public website plus a React member portal, with roles,
profiles, an aircraft register, online join/renew, renewal reminders and
admin reporting.

The documentation in ``docs/`` is the specification. If the code and the docs
disagree, one of them is wrong — fix it in the same pull request.


Features
========

- **Accounts and roles.** Email-and-password sign-in, six roles held as
  Django groups, and self-service password reset.
- **Membership.** Two plans — Annual at $45 for 365 days and Life at $650 —
  bought online and activated the instant the payment clears.
- **Profiles.** Contact details, DART (Disaster Airlift Response Team)
  affiliation, pilot certificate, medical, flight review, hours and
  volunteer interests.
- **Aircraft.** One shared register of airframes with insurance carriers,
  limits and expiry dates, which members attach to their own profiles.
- **The leader check.** One screen that answers "may this person fly this
  airplane for us today?" — membership, medical and insurance in a single
  GO / NO-GO verdict.
- **Payments.** Stripe (card, Apple Pay, Google Pay, Link) and PayPal, plus a
  mock provider for demonstrations and tests, with optional donations at
  checkout and month-by-month reporting.
- **Reminders.** Scheduled renewal email at 60, 30 and 7 days before expiry,
  on the day, and 30 days after.
- **Reports.** Membership and aircraft exports as CSV and PDF, payment
  exports as CSV, all with the same filters as the screen you exported them
  from.
- **Content.** Wagtail page types, StreamField blocks, three themes, and a
  members-only wall that only current members and staff get past.
- **Operations.** Health checks, database backups, restore and reset, from
  the command line or the portal.


Requirements
============

Python 3.12, `uv <https://docs.astral.sh/uv/>`_, Node 20+ and npm, Docker
with Compose, and ``make``. No local PostgreSQL client is needed; the
compose stack provides one. The lock file resolves Django 6. See
``docs/developer/configuration.rst`` for every setting ``.env`` accepts.


Setup
=====

.. code-block:: console

   $ make setup     # uv sync, npm ci, copy .env.example to .env
   $ make up        # start Postgres (:5432) and Mailpit (:8025 / :1025)
   $ make migrate   # create the schema and the role groups
   $ make seed      # demo accounts, members, aircraft, payments and content
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

``make seed`` creates these demo accounts, all with the password
``caldart-demo``:

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

Everyday commands:

.. code-block:: console

   $ make test      # pytest + vitest
   $ make e2e       # Playwright, end to end (see below)
   $ make lint      # ruff + mypy + tsc + eslint + prettier + codespell
   $ make check     # system checks, migrations, deployment checks, build
   $ make docs      # Sphinx, nitpicky, warnings are errors
   $ make audit     # known vulnerabilities in Python and npm dependencies
   $ make reset     # destroy and re-seed the dev database
   $ make backup    # gzipped pg_dump into backups/
   $ make help      # every target, one line each

The Make targets table in ``docs/developer/setup.rst`` lists every target in
full.


End-to-end tests
=================

``frontend/e2e`` holds Playwright specs for the five flows of the demo
walkthrough, run with ``make e2e``. See ``docs/developer/testing.rst`` for
the browser install step, environment variables, and how to run or watch a
single spec.


Documentation
=============

.. code-block:: console

   $ make docs

builds the Sphinx documentation into ``docs/_build/html/index.html``; there
is no hosted copy. It covers the user guide (``docs/user/``) for members,
DART leaders and administrators, and the developer guide
(``docs/developer/``) for setup, architecture and the API reference.


Contributing
============

Read ``CLAUDE.md`` for the conventions this repository follows and the
"Before you open a pull request" section of ``docs/developer/setup.rst`` for
the gates every pull request must pass:

.. code-block:: console

   $ make test     # pytest + vitest; a warning fails the run
   $ make lint     # ruff, mypy, tsc, eslint (no warnings), prettier, codespell
   $ make check    # manage.py check, makemigrations --check, npm run build
   $ make docs     # sphinx-build -n -W: nitpicky, warnings are errors
   $ make audit    # uv audit + npm audit: known vulnerabilities

See ``docs/developer/testing.rst`` for how the test suites are organized.


License
=======

Prototype code for CalDART. It carries no license for redistribution.
