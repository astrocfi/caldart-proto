# Tooling and documentation follow-ups: the low-priority findings in #60 and #61

This plan works through the documentation findings collected in #60 and the tooling and
cross-cutting findings in #61, as re-audited on 2026-09-21 against `main`
(`critiques/2026-09-21-remaining-findings.md`), plus two findings that audit showed no
issue had captured: an API page for the reminder, system and site endpoints, and the
abstract models in the data-model diagram. Fifteen work packages in three waves; eight
run on Sonnet, seven on Opus (§7 names the model for each).

## 1. How to run this plan

The orchestrator runs waves in order. Within a wave, packages run in parallel, each in its
own worktree and branch, and each is reviewed by one adversarial reviewer confined to the
diff. The orchestrator reads every PR before merging it: no PR auto-merges. A package's
`after` list in the §8 manifest names the packages that must be merged before it starts,
so a later wave may start a package as soon as its own dependencies have merged.

## 2. Preconditions

- This plan is on `main` and every package of `plans/archive/2026-09-14-non-low-issues.md`
  has merged (it has: PRs #69 to #128).
- `make up` is running; `main` is green.
- Issues #60 and #61 are open. No new issue is opened for the two uncaptured findings; the
  packages that carry them say so in their PR bodies, and #60 closes when its last package
  merges.

## 3. Conventions for every work package

Every worker follows `CLAUDE.md` and the rules in `.claude/rules/`. On top of those:

- **Branch and worktree.** `git fetch origin && git worktree add .claude/worktrees/<package> -b <branch> origin/main`, with the branch from the manifest.
- **Database.** `DATABASE_URL=postgres://caldart:caldart@localhost:5432/<database>` from the manifest, then `make createdb`.
- **End-to-end runs.** A package with an `e2e_port` runs `make e2e E2E_PORT=<e2e_port> E2E_DB=<database>_e2e`.
- **Docs are the specification.** Every docs change describes the current state of the software only; never "new", "now", "legacy", "previously". Never cite a plan from the docs, docstrings or comments. `critiques/` files are dated records: never edit them. The archived plans are frozen.
- **Docs pages must build.** `make docs` runs `sphinx-build -n -W`; a warning is a failure. A new page goes into the toctree of its section index in the same commit. Diagrams follow `doc_python` §5: a `.. only:: graphviz` block with an ASCII equivalent in `.. only:: not graphviz`.
- **Scope.** Edit only the files the package owns (§7 and the manifest; a `#section` suffix limits the part of a file), plus new pages and new test files it names. If a change genuinely needs another file, keep it additive and say so in the PR under Potential Impacts.
- **Test first** for every behavior change (`python_testing` §1); a tooling package that adds a gate proves the gate bites (a deliberate violation fails it) before it lands, and says so in the PR.
- **Frontend dependencies.** npm 10 crashes on this tree; add or upgrade packages with `npx -y npm@11 install …`, then verify with a clean `npm ci`.
- **Commits.** Conventional Commits, one logical change per commit, every message ending with the two trailer lines from `CLAUDE.md`, naming the model doing the work (`Claude Sonnet 5` or `Claude Opus 5`).
- **Gates.** `make lint test check docs audit` must pass before the PR opens, plus `make e2e` where the manifest gives a port, plus the package's own "Verify" list.
- **Pull request.** `gh pr create --base main`, body per `.github/pull_request_template.md`, with one `Refs #N.` sentence per issue in `refs` and one `Closes #N.` per issue in `closes`.

## 4. Merging

The orchestrator merges each approved PR itself, one at a time, after reading it against
its manifest scope and the reviewer's report: rebase on `main` if needed (a docs page or
a config list edited by two packages is the expected conflict; keep both sides' changes),
gates green, CI green, `gh pr merge --squash`, `main` green afterwards, then the worktree
and branch are removed. Nothing merges on a red check.

## 5. Decisions

Settled here so no worker has to choose:

- **Node.** Pin Node 22, the version CI already uses: `engines.node` in `frontend/package.json` as `>=22 <23`, a `.nvmrc` reading `22`, and the prose in `README.rst` and `setup.rst` says 22.
- **Python minimums.** `django>=5.2,<6.0`, `wagtail>=8.0`, `djangorestframework>=3.18`, matching what the lock resolves. The `<6.0` bound stays, with a comment beside it: the lock and gates are verified on Django 5.2 only, and the bound moves when the lock does.
- **`make help`.** Add a `##` comment to every target that lacks one rather than softening the claim; internal helpers such as `wait-db` get a comment that says they are helpers.
- **Deploy check.** `make check-deploy` runs `manage.py check --deploy --fail-level WARNING --settings caldart.settings.prod` with a throwaway environment set inline (a dummy `SECRET_KEY`, `ALLOWED_HOSTS`, `DATABASE_URL`, `SITE_URL`, and the secure flags on). It runs in CI's backend job. `security.W019` is silenced in `prod.py` with a comment: `X_FRAME_OPTIONS = "SAMEORIGIN"` is deliberate because the Wagtail admin previews pages in a same-origin frame.
- **Ruff.** Enable both `RUF` and `N` (the audit measured five `N` diagnostics and the rest auto-fixable). Fix every diagnostic; do not add ignores. Delete the `noqa` directives for rules that are not selected (`S603`, `BLE001`) and the `N802` ones once `N` is on and the names are fixed or, where DRF's method names such as `has_permission` are imposed, replaced by the narrowest per-line `noqa` with a comment.
- **ESLint.** Adopt `tseslint.configs.recommendedTypeChecked` with `languageOptions.parserOptions.projectService` (not a hand-listed `project` array) and fix every diagnostic; suppressions only where a library's types force one, each with a comment. Add `eslint-plugin-jsx-a11y` with its `recommended` flat config and fix its findings. Test-only types (`vitest/globals`, `@testing-library/jest-dom`) move to a `tsconfig.test.json` that `include`s test files and `src/test/`, referenced by the vitest config's `typecheck` and by ESLint's project service.
- **Content-Security-Policy.** Use `django-csp` (the `CSP_*` settings of its 4.x `CONTENT_SECURITY_POLICY` dict form). Enforce, not report-only. Sources: `default-src 'self'`; `script-src 'self' https://js.stripe.com https://www.paypal.com https://www.sandbox.paypal.com`; `frame-src` the same two vendors; `connect-src 'self' https://api.stripe.com https://www.paypal.com https://www.sandbox.paypal.com`; `img-src 'self' data:`; `style-src 'self' 'unsafe-inline'` (Stripe's Payment Element and Wagtail's admin both inject inline styles; the templates carry no inline scripts). In `dev.py`, add the Vite dev server origin and `ws:` for HMR. The Wagtail admin path gets `script-src 'self' 'unsafe-inline'` through django-csp's per-view exemption, because Wagtail's admin inlines scripts. The checkout e2e specs and the Wagtail admin smoke test must pass with the header on.
- **API contract test.** Add `drf-spectacular`; `make check-backend` generates `backend/openapi.json` (not committed) and a backend test asserts the schema's component names and field sets match a committed snapshot at `backend/tests/snapshots/openapi-components.json` (update by running the test with `--snapshot-update` style flag documented in `testing.rst`). On the frontend, `openapi-typescript` generates `src/portal/api/schema.d.ts` from that JSON (not committed; generated by `make check-frontend` before `tsc`), and a type-level vitest test asserts each interface in `api/types.ts` is mutually assignable with its schema counterpart. That is the contract: a serializer change that the TS types do not follow fails `make check`.
- **The API pages.** Every endpoint gets a heading in the form `` `GET /admin/members` `` (method and path), a one-paragraph description, a request example where there is a body, a `code-block:: json` response example, and a status list covering every status the view can answer. Pages keep their prose sections between endpoints. A new `docs/developer/api-system.rst` documents the reminder, system and site endpoints; `api-reference.rst` and the developer index link it.
- **Diagrams.** Graphviz with an ASCII equivalent, per the docs rule. The member-lifecycle diagram lives on a new `docs/user/overview.rst`, first in the user toctree. The checkout sequence diagram goes in `payments-setup.rst`. The production topology goes in `deployment.rst`. The abstract models (`TimestampedModel`, `BasePage`) join the existing data-model diagram.
- **How-to articles.** Four pages under `docs/user/how-to/`: grant or correct a membership by hand, run and check the reminders, restore a backup, and preview and select a theme. Each follows the how-to shape (prerequisites, numbered steps, what success looks like, troubleshooting, related pages). `demo-walkthrough.rst` takes the same shape, with its five tasks as numbered sections.
- **Extension recipes.** One page, `docs/developer/extending.rst`, with a code skeleton for each of: a payment provider, an API endpoint, a portal screen, a management command, a page type and a block (the last two replace the prose recipes in `cms.rst`, which then link here). Skeletons are complete enough to compile after renaming; each states which docs page must change with it.
- **Cross-references.** Every cross-directory `:doc:` target is written absolute (`/developer/...`, `/user/...`). Each subsystem chapter ends with a "Related" section linking its API page.
- **README.** Sections in this order: title (plain "CalDART"), one-paragraph description, Features, Requirements, Setup, Documentation (links to the built docs and the two guides), Contributing (the gates and the PR conventions in five lines, linking `testing.rst`), License. The end-to-end section shrinks to three lines linking `testing.rst`.
- **`nitpicky = True`.** Turn it on; fix every reference it surfaces rather than adding to `nitpick_ignore`, unless the target genuinely cannot resolve, in which case the entry carries a comment.

## 6. Failure handling and the final report

- **A failing gate.** Three fix attempts within scope; then the PR stays open as a draft with a comment on #60 or #61 saying what failed, and the orchestrator carries on with every package that does not depend on it.
- **A rebase conflict outside the package's files.** Same.
- **CI red on `main`.** No new package starts until a fix PR restores it.
- **The final report** lists every PR merged, every item of #60 and #61 still open and why, and every decision taken that §5 did not cover.
- **Archive.** When every package has merged, one last PR moves this plan to `plans/archive/`.

## 7. Work packages

### Wave 1

#### make-help-and-pins (Sonnet)

- **Refs:** #61
- **Branch:** `chore/make-help-and-pins`; database `caldart_make_help_and_pins`
- **Owns:** `Makefile#help-comments`, `frontend/package.json#engines`, `.nvmrc` (new), `README.rst#requirements`, `docs/developer/setup.rst#requirements`, `pyproject.toml#dependencies`.
- **Steps:**
  1. Add a `##` comment to `wait-db`, `lint-backend`, `lint-spelling`, `lint-frontend`, `check-backend`, `check-frontend`, `audit-backend`, `audit-frontend`, so `make help` really lists every target (§5).
  2. Pin Node 22 (§5) and update the two prose mentions.
  3. Raise the three dependency minimums and comment the `<6.0` bound (§5); `uv lock` must not change any resolved version (`git diff uv.lock` empty or metadata-only).
- **Verify:** `make help | wc -l` equals the number of targets in `.PHONY`; `node -e "require('./frontend/package.json').engines"` prints the range; `uv lock --check` passes.

#### ruff-ruf-n (Sonnet)

- **Refs:** #61
- **Branch:** `chore/ruff-ruf-n`; database `caldart_ruff_ruf_n`
- **Owns:** `pyproject.toml#ruff`, every backend `.py` file the new rules flag (fixes only), `.claude/rules/python.md#ruff-categories`, `docs/developer/testing.rst#ruff`.
- **Steps:** enable `RUF` and `N` (§5), fix every diagnostic, delete the unselected-rule `noqa` directives, and update the rule table in `python.md` §7 and the ruff sentence in `testing.rst`.
- **Verify:** `uv run ruff check backend` clean; `git grep -n "noqa: \(S603\|BLE001\)"` empty; the full backend suite passes.

#### eslint-type-checked (Opus)

- **Refs:** #61
- **Branch:** `chore/eslint-type-checked`; database `caldart_eslint_type_checked`; e2e port 8121
- **Owns:** `frontend/eslint.config.js`, `frontend/tsconfig.json`, `frontend/tsconfig.test.json` (new), `frontend/vite.config.ts#test-typecheck`, `frontend/package.json#devDependencies`, `frontend/package-lock.json`, every file under `frontend/src` and `frontend/e2e` the new rules flag (fixes only), `.claude/rules/javascript_typescript_best_practices.md#lint`, `docs/developer/testing.rst#eslint`.
- **Steps:** §5's ESLint decision: type-checked preset with the project service, `jsx-a11y`, the test-only tsconfig, then fix every diagnostic. An accessibility finding is fixed in the markup, not suppressed. Document the two new rule sources in the rules file and `testing.rst`.
- **Verify:** `cd frontend && npx eslint . --max-warnings 0` clean; `npx tsc --noEmit -p tsconfig.json` and `-p tsconfig.test.json` clean; a throwaway file with an unawaited promise fails lint (`@typescript-eslint/no-floating-promises`), then is deleted.

#### user-guide-corrections (Sonnet)

- **Refs:** #60
- **Branch:** `docs/user-guide-corrections`; database `caldart_user_guide_corrections`
- **Owns:** `docs/user/system-administrator-guide.rst`, `docs/user/account-administrator-guide.rst`, `docs/user/getting-started.rst`, `docs/user/website-administrator-guide.rst`, `docs/user/member-guide.rst`, `docs/user/index.rst`, `docs/user/payments.rst#placement`, `docs/developer/deployment.rst#troubleshooting-label`.
- **Steps:**
  1. `system-administrator-guide.rst`: line 208 says any name `--name` accepts is downloadable; lines 169 and 245-246 show the full `caldart_manage` invocation and link the operator-commands section; document `health --json`'s always-zero exit status with a sample JSON body; lines 25-26 state that every system administrator is a Django superuser (`accounts/services.py:140` always sets it); line 52 becomes a `:ref:` to a new label above `deployment.rst:540`.
  2. `account-administrator-guide.rst:10`: the role also covers Payments and Aircraft (`nav.ts:45-47`).
  3. `getting-started.rst:74-75`: the account_admin row includes leader checks and deletion; `:167-168` lists "Change password".
  4. `website-administrator-guide.rst:264,269`: quote Wagtail's generated labels ("Org name", "Facebook url", "Twitter url").
  5. `member-guide.rst`: add `:doc:` links to the pages it mentions.
  6. `index.rst`: trim lines 5-11 and 38-39 to a short intro; move `payments.rst` out of "For members" to the administrator group.
  7. Expand DART as "Disaster Airlift Response Team" on its first use in the user guide.
- **Verify:** `make docs` clean; each cited line matches the code it describes.

#### faq-and-walkthrough (Sonnet)

- **Refs:** #60
- **Branch:** `docs/faq-and-walkthrough`; database `caldart_faq_and_walkthrough`
- **Owns:** `docs/user/faq.rst`, `docs/demo-walkthrough.rst#facts`.
- **Steps:**
  1. `faq.rst:83`: the tab is "Test payment"; `:182`: "Forgot your password?" (`LoginPage.tsx:82`); `:110`: drop "yet"; add a `:doc:` link on each of the fourteen answers that has none.
  2. `demo-walkthrough.rst:122`: "Test payment"; `:143`: quote the message the code shows for a duplicate email (`accounts/api/serializers.py`); `:36-37`: checkout runs on the same `:8000`; `:363-364`: a website administrator can open `/django-admin/` because `services.py:141` sets `is_staff`.
- **Verify:** `make docs` clean; every quoted label exists in the source it cites.

#### api-members-aircraft-profile (Opus)

- **Refs:** #60
- **Branch:** `docs/api-members-aircraft-profile`; database `caldart_api_members_aircraft_profile`
- **Owns:** `docs/developer/api-members.rst`, `docs/developer/api-aircraft.rst`, `docs/developer/api-profile.rst`.
- **Steps:** bring the three pages to the §5 format, reading each view and serializer as you go:
  1. `api-members.rst`: method-and-path headings replace "List members", "Create a member" and the rest; a JSON example and status list for every endpoint; `DELETE /admin/members/{user_id}` documents 204 and 404 and the three 403 refusals; `:327-328` states the real grant start rule (`_latest_expiry` takes the maximum `ends_on` across active terms, so a future-dated term moves the start).
  2. `api-aircraft.rst`: document `PUT /aircraft/{id}` (the view is a `RetrieveUpdateDestroyAPIView`); fix `:227-231`, since `membership_ok` is computed from terms regardless of profile (`aircraft/services.py:100-102`); JSON examples and status lists throughout.
  3. `api-profile.rst`: JSON examples and status lists throughout.
- **Verify:** `make docs` clean; for each documented status, `git grep` finds the code path that produces it; the full backend suite is unchanged.

#### api-auth-payments-system (Opus)

- **Refs:** #60
- **Branch:** `docs/api-auth-payments-system`; database `caldart_api_auth_payments_system`
- **Owns:** `docs/developer/api-auth.rst`, `docs/developer/api-payments.rst`, `docs/developer/api-reference.rst`, `docs/developer/api-system.rst` (new), `docs/developer/index.rst#toctree`.
- **Steps:**
  1. `api-auth.rst` and `api-payments.rst`: the §5 format; `api-payments.rst:142` says `custom_id` is checked only when present (`paypal.py:367-368`); the example datetimes at `:276-277` carry the project's offset, not `Z`.
  2. `api-reference.rst`: `:200-213` names the aircraft list among the views overriding the filter backends (`aircraft/api/views.py:68`); `:226-227` says field errors are lists except where noted and notes the bare-string cases; `:276` says four endpoints across three throttle scopes; `:19-22` links the new page instead of deferring to prose chapters.
  3. New `api-system.rst`: every endpoint under `/system/`, `/reminders/` and `/site/` (read `caldart/api_urls.py` and the three apps' `api/urls.py`), in the §5 format, with the permission each requires; add it to the developer toctree and to the API summary table in `api-reference.rst`.
- **Verify:** `make docs` clean; every route in `api_urls.py` appears on exactly one API page (`git grep` each path).

### Wave 2

#### check-deploy (Sonnet)

- **Refs:** #61
- **After:** make-help-and-pins
- **Branch:** `chore/check-deploy`; database `caldart_check_deploy`
- **Owns:** `Makefile#check-deploy`, `.github/workflows/ci.yml#backend-job`, `backend/caldart/settings/prod.py#silenced-checks`, `docs/developer/testing.rst#gates`, `docs/developer/deployment.rst#check-deploy`, `.claude/rules/environment.md#gates`.
- **Steps:** §5's deploy check; `make check` calls `check-deploy` after `check-backend`; CI's backend job runs it; W019 silenced with its comment; the three docs describe the gate.
- **Verify:** `make check-deploy` passes; with `SECURE_SSL_REDIRECT=false` in the throwaway environment it fails on W008, proving the gate bites.

#### content-security-policy (Opus)

- **Refs:** #61
- **After:** make-help-and-pins
- **Branch:** `feature/content-security-policy`; database `caldart_content_security_policy`; e2e port 8122
- **Owns:** `pyproject.toml#dependencies`, `uv.lock`, `backend/caldart/settings/base.py#csp`, `backend/caldart/settings/dev.py#csp`, `backend/caldart/settings/prod.py#csp`, `backend/caldart/settings/test.py#csp`, `backend/apps/cms/wagtail_hooks.py#csp` (or a middleware module under `backend/caldart/` if the admin exemption needs one), `backend/tests/test_csp.py` (new), `docs/developer/deployment.rst#csp`, `docs/developer/configuration.rst#csp`, `docs/developer/payments-setup.rst#csp`, `deploy/caldart.env.example#csp`.
- **Steps:** §5's policy. Tests assert the exact header on a public page, on a portal page, and the admin exemption; the checkout e2e specs (Stripe mock and PayPal panels) pass with the header enforced; `make e2e` on the package's port.
- **Verify:** `curl -sI http://localhost:8000/ | grep -i content-security-policy` shows the policy; e2e green.

#### developer-guide-corrections (Sonnet)

- **Refs:** #60
- **After:** make-help-and-pins, user-guide-corrections, faq-and-walkthrough
- **Branch:** `docs/developer-guide-corrections`; database `caldart_developer_guide_corrections`
- **Owns:** `docs/conf.py`, `docs/index.rst`, `docs/developer/index.rst#intro`, `docs/developer/roadmap.rst`, `docs/developer/deployment.rst#wording`, `docs/developer/data-model.rst#timestamps`, `docs/developer/reminders.rst#add-a-kind`, `docs/developer/cms.rst#handbook-example`, `docs/developer/reports.rst#is-active-warning`, `docs/developer/testing.rst#e2e-env`, `docs/developer/setup.rst#smoke-test`, the "Related" sections of `payments-setup.rst`, `reminders.rst`, `backup-restore.rst`, `theming.rst`, `cms.rst`, `reports.rst`, every relative `../` `:doc:` target in `docs/`, `backend/tests/test_integration.py#history-comments`, `frontend/src/portal/features/profile/AircraftEditor.tsx#header-comment`.
- **Steps:**
  1. `conf.py`: `nitpicky = True` (§5), drop the duplicate `master_doc`, remove "yet" at `:121`.
  2. `docs/index.rst`: expand DART on first use.
  3. `developer/index.rst:5-11`: name the reader and contrast with the user guide.
  4. `roadmap.rst:45,76,81,95`, `deployment.rst:537`: remove the time-anchored wording.
  5. `data-model.rst:19-21`: `BasePage` and `SiteSettings` carry no `created_at`/`updated_at`.
  6. `reminders.rst:243-246`: the add-a-kind steps include `KIND_ORDER` (`reminders/services.py:53`) and the frontend `ReminderKind` and `KIND_LABELS`.
  7. `cms.rst:113-118`: the `HandbookPage` example declares the `body` field it panels; delete the `DartPage.__str__` claim at `:222-224`.
  8. `reports.rst:202-207`: delete the stale `is_active` warning (`aircraft/api/views.py:141` includes the filter).
  9. `testing.rst`: document `E2E_PORT`, `E2E_DB`, `E2E_DATABASE_URL`, `E2E_LOG`, `SKIP_CREATEDB`, `E2E_BASE_URL` and `CI`.
  10. `setup.rst:100-149`: a smoke test after `make run` showing what a working result looks like.
  11. The six chapters end with a "Related" section linking their API page (§5).
  12. Convert the eighteen relative cross-directory `:doc:` targets to absolute form.
  13. Remove the change history at `test_integration.py:61,119` and the history-named test at `:140`, and at `AircraftEditor.tsx:4-7`.
- **Verify:** `make docs` clean with `nitpicky` on; `git grep -n ":doc:\`[^/\`]*\.\./" docs` empty.

#### how-to-articles (Sonnet)

- **Refs:** #60
- **After:** faq-and-walkthrough, user-guide-corrections
- **Branch:** `docs/how-to-articles`; database `caldart_how_to_articles`
- **Owns:** `docs/user/how-to/` (new pages), `docs/user/index.rst#toctree`, `docs/demo-walkthrough.rst#structure`.
- **Steps:** §5's four how-to pages, each verified against the current UI and commands (read the guides and the code, and run the commands where they are cheap); `demo-walkthrough.rst` restructured into the how-to shape with its five tasks as numbered sections; the user toctree lists the new pages.
- **Verify:** `make docs` clean; every command in a how-to page runs as written in a fresh worktree.

### Wave 3

#### api-contract-test (Opus)

- **Closes:** #61
- **After:** check-deploy, ruff-ruf-n, eslint-type-checked, content-security-policy
- **Branch:** `feature/api-contract-test`; database `caldart_api_contract_test`
- **Owns:** `pyproject.toml#dependencies`, `uv.lock`, `backend/caldart/settings/base.py#spectacular`, `backend/caldart/api_urls.py#schema`, `backend/tests/test_openapi_contract.py` (new), `backend/tests/snapshots/` (new), `Makefile#check-backend`, `Makefile#check-frontend`, `frontend/package.json`, `frontend/package-lock.json`, `frontend/src/portal/api/schema.d.ts` (generated, gitignored), `frontend/src/portal/api/types.contract.test.ts` (new), `.gitignore`, `docs/developer/testing.rst#contract`, `docs/developer/api-reference.rst#schema`, `.claude/rules/javascript_typescript_best_practices.md#api-types`.
- **Steps:** §5's contract test. The PR shows both halves biting: renaming a serializer field fails the backend snapshot test, and changing an interface in `types.ts` fails the type-level test.
- **Verify:** `make check` passes; the two deliberate breakages fail, then are reverted.

#### diagrams-and-overview (Opus)

- **Refs:** #60
- **After:** user-guide-corrections, developer-guide-corrections
- **Branch:** `docs/diagrams-and-overview`; database `caldart_diagrams_and_overview`
- **Owns:** `docs/user/overview.rst` (new), `docs/user/index.rst#toctree`, `docs/developer/payments-setup.rst#sequence`, `docs/developer/deployment.rst#topology`, `docs/developer/data-model.rst#diagram`.
- **Steps:** §5's four diagrams, each with its ASCII twin. The lifecycle diagram's states and reminder kinds come from `members/services.py` and `reminders/models.py`; the sequence diagram from `payments/services.py` and the two providers; the topology from `deploy/`; the abstract models from `caldart/models.py` and `cms/models.py`.
- **Verify:** `make docs` clean with and without `dot` on `PATH` (temporarily shadow it to prove the ASCII branch builds).

#### readme-restructure (Sonnet)

- **Refs:** #60
- **After:** make-help-and-pins, developer-guide-corrections
- **Branch:** `docs/readme-restructure`; database `caldart_readme_restructure`
- **Owns:** `README.rst`.
- **Steps:** §5's README shape; fix `:25` (`make seed` also seeds CMS content), `:148` (time-anchored licensing wording), expand DART on first use.
- **Verify:** `make docs` and `make lint-spelling` clean; every command in the README runs as written.

#### extension-recipes (Opus)

- **Closes:** #60
- **After:** developer-guide-corrections, how-to-articles, diagrams-and-overview, readme-restructure
- **Branch:** `docs/extension-recipes`; database `caldart_extension_recipes`
- **Owns:** `docs/developer/extending.rst` (new), `docs/developer/index.rst#toctree`, `docs/developer/cms.rst#recipes`.
- **Steps:** §5's six skeletons, each checked by pasting it into a scratch module and running `ruff check` and `mypy` (or `tsc`) on it before deletion; `cms.rst`'s two prose recipes become links to the page. The PR body lists every item of #60 with the PR that settled it.
- **Verify:** `make docs` clean; each skeleton type-checks in isolation.

## 8. Manifest

```json
[
  {"wave": 1, "package": "make-help-and-pins", "model": "sonnet", "branch": "chore/make-help-and-pins", "database": "caldart_make_help_and_pins", "e2e_port": null, "closes": [], "refs": [61], "owns": ["Makefile#help-comments", "frontend/package.json#engines", ".nvmrc", "README.rst#requirements", "docs/developer/setup.rst#requirements", "pyproject.toml#dependencies"], "after": []},
  {"wave": 1, "package": "ruff-ruf-n", "model": "sonnet", "branch": "chore/ruff-ruf-n", "database": "caldart_ruff_ruf_n", "e2e_port": null, "closes": [], "refs": [61], "owns": ["pyproject.toml#ruff", "backend/**/*.py#rule-fixes", ".claude/rules/python.md#ruff-categories", "docs/developer/testing.rst#ruff"], "after": []},
  {"wave": 1, "package": "eslint-type-checked", "model": "opus", "branch": "chore/eslint-type-checked", "database": "caldart_eslint_type_checked", "e2e_port": 8121, "closes": [], "refs": [61], "owns": ["frontend/eslint.config.js", "frontend/tsconfig.json", "frontend/tsconfig.test.json", "frontend/vite.config.ts#test-typecheck", "frontend/package.json#devDependencies", "frontend/package-lock.json", "frontend/src/**#rule-fixes", "frontend/e2e/**#rule-fixes", ".claude/rules/javascript_typescript_best_practices.md#lint", "docs/developer/testing.rst#eslint"], "after": []},
  {"wave": 1, "package": "user-guide-corrections", "model": "sonnet", "branch": "docs/user-guide-corrections", "database": "caldart_user_guide_corrections", "e2e_port": null, "closes": [], "refs": [60], "owns": ["docs/user/system-administrator-guide.rst", "docs/user/account-administrator-guide.rst", "docs/user/getting-started.rst", "docs/user/website-administrator-guide.rst", "docs/user/member-guide.rst", "docs/user/index.rst", "docs/user/payments.rst#placement", "docs/developer/deployment.rst#troubleshooting-label"], "after": []},
  {"wave": 1, "package": "faq-and-walkthrough", "model": "sonnet", "branch": "docs/faq-and-walkthrough", "database": "caldart_faq_and_walkthrough", "e2e_port": null, "closes": [], "refs": [60], "owns": ["docs/user/faq.rst", "docs/demo-walkthrough.rst#facts"], "after": []},
  {"wave": 1, "package": "api-members-aircraft-profile", "model": "opus", "branch": "docs/api-members-aircraft-profile", "database": "caldart_api_members_aircraft_profile", "e2e_port": null, "closes": [], "refs": [60], "owns": ["docs/developer/api-members.rst", "docs/developer/api-aircraft.rst", "docs/developer/api-profile.rst"], "after": []},
  {"wave": 1, "package": "api-auth-payments-system", "model": "opus", "branch": "docs/api-auth-payments-system", "database": "caldart_api_auth_payments_system", "e2e_port": null, "closes": [], "refs": [60], "owns": ["docs/developer/api-auth.rst", "docs/developer/api-payments.rst", "docs/developer/api-reference.rst", "docs/developer/api-system.rst", "docs/developer/index.rst#toctree"], "after": []},
  {"wave": 2, "package": "check-deploy", "model": "sonnet", "branch": "chore/check-deploy", "database": "caldart_check_deploy", "e2e_port": null, "closes": [], "refs": [61], "owns": ["Makefile#check-deploy", ".github/workflows/ci.yml#backend-job", "backend/caldart/settings/prod.py#silenced-checks", "docs/developer/testing.rst#gates", "docs/developer/deployment.rst#check-deploy", ".claude/rules/environment.md#gates"], "after": ["make-help-and-pins"]},
  {"wave": 2, "package": "content-security-policy", "model": "opus", "branch": "feature/content-security-policy", "database": "caldart_content_security_policy", "e2e_port": 8122, "closes": [], "refs": [61], "owns": ["pyproject.toml#dependencies", "uv.lock", "backend/caldart/settings/base.py#csp", "backend/caldart/settings/dev.py#csp", "backend/caldart/settings/prod.py#csp", "backend/caldart/settings/test.py#csp", "backend/apps/cms/wagtail_hooks.py#csp", "backend/tests/test_csp.py", "docs/developer/deployment.rst#csp", "docs/developer/configuration.rst#csp", "docs/developer/payments-setup.rst#csp", "deploy/caldart.env.example#csp"], "after": ["make-help-and-pins"]},
  {"wave": 2, "package": "developer-guide-corrections", "model": "sonnet", "branch": "docs/developer-guide-corrections", "database": "caldart_developer_guide_corrections", "e2e_port": null, "closes": [], "refs": [60], "owns": ["docs/conf.py", "docs/index.rst", "docs/developer/index.rst#intro", "docs/developer/roadmap.rst", "docs/developer/deployment.rst#wording", "docs/developer/data-model.rst#timestamps", "docs/developer/reminders.rst#add-a-kind", "docs/developer/cms.rst#handbook-example", "docs/developer/reports.rst#is-active-warning", "docs/developer/testing.rst#e2e-env", "docs/developer/setup.rst#smoke-test", "docs/developer/*.rst#related", "docs/**/*.rst#absolute-doc-targets", "backend/tests/test_integration.py#history-comments", "frontend/src/portal/features/profile/AircraftEditor.tsx#header-comment"], "after": ["make-help-and-pins", "user-guide-corrections", "faq-and-walkthrough"]},
  {"wave": 2, "package": "how-to-articles", "model": "sonnet", "branch": "docs/how-to-articles", "database": "caldart_how_to_articles", "e2e_port": null, "closes": [], "refs": [60], "owns": ["docs/user/how-to/*", "docs/user/index.rst#toctree", "docs/demo-walkthrough.rst#structure"], "after": ["faq-and-walkthrough", "user-guide-corrections"]},
  {"wave": 3, "package": "api-contract-test", "model": "opus", "branch": "feature/api-contract-test", "database": "caldart_api_contract_test", "e2e_port": null, "closes": [61], "refs": [], "owns": ["pyproject.toml#dependencies", "uv.lock", "backend/caldart/settings/base.py#spectacular", "backend/caldart/api_urls.py#schema", "backend/tests/test_openapi_contract.py", "backend/tests/snapshots/*", "Makefile#check-backend", "Makefile#check-frontend", "frontend/package.json", "frontend/package-lock.json", "frontend/src/portal/api/schema.d.ts", "frontend/src/portal/api/types.contract.test.ts", ".gitignore", "docs/developer/testing.rst#contract", "docs/developer/api-reference.rst#schema", ".claude/rules/javascript_typescript_best_practices.md#api-types"], "after": ["check-deploy", "ruff-ruf-n", "eslint-type-checked", "content-security-policy"]},
  {"wave": 3, "package": "diagrams-and-overview", "model": "opus", "branch": "docs/diagrams-and-overview", "database": "caldart_diagrams_and_overview", "e2e_port": null, "closes": [], "refs": [60], "owns": ["docs/user/overview.rst", "docs/user/index.rst#toctree", "docs/developer/payments-setup.rst#sequence", "docs/developer/deployment.rst#topology", "docs/developer/data-model.rst#diagram"], "after": ["user-guide-corrections", "developer-guide-corrections"]},
  {"wave": 3, "package": "readme-restructure", "model": "sonnet", "branch": "docs/readme-restructure", "database": "caldart_readme_restructure", "e2e_port": null, "closes": [], "refs": [60], "owns": ["README.rst"], "after": ["make-help-and-pins", "developer-guide-corrections"]},
  {"wave": 3, "package": "extension-recipes", "model": "opus", "branch": "docs/extension-recipes", "database": "caldart_extension_recipes", "e2e_port": null, "closes": [60], "refs": [], "owns": ["docs/developer/extending.rst", "docs/developer/index.rst#toctree", "docs/developer/cms.rst#recipes"], "after": ["developer-guide-corrections", "how-to-articles", "diagrams-and-overview", "readme-restructure"]}
]
```
