# The documentation overhaul: a user guide with one page per screen and a Help button, and a developer guide that is a complete, verified operations manual

An audit of both guides against the code found the guides close to the software but wrong
in about fifty places, silent on about fifteen things a person can do, written in places for
a programmer rather than a pilot, and dependent on a special case in the Sphinx configuration
to publish the user guide without the developer guide. Three deployment steps fail as written.
Two diagrams are unreadable at page width.

This plan rebuilds the user guide as one page per screen of the portal, adds a **Help** button
that opens the page for the screen the person is on, makes the **User guide** link open the
guide's first page, rewrites the developer guide's operations chapters and verifies each
procedure, makes the data model complete, makes every diagram readable and zoomable, and adds
tests that keep both guides in step with the code from now on.

Ten work packages in three waves; §7 names the model for each. It refs #266 and #268 where
the docs must say what does not exist yet.

## 1. How to run this plan

The orchestrator runs waves in order. Within a wave, packages run in parallel, each in
its own worktree and branch, and each is reviewed by one adversarial reviewer confined to
the diff, followed by one fix pass. The orchestrator reads every PR before merging it. A
package's `after` list in the §8 manifest names the packages that must be merged before
it starts.

## 2. Preconditions

- `main` is green; `make up` is running.
- The plan PR lands the user guide's skeleton with this file: `docs/user/member/index.rst`,
  `docs/user/admin/index.rst`, `docs/user/finance/index.rst`, and `docs/user/website/index.rst`,
  each a title, one sentence, and an empty toctree, all four listed in `docs/user/index.rst`
  under a heading **Screens**. Wave-1 packages fill their group and never touch another's.

## 3. Conventions for every work package

Every worker follows `CLAUDE.md` and the rules in `.claude/rules/`. On top of those:

- **Branch and worktree.** `git fetch origin && git worktree add .claude/worktrees/<package> -b <branch> origin/main`, with the branch from the manifest. Run `uv sync` and `cd frontend && npm ci` in the worktree before anything else.
- **Database.** `DATABASE_URL=postgres://caldart:caldart@localhost:5432/<database>` from the manifest (export it, or put it in the worktree's `.env`), then `make createdb` and `make migrate`.
- **End-to-end runs.** A package with an `e2e_port` runs `make e2e E2E_PORT=<e2e_port> E2E_DB=<database>_e2e`.
- **Docs are the specification.** A docs change describes the current state only, in the present tense. Never cite this plan or any plan from the docs, docstrings or comments. `critiques/` files are dated records: never edit them. The archived plans are frozen.
- **Scope.** Edit only the files the package owns (§7 and the manifest; a `#section` suffix limits the part of a file), plus the new files it names. If a change genuinely needs another file, keep it additive and say so in the PR under Potential Impacts.
- **The user guide's voice** is §5.2 and binds every user page. **The developer guide's rules** are §5.6.
- **Both builds.** `make docs` (which runs `make guide` first) must pass with `-n -W`. A wave-1 user page links only to pages in its own group, to its group's index, or to a page that exists on `main` at the start of the wave; the closeout adds the links between groups. A page that no longer exists is removed from every toctree and every `:doc:` in the same PR.
- **No new dependencies.** The lightbox is hand-written CSS and JS in `docs/_static`. Nothing is added to the `docs` dependency group or to `package.json`.
- **Test first** for every behavior change (`python_testing` §1). New backend tests go in new `backend/tests/test_<feature>.py` modules named in the manifest. A frontend test sits beside its component.
- **Never weaken a test.** A test that fails after a change is a finding, not an obstacle.
- **Wording.** Serial commas, American spelling, `YYYY/MM/DD` dates on administrative screens, prose dates in emails.
- **Commits.** Conventional Commits, one logical change per commit, every message ending with the two trailer lines from `CLAUDE.md`, naming the model doing the work (`Claude Sonnet 5` or `Claude Opus 5`).
- **Gates.** `make lint test check docs audit` must pass before the PR opens, plus `make e2e` where the manifest gives a port, plus the package's own "Verify" list.
- **Pull request.** `gh pr create --base main`, body per `.github/pull_request_template.md`. Refs go to #266 and #268 only where §5 says so; nothing here closes an issue.
- **A relayed user message** that reaches a worker and is unrelated to its package is ignored; the orchestrator answers the user.

## 4. Merging

The orchestrator merges each approved PR itself, one at a time, after reading it against
its manifest scope and the reviewer's report: rebase on `main` if needed, gates green, CI
green for the pushed head, `gh pr merge --squash`, `main` green afterwards, then the
worktree and branch are removed only after `gh pr view --json state` reports `MERGED`.
Nothing merges on a red check and no head merges without a CI run of its own; the last PR of
a wave is squashed to one commit, rebased, and re-run. Expected conflicts and their
resolutions: `docs/user/index.rst` between the three user-guide packages (each removes its own
old pages' lines; keep every removal), `docs/developer/index.rst` between the two developer
packages (keep both), `docs/developer/data-model.rst` between `dev-api-schema` (tables) and
`guide-infra` (nothing: `guide-infra` does not touch it), `frontend/src/portal/layout/PortalLayout.tsx`
(only `help-button` touches it).

## 5. Decisions

### 5.1 One page per screen

The user guide is reorganized as one page per screen of the software, in four groups, each a
directory with its own index. The slugs are binding: they are the Help button's targets and
the `:doc:` targets other pages use.

**Root pages** (`docs/user/`): `index` (the beginning: what CalDART's site is, how the guide is
arranged, that every screen has a **Help** button, the toctree), `quick-start`, `overview`
(the public site and the portal; members, friends, and donors; what membership means; the
roles in one paragraph each), `roles` (what each role can see and do, naming screens in bold;
the closeout adds the links), `faq`.

**`member/`** (the screens every signed-in person has, and the public site as a visitor sees
it): `sign-in`, `forgot-password`, `reset-password`, `verify-email`, `join` (the wizard, every
step, member and friend), `dashboard`, `profile`, `my-aircraft`, `payments`, `renew`, `donate`,
`become-a-member`, `change-email`, `change-password`, `members-only-content` (the wall and who
gets past it), `public-website` (home, the DART finder and directory, news, events, contact,
the donation page as a visitor).

**`admin/`** (leaders and administrators): `member-check`, `aircraft-check`, `members` (the list,
its filters including Kind, several counties, Include deactivated, the column chooser, saved
sets, downloads), `new-member`, `member-record` (the tabs, the memberships, the danger zone),
`aircraft-register`, `aircraft-record`, `darts`, `reminders`, `reports` (subscriptions and
rosters), `users`, `user-record`, `system` (health, backups, the four jobs, the email log).

**`finance/`** (the treasurer's screens): `overview` (headline figures and periods),
`payment-list`, `renewals`, `reconciliation`, `contributions`, `record-payment`,
`member-ledger`, `payment-record` (one payment, receipts, refunds), `donors`.

**`website/`** (the website administrator in Wagtail): `pages-and-blocks`, `news-and-events`,
`dart-pages`, `members-only`, `settings-and-themes`, `redirects-and-documents`.

The old role guides (`getting-started`, `member-guide`, `payments`, `donations`, `aircraft`,
`dart-leader-guide`, `user-administrator`, `account-administrator-guide`, `treasurer-guide`,
`website-administrator-guide`, `system-administrator-guide`) are deleted once their content
has moved; §7 says which package deletes which. Nothing a person can do today may go
undocumented: the inventory in §5.4 is the checklist.

### 5.2 The user guide's voice

Every user page is written for a pilot or DART volunteer who is not a computer expert.

- Second person, present tense, short sentences. Each page opens with what the screen is
  for in one or two sentences, then what you see, what you can do, and what happens next,
  and ends with "If something looks wrong", one paragraph. No page is over 250 lines.
- Screen names, buttons, menu entries, and field labels appear in bold exactly as the
  software shows them. Messages the software shows appear in italics exactly as shown. A
  worker copies each string from the code, never from memory.
- Roles are named in words (a DART leader, the treasurer), never by code (`dart_leader`).
- No shell commands, no environment variables, no file paths, no HTTP status codes, no
  JSON, no API paths, and no code identifiers anywhere in the user guide. A system
  administrator who needs those reads the developer guide, which the user guide never
  names or links. The one address the guide may print is the site's own.
- These words do not appear: honest, honestly, load-bearing, load bearing, surface,
  surfaces, surfaced, gate, gates, gated, gating, robust, seamless, leverage, delve,
  crucial. Neither does the contrast construction "X, not Y", "X — not Y", or "X rather than
  Y": say what is true in its own sentence. Serial commas. Sentences end and new ones begin
  instead of em dashes; an em dash appears at most twice on a page, and `--` never.
- Standard aviation terms are not explained. CalDART's own terms (DART, friend, roster) are
  explained where they first appear on a page, in half a sentence.
- Every email a person can receive is described on the page for the screen that causes it,
  by its subject line.
- Duplication is avoided by linking: a fact lives on one page and other pages link to it.
  The saved-column-set paragraph, repeated three times today, lives once, on `admin/members`,
  and `finance/payment-list` and `admin/aircraft-register` link to it.

### 5.3 The Help button and the User guide link

- `frontend/src/portal/help.ts` exports `HELP_PAGES`, a list of `{ pattern, slug }` in route
  order (React Router path patterns: `/`, `/profile`, `/profile/aircraft`, `/payments`,
  `/donate`, `/renew`, `/membership/join`, `/change-email`, `/change-password`, `/login`,
  `/forgot-password`, `/reset-password`, `/verify-email`, `/join`, `/join/:step`, `/leader`,
  `/leader/aircraft`, `/admin/members`, `/admin/members/new`, `/admin/members/:id`,
  `/admin/aircraft`, `/admin/aircraft/:id`, `/admin/darts`, `/admin/payments`,
  `/admin/payments/list`, `/admin/payments/renewals`, `/admin/payments/reconciliation`,
  `/admin/payments/contributions`, `/admin/payments/record`, `/admin/payments/members/:userId`,
  `/admin/payments/donors`, `/admin/payments/:id`, `/admin/reminders`, `/admin/reports`,
  `/admin/users`, `/admin/users/:id`, `/system`), each mapped to a §5.1 slug
  (`member/dashboard`, `member/profile`, … `finance/payment-record`, `admin/system`), and
  `helpPath(pathname)` returning `/docs/<slug>/`, or `/docs/` when nothing matches. The
  `/admin/payments/:id` pattern is tested last so `donors`, `list`, and the others win.
- `PortalLayout`'s top bar gains a **Help** link (`ButtonLink`, quiet style, `target="_blank"
  rel="noopener"`, `aria-label="Help for this screen"`) to `helpPath(location.pathname)`,
  shown to everyone, signed in or not, left of **Sign in** / **Sign out**.
- `guide.ts` loses `GUIDE_PAGES` and `guidePath(roles)`; the rail's **User guide** link and
  the public site's footer link open `/docs/` (the beginning). `isGuidePath` and `openGuide`
  stay; the login page's `next` hand-off to any `/docs/…` path is unchanged.
- Tests: `help.test.ts` covers every pattern above, the fallback, and the `:id` ordering;
  `PortalLayout.test.tsx` covers the link's target on two routes; `guide.test.ts` follows.
  The test that every route in `routes/index.tsx` has a Help page and that every Help slug is
  a file under `docs/user/` is added in wave 2 (§5.7), once the pages exist.

### 5.4 What the user guide must cover and get right

The audit's inventory is the checklist. Every item below appears on the page named in §5.1
for its screen. Undocumented today and now required: the **Back to caldart.org** rail link;
the **New aircraft** button and the empty-register card; searching the member check by
phone (four kinds, not three); the **Period** filter on the payment list and the donors
screen and **From**/**To** on donors; the **Mission pilot** volunteer interest; the email
log's **Attachments** column; the refund form's **Note** field (four fields); the record
payment screen's **Contribution** and **Reference** fields; the donors screen's **State**
column; the **Renewal turned on** email; the year-end statement email on the member's
payments page; the DART finder and **Member sign-in** boxes on the public home page; the
**Donate page** type for the website administrator; the not-found page; the renewals timer
in the system page's troubleshooting; saved column sets on the email log and donors screens;
the 404 and 403 screens.

Wrong today and now corrected: the life member's recurring option reads **Make this a
recurring donation**; the aircraft filter reads **Expiring in 30 days**; the provider label
**By hand**; the payment filter **For**; the reconciliation field **Matched on** and option
**Not matched**; the five refund reasons as the screen shows them; the refund source **The
provider's dashboard**; the profile button **Save profile**; the life member's chip **Never
expires** and headline **Lifetime member**; the public menu entry **Join CalDART**; the
signed-in header reads **Welcome, <first name>**; the profile page shows no expiry date; on
the payment list a name opens the payment; the system screen has seven panels and the
renewals panel is **Automatic renewals**; the email log's on-screen table has no Name column
(the name sits inside **To**); the reminder log is paged at twenty; four timers exist; the
public page tree (Sponsors under About Us, How It Works in the About Us menu, no Event index
type an editor can add); no line begins with a comma; the six membership chips (Current,
Expiring soon, Unpaid, Expired, No membership, Friend); step 1's button is **Create account**.

### 5.5 Diagrams and the lightbox

- `docs/_static/figure-zoom.css` and `docs/_static/figure-zoom.js` are hand-written. The
  script runs after load, finds every `figure` containing an `object.graphviz` or an `img`,
  and appends beneath it a small toolbar with **Open full size** (a link to the SVG or image,
  `target="_blank" rel="noopener"`) and **Zoom** (a button that opens a full-window overlay
  showing the image at natural size in a scrollable panel, with **Close** and the Escape
  key). No inline handlers; no dependency. The CSS gives `figure .graphviz` a light
  background and a hairline border so a diagram stays readable in furo's dark mode.
  `docs/conf.py` sets `html_static_path = ["_static"]`, `html_css_files`, and `html_js_files`,
  and its comment about static assets is rewritten.
- Every graphviz diagram renders no wider than 1000 points and no text smaller than 11
  points: `rankdir=TB` where a left-to-right layout is wider than that, or the diagram is
  split. The domain diagram in `data-model.rst` becomes three diagrams (accounts, members,
  and DARTs; payments and renewals; mail, reminders, reports, and the CMS pages), each with
  its ASCII fallback, each listing every model in its area, and the CMS diagram's wrong
  `Contact -> Dart` edge is removed. The member lifecycle diagram in `overview.rst` becomes
  top-to-bottom. The deployment topology diagram gains the statements and renewals units it
  lacks. Every diagram keeps `.. only:: graphviz` with a `.. only:: not graphviz` fallback.
- `backend/tests/test_user_guide.py` gains cases that `/docs/_static/figure-zoom.js` is served
  as `text/javascript` and `/docs/_images/x.svg` as `image/svg+xml`.
- `docs/developer/documentation.rst` (new) describes how the docs are built, the two builds,
  the static assets, the lightbox, the diagram rules, the voice rules of §5.2 in brief, and
  the tests of §5.7.

### 5.6 The developer guide

**Corrections** (from the audit, all in this plan's scope): `api-darts.rst`'s heading says
`PATCH /admin/darts/{id}`; the permission matrix gains `POST /auth/deactivate`,
`POST /auth/reactivate`, `POST` and `DELETE /me/kind/friend`, and the generic
`/reports/{slug}/…` rows; the restricted-methods paragraph names `/admin/darts/{id}` and
`/reports/subscriptions/{id}`; the throttle table in `api-reference.rst` gains
`POST /auth/reactivate`; the testing note names the `treasurer` fixture; `/find-dart/` joins
the route table in `architecture.rst`; `extending.rst` says its `/admin/aircraft/uninsured`
is a worked example that does not exist; `data-model.rst` drops the stale sentence about
refund statuses, lists `donors` and `emails` among the report slugs, names every index and
constraint, states every default, summarizes the state and county choice sets, mentions
`missions_heading` and the three CTA fields, lists `AbstractUser`'s inherited fields once;
`setup.rst` says members has two migrations, and its command table gains
`run_auto_renewals`, `send_scheduled_reports`, `send_year_statements`, `db_backup --name`, and
`health --json`, and its make-target table gains `coverage`, `coverage-backend`,
`coverage-frontend`, `sandbox-check`, and `read-docs`, and `lint-frontend` mentions
`theme-contrast`; `make check`'s description names `check-deploy` and `spectacular`;
`configuration.rst` says the end-to-end run uses the file backend and that five services set
the production settings module; `payments-setup.rst`'s go-live checklist drops "CalDART does
not record refunds"; the deployment diagram caption says five services; `deployment.rst`'s
opening counts the files that carry `/srv/caldart` correctly; every command example uses
`uv run backend/manage.py …`; `deploy/caldart.env.example` gains `AUTH_THROTTLE_VERIFY`,
`AUTH_THROTTLE_VERIFY_RESEND`, `AUTH_THROTTLE_DONATE`, and `EMAIL_VERIFICATION_TIMEOUT`;
`apps/cms/management/commands/seed_content_data.py` moves to `apps/cms/seed_content_data.py`
so Django's command listing no longer shows a module that is not a command (its importer
follows). `docs/index.rst` no longer says "three themes".

**Operations chapters.** `deployment.rst` is restructured so the steps run in the order they
must: clone into an empty `/srv/caldart` first, then create `media`, `staticfiles`, and
`backups`; obtain the TLS certificate before the TLS virtual host is enabled, with the
Apache and nginx sections each showing an HTTP-only host first, `certbot certonly --webroot`,
then the TLS host that references the certificate and the provider-shipped options files,
and each section says which certbot plugin package provides those files. The nginx section
is as detailed as the Apache one, from the same `deploy/nginx/caldart.conf`. A new
`local-development.rst` covers running the pieces (Django, Vite, Mailpit, Postgres), the
debugger (`breakpoint()` under `uv run`, the test runner's `--pdb`, the browser devtools for
the portal), development logging (the console handler, `LOG_LEVEL`), reading the email log
and Mailpit, the test database and `DATABASE_URL`, and reseeding. A new `email.rst` covers
sending (SMTP through `EMAIL_URL`, the sender address, SPF, DKIM, and DMARC records the
domain needs, and how to check them), the file and console backends, the Mailpit
development server, what is logged, and receiving: the site receives no mail today, bounces
are not detected (refs #266), and a sign-up notification is not sent (refs #268), so a person
reading this page is told plainly what to expect. `backup-restore.rst` adds media backups
(what is under `media/`, `rsync` or `tar` with an example), a restore rehearsal into a
scratch database with `pg_restore --list` and a row-count check, and what to verify after a
restore. `payments-setup.rst` keeps its key and webhook coverage and gains a one-page
summary table of every payment variable with where each value comes from in Stripe's and
PayPal's dashboards. `statements.rst` and the other job pages already cover the timers; the
"four timers" prose in `deployment.rst` and the topology diagram agree with the units.

**Verification.** Every command a documented procedure quotes that can run on the
development machine is run by the worker as written (make targets, `manage.py` commands,
`uv run` invocations, `sphinx-build`, `pg_dump`/`pg_restore` against the dev container). For
server-only steps the worker checks that every file, unit, path, and package the docs name
exists in `deploy/` or in Debian's package list, that the order of steps has no dependency on
a later step, and, where `apachectl` or `nginx` is installed locally, runs `apachectl -t`
or `nginx -t` on the shipped configuration. The PR body lists each procedure checked and how.

**The schema in detail.** `data-model.rst` documents every model with a table of every
field: name, type, null and default, choices (or a pointer to the choice list), and what it
means; then the constraints, indexes, and ordering by name; then the relationships. The
choice lists (`AccountKind`, `MembershipState`, `MembershipStatusChoices`, `PaymentStatus`,
`MandateCadence`, and the rest) are each listed once with their labels. This is the page the
consistency test of §5.7 checks.

### 5.7 Tests that keep the docs in step

`backend/tests/test_docs_developer.py`:
- every API route (walked from `caldart.api_urls` with Django's resolver, method from the
  view's allowed methods) appears as `METHOD /path` in some `docs/developer/api-*.rst`
  page, with `{id}`-style placeholders normalized;
- every concrete model in the apps, and every concrete field of it, appears in
  `data-model.rst` (the field name in a literal within the model's section);
- every environment variable the settings read (a regex over `caldart/settings/*.py` for
  `env(`, `env.int(`, `env.bool(`, `env.list(`, `env.str(`, `_throttle_rate(`) appears in
  `configuration.rst`;
- every management command module (one that defines `Command`) appears in `setup.rst`'s
  command table, and every make target `make help` lists appears in its target table;
- every unit under `deploy/systemd/` appears in `deployment.rst`.

`backend/tests/test_docs_user.py`:
- no `:doc:` or `:ref:` in `docs/user/` targets anything outside `docs/user/` (resolved
  against the files and labels in the tree), and no user page contains the string
  `/developer/` or the words "developer guide";
- the banned words of §5.2 do not appear (case-insensitive, whole words), and neither does
  the contrast construction, checked as the regular expressions `,\s+not\s`, `—\s*not\s`,
  and `\brather than\b`;
- no user page contains `--`, more than two em dashes, a line beginning with a comma, or
  more than 250 lines;
- every email purpose label from `apps/mail/purposes.py` appears somewhere in `docs/user/`;
- `docs/conf.py` no longer defines `_unpublished_developer_reference` or `_developer_titles`,
  and `make guide`'s build has no special case for links into the developer guide (the
  handler and its helper are deleted in this package once the pages are clean).

`frontend/src/portal/help.test.ts` (wave 2 addition): every route path in `routes/index.tsx`
matches a `HELP_PAGES` entry, and every slug in `HELP_PAGES` is a file `docs/user/<slug>.rst`
read from the repository (Vitest may read the filesystem).

`docs/developer/documentation.rst` and `testing.rst` describe these tests.

## 6. Failure handling and the final report

- **A failing gate.** Three fix attempts within scope; then the PR stays open as a draft with
  a comment saying what failed, and the orchestrator carries on with every package that does
  not depend on it.
- **A rebase conflict outside the package's files.** Same.
- **CI red on `main`.** No new package starts until a fix PR restores it.
- **The final report** lists every PR merged, every page of the new user guide, every
  developer chapter rewritten, every procedure verified, and every decision taken that §5 did
  not cover.
- **Archive.** The closeout PR moves this plan to `plans/archive/`.

## 7. Work packages

### Wave 1

#### guide-infra (Opus)

- **Branch:** `docs/guide-infra`; database `caldart_guide_infra`
- **Owns:** `docs/conf.py#static`, `docs/_static/**` (new), `docs/developer/documentation.rst` (new), `docs/developer/index.rst#documentation`, `docs/developer/deployment.rst#diagram`, `docs/developer/payments-setup.rst#diagram`, `backend/tests/test_user_guide.py#assets`, `Makefile#docs-comment`.
- **Steps:** §5.5 except the diagrams in `data-model.rst` and `overview.rst`, which belong to `dev-api-schema` and `user-member`; write `documentation.rst` including the diagram rules and the §5.2 voice in brief, and describe the §5.7 tests as planned (present tense, "the test suite checks that…", with the module names).
- **Verify:** `make docs`; open `docs/_build/guide/index.html` in a browser: a diagram shows **Open full size** and **Zoom**, Zoom opens and Escape closes; the deployment diagram is under 1000 pt wide.

#### help-button (Sonnet)

- **Branch:** `feature/help-button`; database `caldart_help_button`; e2e port 8211
- **Owns:** `frontend/src/portal/help.ts` (new), `frontend/src/portal/help.test.ts` (new), `frontend/src/portal/guide.ts`, `frontend/src/portal/guide.test.ts`, `frontend/src/portal/layout/PortalLayout.tsx#help`, `frontend/src/portal/layout/PortalLayout.test.tsx#help`, `frontend/src/portal/portal.css#help`, `backend/templates/base.html#guide-link`, `backend/tests/test_user_guide.py#footer`, `frontend/e2e/public-site.spec.ts#guide`, `docs/developer/architecture.rst#help`.
- **Steps:** §5.3 in full.
- **Verify:** `make test e2e`; `make lint`; in `make run`, the Help link on `/portal/profile` opens `/docs/member/profile/` in a new tab (a 404 until the pages land is expected in this wave).

#### user-member (Opus)

- **Branch:** `docs/user-member`; database `caldart_user_member`
- **Owns:** `docs/user/index.rst#root-and-member`, `docs/user/quick-start.rst` (new), `docs/user/overview.rst`, `docs/user/roles.rst` (new), `docs/user/faq.rst`, `docs/user/member/**`, and the deletion of `docs/user/getting-started.rst`, `docs/user/member-guide.rst`, `docs/user/payments.rst`, `docs/user/donations.rst`.
- **Steps:** write every `member/` page of §5.1, `quick-start` (an account; adding an aircraft; becoming a member or a friend and back; paying, renewing, and giving; each as a short numbered walk with the exact button names), `overview`, `roles` (screens in bold, no links yet), and `faq` (short answers that link to the pages in this group; questions about other groups' screens are rewritten to point at the group index); the member lifecycle diagram top-to-bottom per §5.5; the `member/index.rst` toctree; remove the four deleted pages from `docs/user/index.rst`. The member half of `aircraft.rst` moves into `member/my-aircraft`; the page itself is deleted by `user-admin`.
- **Verify:** `make docs`; `grep -rn "developer" docs/user/member docs/user/*.rst` finds nothing; no page over 250 lines.

#### user-admin (Opus)

- **Branch:** `docs/user-admin`; database `caldart_user_admin`
- **Owns:** `docs/user/index.rst#admin`, `docs/user/admin/**`, and the deletion of `docs/user/aircraft.rst`, `docs/user/dart-leader-guide.rst`, `docs/user/user-administrator.rst`, `docs/user/account-administrator-guide.rst`, `docs/user/system-administrator-guide.rst`.
- **Steps:** write every `admin/` page of §5.1 (`admin/system` covers health, backups, the four jobs with their Run now panels, and the email log, in words a system administrator who is not a programmer can follow, with no commands); the `admin/index.rst` toctree; remove the five deleted pages from `docs/user/index.rst`.
- **Verify:** `make docs`; `grep -rln "manage.py\|systemctl\|journalctl\|\`\`" docs/user/admin` finds nothing.

#### user-finance-website (Opus)

- **Branch:** `docs/user-finance-website`; database `caldart_user_finance`
- **Owns:** `docs/user/index.rst#finance-website`, `docs/user/finance/**`, `docs/user/website/**`, and the deletion of `docs/user/treasurer-guide.rst`, `docs/user/website-administrator-guide.rst`.
- **Steps:** write every `finance/` and `website/` page of §5.1; the two group index toctrees; remove the two deleted pages from `docs/user/index.rst`.
- **Verify:** `make docs`; no page over 250 lines.

#### dev-api-schema (Opus)

- **Branch:** `docs/dev-api-schema`; database `caldart_dev_api_schema`
- **Owns:** `docs/developer/api-*.rst`, `docs/developer/data-model.rst`, `docs/developer/architecture.rst#routes`, `docs/developer/extending.rst#example`, `docs/index.rst#themes`, `docs/developer/reports.rst#slugs`.
- **Steps:** the API and schema corrections of §5.6, the three diagrams of §5.5 with fallbacks, and the schema in detail of §5.6.
- **Verify:** `make docs`; every model in `backend/apps/*/models.py` has a section; the three diagrams are each under 1000 pt wide.

#### dev-operations (Opus)

- **Branch:** `docs/dev-operations`; database `caldart_dev_operations`
- **Owns:** `docs/developer/setup.rst`, `docs/developer/local-development.rst` (new), `docs/developer/deployment.rst` (except `#diagram`), `docs/developer/backup-restore.rst`, `docs/developer/email.rst` (new), `docs/developer/configuration.rst`, `docs/developer/payments-setup.rst` (except `#diagram`), `docs/developer/index.rst#operations`, `docs/developer/testing.rst#seed-facts`, `deploy/caldart.env.example`, `deploy/apache/caldart.conf#tls-order`, `deploy/nginx/caldart.conf#tls-order`, `backend/apps/cms/seed_content_data.py` (moved from `management/commands/`), `backend/apps/cms/management/commands/seed_content.py#import`, `backend/tests/test_cms_seed_content.py#import`, `backend/tests/test_settings_fail_closed.py#env-example`.
- **Steps:** the operations chapters, corrections, and verification of §5.6.
- **Verify:** `make docs`; the PR body's verification list; `uv run backend/manage.py help` no longer lists `seed_content_data`.

### Wave 2

#### docs-tests (Opus)

- **After:** guide-infra, help-button, user-member, user-admin, user-finance-website, dev-api-schema, dev-operations
- **Branch:** `test/docs-consistency`; database `caldart_docs_tests`
- **Owns:** `backend/tests/test_docs_developer.py` (new), `backend/tests/test_docs_user.py` (new), `docs/conf.py#handler`, `frontend/src/portal/help.test.ts#completeness`, `docs/developer/documentation.rst#tests`, `docs/developer/testing.rst#docs-tests`, and `docs/**#test-fixes` for whatever the new tests find (a missing field in a table, a stray word, an undocumented route), each fixed at its page.
- **Steps:** §5.7 in full: write each test, watch it fail on what the wave-1 pages missed, fix the docs, then delete the `missing-reference` handler and its helper from `docs/conf.py` and prove `make guide` builds without them.
- **Verify:** `make test docs`; `grep -n "missing-reference\|_developer_titles" docs/conf.py` finds nothing.

### Wave 3

#### closeout (Sonnet)

- **After:** docs-tests
- **Branch:** `chore/documentation-overhaul-closeout`; database `caldart_docs_closeout`; e2e port 8212
- **Owns:** `docs/**#residue`, `frontend/src/**#residue`, `backend/**#residue`, `plans/2026-09-26-documentation-overhaul.md` (moves to `plans/archive/`).
- **Steps:** add the links between groups (`roles` to every screen page; `faq` answers to their pages; `quick-start` to the pages it walks through); read the whole user guide top to bottom in the built `docs/_build/guide` as a reader would, following every Help target from the running portal, and fix residue; read the developer guide's operations chapters once more against `deploy/`; confirm `make guide` output has no italic dead links; move the plan to the archive; the PR body lists every page of both guides.
- **Verify:** `make lint test check docs audit e2e` green.

## 8. Manifest

```json
[
  {"wave": 1, "package": "guide-infra", "model": "opus", "branch": "docs/guide-infra", "database": "caldart_guide_infra", "e2e_port": null, "closes": [], "refs": [], "after": []},
  {"wave": 1, "package": "help-button", "model": "sonnet", "branch": "feature/help-button", "database": "caldart_help_button", "e2e_port": 8211, "closes": [], "refs": [], "after": []},
  {"wave": 1, "package": "user-member", "model": "opus", "branch": "docs/user-member", "database": "caldart_user_member", "e2e_port": null, "closes": [], "refs": [], "after": []},
  {"wave": 1, "package": "user-admin", "model": "opus", "branch": "docs/user-admin", "database": "caldart_user_admin", "e2e_port": null, "closes": [], "refs": [], "after": []},
  {"wave": 1, "package": "user-finance-website", "model": "opus", "branch": "docs/user-finance-website", "database": "caldart_user_finance", "e2e_port": null, "closes": [], "refs": [], "after": []},
  {"wave": 1, "package": "dev-api-schema", "model": "opus", "branch": "docs/dev-api-schema", "database": "caldart_dev_api_schema", "e2e_port": null, "closes": [], "refs": [], "after": []},
  {"wave": 1, "package": "dev-operations", "model": "opus", "branch": "docs/dev-operations", "database": "caldart_dev_operations", "e2e_port": null, "closes": [], "refs": [266, 268], "after": []},
  {"wave": 2, "package": "docs-tests", "model": "opus", "branch": "test/docs-consistency", "database": "caldart_docs_tests", "e2e_port": null, "closes": [], "refs": [], "after": ["guide-infra", "help-button", "user-member", "user-admin", "user-finance-website", "dev-api-schema", "dev-operations"]},
  {"wave": 3, "package": "closeout", "model": "sonnet", "branch": "chore/documentation-overhaul-closeout", "database": "caldart_docs_closeout", "e2e_port": 8212, "closes": [], "refs": [], "after": ["docs-tests"]}
]
```
