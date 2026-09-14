# Plan: fix the Critical, High and Medium critique issues

**Date:** 2026-09-14

**Scope:** the 42 issues labelled `priority-critical`, `priority-high` or `priority-medium`. They were filed from the 2026-09-13 critiques in `critiques/`. The six `priority-low` checklist issues are out of scope.

**Status:** ready to run once #13 is merged, this plan is committed, and the decisions in §5 have been reviewed.

## 1. How to run this plan

One orchestrating Claude Code session runs the plan with no human input:

1. **Start.** Open a session in the repository on an up-to-date `main`, and say: "Execute `plans/2026-09-14-non-low-issues.md`." To fan the packages out with the Workflow tool, add "use a workflow". Otherwise the orchestrator uses one subagent per package.
2. **Dispatch.** The orchestrator reads the manifest in §8. It starts a package as soon as every package in its `after` list has merged; the waves in §7 are the default order. Each package gets its own worker, in its own git worktree, on a branch from a fresh `origin/main`.
3. **Implement.** Each worker implements its package (§7) under the conventions in §3, opens a PR, and reports back.
4. **Merge.** The orchestrator merges the PRs one at a time (§4). Two packages never own the same code without an `after` order between them, so any packages that are ready can run in parallel.
5. **Report.** When every package has merged or stopped, the orchestrator reports as §6 describes.

No step waits for an answer, because §5 settles every open choice in advance. If a worker meets a choice the plan did not foresee, it takes the option closest to the issue's suggested fix. It records the choice under Notes in the PR and carries on.

## 2. Preconditions

The orchestrator checks these first. If any check fails, it stops and reports.

- **#13 is merged into `main`.** The plan relies on what that PR added: `make check`, `make audit`, the nitpicky docs build, warnings as errors, and the rules and skills in `.claude/`.
- **This plan is committed to `main`.** `git ls-files plans/2026-09-14-non-low-issues.md` prints the path, so every worktree has it.
- **Tracked files are clean and `main` is current.** `git status --porcelain --untracked-files=no` prints nothing, and `git pull --ff-only` succeeds. Untracked directories such as `critiques/` don't matter.
- **The containers are running.** `make up` has started Postgres and Mailpit, and `docker ps` lists `caldart-db-1`.
- **The tools are installed.** `uv`, Node 22 with npm, GNU make, Chromium for Playwright (`cd frontend && npx playwright install chromium`), and `gh`. Run `gh` with no prefix: this repository's wrapper already uses the `astrocfi` account.
- **Every issue in §8 is still open.** If an issue is already closed, drop it from its package, and note that in the report.

## 3. Conventions for every work package

Every worker follows `CLAUDE.md` and the rules in `.claude/rules/`. On top of those:

- **Branch and worktree.** Create the worktree with `git fetch origin && git worktree add .claude/worktrees/<package> -b <branch> origin/main`, using the package's branch from the manifest (the `git-workflow` skill's naming).
- **Database.** Set `DATABASE_URL=postgres://caldart:caldart@localhost:5432/<database>`, with `<database>` from the manifest, and run `make createdb`.
- **End-to-end runs.** A package with an `e2e_port` in the manifest runs `make e2e E2E_PORT=<e2e_port> E2E_DB=<database>_e2e`. Parallel packages then never share a server or a database.
- **Test first.** For every behavior change, write the failing test first, and watch it fail for the right reason before fixing the code (`python_testing` §1). Backend tests go in `backend/tests/test_<feature>.py`; frontend tests sit beside the code.
- **Scope.** Edit only the files the package owns (§7 and the manifest), plus new test files and the docs pages it lists. Docs pages and `PLAN.rst` are shared: any package may edit the sections its change affects. If a fix genuinely needs another code file, keep that change additive and say so in the PR.
- **Docs in the same PR.** Update every page the change affects (`doc_python` §6). When behavior departs from `PLAN.rst`, update `PLAN.rst` in the same PR.
- **Frontend dependencies.** npm 10.9.2 crashes (`reading 'edgesOut'`) when it installs into this tree. To add or upgrade a package, run `npx -y npm@11 install …`, then check with a clean `npm ci`.
- **Commits.** Use Conventional Commits, with one logical change per commit (the `git-workflow` skill). Every commit message ends with these two lines:

  ```
  Co-Authored-By: Claude <name of the model doing the work> <noreply@anthropic.com>
  Claude-Session: <the session URL>
  ```

- **Gates.** Before opening the PR, `make lint test check docs audit` must pass. A package with an `e2e_port` also runs `make e2e` as above. Every command under the package's "Verify" must pass too.
- **Pull request.** Open it with `gh pr create --base main`. The body follows `.github/pull_request_template.md` (the `pull-request` skill). Write one `Closes #N.` sentence for each issue in the package's `closes`, and one `Refs #N.` sentence for each in its `refs`.

## 4. Merging

The orchestrator merges one PR at a time:

1. **Rebase.** Rebase the branch on `origin/main` and push with `--force-with-lease`. Resolve conflicts in files the package owns, and in shared docs, keeping both sides' intent. If any other file conflicts, follow §6.
2. **Re-run the gates** on the rebased branch.
3. **Wait for CI** with `gh pr checks <pr> --watch --fail-fast`. Every job must pass.
4. **Merge** with `gh pr merge <pr> --squash`.
5. **Confirm the merge.** `gh pr view <pr> --json state --jq .state` must print `MERGED`. Only then remove the worktree and delete the branch:
   - `git worktree remove .claude/worktrees/<package>`
   - `git push origin --delete <branch>`
   - `git branch -D <branch>`

   If the PR is not `MERGED`, keep its branch.
6. **Check the issues.** Every issue in `closes` must show as closed: `gh issue view <n> --json state`.

## 5. Decisions

These are the defaults the workers apply. Each comes from the issue's suggested fix, or from the reasoning recorded while the issue was drafted. Review them before starting the run; to change one, edit this list first.

- **#14, account-edit guard:**
  - An admin may change another account's `email` or `is_active` only when they hold every role that account holds. A `system_admin` or superuser actor always may. The rule is this general form, not a `system_admin`-only guard.
  - A superuser target counts as `system_admin`.
  - Names stay editable by anyone who could already edit them.
  - A refusal is a field-keyed 400, matching the existing role guard.
  - A change that only differs in letter case is not a change.
- **#15, throttle identity:**
  - A constant `NUM_PROXIES = 1` in `prod.py`, not an environment variable.
  - A `DatabaseCache` default cache in production; no new service or dependency.
  - Development and tests keep the local-memory cache.
- **#21, CSRF:** one project-wide authentication class that checks CSRF for anonymous callers too, instead of per-view `csrf_protect`. The auth views are not restricted to JSON.
- **#22, members-only documents:**
  - A "Members only" document collection, identified by name, guarded by a `before_serve_document` hook.
  - A refusal renders the members-only wall with status 403.
  - nginx answers 404 for `/media/documents/`, and Apache 403.
  - No `X-Accel-Redirect` offload.
- **#23, provider errors:**
  - Messages are generic "could not be reached; please try again".
  - Transient failures are logged at WARNING. A capture in transit, or a mismatched capture, is logged at ERROR and stays pending for a human to reconcile.
- **#24, Stripe client:**
  - `StripeClient` with a 20-second timeout and one network retry.
  - Idempotency key `caldart-payment-<pk>-start`.
  - PayPal request ids are out of scope.
- **#25, reminders:**
  - A three-day catch-up window; `expired` is never sent late.
  - Subjects state the real day count.
  - The API payload stays `{sent, skipped}`.
  - The command exits non-zero when a send fails.
  - Logs carry ids and the exception class only.
- **#26, member delete:**
  - `Payment.user` becomes `PROTECT`, and deletion is refused with 403 when a member has any payment, whatever its status. Deactivation is the alternative.
  - Payments are not re-parented with a copied name.
- **#27, production settings:**
  - `test.py` still reads `.env`, for the per-worktree `DATABASE_URL`.
  - Production reads `PAYMENTS_MOCK_ENABLED_IN_PRODUCTION`, never the development flag.
  - `prod.py` refuses the published development `SECRET_KEY`.
  - The template lives at `deploy/caldart.env.example`.
  - `manage.py` keeps its development default.
- **#28, security headers:**
  - Django owns HSTS, `nosniff` and `Referrer-Policy`, and the proxies drop their server-level copies. `nosniff` stays on `/media/`.
  - `SECURE_HSTS_SECONDS` keeps its one-year default, and `SECURE_HSTS_PRELOAD` defaults to false.
- **#30, throttle rates:**
  - An empty value turns the throttle off, and a malformed one stops start-up.
  - Normalise in settings, and also treat a falsy rate as off in `get_rate`.
- **#19, Stripe objects and signatures:**
  - Delete the `construct_event` stub, and sign every webhook test's payload for real.
  - Convert SDK objects with `.to_dict()` at the boundary in `start`, `confirm` and `handle_webhook`, as part of the same fix.
  - Amend PLAN §15 to describe the SDK-boundary fakes. Don't route Stripe through `httpx` just so `respx` can mock it.
  - The signing helper lives in `test_payments_stripe.py`.
  - Filed as `priority-high` rather than medium: the defect it uncovered breaks every real Stripe confirmation and webhook.
- **#48, profile completeness:** the canonical five-field rule goes in PLAN §6.1. The member guide keeps its nudge entry, reworded.
- **#49, stale duplicate:** delete it in its own first commit, before any other `data-model.rst` edit.
- **#50, diagrams:**
  - Two diagrams, domain and CMS.
  - Dashed "(abstract)" boxes, with empty-arrowhead inheritance edges.
  - One `TimestampedModel` node, with its subclasses named in the caption.
  - Each ASCII fallback is a drawing plus an edge list.
- **#51, Redirects:**
  - Document Wagtail's automatic redirects, once a dev-server check confirms them.
  - Add a short Redirects section to the website administrator guide.
- **#52, aircraft editing:** document what an account administrator sees on their own My aircraft. No frontend change.
- **#53, confirm endpoints:** the owner-only rule is deliberate, so only the docs change.
- **#54, production commands:**
  - A documented `caldart_manage` shell function built on `systemd-run -p EnvironmentFile=`.
  - The backup service and timer units shown inline in `backup-restore.rst`, not shipped in `deploy/`.
  - No cron alternative.
- **#55, make switches:**
  - `1`, `yes` and `true` mean on; `0`, `no`, `false`, empty or unset mean off; anything else is an error.
  - Lower case only.
  - A pytest regression test guards the behavior.

- **#29, membership annotations:**
  - The SQL rule lives in `members/services.py`.
  - `full_name` and `effective_expiry` stay in `admin_filters.py`.
  - The reminder scan's per-candidate status check is out of scope, because it is a daily batch job.
- **#16, services:**
  - The domain exceptions live in `caldart/exceptions.py`.
  - Status codes and response bodies don't change.
  - The payment-report query is validated by a DRF serializer, which also fixes the impossible-date 500.
  - `AccountChanges` is a `TypedDict` with `total=False`.
  - `register_member` replaces `register_user`, and `register_user` is deleted.
  - Term correction stays a plain `ModelSerializer` update.
- **#31, audit logging:**
  - Logging now; an `AuditEntry` model stays on the roadmap.
  - A dedicated `caldart.audit` logger that doesn't propagate.
  - Refusals are logged at WARNING.
  - Email and name changes log field names only.
  - The actor for commands and the timer is `command`.
- **#32, layering:**
  - Domain modules follow a one-way layer order; `api/`, `admin.py` and commands are the composition points.
  - The `User` membership properties and the site-settings lookups keep their sanctioned inline imports.
  - An `ast`-based pytest enforces the rule, instead of `import-linter`.
  - `aircraft` and `payments` are sibling layers.
- **#33, shared types:**
  - `MembershipState` lives in `members/models.py`.
  - The shared serializers go in a new `members/api/serializers.py`.
  - The invitation subject is `"<org_name>: set your password"`.
  - `send_password_invitation` lives in `accounts/services.py`.
- **#17, annotations:**
  - Enforced by ruff `ANN`, with a `per-file-ignores` ratchet; no type checker yet.
  - `allow-star-arg-any` is on, and `ANN401` stays enabled.
  - Units run in this order: core, reminders, sysadmin, aircraft, payments, accounts, cms, members, then the test groups.
  - Each unit's annotations and docstrings ship in the same PR.
- **#18, docstrings:**
  - Docstrings describe behavior in prose. No `Parameters:`, `Returns:` or `Raises:` sections are required: they exist for ReadTheDocs rendering, which this project doesn't use. The prose names the parameters, return value and exceptions a caller needs.
  - ruff's `D` rules enforce that docstrings exist and are well formed. `D417` checks nothing without sections.
  - Ignore `D104` and `D106`, and amend `python.md` §5 to match.
  - Defer the pydoclint `DOC` rules, which are still preview.
  - Test docstrings are one sentence.
- **#34, permission gaps:**
  - The cases go in one new module.
  - Pin today's behavior for a role-less account: its own records and checkout are allowed, role-gated endpoints give 403.
  - The fixture is renamed `no_role_user`.
  - The Wagtail admin redirects `user_admin` and `account_admin` to its login page.
- **#35, server-controlled fields:**
  - The cases go in one new module.
  - Extra fields are silently ignored, not rejected with 400.
  - Seven cases.

- **#20, React refresh:** nothing to decide. The tag renders nothing in production.
- **#36, CSRF bootstrap:**
  - Retry once after a `CSRF Failed` 403.
  - A failed bootstrap rejects with its underlying error.
  - The profile save test asserts the header.
- **#37, sign-in check:**
  - `/auth/me` uses the app's retry policy.
  - The public screens keep treating an error as anonymous.
  - The error copy is "We could not check your sign-in", with "Try again".
- **#38, StrictMode:**
  - Use an `AbortController` in `CheckoutReturn`, rather than a TanStack Query rewrite.
  - Turn StrictMode on for every test through `configure()`.
  - Fold in the core of the #58 checklist item "Stop the Stripe panel creating duplicate PaymentIntents" (an abortable Stripe checkout), since the StrictMode tests need it.
- **#39, unexpected responses:**
  - A separate `UnexpectedResponseError`, not an `ApiError` subclass.
  - An empty 2xx returns `null`.
- **#40, lazy routes:**
  - The auth, dashboard and not-found routes stay eager.
  - Use the function form of `lazy`.
  - No navigation progress bar.
  - The shared `Loading` lives in `components/`.
- **#41, profile fieldset:**
  - The member form's labels and constraints are canonical.
  - The admin-only fields are a separate `AdminOnlyFields` component.
  - The shared fieldset lives in `features/profile/`.
  - Use the `.form-grid` layout.
- **#42, debounce hook:** it lives in `components/useDebounced.ts`, outside the barrel.
- **#43, API types:**
  - The admin-members request payloads move too.
  - `InsuranceState` stays in the aircraft feature.
  - `admin-members/types.ts` keeps only the filter state.
- **#44, return types:**
  - Components return `JSX.Element`, not `ReactNode`.
  - Mutation errors are typed `Error`.
  - The rule applies to `src/test/` and `e2e/` too.
  - Roll out with a growing `files` list, one PR per group.
- **#45, JSDoc:**
  - Enforce it with `eslint-plugin-jsdoc`, using `require-jsdoc` (`publicOnly`) and `no-types`.
  - Exported types don't need JSDoc.
  - `@param` and `@returns` are optional.
  - Document the fixture modules where they sit.
  - Roll out together with the return-type rule.
- **#46, route table:**
  - Stub the pages with `vi.mock`.
  - Include a signed-in user with no roles.
  - The memory router has no `/portal` basename.
- **#47, fake timers:**
  - Fix the clock at `2026-06-15T12:00:00Z`.
  - Restore real timers globally in `setup.ts`.

## 6. Failure handling and the final report

- **A failing gate.** The worker gets up to three fix attempts within the package's scope. If the gate still fails, it leaves the PR open as a draft, comments on each issue with the failure and what it tried, and stops. The orchestrator carries on with every package that does not depend on the stopped one.
- **A rebase conflict outside the package's files and the shared docs.** Stop that package the same way.
- **Never** push to `main`, merge a PR with a failing check, skip hooks, or force-push anything except a package branch.
- **CI fails on `main` after a merge.** Start no new package until a fix PR restores `main`. The fix follows the same conventions and is its own package.
- **The final report.** The orchestrator ends by listing:
  - every PR merged, with the issues it closed;
  - every issue still open, and why;
  - every decision it took that §5 did not cover.

## 7. Work packages

Packages are described by area below. The manifest (§8) gives their order, and this table summarises it. Tracking packages that only reference their issues are listed with those issues.

| Wave | Packages (issues) |
|---|---|
| 1 | `account-edit-guard` (#14); `production-settings` (#27, #28, #15); `payment-provider-errors` (#19, #23, #24); `reminder-scan-resilience` (#25); `docs-accuracy` (#49, #48, #50, #53, #51, #52); `make-switches` (#55); `server-controlled-field-tests` (#35); `vite-react-refresh` (#20); `api-client-errors` (#36, #39); `auth-check-errors` (#37); `shared-debounce` (#42); `profile-fieldsets` (#41) |
| 2 | `member-delete-keeps-payments` (#26); `auth-csrf-and-throttle-rates` (#30, #21); `members-only-documents` (#22); `production-commands-docs` (#54); `membership-annotations` (#29); `checkout-strict-mode` (#38); `route-table` (#46, #40) |
| 3 | `shared-membership-types` (#33); `permission-matrix-tests` (#34); `api-types` (#43); `fake-timers` (#47) |
| 4 | `account-and-member-services` (#16); `frontend-types-docs-shared` (#44, #45) |
| 5 | `app-layering` (#32); `frontend-types-docs-admin` (#44, #45) |
| 6 | `audit-logging` (#31); `frontend-types-docs-flows` (#44, #45) |
| 7 | `backend-types-ratchet` (#17, #18); `frontend-types-docs-finish` (#44, #45) |
| 8 | `backend-types-core` (#17, #18); `backend-types-reminders` (#17, #18); `backend-types-sysadmin` (#17, #18); `backend-types-aircraft` (#17, #18); `backend-types-payments` (#17, #18); `backend-types-accounts` (#17, #18); `backend-types-cms` (#17, #18); `backend-types-members` (#17, #18); `backend-types-tests-accounts` (#17, #18); `backend-types-tests-members` (#17, #18); `backend-types-tests-aircraft` (#17, #18); `backend-types-tests-payments` (#17, #18); `backend-types-tests-reminders` (#17, #18); `backend-types-tests-cms` (#17, #18); `backend-types-tests-sysadmin` (#17, #18); `backend-types-tests-shared` (#17, #18) |
| 9 | `backend-types-finish` (#17, #18) |

### account-edit-guard: close the admin account-takeover path

- **Issues:** #14
- **Branch:** `bugfix/account-edit-guard`; database `caldart_account_edit_guard`
- **Owns:** `backend/apps/accounts/services.py`, `backend/apps/accounts/api/serializers.py`, `backend/apps/members/api/admin_serializers.py`, `backend/apps/members/api/admin_views.py`, `backend/tests/test_account_edit_guard.py` (new)
- **Docs:** `docs/developer/api-auth.rst`, `docs/developer/api-members.rst`, `docs/user/user-administrator.rst`, `docs/user/account-administrator-guide.rst`, `PLAN.rst` §4.1, §6.2 and §6.4
- **Steps:**
  1. **Service.** In `accounts/services.py`, add:
     - a module logger;
     - `effective_roles(user)`: the user's roles, plus `system_admin` when `is_superuser`;
     - `PROTECTED_ACCOUNT_FIELDS = {"email", "is_active"}`;
     - an `AccountEditRefused(field, message)` exception;
     - three message constants: self-deactivation, email refused, status refused;
     - `check_account_edit(actor, target, changes)`.
  2. **The rule.** Only a real change to a protected field counts. Compare email case-insensitively after stripping, and `is_active` as a bool.
     - Refuse self-deactivation.
     - Otherwise refuse unless the actor is `system_admin` or holds every role the target holds.
     - Log each refusal at WARNING with ids only.
  3. **Serializers.** Call the rule from `AdminUserSerializer.validate()` and `MemberUpdateSerializer.validate()`, turning the exception into a field-keyed 400. Delete the old self-check in `validate_is_active`. Pass the serializer context in `MemberAdminDetailView.update()`.
  4. **Delete guard.** In `perform_destroy`, use `effective_roles` for both caller and target, so a superuser without the role counts as `system_admin`.
- **Tests:** `test_account_edit_guard.py` replays the takeover on both endpoints and checks:
  - email and deactivation refused for a system admin target, and for a role-less superuser;
  - the general rule, i.e. an account admin cannot change a user admin;
  - allowed edits still succeed, including resending unchanged values;
  - self-deactivation refused on the members endpoint;
  - delete refused for a role-less superuser;
  - after a refusal, the reset sends no mail;
  - the log record carries ids and no `@`.
- **Verify:** `uv run pytest backend/tests/test_account_edit_guard.py backend/tests/test_users_admin_api.py backend/tests/test_members_admin.py -q`

### production-settings: fail closed in production, one HSTS owner, real client IPs

- **Issues, in commit order:** #27, #28, #15
- **Branch:** `bugfix/production-settings`; database `caldart_production_settings`; e2e on port 8101
- **Owns:**
  - `backend/caldart/settings/_dotenv.py` (new), `base.py` (only the `.env` read at the top), `dev.py`, `test.py`, `prod.py`
  - `backend/caldart/wsgi.py`, `backend/caldart/asgi.py`
  - `deploy/caldart.env.example` (new), `deploy/systemd/caldart-web.service`, `deploy/apache/caldart.conf`, `deploy/nginx/caldart.conf`
  - `backend/tests/test_sysadmin_settings.py`, and the new `backend/tests/test_settings_fail_closed.py`, `test_hsts.py` and `test_auth_throttle_ident.py`
- **Docs:** `docs/developer/configuration.rst`, `docs/developer/deployment.rst`, `PLAN.rst` §14
- **Steps:**
  1. **#27: stop production reading `.env`.**
     - Move the `.env` read out of `base.py` into `settings/_dotenv.py`, which `dev.py` and `test.py` import before `base`.
     - In `prod.py`, read `PAYMENTS_MOCK_ENABLED_IN_PRODUCTION` (default false) and ignore the development flag.
     - Refuse the published development `SECRET_KEY`.
     - Make `wsgi.py` and `asgi.py` raise `ImproperlyConfigured` when `DJANGO_SETTINGS_MODULE` is unset.
     - Add `deploy/caldart.env.example`: required values commented out, so an unedited copy fails at start-up, and no mock-payments line. Point `caldart-web.service` at it.
     - Extend `UNSET` in `test_sysadmin_settings.py` to every variable `prod.py` reads, and add a test that keeps it complete.
  2. **#28: give HSTS one owner.** Delete the HSTS, `nosniff` and `Referrer-Policy` headers the Apache and nginx configs set at server level; Django owns them. Keep `nosniff` on `/media/`. Make `SECURE_HSTS_PRELOAD` default to false.
  3. **#15: key throttles on the real client IP.** In `prod.py`, set `REST_FRAMEWORK["NUM_PROXIES"] = 1` on a deep copy, and add a `DatabaseCache` default cache. Add `manage.py createcachetable` to the deployment guide's first-deploy and upgrade steps.
- **Tests:**
  - `test_settings_fail_closed.py`:
    - `prod` never reads `.env`; `dev` does;
    - a missing or development `SECRET_KEY` fails;
    - the mock flag is ignored, and the override works;
    - `wsgi` and `asgi` require the settings module;
    - the template is safe, and an unedited copy fails.
  - `test_hsts.py`:
    - neither proxy sets HSTS;
    - `/media/` keeps `nosniff`;
    - Django sends exactly one HSTS header, and none at zero seconds.
  - `test_auth_throttle_ident.py`:
    - spoofed `X-Forwarded-For` prefixes share one budget;
    - each real client gets its own budget.
  - `test_sysadmin_settings.py`: `NUM_PROXIES == 1`, the database cache, and `SECURE_HSTS_PRELOAD` false by default.
- **Verify:**
  - `uv run pytest backend/tests/test_settings_fail_closed.py backend/tests/test_hsts.py backend/tests/test_auth_throttle_ident.py backend/tests/test_sysadmin_settings.py -q`
  - `make run` still boots from `.env`.

### payment-provider-errors: handle Stripe objects, turn outages into 400s, bound Stripe's time

- **Issues, in commit order:** #19, #23, #24
- **Branch:** `bugfix/payment-provider-errors`; database `caldart_payment_provider_errors`; e2e on port 8102
- **Owns:** `backend/apps/payments/providers/base.py`, `stripe.py`, `paypal.py`, `backend/tests/test_payments_stripe.py`, and the new `backend/tests/test_payments_provider_errors.py` and `test_payments_stripe_client.py`
- **Docs:** `PLAN.rst` §15, `docs/developer/testing.rst` (the Stripe test seam)
- **Steps:**
  0. **#19: treat Stripe SDK results as objects, and test real signatures.** This goes first, because #23 and #24 rewrite the same functions.
     - The locked stripe 15.6.1 returns `stripe.Event` and `stripe.PaymentIntent` objects, which have no `.get`. Every real webhook and confirmation therefore fails today with `AttributeError`, as a 500.
     - In `stripe.py`, convert with `.to_dict()` at the SDK boundary in `handle_webhook`, `confirm` and `start`, and reduce `jsonable` to a JSON round trip.
     - In `test_payments_stripe.py`:
       - add `sign_stripe_payload()` and `stripe_event()`, which sign each webhook payload with the test secret the way Stripe does, so the real `construct_event` verifies it;
       - delete `stub_construct_event`;
       - make `FakeIntents` return `stripe.PaymentIntent.construct_from(...)` objects.
     - Add signature tests:
       - a valid signature is accepted;
       - a wrong secret, a timestamp over 300 seconds old, a missing header and a tampered body each get a 400 `{"detail": "Invalid Stripe signature."}` and leave the payment unchanged.
     - Assert that `Payment.raw` is a dict after start, after confirm and after a webhook.
     - Amend PLAN §15 and `testing.rst`: Stripe is faked at the SDK boundary with real objects and real signatures, and PayPal HTTP is mocked with `respx`.
  1. **#23: wrap provider errors.**
     - Add `ProviderUnavailable(PaymentError)` to `providers/base.py`.
     - Wrap only the Stripe SDK calls (`PaymentIntent.create` and `retrieve`, catching `stripe.StripeError`), and the PayPal HTTP calls (catching `httpx.HTTPError`, and `ValueError` on a JSON decode).
     - Messages are generic: "could not be reached; nothing was charged; try again".
     - In PayPal `verify_signature`, catch `PaymentError`.
     - Log a capture failure in transit, and every post-capture mismatch, at ERROR, with the payment id and amounts and no email address.
     - `CheckoutView` already deletes the pending row on `PaymentError`.
  2. **#24: bound Stripe's time.**
     - Add a `stripe_client()` factory: `StripeClient` with a 20-second timeout and one network retry. Use the `.v1.payment_intents` namespace, because the un-namespaced form raises a `DeprecationWarning`, which pytest turns into an error.
     - Pass `idempotency_key=f"caldart-payment-{pk}-start"` on create.
     - Move the `fake_intents` fixture in `test_payments_stripe.py` to patch `stripe_client`.
- **Tests:**
  - `test_payments_provider_errors.py`:
    - Stripe `APIConnectionError`, `RateLimitError`, `APIError` and `AuthenticationError` at checkout each give a 400 with the message and no `Payment` row;
    - a Stripe outage at confirm keeps the payment pending;
    - PayPal token and order failures, and a non-JSON token response;
    - a capture timeout logs an ERROR;
    - a wrong-amount capture is logged;
    - a verification failure leaves the webhook unverified;
    - no log line contains `@`.
  - `test_payments_stripe_client.py`:
    - the timeout and retry values;
    - the timeout budget fits under the gunicorn, nginx and Apache timeouts, read from `deploy/`;
    - checkout sends the idempotency key.
- **Verify:** `uv run pytest backend/tests/test_payments_provider_errors.py backend/tests/test_payments_stripe_client.py backend/tests/test_payments_stripe.py backend/tests/test_payments_paypal.py backend/tests/test_payments_api.py -q`

### reminder-scan-resilience: one failed email never stops the reminder run

- **Issues:** #25
- **Branch:** `bugfix/reminder-scan-resilience`; database `caldart_reminder_scan_resilience`
- **Owns:** `backend/apps/reminders/services.py`, `backend/apps/reminders/management/commands/send_renewal_reminders.py`, `backend/templates/emails/reminder_*.{txt,html}`, `backend/tests/test_reminders.py`, `backend/tests/test_reminders_resilience.py` (new)
- **Docs:** `docs/developer/reminders.rst`, `PLAN.rst` §4.5
- **Steps:**
  1. **Window.** Set `WINDOW_DAYS = 3`. t60, t30, t7 and post30 match `ends_on` within the last three days of their date; `expired` stays exact-day.
  2. **Real day count.** Subjects and bodies use the actual number of days (`abs(ends_on - today)`), not the kind's nominal offset.
  3. **Resilience.**
     - Around `_send_one`, catch `IntegrityError` as `already_sent`, and `smtplib.SMTPException`/`OSError` as a failure.
     - Log each failure at ERROR with ids and the exception class only, count it in `ReminderRun`, and carry on.
     - `as_dict()` stays `{sent, skipped}`.
  4. **Exit status.** The command raises `CommandError` when anything failed and it wasn't a dry run, so systemd marks the unit failed.
- **Tests:** `test_reminders_resilience.py`:
  - one failing recipient doesn't stop the scan;
  - a failed send is retried the next day;
  - a missed day is caught up within the window (1 and 2 days late send, 3 days late doesn't);
  - `expired` is never sent late;
  - a racing run counts as `already_sent`;
  - a late subject states the real day count;
  - the failure log line carries no address;
  - the command exits non-zero;
  - the run endpoint still returns `{sent, skipped}`.

  Split `test_nothing_fires_a_day_either_side` in `test_reminders.py`.
- **Verify:** `uv run pytest backend/tests/test_reminders.py backend/tests/test_reminders_resilience.py backend/tests/test_reminders_api.py -q`

### docs-accuracy: make the data model, permissions and user-guide claims true

- **Issues, in commit order:** #49, #48, #50, #53, #51, #52
- **Branch:** `bugfix/docs-accuracy`; database `caldart_docs_accuracy`
- **Owns:** `docs/developer/data-model.rst`, `api-profile.rst`, `api-reference.rst` (the permission bullets and matrix note), `api-payments.rst`, `cms.rst`; `docs/user/member-guide.rst`, `aircraft.rst`, `website-administrator-guide.rst`, `system-administrator-guide.rst`; `docs/demo-walkthrough.rst`
- **Docs:** `PLAN.rst` §4.6, §5 and §6.1
- **Steps:**
  1. **#49: delete the stale duplicate.** Delete `data-model.rst` from the second "Roles" heading up to the "``MembershipPlan``" heading, and remove `api-profile.rst`'s pointer to the deleted warning. First check with `diff` that the copies differ only in `is_complete`.
  2. **#48: one profile-completeness rule.**
     - Add the five-field rule to PLAN §6.1: `phone`, `address_line1`, `city`, `postal_code`, `pilot_certificate_type`, which is `MemberProfile.COMPLETE_FIELDS`.
     - Rewrite the member-guide nudge entry, the two demo-walkthrough passages (quoting "A phone number is required."), and the `api-profile.rst` paragraph. Drop `PROFILE_COMPLETE_FIELDS`.
  3. **#50: fix the diagrams.** Split the diagram in two: the domain schema, and the CMS page models.
     - Correct `DartPage.dart` to `SET_NULL` and add the roles edge.
     - Draw `TimestampedModel`, `Provider` and the CMS bases as dashed "(abstract)" boxes.
     - Rewrite the captions, and give each `.. only:: not graphviz` block a drawing plus an edge list at parity with its diagram.
  4. **#53: `system_admin` passes role checks, not ownership checks.** The three payment-confirm endpoints are owner-only. Correct:
     - the `api-reference.rst` bullets, matrix note and row notes;
     - `data-model.rst`;
     - `api-payments.rst`;
     - `system-administrator-guide.rst:19`;
     - PLAN §5.
  5. **#51: Redirects.** `website_admin` has add, change and delete on redirects, and Wagtail creates redirects automatically on slug changes and page moves. First confirm on a dev server: as `webadmin@example.org`, rename a page's slug, then check that the old URL redirects. Then fix the guide (adding a short Redirects section), `cms.rst` and PLAN §4.6.
  6. **#52: aircraft editing.** Members edit aircraft they added from **My aircraft**, and see the "Someone else added this aircraft" card on others. Correct `aircraft.rst` and `member-guide.rst`, and add the one-sentence note about the account administrator's view.
- **Verify:**
  - `grep -c '^Roles$' docs/developer/data-model.rst` prints `1`.
  - `grep -rn "PROFILE_COMPLETE_FIELDS\|read by nothing\|not currently granted" docs PLAN.rst` finds nothing.
  - The no-Graphviz build passes: `env PATH=/nonexistent .venv/bin/sphinx-build -n -W -E -a -b html docs "$(mktemp -d)"`.

### make-switches: `YES=0` and `DRY_RUN=0` mean off

- **Issues:** #55
- **Branch:** `bugfix/make-switches`; database `caldart_make_switches`
- **Owns:** `Makefile` (the `flag` helper plus the `restore` and `reminders` recipes), `backend/tests/test_makefile_switches.py` (new)
- **Docs:** `docs/developer/setup.rst` (a `make-switches` label after the target table), `docs/developer/backup-restore.rst`, `docs/developer/reminders.rst`, `PLAN.rst` §14
- **Steps:**
  1. Add the commented `flag` helper from the issue: `1`, `yes` and `true` mean on; `0`, `no`, `false`, empty or unset mean off; anything else stops `make`.
  2. Use `$(call flag,YES,--yes)` in `restore` and `$(call flag,DRY_RUN,--dry-run)` in `reminders`.
- **Tests:** `test_makefile_switches.py` runs `make -n` and checks:
  - the on values add the option;
  - the off values, including unset, don't;
  - `maybe` stops `make`, and stderr names the variable.
- **Verify:** `make -n restore FILE=x YES=0 | grep -c -- --yes` prints `0`.

### member-delete-keeps-payments: refuse to delete a member who has payments

- **Issues:** #26
- **Branch:** `bugfix/member-delete-keeps-payments`; database `caldart_member_delete_keeps_payments`; after `account-edit-guard`
- **Owns:** `backend/apps/payments/models.py`, `backend/apps/payments/migrations/0001_initial.py`, `backend/apps/members/api/admin_views.py` (`perform_destroy`), `backend/tests/test_members_admin.py` (the delete test), `backend/tests/test_members_delete_payments.py` (new), `frontend/src/portal/features/admin-members/MemberDangerZone.tsx`, and its new `.test.tsx`
- **Docs:** `docs/developer/api-members.rst`, `docs/user/account-administrator-guide.rst`, `docs/developer/data-model.rst`, `PLAN.rst` §4.4 and §6.4
- **Steps:**
  1. **Model.** Set `Payment.user` to `on_delete=PROTECT` in the model and in `0001_initial.py`. Don't stack a new migration; `make check` must report no changes.
  2. **Delete guard.** `perform_destroy` refuses with 403 ("… has N payment record(s) … Deactivate the account instead.") when the member has any payment. Also catch `ProtectedError` as the same 403.
  3. **Frontend.** The Danger zone shows that explanation instead of the form when the member has payments.
- **Tests:**
  - `test_members_delete_payments.py`:
    - refusal for each payment status;
    - the payment summary is unchanged after a refusal;
    - a system admin is refused too;
    - a member without payments is deleted along with the profile and terms;
    - the model raises `ProtectedError`.
  - `test_members_admin.py`: replace the cascade test.
  - `MemberDangerZone.test.tsx`: with and without payments.
- **Verify:**
  - `uv run pytest backend/tests/test_members_delete_payments.py backend/tests/test_members_admin.py backend/tests/test_payments_reports.py -q`
  - `cd frontend && npx vitest run src/portal/features/admin-members/MemberDangerZone.test.tsx`

### auth-csrf-and-throttle-rates: CSRF for anonymous callers; empty rate means off

- **Issues, in commit order:** #30, #21
- **Branch:** `bugfix/auth-csrf-and-throttle-rates`; database `caldart_auth_csrf_and_throttle_rates`; e2e on port 8106; after `production-settings`, `payment-provider-errors` and `api-client-errors`
- **Owns:**
  - `backend/caldart/settings/base.py` (the `REST_FRAMEWORK` authentication classes and the `AUTH_THROTTLE_RATES` block), `backend/caldart/authentication.py` (new), `backend/apps/accounts/throttling.py`, `.env.example` (the throttle comment)
  - `backend/tests/conftest.py` (the `csrf_client` fixture and `csrf_headers` helper), `backend/tests/test_payments_stripe.py` (the webhook CSRF test)
  - the new `backend/tests/test_auth_throttle_rates.py` and `test_csrf.py`
- **Docs:** `docs/developer/configuration.rst`, `api-reference.rst` (the CSRF bootstrap and throttling passages), `api-auth.rst`, `testing.rst` (the fixture table)
- **Steps:**
  1. **#30: empty means off.** In `base.py`, add `_throttle_rate(variable, default)`: empty means `None`, i.e. off, and a malformed value raises `ImproperlyConfigured`. Build `AUTH_THROTTLE_RATES` with it. `AuthScopedThrottle.get_rate` returns `settings.AUTH_THROTTLE_RATES.get(self.scope) or None`. Fix its docstring.
  2. **#21: CSRF for anonymous callers.**
     - Add `caldart.authentication.CsrfEnforcingSessionAuthentication`, which calls `enforce_csrf` when `authenticate()` finds no session, and make it `DEFAULT_AUTHENTICATION_CLASSES`.
     - The webhooks keep `authentication_classes = []`.
     - Add the `csrf_client` fixture (`APIClient(enforce_csrf_checks=True)`) and the `csrf_headers` helper, and switch the Stripe webhook's CSRF test to the enforcing client.
- **Tests:**
  - `test_auth_throttle_rates.py`:
    - empty and blank values turn the throttle off;
    - unset uses the default;
    - valid rates are kept;
    - malformed values stop start-up;
    - an empty override never produces a 500 or 429.
  - `test_csrf.py`:
    - each anonymous auth POST without a token gets a 403 "CSRF Failed";
    - a cross-site multipart login or registration is refused and sets no session;
    - with the bootstrapped token each POST succeeds with its exact status;
    - a refused reset sends no email;
    - a signed-in checkout without a token gets a 403;
    - the webhooks need no token;
    - safe methods need no token.
- **Verify:**
  - `uv run pytest backend/tests/test_csrf.py backend/tests/test_auth_throttle_rates.py backend/tests/test_accounts_auth.py backend/tests/test_payments_stripe.py -q`
  - `make e2e` with the package's port. The SPA signs in through the header path.

### members-only-documents: guard documents in the Members-only collection

- **Issues:** #22
- **Branch:** `bugfix/members-only-documents`; database `caldart_members_only_documents`; after `production-settings`
- **Owns:**
  - `backend/apps/cms/wagtail_hooks.py` (new), `backend/apps/cms/models.py` (the constant, the collection helper, and the wall context as a function)
  - `backend/apps/cms/management/commands/seed_content.py`, `backend/caldart/settings/base.py` (`WAGTAILDOCS_SERVE_METHOD`)
  - `deploy/nginx/caldart.conf` and `deploy/apache/caldart.conf` (the `/media/documents/` refusal)
  - `backend/tests/test_cms_documents.py` (new)
- **Docs:** `docs/user/website-administrator-guide.rst`, `docs/developer/cms.rst`, `docs/developer/deployment.rst`, `PLAN.rst` §4.6
- **Steps:**
  1. **Hook.** Add a `before_serve_document` hook. A document in the "Members only" collection, or any collection beneath it, gets a 403 with the members-only wall for anyone without members-only access. Everything else stays public.
  2. **Serving path.** Set `WAGTAILDOCS_SERVE_METHOD = "serve_view"` so every document link goes through Django.
  3. **Proxies.** nginx returns 404 for `/media/documents/`; Apache sets `Require all denied` on the `media/documents` directory.
  4. **Seed.** `seed_content` creates the collection idempotently, and its copy tells editors to upload members-only files there.
- **Tests:** `test_cms_documents.py`:
  - an anonymous visitor, and a member without a current membership, are refused;
  - a current member, and a DART leader without a membership, are served;
  - a child collection is protected;
  - a root-collection document stays public;
  - documents are served through Django;
  - the seed creates the collection once;
  - both proxy configs refuse `/media/documents/` (whitespace-tolerant regexes).
- **Verify:** `uv run pytest backend/tests/test_cms_documents.py backend/tests/test_cms_pages.py backend/tests/test_cms_seed_content.py -q`

### production-commands-docs: management commands that work in production

- **Issues:** #54
- **Branch:** `bugfix/production-commands-docs`; database `caldart_production_commands_docs`; after `production-settings` and `make-switches`
- **Owns:** `docs/developer/deployment.rst` (the command invocations) and `docs/developer/backup-restore.rst` (the production and scheduling blocks)
- **Steps:**
  1. **`caldart_manage`.** Add a "Running management commands" subsection (label `deploy-manage-commands`) that defines `caldart_manage` as `systemd-run` with `-p EnvironmentFile=`. It mirrors `User`, `WorkingDirectory` and `Environment` from `caldart-web.service`, with `--wait --pipe`.
  2. **Replace invocations.** Swap every production `env $(… | xargs)` and `sudo -u caldart … manage.py` for `caldart_manage …`.
  3. **Backups.** Replace the backup cron example with inline `caldart-backup.service` and `caldart-backup.timer` units. Verify both with `systemd-analyze verify`.
- **Verify:**
  - `grep -rn "xargs" docs` finds no `manage.py` invocation.
  - `systemd-analyze verify` passes on both units, written to a temporary directory.

### server-controlled-field-tests: request bodies cannot set server-controlled fields

- **Issues:** #35
- **Branch:** `feature/server-controlled-field-tests`; database `caldart_server_controlled_field_tests`
- **Owns:** `backend/tests/test_server_controlled_fields.py` (new)
- **Steps:**
  1. Add a module-level autouse fixture that sets `settings.PAYMENTS_MOCK_ENABLED = True`.
  2. Write seven tests. Each sends fields the server controls, then checks that the server's own values were stored.

     | Endpoint | Forbidden fields sent | What must hold |
     |---|---|---|
     | Registration | `roles`, `is_staff`, `is_superuser`, `is_active=false` | roles `["member"]`, both flags false, account active |
     | Members-admin create | `roles`, `is_staff`, `is_superuser` | none of them applied |
     | Members-admin update | the same fields, plus a harmless `first_name` change | the name changes, and nothing else does |
     | Users-admin update | `is_superuser`, `is_staff` | both stay false |
     | `PATCH /me/profile` | `user` set to another member's id | the profile stays the caller's |
     | Manual grant | `source`, `granted_by`, `ends_on`, `status`, `payment` | `source="manual"`, `granted_by` is the caller, `ends_on` computed from the plan, `status="active"`, no linked payment |
     | Checkout | `user`, `status`, `amount_cents` | the caller's payment, `pending`, the plan's price |
  3. **Mutation check**, not committed: for each case, add the forbidden field to its serializer, confirm the test fails, then revert.
- **Verify:** `uv run pytest backend/tests/test_server_controlled_fields.py -v`

### membership-annotations: one SQL membership rule for every list

- **Issues:** #29
- **Branch:** `feature/membership-annotations`; database `caldart_membership_annotations`; e2e on port 8107; after `account-edit-guard`
- **Owns:**
  - `backend/apps/members/services.py`, `backend/apps/members/api/admin_filters.py`, `backend/apps/members/reports.py`, `backend/apps/members/api/admin_serializers.py` (`get_membership` and imports)
  - `backend/apps/accounts/api/views.py` (the admin-user queryset), `backend/apps/accounts/api/serializers.py` (`UserSerializer.get_membership`)
  - `backend/apps/aircraft/services.py`
  - `backend/tests/test_members_admin_status.py`, `backend/tests/test_membership_query_counts.py` (new)
- **Docs:**
  - `docs/developer/api-members.rst`
  - `docs/developer/data-model.rst` (the `membership-status-sql` section)
  - `docs/developer/api-auth.rst`
  - `docs/developer/api-aircraft.rst`
- **Steps:**
  1. **Tests first.**
     - Endpoints: `/admin/users`, `/leader/search`, `/aircraft/{id}`, `/aircraft/lookup`, `/leader/aircraft` and `/admin/members`.
     - At 3 rows and at 20 rows, each endpoint must issue the same number of queries.
     - Today they differ: 16 vs 56, 8 vs 32 and 7 vs 23. `/admin/members` already passes.
  2. **Move the rule.**
     - Move `membership_annotations` and `membership_payload` from `api/admin_filters.py` into `members/services.py`.
     - Add `with_membership(queryset, *, today=None)` and `membership_of(user)`. `membership_of` reads the annotation when present and falls back to `membership_status` otherwise.
     - Rebuild `member_admin_queryset` on `with_membership`.
  3. **Accounts.** The admin-user views build their queryset in `get_queryset()`, so "today" is computed per request rather than frozen at start-up. `UserSerializer.get_membership` uses `membership_of`.
  4. **Aircraft.** The search results and the pilot list annotate their queries, and read from the payload.
  5. **Pin the counts.** Replace the equality checks with exact `django_assert_num_queries(K)` values.
- **Tests:**
  - query counts;
  - payload agreement for current, expired, lifetime and never-joined users: each list's `membership` equals `membership_status(user)`;
  - a frozen clock that crosses `ends_on` flips the status, which proves the queryset is built per request.
- **Verify:**
  - `uv run pytest backend/tests/test_membership_query_counts.py backend/tests/test_members_admin_status.py -x`
  - `grep -rn "apps.members.api" backend/apps --include=*.py | grep -v "/api/"` prints nothing.

### shared-membership-types: one status serializer, plan serializer, enum and invitation email

- **Issues:** #33
- **Branch:** `feature/shared-membership-types`; database `caldart_shared_membership_types`; after `membership-annotations`
- **Owns:**
  - `backend/apps/members/models.py` (`MembershipState`), `backend/apps/members/api/serializers.py` (new), `profile_serializers.py`, `profile_views.py`, `admin_serializers.py`, `admin_filters.py`, `backend/apps/members/services.py`
  - `backend/apps/accounts/api/serializers.py` (the status-serializer import), `backend/apps/accounts/services.py` (`send_password_invitation`), `backend/apps/accounts/models.py`
  - `backend/apps/payments/api/serializers.py`, `backend/apps/aircraft/api/serializers.py`, `backend/apps/aircraft/services.py`, `backend/apps/reminders/services.py`
  - `backend/templates/emails/member_invitation.{txt,html}` (new), `backend/tests/test_member_invitation.py` (new)
- **Steps:**
  1. **Tests first.**
     - The invitation link has no double slash, whether or not `SITE_URL` ends in `/`.
     - The subject is `"<org_name>: set your password"`.
     - The email has a text part and an HTML part.
     - The link works in the reset confirm.
     - A member created with a password gets no email.
  2. **Enum.** Add `MembershipState(TextChoices)`, keeping the existing labels.
  3. **Shared serializers.** Create `members/api/serializers.py` holding the one `MembershipStatusSerializer` and the one `PlanSerializer`. Repoint every import, and delete the copies.
  4. **Replace the literals.** Replace every `"current"`/`"expired"`/`"none"` list and comparison with the enum. Its members are `str`, so the JSON output doesn't change.
  5. **Invitation email.** Move `send_password_invitation` into `accounts/services.py`.
     - Build the link with `build_reset_url`, and render the new templates.
     - Use the same subject pattern as the reset email.
     - Send an HTML alternative.
     - Keep `transaction.on_commit` at the call site.
- **Verify:**
  - `grep -rn '"current", "expired", "none"' backend/apps` prints nothing.
  - `grep -rn "class MembershipStatusSerializer\|class PlanSerializer" backend/apps` prints two lines.

### permission-matrix-tests: pin the permission-matrix gaps

- **Issues:** #34
- **Branch:** `feature/permission-matrix-tests`; database `caldart_permission_matrix_tests`; after `auth-csrf-and-throttle-rates`
- **Owns:** `backend/tests/test_permission_matrix.py` (new), `backend/tests/conftest.py` (rename `anonymous_user` to `no_role_user`)
- **Docs:** `docs/developer/api-reference.rst`: one sentence on what a signed-in account with no roles may do.
- **Steps:**
  1. **Fixtures.** Rename the fixture, and add module fixtures:
     - an aircraft owned by another member;
     - a target member with a profile and one term;
     - autouse mock payments.
  2. **Parametrized tests**, with readable ids:
     - anonymous: 401 on seven write endpoints, and the rows are unchanged;
     - `system_admin` writes on members admin: create, update, grant, term correction;
     - `dart_leader`, `user_admin` and `website_admin` get 403 patching someone else's aircraft;
     - every role may `PUT` and `PATCH` its own profile;
     - the Wagtail admin redirects `user_admin`, `account_admin` and a role-less user to `/admin/login/`;
     - a role-less user gets its self-service GETs and checkout (200/201), and a 403 on role-gated endpoints.
- **Verify:** `uv run pytest backend/tests/test_permission_matrix.py -v`, and `grep -rn "anonymous_user" backend/tests` prints nothing.

### account-and-member-services: domain logic in services that raise domain errors

- **Issues:** #16
- **Branch:** `feature/account-and-member-services`; database `caldart_account_and_member_services`; e2e on port 8110
- **After:** `shared-membership-types`, `member-delete-keeps-payments`, `server-controlled-field-tests`, `auth-csrf-and-throttle-rates` and `payment-provider-errors`
- **Owns:**
  - `backend/caldart/exceptions.py`
  - `backend/apps/accounts/services.py`, `backend/apps/accounts/api/serializers.py`, `backend/apps/accounts/api/views.py`
  - `backend/apps/members/services.py`, `backend/apps/members/api/admin_serializers.py`, `backend/apps/members/api/admin_views.py`
  - `backend/apps/payments/services.py`, `backend/apps/payments/reports.py`, `backend/apps/payments/api/serializers.py`, `backend/apps/payments/api/views.py`
  - `backend/tests/test_payments_mock_provider.py`, `backend/tests/test_accounts_auth.py` (one docstring)
  - new tests: `test_account_services.py`, `test_member_services.py`, `test_domain_errors.py`, `test_payment_report_query.py`
- **Docs:** `docs/developer/api-reference.rst` (Error shape), `PLAN.rst` §6 introduction
- **Steps:**
  1. **Domain errors.** Add `DomainError`, `DomainValidationError(field, message)` and `DomainPermissionError(message)` to `caldart/exceptions.py`. The handler renders them as a field-keyed 400 and a `detail` 403. Write `test_domain_errors.py` first.
  2. **`accounts.services`.**
     - Add `AccountChanges` (a `TypedDict`, `total=False`).
     - `create_account(...)` creates the user and grants `member`.
     - `update_account(actor, target, changes)` runs atomically, in this order:
       1. refuse self-deactivation;
       2. only `system_admin` may grant or revoke `system_admin`;
       3. apply the guard from `account-edit-guard`, moved here unchanged;
       4. assign the fields;
       5. set the roles and call `sync_django_flags`.
     - Delete `register_user`.
  3. **`members.services`.**
     - `register_member(...)` (atomic).
     - `create_member(actor, ...)`, which queues the invitation on commit when there is no password.
     - `update_member(actor, target, *, account, profile)`.
     - `delete_member(actor, target)`, which carries the delete guards, including the payment guard from `member-delete-keeps-payments`, moved unchanged.
  4. **Rewire the callers.** The serializers and views call the services, and `RegisterView` calls `register_member`.
  5. **Payments.**
     - `create_checkout` raises `DomainValidationError`, keeping the messages.
     - Add a `PaymentReportQuerySerializer` for the three report views: `from`, `to`, `provider`, `status`, `search` and `group`, with today's exact messages.
     - An impossible date then answers 400, not 500.
     - `summarise` takes a group that has already been validated.
  6. **Keep the contract.** Status codes and bodies don't change, and every existing API test passes unmodified.
- **Tests:**
  - `test_domain_errors.py`: the two error shapes; `NotAuthenticated` stays 401.
  - `test_account_services.py`: the update rules, including the takeover guard and role canonicalisation.
  - `test_member_services.py`: atomic registration; the invitation sent only on commit; update, and the delete guards.
  - `test_payments_mock_provider.py`: the refusals, by exception type and `match=`.
  - `test_payment_report_query.py`: `?from=2026-02-30` is a 400 on list, summary and export.
- **Verify:**
  - `grep -rn "rest_framework" backend/apps/*/services.py backend/apps/*/reports.py` prints nothing.
  - `uv run pytest backend/tests/test_domain_errors.py backend/tests/test_account_services.py backend/tests/test_member_services.py backend/tests/test_payment_report_query.py -x`

### app-layering: one-way dependencies between apps; TimestampedModel in the project package

- **Issues:** #32
- **Branch:** `feature/app-layering`; database `caldart_app_layering`; after `account-and-member-services` and `membership-annotations`
- **Owns:**
  - `backend/caldart/models.py` (new)
  - the `TimestampedModel` import in `backend/apps/{members,aircraft,payments,reminders}/models.py`
  - the sanctioned-import comments in `backend/apps/accounts/models.py`, `backend/apps/accounts/services.py` and `backend/apps/reminders/services.py`
  - `backend/tests/test_app_layering.py` (new)
- **Docs:** `PLAN.rst` §3 (the layout, plus a "Dependencies between apps" paragraph), the `CLAUDE.md` Layout entry for `caldart/`, `docs/developer/data-model.rst` (where `TimestampedModel` lives)
- **Steps:**
  1. **Move the base model.** Move `TimestampedModel` verbatim into `caldart/models.py` and update its four imports. `makemigrations --check` must report no changes.
  2. **Write `test_app_layering.py`.** It is `ast`-based, with no new dependency, and checks that:
     - with layers `accounts 1`, `members 2`, `aircraft 3`, `payments 3`, `reminders 4`, `cms 5` and `sysadmin 5`, a domain module imports only its own app or a lower layer;
     - no domain module imports `apps.<x>.api`. `api/`, `admin.py` and `management/` are composition points and are exempt;
     - every inline cross-app import is on the sanctioned list, and every entry on that list still exists;
     - `caldart/models.py`, `reports.py`, `exceptions.py` and `pagination.py` import nothing from `apps`.
  3. **Comment the sanctioned inline imports.** Each gets a comment giving its reason: `python.md` §2 allows inline imports to break a cycle.
- **Verify:** `makemigrations --check --dry-run` (part of `make check`), and `uv run pytest backend/tests/test_app_layering.py -v`.

### audit-logging: record privileged actions

- **Issues:** #31
- **Branch:** `feature/audit-logging`; database `caldart_audit_logging`; after `app-layering` and `reminder-scan-resilience`
- **Owns:**
  - `backend/caldart/audit.py` (new), `backend/caldart/settings/base.py` (the `caldart.audit` entry in `LOGGING`)
  - the call sites in `backend/apps/accounts/services.py`, `backend/apps/accounts/api/views.py`, `backend/apps/members/services.py` and `backend/apps/members/api/admin_views.py`
  - `backend/apps/sysadmin/services.py`, `backend/apps/sysadmin/api/views.py`, `backend/apps/sysadmin/management/commands/db_reset.py`
  - `backend/apps/reminders/services.py` (the run summary), `backend/apps/reminders/api/views.py`
  - `backend/tests/test_audit_logging.py` (new)
- **Docs:** `docs/developer/deployment.rst` (Logs), `docs/developer/configuration.rst` (the `LOG_LEVEL` note), `docs/developer/roadmap.rst` (Audit log)
- **Steps:**
  1. **The logger.** `caldart.audit` has `propagate: False` and level INFO, so `LOG_LEVEL=WARNING` doesn't silence it. `record(action, *, actor, target=None, level=INFO, **fields)` accepts only ints, bools, short slugs and lists of slugs, and raises `TypeError` for anything else, so no value can be logged by accident.
  2. **Instrument these actions:**
     - `account.update` (field names only) and `account.roles` (added, removed);
     - `account.deactivate` and `account.activate`;
     - `member.create` and `member.delete`;
     - `membership.grant` and `membership.correct`;
     - `password_reset.admin_sent`;
     - `backup.create`, `backup.download` and `backup.restore`;
     - `db.reset`;
     - `reminders.run`, with its counts.

     Log refusals at WARNING with a reason slug. The actor is `command` for management commands and the timer.
- **Tests:**
  - one test per action, through the public API or command, asserting exactly one record;
  - the refusals;
  - no email address or name appears in any record;
  - the audit record is still captured with the root logger at WARNING.
- **Verify:** `uv run pytest backend/tests/test_audit_logging.py -x`

### Tracking: annotate and document every backend function (#17, #18)

These two tracking issues ship as one ratchet PR, then one PR per unit, then a closing PR. Each unit PR carries both its annotations and its docstrings. Every PR says `Refs #17.` and `Refs #18.`, except the closing PR, which says `Closes`.

1. **`backend-types-ratchet`.**
   - In `pyproject.toml`, add `"ANN"` and `"D"` to `select`, and add these settings:
     - `[tool.ruff.lint.flake8-annotations] allow-star-arg-any = true`
     - `[tool.ruff.lint.pydocstyle] convention = "google"`
     - `[tool.ruff.lint.pycodestyle] max-doc-length = 90`
   - Ignore `D104` and `D106`.
   - Add a `[tool.ruff.lint.per-file-ignores]` table with one `["ANN", "D"]` entry for each unit below, each under a comment naming the unit. List the test files explicitly under their group's comment.
   - Rewrap the two over-long docstring lines, `backend/apps/cms/models.py:263` and `backend/tests/test_cms_seed_content.py:1`.
   - `make lint` stays green.
2. **One package per unit.** The units run in parallel after the ratchet merges. For each unit:
   1. delete its `per-file-ignores` entry;
   2. run `uv run ruff check <paths>`;
   3. annotate and document until ruff is clean;
   4. run `make lint test`.

   Behavior must not change. Conventions:
   - **Types:**
     - DRF's `Request` and `Response` for handlers;
     - `QuerySet[User]` for querysets;
     - `dict[str, Any]` for `validate(attrs)` and `to_representation`;
     - `-> None` on `__init__` and `handle`;
     - `if TYPE_CHECKING:` imports where a real import would create a cycle.
   - **Docstrings** follow `python.md` §5: a summary line, then the behavior in prose, naming the parameters, return value and exceptions a caller needs. No `Parameters:`, `Returns:` or `Raises:` sections are required.
     - DRF views state the method, path, permission, request and response shapes, and status codes.
     - Serializers state what each validator rejects, with the exact message.
     - Wrap at 90 characters, and keep `.py` files ASCII.
   - **Members unit:** replace `MembershipStatusDict = dict` with a `TypedDict` typed with `MembershipState`.

   | Package | Unit |
   |---|---|
   | `backend-types-core` | `backend/caldart/**`, `backend/manage.py`, `docs/conf.py` |
   | `backend-types-reminders`, `-sysadmin`, `-aircraft`, `-payments`, `-accounts`, `-cms`, `-members` | `backend/apps/<app>/**` (migrations stay excluded) |
   | `backend-types-tests-accounts`, `-members`, `-aircraft`, `-payments`, `-reminders`, `-cms`, `-sysadmin`, `-shared` | the test files listed under that group's comment in `per-file-ignores` (`shared` includes `conftest.py` and `factories.py`) |
3. **`backend-types-finish`.** Start it only when `per-file-ignores` has no `ANN` or `D` entry left.
   - Update `.claude/rules/python.md`:
     - §5: docstrings are prose with no required sections, and ruff's `D` rules enforce that they exist and are well formed. `D104` and `D106` are ignored.
     - §7: add the `ANN` and `D` rows.
   - Update the ruff paragraph in `docs/developer/testing.rst`.
   - The PR says `Closes #17.` and `Closes #18.`.

When a unit's rebase conflicts in `per-file-ignores`, keep every deletion from both sides.

### vite-react-refresh: the portal boots under the Vite dev server

- **Issues:** #20
- **Branch:** `bugfix/vite-react-refresh`; database `caldart_vite_react_refresh`
- **Owns:** `backend/templates/portal.html`, `backend/tests/test_shell_views.py`
- **Docs:** `docs/developer/setup.rst` ("Working on the frontend", and a troubleshooting entry for "can't detect preamble")
- **Steps:**
  1. Add `{% vite_react_refresh %}` immediately before `{% vite_hmr_client %}` in `portal.html`, and say why in the template comment. It renders nothing in production.
  2. Add a `vite_dev_mode(settings)` fixture:
     1. deep-copy `DJANGO_VITE`, set `dev_mode = True` on the copy, and assign it back;
     2. reset `DjangoViteAssetLoader._instance = None` before and after, because django-vite caches the setting in a singleton.
- **Tests:**
  - in dev mode, `/portal/` contains `window.$RefreshReg$`, and `RefreshRuntime` comes before `@vite/client`, which comes before `src/portal/main.tsx`;
  - in production, the page has no `RefreshRuntime`.
- **Verify:** `uv run pytest backend/tests/test_shell_views.py -x`. On a workstation, also run with `DJANGO_VITE_DEV_MODE=true`, `make run` and `make dev-frontend`: `/portal/login` must render with no preamble error.

### api-client-errors: CSRF bootstrap recovers; a non-JSON 2xx is an error

- **Issues, in commit order:** #36, #39
- **Branch:** `bugfix/api-client-errors`; database `caldart_api_client_errors`; e2e on port 8103
- **Owns:**
  - `frontend/src/portal/api/client.ts`, `frontend/src/portal/api/client.test.ts`
  - `frontend/src/test/setup.ts` (the CSRF reset), `frontend/src/test/handlers.ts`
  - `frontend/src/portal/features/profile/ProfilePage.test.tsx`
- **Docs:** `docs/developer/testing.rst`, `docs/developer/api-auth.rst`, `PLAN.rst` §6 front matter and §8
- **Steps:**
  1. **#36: the CSRF bootstrap recovers.**
     - `ensureCsrfToken({ force })` rejects on a failed bootstrap and clears the cached promise in `finally`, so the next call retries.
     - `request` retries once after a 403 whose `detail` starts with `CSRF Failed`: it re-bootstraps with `force`, re-reads the cookie, and resends. Keep the prefix in a module constant.
     - The test harness calls `resetCsrfBootstrap()` in `afterEach`, and the default `/auth/csrf` handler sets `csrftoken`.
     - The profile save test asserts `X-CSRFToken`.
  2. **#39: a 2xx must be JSON.**
     - Split `parseBody` into `parseErrorBody`, which is lenient, and `parseSuccessBody`.
     - An empty 2xx returns `null`. JSON that doesn't parse, or any non-JSON content type, throws the new exported `UnexpectedResponseError(status, contentType)`.
- **Tests:** `client.test.ts`:
  - the bootstrap retries after a network failure, after a 500, and when no cookie was set;
  - concurrent requests share one bootstrap;
  - a CSRF 403 is retried exactly once;
  - a second CSRF 403 doesn't loop;
  - a permission 403 is not retried;
  - a 2xx HTML page and broken JSON both reject;
  - an empty 2xx returns `null`;
  - an HTML error page is still an `ApiError`.
- **Verify:** `cd frontend && npx vitest run --sequence.shuffle`, twice.

### auth-check-errors: a failed sign-in check shows an error, not the login page

- **Issues:** #37
- **Branch:** `bugfix/auth-check-errors`; database `caldart_auth_check_errors`; e2e on port 8104
- **Owns:** `frontend/src/portal/auth/useAuth.ts`, `frontend/src/portal/auth/guards.tsx`, `frontend/src/portal/auth/guards.test.tsx`
- **Docs:** `docs/developer/api-auth.rst` ("How the portal uses this"), `PLAN.rst` §8
- **Steps:**
  1. **`useAuth` state.** Add `refetch` and `isRefetching` to `AuthState`. Drop `retry: false` from `useMe`, so the app-wide policy retries 5xx and network errors twice.
  2. **Guards.** In `RequireAuth` and `RequireRole`, after the loading check, show `AuthUnavailable` when `user === null && error != null`. It is a `role="alert"` empty state titled "We could not check your sign-in", with a "Try again" button.
  3. **Comment.** Rewrite the guards' header comment to cover all three outcomes: anonymous → login; wrong role → 403; failed check → error with a retry.
- **Tests:** `guards.test.tsx`:
  - a 500 shows the alert and the button;
  - a network failure shows it too;
  - "Try again" recovers;
  - a failed background refetch keeps the page;
  - the existing 401 cases don't change.

### shared-debounce: one tested debounce hook

- **Issues:** #42
- **Branch:** `feature/shared-debounce`; database `caldart_shared_debounce`
- **Owns:**
  - `frontend/src/portal/components/useDebounced.ts` and `.test.ts` (both new)
  - `frontend/src/portal/features/admin-users/useDebounced.ts` and `features/aircraft/useDebounced.ts` (both deleted)
  - `frontend/src/portal/features/admin-users/index.ts`, `UsersListPage.tsx`
  - `frontend/src/portal/features/aircraft/AircraftPicker.tsx`, `frontend/src/portal/features/admin-aircraft/AircraftRegisterPage.tsx`, `frontend/src/portal/features/leader/LeaderSearchPage.tsx`
  - `frontend/src/portal/features/checkout/StripePanel.tsx`
- **Steps:**
  1. Create `components/useDebounced.ts`, exporting `SEARCH_DEBOUNCE_MS = 250` and `useDebounced(value, delayMs)`, with JSDoc. Don't add it to the components barrel.
  2. Repoint the four page imports. Delete `StripePanel`'s private copy, but keep its `500` ms call.
  3. Delete the two feature hooks and the `admin-users` re-export.
- **Tests:** `useDebounced.test.ts`, with fake timers:
  - the initial value;
  - no change before the delay;
  - the timer restarts on each change;
  - a custom delay;
  - no update after unmount.

### profile-fieldsets: one profile fieldset for members and admins

- **Issues:** #41
- **Branch:** `feature/profile-fieldsets`; database `caldart_profile_fieldsets`; e2e on port 8105
- **Owns:**
  - `frontend/src/portal/features/profile/ProfileFieldsets.tsx` and `.test.tsx` (both new), `ProfileForm.tsx`
  - `frontend/src/portal/features/admin-members/MemberFormFields.tsx`, `MemberCreatePage.tsx`, `MemberProfileTab.tsx`, `choices.ts`
  - `frontend/src/portal/features/admin-members/MemberCreatePage.test.tsx` and `MemberDetailPage.test.tsx` (only where a label deliberately changes)
- **Steps:**
  1. **Shared fieldset.** Move the three fieldsets from `ProfileForm.tsx` into `ProfileFieldsets`: `value`, `onChange`, `errors`, `darts`, `dartsLoading` and `markRequired`. The member form's labels, hints, input types and constraints are canonical.
  2. **Member form.** `ProfileForm` keeps its state, validation and submit handling, and renders `<ProfileFieldsets markRequired …/>`.
  3. **Admin forms.** `MemberFormFields` keeps only an `AdminOnlyFields` component. The admin create page and profile tab render `ProfileFieldsets` plus `AdminOnlyFields`.
  4. **Clean up.** Delete any `choices.ts` export left without an importer.
- **Tests:** `ProfileFieldsets.test.tsx`:
  - every label renders;
  - typing and selecting emit the right values;
  - State is upper-cased;
  - toggles work;
  - errors render under their field;
  - the required markers depend on `markRequired`.

  The existing profile, join and admin-members tests stay green.
- **Verify:** `make e2e` with the package's port; the self-service flow edits the profile.

### checkout-strict-mode: checkout effects are safe to run twice

- **Issues:** #38
- **Branch:** `bugfix/checkout-strict-mode`; database `caldart_checkout_strict_mode`; e2e on port 8108; after `api-client-errors` and `shared-debounce`
- **Owns:**
  - `frontend/src/portal/features/checkout/CheckoutReturn.tsx`, `api.ts`, `Checkout.tsx`, `StripePanel.tsx`
  - `frontend/src/test/setup.ts` (the StrictMode switch)
  - `frontend/src/portal/features/checkout/CheckoutReturn.test.tsx`, `Checkout.test.tsx`
- **Docs:** `docs/developer/testing.rst` (every render runs in StrictMode)
- **Steps:**
  1. **Stripe panel.** Fold in the core of "Stop the Stripe panel creating duplicate PaymentIntents", from the frontend-code checklist in #58: `createCheckout(request, signal?)`. The `StripePanel` effect aborts its request in cleanup and ignores `AbortError`.
  2. **API signals.** `confirmStripePayment` and `fetchPayment` take an optional `signal`.
  3. **`CheckoutReturn`.**
     - Drop the `started` ref.
     - Create one `AbortController` per effect run, use an abortable wait, and check `signal.aborted` where the code checked `cancelled`.
     - Abort in cleanup.
  4. **`Checkout.tsx`.** Derive `effectivePlan` from the offered plans, instead of a ref-guarded effect.
  5. **Tests.** Call `configure({ reactStrictMode: true })` in `setup.ts`. The seven StrictMode failures must go away. Fix them in the components, never in the tests.
- **Tests:**
  - `CheckoutReturn.test.tsx`: the confirmation is posted once under StrictMode.
  - `Checkout.test.tsx`: the first offered plan is selected when there is no annual plan, and there is exactly one checkout request.
- **Verify:** `cd frontend && npx vitest run src/portal/features/checkout src/portal/features/join`, plus `make e2e` (join and pay).

### route-table: test the real route table; load feature pages lazily

- **Issues, in commit order:** #46, #40
- **Branch:** `feature/route-table`; database `caldart_route_table`; e2e on port 8109; after `auth-check-errors`
- **Owns:**
  - `frontend/src/portal/routes/*.tsx` (including `index.tsx`) and `frontend/src/portal/routes/index.test.tsx` (new)
  - `frontend/src/portal/components/Loading.tsx` (new), `frontend/src/portal/auth/guards.tsx` (the `Loading` move)
  - `frontend/src/test/render.tsx` (`renderRoutes`)
- **Docs:** `docs/developer/testing.rst`, `PLAN.rst` §8
- **Steps:**
  1. **#46: test the real route table.**
     - Add `renderRoutes(routes, { route, client })` to `render.tsx`.
     - In `routes/index.test.tsx`, stub every page module with `vi.mock`, and keep the layout, guards and `NotFound` real.
     - Declare two tables, identities and guarded paths, with each path's `allowed` list written out explicitly.
     - Assert: an allowed identity sees the page heading; a denied one sees "You do not have access to this page"; an anonymous visitor is redirected to `/login?next=<path>`.
     - Add three single cases: `/login`, `/join`, and an unknown path.
     - Removing `RequireRole` from `routes/system.tsx` must make the test fail. Try it, then revert.
  2. **#40: load feature pages lazily.**
     - Move `Loading` into `components/Loading.tsx`.
     - Convert every route file except `auth`, `dashboard` and `not-found` to the function form of `lazy`, importing page modules directly and never through barrels.
     - Add `hydrateFallbackElement: <Loading />` to the root route.
     - Update the `vi.mock` specifiers from step 1 to the direct page modules.
- **Tests:** the route table test (about 16 paths × 8 identities, plus the three single cases), a lazy route rendering through the real table, and the loading status while it loads.
- **Verify:** after `npm run build`:
  - the manifest's portal entry lists `dynamicImports`;
  - `grep -l "Taking a backup" dist/assets/*.js` doesn't match the entry chunk;
  - the PR records the entry and chunk sizes.

### api-types: every API shape in `api/types.ts`

- **Issues:** #43
- **Branch:** `feature/api-types`; database `caldart_api_types`
- **After:** `profile-fieldsets`, `auth-check-errors`, `shared-debounce` and `member-delete-keeps-payments`
- **Owns:**
  - `frontend/src/portal/api/types.ts`
  - `frontend/src/portal/features/admin-members/{types,index,api,fixtures}.ts`, and the admin-members components `MemberDetailPage`, `MemberProfileTab`, `MemberMembershipsTab`, `MemberPaymentsTab`, `MemberDangerZone` and `MemberFormFields`
  - `frontend/src/portal/features/aircraft/{api,index}.ts`
  - `frontend/src/portal/features/leader/api.ts`, `AircraftStatusCard.tsx`, `LeaderAircraftPage.test.tsx`
  - `frontend/src/portal/features/admin-aircraft/AircraftRecordPage.test.tsx`
  - `frontend/src/portal/features/admin-users/{api,index}.ts`
  - `frontend/src/portal/auth/useAuth.ts`, `frontend/src/portal/features/profile/api.ts`
- **Steps:**
  1. **Check the shapes first.** Compare each shape with its serializer, and report any mismatch in the PR.
  2. **Move the types into `api/types.ts`**, with their JSDoc and the endpoint each belongs to:
     - `PasswordResetRequestPayload`, `AdminUserPatch`, `SendPasswordResetResult`;
     - `AttachedAircraft`, `AircraftPilot`, `AircraftDetail`;
     - `AdminProfile`, `MemberTerm`, `MemberPayment`, `MemberDetail`;
     - the five admin-members request payloads.
  3. **Repoint the importers** to `import type … from '…/api/types'`.
  4. **Barrels.** Drop the moved names from the barrels, and keep only the filter state in `admin-members/types.ts`.
- **Verify:** `npm run typecheck && npm run lint && npm run test`.

### fake-timers: time-dependent tests run on a controlled clock

- **Issues:** #47
- **Branch:** `feature/fake-timers`; database `caldart_fake_timers`; after `checkout-strict-mode`
- **Owns:**
  - `frontend/src/test/setup.ts` (the timer reset)
  - `CheckoutReturn.test.tsx`, `AircraftPicker.test.tsx`, `LeaderSearchPage.test.tsx`, `UsersListPage.test.tsx` and `AircraftRegisterPage.test.tsx`
  - `HealthPanel.test.tsx`, `SystemPage.test.tsx`, `BackupsPanel.test.tsx` and `DashboardPage.test.tsx`, all under `frontend/src/portal/features/`
- **Docs:** `docs/developer/testing.rst` (a short "Time" paragraph)
- **Steps:**
  1. **Global reset.** `setup.ts` restores real timers after every test.
  2. **Debounce tests.** Use `vi.useFakeTimers({ shouldAdvanceTime: true })` with `userEvent.setup({ advanceTimers: vi.advanceTimersByTime })`, and advance by `SEARCH_DEBOUNCE_MS`, imported from the shared hook.
  3. **CheckoutReturn.** Advance by `POLL_INTERVAL_MS`, drop the five-second timeouts, and assert exactly two polls. Add the "still being processed" timeout test.
  4. **Pin the clock** at `2026-06-15T12:00:00Z` in the health, system and dashboard tests. `isoIn` reads `NOW` and uses no `toISOString`. Add the two dashboard boundary cases around `EXPIRING_WINDOW_DAYS`.
  5. **Backups panel.** Use msw's `delay(50)` instead of a real sleep.
- **Verify:** `cd frontend && npx vitest run --reporter=verbose`. The converted tests no longer wait 250 ms or 1,000 ms in real time.

### Tracking: return types and JSDoc on every exported function (#44, #45)

Four chained PRs. Each one annotates a group of directories with both return types and JSDoc, and appends those directories to the `files` list of one ESLint block that enables both rules. Every PR says `Refs #44.` and `Refs #45.`, except the last, which says `Closes`.

**Rules:**
- `@typescript-eslint/explicit-module-boundary-types`;
- `jsdoc/require-jsdoc`, with `publicOnly: true` and function declarations and expressions required;
- `jsdoc/no-types`.

**Conventions:**
- **Components** return `JSX.Element`, or `JSX.Element | null`.
- **Query hooks** return `UseQueryResult<T>`.
- **Mutation hooks** return `UseMutationResult<TData, Error, TVariables>`.
- **JSDoc** is one sentence of purpose. Add `@param`, `@returns` and `@throws` only where the signature doesn't already say it: the endpoint called, the query keys invalidated, the errors thrown. Use no `{type}` braces, and no change history.
- **Nothing else changes.** No behavior changes.

| Package | Directories | Extra work |
|---|---|---|
| `frontend-types-docs-shared` | `components/`, `api/`, `auth/`, `routes/`, `layout/`, `App.tsx`, `choices.ts`, `nav.ts`, `src/site/`, `src/test/` | Add `eslint-plugin-jsdoc` in its own `build:` commit, installed with `npx -y npm@11 install --save-dev eslint-plugin-jsdoc`, because npm 10.9.2 crashes on this tree. Verify it with a clean `npm ci` and `make audit`. Create the ESLint block. |
| `frontend-types-docs-admin` | `features/admin-aircraft/`, `admin-members/`, `admin-payments/`, `admin-users/` | none |
| `frontend-types-docs-flows` | `features/aircraft/`, `auth/`, `checkout/`, `dashboard/` | none |
| `frontend-types-docs-finish` | `features/join/`, `leader/`, `profile/`, `system/` | Move both rules into the main ESLint block for `**/*.{ts,tsx}`, delete the per-directory block, and update `testing.rst` if it lists the enforced rules. `Closes #44.` `Closes #45.` |

Before the finishing PR, running ESLint with the widened config must report zero violations of the three rules.

## 8. Manifest

The orchestrator reads this block. It holds one JSON object per package. The fields:

- `after`: the packages that must merge first.
- `closes` and `refs`: issue numbers.
- `database` and `e2e_port`: the package's own database and port (§3).
- `owns`: the files and globs the package may change.
  - A `#section` suffix names the part of a shared file a package may change, so two packages can own different sections of one file.
  - `backend/tests/@<group>` means the test files listed under that group's comment in the `per-file-ignores` table that `backend-types-ratchet` creates.

```json
[
  {"wave": 1, "package": "account-edit-guard", "branch": "bugfix/account-edit-guard", "database": "caldart_account_edit_guard", "e2e_port": null, "closes": [14], "refs": [], "owns": ["backend/apps/accounts/services.py", "backend/apps/accounts/api/serializers.py", "backend/apps/members/api/admin_serializers.py", "backend/apps/members/api/admin_views.py", "backend/tests/test_account_edit_guard.py"], "after": []},
  {"wave": 1, "package": "production-settings", "branch": "bugfix/production-settings", "database": "caldart_production_settings", "e2e_port": 8101, "closes": [27, 28, 15], "refs": [], "owns": ["backend/caldart/settings/_dotenv.py", "backend/caldart/settings/base.py#dotenv", "backend/caldart/settings/dev.py", "backend/caldart/settings/test.py", "backend/caldart/settings/prod.py", "backend/caldart/wsgi.py", "backend/caldart/asgi.py", "deploy/caldart.env.example", "deploy/systemd/caldart-web.service", "deploy/apache/caldart.conf#headers", "deploy/nginx/caldart.conf#headers", "backend/tests/test_sysadmin_settings.py", "backend/tests/test_settings_fail_closed.py", "backend/tests/test_hsts.py", "backend/tests/test_auth_throttle_ident.py"], "after": []},
  {"wave": 1, "package": "payment-provider-errors", "branch": "bugfix/payment-provider-errors", "database": "caldart_payment_provider_errors", "e2e_port": 8102, "closes": [19, 23, 24], "refs": [], "owns": ["backend/apps/payments/providers/base.py", "backend/apps/payments/providers/stripe.py", "backend/apps/payments/providers/paypal.py", "backend/tests/test_payments_stripe.py", "backend/tests/test_payments_provider_errors.py", "backend/tests/test_payments_stripe_client.py"], "after": []},
  {"wave": 1, "package": "reminder-scan-resilience", "branch": "bugfix/reminder-scan-resilience", "database": "caldart_reminder_scan_resilience", "e2e_port": null, "closes": [25], "refs": [], "owns": ["backend/apps/reminders/services.py", "backend/apps/reminders/management/commands/send_renewal_reminders.py", "backend/templates/emails/reminder_*", "backend/tests/test_reminders.py", "backend/tests/test_reminders_resilience.py"], "after": []},
  {"wave": 1, "package": "docs-accuracy", "branch": "bugfix/docs-accuracy", "database": "caldart_docs_accuracy", "e2e_port": null, "closes": [49, 48, 50, 53, 51, 52], "refs": [], "owns": ["docs/developer/data-model.rst", "docs/developer/api-profile.rst", "docs/developer/api-reference.rst#permissions", "docs/developer/api-payments.rst", "docs/developer/cms.rst", "docs/user/member-guide.rst", "docs/user/aircraft.rst", "docs/user/website-administrator-guide.rst", "docs/user/system-administrator-guide.rst", "docs/demo-walkthrough.rst"], "after": []},
  {"wave": 1, "package": "make-switches", "branch": "bugfix/make-switches", "database": "caldart_make_switches", "e2e_port": null, "closes": [55], "refs": [], "owns": ["Makefile#switches", "backend/tests/test_makefile_switches.py"], "after": []},
  {"wave": 1, "package": "server-controlled-field-tests", "branch": "feature/server-controlled-field-tests", "database": "caldart_server_controlled_field_tests", "e2e_port": null, "closes": [35], "refs": [], "owns": ["backend/tests/test_server_controlled_fields.py"], "after": []},
  {"wave": 1, "package": "vite-react-refresh", "branch": "bugfix/vite-react-refresh", "database": "caldart_vite_react_refresh", "e2e_port": null, "closes": [20], "refs": [], "owns": ["backend/templates/portal.html", "backend/tests/test_shell_views.py"], "after": []},
  {"wave": 1, "package": "api-client-errors", "branch": "bugfix/api-client-errors", "database": "caldart_api_client_errors", "e2e_port": 8103, "closes": [36, 39], "refs": [], "owns": ["frontend/src/portal/api/client.ts", "frontend/src/portal/api/client.test.ts", "frontend/src/test/setup.ts#csrf", "frontend/src/test/handlers.ts", "frontend/src/portal/features/profile/ProfilePage.test.tsx"], "after": []},
  {"wave": 1, "package": "auth-check-errors", "branch": "bugfix/auth-check-errors", "database": "caldart_auth_check_errors", "e2e_port": 8104, "closes": [37], "refs": [], "owns": ["frontend/src/portal/auth/useAuth.ts", "frontend/src/portal/auth/guards.tsx", "frontend/src/portal/auth/guards.test.tsx"], "after": []},
  {"wave": 1, "package": "shared-debounce", "branch": "feature/shared-debounce", "database": "caldart_shared_debounce", "e2e_port": null, "closes": [42], "refs": [], "owns": ["frontend/src/portal/components/useDebounced.ts", "frontend/src/portal/components/useDebounced.test.ts", "frontend/src/portal/features/admin-users/useDebounced.ts", "frontend/src/portal/features/aircraft/useDebounced.ts", "frontend/src/portal/features/admin-users/index.ts", "frontend/src/portal/features/admin-users/UsersListPage.tsx", "frontend/src/portal/features/aircraft/AircraftPicker.tsx", "frontend/src/portal/features/admin-aircraft/AircraftRegisterPage.tsx", "frontend/src/portal/features/leader/LeaderSearchPage.tsx", "frontend/src/portal/features/checkout/StripePanel.tsx"], "after": []},
  {"wave": 1, "package": "profile-fieldsets", "branch": "feature/profile-fieldsets", "database": "caldart_profile_fieldsets", "e2e_port": 8105, "closes": [41], "refs": [], "owns": ["frontend/src/portal/features/profile/ProfileFieldsets.tsx", "frontend/src/portal/features/profile/ProfileFieldsets.test.tsx", "frontend/src/portal/features/profile/ProfileForm.tsx", "frontend/src/portal/features/admin-members/MemberFormFields.tsx", "frontend/src/portal/features/admin-members/MemberCreatePage.tsx", "frontend/src/portal/features/admin-members/MemberProfileTab.tsx", "frontend/src/portal/features/admin-members/choices.ts", "frontend/src/portal/features/admin-members/MemberCreatePage.test.tsx", "frontend/src/portal/features/admin-members/MemberDetailPage.test.tsx"], "after": []},
  {"wave": 2, "package": "member-delete-keeps-payments", "branch": "bugfix/member-delete-keeps-payments", "database": "caldart_member_delete_keeps_payments", "e2e_port": null, "closes": [26], "refs": [], "owns": ["backend/apps/payments/models.py", "backend/apps/payments/migrations/0001_initial.py", "backend/apps/members/api/admin_views.py", "backend/tests/test_members_admin.py", "backend/tests/test_members_delete_payments.py", "frontend/src/portal/features/admin-members/MemberDangerZone.tsx", "frontend/src/portal/features/admin-members/MemberDangerZone.test.tsx"], "after": ["account-edit-guard"]},
  {"wave": 2, "package": "auth-csrf-and-throttle-rates", "branch": "bugfix/auth-csrf-and-throttle-rates", "database": "caldart_auth_csrf_and_throttle_rates", "e2e_port": 8106, "closes": [30, 21], "refs": [], "owns": ["backend/caldart/settings/base.py#rest-framework", "backend/caldart/authentication.py", "backend/apps/accounts/throttling.py", ".env.example#throttles", "backend/tests/conftest.py", "backend/tests/test_payments_stripe.py", "backend/tests/test_auth_throttle_rates.py", "backend/tests/test_csrf.py"], "after": ["production-settings", "payment-provider-errors", "api-client-errors"]},
  {"wave": 2, "package": "members-only-documents", "branch": "bugfix/members-only-documents", "database": "caldart_members_only_documents", "e2e_port": null, "closes": [22], "refs": [], "owns": ["backend/apps/cms/wagtail_hooks.py", "backend/apps/cms/models.py", "backend/apps/cms/management/commands/seed_content.py", "backend/caldart/settings/base.py#wagtaildocs", "deploy/nginx/caldart.conf#media", "deploy/apache/caldart.conf#media", "backend/tests/test_cms_documents.py"], "after": ["production-settings"]},
  {"wave": 2, "package": "production-commands-docs", "branch": "bugfix/production-commands-docs", "database": "caldart_production_commands_docs", "e2e_port": null, "closes": [54], "refs": [], "owns": ["docs/developer/deployment.rst#commands", "docs/developer/backup-restore.rst#production"], "after": ["production-settings", "make-switches"]},
  {"wave": 2, "package": "membership-annotations", "branch": "feature/membership-annotations", "database": "caldart_membership_annotations", "e2e_port": 8107, "closes": [29], "refs": [], "owns": ["backend/apps/members/services.py", "backend/apps/members/api/admin_filters.py", "backend/apps/members/reports.py", "backend/apps/members/api/admin_serializers.py", "backend/apps/accounts/api/views.py", "backend/apps/accounts/api/serializers.py", "backend/apps/aircraft/services.py", "backend/tests/test_members_admin_status.py", "backend/tests/test_membership_query_counts.py"], "after": ["account-edit-guard"]},
  {"wave": 2, "package": "checkout-strict-mode", "branch": "bugfix/checkout-strict-mode", "database": "caldart_checkout_strict_mode", "e2e_port": 8108, "closes": [38], "refs": [], "owns": ["frontend/src/portal/features/checkout/CheckoutReturn.tsx", "frontend/src/portal/features/checkout/api.ts", "frontend/src/portal/features/checkout/Checkout.tsx", "frontend/src/portal/features/checkout/StripePanel.tsx", "frontend/src/test/setup.ts#strict-mode", "frontend/src/portal/features/checkout/CheckoutReturn.test.tsx", "frontend/src/portal/features/checkout/Checkout.test.tsx"], "after": ["api-client-errors", "shared-debounce"]},
  {"wave": 2, "package": "route-table", "branch": "feature/route-table", "database": "caldart_route_table", "e2e_port": 8109, "closes": [46, 40], "refs": [], "owns": ["frontend/src/portal/routes/*", "frontend/src/portal/components/Loading.tsx", "frontend/src/portal/auth/guards.tsx", "frontend/src/test/render.tsx"], "after": ["auth-check-errors"]},
  {"wave": 3, "package": "shared-membership-types", "branch": "feature/shared-membership-types", "database": "caldart_shared_membership_types", "e2e_port": null, "closes": [33], "refs": [], "owns": ["backend/apps/members/models.py", "backend/apps/members/api/serializers.py", "backend/apps/members/api/profile_serializers.py", "backend/apps/members/api/profile_views.py", "backend/apps/members/api/admin_serializers.py", "backend/apps/members/api/admin_filters.py", "backend/apps/members/services.py", "backend/apps/accounts/api/serializers.py", "backend/apps/accounts/services.py", "backend/apps/accounts/models.py", "backend/apps/payments/api/serializers.py", "backend/apps/aircraft/api/serializers.py", "backend/apps/aircraft/services.py", "backend/apps/reminders/services.py", "backend/templates/emails/member_invitation.*", "backend/tests/test_member_invitation.py"], "after": ["membership-annotations", "reminder-scan-resilience"]},
  {"wave": 3, "package": "permission-matrix-tests", "branch": "feature/permission-matrix-tests", "database": "caldart_permission_matrix_tests", "e2e_port": null, "closes": [34], "refs": [], "owns": ["backend/tests/test_permission_matrix.py", "backend/tests/conftest.py"], "after": ["auth-csrf-and-throttle-rates"]},
  {"wave": 3, "package": "api-types", "branch": "feature/api-types", "database": "caldart_api_types", "e2e_port": null, "closes": [43], "refs": [], "owns": ["frontend/src/portal/api/types.ts", "frontend/src/portal/features/admin-members/types.ts", "frontend/src/portal/features/admin-members/index.ts", "frontend/src/portal/features/admin-members/api.ts", "frontend/src/portal/features/admin-members/fixtures.ts", "frontend/src/portal/features/admin-members/MemberDetailPage.tsx", "frontend/src/portal/features/admin-members/MemberProfileTab.tsx", "frontend/src/portal/features/admin-members/MemberMembershipsTab.tsx", "frontend/src/portal/features/admin-members/MemberPaymentsTab.tsx", "frontend/src/portal/features/admin-members/MemberDangerZone.tsx", "frontend/src/portal/features/admin-members/MemberFormFields.tsx", "frontend/src/portal/features/aircraft/api.ts", "frontend/src/portal/features/aircraft/index.ts", "frontend/src/portal/features/leader/api.ts", "frontend/src/portal/features/leader/AircraftStatusCard.tsx", "frontend/src/portal/features/leader/LeaderAircraftPage.test.tsx", "frontend/src/portal/features/admin-aircraft/AircraftRecordPage.test.tsx", "frontend/src/portal/features/admin-users/api.ts", "frontend/src/portal/features/admin-users/index.ts", "frontend/src/portal/auth/useAuth.ts", "frontend/src/portal/features/profile/api.ts"], "after": ["profile-fieldsets", "auth-check-errors", "shared-debounce", "member-delete-keeps-payments"]},
  {"wave": 3, "package": "fake-timers", "branch": "feature/fake-timers", "database": "caldart_fake_timers", "e2e_port": null, "closes": [47], "refs": [], "owns": ["frontend/src/test/setup.ts#timers", "frontend/src/portal/features/checkout/CheckoutReturn.test.tsx", "frontend/src/portal/features/aircraft/AircraftPicker.test.tsx", "frontend/src/portal/features/leader/LeaderSearchPage.test.tsx", "frontend/src/portal/features/admin-users/UsersListPage.test.tsx", "frontend/src/portal/features/admin-aircraft/AircraftRegisterPage.test.tsx", "frontend/src/portal/features/system/HealthPanel.test.tsx", "frontend/src/portal/features/system/SystemPage.test.tsx", "frontend/src/portal/features/system/BackupsPanel.test.tsx", "frontend/src/portal/features/dashboard/DashboardPage.test.tsx"], "after": ["checkout-strict-mode"]},
  {"wave": 4, "package": "account-and-member-services", "branch": "feature/account-and-member-services", "database": "caldart_account_and_member_services", "e2e_port": 8110, "closes": [16], "refs": [], "owns": ["backend/caldart/exceptions.py", "backend/apps/accounts/services.py", "backend/apps/accounts/api/serializers.py", "backend/apps/accounts/api/views.py", "backend/apps/members/services.py", "backend/apps/members/api/admin_serializers.py", "backend/apps/members/api/admin_views.py", "backend/apps/payments/services.py", "backend/apps/payments/reports.py", "backend/apps/payments/api/serializers.py", "backend/apps/payments/api/views.py", "backend/tests/test_payments_mock_provider.py", "backend/tests/test_accounts_auth.py", "backend/tests/test_account_services.py", "backend/tests/test_member_services.py", "backend/tests/test_domain_errors.py", "backend/tests/test_payment_report_query.py"], "after": ["shared-membership-types", "member-delete-keeps-payments", "server-controlled-field-tests", "auth-csrf-and-throttle-rates", "payment-provider-errors"]},
  {"wave": 4, "package": "frontend-types-docs-shared", "branch": "feature/frontend-types-docs-shared", "database": "caldart_frontend_types_docs_shared", "e2e_port": null, "closes": [], "refs": [44, 45], "owns": ["frontend/eslint.config.js", "frontend/package.json", "frontend/package-lock.json", "frontend/src/portal/components/*", "frontend/src/portal/api/*", "frontend/src/portal/auth/*", "frontend/src/portal/routes/*", "frontend/src/portal/layout/*", "frontend/src/portal/App.tsx", "frontend/src/portal/choices.ts", "frontend/src/portal/nav.ts", "frontend/src/site/*", "frontend/src/test/*"], "after": ["api-types", "fake-timers", "route-table", "vite-react-refresh"]},
  {"wave": 5, "package": "app-layering", "branch": "feature/app-layering", "database": "caldart_app_layering", "e2e_port": null, "closes": [32], "refs": [], "owns": ["backend/caldart/models.py", "backend/apps/members/models.py", "backend/apps/aircraft/models.py", "backend/apps/payments/models.py", "backend/apps/reminders/models.py", "backend/apps/accounts/models.py", "backend/apps/accounts/services.py", "backend/apps/reminders/services.py", "backend/tests/test_app_layering.py"], "after": ["account-and-member-services", "membership-annotations"]},
  {"wave": 5, "package": "frontend-types-docs-admin", "branch": "feature/frontend-types-docs-admin", "database": "caldart_frontend_types_docs_admin", "e2e_port": null, "closes": [], "refs": [44, 45], "owns": ["frontend/eslint.config.js", "frontend/src/portal/features/admin-*"], "after": ["frontend-types-docs-shared"]},
  {"wave": 6, "package": "audit-logging", "branch": "feature/audit-logging", "database": "caldart_audit_logging", "e2e_port": null, "closes": [31], "refs": [], "owns": ["backend/caldart/audit.py", "backend/caldart/settings/base.py#logging", "backend/apps/accounts/services.py", "backend/apps/accounts/api/views.py", "backend/apps/members/services.py", "backend/apps/members/api/admin_views.py", "backend/apps/sysadmin/services.py", "backend/apps/sysadmin/api/views.py", "backend/apps/sysadmin/management/commands/db_reset.py", "backend/apps/reminders/services.py", "backend/apps/reminders/api/views.py", "backend/tests/test_audit_logging.py"], "after": ["app-layering", "reminder-scan-resilience"]},
  {"wave": 6, "package": "frontend-types-docs-flows", "branch": "feature/frontend-types-docs-flows", "database": "caldart_frontend_types_docs_flows", "e2e_port": null, "closes": [], "refs": [44, 45], "owns": ["frontend/eslint.config.js", "frontend/src/portal/features/aircraft/*", "frontend/src/portal/features/auth/*", "frontend/src/portal/features/checkout/*", "frontend/src/portal/features/dashboard/*"], "after": ["frontend-types-docs-admin"]},
  {"wave": 7, "package": "backend-types-ratchet", "branch": "feature/backend-types-ratchet", "database": "caldart_backend_types_ratchet", "e2e_port": null, "closes": [], "refs": [17, 18], "owns": ["pyproject.toml#ruff", "backend/apps/cms/models.py#w505", "backend/tests/test_cms_seed_content.py#w505"], "after": ["audit-logging", "members-only-documents", "permission-matrix-tests", "make-switches", "vite-react-refresh"]},
  {"wave": 7, "package": "frontend-types-docs-finish", "branch": "feature/frontend-types-docs-finish", "database": "caldart_frontend_types_docs_finish", "e2e_port": null, "closes": [44, 45], "refs": [], "owns": ["frontend/eslint.config.js", "frontend/src/portal/features/join/*", "frontend/src/portal/features/leader/*", "frontend/src/portal/features/profile/*", "frontend/src/portal/features/system/*"], "after": ["frontend-types-docs-flows"]},
  {"wave": 8, "package": "backend-types-core", "branch": "feature/backend-types-core", "database": "caldart_backend_types_core", "e2e_port": null, "closes": [], "refs": [17, 18], "owns": ["backend/caldart/*", "backend/manage.py", "docs/conf.py", "pyproject.toml#per-file-ignores-core"], "after": ["backend-types-ratchet"]},
  {"wave": 8, "package": "backend-types-reminders", "branch": "feature/backend-types-reminders", "database": "caldart_backend_types_reminders", "e2e_port": null, "closes": [], "refs": [17, 18], "owns": ["backend/apps/reminders/*", "pyproject.toml#per-file-ignores-reminders"], "after": ["backend-types-ratchet"]},
  {"wave": 8, "package": "backend-types-sysadmin", "branch": "feature/backend-types-sysadmin", "database": "caldart_backend_types_sysadmin", "e2e_port": null, "closes": [], "refs": [17, 18], "owns": ["backend/apps/sysadmin/*", "pyproject.toml#per-file-ignores-sysadmin"], "after": ["backend-types-ratchet"]},
  {"wave": 8, "package": "backend-types-aircraft", "branch": "feature/backend-types-aircraft", "database": "caldart_backend_types_aircraft", "e2e_port": null, "closes": [], "refs": [17, 18], "owns": ["backend/apps/aircraft/*", "pyproject.toml#per-file-ignores-aircraft"], "after": ["backend-types-ratchet"]},
  {"wave": 8, "package": "backend-types-payments", "branch": "feature/backend-types-payments", "database": "caldart_backend_types_payments", "e2e_port": null, "closes": [], "refs": [17, 18], "owns": ["backend/apps/payments/*", "pyproject.toml#per-file-ignores-payments"], "after": ["backend-types-ratchet"]},
  {"wave": 8, "package": "backend-types-accounts", "branch": "feature/backend-types-accounts", "database": "caldart_backend_types_accounts", "e2e_port": null, "closes": [], "refs": [17, 18], "owns": ["backend/apps/accounts/*", "pyproject.toml#per-file-ignores-accounts"], "after": ["backend-types-ratchet"]},
  {"wave": 8, "package": "backend-types-cms", "branch": "feature/backend-types-cms", "database": "caldart_backend_types_cms", "e2e_port": null, "closes": [], "refs": [17, 18], "owns": ["backend/apps/cms/*", "pyproject.toml#per-file-ignores-cms"], "after": ["backend-types-ratchet"]},
  {"wave": 8, "package": "backend-types-members", "branch": "feature/backend-types-members", "database": "caldart_backend_types_members", "e2e_port": null, "closes": [], "refs": [17, 18], "owns": ["backend/apps/members/*", "pyproject.toml#per-file-ignores-members"], "after": ["backend-types-ratchet"]},
  {"wave": 8, "package": "backend-types-tests-accounts", "branch": "feature/backend-types-tests-accounts", "database": "caldart_backend_types_tests_accounts", "e2e_port": null, "closes": [], "refs": [17, 18], "owns": ["backend/tests/@accounts", "pyproject.toml#per-file-ignores-tests-accounts"], "after": ["backend-types-ratchet"]},
  {"wave": 8, "package": "backend-types-tests-members", "branch": "feature/backend-types-tests-members", "database": "caldart_backend_types_tests_members", "e2e_port": null, "closes": [], "refs": [17, 18], "owns": ["backend/tests/@members", "pyproject.toml#per-file-ignores-tests-members"], "after": ["backend-types-ratchet"]},
  {"wave": 8, "package": "backend-types-tests-aircraft", "branch": "feature/backend-types-tests-aircraft", "database": "caldart_backend_types_tests_aircraft", "e2e_port": null, "closes": [], "refs": [17, 18], "owns": ["backend/tests/@aircraft", "pyproject.toml#per-file-ignores-tests-aircraft"], "after": ["backend-types-ratchet"]},
  {"wave": 8, "package": "backend-types-tests-payments", "branch": "feature/backend-types-tests-payments", "database": "caldart_backend_types_tests_payments", "e2e_port": null, "closes": [], "refs": [17, 18], "owns": ["backend/tests/@payments", "pyproject.toml#per-file-ignores-tests-payments"], "after": ["backend-types-ratchet"]},
  {"wave": 8, "package": "backend-types-tests-reminders", "branch": "feature/backend-types-tests-reminders", "database": "caldart_backend_types_tests_reminders", "e2e_port": null, "closes": [], "refs": [17, 18], "owns": ["backend/tests/@reminders", "pyproject.toml#per-file-ignores-tests-reminders"], "after": ["backend-types-ratchet"]},
  {"wave": 8, "package": "backend-types-tests-cms", "branch": "feature/backend-types-tests-cms", "database": "caldart_backend_types_tests_cms", "e2e_port": null, "closes": [], "refs": [17, 18], "owns": ["backend/tests/@cms", "pyproject.toml#per-file-ignores-tests-cms"], "after": ["backend-types-ratchet"]},
  {"wave": 8, "package": "backend-types-tests-sysadmin", "branch": "feature/backend-types-tests-sysadmin", "database": "caldart_backend_types_tests_sysadmin", "e2e_port": null, "closes": [], "refs": [17, 18], "owns": ["backend/tests/@sysadmin", "pyproject.toml#per-file-ignores-tests-sysadmin"], "after": ["backend-types-ratchet"]},
  {"wave": 8, "package": "backend-types-tests-shared", "branch": "feature/backend-types-tests-shared", "database": "caldart_backend_types_tests_shared", "e2e_port": null, "closes": [], "refs": [17, 18], "owns": ["backend/tests/@shared", "pyproject.toml#per-file-ignores-tests-shared"], "after": ["backend-types-ratchet"]},
  {"wave": 9, "package": "backend-types-finish", "branch": "feature/backend-types-finish", "database": "caldart_backend_types_finish", "e2e_port": null, "closes": [17, 18], "refs": [], "owns": [".claude/rules/python.md#annotations"], "after": ["backend-types-core", "backend-types-reminders", "backend-types-sysadmin", "backend-types-aircraft", "backend-types-payments", "backend-types-accounts", "backend-types-cms", "backend-types-members", "backend-types-tests-accounts", "backend-types-tests-members", "backend-types-tests-aircraft", "backend-types-tests-payments", "backend-types-tests-reminders", "backend-types-tests-cms", "backend-types-tests-sysadmin", "backend-types-tests-shared"]}
]
```
