# Code and test-suite follow-ups: the low-priority findings in #56 to #59

This plan works through the four low-priority issues the 2026-09-13 critiques left open:
#56 (backend code), #57 (backend test suite), #58 (frontend code) and #59 (frontend test
suite), as re-audited on 2026-09-21 in `critiques/2026-09-21-remaining-findings.md`. That
audit also named three findings the critiques rated high priority that were triaged into
these issues (a payment test that can make a live HTTP call, two PDF tests whose names
overclaim, and profile form tests that assert existence rather than message text); they
run first. Of the three findings the audit said no issue captured, two are already
settled on `main` (`docs/developer/api-system.rst` exists, and the abstract models are in
the data-model diagram); the third, distinguishing a CSRF 403 from a permission 403 in
the portal, is implemented in `api/client.ts` and only needs a test, which
`frontend-fixes` carries. Eleven work packages in four waves; three run on Sonnet, eight
on Opus (§7 names the model for each).

## 1. How to run this plan

The orchestrator runs waves in order. Within a wave, packages run in parallel, each in its
own worktree and branch, and each is reviewed by one adversarial reviewer confined to the
diff. The orchestrator reads every PR before merging it: no PR auto-merges. A package's
`after` list in the §8 manifest names the packages that must be merged before it starts,
so a later wave may start a package as soon as its own dependencies have merged.

## 2. Preconditions

- This plan is on `main` and every package of `plans/archive/2026-09-21-tooling-and-docs.md`
  has merged (it has: PRs #130 to #158).
- `make up` is running; `main` is green.
- Issues #56 to #59 are open. Each closes when its last package merges; the PR bodies list
  every item of the issue with the PR that settled it or the reason it stays open.

## 3. Conventions for every work package

Every worker follows `CLAUDE.md` and the rules in `.claude/rules/`. On top of those:

- **Branch and worktree.** `git fetch origin && git worktree add .claude/worktrees/<package> -b <branch> origin/main`, with the branch from the manifest.
- **Database.** `DATABASE_URL=postgres://caldart:caldart@localhost:5432/<database>` from the manifest, then `make createdb`.
- **End-to-end runs.** A package with an `e2e_port` runs `make e2e E2E_PORT=<e2e_port> E2E_DB=<database>_e2e`.
- **Docs are the specification.** A behavior change updates the docs page that describes it in the same PR, describing the current state only. Never cite a plan from the docs, docstrings or comments. `critiques/` files are dated records: never edit them. The archived plans are frozen.
- **Lint over review.** A convention a linter can check gets a lint rule or a test in `backend/tests/test_lint_config.py` (or a frontend equivalent), not a review note. Where a package settles a style question (§5), it adds the check that keeps it settled.
- **Scope.** Edit only the files the package owns (§7 and the manifest; a `#section` suffix limits the part of a file), plus the new files it names. If a change genuinely needs another file, keep it additive and say so in the PR under Potential Impacts.
- **Test first** for every behavior change (`python_testing` §1). A package that fixes a bug lands the failing test in the commit before the fix. A package that removes a test says in the PR body which surviving test covers the same behavior.
- **Never weaken a test.** A test that fails after a change is a finding, not an obstacle; fix the code or explain in the PR.
- **Frontend dependencies.** npm 10 crashes on this tree; add or upgrade packages with `npx -y npm@11 install …`, then verify with a clean `npm ci`.
- **Commits.** Conventional Commits, one logical change per commit, every message ending with the two trailer lines from `CLAUDE.md`, naming the model doing the work (`Claude Sonnet 5` or `Claude Opus 5`).
- **Gates.** `make lint test check docs audit` must pass before the PR opens, plus `make e2e` where the manifest gives a port, plus the package's own "Verify" list.
- **Pull request.** `gh pr create --base main`, body per `.github/pull_request_template.md`, with one `Refs #N.` sentence per issue in `refs` and one `Closes #N.` per issue in `closes`.

## 4. Merging

The orchestrator merges each approved PR itself, one at a time, after reading it against
its manifest scope and the reviewer's report: rebase on `main` if needed (`conftest.py`
and `pyproject.toml` edited by two packages is the expected conflict; keep both sides'
changes), gates green, CI green, `gh pr merge --squash`, `main` green afterwards, then the
worktree and branch are removed. Nothing merges on a red check. Before every squash the
orchestrator checks `git log --format=%(trailers)` on the branch and sets the trailers
explicitly with `--subject` and `--body-file` if any commit lacks them.

## 5. Decisions

Settled here so no worker has to choose:

- **CSV formula injection.** Cells whose first character is `=`, `+`, `-`, `@`, tab or carriage return are prefixed with a single quote in `csv_rows`, the OWASP treatment. Numbers and dates the code formats itself are exempt because they never start with those characters. `reports.rst` states the rule; a test pins it with one cell of each kind.
- **Login and deactivated accounts.** The wrong-password path and the deactivated-account path answer the same 400 body unless the password is correct: `authenticate()` fails, the view checks the password against the inactive account, and only a correct password discloses "This account has been deactivated". A test covers the three cases.
- **Sign-out.** The header's "Log out" control becomes a real button that calls the logout mutation and then navigates to `/login`; the join flow's "Use a different account" link becomes the same kind of button. The `/portal/logout` route and `LogoutPage` are deleted, so no address ends a session on load. `member-guide.rst` and `architecture.rst`'s route list describe the button.
- **PayPal panel.** `createOrder` wraps the API call in try/catch and surfaces `ApiError.message`; every other error keeps the generic text. `onCancel` shows "Payment cancelled" through the existing toast and leaves the checkout in place.
- **Same-origin client.** `buildUrl` accepts a path, or an absolute URL whose origin equals `window.location.origin`, and throws `TypeError` for anything else, so `X-CSRFToken` and credentials can never leave the site.
- **Reminder log for account admins.** Account admins get a portal screen for the log: a new route `/admin/reminders` under the Administration nav group, labeled "Reminders", gated to `account_admin` (system admins see everything already). It shows the same log table and kind filter as the system page's panel, without the "run the scan" controls, which stay on `/portal/system` because `POST /admin/reminders/run` is `system_admin` only. The panel splits into a shared `ReminderLog` component used by both screens. `reminders.rst`, the account administrator guide, the user overview and `architecture.rst`'s route list describe the screen.
- **Component barrel.** Delete `frontend/src/portal/components/index.ts`; every import names the file. An ESLint `no-restricted-imports` pattern refuses `@/portal/components` and `./components` with no file segment.
- **Cross-feature imports.** The `@/` alias for anything outside the importing feature; relative paths only within a feature. An ESLint `no-restricted-imports` pattern for `../../*` enforces it. `useDarts`, `usePlans` and `useSiteConfig` move to `src/portal/api/queries.ts`.
- **`CheckoutResponse`.** Becomes a union discriminated on `provider` (`stripe` carries `client_secret`, `paypal` carries `order_id`, `mock` carries neither). The serializer side gains the matching `OneOf` through drf-spectacular's polymorphic support so the contract test still pairs the type; `Health.db` and `SiteConfig.theme` get literal unions from the model choices the schema already states.
- **Coverage.** `pytest-cov` and `@vitest/coverage-v8`, measuring production code only (`backend/apps`, `backend/caldart`, `frontend/src` minus `src/test`, tests and migrations excluded), exposed as `make coverage-backend`, `make coverage-frontend` and `make coverage`. Reports are written, no threshold gates CI; a threshold is a later decision once the baseline is known.
- **Order independence.** Add `pytest-randomly` to the dev group; `-p no:randomly` and `-p randomly -p "randomly_seed=N"` are documented in `testing.rst` for reproducing an order-dependent failure. `seed_demo.py` seeds a local `Faker` instance instead of the global one. The ordering test creates its own fixed-name members.
- **Frozen clock.** The `today` fixture freezes time with `freezegun` for the test that requests it and returns the frozen date; `freezegun.configure(extend_ignore_list=["_pytest", "pluggy"])` keeps pytest's own timing real. Tests that compute expected dates from `timezone.localdate()` switch to the fixture.
- **Slow tests.** A `slow` marker registered in `pyproject.toml` and applied to the seed tests (24 tests, 24 of the suite's 71 seconds on 2026-09-22). The default run keeps every test; `testing.rst` documents `uv run pytest -m "not slow"` as the quick local loop. No Makefile target changes.
- **Frontend-bundle tests.** A registered `needs_frontend_build` marker replaces the imperative `pytest.skip`; the fixture builds its manifest in `tmp_path` and points `DJANGO_VITE_MANIFEST_PATH` at it, so nothing is written under `frontend/dist`. CI's backend job builds the frontend first so those tests run rather than skip.
- **`STATIC_ROOT`.** `test.py` sets `STATIC_ROOT` to a temporary directory the settings module creates, so WhiteNoise's warning never fires and the `filterwarnings` ignore is deleted.
- **Golden files.** `backend/tests/golden/` holds the expected email bodies and CSV exports; a test compares the rendered output byte for byte after normalizing dates the seed varies. A documented `--update-golden` option (in `conftest.py`, `testing.rst`) rewrites them. The CSV reader in tests is `csv.reader`, once, in `conftest.py`.
- **PDF assertions.** A stdlib decoder in `conftest.py` inflates every `FlateDecode` stream in a PDF and returns the text operators' strings, so PDF tests assert on the subtitle and row content they name. No new dependency.
- **`seed_content` copy.** Moves to `backend/apps/cms/management/commands/seed_content_data.py`: a typed module of frozen dataclasses (`PageSpec`, `BlockSpec`), no YAML. The command keeps the logic.
- **cms migrations.** `0001_initial` through `0004` are regenerated as one schema migration plus the data migrations that must follow it, since the prototype carries no data to preserve (`CLAUDE.md`, "No backwards compatibility").
- **Backups.** `pg_dump` output streams through `gzip` into the file (`subprocess.Popen` with a pipe, chunked writes); restore streams the reverse. The password travels in `PGPASSWORD`, never in the URL; user and password are URL-quoted where a URL is still needed. Peak memory no longer scales with the dump.
- **PayPal token cache.** Moves into Django's cache (`caches["default"]`, key `paypal:access_token`, timeout from the token's `expires_in` minus a safety margin). The module-level dict and `reset_token_cache()` go; tests use `cache.clear()`. The docstring states that the cache backend decides sharing across processes.
- **Dead backend code.** `CheckoutResponseSerializer`, `Payment.amount_dollars` and `MemberProfile.volunteer_interests` are deleted; the last takes the members migration with it, regenerated rather than stacked (§ cms migrations applies the same rule).
- **Provider registry.** `Provider` gains `is_configured() -> bool` as a classmethod; `available_providers()` iterates `_REGISTRY` and asks each. `payments-setup.rst`'s provider-interface section names the method.
- **Event handlers.** Local handlers are `handle*` throughout; an ESLint `react/jsx-handler-names` rule (`eventHandlerPrefix: handle`, `checkLocalVariables: true`) enforces it, so the sweep cannot regress.
- **Vitest config.** `allowOnly: false`, `restoreMocks: true`, `sequence.shuffle: true`, and a setup-file guard that fails a test on `console.error` or `console.warn` unless the test opts out with the documented helper.
- **Test fixtures and alias.** `features/profile/fixtures.ts` and `features/admin-members/fixtures.ts` move to `src/test/fixtures/`; a `@test/` alias in `tsconfig.json` and `vite.config.ts` replaces the `../../../test/render` paths, enforced by the same `no-restricted-imports` pattern.
- **E2E robustness.** Role and label locators replace CSS-class locators; `networkidle` waits become `expect(...).toBeVisible()`; `failOnFlakyTests: true` in `playwright.config.ts`; row counts come from the seed's constants imported through a small helper that reads `apps/*/seed.py` values the specs need (exported once as JSON by `make e2e`'s server start, `e2e/helpers.ts` reads it).
- **Non-ASCII in `.py` files.** A `test_lint_config.py` check refuses any non-ASCII byte in `backend/**/*.py` outside migrations, once the sweep is done, so the tracking item closes for good.
- **Test naming and style.** `.json()` on API responses everywhere; the `settings` fixture, never `override_settings`; filename checks with `==`; test names that state the behavior. A `PT` ruff rule already covers the assert forms; the rest is settled by the sweep and by review of new tests only.

## 6. Failure handling and the final report

- **A failing gate.** Three fix attempts within scope; then the PR stays open as a draft with a comment on its issue saying what failed, and the orchestrator carries on with every package that does not depend on it.
- **A rebase conflict outside the package's files.** Same.
- **CI red on `main`.** No new package starts until a fix PR restores it.
- **The final report** lists every PR merged, every item of #56 to #59 still open and why, and every decision taken that §5 did not cover.
- **Archive.** When every package has merged, one last PR moves this plan to `plans/archive/`.

## 7. Work packages

### Wave 1

#### tests-high-priority (Opus)

- **Refs:** #57
- **Branch:** `test/high-priority-findings`; database `caldart_tests_high_priority`
- **Owns:** `backend/tests/conftest.py#respx-guard`, `backend/tests/conftest.py#pdf-decoder`, `backend/tests/test_payments_paypal.py`, `backend/tests/test_payments_stripe.py#http-guard`, `backend/tests/test_aircraft_exports.py#pdf-content`, `backend/tests/test_reports.py#pdf-content`, `docs/developer/testing.rst#http-guard`.
- **Steps:**
  1. An autouse fixture in `conftest.py` that arms `respx` with `assert_all_mocked=True` for every test in the payment modules, so an unmocked call fails; prove it by removing a mock and watching the failure.
  2. The PDF decoder of §5; rewrite `test_pdf_states_the_filters_it_was_run_with` and `test_pdf_paginates_100_rows_with_a_repeated_header` to assert the subtitle text and the row content, and rename any test whose name still overclaims.
  3. `test_an_expired_token_is_fetched_again` advances a frozen clock past `expires_in` instead of calling `reset_token_cache()`.
- **Verify:** the deliberate unmocked call fails; the two PDF tests fail when the subtitle is blanked in the view and pass again.

#### backend-fixes (Opus)

- **Refs:** #56
- **Branch:** `fix/backend-low-priority`; database `caldart_backend_fixes`
- **Owns:** `backend/apps/payments/api/serializers.py#contribution-max`, `backend/apps/accounts/api/views.py#login-disclosure`, `backend/apps/accounts/permissions.py#getattr`, `backend/caldart/reports.py#escape-and-csv`, `backend/apps/sysadmin/services.py#credentials`, `backend/apps/payments/views.py#getattr`, `backend/apps/payments/providers/paypal.py#token-cache`, `backend/apps/payments/providers/paypal.py#getattr`, `backend/tests/test_backend_fixes.py` (new), `docs/developer/reports.rst#csv-policy`, `docs/developer/api-auth.rst#login-errors`, `docs/developer/backup-restore.rst#credentials`, `docs/developer/payments-setup.rst#token-cache`.
- **Steps:** §5's decisions on `contribution_cents` (a `max_value` of 1,000,000,000 cents, answering 400), login disclosure, PDF title and subtitle escaping, the CSV policy, `PGPASSWORD` and URL-quoting, the PayPal token cache, and the three `getattr` calls. One commit per item, the test first.
- **Verify:** `make test`; the new module has one test per item that fails on `origin/main`.

#### frontend-fixes (Opus)

- **Refs:** #58
- **Branch:** `fix/frontend-low-priority`; database `caldart_frontend_fixes`; e2e port 8131
- **Owns:** `frontend/src/portal/features/checkout/Checkout.tsx#invalidation`, `frontend/src/portal/features/checkout/PayPalPanel.tsx`, `frontend/src/portal/features/checkout/StripePanel.tsx#exports-and-effect`, `frontend/src/portal/features/checkout/*.test.tsx`, `frontend/src/portal/features/admin-members/api.ts#placeholder`, `frontend/src/portal/features/aircraft/api.ts#placeholder`, `frontend/src/portal/features/auth/LogoutPage.tsx` (deleted), `frontend/src/portal/features/auth/LogoutPage.test.tsx` (deleted), `frontend/src/portal/auth/useAuth.ts#logout`, `frontend/src/portal/layout/PortalLayout.tsx#logout-button`, `frontend/src/portal/layout/PortalLayout.test.tsx`, `frontend/src/portal/routes/auth.tsx#logout-route`, `frontend/src/portal/routes/index.test.tsx#logout`, `frontend/src/portal/features/join/AccountStep.tsx#different-account`, `frontend/src/portal/features/auth/form.tsx#narrowing`, `frontend/src/portal/features/leader/AircraftStatusCard.tsx#narrowing`, `frontend/src/portal/api/client.ts#same-origin`, `frontend/src/portal/api/client.test.ts`, `frontend/vite.config.ts#cors`, `frontend/e2e/**#logout`, `docs/user/member-guide.rst#sign-out`, `docs/developer/architecture.rst#logout-route`, `docs/developer/api-reference.rst#client`.
- **Steps:** §5's decisions on the no-op invalidation, `placeholderData`, the PayPal panel, sign-out (the button, the deleted route, the join-flow link), the same-origin client, `server.cors`, the three non-null assertions, the un-exported StripePanel internals, and the exhaustive-deps suppression (restructure the effect so the dependency list is honest). Add the test that a `CSRF Failed` 403 is retried once with a fresh token while a permission 403 surfaces its message unchanged.
- **Verify:** `make test`, `make e2e`; each fix has a test that fails on `origin/main`; `GET /portal/logout` while signed in answers the not-found screen and leaves the session intact.

#### reminders-for-account-admins (Opus)

- **Refs:** #58
- **Branch:** `feature/reminders-for-account-admins`; database `caldart_reminders_for_account_admins`; e2e port 8135
- **Owns:** `frontend/src/portal/features/system/RemindersPanel.tsx`, `frontend/src/portal/features/system/RemindersPanel.test.tsx`, `frontend/src/portal/features/system/ReminderLog.tsx` (new), `frontend/src/portal/features/system/ReminderLog.test.tsx` (new), `frontend/src/portal/features/admin-reminders/**` (new), `frontend/src/portal/routes/admin-reminders.tsx` (new), `frontend/src/portal/routes/index.tsx#admin-reminders`, `frontend/src/portal/routes/index.test.tsx#admin-reminders`, `frontend/src/portal/nav.ts#reminders`, `frontend/src/portal/nav.test.ts`, `frontend/e2e/reminders.spec.ts` (new), `docs/developer/reminders.rst#account-admin`, `docs/user/account-administrator-guide.rst#reminders`, `docs/user/overview.rst#reminders`, `docs/developer/architecture.rst#routes`.
- **Steps:** §5's reminder-log screen. The route test proves `account_admin` reaches it and `dart_leader` does not; the e2e spec signs in as the seeded account admin, opens Reminders, filters by kind, and never sees a run button.
- **Verify:** `make test`, `make e2e`; the system page's panel is unchanged for system admins.

#### frontend-tests (Opus)

- **Refs:** #59
- **Branch:** `test/frontend-low-priority`; database `caldart_frontend_tests`; e2e port 8132
- **Owns:** `frontend/vite.config.ts#test`, `frontend/tsconfig.json#paths`, `frontend/package.json`, `frontend/package-lock.json`, `frontend/src/test/**`, `frontend/src/portal/features/profile/fixtures.ts` (moves), `frontend/src/portal/features/admin-members/fixtures.ts` (moves), `frontend/src/portal/features/profile/form.test.ts`, `frontend/src/portal/features/checkout/CheckoutReturn.test.tsx`, `frontend/src/portal/routes/guards.test.tsx`, `frontend/src/portal/api/client.test.ts#verb-table`, `frontend/src/portal/components/DataTable.test.tsx`, `frontend/src/portal/PortalLayout.test.tsx` (new), `frontend/src/portal/App.test.tsx` (new), `frontend/src/portal/components/Toast.test.tsx` (new), `frontend/src/portal/features/auth/LoginPage.test.tsx#cache`, `frontend/src/**/*.test.ts*#alias-imports`, `frontend/e2e/**`, `frontend/playwright.config.ts`, `Makefile#coverage-frontend`, `docs/developer/testing.rst#frontend`.
- **Steps:** §5's decisions on message assertions, the `fetchPayment` failure test, the four missing component tests, `it.each` conversions with boundary and accented cases, the vitest config, coverage, the fixture move and `@test/` alias, and the e2e robustness and assertion items. The `client.test.ts` verb-table conversion is coordinated with `frontend-fixes` by touching only the `#verb-table` section.
- **Verify:** `make test`, `make e2e` three times in a row green (flake gate on), `make coverage-frontend` writes a report.

### Wave 2

#### backend-test-infra (Sonnet)

- **Refs:** #57
- **After:** tests-high-priority
- **Branch:** `test/backend-infra`; database `caldart_backend_test_infra`
- **Owns:** `pyproject.toml#pytest`, `pyproject.toml#dev-dependencies`, `pyproject.toml#coverage`, `uv.lock`, `backend/caldart/settings/test.py#static-root`, `backend/tests/conftest.py#manifest-fixture`, `backend/tests/conftest.py#today`, `backend/tests/conftest.py#markers`, `backend/tests/test_shell_views.py#marker`, `backend/tests/test_seed.py#slow`, `backend/tests/test_cms_seed_content.py#slow`, `backend/tests/test_sysadmin_settings.py#whitespace`, `backend/apps/accounts/seed.py#faker-instance` (or wherever `Faker.seed` lives), `backend/tests/test_members_admin.py#ordering-fixture`, `.github/workflows/ci.yml#backend-job`, `Makefile#test-targets`, `Makefile#coverage-backend`, `docs/developer/testing.rst#markers-coverage-randomly`, `.claude/rules/python_testing.md#markers`, `.claude/rules/environment.md#targets`.
- **Steps:** §5's decisions on the `slow` and `needs_frontend_build` markers, the manifest fixture in `tmp_path`, CI building the frontend, coverage, `STATIC_ROOT`, the frozen `today`, `pytest-randomly` and the ordering test, and the whitespace-tolerant Apache assertion.
- **Verify:** `uv run pytest -p randomly` green on three seeds; `make coverage-backend` writes a report; `git status` clean under `frontend/dist` after `make test-backend`.

#### backend-maintenance (Opus)

- **Refs:** #56
- **After:** backend-fixes
- **Branch:** `refactor/backend-maintenance`; database `caldart_backend_maintenance`
- **Owns:** `backend/apps/payments/api/serializers.py#dead-code`, `backend/apps/payments/models.py#dead-code`, `backend/apps/members/models.py#volunteer-interests`, `backend/apps/members/migrations/`, `backend/apps/payments/providers/base.py#registry`, `backend/apps/payments/providers/*.py#is-configured`, `backend/apps/cms/management/commands/seed_content.py`, `backend/apps/cms/management/commands/seed_content_data.py` (new), `backend/apps/cms/migrations/`, `backend/apps/sysadmin/services.py#streaming`, `backend/**/*.py#non-ascii`, `backend/tests/test_lint_config.py#ascii`, `backend/tests/test_sysadmin.py#streaming`, `backend/tests/test_payments_providers_registry.py` (new), `backend/tests/test_cms_seed_content.py#data-module`, `docs/developer/payments-setup.rst#is-configured`, `docs/developer/backup-restore.rst#streaming`, `docs/developer/cms.rst#seed-data`, `docs/developer/data-model.rst#volunteer-interests`, `docs/developer/setup.rst#migrations`.
- **Steps:** §5's decisions on dead code and its migration, the provider registry, the `seed_content` data module, the cms migration squash, streaming backups, and the non-ASCII sweep with its lint test. A migration regeneration is one commit that shows `makemigrations --check` clean and `make reset` succeeding.
- **Verify:** `make check`; `make reset && make seed` from an empty database; a 200 MB synthetic dump restores with resident memory under 100 MB (`/usr/bin/time -v`, figure in the PR).

#### frontend-maintenance (Sonnet)

- **Refs:** #58
- **After:** frontend-fixes, frontend-tests, reminders-for-account-admins
- **Branch:** `refactor/frontend-maintenance`; database `caldart_frontend_maintenance`; e2e port 8133
- **Owns:** `frontend/eslint.config.js#import-rules`, `frontend/eslint.config.js#handler-names`, `frontend/package.json`, `frontend/package-lock.json`, `frontend/src/portal/components/index.ts` (deleted), `frontend/src/portal/api/queries.ts` (new), `frontend/src/portal/api/types.ts#unions`, `frontend/src/portal/api/types.contract.test.ts`, `frontend/src/portal/features/profile/api.ts#cross-feature`, `frontend/src/**#import-style`, `frontend/src/**#handler-names`, `frontend/src/styles/index.css#font-subsets`, `backend/apps/payments/api/serializers.py#checkout-response`, `backend/apps/payments/api/views.py#checkout-schema`, `backend/tests/snapshots/openapi-components.json`, `backend/tests/test_openapi_contract.py#polymorphic`, `docs/developer/api-payments.rst#checkout-response`, `.claude/rules/javascript_typescript_best_practices.md#imports`, `.claude/rules/javascript_typescript_best_practices.md#handlers`.
- **Steps:** §5's decisions on the barrel, the import style and the shared queries module, the `handle*` rule and sweep, the discriminated `CheckoutResponse` and the two literal unions (backend serializer and snapshot updated in the same PR), and the Latin font subsets. Each lint rule lands with a deliberate violation shown failing in the PR.
- **Verify:** `make lint`, `make check`, `make e2e`; `npm run build` output lists no non-Latin font files.

### Wave 3

#### backend-test-hygiene (Opus)

- **Refs:** #57
- **After:** backend-test-infra, backend-maintenance
- **Branch:** `test/backend-hygiene`; database `caldart_backend_test_hygiene`
- **Owns:** `backend/tests/conftest.py#shared-helpers`, `backend/tests/conftest.py#roles`, `backend/tests/factories.py`, `backend/tests/test_integration.py` (split and deleted), `backend/tests/test_*.py#hygiene`, `.claude/rules/python_testing.md#style`, `docs/developer/testing.rst#layout`.
- **Steps:** §5's style decisions applied across the suite: `ROLE_MATRIX` in `conftest.py` and the five loops parametrized; `backup_dir`, `admin_client`, `register`, the CSV reader and the PDF page counter consolidated; unused fixtures and dead factory branches deleted; the redundant tests the audit enumerated removed (each with its surviving twin named in the PR); `test_integration.py` split into feature modules; the `_roles` fixture justified in its docstring or removed and `pytestmark` added to the eight modules; in-body imports hoisted; compound asserts split and the `test_leader_api.py` tautology fixed; naming and `.json()`/`settings` consistency.
- **Verify:** `make test`; the test count drops only by the removed tests listed in the PR; `uv run pytest -p randomly` green.

### Wave 4

#### backend-test-coverage (Opus)

- **Closes:** #57
- **After:** backend-test-hygiene
- **Branch:** `test/backend-coverage-gaps`; database `caldart_backend_test_coverage`
- **Owns:** `backend/tests/golden/` (new), `backend/tests/conftest.py#golden`, `backend/tests/test_boundaries.py` (new), `backend/tests/test_membership_transitions.py` (new), `backend/tests/test_payments_race.py` (new), `backend/tests/test_cms_seed.py` (new), `backend/tests/test_sysadmin_commands.py#drop-schema`, `backend/tests/test_payments_reports.py#golden`, `backend/tests/test_reminders.py#golden`, `backend/tests/test_*.py#exact-assertions`, `docs/developer/testing.rst#golden`.
- **Steps:** §5's golden files; exact values for the dozen truthiness, `>=` and superset assertions and the bare `pytest.raises` blocks; boundary tests (pagination 25 and 200, `expiring_within` overflow, `max_length`, non-ASCII names in the factories); the failed-to-succeeded payment and cancelled-to-active membership transitions; a threaded test of the `mark_succeeded` race; `cms/seed.py`'s site-root repair; `drop_schema` through a recording cursor. The PR body lists every item of #57 with the PR that settled it.
- **Verify:** `make test`; the race test fails with `select_for_update` removed and passes with it restored.

#### frontend-closeout (Sonnet)

- **Closes:** #56, #58, #59
- **After:** backend-maintenance, frontend-maintenance
- **Branch:** `chore/low-priority-closeout`; database `caldart_frontend_closeout`; e2e port 8134
- **Owns:** `frontend/src/**#residue`, `backend/**#residue`, `docs/**#residue`.
- **Steps:** Re-run the audit's checks for #56, #58 and #59 item by item against `main`; fix any residue a package left (small, in-scope items only); the PR body lists every item of the three issues with the PR that settled it. If nothing is left, the PR is the list alone and touches no code.
- **Verify:** `make lint test check docs audit e2e` green.

## 8. Manifest

```json
[
  {"wave": 1, "package": "tests-high-priority", "model": "opus", "branch": "test/high-priority-findings", "database": "caldart_tests_high_priority", "e2e_port": null, "closes": [], "refs": [57], "owns": ["backend/tests/conftest.py#respx-guard", "backend/tests/conftest.py#pdf-decoder", "backend/tests/test_payments_paypal.py", "backend/tests/test_payments_stripe.py#http-guard", "backend/tests/test_aircraft_exports.py#pdf-content", "backend/tests/test_reports.py#pdf-content", "docs/developer/testing.rst#http-guard"], "after": []},
  {"wave": 1, "package": "backend-fixes", "model": "opus", "branch": "fix/backend-low-priority", "database": "caldart_backend_fixes", "e2e_port": null, "closes": [], "refs": [56], "owns": ["backend/apps/payments/api/serializers.py#contribution-max", "backend/apps/accounts/api/views.py#login-disclosure", "backend/apps/accounts/permissions.py#getattr", "backend/caldart/reports.py#escape-and-csv", "backend/apps/sysadmin/services.py#credentials", "backend/apps/payments/views.py#getattr", "backend/apps/payments/providers/paypal.py#token-cache", "backend/apps/payments/providers/paypal.py#getattr", "backend/tests/test_backend_fixes.py", "docs/developer/reports.rst#csv-policy", "docs/developer/api-auth.rst#login-errors", "docs/developer/backup-restore.rst#credentials", "docs/developer/payments-setup.rst#token-cache"], "after": []},
  {"wave": 1, "package": "frontend-fixes", "model": "opus", "branch": "fix/frontend-low-priority", "database": "caldart_frontend_fixes", "e2e_port": 8131, "closes": [], "refs": [58], "owns": ["frontend/src/portal/features/checkout/Checkout.tsx#invalidation", "frontend/src/portal/features/checkout/PayPalPanel.tsx", "frontend/src/portal/features/checkout/StripePanel.tsx#exports-and-effect", "frontend/src/portal/features/checkout/*.test.tsx", "frontend/src/portal/features/admin-members/api.ts#placeholder", "frontend/src/portal/features/aircraft/api.ts#placeholder", "frontend/src/portal/features/auth/LogoutPage.tsx", "frontend/src/portal/features/auth/LogoutPage.test.tsx", "frontend/src/portal/auth/useAuth.ts#logout", "frontend/src/portal/layout/PortalLayout.tsx#logout-button", "frontend/src/portal/layout/PortalLayout.test.tsx", "frontend/src/portal/routes/auth.tsx#logout-route", "frontend/src/portal/routes/index.test.tsx#logout", "frontend/src/portal/features/join/AccountStep.tsx#different-account", "frontend/src/portal/features/auth/form.tsx#narrowing", "frontend/src/portal/features/leader/AircraftStatusCard.tsx#narrowing", "frontend/src/portal/api/client.ts#same-origin", "frontend/src/portal/api/client.test.ts", "frontend/vite.config.ts#cors", "frontend/e2e/**#logout", "docs/user/member-guide.rst#sign-out", "docs/developer/architecture.rst#logout-route", "docs/developer/api-reference.rst#client"], "after": []},
  {"wave": 1, "package": "reminders-for-account-admins", "model": "opus", "branch": "feature/reminders-for-account-admins", "database": "caldart_reminders_for_account_admins", "e2e_port": 8135, "closes": [], "refs": [58], "owns": ["frontend/src/portal/features/system/RemindersPanel.tsx", "frontend/src/portal/features/system/RemindersPanel.test.tsx", "frontend/src/portal/features/system/ReminderLog.tsx", "frontend/src/portal/features/system/ReminderLog.test.tsx", "frontend/src/portal/features/admin-reminders/**", "frontend/src/portal/routes/admin-reminders.tsx", "frontend/src/portal/routes/index.tsx#admin-reminders", "frontend/src/portal/routes/index.test.tsx#admin-reminders", "frontend/src/portal/nav.ts#reminders", "frontend/src/portal/nav.test.ts", "frontend/e2e/reminders.spec.ts", "docs/developer/reminders.rst#account-admin", "docs/user/account-administrator-guide.rst#reminders", "docs/user/overview.rst#reminders", "docs/developer/architecture.rst#routes"], "after": []},
  {"wave": 1, "package": "frontend-tests", "model": "opus", "branch": "test/frontend-low-priority", "database": "caldart_frontend_tests", "e2e_port": 8132, "closes": [], "refs": [59], "owns": ["frontend/vite.config.ts#test", "frontend/tsconfig.json#paths", "frontend/package.json", "frontend/package-lock.json", "frontend/src/test/**", "frontend/src/portal/features/profile/fixtures.ts", "frontend/src/portal/features/admin-members/fixtures.ts", "frontend/src/portal/features/profile/form.test.ts", "frontend/src/portal/features/checkout/CheckoutReturn.test.tsx", "frontend/src/portal/routes/guards.test.tsx", "frontend/src/portal/api/client.test.ts#verb-table", "frontend/src/portal/components/DataTable.test.tsx", "frontend/src/portal/PortalLayout.test.tsx", "frontend/src/portal/App.test.tsx", "frontend/src/portal/components/Toast.test.tsx", "frontend/src/portal/features/auth/LoginPage.test.tsx#cache", "frontend/src/**/*.test.ts*#alias-imports", "frontend/e2e/**", "frontend/playwright.config.ts", "Makefile#coverage-frontend", "docs/developer/testing.rst#frontend"], "after": []},
  {"wave": 2, "package": "backend-test-infra", "model": "sonnet", "branch": "test/backend-infra", "database": "caldart_backend_test_infra", "e2e_port": null, "closes": [], "refs": [57], "owns": ["pyproject.toml#pytest", "pyproject.toml#dev-dependencies", "pyproject.toml#coverage", "uv.lock", "backend/caldart/settings/test.py#static-root", "backend/tests/conftest.py#manifest-fixture", "backend/tests/conftest.py#today", "backend/tests/conftest.py#markers", "backend/tests/test_shell_views.py#marker", "backend/tests/test_seed.py#slow", "backend/tests/test_cms_seed_content.py#slow", "backend/tests/test_sysadmin_settings.py#whitespace", "backend/apps/**/seed*.py#faker-instance", "backend/tests/test_members_admin.py#ordering-fixture", ".github/workflows/ci.yml#backend-job", "Makefile#test-targets", "Makefile#coverage-backend", "docs/developer/testing.rst#markers-coverage-randomly", ".claude/rules/python_testing.md#markers", ".claude/rules/environment.md#targets"], "after": ["tests-high-priority"]},
  {"wave": 2, "package": "backend-maintenance", "model": "opus", "branch": "refactor/backend-maintenance", "database": "caldart_backend_maintenance", "e2e_port": null, "closes": [], "refs": [56], "owns": ["backend/apps/payments/api/serializers.py#dead-code", "backend/apps/payments/models.py#dead-code", "backend/apps/members/models.py#volunteer-interests", "backend/apps/members/migrations/*", "backend/apps/payments/providers/base.py#registry", "backend/apps/payments/providers/*.py#is-configured", "backend/apps/cms/management/commands/seed_content.py", "backend/apps/cms/management/commands/seed_content_data.py", "backend/apps/cms/migrations/*", "backend/apps/sysadmin/services.py#streaming", "backend/**/*.py#non-ascii", "backend/tests/test_lint_config.py#ascii", "backend/tests/test_sysadmin.py#streaming", "backend/tests/test_payments_providers_registry.py", "backend/tests/test_cms_seed_content.py#data-module", "docs/developer/payments-setup.rst#is-configured", "docs/developer/backup-restore.rst#streaming", "docs/developer/cms.rst#seed-data", "docs/developer/data-model.rst#volunteer-interests", "docs/developer/setup.rst#migrations"], "after": ["backend-fixes"]},
  {"wave": 2, "package": "frontend-maintenance", "model": "sonnet", "branch": "refactor/frontend-maintenance", "database": "caldart_frontend_maintenance", "e2e_port": 8133, "closes": [], "refs": [58], "owns": ["frontend/eslint.config.js#import-rules", "frontend/eslint.config.js#handler-names", "frontend/package.json", "frontend/package-lock.json", "frontend/src/portal/components/index.ts", "frontend/src/portal/api/queries.ts", "frontend/src/portal/api/types.ts#unions", "frontend/src/portal/api/types.contract.test.ts", "frontend/src/portal/features/profile/api.ts#cross-feature", "frontend/src/**#import-style", "frontend/src/**#handler-names", "frontend/src/styles/index.css#font-subsets", "backend/apps/payments/api/serializers.py#checkout-response", "backend/apps/payments/api/views.py#checkout-schema", "backend/tests/snapshots/openapi-components.json", "backend/tests/test_openapi_contract.py#polymorphic", "docs/developer/api-payments.rst#checkout-response", ".claude/rules/javascript_typescript_best_practices.md#imports", ".claude/rules/javascript_typescript_best_practices.md#handlers"], "after": ["frontend-fixes", "frontend-tests", "reminders-for-account-admins"]},
  {"wave": 3, "package": "backend-test-hygiene", "model": "opus", "branch": "test/backend-hygiene", "database": "caldart_backend_test_hygiene", "e2e_port": null, "closes": [], "refs": [57], "owns": ["backend/tests/conftest.py#shared-helpers", "backend/tests/conftest.py#roles", "backend/tests/factories.py", "backend/tests/test_integration.py", "backend/tests/test_*.py#hygiene", ".claude/rules/python_testing.md#style", "docs/developer/testing.rst#layout"], "after": ["backend-test-infra", "backend-maintenance"]},
  {"wave": 4, "package": "backend-test-coverage", "model": "opus", "branch": "test/backend-coverage-gaps", "database": "caldart_backend_test_coverage", "e2e_port": null, "closes": [57], "refs": [], "owns": ["backend/tests/golden/*", "backend/tests/conftest.py#golden", "backend/tests/test_boundaries.py", "backend/tests/test_membership_transitions.py", "backend/tests/test_payments_race.py", "backend/tests/test_cms_seed.py", "backend/tests/test_sysadmin_commands.py#drop-schema", "backend/tests/test_payments_reports.py#golden", "backend/tests/test_reminders.py#golden", "backend/tests/test_*.py#exact-assertions", "docs/developer/testing.rst#golden"], "after": ["backend-test-hygiene"]},
  {"wave": 4, "package": "frontend-closeout", "model": "sonnet", "branch": "chore/low-priority-closeout", "database": "caldart_frontend_closeout", "e2e_port": 8134, "closes": [56, 58, 59], "refs": [], "owns": ["frontend/src/**#residue", "backend/**#residue", "docs/**#residue"], "after": ["backend-maintenance", "frontend-maintenance"]}
]
```
