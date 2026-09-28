# Fifth walkthrough: verify-first onboarding, MM/DD/YYYY dates, the System section split, and ten smaller fixes (#349)

The owner's comments, in their words, are the body of issue #349; §5 reproduces each one and settles the decisions a worker needs. Nine work packages in three waves. The plan closes #349; it touches #150 and #154 without closing them.

Facts settled before planning (from reading the code on 2026-09-27):

- Nothing blocks an unverified account today. `POST /auth/register` signs the new account in, `POST /auth/login` never looks at `email_verified_at`, and no permission class or route guard reads it. The join wizard (`features/join/`) derives its step from `email_verified`, `profile_complete`, `kind`, and `membership.status` on the `/auth/me` payload; nothing is stored. The wizard renders inside `PortalLayout`, so the rail shows during it. Four end-to-end specs (`email-change`, `recurring-donation`, `deactivation`, `friend-switching`) roam the portal before the wizard is finished.
- Changing an address (`accounts/services.py` ~L290) clears `email_verified_at` and mails the new address a link that carries `previous_email`.
- An unpaid member already counts as a friend everywhere but the wizard (`account_kind()`, `MembershipState`); `POST /me/kind/friend` turns a member with no term into a stored friend at once.
- The email letterhead, subjects, and footers all read `{{ org_name }}`, which is `SiteSettings.org_name`, whose model default is `"The California DART Network"`; `DEFAULT_ORG_NAME` in `caldart/org.py` is already `"CalDART"` and the from-address display name is already `CalDART`.
- The user guide is one static `dirhtml` tree built with the `guide` tag, served by `caldart.views.user_guide` to any signed-in user; furo's sidebar is stock; the guide groups pages by area (`member/`, `admin/`, `finance/`, `website/`), not by role; no page carries role metadata.
- `components/DateText.tsx` is the one formatter (`YYYY/MM/DD`, `YYYY/MM/DD HH:MM`). Three places bypass it: a raw ISO toast in `MemberMembershipsTab.tsx`, `periodLabel()` in `PeriodTable.tsx`, and `RegistryPanel.tsx`, which splits the formatted string to get the time. About thirty frontend test files, two end-to-end files, thirteen user-guide pages, and four developer pages spell the slash format.
- `Payment.user` is the only `PROTECT` link to an account; `delete_member` refuses when any payment exists, and `payments/wagtail_hooks.py` blocks the Wagtail delete the same way. `RenewalMandate.user` and `YearStatement.user` cascade. No placeholder account exists; the donor kind has no password and no role.
- The member record's top block is `MemberVerificationCard` (a "Verification" card: one `verification-items__row` per item with label, detail, and `VerifiedMark`; **Verify** in the footer swaps the card for the one-save panel). The aircraft record has no such card: the chip, the mark, and **Verify** sit in the page header and the panel is inserted above **Details**.
- `MemberProfile.save()` already normalizes the phone fields; nothing cases street or city. Every write path (own profile, admin editor, donation form, seed) ends in `save()`.
- The System page is one route with eight hand-written panels; five name a systemd timer in their body text. The blurb of comment 12 is the lede of the **Notifications** page (`AdminNotificationsPage.tsx`), not the Subscriptions page. `DeleteButton` (the trashcan) never confirms; the two worded deletes that confirm do so with local inline state, and no shared confirmation primitive exists.

## 1. How to run this plan

Wave 1 has seven packages in parallel, wave 2 two, wave 3 one. Each package is a worktree, a branch, a database, a worker, and (where the manifest says `review: true`) an Opus reviewer confined to the diff with a fix pass only on a blocking finding. The orchestrator reads every PR before merging it and merges one at a time, the last of a wave rebased with its own CI run. The plan PR lands this file alone.

## 2. Preconditions

`main` is green; `make up` is running; issue #349 is open.

## 3. Conventions for every work package

Every worker follows `CLAUDE.md` and the rules in `.claude/rules/`. On top of those, the conventions of `plans/archive/2026-09-27-aircraft-registry.md` §3 hold word for word (branch and worktree, per-worker database, docs as the specification, scope, test first, wording, commits, gates, the pull request, relayed messages), with these changes:

- **End-to-end runs.** A package with an `e2e_port` runs both `make e2e E2E_PORT=<e2e_port> E2E_DB=<database>_e2e` and `make e2e E2E_PORT=<e2e_port> E2E_DB=<database>_e2e E2E_URL_PREFIX=/caldart-proto` (CI runs both).
- **The API contract.** A serializer change updates `frontend/src/portal/api/types.ts` and refreshes the snapshot with `UPDATE_OPENAPI_SNAPSHOT=1 uv run pytest backend/tests/test_openapi_contract.py`.
- **No backwards compatibility.** A removed field or refusal disappears everywhere; a schema default changes by editing the model and its initial migration in place, never by stacking one (`make reset` afterwards).
- **Wording.** Serial commas, American spelling. Dates on screens read `MM/DD/YYYY` once §5.7 lands (wave 2); a wave-1 package leaves date formatting alone.
- **Pull request.** `Refs #349.` in every body; `Closes #349.` only in the closeout's. `Refs #150.` on `onboarding-gate`; `Refs #154.` on `addresses-and-airports`.

## 4. Merging

One PR at a time, in manifest order within a wave, gates green, CI green for the pushed head, `gh pr merge --squash`, the last PR of a wave rebased on `main` and waiting for its own CI run.

## 5. Decisions

### 5.1 Nothing until the address is verified (comment 1)

> During the new user flow, when the verification email has been sent, the user shouldn't be able to do anything else until that email is verified. The screen they get after entering the name and password should say they got an email, and not allow any other work. If they try to login with that email but without the email verified, it should offer to send it again, but still not allow them to go any further. There should be nothing in the left sidebar at all.

- **Sign-in still creates a session.** `POST /auth/register` and `POST /auth/login` behave as they do; what changes is what a session whose account is unverified may do. (Resending needs a session, and the session is how the portal knows whose address to show.)
- **The API refuses an unverified session.** A new middleware, `apps/accounts/middleware.py` `EmailVerificationGateMiddleware`, installed after `AuthenticationMiddleware`: for a request under the API prefix whose `request.user` is authenticated and whose `email_verified` is false, and whose path is not one of the allowed endpoints, it answers `403 {"detail": "Verify your email address to continue.", "code": "email_unverified"}`. Allowed: `auth/me`, `auth/logout`, `auth/email/verify`, `auth/email/resend`, `auth/email/change`, and `site/config`. The user guide (`/docs/`) stays readable. Document the gate and the code in `api-auth.rst` (the payload section, the login section, and a new **Unverified sessions** section), and in `security.md`'s spirit: the check is server-side, not only a screen.
- **The portal shows one screen.** A new guard, `RequireOnboarded`, wraps every route except `login`, `forgot-password`, `reset-password`, `verify-email`, `change-email`, and `join/*`. With a signed-in user whose `email_verified` is false it redirects to `/join/verify`; the wizard's `verify` step is the "Check your email" card as today (the address, **Resend verification message**, **I've clicked the link**, and the link to change the address), with the lede reworded to say that nothing else is available until the address is verified. Signing in with an unverified address therefore lands on that screen: **Resend** is the offer to send it again. `LoginPage` needs no special case; `VerifyEmailPage`'s success screen continues to `/join`, which resolves to the next step (§5.2), and its failure screen tells the reader to sign in and press **Resend** on the screen they land on (not "on your dashboard"). The verification email's "sign in and use Resend … on your dashboard" sentence changes to match, in both `email_verification.txt` and `.html`.
- **No rail, no menu.** `PortalLayout` computes `isOnboarded(user)` (§5.2) and shows the rail and the **Menu** toggle only when it is true; the frame carries `portal__frame--no-rail` otherwise (the class that already exists for signed-out visitors). The header keeps **Help**, the address, and **Sign out**. The dashboard's link cards are unaffected because the dashboard is unreachable until onboarded.
- **A changed address is unverified.** Because a change of address clears `email_verified_at`, a member who changes their address sees the verify screen (naming the new address) until they follow the link; `change-email` stays reachable so a mistyped address can be corrected. `member/change-email.rst` says so.
- **The dashboard's nudges go.** The "Verify your email address" and "Finish your profile" cards on `DashboardPage.tsx` describe states that can no longer reach the dashboard; remove them and their tests. `ResendVerificationButton` stays (the wizard uses it).

### 5.2 Then the profile, then payment, and resume where you left (comment 2)

> Likewise after verification, it should require you to enter your profile info and then your payment info (if needed) with no option to navigate anywhere else. If you abort and log in again it should take you to the part of the wizard you last saw.

- **Onboarded** means: `email_verified`, and `profile_complete`, and (`kind !== 'member'` or `membership.status === 'current'`). A stored friend or donor needs no payment; a member needs a current term. One function, `isOnboarded(user)` in `features/join/steps.ts`, is the definition; `furthestJoinStep` uses it and `RequireOnboarded` and `PortalLayout` import it.
- **The guard sends the reader to the step they must finish**: `/join/verify`, `/join/profile`, or `/join/pay`, from `furthestJoinStep(user)`. That is the part of the wizard they last saw, because a step is left only by completing it: the state the server holds is the resume point, and nothing new is stored. `JoinWizard`'s `clampJoinStep` keeps letting the reader go back a step (to fix the profile, say) but never forward.
- **The pay step has no way out for a member** except paying or choosing to be a friend (§5.4). A friend's pay step (`Checkout mode="contribute"`) keeps **Not now**, which completes onboarding.
- **Staff and imported accounts are not exempt.** An account an administrator created with an incomplete profile finishes the profile step on first sign-in. The seed's demo accounts all have complete profiles; confirm that with a test in `test_seed.py` (every seeded user with a profile has `is_complete`), so the demo sign-ins the end-to-end suite uses are never gated.
- **A fully onboarded reader who opens `/join`** sees the `done` step as today.
- **Tests.** `steps.test.ts` covers `isOnboarded` for every combination; `guards.test.tsx` covers `RequireOnboarded` (unverified → verify, incomplete → profile, unpaid member → pay, friend → through, onboarded → through); `PortalLayout.test.tsx` asserts no rail and no Menu for a gated user; a backend test module `test_verification_gate.py` covers the middleware (403 with the code on a member endpoint, 200 on each allowed endpoint, no effect on a verified session or an anonymous request, the guide still served). The four roaming end-to-end specs are rewritten to finish onboarding first (verify, complete the profile, pay or choose friend) before they go elsewhere; `friend-switching.spec.ts`'s "leaves the pay step" case becomes the §5.4 case. `helpers.ts` gains `completeOnboarding(page, email, {as: 'member' | 'friend'})` so the specs share one path.
- **Docs.** `member/join.rst` (the wizard is the whole portal until it is done; resuming), `member/verify-email.rst` (drop "does not lock you out of anything"), `member/sign-in.rst`, `member/dashboard.rst` (no verify card), `quick-start.rst`, `faq.rst`, `admin/new-member.rst` (first sign-in finishes the profile), `api-auth.rst`, `api-profile.rst` (`profile_complete` gates the portal), `architecture.rst` (guards, the no-rail frame).

### 5.3 `XXX` in the airport boxes (comment 3)

> The ghost text in home and secondary airport shouldn't be real airport names PAO and SQL because it's confusing, just write XXX.

`placeholder: 'XXX'` on both airport controls in `ProfileFieldsets.tsx` and on the donation form's home airport in `frontend/src/donate/DonorDetails.tsx`. A test asserts the placeholder on each. The validation message ("Use a three-character identifier like PAO, E16, or KLS.") is not ghost text and stays.

### 5.4 "I changed my mind, I just want to be a friend" (comment 4)

> When joining as a member in addition to annual and lifetime, add a third option for "I changed my mind, I just want to be a friend".

- `PlanChooser` takes `offerFriend?: boolean`. When true it renders a third radio card after the plans, value `friend`, headed exactly **I changed my mind, I just want to be a friend**, with the one-line body "A friend has an account and hears from CalDART, but is not a member." `Checkout` passes `offerFriend` only in `mode="join"` when its host asks; `PayStep` asks when `joiningAs(user) === 'member'` (the reader chose member at sign-up and is at the wizard's pay step). `JoinAsMemberPage` (a friend becoming a member) and `RenewPage` do not offer it.
- Choosing it hides the payment method and contribution controls and shows one primary button, **Continue as a friend**, which calls `POST /me/kind/friend` (the existing `useBecomeFriend`), refetches `me`, and moves the wizard on; with the stored kind now `friend`, `furthestJoinStep` is `done` and the reader is onboarded. The done step reads "You are a friend of CalDART." (§5.5 wording).
- The wizard's `LEDE` no longer hard-codes "$45 a year, or $650 for life": it reads the plan list the checkout already fetches, or says "Membership is annual or for life; the pay step shows the prices."
- Tests: `PlanChooser.test.tsx` (third card only with `offerFriend`), `Checkout.test.tsx` (friend choice shows the one button and calls the endpoint), `JoinWizard.test.tsx` (member who chooses friend reaches done), the end-to-end case in `friend-switching.spec.ts`. Docs: `member/join.rst` step 4, `member/become-a-member.rst` (a friend can join later, as today). `Refs #150.` in the PR; the $20 preselection #150 also asks for is not in scope.

### 5.5 "CalDART" in the email header (comment 5)

> Every place the email header says "The California DART Network" it should just say "CalDART".

- `SiteSettings.org_name` defaults to `"CalDART"`: the model field and the default recorded in `apps/cms/migrations/0001_initial.py`, edited in place. The public site's fallbacks in `templates/base.html` (footer `firstof … "The California DART Network"`) say `"CalDART"` too; the tagline fallback ("California DART Network") is a tagline, not the name, and stays.
- Every test, golden file, and doc that spells the long name where the org name is meant follows: `test_receipts_pdf.py`, `test_reminders.py`, `test_mail.py`, `test_site_config.py`, `test_scheduled_reports.py`, `test_email_verification.py`, `test_dart_rosters.py`, `test_member_invitation.py`, `test_reminder_stages.py`, `backend/tests/golden/*.txt`, the quoted subjects in `docs/user/finance/{payment-record,contributions,renewals,record-payment}.rst`, `docs/developer/cms.rst`'s example, and `data-model.rst`'s documented default. `docs/conf.py`'s `|org|` substitution describes the organization in prose and stays.
- The wizard's done text ("You are a member of the California DART Network.") is owned by `onboarding-gate`, which writes "You are a member of CalDART." / "You are a friend of CalDART."
- A site whose settings row already holds the long name keeps it until an administrator edits **Settings** in Wagtail or the database is reset; `docs/user/website/settings-and-themes.rst` names the field. The PR body says so under Potential Impacts.

### 5.6 The user guide shows only what the reader may use (comment 6)

> The user guide should only display those parts that the user has privileges for.

- **Role metadata on pages.** A guide page that only some roles may use opens with a docinfo field list before its title: `:roles: account_admin, dart_leader` (the role slugs from `apps/accounts/roles.py`, comma-separated; a reader holding any one of them, or `system_admin`, may see the page). Pages without the field are for every signed-in reader. Assignments follow `nav.ts`: `admin/member-check`, `admin/aircraft-check`: `dart_leader, account_admin, user_admin, verifier`; `admin/members`, `admin/new-member`, `admin/member-record`: `account_admin, dart_leader`; `admin/aircraft-register`, `admin/aircraft-record`, `admin/darts`, `admin/reminders`, `admin/notifications`: `account_admin`; `admin/subscriptions`: `account_admin, treasurer`; `admin/users`, `admin/user-record`: `user_admin`; the three System pages of §5.11: `system_admin`; every `finance/*` page: `treasurer, account_admin`; every `website/*` page: `website_admin`. `member/*`, `roles`, `overview`, `quick-start`, `faq`: none. An index page (`admin/index`, `finance/index`, `website/index`) carries no field; its roles are the union of its toctree children, computed.
- **A local Sphinx extension**, `docs/_ext/guide_roles.py` (added to `sys.path` and `extensions` in `conf.py`; pure Python, no system package), reads `env.metadata[docname]["roles"]`, computes the union for each index page from its toctree, fails the build (`-W`) on a slug that is not one of the known role slugs (the list is spelled in the extension; `test_docs_user.py` asserts it equals `ROLE_SLUGS`), and writes `roles.json` (`{docname: [slugs]}`) into the output directory on `build-finished`.
- **The server enforces it.** `caldart.views.user_guide` loads `roles.json` from `USER_GUIDE_ROOT` (cached by mtime) and, for a page whose docname has roles the reader lacks (`user.has_any_role`), redirects to the guide's index. `roles.json` and the static assets are always served. `test_user_guide.py` covers: a member asking for `admin/system/` is redirected, a system administrator is served, a page without roles is served to a member, a missing `roles.json` serves everything (a build without the extension is still a guide).
- **The sidebar hides them.** `docs/_static/guide-roles.js` (listed in `html_js_files` under the `guide` tag only, `defer`) fetches `roles.json` and `<prefix>/api/v1/auth/me` (the prefix is the guide root minus `/docs/`, from `document.documentElement.dataset.content_root`), then removes from `.sidebar-tree` and every `.toctree-wrapper` the `li` whose link resolves to a docname the reader may not see, and any section whose entries are all removed; `system_admin` sees everything. A `guide-roles-pending` class on `<html>` (set inline before the tree renders, cleared when the fetch settles or fails) keeps the trees hidden until then. The existing CSP `script-src` override in the view already permits the guide's own scripts; confirm `connect-src` allows the same-origin fetch.
- **Docs.** `docs/developer/documentation.rst` gains **Role-gated pages** (the field, the extension, the JSON, the view, the script); `docs/user/roles.rst` says the guide shows each reader the screens their roles reach. `test_docs_user.py` gains: every page under `admin/`, `finance/`, `website/` (indexes excepted) carries `:roles:`; no page under `member/` does; every slug is known.

### 5.7 `MM/DD/YYYY`, from one place (comment 7)

> All dates should be in the form MM/DD/YYYY when displayed in the GUI. Make sure date conversion exists in a single place so we can modify it later.

- **The one place is `components/DateText.tsx`.** `dateParts` becomes `MM/DD/YYYY`; `formatDateTime` gives `MM/DD/YYYY HH:MM`. It gains `formatTime(value)` (`HH:MM`; `RegistryPanel.tsx` uses it instead of splitting the string) and `formatMonth(yyyyMm)` (`Mar 2026`; `PeriodTable.periodLabel` and `reports-api.ts` use it). The raw ISO toast in `MemberMembershipsTab.tsx` uses `formatDate`. Its doc comment states the rule: every date or time a portal screen shows passes through this module. An ESLint restriction is welcome if cheap (`no-restricted-syntax` on `toLocaleDateString`/`toLocaleString` under `src/portal`), otherwise a vitest test that greps `src/portal` for those calls outside `DateText.tsx`.
- **Date inputs** stay native `<input type="date">` (the browser renders its own locale; there is no text mask to change).
- **The backend's one place** is `caldart/dates.py`: `DISPLAY_DATE_FORMAT = "%m/%d/%Y"`, `format_display_date(d)`, `format_display_datetime(dt)`. Used by everything that puts a date into text a portal screen or a download shows: `apps/aircraft/verification_report.py` (the PDF and CSV), `apps/notifications/messages.py` (`_slash`, whose subjects appear in the Sent Emails screen), `apps/payments/renewals.py`'s subjects (raw ISO today), `apps/mail/reports.py` (`SENT_AT_FORMAT` → `MM/DD/YYYY HH:MM`), `caldart/reports.py`'s PDF footer, and `sysadmin/management/commands/seed_facts.py`. Untouched, and documented as such: ISO dates in CSV data columns (`reports.rst` says CSV dates are ISO-8601 for spreadsheets), prose dates in email bodies (`F j, Y`) and on the public site's CMS templates, and the receipt PDF's ISO dates (a legal record; leave them).
- **Every test and doc that spells the slash format follows**: the frontend test files, `frontend/e2e/aircraft-registry.spec.ts` (`screenDate`) and `helpers.ts` (`asOf`), `test_notifications.py`, `test_verification_report.py`, the thirteen user-guide pages and four developer pages listed under Facts. `history.ts`'s doc-comment examples too.
- **Docs.** `architecture.rst` names the module and the rule; `reports.rst` states which dates are ISO and which are `MM/DD/YYYY`; the user guide's examples read `09/27/2026`.

### 5.8 Delete a member who has payments (comment 8)

> The "Danger Zone" for members needs to allow deleting of any account even if payments are present. In that case, change the payments to be owned by "Deleted member 5" or similar.

- **A tombstone account owns the payments.** `delete_member` no longer refuses on payments. When the target has any payment, it creates `tombstone_for(target)` in `members/services.py`: a `User` of kind `donor` (no password, no role, cannot sign in), `is_active=False`, `first_name="Deleted member"`, `last_name=str(target.id)` (so `display_name` reads **Deleted member 5**), email `deleted-<id>@deleted.invalid`, a blank `MemberProfile`, then `Payment.objects.filter(user=target).update(user=tombstone)` inside the same transaction. `Payment.user` stays `PROTECT`; `payment_deletion_refusal` and `REASON_HAS_PAYMENTS` are removed, and the model-level `ProtectedError` branch in `delete_member` goes with them. Before the reassignment, every active or pending `RenewalMandate` of the target is canceled through the existing cancel service (so a saved card is released at the provider) with the audit reason `member.delete`; the mandates and statements then cascade with the account.
- **Wagtail follows.** `payments/wagtail_hooks.py`'s single and bulk hooks call the same reassignment instead of blocking, so an administrator who deletes from Wagtail gets the same result. The audit line `member.delete` gains `payments=<n> owner=<tombstone id>` when payments moved.
- **The Danger zone.** `MemberDangerZone.tsx` drops `PaymentsKept`. The **Delete this member** card keeps the type-the-email confirmation and, when `member.payments.length > 0`, adds the sentence "{name} has N payment records. They stay in the books under the name Deleted member {id}." The self-delete and system-administrator refusals stay.
- **Reports.** The donors report, the payment list, and the ledger show the tombstone's display name; the members list and the Users & roles list, which show active accounts by default, do not show it (a test asserts the tombstone is absent from `GET /admin/members` and present as the owner in `GET /admin/payments`).
- **Tests.** `test_members_delete_payments.py` rewritten: every payment status moves, the tombstone's kind, activity, name, and email, the mandate canceled, the account gone, refunds still attached to their payments, the Wagtail single and bulk paths, the audit line. `MemberDangerZone.test.tsx` covers the sentence. **Docs.** `admin/member-record.rst` **Danger zone**, `admin/user-record.rst`, `api-members.rst` (`DELETE /admin/members/{user_id}`: the refusals that remain, the tombstone), `data-model.rst` (`Payment.user` and the tombstone), `finance/donors.rst` and `finance/payment-list.rst` (a **Deleted member N** row).

### 5.9 The aircraft record's verification block (comment 9)

> The verification block at the top of the aircraft details should look like that for members.

- A new `features/verification/InsuranceVerificationCard.tsx` mirrors `MemberVerificationCard`: a `Card title="Verification"` with `ul.verification-items` holding one `verification-items__row` for **Insurance** (label; detail from a shared `insuranceDetail(aircraft)`: carrier, policy number, the liability limit, and "expires <date>" joined with " · ", or "Not on file"; `VerifiedMark verification={aircraft.insurance_verification}`), and **Verify** in the footer under the same condition the header button uses today. Pressing **Verify** replaces the card with `InsuranceVerificationPanel`; `onSaved` restores the card and refreshes the record (the existing `formResetKey` bump).
- `AircraftRecordPage.tsx` renders the card first, above **Details**; the header's actions keep `InsuranceChip` and `ServiceChip` and lose the mark and the button. `verification.css`'s comment that `.verification-items` is "on the member record" is corrected. The leader's aircraft check card is unchanged.
- Tests: `InsuranceVerificationCard.test.tsx` (detail text, mark, Verify swaps in the panel, save restores), `AircraftRecordPage.test.tsx` updated; the end-to-end specs that press **Verify** on the record page (`verification.spec.ts`, `aircraft-registry.spec.ts#verification`) follow. Docs: `admin/aircraft-record.rst` **What you see**.

### 5.10 Title case for streets and cities (comment 10)

> Normalize street addresses and city names to always be in title case for every word.

- `caldart/casing.py`: `title_case_words(value: str) -> str`. Trim; collapse internal runs of whitespace to one space; for each word, leave it unchanged when it contains a digit (`3B`, `94301`, `2nd`), otherwise capitalize each part split on `-` and `'` (first letter upper, the rest lower): `"o'brien-smith LANE"` → `"O'Brien-Smith Lane"`, `"palo alto"` → `"Palo Alto"`, `"123 MAIN ST NE"` → `"123 Main St Ne"` (every word, as asked). Empty stays empty.
- Applied in `MemberProfile.save()` to `TITLE_CASE_FIELDS = ("address_line1", "address_line2", "city")`, beside the phone normalization, so every write path (own profile, admin editor, donation form, seed, Django admin, a picked Geoapify suggestion) stores the same casing. The serializers need no validator: the response after a save shows the stored value. Refs #154, which also asks for names and county; names are not in this comment and county is a choice list. The PR comments on #154 with what landed.
- Tests: `test_address_casing.py` (the function's cases above, the own-profile path, the admin path, the donation path). Docs: `member/profile.rst` (street and city are stored in title case, every word), `api-profile.rst`, `api-payments.rst` (the donor fields), `data-model.rst`.

### 5.11 System, in three pages (comment 11)

> Split system System section into multiple pages - "Health & Database" (includes health, backups, and loading the aircraft database), "Sent Emails", and "Scheduled" for everything else. The "renewal reminders" and "automatic renewals" should be first. It's confusing what these are called and the descriptions overlap. If one is just the reminder email and the other is the actual renewal, be more clear. Don't mention a systemd timer name anywhere in the UI.

- **Three routes, three nav entries** in the `System` group, in this order and with these labels: **Health & Database** (`/system/health`), **Sent Emails** (`/system/emails`), **Scheduled** (`/system/scheduled`); `/system` redirects to `/system/health`. Each is a lazy page in `features/system/` (`HealthDatabasePage.tsx`, `SentEmailsPage.tsx`, `ScheduledPage.tsx`); `SystemPage.tsx` goes. `help.ts` maps them to `admin/health-database`, `admin/sent-emails`, `admin/scheduled`.
- **Health & Database** holds, in order: **Health**, **Backups**, **Aircraft database** (the registry import panel, retitled; its body: "Loads the FAA aircraft registry, which is what the N-number box on an aircraft form offers. It runs every night and changes nothing else, so running it again is harmless."). Page lede: "How the server is doing, the database dumps it holds, and the aircraft database it loads."
- **Sent Emails** is the email log panel as the page body; page title **Sent Emails**, lede "Every message the site has sent, with who it went to and why."
- **Scheduled** holds, in order: **Renewal reminder emails** (the reminders panel, retitled), **Automatic renewal charges** (the renewals panel, retitled), **Scheduled reports**, **Year-end statements**. Page lede: "The jobs the server runs on a schedule. Each one can be run by hand here, and a dry run shows what it would do." The two bodies are rewritten so the difference is plain:
  - Renewal reminder emails: "Emails members whose membership is about to expire or has just expired: 60, 30, and 7 days before, on the day, and 30 days after. It sends email only and never charges anyone. A member whose automatic renewal is on is skipped. It runs every morning; running it again is harmless, because each member gets each reminder once per membership."
  - Automatic renewal charges: "Charges the saved card or PayPal account of every member whose automatic renewal is due, after emailing a notice two weeks ahead and a warning when the card is about to expire. It runs every morning before the reminder emails, so a member it renews is not also reminded. Running it again is harmless: every scheduled charge records what has already gone out."
  - The reports and statements bodies lose their timer names and clock times ("runs every morning" / "runs once a year in January").
- **No timer name anywhere on a screen.** A vitest test in `features/system/` renders each page and asserts no text matches `/caldart-[a-z]+|systemd|\.timer/`. Backend docstrings may still name the units.
- **Tests and docs.** `SystemPage.test.tsx` becomes one test file per page (the panels present, in order); `nav.test.ts`, `help.test.ts`, `routes/index.test.tsx`, `lazy-gate.test.tsx` follow; the end-to-end specs that visit `/system` (`reminders.spec.ts`, `finance-reports.spec.ts`, `aircraft-registry.spec.ts#import`) visit the right page. `docs/user/admin/system.rst` becomes `health-database.rst`, `sent-emails.rst`, and `scheduled.rst` (each under 250 lines, the headings matching the screen), the `admin/index.rst` toctree lists the three, and every reference to the System page (`roles.rst`, `admin/reminders.rst`, `finance/contributions.rst`, `member/dashboard.rst`, the developer pages that say "the System page") names the right one. `test_docs_user.py`'s `PURPOSE_LABELS` check must still find every purpose label, on the Sent Emails page.

### 5.12 The Notifications lede (comment 12)

> Change "The email addresses that hear about what happens in CalDART, and the events each one hears about." to "Email addresses that receive notification of system changes".

`AdminNotificationsPage.tsx`'s `lede` becomes exactly `Email addresses that receive notification of system changes`, with a test asserting it; `docs/user/admin/notifications.rst`'s opening sentence is aligned with the same words.

### 5.13 Every trashcan asks first (comment 13)

> With the trashcan on the "my aircraft" page and the addresses on the subscriptions page ask for verification. Same for any other trashcan.

- `components/DeleteButton.tsx` confirms in both forms. The first press replaces the control, in place, with a small inline pair: a danger `Button` reading the `confirmLabel` prop (default **Delete**) and a plain **Keep**; `onDelete` fires only from the danger button; **Keep**, Escape, or focus leaving the pair restores the trashcan. The pair carries `role="group"` and an `aria-label` from the button's `label`. The docstring's convention line ("keeps its words") is replaced by: every delete asks first.
- Every caller keeps working through the primitive: `MyAircraftPage` (`confirmLabel="Remove"`), `SubscriptionsCard`, `NotificationSubscriptionsCard`, `ColumnChooser` (the saved set), and `DartForm`'s per-person trashcan (`confirmLabel="Remove"`; it removes a row from the form, and still asks). The two worded deletes that already confirm with their own state (`DartForm` **Delete this DART**, `AircraftRecordPage` **Delete this aircraft**) move onto the primitive's confirmation if that is a simplification, otherwise stay; `MemberDangerZone` keeps its type-the-email confirmation.
- Tests: `DeleteButton.test.tsx` (nothing on first press, delete on confirm, Keep and Escape restore), each caller's test presses twice; the end-to-end steps that delete a saved set (`payment-reports.spec.ts`) and a DART (`darts-admin.spec.ts`) confirm. Docs: `member/my-aircraft.rst`, `admin/subscriptions.rst`, `admin/notifications.rst`, `admin/darts.rst`, and the column-chooser paragraph in `member/payments.rst` (or wherever the saved sets are described) say a trashcan asks before it removes.

## 6. Ownership summary

Files two packages would both want are assigned once: `features/join/**` and `JoinWizard`'s done text belong to `onboarding-gate` (not `org-name`); `features/system/**` to `system-pages` (`dates` reaches it in wave 2); `frontend/e2e/aircraft-registry.spec.ts` is split by section (`#verification` to `aircraft-verification-card`, `#import` to `system-pages`, `#dates` to `dates` in wave 2); `docs/user/admin/*.rst` headers (`:roles:`) belong to `guide-by-role` in wave 2, after `system-pages` has split the System page.

## 7. Work packages

### Wave 1

#### onboarding-gate (Opus, reviewed)

- **Refs:** #349, #150
- **Branch:** `feature/onboarding-gate`; database `caldart_onboard`; e2e port 8301
- **Owns:** `backend/apps/accounts/middleware.py` (new), `backend/caldart/settings/base.py#middleware`, `backend/templates/emails/email_verification.{txt,html}`, `backend/tests/test_verification_gate.py` (new), `backend/tests/test_seed.py#complete`, `frontend/src/portal/auth/**`, `frontend/src/portal/layout/**`, `frontend/src/portal/routes/{index,auth,join}.tsx`, `frontend/src/portal/features/join/**`, `frontend/src/portal/features/auth/**`, `frontend/src/portal/features/checkout/**`, `frontend/src/portal/features/dashboard/DashboardPage.tsx` (+test), `frontend/src/portal/features/membership/**`, `frontend/e2e/helpers.ts`, `frontend/e2e/{join-and-pay,join-friend,friend-switching,auto-renew,notifications,deactivation,email-change,recurring-donation}.spec.ts`, `docs/user/member/{join,verify-email,sign-in,dashboard,change-email,become-a-member}.rst`, `docs/user/{quick-start,faq}.rst`, `docs/user/admin/new-member.rst`, `docs/developer/{api-auth,api-profile,architecture}.rst`.
- **Steps:** §5.1, §5.2, §5.4, and the wizard's done text from §5.5.
- **Verify:** all gates, both e2e runs; on `make run`: register, see only the verify screen with no rail; sign out and in again, same screen with **Resend**; follow the link, land on the profile step with no rail; complete it, land on pay; choose the friend card, land on done and then a dashboard with a rail; a demo administrator signs in straight to the dashboard.

#### system-pages (Opus, reviewed)

- **Refs:** #349
- **Branch:** `feature/system-pages`; database `caldart_system`; e2e port 8311
- **Owns:** `frontend/src/portal/features/system/**`, `frontend/src/portal/nav.ts#system` (+`nav.test.ts`), `frontend/src/portal/routes/system.tsx` (+`routes/index.test.tsx#system`, `lazy-gate.test.tsx#system`), `frontend/src/portal/help.ts#system` (+`help.test.ts`), `frontend/e2e/{reminders,finance-reports}.spec.ts`, `frontend/e2e/aircraft-registry.spec.ts#import`, `docs/user/admin/{health-database,sent-emails,scheduled}.rst` (new; `system.rst` removed), `docs/user/admin/index.rst`, the System references in `docs/user/{roles,admin/reminders,finance/contributions,member/dashboard}.rst` and `docs/developer/**`.
- **Steps:** §5.11.
- **Verify:** all gates, both e2e runs; on `make run` as the demo system administrator: three entries under System, each page's panels in the stated order, no timer name on any of them, `/system` lands on Health & Database.

#### confirm-deletes (Sonnet, reviewed)

- **Refs:** #349
- **Branch:** `feature/confirm-deletes`; database `caldart_confirm`; e2e port 8321
- **Owns:** `frontend/src/portal/components/DeleteButton.tsx` (+test), `frontend/src/portal/components/ColumnChooser.tsx` (+test), `frontend/src/portal/features/profile/MyAircraftPage.tsx` (+test), `frontend/src/portal/features/admin-reports/SubscriptionsCard.tsx` (+test), `frontend/src/portal/features/admin-notifications/**`, `frontend/src/portal/features/admin-darts/DartForm.tsx` (+`DartsPage.test.tsx`), `frontend/src/portal/features/admin-aircraft/AircraftRecordPage.tsx#delete`, `frontend/e2e/{payment-reports,darts-admin}.spec.ts`, `docs/user/member/{my-aircraft,payments}.rst`, `docs/user/admin/{subscriptions,notifications,darts}.rst`.
- **Steps:** §5.13 and §5.12.
- **Verify:** all gates, both e2e runs; on `make run`: the trashcan on My aircraft, on Subscriptions, on Notifications, on a saved column set, and on a DART person each show Delete/Keep before anything happens; the Notifications lede reads the new sentence.

#### aircraft-verification-card (Sonnet, reviewed)

- **Refs:** #349
- **Branch:** `feature/aircraft-verification-card`; database `caldart_aircard`; e2e port 8331
- **Owns:** `frontend/src/portal/features/verification/InsuranceVerificationCard.tsx` (new, +test), `frontend/src/portal/features/verification/verification.css`, `frontend/src/portal/features/admin-aircraft/AircraftRecordPage.tsx#verification` (+test), `frontend/e2e/verification.spec.ts`, `frontend/e2e/aircraft-registry.spec.ts#verification`, `docs/user/admin/aircraft-record.rst`.
- **Steps:** §5.9.
- **Verify:** all gates, both e2e runs; on `make run` the aircraft record opens with a Verification card at the top that looks like the member record's, and Verify swaps in the panel.

#### delete-with-payments (Opus, reviewed)

- **Refs:** #349
- **Branch:** `feature/delete-with-payments`; database `caldart_delete`
- **Owns:** `backend/apps/members/services.py#delete`, `backend/apps/payments/models.py#refusal`, `backend/apps/payments/wagtail_hooks.py`, `backend/caldart/audit.py#delete`, `backend/tests/test_members_delete_payments.py`, `backend/tests/test_members_admin.py#delete`, `backend/tests/test_member_services.py#delete`, `frontend/src/portal/features/admin-members/MemberDangerZone.tsx` (+test), `frontend/src/portal/features/admin-members/MemberDetailPage.test.tsx#danger`, `docs/user/admin/{member-record,user-record}.rst`, `docs/user/finance/{donors,payment-list}.rst`, `docs/developer/{api-members,data-model}.rst`.
- **Steps:** §5.8.
- **Verify:** all gates; on `make run` delete a seeded member who has payments: the account is gone, the payment list shows **Deleted member N** as the owner, and the donors report still totals the same.

#### addresses-and-airports (Sonnet, reviewed)

- **Refs:** #349, #154
- **Branch:** `feature/addresses-and-airports`; database `caldart_addr`; e2e port 8341
- **Owns:** `backend/caldart/casing.py` (new), `backend/apps/members/models.py#save`, `backend/tests/test_address_casing.py` (new), `frontend/src/portal/features/profile/ProfileFieldsets.tsx#placeholders` (+test), `frontend/src/donate/DonorDetails.tsx` (+test), `docs/user/member/profile.rst`, `docs/developer/{api-profile,api-payments,data-model}.rst`.
- **Steps:** §5.10 and §5.3.
- **Verify:** all gates, both e2e runs (`address-completion.spec.ts` still passes); on `make run` save "123 MAIN st" and "palo ALTO" and read back "123 Main St" and "Palo Alto"; both airport boxes show `XXX`.

#### org-name (Sonnet, reviewed)

- **Refs:** #349
- **Branch:** `feature/org-name`; database `caldart_orgname`
- **Owns:** `backend/apps/cms/models.py#org_name`, `backend/apps/cms/migrations/0001_initial.py#org_name`, `backend/templates/base.html#footer`, the backend tests and golden files named in §5.5, `docs/user/finance/{payment-record,contributions,renewals,record-payment}.rst`, `docs/user/website/settings-and-themes.rst`, `docs/developer/{cms,data-model}.rst`.
- **Steps:** §5.5 (except the wizard text).
- **Verify:** all gates; after `make reset`, send a reminder dry run or a test email and read `CalDART` in the letterhead and the subject.

### Wave 2

#### dates (Opus, reviewed)

- **Refs:** #349
- **Branch:** `feature/dates`; database `caldart_dates`; e2e port 8351
- **Owns:** `frontend/src/portal/components/DateText.tsx` (+test), `frontend/src/portal/features/admin-payments/{PeriodTable,reports-api}.ts*`, `frontend/src/portal/features/admin-members/MemberMembershipsTab.tsx#toast`, `frontend/src/portal/features/system/RegistryPanel.tsx#time`, `frontend/src/portal/features/admin-aircraft/history.ts#comments`, every frontend test file that spells `YYYY/MM/DD`, `frontend/eslint.config.js#dates` (if the restriction is added), `frontend/e2e/helpers.ts#asOf`, `frontend/e2e/aircraft-registry.spec.ts#dates`, `backend/caldart/dates.py` (new), `backend/apps/aircraft/verification_report.py`, `backend/apps/notifications/messages.py#dates`, `backend/apps/payments/renewals.py#subjects`, `backend/apps/mail/reports.py#format`, `backend/caldart/reports.py#footer`, `backend/apps/sysadmin/management/commands/seed_facts.py#asOf`, `backend/tests/test_dates.py` (new), `backend/tests/{test_notifications,test_verification_report}.py#dates`, the user-guide and developer pages listed in §5.7.
- **Steps:** §5.7.
- **Verify:** all gates, both e2e runs; on `make run` every screen date reads `MM/DD/YYYY` and datetimes `MM/DD/YYYY HH:MM`; `grep -rn "toLocaleDateString\|toLocaleString" frontend/src/portal` finds only `DateText.tsx`.

#### guide-by-role (Opus, reviewed)

- **Refs:** #349
- **Branch:** `feature/guide-by-role`; database `caldart_guide`; e2e port 8361
- **Owns:** `docs/_ext/guide_roles.py` (new), `docs/_static/guide-roles.{js,css}` (new), `docs/conf.py`, the `:roles:` header of every page under `docs/user/{admin,finance,website}/`, `docs/user/roles.rst`, `docs/developer/documentation.rst`, `backend/caldart/views.py#guide`, `backend/tests/test_user_guide.py`, `backend/tests/test_docs_user.py#roles`, `frontend/e2e/user-guide.spec.ts` (new: a member opening an administrator page is sent to the index, and their sidebar lacks the administrator sections).
- **Steps:** §5.6.
- **Verify:** all gates, both e2e runs; `make guide` writes `roles.json`; on `make run` a demo member's guide sidebar shows only Start here, Your screens, and Reference, and typing an administrator page's address lands on the index; the system administrator sees everything.

### Wave 3

#### closeout (Sonnet, not reviewed)

- **Closes:** #349
- **Branch:** `chore/walk5-closeout`; database `caldart_walk5_closeout`
- **Owns:** whatever §9 and §10 name, plus a docs sweep.
- **Steps:** resolve every item in §9 and §10 (the orchestrator numbers them during waves 1 and 2); sweep the docs for stale references ("the System page", "eight panels", "YYYY/MM/DD", "does not lock you out", "cannot be deleted"), and fix what the sweep finds; run every gate and both e2e runs.
- **Verify:** all gates; `make reset && make build && make guide` from the worktree.

## 8. Manifest

```json
[
  {"wave": 1, "package": "onboarding-gate", "model": "opus", "review": true, "branch": "feature/onboarding-gate", "database": "caldart_onboard", "e2e_port": 8301, "closes": [], "refs": [349, 150], "after": []},
  {"wave": 1, "package": "system-pages", "model": "opus", "review": true, "branch": "feature/system-pages", "database": "caldart_system", "e2e_port": 8311, "closes": [], "refs": [349], "after": []},
  {"wave": 1, "package": "confirm-deletes", "model": "sonnet", "review": true, "branch": "feature/confirm-deletes", "database": "caldart_confirm", "e2e_port": 8321, "closes": [], "refs": [349], "after": []},
  {"wave": 1, "package": "aircraft-verification-card", "model": "sonnet", "review": true, "branch": "feature/aircraft-verification-card", "database": "caldart_aircard", "e2e_port": 8331, "closes": [], "refs": [349], "after": []},
  {"wave": 1, "package": "delete-with-payments", "model": "opus", "review": true, "branch": "feature/delete-with-payments", "database": "caldart_delete", "closes": [], "refs": [349], "after": []},
  {"wave": 1, "package": "addresses-and-airports", "model": "sonnet", "review": true, "branch": "feature/addresses-and-airports", "database": "caldart_addr", "e2e_port": 8341, "closes": [], "refs": [349, 154], "after": []},
  {"wave": 1, "package": "org-name", "model": "sonnet", "review": true, "branch": "feature/org-name", "database": "caldart_orgname", "closes": [], "refs": [349], "after": []},
  {"wave": 2, "package": "dates", "model": "opus", "review": true, "branch": "feature/dates", "database": "caldart_dates", "e2e_port": 8351, "closes": [], "refs": [349], "after": ["onboarding-gate", "system-pages", "confirm-deletes", "aircraft-verification-card", "delete-with-payments", "addresses-and-airports", "org-name"]},
  {"wave": 2, "package": "guide-by-role", "model": "opus", "review": true, "branch": "feature/guide-by-role", "database": "caldart_guide", "e2e_port": 8361, "closes": [], "refs": [349], "after": ["system-pages"]},
  {"wave": 3, "package": "closeout", "model": "sonnet", "review": false, "branch": "chore/walk5-closeout", "database": "caldart_walk5_closeout", "closes": [349], "refs": [], "after": ["dates", "guide-by-role"]}
]
```
