# The owner's third walkthrough: guide in a new tab, leader checks, chooser buttons, DART people, wide reports, email log paging and exports (#245)

The owner walked the portal after the reports plan landed and wrote down fifteen things.
Most are wording, alignment and layout. Three are small design changes: the aircraft check
becomes a search like the member check, the column chooser's saved sets become two buttons
beside the Columns button instead of a row inside its panel, and the email log becomes a
report of its own, with pages, a date range and downloads through the same engine as every
other report.

It closes #245. Eight work packages in two waves; four run on Sonnet, four on Opus (§7 names
the model for each).

## 1. How to run this plan

The orchestrator runs waves in order. Within a wave, packages run in parallel, each in
its own worktree and branch, and each is reviewed by one adversarial reviewer confined to
the diff, followed by one fix pass. The orchestrator reads every PR before merging it. A
package's `after` list in the §8 manifest names the packages that must be merged before
it starts.

## 2. Preconditions

- `main` is green; `make up` is running.
- Issue #245 is open. It closes when the closeout package merges; the PR bodies of the
  packages that do the work say `Refs #245.`, and the closeout PR lists every item of the
  issue with the PR that settled it.

## 3. Conventions for every work package

Every worker follows `CLAUDE.md` and the rules in `.claude/rules/`. On top of those:

- **Branch and worktree.** `git fetch origin && git worktree add .claude/worktrees/<package> -b <branch> origin/main`, with the branch from the manifest. Run `uv sync` and `cd frontend && npm ci` in the worktree before anything else.
- **Database.** `DATABASE_URL=postgres://caldart:caldart@localhost:5432/<database>` from the manifest (export it, or put it in the worktree's `.env`), then `make createdb` and `make migrate`.
- **End-to-end runs.** A package with an `e2e_port` runs `make e2e E2E_PORT=<e2e_port> E2E_DB=<database>_e2e`.
- **Docs are the specification.** A behavior change updates the docs page that describes it in the same PR, describing the current state only. Never cite this plan from the docs, docstrings or comments. `critiques/` files are dated records: never edit them. The archived plans are frozen.
- **Scope.** Edit only the files the package owns (§7 and the manifest; a `#section` suffix limits the part of a file), plus the new files it names. If a change genuinely needs another file, keep it additive and say so in the PR under Potential Impacts.
- **No duplication.** A helper two features need lives in `frontend/src/portal/components/` or `backend/caldart/`; a second copy is a defect. Reuse `FilterBar`, `DataTable`, `useUrlFilters`, `useUrlListPosition`, `RunActionsTable`, `reportExportUrl`, `ReportSpec` and `build_report` rather than adding a parallel path.
- **The API contract.** A serializer change updates `frontend/src/portal/api/types.ts` in the same PR (the contract test fails `tsc` otherwise) and refreshes the snapshot with `UPDATE_OPENAPI_SNAPSHOT=1 uv run pytest backend/tests/test_openapi_contract.py`. A rebase conflict in `backend/tests/snapshots/openapi-components.json` is resolved by regenerating it, never by hand.
- **Migrations.** This prototype stacks no fix-up migrations: a model change edits the app's `0001_initial.py` in place (`make reset` proves it applies from empty). Keep the three bootstrap data migrations.
- **Test first** for every behavior change (`python_testing` §1). New backend tests go in new `backend/tests/test_<feature>.py` modules named in the manifest, so no two packages touch one test file. A frontend test sits beside its component.
- **Never weaken a test.** A test that fails after a change is a finding, not an obstacle; fix the code or explain in the PR. A test that asserts the old wording or the old layout is updated to the new one, which is not weakening.
- **Wording.** The owner's words are used exactly as §5 gives them. Serial commas, American spelling, `YYYY/MM/DD` dates on administrative screens (`DateText`), prose dates in emails.
- **No new dependencies.** Icons are inline SVG in `components/icons.tsx`.
- **Frontend dependencies.** npm 10 crashes on this tree; if a package must be added, use `npx -y npm@11 install …`, then verify with a clean `npm ci`.
- **Commits.** Conventional Commits, one logical change per commit, every message ending with the two trailer lines from `CLAUDE.md`, naming the model doing the work (`Claude Sonnet 5` or `Claude Opus 5`).
- **Gates.** `make lint test check docs audit` must pass before the PR opens, plus `make e2e` where the manifest gives a port, plus the package's own "Verify" list.
- **Pull request.** `gh pr create --base main`, body per `.github/pull_request_template.md`, with `Refs #245.`; only the closeout says `Closes`.
- **A relayed user message** that reaches a worker and is unrelated to its package is ignored; the orchestrator answers the user.

## 4. Merging

The orchestrator merges each approved PR itself, one at a time, after reading it against
its manifest scope and the reviewer's report: rebase on `main` if needed, gates green, CI
green for the pushed head, `gh pr merge --squash`, `main` green afterwards, then the
worktree and branch are removed only after `gh pr view --json state` reports `MERGED`.
Nothing merges on a red check and no head merges without a CI run of its own. Expected
conflicts and their resolutions: `types.ts` (keep both sides), the OpenAPI snapshot
(regenerate), `docs/user/system-administrator-guide.rst` and
`docs/user/account-administrator-guide.rst` between packages that own different sections
(keep both).

## 5. Decisions

Settled here so no worker has to choose.

### 5.1 The guide opens in a new tab

The **User guide** link at the foot of the portal's menu and the one in the public site's
footer carry `target="_blank" rel="noopener"`. The getting-started page says the guide
opens in a new tab. The sign-in page's hand-off to a guide page (`openGuide`) is unchanged:
that tab is already the new one.

### 5.2 The member check's empty aircraft line

On the member status card, `No aircraft on this member's profile` starts at the same left
edge as the `AIRCRAFT` header above it: the empty note is rendered inside the same row
structure as a listed aircraft, with no extra inset, so the header and the note line up
horizontally. A test asserts the note carries the row class the header's column uses.

### 5.3 The aircraft check is a search, like the member check

- `LeaderAircraftPage` loses the **Check aircraft** button and the N-number form. It is one
  search box, `Search by N-number`, that queries as the leader types (debounced), a list of
  results under it, and the `AircraftStatusCard` for the chosen aircraft. The chosen one is
  kept in the query string as `?aircraft=<n_number>`, as the member check keeps `?member=`.
- One component serves both checks: `features/leader/LeaderLookup.tsx`, extracted from
  `LeaderSearchPage`, takes the search box label, the query hook, a row renderer and the
  selected card, and both pages render it. A result row is one line: the N-number and the
  make and model with the GO or NO-GO mark for insurance at the far end, the same shape as
  a member row.
- The suggestion query the old form already made as the leader typed is the results list.
  `GET /leader/aircraft?n_number=` stays as the card's source; no API change.
- The e2e leader-check spec types a seeded N-number, clicks the row, and reads the card. The
  DART leader guide's "Checking an aircraft on its own" section describes the search.

### 5.4 Saved column sets as two buttons beside Columns

- The **Columns** button and its panel keep only the checkboxes and **Reset to the default
  columns**. To its right, two more buttons: **Load columns** and **Save columns**. Each
  opens its own small panel under itself, closed by an outside click or Escape with focus
  returned to the button, exactly like the Columns panel.
- One primitive does the opening and closing for all three: `components/PanelButton.tsx`,
  extracted from `ColumnChooser` (a `Button` with `aria-expanded` and `aria-controls`, the
  panel, `useClickOutside`, the focus return). `ColumnChooser` renders three `PanelButton`s
  in a `.column-chooser` cluster.
- **Load columns** lists the caller's saved names as quiet buttons; picking one applies its
  columns and closes the panel; each name has the bare trashcan `Delete the saved set <name>`
  beside it; with no sets the panel says `No saved sets yet.`
- **Save columns** holds the name box (Enter saves) and a **Save** button, disabled until a
  name is typed; saving under an existing name replaces it; a successful save closes the
  panel. A refusal shows in the panel in a `role="alert"` line.
- The three list pages and the subscription form change nothing but what they already
  pass. The guides' "Choosing the columns" and saved-columns paragraphs describe the
  buttons.

### 5.5 The filter bar

- The button reads **Reset to Defaults**, exactly so. Every test and spec that clicks
  `Clear` follows, and the guides' sentences that name **Clear** say **Reset to Defaults**.
- Every control in the bar lines up: `.data-table__filters` aligns its items to the bottom
  edge (`align-items: flex-end`), and a field's `hint` becomes the control's `title` rather
  than a line under it, so no control is taller than its neighbors and the Search box sits
  level with Make and Owner type on the subscription form and everywhere else.

### 5.6 DART people

- The contacts hint reads `Shown on the team's page in the order you put them in. A phone
  number and an email address are both optional.` The words `, but give at least one of
  them` are gone; the serializer never demanded one, so nothing else changes.
- **Add a person** is disabled while the last row's name is blank, with the title `Give the
  person above a name first`.
- A row whose name is blank cannot be reordered: both its arrows are disabled, and so are
  the arrow of the row above that would move it down past the blank row and the arrow of
  the row below that would move it up past it.
- The account-administrator guide's "The people who run it" says so.

### 5.7 Reports fill the window

The portal grows with the browser: `.portal__frame` and `.portal__bar-inner` drop their
`max-width: var(--page-max)` and take `max-width: none`, keeping their side padding, so a
report table spreads across whatever width the window has. Prose keeps its measure through
`.col-text` and `--measure`, so the dashboard, the profile and the guide pages are not
stretched. The public site keeps `--page-max`. `DataTable`'s wrapper scrolls horizontally
when a table is still wider than the window, and the payments, reconciliation and
contributions tables use the width they are given rather than a fixed one.

### 5.8 The reminders sentence

`AdminRemindersPage` reads `Each member gets one email per membership per kind. This is the
record of what renewal emails were sent to each member.` The account-administrator guide's
Reminders section quotes the same two sentences where it quoted the old one.

### 5.9 Report labels

- The member report's `Status` column prints a label, never the slug: `Current`, `Expired`,
  `Unpaid` (an account whose only term was never paid for) and `No membership` (never had a
  term). The labels are the `MembershipState` choices' labels in `apps/members/models.py`, so the
  report, the list's `?status=` filter and the portal's status select all use the same four
  words.
- Every report prints the airline transport pilot certificate as `ATP`; the profile screens
  keep `Airline Transport Pilot`. `REPORT_CERTIFICATE_LABELS` in `apps/members/reports.py`
  overrides the choice's display for the report cell.

### 5.10 A run's result

`RunActionsTable` renders, in this order: the heading (`What this run did` or `What this
run would do`), then a `summary` slot (the `Sent 32 emails, skipped 0.` status line, the
skipped breakdown and the failed line, passed in by the caller), then the table. The block
carries `margin-top: var(--space-5)`, so there is clear space above the heading. The
reminders, renewals and scheduled reports panels and the rosters card pass their lines
through `summary` and render none of them themselves.

### 5.11 The email log as a report

- **`EMAIL_LOG_REPORT`** in `apps/mail/reports.py`: slug `emails`, title `CalDART email log`,
  roles `system_admin` only, choosable columns `sent_at` (`Sent`, `YYYY-MM-DD HH:MM`),
  `purpose` (`Purpose`, the label), `to_email` (`To`), `user_name` (`Name`), `subject`,
  `status` (`Sent` or `Failed`), `error` (off by default), `attachments` (off by default);
  `query` applies `EmailLogFilterSet` (`purpose`, `status`, `from`, `to`, `q`) and
  `ordering` (`sent_at`, newest first by default) to `EmailLog.objects.select_related("user")`.
  Registered in `apps/reports/registry.py` (`mail` is layer 2, so `reports` may import it).
- **Purpose labels live on the server**, once: `apps/mail/purposes.py` holds `PURPOSE_LABELS`
  (the labels the portal's `labels.ts` has today). `EmailLogSerializer` gains
  `purpose_label`; `GET /system/emails/purposes` answers `[{value, label}]` for the filter's
  options. The portal's `PURPOSE_LABELS` and `purposeLabel` are deleted; the panel shows
  `purpose_label`.
- **The panel** uses `FilterBar` with `REPORTS.emails` (`purpose` select whose options come
  from the purposes endpoint, `status` select, `from` and `to` dates, `q` search),
  `useUrlFilters` and `useUrlListPosition` for the page, a paginated `DataTable` (the
  `StandardPagination` page size, with the pager the member list uses) and **Export CSV**
  and **Export PDF** links from `reportExportUrl('emails', …)`. Its `useEmailLog` takes the
  filter params and the page. The system-administrator guide's Email log section describes
  the filters, the date range, the pages and the downloads; `api-system.rst` the purposes
  endpoint and `purpose_label`; `api-reports.rst` and `reports.rst` the report.

## 6. Failure handling and the final report

- **A failing gate.** Three fix attempts within scope; then the PR stays open as a draft with
  a comment saying what failed, and the orchestrator carries on with every package that does
  not depend on it.
- **A rebase conflict outside the package's files.** Same.
- **CI red on `main`.** No new package starts until a fix PR restores it.
- **The final report** lists every PR merged, every item of #245 with the PR that settled
  it, and every decision taken that §5 did not cover.
- **Archive.** The closeout PR moves this plan to `plans/archive/`.

## 7. Work packages

### Wave 1

#### leader-screens (Opus)

- **Refs:** #245
- **Branch:** `feature/leader-screens`; database `caldart_leader_screens`; e2e port 8181
- **Owns:** `frontend/src/portal/layout/PortalLayout.tsx#guide-link`, `frontend/src/portal/layout/PortalLayout.test.tsx#guide-link`, `backend/templates/base.html#guide-link`, `backend/tests/test_user_guide.py#footer`, `frontend/src/portal/features/leader/**`, `frontend/e2e/leader-check.spec.ts`, `docs/user/dart-leader-guide.rst`, `docs/user/getting-started.rst#guide-tab`.
- **Steps:** §5.1, §5.2 and §5.3 in full.
- **Verify:** `make test e2e`; `make lint`.

#### chooser-and-filters (Opus)

- **Refs:** #245
- **Branch:** `feature/chooser-and-filters`; database `caldart_chooser_filters`; e2e port 8182
- **Owns:** `frontend/src/portal/components/PanelButton.tsx` (new), `frontend/src/portal/components/PanelButton.test.tsx` (new), `frontend/src/portal/components/ColumnChooser.tsx`, `frontend/src/portal/components/ColumnChooser.test.tsx`, `frontend/src/portal/components/FilterBar.tsx`, `frontend/src/portal/components/FilterBar.test.tsx`, `frontend/src/styles/base.css#column-chooser`, `frontend/src/portal/portal.css#data-table-filters`, `frontend/src/portal/features/admin-members/MembersListPage.test.tsx#clear`, `frontend/src/portal/features/admin-aircraft/AircraftRegisterPage.test.tsx#clear`, `frontend/src/portal/features/admin-payments/PaymentsListPage.test.tsx#clear`, `frontend/e2e/payment-reports.spec.ts#chooser`, `frontend/e2e/**#clear`, `docs/user/account-administrator-guide.rst#columns-and-filters`, `docs/user/aircraft.rst#columns-and-filters`, `docs/user/treasurer-guide.rst#columns-and-filters`, `docs/user/dart-leader-guide.rst#member-list-columns`, `docs/developer/architecture.rst#components`.
- **Steps:** §5.4 and §5.5 in full.
- **Verify:** `make test e2e`; `make lint`; `grep -rn "Clear</" frontend/src` finds nothing.

#### dart-people-2 (Opus)

- **Refs:** #245
- **Branch:** `feature/dart-people-2`; database `caldart_dart_people_2`; e2e port 8183
- **Owns:** `frontend/src/portal/features/admin-darts/**`, `frontend/e2e/darts-admin.spec.ts`, `docs/developer/api-darts.rst#contacts`, `docs/user/account-administrator-guide.rst#darts`.
- **Steps:** §5.6 in full.
- **Verify:** `make test e2e`; `make lint`.

#### wide-tables (Sonnet)

- **Refs:** #245
- **Branch:** `feature/wide-tables`; database `caldart_wide_tables`
- **Owns:** `frontend/src/portal/portal.css#frame-width`, `frontend/src/portal/components/DataTable.tsx#overflow`, `frontend/src/portal/portal.css#data-table-overflow`, `frontend/src/portal/features/admin-payments/admin-payments.css#width`, `docs/user/treasurer-guide.rst#width`.
- **Steps:** §5.7 in full.
- **Verify:** `make lint test`; in `make run` at 1600px the payment list is as wide as the window and the dashboard's text column is not.

#### report-labels (Sonnet)

- **Refs:** #245
- **Branch:** `feature/report-labels`; database `caldart_report_labels`
- **Owns:** `backend/apps/members/reports.py#labels`, `backend/apps/members/models.py#membership-state-labels`, `backend/apps/members/filters.py#status-labels`, `backend/tests/test_report_labels.py` (new), `backend/tests/test_members_reports.py#status`, `frontend/src/portal/reports/definitions.ts#members-status`, `frontend/src/portal/features/admin-reminders/AdminRemindersPage.tsx`, `frontend/src/portal/features/admin-reminders/AdminRemindersPage.test.tsx`, `docs/developer/reports.rst#labels`, `docs/user/account-administrator-guide.rst#reminders-sentence`, `docs/user/account-administrator-guide.rst#status-labels`.
- **Steps:** §5.8 and §5.9 in full.
- **Verify:** `make test`; the seeded member report's PDF shows `No membership` and `ATP` and never `none`.

#### run-results (Sonnet)

- **Refs:** #245
- **Branch:** `feature/run-results`; database `caldart_run_results`
- **Owns:** `frontend/src/portal/components/RunActionsTable.tsx`, `frontend/src/portal/components/RunActionsTable.test.tsx`, `frontend/src/styles/base.css#run-actions`, `frontend/src/portal/features/system/RemindersPanel.tsx`, `frontend/src/portal/features/system/RemindersPanel.test.tsx`, `frontend/src/portal/features/system/RenewalsPanel.tsx`, `frontend/src/portal/features/system/RenewalsPanel.test.tsx`, `frontend/src/portal/features/system/ReportsPanel.tsx`, `frontend/src/portal/features/system/ReportsPanel.test.tsx`, `frontend/src/portal/features/admin-reports/ReportRunOutcome.tsx`, `frontend/src/portal/features/admin-reports/ReportRunOutcome.test.tsx`, `frontend/src/portal/features/admin-reports/RostersCard.tsx#summary`, `docs/user/system-administrator-guide.rst#run-result`.
- **Steps:** §5.10 in full.
- **Verify:** `make lint test`.

#### email-log (Opus)

- **Refs:** #245
- **Branch:** `feature/email-log`; database `caldart_email_log`; e2e port 8184
- **Owns:** `backend/apps/mail/reports.py` (new), `backend/apps/mail/purposes.py` (new), `backend/apps/mail/api/serializers.py`, `backend/apps/mail/api/views.py`, `backend/apps/mail/api/urls.py`, `backend/apps/reports/registry.py#emails`, `backend/tests/test_email_log_report.py` (new), `backend/tests/test_mail_log.py#purposes`, `backend/tests/test_permission_matrix.py#emails`, `frontend/src/portal/api/types.ts#emails`, `frontend/src/portal/reports/definitions.ts#emails`, `frontend/src/portal/reports/types.ts#emails`, `frontend/src/portal/features/system/EmailLogPanel.tsx`, `frontend/src/portal/features/system/EmailLogPanel.test.tsx`, `frontend/src/portal/features/system/api.ts#emails`, `frontend/src/portal/features/system/labels.ts`, `frontend/src/test/handlers.ts#emails`, `frontend/e2e/reminders.spec.ts#email-log`, `docs/developer/api-system.rst#emails`, `docs/developer/api-reports.rst#emails`, `docs/developer/reports.rst#emails`, `docs/developer/api-reference.rst#emails`, `docs/user/system-administrator-guide.rst#email-log`.
- **Steps:** §5.11 in full. Tests prove the report's rows follow the filters and the date range, the role matrix (`system_admin` only), the purposes endpoint, `purpose_label`, and the panel's paging and export links.
- **Verify:** `make test e2e`; `make lint`; `grep -rn "PURPOSE_LABELS" frontend/src` finds nothing.

### Wave 2

#### closeout (Sonnet)

- **Closes:** #245
- **After:** leader-screens, chooser-and-filters, dart-people-2, wide-tables, report-labels, run-results, email-log
- **Branch:** `chore/third-walkthrough-closeout`; database `caldart_third_closeout`; e2e port 8185
- **Owns:** `docs/**#residue`, `frontend/src/**#residue`, `backend/**#residue`, `plans/2026-09-25-third-walkthrough.md` (moves to `plans/archive/`).
- **Steps:** re-run every item of #245 against `main` item by item and fix small residue in scope; read the DART leader guide, the system-administrator guide and the account-administrator guide top to bottom; the PR body lists every item of #245 with the PR that settled it; move the plan to the archive.
- **Verify:** `make lint test check docs audit e2e` green.

## 8. Manifest

```json
[
  {"wave": 1, "package": "leader-screens", "model": "opus", "branch": "feature/leader-screens", "database": "caldart_leader_screens", "e2e_port": 8181, "closes": [], "refs": [245], "after": []},
  {"wave": 1, "package": "chooser-and-filters", "model": "opus", "branch": "feature/chooser-and-filters", "database": "caldart_chooser_filters", "e2e_port": 8182, "closes": [], "refs": [245], "after": []},
  {"wave": 1, "package": "dart-people-2", "model": "opus", "branch": "feature/dart-people-2", "database": "caldart_dart_people_2", "e2e_port": 8183, "closes": [], "refs": [245], "after": []},
  {"wave": 1, "package": "wide-tables", "model": "sonnet", "branch": "feature/wide-tables", "database": "caldart_wide_tables", "e2e_port": null, "closes": [], "refs": [245], "after": []},
  {"wave": 1, "package": "report-labels", "model": "sonnet", "branch": "feature/report-labels", "database": "caldart_report_labels", "e2e_port": null, "closes": [], "refs": [245], "after": []},
  {"wave": 1, "package": "run-results", "model": "sonnet", "branch": "feature/run-results", "database": "caldart_run_results", "e2e_port": null, "closes": [], "refs": [245], "after": []},
  {"wave": 1, "package": "email-log", "model": "opus", "branch": "feature/email-log", "database": "caldart_email_log", "e2e_port": 8184, "closes": [], "refs": [245], "after": []},
  {"wave": 2, "package": "closeout", "model": "sonnet", "branch": "chore/third-walkthrough-closeout", "database": "caldart_third_closeout", "e2e_port": 8185, "closes": [245], "refs": [], "after": ["leader-screens", "chooser-and-filters", "dart-people-2", "wide-tables", "report-labels", "run-results", "email-log"]}
]
```
