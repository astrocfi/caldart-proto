=====================================================
CalDART Website & Member Management System — Master Plan
=====================================================

:Status: authoritative spec for all implementation work
:Audience: implementers (human or agent) and reviewers

This document is the single source of truth for the prototype. Every
feature branch implements a slice of it. If code and this document
disagree, fix one of them in the same PR.

.. contents::
   :depth: 2


1. Goals
========

Build a prototype for **The California DART Network (CalDART)**, a
501(c)(3) that organizes California pilots and ground personnel to
provide volunteer disaster air transportation. Two deliverables:

1. A **public website** with CMS-managed content (home, about, history,
   DARTs, news, join, donate, sponsors, contact, members-only area).
2. A **member management system**: accounts with roles, member profiles
   with pilot/medical data, an aircraft database with insurance data,
   online join/renew with Stripe (card, Apple Pay, Google Pay) and
   PayPal, real-time activation, scheduled renewal reminders, reports
   (PDF/CSV with filters), and admin tooling for accounts, content, and
   system maintenance.

The five *low-friction* flows that must feel effortless, especially on a
phone:

A. Visitor signs up and pays → immediately a current member.
B. Member logs in, edits profile, reads members-only content.
C. DART leader checks a member: membership current? medical current?
   insurance current on the plane they are flying?
D. Account administrator sees payments per month / year.
E. Website administrator adds, edits, deletes pages.

Non-goals for the prototype: backwards compatibility, data migration
from the live site, i18n, auto-renewing subscriptions (documented as
future work).


2. Stack
========

=================  ==========================================================
Layer              Choice
=================  ==========================================================
Language           Python 3.12 (backend), TypeScript (frontend)
Backend            Django 5.x + Wagtail (latest stable) + Django REST
                   Framework + django-filter
Database           PostgreSQL 16 in Docker (``docker compose``), psycopg 3
Frontend           Vite + React 19 + TypeScript (strict) + React Router +
                   TanStack Query. Bundled by Vite, integrated with Django
                   via ``django-vite``.
CMS                Wagtail (page tree, StreamField, images/documents,
                   site settings, editor permissions for website admins)
Payments           Stripe Payment Element (card, Apple Pay, Google Pay),
                   PayPal Orders v2 REST (called with ``httpx``, no SDK),
                   plus a ``mock`` provider for dev/tests
PDF / CSV          reportlab (pure Python) / stdlib ``csv``
Email              Django email; Mailpit in dev (SMTP 1025, UI 8025)
Scheduler          Management command + systemd timer (prod) / ``make``
Web server         Apache 2.4 ``mod_proxy`` → gunicorn (nginx config also
                   shipped as an alternative)
Static files       whitenoise (works identically in dev and behind Apache)
Packaging          ``uv`` (``pyproject.toml`` + committed ``uv.lock``),
                   ``npm`` (``package-lock.json``)
Tests              pytest + pytest-django + factory_boy (backend);
                   vitest + Testing Library (frontend); Playwright (e2e)
Lint               ruff (backend); eslint + tsc --noEmit (frontend)
Docs               Sphinx, RST, ``furo`` theme, under ``docs/``
CI                 GitHub Actions: backend tests (Postgres service),
                   frontend tests + typecheck, docs build
=================  ==========================================================

Why this stack: Django+Wagtail gives us auth, ORM, migrations, admin,
and a real page-editing UI for website administrators for free. DRF
gives a clean JSON API for the TypeScript portal. Keeping the public
site server-rendered by Wagtail and the *portal* as a React SPA is the
lowest-risk split: content editors get preview/history, and the
interactive member flows get a proper app. One shared CSS design system
keeps both halves looking identical.


3. Repository layout
====================

::

  caldart-proto/
    PLAN.rst                      this file
    CLAUDE.md                     agent conventions (keep credentials section)
    README.rst                    quick start
    Makefile                      all dev tasks (see §14)
    docker-compose.yml            name: caldart; services: db, mailpit
    .env.example                  every env var, with dev defaults
    pyproject.toml, uv.lock       backend deps + tool config (ruff, pytest)
    backend/
      manage.py
      caldart/                    Django project
        settings/{base,dev,prod,test}.py
        urls.py                   root: /admin (Wagtail), /django-admin,
                                  /api/v1/ (api_urls), /portal/ (SPA), pages
        api_urls.py               includes every app's api/urls.py
        wsgi.py, asgi.py
      apps/
        accounts/   User, roles, auth API, user-admin API
        members/    Dart, MemberProfile, MembershipPlan, Membership,
                    profile API, admin-members API, membership reports
        aircraft/   Aircraft, aircraft API, exports, leader-check API
        payments/   Payment, providers/, checkout API, webhooks,
                    activation service, payment reports API
        reminders/  ReminderLog, scan command, email templates
        cms/        Wagtail pages, blocks, SiteSettings, templates
        sysadmin/   backup/restore/reset commands, health + backups API
      templates/                  base.html, portal.html, cms/*, emails/*
      tests/                      shared fixtures (conftest.py, factories)
    frontend/
      package.json, vite.config.ts, tsconfig.json, eslint.config.js
      src/
        styles/                   tokens.css, base.css, themes/*.css
        site/main.ts              public-site enhancements (nav, theme)
        portal/
          main.tsx, App.tsx
          api/{client.ts,types.ts}
          routes/*.tsx            one file per feature (see §8)
          features/<feature>/     pages + components + tests
          components/             shared UI primitives
          nav.ts                  role-gated nav definition
      e2e/                        Playwright specs
    docs/                         Sphinx (user/ and developer/)
    deploy/                       apache/, nginx/, systemd/, gunicorn.conf.py
    backups/                      (gitignored) pg_dump output


4. Domain model
===============

All money is stored as integer cents in USD. All dates are ``DateField``
unless noted. Every model has ``created_at``/``updated_at``.

4.1 accounts
------------

``User`` — custom ``AbstractUser``; ``email`` is the login (unique,
case-insensitive); no ``username`` field; ``first_name``, ``last_name``,
``is_active``. Properties: ``roles`` (list of slugs), ``has_role(slug)``,
``membership_status`` (delegates to members), ``can_access_members_content``.

**Roles are Django ``Group`` rows** whose ``name`` is the role slug.
This makes "add a role later" a data change and lets Wagtail reuse the
same groups for editor permissions.

===================  ==================================================
Slug                 Grants
===================  ==================================================
``member``           own profile, own payments/membership, join/renew,
                     members-only content *when membership is current*
``dart_leader``      + look up any member; see membership / medical /
                     certificate / aircraft insurance currency
``user_admin``       + list users, assign roles, activate/deactivate,
                     trigger password reset
``account_admin``    + create/edit/delete members and profiles, grant or
                     extend memberships manually, aircraft CRUD, payment
                     history and payment reports, membership and
                     aircraft reports (CSV/PDF)
``website_admin``    + Wagtail admin: create/edit/delete/publish pages,
                     images, documents, site settings
``system_admin``     everything above + backups, health, reminder run,
                     Django superuser
===================  ==================================================

Rules: ``member`` is granted at registration. Roles are additive.
``system_admin`` implies every other role in permission checks.
``can_access_members_content = membership is current OR user holds any
role other than member``.

Seed: ``manage.py seed_roles`` (idempotent) — also invoked by the
``accounts`` initial data migration.

4.2 members
-----------

``Dart`` — ``name``, ``airport_identifier`` (e.g. ``E16``), ``city``,
``is_active``, ``sort_order``. Seeded with: Angwin, Central Coast,
Contra Costa, Half Moon Bay, Hayward, Livermore, Monterey, Napa,
Palo Alto, Reid-Hillview, San Carlos, San Martin (South County),
Santa Monica, Santa Rosa, Watsonville, Unaffiliated.

``MemberProfile`` — OneToOne ``user``.

*Contact* (mirrors the live join form): ``phone`` (required),
``phone_alt``, ``address_line1``, ``address_line2``, ``city``,
``state`` (2-letter, default CA), ``postal_code``, ``county``
(free text, CA counties offered as suggestions), ``emergency_contact_name``,
``emergency_contact_phone``.

*Aviation*: ``home_airport_identifier``, ``home_airport_city``, ``dart``
(FK Dart, nullable), ``air_care_alliance_number``,
``pilot_certificate_type`` choices ``none | student | sport |
recreational | private | commercial | atp``, ``certificate_number``,
``ifr_rated`` (``na | yes | no``), ``ratings`` (JSON list of strings from
``instrument, multi_engine, cfi, cfii, mei, seaplane, helicopter, glider``),
``medical_type`` choices ``none | basicmed | first | second | third``,
``medical_expiration`` (date, nullable), ``flight_review_date``,
``total_hours`` (int, nullable), ``aircraft`` (M2M ``aircraft.Aircraft``,
"planes commonly flown").

*Volunteer interests* (booleans): ``vol_ground_team``,
``vol_exercise_training``, ``vol_member_support``, ``vol_fundraising``,
``vol_social_media``, ``vol_newsletter``.

*Admin only*: ``notes`` (text), ``how_heard``.

Properties: ``medical_is_current`` (expiration ≥ today; BasicMed and
class medicals both use the stored expiration date; ``none`` → False),
``display_name``.

``MembershipPlan`` — ``name``, ``slug``, ``price_cents``,
``duration_days`` (nullable → lifetime), ``is_active``, ``sort_order``,
``description``. Seeded: **Annual** ($45.00, 365 days), **Life**
($650.00, lifetime).

``Membership`` — one row per paid/granted term. ``user``, ``plan``,
``starts_on``, ``ends_on`` (nullable → lifetime), ``status`` choices
``active | expired | cancelled``, ``source`` choices ``payment | manual |
seed``, ``payment`` (OneToOne to ``payments.Payment``, nullable),
``granted_by`` (FK User, nullable), ``note``.

Membership status service (``members/services.py``)::

  membership_status(user) -> {
      "status": "current" | "expired" | "none",
      "expires_on": date | None,      # None for lifetime
      "plan": "Annual" | "Life" | None,
      "is_lifetime": bool,
  }
  activate_term(user, plan, *, source, payment=None, granted_by=None,
                starts_on=None) -> Membership
      # starts the day after the current expiry if the user is current,
      # else today; ends_on = starts_on + duration_days - 1, or None
      # for lifetime. Idempotent on payment.

4.3 aircraft
------------

``Aircraft`` — ``n_number`` (unique, stored upper-case, without leading
"N" normalised to include it: ``N12345``), ``make``, ``model``, ``year``
(nullable), ``owner_type`` choices ``individual | fbo | club``,
``owner_name``, ``owner_contact`` (email/phone free text), ``seats``,
``insurance_carrier``, ``insurance_policy_number``,
``insurance_liability_per_occurrence_cents``,
``insurance_liability_per_person_cents``, ``insurance_hull_cents``
(nullable), ``insurance_expiration`` (nullable), ``notes``, ``created_by``
(FK User, nullable), ``is_active``.

Properties: ``insurance_is_current`` (expiration ≥ today),
``insurance_summary`` (e.g. "$1,000,000 / $100,000 · exp 2027-03-01").

Members may search the aircraft table and attach any aircraft to their
profile, and may create a new aircraft record if the N-number is
unknown. Members may edit aircraft they created; ``account_admin`` /
``system_admin`` may edit any.

4.4 payments
------------

``Payment`` — ``user``, ``plan`` (FK, nullable for pure donations),
``amount_cents`` (total charged), ``plan_amount_cents``,
``contribution_cents`` (optional donation added at checkout; tiers
offered: $20 Participating, $100 Bronze, $300 Silver, $1,000 Gold,
$3,000 Diamond, $10,000 Platinum, other amount, none), ``currency``
(``usd``), ``provider`` choices ``stripe | paypal | mock``, ``wallet``
choices ``card | apple_pay | google_pay | link | paypal | mock | unknown``
(what Stripe reports as ``payment_method_details.card.wallet.type`` or
``paypal``), ``provider_ref`` (PaymentIntent id / PayPal order id,
unique per provider), ``status`` choices ``pending | succeeded | failed |
refunded``, ``completed_at`` (datetime, nullable), ``raw`` (JSON, last
provider payload), ``membership`` (reverse OneToOne from Membership).

Service ``payments/services.py``::

  create_checkout(user, plan_slug, contribution_cents, provider) -> Payment(pending)
  mark_succeeded(payment, *, wallet, raw) -> Payment
      # idempotent; on first success calls members.activate_term(...)
  mark_failed(payment, raw)

Providers ``payments/providers/{base,stripe,paypal,mock}.py`` implement::

  class Provider:
      slug: str
      def start(self, payment) -> dict          # client-side params
      def confirm(self, payment, **kw) -> bool  # server-side verify → mark_succeeded
      def handle_webhook(self, request) -> HttpResponse

4.5 reminders
-------------

``ReminderLog`` — ``user``, ``membership``, ``kind`` choices
``t60 | t30 | t7 | expired | post30``, ``sent_at``, ``to_email``.

``manage.py send_renewal_reminders [--dry-run] [--today=YYYY-MM-DD]``:
for every user whose membership expiry is exactly 60, 30, or 7 days
ahead, is today (expired), or was 30 days ago, send the matching email
unless a ``ReminderLog`` row already exists for that user/membership/kind.
Also flips ``Membership.status`` to ``expired`` when ``ends_on`` has
passed. Lifetime members are skipped. Emails render from
``templates/emails/reminder_<kind>.{txt,html}`` and link to
``/portal/renew``.

4.6 cms (Wagtail)
-----------------

Page types (all with ``show_in_menus`` used to build the top nav):

- ``HomePage`` — hero (heading, lede, image, primary/secondary CTA),
  mission statement, "concept of operations" StreamField, tax-status
  block, featured news (auto: 3 latest).
- ``StandardPage`` — ``intro``, ``body`` StreamField, ``members_only``.
- ``NewsIndexPage`` / ``NewsPage`` (``date``, ``intro``, ``image``,
  ``body``, ``members_only``).
- ``DartIndexPage`` / ``DartPage`` (``dart`` FK to ``members.Dart``,
  ``leader_name``, ``leader_contact``, ``body``).
- ``ContactPage`` (intro + email/phone/address pulled from settings).

StreamField blocks: ``heading``, ``paragraph`` (rich text), ``image``,
``quote``, ``cta`` (label, URL/page, style), ``document`` (link),
``two_columns``, ``embed``, ``raw_html`` (website_admin only).

``MembersOnlyMixin``: pages with ``members_only=True`` are served only
when ``request.user.can_access_members_content``; otherwise render
``cms/members_only_wall.html`` (login / join / renew CTAs), HTTP 403.
Wagtail's native page privacy remains available on top of this.

``SiteSettings`` (``BaseSiteSetting``): ``org_name``, ``tagline``,
``contact_email``, ``contact_phone``, ``mailing_address``, ``ein``,
``donate_url``, ``facebook_url``, ``twitter_url``, ``theme`` (choice of
the shipped themes, default ``sierra``), ``footer_text``.

Permissions: group ``website_admin`` gets Wagtail "Access the Wagtail
admin" + full page/image/document/settings permissions on the root
collection and root page. ``system_admin`` users are ``is_superuser``.

``manage.py seed_content`` (idempotent) creates the example site: Home,
About Us (History, DARTs index + 16 DART pages, Directors and Officers),
News (3 posts), Join CalDART (CTA into ``/portal/join``), Donate,
Sponsors, Contact Us, Members (members-only: Members Only, Docs/Links).
Text may be paraphrased from caldart.org; it is example content.

4.7 sysadmin
------------

Commands: ``db_backup`` (writes ``backups/caldart-<ts>.sql.gz`` using
``pg_dump`` locally if present, else ``docker compose exec -T db
pg_dump``), ``db_restore <file>``, ``db_reset`` (``DROP SCHEMA public
CASCADE; CREATE SCHEMA public;`` via the Django connection, then
``migrate``, ``seed_roles``, and optionally ``seed_demo`` +
``seed_content`` with ``--seed``), ``health`` (prints DB connectivity,
pending migrations, disk free, last backup).


5. Permission matrix (API)
==========================

Implemented as DRF permission classes in ``accounts/permissions.py``:
``IsAuthenticated``, ``HasRole("dart_leader")``, ``HasAnyRole(...)``.
``system_admin`` always passes. Object-level rules noted in §6.


6. API contract (``/api/v1/``)
==============================

Session authentication (same origin). CSRF: the SPA calls
``GET /api/v1/auth/csrf`` once, then sends ``X-CSRFToken``. All errors
are DRF-standard JSON. Pagination: ``?page=&page_size=`` (default 25,
max 200), response ``{count, next, previous, results}``. Filters use
django-filter query params. Dates ISO-8601.

6.1 auth (accounts)
-------------------

::

  GET  /auth/csrf                      → 204, sets csrftoken cookie
  POST /auth/register                  {email, password, first_name, last_name}
                                       → 201 {user}, logs in, grants role member,
                                         creates empty MemberProfile
  POST /auth/login                     {email, password} → {user}
  POST /auth/logout                    → 204
  GET  /auth/me                        → {user}  (401 if anonymous)
  POST /auth/password/change           {current_password, new_password}
  POST /auth/password/reset            {email} → 204 always (emails link)
  POST /auth/password/reset/confirm    {uid, token, new_password}

  user := {id, email, first_name, last_name, roles: [slug],
           is_active, membership: <membership_status>, profile_complete: bool}

6.2 users admin (accounts) — user_admin
---------------------------------------

::

  GET    /admin/users?search=&role=&is_active=   → paginated [user]
  GET    /admin/users/{id}
  PATCH  /admin/users/{id}                 {roles: [slug], is_active, first_name, last_name, email}
  POST   /admin/users/{id}/send-password-reset
  GET    /roles                            → [{slug, description}]   (any authenticated)

6.3 profile (members) — member
------------------------------

::

  GET  /me/profile            → {profile}   (all MemberProfile fields except admin-only,
                                           aircraft: [aircraft summary], dart: {id,name})
  PUT  /me/profile            full update; PATCH partial
  GET  /me/membership         → {status, expires_on, plan, is_lifetime,
                                 history: [{plan, starts_on, ends_on, status, source}]}
  GET  /me/payments           → [payment summary]
  GET  /darts                 → [{id, name, airport_identifier, city}]  (public)
  GET  /plans                 → [{slug, name, price_cents, duration_days, description}] (public)

6.4 members admin (members) — account_admin
-------------------------------------------

::

  GET    /admin/members?search=&status=current|expired|none&certificate=&medical=
                        &dart=&role=&expiring_within=<days>&ordering=
         → paginated [{user + profile summary + membership_status}]
  POST   /admin/members       {email, first_name, last_name, password?, profile:{...}}
  GET    /admin/members/{user_id}     → full user + profile + memberships + payments
  PATCH  /admin/members/{user_id}     {first_name, last_name, email, is_active, profile:{...}}
  DELETE /admin/members/{user_id}     → 204 (hard delete; prototype)
  POST   /admin/members/{user_id}/memberships   {plan, starts_on?, note}  → grants a term
  PATCH  /admin/memberships/{id}      {ends_on, status, note}
  GET    /admin/members/export.csv?<same filters>
  GET    /admin/members/export.pdf?<same filters>   (landscape, letter)

6.5 aircraft — member (read/create), account_admin (all)
--------------------------------------------------------

::

  GET    /aircraft?search=&make=&owner_type=&insurance=current|expired|missing
                  &expiring_within=<days>&ordering=      → paginated
  POST   /aircraft                    (any member; created_by = user)
  GET    /aircraft/{id}
  PATCH  /aircraft/{id}               (creator or account_admin)
  DELETE /aircraft/{id}               (account_admin)
  GET    /aircraft/lookup?n_number=N12345   → exact match or 404 (any authenticated)
  POST   /me/profile/aircraft         {aircraft_id}  attach ; DELETE .../{aircraft_id} detach
  GET    /admin/aircraft/export.csv?<filters>
  GET    /admin/aircraft/export.pdf?<filters>

6.6 leader check (aircraft app) — dart_leader
---------------------------------------------

::

  GET /leader/search?q=<name|email|n-number>   → [{user_id, name, email, dart,
                                                   membership_status}]  (max 20)
  GET /leader/members/{user_id}/status →
      {name, email, phone, dart,
       membership: {status, expires_on, plan},
       certificate: {type, number, ifr_rated, ratings},
       medical: {type, expiration, is_current},
       aircraft: [{id, n_number, make, model, insurance_is_current,
                   insurance_expiration, insurance_summary}],
       go_no_go: {membership: bool, medical: bool}}
  GET /leader/aircraft?n_number=   → aircraft status card (any N-number in DB)

6.7 payments
------------

::

  GET  /payments/config      → {providers: ["stripe","paypal","mock"],
                                stripe_publishable_key, paypal_client_id,
                                plans: [...], contribution_tiers: [...]}
  POST /payments/checkout    {plan: slug, contribution_cents, provider}
                             → {payment_id, provider, client: {...}}
          stripe → client: {client_secret}
          paypal → client: {order_id}
          mock   → client: {}
  POST /payments/stripe/confirm   {payment_id, payment_intent_id}
          server retrieves the PaymentIntent, verifies amount + status
          "succeeded", marks succeeded → membership active immediately
  POST /payments/paypal/capture   {payment_id, order_id}
          server captures the order; on COMPLETED marks succeeded
  POST /payments/mock/complete    {payment_id, outcome: "succeed"|"fail"}
          only when PAYMENTS_MOCK_ENABLED
  POST /payments/stripe/webhook   (Stripe-Signature verified; handles
          payment_intent.succeeded / payment_failed idempotently)
  POST /payments/paypal/webhook   (optional; capture is authoritative)
  GET  /payments/{payment_id}     → {status, membership: <membership_status>}

6.8 payment reports (payments) — account_admin
----------------------------------------------

::

  GET /admin/payments?from=&to=&provider=&status=&search=&ordering=  → paginated
  GET /admin/payments/summary?group=month|year&from=&to=
      → [{period: "2026-03", count, total_cents, plan_cents, contribution_cents,
          by_provider: {stripe: cents, paypal: cents, mock: cents}}]
  GET /admin/payments/export.csv?<filters>

6.9 reminders & system — system_admin (log also account_admin)
--------------------------------------------------------------

::

  GET  /admin/reminders/log?kind=&from=&to=          → paginated
  POST /system/reminders/run   {dry_run: bool}       → {sent: n, skipped: n}
  GET  /system/health           → {db: "ok", pending_migrations: n, disk_free_mb,
                                   last_backup, version, debug}
  GET  /system/backups          → [{name, size_bytes, created_at}]
  POST /system/backups          → creates one, returns its entry
  GET  /system/backups/{name}/download  → application/gzip

6.10 site
---------

::

  GET /site/config              → {org_name, theme, contact_email, nav: [...],
                                   members_pages: [{title, url}] (only when the
                                   caller can access members content)}


7. Frontend: public site
========================

Server-rendered Wagtail templates under ``backend/templates/cms/``.
``base.html`` loads ``{% vite_asset 'src/site/main.ts' %}`` which
imports the global CSS (tokens, base, themes, fonts) and registers small
behaviours: mobile nav toggle, theme attribute from ``SiteSettings``,
"skip to content". Top nav = menu pages + ``Join`` (→ ``/portal/join``)
+ ``Login`` / ``Members`` (→ ``/portal/``).


8. Frontend: portal SPA
=======================

Mounted at ``/portal/`` by Django view ``portal_shell`` rendering
``portal.html`` with ``{% vite_asset 'src/portal/main.tsx' %}`` and
``<html data-theme="...">``. React Router (browser history, basename
``/portal``). Data via TanStack Query over ``api/client.ts`` (fetch,
credentials same-origin, CSRF header, JSON errors → typed ``ApiError``).

Route ownership (one file per feature in ``src/portal/routes/``; each
exports ``RouteObject[]``; ``routes/index.tsx`` concatenates them):

===================  =====================================================
File                 Routes
===================  =====================================================
``auth.tsx``         ``/login``, ``/logout``, ``/forgot-password``,
                     ``/reset-password``, ``/change-password``
``join.tsx``         ``/join`` (wizard: account → profile → pay → done),
                     ``/renew``
``dashboard.tsx``    ``/`` (member home: status card, renew CTA, quick links,
                     members-only pages list)
``profile.tsx``      ``/profile`` (edit), ``/profile/aircraft`` (attach/create)
``leader.tsx``       ``/leader`` (search + status card), ``/leader/aircraft``
``admin-members.tsx`` ``/admin/members``, ``/admin/members/new``,
                     ``/admin/members/:id``
``admin-aircraft.tsx`` ``/admin/aircraft``, ``/admin/aircraft/:id``
``admin-payments.tsx`` ``/admin/payments`` (summary + table + export)
``admin-users.tsx``  ``/admin/users``, ``/admin/users/:id``
``system.tsx``       ``/system`` (health, backups, reminders)
===================  =====================================================

``nav.ts`` defines every nav entry with its required role(s) up front so
feature work never edits it. ``components/`` holds shared primitives:
``Page``, ``Card`` (flat, hairline border), ``Field``, ``Button``,
``StatusChip`` (current/expiring/expired/none), ``DataTable`` (sortable,
with filter bar + CSV/PDF export buttons), ``Money``, ``DateText``,
``EmptyState``, ``Toast``.

Route guards: ``RequireAuth``, ``RequireRole(...)``. Unauthenticated →
``/login?next=``. Wrong role → 403 page.


9. Design system & theming
==========================

The brief: *clean, modern, editorial; not the generic AI-site look.* No
purple/indigo gradients, no glassmorphism, no floating rounded cards
with drop shadows on every element, no hero blobs, no emoji bullets.

- **Layout**: generous whitespace, a 12-column grid with deliberate
  asymmetry (text columns 7/12, sidebars 4/12), hairline rules
  (``1px`` in ``--color-rule``) instead of boxes, near-square corners
  (``--radius: 2px``). Sections separated by rules and spacing, not by
  background-colour bands.
- **Type**: display/headings in *Fraunces* (variable serif, optical
  size), body in *IBM Plex Sans*, data (N-numbers, certificate numbers,
  money, dates in tables) in *IBM Plex Mono*. All self-hosted via
  ``@fontsource`` packages so the site works offline. Big, confident
  headings; tight leading; small caps eyebrow labels.
- **Colour tokens** live in ``styles/tokens.css`` and each theme in
  ``styles/themes/<name>.css`` overriding them under
  ``:root[data-theme="<name>"]``. Ship three:

  ``sierra`` (default): paper ``#F4F1EA``, ink ``#1B1F24``, primary deep
  conifer ``#1F4D3A``, accent signal orange ``#E4572E``, secondary
  poppy gold ``#F2A900``, rule ``#D9D3C7``, muted ``#6B6F76``.

  ``pacific``: paper ``#F6F7F5``, ink ``#14212B``, primary deep pacific
  ``#0F3D5C``, accent ``#E4572E``, secondary fog ``#8DA9B8``.

  ``night`` (dark): paper ``#151719``, ink ``#ECE9E1``, primary
  ``#7FB69B``, accent ``#FF7A52``, secondary ``#F2C14E``.

  Status colours: ok ``#2E7D4F``, warn ``#C98A00``, bad ``#B23A2B``.
- Semantic tokens only in components (``--color-bg``, ``--color-fg``,
  ``--color-primary``, ``--color-accent``, ``--color-rule``,
  ``--color-muted``, ``--color-ok/warn/bad``, ``--font-display``,
  ``--font-body``, ``--font-mono``, ``--radius``, ``--space-1..8``,
  ``--measure``). Changing the theme = editing one file or picking
  another in Wagtail Site Settings; documented in
  ``docs/developer/theming.rst``.
- Respect ``prefers-reduced-motion``; focus rings always visible;
  colour contrast ≥ 4.5:1 for text.


10. Payments architecture
=========================

- **Stripe**: server creates a PaymentIntent (``automatic_payment_methods``)
  for ``amount_cents`` with metadata ``{payment_id, user_id, plan}``.
  Client mounts Payment Element (card + Apple Pay + Google Pay + Link
  appear automatically when eligible) and calls ``stripe.confirmPayment``
  with ``redirect: "if_required"`` and ``return_url=/portal/join/done``.
  On success the client POSTs ``/payments/stripe/confirm`` → server
  verifies with Stripe → membership activated *now*. The webhook is a
  safety net (e.g. redirect-based methods) and is idempotent.
- **PayPal**: client loads the JS SDK with the client id; ``createOrder``
  calls ``/payments/checkout`` (provider paypal) which creates the order
  server-side (``intent=CAPTURE``); ``onApprove`` calls
  ``/payments/paypal/capture``; server captures and activates.
- **Apple Pay / Google Pay** come through Stripe's Payment Element. Apple
  Pay additionally needs the domain registered in the Stripe dashboard
  and ``/.well-known/apple-developer-merchantid-domain-association``
  served (Django view reading ``STRIPE_APPLE_PAY_DOMAIN_ASSOCIATION``
  file path). Google Pay needs nothing extra in test mode.
- **Mock** provider (``PAYMENTS_MOCK_ENABLED``, on in dev/test, off in
  prod): renders "Succeed" / "Fail" buttons. Used by e2e tests and by
  anyone without payment keys.
- Amount safety: the server never trusts a client amount; totals are
  recomputed from plan + contribution.
- Renewal uses the same checkout with ``/portal/renew``; the new term
  starts the day after the current expiry.


11. Reports
===========

Membership report (account_admin): filters as in §6.4; CSV columns:
name, email, phone, dart, status, plan, expires_on, certificate,
certificate_number, ifr, medical_type, medical_expiration, aircraft
(N-numbers joined), city, state, joined_on. PDF: landscape letter,
title + filter summary + generated timestamp, zebra rows, repeated
header, page numbers. Aircraft report: n_number, make, model, owner,
owner_type, insurance carrier, liability limits, hull, expiration,
current?, pilots (member names). Payments: table export + summary by
period. Shared helpers in ``backend/caldart/reports.py`` (CSV streaming
response, reportlab table builder with house style).


12. Reminders scheduling
========================

Prod: ``deploy/systemd/caldart-reminders.timer`` runs
``manage.py send_renewal_reminders`` daily at 07:00. Dev: ``make
reminders`` (optionally ``TODAY=2027-01-01``). System admins can also
trigger from ``/portal/system``.


13. Deployment (a machine like this one)
========================================

- Postgres: ``docker compose up -d db`` (volume ``caldart_pgdata``).
- App: ``uv sync --frozen``; ``npm ci && npm run build``; ``manage.py
  migrate collectstatic``; gunicorn via ``deploy/systemd/caldart-web.service``
  listening on ``127.0.0.1:8001``.
- Apache: ``deploy/apache/caldart.conf`` — VirtualHost with
  ``ProxyPass / http://127.0.0.1:8001/``, ``ProxyPreserveHost On``,
  ``RequestHeader set X-Forwarded-Proto``, TLS via certbot, plus
  ``Alias /media/``. (nginx equivalent in ``deploy/nginx/``.)
- Settings ``prod.py``: ``SECURE_PROXY_SSL_HEADER``, ``ALLOWED_HOSTS``
  from env, ``CSRF_TRUSTED_ORIGINS``, whitenoise, email via SMTP URL.
- Documented in ``docs/developer/deployment.rst``.


14. Developer workflow (Makefile targets)
=========================================

::

  make setup      uv sync + npm ci + copy .env.example → .env if missing
  make up/down    docker compose up -d db mailpit / down
  make migrate    manage.py migrate
  make seed       seed_roles + seed_demo + seed_content
  make reset      db_reset --seed   (destroys the dev database)
  make run        Django on :8000 (+ prints how to run `make dev-frontend`)
  make dev-frontend   vite dev server on :5173 (HMR)
  make build      npm run build (production assets)
  make test       backend + frontend unit tests
  make test-backend / test-frontend / e2e
  make lint       ruff + eslint + tsc
  make backup / restore FILE=... / reminders [TODAY=...]
  make docs       sphinx-build -W docs docs/_build/html

Demo accounts created by ``seed_demo`` (password ``caldart-demo``):
``member@example.org``, ``expired@example.org``, ``leader@example.org``,
``useradmin@example.org``, ``accountadmin@example.org``,
``webadmin@example.org``, ``sysadmin@example.org`` (superuser), plus
~40 generated members with mixed statuses, ~25 aircraft, and 24 months
of payments.

Env vars (``.env.example`` is the reference): ``DATABASE_URL``,
``SECRET_KEY``, ``DEBUG``, ``ALLOWED_HOSTS``, ``SITE_URL``,
``EMAIL_URL``, ``DEFAULT_FROM_EMAIL``, ``STRIPE_PUBLISHABLE_KEY``,
``STRIPE_SECRET_KEY``, ``STRIPE_WEBHOOK_SECRET``,
``STRIPE_APPLE_PAY_DOMAIN_ASSOCIATION``, ``PAYPAL_CLIENT_ID``,
``PAYPAL_CLIENT_SECRET``, ``PAYPAL_ENV`` (``sandbox``/``live``),
``PAYMENTS_MOCK_ENABLED``, ``DJANGO_VITE_DEV_MODE``, ``BACKUP_DIR``,
``DB_BACKUP_VIA_DOCKER``.


15. Testing strategy
====================

- Backend: pytest-django against Postgres. Factories for every model.
  Cover: role helpers and permission classes (every endpoint × role
  matrix at least for allow/deny), membership status math (edge dates,
  lifetime, renewal start-day rule), profile API, aircraft API + N-number
  normalisation, leader status card, checkout → confirm → activation for
  each provider (Stripe/PayPal HTTP mocked with ``respx``; webhook
  signature), idempotency of success, reminder scanner kinds + dedupe
  (``freezegun``), CSV/PDF exports (content + filters), CMS members-only
  wall, seed commands run twice cleanly, backup/reset commands (tmp dir).
- Frontend: vitest + Testing Library + msw for: auth flow, join wizard
  steps, profile form validation, leader search/status card, data table
  filters + export links, admin payments summary rendering, route guards.
- E2E (Playwright, ``make e2e``, mock provider): the five flows in §1.
- CI runs backend + frontend + docs (``-W``) on every PR.


16. Documentation (Sphinx, RST)
===============================

``docs/index.rst`` → ``user/`` (getting started, member guide, DART
leader guide, account administrator guide, website administrator guide,
system administrator guide, FAQ) and ``developer/`` (architecture,
setup, configuration, payments-setup [Stripe / PayPal / Apple Pay /
Google Pay accounts and test cards], data model, API reference, theming,
testing, deployment, backup-restore, roadmap). ``PLAN.rst`` is included
via ``.. include::``.


17. Work breakdown, branches, and merge order
=============================================

Phase 1 — ``feat/foundation`` (sequential; everything depends on it)
  Scaffolding, all models + initial migrations, roles, seed_demo,
  settings, Makefile, docker-compose, django-vite + Vite/React scaffold,
  design tokens + three themes + fonts, portal shell with route stubs,
  nav, shared components, API client + types, permission classes, CI,
  Sphinx skeleton, deploy skeleton, CLAUDE.md conventions.

Phase 2 — parallel feature branches (each owns the files listed; do not
edit other owners' files; rebase on ``origin/main`` before opening PR)

  ``feat/auth-portal``      accounts API (auth, users admin), portal auth
                            pages, guards, ``routes/auth.tsx``,
                            ``routes/admin-users.tsx``, ``features/auth``,
                            ``features/admin-users``
  ``feat/profile-join``     members profile API, ``routes/join.tsx``,
                            ``routes/dashboard.tsx``, ``routes/profile.tsx``,
                            ``features/join``, ``features/dashboard``,
                            ``features/profile`` (aircraft attach UI calls
                            aircraft API per §6.5)
  ``feat/payments``         payments app (providers, checkout, webhooks,
                            reports API), ``features/checkout`` (reusable
                            ``<Checkout/>`` used by join/renew),
                            ``routes/admin-payments.tsx``,
                            ``features/admin-payments``, payments docs
  ``feat/aircraft-leader``  aircraft app (API, exports, leader API),
                            ``routes/leader.tsx``, ``routes/admin-aircraft.tsx``,
                            ``features/leader``, ``features/admin-aircraft``
  ``feat/members-admin``    members admin API + CSV/PDF reports,
                            ``caldart/reports.py``,
                            ``routes/admin-members.tsx``,
                            ``features/admin-members``
  ``feat/cms-site``         cms app (pages, blocks, settings, templates,
                            members-only wall, seed_content, Wagtail
                            perms), ``src/site/``, public templates,
                            ``/site/config`` endpoint
  ``feat/ops``              reminders app + emails, sysadmin app
                            (commands + API), ``routes/system.tsx``,
                            ``features/system``, ``deploy/``, ops docs

Phase 3 — after all Phase 2 PRs are merged
  ``feat/integration-qa``   full-suite run, cross-feature fixes, Playwright
                            e2e for the five flows, seed sanity, README
  ``feat/docs``             complete user + developer docs

Conventions
  - Branch from fresh ``origin/main``; small focused commits; each
    commit message ends with the Co-Authored-By / Claude-Session
    trailers required by the session.
  - Each PR: description with what/why/how-tested; all tests green
    locally (``make test``); ``make lint`` clean; docs stubs for the
    feature added under ``docs/``.
  - Per-worker database: ``DATABASE_URL=postgres://caldart:caldart@
    localhost:5432/caldart_<branch-slug>`` so parallel test runs never
    collide (Django names the test DB ``test_caldart_<slug>``).
  - No backwards-compatibility shims. Change the schema freely; regenerate
    migrations rather than stacking fix-ups where it keeps things clean.
