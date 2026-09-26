# Members, friends, and donors: account kinds, donations, recurring giving, self-deactivation and reactivation (#264)

The owner set out three kinds of people. A **member** pays dues when they join and is expected
to keep paying, or to buy a lifetime plan; they may add a contribution to any payment, give
once on demand, or give on a schedule. A **friend** is the same person without the intent:
no dues at sign-up, never "current", never "expired", never nagged to renew, free to give
once or on a schedule, and free to become a member by paying. A **donor** gives through the
public site, gets an account with no password, cannot sign in, and appears in no member list;
the treasurer sees donors in a report of their own. Members and friends can switch kinds from
their dashboard or profile, and can deactivate their own account and reactivate it later.
The county filter on the member list and report takes several counties at once.

It closes #264 and refs #265. Nine work packages in four waves; §7 names the model for each.

## 1. How to run this plan

The orchestrator runs waves in order. Within a wave, packages run in parallel, each in
its own worktree and branch, and each is reviewed by one adversarial reviewer confined to
the diff, followed by one fix pass. The orchestrator reads every PR before merging it. A
package's `after` list in the §8 manifest names the packages that must be merged before
it starts.

## 2. Preconditions

- `main` is green; `make up` is running.
- Issue #264 is open. It closes when the closeout package merges; the PR bodies of the
  packages that do the work say `Refs #264.`, and the closeout PR lists every decision of
  the issue with the PR that settled it.

## 3. Conventions for every work package

Every worker follows `CLAUDE.md` and the rules in `.claude/rules/`. On top of those:

- **Branch and worktree.** `git fetch origin && git worktree add .claude/worktrees/<package> -b <branch> origin/main`, with the branch from the manifest. Run `uv sync` and `cd frontend && npm ci` in the worktree before anything else.
- **Database.** `DATABASE_URL=postgres://caldart:caldart@localhost:5432/<database>` from the manifest (export it, or put it in the worktree's `.env`), then `make createdb` and `make migrate`. Run `make reset` after any migration change.
- **End-to-end runs.** A package with an `e2e_port` runs `make e2e E2E_PORT=<e2e_port> E2E_DB=<database>_e2e`.
- **Docs are the specification.** A behavior change updates the docs page that describes it in the same PR, describing the current state only. Never cite this plan from the docs, docstrings or comments. `critiques/` files are dated records: never edit them. The archived plans are frozen.
- **Scope.** Edit only the files the package owns (§7 and the manifest; a `#section` suffix limits the part of a file), plus the new files it names. If a change genuinely needs another file, keep it additive and say so in the PR under Potential Impacts.
- **No duplication.** A helper two features need lives in `frontend/src/portal/components/` or `backend/caldart/`; a second copy is a defect. Reuse `Checkout`, `ContributionChooser`, the provider panels, `FilterBar`, `DataTable`, `RunActionsTable`, `send_templated`, `update_account`, `cancel_mandate`, `create_checkout`, `mark_succeeded`, `ReportSpec` and `build_report` rather than adding a parallel path.
- **The API contract.** A serializer change updates `frontend/src/portal/api/types.ts` in the same PR (the contract test fails `tsc` otherwise) and refreshes the snapshot with `UPDATE_OPENAPI_SNAPSHOT=1 uv run pytest backend/tests/test_openapi_contract.py`. A rebase conflict in `backend/tests/snapshots/openapi-components.json` is resolved by regenerating it, never by hand. A new choice set gets an `ENUM_NAME_OVERRIDES` entry in `caldart/settings/base.py`.
- **Migrations.** This prototype stacks no fix-up migrations: a model change edits the app's `0001_initial.py` in place (`make reset` proves it applies from empty). Keep the bootstrap data migrations.
- **App layering.** `accounts` 1, `darts`/`mail` 2, `members` 3, `aircraft`/`payments` 4, `reminders`/`reports` 5, `cms`/`sysadmin` 6. A domain module imports only its own app or a lower layer; `api/`, `management/`, `migrations/` and `admin.py` are exempt. A new sanctioned inline import is added to `backend/tests/test_app_layering.py` with an `# Inline:` comment.
- **Test first** for every behavior change (`python_testing` §1). New backend tests go in new `backend/tests/test_<feature>.py` modules named in the manifest, so no two packages touch one test file. A frontend test sits beside its component.
- **Never weaken a test.** A test that fails after a change is a finding, not an obstacle; fix the code or explain in the PR. A test that asserts the old wording or the old layout is updated to the new one, which is not weakening.
- **Wording.** The owner's words are used exactly as §5 gives them. Serial commas, American spelling, `YYYY/MM/DD` dates on administrative screens (`DateText`), prose dates in emails. Money is integer cents in the API and the database.
- **No new dependencies.** Icons are inline SVG in `components/icons.tsx`. No shadows.
- **Frontend dependencies.** npm 10 crashes on this tree; if a package must be added, use `npx -y npm@11 install …`, then verify with a clean `npm ci`.
- **Commits.** Conventional Commits, one logical change per commit, every message ending with the two trailer lines from `CLAUDE.md`, naming the model doing the work (`Claude Sonnet 5` or `Claude Opus 5`).
- **Gates.** `make lint test check docs audit` must pass before the PR opens, plus `make e2e` where the manifest gives a port, plus the package's own "Verify" list.
- **Pull request.** `gh pr create --base main`, body per `.github/pull_request_template.md`, with `Refs #264.`; only the closeout says `Closes`.
- **A relayed user message** that reaches a worker and is unrelated to its package is ignored; the orchestrator answers the user.

## 4. Merging

The orchestrator merges each approved PR itself, one at a time, after reading it against
its manifest scope and the reviewer's report: rebase on `main` if needed, gates green, CI
green for the pushed head, `gh pr merge --squash`, `main` green afterwards, then the
worktree and branch are removed only after `gh pr view --json state` reports `MERGED`.
Nothing merges on a red check and no head merges without a CI run of its own; the last PR of
a wave is rebased and re-run even when GitHub reports it mergeable. Expected conflicts and
their resolutions: `types.ts` (keep both sides), the OpenAPI snapshot (regenerate),
`backend/tests/test_seed.py` (keep both), `frontend/src/test/handlers.ts` (keep both),
`docs/user/member-guide.rst` and `docs/developer/api-auth.rst` between packages that own
different sections (keep both), `Checkout.tsx` between `recurring-donations` and
`join-friend` (keep both: the recurring chooser and the `onSkip` button).

## 5. Decisions

Settled here so no worker has to choose.

### 5.1 The kind, and how it is computed

- `apps/accounts/models.py` gains `AccountKind(TextChoices)`: `MEMBER = "member", "Member"`,
  `FRIEND = "friend", "Friend"`, `DONOR = "donor", "Donor"`; `User.kind` (`CharField`,
  default `MEMBER`) and `User.friend_on` (`DateField`, null: the day a member who asked to
  become a friend becomes one). `ENUM_NAME_OVERRIDES` gains `AccountKindEnum`.
- **Effective kind.** `apps/members/services.py` gets `account_kind(user, today) -> AccountKind`
  (`FRIEND` when `user.kind == FRIEND` or `friend_on` is set and `<= today`; otherwise
  `user.kind`) and `kind_annotation(today)` returning the same rule as a `Case` expression, so
  the Python rule and the SQL rule agree, as `membership_status` and `membership_annotations`
  already do. `convert_due_friends(today)` writes the pending conversions down
  (`kind = FRIEND`, `friend_on = None`, audit `account.kind`); the reminders daily run calls it
  next to `expire_lapsed_memberships`.
- **Roles.** `create_account(..., kind=AccountKind.MEMBER)` adds the `member` role for members
  and friends and no role for donors. The `member` role's description reads "A member or a
  friend with a portal account". `STAFF_ROLE_SLUGS` is unchanged, so a friend with a staff role
  keeps its powers.
- **Membership state.** `MembershipState` gains `FRIEND = "friend", "Friend"`.
  `membership_status(user)` returns `FRIEND` (with `expires_on`, `plan` null, `is_lifetime`
  false) whenever the effective kind is friend, before looking at terms: a friend's past
  terms never make them expired. Both rules (Python and SQL) implement this. `can_access_members_content`
  stays as it is: a friend without a staff role is refused, with the wall's `wall_state`
  `"friend"` and the sentence "Friends of CalDART can read this page by becoming a member."
  and a **Make me a member** link to `/portal/membership/join`.
- **Terms and kinds.** `activate_term` for a friend makes them a member (`kind = MEMBER`,
  `friend_on = None`): paying dues, or an administrator's manual grant, is what membership
  is. `create_checkout` lets a friend buy a plan. A donor never reaches checkout through the
  portal (they cannot sign in).
- **Payload.** `UserSerializer` gains `kind` and `friend_on`; `MemberListSerializer`,
  `MemberDetailSerializer` and `AdminUserSerializer` gain `kind`; `MemberCreateSerializer`
  and `MemberUpdateSerializer` accept `kind` (`member` or `friend`; an administrator never
  makes a donor by hand, and never turns a donor into anything: that happens when the donor
  registers). `types.ts` follows; `makeUser` defaults `kind: 'member', friend_on: null`.
- **Labels.** `portal/choices.ts` gains `ACCOUNT_KIND_LABELS` and adds `friend: 'Friend'` to
  `MEMBERSHIP_STATUS_LABELS`; `StatusChip`'s tone for `friend` is neutral (the same as `none`).
- **Seed.** `MEMBERSHIP_TARGETS` gains `("friend", 5)`; a demo account `friend@example.org`
  ("Frances Lee", verified, complete profile, one contribution payment, no terms); one
  generated member with `friend_on` set to a date next month; six donors (see §5.6). Every
  count in `test_seed.py` follows.
- **Docs.** `docs/user/overview.rst` (the state diagram gains Friend), `getting-started.rst`
  ("Members, friends, and donors" section), `member-guide.rst`, `faq.rst` ("What is a
  friend?"), `docs/developer/data-model.rst` (`kind`, `friend_on`, the state), `api-auth.rst`
  (payload), `api-members.rst` (fields), `api-profile.rst` (`/me/membership` statuses).

### 5.2 Joining as a member or as a friend

- `POST /auth/register` accepts `kind` (`member` or `friend`, default `member`).
- The wizard's account step opens with the choice, above the name fields: two radio cards,
  **Join as a member**, "Pay annual dues now and be counted as a current member.", and
  **Join as a friend**, "No dues. Support CalDART when you like, and become a member any
  time." The chosen kind is shown on the verify step's eyebrow.
- Steps stay `account, verify, profile, pay, done`. For a friend the pay step is headed
  **Contribute to CalDART**, renders `<Checkout mode="contribute" onSkip=…>`, and its
  **Not now** button goes to `done`. `furthestJoinStep`: a friend with a complete profile is at
  `pay` if they arrived from `profile` in this visit, otherwise `done` (a friend is never
  held at `pay`). `Checkout` gains the optional `onSkip` prop (renders a quiet **Not now**
  button under the provider tabs).
- A donor's email at registration: `RegisterSerializer` upgrades the donor instead of
  refusing: the account gets the password, the names, `kind` as chosen, the `member` role,
  `email_verified_at = None`, and the verification message; the donations stay on the
  account. A deactivated account's email at registration is refused with
  `{"email": ["This email belongs to a deactivated account. Sign in to reactivate it."],
  "code": "deactivated"}`, and the account step shows a **Sign in to reactivate** link to
  `/login?email=<address>` (the login form prefills the address).
- The dashboard for a friend: the membership card is headed **Friend of CalDART**, its body
  "You are a friend of CalDART: no dues, no expiry. Become a member any time.", its footer
  button **Make me a member** (`/membership/join`, §5.4). `MembershipHeadline` reads
  "You are a friend of CalDART". No urgent edge.
- Docs: `member-guide.rst` (Joining, the steps, the dashboard), `getting-started.rst`,
  `faq.rst`, `docs/developer/api-auth.rst` (`kind` on register, the donor upgrade, the
  deactivated refusal).

### 5.3 Lists, reports, rosters, the member check, and several counties

- **Kind selector.** `MemberAdminFilterSet` gains `kind` (`member` | `friend`; absent means
  all). `MEMBER_FILTERS` in `reports/definitions.ts` gains a select `Kind` with options
  `All` (value `""`), `Members only` (`member`), `Friends only` (`friend`), default `All`,
  placed first. It reaches the member list, the member report (a `Kind` column, on by
  default, right after `Status`), the subscription form, and the rosters: `roster_params`
  passes the roster's `kind` through and `ROSTER_COLUMNS` gains `kind`. `EXPORT_FILTER_PARAMS`
  gains `kind`.
- **Donors and deactivated accounts.** `member_admin_queryset()` excludes `kind = DONOR`
  always. The `is_active` toggle **Active accounts only** becomes **Include deactivated**
  (`include_inactive`, default off): the member list hides deactivated accounts unless it is
  on. The member report, the rosters, and the leader's member check never include
  deactivated accounts or donors. `aircraft_pilots` and `search_members` filter
  `is_active=True` and `kind != DONOR`.
- **The member check.** `LeaderMembershipSerializer` carries the `friend` state; the status
  card's chip reads **Friend**, `noGoReasons` says "Friend of CalDART, not a member", and
  `go_no_go.membership` stays false.
- **Several counties.** `county` on the member list, the member report, and the subscription
  form accepts a comma-separated list (`county=Alameda,Marin`); the filter set uses
  `county__in`. `FilterBar` gains the kind `multiselect` (a `<select multiple>` sized to six
  rows, values joined with commas in the URL and in a subscription's `filters`), and the
  county field becomes one. The PDF subtitle prints the counties joined with ", ". The same
  `multiselect` kind is used for the aircraft register's county filter if it has one, and
  nowhere else.
- Docs: `account-administrator-guide.rst` (Filtering: Kind, Include deactivated, several
  counties; Reports), `dart-leader-guide.rst` (the status card, the member list),
  `docs/developer/api-members.rst` (filters), `reports.rst` (the Kind column, the roster
  columns), `scheduled-reports.rst` (rosters), `architecture.rst#components` (`multiselect`).

### 5.4 Switching kinds

Two endpoints in `apps/members/api/profile_urls.py`, both `IsAuthenticated`, both refusing a
donor (they cannot sign in anyway) and a lifetime member (`400 {"detail": "A lifetime member
stays a member."}`):

- `POST /me/kind/friend` with `{"keep_contribution": true | false}` (required only when the
  renewal mandate carries a contribution). For a member with a current term: `friend_on =
  term.ends_on + 1 day`; the renewal mandate is canceled (`cancel_mandate`, `self_service`);
  when `keep_contribution` is true, a recurring donation (§5.5) is created from the mandate's
  method at yearly cadence for the mandate's `contribution_cents`, first charge on the
  mandate's `next_charge_on`. For a member with no current term (expired, unpaid, or none):
  `kind = FRIEND` at once. Answer `200` with the user payload. Audit `account.kind` with
  `to=friend`, `on=<date>`.
- `DELETE /me/kind/friend`: clears a pending `friend_on` (the Undo). `400 {"detail": "You
  have no pending change."}` otherwise. Canceled mandates are not restored.
- **Make me a member** is not an endpoint: a friend goes to `/portal/membership/join`, a
  page (`features/membership/JoinAsMemberPage.tsx`) that renders `<Checkout mode="join">`;
  the payment's success makes them a member through `activate_term` (§5.1). Nothing changes
  if they leave.
- **Where the buttons live.** The dashboard's membership card footer: a member (not
  lifetime) sees **Make me a friend** beside **Renew**; a friend sees **Make me a member**. The
  profile page gets a card **Your kind of account** below the form with the same button and
  a sentence saying which they are. **Make me a friend** opens a confirmation panel: "Your
  membership stays current through YYYY/MM/DD. On <date> you become a friend of CalDART:
  no dues, no expiry, and no renewal reminders." When the mandate carries a contribution:
  "Your automatic renewal also gives $X each year. Keep giving $X a year as a recurring
  donation?" with **Keep the contribution** and **Stop it** buttons; otherwise a **Make me a
  friend** confirm button. Afterwards the card shows "You become a friend on YYYY/MM/DD."
  with an **Undo** button. A member with no current term converts at once and the card
  changes to the friend card.
- Docs: `member-guide.rst` ("Becoming a friend, becoming a member"), `faq.rst`,
  `docs/developer/api-profile.rst` (the two endpoints), `data-model.rst`.

### 5.5 Recurring donations

The renewal mandate becomes the one mechanism for every scheduled charge.

- **Model.** `RenewalMandate.user` becomes a `ForeignKey` (`related_name="renewal_mandates"`)
  with two conditional unique constraints: one mandate with `plan` set per user
  (`renewal_mandate_one_plan_per_user`) and one with `plan` null per user
  (`renewal_mandate_one_donation_per_user`). `RenewalMandate.cadence` (`CharField`, choices
  `MONTHLY`, `QUARTERLY`, `YEARLY`, default `YEARLY`; a plan mandate is always yearly and the
  serializer refuses anything else). `RenewalAttempt.membership` becomes nullable (a donation
  attempt has no term). `MandateKind` keeps `renewal`, `both`, `contribution`; in every
  user-facing string a contribution-only mandate is a **recurring donation**, a plan mandate
  with a contribution is **automatic renewal and contribution**, and the lifetime member's
  "automatic contribution" is now a recurring donation at yearly cadence.
- **Schedule.** `advance_by_cadence(day, cadence)`: `MONTHLY` adds one month, `QUARTERLY`
  three, `YEARLY` twelve, clamping to the last day of a shorter month (`2026-01-31` monthly
  becomes `2026-02-28`). A donation mandate's `next_charge_on` after a success is
  `advance_by_cadence(attempt.scheduled_on, cadence)`. The 14-day notice email is sent only
  for yearly cadence; monthly and quarterly charges send the charged receipt only (the
  charged email's subject for a donation reads "your recurring donation"). Retries and
  pausing are unchanged.
- **Setting one up.** From the portal's **Donate** screen (`/portal/donate`,
  `features/donate/DonatePage.tsx`, nav entry **Donate** in the Membership group after
  **Payments**), which renders `<Checkout mode="contribute">` with a new block below the
  amount: **Make this a recurring donation** (checkbox), cadence radios **Monthly**,
  **Quarterly**, **Yearly**, and **First charge on** (date, default today, never in the
  past). With the checkbox on and the date today, the payment is taken now and the mandate
  is activated from it (the existing `auto_renew` path) with `next_charge_on =
  advance_by_cadence(today, cadence)`. With a later date, no payment is taken now: the screen
  goes through the setup path (`POST /me/donation/setup`, `POST /me/donation/confirm`) and
  the first charge falls on that date. The `CheckoutSerializer` gains `cadence`; `auto_renew`
  with `plan` null means a recurring donation.
- **Endpoints.** `/me/renewal*` keeps meaning the plan mandate. New `/me/donation`
  (`GET`, `PATCH` with `contribution_cents`, `cadence`, `next_charge_on`, `DELETE`),
  `/me/donation/setup`, `/me/donation/confirm`: the same views and serializers as the renewal
  ones, parameterized by kind (no second copy). `GET /admin/renewals` lists both kinds with a
  `kind` column and a `kind` filter; `RenewalRunResult` and the renewals report gain nothing.
- **One contribution, one place.** `POST /me/donation/setup` or a checkout with `auto_renew`
  and `plan` null, when the user's plan mandate has `contribution_cents > 0`: `400
  {"detail": "Your automatic renewal already includes a contribution of $X a year. Set up a
  recurring donation and that contribution comes off the renewal; your dues still renew
  automatically.", "code": "renewal_contribution"}` unless the body carries
  `remove_renewal_contribution: true`, in which case the plan mandate's `contribution_cents`
  becomes 0 first (audit `renewal.change`). The portal shows that message with a **Continue**
  button that resends with the flag. `PATCH /me/renewal` with `contribution_cents > 0` while
  a donation mandate exists is refused: `{"contribution_cents": ["You already have a recurring
  donation. Change it on the Donate screen."]}`. `check_renewable` for a donation mandate
  requires only `contribution_cents > 0` (any kind of account, lifetime or not).
- **The Payments screen.** `AutoRenewalCard` shows the plan mandate; a second card
  **Recurring donation** (`RecurringDonationCard.tsx`, the same component parameterized, not a
  copy) shows the donation mandate with its cadence and next charge, **Change**, **Turn off**,
  and **Set up** linking to `/donate`. The lifetime member's card is this one.
- **Friends and donors in the scan.** `run_auto_renewals` skips a plan mandate whose user's
  effective kind is friend (`skipped` with reason `friend`; §5.4 cancels them anyway) and
  never touches donors (they hold no mandates). A donation mandate charges regardless of
  membership.
- Docs: `payments.rst` ("Giving", "Recurring donations", the renewal section's wording),
  `treasurer-guide.rst` (Automatic renewals lists both kinds), `docs/developer/renewals.rst`
  (the kinds, the cadence, the constraints), `api-renewals.rst` (the donation endpoints),
  `api-payments.rst` (`cadence`, the refusal), `data-model.rst`.

### 5.6 Donors and the public donation page

- **The page.** `apps/cms/models.py` gains `DonatePage(BasePage)` with `intro`
  (RichText) and `thanks` (RichText, shown after a gift); `HomePage` and `StandardPage`
  allow it as a child; the seed replaces the `donate` `StandardPage` with a `DonatePage` at
  the same slug (`test_cms_seed_content.py` follows). Its template `cms/donate_page.html`
  renders the intro, then `<div id="donate-app" data-config-url="/api/v1/donations/config"
  data-return-url="/donate/">`, and includes a third Vite entry `src/site/donate.tsx`
  through `{% vite_asset %}` in `extra_head`. No inline script (the CSP forbids it).
- **The island.** `src/site/donate.tsx` mounts `<DonationForm>` from
  `frontend/src/donate/DonationForm.tsx` (a new top-level directory beside `site/` and
  `portal/`, so the portal's `no-restricted-imports` rule is untouched). It reuses
  `ContributionChooser`, `Field`, `Button`, `MaskedInput`, the Stripe, PayPal and mock panels,
  and `api/client.ts`; the panels take their endpoints as props (`createIntent`,
  `confirm`, …) so the portal and the public page share one copy. It is wrapped in its own
  `QueryClientProvider` and `ToastProvider`; no router. Fields, in order: **Amount** (the
  tiers and Other amount), **First name***, **Last name***, **Email***, **Phone***, then a
  collapsed **Tell us more (optional)** section with street address, address line 2, city,
  state, postal code, county, airport identifier, airport city, DART, Air Care Alliance
  number, pilot certificate, IFR rated, type of plane, and the six volunteer checkboxes,
  mapped one to one onto `MemberProfile`. Then the provider tabs. After success: the page's
  `thanks` text, the receipt sentence "A receipt is on its way to <email>.", and nothing else.
- **Endpoints** (`apps/payments/api/donation_urls.py`, all `AllowAny`, CSRF enforced by
  the session authentication class, throttle `DonateThrottle` scope `donate`,
  `AUTH_THROTTLE_DONATE`, default `10/hour`):

  | Method and path | Body | Answer |
  | --- | --- | --- |
  | `GET /donations/config` | none | `providers`, `stripe_publishable_key`, `paypal_client_id`, `contribution_tiers`, `max_contribution_cents`, `counties`, `darts`, `states` |
  | `POST /donations/checkout` | the donor fields, `contribution_cents`, `provider` | `201 {"payment_id", "token", ...provider fields}`; `400 {"email": ["An account already uses that email address. Sign in to donate."], "code": "has_account"}` when the address belongs to a member or friend, active or not |
  | `POST /donations/stripe/confirm`, `POST /donations/paypal/capture`, `POST /donations/mock/complete` | the provider's fields plus `payment_id` and `token` | as the portal's confirm endpoints |
  | `GET /donations/{id}?token=` | | the payment's status, for the Stripe redirect return |

  `token` is `signing.dumps({"payment": pk}, salt="payments.donation")`, checked with
  `max_age = 3600`; it is the anonymous caller's proof that they started the payment. The
  services live in `apps/payments/donations.py`: `donor_for(fields)` finds an existing donor by
  email (case-insensitive) and updates its names, phone and profile fields, or creates one
  (`create_account(kind=DONOR)`, unusable password, no role, `email_verified_at` null, a
  `MemberProfile`), then `create_checkout(user, None, contribution_cents, provider)`.
- **Donors cannot sign in or set a password.** Login for a donor answers the generic
  "Incorrect email address or password." (an unusable password never matches);
  `send_password_reset_email`, the invitation, the admin send-reset and send-verification
  views skip a donor, and the reset-confirm serializer refuses a donor's link. A donor gets
  no verification message.
- **Receipts and statements for donors.** `send_receipt` is unchanged; the receipt email's
  "See your payments" link is omitted for a donor (the template branches on
  `user.kind`). Year-end statements: §5.7.
- **Where donors show.** Nowhere in the member list, report, rosters, or member check
  (§5.3). The user administrator's user list gains a `kind` column and filter, so a donor's
  record can be found and its email fixed; the user detail page shows **Donor** and hides the
  password-reset and verification buttons.
- **Seed.** Six donors (`donor1@example.org` … through generated names), each with one to
  three settled mock contribution payments dated through the last two years, one of them
  sharing a DART.
- Docs: a new `docs/user/donations.rst` ("Giving to CalDART" for members and friends; "The
  public donation page" for donors; what a donor gets), `treasurer-guide.rst` (donors),
  `user-administrator.rst` (donor accounts), `docs/developer/api-payments.rst` (the
  donation endpoints), `cms.rst` (`DonatePage`), `architecture.rst` (the third entry),
  `configuration.rst` (`AUTH_THROTTLE_DONATE`), `data-model.rst`.

### 5.7 The donors report and year-end statements

- **Donors report.** `DONOR_REPORT` in `apps/payments/reports.py`: slug `donors`, title
  "Donors", roles `(TREASURER,)`, choosable, landscape, `resolve=payment_period`
  (`period` and `from`/`to` bound the gifts counted). One row per account with `kind =
  DONOR` that has at least one settled contribution in the range: `name`, `email`, `phone`,
  `city`, `state`, `county`*, `dart`*, `first_gift`, `last_gift`, `gifts`, `given`,
  `refunded`*, `net`, `active`* (an asterisk means off by default). Filters: `search`,
  `county` (multiselect), `dart`, `min_cents`, `max_cents`. Registered in `REPORTS`;
  `ReportSlug` gains `'donors'`; `definitions.ts` gains the entry. The finance area gets a
  **Donors** tab (`/admin/payments/donors`, `DonorsPage.tsx`) shown only to a treasurer (or
  a system administrator): `FinanceTabs` learns a per-tab `roles` list. The subscription
  form offers the report to treasurers through the existing role filter.
- **Year-end statements.** `apps/payments/statements.py`: `send_year_statements(year, *,
  today, dry_run) -> StatementRun` sends, to every active account of any kind with settled
  contributions in `year`, the email `contribution_statement` (subject `f"{org}: your {year}
  contribution statement"`, body: thanks, the total, the "No goods or services" sentence,
  and for members and friends a link to Payments) with the statement PDF attached, and
  records `YearStatement(user, year, sent_at)` (unique on `user`, `year`) so a rerun sends
  nothing twice. Purpose label `"contribution_statement": "Contribution statement"`. The
  command `send_year_statements [--year N] [--dry-run] [--today]` defaults `year` to the
  previous calendar year. The timer `caldart-statements.timer` runs `OnCalendar=*-01-15
  06:45:00`, persistent. `POST /system/statements/run` (`IsSystemAdmin`, body `{dry_run,
  year?}`) and a **Year-end statements** panel on the System screen (`StatementsPanel.tsx`,
  the same shape as the reports panel, with a year box defaulting to last year) show the
  run through `RunActionsTable`. Audit `statements.run`. `SystemPage`'s lede counts four
  jobs.
- Docs: `docs/developer/scheduled-reports.rst` or a new `statements.rst` (the job),
  `deployment.rst` (timer section 13, the diagram, "four timers"),
  `system-administrator-guide.rst` (the panel), `treasurer-guide.rst` (the donors tab, the
  statements), `donations.rst`, `reports.rst` (the donors report), `api-reports.rst`,
  `api-system.rst`, `api-payments.rst`, `data-model.rst` (`YearStatement`).

### 5.8 Self-deactivation and reactivation

- **Deactivate.** `POST /auth/deactivate` with `{"current_password"}` (`IsAuthenticated`,
  refused for a donor and a system administrator with `400 {"detail": "A system
  administrator cannot deactivate their own account."}`): cancels every mandate
  (`cancel_mandate` with `self_service`, `discard_pending_mandate`), suspends the covering
  term (below), sets `is_active = False`, records `account.deactivate` with `self_service`,
  and logs the session out. Answer `204`. The `_refuse_self_deactivation` guard in
  `update_account` stays: this is the only self-service path.
- **Suspended terms.** `MembershipStatusChoices` gains `SUSPENDED = "suspended",
  "Suspended"`. Deactivation sets the covering term's status to `SUSPENDED`; a suspended term
  never covers, never counts as past (so `membership_status` for a suspended-only history is
  `NONE` while inactive), and the reminders' `_candidates` excludes it like `CANCELED`.
  Reactivation turns a suspended term whose `ends_on >= today` (or lifetime) back to
  `ACTIVE`, and one whose `ends_on < today` to `EXPIRED`. Audit `membership.correct` for
  both.
- **Reactivate.** `POST /auth/reactivate` with `{"email", "password"}` (`AllowAny`, throttle
  scope `auth_login`): when the account is inactive and the password matches, sets
  `is_active = True`, restores the term, keeps kind and roles, records `account.activate`
  with `self_service`, sends the verification message if `email_verified_at` is null, logs
  the person in, and answers `200` with the user payload. Anything else answers `400
  {"detail": "Incorrect email address or password."}`. A donor is refused the same way.
- **Sign-in.** `POST /auth/login` for an inactive account with the right password keeps its
  `403` and gains `"code": "deactivated"`; its `detail` reads "This account is deactivated.
  You can reactivate it." The login page then shows a panel **Reactivate my account** with
  the sentence "Reactivating brings back your roles and any membership that has not yet
  run out." and a button that posts to `/auth/reactivate` with the same credentials, then
  continues as a sign-in does. The password-reset flow works for an inactive account too:
  `send_password_reset_email` no longer skips it, and a successful reset-confirm for an
  inactive account reactivates it exactly as the endpoint does (the person proved the
  address and chose to come back). The register-side refusal is §5.2.
- **Where the button lives.** The profile page gets a card **Deactivate my account** at the
  bottom: "You will be signed out and will not appear in any list. Your information and your
  payment history are kept. Sign in again any time to reactivate." When the membership is
  current: "Your membership is current through YYYY/MM/DD. Deactivating ends it now; if you
  reactivate before that date, it resumes." A current-password field and a **Deactivate my
  account** button. Success goes to `/login` with the toast "Your account is deactivated.
  Sign in any time to reactivate it."
- The administrator's **Account is active** checkbox and the user administrator's flag work
  as before, and the user guide says a deactivated person can reactivate at sign-in (#265
  is the future block).
- Docs: `member-guide.rst` ("Deactivating your account"), `getting-started.rst` (Signing
  in: the reactivation panel), `faq.rst`, `user-administrator.rst` (Activating and
  deactivating: what the person can do themselves), `account-administrator-guide.rst`
  (Danger zone), `docs/developer/api-auth.rst` (the two endpoints, the login code, the reset
  rule), `data-model.rst` (`SUSPENDED`), `reminders.rst`.

## 6. Failure handling and the final report

- **A failing gate.** Three fix attempts within scope; then the PR stays open as a draft with
  a comment saying what failed, and the orchestrator carries on with every package that does
  not depend on it.
- **A rebase conflict outside the package's files.** Same.
- **CI red on `main`.** No new package starts until a fix PR restores it.
- **The final report** lists every PR merged, every decision of #264 with the PR that
  settled it, and every decision taken that §5 did not cover.
- **Archive.** The closeout PR moves this plan to `plans/archive/`.

## 7. Work packages

### Wave 1

#### account-kinds (Opus)

- **Refs:** #264
- **Branch:** `feature/account-kinds`; database `caldart_account_kinds`; e2e port 8201
- **Owns:** `backend/apps/accounts/models.py#kind`, `backend/apps/accounts/migrations/0001_initial.py`, `backend/apps/accounts/roles.py#member-description`, `backend/apps/accounts/services.py#kind`, `backend/apps/accounts/api/serializers.py#kind`, `backend/apps/accounts/api/views.py#kind`, `backend/apps/accounts/api/filters.py#kind`, `backend/apps/accounts/seed.py#friend`, `backend/apps/members/models.py#friend-state`, `backend/apps/members/services.py#kind`, `backend/apps/members/api/admin_serializers.py#kind`, `backend/apps/members/api/profile_serializers.py#kind`, `backend/apps/members/seed.py#friend`, `backend/apps/payments/seed.py#friend`, `backend/apps/payments/services.py#friend-checkout`, `backend/apps/cms/models.py#wall-friend`, `backend/templates/cms/members_only_wall.html#friend`, `backend/apps/reminders/services.py#convert-friends`, `backend/caldart/audit.py#kind`, `backend/caldart/settings/base.py#kind-enum`, `backend/tests/test_account_kinds.py` (new), `backend/tests/test_seed.py#kinds`, `backend/tests/test_members_admin_status.py#friend`, `backend/tests/factories.py#kind`, `backend/tests/conftest.py#friend-fixture`, `frontend/src/portal/api/types.ts#kind`, `frontend/src/portal/choices.ts#kind`, `frontend/src/portal/components/StatusChip.tsx#friend`, `frontend/src/test/handlers.ts#kind`, `frontend/src/portal/features/admin-users/UsersListPage.tsx#kind`, `frontend/src/portal/features/admin-users/UserDetailPage.tsx#kind`, `frontend/src/portal/features/admin-members/MemberDetailPage.tsx#kind`, `frontend/src/portal/features/admin-members/MemberFormFields.tsx#kind`, `docs/user/overview.rst#kinds`, `docs/user/getting-started.rst#kinds`, `docs/user/member-guide.rst#kinds`, `docs/user/faq.rst#friend`, `docs/user/user-administrator.rst#kind`, `docs/user/account-administrator-guide.rst#kind-field`, `docs/developer/data-model.rst#kind`, `docs/developer/api-auth.rst#kind`, `docs/developer/api-members.rst#kind`, `docs/developer/api-profile.rst#friend-state`, `docs/developer/reminders.rst#convert-friends`, `docs/developer/cms.rst#wall-friend`.
- **Steps:** §5.1 in full, plus the `kind` accepted by `POST /auth/register` from §5.2 (the wizard's UI is `join-friend`'s), the donor upgrade and the deactivated refusal at registration from §5.2, the user administrator's `kind` column, filter, and detail label from §5.6 (a donor's detail page hides the reset and verification buttons), and the donor sign-in and password rules from §5.6 (login, reset, invitation, admin sends, reset-confirm all refuse a donor).
- **Verify:** `make test e2e`; `make lint`; after `make reset`, `friend@example.org` signs in and `/me/membership` answers `friend`; the member list shows the friend with the Friend chip.

### Wave 2

#### join-friend (Opus)

- **Refs:** #264
- **After:** account-kinds
- **Branch:** `feature/join-friend`; database `caldart_join_friend`; e2e port 8202
- **Owns:** `frontend/src/portal/features/join/**`, `frontend/src/portal/features/checkout/Checkout.tsx#skip`, `frontend/src/portal/features/checkout/Checkout.test.tsx#skip`, `frontend/src/portal/features/dashboard/DashboardPage.tsx#friend`, `frontend/src/portal/features/dashboard/DashboardPage.test.tsx#friend`, `frontend/src/portal/features/auth/LoginPage.tsx#prefill`, `frontend/src/portal/features/auth/LoginPage.test.tsx#prefill`, `frontend/src/portal/auth/useAuth.ts#register-kind`, `frontend/e2e/join-and-pay.spec.ts#friend`, `frontend/e2e/join-friend.spec.ts` (new), `docs/user/member-guide.rst#joining`, `docs/user/getting-started.rst#joining`, `docs/user/faq.rst#joining`.
- **Steps:** §5.2 in full except the backend pieces `account-kinds` shipped.
- **Verify:** `make test e2e`; `make lint`.

#### list-filters (Opus)

- **Refs:** #264
- **After:** account-kinds
- **Branch:** `feature/list-filters`; database `caldart_list_filters`; e2e port 8203
- **Owns:** `backend/apps/members/filters.py`, `backend/apps/members/reports.py#kind`, `backend/apps/members/api/admin_views.py#kind`, `backend/apps/aircraft/services.py#active-kind`, `backend/apps/aircraft/api/serializers.py#friend`, `backend/apps/aircraft/filters.py#county`, `backend/apps/reports/services.py#roster-kind`, `backend/tests/test_list_filters.py` (new), `backend/tests/test_members_reports.py#kind`, `backend/tests/test_dart_rosters.py#kind`, `backend/tests/test_leader_api.py#friend`, `backend/tests/test_member_county.py#multi`, `frontend/src/portal/components/FilterBar.tsx#multiselect`, `frontend/src/portal/components/FilterBar.test.tsx#multiselect`, `frontend/src/portal/reports/types.ts#multiselect`, `frontend/src/portal/reports/definitions.ts#members`, `frontend/src/portal/features/admin-members/MembersListPage.tsx`, `frontend/src/portal/features/admin-members/MembersListPage.test.tsx`, `frontend/src/portal/features/admin-members/choices.ts`, `frontend/src/portal/features/leader/**`, `frontend/src/portal/features/admin-reports/RostersCard.tsx#kind`, `frontend/e2e/leader-check.spec.ts#friend`, `docs/user/account-administrator-guide.rst#filtering`, `docs/user/dart-leader-guide.rst#friend`, `docs/developer/api-members.rst#filters`, `docs/developer/reports.rst#kind-column`, `docs/developer/scheduled-reports.rst#roster-kind`, `docs/developer/architecture.rst#multiselect`.
- **Steps:** §5.3 in full.
- **Verify:** `make test e2e`; `make lint`; the member report's PDF with `county=Alameda,Marin` lists both counties in its subtitle.

#### recurring-donations (Opus)

- **Refs:** #264
- **After:** account-kinds
- **Branch:** `feature/recurring-donations`; database `caldart_recurring_donations`; e2e port 8204
- **Owns:** `backend/apps/payments/models.py#mandate`, `backend/apps/payments/migrations/0001_initial.py`, `backend/apps/payments/renewals.py`, `backend/apps/payments/services.py#donation-checkout`, `backend/apps/payments/api/serializers.py#mandate`, `backend/apps/payments/api/renewal_views.py`, `backend/apps/payments/api/renewal_urls.py`, `backend/apps/payments/api/checkout_urls.py#donation`, `backend/apps/payments/seed.py#donation-mandate`, `backend/apps/payments/management/commands/run_auto_renewals.py`, `backend/templates/emails/renewal_*`, `backend/caldart/audit.py#renewal`, `backend/caldart/settings/base.py#cadence-enum`, `backend/tests/test_recurring_donations.py` (new), `backend/tests/test_renewals.py#kinds`, `backend/tests/test_renewals_api.py#donation`, `backend/tests/test_contribution_mandates.py`, `backend/tests/test_contribution_mandate_enable.py`, `backend/tests/test_renewal_date.py#cadence`, `backend/tests/factories.py#mandate`, `backend/tests/golden/renewal-*.txt`, `frontend/src/portal/api/types.ts#mandate`, `frontend/src/portal/api/queries.ts#donation`, `frontend/src/portal/features/checkout/**` (except `Checkout.tsx#skip`), `frontend/src/portal/features/payments/**`, `frontend/src/portal/features/donate/**` (new), `frontend/src/portal/routes/donate.tsx` (new), `frontend/src/portal/nav.ts#donate`, `frontend/src/portal/features/admin-payments/RenewalsPage.tsx#kind`, `frontend/src/test/handlers.ts#donation`, `frontend/src/test/fixtures/payments.ts`, `frontend/e2e/auto-renew.spec.ts`, `frontend/e2e/recurring-donation.spec.ts` (new), `docs/user/payments.rst`, `docs/user/treasurer-guide.rst#renewals`, `docs/developer/renewals.rst`, `docs/developer/api-renewals.rst`, `docs/developer/api-payments.rst#cadence`, `docs/developer/data-model.rst#mandate`.
- **Steps:** §5.5 in full.
- **Verify:** `make test e2e`; `make lint`; `make reset` then a monthly donation set up for today charges at once and its next charge is one month on.

#### self-deactivation (Opus)

- **Refs:** #264, #265
- **After:** account-kinds
- **Branch:** `feature/self-deactivation`; database `caldart_self_deactivation`; e2e port 8205
- **Owns:** `backend/apps/accounts/services.py#deactivation`, `backend/apps/accounts/api/serializers.py#deactivation`, `backend/apps/accounts/api/views.py#deactivation`, `backend/apps/accounts/api/urls.py#deactivation`, `backend/apps/members/models.py#suspended`, `backend/apps/members/migrations/0001_initial.py`, `backend/apps/members/services.py#suspend`, `backend/apps/reminders/services.py#suspended`, `backend/caldart/audit.py#self-service`, `backend/tests/test_self_deactivation.py` (new), `backend/tests/test_accounts_auth.py#reactivate`, `backend/tests/test_reminders.py#suspended`, `frontend/src/portal/api/types.ts#deactivation`, `frontend/src/portal/auth/useAuth.ts#deactivation`, `frontend/src/portal/features/auth/LoginPage.tsx#reactivate`, `frontend/src/portal/features/auth/LoginPage.test.tsx#reactivate`, `frontend/src/portal/features/profile/ProfilePage.tsx#deactivate`, `frontend/src/portal/features/profile/DeactivateCard.tsx` (new), `frontend/src/portal/features/profile/DeactivateCard.test.tsx` (new), `frontend/src/portal/features/profile/api.ts#deactivate`, `frontend/src/test/handlers.ts#deactivation`, `frontend/e2e/deactivation.spec.ts` (new), `docs/user/member-guide.rst#deactivation`, `docs/user/getting-started.rst#reactivation`, `docs/user/faq.rst#deactivation`, `docs/user/user-administrator.rst#self-deactivation`, `docs/user/account-administrator-guide.rst#danger-zone`, `docs/developer/api-auth.rst#deactivation`, `docs/developer/data-model.rst#suspended`, `docs/developer/reminders.rst#suspended`.
- **Steps:** §5.8 in full. The mandate cancellation calls the `cancel_mandate` and `discard_pending_mandate` that exist on `main` at the start of the wave; `recurring-donations` changes their shape in the same wave, so this package calls them through one helper `cancel_all_mandates(user)` that it adds to `apps/payments/renewals.py#cancel-all` (additive, declared), which the orchestrator reconciles at merge.
- **Verify:** `make test e2e`; `make lint`.

### Wave 3

#### friend-switching (Opus)

- **Refs:** #264
- **After:** join-friend, recurring-donations, self-deactivation
- **Branch:** `feature/friend-switching`; database `caldart_friend_switching`; e2e port 8206
- **Owns:** `backend/apps/members/services.py#switch`, `backend/apps/members/api/profile_views.py#kind`, `backend/apps/members/api/profile_serializers.py#switch`, `backend/apps/members/api/profile_urls.py#kind`, `backend/apps/payments/renewals.py#convert-contribution`, `backend/tests/test_friend_switching.py` (new), `frontend/src/portal/api/types.ts#switch`, `frontend/src/portal/features/dashboard/DashboardPage.tsx#switch`, `frontend/src/portal/features/dashboard/DashboardPage.test.tsx#switch`, `frontend/src/portal/features/dashboard/KindSwitch.tsx` (new), `frontend/src/portal/features/dashboard/KindSwitch.test.tsx` (new), `frontend/src/portal/features/profile/ProfilePage.tsx#kind`, `frontend/src/portal/features/profile/api.ts#kind`, `frontend/src/portal/features/membership/**` (new), `frontend/src/portal/routes/membership.tsx` (new), `frontend/src/test/handlers.ts#switch`, `frontend/e2e/friend-switching.spec.ts` (new), `docs/user/member-guide.rst#switching`, `docs/user/faq.rst#switching`, `docs/developer/api-profile.rst#switching`, `docs/developer/data-model.rst#switching`, `docs/developer/renewals.rst#switching`.
- **Steps:** §5.4 in full.
- **Verify:** `make test e2e`; `make lint`.

#### public-donations (Opus)

- **Refs:** #264
- **After:** recurring-donations
- **Branch:** `feature/public-donations`; database `caldart_public_donations`; e2e port 8207
- **Owns:** `backend/apps/cms/models.py#donate-page`, `backend/apps/cms/migrations/0001_initial.py`, `backend/apps/cms/management/commands/seed_content.py#donate`, `backend/apps/cms/management/commands/seed_content_data.py#donate`, `backend/templates/cms/donate_page.html` (new), `backend/apps/payments/donations.py` (new), `backend/apps/payments/api/donation_views.py` (new), `backend/apps/payments/api/donation_serializers.py` (new), `backend/apps/payments/api/donation_urls.py` (new), `backend/apps/payments/api/urls.py#donations`, `backend/apps/payments/seed.py#donors`, `backend/apps/accounts/throttling.py#donate`, `backend/caldart/settings/base.py#donate-throttle`, `.env.example#donate`, `backend/templates/emails/receipt.*#donor`, `backend/tests/test_public_donations.py` (new), `backend/tests/test_cms_seed_content.py#donate`, `backend/tests/test_seed.py#donors`, `backend/tests/test_auth_throttle_rates.py#donate`, `frontend/vite.config.ts#donate-entry`, `frontend/src/site/donate.tsx` (new), `frontend/src/donate/**` (new), `frontend/src/portal/features/checkout/StripePanel.tsx#endpoints`, `frontend/src/portal/features/checkout/PayPalPanel.tsx#endpoints`, `frontend/src/portal/features/checkout/MockPanel.tsx#endpoints`, `frontend/eslint.config.js#donate`, `frontend/e2e/public-donation.spec.ts` (new), `frontend/e2e/public-site.spec.ts#donate`, `docs/user/donations.rst` (new), `docs/user/index.rst#donations`, `docs/user/treasurer-guide.rst#donors`, `docs/user/user-administrator.rst#donors`, `docs/developer/api-payments.rst#donations`, `docs/developer/cms.rst#donate-page`, `docs/developer/architecture.rst#donate-entry`, `docs/developer/configuration.rst#donate`, `docs/developer/data-model.rst#donors`.
- **Steps:** §5.6 in full except the pieces `account-kinds` shipped (the donor's sign-in and password rules, the user list column).
- **Verify:** `make test e2e`; `make lint`; `make build` then `make run` signed out: `/donate/` takes a mock gift from a new address, the receipt appears in Mailpit, and a second gift from the same address reuses the donor.

#### donors-and-statements (Sonnet)

- **Refs:** #264
- **After:** account-kinds
- **Branch:** `feature/donors-and-statements`; database `caldart_donors_statements`; e2e port 8208
- **Owns:** `backend/apps/payments/reports.py#donors`, `backend/apps/payments/statements.py` (new), `backend/apps/payments/models.py#year-statement`, `backend/apps/payments/migrations/0001_initial.py#year-statement`, `backend/apps/payments/management/commands/send_year_statements.py` (new), `backend/apps/payments/api/report_views.py#donors`, `backend/apps/payments/api/report_urls.py#donors`, `backend/apps/payments/api/serializers.py#statements-run`, `backend/apps/sysadmin/api/views.py#statements`, `backend/apps/sysadmin/api/urls.py#statements`, `backend/apps/reports/registry.py#donors`, `backend/apps/mail/purposes.py#statement`, `backend/templates/emails/contribution_statement.txt` (new), `backend/templates/emails/contribution_statement.html` (new), `backend/caldart/audit.py#statements`, `deploy/systemd/caldart-statements.service` (new), `deploy/systemd/caldart-statements.timer` (new), `backend/tests/test_donor_report.py` (new), `backend/tests/test_year_statements.py` (new), `backend/tests/test_permission_matrix.py#donors`, `backend/tests/test_report_registry.py#donors`, `frontend/src/portal/api/types.ts#statements`, `frontend/src/portal/reports/types.ts#donors`, `frontend/src/portal/reports/definitions.ts#donors`, `frontend/src/portal/reports/definitions.test.ts#donors`, `frontend/src/portal/features/admin-payments/FinanceTabs.tsx`, `frontend/src/portal/features/admin-payments/DonorsPage.tsx` (new), `frontend/src/portal/features/admin-payments/DonorsPage.test.tsx` (new), `frontend/src/portal/features/admin-payments/api.ts#donors`, `frontend/src/portal/routes/admin-payments.tsx#donors`, `frontend/src/portal/features/system/StatementsPanel.tsx` (new), `frontend/src/portal/features/system/StatementsPanel.test.tsx` (new), `frontend/src/portal/features/system/SystemPage.tsx#statements`, `frontend/src/portal/features/system/api.ts#statements`, `frontend/src/test/handlers.ts#statements`, `docs/developer/statements.rst` (new), `docs/developer/index.rst#statements`, `docs/developer/deployment.rst#statements`, `docs/user/system-administrator-guide.rst#statements`, `docs/user/treasurer-guide.rst#donors-tab`, `docs/developer/reports.rst#donors`, `docs/developer/api-reports.rst#donors`, `docs/developer/api-system.rst#statements`, `docs/developer/api-payments.rst#donors`, `docs/developer/data-model.rst#year-statement`.
- **Steps:** §5.7 in full. `payments/migrations/0001_initial.py` is also edited by `recurring-donations` in wave 2; this package starts after it merges (its `after` list), so the file is rebased, not conflicted. The statements job runs on `main`'s seed: on a fresh seed of `year = today.year - 1` it emails every account with contributions in that year.
- **Verify:** `make test e2e`; `make lint`; `make reset` then `uv run python backend/manage.py send_year_statements --dry-run` lists the seeded givers of last year.

### Wave 4

#### closeout (Sonnet)

- **Closes:** #264
- **After:** friend-switching, public-donations, donors-and-statements, list-filters
- **Branch:** `chore/members-friends-donors-closeout`; database `caldart_kinds_closeout`; e2e port 8209
- **Owns:** `docs/**#residue`, `frontend/src/**#residue`, `backend/**#residue`, `plans/2026-09-25-members-friends-donors.md` (moves to `plans/archive/`).
- **Steps:** re-run every numbered decision of #264 against `main` and fix small residue in scope; read the member guide, getting-started, the FAQ, the payments and donations pages, the treasurer guide, the user administrator page, and the account administrator guide top to bottom for contradictions (a friend called "expired", a donor in a member list, "each year" where a cadence applies, "three jobs"); confirm the e2e seed facts still pick a member for the leader check; the PR body lists every decision of #264 with the PR that settled it; move the plan to the archive.
- **Verify:** `make lint test check docs audit e2e` green.

## 8. Manifest

```json
[
  {"wave": 1, "package": "account-kinds", "model": "opus", "branch": "feature/account-kinds", "database": "caldart_account_kinds", "e2e_port": 8201, "closes": [], "refs": [264], "after": []},
  {"wave": 2, "package": "join-friend", "model": "opus", "branch": "feature/join-friend", "database": "caldart_join_friend", "e2e_port": 8202, "closes": [], "refs": [264], "after": ["account-kinds"]},
  {"wave": 2, "package": "list-filters", "model": "opus", "branch": "feature/list-filters", "database": "caldart_list_filters", "e2e_port": 8203, "closes": [], "refs": [264], "after": ["account-kinds"]},
  {"wave": 2, "package": "recurring-donations", "model": "opus", "branch": "feature/recurring-donations", "database": "caldart_recurring_donations", "e2e_port": 8204, "closes": [], "refs": [264], "after": ["account-kinds"]},
  {"wave": 2, "package": "self-deactivation", "model": "opus", "branch": "feature/self-deactivation", "database": "caldart_self_deactivation", "e2e_port": 8205, "closes": [], "refs": [264, 265], "after": ["account-kinds"]},
  {"wave": 3, "package": "friend-switching", "model": "opus", "branch": "feature/friend-switching", "database": "caldart_friend_switching", "e2e_port": 8206, "closes": [], "refs": [264], "after": ["join-friend", "recurring-donations", "self-deactivation"]},
  {"wave": 3, "package": "public-donations", "model": "opus", "branch": "feature/public-donations", "database": "caldart_public_donations", "e2e_port": 8207, "closes": [], "refs": [264], "after": ["recurring-donations"]},
  {"wave": 3, "package": "donors-and-statements", "model": "sonnet", "branch": "feature/donors-and-statements", "database": "caldart_donors_statements", "e2e_port": 8208, "closes": [], "refs": [264], "after": ["account-kinds", "recurring-donations"]},
  {"wave": 4, "package": "closeout", "model": "sonnet", "branch": "chore/members-friends-donors-closeout", "database": "caldart_kinds_closeout", "e2e_port": 8209, "closes": [264], "refs": [], "after": ["friend-switching", "public-donations", "donors-and-statements", "list-filters"]}
]
```
