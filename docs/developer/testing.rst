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
   $ uv run pytest -m "not slow"                         # skip the seed tests (§Markers below)

Configuration lives in ``pyproject.toml`` under ``[tool.pytest.ini_options]``:
``DJANGO_SETTINGS_MODULE = "caldart.settings.test"``, ``pythonpath =
["backend"]``, ``testpaths = ["backend/tests"]``, ``addopts = "-ra
--strict-markers --strict-config"``, and ``filterwarnings = ["error"]``. You
never need to set ``DJANGO_SETTINGS_MODULE`` yourself, an undeclared marker or
a mistyped setting is an error rather than a silent typo, and any warning is a
test failure. Fix a warning that comes from our own code; silence one from a
third-party package only with a narrow ``ignore:`` entry after ``"error"`` and
a comment saying why.

**The tests need Postgres.**  ``make up`` must have run.  Django creates
``test_<the database in DATABASE_URL>``, so a worktree using
``caldart_payments`` tests against ``test_caldart_payments`` and two branches
can run ``pytest`` at the same time without colliding.  Add ``--reuse-db`` if
you are iterating and the schema has not changed.

Markers
-------

Two custom markers are registered in ``pyproject.toml``:

``slow``
    The seed-command tests in ``test_seed.py`` and ``test_cms_seed_content.py``,
    which each run ``seed_demo`` or ``seed_content`` in full.  The default run
    still runs them; ``uv run pytest -m "not slow"`` skips them for a faster
    local loop.

``needs_frontend_build``
    The two ``test_shell_views.py`` tests that assert on the built bundle's
    filenames.  A hook in ``conftest.py`` skips them locally, and fails them in
    CI, unless a real Vite manifest is configured
    (:ref:`testing-vite-manifest`).

Order independence
------------------

``pytest-randomly`` shuffles the test order on every run (and reseeds
``random`` and Faker's shared generator per test), so a test that only passes
after another one has run fails sooner or later rather than the day someone
reorders a file.  To reproduce an order-dependent failure, pytest-randomly
prints the seed it used at the top of every run; rerun with the same one:

.. code-block:: console

   $ uv run pytest --randomly-seed=1234567890  # the exact order that failed
   $ uv run pytest -p no:randomly              # file order, unshuffled

Coverage
--------

.. code-block:: console

   $ make coverage-backend  # writes backend/htmlcov/ and a terminal summary

``make coverage-backend`` runs ``pytest-cov`` over ``backend/apps`` and
``backend/caldart`` only — tests and migrations are excluded
(``[tool.coverage.run]`` in ``pyproject.toml``).  No threshold gates CI; the
report is informational until a baseline is established.

.. _testing-golden-files:

Golden files
------------

``backend/tests/golden/`` holds whole documents the code renders — the five
renewal-reminder emails and the payment CSV export — one file each.  A test
gets the ``golden`` fixture and hands it the file name and the text it
rendered:

.. code-block:: python

   def test_export_matches_the_recorded_document(golden, api_client, history):
       body = csv_body(api_client.get("/api/v1/admin/payments/export.csv"))
       golden("payments-export.csv", body, replace={history[0].provider_ref: "ref-1"})

The comparison is character for character, line endings included, so a stray
blank line or a changed CSV separator fails.  ``replace`` maps a literal to the
placeholder that stands in for it, which is how a name Faker invented or a
reference carrying a row id stops varying between runs; everything else is
compared as rendered.

When a template or a column legitimately changes, rewrite the files from the
output instead of editing them by hand, then read the diff before committing
it:

.. code-block:: console

   $ uv run pytest backend/tests/test_reminders.py --update-golden
   $ git diff backend/tests/golden

``--update-golden`` rewrites every golden file the selected tests touch and
asserts nothing, so a run with it passes whatever the code produced.

What ``caldart.settings.test`` changes
--------------------------------------

- ``PASSWORD_HASHERS`` is MD5 — the single biggest speed-up in a suite that
  creates hundreds of users.
- The one mailer in ``MAILERS`` uses the ``locmem`` backend, so
  ``django.core.mail.outbox`` is what you assert against and nothing leaves the
  process.  A test that needs a different backend assigns a whole ``MAILERS``
  dict, as ``test_reminders_resilience.py`` does to make one address fail.
- Every entry in ``AUTH_THROTTLE_RATES`` is set to ``None``, which makes the
  auth throttles inert.  The throttling test turns one back on with
  ``override_settings`` rather than having every other test race a shared
  counter.
- ``STATIC_ROOT`` is a temporary directory the settings module creates on
  import, because WhiteNoise warns about a ``STATIC_ROOT`` that is not on disk
  and the suite never runs ``collectstatic``.  ``conftest.py``'s
  ``pytest_unconfigure`` removes it, along with any stub manifest directory, at
  the end of the session, so a run leaves nothing behind in the temporary
  directory.
- ``PAYMENTS_MOCK_ENABLED`` is on; ``DEBUG`` is off; storage is in-memory;
  the root logger is quietened to ``ERROR``.  The ``caldart.audit`` logger
  keeps its own ``INFO`` level (:ref:`deploy-audit-log`), so a test that
  provokes a privileged action shows the record in the captured output.
  ``tests/test_audit_logging.py`` shows how to capture it: the logger does not
  propagate, so ``caplog.handler`` has to be attached to it.

.. _testing-vite-manifest:

The Vite manifest
-----------------

``templates/base.html`` and ``templates/portal.html`` call ``{% vite_asset %}``,
which raises when the entry is missing from the manifest.  Backend tests must
not depend on ``npm run build`` having been run — CI runs the two suites in
separate jobs.

``caldart.settings.test`` resolves ``DJANGO_VITE``'s manifest path from the
``DJANGO_VITE_MANIFEST_PATH`` environment variable, falling back to the
default ``frontend/dist/.vite/manifest.json``.  CI's backend job builds the
frontend first and sets the variable to that real manifest.  A local run with
nothing built has neither, so ``conftest.py``'s ``pytest_configure`` builds a
stub manifest in a directory outside the checkout and overrides the
already-loaded setting to point there instead, forcing django-vite to re-read
it.  Nothing is written under ``frontend/dist``.

The test settings load ``.env``, so a ``DJANGO_VITE_MANIFEST_PATH`` set there
decides which manifest the suite reads (:doc:`configuration`).

A test that genuinely needs the real bundle carries
``@pytest.mark.needs_frontend_build``; ``conftest.py``'s
``pytest_runtest_setup`` acts on the marker whenever that fallback fired,
naming the manifest that was missing.  What it does depends on the ``CI``
environment variable:

- Unset, as in a local run, the test is skipped: the checkout simply has no
  build yet.
- Set, as the CI runner sets it, the test fails with the same message.  CI's
  backend job builds the frontend precisely so these tests run, so a manifest
  that is not where the job says it is means the job is not testing the bundle
  at all — a green run would be a lie.

.. code-block:: console

   $ npm --prefix frontend run build
   $ DJANGO_VITE_MANIFEST_PATH="$PWD/frontend/dist/.vite/manifest.json" uv run pytest -m needs_frontend_build

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
   * - ``superuser``
     - ``is_superuser=True`` as well as the ``system_admin`` role
   * - ``no_role_user``
     - a signed-up user with **no** roles at all
   * - ``all_role_users``
     - a ``{slug: user}`` dict, for allow/deny matrix tests
   * - ``account_admin_client``
     - an ``APIClient`` already signed in as an account administrator; the name
       says which administrator, because pytest-django's own ``admin_client``
       is a plain Django client signed in as a superuser
   * - ``annual_plan``, ``life_plan``
     - the two seeded plans
   * - ``dart``, ``profile``, ``aircraft``
     - a Palo Alto DART, a profile for ``member``, one insured airplane
   * - ``register``
     - a four-aircraft register covering every insurance state: current,
       expiring inside 30 days, expired, and nothing on file
   * - ``backup_dir``
     - ``BACKUP_DIR`` pointed at a throwaway directory under ``tmp_path`` and
       created, so no test touches the repository's own
   * - ``home_page``, ``site_settings``
     - a Wagtail tree with a home page, and the settings row
   * - ``today``, ``days``
     - ``today`` freezes the clock (via ``freezegun``) at the current local date
       and returns it, so a test's date math cannot shift mid-test; ``days(7)``
       is ``timedelta(days=7)``, to keep the arithmetic readable
   * - ``pdf_text``
     - ``pdf_text(body)`` reads a rendered PDF back into the strings it draws,
       one list per page, so an export test asserts on the words the document
       shows
   * - ``golden``
     - ``golden(name, text)`` compares a whole rendered document with
       ``backend/tests/golden/name`` (:ref:`testing-golden-files`)

The six role groups exist in every test database already: the accounts data
migration creates one ``Group`` per role slug, so nothing has to seed them.  A
test that needs the database says so with ``pytestmark = pytest.mark.django_db``
or by taking a fixture that opens it; a module that declares neither runs
without a database, which is what keeps the pure-logic tests fast.

The factory classes themselves are also exposed as fixtures — ``user_factory``,
``payment_factory``, ``profile_factory`` — for tests that need many rows.

``conftest.py`` also holds the helpers that are not fixtures, which a test
module imports by name from ``tests.conftest``:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Helper
     - What it does
   * - ``ROLE_MATRIX``, ``role_matrix(*allowed)``
     - ``ROLE_MATRIX`` is every role slug in privilege order;
       ``role_matrix(ACCOUNT_ADMIN, SYSTEM_ADMIN)`` turns it into the
       ``(slug, allowed)`` pairs an allow/deny parametrization needs, one case
       per role
   * - ``read_csv(response)``
     - the rows of a streamed CSV download, parsed with ``csv.reader`` so a
       quoted cell keeps its commas, header first
   * - ``csv_body(response)``
     - the same download as one string, separators, and line endings intact, for
       a comparison against a golden file
   * - ``pdf_page_count(body)``
     - the number of pages in a rendered PDF
   * - ``LOGIN_URL``, ``REGISTER_URL``, ``ME_URL``, ``CHANGE_URL``,
       ``RESET_URL``, ``RESET_CONFIRM_URL``
     - the auth endpoints, named once
   * - ``GOOD_PASSWORD``, ``register_payload(**overrides)``
     - a password that passes every validator, and a valid registration body
   * - ``REPO_ROOT``, ``DEPLOY_DIR``
     - the checkout root and ``deploy/``, for the tests that read the
       deployment templates

Writing tests with the factories
--------------------------------

``backend/tests/factories.py`` has a ``factory_boy`` factory per model.  Each
subclasses ``ModelFactory[SomeModel]``, which names the model the factory
returns so a type checker knows it too.  Most use ``django_get_or_create``, so
asking twice for the same key returns the same row instead of a
unique-constraint error.

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
- ``AircraftFactory`` produces an insured airplane — expiry 200 days out —
  so "insurance current" is the default and you opt into the awkward cases.
- ``PaymentFactory`` defaults to the ``mock`` provider with status
  ``pending``; drive it through ``payments.services.mark_succeeded`` rather
  than setting ``status`` by hand, or you will not get the membership term.
  ``created_at=<datetime>`` backdates the row after the insert, which is the
  only way to place a payment in a past month, since the column is
  ``auto_now_add``.
- ``ReminderLogFactory`` gives ``user`` and ``membership`` independent
  defaults, and addresses the log to its own ``user``.  Pass both when the log
  has to be about that member's own membership.
- ``make_home_page()`` returns the ``HomePage`` the CMS migrations publish and
  ``make_site_settings(**kwargs)`` the settings row of the default site they
  create, with ``kwargs`` applied to it.
- ``publish()``, ``make_standard_page()``, ``make_news_index()``,
  ``make_news_page()``, ``make_dart_index()``, ``make_dart_page()`` and
  ``make_contact_page()`` publish a page of each type under a parent, and
  ``grant_membership()`` / ``expire_membership()`` give a user a term that is
  current or lapsed.  They live here rather than in a test module so no test
  module has to import another.

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
- **No payment test may leave the machine.**  The payment providers are the
  only code that calls a third party, so the ``test_payments*`` modules are the
  only ones the guard covers.  An autouse fixture in ``conftest.py`` wraps every
  test in such a module in a ``respx`` router armed with
  ``assert_all_mocked=True``, so an ``httpx`` request no route matches raises
  ``AllMockedAssertionError`` instead of travelling; the router nests inside the
  one an individual test starts, so its own routes still answer.  Tests in every
  other module run untouched.
  The Stripe SDK carries its own transport rather than ``httpx``, so
  ``test_payments_stripe.py`` replaces the provider's ``http_client`` factory
  with one that raises.  Either way a forgotten mock fails the test that forgot
  it, and each module keeps a test that shows the refusal.
- **Assert what a document says, not how large it is.**  A PDF test reads the
  rendered bytes back with the ``pdf_text`` fixture and asserts on the title,
  the subtitle of applied filters, the column headings and the cells, so a
  report that renders the wrong rows fails instead of merely changing size.
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
   * - ``test_app_layering.py``
     - the one-way dependency rule between the apps
       (:ref:`architecture-app-dependencies`), checked by an ``ast`` pass
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
   * - ``test_profile_api.py``, ``test_profile_aircraft_api.py``,
       ``test_profile_completeness.py``
     - ``/me/profile``, ``PUT`` versus ``PATCH``, attach, and detach, and the
       one rule that decides ``profile_complete``
   * - ``test_members_admin.py``, ``test_members_admin_status.py``
     - the admin list, its filters, and SQL-versus-service agreement
   * - ``test_members_reports.py``, ``test_aircraft_exports.py``,
       ``test_payments_reports.py``, ``test_reports.py``
     - CSV content cell by cell, the text each PDF page draws, and filter
       propagation
   * - ``test_aircraft_api.py``, ``test_aircraft_models.py``
     - N-number normalization, filters, orderings, object permissions
   * - ``test_leader_api.py``
     - search, the status card, and the membership × medical × insurance
       truth table
   * - ``test_payments_api.py``, ``…_stripe.py``, ``…_paypal.py``,
       ``…_mock_provider.py``, ``…_apple_pay.py``
     - checkout → confirm → activation for each provider, webhook signatures
       , amount, and currency mismatches, idempotency
   * - ``test_reminders.py``, ``test_reminders_resilience.py``,
       ``test_reminders_api.py``
     - each kind on its own offset, the three-day catch-up window, dedupe, dry
       runs, skip reasons, and a send the mail server refuses
   * - ``test_cms_pages.py``, ``…_permissions.py``, ``…_seed_content.py``,
       ``test_cms_documents.py``, ``test_site_config.py``
     - page types, blocks, the members-only wall in every visitor state,
       the document guard and the proxy rules behind it, editor permissions,
       and the seeded tree
   * - ``test_sysadmin*.py``
     - backup, restore, reset, health, the production settings module
   * - ``test_openapi_contract.py``
     - the serializers still render the components, properties, and enum values
       the snapshot records (:ref:`testing-api-contract`)
   * - ``test_seed.py``, ``test_shell_views.py``
     - the seed commands run twice cleanly; the portal and public shells
   * - ``test_boundaries.py``
     - the edges: page sizes at 25 and 200, an ``expiring_within`` window
       clamped to ten years, a string one character over its column, and names
       written outside ASCII
   * - ``test_membership_transitions.py``, ``test_payments_race.py``
     - a failed payment that later succeeds, a canceled term that is bought
       again, and two threads confirming one payment at once

Running the frontend suite
==========================

.. code-block:: console

   $ make test-frontend                 # vitest run, once
   $ make coverage-frontend             # the same run, with a coverage report
   $ cd frontend && npm run test:watch  # watch mode
   $ cd frontend && npx vitest run src/portal/features/join

Configuration is the ``test`` key in ``frontend/vite.config.ts``: the ``jsdom``
environment, globals off, ``src/test/setup.ts`` as the setup file, CSS
processing off, and ``src/**/*.{test,spec}.{ts,tsx}`` as the include pattern.
Three settings keep the suite honest:

``allowOnly: false``
    A committed ``.only`` would narrow the run to one test and still report
    green.  vitest refuses it, exactly as Playwright's ``forbidOnly`` refuses
    ``test.only`` in CI.

``restoreMocks: true``
    Every spy is restored before the next test, so a file that patches a module
    member cannot leak it into the file that runs after it.  A spy therefore has
    to be installed per test (or in a ``beforeEach``), never once in a
    ``beforeAll``.

``sequence.shuffle: true``
    The files, and the tests inside each file, run in a random order — the
    frontend's counterpart to ``pytest-randomly``.  A test that only passes
    after another has run fails sooner or later, rather than the day someone
    reorders a file.

**Every test file imports what it uses.**  ``globals: false`` means the runner
injects nothing, and ``tsconfig.json``'s ``types`` lists only ``vite/client``,
so ``describe``, ``it``, ``expect``, ``vi``, and the lifecycle hooks come from a
single ``import {...} from 'vitest'`` at the top of each file.  The jest-dom
matchers are typed once for the whole suite by ``src/test/setup.ts``, which
imports ``@testing-library/jest-dom/vitest``; individual files use
``toBeInTheDocument`` and its siblings without importing anything further.  A
production module that reaches for ``expect`` fails ``tsc`` instead of
compiling, which is the point of keeping the globals out of the type
environment.

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

**The console is a gate.**  ``src/test/console.ts`` replaces ``console.error``
and ``console.warn`` with capturing spies before every test and fails the test
afterwards if it wrote a message — React's complaint about a missing ``key``, a
library's deprecation notice, msw's report of a request nobody stubbed.  It is
the frontend's counterpart to pytest's ``filterwarnings = error``.  A test whose
subject *is* the message declares it first:

.. code-block:: ts

   import { expectConsoleMessage } from '@test/console';

   it('warns about an unknown tone', () => {
     expectConsoleMessage(/unknown tone/i);
     // …
   });

The declaration covers the current test only, and every message it does not
match still fails.  It runs in both directions: a declaration nothing matched
fails the test too, so a test whose subject is the warning cannot keep passing
once the warning stops being written.

Three helpers do the heavy lifting:

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

``src/test/fixtures/``
    The object factories that more than one file wants: ``profile.ts`` for the
    profile, join, and dashboard suites, ``members.ts`` for the members-admin
    screens.  Test data lives here rather than beside the component, so nothing
    test-only ships in the portal bundle.

**Reach the helpers through the ``@test/`` alias** — ``@test/render``,
``@test/server``, ``@test/handlers``, ``@test/console``,
``@test/fixtures/profile`` — rather than counting ``../``s.  It is a path
mapping in ``frontend/tsconfig.json`` mirrored by a ``resolve.alias`` entry in
``frontend/vite.config.ts``, alongside the ``@/`` alias for ``src``.

**Time.**  A test never waits out a real debounce, poll, or delay, and never
builds a fixture date from the real clock.  Pin the system clock with
``vi.useFakeTimers()`` and ``vi.setSystemTime(...)`` (add
``{shouldAdvanceTime: true}`` when the component under test also renders and
needs its own effects to keep making progress), then settle a debounce or a
poll explicitly with ``await vi.advanceTimersByTimeAsync(ms)`` wrapped in
``act(...)``.  Configure ``userEvent.setup({advanceTimers:
vi.advanceTimersByTime})`` so its own internal waits advance the fake clock
instead of sleeping.  ``src/test/setup.ts`` calls ``vi.useRealTimers()`` after
every test, so a file that fakes the clock need not restore it itself, though
doing so in its own ``afterEach`` documents the intent.  A one-off delay
inside an msw handler uses msw's own ``delay(ms)`` rather than a raw
``setTimeout``.

.. code-block:: tsx

   import { http, HttpResponse } from 'msw';
   import { screen } from '@testing-library/react';

   import { renderWithProviders } from '@test/render';
   import { server } from '@test/server';
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

Measuring frontend coverage
---------------------------

``make coverage-frontend`` runs the same suite through ``@vitest/coverage-v8``
and writes a text summary to the terminal and an HTML report to
``frontend/coverage/`` (git-ignored; open ``frontend/coverage/index.html``).
The measurement covers production code only: ``src/**/*.{ts,tsx}`` minus
``src/test/``, the test files themselves and the generated
``src/portal/api/schema.d.ts``.

No threshold fails the run, and CI does not gate on the number.  The report is
there to find the module nothing exercises, not to be argued with.

What the frontend suite covers
------------------------------

The query client's retry policy, which gives up on a 4xx and tries a 5xx three
times in all; the portal chrome — the skip link, the role-filtered rail, the
identity area and the mobile drawer that closes on navigation; the toast queue,
including the timeout that drops a toast on its own; the cache that sign-in
empties before seeding it with whoever just signed in;
the API client and its error mapping; the route guards, and the real route
table opened at every guarded path by an anonymous visitor and by a user
holding each role, so a guard that loses a role fails a case, plus the order a
guard and an on-demand page resolve in; the shared
``DataTable`` and ``StatusChip``; the auth pages; the join wizard's step
progression, resume, and clamp rules; profile form conversion and validation;
the aircraft picker's search, exclude, and create paths; the leader search and
status card in each verdict state; every admin screen's filters, paging, export
links and save paths; the payments summary's headline tiles and its table by
month and by year; the checkout with the Stripe and PayPal SDKs mocked; and
the four system panels.  ``api/types.contract.test.ts`` is a different kind of
test: it checks the portal's own types against the backend's schema rather than
any component's behavior (:ref:`testing-api-contract`).

.. _testing-api-contract:

The API contract
================

The DRF serializers under ``apps/*/api/`` and the portal's
``frontend/src/portal/api/types.ts`` describe the same objects.  Two test files
keep them saying the same thing, and both run inside ``make check``: rename a
serializer field without following it in ``types.ts`` and the gate goes red.

The description in the middle is OpenAPI, generated from the views:

.. code-block:: console

   $ make check-backend     # writes backend/openapi.json
   $ cd frontend && npm run schema   # that JSON, then src/portal/api/schema.d.ts

Neither artifact is committed.  ``backend/openapi.json`` comes from
``manage.py spectacular``; ``frontend/src/portal/api/schema.d.ts`` comes from
``openapi-typescript`` reading it.  The frontend's ``pretypecheck`` and
``pretest`` scripts regenerate both, so ``tsc`` and vitest always read a schema
that matches the serializers in the working tree.  ``drf-spectacular`` is
configured by ``SPECTACULAR_SETTINGS`` in ``caldart/settings/base.py``, and
``caldart/api_urls.py`` carries the preprocessing hook that narrows the schema
to ``/api/v1/`` along with the description of the session authentication.  No
route serves the schema: it is build output, not an endpoint.

The backend half
----------------

``backend/tests/test_openapi_contract.py`` reduces the generated description to
one summary per component and compares that to
``backend/tests/snapshots/openapi-components.json``.  An enumeration's summary is
its values in declared order; every other component's is its required names,
sorted, plus a mapping from each property name to that property's type.  A type
reads as ``integer``, ``string``, ``string(date)``, ``ref:Dart`` for a reference
to another component, ``array<ref:RatingsEnum>`` for a list, ``map<integer>``
for a free-keyed object, and carries ``|null`` when the property is nullable.
Renaming a field, adding one, dropping one and retyping one therefore all fail
here, for every component, whether or not the portal pairs it.  A difference is
reported one line per component, naming the snapshot's summary and the schema's.

The test also asserts that no operation is left with an empty ``responses``
entry, which is what the generator writes for a view it cannot read.

When the change is intended, refresh the snapshot and commit it with the code:

.. code-block:: console

   $ UPDATE_OPENAPI_SNAPSHOT=1 uv run pytest backend/tests/test_openapi_contract.py

The test reports as skipped on that run, and passes on the next one.

The frontend half
-----------------

``frontend/src/portal/api/types.contract.test.ts`` pairs each object and union in
``api/types.ts`` with its schema component and asserts the two are mutually
assignable.  The comparison strips ``readonly`` and optionality at every depth,
because OpenAPI marks a property optional whenever the serializer does not
require it on input, which says nothing about whether the response carries it;
property names and property types are what the two sides must agree on.  A
mismatch is a ``tsc --noEmit`` error on the assertion's line, so
``make lint-frontend`` and ``make check-frontend`` both catch it.  The file's
runtime half asserts that every component the pairs name is still in the
generated schema, which is the clearer failure when a serializer disappears
altogether, and it says which command writes ``backend/openapi.json`` when that
file is missing.

Pairing an interface directly is not the only way it is covered: a component
another paired component nests is checked with it, so ``DartRef`` is held by
``Profile``, the four halves of the leader status card by ``LeaderStatus``, and
``AdminUser`` by ``Paginated<User>``.

What the schema does not cover
------------------------------

Every endpoint under ``/api/v1/`` describes its request and its response, so the
residual is short:

* **Bodiless answers.**  ``GET /auth/csrf``, ``POST /auth/logout``, the three
  password endpoints and ``DELETE /me/profile/aircraft/{id}`` answer **204** with
  no body, and the two payment webhooks answer **200** with whatever the
  provider's own handler returns.  Each declares that response, but there is no
  object to describe.
* **Downloads.**  The member, aircraft, and payment exports and the backup
  download answer with a file.  Each names its media type -- ``text/csv``,
  ``application/pdf``, ``application/gzip`` -- and describes the body as opaque
  bytes, so there is no component to compare.
* **Error bodies.**  A **400** field-keyed error, and the **401**, **403**, and
  **404** bodies, are described in :doc:`api-reference` rather than in the
  schema.
* **Two type aliases.**  ``IsoDate`` and ``IsoDateTime`` in ``api/types.ts`` name
  the string format of a date and a timestamp; they are not objects, and the
  schema carries the same information as ``string(date)`` and
  ``string(date-time)`` on each property that uses them.

A handful of small request bodies the portal builds inline rather than typing --
the Stripe confirm, PayPal capture, mock completion and reminder-run payloads,
and the aircraft attach and create bodies -- have a component but no interface to
pair with.  The snapshot covers them, property names and types alike.

End-to-end tests
================

.. code-block:: console

   $ make e2e                    # playwright test
   $ cd frontend && npx playwright test --ui

Playwright drives a real browser against a real server, and covers the five
low-friction flows the system is built around (:doc:`architecture`) — the
same ones the :doc:`/demo-walkthrough` walks a person through:

1. a visitor signs up and pays and is immediately a current member;
2. a member signs in, edits their profile and reads members-only content;
3. a DART leader checks a member's membership, medical, and aircraft insurance;
4. an account administrator sees payments per month and per year;
5. a website administrator adds, edits, and deletes a page.

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

``failOnFlakyTests`` is on in ``playwright.config.ts``.  CI retries a failing
spec once so the failure is easy to read, but a spec that fails and then passes
still fails the run: a flaky end-to-end spec is a race somewhere real.

Writing a spec
--------------

**Locate by role and by label, never by CSS class.**  A class is styling, and a
styling change should not break a test.  Every screen the specs touch gives
them something better: the status cards are ``<section>`` elements with an
``aria-label`` (``getByRole("region", {name: "Status for Owen Delgado"})``), the
by-period report is labeled by its own heading, tables expose ``row``,
``rowgroup``, ``columnheader``, and ``term``, and every control has an accessible
name.

**Wait for what you are about to assert, never for the network.**
``waitForLoadState("networkidle")`` guesses that quiet means finished, which a
long poll or a late asset makes wrong.  ``await expect(locator).toBeVisible()``
waits for the thing itself, and says what went wrong when it never appears.

**Take the seed's own values from** ``frontend/e2e/seed-facts.json``.  ``make
e2e`` writes it with ``manage.py seed_facts`` straight after seeding the
database, and ``e2e/helpers.ts`` reads it once per run and exports
``DEMO_PASSWORD``, ``DEMO`` (the demo key to address map) and ``SEED``
(``planPricesCents`` among them).  A spec that hard-codes ``caldart-demo`` or
``$45.00`` is a copy of ``apps/*/seed.py`` that will one day disagree with it.
Running Playwright against a server you started yourself means writing the file
yourself first, with the same command.

**Derive a row count rather than asserting "more than none".**  The payments
report counts its rows against the CSV export downloaded in the same test, so
the count is exact and stays right even though an earlier spec in the run paid
for a membership of its own.  Derive it from the rows the screen actually
reports on: the export carries every payment, while the by-period summary counts
only the succeeded ones, so the spec counts periods over the export's
``succeeded`` rows and the ledger's caption over all of them.

Environment variables
---------------------

``make e2e`` reads these to isolate itself from your development setup and
from other end-to-end runs on the same machine:

``E2E_PORT``
   The port Django listens on for the run.  Defaults to ``8021``; a parallel
   branch running its own ``make e2e`` sets this to something else so the two
   servers do not collide.
``E2E_DB``
   The database name.  Defaults to ``caldart_e2e``; combine with ``E2E_PORT``
   per branch for isolation.
``E2E_DATABASE_URL``
   The full connection string the run's Django process uses.  Defaults to
   ``postgres://caldart:caldart@localhost:5432/$(E2E_DB)``; set it directly to
   override the host or credentials instead of just the database name.
``E2E_LOG``
   Where the Django server's stdout and stderr are captured.  Defaults to
   ``/tmp/caldart-e2e-server.log``; the target tails it automatically when
   startup fails or a spec run reports failures.
``SKIP_CREATEDB``
   When set to any non-empty value, skips the ``make createdb`` step and
   assumes the database already exists.  CI sets this because it creates the
   database with ``psql`` directly, having no Docker Compose service to run
   ``createdb`` against.
``E2E_BASE_URL``
   Read by ``frontend/playwright.config.ts``, not by the Makefile: the URL the
   specs open in the browser.  ``make e2e`` sets it to
   ``http://localhost:$(E2E_PORT)``; running Playwright by hand against an
   already-running server needs it set explicitly.
``CI``
   Also read by ``playwright.config.ts``.  When set, Playwright forbids
   ``test.only``, retries a failing spec once, and switches its reporter to a
   list plus an HTML report instead of interactive output.  The CI workflow
   sets it; a local run leaves it unset.

Linting and type-checking
=========================

.. code-block:: console

   $ make lint            # everything below
   $ make lint-backend    # ruff check, ruff format --check, mypy backend
   $ make lint-frontend   # tsc --noEmit, eslint --max-warnings 0, prettier --check
   $ make lint-spelling   # codespell over the prose, the code and the tests
   $ make format          # fix what can be fixed automatically

``ruff`` is configured in ``pyproject.toml``: line length 100, target
``py312``, rule sets ``E``, ``F``, ``I``, ``UP``, ``B``, ``DJ``, ``C4``, ``W``,
``ANN``, ``D``, ``A``, ``N``, ``RUF``, ``SIM``, ``PT``, ``PTH``, ``RET``,
``PERF``, ``ERA``, ``T20``, and ``S``, with migrations excluded.  ``ANN``
requires an annotation on every parameter and every return value, and ``D``
requires a docstring on every public module, class, function, and method and
checks the form of every docstring it finds (a ``_``-prefixed helper's
docstring is a matter for review); ``max-doc-length = 90`` turns on ``W505``,
which wraps those docstrings at 90 characters.  A package's ``__init__.py``
(``D104``) and a nested ``Meta`` class (``D106``) need no docstring.  ``ANN``
and ``D`` apply to the whole backend, tests included: there is no
``[tool.ruff.lint.per-file-ignores]`` entry for either, no file may be
exempted from either, and ``backend/tests/test_lint_config.py`` fails if an
exemption or an ``ignore_errors`` mypy override appears.  ``RUF012`` is
ignored everywhere, because Django's ``Meta`` options, admin ``list_display``
lists and serializer ``fields`` are class-level configuration the framework
reads and nothing mutates; ``S101`` is ignored for ``backend/tests/**`` only,
because ``assert`` is pytest's assertion mechanism.  Every other diagnostic
from an enabled rule set is fixed at the call site; a single-line ``# noqa:
<code> - <reason>`` is allowed only where the framework genuinely imposes the
shape, and ``RUF100`` fails the build if a ``noqa`` names a rule that is not
selected.  ``ARG`` (an unused function argument) stays off, because nearly
every diagnostic it raises is a Django or DRF signature such as ``get(self,
request, *args, **kwargs)``, where the framework dictates the parameter list.

``mypy`` type-checks ``backend`` — the application and the tests alike — as the
third step of ``make lint-backend``.  ``[tool.mypy]`` in ``pyproject.toml`` sets
``strict = true``, the ``mypy_django_plugin`` and ``mypy_drf_plugin`` plugins,
and ``caldart.settings.test`` as the settings module the Django plugin reads;
migrations are excluded.  ``disallow_subclassing_any`` is off because Wagtail's
page, block, and settings base classes carry no types, and Wagtail, the four
libraries it builds on (``django-modelcluster``, ``django-taggit``
, ``django-treebeard``, and ``modelsearch``), ``django-environ``,
``django-filter``, ``django-vite``, and ``whitenoise`` are declared as untyped
imports for the same reason.  ``factory_boy`` is followed rather than skipped,
so that a factory's model type reaches its callers, and two settings absorb its
stub gaps: ``untyped_calls_exclude = ["factory"]`` accepts the unannotated
declarative API (``Faker``, ``Sequence``, ``SubFactory``, ``LazyFunction``,
``LazyAttribute``, ``post_generation``), and ``implicit_reexport`` accepts the
names ``factory`` re-exports without an ``as`` alias.  As with the ruff rule sets,
no ``[[tool.mypy.overrides]]`` entry carries ``ignore_errors = true``: mypy checks
the whole backend clean.  Silencing one line takes ``# type: ignore[<code>]`` with
a comment naming the stub gap behind it.

TypeScript runs in strict mode; ``tsc --noEmit`` is
part of linting rather than of the build, so a type error fails ``make lint``.
ESLint runs with ``--max-warnings 0``, so a warning, such as a missing hook
dependency, fails ``make lint`` too.  ``frontend/eslint.config.js`` draws its
rules from four sources: ``@eslint/js``'s recommended set,
``typescript-eslint``'s ``recommendedTypeChecked``,
``eslint-plugin-jsx-a11y``'s ``recommended`` flat config, and the project's own
rules below.

``recommendedTypeChecked`` needs type information, which
``languageOptions.parserOptions.projectService`` supplies: ESLint hands each
file to the TypeScript program that already owns it, so a path added to
``tsconfig.json``'s ``include`` is type-checked by the linter without a second
list to maintain.  The rules that information buys are the ones review keeps
missing — ``@typescript-eslint/no-floating-promises`` (a promise nothing awaits
or marks with the ``void`` operator), ``no-misused-promises`` (an async
function handed to an attribute that expects a void return),
``no-unsafe-assignment`` and ``no-unsafe-argument`` (an ``any`` flowing into
typed code), ``no-unnecessary-type-assertion`` and ``require-await``.  React
Router's ``navigate`` returns a promise that callers deliberately do not await,
so those call sites read ``void navigate(...)``.  A rule is suppressed only
where a library's types force it, and the suppression carries a comment saying
which.

``eslint-plugin-jsx-a11y`` checks the markup: a label without a control, an
image without ``alt``, an interactive role that cannot take focus, an
``autoFocus`` prop.  An accessibility finding is fixed in the markup rather
than silenced.  The one configured exception is
``jsx-a11y/no-redundant-roles``, which allows ``role="list"`` on ``ul`` and
``ol``: ``src/styles/base.css`` strips the markers from both
``ul[role='list']`` and ``ol[role='list']``, and VoiceOver stops announcing a
list once its markers are gone, so the attribute carries the semantics rather
than repeating them.

The project's own rules apply to every TypeScript file under ``frontend``, its
configuration files included.
``@typescript-eslint/explicit-module-boundary-types`` requires an explicit
return type on every exported function, and ``eslint-plugin-jsdoc``'s
``jsdoc/require-jsdoc`` requires a JSDoc comment on every exported function
, component, and class (``jsdoc/no-types`` keeps that comment free of ``{type}``
annotations, since the types live in TypeScript).
``@typescript-eslint/consistent-type-imports`` requires a separate ``import
type`` statement for a type-only symbol, and
``@typescript-eslint/no-unused-vars`` accepts a name that begins with an
underscore, the marker for a deliberately unused variable or parameter.  The
``react-hooks`` recommended rules join them, and
``react-refresh/only-export-components`` is off, because a feature module
deliberately keeps a component beside the pure helper that computes its input.
``jsx-a11y/no-redundant-roles`` carries its list exception here as well.

``make lint-spelling`` runs ``codespell``, configured under ``[tool.codespell]``
in ``pyproject.toml``, over ``README.rst``, ``CLAUDE.md``, ``docs``, ``backend``,
``frontend/src``, ``frontend/e2e``, ``.github``, ``deploy``, and ``.claude``.  The
``clear`` and ``rare`` dictionaries catch common typos and the ``en-GB_to_en-US``
dictionary enforces American spelling, so a British spelling anywhere in the
prose, the code or the tests fails ``make lint``.  ``plans`` stays out — the
archived plans are frozen, and a live plan may quote the very words a fix
replaces — and so does ``.claude/worktrees``, which holds nested checkouts of
this repository.  Two words are ignored repository-wide, ``nnumber``, and
``unparseable``; to keep any other word the dictionaries flag, end its line with
a ``codespell:ignore`` comment naming the word rather than widening the list.

System checks and dependency audits
===================================

.. code-block:: console

   $ make check           # every check below
   $ make check-backend   # manage.py check, makemigrations --check --dry-run, spectacular
   $ make check-deploy    # manage.py check --deploy, throwaway environment
   $ make check-frontend  # npm run typecheck, npm run build
   $ make audit           # both halves below
   $ make audit-backend   # uv audit: the versions in uv.lock against the OSV database
   $ make audit-frontend  # npm audit: the versions in package-lock.json

``make check`` fails on a Django system-check warning, on a model change
without its migration, on a deployment warning against the production settings,
on portal types that no longer match the serializers
(:ref:`testing-api-contract`), and on a frontend that type-checks but does not
build. ``check-backend`` uses ``caldart.settings.test``, and writes the OpenAPI
description ``check-frontend`` then checks the portal against.

``check-deploy`` runs ``manage.py check --deploy`` against
``caldart.settings.prod``, with a throwaway environment set inline in the
Makefile recipe: a dummy ``SECRET_KEY``, ``ALLOWED_HOSTS``, ``DATABASE_URL``
, ``SITE_URL``, and ``EMAIL_URL``, and no secure flag at all — each of those comes
from ``caldart.settings.prod``'s own default, so turning one off fails the gate
rather than being masked by a value the recipe supplies. The recipe names every
tag Django's deployment-only checks carry — ``security``, ``caches``
, ``async_support``, and ``mail`` — so all of them run, while the default checks
``check-backend`` already covers stay out, one of which would need a
``frontend/dist`` this gate never builds. :doc:`deployment` covers the two
warnings ``caldart.settings.prod`` silences deliberately.

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
    ``make lint-backend``, ``make lint-spelling``, ``make check-backend``,
    ``make check-deploy`` and ``make test-backend``.

**Frontend**
    Node 22 and ``npm ci``, plus uv and ``uv sync`` because every frontend
    target regenerates the OpenAPI description from the serializers first; then
    ``make lint-frontend``, ``make test-frontend`` and ``make check-frontend``.

**Audit**
    ``make audit``.

**End-to-end**
    ``make e2e`` against a PostgreSQL 16 service container in Chromium. When a
    flow fails, the job prints the Django log and uploads the Playwright
    report.

**Docs**
    ``uv sync --frozen`` and ``make docs``. Warnings are errors and every
    cross-reference must resolve.
