# Documentation Critique Report

**Generated:** 2026-09-13
**Scope:** README.rst, PLAN.rst, docs/ (user guide, developer guide and API reference, how-tos), docstrings and JSDoc, Sphinx setup
**Rules applied:** `doc_python` (`.claude/rules/doc_python.md`); `python` §5 Docstrings
(`.claude/rules/python.md`); `javascript_typescript_best_practices` §7 Comments and
Documentation (`.claude/rules/javascript_typescript_best_practices.md`); `doc-readme`,
`doc-user-guide`, `doc-dev-guide`, `doc-how-to` (`.claude/skills/<name>/SKILL.md`). Every
referenced rule is present, so no checklist area was skipped.

**Basis.** This review covers branch `feature/dev-standards`, working tree of 2026-09-13.
Another session was committing on the branch during the review; at the end only
`docs/developer/testing.rst` and `pyproject.toml` had uncommitted changes, and every line
number cited below was re-checked against the final tree. Each finding was verified by reading
both the documentation and the code or configuration it describes.

## Executive summary

- **Overall assessment.** The set is large (about 10,300 lines of reStructuredText: README,
  PLAN, and 33 pages under `docs/`), carefully written, and mostly accurate.
  - **Strengths:** it builds clean, all 50 URL patterns in `backend/apps/*/api/urls.py` are
    documented somewhere, the permission matrix matches the permission classes on almost
    every row, and the role chapters largely match `frontend/src/portal/nav.ts`.
  - **Weakness 1, drift.** About a dozen claims contradict the code, and often each other.
    They are left over from code changes that did not update every page.
  - **Weakness 2, API page format.** The API pages explain behavior well in prose but lack
    the per-endpoint headings, status codes and JSON examples `doc-dev-guide` §6 requires.
  - **Weakness 3, missing developer-guide pieces.** Four of the five extension recipes are
    absent, there is no coding-conventions pointer, and no subsystem chapter ends with an API
    link.
  - **Weakness 4, README.** Four of its required sections are missing.
  - **Weakness 5, convention debt.** 138 British spellings, 18 relative cross-directory
    `:doc:` targets, about 60% of backend functions without docstrings, and 63% of exported
    frontend functions without JSDoc.
  - **The spec is stale too.** `PLAN.rst`, the authoritative specification, is out of date
    in about fifteen places.
- **Build health.** `make docs` (`sphinx-build -n -W`) passes with exit 0 and **zero
  warnings**.
  - Fresh full rebuilds (`-E -a`, `--keep-going`) also produce zero warnings, both with
    Graphviz on `PATH` and with it removed, so the `.. only::` fallback works.
  - There are no `nitpick_ignore` entries.
  - The one configuration defect is that `docs/conf.py:103` sets `nitpicky = False`, so
    nitpicky mode depends on the Makefile flag alone.
- **High priority** (wrong information a reader will act on):
  1. The profile-completeness rule is stated five different ways across the member guide,
     the demo walkthrough, `api-profile.rst` and `data-model.rst`; only one matches the code.
  2. `data-model.rst` carries a stale duplicate of four sections (lines 319-482) that
     contradicts the first copy and the code. Its ERD also labels `DartPage.dart` `PROTECT`,
     but the code uses `SET_NULL`.
  3. The user guide says website administrators cannot use Redirects and members cannot edit
     aircraft. Both are false.
  4. `configuration.rst` and `api-reference.rst` say an empty `AUTH_THROTTLE_*` value turns a
     throttle off. In fact it makes login, registration and password reset fail with a 500.
  5. `api-reference.rst` says `system_admin` passes every row. It does not pass the three
     owner-only payment-confirmation endpoints.
  6. README and `setup.rst` say `make help` lists every target, but it omits `make e2e`. The
     "In full" table also omits `check`, `audit` and `createdb`.
  7. The production `env $(grep ... | xargs)` invocation in `deployment.rst` and
     `backup-restore.rst` breaks on the shipped `DEFAULT_FROM_EMAIL` value.
- **Nice to have:** an American-spelling sweep, absolute cross-directory `:doc:` targets, the
  docstring and JSDoc backlog, workflow diagrams, real how-to articles, and README
  restructuring.

## 1. Documentation system and build

**Build (`doc_python` §5).**
- **`make docs`:** exit 0, "build succeeded", no warnings. That run was incremental, so it was
  repeated as a fresh `sphinx-build -n -W --keep-going -E -a` into a scratch directory:
  - with `/usr/bin/dot` available: zero warnings;
  - with `PATH` stripped, so `conf.py` takes the no-Graphviz branch: zero warnings.
- **Toctree:** no broken `toctree` entries and no orphan documents. All 33 pages under
  `docs/` are reachable from `docs/index.rst`.
- **Build output:** `docs/_build/` is git-ignored (`.gitignore`); single source tree with one
  `conf.py`.

**Sphinx configuration (`doc_python` §3).**
- `docs/conf.py:103` sets `nitpicky = False`. `make docs` and CI are nitpicky only because
  `Makefile:223` passes `-n`. Any other invocation (an editor preview, a bare `sphinx-build`)
  is silently not nitpicky. Set `nitpicky = True` so the configuration states the rule.
- `docs/conf.py:80-81` sets both `master_doc` and `root_doc`; only `root_doc` is needed.
  Minor, but the rule asks for a minimal file.
- The no-op `graphviz` directive registered in `setup()` (`docs/conf.py:45-76`) is justified
  and well commented. Keep it.
- `conf.py` as Python code (`python` rule §4-5):
  - `setup(app)` (line 45) has no type annotations, and its docstring has no `Parameters:`
    section.
  - `_NoGraphviz.run` (line 73) has no docstring.
  - Line 96 says "organisation's" (British spelling).
  - Line 115, "No custom static assets or templates yet", is time-anchored.

**Prose conventions (`doc_python` §2).**
- **American spelling: 138 British spellings in 28 `.rst` files.** "aeroplane(s)" alone
  appears 54 times; "airplane" never does. Examples:
  - `docs/index.rst:6` "organises", `docs/index.rst:66` "aeroplane";
  - `README.rst:141` "Licence";
  - `PLAN.rst:250` "normalised", and "colour" at `PLAN.rst:598/604/618/627`;
  - `docs/user/getting-started.rst:22` "capitalisation", `:119` "recognises";
  - `docs/user/account-administrator-guide.rst:150,218-220` "cheque";
  - `docs/developer/theming.rst`, 7 uses of "colour"/"colours";
  - `docs/developer/roadmap.rst` "catalogue", "enrolment", "behaviour".

  Code has 61 more in `.py`/`.ts` comments, docstrings and UI strings, and `Makefile:226`
  ("Remove build artefacts") appears in `make help`. Some doc spellings quote UI text, e.g.
  the Site settings panel heading "Organisation" (`backend/apps/cms/models.py:474`). Change
  such a label and its doc together.
- **Time-anchored framing** (few instances, but present):
  - `README.rst:144` "Not yet licensed";
  - `docs/user/website-administrator-guide.rst:268` "not currently granted" (also false, §5);
  - `docs/developer/data-model.rst:463` "currently read by nothing" (also false, §6);
  - `docs/user/faq.rst:110` "does not send a receipt of its own yet";
  - `docs/developer/roadmap.rst:39,45,76,95` "today", and `:81` "which they currently
    ignore";
  - `docs/developer/deployment.rst:390` "not backwards compatible";
  - `docs/conf.py:115` "yet".
- **Terms defined on first use:**
  - "DART" is expanded ("Disaster Airlift Response Team") only in
    `docs/developer/data-model.rst:222`. README, `docs/index.rst` and the user guide never
    expand it, although they use it from the first paragraph.
  - "N-number", "BasicMed" and "flight review" appear throughout the user guide without
    definition. `docs/user/aircraft.rst:11-24` explains an N-number's canonical form but not
    what one is.
- **Unicode inside `.py` files.** 158 lines in 47 `.py` files (migrations excluded) contain
  em/en dashes, smart quotes or arrows. Examples:
  - `backend/apps/cms/blocks.py:49` (smart quotes in a `help_text`);
  - `backend/apps/cms/management/commands/seed_content.py:216`;
  - `backend/caldart/settings/prod.py:3`;
  - `backend/tests/test_cms_pages.py:296` (a left arrow).

  The section sign (220 uses) is not on the banned list.

## 2. Docstrings and code documentation

Measured with an AST walk over `backend/` (migrations excluded) and a scan of exported
functions and components in `frontend/src/` (tests excluded).

**Backend coverage** (`python` §5: "a docstring for every module, class, function, and method").

| | Modules | Classes | Functions and methods |
|---|---|---|---|
| App code | 7 of 94 missing (the seven `apps.py`) | 104 of 252 missing (53 of 201 excluding `Meta`) | 235 of 390 missing |
| Tests | 0 of 36 missing | 20 of 21 missing (factories, their `Meta`, one helper view) | 748 of 833 missing |

- **Undocumented non-trivial app code**, examples:
  - 38 DRF handler methods (`get`, `post`, and so on), e.g.
    `backend/apps/accounts/api/views.py:47,58,72`;
  - serializer validators: `backend/apps/accounts/api/serializers.py:96` `validate_email`,
    `:210` `validate_roles`, `:220` `update`;
  - `User` helpers: `backend/apps/accounts/models.py:104` `has_any_role`, `:110` `add_role`,
    `:114` `remove_role`;
  - the throttle classes: `backend/apps/accounts/throttling.py:43,47,51`;
  - management-command classes and `handle` methods: `seed_demo.py:33,45`,
    `seed_roles.py:20,23`.
- **Too thin to write a black-box test from.** 29 app functions of 15 or more lines carry a
  one-line docstring:
  - `backend/apps/payments/providers/stripe.py:172` `handle_webhook` (38 lines);
  - `backend/apps/payments/providers/paypal.py:210` `confirm` (45 lines);
  - `backend/apps/members/api/admin_filters.py:72` `membership_annotations` (44 lines);
  - `backend/apps/cms/permissions.py:95` `grant_website_admin_permissions` (37 lines).

  Also, 125 documented functions that take parameters have no `Parameters:` section, e.g.
  `backend/apps/accounts/permissions.py:23` `user_has_any_role` and
  `backend/apps/accounts/services.py:52` `sync_django_flags`.
- **Format.** Good: no `Args:` sections and no ticket numbers. Two docstring lines exceed 90
  characters: `backend/apps/cms/models.py:263` (93) and
  `backend/tests/test_cms_seed_content.py:1` (91).
- **Change history in docstrings, or inaccurate docstrings:**
  - `backend/tests/test_integration.py:52` "The portal's form used to insist on it..." and
    `:109` "``apps.members`` used to carry its own copy..." (plus the test name
    `test_db_reset_seed_no_longer_swallows_a_failure` at `:126`);
  - `backend/apps/accounts/throttling.py:9-11` says the test settings leave the scopes
    "missing entirely", but `backend/caldart/settings/test.py:11` maps them to `None`;
  - `backend/apps/members/models.py:171` says `COMPLETE_FIELDS` are "the fields PLAN §6.1
    names", but PLAN §6.1 names no fields.

**Frontend JSDoc (`javascript_typescript_best_practices` §7).**
- **139 of 222 exported functions and components have no JSDoc.** Examples:
  - the route guards `RequireAuth`, `RequireRole` and `Forbidden`
    (`frontend/src/portal/auth/guards.tsx:33,47,62`);
  - the shared primitives `Button` (`components/Button.tsx:25`), `DataTable`
    (`components/DataTable.tsx:60`), `StatusChip` (`components/StatusChip.tsx:51`), and
    `ToastProvider`/`useToast` (`components/Toast.tsx:26,53`);
  - every page component under `features/*/`, and nearly every data hook in
    `features/*/api.ts` (`useAdminUsers`, `useMembers`, `useReminderLog`, ...).
- **Modification history in JSDoc and comments:**
  - `frontend/src/portal/features/profile/AircraftEditor.tsx:4-7` ("`AircraftPermission` has
    always said so -- but the only edit form used to be the account administrator's...");
  - `frontend/src/portal/nav.ts:27-28` ("without an entry here nothing in the portal linked
    to it").

## 3. Cross-reference completeness

- **Python roles.** None appear in `docs/`, `README.rst` or `PLAN.rst`. Good.
- **Relative cross-directory `:doc:` targets (`doc-user-guide` §1).** All 18 cross-directory
  targets use `../`; none are absolute.
  - Nine are in `docs/user/system-administrator-guide.rst`, at lines 98, 128, 159-163, 204
    and 215.
  - Others: `docs/user/index.rst:38`, `docs/developer/index.rst:14`,
    `docs/developer/setup.rst:8`, `docs/developer/testing.rst:311`,
    `docs/user/user-administrator.rst:202`, `docs/user/aircraft.rst:164`,
    `docs/user/account-administrator-guide.rst:200`,
    `docs/user/website-administrator-guide.rst:260`, `docs/user/payments.rst:178`.

  Convert them to `` :doc:`/developer/...` `` and `` :doc:`/demo-walkthrough` ``.
- **Bare titles instead of links (`doc_python` §4).**
  - `docs/user/system-administrator-guide.rst:12` "is in the developer guide";
  - `:51` "see the deployment guide's troubleshooting section". The target
    (`docs/developer/deployment.rst:393`, "Troubleshooting") has no label to `:ref:`, so add
    one.
- **Pages that should link but do not:**
  - `docs/user/member-guide.rst` has no `:doc:` links at all, although `payments.rst` and
    `aircraft.rst` cover the same workflows in more depth.
  - `docs/developer/payments-setup.rst`, `reminders.rst`, `backup-restore.rst` and
    `theming.rst` have no `:doc:` links, so none of them points to its API page.
  - `docs/user/faq.rst:5-6` promises "Each one points at the page that covers it properly",
    but only 5 of its 17 answers carry a link.
- **Stale references:**
  - `docs/developer/api-profile.rst:145` and `docs/developer/data-model.rst:466,478` cite
    `PROFILE_COMPLETE_FIELDS` in `apps/accounts/api/serializers.py`. No such constant exists.
    The flag is `profile.is_complete` (`backend/apps/accounts/api/serializers.py:52-55`),
    which reads `MemberProfile.COMPLETE_FIELDS` (`backend/apps/members/models.py:175`).
  - `docs/developer/reports.rst:202-207` warns that `is_active` is missing from
    `AircraftExportMixin.applied_filters`. It is present
    (`backend/apps/aircraft/api/views.py:114-121`). Delete the warning.
- **File paths used as page references in `PLAN.rst`** (which Sphinx includes):
  - `PLAN.rst:625` "documented in ``docs/developer/theming.rst``";
  - `PLAN.rst:696` "Documented in ``docs/developer/deployment.rst``".

  Low priority, since PLAN is also read on GitHub.

## 4. README

Checked against `doc-readme` §§1-3.

- **Format.** It is reStructuredText with one over-and-underlined title and `=` section
  underlines. The title is "CalDART — website and member management system"
  (`README.rst:2`) rather than the project name alone.
- **Required sections.**
  - Present:
    - an introduction (lines 5-10) that correctly names `PLAN.rst` as authoritative;
    - a combined requirements, setup and quick start (13-43);
    - demo accounts (46-65);
    - everyday commands (68-83);
    - end-to-end tests (86-125);
    - layout (128-138);
    - "Licence" (141-144).
  - Missing or not conforming:
    - **Features.** There is no bulleted feature list. It should mirror "What it does"
      (`docs/index.rst:53-78`, ten bold-lead-in bullets). The two introductions
      (`README.rst:5-7`, `docs/index.rst:5-15`) also describe the system differently.
    - **Requirements and setup.** This should be its own section, pointing to
      `docs/developer/configuration.rst` for `.env` settings. The README never mentions
      `configuration.rst`.
    - **Documentation.** No section says `make docs` writes `docs/_build/html/index.html`.
    - **Contributing.** No pointer to `CLAUDE.md`, or to the "Before you open a pull request"
      section (`docs/developer/setup.rst:309`).
    - **License.** It is spelled "Licence" and says "Not yet licensed for redistribution"
      (`README.rst:141-144`). The rule wants "License" and a plain statement that the code is
      not licensed for redistribution (there is no license file).
- **Accuracy:**
  - **`make help`.** `README.rst:81` ("make help # every target") and `:83` ("Run
    ``make help`` for the full list") are false. The help recipe's pattern
    `^[a-zA-Z_-]+:` (`Makefile:60`) cannot match `e2e:`. So `make help` omits `make e2e`,
    the very target the README documents next, plus every target without a `##` comment
    (`wait-db`, `lint-backend`, `lint-frontend`, `check-backend`, `check-frontend`,
    `audit-backend`, `audit-frontend`).
  - **Node version.** `README.rst:16` says "Node 20+". The lockfile pins vitest 4.1.11
    (engines `^20.0.0 || ^22.0.0 || >=24.0.0`) and eslint 9.39.5 (engines
    `^18.18.0 || ^20.9.0 || >=21.1.0`). That rules out Node 20.0-20.8, 21 and 23. CI uses 22
    (`.github/workflows/ci.yml:74`). State "Node 22 (or 20.9+ or 24+)".
  - **Checked and correct:** demo accounts, generated counts (40 members, 25 aircraft, 24
    months of payments), URLs and compose ports match
    `backend/apps/accounts/seed.py:26-49`, `backend/apps/aircraft/seed.py:9`,
    `backend/apps/payments/seed.py:25`, `backend/caldart/urls.py` and `docker-compose.yml`.
    `make migrate` does create the role groups
    (`backend/apps/accounts/migrations/0002_seed_roles.py`).
  - **`make seed` comment.** The comment at `README.rst:25` omits that `make seed` also runs
    `seed_content` (`Makefile:100`).
- **Summary, not manual.** The end-to-end section (`README.rst:86-125`) is 40 lines,
  including `sudo` and headed-mode recipes. That is manual-level detail for
  `docs/developer/testing.rst`, and the section has no link there (`doc-readme` §2: keep such
  sections short and link to the developer guide).

## 5. User guide

**Layout (`doc-user-guide` §1).**
- **Landing page.** `docs/user/index.rst` has captioned toctrees ("For members", "For leaders
  and administrators", "Reference"), with `getting-started` first and the FAQ under
  Reference. It also carries two extra prose paragraphs (lines 9-11, 38-39); the rule allows
  a 1-2 sentence introduction and no other prose.
- **Chapters.** All six role chapters, plus `payments.rst` and `aircraft.rst`, exist. The
  latter two sit under "For members", but their second halves are account-administrator
  material.
- **Links.** The cross-directory `:doc:` targets are relative (§3).

**Required content (`doc-user-guide` §2).**
- **Present and good:**
  - an introduction;
  - getting started: accounts, sign-in, forgotten and changed passwords, throttling, roles
    (`docs/user/getting-started.rst`);
  - browser-side configuration: Site settings in the website-administrator guide, roles in
    the user-administrator guide, backups and reminders in the system-administrator guide,
    with a pointer to the configuration page (`system-administrator-guide.rst:161`);
  - step-by-step screens with expected results.
- **Missing: the overview.** No page describes the end-to-end workflow: join and pay, the
  membership term, the renewal reminders, the profile and aircraft a leader checks, and what
  each administrator looks after. There is also no diagram, although the flow has more than
  two stages.
- **Examples.** The demo walkthrough is linked only from `docs/user/index.rst:38`. No role
  chapter links to its matching flow (e.g. `dart-leader-guide.rst` to flow C,
  `website-administrator-guide.rst` to flow E).

**Role accuracy against `nav.ts`, the code and PLAN.**
- **The account-administrator chapter is incomplete.**
  `docs/user/account-administrator-guide.rst:9-11` says "Everything lives under **Members**
  in the portal menu". But `account_admin` also gets **Aircraft** and **Payments**
  (`frontend/src/portal/nav.ts:47-48`) and **Member check** and **Aircraft check**
  (`nav.ts:33-44`). Those screens are documented in `aircraft.rst`, `payments.rst` and
  `dart-leader-guide.rst`, none of which this chapter links to.
- **Reminder log.** `docs/user/system-administrator-guide.rst:124-125` says "Account
  administrators can see this log too."
  - The API does allow it (`backend/apps/reminders/api/views.py:47`).
  - But the only screen is `RemindersPanel` on `/portal/system`
    (`frontend/src/portal/features/system/SystemPage.tsx:16`), which is gated to
    `system_admin` (`frontend/src/portal/routes/system.tsx:9`, `nav.ts:51`).
  - So an account administrator cannot see the log in the portal.
- **Superuser.** `docs/user/system-administrator-guide.rst:25-26` says you can sign in to the
  Django admin "if your account is also a superuser". Holding `system_admin` always sets
  `is_superuser` (`backend/apps/accounts/services.py:60`), as
  `docs/user/user-administrator.rst:90-91` correctly says.
- **Redirects.** Two statements are false:
  - `docs/user/website-administrator-guide.rst:266-269` "the ``website_admin`` role is not
    currently granted permission to use it";
  - `:306-310` "the Redirects tool is not part of what ``website_admin`` grants".

  `backend/apps/cms/permissions.py:52-56` grants `add_redirect`, `change_redirect` and
  `delete_redirect`, and migration
  `backend/apps/cms/migrations/0004_website_admin_permissions.py` applies them.
- **Member aircraft editing.**
  - `docs/user/aircraft.rst:56-59` says "There is no member-facing screen for editing an
    aircraft -- not even one you added". That contradicts the same page (`:161-165`),
    `docs/user/member-guide.rst:174-177`, and the code:
    `frontend/src/portal/features/profile/MyAircraftPage.tsx:74-81` shows **Edit** on every
    attached aircraft, and `AircraftEditor.tsx:62-74` opens the form for the record's
    creator. Anyone else sees "Someone else added this aircraft".
  - `member-guide.rst:249-250` ("only the member who added it sees **Edit**") is also
    inaccurate: everyone sees **Edit**; non-creators get the explanation card.
- **Profile completeness: one rule, several versions.** The code has one list: phone, address
  line 1, city, ZIP, and certificate type (`backend/apps/members/models.py:175-181`, mirrored
  in `frontend/src/portal/features/profile/form.ts:184-190`).
  - `docs/user/member-guide.rst:32-43` states it correctly ("a form that saves is a profile
    that lets you move on").
  - `:232-237` of the same page contradicts it: the nudge wants "phone, address line 1,
    city, state and ZIP", and "a profile that saved cleanly can still be counted as
    unfinished".
  - `docs/demo-walkthrough.rst:105-106` says "Phone, city, state and postal code are what
    the form insists on", contradicting its own lines 205-206.
  - The developer-side versions are covered in §6.
- **Getting-started role table and menu.**
  - `docs/user/getting-started.rst:74-75` (the `account_admin` row) omits the leader checks
    and deleting members.
  - The **Membership** group description (`:167-168`) omits **Change password**
    (`nav.ts:29`).
- **Labels that do not match the UI.** `doc-user-guide` §4 says to name every screen and
  control "exactly as the portal or the Wagtail admin shows it".
  - **Mock provider.** The portal labels it "Test payment"
    (`frontend/src/portal/features/checkout/api.ts:72`), and "Test" in the filters
    (`frontend/src/portal/choices.ts:115,131`).
    - `docs/user/faq.rst:82-83` says "a single **Mock** panel";
    - `docs/demo-walkthrough.rst:120-121` says "the only tab is **Mock**";
    - `docs/demo-walkthrough.rst:306-308` says "everything under ``mock``".

    `docs/user/payments.rst:59,148,207` gets it right.
  - **Forgot-password link.** `docs/user/faq.rst:182` says "**Forgot password**"; the link
    reads "Forgot your password?"
    (`frontend/src/portal/features/auth/LoginPage.tsx:82`).
  - **Duplicate-email message.** `docs/demo-walkthrough.rst:142` quotes "A user with this
    email already exists." The register serializer says "An account already uses that email
    address. Sign in, or reset your password."
    (`backend/apps/accounts/api/serializers.py:100`).
  - **Site settings field names** (`docs/user/website-administrator-guide.rst:222-236`). The
    fields declare no `verbose_name` (`backend/apps/cms/models.py:450,459,460`), so Wagtail
    labels them "Org name", "Facebook url" and "Twitter url", not "Organisation name" and
    "Facebook / X URL".
- **Checked and correct:**
  - `dart-leader-guide.rst` roles and entry names;
  - the insurance chips on the leader card (`frontend/src/portal/features/aircraft/insurance.ts:40-45`)
    and on My aircraft (`frontend/src/portal/components/StatusChip.tsx:73-87`);
  - the 403 page wording (`frontend/src/portal/auth/guards.tsx:62-77`);
  - the user-administrator filters (`features/admin-users/UsersListPage.tsx:105-129`);
  - the health thresholds of 2048/512 MB and 7/30 days (`features/system/HealthPanel.tsx:26-31`);
  - the twenty-row reminder log (`features/system/api.ts:29`);
  - Stripe receipts (`receipt_email`, `backend/apps/payments/providers/stripe.py:120`).

**Operator commands (`doc-user-guide` §3).** The system-administrator guide delegates to the
developer pages (the table at lines 156-164), but:
- **Bare commands.** It shows `manage.py health --json` (168, 239-240), `manage.py db_backup`
  (199) and `manage.py migrate` (56, 213) bare. None runs as written on the server, and those
  lines do not link to the page that has the full invocation.
- **Missing commands.** `db_reset`, and the `make backup`, `make restore` and
  `make reminders` wrappers, are not mentioned anywhere in `docs/user/`.
- **Option drift in the "complete" command table:**
  - `docs/developer/setup.rst:295` lists `db_backup` without `--name`
    (`backend/apps/sysadmin/management/commands/db_backup.py:12`);
  - `:301-302` lists `health` without `--json` (`health.py:14`), and with only four of its
    six facts;
  - flag aliases (`db_restore --noinput`/`--no-input`, `db_reset --no-input`) are documented
    nowhere.
- **Make-variable semantics are undocumented and dangerous.** Any non-empty value turns the
  option on:
  - `make restore FILE=... YES=0` still passes `--yes`, which skips the confirmation on a
    destructive command (`Makefile:112`);
  - `make reminders DRY_RUN=0` still does a dry run (`Makefile:219`).

  The docs only ever show `YES=1` and `DRY_RUN=1`.
- **Output formats.** `health --json` is partly documented
  (`docs/developer/backup-restore.rst:175-187`), which calls it "what to point a monitoring
  check at". But it never says the command always exits 0, even when the database is down
  (`health.py:16-23` has no failure path), and it gives no sample output.
- **Pages disagree:**
  - **Default `pg_dump`.** `docs/developer/deployment.rst:56-58` and `setup.rst:36-38` say
    the local binary is preferred. `backup-restore.rst:32` says the container is the
    default, which matches the code: the container is used whenever Docker exists and
    `DB_BACKUP_VIA_DOCKER` keeps its default of `true`
    (`backend/apps/sysadmin/services.py:80-84`, `backend/caldart/settings/base.py:244`).
  - **Downloadable backup names.** `system-administrator-guide.rst:207-210` says only
    `caldart-....sql.gz` names can be downloaded. `backup-restore.rst:19-23` recommends
    `--name before-the-schema-change.sql.gz`, which the pattern
    `^[A-Za-z0-9][A-Za-z0-9._-]*\.sql\.gz$` accepts (`backend/apps/sysadmin/services.py:29`).
  - **Health facts.** `setup.rst:302` and `demo-walkthrough.rst:386-388` list four; the code
    and the other pages list six.

## 6. Developer guide and API reference

**Layout (`doc-dev-guide` §1).**
- Conforms: `docs/developer/index.rst` has captioned toctrees in the prescribed order, the
  five `api-<area>.rst` pages are in the toctree of `api-reference.rst`, and
  `architecture.rst` includes `PLAN.rst` under a `#` title so the plan nests.
- Gap: the landing page's opening (`docs/developer/index.rst:5-7`) describes the content, not
  the reader, and never says how this guide differs from the user guide.

**Required chapters (`doc-dev-guide` §2).**
- **Coding-conventions pointer: absent.** No page under `docs/developer/` mentions
  `CLAUDE.md` or `.claude/rules/`.
- **Repository layout** (`PLAN.rst` §3, lines 87-135) omits:
  - `.claude/`, `.github/`, `.python-version`;
  - `frontend/src/portal/auth/`, `frontend/src/portal/layout/`,
    `frontend/src/portal/choices.ts`, `frontend/src/test/`;
  - the per-app `seed.py` modules;
  - `backend/caldart/{reports,pagination,exceptions,views}.py`.
- **Environment setup:**
  - **Make targets.** `docs/developer/setup.rst:211` says "``make help`` lists them all",
    which is false (§4).
    - The "In full" table (`:213-273`) omits `help`, `createdb`, `check`, `check-backend`,
      `check-frontend`, `audit`, `audit-backend` and `audit-frontend`.
    - Its `docs` row (`:270`) says "``sphinx-build -W``"; the Makefile runs `-n -W`
      (`Makefile:223`).
    - Its `e2e` row (`:253-254`) says only "``npm run e2e``". The target actually creates a
      database, reseeds, builds, collects static files and starts its own server
      (`Makefile:149-173`).
  - **Test and build environment variables are documented nowhere in `docs/`:** `E2E_PORT`,
    `E2E_DB`, `E2E_DATABASE_URL`, `E2E_LOG`, `SKIP_CREATEDB` (`Makefile:23-26,151`), and
    `E2E_BASE_URL` and `CI` (`frontend/playwright.config.ts`).
  - **Pre-PR commands.** `setup.rst:312` ("Five commands must be green, and CI runs all
    five") leaves out `make e2e`, which CI runs as its own job
    (`.github/workflows/ci.yml:111-170`).
  - **Smoke test.** None is given after `make run`: nothing says what a working result looks
    like.
  - **CI trigger.** `docs/developer/testing.rst:5-6` says "all of which CI runs on every
    push". CI runs only on pushes to `main` and on pull requests (`ci.yml:3-6`).
- **Configuration.** Every variable the settings read is documented, but
  `docs/developer/configuration.rst:117-119` says an empty `AUTH_THROTTLE_*` value "turns
  that throttle **off**, which is what ``caldart.settings.test`` does". That is wrong:
  - The rates are read with non-`None` defaults (`backend/caldart/settings/base.py:211-213`),
    so django-environ returns `""` for an empty variable.
  - DRF's rate parser then raises `ValueError`, so following the doc breaks login,
    registration and password reset.
  - `settings/test.py:11` sets the rates to `None` in Python; it does not use empty
    environment values.

  `docs/developer/api-reference.rst:228` repeats the claim.
- **Server upgrade.** It is documented (`docs/developer/deployment.rst:365-390`), but its
  commands are elided to `sudo -u caldart ... manage.py`, and the full form they stand for
  does not run.
  - `deployment.rst:184-186` and `backup-restore.rst:55-57` build the environment with
    `env $(grep -v '^#' /etc/caldart/caldart.env | xargs)`. That word-splits the shipped
    value `DEFAULT_FROM_EMAIL=CalDART <noreply@caldart.example.org>` (`.env.example:24`), so
    `env` tries to execute `<noreply@caldart.example.org>`.
  - The backup cron example (`backup-restore.rst:81-84`) loads no environment at all, so
    `prod.py` would fail for want of `SECRET_KEY` and the other required variables. It also
    continues a line with `\`, which cron does not support.

**Entity-relationship diagram and data model (`doc-dev-guide` §3).**
- **Conforms:** the Graphviz diagram is inside `.. only:: graphviz` and the ASCII version
  inside `.. only:: not graphviz`, with `:alt:` and `:caption:`
  (`docs/developer/data-model.rst:26-98`), followed by narrative for each app.
- **Duplicated, stale sections.** "Roles", "members", "``Dart``" and "``MemberProfile``"
  appear twice: at lines 167-318 and again at 319-482. The second copy's `is_complete` entry
  (`:458-479`) makes three claims, all false (§3):
  - that `is_complete` is "``phone`` **and** ``city`` **and** ``state`` **and**
    ``postal_code``";
  - that it is "currently read by nothing";
  - that it is not the rule behind `profile_complete`.

  Delete lines 319-482.
- **Wrong delete rule.** `DartPage.dart` is `on_delete=models.SET_NULL`
  (`backend/apps/cms/models.py:358-363`). But the diagram says "dart (PROTECT)"
  (`data-model.rst:64`, `:88`), and the prose says a DART with a page cannot be deleted
  (`:231`, `:383`, `:903`).
- **Missing from the diagram, though §3 requires them:**
  - the abstract `BasePage`, `MembersOnlyMixin` and `TimestampedModel` are not marked;
  - the payment `Provider` contract is not shown (`start`, `confirm`, `handle_webhook`;
    `backend/apps/payments/providers/base.py:27-47`);
  - `DartPage` is the only CMS model drawn.
- **ASCII diagram not equivalent.** `:69-70` says it "says the same thing", but it omits the
  `Membership.granted_by -> User` and `ReminderLog.user -> User` edges and every key field.
- **Mislabelled edge.** The User-Group edge is labelled "roles (m2m)" (`:51`), but the
  many-to-many field is Django's `groups`; `roles` is a derived property
  (`backend/apps/accounts/models.py:93-97`).
- **Caption.** It explains solid, double and `1--1` lines, but not the dashed and dotted ones
  the diagram also uses.
- **Timestamps.** `data-model.rst:18-20` (and `PLAN.rst:142`) say every model carries
  `created_at` and `updated_at`. The CMS page models and `SiteSettings` do not
  (`backend/apps/cms/models.py:69,447`).

**Per-subsystem prose (`doc-dev-guide` §4).**
- **No subsystem chapter ends with a link to its API page:**
  - `payments-setup.rst`, `reminders.rst`, `backup-restore.rst` and `theming.rst` contain no
    `:doc:` at all;
  - `reports.rst` links `api-members` once, mid-chapter (`:78`);
  - `cms.rst` links only `theming`.
- **`payments-setup.rst` is an operator setup guide, not a subsystem chapter.** It never:
  - names `backend/apps/payments/` or `frontend/src/portal/features/checkout/`;
  - describes the `Provider` contract, the registry (`register`, `get_provider`,
    `available_providers`; `providers/base.py:53-85`) or the error classes;
  - names the `StripeProvider`, `PayPalProvider` and `MockProvider` classes;
  - states the invariants: owner-only confirmation
    (`backend/apps/payments/api/views.py:53-64`), `mark_failed` never downgrading a
    succeeded payment, and the currency fixed to `usd`.
- **`reminders.rst:164-167` ("Changing which reminders exist").** It omits `KIND_ORDER`
  (`backend/apps/reminders/services.py:36`), which is what the scanner iterates (`:204`), so a
  kind added as the page says would never be scanned. It also omits the frontend
  `ReminderKind` and `KIND_LABELS`.
- **`cms.rst` has three errors:**
  - The `HandbookPage` example (`:106-114`) lists `FieldPanel("body")` but declares no `body`
    field, so Wagtail raises `FieldError` when it builds the edit form.
  - `:169-171` says "``DartPage`` has [a ``__str__``]". It does not
    (`backend/apps/cms/models.py:355-414`); `HomePage`, `StandardPage` and `NewsPage` do.
  - `:244-249` leaves out the redirect permissions (§5).
- **`reports.rst:202-207`:** a stale warning (§3).

**Extending the system (`doc-dev-guide` §5).**

| Extension point | Recipe | Code skeleton |
|---|---|---|
| Payment provider | **missing** (only a hint at `roadmap.rst:57-58`) | none |
| Wagtail page type / block | `cms.rst:161` "Adding a page type", `:132` "Adding a block" | **none** (numbered prose only) |
| API endpoint | **missing** | none |
| Portal screen | **missing** | none |
| Management command | **missing** (only the table at `setup.rst:278-305`) | none |

The recipes must also cover steps the skill's outline leaves out.
- **A provider recipe must also say:**
  - `available_providers()` hard-codes the three slugs (`providers/base.py:79-84`) instead of
    reading the registry;
  - the slug must be added to the `PaymentProvider` choices, which needs a migration;
  - each provider has its own confirm route (`backend/apps/payments/api/urls.py:13-17`);
  - the checkout needs a panel for it.
- **A portal-screen recipe must include editing `routes/index.tsx`,** which imports each
  route file explicitly (`frontend/src/portal/routes/index.tsx:15-24`).

**API reference (`doc-dev-guide` §6).**
- **Coverage.** All 50 URL patterns in `backend/apps/*/api/urls.py`, plus the Apple Pay route
  (`backend/caldart/urls.py:23-27`), are documented somewhere, and every documented endpoint
  exists. The reminder, system and site endpoints are listed at `api-reference.rst:628-674`.
- **Format gaps:**
  - `api-auth.rst` and `api-aircraft.rst` contain no `.. code-block:: json` at all. Their
    payloads are `::` literal blocks, some with placeholders such as `<aircraft summary>`
    and `...`.
  - `api-members.rst` uses topic headings ("List members", "Create a member", "Retrieve,
    update, delete", "Membership terms", "Exports") instead of method-and-path headings, and
    gives JSON only for the list response.
  - The reminder-log, reminder-run, health and backup list/create endpoints have no JSON
    example on any page. `cms.rst` is the only chapter that gives an endpoint
    (`GET /site/config`) a method-and-path heading.
  - Status codes missing:
    - the 204 for `DELETE /admin/members/{user_id}`, and every 404 on that page
      (`api-members.rst:240-245`);
    - 201/400/403/404/204 on the aircraft writes;
    - 429 under each throttled auth endpoint;
    - 401 on `POST /auth/password/change`;
    - the wrong-provider 400 on the confirm endpoints
      (`backend/apps/payments/api/views.py:62-63`);
    - the `group` 400 on `GET /admin/payments/summary`.
- **Accuracy:**
  - **Undocumented PUT.** `PUT /aircraft/{id}` is allowed (`AircraftDetailView` is a
    `RetrieveUpdateDestroyAPIView` with no `http_method_names`;
    `backend/apps/aircraft/api/views.py:76`). `api-aircraft.rst:126-137` documents only GET,
    PATCH and DELETE; the matrix (`api-reference.rst:454`) does list it.
  - **`system_admin` does not pass everything.** `api-reference.rst:240-243`
    ("**``system_admin`` passes everything.**", and superusers too) and `:257` ("passes
    every row") are false for three endpoints: `POST /payments/stripe/confirm`,
    `/payments/paypal/capture` and `/payments/mock/complete`. They filter by
    `user=request.user` with no role bypass (`backend/apps/payments/api/views.py:53-64`).
  - **Filter backends.** `api-reference.rst:161-171` says two list endpoints skip the default
    filter backends. The aircraft list replaces them too, which drops `SearchFilter`
    (`backend/apps/aircraft/api/views.py:60`).
  - **Error shape.** `api-reference.rst:184-185` promises field errors as lists, but several
    hand-raised errors are bare strings, e.g.
    `{"payment_id": "That payment is not a stripe payment."}` (`payments/api/views.py:63`).
  - **Endpoint count.** `api-reference.rst:208` says "Three anonymous auth endpoints", but
    four endpoints share the three throttle scopes.
  - **Throttle key.** `api-reference.rst:208-209`, `configuration.rst:115` and
    `getting-started.rst:155-156` say the auth throttles key on the client's address. With
    `NUM_PROXIES` unset, DRF keys on the whole `X-Forwarded-For` header when one is present
    (`rest_framework/throttling.py:29-40` in `.venv`). Behind the shipped Apache and nginx
    proxies, the limit is therefore per header value, which a client can vary.
  - **Checkout refusal.** `api-payments.rst:85-88` says a provider refusal at checkout is a
    400 that leaves nothing behind. Only `PaymentError` is caught
    (`payments/api/views.py:115-119`), and `stripe.PaymentIntent.create` is not wrapped
    (`providers/stripe.py:114`). A Stripe refusal is therefore a 500, and it leaves the
    pending `Payment` row behind.
  - **PayPal capture and datetimes.** `api-payments.rst:135` requires a `custom_id`, but the
    code checks it only when present (`providers/paypal.py:245-246`). The example datetimes
    (`:254-255`) end in `Z`, but `TIME_ZONE = "America/Los_Angeles"` with `USE_TZ` renders
    an offset (`backend/caldart/settings/base.py:141`).
  - **`api-profile.rst` has four errors:**
    - `:138-139` says the form requires "``phone``, ``city``, ``state`` and
      ``postal_code``"; it requires phone, address line 1, city, ZIP and certificate type
      (`form.ts:184-190`);
    - `:145-148` cites the non-existent `PROFILE_COMPLETE_FIELDS`;
    - `:260-262` says the aircraft summary serializer is declared locally; it is imported
      (`backend/apps/members/api/profile_serializers.py:14`);
    - `:128-130` says the cross-field rules see the row "as it would be". That holds for
      PATCH but not PUT: fields left out of a PUT are validated against their stored values
      and then reset (`profile_serializers.py:181-185,215-222`).
  - **Leader card without a profile.** `api-aircraft.rst:218-221` says a user with no
    profile gets both `go_no_go` flags false. The `membership` flag is computed from terms
    whether or not a profile exists (`backend/apps/aircraft/services.py:91`).
  - **Grant start date.** `api-members.rst:259-261` gives the grant start date as "the day
    after the current expiry for a current member, today otherwise". The code uses the
    latest `ends_on` of any active term (`backend/apps/members/services.py:41-50,157-160`),
    so a future-dated term moves the start.
- **Permission matrix against PLAN §5 and the permission classes.**
  - **The matrix itself.** Apart from the owner-only rows above, every row matches the
    `permission_classes`, object permissions and `http_method_names`.
  - **PLAN §5 has no matrix.** `PLAN.rst:364-369` is one sentence naming
    `HasRole("dart_leader")` and `HasAnyRole(...)` in `accounts/permissions.py`.
  - **The code differs from that sentence.** The leader check is gated by
    `IsLeader = HasAnyRole(DART_LEADER, ACCOUNT_ADMIN)`
    (`backend/apps/aircraft/api/views.py:33`), and the object permissions
    (`AircraftPermission`, `IsPaymentOwnerOrAccountAdmin`) live outside
    `accounts/permissions.py`.
  - **The skills point to a section that does not exist.** Both send readers to "the
    permission matrix (`PLAN.rst` §5)". The real matrix is `api-reference.rst:251-626`.

## 7. How-to articles

Checked against `doc-how-to`.
- **There are no how-to articles.** No page is titled "How to ...", and none sits in a
  guide's toctree as a task article. The only task-shaped page is `docs/demo-walkthrough.rst`,
  in the root toctree.
- **The walkthrough against the how-to structure.**
  - Good: prerequisites ("Before you start", `:16-80`), numbered steps with observed
    results, a "What to check" per flow (expected results), and "What can go wrong"
    (troubleshooting).
  - Lacking: an action-oriented title and a closing related-material section. It is also a
    tour of five tasks rather than one task.
- **Accuracy problems in the walkthrough:**
  - `:34-38` says side-by-side checkouts each use "its own port"; `make run` always binds
    8000 (`Makefile:123`).
  - `:105-106` gives the wrong required profile fields (§5).
  - `:120-121` and `:306-308` say "Mock" where the UI says "Test payment" and "Test" (§5).
  - `:142` quotes a duplicate-email message the system never shows (§5).
  - `:360-362` says a website administrator "cannot reach ``/django-admin/``". The
    `website_admin` role sets `is_staff` (`backend/apps/accounts/services.py:61`), and
    Django's admin admits any active staff user (`django/contrib/admin/sites.py:202-207`).
    So they can sign in; they just see an empty index.
  - `:386-388` lists four health facts; the panel shows six.
- **Candidates for real how-tos,** each linked from the chapter it serves
  (`doc-user-guide` §4):
  - "How to restore a backup" (operator; currently prose in `backup-restore.rst`);
  - "How to record a refund" (`payments.rst:162-178` is already two steps);
  - "How to grant a membership term by hand";
  - "How to add a payment provider" (contributor).

## 8. Diagrams and figures

Checked against `doc-how-to` §6 and `doc-dev-guide` §3.
- **The one diagram.** The whole set has a single diagram, the ERD in
  `docs/developer/data-model.rst`. It renders in both build modes, sits inline beside its
  prose, and has alt text and a caption. There are no images, so filename and alt-text
  checks are otherwise moot.
- **Its problems.** The ASCII fallback is not equivalent to the Graphviz version, and the
  content has the errors listed in §6.
- **Missing diagrams, where a picture would be clearer than prose:**
  - the member lifecycle (join, pay, term, reminders at t60/t30/t7/expired/post30, renew),
    for the user-guide overview;
  - the checkout, confirmation and webhook sequence, for `payments-setup.rst`;
  - the production topology (Apache, gunicorn, Django, Postgres, and the systemd reminder
    timer), for `deployment.rst`.

  Each needs the same Graphviz-plus-ASCII pair.

## 9. Change discipline and consistency

Checked against `doc_python` §6.

**Code changes that did not update the docs in the same change:**
- **Redirect permissions** for `website_admin` (`backend/apps/cms/permissions.py:52-56`): not
  reflected in `website-administrator-guide.rst:266-269,306-310`, `cms.rst:244-249` or
  `PLAN.rst:342-344`.
- **The member-side aircraft editor** (`AircraftEditor.tsx`): `aircraft.rst:56-59` still
  says there is none.
- **The single `COMPLETE_FIELDS` list** (`members/models.py:175`): stale in
  `api-profile.rst:138-148`, `data-model.rst:458-479`, `member-guide.rst:232-237` and
  `demo-walkthrough.rst:105-106`.
- **`is_active` in the aircraft PDF subtitle:** `reports.rst:202-207` still warns it is
  missing.

**Disagreements between pages:**
- which `pg_dump` is the default, which backup names can be downloaded, and how many facts
  `health` reports (§5);
- the mock provider's name and the duplicate-email message (§5);
- whether `system_admin` implies superuser (`system-administrator-guide.rst:25-26` against
  `user-administrator.rst:90-91`);
- the Node version ("20+" in README and `setup.rst`, against the lockfile and CI);
- the CI trigger (`testing.rst:6` and `PLAN.rst:754` say every push; `ci.yml:3-6` says pushes
  to `main` and pull requests).

**Disagreements with `PLAN.rst`.** PLAN is the specification; fix PLAN or the code in the
same change.
- **§2 and §15, CI.** The §2 CI row (`:74-75`) lists only backend tests, frontend tests with
  typecheck, and the docs build. CI also runs lint, check, audit, e2e and the production
  build. §15 (`:754`) says "every push".
- **§3, repository layout (`:87-135`):** the omissions listed in §6.
- **§4 and §4.1, domain model.**
  - "Every model has `created_at`/`updated_at`" (`:142`) is false for the CMS models.
  - "accounts initial data migration" (`:180-181`): it is `0002_seed_roles`.
- **§4.6, CMS permissions (`:342-344`):** omits the redirect permissions.
- **§4.7, sysadmin commands (`:355-361`).**
  - It says `db_backup` prefers a local `pg_dump`; the code prefers the container.
  - It omits `db_backup --name`, `db_restore --yes`, `db_reset --noinput`, `health --json`,
    and two of the six health facts.
- **§5 and §6.6, permissions and the leader check.** §5 (`:364-369`) has no matrix and names
  the wrong permission classes. §6.6 (`:458`) says the leader check is for `dart_leader`
  only; the code, `nav.ts`, `routes/leader.tsx` and every doc page also admit
  `account_admin`.
- **§6.3, profile endpoints (`:411`):** the heading says "— member", but the endpoints
  require only a signed-in user.
- **§6.5, aircraft endpoints:** omits `PUT /aircraft/{id}` and the `is_active` filter.
- **§6.8, payment summary (`:506-508`).** It lists only `from`/`to` as summary filters and a
  fixed three-key `by_provider`. The code accepts every filter and omits providers that took
  no money in the period.
- **§7, public site (`:540-542`).** It says `main.ts` sets the theme attribute (the server
  renders it) and the nav says "Login" (the code says "Log in").
- **§12 and §14, make targets (`:678-679`, `:708`, `:717`).** They omit `YES=` and `DRY_RUN=`,
  and `make reset` actually runs `db_reset --seed --noinput`.
- **§14, environment variables (`:727-735`).** The list omits:
  - `CSRF_TRUSTED_ORIGINS`;
  - the three `AUTH_THROTTLE_*` variables;
  - every production-only variable: `SECURE_*`, `DB_CONN_MAX_AGE`, `EMAIL_TIMEOUT`,
    `DJANGO_VITE_MANIFEST_PATH`, `LOG_LEVEL`, `ADMIN_EMAILS` and `WEB_CONCURRENCY`.
- **§16, docs tree (`:763-769`).** It lists the tree without `user-administrator`,
  `payments`, `aircraft`, `cms`, `reports`, `reminders`, or the `api-*` pages.

**Code issues the review surfaced.** These are outside a documentation fix; file them
separately and meanwhile document current behavior:
- the throttle identity is the whole `X-Forwarded-For` header, so it can be spoofed behind the
  proxy;
- an empty `AUTH_THROTTLE_*` value causes a 500;
- a Stripe refusal at checkout is a 500 that leaves an orphaned pending payment;
- `PUT /me/profile` can store a medical class without its expiry date;
- `?expiring_within=` on `/admin/members` is unbounded
  (`backend/apps/members/api/admin_filters.py:236-237`), so a huge value overflows into a 500,
  whereas the aircraft filter clamps its value;
- `YES=0` and `DRY_RUN=0` still enable their options (`Makefile:112,219`);
- `make help` drops `e2e` (`Makefile:60`);
- `available_providers()` ignores the provider registry.

## Recommended priorities

1. **Remove the wrong statements readers act on.** This is a small, high-value change:
   - delete `data-model.rst:319-482`, and change `DartPage` to `SET_NULL` in the diagram and
     prose;
   - make every profile-completeness statement match `COMPLETE_FIELDS`;
   - correct the Redirects and member-aircraft-editing claims;
   - correct the empty-throttle claim in `configuration.rst` and `api-reference.rst`;
   - correct "`system_admin` passes everything";
   - fix the `make help` and "In full" claims;
   - delete the stale `reports.rst` warning;
   - fix the `env $(... | xargs)` invocation and the cron example.
2. **Bring the API reference to the §6 format:**
   - method-and-path headings on `api-members.rst`;
   - a `.. code-block:: json` example and a status-code list for every response on all five
     pages;
   - a page or full section for the reminder and system endpoints;
   - `PUT /aircraft/{id}`.
3. **Update `PLAN.rst`,** since every page defers to it: §2, §3, §4, §4.6, §4.7, §5 (add the
   real matrix or point to `api-reference`), §6.3, §6.5, §6.6, §6.8, §7, §12, §14, §15 and
   §16.
4. **Fill the developer-guide gaps:**
   - a coding-conventions pointer;
   - extension recipes with code skeletons for a payment provider, an API endpoint, a portal
     screen and a management command, plus skeletons for the two CMS recipes;
   - an API link at the end of every subsystem chapter;
   - the `Provider` contract and the abstract models in the ERD;
   - the test and build environment variables.
5. **Finish the README and the user guide:**
   - README: Features, Requirements and setup, Documentation, Contributing and License
     sections;
   - a user-guide overview with a member-lifecycle diagram;
   - the missing pointers in the account-administrator chapter;
   - every quoted label matching the UI;
   - a complete operator-command reference: all options, the `YES=`/`DRY_RUN=` semantics,
     and the `health --json` exit status and sample output.
6. **Sweep the conventions:**
   - American spelling (138 in the docs, 61 in code);
   - absolute cross-directory `:doc:` targets (18);
   - `:ref:` labels in place of bare titles;
   - `nitpicky = True`;
   - the backend docstring and frontend JSDoc backlog. Start with the shared primitives, the
     permission classes, the payment providers and the route guards.

## Prompt for an AI agent to fix the documentation

```text
You are fixing the documentation of the caldart-proto repository (Django 5 + Wagtail backend in
backend/, React 19 + TypeScript frontend in frontend/). Read critiques/2026-09-13-documentation.md
in full first: it lists every problem with file paths and line numbers, grouped as
  1 documentation system and build, 2 docstrings and JSDoc, 3 cross-references, 4 README,
  5 user guide, 6 developer guide and API reference, 7 how-to articles, 8 diagrams,
  9 change discipline (including PLAN.rst disagreements and out-of-scope code issues).
Re-read each cited file before you edit it; line numbers may have moved.

Standards (authoritative; read them before editing):
- .claude/rules/doc_python.md (prose, conf.py, cross-references, build discipline, change
  discipline)
- .claude/rules/python.md §5 (docstrings) and
  .claude/rules/javascript_typescript_best_practices.md §7 (JSDoc)
- .claude/skills/doc-readme/SKILL.md, .claude/skills/doc-user-guide/SKILL.md,
  .claude/skills/doc-dev-guide/SKILL.md, .claude/skills/doc-how-to/SKILL.md
PLAN.rst is the specification. Where the report says the docs or the code disagree with
PLAN.rst, update PLAN.rst to describe the code's current behavior, unless the report lists the
code behavior as a bug.

Scope:
- Fix documentation only: README.rst, PLAN.rst, docs/**/*.rst, docs/conf.py, and docstrings,
  JSDoc and comments in backend/ and frontend/src/. Do NOT change production code behavior.
  A user-visible label may change only where the report says a doc and a UI label must agree.
- The items under "Code issues the review surfaced" (report §9) are out of scope. Do not fix
  them; document the current behavior accurately instead (for example: YES=0 still skips the
  restore prompt; an empty AUTH_THROTTLE_* value causes a 500 rather than disabling the
  throttle), and list them in your final summary as issues to file.

Order of work:
1. Remove wrong statements: delete docs/developer/data-model.rst lines 319-482 (the stale
   duplicate) and fix DartPage.dart to SET_NULL in both diagrams and the prose; make every
   profile-completeness statement match MemberProfile.COMPLETE_FIELDS (phone, address_line1,
   city, postal_code, pilot_certificate_type) in member-guide.rst, demo-walkthrough.rst,
   api-profile.rst and data-model.rst; correct the Redirects claims in
   website-administrator-guide.rst and cms.rst; correct aircraft.rst:56-59 and
   member-guide.rst:249-250 on member aircraft editing; correct the empty-throttle claim in
   configuration.rst and api-reference.rst; correct "system_admin passes everything" for the
   three owner-only payment confirmation endpoints; fix the "make help lists them all" claims
   and complete the setup.rst make-target table; delete the stale reports.rst warning; fix
   the env $(... | xargs) invocation and the cron example in deployment.rst and
   backup-restore.rst.
2. API reference (report §6): every endpoint gets its method and path as a heading, who may
   call it, request body and query parameters, and every response with status code and a
   `.. code-block:: json` example; document PUT /aircraft/{id}; give the reminder and system
   endpoints a full treatment; keep the permission matrix in api-reference.rst in exact
   agreement with the permission classes.
3. PLAN.rst (report §9): §2, §3, §4, §4.6, §4.7, §5, §6.3, §6.5, §6.6, §6.8, §7, §12, §14,
   §15, §16.
4. Developer guide (report §6): coding-conventions pointer to CLAUDE.md and .claude/rules/;
   extension recipes with minimal correct code skeletons (payment provider, API endpoint,
   portal screen, management command; add skeletons to cms.rst's page-type and block recipes
   and fix the HandbookPage example); an api-<area> link at the end of every subsystem
   chapter; the Provider contract and abstract models in the ERD; test/build environment
   variables; a smoke test in setup.rst.
5. README and user guide (report §§4-5): the missing README sections; a user-guide overview;
   account-administrator chapter pointers; every quoted label exactly as the UI shows it; a
   complete operator-command reference.
6. Conventions (report §§1-3): American spelling; no time-anchored wording ("new", "now",
   "yet", "currently", "used to", "no longer", "backwards compatible"); absolute
   cross-directory :doc: targets (:doc:`/developer/backup-restore`), relative ones within a
   directory; :ref: labels instead of bare titles; nitpicky = True in docs/conf.py; no unicode
   dashes, smart quotes or arrows in .py files; then the docstring and JSDoc backlog (report
   §2), starting with shared components, permission classes, payment providers and route
   guards.

Rules while editing:
- Code symbols, endpoints, file paths, settings and environment variables go in ``inline
  literals``; no Python roles (:class:, :func:) anywhere in docs/ or PLAN.rst.
- Any diagram you add or change: `.. graphviz::` inside `.. only:: graphviz` with an
  equivalent ASCII literal block inside `.. only:: not graphviz`; change both together.
- Same-change rule: when you rename, move or correct a page, label, endpoint, setting, command
  option or UI label, update every reference to it across README.rst, PLAN.rst, docs/ (user
  guide, developer guide, API pages, demo walkthrough, FAQ) and the docstrings in the same
  change. Grep for the old wording before you finish.

Build gate: `make docs` (sphinx-build -n -W: nitpicky, warnings are errors) must pass with zero
warnings before the work is considered done. Also build once with Graphviz absent from PATH,
for example
  env PATH=/nonexistent .venv/bin/sphinx-build -n -W -E -a -b html docs /tmp/docs-nodot
to prove the ASCII fallbacks. If you touched docstrings or JSDoc, `make lint` must pass too.
Finish with a summary that marks each report item as fixed, deferred (with the reason), or
out of scope (code issues to file).
```
