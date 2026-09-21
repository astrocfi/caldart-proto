# What the 2026-09-13 critiques found that is still not done

Checked against `main` at `0ad50c7` (2026-09-21). The three critiques are
`critiques/2026-09-13-backend.md`, `critiques/2026-09-13-documentation.md` and
`critiques/2026-09-13-frontend.md`. Every critical, high and medium finding became one of
the 48 issues the archived plan `plans/archive/2026-09-14-non-low-issues.md` closed
(#14-#55, #62, #64-#68; #70 and #84 closed alongside). The low-priority remainder sits in
six open issues, #56 to #61. This report is a literal re-check of each of their 121 items.

Status key: **DONE** — the specific thing the finding names is no longer true.
**PARTIAL** — part of it was fixed; the rest is named. **OPEN** — still true on `main`.

**Totals: 14 DONE, 26 PARTIAL, 81 OPEN.**

| Issue | Items | DONE | PARTIAL | OPEN |
| --- | --- | --- | --- | --- |
| #56 backend code | 16 | 3 | 3 | 10 |
| #57 backend tests | 28 | 1 | 6 | 21 |
| #58 frontend code | 18 | 2 | 1 | 15 |
| #59 frontend tests | 9 | 0 | 3 | 6 |
| #60 documentation | 40 | 8 | 11 | 21 |
| #61 tooling | 10 | 0 | 2 | 8 |

---

## Traceability of the non-low findings

`critiques/2026-09-13-backend.md` Part 1 labels every finding: 1 Critical, 3 High,
14 Medium, 16 Low. All 18 non-low findings trace to a closed issue:

| Critique finding | Issue |
| --- | --- |
| Critical: `user_admin`/`account_admin` can take over a `system_admin` account (§7) | #14 |
| High: domain logic in serializers; services raise DRF exceptions (§2) | #16 |
| High: annotation and docstring coverage (§3) | #17, #18 |
| High: auth throttles bypassable and per-process (§7) | #15 |
| Medium: app import cycles; `TimestampedModel` in a domain app (§1) | #32 |
| Medium: membership rules implemented twice (§1) | #29 |
| Medium: code copied between apps (§1) | #33 |
| Medium: almost no logging (§2) | #31 |
| Medium: provider failures are not domain exceptions (§2) | #23 |
| Medium: the suite catches none of the §5/§7 defects (§4) | #34, #35 |
| Medium: N+1 membership queries (§5) | #29 |
| Medium: Stripe timeouts and no idempotency key (§5) | #24 |
| Medium: members-only documents are downloadable (§7) | #22 |
| Medium: anonymous auth POSTs skip CSRF (§7) | #21 |
| Medium: one SMTP failure aborts the reminder scan (§7) | #25 |
| Medium: hard-deleting a member deletes payment history (§7) | #26 |
| Medium: three fail-open production defaults (§10) | #27 |
| Medium: HSTS set in two places that disagree (§10) | #28 |

The frontend and documentation critiques label no finding with a severity; their own
"top priorities" lists map to closed issues (frontend 1-10 to #20, #36, #37, #38, #40, #41,
#42, #43, #44, #45, #46, #47, #67; documentation high-priority 1-7 to #48, #49, #50, #51,
#52, #30, #53, #54). Two items those lists call high-priority were nevertheless triaged into
the low-priority issues; see "Findings triaged below their stated priority" at the end.

---

## #56 Low-priority backend code findings (16 items: 3 DONE, 3 PARTIAL, 10 OPEN)

| Item | Status | Evidence |
| --- | --- | --- |
| Bound `contribution_cents` so an oversized value answers 400 | OPEN | `backend/apps/payments/api/serializers.py:46` is still `IntegerField(required=False, min_value=0, default=0)` with no `max_value`, feeding 32-bit `PositiveIntegerField`s at `backend/apps/payments/models.py:80-82` |
| Clamp members `?expiring_within=` | DONE | `backend/apps/members/api/admin_filters.py:172-188` clamps to `MAX_EXPIRING_WINDOW_DAYS`; fixed by issue #65 / PR #97 |
| 400 for impossible dates in payment-report filters | DONE | `ReportDateField` at `backend/apps/payments/api/serializers.py:140-166`; covered by `backend/tests/test_payment_report_query.py:27` |
| Stop login revealing a deactivated account on a wrong password | OPEN | `backend/apps/accounts/api/views.py:112-121` still looks the address up with `is_active=False` whenever `authenticate()` fails, without checking the password |
| Escape PDF title and subtitle | OPEN | `backend/caldart/reports.py:231-233` passes `title`/`subtitle` to `Paragraph` unescaped while cells go through `_as_cells` at `:161-166`; `filter_summary` at `:266-269` feeds raw query values in |
| `PGPASSWORD` and URL-quoted credentials for `pg_dump`/`psql` | OPEN | `backend/apps/sysadmin/services.py:70-77` still builds an unquoted `postgres://user:password@host/...` URL and passes it as `--dbname`; no `PGPASSWORD`, no `urllib.parse.quote` |
| Stop `PUT /me/profile` storing a medical class without its expiry | DONE | `backend/apps/members/api/profile_serializers.py:203-227` requires `medical_expiration` whenever `medical_type != MedicalType.NONE` |
| CSV formula-injection policy | OPEN | `csv_rows` at `backend/caldart/reports.py:93-98` writes values verbatim; no test in `backend/tests/` mentions formula injection |
| Delete dead backend code | PARTIAL | `IsDartLeader`, `IsWebsiteAdmin` and `IsSelfOrHasAnyRole` were removed by issue #67 / PR #106; `CheckoutResponseSerializer` (`backend/apps/payments/api/serializers.py:50`), `Payment.amount_dollars` (`backend/apps/payments/models.py:117`) and `MemberProfile.volunteer_interests` (`backend/apps/members/models.py:170`) are all still defined and never referenced |
| Build `available_providers()` from the provider registry | OPEN | `backend/apps/payments/providers/base.py:106-124` still hardcodes each provider's configuration test instead of asking `_REGISTRY` |
| Replace defensive `getattr` on attributes that always exist | PARTIAL | The `cms` and `throttling` cases are fixed; three remain: `backend/apps/payments/views.py:28` and `backend/apps/payments/providers/paypal.py:432` (both read settings always defined at `backend/caldart/settings/base.py:277,282`) and `backend/apps/accounts/permissions.py:31` (`getattr(user, "is_superuser", False)`) |
| Move `seed_content` page copy into a data file | OPEN | `backend/apps/cms/management/commands/seed_content.py` has grown from 835 to 935 lines with the copy still inline |
| Regenerate the cms schema migrations as one | OPEN | `backend/apps/cms/migrations/` still holds `0001_initial.py`, `0002_site_root.py`, `0003_page_types.py`, `0004_website_admin_permissions.py`; schema is still split across `0001` and `0003` |
| Lock or relocate the PayPal token cache | OPEN | `backend/apps/payments/providers/paypal.py:113-174` is still a bare module-level dict mutated with no lock and no use of Django's cache |
| Stream backups and restores | OPEN | `backend/apps/sysadmin/services.py:103` still uses `subprocess.run(..., capture_output=True)` and writes all of `result.stdout` at `:172`; restore still does `handle.read()` in full |
| Tracking: remove non-ASCII characters from `.py` files | PARTIAL | Down from 280 lines in 69 files to 138 lines in 30 non-test, non-migration files; heaviest are `backend/apps/cms/management/commands/seed_content.py` (45), `backend/apps/payments/api/views.py` (13), `backend/apps/accounts/api/views.py` (11) |

### Remaining work — backend code

- Add a `max_value` to `contribution_cents` in `backend/apps/payments/api/serializers.py:46` so an oversized contribution answers 400 instead of raising `DataError` (trivial).
- Check the password before disclosing a deactivated account in `backend/apps/accounts/api/views.py:112-121` (trivial).
- Escape the PDF title and subtitle in `backend/caldart/reports.py:231-233` the way `_as_cells` escapes cells, so a `<` in a filter cannot crash an export (trivial).
- Pass the database password to `pg_dump`/`psql` through `PGPASSWORD` and URL-quote the user and password in `backend/apps/sysadmin/services.py:70-77` (small).
- Decide a CSV formula-injection policy for the exports in `backend/caldart/reports.py:93-98` and add a test that pins it (small).
- Delete the three remaining dead symbols: `CheckoutResponseSerializer`, `Payment.amount_dollars`, `MemberProfile.volunteer_interests` (trivial; the last needs a model migration).
- Build `available_providers()` from `_REGISTRY` with an `is_configured()` classmethod on `Provider` instead of hardcoding each provider's test (small).
- Replace the last three defensive `getattr` calls with direct attribute access (`payments/views.py:28`, `payments/providers/paypal.py:432`, `accounts/permissions.py:31`) (trivial).
- Move the inline page copy out of the 935-line `seed_content` command into a data file beside it (small).
- Regenerate the cms schema as a single migration ahead of the two data migrations (small).
- Guard the PayPal module-level token cache with a lock or move it into Django's cache, and state the thread-safety in its docstring (small).
- Stream `pg_dump` output into gzip and the reverse on restore, instead of buffering the whole dump in memory (medium).
- Continue the non-ASCII sweep of `.py` files: 138 lines across 30 modules remain, concentrated in `seed_content.py` (45), `payments/api/views.py` (13) and `accounts/api/views.py` (11) (small, ongoing).

---

## #57 Low-priority backend test-suite findings (28 items: 1 DONE, 6 PARTIAL, 21 OPEN)

| Item | Status | Evidence |
| --- | --- | --- |
| Autouse `respx_mock` to block live HTTP in payment tests | OPEN | No `respx_mock` fixture anywhere; `test_capture_of_an_order_id_we_did_not_issue_is_refused` (`backend/tests/test_payments_paypal.py:349`) still has no `@respx.mock`, so a regressed guard would make a live call |
| Assert error-message content in `pytest.raises` and 400 responses | PARTIAL | Of 66 `pytest.raises`, about 6 still assert nothing (`test_payments_paypal.py:139,146`, `test_payments_mock_provider.py:197,233`, `test_accounts_auth.py:155`, `test_aircraft_models.py:48`); many 400s stay body-blind, e.g. `test_accounts_auth.py:271`, `test_payments_paypal.py:534`, `test_payments_api.py:187`, and `test_accounts_auth.py:98` still checks only `"email" in response.json()` |
| Assert PDF content via a stream decoder; fix overclaiming names | OPEN | No ASCII85/zlib decoder exists in `backend/tests/`; `test_pdf_states_the_filters_it_was_run_with` (`test_aircraft_exports.py:274`) and `test_pdf_paginates_100_rows_with_a_repeated_header` (`test_reports.py:86`) still check only page and byte counts |
| Token-expiry and newest-first backup tests check their names | PARTIAL | `test_list_backups_newest_first` (`test_sysadmin.py:38`) is fixed with `os.utime` and an exact order assertion; `test_an_expired_token_is_fetched_again` (`test_payments_paypal.py:123`) still never lets a token expire, forcing a refetch with `reset_token_cache()` |
| Exact values instead of truthiness, `>=` and superset assertions | OPEN | `test_sysadmin.py:91,99`, `test_sysadmin_api.py:174,195`, `test_payments_reports.py:109`, `test_users_admin_api.py:216` (`>= 9`), `test_members_reports.py:241` (`>= 33`), `test_auth_api.py:132`, `test_members_admin.py:481` (`set(...) >=`), plus status-set asserts at `test_cms_permissions.py:174`, `test_roles_permissions.py:216`, `test_auth_api.py:79` |
| Test invalid inputs and boundaries | OPEN | No pagination default (25) or cap (200/201) boundary test, no `expiring_within` overflow test, no non-ASCII test data anywhere in `backend/tests/`, no `max_length` boundary tests |
| Payment and membership state transitions and duplicate deliveries | PARTIAL | Duplicate delivery is covered (`test_webhook_after_confirm_is_a_no_op`, `test_payments_stripe.py:614`; `test_capturing_twice_grants_one_term`, `test_payments_paypal.py:360`); the failed-to-succeeded transition and cancelled/expired-to-active via `PATCH /admin/memberships/{id}` are untested (only active-to-cancelled, `test_members_admin.py:861`) |
| Concurrent webhook/confirm race in `mark_succeeded` | OPEN | No threading test exercises `mark_succeeded`'s `select_for_update`; only the unrelated reminders race was added (`test_reminders_resilience.py:185`) |
| `caplog` assertions for payment-provider log lines | DONE | `backend/tests/test_payments_provider_errors.py` sets `caplog.set_level(...)` and asserts message content for Stripe (~208-265) and PayPal (~391-472) |
| Cover uncovered behavior branches | PARTIAL | Provider error branches are now well covered (21 tests in `test_payments_provider_errors.py`); `cms/seed.py`'s site-root repair path still has no dedicated test, and `drop_schema`'s SQL is still always mocked out (`test_sysadmin_commands.py:53`) rather than run through a recording cursor |
| Whole-output assertions for emails and CSVs (golden files, 11 columns) | OPEN | No `backend/tests/golden/`; `read_csv` at `test_payments_reports.py:277-279` still splits on commas rather than using `csv.reader`, and `test_export_returns_a_csv_download` (`:280`) checks only `rows[0][:4]`, never `wallet`/`provider_ref` |
| Stop `conftest.py` writing the Vite manifest into `frontend/dist` | OPEN | `backend/tests/conftest.py:99-121` still writes and deletes `frontend/dist/.vite/manifest.json` in the repo tree |
| Run the frontend-bundle tests in CI behind a marker | OPEN | `test_shell_views.py:73,125` still call `pytest.skip(...)` imperatively, and the backend job in `.github/workflows/ci.yml` still never builds the frontend |
| Register a `slow` marker and cut seed-test runtime | OPEN | `[tool.pytest.ini_options]` in `pyproject.toml` has no `markers` table and no `slow` marker; the 24 seed tests in `test_seed.py` and `test_cms_seed_content.py` still run unmarked in the default set |
| Coverage configuration that measures production code only | OPEN | No `[tool.coverage]` section and no `pytest-cov` dependency in `pyproject.toml` |
| Fix the `STATIC_ROOT` warning at source; drop the ignore | OPEN | `pyproject.toml:49-55` still carries `"ignore:No directory at:UserWarning"`; `STATIC_ROOT` is unchanged at `backend/caldart/settings/base.py:155` with no test-settings override |
| Freeze "now" in date-relative API tests | OPEN | The `today` fixture (`backend/tests/conftest.py:321`) still calls `timezone.localdate()` unfrozen, and there is no `freezegun.configure(extend_ignore_list=...)` anywhere |
| Make tests order-independent | OPEN | `seed_demo.py` still calls the global `Faker.seed(seed)`; no `pytest-randomly`; `test_ordering_by_name_is_the_default` (`test_members_admin.py:419`) still compares against a Faker-named `account_admin` (`conftest.py:208`) |
| Whitespace-tolerant deploy-file assertions | OPEN | `test_apache_proxies_to_gunicorn_and_sets_the_scheme_header` (`test_sysadmin_settings.py:286`) still asserts the exact string `"ProxyPass        / http://127.0.0.1:8001/"` |
| Parametrize role matrices from one `ROLES` table | PARTIAL | Some were converted (e.g. `test_reminders_api.py:53`); raw loops over `all_role_users.items()` remain at `test_aircraft_api.py:353`, `test_leader_api.py:84`, `test_payments_api.py:234,449`, `test_profile_api.py:61`, and `ROLE_MATRIX` is still duplicated verbatim in `test_users_admin_api.py:46` and `test_sysadmin_api.py:70` |
| Consolidate duplicated fixtures and helpers | OPEN (worse) | `backup_dir` is now defined 4 times (`test_audit_logging.py:100`, `test_sysadmin_api.py:44`, `test_sysadmin.py:26`, `test_sysadmin_commands.py:28`), `admin_client` 5 times, `register` twice; 3 different CSV readers and 3 different PDF page counters, none moved into `conftest.py`/`factories.py` |
| Delete unused fixtures and dead branches; fix `annual_plan` | PARTIAL | `anonymous_user` is gone and `annual_plan` (`conftest.py:249`) is annotated `-> MembershipPlan`; still unused are `_unused` (`test_seed.py:24`), `page_map` (`test_cms_seed_content.py:31`) and conftest's `membership_factory`/`reminder_log_factory`/`aircraft_factory` (`:285,291,297`); the `make_home_page`/`make_site_settings` dead branches are unchanged |
| Remove redundant tests | OPEN | Every example the critique named still exists: both roles-endpoint tests, both apple-pay duplicates, `profile_complete` asserted in 3+ modules, `test_site_config_is_public` (`test_auth_api.py:127`), the sysadmin service/API pairs, `test_create_checkout_ignores_a_client_amount` (`test_payments_mock_provider.py:33`), `test_stripe_provider_is_registered` (`test_payments_stripe.py:716`) |
| Split `test_integration.py`; drop history and code-shape tests | OPEN | Still 243 lines mixing profile completeness, db_reset, reminders, redirects and export subtitles; change-history docstrings at `:61,119`, test name `test_db_reset_seed_no_longer_swallows_a_failure` at `:140`, code-shape tests at `:118,239` |
| Remove or justify the autouse `_roles` fixture; add `django_db` marks | OPEN (worse) | `_roles` (`conftest.py:130-135`) is unchanged and still autouse with a one-line docstring; 8 modules now lack `pytestmark = pytest.mark.django_db` (up from the 2 the critique named), including `test_members_delete_payments.py` and `test_members_request_actor.py` |
| Tracking: hoist imports out of test bodies | OPEN | About 55 indented import lines remain (12 are legitimate `if TYPE_CHECKING:` blocks); genuine in-body imports persist at `test_integration.py` (9), `test_roles_permissions.py` (7), `test_seed.py` (5), `conftest.py:133,323` |
| Tracking: one condition per assert | OPEN | About 10 `assert X and Y` remain in the files the critique named: `test_cms_seed_content.py:74,88`, `test_aircraft_exports.py:173`, `test_cms_pages.py:177,208,209,210`, `test_seed.py:57`, `test_sysadmin_commands.py:89`, `test_roles_permissions.py:155`; the tautology at `test_leader_api.py:315` is unchanged |
| Consistent test naming and style | OPEN | Terse names unchanged (`test_remove_role`, `test_ordering`, `test_status_filter`); `test_str_and_display_name` duplicated in `test_aircraft_models.py:95` and `test_roles_permissions.py:123`; `.data` (12 files) vs `.json()` (17 files) still mixed; `override_settings` still used in `test_accounts_auth.py` alongside the `settings` fixture; filename checks mix `==` (`test_members_reports.py:161`) and `in` (`test_aircraft_exports.py:139`) |

### Remaining work — backend test suite

- Add an autouse `respx` guard so no payment test can make a live HTTP call, starting with `test_payments_paypal.py:349` which has no `@respx.mock` (small).
- Assert the exception message in the ~6 remaining bare `pytest.raises` blocks and the response body on the 400-only tests named above (small).
- Write a stdlib ASCII85/zlib PDF stream decoder in `conftest.py` and make the two overclaiming PDF tests assert the subtitle and row content they promise (medium).
- Make `test_an_expired_token_is_fetched_again` (`test_payments_paypal.py:123`) actually expire a PayPal token rather than calling `reset_token_cache()` (small).
- Replace the dozen truthiness, `>=` and superset assertions listed above with exact values and exact key sets (small).
- Add boundary and invalid-input tests: pagination default 25 and cap 200, `expiring_within` overflow, `max_length` limits, and non-ASCII names anywhere in the fixtures (medium).
- Test the failed-to-succeeded payment transition and the cancelled/expired-to-active membership transition through `PATCH /admin/memberships/{id}` (small).
- Add a threaded test for the webhook/confirm race that `mark_succeeded`'s `select_for_update` is supposed to settle (medium).
- Cover `cms/seed.py`'s site-root repair path and run `drop_schema`'s SQL through a recording cursor instead of mocking it out (small).
- Assert whole email bodies and whole CSV exports against golden files, including all 11 payment columns, and switch `read_csv` to `csv.reader` (medium).
- Stop `backend/tests/conftest.py:99-121` writing `frontend/dist/.vite/manifest.json` into the repo tree; build the fixture in `tmp_path` instead (small).
- Replace the imperative `pytest.skip` in `test_shell_views.py:73,125` with a registered `needs_frontend_build` marker, and have CI build the frontend before the backend job (small).
- Register a `slow` marker, apply it to the 24 seed tests, and exclude it from the default `addopts` run (small).
- Add `[tool.coverage]` configuration to `pyproject.toml` that measures production code only (excluding `backend/tests/` and migrations) (trivial).
- Set `STATIC_ROOT` in the test settings so WhiteNoise stops warning, then delete the `"ignore:No directory at:UserWarning"` filter (trivial).
- Freeze the clock in the date-relative API tests by making the `today` fixture (`conftest.py:321`) authoritative, and keep freezegun out of pytest's own timing with `extend_ignore_list` (small).
- Make the suite order-independent: drop the global `Faker.seed` from `seed_demo.py`, give the ordering test fixed names, and consider `pytest-randomly` to prove it (small).
- Make the Apache deploy-file assertion at `test_sysadmin_settings.py:286` whitespace-tolerant (trivial).
- Move `ROLE_MATRIX` into `conftest.py` and convert the five remaining `all_role_users` loops into parametrized cases with readable ids (small).
- Consolidate the duplicated `backup_dir` (4 copies), `admin_client` (5 copies), `register` (2 copies), three CSV readers and three PDF page counters into `conftest.py`/`factories.py` (medium).
- Delete the unused `_unused`, `page_map`, `membership_factory`, `reminder_log_factory` and `aircraft_factory` fixtures and the dead `make_home_page`/`make_site_settings` branches (small).
- Delete the redundant tests the critique enumerated (duplicate roles-endpoint, apple-pay, `profile_complete`, `test_site_config_is_public`, the sysadmin service/API pairs) (small).
- Split the 243-line `test_integration.py` into feature modules and drop its change-history docstrings and two code-shape tests (medium).
- Justify or remove the autouse `_roles` fixture, and add the missing `pytestmark = pytest.mark.django_db` to the 8 modules that rely on it implicitly (small).
- Hoist the genuine in-body imports out of test functions in `test_integration.py` (9), `test_roles_permissions.py` (7), `test_seed.py` (5) and `conftest.py` (small).
- Split the ~10 remaining `assert X and Y` into one condition per assert and fix the tautology at `test_leader_api.py:315` (small).
- Sweep test naming and style: descriptive names, one of `.data`/`.json()`, the `settings` fixture instead of `override_settings`, and one filename-check form (medium).

---

## #58 Low-priority frontend code findings (18 items: 2 DONE, 1 PARTIAL, 15 OPEN)

| Item | Status | Evidence |
| --- | --- | --- |
| Fix the no-op `['membership']` invalidation | OPEN | `frontend/src/portal/features/checkout/Checkout.tsx:80` still invalidates `['membership']`, which no query uses; the real key is `['me','membership']` (`features/profile/api.ts:26`), and both invalidations sit side by side |
| Keep the previous page as placeholder data | OPEN | Neither `useMembers` (`features/admin-members/api.ts:50-59`) nor `useAircraftList` (`features/aircraft/api.ts:57-67`) sets `placeholderData`; `admin-users/api.ts:52` and `admin-payments/api.ts:78` do |
| Stop the Stripe panel creating duplicate PaymentIntents | DONE | `features/checkout/StripePanel.tsx:110-143` now uses an `AbortController`, checks `signal.aborted`, and aborts on cleanup |
| PayPal `createOrder` server message and `onCancel` | OPEN | `PayPalPanel.tsx:45-56` still has no try/catch, so an `ApiError` falls through to the generic "PayPal could not be reached" at `:78`; no `onCancel` prop in the file |
| Account admins get a reminder-log view, or correct the guide | OPEN | `frontend/src/portal/routes/system.tsx:8` still gates `/system` to `system_admin` only, while `docs/developer/reminders.rst:300-303` still says the API is open to `account_admin` "or in the reminders panel of `/portal/system`" |
| Restrict absolute URLs in the API client to the same origin | OPEN | `buildUrl` at `frontend/src/portal/api/client.ts:148` passes through anything starting with `http`, and `send()` at `:217-220` attaches `X-CSRFToken` with no origin check |
| Sign out only on an explicit POST | OPEN | `features/auth/LogoutPage.tsx:15-19` still fires the logout mutation from a mount effect, so merely loading `/portal/logout` ends the session |
| Remove `server.cors: true` | OPEN | `frontend/vite.config.ts:37` |
| Delete dead frontend code | DONE | `routes/placeholder.tsx` and the duplicate `features/join/useRegister.ts` are gone; `useAuth.ts:110` is the sole implementation, used at `features/join/AccountStep.tsx:7,20` (issues #66, #67) |
| Move cross-feature queries out of `features/profile/api.ts` | OPEN | `useDarts`, `usePlans` and `useSiteConfig` still live at `features/profile/api.ts:53-78` and are imported by dashboard, join and admin-members |
| Drop the component barrel and re-export chains | OPEN | `frontend/src/portal/components/index.ts:1` still instructs "Import from here, not from the files", yet only 12 imports use it against 34+ direct file imports |
| One cross-feature import style; fix the vite alias comment | PARTIAL | The alias comment is corrected (`frontend/vite.config.ts:16-20`); the style is still mixed — 7 files use `@/` (e.g. `features/join/PayStep.tsx`, `features/profile/AircraftEditor.tsx`) while others use relative paths (`features/admin-members/api.ts:11`, `features/leader/api.ts:5`) |
| Rename event handlers to `handle*` | OPEN | All three cited cases remain — `onKeyDown` (`Checkout.tsx:164`), `submit` (`StripePanel.tsx:199`), `pay` (`MockPanel.tsx:20`) — plus a dozen more (`save`, `destroy`, `submitNew`, `submitGrant`, `changeFilters`, `startAdding`, `back`, `takeBackup`) |
| Replace non-null assertions with explicit narrowing | OPEN | Exactly the three cited remain: `features/auth/form.tsx:29`, `features/leader/AircraftStatusCard.tsx:32`, `features/checkout/Checkout.tsx:162`; no others exist in non-test `src/` |
| Un-export StripePanel internals | OPEN | `stripeFor`, `appearanceFromTokens`, `returnUrl` and `StripeForm` are still exported at `StripePanel.tsx:30,45,78,185` with no importers outside the file |
| Discriminated and literal unions in `api/types.ts` | OPEN | `CheckoutResponse.client` (`api/types.ts:379-386`) is still `{ client_secret?, order_id? }` rather than discriminated on `provider`; `Health.db` (`:460`) and `SiteConfig.theme` (`:488`) are still plain `string` |
| Remove the exhaustive-deps suppression in StripePanel | OPEN | `// eslint-disable-next-line react-hooks/exhaustive-deps` at `StripePanel.tsx:142` |
| Import only Latin font subsets | OPEN | `frontend/src/styles/index.css:13-19` imports the all-subset `@fontsource/ibm-plex-sans/400.css` etc. rather than the `latin-*.css` variants |

### Remaining work — frontend code

- Fix or delete the no-op `['membership']` invalidation at `features/checkout/Checkout.tsx:80` so one post-payment refresh remains (trivial).
- Add `placeholderData: keepPreviousData` to `useMembers` and `useAircraftList` so their tables do not blank out between pages (trivial).
- Wrap PayPal's `createOrder` (`PayPalPanel.tsx:45-56`) in try/catch to surface the server's message, and add an `onCancel` handler (small).
- Either give account admins a portal view of the reminder log or correct `docs/developer/reminders.rst:300-303`, which currently points them at a system-admin-only panel (small).
- Restrict `buildUrl` (`api/client.ts:148`) to same-origin absolute URLs so `X-CSRFToken` can never be sent cross-origin (small).
- Make `/portal/logout` require an explicit POST instead of signing out from a mount effect (`features/auth/LogoutPage.tsx:15-19`) (small).
- Remove `server.cors: true` from `frontend/vite.config.ts:37` (trivial).
- Move `useDarts`, `usePlans` and `useSiteConfig` out of `features/profile/api.ts:53-78` into a shared queries module (small).
- Decide on the component barrel: either make every import go through `components/index.ts` or delete it and its re-export chain (small).
- Settle on one cross-feature import style — `@/` alias or relative — and apply it across the 7 alias files and the rest (small).
- Rename the ~15 local event handlers to `handle*` (`Checkout.tsx:164`, `StripePanel.tsx:199`, `MockPanel.tsx:20`, and the `save`/`destroy`/`submitNew`/`submitGrant`/`changeFilters`/`startAdding`/`back`/`takeBackup` group) (small).
- Replace the three non-null assertions with explicit narrowing (`auth/form.tsx:29`, `leader/AircraftStatusCard.tsx:32`, `checkout/Checkout.tsx:162`) (trivial).
- Un-export `stripeFor`, `appearanceFromTokens`, `returnUrl` and `StripeForm` from `StripePanel.tsx`, which nothing outside the file imports (trivial).
- Make `CheckoutResponse` a union discriminated on `provider`, and give `Health.db` and `SiteConfig.theme` literal unions in `api/types.ts` (small).
- Restructure the StripePanel effect so the `react-hooks/exhaustive-deps` suppression at `StripePanel.tsx:142` can be removed (small).
- Switch `frontend/src/styles/index.css:13-19` to the `latin-*.css` fontsource subsets so the bundle stops shipping every script (trivial).

---

## #59 Low-priority frontend test-suite findings (9 items: 0 DONE, 3 PARTIAL, 6 OPEN)

| Item | Status | Evidence |
| --- | --- | --- |
| Assert message text and exact calls instead of existence | PARTIAL | `CheckoutReturn.test.tsx:73` now asserts `calls.count` exactly, but `:97` still calls bare `expect(onSuccess).toHaveBeenCalled()` and `features/profile/form.test.ts:95,100,108,116` still use `.toBeDefined()`/`.toBeUndefined()` |
| Cover checkout error paths | PARTIAL | Stripe confirm (`Checkout.test.tsx:344`), PayPal capture (`:398`) and the CheckoutReturn timeout (`CheckoutReturn.test.tsx:76`) are covered; a `fetchPayment` failure (the catch at `CheckoutReturn.tsx:86-91`) has no test — every `servePayment` sequence returns success |
| Test PortalLayout, the query retry policy, Toast and login cache clearing | OPEN | No `PortalLayout.test.tsx`, `App.test.tsx` or `Toast.test.tsx` exists; `LoginPage.test.tsx` has no cache assertion (only `LogoutPage.test.tsx:41-47` checks cache clearing) |
| Table-drive repeated cases; boundary and accented inputs | PARTIAL | `it.each` now appears in five files (`routes/index.test.tsx`, `MemberStatusCard.test.tsx`, `ProfileFieldsets.test.tsx`, `insurance.test.ts`, `MemberCreatePage.test.tsx`); the named candidates are unchanged — `guards.test.tsx` role cases are separate `it`s, `client.test.ts:147-174` is still a manual `for`/`switch`, `profile/form.test.ts:91-96,114-118` has no new boundary values, `DataTable.test.tsx` has no accented-name case |
| Harden the vitest config | OPEN | The `test` block at `frontend/vite.config.ts:40-46` sets only `environment`, `globals`, `setupFiles`, `css`, `include` — no `allowOnly`, `restoreMocks`/`clearMocks` or `sequence.shuffle`; `src/test/setup.ts` has no console guard |
| Vitest coverage provider and make target | OPEN | No `@vitest/coverage-*` in `frontend/package.json`, no coverage npm script, no coverage target in the `Makefile` |
| Move test fixtures into `src/test`; add an `@/test` alias | OPEN | `src/portal/features/profile/fixtures.ts` and `src/portal/features/admin-members/fixtures.ts` are still in the production tree, and every test imports the helpers by relative path (`../../../test/render`) |
| Make e2e specs robust | OPEN | `e2e/website-admin.spec.ts:25,75` still call `waitForLoadState('networkidle')`; `e2e/join-and-pay.spec.ts:18` still branches on an unawaited `isVisible()`; `playwright.config.ts` has no `failOnFlakyTests`; CSS-class locators remain (`.leader-card` at `leader-check.spec.ts:25,51,64`, `.dashboard__status .chip`, `.period-table`) |
| Strengthen e2e assertions | OPEN | `e2e/payment-reports.spec.ts:28-39,56` still uses `toBeGreaterThan(0)` rather than seed-derived counts; `leader-check.spec.ts:66` asserts `not.toHaveText('Insured')` instead of the lapsed-insurance label; the tail-number test at `:72-80` asserts nothing about the aircraft card's insurance state |

### Remaining work — frontend test suite

- Assert the payload at `CheckoutReturn.test.tsx:97` and the actual message text in `features/profile/form.test.ts:95,100,108,116` instead of mere existence (small).
- Add a test for a failing `fetchPayment` so the catch at `CheckoutReturn.tsx:86-91` is exercised (small).
- Add tests for `PortalLayout`, the query client's retry policy, the `Toast` component, and cache clearing on login (medium).
- Convert `guards.test.tsx`'s role cases and `client.test.ts:147-174`'s verb loop to `it.each`, and add boundary (negative, decimal, six-digit ZIP) and accented-name cases (small).
- Harden the vitest config in `frontend/vite.config.ts:40-46` with `allowOnly: false`, `restoreMocks`, `sequence.shuffle`, and add a console.error/warn guard to `src/test/setup.ts` (trivial).
- Install a vitest coverage provider, add a coverage npm script, and add a `make coverage-frontend` target (small).
- Move `features/profile/fixtures.ts` and `features/admin-members/fixtures.ts` into `src/test/` and add an `@/test` alias so tests stop importing by `../../../test/render` (small).
- Make the e2e specs robust: replace `.leader-card`/`.period-table`/`.chip` CSS locators with role locators, drop the two `networkidle` waits, await the `isVisible()` branch in `join-and-pay.spec.ts:18`, and set `failOnFlakyTests` in `playwright.config.ts` (medium).
- Strengthen the e2e assertions: seed-derived exact row counts in `payment-reports.spec.ts`, the lapsed-insurance label in `leader-check.spec.ts:66`, and the aircraft card's insurance state in the tail-number test (small).

---

## #60 Low-priority documentation findings (40 items: 8 DONE, 11 PARTIAL, 21 OPEN)

Note: `PLAN.rst` was archived to `plans/archive/2026-09-04-prototype-master-plan.rst` and is
no longer cited by any page, so the items that asked only for PLAN edits are settled by that
archival; where a PLAN item also named live pages, the live pages are judged below.

| Item | Status | Evidence |
| --- | --- | --- |
| setup.rst make-target table and README `make seed` comment | PARTIAL | The `setup.rst` table now includes `help`, `createdb`, `check-*`, `audit-*` and `e2e`; `README.rst:25` still describes `make seed` as "demo accounts, members, aircraft, payments", omitting `seed_content` (`Makefile:107`) |
| CI descriptions in testing.rst and setup.rst | DONE | `docs/developer/testing.rst:5-6,498-499` names the real trigger and all five jobs; `setup.rst:359`'s "five commands" matches the project's own pre-PR policy |
| Reconcile backup and health docs with the code | PARTIAL | The `pg_dump` container-first default (`backup-restore.rst:30-33`) and all six health facts (`:249-268`) are correct; `docs/user/system-administrator-guide.rst:208` still claims only `caldart-….sql.gz` names are downloadable, contradicting `--name` at `backup-restore.rst:20` |
| Complete the operator-command docs | PARTIAL | `db_reset`, the `make backup`/`restore`/`reminders` wrappers and the strict `YES=`/`DRY_RUN=` semantics are documented; `health --json`'s always-zero exit status and a sample JSON body are still missing, and `system-administrator-guide.rst:169,245-246` still shows bare `manage.py health --json` with no link to the full invocation |
| Correct role descriptions in the user guide | OPEN | `account-administrator-guide.rst:10` still says "Everything lives under Members" while its own `:178` covers Payments and `nav.ts:45-47` adds Aircraft; `getting-started.rst:74-75` omits leader checks and deletion from the account_admin row; `:167-168` omits "Change password"; `system-administrator-guide.rst:25-26` still frames superuser as conditional though `services.py:140` always sets it |
| Quote UI labels exactly | OPEN | `faq.rst:83` and `demo-walkthrough.rst:122` still say the tab is "Mock" (the UI says "Test payment"); `faq.rst:182` says "Forgot password" vs the UI's "Forgot your password?" (`LoginPage.tsx:82`); `demo-walkthrough.rst:143` quotes a message the code never shows; `website-administrator-guide.rst:264,269` say "Organization name"/"Facebook / X URL" vs Wagtail's generated "Org name"/"Facebook url"/"Twitter url" |
| demo-walkthrough per-checkout port and /django-admin claims | OPEN | `docs/demo-walkthrough.rst:36-37` still claims each checkout uses its own port though `make run` always binds :8000 (`Makefile:122`); `:363-364` still says website_admin cannot reach `/django-admin/` though `services.py:141` sets `is_staff=True` |
| User-guide overview with a member-lifecycle diagram | OPEN | No overview page under `docs/user/` and no lifecycle diagram anywhere; the only diagram is the ERD in `data-model.rst` |
| Tidy the user-guide landing page and chapter placement | OPEN | `docs/user/index.rst:5-11,38-39` still carries two extra prose paragraphs; `payments.rst` still sits under "For members" while `:115-118` is account_admin-only material |
| Missing user-guide cross-links and `:ref:` labels | OPEN | `member-guide.rst` has zero `:doc:` links; `faq.rst` links 5 of 19 answers; `system-administrator-guide.rst:52` refers to "the deployment guide's troubleshooting section" in bare prose and `deployment.rst:540` has no label |
| Subsystem chapters end with an API link | OPEN | `payments-setup.rst`, `reminders.rst`, `backup-restore.rst`, `theming.rst`, `cms.rst` and `reports.rst` all end with troubleshooting or coverage prose; none links its API page |
| Tracking: absolute cross-directory `:doc:` targets | OPEN | 18 relative `../` cross-directory targets remain (e.g. `system-administrator-guide.rst:99,160-164,205,216`, `user-administrator.rst:251`) |
| Tracking: American spelling in docs and code | DONE | `Makefile:194-195` runs `codespell` over `README.rst CLAUDE.md docs backend frontend/src` as part of `make lint` (issues #62, #70); spot checks find no British spellings left |
| Remove time-anchored wording | PARTIAL | The Redirects and "currently read by nothing" cases are gone; `README.rst:148` ("Not yet licensed"), `faq.rst:110` ("yet"), `roadmap.rst:45,76,81,95` ("today", "currently ignore"), `deployment.rst:537` ("not backwards compatible") and `docs/conf.py:121` ("yet") remain |
| Expand DART on first use | OPEN | README.rst, `docs/index.rst` and `docs/user/` never expand it; only `data-model.rst:436` says "A local Disaster Airlift Response Team" |
| docs/conf.py: nitpicky, master_doc, annotated setup() | PARTIAL | `setup(app: Sphinx) -> None` and `_NoGraphviz.run` are typed and documented; `docs/conf.py:111` is still `nitpicky = False` and `:88-89` still sets both `master_doc` and `root_doc` |
| Remove change history from docstrings and JSDoc | PARTIAL | `accounts/throttling.py` and `members/models.py:188-207` are clean; `backend/tests/test_integration.py:61,119` still say "used to insist"/"used to carry its own copy", the test name at `:140` references history, and `frontend/src/portal/features/profile/AircraftEditor.tsx:4-7` still says "the only edit form used to be" |
| Restructure the README to doc-readme | OPEN | Sections are still Quick start / Demo accounts / Everyday commands / End-to-end tests / Layout / License, with no Features, Documentation or Contributing; the title is still "CalDART — website and member management system"; the e2e section is still ~40 lines with no link to `testing.rst` |
| Developer-guide landing page: audience and conventions | PARTIAL | A conventions pointer exists at `architecture.rst:562`; `docs/developer/index.rst:5-11` still opens by describing content rather than naming the reader or contrasting with the user guide |
| PLAN §3 repository layout | DONE | PLAN.rst is archived; the layout now lives at `architecture.rst:92-149` and includes `.claude/`, `.github/`, per-app `seed.py`, `caldart/{reports,pagination,exceptions,views}.py` and `frontend/src/test/` |
| Document the E2E and CI environment variables | OPEN | `E2E_PORT`, `E2E_DB`, `E2E_DATABASE_URL`, `E2E_LOG`, `SKIP_CREATEDB`, `E2E_BASE_URL` and `CI` appear only in `Makefile:30-33,158-179` and `frontend/playwright.config.ts:20-22`, never in `testing.rst` or `setup.rst` |
| Smoke test after `make run` in setup.rst | OPEN | `docs/developer/setup.rst:100-149` gives a URL table and demo accounts but no confirmation step showing what a working result looks like |
| Every-model-has-timestamps and initial-migration claims | PARTIAL | The initial-migration claim is now correct (`setup.rst:87-89` names `accounts.0002_seed_roles`); `data-model.rst:19-21` still says every model carries `created_at`/`updated_at`, false for `BasePage` and `SiteSettings` (`backend/apps/cms/models.py:150,603`) |
| Rewrite payments-setup.rst as a subsystem chapter with a sequence diagram | PARTIAL | A "The provider interface" section now documents the registry, error classes and provider names (`payments-setup.rst:407-449`); there is still no checkout sequence diagram and no `:doc:` link to `api-payments` |
| reminders.rst KIND_ORDER and frontend labels | OPEN | `docs/developer/reminders.rst:243-246` still omits `KIND_ORDER` (`backend/apps/reminders/services.py:53`) and the frontend `ReminderKind`/`KIND_LABELS` |
| cms.rst HandbookPage example and DartPage `__str__` | OPEN | `docs/developer/cms.rst:113-118` still shows `FieldPanel("body")` with no `body` field declared; `:222-224` still claims `DartPage` has a `__str__`, but `backend/apps/cms/models.py:509-571` defines none |
| Delete the stale is_active warning in reports.rst | OPEN | The warning is still at `docs/developer/reports.rst:202-207`, and the bug it describes is fixed (`backend/apps/aircraft/api/views.py:141` now includes `is_active` in `applied_filters`), so it is doubly wrong |
| Add extension recipes with code skeletons | OPEN | No recipe for adding an API endpoint, portal screen, management command or payment provider exists in `docs/developer/`; only the prose "Adding a page type"/"Adding a block" at `cms.rst:185,214` |
| Tracking: method/path headings, status codes, JSON examples | OPEN | `api-auth.rst` and `api-aircraft.rst` have zero `code-block:: json`; `api-members.rst` still uses topic headings ("List members", "Create a member" at `:67,217,259`); `DELETE /admin/members/{user_id}` documents no 204 or 404 (`api-members.rst:284-296`) |
| api-reference.rst filter-backend, error-shape, endpoint-count | OPEN | `:200-213` names only `/admin/members` and `/admin/payments` as overriding the default filter backends, omitting the aircraft list (`backend/apps/aircraft/api/views.py:68`); `:226-227` still says field errors are always lists, contradicted by the bare string at `backend/apps/payments/api/views.py:86`; `:276` still says "Three anonymous auth endpoints" for four endpoints across three scopes |
| Aircraft API: PUT, is_active filter, leader card with no profile | PARTIAL | The `is_active` filter is documented (`api-aircraft.rst:71`); `PUT /aircraft/{id}` is still undocumented though the view is a `RetrieveUpdateDestroyAPIView` with no `http_method_names` (`backend/apps/aircraft/api/views.py:85`); the no-profile claim at `:227-231` is still wrong because `membership_ok` is computed from terms regardless of profile (`aircraft/services.py:100-102`) |
| Payments API: custom_id, datetime offsets, summary filters | PARTIAL | Summary filters are now correct (`api-payments.rst:284-286,297`); `custom_id` is still documented as required at `:142` though the code checks it only when present (`paypal.py:367-368`); example datetimes still end in `Z` (`:276-277`) despite `TIME_ZONE="America/Los_Angeles"` |
| api-profile.rst aircraft summary serializer | DONE | `api-profile.rst:283` now says it comes from `apps.aircraft.api.serializers`, matching `backend/apps/members/api/profile_serializers.py:17` |
| api-members.rst grant start-date rule | OPEN | `api-members.rst:327-328` still says "the day after the current expiry for a current member, today otherwise", but `_latest_expiry` takes `max(ends_on)` across all active terms (`backend/apps/members/services.py:282-291`), so a future-dated term moves the start |
| Align PLAN permission statements with the code | DONE | PLAN.rst is archived and uncited; the content now lives correctly at `api-reference.rst:322-330` and the matrix at `:568-588` |
| Correct PLAN §7 public-site claims | DONE | `theming.rst:127-137,150-151` attributes `data-theme` to server rendering; `architecture.rst:375` and `backend/templates/base.html:66` both say "Log in" |
| Update the PLAN §16 docs tree | DONE | PLAN.rst is archived; `docs/developer/index.rst:17-44` and `docs/user/index.rst:13-36` are complete toctrees that link pages rather than list file paths |
| Add how-to articles; give the walkthrough how-to structure | OPEN | No page titled "How to …" exists in `docs/`; `docs/demo-walkthrough.rst` still tours five tasks and ends with "After the walkthrough" rather than prerequisites, steps and related material |
| Production-topology diagram in deployment.rst | OPEN | No `graphviz`, `digraph` or `only::` diagram directive anywhere in `docs/developer/deployment.rst` |
| Complete the env-var lists | DONE | `.env.example:20-22` carries the three `AUTH_THROTTLE_*` vars; `deploy/caldart.env.example:40-105` lists `CSRF_TRUSTED_ORIGINS`, `EMAIL_TIMEOUT`, `ADMIN_EMAILS`, `DJANGO_VITE_MANIFEST_PATH`, `SECURE_*`, `LOG_LEVEL`, `DB_CONN_MAX_AGE` and `WEB_CONCURRENCY`, all documented at `configuration.rst:115-372` |

### Remaining work — documentation

- Correct the `make seed` comment at `README.rst:25` to say it also seeds CMS content (trivial).
- Fix `docs/user/system-administrator-guide.rst:208`, which still says only `caldart-….sql.gz` files are downloadable although `--name` accepts any name (trivial).
- Document `health --json`'s always-zero exit status with a sample JSON body, and link the bare `manage.py health --json` at `system-administrator-guide.rst:169,245-246` to the full `caldart_manage` invocation (small).
- Correct the four role descriptions: `account-administrator-guide.rst:10` ("Everything lives under Members"), the account_admin row at `getting-started.rst:74-75`, the Membership menu at `:167-168`, and the conditional superuser framing at `system-administrator-guide.rst:25-26` (small).
- Requote five UI labels to match the code: "Test payment" not "Mock" (`faq.rst:83`, `demo-walkthrough.rst:122`), "Forgot your password?" (`faq.rst:182`), the duplicate-email message (`demo-walkthrough.rst:143`), and the Site settings field names (`website-administrator-guide.rst:264,269`) (small).
- Fix the two demo-walkthrough claims: checkout does not get its own port (`:36-37`, `make run` binds :8000), and website_admin can reach `/django-admin/` because `services.py:141` sets `is_staff` (`:363-364`) (trivial).
- Add a user-guide overview page with a member-lifecycle diagram (join, pay, term, reminders at t60/t30/t7/expired/post30, renew) (medium).
- Trim `docs/user/index.rst:5-11,38-39` to a short intro and move `payments.rst` out of "For members", since `:115-118` is account_admin material (small).
- Add the missing user-guide cross-links: `:doc:` links in `member-guide.rst`, links on the other 14 `faq.rst` answers, and a `:ref:` label on `deployment.rst:540` for `system-administrator-guide.rst:52` to point at (small).
- End `payments-setup.rst`, `reminders.rst`, `backup-restore.rst`, `theming.rst`, `cms.rst` and `reports.rst` with a link to their API page (trivial).
- Convert the 18 remaining relative `../` cross-directory `:doc:` targets to absolute `/developer/...` form (small).
- Remove the remaining time-anchored wording: `README.rst:148`, `faq.rst:110`, `roadmap.rst:45,76,81,95`, `deployment.rst:537`, `docs/conf.py:121` (small).
- Expand DART as "Disaster Airlift Response Team" on first use in `README.rst`, `docs/index.rst` and the user guide (trivial).
- Set `nitpicky = True` in `docs/conf.py:111` and drop the duplicate `master_doc` at `:88-89` (trivial).
- Remove the remaining change history from `backend/tests/test_integration.py:61,119,140` and `frontend/src/portal/features/profile/AircraftEditor.tsx:4-7` (trivial).
- Restructure `README.rst` to the doc-readme shape: a plain title, Features, Requirements and setup, Documentation, Contributing and License sections, and a shorter e2e section that links `testing.rst` (medium).
- Rewrite the opening of `docs/developer/index.rst:5-11` to name the audience and contrast the developer guide with the user guide (trivial).
- Document `E2E_PORT`, `E2E_DB`, `E2E_DATABASE_URL`, `E2E_LOG`, `SKIP_CREATEDB`, `E2E_BASE_URL` and `CI` in `testing.rst` (small).
- Add a smoke test after `make run` in `docs/developer/setup.rst:100-149` showing what a working result looks like (trivial).
- Correct `data-model.rst:19-21`: `BasePage` and `SiteSettings` do not carry `created_at`/`updated_at` (trivial).
- Add a checkout sequence diagram and an `api-payments` link to `payments-setup.rst` (medium).
- Add `KIND_ORDER` and the frontend `ReminderKind`/`KIND_LABELS` to the add-a-kind steps at `reminders.rst:243-246` (small).
- Fix the `HandbookPage` example at `cms.rst:113-118` (it panels a `body` field it never declares) and delete the false `DartPage.__str__` claim at `:222-224` (trivial).
- Delete the stale `is_active` warning at `reports.rst:202-207`, now that the aircraft export includes the filter (trivial).
- Add extension recipes with code skeletons for a payment provider, an API endpoint, a portal screen and a management command, plus skeletons for the two CMS recipes (medium).
- Bring the API pages to the doc-dev-guide §6 format: method-and-path headings on `api-members.rst`, a JSON example and status-code list for every response across all five pages, and the 204/404 on `DELETE /admin/members/{user_id}` (medium).
- Correct three `api-reference.rst` claims: the aircraft list also overrides the filter backends (`:200-213`), field errors are not always lists (`:226-227`), and the throttle count is four endpoints across three scopes (`:276`) (small).
- Document `PUT /aircraft/{id}` and fix the leader-card-with-no-profile claim at `api-aircraft.rst:227-231`, since `membership_ok` ignores the profile (small).
- Fix `api-payments.rst:142` (`custom_id` is checked only when present) and the `Z`-suffixed example datetimes at `:276-277`, which contradict the project time zone (small).
- Correct the grant start-date rule at `api-members.rst:327-328`: `_latest_expiry` takes the maximum `ends_on` across all active terms, so a future-dated term moves the start (trivial).
- Add real how-to articles and give `docs/demo-walkthrough.rst` how-to structure (prerequisites, numbered steps, troubleshooting, related material) (medium).
- Add a production-topology diagram (Apache, gunicorn, Django, Postgres, the systemd reminder timer) to `deployment.rst` (small).

---

## #61 Low-priority tooling and cross-cutting findings (10 items: 0 DONE, 2 PARTIAL, 8 OPEN)

| Item | Status | Evidence |
| --- | --- | --- |
| `make help` lists every target, or stop claiming it does | PARTIAL | `make e2e` now carries a help comment (`Makefile:156`), and `README.rst:81-84` and `docs/developer/setup.rst:220-221` were softened to "the everyday targets"; but `Makefile:3` still says "Every target runs from the repository root. `make help` lists them" while eight targets have no `##` comment (`wait-db:84`, `lint-backend:185`, `lint-spelling:194`, `lint-frontend:198`, `check-backend:213`, `check-frontend:217`, `audit-backend:225`, `audit-frontend:228`) |
| `check-deploy` gate; silence W019 deliberately | OPEN | No `check-deploy` target in the `Makefile` (only `check-backend`/`check-frontend` at `:211-216`) or in `.github/workflows/ci.yml:63,92`; `backend/caldart/settings/prod.py:79` silences only `security.W021`, leaving `X_FRAME_OPTIONS = "SAMEORIGIN"` (`:94`) to raise W019 |
| Pin and document the Node version | OPEN | No `.nvmrc` or `.node-version`, no `engines` field in `frontend/package.json`; `README.rst:16` and `docs/developer/setup.rst:26-28` still say only "Node 20+" |
| Raise dependency minimums; justify or drop Django `<6.0` | OPEN | `pyproject.toml:8-10` is unchanged: `django>=5.1,<6.0`, `wagtail>=6.3`, `djangorestframework>=3.15`, with no comment explaining the upper bound (the lock resolves Django 5.2.17, Wagtail 8.0, DRF 3.18) |
| Enable ruff RUF and N, or delete unused noqa | OPEN | `pyproject.toml:82` selects `["E","F","I","UP","B","DJ","C4","W","ANN","D"]`; noqa directives for unselected rules remain at `backend/apps/accounts/permissions.py:53,61` (`N802`), `backend/apps/sysadmin/services.py:100` (`S603`), `backend/apps/payments/providers/stripe.py:302` (`BLE001`) |
| Adopt the type-checked ESLint preset; remove the dead override | PARTIAL | The duplicate `react-refresh/only-export-components` override block is gone; `frontend/eslint.config.js:11` still extends plain `tseslint.configs.recommended` with no `recommendedTypeChecked` and no `parserOptions.project` |
| Accessibility linting (jsx-a11y) | OPEN | No `eslint-plugin-jsx-a11y` in `frontend/package.json` and no reference in `frontend/eslint.config.js` |
| Scope vitest globals to test files | OPEN | `frontend/tsconfig.json:15` still puts `vitest/globals` and `@testing-library/jest-dom` in the one project-wide `types` array covering `src`, `e2e` and the config files; there is no test-only tsconfig |
| Content-Security-Policy allowing the Stripe and PayPal hosts | OPEN | No CSP header anywhere in `backend/caldart/settings/`, `deploy/` or the templates; only `django.middleware.security.SecurityMiddleware` (`backend/caldart/settings/base.py:88`), which sets none |
| Contract test between the DRF serializers and `api/types.ts` | OPEN | No schema tooling (e.g. drf-spectacular) in `pyproject.toml` or `frontend/package.json`, and no contract test in `backend/tests/` or `frontend/src/test/` |

### Remaining work — tooling and cross-cutting

- Either add `##` help comments to the eight uncommented Makefile targets or soften the claim at `Makefile:3` that `make help` lists every target (trivial).
- Add a `make check-deploy` target running `manage.py check --deploy --fail-level WARNING` under `caldart.settings.prod` with a throwaway environment, call it from CI, and silence `security.W019` in `prod.py` with a comment (small).
- Pin Node: add `engines` to `frontend/package.json` and a `.nvmrc`, and update `README.rst:16` and `docs/developer/setup.rst:26-28` from "Node 20+" to the pinned version (trivial).
- Raise the dependency minimums in `pyproject.toml:8-10` to what the lock resolves (`django>=5.2`, `wagtail>=8.0`, `djangorestframework>=3.18`) and either drop `<6.0` or record the incompatibility beside it (trivial).
- Either enable ruff's `RUF` and `N` rule sets or delete the three noqa directives for rules that are not selected (small).
- Adopt `tseslint.configs.recommendedTypeChecked` with `parserOptions.project` in `frontend/eslint.config.js` and fix the resulting diagnostics (medium).
- Add `eslint-plugin-jsx-a11y` to the frontend lint config (small).
- Move `vitest/globals` and `@testing-library/jest-dom` out of the project-wide `frontend/tsconfig.json:15` into a test-only tsconfig (small).
- Add a Content-Security-Policy that allows the Stripe and PayPal hosts the checkout panels load (medium).
- Add a contract test that keeps the DRF serializers and `frontend/src/portal/api/types.ts` in step (medium).

---

## Findings triaged below their stated priority

Both are traceable to an open low-priority issue, so nothing is lost — but the critiques
themselves called them high priority:

1. **`make help` does not list every target.** The documentation critique's executive
   summary lists this as high-priority item 6 ("wrong information a reader will act on"),
   alongside the six findings that became closed issues #48-#54. It was triaged into #61
   instead and is still PARTIAL (see above).
2. **Four of the backend test critique's six "high-priority fixes" live in #57.** Fixes 3
   (assert error-message content), 4 (assert PDF content and rename the overclaiming
   tests), 5 (stop `conftest.py` writing into `frontend/dist/` and run the bundle tests in
   CI) and half of fix 2 (guard against live HTTP in all payment tests) were collected as
   low-priority items in #57 rather than becoming plan issues. Fixes 1, 6 and the rest of 2
   did become issues (#65, #23, #34, #21, #19) and are closed.
3. **"Message assertions in the profile form tests"** is high-priority item 4 in the
   frontend test critique's executive summary; it is item 1 of #59 and remains PARTIAL
   (`features/profile/form.test.ts:95,100,108,116`).

## Findings the plan and the six issues did not capture

- **A full treatment for the reminder and system API endpoints.** The documentation
  critique's priority 2 and its agent prompt both ask for "a page or full section for the
  reminder and system endpoints". #60 item 29 covers only headings, status codes and JSON
  examples on the five existing `api-*` pages. `docs/developer/api-reference.rst:19-22`
  still states that reminder, system and site endpoints have no page of their own and
  defers to `reminders.rst`, `backup-restore.rst` and `cms.rst`, which are prose chapters
  rather than API references. Nothing in #56-#61 asks for this.
- **The `Provider` contract and the abstract models in the ERD** (documentation critique
  priority 4). The ERD itself was corrected by closed issue #50, and #60 item 24 partly
  covers the `Provider` contract through the payments-setup rewrite (a "The provider
  interface" section now exists at `payments-setup.rst:407-449`), but no item asks for the
  abstract models to appear in the ERD.
- **Distinguishing a CSRF 403 from a permission 403 in the frontend** (frontend critique
  Part 2 §12). Minor, and no issue names it.
