# The CalDART roles report, editable subscriptions, and Active only by default (#298)

The owner asked for three things: a report a subscription can send, named the CalDART roles
report, with a separate section for the people who hold each role other than member; a way to
edit an existing subscription, its filters included; and, on the Users and roles screen, the
account-status filter defaulting to **Active only** and sitting after the **Kind of account**
drop-down.

It closes #298. Four work packages in three waves; §7 names the model for each.

## 1. How to run this plan

The orchestrator runs waves in order. Within a wave, packages run in parallel, each in its
own worktree and branch, and each is reviewed by one adversarial reviewer confined to the
diff, followed by one fix pass. The orchestrator reads every PR before merging it. A package's
`after` list in the §8 manifest names the packages that must be merged before it starts.

## 2. Preconditions

- `main` is green; `make up` is running; the county filter drop-down (`MultiSelect`) has
  merged, so `FilterBar` draws a `multiselect` field as a drop-down of checkboxes.
- Issue #298 is open. It closes when the closeout package merges.

## 3. Conventions for every work package

Every worker follows `CLAUDE.md` and the rules in `.claude/rules/`. On top of those:

- **Branch and worktree.** `git fetch origin && git worktree add .claude/worktrees/<package> -b <branch> origin/main`, with the branch from the manifest. Run `uv sync` and `cd frontend && npm ci` in the worktree before anything else.
- **Database.** `DATABASE_URL=postgres://caldart:caldart@localhost:5432/<database>` from the manifest, then `make createdb` and `make migrate`; `make reset` after any migration change.
- **End-to-end runs.** A package with an `e2e_port` runs `make e2e E2E_PORT=<e2e_port> E2E_DB=<database>_e2e`.
- **Docs are the specification.** A behavior change updates the docs page that describes it in the same PR, describing the current state only; the user guide's voice rules are enforced by `test_docs_user.py` (banned words, no contrast construction outside italics, no `--`, at most two em dashes, no line starting with a comma, 250 lines, no reference outside `docs/user/`), and `test_docs_developer.py` checks the developer guide's routes, models, commands, and units against the code. Never cite this plan from the docs, docstrings or comments.
- **Scope.** Edit only the files the package owns (§7; a `#section` suffix limits the part of a file), plus the new files it names. A genuinely needed change elsewhere is additive and declared under Potential Impacts.
- **The API contract.** A serializer or choice change updates `frontend/src/portal/api/types.ts` in the same PR and refreshes the snapshot with `UPDATE_OPENAPI_SNAPSHOT=1 uv run pytest backend/tests/test_openapi_contract.py`; a conflict in the snapshot is resolved by regenerating it.
- **Migrations.** None of these packages changes a model. A package that finds it must says so in the PR and edits the app's `0001_initial.py` in place.
- **Test first** for every behavior change. New backend tests go in new `backend/tests/test_<feature>.py` modules named in the manifest. **Never weaken a test**; a test that counts seven reports is updated to count eight, which is not weakening.
- **Wording.** Serial commas, American spelling, `YYYY/MM/DD` on administrative screens. A role is named the way the screens name it: Member, DART leader, User administrator, Treasurer, Account administrator, Website administrator, System administrator.
- **Commits.** Conventional Commits, every message ending with the two trailer lines from `CLAUDE.md`, naming the model doing the work.
- **Gates.** `make lint test check docs audit` green before the PR opens, plus `make e2e` where the manifest gives a port.
- **Pull request.** `gh pr create --base main`, body per the template, `Refs #298.`; only the closeout says `Closes #298.`
- **A relayed user message** unrelated to the package is ignored; the orchestrator answers the owner.

## 4. Merging

As in every plan: one PR at a time, rebased if needed, gates green, CI green for the pushed head, `gh pr merge --squash`, `main` green afterwards, the last PR of a wave squashed and rebased before its CI run. Expected conflicts: `docs/user/admin/reports.rst` between the two wave-1 packages (different sections, see §7), and the OpenAPI snapshot (regenerate).

## 5. Decisions

### 5.1 Sections in the report engine

- `ReportSpec` (`backend/caldart/reports.py`) gains `section: Callable[[RowT], str] | None = None`: the title of the section a row belongs to. `ReportQuery` gains `sections: Sequence[str] | None = None`: every section title, in order, so a section with no rows still appears.
- `ReportTable` gains `sections: list[ReportSection]`, where `ReportSection` is a frozen dataclass of `title: str` and `rows: list[list[str]]`. `ReportTable.rows` stays the flat list of every row in order, which the CSV writes and `test_report_columns.py` measures. `ReportSpec.table()` fills `sections`: with `section` unset, one section titled `""` holding every row; with it set and `ReportQuery.sections` given, one section per listed title in that order, each holding the rows whose title it is, and a row whose title is not listed raises `ValueError` reading `Row in unlisted section '<title>'`; with it set and `ReportQuery.sections` unset, the distinct titles in the order they are first seen.
- The CSV is unchanged: the header, then `ReportTable.rows`. A sectioned report carries its section as a column too (the roles report's **Role** column), so the CSV loses nothing.
- The PDF (`build_pdf_table`) takes `sections: Sequence[tuple[str, Sequence[Sequence[Any]]]] | None = None`; with it, the story draws, per section, its title as a `Paragraph` in a `SECTION_STYLE` (the subtitle's face at 10pt, semibold, `PRIMARY`, 8pt above and 4pt below) followed by that section's own `LongTable` with the repeated header, and a section with no rows draws its title followed by the italic line *Nobody holds this role.* only when the spec says so: the line's words come from `ReportSpec.empty_section: str = ""`, and a blank `empty_section` draws an empty section as its title alone. Without `sections`, the PDF is exactly what it is today. `build_report` passes `table.sections` when the table has more than one section or its one section has a title.
- `backend/tests/test_report_sections.py` (new) covers the grouping rules, the unlisted-section refusal, the CSV staying flat, and the PDF drawing one heading per section (read the PDF's text back with `pypdf`, as the existing PDF tests do).

### 5.2 The roles report

- `backend/apps/accounts/reports.py` (new) declares `ROLES_REPORT: ReportSpec[RoleRow]` with `slug="roles"`, `title="CalDART roles report"`, `filename_stem="caldart-roles"`, `roles=(USER_ADMIN, ACCOUNT_ADMIN)`, `landscape=True`, `choosable=True`, `section=lambda row: row.role_label`, `empty_section="Nobody holds this role."`. It is added to `REPORTS` in `apps/reports/registry.py` after `members`, so the portal lists it second. `test_report_registry.py` counts eight.
- `apps/accounts/roles.py` gains `ROLE_LABELS: dict[str, str]`, the seven labels §3 names in `ROLE_SLUGS` order, and `STAFF_ROLE_LABELS` for the six other than member. The frontend's `ROLE_LABELS` in `frontend/src/portal/choices.ts` already agrees; `backend/tests/test_roles_report.py` asserts the backend map's values.
- **Rows.** One `RoleRow` per (role, account) pair: every active account (`is_active=True`; a deactivated account is never listed, as the membership report never lists one) holding a role in `STAFF_ROLE_SLUGS`, once per such role. Sections are the six staff roles in `ROLE_SLUGS` order (least to most privileged), each present even when empty; within a section, rows are ordered by last name, first name, then email. A system administrator who also holds account administrator appears in both sections.
- **Filters**, read by a `RolesReportFilterSet` in `apps/accounts/api/filters.py` through `apply_filterset`, with `applied_filters` naming each for the PDF subtitle and the email: `search` (the same first-name, last-name, email match as the users list, every word matching), `role` (one staff role slug; the report then draws that one section), and `kind` (`member` or `friend`; a donor never holds a role). Any other query parameter is refused as the users list refuses it.
- **Columns**, in registry order with widths tuned so no seeded default cell wraps (`test_report_columns.py`): **Role** (default), **Name** (default), **Email** (default), **Phone** (default), **DART** (default), **Kind** (default; Member or Friend, from `account_kind()`), **Membership** (default; the membership state's label, Current, Expiring soon, Expired, or Friend, as the membership report's column reads it), **City**, **County**, **Home airport**. The rows read a profile that may be missing, exactly as the membership report's `_row_context` does; a missing profile leaves those cells blank.
- **The subscription form.** `frontend/src/portal/reports/types.ts` adds `'roles'` to `ReportSlug`; `definitions.ts` adds `REPORTS.roles` with `label: 'Roles'`, `choosable: true`, `periods: false`, and the filters `search` (placeholder `Name or email`), `role` (a `select` over the six staff roles, placeholder `Every role`), and `kind` (a `select` of Member and Friend, placeholder `Any kind`). `definitions.test.ts` lists the eighth slug. The API's `GET /reports` answers it for an account administrator (the treasurer does not read it); the subscription endpoints stay with `IsFinance`, so the account administrator sets the subscription up, and the recipient must hold user administrator or account administrator, or be a system administrator, as `recipient_may_read` already decides.
- **Docs.** `docs/developer/reports.rst`: a paragraph on sections under "The engine" and a "The roles report" section after the membership report's; `docs/developer/api-reports.rst`: a `roles` row in the slug table (title, roles `user_admin`, `account_admin`, chosen, no); `docs/user/admin/reports.rst#report-list`: the roles report joins the account administrator's list under "Setting one up", with one sentence on its sections; `docs/user/roles.rst`: the user administrator and account administrator sections mention the report; `docs/developer/scheduled-reports.rst` only if it enumerates reports.

### 5.3 Editing a subscription

- The API already allows it: `PATCH /reports/subscriptions/{id}` takes `filters`, `columns`, `formats`, `cadence`, `weekday`, and `is_active`, checks the filters and columns against the report, and moves `next_due_on` when the schedule changes. No backend change; `docs/developer/api-reports.rst#patch` gains one sentence saying the Subscriptions screen's Edit form sends the first five.
- **The screen.** Each row of the Subscriptions table gains an **Edit** quiet small button, first of its controls, before **Send now**. Pressing it opens the subscription form under the table in edit mode, headed *Edit subscription* (the form's `aria-label` follows), filled with the row's report, filters, columns, formats, schedule, and day. The report and the recipient are drawn as plain text in the form, since the API keeps both fixed; everything else edits as when creating. **Save** sends `PATCH` with `filters`, `columns`, `formats`, `cadence`, and `weekday` through `useUpdateSubscription`; on success the form closes and the table shows the change (the query is invalidated, as the other row actions do). **Cancel** closes it unchanged. A server refusal shows where the create form shows it: a filter's message under the filters through `filterErrors`, a columns message under the chooser, anything else above the buttons.
- One form at a time: **New subscription** closes an open edit, **Edit** on another row replaces the open form, and **Edit** on the row already being edited closes it. The stored `columns` list, empty for the defaults, fills the chooser as the defaults; Save sends the chooser's list as it stands, so an untouched chooser sends the stored list back unchanged.
- `SubscriptionForm` takes either `{ subscription }` to edit or nothing to create; `SubscriptionsCard` owns which. Tests in `SubscriptionForm.test.tsx` (edit mode shows the fixed report and recipient, prefills every field, sends the PATCH body, shows a filter refusal) and `SubscriptionsCard.test.tsx` (Edit opens the form for that row, the second Edit swaps, New subscription closes an edit, Save refreshes the row).
- `frontend/e2e/reports.spec.ts#edit`: a second step in the account administrator's flow edits the subscription just made, changing the schedule to weekly on Thursday, and reads *Weekly on Thursday* in the row.
- **Docs.** `docs/user/admin/reports.rst#edit`: "Each row carries four controls", an **Edit** entry among the row controls, and a "Changing one" subsection after "Setting one up" describing the form in edit mode and that the report and recipient cannot change (delete and set up again for those).

### 5.4 The Users and roles screen

- The account-status filter starts on **Active only** (`isActive` initial state `'true'`); its choices stay **Active and deactivated**, **Active only**, and **Deactivated only** in that order. The fields are drawn in the order **Search**, **Kind of account**, **Account status**. `UsersListPage.test.tsx` asserts the first request carries `is_active=true` and that the filters appear in that order.
- The screen gains what every other report's screen has: **Export CSV** and **Export PDF** links to `reportExportUrl('roles', ...)` carrying `search`, `role`, and `kind` (never `is_active`: the roles report lists active accounts only, and the docs say so), and a `ColumnChooser` for `roles` with the legend *Columns to export*, whose chosen keys go into `columns` on the links. They sit above the table where the members list puts them. Tests cover the links' query strings and that `is_active` is left out.
- **Docs.** `docs/user/admin/users.rst`: the "Finding an account" entries in the drawn order, **Account status** saying it starts on **Active only**, and an "Exporting the roles report" section (what the report is, its sections, that it lists active accounts whatever **Account status** shows, and where the same report can be sent on a schedule, linking `admin/reports`). `docs/user/admin/reports.rst` is not touched by this package.

### 5.5 Seed

- No seed change: the seeded staff accounts already hold every role, so each section of the roles report has at least one row after `make reset`. The closeout confirms it.

## 6. Failure handling and the final report

A package that cannot finish reports the reason under `open_problems`; the orchestrator decides whether to fix, re-run, or reduce. The closeout's PR body lists the three owner requests with the PR that settled each, and the orchestrator's report to the owner does the same.

## 7. Work packages

### Wave 1

#### roles-report (Opus)

- **Refs:** #298
- **Branch:** `feature/roles-report`; database `caldart_roles_report`; e2e port 8231
- **Owns:** `backend/caldart/reports.py#sections`, `backend/apps/accounts/reports.py` (new), `backend/apps/accounts/roles.py#labels`, `backend/apps/accounts/api/filters.py#roles-report`, `backend/apps/reports/registry.py`, `backend/tests/test_report_sections.py` (new), `backend/tests/test_roles_report.py` (new), `backend/tests/test_report_registry.py`, `backend/tests/test_report_columns.py#roles`, `backend/tests/test_openapi_contract*` (snapshot), `frontend/src/portal/reports/types.ts#slug`, `frontend/src/portal/reports/definitions.ts#roles`, `frontend/src/portal/reports/definitions.test.ts`, `frontend/src/portal/api/types.ts#roles`, `docs/developer/reports.rst`, `docs/developer/api-reports.rst#slug-table`, `docs/developer/scheduled-reports.rst#report-list`, `docs/user/admin/reports.rst#report-list`, `docs/user/roles.rst#roles-report`.
- **Steps:** §5.1 and §5.2 in full.
- **Verify:** `make test e2e`; `make lint`; after `make reset`, `GET /api/v1/reports/roles/export.pdf` as the seeded account administrator has six section headings in `ROLE_SLUGS` order and lists the seeded system administrator under System administrator; `GET /api/v1/reports/roles/export.csv?role=treasurer` has the treasurer rows alone; `GET /api/v1/reports` as the treasurer does not list `roles`.

#### subscription-edit (Opus)

- **Refs:** #298
- **Branch:** `feature/subscription-edit`; database `caldart_subscription_edit`; e2e port 8232
- **Owns:** `frontend/src/portal/features/admin-reports/SubscriptionForm.tsx`, `frontend/src/portal/features/admin-reports/SubscriptionForm.test.tsx`, `frontend/src/portal/features/admin-reports/SubscriptionsCard.tsx`, `frontend/src/portal/features/admin-reports/SubscriptionsCard.test.tsx`, `frontend/src/portal/reports/api.ts#update` (only if the hook needs a change), `frontend/src/test/handlers.ts#subscriptions`, `frontend/e2e/reports.spec.ts#edit`, `docs/user/admin/reports.rst#edit`, `docs/developer/api-reports.rst#patch`, `docs/developer/architecture.rst#subscriptions` (only if it describes the card's controls).
- **Steps:** §5.3 in full.
- **Verify:** `make test e2e`; `make lint`; on the running portal as the seeded account administrator, edit a subscription's schedule and a filter, save, and read both in the row and in `GET /api/v1/reports/subscriptions`.

### Wave 2

#### users-screen (Opus)

- **Refs:** #298
- **After:** roles-report
- **Branch:** `feature/users-screen`; database `caldart_users_screen`; e2e port 8233
- **Owns:** `frontend/src/portal/features/admin-users/UsersListPage.tsx`, `frontend/src/portal/features/admin-users/UsersListPage.test.tsx`, `frontend/src/portal/features/admin-users/api.ts#exports` (only if a hook is needed), `docs/user/admin/users.rst`.
- **Steps:** §5.4 in full.
- **Verify:** `make test e2e`; `make lint`; on the running portal as the seeded user administrator, the screen opens on Active only with the fields in the drawn order, and Export PDF downloads the roles report with the screen's search and role.

### Wave 3

#### closeout (Sonnet)

- **Closes:** #298
- **After:** roles-report, subscription-edit, users-screen
- **Branch:** `chore/roles-report-closeout`; database `caldart_roles_closeout`; e2e port 8234
- **Owns:** `docs/**#residue`, `frontend/src/**#residue`, `backend/**#residue`, `plans/2026-09-26-roles-report-and-subscription-editing.md` (moves to `plans/archive/`).
- **Steps:** on `main` after `make reset`, run the owner's three requests end to end: subscribe the seeded account administrator to the roles report, send it now, and read the six sections in the emailed PDF; edit that subscription's filters and schedule and read them back; open Users and roles and confirm Active only is selected and sits after Kind of account. Read every docs page the wave-1 and wave-2 packages touched once more against the running portal. Move the plan to the archive. The PR body lists each request with the PR that settled it.
- **Verify:** `make lint test check docs audit e2e` green.

## 8. Manifest

```json
[
  {"wave": 1, "package": "roles-report", "model": "opus", "branch": "feature/roles-report", "database": "caldart_roles_report", "e2e_port": 8231, "closes": [], "refs": [298], "after": []},
  {"wave": 1, "package": "subscription-edit", "model": "opus", "branch": "feature/subscription-edit", "database": "caldart_subscription_edit", "e2e_port": 8232, "closes": [], "refs": [298], "after": []},
  {"wave": 2, "package": "users-screen", "model": "opus", "branch": "feature/users-screen", "database": "caldart_users_screen", "e2e_port": 8233, "closes": [], "refs": [298], "after": ["roles-report"]},
  {"wave": 3, "package": "closeout", "model": "sonnet", "branch": "chore/roles-report-closeout", "database": "caldart_roles_closeout", "e2e_port": 8234, "closes": [298], "refs": [], "after": ["roles-report", "subscription-edit", "users-screen"]}
]
```
