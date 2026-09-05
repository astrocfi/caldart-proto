=============================================
CalDART — website and member management system
=============================================

A prototype for **The California DART Network**: a Wagtail-managed public
website plus a React member portal with roles, profiles, an aircraft
register, online join/renew, renewal reminders and admin reporting.

``PLAN.rst`` is the authoritative specification. If the code and the plan
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

=============================  ============================================
URL                            What it is
=============================  ============================================
http://localhost:8000/         public site (Wagtail)
http://localhost:8000/portal/  member portal (React SPA)
http://localhost:8000/admin/   Wagtail admin
http://localhost:8000/django-admin/  Django admin
http://localhost:8025/         Mailpit — every email sent in development
=============================  ============================================

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
   $ make lint           # ruff + tsc + eslint + prettier
   $ make docs           # Sphinx, warnings are errors
   $ make reset          # destroy and re-seed the dev database
   $ make backup         # gzipped pg_dump into backups/
   $ make help           # every target

Run ``make help`` for the full list.


Layout
======

::

   backend/     Django + Wagtail (caldart project, apps/, templates/, tests/)
   frontend/    Vite + React + TypeScript (public-site JS and the portal SPA)
   docs/        Sphinx documentation (user/ and developer/)
   deploy/      gunicorn, systemd, Apache and nginx configuration
   PLAN.rst     the specification
   CLAUDE.md    conventions for working in this repository


Licence
=======

Prototype code for CalDART. Not yet licensed for redistribution.
