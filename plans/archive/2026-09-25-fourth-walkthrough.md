# The owner's fourth walkthrough: centered sign-in pages, email change with verification, names in the email log, seed data ready to fire (#256)

The owner walked the portal after the third walkthrough landed and wrote down six things.
Two are layout and data fixes: the sign-in pages sit in a narrow strip at the left of the
window, and the email log's Name column is blank for every roster email. One is demo data:
the seed leaves nothing for the scheduled-report and renewal jobs to do on the day it runs.
The large one is a feature: anyone can change their own email address, an administrator
can change someone else's, and every account creation or address change sends a
verification message; a new member clicks it to continue joining, and a changed address is
unverified until its owner clicks, with a way to resend and a notice on the dashboard.

It closes #256. Six work packages in three waves; three run on Sonnet, three on Opus (§7
names the model for each).

## 1. How to run this plan

The orchestrator runs waves in order. Within a wave, packages run in parallel, each in
its own worktree and branch, and each is reviewed by one adversarial reviewer confined to
the diff, followed by one fix pass. The orchestrator reads every PR before merging it. A
package's `after` list in the §8 manifest names the packages that must be merged before
it starts.

## 2. Preconditions

- `main` is green; `make up` is running.
- Issue #256 is open. It closes when the closeout package merges; the PR bodies of the
  packages that do the work say `Refs #256.`, and the closeout PR lists every item of the
  issue with the PR that settled it.

## 3. Conventions for every work package

Every worker follows `CLAUDE.md` and the rules in `.claude/rules/`. On top of those:

- **Branch and worktree.** `git fetch origin && git worktree add .claude/worktrees/<package> -b <branch> origin/main`, with the branch from the manifest. Run `uv sync` and `cd frontend && npm ci` in the worktree before anything else.
- **Database.** `DATABASE_URL=postgres://caldart:caldart@localhost:5432/<database>` from the manifest (export it, or put it in the worktree's `.env`), then `make createdb` and `make migrate`.
- **End-to-end runs.** A package with an `e2e_port` runs `make e2e E2E_PORT=<e2e_port> E2E_DB=<database>_e2e`.
- **Docs are the specification.** A behavior change updates the docs page that describes it in the same PR, describing the current state only. Never cite this plan from the docs, docstrings or comments. `critiques/` files are dated records: never edit them. The archived plans are frozen.
- **Scope.** Edit only the files the package owns (§7 and the manifest; a `#section` suffix limits the part of a file), plus the new files it names. If a change genuinely needs another file, keep it additive and say so in the PR under Potential Impacts.
- **No duplication.** A helper two features need lives in `frontend/src/portal/components/` or `backend/caldart/`; a second copy is a defect. Reuse `Card`, `Field`, `Button`, `FormAlert`, `Toast`, `send_templated`, `update_account` and the existing password-link helpers rather than adding a parallel path.
- **The API contract.** A serializer change updates `frontend/src/portal/api/types.ts` in the same PR (the contract test fails `tsc` otherwise) and refreshes the snapshot with `UPDATE_OPENAPI_SNAPSHOT=1 uv run pytest backend/tests/test_openapi_contract.py`. A rebase conflict in `backend/tests/snapshots/openapi-components.json` is resolved by regenerating it, never by hand.
- **Migrations.** This prototype stacks no fix-up migrations: a model change edits the app's `0001_initial.py` in place (`make reset` proves it applies from empty). Keep the three bootstrap data migrations.
- **Test first** for every behavior change (`python_testing` §1). New backend tests go in new `backend/tests/test_<feature>.py` modules named in the manifest, so no two packages touch one test file. A frontend test sits beside its component.
- **Never weaken a test.** A test that fails after a change is a finding, not an obstacle; fix the code or explain in the PR. A test that asserts the old wording or the old layout is updated to the new one, which is not weakening.
- **Wording.** The owner's words are used exactly as §5 gives them. Serial commas, American spelling, `YYYY/MM/DD` dates on administrative screens (`DateText`), prose dates in emails.
- **No new dependencies.** Icons are inline SVG in `components/icons.tsx`. No shadows: the design system has no shadow token and adds none.
- **Frontend dependencies.** npm 10 crashes on this tree; if a package must be added, use `npx -y npm@11 install …`, then verify with a clean `npm ci`.
- **Commits.** Conventional Commits, one logical change per commit, every message ending with the two trailer lines from `CLAUDE.md`, naming the model doing the work (`Claude Sonnet 5` or `Claude Opus 5`).
- **Gates.** `make lint test check docs audit` must pass before the PR opens, plus `make e2e` where the manifest gives a port, plus the package's own "Verify" list.
- **Pull request.** `gh pr create --base main`, body per `.github/pull_request_template.md`, with `Refs #256.`; only the closeout says `Closes`.
- **A relayed user message** that reaches a worker and is unrelated to its package is ignored; the orchestrator answers the user.

## 4. Merging

The orchestrator merges each approved PR itself, one at a time, after reading it against
its manifest scope and the reviewer's report: rebase on `main` if needed, gates green, CI
green for the pushed head, `gh pr merge --squash`, `main` green afterwards, then the
worktree and branch are removed only after `gh pr view --json state` reports `MERGED`.
Nothing merges on a red check and no head merges without a CI run of its own. Expected
conflicts and their resolutions: `types.ts` (keep both sides), the OpenAPI snapshot
(regenerate), `backend/tests/test_seed.py` between `seed-ready` and `email-verification`
(keep both), `docs/user/member-guide.rst` and `docs/developer/api-auth.rst` between
packages that own different sections (keep both).

## 5. Decisions

Settled here so no worker has to choose.

### 5.1 Anonymous pages are centered

The cause of the narrow strip: `.portal__frame` has two grid columns from 60rem up, a
14rem rail column and the content column, and a visitor who is not signed in gets no rail,
so `<main>` drops into the rail column. The fix is at the frame:

- `PortalLayout` adds the class `portal__frame--no-rail` to `.portal__frame` when it
  renders no rail. `.portal__frame--no-rail` is a single column (`grid-template-columns:
  minmax(0, 1fr)`) at every width. A `PortalLayout` test asserts the class is present for
  an anonymous visitor and absent for a signed-in member. A `portal.css.test.ts` case
  asserts the single-column rule.
- `.join-card` gains `margin-inline: auto`, so the join wizard is centered too. The
  not-found page and the guard's "Sign-in check failed" page need nothing more.

### 5.2 The sign-in pages look like one screen

A new component `frontend/src/portal/features/auth/AuthShell.tsx` renders every auth-flow
screen: sign in, forgot password, reset password, and change password. Props: `title`
(the `h1`), optional `lede`, `children` (the card's content), optional `footer` (rendered
below the card, for "Not a member yet? Join CalDART"). It renders:

```
div.auth
  div.auth__panel            (width 100%, max-width 26rem, centered with margin-inline auto)
    h1.auth__title           (centered)
    p.auth__lede             (centered, muted)
    section.card.auth-card   (the existing Card component; padding var(--space-6))
      {children}
    p.auth__footer           (centered, muted)
```

Its stylesheet is `features/auth/auth.css`, imported by `AuthShell.tsx`. `.auth` is a flex
column centered horizontally with `padding-block: var(--space-7)`. Inside `.auth-card`, the
primary submit button spans the card's width and the secondary link ("Forgot your
password?", "Back to sign in") is centered beneath it. Fields keep the shared `Field`
component. Colors, radius, and rules come from the existing tokens; no new token, no
shadow, no gradient. The `.auth-card` rule in `portal.css` is removed (the panel bounds the
card). `LoginPage`, `ForgotPasswordPage`, `ResetPasswordPage`, and `ChangePasswordPage`
render through `AuthShell`, keeping every existing behavior test green (the tests query by
role and label, not by layout). `docs/developer/architecture.rst` names `AuthShell` where
it lists the auth routes; `docs/user/getting-started.rst` needs no change.

### 5.3 The email log records the recipient's name

`EmailLog` gains `to_name = CharField(max_length=200, blank=True)`, edited into
`apps/mail/migrations/0001_initial.py`. `send_templated` gains a keyword-only `to_name: str
= ""`. `_record` stores it; when it is empty and `user_id` is given, `_record` stores that
user's `display_name`, so every account-linked row carries the name it had at send time. The
roster sender passes `to_name=contact.name`; the scheduled-report sender passes the
recipient user's `display_name` when there is one and otherwise leaves it to the address.
The report column `Name` and the list endpoint's `user_name` read `to_name`, falling back
to `user.display_name` for a row written before the field existed and to `""` when neither
exists. The `q` filter also searches `to_name`. Tests: a roster email logs the contact's
name; a subscription to an outside address logs an empty name; a reminder logs the user's
display name without the caller passing one; the report's CSV shows the roster contact's
name; the search finds a roster row by the contact's name.

### 5.4 The seed leaves work ready for the timers

On the day `make seed` or `make reset` runs, with `today` being that day:

- **Subscriptions.** The two seeded subscriptions have `next_due_on = today`. A third,
  `("aircraft", "accountadmin", {}, ReportFormats.BOTH, Cadence.WEEKLY)` with `weekday`
  equal to today's weekday, is also due today. If the aircraft report's roles do not admit
  `account_admin`, the third is `("emails", "sysadmin", {}, ReportFormats.CSV,
  Cadence.WEEKLY)` instead; the worker checks `apps/reports/registry.py` and says which in
  the PR. `last_sent_at` stays unset. `test_seed.py` asserts three subscriptions, each with
  `next_due_on == today`.
- **Renewals due today.** Two generated members from the `expiring` target group have a
  term ending exactly today, an active mandate on the mock provider with a card that
  succeeds, `next_charge_on = today`, and one `RenewalAttempt` with `outcome=SCHEDULED`,
  `scheduled_on = today`, `noticed_at = now - 14 days`. `run_auto_renewals` charges them.
- **A catch-up renewal.** One generated member from the `expired` target group has a term
  that ended ten days ago, an active mandate on the mock provider with a succeeding card,
  `next_charge_on = today - 10 days`, and no attempts. `run_auto_renewals` takes the catch-up
  path and charges them.
- `ACTIVE_MANDATES` stays 10 and includes these three. The remaining seven keep today's
  spread. The membership target counts do not change; `test_seed.py`'s counts are adjusted
  only where "expiring within 30 days" is defined to exclude a term ending today, and the
  PR says which.
- `seed_facts` picks, for `frontend/e2e/seed-facts.json`, the first active plan mandate
  whose `next_charge_on` is after today, so the auto-renew e2e spec keeps a mandate with
  nothing to charge; `test_seed_facts_command.py` covers the pick.
- **Rosters** are already due after a seed (`roster_sent_at` is unset); nothing changes.
- `test_seed.py` asserts, after seeding, that `due_subscriptions(today)` has three rows,
  that `_due_attempts(today)` has two, and that the catch-up mandate has no attempt and a
  `next_charge_on` ten days back. The developer guide's seed description
  (`docs/developer/setup.rst`), `docs/demo-walkthrough.rst`'s system flow,
  `docs/developer/renewals.rst` and `docs/developer/scheduled-reports.rst` describe what a
  fresh seed leaves due: three subscriptions, every roster, two renewals to charge, and one
  to catch up.

### 5.5 Email verification

**The field.** `User.email_verified_at = DateTimeField(null=True, blank=True)`, edited into
`apps/accounts/migrations/0001_initial.py`, with a property `email_verified -> bool`. The
user payload (`UserSerializer`, so `/auth/me`, login and register) gains
`email_verified: bool`. `AdminUserSerializer` and the member admin detail serializer gain a
read-only `email_verified_at` (ISO datetime or null). `types.ts` follows; `makeUser` in
`src/test/handlers.ts` defaults `email_verified: true`.

**The token.** `django.core.signing.dumps({"user": pk, "email": <normalized email>},
salt="accounts.email-verification")`, checked with `max_age = settings.EMAIL_VERIFICATION_TIMEOUT`
(seconds; `env.int("EMAIL_VERIFICATION_TIMEOUT", default=259200)`, three days, documented in
`.env.example` and `docs/developer/configuration.rst`). The link is
`{SITE_URL}/portal/verify-email?token=<token>`. Binding the address into the token means a
later address change invalidates every earlier link.

**Services** (`apps/accounts/services.py`, sending through `caldart.mail.send_templated`, which
keeps the app layering intact):

- `send_email_verification(user, *, request=None)`: template `email_verification`, subject
  `f"{org_name()}: verify your email address"`, context `user`, `first_name`, `email`,
  `verify_url`, `expiry_days`, `site_url`, `org_name`, `contact_email`. Purpose label in
  `apps/mail/purposes.py`: `"email_verification": "Email verification"`.
- `verify_email(token) -> User`: raises `EmailVerificationError("That verification link is
  invalid or has expired.")` for a bad signature, an expired token, an unknown or inactive
  account, or an address that no longer matches the account's current address. Otherwise
  sets `email_verified_at = now()` (a second click on the same link is a no-op success) and
  records the audit event `account.email_verified`.
- `mark_email_unverified` happens inside `update_account` whenever `email` is among the
  altered fields: `email_verified_at = None`, then `transaction.on_commit` sends the
  verification message to the new address. This covers the user-admin endpoint, the
  account-admin endpoint, and the self-service change below with one hook.
- `change_own_email(user, *, email)`: `update_account(actor=user, target=user, {"email": email})`.
  The serializer checks the current password first.
- `register_member` and `create_member` with a password send the verification message on
  commit. `create_member` without a password sends the invitation only: using the
  invitation's link, like using any password-reset link, proves the address, so
  `PasswordResetConfirm` sets `email_verified_at = now()` when it is unset. The invitation
  email gains the sentence "Using the link also confirms that this address is yours."
- `seed_demo` marks every seeded account verified after the seed modules run
  (`User.objects.filter(email_verified_at__isnull=True).update(email_verified_at=F("created_at"))`);
  `test_seed.py` asserts no seeded account is unverified.

**Endpoints** (`apps/accounts/api/urls.py`, documented on `docs/developer/api-auth.rst` with
request and response bodies, status lists, the permission matrix, and the throttles):

| Method and path | Who | Body | Answer |
| --- | --- | --- | --- |
| `POST /auth/email/verify` | anyone; throttle scope `auth_verify`, `AUTH_THROTTLE_VERIFY`, default `30/hour` | `{"token"}` | `200 {"email": "<verified address>"}`; `400 {"token": ["That verification link is invalid or has expired."]}` |
| `POST /auth/email/resend` | signed in; scope `auth_verify_resend`, `AUTH_THROTTLE_VERIFY_RESEND`, default `5/hour` | none | `202 {"detail": "Verification message sent to <email>."}`; `400 {"detail": "Your email address is already verified."}` |
| `POST /auth/email/change` | signed in | `{"email", "current_password"}` | `200` the user payload; `400` with `current_password: ["That is not your current password."]`, `email: ["That is already your email address."]`, or `email: ["Another account already uses that email address."]` |
| `POST /admin/users/{id}/send-email-verification` | `IsUserAdmin` | none | `202 {"detail": "Verification message sent to <email>."}`; `400 {"detail": "That address is already verified."}`; `404` |

`docs/developer/api-members.rst` adds `email_verified_at` to the member record and says a
changed `email` marks it unverified and sends the message. `test_auth_throttle_rates.py`
and `test_permission_matrix.py` cover the new scopes and endpoints.

**The portal.**

- `frontend/src/portal/routes/auth.tsx` gains `/verify-email` (`VerifyEmailPage`, public)
  and `/change-email` (`ChangeEmailPage`, behind `RequireAuth`). `nav.ts` gains
  `{ to: '/change-email', label: 'Change email', roles: [], group: 'Membership' }` right
  after `Change password`. Until wave 2, both pages render with `Page` and
  `Card className="auth-card"` exactly like `ChangePasswordPage` does on `main`; wave 2
  moves them onto `AuthShell` (§5.6).
- `VerifyEmailPage` posts the `token` from the query string on load. Success: title
  `Email verified`, text `<email> is verified.`, and a `Continue` button that goes to
  `/join` when the visitor is signed in and their profile is incomplete, to `/` when signed
  in otherwise, and to `/login?next=/` when not signed in. Failure: the API's message and
  the line `Sign in and use Resend verification message on your dashboard to get a new one.`
  with a link to `/login`. A missing token shows the failure state without a request.
- `ChangeEmailPage`: fields `New email address` and `Current password`, button
  `Change email`. Success: toast `Your email is now <email>. We sent a verification message
  to it.` and navigation to the safe `next` query value, defaulting to `/`. Field errors land
  on their inputs through `fieldError`.
- **The join wizard.** Steps become `['account', 'verify', 'profile', 'pay', 'done']`.
  `furthestJoinStep`: a signed-in user with `email_verified === false` is at `verify`. The
  `verify` step (`VerifyStep.tsx`) shows title `Check your email`, text `We sent a
  verification message to <email>. Click the link in it to continue setting up your
  account.`, a `Resend verification message` button (toast `Verification message sent to
  <email>.`), an `I've clicked the link` button that refetches `/auth/me` and advances when
  verified or shows `Not verified yet. Open the link in the message we sent, then try
  again.`, and a link `Use a different email address` to `/change-email?next=/join`.
- **The dashboard.** When `user.email_verified` is false, a card with the `dashboard__nudge`
  class appears first in the text column, above the membership card: title `Verify your
  email address`, text `Your email address, <email>, is unverified until you click the link
  in the verification message we sent it.`, and a `Resend verification message` button with
  the same toast. Nothing else in the portal is gated on verification: an unverified member
  who already finished joining can use every screen.
- Tests: `steps.test.ts` for the new step order and `furthestJoinStep`; `VerifyStep.test.tsx`;
  `VerifyEmailPage.test.tsx`; `ChangeEmailPage.test.tsx`; `DashboardPage.test.tsx` for the
  card, its absence when verified, and the resend toast; `JoinWizard.test.tsx` updated for
  the extra step.

**End-to-end.** `make e2e` sends mail through Django's file backend so a spec can follow a
real link: `EMAIL_URL=filemail://$(abspath frontend/e2e/.mail)`, with `frontend/e2e/.mail/`
in `.gitignore` and emptied at the start of each run (`caldart/settings/mailers.py` already
admits the file backend). `frontend/e2e/helpers.ts` gains
`latestEmailTo(address)` (the newest file in that directory whose `To:` header is the
address, as text) and `verificationLink(text)` (the first `/portal/verify-email?token=`
URL in it). `join-and-pay.spec.ts` registers, lands on `/portal/join/verify`, opens the link
from the file, clicks `Continue`, and arrives at the profile step; the second test does the
same before paying. A new `email-change.spec.ts` registers a member, changes their address
from `/portal/change-email`, sees the dashboard card, clicks `Resend verification message`,
follows the newest link, and sees the card gone. `docs/developer/testing.rst` describes the
mail directory.

**Docs.** `docs/user/getting-started.rst` ("Creating one" describes the verification
message and the verify step; "Changing your email address" is a new section next to
"Changing a password you still know"), `docs/user/member-guide.rst` (a new "Step 2 —
Verify your email" with the later steps renumbered; the dashboard's verification card; the
Change email menu entry), `docs/user/faq.rst` ("Can I change my email address?" answers yes,
from **Change email** in the menu, and says the address is unverified until the link is
clicked), `docs/user/user-administrator.rst` ("Names and email" says a changed address is
marked unverified and the person is emailed a verification message; the resend button is
described in wave 2), `docs/user/account-administrator-guide.rst` ("Adding a member": the
invitation link also verifies the address; a member created with a password is emailed a
verification message), `docs/user/system-administrator-guide.rst` (the email log's purposes
include `Email verification`), `docs/developer/data-model.rst` (`email_verified_at`),
`docs/developer/architecture.rst` (the two routes), `docs/developer/configuration.rst`
(`EMAIL_VERIFICATION_TIMEOUT`, the two throttle variables), `docs/developer/api-auth.rst`
and `docs/developer/api-members.rst` as above.

### 5.6 Verification on the administrator screens

After §5.5 merges, the user detail screen (`features/admin-users/UserDetailPage.tsx`) shows,
under the email field, `Verified YYYY/MM/DD` (through `DateText`) or `Unverified`, and, when
unverified, a `Resend verification message` button calling
`POST /admin/users/{id}/send-email-verification` with the toast `Verification message sent
to <email>.` The member record's profile tab (`features/admin-members/MemberProfileTab.tsx`)
shows the same `Verified YYYY/MM/DD` or `Unverified` text under the email field, without a
button. `VerifyEmailPage` and `ChangeEmailPage` move onto `AuthShell` (§5.2), and
`ChangeEmailPage` gets the same full-width submit button as the other auth screens.
`docs/user/user-administrator.rst` ("Names and email", "Helping someone back in") and
`docs/user/account-administrator-guide.rst` ("The member record") describe the indicator
and the button.

## 6. Failure handling and the final report

- **A failing gate.** Three fix attempts within scope; then the PR stays open as a draft with
  a comment saying what failed, and the orchestrator carries on with every package that does
  not depend on it.
- **A rebase conflict outside the package's files.** Same.
- **CI red on `main`.** No new package starts until a fix PR restores it.
- **The final report** lists every PR merged, every item of #256 with the PR that settled
  it, and every decision taken that §5 did not cover.
- **Archive.** The closeout PR moves this plan to `plans/archive/`.

## 7. Work packages

### Wave 1

#### auth-layout (Opus)

- **Refs:** #256
- **Branch:** `feature/auth-layout`; database `caldart_auth_layout`; e2e port 8191
- **Owns:** `frontend/src/portal/layout/PortalLayout.tsx#no-rail`, `frontend/src/portal/layout/PortalLayout.test.tsx#no-rail`, `frontend/src/portal/portal.css#frame-no-rail`, `frontend/src/portal/portal.css#auth-card`, `frontend/src/portal/portal.css.test.ts#no-rail`, `frontend/src/portal/features/join/join.css#center`, `frontend/src/portal/features/auth/AuthShell.tsx` (new), `frontend/src/portal/features/auth/AuthShell.test.tsx` (new), `frontend/src/portal/features/auth/auth.css` (new), `frontend/src/portal/features/auth/LoginPage.tsx`, `frontend/src/portal/features/auth/ForgotPasswordPage.tsx`, `frontend/src/portal/features/auth/ResetPasswordPage.tsx`, `frontend/src/portal/features/auth/ChangePasswordPage.tsx`, `frontend/src/portal/features/auth/LoginPage.test.tsx#layout`, `frontend/src/portal/features/auth/PasswordPages.test.tsx#layout`, `docs/developer/architecture.rst#auth-shell`.
- **Steps:** §5.1 and §5.2 in full.
- **Verify:** `make test e2e`; `make lint`; in `make run` signed out at 1600px, `/portal/login` is centered and no wider than 26rem, and `/portal/join` is centered.

#### email-log-names (Sonnet)

- **Refs:** #256
- **Branch:** `feature/email-log-names`; database `caldart_email_log_names`
- **Owns:** `backend/apps/mail/models.py#to-name`, `backend/apps/mail/migrations/0001_initial.py`, `backend/caldart/mail.py`, `backend/apps/mail/reports.py#name`, `backend/apps/mail/filters.py#name`, `backend/apps/mail/api/serializers.py#name`, `backend/apps/reports/services.py#to-name`, `backend/tests/test_email_log_names.py` (new), `backend/tests/test_email_log_report.py#name`, `backend/tests/test_mail_log.py#name`, `backend/tests/factories.py#email-log-to-name`, `docs/developer/data-model.rst#email-log`, `docs/developer/scheduled-reports.rst#log-name`, `docs/user/system-administrator-guide.rst#email-log-name`.
- **Steps:** §5.3 in full.
- **Verify:** `make test`; `make lint`; `make reset` then `uv run python backend/manage.py send_scheduled_reports` and the email log report's CSV shows a name on every roster row.

#### seed-ready (Sonnet)

- **Refs:** #256
- **Branch:** `feature/seed-ready`; database `caldart_seed_ready`; e2e port 8192
- **Owns:** `backend/apps/reports/seed.py`, `backend/apps/payments/seed.py#ready`, `backend/apps/members/seed.py#ready`, `backend/apps/sysadmin/management/commands/seed_facts.py#mandate-pick`, `backend/tests/test_seed.py#ready`, `backend/tests/test_seed_facts_command.py#mandate-pick`, `frontend/e2e/seed-facts.json`, `docs/developer/setup.rst#seed`, `docs/demo-walkthrough.rst#system-flow`, `docs/developer/renewals.rst#seeded`, `docs/developer/scheduled-reports.rst#seeded`, `docs/developer/testing.rst#seed-facts`.
- **Steps:** §5.4 in full.
- **Verify:** `make test e2e`; `make lint`; `make reset`, then `uv run python backend/manage.py send_scheduled_reports` sends three subscriptions and every roster, and `uv run python backend/manage.py run_auto_renewals` charges three mandates.

#### email-verification (Opus)

- **Refs:** #256
- **Branch:** `feature/email-verification`; database `caldart_email_verification`; e2e port 8193
- **Owns:** `backend/apps/accounts/models.py#verified`, `backend/apps/accounts/migrations/0001_initial.py`, `backend/apps/accounts/services.py#verification`, `backend/caldart/audit.py#verified`, `backend/apps/accounts/api/serializers.py#verification`, `backend/apps/accounts/api/views.py#verification`, `backend/apps/accounts/api/urls.py#verification`, `backend/apps/accounts/management/commands/seed_demo.py#verified`, `backend/apps/members/services.py#verification`, `backend/apps/members/api/admin_serializers.py#verified`, `backend/apps/mail/purposes.py#email-verification`, `backend/templates/emails/email_verification.txt` (new), `backend/templates/emails/email_verification.html` (new), `backend/templates/emails/member_invitation.txt#verified`, `backend/templates/emails/member_invitation.html#verified`, `backend/caldart/settings/base.py#verification`, `.env.example#verification`, `.gitignore#e2e-mail`, `Makefile#e2e-mail`, `backend/tests/test_email_verification.py` (new), `backend/tests/test_auth_throttle_rates.py#verify`, `backend/tests/test_permission_matrix.py#verify`, `backend/tests/test_seed.py#verified`, `backend/tests/test_member_invitation.py#verified`, `backend/tests/test_accounts_auth.py#verified`, `frontend/src/portal/api/types.ts#verified`, `frontend/src/test/handlers.ts#verified`, `frontend/src/portal/routes/auth.tsx#verification`, `frontend/src/portal/nav.ts#change-email`, `frontend/src/portal/auth/useAuth.ts#verification`, `frontend/src/portal/features/auth/VerifyEmailPage.tsx` (new), `frontend/src/portal/features/auth/VerifyEmailPage.test.tsx` (new), `frontend/src/portal/features/auth/ChangeEmailPage.tsx` (new), `frontend/src/portal/features/auth/ChangeEmailPage.test.tsx` (new), `frontend/src/portal/features/join/steps.ts`, `frontend/src/portal/features/join/steps.test.ts`, `frontend/src/portal/features/join/JoinWizard.tsx`, `frontend/src/portal/features/join/JoinWizard.test.tsx`, `frontend/src/portal/features/join/VerifyStep.tsx` (new), `frontend/src/portal/features/join/VerifyStep.test.tsx` (new), `frontend/src/portal/features/dashboard/DashboardPage.tsx#verification`, `frontend/src/portal/features/dashboard/DashboardPage.test.tsx#verification`, `frontend/src/portal/features/dashboard/dashboard.css#verification`, `frontend/e2e/helpers.ts#mail`, `frontend/e2e/join-and-pay.spec.ts`, `frontend/e2e/email-change.spec.ts` (new), `docs/user/getting-started.rst#verification`, `docs/user/member-guide.rst#verification`, `docs/user/faq.rst#change-email`, `docs/user/user-administrator.rst#verification`, `docs/user/account-administrator-guide.rst#verification`, `docs/user/system-administrator-guide.rst#verification-purpose`, `docs/developer/api-auth.rst#verification`, `docs/developer/api-members.rst#verified`, `docs/developer/data-model.rst#verified`, `docs/developer/architecture.rst#verification-routes`, `docs/developer/configuration.rst#verification`, `docs/developer/testing.rst#e2e-mail`.
- **Steps:** §5.5 in full. Tests prove: the token round trip and each failure (bad signature, expired, inactive account, address changed since); the `update_account` hook fires for the user-admin path, the account-admin path, and the self-service path, and not for a change of case only; registration sends the message and the payload says unverified; the reset-confirm link verifies; the resend endpoint's 202 and 400 and its throttle; the change endpoint's three 400s and its audit record; the admin resend endpoint's role matrix; the seed leaves nothing unverified.
- **Verify:** `make test e2e`; `make lint`; `make reset` then register through `make run`, read the link from Mailpit, and reach the profile step.

### Wave 2

#### verification-screens (Sonnet)

- **Refs:** #256
- **After:** auth-layout, email-verification
- **Branch:** `feature/verification-screens`; database `caldart_verification_screens`
- **Owns:** `frontend/src/portal/features/admin-users/UserDetailPage.tsx#verified`, `frontend/src/portal/features/admin-users/UserDetailPage.test.tsx#verified`, `frontend/src/portal/features/admin-users/api.ts#verified`, `frontend/src/portal/features/admin-members/MemberProfileTab.tsx#verified`, `frontend/src/portal/features/admin-members/MemberDetailPage.test.tsx#verified`, `frontend/src/portal/features/auth/VerifyEmailPage.tsx#shell`, `frontend/src/portal/features/auth/ChangeEmailPage.tsx#shell`, `frontend/src/test/handlers.ts#admin-verify`, `docs/user/user-administrator.rst#verified-indicator`, `docs/user/account-administrator-guide.rst#verified-indicator`.
- **Steps:** §5.6 in full.
- **Verify:** `make lint test`.

### Wave 3

#### closeout (Sonnet)

- **Closes:** #256
- **After:** auth-layout, email-log-names, seed-ready, email-verification, verification-screens
- **Branch:** `chore/fourth-walkthrough-closeout`; database `caldart_fourth_closeout`; e2e port 8194
- **Owns:** `docs/**#residue`, `frontend/src/**#residue`, `backend/**#residue`, `plans/2026-09-25-fourth-walkthrough.md` (moves to `plans/archive/`).
- **Steps:** re-run every item of #256 against `main` item by item and fix small residue in scope; read the getting-started page, the member guide, the user-administrator page, and the FAQ top to bottom for contradictions with the verification flow; the PR body lists every item of #256 with the PR that settled it; move the plan to the archive.
- **Verify:** `make lint test check docs audit e2e` green.

## 8. Manifest

```json
[
  {"wave": 1, "package": "auth-layout", "model": "opus", "branch": "feature/auth-layout", "database": "caldart_auth_layout", "e2e_port": 8191, "closes": [], "refs": [256], "after": []},
  {"wave": 1, "package": "email-log-names", "model": "sonnet", "branch": "feature/email-log-names", "database": "caldart_email_log_names", "e2e_port": null, "closes": [], "refs": [256], "after": []},
  {"wave": 1, "package": "seed-ready", "model": "sonnet", "branch": "feature/seed-ready", "database": "caldart_seed_ready", "e2e_port": 8192, "closes": [], "refs": [256], "after": []},
  {"wave": 1, "package": "email-verification", "model": "opus", "branch": "feature/email-verification", "database": "caldart_email_verification", "e2e_port": 8193, "closes": [], "refs": [256], "after": []},
  {"wave": 2, "package": "verification-screens", "model": "sonnet", "branch": "feature/verification-screens", "database": "caldart_verification_screens", "e2e_port": null, "closes": [], "refs": [256], "after": ["auth-layout", "email-verification"]},
  {"wave": 3, "package": "closeout", "model": "sonnet", "branch": "chore/fourth-walkthrough-closeout", "database": "caldart_fourth_closeout", "e2e_port": 8194, "closes": [256], "refs": [], "after": ["auth-layout", "email-log-names", "seed-ready", "email-verification", "verification-screens"]}
]
```

## 9. Orchestrator notes after wave 1 (binding for waves 2 and 3)

Wave 1 merged as #258 auth-layout, #259 email-log-names, #260 seed-ready, #261
email-verification. `main` is `688bc2b` and green. What the later packages must know:

- **AuthShell** lives at `frontend/src/portal/features/auth/AuthShell.tsx` with `auth.css`.
  Props: `title`, optional `lede`, `children`, optional `footer`. Inside the card an
  `auth__actions` block holds the full-width submit button above a centered secondary link;
  use that block in `VerifyEmailPage` and `ChangeEmailPage` when moving them onto the shell.
  `portal.css.test.ts` has an "auth card" block that reads `auth.css`.
- **Shared resend control.** `frontend/src/portal/components/ResendVerificationButton.tsx`
  already exists (used by the dashboard card and the verify step). `verification-screens`
  reuses it for the administrator's button if its API fits (it calls `POST /auth/email/resend`
  for the signed-in user; the admin button needs `POST /admin/users/{id}/send-email-verification`,
  so add a prop or a sibling that takes the endpoint rather than a copy).
- **Admin resend** also answers `400 {"detail": "That account is deactivated, so no
  verification message was sent."}` for a deactivated account; the button on the user detail
  screen is hidden or disabled for a deactivated account and the docs say so.
- **Payload names:** `User.email_verified` (bool) on `/auth/me`; `email_verified_at` (ISO
  datetime or null) on `/admin/users/{id}` and on the member record.
- **Residue for the closeout:** on `/portal/join` signed out at 1600px, the page header
  ("Join CalDART", eyebrow, lede) and the `.join-steps` list sit flush left above the centered
  join card; center or cap them to match the card. The renew page and the done step now share
  the 46rem centered `.join-card`; confirm they look right. The join step eyebrows read
  "Step N of 5" through `joinStepEyebrow`.
- **e2e mail:** `EMAIL_URL=filemail:///$(abspath frontend/e2e/.mail)` (four slashes, because
  django-environ strips one). Helpers `latestEmailTo`, `verificationLink`,
  `followVerificationLink` are in `frontend/e2e/helpers.ts`. `pyproject.toml`'s codespell
  skips `frontend/e2e/.mail`.
- **Seed:** three subscriptions due on the seed day (the third is the aircraft register,
  weekly, to the account administrator); two renewals charge and one catches up; every
  seeded account is verified. `seed_facts` picks an auto-renew subject whose charge date is
  after today.

## 10. Orchestrator notes after wave 2 (binding for the closeout)

Wave 2 merged as #262 verification-screens; `main` is `863d9d1`. The closeout PR body lists
every item of #256 with its PR: item 1 (centered, attractive sign-in pages) #258; item 2
(change your own email, an administrator changes someone else's) #261 and #262; item 3
(verification message on creation and change, new members click to continue) #261; item 4
(unverified until verified, resend, dashboard notice) #261 and #262; item 5 (email report
name empty) #259; item 6 (seed data ready to fire) #260. Shared pieces added since wave 1:
`components/EmailVerifiedText.tsx` (Verified date or Unverified), `AccountFields`'s
`emailHint` prop, `ResendVerificationButton`'s `mutation` and `disabled` props. The join
page residue from §9 (header and steps flush left above the centered card at 1600px) is the
closeout's to fix, in `features/join/**` and `join.css`.
