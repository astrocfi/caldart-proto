# The owner's walkthrough: profile, aircraft, money, member check, reports and DARTs (#204)

After the payments build the owner walked every portal screen and wrote down what was
wrong. This plan settles the whole list: narrow phone boxes and stray wording on the
profile, an aircraft picker that offers two "add" buttons, a rail that marks two entries as
current, text buttons where a trashcan belongs, an automatic-renewal card that has no answer
for a life member, emails that never say when the next charge falls, dry runs that report
counts but not who would have been emailed, a member check that hides the go/no-go behind a
click, member sorts with no secondary key, a membership PDF that wraps, member and aircraft
reports without the column chooser the payments page has, role slugs shown raw, and a DART
screen with a Town field nobody wants, a Delete button in the wrong place and people who
cannot be reordered.

It closes #204 and refs #155 (the column chooser is one of its asks). Nine work packages in
three waves; two run on Sonnet, seven on Opus (§7 names the model for each).

## 1. How to run this plan

The orchestrator runs waves in order. Within a wave, packages run in parallel, each in
its own worktree and branch, and each is reviewed by one adversarial reviewer confined to
the diff, followed by one fix pass. The orchestrator reads every PR before merging it. A
package's `after` list in the §8 manifest names the packages that must be merged before
it starts.

## 2. Preconditions

- `main` is green; `make up` is running.
- Issue #204 is open. It closes when the closeout package merges; the PR bodies of the
  packages that do the work say `Refs #204.`, and the closeout PR lists every item of the
  issue with the PR that settled it.

## 3. Conventions for every work package

Every worker follows `CLAUDE.md` and the rules in `.claude/rules/`. On top of those:

- **Branch and worktree.** `git fetch origin && git worktree add .claude/worktrees/<package> -b <branch> origin/main`, with the branch from the manifest. Run `uv sync` and `cd frontend && npm ci` in the worktree before anything else.
- **Database.** `DATABASE_URL=postgres://caldart:caldart@localhost:5432/<database>` from the manifest (export it, or put it in the worktree's `.env`), then `make createdb` and `make migrate`.
- **End-to-end runs.** A package with an `e2e_port` runs `make e2e E2E_PORT=<e2e_port> E2E_DB=<database>_e2e`.
- **Docs are the specification.** A behavior change updates the docs page that describes it in the same PR, describing the current state only. Never cite this plan from the docs, docstrings or comments. `critiques/` files are dated records: never edit them. The archived plans are frozen.
- **Scope.** Edit only the files the package owns (§7 and the manifest; a `#section` suffix limits the part of a file), plus the new files it names. If a change genuinely needs another file, keep it additive and say so in the PR under Potential Impacts.
- **The API contract.** A serializer change updates `frontend/src/portal/api/types.ts` in the same PR (the contract test fails `tsc` otherwise) and refreshes the snapshot with `UPDATE_OPENAPI_SNAPSHOT=1 uv run pytest backend/tests/test_openapi_contract.py`. A rebase conflict in `backend/tests/snapshots/openapi-components.json` is resolved by regenerating it, never by hand.
- **Migrations.** This prototype stacks no fix-up migrations: a model change edits the app's `0001_initial.py` by regenerating it (`make reset` proves it applies from empty). Keep the three bootstrap data migrations (`accounts/0002_seed_roles.py`, `cms/0002_site_root.py`, `cms/0003_website_admin_permissions.py`).
- **Test first** for every behavior change (`python_testing` §1). New backend tests go in new `backend/tests/test_<feature>.py` modules named in the manifest, so no two packages touch one test file. A frontend test sits beside its component.
- **Never weaken a test.** A test that fails after a change is a finding, not an obstacle; fix the code or explain in the PR. A test that asserts the old wording is updated to the new wording, which is not weakening.
- **Wording.** The owner's words are used exactly as §5 gives them. Serial commas, American spelling, `YYYY/MM/DD` dates on administrative screens (the `DateText` component), prose dates in member-facing emails.
- **No new dependencies** unless §5 names one (it names none): the trashcan is an inline SVG, reordering is two buttons.
- **Frontend dependencies.** npm 10 crashes on this tree; if a package must be added, use `npx -y npm@11 install …`, then verify with a clean `npm ci`.
- **Commits.** Conventional Commits, one logical change per commit, every message ending with the two trailer lines from `CLAUDE.md`, naming the model doing the work (`Claude Sonnet 5` or `Claude Opus 5`).
- **Gates.** `make lint test check docs audit` must pass before the PR opens, plus `make e2e` where the manifest gives a port, plus the package's own "Verify" list.
- **Pull request.** `gh pr create --base main`, body per `.github/pull_request_template.md`, with `Refs #204.` (and `Refs #155.` where the manifest says so); only the closeout says `Closes`.
- **A relayed user message** that reaches a worker and is unrelated to its package is ignored; the orchestrator answers the user.

## 4. Merging

The orchestrator merges each approved PR itself, one at a time, after reading it against
its manifest scope and the reviewer's report: rebase on `main` if needed, gates green, CI
green for the pushed head, `gh pr merge --squash`, `main` green afterwards, then the
worktree and branch are removed only after `gh pr view --json state` reports `MERGED`.
Nothing merges on a red check and no head merges without a CI run of its own. Expected
conflicts and their resolutions: `types.ts` (keep both sides), the OpenAPI snapshot
(regenerate), `docs/developer/index.rst` (keep both sides).

## 5. Decisions

Settled here so no worker has to choose.

### 5.1 Shared portal pieces

- **The trashcan.** `frontend/src/portal/components/DeleteButton.tsx` exports `DeleteButton`, a `Button` (quiet, small by default; `variant` may be `danger`) whose first child is an inline SVG trashcan (`aria-hidden`, drawn in `currentColor`, `1em` square, no library). Props: `label` (required: the accessible name, e.g. "Remove N12345" or "Delete this DART"), optional `children` (text shown after the icon), and every `ButtonProps` field (`onClick`, `disabled`, `title`, `type`, `variant`, `small`). With no children the button is icon-only, square (`.button--icon` in `base.css`: equal padding, no text), with `aria-label={label}` and `title={label}`; with children the text follows the icon and `label` is not repeated as `aria-label`. Every Remove or Delete control in the portal uses it: icon-only where the control sits in a row or a form line (an attached aircraft, a person on a DART), icon with text where the action is destructive and confirmed (delete an aircraft record, delete a member, delete a DART). The confirmation buttons ("Yes, delete it", "Delete for good", "Keep") keep their text and do not take the icon.
- **Click outside.** `frontend/src/portal/components/useClickOutside.ts` exports `useClickOutside(ref, onOutside, isActive)`: while `isActive`, a `pointerdown` outside `ref.current` and an `Escape` keydown call `onOutside`. The column chooser uses it; so may any later popover.
- **The column chooser moves to the shared components** as `frontend/src/portal/components/ColumnChooser.tsx` (with `defaultColumnKeys` and `toggleColumn`, its test file, and its `.column-chooser*` rules moved from `admin-payments.css` into `base.css`). It closes on a click outside and on Escape; the Columns button still toggles it. The finance list imports it from the new path.
- **Role labels.** `ROLE_CHOICES` and `roleLabel` move from `features/admin-members/choices.ts` to the shared `frontend/src/portal/choices.ts`, and gain `treasurer` ("Treasurer"). The labels are: Member, DART leader, User administrator, Treasurer, Account administrator, Website administrator, System administrator. Every place that rendered a slug (the users list chips and filter buttons, the user detail checkboxes, the 403 sentence in `auth/guards.tsx`, the member detail) renders `roleLabel(slug)`. Nothing in the UI shows an underscore or a lowercase role again.
- **The rail.** `NAV_ITEMS` entries `/profile` and `/leader` take `end: true`, so My aircraft does not also mark My profile and Aircraft check does not also mark Member check. `PortalLayout.test.tsx` asserts that at `/profile/aircraft` exactly one link carries `aria-current="page"`.

### 5.2 Profile and My aircraft

- **Phone boxes.** `.field-pair .field-pair__main` is `16ch` wide and `.field-pair .field-pair__extension input` is `9ch` (the inputs are `border-box`, so the widths include the padding; `415-555-0100` and a six-digit extension fit with room). The DART form's contact phone is untouched.
- **Hints.** Home airport: `Three characters, omit the leading K`. DART: label `DART`, hint `Your primary DART`. `member-guide.rst` follows.
- **The volunteer note** stays one sentence pair on one line: `.profile-form__note { max-width: none; }` (the paragraph measure in `base.css` is what wrapped it).
- **"Ground support"** replaces "Ground team" in `VOLUNTEER_INTERESTS` (field name unchanged), the test's label table, and `member-guide.rst`.
- **My aircraft lede** is `The planes you commonly fly.` and nothing more.
- **The aircraft picker** (`features/aircraft/AircraftPicker.tsx`) renders, in this order under the search field: the visually hidden status line; while searching, `Searching…`; when the search has results, a paragraph `Click on an aircraft to add it to your list.` followed by the results list; when the search found nothing, the empty state titled `No aircraft matches that` with the description `If the plane is not in the register yet, add it below.` and **no** action button; then the "already on your list" note; then one `Add an aircraft` button at the normal size (no `small`), with its `Not in the register? Add it yourself.` note, which opens the inline form as today. The second "Add a new aircraft" button no longer exists. `aircraft.rst` describes the new order.
- **Remove** on an attached aircraft is a `DeleteButton` labeled `Remove <N-number>`.

### 5.3 Contribution-only mandates and the next charge date

- **A life member's standing authority is a contribution.** `RenewalMandate.plan` becomes nullable (`null=True, blank=True`; `payments/0001_initial.py` regenerated). `plan` null means the member holds a lifetime term and the mandate charges `contribution_cents` once a year; nothing renews. The model docstring says so.
- **Kind.** `apps/payments/renewals.py` gains `MandateKind` (`RENEWAL = "renewal"`, `BOTH = "both"`, `CONTRIBUTION = "contribution"`) and `mandate_kind(mandate)`: `contribution` when `plan` is null, `both` when a plan and a contribution, `renewal` otherwise. `kind_label(kind)` gives the words every email and screen uses: `renewal`, `renewal and contribution`, `contribution`. The mandate serializer exposes `kind`; `plan` and `plan_name` are null for a contribution-only mandate.
- **What may be set up.** `check_renewable(plan, provider, *, user, contribution_cents)`: a member with an active lifetime term may hold only a contribution-only mandate (a plan is refused with `A life member's membership does not renew; choose a contribution instead.`, and a zero contribution with `A contribution to charge each year is needed.`); a member without one needs a plan with a duration, as today. The same rule guards `POST /me/renewal/setup`, `PATCH /me/renewal`, and the checkout's `auto_renew`. All three errors are keyed by `auto_renew`.
- **Checkout for a life member.** `POST /payments/checkout` refuses a `plan` for a member whose current term is a lifetime one, keyed by `plan`: `You are a life member, so there is nothing to renew. Make a contribution instead.` A contribution-only checkout with `auto_renew` true creates a contribution-only pending mandate and activates it on success, as an annual one is today.
- **`PATCH /me/renewal`** takes `{plan?, contribution_cents}`: `plan` (a slug, or absent) changes the plan that renews for a member with a dated term, and is refused for a life member; `contribution_cents` as today. The response is the mandate envelope.
- **Amount.** `renewal_amount_cents` is the plan's price when there is a plan, plus the contribution.
- **The next charge is never unknown while a mandate is active.** `next_charge_on(mandate, today)` returns `None` only for a mandate that is not `active`. For an active one, in order: the earliest `scheduled` attempt's date; for a contribution-only mandate, `contribution_charge_date(mandate, today)`; for a member with a dated current term, the charge date of that term; otherwise (the term has already run out and the next scan will charge it) `today`. `contribution_charge_date` is one year after the local date of `last_charged_at`, or of `created_at` when nothing has been charged yet (29 February becomes 28 February), and `today` when that anniversary has already passed. The renewals page of the developer docs states this rule.
- **The scanner** treats a contribution-only mandate like a renewal whose charge date is `contribution_charge_date`: the notice goes out `NOTICE_DAYS` before it and schedules the attempt (`attempt.membership` is the lifetime term), the charge creates a contribution-only payment and extends no term, the retry ladder and the pause apply unchanged, and `_already_renewed` does not apply. The skip reason `lifetime` is recorded when an annual mandate's member turns out to hold a lifetime term (today that falls through as `no_term`).
- **Wording by kind in every renewal email** (subjects in `SUBJECTS` and the six template pairs): a `renewal` mandate keeps today's words; `both` says "renew your membership and take your contribution" where the verb appears and "renewal and contribution" where the noun does; `contribution` never says "renew" or "membership renewal" ("we will take your contribution on …", "thank you for your contribution", "automatic contribution is on/off"). Templates receive `kind` and `kind_label` through `mandate_context`.
- **The next charge date in the emails.** `renewal_enabled` and `renewal_charged` each carry `next_charge_on` (never null: for `renewal_charged` it is computed after the term has been extended) and say `Your next charge will be on <date>` (prose date, as the other renewal emails print dates). The golden files follow.
- **Screens** follow in §5.6 and §5.8.

### 5.4 Dry runs that name people

- `RenewalRun` gains `actions: list[RunAction]`, where `RunAction` (in `caldart/runs.py`, new, shared with the reminders) is a frozen dataclass `{kind: str, member: str, email: str, on: date | None, amount_cents: int | None, detail: str}`. The scanner appends one action for every email it sends or would send (`notice`, `card_warning`, `charged`, `failed`, `paused`, `abandoned`, `canceled` is not a scan action) and for every charge (`charge`, with the amount), in both modes: in a live run they record what happened, in a dry run what would have. `as_dict()` carries `actions` (dates as ISO strings) and `as_lines()` prints one line per action after the counts, `would email <kind> to <member> <<email>>` in a dry run and `emailed …` live, with the amount and date where there is one.
- `ReminderRun` gains the same `actions` (kind = the reminder kind, `on` = the term's expiry), `as_dict()` carries them, and `send_renewal_reminders --dry-run` prints them.
- `POST /system/renewals/run` and `POST /system/reminders/run` answer with `actions` beside the counts; the API page shows a body with two actions. The system page's two panels list them (§5.8).

### 5.5 Member check, member sorting, member and aircraft reports

- **Search results carry the readiness.** `search_result()` and `LeaderSearchResultSerializer` add `go_no_go` (`{membership, medical}` booleans, exactly the status card's rule) and `medical` (`{type, expiration, is_current}`), computed from the profile the query already selects (the query-count test proves no extra query per row). The results list shows, after the membership chip: a `StatusDot` GO (tone `current`) or NO-GO (tone `expired`) with the word, then the medical in words (`Class 3 medical to 2027/03/31`, `Medical expired 2026/01/31`, `No medical on file`); `dart-leader-guide.rst` says the list already answers go/no-go and the card gives the detail.
- **"Coverage is current"** replaces "Cover is current" in `AircraftStatusCard.tsx` and the leader-check e2e spec.
- **Secondary sort keys** in `MemberOrderingFilter.aliases`: `name` is `last_name, first_name, profile__dart__name, email`; `expires_on` is `effective_expiry, last_name, first_name`; `email` is `email, last_name, first_name`; `pilot` and `dart` already end in the name. `api-members.rst` lists each alias's full order.
- **Column registries.** `MEMBER_REPORT_COLUMNS` (`apps/members/reports.py`) and the aircraft columns (`apps/aircraft/reports.py`) become tuples of `ReportColumn`, with labels a person reads and a default set that fits one landscape page: members default `name, email, phone, dart, status, expires_on, certificate, medical_type, medical_expiration, aircraft` (the other seven available); aircraft default `n_number, make, model, owner_name, insurance_expiration` plus whatever else fits, the rest available. `ReportColumn` gains `width: float = 1.0`, a relative width the PDF uses; the exports pass `widths=[c.width for c in columns]`. `GET /admin/members/columns` and `GET /admin/aircraft/columns` (`IsAccountAdmin`) answer the registries as `GET /admin/payments/columns` does; the four exports take `?columns=` exactly as the payments exports do (unknown or repeated key is a 400 keyed `columns`; absent means the defaults). The CSV header is the labels.
- **No default cell wraps.** A test builds the members PDF for the seeded members with the default columns and asserts, with reportlab's `stringWidth` at the cell font, that every default cell of every seeded row fits its column width less the padding; the same for aircraft. Widths are tuned until it passes; the font is not shrunk.
- **The chooser on the two lists.** The member list and the aircraft register put `ColumnChooser` in the `DataTable` filters slot; the chosen keys drive the export links (`columns=`), as on the payments list. The docs pages for both reports gain a "Choosing the columns" paragraph mirroring `payments.rst`.

### 5.6 The member's money screens

- **Words.** `We will email you fourteen days before every charge.` and `Turn this on and CalDART will charge a saved card or PayPal account the day before your membership runs out, so it never lapses.`; the setup total sentence likewise says `We will email you`.
- **The card's title** is `Automatic renewal` for a member with a dated term and `Automatic contribution` for a life member (`is_lifetime` from `useMembership`). Its faces say `renewal`, `contribution` or `renewal and contribution` from the mandate's `kind` (the off face for a life member: `Turn this on and CalDART will charge a saved card or PayPal account once a year for the contribution you choose.`). Toasts follow (`Automatic contribution is on.`).
- **Change contribution** opens the same choosers the setup shows: `PlanChooser` over the renewable plans (not for a life member) and `ContributionChooser` with its tiers and "Other amount", preselected from the mandate; Save sends `PATCH /me/renewal` with `{plan, contribution_cents}` (no `plan` for a life member). The `ContributionForm`'s bare dollars box goes.
- **Setup for a life member** shows no `PlanChooser`, the `ContributionChooser` only, and the total sentence `Each year CalDART will charge <amount> for your contribution. We will email you fourteen days before every charge.` A zero contribution cannot be saved (the Save/provider step is disabled with `Choose a contribution to charge each year.`).
- **Next charge** always shows the date and the amount for an active mandate; the "Nothing due yet" branch is deleted, on the card and on the dashboard (`Automatic contribution is on: $50.00 on …`).
- **The renew page for a life member** is titled `Contribute to CalDART`, eyebrow `Membership`, lede `As a life member you have nothing to renew. A contribution keeps the DARTs flying.`, the "Where you stand" card says `You are a life member. Thank you.`, and the checkout below runs in `mode="contribute"`: no plan chooser, the contribution chooser, and the auto-renew checkbox worded `Contribute this amount automatically each year`. The nav label stays `Renew`.
- **Checkout `mode="contribute"`** posts no `plan`; its success toast is `Thank you for your contribution.`; a life member who reaches `mode="renew"` or `mode="join"` is shown the contribute form instead (the server refuses a plan anyway).
- The e2e `auto-renew.spec.ts` gains a life member run: sign in as the seeded life member with the mock provider, see `Automatic contribution`, turn it on with a tier, see the next charge date, turn it off.

### 5.7 DARTs

- **No Town.** `Dart.city` is removed (model, `darts/0001_initial.py` regenerated, serializers, admin `list_display`/`search_fields`, `DartFactory`, the seed's `DARTS` triples become pairs, `seed_content.py` uses the airport identifiers for `where` and `their` for `county`, `types.ts`, the form, the list column, the tests, the e2e spec, `api-darts.rst`, `data-model.rst` in both diagram forms, `account-administrator-guide.rst`). The guide's "Position in the list" sentence, which describes a field that does not exist, goes too.
- **Delete moves to the form.** The list's actions column holds only Edit. The edit card's `DartForm` gets a footer row with `DeleteButton` (danger, with the text `Delete this DART`), disabled with the in-use reason in its `title` when members or pages are attached, and the same inline `Delete for good` / `Keep` confirmation the list had. `DartForm` takes `onDelete` and `deleteBlockedBy` props; the add form shows no delete. The e2e spec's "cannot be deleted" test opens the DART first.
- **"DART management"** is the contacts fieldset legend.
- **The member count** in the list is a `Link` to `/admin/members?dart=<id>` (the list already reads `dart` from the URL).
- **Reordering people.** Each contact row gets `Move up` and `Move down` quiet small buttons (`aria-label="Move person N up"`), disabled at the ends; the array order is what is saved, as today, and the guide says the order is the order the public site lists them.
- **Remove a person** is a `DeleteButton` labeled `Remove person N`.

### 5.8 Finance and system screens

- **Contribution-only mandates on the finance screens.** The Renewals tab's plan column reads `Contribution` when `plan` is null, and the "Automatic renewal" strings on the member ledger card, the payment detail row and the Renewals tab rows read by kind (`Automatic contribution` for a contribution-only mandate). The `plan_name` type is `string | null`.
- **The system page's panels** show, under the summary line, a table of the run's actions: what (the email kind or `charge`), who (name and email), when, amount. In a dry run the heading is `What a live run would do`; live, `What this run did`. Empty when nothing was due.

### 5.9 Seed

- The account-administrator demo account (a life member) gets an active contribution-only mandate on the mock provider, $50 a year, created a year ago less thirty days so its next charge is a month out. `seed_facts` reports `contribution_mandate` (its user's email). The finance list's seeded counts in the e2e specs change accordingly.

### 5.10 Docs pages

`member-guide.rst`, `aircraft.rst`, `payments.rst`, `faq.rst`, `dart-leader-guide.rst`,
`account-administrator-guide.rst`, `system-administrator-guide.rst`, `user-administrator.rst`
(role names), `renewals.rst`, `reports.rst`, `reminders.rst`, `api-members.rst`,
`api-aircraft.rst`, `api-renewals.rst`, `api-payments.rst`, `api-darts.rst`,
`api-system.rst`, `data-model.rst`. Each package's entry names its pages.

## 6. Failure handling and the final report

- **A failing gate.** Three fix attempts within scope; then the PR stays open as a draft with a comment saying what failed, and the orchestrator carries on with every package that does not depend on it.
- **A rebase conflict outside the package's files.** Same.
- **CI red on `main`.** No new package starts until a fix PR restores it.
- **The final report** lists every PR merged, every item of #204 with the PR that settled it, and every decision taken that §5 did not cover.
- **Archive.** The closeout PR moves this plan to `plans/archive/`.

## 7. Work packages

### Wave 1

#### shared-ui (Opus)

- **Refs:** #204
- **Branch:** `feature/shared-ui`; database `caldart_shared_ui`
- **Owns:** `frontend/src/portal/components/DeleteButton.tsx` (new), `frontend/src/portal/components/DeleteButton.test.tsx` (new), `frontend/src/portal/components/useClickOutside.ts` (new), `frontend/src/portal/components/useClickOutside.test.ts` (new), `frontend/src/portal/components/ColumnChooser.tsx` (moved), `frontend/src/portal/components/ColumnChooser.test.tsx` (moved), `frontend/src/portal/features/admin-payments/ColumnChooser.tsx` (deleted), `frontend/src/portal/features/admin-payments/ColumnChooser.test.tsx` (deleted), `frontend/src/portal/features/admin-payments/PaymentsListPage.tsx#import`, `frontend/src/portal/features/admin-payments/admin-payments.css#column-chooser`, `frontend/src/styles/base.css#icon-button-and-column-chooser`, `frontend/src/portal/choices.ts#roles`, `frontend/src/portal/features/admin-members/choices.ts#roles`, `frontend/src/portal/features/admin-members/MemberDetailPage.tsx#role-import`, `frontend/src/portal/features/admin-users/UsersListPage.tsx`, `frontend/src/portal/features/admin-users/UserDetailPage.tsx`, `frontend/src/portal/features/admin-users/*.test.tsx`, `frontend/src/portal/auth/guards.tsx`, `frontend/src/portal/auth/guards.test.tsx`, `frontend/src/portal/nav.ts`, `frontend/src/portal/nav.test.ts`, `frontend/src/portal/layout/PortalLayout.test.tsx`, `frontend/src/portal/features/admin-aircraft/AircraftRecordPage.tsx`, `frontend/src/portal/features/admin-aircraft/AircraftRecordPage.test.tsx`, `frontend/src/portal/features/admin-members/MemberDangerZone.tsx`, `frontend/src/portal/features/admin-members/MemberDangerZone.test.tsx`, `docs/user/user-administrator.rst#role-names`, `docs/user/aircraft.rst#delete-button`, `docs/user/account-administrator-guide.rst#delete-member-button`, `docs/developer/architecture.rst#components`.
- **Steps:** §5.1 in full. The `DeleteButton` test covers icon-only (accessible name from `label`, `title`), with text, `disabled`, and `variant="danger"`. The `useClickOutside` test covers a pointerdown inside (no call), outside (call), Escape, and inactive. The chooser's test gains "closes on a click outside" and "closes on Escape". The rail test asserts the single `aria-current` at `/profile/aircraft` and at `/leader/aircraft`.
- **Verify:** `make lint test`; `grep -rn "replace(/_/g" frontend/src/portal` finds nothing; the finance list still chooses columns.

#### renewal-contributions (Opus)

- **Refs:** #204
- **Branch:** `feature/renewal-contributions`; database `caldart_renewal_contributions`
- **Owns:** `backend/apps/payments/models.py#mandate-plan-nullable`, `backend/apps/payments/migrations/0001_initial.py`, `backend/apps/payments/renewals.py`, `backend/apps/payments/services.py#checkout-lifetime-and-contribution-mandate`, `backend/apps/payments/api/serializers.py#renewals-and-checkout`, `backend/apps/payments/api/renewal_views.py`, `backend/apps/payments/api/views.py#checkout-lifetime`, `backend/apps/payments/management/commands/run_auto_renewals.py`, `backend/apps/reminders/services.py#run-actions`, `backend/apps/reminders/management/commands/send_renewal_reminders.py`, `backend/apps/reminders/api/**#run-actions`, `backend/apps/sysadmin/api/views.py#renewals-run-actions`, `backend/caldart/runs.py` (new), `backend/templates/emails/renewal_*.{txt,html}`, `backend/apps/payments/seed.py#contribution-mandate`, `backend/apps/sysadmin/management/commands/seed_facts.py#contribution-mandate`, `backend/tests/test_contribution_mandates.py` (new), `backend/tests/test_run_actions.py` (new), `backend/tests/test_renewals.py#kind-and-next-charge`, `backend/tests/test_renewals_api.py#patch-plan`, `backend/tests/test_reminders.py#actions`, `backend/tests/test_payments_api.py#lifetime-checkout`, `backend/tests/golden/renewal-*.txt`, `backend/tests/factories.py#mandate-plan-optional`, `frontend/src/portal/api/types.ts#renewals-and-runs`, `frontend/e2e/helpers.ts#contribution-mandate`, `docs/developer/renewals.rst`, `docs/developer/api-renewals.rst`, `docs/developer/api-payments.rst#checkout-lifetime`, `docs/developer/api-system.rst#run-actions`, `docs/developer/reminders.rst#run-actions`, `docs/developer/data-model.rst#mandate-plan`, `docs/user/payments.rst#contribution-mandates`, `docs/user/faq.rst#life-members`, `docs/user/system-administrator-guide.rst#dry-run-actions`.
- **Steps:** §5.3, §5.4 and §5.9. Tests drive a life member through setup, notice, charge, retry and pause on a frozen clock; a member with a dated term changes plan through `PATCH`; the checkout refuses a plan for a life member; `next_charge_on` is a date for every active seeded mandate; a dry run's `actions` name each member and email that a live run then actually emails (compare the two lists).
- **Verify:** `make reset && make seed`; `manage.py run_auto_renewals --dry-run` on the seed prints one `would email` line per seeded notice; `send_renewal_reminders --dry-run` prints who would get which reminder; `GET /me/renewal` for the account administrator shows `kind: contribution` and a date.

#### member-reports-backend (Opus)

- **Refs:** #204, #155
- **Branch:** `feature/member-reports-backend`; database `caldart_member_reports`
- **Owns:** `backend/apps/aircraft/services.py#search-result`, `backend/apps/aircraft/api/serializers.py#search-result`, `backend/apps/aircraft/api/views.py#columns-and-exports`, `backend/apps/aircraft/api/urls.py#columns`, `backend/apps/aircraft/reports.py`, `backend/apps/members/reports.py`, `backend/apps/members/api/admin_filters.py#ordering-aliases`, `backend/apps/members/api/admin_views.py#columns-and-exports`, `backend/apps/members/api/admin_urls.py#columns`, `backend/caldart/reports.py#column-width`, `backend/tests/test_report_columns.py` (new), `backend/tests/test_leader_search_readiness.py` (new), `backend/tests/test_members_reports.py`, `backend/tests/test_aircraft_exports.py`, `backend/tests/test_members_admin.py#ordering`, `backend/tests/test_membership_query_counts.py#search`, `backend/tests/test_reports.py#width`, `backend/tests/test_permission_matrix.py#columns`, `frontend/src/portal/api/types.ts#leader-and-columns`, `docs/developer/api-members.rst`, `docs/developer/api-aircraft.rst`, `docs/developer/reports.rst`, `docs/developer/api-reference.rst#columns-matrix`.
- **Steps:** §5.5's backend half: the readiness on search results, the aliases, the two registries with widths and defaults, the two columns endpoints, `columns=` on the four exports, the no-wrap test, the permission-matrix rows.
- **Verify:** `make test`; `GET /admin/members/export.pdf` on the seed with the defaults decodes to the label header; `GET /admin/members/export.csv?columns=name,bogus` is a 400 keyed `columns`.

### Wave 2

#### profile-and-aircraft (Opus)

- **Refs:** #204
- **After:** shared-ui
- **Branch:** `feature/profile-and-aircraft`; database `caldart_profile_aircraft`; e2e port 8151
- **Owns:** `frontend/src/portal/features/profile/ProfileFieldsets.tsx`, `frontend/src/portal/features/profile/ProfileFieldsets.test.tsx`, `frontend/src/portal/features/profile/constants.ts`, `frontend/src/portal/features/profile/profile.css`, `frontend/src/portal/features/profile/MyAircraftPage.tsx`, `frontend/src/portal/features/profile/MyAircraftPage.test.tsx`, `frontend/src/portal/features/aircraft/AircraftPicker.tsx`, `frontend/src/portal/features/aircraft/AircraftPicker.test.tsx`, `frontend/src/portal/features/aircraft/aircraft.css`, `frontend/e2e/member-self-service.spec.ts#profile-wording`, `docs/user/member-guide.rst`, `docs/user/aircraft.rst#picker`.
- **Steps:** §5.2 in full.
- **Verify:** `make test e2e`; `make lint`.

#### member-money (Opus)

- **Refs:** #204
- **After:** shared-ui, renewal-contributions
- **Branch:** `feature/member-money`; database `caldart_member_money`; e2e port 8152
- **Owns:** `frontend/src/portal/features/payments/**`, `frontend/src/portal/features/checkout/**`, `frontend/src/portal/features/join/RenewPage.tsx`, `frontend/src/portal/features/join/RenewPage.test.tsx`, `frontend/src/portal/features/dashboard/DashboardPage.tsx`, `frontend/src/portal/features/dashboard/DashboardPage.test.tsx`, `frontend/src/test/handlers.ts#renewal-kind`, `frontend/src/test/fixtures/payments.ts`, `frontend/e2e/auto-renew.spec.ts`, `frontend/e2e/join-and-pay.spec.ts#contribute`, `docs/user/payments.rst#member-screens`, `docs/user/faq.rst#member-screens`, `docs/user/member-guide.rst#renew-and-contribute`.
- **Steps:** §5.6 in full, on the API §5.3 shipped (read `api-renewals.rst` and `api-payments.rst` on `main`, not this plan, for the shapes).
- **Verify:** `make test e2e`; `make lint`; `grep -rn "Nothing due yet\|nothing due yet" frontend/src` finds nothing.

#### leader-and-members-screens (Opus)

- **Refs:** #204, #155
- **After:** shared-ui, member-reports-backend
- **Branch:** `feature/leader-and-members-screens`; database `caldart_leader_members`; e2e port 8153
- **Owns:** `frontend/src/portal/features/leader/LeaderSearchPage.tsx`, `frontend/src/portal/features/leader/LeaderSearchPage.test.tsx`, `frontend/src/portal/features/leader/AircraftStatusCard.tsx`, `frontend/src/portal/features/leader/labels.ts`, `frontend/src/portal/features/leader/leader.css`, `frontend/src/portal/features/admin-members/MembersListPage.tsx`, `frontend/src/portal/features/admin-members/MembersListPage.test.tsx`, `frontend/src/portal/features/admin-members/api.ts`, `frontend/src/portal/features/admin-members/types.ts`, `frontend/src/portal/features/admin-aircraft/AircraftRegisterPage.tsx`, `frontend/src/portal/features/admin-aircraft/AircraftRegisterPage.test.tsx`, `frontend/src/portal/features/aircraft/api.ts#export-columns`, `frontend/src/test/handlers.ts#leader-and-columns`, `frontend/e2e/leader-check.spec.ts`, `docs/user/dart-leader-guide.rst`, `docs/user/account-administrator-guide.rst#members-columns-and-sorting`, `docs/user/aircraft.rst#columns`.
- **Steps:** §5.5's screen half: the readiness and medical on the results, "Coverage is current", the chooser on both lists with the export links following it, the guides.
- **Verify:** `make test e2e`; `make lint`.

#### darts (Opus)

- **Refs:** #204
- **After:** shared-ui
- **Branch:** `feature/darts`; database `caldart_darts`; e2e port 8154
- **Owns:** `backend/apps/darts/**`, `backend/apps/members/seed.py#darts`, `backend/apps/cms/management/commands/seed_content.py#dart-city`, `backend/tests/factories.py#dart`, `backend/tests/test_darts_admin.py`, `backend/tests/test_cms_seed_content.py#dart-city`, `backend/tests/test_seed.py#dart-city`, `frontend/src/portal/api/types.ts#dart`, `frontend/src/portal/features/admin-darts/**`, `frontend/src/portal/features/admin-members/MemberCreatePage.test.tsx#dart-fixture`, `frontend/src/test/handlers.ts#darts`, `frontend/e2e/darts-admin.spec.ts`, `docs/developer/api-darts.rst`, `docs/developer/data-model.rst#dart`, `docs/user/account-administrator-guide.rst#darts`.
- **Steps:** §5.7 in full. Backend first (the field, the migration regenerated, the seed, the snapshot), then the form.
- **Verify:** `make reset && make seed` from empty; `make test e2e`; `grep -rn "city" backend/apps/darts` finds nothing.

#### finance-and-system-screens (Sonnet)

- **Refs:** #204
- **After:** renewal-contributions
- **Branch:** `feature/finance-and-system-screens`; database `caldart_finance_system`; e2e port 8155
- **Owns:** `frontend/src/portal/features/admin-payments/RenewalsPage.tsx`, `frontend/src/portal/features/admin-payments/RenewalsPage.test.tsx`, `frontend/src/portal/features/admin-payments/MemberLedgerPage.tsx`, `frontend/src/portal/features/admin-payments/MemberLedgerPage.test.tsx`, `frontend/src/portal/features/admin-payments/PaymentDetailPage.tsx`, `frontend/src/portal/features/admin-payments/PaymentDetailPage.test.tsx`, `frontend/src/portal/features/admin-payments/labels.ts`, `frontend/src/portal/features/system/RenewalsPanel.tsx`, `frontend/src/portal/features/system/RenewalsPanel.test.tsx`, `frontend/src/portal/features/system/RemindersPanel.tsx`, `frontend/src/portal/features/system/RemindersPanel.test.tsx`, `frontend/src/portal/features/system/api.ts`, `frontend/src/test/handlers.ts#system-actions`, `frontend/src/test/fixtures/finance.ts#contribution-mandate`, `frontend/e2e/finance-reports.spec.ts`, `frontend/e2e/reminders.spec.ts`, `docs/user/payments.rst#finance-contribution-mandates`, `docs/user/system-administrator-guide.rst#panels`.
- **Steps:** §5.8 in full, on the API §5.3 and §5.4 shipped.
- **Verify:** `make test e2e`; `make lint`.

### Wave 3

#### closeout (Sonnet)

- **Closes:** #204
- **After:** profile-and-aircraft, member-money, leader-and-members-screens, darts, finance-and-system-screens
- **Branch:** `chore/walkthrough-closeout`; database `caldart_walkthrough_closeout`; e2e port 8156
- **Owns:** `docs/**#residue`, `frontend/src/**#residue`, `backend/**#residue`, `plans/2026-09-24-walkthrough-fixes.md` (moves to `plans/archive/`).
- **Steps:** re-run every item of #204 against `main` item by item and fix small residue in scope (a leftover "Remove" text button, a slug rendered raw, a "renew" in a contribution-only email, a docs sentence describing the old picker); read `payments.rst`, `member-guide.rst` and `account-administrator-guide.rst` top to bottom for a single voice; comment on #155 saying which of its asks the column chooser settled; the PR body lists every item of #204 with the PR that settled it; move the plan to the archive.
- **Verify:** `make lint test check docs audit e2e` green.

## 8. Manifest

```json
[
  {"wave": 1, "package": "shared-ui", "model": "opus", "branch": "feature/shared-ui", "database": "caldart_shared_ui", "e2e_port": null, "closes": [], "refs": [204], "after": []},
  {"wave": 1, "package": "renewal-contributions", "model": "opus", "branch": "feature/renewal-contributions", "database": "caldart_renewal_contributions", "e2e_port": null, "closes": [], "refs": [204], "after": []},
  {"wave": 1, "package": "member-reports-backend", "model": "opus", "branch": "feature/member-reports-backend", "database": "caldart_member_reports", "e2e_port": null, "closes": [], "refs": [204, 155], "after": []},
  {"wave": 2, "package": "profile-and-aircraft", "model": "opus", "branch": "feature/profile-and-aircraft", "database": "caldart_profile_aircraft", "e2e_port": 8151, "closes": [], "refs": [204], "after": ["shared-ui"]},
  {"wave": 2, "package": "member-money", "model": "opus", "branch": "feature/member-money", "database": "caldart_member_money", "e2e_port": 8152, "closes": [], "refs": [204], "after": ["shared-ui", "renewal-contributions"]},
  {"wave": 2, "package": "leader-and-members-screens", "model": "opus", "branch": "feature/leader-and-members-screens", "database": "caldart_leader_members", "e2e_port": 8153, "closes": [], "refs": [204, 155], "after": ["shared-ui", "member-reports-backend"]},
  {"wave": 2, "package": "darts", "model": "opus", "branch": "feature/darts", "database": "caldart_darts", "e2e_port": 8154, "closes": [], "refs": [204], "after": ["shared-ui"]},
  {"wave": 2, "package": "finance-and-system-screens", "model": "sonnet", "branch": "feature/finance-and-system-screens", "database": "caldart_finance_system", "e2e_port": 8155, "closes": [], "refs": [204], "after": ["renewal-contributions"]},
  {"wave": 3, "package": "closeout", "model": "sonnet", "branch": "chore/walkthrough-closeout", "database": "caldart_walkthrough_closeout", "e2e_port": 8156, "closes": [204], "refs": [], "after": ["profile-and-aircraft", "member-money", "leader-and-members-screens", "darts", "finance-and-system-screens"]}
]
```
