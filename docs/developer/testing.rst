=======
Testing
=======

Three suites, all of which must be green before a pull request is opened, and
all of which CI runs on every push to ``main`` and every pull request:

.. list-table::
   :header-rows: 1
   :widths: 22 22 56

   * - Suite
     - Command
     - What it covers
   * - Backend
     - ``make test-backend``
     - pytest-django against a real PostgreSQL, in ``backend/tests/``
   * - Frontend
     - ``make test-frontend``
     - vitest + Testing Library + msw, beside the code they test
   * - End-to-end
     - ``make e2e``
     - Playwright through a real browser against a running application

``make test`` runs the first two.  ``make e2e`` is separate because it needs a
built frontend, a seeded database and a browser.

Running the backend suite
=========================

.. code-block:: console

   $ make test-backend                                   # everything
   $ uv run pytest                                       # the same thing
   $ uv run pytest backend/tests/test_payments_stripe.py # one module
   $ uv run pytest -k "leader and insurance"             # by name
   $ uv run pytest -x --ff                               # stop at the first failure, failures first

Configuration lives in ``pyproject.toml`` under ``[tool.pytest.ini_options]``:
``DJANGO_SETTINGS_MODULE = "caldart.settings.test"``, ``pythonpath =
["backend"]``, ``testpaths = ["backend/tests"]``, ``addopts = "-ra
--strict-markers --strict-config"``, and a ``filterwarnings`` list that starts
with ``"error"``. You never need to set ``DJANGO_SETTINGS_MODULE`` yourself, an
undeclared marker or a mistyped setting is an error rather than a silent typo,
and any warning is a test failure. Fix a warning that comes from our own code.
Silence one from a third-party package only with a narrow ``ignore:`` entry
after ``"error"`` and a comment saying why, as the entry for WhiteNoise's
missing-``STATIC_ROOT`` warning does.

**The tests need Postgres.**  ``make up`` must have run.  Django creates
``test_<the database in DATABASE_URL>``, so a worktree using
``caldart_payments`` tests against ``test_caldart_payments`` and two branches
can run ``pytest`` at the same time without colliding.  Add ``--reuse-db`` if
you are iterating and the schema has not changed.

What ``caldart.settings.test`` changes
--------------------------------------

- ``PASSWORD_HASHERS`` is MD5 — the single biggest speed-up in a suite that
  creates hundreds of users.
- ``EMAIL_BACKEND`` is ``locmem``, so ``django.core.mail.outbox`` is what you
  assert against and nothing leaves the process.
- Every entry in ``AUTH_THROTTLE_RATES`` is set to ``None``, which makes the
  auth throttles inert.  The throttling test turns one back on with
  ``override_settings`` rather than having every other test race a shared
  counter.
- ``PAYMENTS_MOCK_ENABLED`` is on; ``DEBUG`` is off; storage is in-memory;
  logging is quietened to ``ERROR``.

The Vite manifest
-----------------

``templates/base.html`` and ``templates/portal.html`` call ``{% vite_asset %}``,
which raises when the entry is missing from the manifest.  Backend tests must
not depend on ``npm run build`` having been run — CI runs the two suites in
separate jobs — so ``conftest.py`` writes a stub manifest in
``pytest_configure`` when there is no real one, forces django-vite to re-read
it (its ``AppConfig.ready()`` caches the loader during ``django.setup()``,
before the hook runs), and removes the stub again in ``pytest_unconfigure``.

A test that genuinely needs the real bundle asks for the ``frontend_is_built``
fixture, which is ``False`` when the manifest is the stub.

Fixtures
--------

``backend/tests/conftest.py`` holds everything shared.  The ones you will reach
for constantly:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Fixture
     - What you get
   * - ``api_client``
     - an unauthenticated DRF ``APIClient``; sign in with
       ``api_client.force_login(user)``
   * - ``csrf_client``
     - the same client with ``enforce_csrf_checks=True``, for tests that must
       see a missing CSRF token
   * - ``csrf_headers``
     - ``csrf_headers(client)`` fetches ``GET /auth/csrf`` and returns the
       ``{"HTTP_X_CSRFTOKEN": …}`` kwargs an unsafe method needs
   * - ``member``, ``dart_leader``, ``user_admin``, ``account_admin``,
       ``website_admin``, ``system_admin``
     - one ``User`` per role, each also holding ``member``
   * - ``leader``
     - an alias for ``dart_leader``, the name most tests use
   * - ``superuser``
     - ``is_superuser=True`` as well as the ``system_admin`` role
   * - ``anonymous_user``
     - a signed-up user with **no** roles at all
   * - ``all_role_users``
     - a ``{slug: user}`` dict, for allow/deny matrix tests
   * - ``annual_plan``, ``life_plan``
     - the two seeded plans
   * - ``dart``, ``profile``, ``aircraft``
     - a Palo Alto DART, a profile for ``member``, one insured aeroplane
   * - ``home_page``, ``site_settings``
     - a Wagtail tree with a home page, and the settings row
   * - ``today``, ``days``
     - ``timezone.localdate()`` and ``days(7) -> timedelta(days=7)``, to keep
       date arithmetic readable

An autouse ``_roles`` fixture runs ``seed_roles()`` for every test, so the six
groups always exist exactly as ``migrate`` leaves them.  The factory classes
themselves are also exposed as fixtures — ``user_factory``,
``payment_factory``, ``membership_factory``, ``aircraft_factory``,
``profile_factory``, ``reminder_log_factory`` — for tests that need many rows.

Writing tests with the factories
--------------------------------

``backend/tests/factories.py`` has a ``factory_boy`` factory per model.  Most
use ``django_get_or_create``, so asking twice for the same key returns the same
row instead of a unique-constraint error.

.. code-block:: python

   import pytest
   from tests.factories import MembershipFactory, UserFactory

   pytestmark = pytest.mark.django_db

   def test_a_lapsed_term_reads_as_expired(annual_plan, today, days):
       user = UserFactory(email="lapsed@example.test", roles=["member"])
       MembershipFactory(
           user=user,
           plan=annual_plan,
           starts_on=today - days(400),
           ends_on=today - days(35),
       )
       assert user.membership_status["status"] == "expired"

Things worth knowing about the factories:

- ``UserFactory`` takes ``roles=[...]`` as a post-generation hook and sets
  ``DEFAULT_PASSWORD`` (``"test-password-123"``, also available as the
  ``password`` fixture) unless you pass ``password="…"``.
- ``MembershipFactory`` computes ``ends_on`` from the plan
  (``starts_on + duration_days - 1``, ``None`` for a lifetime plan), so a
  correct term is one line.  Its ``source`` defaults to ``seed``.
- ``AircraftFactory`` produces an insured aeroplane — expiry 200 days out —
  so "insurance current" is the default and you opt into the awkward cases.
- ``PaymentFactory`` defaults to the ``mock`` provider with status
  ``pending``; drive it through ``payments.services.mark_succeeded`` rather
  than setting ``status`` by hand, or you will not get the membership term.
- ``make_home_page()`` and ``make_site_settings(**kwargs)`` build the minimum
  Wagtail tree, which several CMS tests need.

Conventions
-----------

- **All backend tests live in ``backend/tests/``**, named
  ``test_<feature>.py``.  There are no per-app ``tests/`` packages, so parallel
  branches never touch the same file.
- **Every endpoint gets an allow *and* a deny test** for each role that matters
  — see the matrix in :doc:`api-reference`.  ``all_role_users`` plus
  ``pytest.mark.parametrize`` keeps that to a few lines.
- **CSRF is enforced in one place and pinned in one place.**  ``api_client``
  skips the check so most tests stay short.  ``backend/tests/test_csrf.py``
  uses ``csrf_client`` to hold the real contract: every unsafe method is
  refused without a token, anonymous ones included, and the payment webhooks
  still need none.
- **Mock at the boundary, never inside.**  Stripe is faked at the SDK
  boundary: the ``fake_intents`` fixture replaces the provider's
  ``stripe_client`` factory, and the stand-in client's
  ``v1.payment_intents.create`` / ``.retrieve`` answer with real
  ``stripe.PaymentIntent`` objects built by ``construct_from``, so the provider
  meets the types the library really returns.  Patch the factory, not
  ``stripe.PaymentIntent``: the provider never calls the module-level helpers.
  Webhook bodies are signed with ``STRIPE_WEBHOOK_SECRET`` exactly as Stripe
  signs them and ``stripe.Webhook.construct_event`` verifies them for real;
  nothing patches the signature check.  PayPal, which is called over ``httpx``
  with no SDK, is exercised with ``respx`` intercepting the HTTP.  Neither
  provider module is stubbed out.
- **Freeze the clock rather than computing around it.**  The reminder scanner's
  tests use ``freezegun`` to land exactly on each offset and to check the day
  either side stays silent.
- **Two implementations of one rule get a test that compares them.**
  ``test_members_admin_status.py`` builds fourteen membership histories and
  asserts the Python service and its SQL restatement agree on every one.  If
  you touch either, add a history there.

What the backend suite covers
-----------------------------

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Module
     - Subject
   * - ``test_roles_permissions.py``
     - role helpers and the DRF permission classes
   * - ``test_server_controlled_fields.py``
     - roles, the Django flags, ownership, membership provenance and payment
       amounts are ignored when a request body sends them
   * - ``test_accounts_auth.py``, ``test_auth_api.py``
     - register, login, logout, password change and reset, throttling
   * - ``test_users_admin_api.py``
     - the ``user_admin`` endpoints, role edits and their guards
   * - ``test_membership_services.py``
     - status math: edge dates, lifetime, the renewal start-day rule
   * - ``test_profile_api.py``, ``test_profile_aircraft_api.py``
     - ``/me/profile``, ``PUT`` versus ``PATCH``, attach and detach
   * - ``test_members_admin.py``, ``test_members_admin_status.py``
     - the admin list, its filters, and SQL-versus-service agreement
   * - ``test_members_reports.py``, ``test_aircraft_exports.py``,
       ``test_payments_reports.py``, ``test_reports.py``
     - CSV content cell by cell, PDF validity, and filter propagation
   * - ``test_aircraft_api.py``, ``test_aircraft_models.py``
     - N-number normalization, filters, orderings, object permissions
   * - ``test_leader_api.py``
     - search, the status card, and the membership × medical × insurance
       truth table
   * - ``test_payments_api.py``, ``…_stripe.py``, ``…_paypal.py``,
       ``…_mock_provider.py``, ``…_apple_pay.py``
     - checkout → confirm → activation for each provider, webhook signatures,
       amount and currency mismatches, idempotency
   * - ``test_reminders.py``, ``test_reminders_api.py``
     - each kind on its exact offset, dedupe, dry runs, skip reasons
   * - ``test_cms_pages.py``, ``…_permissions.py``, ``…_seed_content.py``,
       ``test_cms_documents.py``, ``test_site_config.py``
     - page types, blocks, the members-only wall in every visitor state,
       the document guard and the proxy rules behind it, editor permissions,
       and the seeded tree
   * - ``test_sysadmin*.py``
     - backup, restore, reset, health, the production settings module
   * - ``test_seed.py``, ``test_shell_views.py``
     - the seed commands run twice cleanly; the portal and public shells

Running the frontend suite
==========================

.. code-block:: console

   $ make test-frontend                 # vitest run, once
   $ cd frontend && npm run test:watch  # watch mode
   $ cd frontend && npx vitest run src/portal/features/join

Configuration is the ``test`` key in ``frontend/vite.config.ts``: the ``jsdom``
environment, globals on, ``src/test/setup.ts`` as the setup file, CSS
processing off, and ``src/**/*.{test,spec}.{ts,tsx}`` as the include pattern.

**Tests sit beside what they test** — ``LoginPage.test.tsx`` next to
``LoginPage.tsx`` — so a feature's tests move with it.

**Every render runs in StrictMode.**  ``src/test/setup.ts`` calls
``configure({reactStrictMode: true})``, so Testing Library wraps each render in
``<StrictMode>`` exactly as ``src/portal/main.tsx`` wraps the portal.  React
then runs every effect as setup, cleanup, setup, which means **an effect must
tolerate running twice** or its test fails.  Make the effect undo its own work
in the cleanup — abort the request with an ``AbortController``, clear the timer
— rather than guarding it with a ref: a ref outlives the cycle, so the second
setup does nothing while the first one's cleanup has already canceled its
work.

Two helpers do the heavy lifting:

``src/test/render.tsx``
    ``renderWithProviders(ui, {route})`` wraps a component in the providers the
    portal really uses — a fresh ``QueryClient`` with retries off and no
    caching between tests, the ``ToastProvider``, and a ``MemoryRouter``
    started at ``route``.  Render through it rather than Testing Library's bare
    ``render``, or anything using a query or a toast will throw.

    ``renderRoutes(routes, {route})`` mounts a whole route table instead of one
    component: the same providers around a memory data router, so the layout,
    the guards and each route's ``lazy`` loader all take part.  It returns the
    router alongside the render result, which is how a test reads the location
    a guard redirected to.

``src/test/server.ts`` and ``handlers.ts``
    An `msw <https://mswjs.io/>`_ server with default handlers for the common
    endpoints.  ``src/test/setup.ts`` starts it with
    ``onUnhandledRequest: "error"``, so **a request your test did not stub is a
    failure, not a silent 404** — which is exactly what you want when a
    component quietly starts calling a new endpoint.

    Override per test with ``server.use(...)``.  After each test the handlers,
    the cookies and the client's CSRF bootstrap all reset, so no test inherits
    another's token.  The default ``GET /auth/csrf`` handler sets
    ``csrftoken=test-csrf-token`` exactly as the real endpoint sets a cookie,
    which means a mutation genuinely carries ``X-CSRFToken`` and a test can
    assert on it.

.. code-block:: tsx

   import { http, HttpResponse } from 'msw';
   import { screen } from '@testing-library/react';

   import { renderWithProviders } from '../../../test/render';
   import { server } from '../../../test/server';
   import { DashboardPage } from './DashboardPage';

   it('nudges a member whose profile is incomplete', async () => {
     server.use(
       http.get('/api/v1/auth/me', () =>
         HttpResponse.json({ /* … */ profile_complete: false }),
       ),
     );
     renderWithProviders(<DashboardPage />);
     expect(await screen.findByText(/finish your profile/i)).toBeInTheDocument();
   });

Query by role and by accessible name wherever you can
(``getByRole("button", {name: /save/i})``).  The design system is built for
keyboard and screen-reader use, and a test that goes through the accessibility
tree keeps it that way.

What the frontend suite covers
------------------------------

The API client and its error mapping; the route guards, and the real route
table opened at every guarded path by an anonymous visitor and by a user
holding each role, so a guard that loses a role fails a case, plus the order a
guard and an on-demand page resolve in; the shared
``DataTable`` and ``StatusChip``; the auth pages; the join wizard's step
progression, resume and clamp rules; profile form conversion and validation;
the aircraft picker's search, exclude and create paths; the leader search and
status card in each verdict state; every admin screen's filters, paging, export
links and save paths; the payments summary's headline tiles and its table by
month and by year; the checkout with the Stripe and PayPal SDKs mocked; and
the four system panels.

End-to-end tests
================

.. code-block:: console

   $ make e2e                    # playwright test
   $ cd frontend && npx playwright test --ui

Playwright drives a real browser against a real server, and covers the five
low-friction flows the system is built around (:doc:`architecture`) — the
same ones the :doc:`../demo-walkthrough` walks a person through:

1. a visitor signs up and pays and is immediately a current member;
2. a member signs in, edits their profile and reads members-only content;
3. a DART leader checks a member's membership, medical and aircraft insurance;
4. an account administrator sees payments per month and per year;
5. a website administrator adds, edits and deletes a page.

The specs live in ``frontend/e2e/``, alongside ``playwright.config.ts``.  They
use the **mock** payment provider, so no keys are needed and no money moves;
``PAYMENTS_MOCK_ENABLED`` must be on, which it is by default in development.

``make e2e`` is self-contained: it creates its own database, runs
``db_reset --seed`` against it, builds the production assets, starts Django on
its own port with the mock provider enabled, runs the specs, and stops the
server again — so it never touches your development database.  The first run
on a machine needs the browser: ``cd frontend && npx playwright install
chromium`` (on a bare machine add ``npx playwright install-deps chromium``,
which needs ``sudo``).  The specs are single-worker on purpose: three of the
flows write to the shared database.

Linting and type-checking
=========================

.. code-block:: console

   $ make lint            # everything below
   $ make lint-backend    # ruff check, ruff format --check
   $ make lint-frontend   # tsc --noEmit, eslint --max-warnings 0, prettier --check
   $ make lint-spelling   # codespell over the prose, the code and the tests
   $ make format          # fix what can be fixed automatically

``ruff`` is configured in ``pyproject.toml``: line length 100, target
``py312``, rule sets ``E``, ``F``, ``I``, ``UP``, ``B``, ``DJ``, ``C4``, ``W``,
with migrations excluded.  TypeScript runs in strict mode; ``tsc --noEmit`` is
part of linting rather than of the build, so a type error fails ``make lint``.
ESLint runs with ``--max-warnings 0``, so a warning, such as a missing hook
dependency, fails ``make lint`` too.

``make lint-spelling`` runs ``codespell``, configured under ``[tool.codespell]``
in ``pyproject.toml``, over ``README.rst``, ``CLAUDE.md``, ``docs``, ``backend``,
``frontend/src``, ``frontend/e2e``, ``.github``, ``deploy`` and ``.claude``.  The
``clear`` and ``rare`` dictionaries catch common typos and the ``en-GB_to_en-US``
dictionary enforces American spelling, so a British spelling anywhere in the
prose, the code or the tests fails ``make lint``.  ``plans`` stays out — the
archived plans are frozen, and a live plan may quote the very words a fix
replaces — and so does ``.claude/worktrees``, which holds nested checkouts of
this repository.  Two words are ignored repository-wide, ``nnumber`` and
``unparseable``; to keep any other word the dictionaries flag, end its line with
a ``codespell:ignore`` comment naming the word rather than widening the list.

System checks and dependency audits
===================================

.. code-block:: console

   $ make check           # both halves below
   $ make check-backend   # manage.py check --fail-level WARNING, makemigrations --check --dry-run
   $ make check-frontend  # npm run build
   $ make audit           # both halves below
   $ make audit-backend   # uv audit: the versions in uv.lock against the OSV database
   $ make audit-frontend  # npm audit: the versions in package-lock.json

``make check`` fails on a Django system-check warning, on a model change
without its migration, and on a frontend that type-checks but does not build.
The backend half uses ``caldart.settings.test``.

``make audit`` fails on any known vulnerability in a locked dependency,
development tooling included. Fix a finding by upgrading the affected package.
Do not run ``npm audit fix --force`` blindly: it can resolve an advisory by
downgrading a major version. ``uv audit`` is a uv preview feature.

Continuous integration
======================

``.github/workflows/ci.yml`` runs five jobs on every push to ``main`` and
every pull request. Every check is a make target, so CI runs exactly what the
commands above run locally.

**Backend**
    A PostgreSQL 16 service container, ``uv sync --frozen``, then
    ``make lint-backend``, ``make lint-spelling``, ``make check-backend`` and
    ``make test-backend``.

**Frontend**
    Node 22, ``npm ci``, then ``make lint-frontend``, ``make test-frontend``
    and ``make check-frontend``.

**Audit**
    ``make audit``.

**End-to-end**
    ``make e2e`` against a PostgreSQL 16 service container in Chromium. When a
    flow fails, the job prints the Django log and uploads the Playwright
    report.

**Docs**
    ``uv sync --frozen`` and ``make docs``. Warnings are errors and every
    cross-reference must resolve.
