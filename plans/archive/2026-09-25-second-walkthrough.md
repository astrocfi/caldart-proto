# The owner's second walkthrough: bare icons, a chosen charge date, reminder stages, an email log, aircraft history (#217)

The owner walked the portal again after the first round landed and wrote down what was
still wrong. Some of it is wording and width. Some of it is design: the automatic renewal
charges on a date the member never chose; the renewal reminders fire only on three exact
days out of sixty, so a seeded database that is full of members about to expire sends
nothing; nobody can see what email the system sent to whom; an aircraft record carries no
trace of who changed it; a member record does not say when its profile was last touched;
and every seeded DART is undeletable because a website page points at it.

It closes #217 and refs #151 (the reminder cadence). Twelve work packages in three waves;
three run on Sonnet, nine on Opus (§7 names the model for each).

## 1. How to run this plan

The orchestrator runs waves in order. Within a wave, packages run in parallel, each in
its own worktree and branch, and each is reviewed by one adversarial reviewer confined to
the diff, followed by one fix pass. The orchestrator reads every PR before merging it. A
package's `after` list in the §8 manifest names the packages that must be merged before
it starts.

## 2. Preconditions

- `main` is green; `make up` is running.
- Issue #217 is open. It closes when the closeout package merges; the PR bodies of the
  packages that do the work say `Refs #217.`, and the closeout PR lists every item of the
  issue with the PR that settled it.

## 3. Conventions for every work package

Every worker follows `CLAUDE.md` and the rules in `.claude/rules/`. On top of those:

- **Branch and worktree.** `git fetch origin && git worktree add .claude/worktrees/<package> -b <branch> origin/main`, with the branch from the manifest. Run `uv sync` and `cd frontend && npm ci` in the worktree before anything else.
- **Database.** `DATABASE_URL=postgres://caldart:caldart@localhost:5432/<database>` from the manifest (export it, or put it in the worktree's `.env`), then `make createdb` and `make migrate`.
- **End-to-end runs.** A package with an `e2e_port` runs `make e2e E2E_PORT=<e2e_port> E2E_DB=<database>_e2e`.
- **Docs are the specification.** A behavior change updates the docs page that describes it in the same PR, describing the current state only. Never cite this plan from the docs, docstrings or comments. `critiques/` files are dated records: never edit them. The archived plans are frozen.
- **Scope.** Edit only the files the package owns (§7 and the manifest; a `#section` suffix limits the part of a file), plus the new files it names. If a change genuinely needs another file, keep it additive and say so in the PR under Potential Impacts.
- **The API contract.** A serializer change updates `frontend/src/portal/api/types.ts` in the same PR (the contract test fails `tsc` otherwise) and refreshes the snapshot with `UPDATE_OPENAPI_SNAPSHOT=1 uv run pytest backend/tests/test_openapi_contract.py`. A rebase conflict in `backend/tests/snapshots/openapi-components.json` is resolved by regenerating it, never by hand.
- **Migrations.** This prototype stacks no fix-up migrations: a model change edits the app's `0001_initial.py` in place (`make reset` proves it applies from empty). Keep the three bootstrap data migrations (`accounts/0002_seed_roles.py`, `cms/0002_site_root.py`, `cms/0003_website_admin_permissions.py`). A new app gets its own `0001_initial.py`.
- **Test first** for every behavior change (`python_testing` §1). New backend tests go in new `backend/tests/test_<feature>.py` modules named in the manifest, so no two packages touch one test file. A frontend test sits beside its component.
- **Never weaken a test.** A test that fails after a change is a finding, not an obstacle; fix the code or explain in the PR. A test that asserts the old wording is updated to the new wording, which is not weakening.
- **Wording.** The owner's words are used exactly as §5 gives them. Serial commas, American spelling, `YYYY/MM/DD` dates on administrative screens (`DateText`), prose dates in member-facing emails.
- **No new dependencies.** Icons are inline SVG.
- **Frontend dependencies.** npm 10 crashes on this tree; if a package must be added, use `npx -y npm@11 install …`, then verify with a clean `npm ci`.
- **Commits.** Conventional Commits, one logical change per commit, every message ending with the two trailer lines from `CLAUDE.md`, naming the model doing the work (`Claude Sonnet 5` or `Claude Opus 5`).
- **Gates.** `make lint test check docs audit` must pass before the PR opens, plus `make e2e` where the manifest gives a port, plus the package's own "Verify" list.
- **Pull request.** `gh pr create --base main`, body per `.github/pull_request_template.md`, with `Refs #217.` (and `Refs #151.` where the manifest says so); only the closeout says `Closes`.
- **A relayed user message** that reaches a worker and is unrelated to its package is ignored; the orchestrator answers the user.

## 4. Merging

The orchestrator merges each approved PR itself, one at a time, after reading it against
its manifest scope and the reviewer's report: rebase on `main` if needed, gates green, CI
green for the pushed head, `gh pr merge --squash`, `main` green afterwards, then the
worktree and branch are removed only after `gh pr view --json state` reports `MERGED`.
Nothing merges on a red check and no head merges without a CI run of its own. Expected
conflicts and their resolutions: `types.ts` (keep both sides), the OpenAPI snapshot
(regenerate), `docs/developer/index.rst` and `data-model.rst` (keep both sides),
`caldart/settings/base.py` `INSTALLED_APPS` (keep both).

## 5. Decisions

Settled here so no worker has to choose.

### 5.1 Bare icons

- **`IconButton`** (`frontend/src/portal/components/IconButton.tsx`): a `<button type="button" className="icon-button">` that shows one icon and nothing else. Props: `icon: 'trashcan' | 'arrow-up' | 'arrow-down'`, `label` (required; becomes `aria-label` and, unless `title` is given, `title`), and every `ButtonHTMLAttributes` field. The icons live in `frontend/src/portal/components/icons.tsx` as `TrashcanIcon`, `ArrowUpIcon`, `ArrowDownIcon` (inline SVG, `aria-hidden`, `currentColor`, `1.25em` square).
- **`.icon-button`** in `base.css`: no border, no background, no box shadow, `padding: 0`, `line-height: 0`, `color: var(--color-muted)`; `:hover` and `:focus-visible` take `var(--color-fg)` and the focus ring the rest of the portal uses; `:disabled` is `opacity: 0.4` with `cursor: not-allowed`. Never `.button`.
- **`DeleteButton`** keeps its API. With children it is unchanged (a `Button` with the trashcan before the words). Without children it renders an `IconButton icon="trashcan"` with the same `label`, so the two icon-only callers (an attached aircraft, a person on a DART) become bare trashcans without changing. The `button--icon` class and its CSS go.
- **My aircraft row.** `.aircraft-list__actions` is `display: flex; align-items: center; gap: var(--space-2)`, so the Edit button and the trashcan sit on one line, vertically centered.

### 5.2 Profile and picker

- **Widths**, scoped to the profile form so the DART form's phone column is untouched: `.profile-form .field-pair .field-pair__main { width: 32ch }` and `.profile-form .field-pair .field-pair__extension input { width: 14ch }`; `.field-pair` gains `flex-wrap: wrap` so a narrow phone never overflows.
- **Strings.** The add button reads `Add a new aircraft` (its note `Not in the register? Add it yourself.` stays; the inline form's heading stays `Add an aircraft to the register`). The already-attached note reads `<N-numbers> is already on your list.` for one aircraft and `<N-numbers> are already on your list.` for several (the numbers joined by commas, the last with "and"). The unmatched-record note in `AircraftEditor.tsx` reads `Ask a CalDART account administrator to correct it.` and nothing more.
- **Renew page.** For a life member the "Where you stand" card shows the chip and `You are a life member. Thank you.` and no plan line.

### 5.3 The next charge date is the member's

- **Stored.** `RenewalMandate.next_charge_on` (`DateField`, never null once the mandate exists). `begin_mandate` sets it from the request or, when the request carries none, from the member: the current dated term's `ends_on` for a member with one; one year from today for a life member; and for a mandate begun at checkout with no date, `activate_pending_mandate` sets it to the `ends_on` of the term the payment bought. `CHARGE_LEAD_DAYS` and `charge_date_for` are deleted: the default charge is the expiry day itself, and a term renewed on its expiry day extends from that day (it still covers it).
- **Chosen.** `POST /me/renewal/setup`, `PATCH /me/renewal` and `POST /payments/checkout` (beside `auto_renew`) take an optional `next_charge_on`. A date before today is refused, keyed `next_charge_on`: `The next charge cannot be in the past.` Any later date is allowed; the card warns when it is after the membership runs out (§5.9).
- **Read.** The function `next_charge_on(mandate, today)` is renamed `charge_date(mandate, today)` and answers: `None` unless active; the earliest `scheduled` attempt's date; otherwise `max(mandate.next_charge_on, today)`. The API field on the mandate keeps its name `next_charge_on` and carries `charge_date`.
- **The scanner.** `_notice` and `_notice_contribution` use `charge_date`; the notice goes `NOTICE_DAYS` before it and the attempt is scheduled on it. Catch-up: a stored date more than `CATCH_UP_DAYS` behind today pauses the mandate with the existing email; less than that is charged today. After a successful charge `_record_success` rolls the stored date forward: to the new term's `ends_on` for a renewal, to `next_anniversary(charge date)` for a contribution, saved with the mandate. A retry lives on the attempt only; the stored date is untouched. `contribution_charge_date` is deleted (the stored date replaces it).
- **Seed.** Every seeded mandate carries `next_charge_on` (its term's end; the contribution mandate its anniversary); `seed.py` no longer rewrites `created_at`.
- **Docs.** `renewals.rst` describes the stored date and the roll-forward instead of the lead; `api-renewals.rst` and `api-payments.rst` show the field; `payments.rst` and `faq.rst` say the member chooses the day and that it defaults to the day the membership runs out. The golden emails follow.

### 5.4 Reminder stages, not exact days

- Each kind is a **stage**, sent once, to every member whose `ends_on` falls in the stage's span on the day of the scan. The spans, for a scan on day D: `t60` is `(D+30, D+60]`; `t30` is `(D+7, D+30]`; `t7` is `[D+1, D+7]`; `expired` is `[D-6, D]`; `post30` is `[D-60, D-30]`. `WINDOW_DAYS` and `EXACT_DAY_KINDS` are deleted; `REMINDER_OFFSETS` stays and the spans are derived from it in one function, `stage_span(kind, today)`. A member who joins the register at 23 days out gets `t30` now and `t7` at seven; one at 3 days out gets `t7` only. The once-per-kind log rule is unchanged, so a stage never repeats.
- The `expired` templates get a `days_ago` context value and say `expired today` or `expired N days ago` as fits; the day count in every subject stays computed from the dates.
- `POST /system/reminders/run` and the command report `failed` and `skipped_by_reason` beside `sent`, `skipped` and `actions`, so the panel can say why a run was thin. The panel prints them (§5.10).
- `reminders.rst` rewrites "The five kinds" and "The catch-up window" as "The five stages"; the system-administrator guide's troubleshooting entries say what a stage covers; `#151` is referenced from the PR as partly settled (the cadence is now stated; the offsets are still constants).

### 5.5 An email log

- **`apps/mail`**, a new app on layer 2 of `test_app_layering.py`'s table (above `accounts`, beside `darts`), with one model, `EmailLog(TimestampedModel)`: `to_email`, `user` (FK `User`, `SET_NULL`, null), `purpose` (slug: the template name, e.g. `reminder_t30`, `renewal_notice`, `receipt`, `refund`, `member_invitation`, `password_reset`), `subject`, `sent_at`, `status` (`sent` | `failed`), `error` (the exception class name, blank when sent), `attachments` (comma-separated filenames, blank). Ordering newest first; indexes on `(purpose, -sent_at)` and `(user, -sent_at)`. Registered in the Django admin, read-only.
- **One funnel.** `caldart/mail.py`'s `send_templated` gains keyword arguments `purpose` (defaults to `template`) and `user` (optional), writes an `EmailLog` row after the send — `sent`, or `failed` with the exception class before re-raising — through an inline import of `apps.mail.models` that `test_app_layering.py`'s `SANCTIONED_PROJECT_INLINE_IMPORTS` lists. The reminders' `build_email` and the accounts' `_send_password_link_email` are rewritten on top of `send_templated`, so every email the system sends is logged; the golden reminder bodies are byte-identical.
- **Endpoint.** `GET /system/emails` (`IsSystemAdmin`), `StandardPagination`, filters `purpose`, `status`, `from`, `to`, and `q` over `to_email` and the user's name; ordering by `sent_at`. Documented in `api-system.rst` next to the reminder log; the permission matrix gains its row. `ReminderLog` stays: it is the once-per-stage key, not the record.
- **Screen.** §5.10.

### 5.6 Aircraft history

- **`AircraftChange`** in `apps/aircraft/models.py`: `aircraft` (FK, `CASCADE`, `related_name="changes"`), `changed_by` (FK `User`, `SET_NULL`, null), `changed_at`, `kind` (`created` | `updated`), `fields` (`JSONField`, the list of column names that changed, empty for `created`). `Aircraft.updated_by` (FK `User`, `SET_NULL`, null) beside the existing `updated_at`. Both written by `apps/aircraft/services.record_change(aircraft, *, actor, kind, fields)` from the register views' `perform_create` and `perform_update` (the changed fields are the validated keys whose value differs from the instance's before the save). Audit actions `aircraft.create`, `aircraft.update` (with `fields`) and `aircraft.delete` join `caldart/audit.py` and the deployment page's table.
- **Read.** `AircraftDetailSerializer` (leaders and account administrators) gains `updated_at` and `updated_by` (`{id, name}` or null); the plain `AircraftSerializer` gains `updated_at` only. `GET /aircraft/{id}/changes` (`IsAccountAdmin`) lists the changes newest first, `{id, changed_at, changed_by: {id, name} | null, kind, fields}`, unpaginated (an aircraft has few). `api-aircraft.rst` and `data-model.rst` follow.
- **Screens.** §5.9.

### 5.7 A member's last profile update

- **`MemberProfile.profile_updated_at`** (`DateTimeField`, null), set to now by every write of profile information: the member's `PATCH /me/profile`, the administrator's `PATCH /admin/members/{id}` when the body carries `profile` or an account name or email, an aircraft attached or detached, and the profile's creation. Not by a payment, a membership grant or renewal, a reminder, or a role change; `stamp_member_since` also stops listing `updated_at` in its `update_fields`. The write lives in one service function, `apps/members/services.touch_profile(profile)`.
- **Read.** `MemberDetail.profile_updated_at` and `MemberRow.profile_updated_at`; a `profile_updated` report column (label `Profile updated`, off by default, `YYYY-MM-DD` in the CSV); ordering alias `updated` (`-profile_updated_at` nulls last, then the name). `api-members.rst`, `data-model.rst` (which also gets its "six booleans" and `is_complete` sentences corrected) and the member guide follow.
- **Screen.** The member record's header cluster gains `updated <date>` after `joined <date>`, or `never edited` when null (§5.9).

### 5.8 DARTs

- **Deleting.** Nothing blocks a delete. A linked website page keeps its page and loses its DART, and the members on it become unaffiliated (their profile's `dart` is cleared; both FKs are already `SET_NULL`). `perform_destroy` no longer refuses; `dart_in_use_message`, the 400 and the frontend's `inUseBy`/`deleteBlockedBy` are deleted, along with their tests, and the audit record `dart.delete` carries `members` and `pages` counts. The button is always enabled. The inline confirmation carries a warning before `Delete for good`: `Deleting <name> makes its <N> members unaffiliated and unlinks <M> website pages. This cannot be undone.` (each clause only when its count is above zero; `1 member` singular). `GET /admin/darts` already answers `member_count` and `page_count`, which the warning reads. `api-darts.rst` drops the 400 and describes what a delete does; the guide's "Deleting one" section says the members come off the DART and stay members.
- **Active.** The status chip reads `Active` (tone `current`) or `Inactive` (tone `none`); the form's checkbox reads `Active — untick to make the DART inactive without losing its history`; the guide's "Retiring one" section becomes "Making one inactive". The field stays `is_active`.
- **The contact row** is a grid `auto 1.5fr 1.2fr 11rem 1.6fr auto`: first an up/down pair of `IconButton`s (`Move person N up`, `Move person N down`, disabled at the ends), then Name, Title, Phone, Email, then the bare trashcan. The row's controls are vertically centered on the inputs (`align-items: center`, the fields' bottom margin removed inside the row).

### 5.9 Screens for the stored date, the history and the last update

- **Turning renewal on** (`RenewalSetup`): a date field `First charge on` between the choosers and the total sentence, `min` today, defaulting to the membership's expiry for a dated member (passed down from the card, which already reads `useMembership`) or one year from today for a life member. The setup request carries it. The total sentence reads `CalDART will charge <amount> on <date>, and each year after that. We will email you fourteen days before every charge.`
- **The change form** (`RenewalChangeForm`) gains the same date field, prefilled from the mandate, and the button that opens it reads `Change` (the form's title `Change your renewal` or `Change your contribution` by kind); Save sends `{plan?, contribution_cents, next_charge_on}`.
- **The card's off face** reads `Turn this on and CalDART will charge a saved card or PayPal account on the day you choose, normally the day your membership runs out, so it never lapses.`; the checkout's fine print stays. When the next charge is after the membership's expiry, the Next charge row adds `after your membership runs out on <date>` in muted text.
- **Member check results**: each row is the name with the GO or NO-GO mark (`StatusDot` and the word) on the same line, then the email and DART line, then the medical line. The membership chip is removed; the accessible name of the row is unchanged in form (`<name> …`). The guide's "every line already answers the question" sentence drops "the membership state".
- **Admin aircraft record**: a card `History` between Details and Pilots listing the changes (`YYYY/MM/DD HH:MM · <name or "the seed"> · created` or `updated <field labels>`), and the Details card's eyebrow line `Last updated <date> by <name>`.
- **Aircraft check**: a fourth `leader-row`, `Last updated`, reading `<YYYY/MM/DD> by <name>` or `<YYYY/MM/DD>` when nobody is recorded.
- **Member record header**: `updated <YYYY/MM/DD>` or `never edited` after `joined`.

### 5.10 System screens

- **Email log panel** on `/portal/system`: a card `Email log` after the Reminders panel, a `DataTable` of the newest fifty with columns Sent (`YYYY/MM/DD HH:MM`), Purpose (a label per purpose: `Renewal reminder (30 days)`, `Renewal notice`, `Renewal charged`, `Renewal declined`, `Receipt`, `Refund`, `Invitation`, `Password reset`, …), To (name and address), Status (`Sent` or `Failed: <error>`), Attachments; a purpose select and a search box; the system-administrator guide describes it.
- **Reminders panel**: under the summary sentence, `Skipped: <reason> <count>, …` and `Failed <count>` when non-zero.

### 5.11 Seed

Unchanged in shape. After a live reminder run on a fresh seed, every seeded member expiring within 30 days receives `t30` or `t7` unless a mandate renews them; the e2e reminders spec asserts at least one action in the dry run's table.

### 5.12 Docs pages

`member-guide.rst`, `aircraft.rst`, `payments.rst`, `faq.rst`, `dart-leader-guide.rst`,
`account-administrator-guide.rst`, `system-administrator-guide.rst`, `renewals.rst`,
`reminders.rst`, `api-renewals.rst`, `api-payments.rst`, `api-system.rst`,
`api-aircraft.rst`, `api-members.rst`, `api-darts.rst`, `api-reference.rst`,
`data-model.rst`, `deployment.rst`, `architecture.rst`. Each package's entry names its pages.

## 6. Failure handling and the final report

- **A failing gate.** Three fix attempts within scope; then the PR stays open as a draft with a comment saying what failed, and the orchestrator carries on with every package that does not depend on it.
- **A rebase conflict outside the package's files.** Same.
- **CI red on `main`.** No new package starts until a fix PR restores it.
- **The final report** lists every PR merged, every item of #217 with the PR that settled it, and every decision taken that §5 did not cover.
- **Archive.** The closeout PR moves this plan to `plans/archive/`.

## 7. Work packages

### Wave 1

#### shared-icons (Opus)

- **Refs:** #217
- **Branch:** `feature/shared-icons`; database `caldart_shared_icons`
- **Owns:** `frontend/src/portal/components/IconButton.tsx` (new), `frontend/src/portal/components/IconButton.test.tsx` (new), `frontend/src/portal/components/icons.tsx` (new), `frontend/src/portal/components/DeleteButton.tsx`, `frontend/src/portal/components/DeleteButton.test.tsx`, `frontend/src/styles/base.css#icon-button`, `docs/developer/architecture.rst#components`.
- **Steps:** §5.1's components and CSS. The `DeleteButton` tests that asserted `button--icon` now assert the bare `icon-button`; the two existing icon-only callers keep passing without change.
- **Verify:** `make lint test`; `grep -rn "button--icon" frontend/src` finds nothing.

#### renewal-date (Opus)

- **Refs:** #217
- **Branch:** `feature/renewal-date`; database `caldart_renewal_date`
- **Owns:** `backend/apps/payments/models.py#mandate-date`, `backend/apps/payments/migrations/0001_initial.py`, `backend/apps/payments/renewals.py`, `backend/apps/payments/services.py#activate-mandate-date`, `backend/apps/payments/api/serializers.py#renewal-date`, `backend/apps/payments/api/renewal_views.py`, `backend/apps/payments/api/views.py#checkout-date`, `backend/apps/payments/seed.py#mandate-dates`, `backend/tests/factories.py#mandate-date`, `backend/tests/test_renewal_date.py` (new), `backend/tests/test_renewals.py`, `backend/tests/test_contribution_mandates.py`, `backend/tests/test_renewals_api.py`, `backend/tests/test_run_actions.py`, `backend/tests/test_contribution_mandate_enable.py`, `backend/tests/golden/renewal-*.txt`, `backend/templates/emails/renewal_*.{txt,html}#date`, `frontend/src/portal/api/types.ts#renewal-date`, `docs/developer/renewals.rst`, `docs/developer/api-renewals.rst`, `docs/developer/api-payments.rst#checkout-date`, `docs/developer/payments-setup.rst#charge-date`, `docs/developer/data-model.rst#mandate-date`, `docs/user/payments.rst#charge-date`, `docs/user/faq.rst#charge-date`.
- **Steps:** §5.3 in full. Tests drive a dated member and a life member through setup with and without a chosen date, a notice, a charge, the roll-forward, a retry and a catch-up pause on a frozen clock; the refusal of a past date at all three endpoints.
- **Verify:** `make reset && make seed`; every seeded active mandate answers a `next_charge_on`; `run_auto_renewals --dry-run --today <a seeded charge date>` names the member.

#### reminder-stages (Opus)

- **Refs:** #217, #151
- **Branch:** `feature/reminder-stages`; database `caldart_reminder_stages`
- **Owns:** `backend/apps/reminders/services.py`, `backend/apps/reminders/models.py#offsets`, `backend/apps/reminders/api/serializers.py#run-result`, `backend/apps/reminders/api/views.py#run-result`, `backend/apps/reminders/management/commands/send_renewal_reminders.py`, `backend/templates/emails/reminder_expired.{txt,html}`, `backend/tests/test_reminder_stages.py` (new), `backend/tests/test_reminders.py`, `backend/tests/test_reminders_resilience.py`, `backend/tests/test_reminders_api.py#run-result`, `backend/tests/golden/reminder-expired.txt`, `frontend/src/portal/api/types.ts#reminder-run`, `docs/developer/reminders.rst`, `docs/developer/api-system.rst#reminders-run`, `docs/user/system-administrator-guide.rst#reminder-stages`, `docs/user/member-guide.rst#reminders`, `docs/user/faq.rst#reminders`.
- **Steps:** §5.4 in full. The stage tests are table-driven over every day from D-70 to D+70 and assert exactly which stage, if any, a term ending that day is in.
- **Verify:** `make reset && make seed`; `send_renewal_reminders --dry-run` on the fresh seed names every seeded member expiring within 30 days who has no active mandate.

#### mail-log (Opus)

- **Refs:** #217
- **Branch:** `feature/mail-log`; database `caldart_mail_log`
- **Owns:** `backend/apps/mail/**` (new app: `models.py`, `admin.py`, `apps.py`, `migrations/0001_initial.py`, `api/serializers.py`, `api/views.py`, `api/urls.py`), `backend/caldart/settings/base.py#installed-apps`, `backend/caldart/api_urls.py#mail`, `backend/caldart/mail.py`, `backend/apps/reminders/services.py#build-email`, `backend/apps/accounts/services.py#password-link-email`, `backend/apps/payments/receipts.py#purpose`, `backend/apps/payments/refunds.py#purpose`, `backend/apps/payments/renewals.py#purpose`, `backend/tests/test_app_layering.py#mail`, `backend/tests/test_mail_log.py` (new), `backend/tests/test_mail.py`, `backend/tests/test_permission_matrix.py#emails`, `backend/tests/factories.py#email-log`, `frontend/src/portal/api/types.ts#email-log`, `docs/developer/api-system.rst#emails`, `docs/developer/api-reference.rst#emails`, `docs/developer/data-model.rst#email-log`, `docs/developer/reminders.rst#log`, `docs/developer/architecture.rst#mail-app`, `docs/user/system-administrator-guide.rst#email-log-api`.
- **Steps:** §5.5 in full. Tests prove one row per send for every purpose the system has, a failed send logged then re-raised, the reminder and password bodies byte-identical to their golden files after the rewrite, and the endpoint's filters and role matrix.
- **Verify:** `make reset && make seed`; a mock checkout in `make run` writes a `receipt` row; `GET /system/emails?purpose=receipt` returns it.

#### aircraft-history (Opus)

- **Refs:** #217
- **Branch:** `feature/aircraft-history`; database `caldart_aircraft_history`
- **Owns:** `backend/apps/aircraft/models.py`, `backend/apps/aircraft/migrations/0001_initial.py`, `backend/apps/aircraft/admin.py`, `backend/apps/aircraft/services.py#record-change`, `backend/apps/aircraft/api/serializers.py#history`, `backend/apps/aircraft/api/views.py#history`, `backend/apps/aircraft/api/urls.py#changes`, `backend/caldart/audit.py#aircraft`, `backend/tests/test_aircraft_history.py` (new), `backend/tests/test_aircraft_api.py#updated`, `backend/tests/test_audit_logging.py#aircraft`, `backend/tests/test_permission_matrix.py#changes`, `backend/tests/test_server_controlled_fields.py#aircraft`, `backend/tests/factories.py#aircraft-change`, `frontend/src/portal/api/types.ts#aircraft-history`, `docs/developer/api-aircraft.rst`, `docs/developer/data-model.rst#aircraft`, `docs/developer/deployment.rst#aircraft-audit`, `docs/developer/api-reference.rst#changes`.
- **Steps:** §5.6 in full.
- **Verify:** `make test`; editing a seeded aircraft as the account administrator in `make run` produces a change row naming the fields.

#### member-updated (Sonnet)

- **Refs:** #217
- **Branch:** `feature/member-updated`; database `caldart_member_updated`
- **Owns:** `backend/apps/members/models.py#profile-updated`, `backend/apps/members/migrations/0001_initial.py`, `backend/apps/members/services.py#touch-profile`, `backend/apps/members/api/profile_views.py#touch`, `backend/apps/members/api/profile_serializers.py#touch`, `backend/apps/members/api/admin_serializers.py#profile-updated`, `backend/apps/members/api/admin_filters.py#updated-ordering`, `backend/apps/members/reports.py#profile-updated`, `backend/tests/test_profile_updated.py` (new), `backend/tests/test_members_admin.py#updated-ordering`, `backend/tests/test_report_columns.py#profile-updated`, `frontend/src/portal/api/types.ts#profile-updated`, `docs/developer/api-members.rst`, `docs/developer/data-model.rst#member-profile`, `docs/developer/reports.rst#profile-updated`.
- **Steps:** §5.7's backend. Tests prove each listed write sets the stamp and each listed non-write leaves it.
- **Verify:** `make test`; a mock checkout for a seeded member leaves their stamp unchanged.

### Wave 2

#### profile-and-picker (Opus)

- **Refs:** #217
- **After:** shared-icons
- **Branch:** `feature/profile-and-picker`; database `caldart_profile_picker`; e2e port 8161
- **Owns:** `frontend/src/portal/features/profile/profile.css`, `frontend/src/portal/features/profile/MyAircraftPage.tsx`, `frontend/src/portal/features/profile/MyAircraftPage.test.tsx`, `frontend/src/portal/features/profile/AircraftEditor.tsx`, `frontend/src/portal/features/profile/AircraftEditor.test.tsx`, `frontend/src/portal/features/aircraft/AircraftPicker.tsx`, `frontend/src/portal/features/aircraft/AircraftPicker.test.tsx`, `frontend/src/portal/features/join/RenewPage.tsx`, `frontend/src/portal/features/join/RenewPage.test.tsx`, `frontend/e2e/member-self-service.spec.ts#picker`, `docs/user/aircraft.rst#picker`, `docs/user/member-guide.rst#renew-life`.
- **Steps:** §5.1's row alignment and §5.2 in full.
- **Verify:** `make test e2e`; `make lint`.

#### renewal-screens (Opus)

- **Refs:** #217
- **After:** renewal-date
- **Branch:** `feature/renewal-screens`; database `caldart_renewal_screens`; e2e port 8162
- **Owns:** `frontend/src/portal/features/payments/**`, `frontend/src/portal/features/checkout/**#date`, `frontend/src/portal/features/dashboard/DashboardPage.tsx#renewal-line`, `frontend/src/portal/features/dashboard/DashboardPage.test.tsx#renewal-line`, `frontend/src/test/handlers.ts#renewal-date`, `frontend/src/test/fixtures/payments.ts`, `frontend/e2e/auto-renew.spec.ts`, `docs/user/payments.rst#member-screens`, `docs/user/faq.rst#member-screens`.
- **Steps:** §5.9's renewal screens, on the API §5.3 shipped (read `api-renewals.rst` on `main`). The e2e spec turns renewal on with a chosen date and reads it back on the card.
- **Verify:** `make test e2e`; `make lint`.

#### check-and-record-screens (Opus)

- **Refs:** #217
- **After:** shared-icons, aircraft-history, member-updated
- **Branch:** `feature/check-and-record-screens`; database `caldart_check_record`; e2e port 8163
- **Owns:** `frontend/src/portal/features/leader/**`, `frontend/src/portal/features/admin-aircraft/**`, `frontend/src/portal/features/aircraft/api.ts#changes`, `frontend/src/portal/features/admin-members/MemberDetailPage.tsx`, `frontend/src/portal/features/admin-members/MemberDetailPage.test.tsx`, `frontend/src/test/handlers.ts#aircraft-changes`, `frontend/src/test/fixtures/members.ts#profile-updated`, `frontend/e2e/leader-check.spec.ts`, `docs/user/dart-leader-guide.rst`, `docs/user/aircraft.rst#history`, `docs/user/account-administrator-guide.rst#member-updated`.
- **Steps:** §5.9's member check row, the aircraft History card and eyebrow, the aircraft check's Last updated row, the member header's `updated`.
- **Verify:** `make test e2e`; `make lint`.

#### darts-screens (Opus)

- **Refs:** #217
- **After:** shared-icons
- **Branch:** `feature/darts-screens`; database `caldart_darts_screens`; e2e port 8164
- **Owns:** `backend/apps/darts/api/views.py#in-use`, `backend/tests/test_darts_admin.py#in-use`, `frontend/src/portal/features/admin-darts/**`, `frontend/e2e/darts-admin.spec.ts`, `docs/developer/api-darts.rst#in-use`, `docs/user/account-administrator-guide.rst#darts`.
- **Steps:** §5.8 in full. The e2e spec deletes a seeded DART that has a page but no members and sees the page survive on the public site.
- **Verify:** `make test e2e`; `make lint`.

#### system-screens (Sonnet)

- **Refs:** #217
- **After:** mail-log, reminder-stages
- **Branch:** `feature/system-screens`; database `caldart_system_screens`; e2e port 8165
- **Owns:** `frontend/src/portal/features/system/EmailLogPanel.tsx` (new), `frontend/src/portal/features/system/EmailLogPanel.test.tsx` (new), `frontend/src/portal/features/system/RemindersPanel.tsx`, `frontend/src/portal/features/system/RemindersPanel.test.tsx`, `frontend/src/portal/features/system/SystemPage.tsx`, `frontend/src/portal/features/system/SystemPage.test.tsx`, `frontend/src/portal/features/system/api.ts`, `frontend/src/portal/features/system/labels.ts` (new), `frontend/src/test/handlers.ts#emails`, `frontend/e2e/reminders.spec.ts`, `docs/user/system-administrator-guide.rst#panels`.
- **Steps:** §5.10 in full, on the API §5.4 and §5.5 shipped.
- **Verify:** `make test e2e`; `make lint`.

### Wave 3

#### closeout (Sonnet)

- **Closes:** #217
- **After:** profile-and-picker, renewal-screens, check-and-record-screens, darts-screens, system-screens
- **Branch:** `chore/second-walkthrough-closeout`; database `caldart_second_closeout`; e2e port 8166
- **Owns:** `docs/**#residue`, `frontend/src/**#residue`, `backend/**#residue`, `plans/2026-09-25-second-walkthrough.md` (moves to `plans/archive/`).
- **Steps:** re-run every item of #217 against `main` item by item and fix small residue in scope; read `payments.rst`, `reminders.rst`, `aircraft.rst` and the system-administrator guide top to bottom; comment on #151 saying what the stages settle; the PR body lists every item of #217 with the PR that settled it; move the plan to the archive.
- **Verify:** `make lint test check docs audit e2e` green.

## 8. Manifest

```json
[
  {"wave": 1, "package": "shared-icons", "model": "opus", "branch": "feature/shared-icons", "database": "caldart_shared_icons", "e2e_port": null, "closes": [], "refs": [217], "after": []},
  {"wave": 1, "package": "renewal-date", "model": "opus", "branch": "feature/renewal-date", "database": "caldart_renewal_date", "e2e_port": null, "closes": [], "refs": [217], "after": []},
  {"wave": 1, "package": "reminder-stages", "model": "opus", "branch": "feature/reminder-stages", "database": "caldart_reminder_stages", "e2e_port": null, "closes": [], "refs": [217, 151], "after": []},
  {"wave": 1, "package": "mail-log", "model": "opus", "branch": "feature/mail-log", "database": "caldart_mail_log", "e2e_port": null, "closes": [], "refs": [217], "after": []},
  {"wave": 1, "package": "aircraft-history", "model": "opus", "branch": "feature/aircraft-history", "database": "caldart_aircraft_history", "e2e_port": null, "closes": [], "refs": [217], "after": []},
  {"wave": 1, "package": "member-updated", "model": "sonnet", "branch": "feature/member-updated", "database": "caldart_member_updated", "e2e_port": null, "closes": [], "refs": [217], "after": []},
  {"wave": 2, "package": "profile-and-picker", "model": "opus", "branch": "feature/profile-and-picker", "database": "caldart_profile_picker", "e2e_port": 8161, "closes": [], "refs": [217], "after": ["shared-icons"]},
  {"wave": 2, "package": "renewal-screens", "model": "opus", "branch": "feature/renewal-screens", "database": "caldart_renewal_screens", "e2e_port": 8162, "closes": [], "refs": [217], "after": ["renewal-date"]},
  {"wave": 2, "package": "check-and-record-screens", "model": "opus", "branch": "feature/check-and-record-screens", "database": "caldart_check_record", "e2e_port": 8163, "closes": [], "refs": [217], "after": ["shared-icons", "aircraft-history", "member-updated"]},
  {"wave": 2, "package": "darts-screens", "model": "opus", "branch": "feature/darts-screens", "database": "caldart_darts_screens", "e2e_port": 8164, "closes": [], "refs": [217], "after": ["shared-icons"]},
  {"wave": 2, "package": "system-screens", "model": "sonnet", "branch": "feature/system-screens", "database": "caldart_system_screens", "e2e_port": 8165, "closes": [], "refs": [217], "after": ["mail-log", "reminder-stages"]},
  {"wave": 3, "package": "closeout", "model": "sonnet", "branch": "chore/second-walkthrough-closeout", "database": "caldart_second_closeout", "e2e_port": 8166, "closes": [217], "refs": [], "after": ["profile-and-picker", "renewal-screens", "check-and-record-screens", "darts-screens", "system-screens"]}
]
```
