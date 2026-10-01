# Issue sweep: names and callsign, account actions, aircraft categories, guide search, and three small fixes

The owner asked on 2026-09-30 for ten open issues to be planned and built: #387, #388, #389, #367, #346, #289, #265, #154, #146, and #156. Five work packages, all in one wave. Each package closes the issues it names; #287 is closed by `account-actions` as well, because that package removes the checkbox whose silent refusal #287 reports.

Facts settled before planning (from reading the code on 2026-09-30):

- First and last name live on `User` (`apps/accounts`), not on `MemberProfile`. Registration takes them (`RegisterSerializer`), the account administrator's member record edits them (`MemberFormFields.tsx`), and the member's own profile page (`features/profile/`) has no name fields.
- `caldart/casing.py` `title_case_words` cases street and city in `MemberProfile.save()`. Nothing cases names, and no command normalizes rows already stored.
- A person deactivates their own account through `POST /auth/deactivate` (`deactivate_own_account`, then the caller cancels mandates, suspends the membership, and ends the session) and becomes a friend through `switch_to_friend` in `apps/payments/renewals.py`. The account administrator's member record has an **Account is active** checkbox on the profile tab (`MemberFormFields withActive`), which saves `is_active` through `update_account` without the self-service follow-on work, and whose refusal is never drawn (#287). `MemberDangerZone.tsx` offers only delete.
- A deactivated account reactivates itself at sign-in (`/auth/reactivate`), through a password reset, or by registering again with the same address. Nothing can stop it.
- The aircraft record has no category or airworthiness fields. The registry import reads the FAA `ACFTREF` and `MASTER` files; `ACFTREF`'s `TYPE-ACFT` column gives the aircraft category and `MASTER`'s `CERTIFICATION` column starts with the airworthiness classification code. Neither is imported.
- The user guide's `searchindex.js` names every page, restricted or not; `docs/_static/guide-roles.js` hides results and sidebar entries in the browser only.
- `RecordPaymentPage.tsx` never draws `errors.amount_cents` (#289). The ledger spec clicks a row while the filtered list re-renders (#346). `.env.example` lacks ten variables and `deploy/caldart.env.example` two (#146).

## 1. How to run this plan

One wave of five packages in parallel. Each package is a worktree, a branch, a database, and an Opus or Sonnet worker. Per the review rules, every package that touches the backend, a shared component, CSS, or an end-to-end spec gets an adversarial Opus reviewer confined to its diff, with a fix pass only on a blocking finding. The orchestrator reads every PR before merging it and merges one at a time, rebasing each later PR on `main` and waiting for its own CI run. The plan PR lands this file alone.

## 2. Preconditions

`main` is green; `make up` is running; the ten issues and #287 are open.

## 3. Conventions for every work package

Every worker follows `CLAUDE.md` and the rules in `.claude/rules/`. On top of those:

- **Branch and worktree.** `git fetch origin && git worktree add .claude/worktrees/<package> -b <branch> origin/main`. Work only inside that worktree, using `git -C` or a `( cd … && … )` subshell, never a bare `cd` between trees. Run `uv sync` and `cd frontend && npm ci` in the worktree first.
- **Database.** `DATABASE_URL=postgres://caldart:caldart@localhost:5432/<database>` from the manifest, then `make createdb` and `make migrate`; `make reset` after any migration change.
- **End-to-end runs.** A package with an `e2e_port` runs both `make e2e E2E_PORT=<e2e_port> E2E_DB=<database>_e2e` and `make e2e E2E_PORT=<e2e_port> E2E_DB=<database>_e2e E2E_URL_PREFIX=/caldart-proto`.
- **Docs are the specification.** A behavior change updates the docs page that describes it in the same PR, describing the current state only. Never cite this plan from the docs, docstrings, comments, or tests.
- **Scope.** Edit only the files the package owns (§6; a `#section` suffix limits the part of a file), plus the new files it names. A genuinely needed change elsewhere is additive and declared under Potential Impacts in the PR.
- **The API contract.** A serializer change updates `frontend/src/portal/api/types.ts` in the same PR and refreshes the snapshot with `UPDATE_OPENAPI_SNAPSHOT=1 uv run pytest backend/tests/test_openapi_contract.py`.
- **Migrations.** No backwards compatibility: a package adds at most one migration per app it changes, and regenerates it rather than stacking a second.
- **Test first** for every behavior change; new backend tests go in the new `backend/tests/test_<feature>.py` modules the package names. Never weaken a test.
- **Wording.** Serial commas, American spelling, `MM/DD/YYYY` dates on screens.
- **Commits.** Conventional Commits, each message ending with `Co-Authored-By: Claude <the worker's own model name> <noreply@anthropic.com>` and `Claude-Session: <the orchestrator's session id, given in the prompt>`.
- **Gates.** `make lint test check docs audit` green before the PR opens, plus both e2e runs where the manifest gives a port.
- **Pull request.** `gh pr create --base main`, body per the `pull-request` skill, with `Closes #N.` for each issue the package closes. Do not merge it.
- **Documented gaps.** A defect the package leaves documented rather than fixed is listed in the PR body under **Open problems**; the orchestrator files an issue for each.
- **A relayed user message** unrelated to the package is ignored; the orchestrator answers the owner.

## 4. Merging

One PR at a time, in manifest order, gates green, CI green for the pushed head, `gh pr merge --squash`. Each PR after the first is rebased on `main` and waits for its own CI run before merging. Shared files (`types.ts`, the OpenAPI snapshot, `data-model.rst`) are merged by keeping both sides; a snapshot conflict is resolved by regenerating it.

## 5. Decisions

### 5.1 Names on the profile page, normalized (#388, #154)

- **Editable.** The member's own profile page gets **First name** and **Last name** fields at the top of its first fieldset, required, saved with the rest of the profile. `GET`/`PATCH` of the profile endpoint the page uses carries them (they stay stored on `User`). Blank is refused with the same messages registration gives.
- **Normalized on save.** A new `caldart.casing.person_name` cases a name that arrives entirely upper case or entirely lower case: each word title case, with `Mc` (`MCDONALD` → `McDonald`; not `Mac`, which is ambiguous), `O'` (`o'brien` → `O'Brien`), hyphenated parts each cased (`smith-jones` → `Smith-Jones`), and the particles `van`, `von`, `der`, `den`, `de`, `del`, `della`, `da`, `di`, `du`, `la`, `le` lower case when they are not the first word (`VAN DER BERG` → `Van der Berg`, `jan van der berg` stays `Jan van der Berg`). A name typed in mixed case (`DeAnna`, `MacArthur`, `van Dyke`) is stored as typed: mixed case is a deliberate spelling. Leading and trailing spaces are stripped and runs of spaces collapsed in every case. It applies in `User.save()`, so registration, the profile page, the administrator's editor, the donation form, and the seed all store the same result.
- **Existing rows.** A management command, `normalize_casing`, applies `person_name` to every account's names and `title_case_words` to every profile's street and city, writing only rows that change, and prints one line per changed row (`<email>: last_name "SMITH" -> "Smith"`). `--dry-run` prints without writing. Document it in the operations chapter that lists management commands.
- County is a fixed choice list and needs nothing.

### 5.2 Amateur radio callsign (#387)

- `MemberProfile.ham_callsign`, `CharField(max_length=6, blank=True)`, labeled **Amateur radio callsign**, in its own fieldset directly under **Emergency contact** on the profile page, optional.
- **US format only.** Stored upper case after stripping spaces. Valid: a prefix of `K`, `N`, or `W` alone, `K`, `N`, or `W` followed by one letter, or `A` followed by `A`–`L`; then one digit; then a suffix of one to three letters (regex `^(?:[KNW][A-Z]?|A[A-L])[0-9][A-Z]{1,3}$`). Anything else is refused with *Enter a US amateur radio callsign, such as W6ABC.*. The form field upper-cases as the person types.
- Shown on the administrator's member record (read and edit), in the member list's column chooser, and in the members export; documented in `profile.rst`, the member-record page, `api-profile.rst`, and `data-model.rst`.

### 5.3 The account administrator's account actions, and blocking (#389, #265, #287)

- **Danger zone.** The member record's danger zone gains, above **Delete**, two actions for an account administrator, each with the same Confirm/Cancel step the delete uses:
  - **Make a friend** (shown for a member): does what the person's own switch does (`switch_to_friend`), with the actor recorded as the administrator. When the renewal takes a contribution, the confirm step asks whether to keep it as a recurring donation, as the person's own screen does. Every refusal is drawn in the danger zone.
  - **Deactivate account** / **Reactivate account** (whichever applies): deactivation does everything self-deactivation does (inactive account, mandates canceled, membership suspended, every session of that account ended, audit line with the administrator as actor, the `account_deactivated` event with that actor); reactivation mirrors self-reactivation. The existing refusals hold: a system administrator's account, a donor, and an account holding roles the administrator does not hold are refused, and the message is drawn.
- **The checkbox goes.** The **Account is active** checkbox leaves the member record's profile tab (`withActive` and its plumbing removed), and `update_account` no longer accepts `is_active`. #287 is closed as superseded; the danger zone draws every refusal.
- **Blocked.** `User.reactivation_blocked`, a boolean. Only a user administrator sets or clears it, from the user record (`features/admin-users/`), with a **Block reactivation** / **Allow reactivation** action; setting it on an active account also deactivates it, as above. While it is set, `/auth/reactivate`, sign-in, password-reset completion, and registering again with the address all refuse with *This account has been closed. Contact CalDART to reopen it.* (reading the organization name from site settings), and a password reset sends no mail. The account administrator's **Reactivate account** is refused on a blocked account with the same rule. Audit actions `account.block` and `account.unblock`.
- API: endpoints under the existing member and user administration routes, documented in `api-members.rst` and `api-users.rst` (or whichever pages hold those routes), and in the user guide's member-record and user-record pages.

### 5.4 Aircraft category and airworthiness category (#156)

- **Fields.** `Aircraft.category` and `Aircraft.airworthiness`, both `CharField` with `TextChoices`, blank allowed. Categories: Airplane, Helicopter, Gyroplane, Glider, Balloon, Airship, Powered lift, Weight-shift control, Powered parachute, Other. Airworthiness: Standard, Limited, Restricted, Experimental, Provisional, Multiple, Primary, Special flight permit, Light sport.
- **From the registry.** The import records `AircraftType.category` from `ACFTREF` `TYPE-ACFT` (fixed wing → Airplane, rotorcraft → Helicopter, `9` → Gyroplane, and so on) and `Registration.airworthiness` from the first character of `MASTER` `CERTIFICATION`. Choosing an N-number from the typeahead, or a type from the type picker, prefills both on the aircraft form; the person can change them. Update the test fixture under `apps/aircraft/fixtures` and the registry docs.
- **Everywhere an aircraft is shown.** The profile aircraft editor and the administrator's aircraft record (edit), the aircraft register list (columns in the column chooser and filters in its `FilterBar`), the aircraft exports and report, and the API.
- **Policy exclusions.** A singleton `AircraftCoveragePolicy` in `apps/aircraft`: `excluded_categories`, `excluded_airworthiness` (lists of the choice values), and `note`, a short plain-text statement of the coverage limitation. The account administrator edits it on a **Coverage policy** card on the aircraft register screen (`GET`/`PUT /aircraft/coverage-policy`; any signed-in member may read it). The seed sets helicopters excluded with a sample note.
- **On the card.** The DART leader's aircraft check shows an excluded aircraft as NO-GO with the reason *Not covered: helicopters are excluded by CalDART's policy* (naming the category or airworthiness that matched); an aircraft with no category recorded is not excluded but shows *Category not recorded*. The member check reads the same rule for the member's aircraft.
- **Published.** The member's **My aircraft** page shows the policy note above the list when one is set, and marks an excluded aircraft. The user guide's `faq.rst` gains an entry on which aircraft CalDART covers, pointing to the note on My aircraft, and `my-aircraft.rst`, the aircraft-record and aircraft-register pages, the leader's check page, `api-aircraft.rst` (or whichever page holds those routes), and `data-model.rst` describe the fields and the rule.

### 5.5 The user guide's search index keeps to the reader's roles (#367)

- The view that serves the guide refuses the raw `searchindex.js` and serves, instead, a copy filtered to the pages the signed-in reader's roles reach: the restricted docnames, their titles, and their entries in every term map removed, the remaining document indexes renumbered. Build the filtered copy from `roles.json` and cache it per set of roles (in memory, keyed by the frozen role set and the index file's modification time).
- Check the served HTML too: if a restricted page's title appears in the sidebar navigation of the pages a reader can open, remove those entries server-side in the same view by the same rule (the browser script then has nothing to hide). If that turns out impractical, say so under **Open problems**.
- Remove the known-gap paragraph from `docs/developer/documentation.rst` and describe the filtering; test with a member and an administrator in `backend/tests/test_user_guide_search.py`, and extend `frontend/e2e/user-guide.spec.ts` so a member's search for a word found only on an administrator page finds nothing.

### 5.6 Small fixes (#289, #346, #146)

- **#289.** `RecordPaymentPage.tsx` draws `errors.amount_cents` under **Contribution**, with a component test that the 400 shows *Nothing to charge.*; `record-payment.rst` lists the message.
- **#346.** `finance.spec.ts`'s ledger test waits for the filtered list to show exactly the member's rows before clicking (or opens the payment by URL from `seed-facts.json`); `prefix_proxy.py` `_relay` catches `BrokenPipeError` and `ConnectionResetError` and logs one line instead of a traceback. Run the spec ten times under the prefix (`--repeat-each=10`) and report the result.
- **#146.** Add the ten variables to `.env.example` and the two to `deploy/caldart.env.example`, commented out with the default and a one-line description, in the files' existing sections; add a test that every `env(...)` name the settings read appears in one of the two example files.

## 6. Work packages

### profile-names-callsign (Opus, reviewed)

- **Closes:** #388, #387, #154
- **Branch:** `feature/profile-names-callsign`; database `caldart_names`; e2e port 8401
- **Owns:** `backend/caldart/casing.py`, `backend/apps/accounts/models.py#save`, `backend/apps/members/models.py#ham_callsign`, `backend/apps/members/migrations/` (one new), `backend/apps/members/api/profile_serializers.py`, the members admin serializer fields for names and callsign, `backend/apps/members/reports.py#callsign`, `backend/apps/members/management/commands/normalize_casing.py` (new), `backend/tests/test_name_casing.py` (new), `backend/tests/test_ham_callsign.py` (new), `frontend/src/portal/features/profile/**`, `frontend/src/portal/features/admin-members/{MemberFormFields,MemberProfileTab,MembersListPage}.tsx#callsign` (+tests), `frontend/src/portal/api/types.ts#profile`, `frontend/e2e/profile*.spec.ts`, `docs/user/member/profile.rst`, `docs/user/admin/member-record.rst#callsign`, `docs/developer/{api-profile,data-model}.rst#profile`, the developer page listing management commands.
- **Steps:** §5.1, §5.2.
- **Verify:** all gates, both e2e runs; on `make run` a member edits their names on the profile page, `SMITH` saves as `Smith`, `DeAnna` stays, a callsign `w6abc` saves as `W6ABC` and `X1ABC` is refused; `normalize_casing --dry-run` lists changes after the seed.

### account-actions (Opus, reviewed)

- **Closes:** #389, #265, #287
- **Branch:** `feature/account-actions`; database `caldart_acctact`; e2e port 8411
- **Owns:** `backend/apps/accounts/{models,services,audit}.py#block,admin-deactivate`, `backend/apps/accounts/migrations/` (one new), `backend/apps/accounts/api/{views,serializers,urls}.py#reactivate,block,update_account`, `backend/apps/members/api/**#admin-actions`, `backend/apps/payments/renewals.py#switch_to_friend-actor` (additive: an `actor` keyword), `backend/caldart/audit.py#block`, `backend/tests/test_admin_account_actions.py` (new), `backend/tests/test_reactivation_block.py` (new), `frontend/src/portal/features/admin-members/{MemberDangerZone,MemberProfileTab,MemberFormFields,errors}.ts*#active` (+tests), `frontend/src/portal/features/admin-users/**#block`, `frontend/src/portal/features/auth/**#blocked`, `frontend/src/portal/api/types.ts#accounts`, `frontend/e2e/{deactivation,friend-switching}.spec.ts`, `docs/user/admin/{member-record,user-record}.rst`, `docs/user/member/sign-in.rst#blocked`, `docs/developer/{api-auth,api-members,data-model}.rst#accounts`.
- **Steps:** §5.3.
- **Verify:** all gates, both e2e runs; on `make run` the account administrator makes a member a friend and deactivates and reactivates an account from the danger zone; the profile tab has no **Account is active** box; a user administrator blocks an account and its owner cannot reactivate it by sign-in, reset, or registering again.

### aircraft-categories (Opus, reviewed)

- **Closes:** #156
- **Branch:** `feature/aircraft-categories`; database `caldart_aircat`; e2e port 8421
- **Owns:** `backend/apps/aircraft/**`, `backend/apps/darts/**#check` (the leader's aircraft check), `backend/apps/members/**#check` only where the member check reads the aircraft rule, `backend/tests/test_aircraft_categories.py` (new), `backend/tests/test_aircraft_coverage_policy.py` (new), the existing aircraft and registry tests where the fixture changes, `frontend/src/portal/features/{aircraft,admin-aircraft,leader}/**`, `frontend/src/portal/features/profile/{MyAircraftPage,AircraftEditor}.tsx` (+tests), `frontend/src/portal/api/types.ts#aircraft`, `frontend/e2e/aircraft*.spec.ts`, `docs/user/faq.rst`, `docs/user/member/my-aircraft.rst`, `docs/user/admin/aircraft-*.rst`, the leader's check page, `docs/developer/{api-aircraft,data-model,registry}.rst#aircraft` (whichever pages hold those).
- **Steps:** §5.4.
- **Verify:** all gates, both e2e runs; on `make run` add a helicopter by N-number from the typeahead and see Helicopter and Standard prefilled; the leader's check shows it NO-GO with the policy reason; My aircraft shows the note; the register filters by category.

### guide-search (Opus, reviewed)

- **Closes:** #367
- **Branch:** `feature/guide-search`; database `caldart_guidesearch`; e2e port 8431
- **Owns:** `backend/caldart/views.py#guide`, `backend/caldart/guide_search.py` (new), `docs/_ext/guide_roles.py`, `docs/_static/guide-roles.js`, `docs/conf.py` (only if needed), `docs/developer/documentation.rst`, `backend/tests/test_user_guide_search.py` (new), `frontend/e2e/user-guide.spec.ts`.
- **Steps:** §5.5.
- **Verify:** all gates, both e2e runs; `make guide`, then on `make run` a demo member fetching `/docs/searchindex.js` sees no administrator page title, and the system administrator sees them all.

### small-fixes (Sonnet, reviewed)

- **Closes:** #289, #346, #146
- **Branch:** `fix/small-fixes`; database `caldart_smallfix`; e2e port 8441
- **Owns:** `frontend/src/portal/features/admin-payments/RecordPaymentPage.tsx` (+test), `docs/user/finance/record-payment.rst`, `frontend/e2e/finance.spec.ts`, `frontend/e2e/prefix_proxy.py`, `.env.example`, `deploy/caldart.env.example`, `backend/tests/test_env_examples.py` (new).
- **Steps:** §5.6.
- **Verify:** all gates, both e2e runs, plus the repeated ledger spec.

## 7. Manifest

```json
[
  {"package": "small-fixes", "model": "sonnet", "review": true, "branch": "fix/small-fixes", "database": "caldart_smallfix", "e2e_port": 8441, "closes": [289, 346, 146]},
  {"package": "guide-search", "model": "opus", "review": true, "branch": "feature/guide-search", "database": "caldart_guidesearch", "e2e_port": 8431, "closes": [367]},
  {"package": "profile-names-callsign", "model": "opus", "review": true, "branch": "feature/profile-names-callsign", "database": "caldart_names", "e2e_port": 8401, "closes": [388, 387, 154]},
  {"package": "account-actions", "model": "opus", "review": true, "branch": "feature/account-actions", "database": "caldart_acctact", "e2e_port": 8411, "closes": [389, 265, 287]},
  {"package": "aircraft-categories", "model": "opus", "review": true, "branch": "feature/aircraft-categories", "database": "caldart_aircat", "e2e_port": 8421, "closes": [156]}
]
```
