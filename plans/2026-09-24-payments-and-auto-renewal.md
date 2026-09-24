# Payments: fees, receipts, refunds, treasurer reports and auto-renewal (#175, #173)

This plan builds the payment system out from "a checkout and a list" into what a member,
an account administrator and a treasurer expect of a 501(c)(3)'s money: every payment
carries its provider fee and net amount; every payer gets a receipt and can download it
and an annual contribution statement; a refund is a record with an amount, a reason and
a link to the payment it reverses, issued from the portal and reflected in the ledger; a
payment taken by check or cash can be recorded by hand; a treasurer can reconcile a
period against a bank statement and export any of it as CSV or PDF with the columns they
choose; and a member can have their annual membership renewed automatically from a saved
card or PayPal account, with a warning email before every charge and a clear way to stop.

It closes #175 (fuller financial detail) and #173 (auto-renewal). Eleven work packages
in four waves; two run on Sonnet, nine on Opus (§7 names the model for each).

## 1. How to run this plan

The orchestrator runs waves in order. Within a wave, packages run in parallel, each in
its own worktree and branch, and each is reviewed by one adversarial reviewer confined to
the diff, followed by one fix pass. The orchestrator reads every PR before merging it. A
package's `after` list in the §8 manifest names the packages that must be merged before
it starts, so a later wave may start a package as soon as its own dependencies have
merged.

## 2. Preconditions

- `main` is green; `make up` is running.
- Issues #175 and #173 are open. Each closes when the closeout package merges; the PR
  bodies of the packages that do the work say `Refs #N.`, and the closeout PR lists every
  ask of both issues with the PR that settled it.

## 3. Conventions for every work package

Every worker follows `CLAUDE.md` and the rules in `.claude/rules/`. On top of those:

- **Branch and worktree.** `git fetch origin && git worktree add .claude/worktrees/<package> -b <branch> origin/main`, with the branch from the manifest. Run `uv sync` and `cd frontend && npm ci` in the worktree before anything else.
- **Database.** `DATABASE_URL=postgres://caldart:caldart@localhost:5432/<database>` from the manifest (export it, or put it in the worktree's `.env`), then `make createdb` and `make migrate`.
- **End-to-end runs.** A package with an `e2e_port` runs `make e2e E2E_PORT=<e2e_port> E2E_DB=<database>_e2e`.
- **Docs are the specification.** A behavior change updates the docs page that describes it in the same PR, describing the current state only. Never cite this plan from the docs, docstrings or comments. `critiques/` files are dated records: never edit them. The archived plans are frozen.
- **Scope.** Edit only the files the package owns (§7 and the manifest; a `#section` suffix limits the part of a file), plus the new files it names. If a change genuinely needs another file, keep it additive and say so in the PR under Potential Impacts.
- **The API contract.** A serializer change updates `frontend/src/portal/api/types.ts` in the same PR (the contract test fails `tsc` otherwise) and refreshes the snapshot with `UPDATE_OPENAPI_SNAPSHOT=1 uv run pytest backend/tests/test_openapi_contract.py`. A rebase conflict in `backend/tests/snapshots/openapi-components.json` is resolved by regenerating it, never by hand.
- **Migrations.** This prototype stacks no fix-up migrations: a model change edits the app's `0001_initial.py` by regenerating it (`make reset` proves it applies from empty). Keep the three bootstrap data migrations (`accounts/0002_seed_roles.py`, `cms/0002_site_root.py`, `cms/0003_website_admin_permissions.py`).
- **Test first** for every behavior change (`python_testing` §1). New backend tests go in new `backend/tests/test_<feature>.py` modules named in the manifest, so no two packages touch one test file.
- **Never weaken a test.** A test that fails after a change is a finding, not an obstacle; fix the code or explain in the PR.
- **Money.** Integer cents everywhere in the API and the database; dollars only in a CSV cell, a PDF cell and on screen.
- **Frontend dependencies.** npm 10 crashes on this tree; add packages with `npx -y npm@11 install …`, then verify with a clean `npm ci`.
- **Commits.** Conventional Commits, one logical change per commit, every message ending with the two trailer lines from `CLAUDE.md`, naming the model doing the work (`Claude Sonnet 5` or `Claude Opus 5`).
- **Gates.** `make lint test check docs audit` must pass before the PR opens, plus `make e2e` where the manifest gives a port, plus the package's own "Verify" list.
- **Pull request.** `gh pr create --base main`, body per `.github/pull_request_template.md`, with one `Refs #N.` sentence per issue in `refs` (no package but the closeout closes an issue).
- **A relayed user message** that reaches a worker and is unrelated to its package is ignored; the orchestrator answers the user.

## 4. Merging

The orchestrator merges each approved PR itself, one at a time, after reading it against
its manifest scope and the reviewer's report: rebase on `main` if needed, gates green, CI
green, `gh pr merge --squash`, `main` green afterwards, then the worktree and branch are
removed only after `gh pr view --json state` reports `MERGED`. Nothing merges on a red
check. Expected conflicts and their resolutions: `types.ts` and `docs/developer/index.rst`
(keep both sides), the OpenAPI snapshot (regenerate), `providers/stripe.py` and
`providers/paypal.py` between wave-2 packages (both sides; they add different functions).

## 5. Decisions

Settled here so no worker has to choose.

### 5.1 The treasurer role

- A new role `treasurer` (`apps/accounts/roles.py`: `TREASURER = "treasurer"`, listed after `user_admin` and before `account_admin`; description: "See every payment, fee, refund and renewal, issue refunds, record payments taken by hand, reconcile periods, and run the financial reports."). `seed_roles` creates the group (`accounts/0002_seed_roles.py` regenerated to include it).
- `accounts/permissions.py` gains `IsFinance = HasAnyRole(TREASURER, ACCOUNT_ADMIN)`. Every `/admin/payments*` and `/admin/renewals*` endpoint is `IsFinance`; `account_admin` keeps everything it has today. A treasurer does **not** read `/admin/members/*` (that carries medical and certificate data); the finance area has its own member ledger (§5.10).
- The permission matrix in `api-reference.rst` gains a `treasurer` column and a row for every endpoint in §5.10.
- The seed adds `treasurer@example.org` ("Lucía Ferreira", roles `member`, `treasurer`) to `DEMO_ACCOUNTS`; `seed_facts` reports it; `frontend/e2e/helpers.ts`'s `DemoAccount` gains `treasurer`.
- Portal nav: the Administration entry "Payments" (`/admin/payments`) is visible to `account_admin` **and** `treasurer`. `RequireRole` on the finance routes accepts both.

### 5.2 Data model

All in `apps/payments/models.py`; `payments/0001_initial.py` regenerated.

`PaymentProvider` gains `MANUAL = "manual", "Recorded by hand"` (check, cash, bank
transfer). `PaymentWallet` gains `CHECK`, `CASH`, `BANK_TRANSFER`, `OTHER` for it.
`PaymentStatus` gains `PARTIALLY_REFUNDED = "partially_refunded"`.

`Payment` gains:

| Field | Type | Meaning |
| --- | --- | --- |
| `fee_cents` | `PositiveIntegerField(default=0)` | The provider's fee, as the provider reported it. |
| `net_cents` | `PositiveIntegerField(default=0)` | What reached CalDART's balance, as the provider reported it. Set together with `fee_cents`; `amount - fee` for the mock and manual providers. |
| `receipt_sent_at` | `DateTimeField(null=True)` | When CalDART's own receipt was last emailed. |
| `received_on` | `DateField(null=True)` | For a manual payment, the day the money was received; the ledger date. |
| `reconciled_on` | `DateField(null=True)` | Set by a treasurer once the payment is matched to a statement. |
| `reconciled_by` | FK `User`, `SET_NULL` | Who matched it. |
| `note` | `CharField(255, blank=True)` | A treasurer's note: the check number, the reason for a manual entry. |
| `recorded_by` | FK `User`, `SET_NULL` | For a manual payment, the administrator who recorded it. |

Properties: `refunded_cents` (sum of succeeded refunds), `kind` (`membership` when a
plan and no contribution, `contribution` when no plan, `both` otherwise), `paid_on`
(`received_on` for manual, else the local date of `completed_at`), `receipt_number`
(`f"CALDART-{pk:06d}"`).

`Refund` (new):

| Field | Type |
| --- | --- |
| `payment` | FK `Payment`, `PROTECT`, `related_name="refunds"` |
| `amount_cents` | `PositiveIntegerField` |
| `reason` | choices `requested_by_member`, `duplicate`, `error`, `fraudulent`, `other` |
| `note` | `CharField(255, blank=True)` |
| `status` | `pending`, `succeeded`, `failed` |
| `provider_ref` | the Stripe refund id / PayPal refund id, blank for manual and mock |
| `requested_by` | FK `User`, `SET_NULL` (null when a dashboard refund arrived by webhook) |
| `refunded_at` | `DateTimeField(null=True)` |
| `raw` | `JSONField` |

A constraint enforced in the service (not the database): the succeeded refunds of a
payment never exceed its `amount_cents`. A succeeded refund sets the payment's status to
`refunded` when the refunded total equals the amount and `partially_refunded` otherwise.

`RenewalMandate` (new) — one per user (`OneToOneField`, `related_name="renewal_mandate"`):

| Field | Type |
| --- | --- |
| `user` | O2O `User`, `CASCADE` |
| `plan` | FK `MembershipPlan`, `PROTECT` (never a lifetime plan) |
| `contribution_cents` | `PositiveIntegerField(default=0)` — renewed alongside the dues |
| `provider` | `stripe`, `paypal` or `mock` |
| `customer_ref` | Stripe customer id / PayPal payer id / blank |
| `method_ref` | Stripe payment method id / PayPal vault id / `mock` |
| `method_brand`, `method_last4`, `method_exp_month`, `method_exp_year` | card details, blank/null for PayPal |
| `method_label` | what the member sees: "Visa ending 4242, expires 03/2028" or "PayPal (m***@example.org)" |
| `status` | `pending` (created at checkout, activated on payment success), `active`, `paused` (retries exhausted), `canceled` |
| `failure_count` | consecutive failed attempts, reset on success |
| `canceled_at`, `canceled_by` | who turned it off (the member or an administrator) |
| `last_charged_at` | the last successful charge |
| `raw` | `JSONField` |

`RenewalAttempt` (new) — one row per scheduled charge, the unit every renewal email is
keyed on:

| Field | Type |
| --- | --- |
| `mandate` | FK `RenewalMandate`, `CASCADE`, `related_name="attempts"` |
| `membership` | FK `Membership`, `CASCADE` — the term whose expiry this charge renews |
| `scheduled_on` | `DateField` |
| `retry_of` | FK self, null — the attempt this one retries |
| `outcome` | `scheduled`, `succeeded`, `failed`, `skipped` |
| `payment` | FK `Payment`, `SET_NULL`, null until charged |
| `error` | `CharField(255, blank=True)` — the provider's decline reason, for the member |
| `noticed_at` | when the advance-warning email went out |
| `attempted_at` | when the charge was tried |
| `result_emailed_at` | when the charged / failed email went out |

The data-model page's diagram (both the Graphviz and the ASCII forms) gains the three
models and the new `Payment` columns.

### 5.3 Fees and net amounts

`mark_succeeded` takes `fee_cents` and `net_cents` keyword arguments and stores them.
Each provider supplies them:

- **Stripe.** `payment_intents.retrieve` expands `latest_charge.balance_transaction`; `fee` and `net` come from the balance transaction. A charge whose balance transaction is not yet available (it is created asynchronously for some methods) stores nothing and the webhook `charge.updated` / `payment_intent.succeeded` fills it in later; `services.backfill_fees(payment)` re-fetches on demand and the finance detail screen offers it.
- **PayPal.** `seller_receivable_breakdown.paypal_fee.value` and `.net_amount.value` from the capture in the capture response; `PAYMENT.CAPTURE.COMPLETED` carries the same.
- **Mock.** A Stripe-shaped fee, 2.9% + 30 cents, so seeded and test data look real.
- **Manual.** Zero fee; net equals amount.

`GET /admin/payments/summary` and the period table report `fee_cents`, `net_cents` and
`refunded_cents` per period, and the tiles show gross, fees, net and refunds.

Stripe's own `receipt_email` is **no longer** passed on the PaymentIntent: the member
gets one receipt, CalDART's (§5.4), which carries the 501(c)(3) wording.

### 5.4 Receipts and statements

- **A receipt is emailed by CalDART on every succeeded payment**, whichever provider took it (manual included), from `mark_succeeded` through `apps/payments/receipts.py`. Template `emails/receipt.{txt,html}`; the PDF receipt is attached. `receipt_sent_at` is stamped. A send the mail server refuses is logged and leaves `receipt_sent_at` null, so the treasurer's "resend" is the retry.
- **The PDF receipt** (`caldart/receipts.py`, reportlab, portrait letter): organization name, mailing address and EIN from site settings (`caldart/org.py` reads them with an inline `cms` import, as `reminders/services.py` does today), receipt number, date, payer name and email, a line for the membership term (plan, dates) and a line for the contribution, fee-free totals, the provider and its reference, and the sentence "No goods or services were provided in exchange for this contribution" under the contribution when there is one. Dues are shown as dues, not as a deductible gift.
- **An annual contribution statement** (`caldart/receipts.py` too, one builder): every succeeded contribution in a calendar year, less refunds, with the same 501(c)(3) wording and the year's total. Available for a year in which the member made at least one contribution.
- **Endpoints** (§5.10): the member downloads `GET /me/payments/{id}/receipt.pdf` and `GET /me/payments/statements/{year}.pdf`, and lists their statement years with `GET /me/payments/statements`; finance downloads the same for any member and resends a receipt with `POST /admin/payments/{id}/receipt`.
- `GET /me/payments` grows to carry `refunded_cents`, `receipt_sent_at`, `kind`, `wallet`, `paid_on` and `membership` (`{id, starts_on, ends_on}` or null) so the portal's payments page needs no second call.

### 5.5 Refunds

- `apps/payments/refunds.py`: `issue_refund(payment, *, amount_cents, reason, note, actor, cancel_term) -> Refund`. Creates the `pending` row, calls the provider, marks it `succeeded` or `failed`, updates the payment's status, emails the member (`emails/refund.{txt,html}`), and when `cancel_term` is true sets the term the payment bought to `canceled` with a note naming the refund. `DomainValidationError` keyed by `amount_cents` when the amount is zero, exceeds what is left unrefunded, or the payment is not succeeded.
- Provider calls: Stripe `refunds.create({payment_intent, amount})` (idempotency key `caldart-refund-{refund.pk}`); PayPal `POST /v2/payments/captures/{capture_id}/refund` with the amount (the capture id is read from the stored capture); mock succeeds immediately; manual records the refund without calling anything (the check was written by hand).
- **Dashboard refunds are recorded.** Stripe `charge.refunded` and PayPal `PAYMENT.CAPTURE.REFUNDED` webhooks create the `Refund` row (`requested_by` null, reason `other`, note "Issued in the provider's dashboard") when no row with that provider reference exists, so the ledger is right even when somebody refunds outside CalDART. No term is canceled by a webhook; the treasurer decides that on the payment's detail screen.
- `POST /admin/payments/{id}/refunds` is `IsFinance`. The response is the refund row plus the payment as it now stands.
- The default in the refund form: amount prefilled with what is left unrefunded; `cancel_term` prefilled true when the amount covers the dues, false otherwise.

### 5.6 Payments recorded by hand

`POST /admin/payments/record` (`IsFinance`) creates a `succeeded` payment with provider
`manual`, `wallet` from `method`, `received_on`, `note` (the check number goes here),
`recorded_by`, fee zero, and activates the term through the same `mark_succeeded` path,
which also emails the receipt. Body: `{user_id, plan (slug or null), contribution_cents,
method, reference, received_on, note}`; `reference` is stored as `provider_ref` (blank
allowed; the unique constraint already ignores blanks). A lifetime plan is allowed.

### 5.7 Reconciliation

- `PATCH /admin/payments/{id}` with `{reconciled_on}` (a date, or null to clear) and/or `{note}`; `reconciled_by` follows. Audit action `payment.reconcile`.
- `GET /admin/payments/reconciliation?from&to&provider&group=month|provider` answers one row per period (or per provider when `group=provider`): `count`, `gross_cents`, `fee_cents`, `net_cents`, `refunded_cents`, `net_after_refunds_cents`, `reconciled_count`, `unreconciled_count`. Succeeded, partially refunded and refunded payments count; refunds are dated by `refunded_at`. CSV and PDF exports of the same rows, filenames `caldart-reconciliation-<from>-<to>.{csv,pdf}`.
- The list filter `reconciled=yes|no` narrows to matched or unmatched payments.

### 5.8 Auto-renewal

**Mechanism.** A saved payment method charged off-session by CalDART's own scheduler —
not Stripe Subscriptions, not PayPal Subscriptions — so the plan, price, term and reminder
logic stay in one place. Lifetime plans cannot hold a mandate.

- **Stripe.** At a checkout with `auto_renew: true` the PaymentIntent is created with `setup_future_usage: "off_session"` and a `customer` (a Stripe Customer created for the user then, id kept on the pending mandate's `customer_ref`). On success `mark_succeeded` activates the mandate with the charge's `payment_method` (id, brand, last4, expiry from `payment_method_details.card`). Turning on from the portal without paying uses a SetupIntent (`POST /me/renewal/setup` → `{client_secret}`; the Payment Element renders in `setup` mode; `POST /me/renewal/confirm {setup_intent_id}` activates it). A charge is `payment_intents.create({amount, currency, customer, payment_method, off_session: true, confirm: true, metadata})` with the renewal's own `Payment` row created first, so the existing webhook handlers apply to it unchanged. `authentication_required` and `card_declined` are failures with the provider's reason kept in `error`.
- **PayPal.** The order at checkout carries `payment_source.paypal.attributes.vault = {store_in_vault: "ON_SUCCESS", usage_type: "MERCHANT"}`; the capture response's `payment_source.paypal.attributes.vault.id` is the `method_ref` and the payer email the label. Turning on from the portal uses `POST /v3/vault/setup-tokens` (`POST /me/renewal/setup` → `{setup_token}`; the buttons approve it) and `POST /v3/vault/payment-tokens` on confirm. A charge is an Orders v2 create with `payment_source: {paypal: {vault_id}}` followed by capture.
- **Mock.** Instant; the mandate reads "Test card ending 4242, expires 12/2030". A mandate whose `method_last4` is `0002` fails every charge with "Your card was declined" so the failure path can be demonstrated and tested; the seed uses it for the paused mandate.

**Schedule.** Constants in `apps/payments/renewals.py`: `CHARGE_LEAD_DAYS = 1` (charge
the day before the term's `ends_on`; the owner's decision, so that a member is never
charged for the coming year while a whole year of coverage still remains — a decline is
therefore retried after the term has run out, and the term a late charge buys starts on
the day the money arrives); `NOTICE_DAYS = 14` (the advance warning goes out fourteen days before
the charge date, stating the amount, the date and how to cancel); `RETRY_OFFSETS = (1, 3,
7)` (days after the failed attempt); `CARD_EXPIRY_WARNING_DAYS = 30`. After the third
retry fails the mandate becomes `paused`, the member is told it is off, and the ordinary
reminders resume for that membership.

**The scanner** `run_auto_renewals(*, today, dry_run, actor)` in
`apps/payments/renewals.py`, called by `manage.py run_auto_renewals [--today YYYY-MM-DD]
[--dry-run]`, `POST /system/renewals/run` and the systemd timer
`deploy/systemd/caldart-renewals.timer` at 06:30 (before the 07:00 reminder scan). In
order: (1) for every `active` mandate whose current coverage ends within `NOTICE_DAYS +
CHARGE_LEAD_DAYS` days and has no attempt for that term, create the `scheduled` attempt
and send `renewal_notice`; (2) warn once per mandate when the card expires before the
next charge (`renewal_card_expiring`); (3) charge every attempt whose `scheduled_on` is
today or past: create the `Payment`, call the provider, on success `mark_succeeded`
activates the next term (which starts the day after the current one ends, as
`activate_term` already does) and `renewal_charged` goes out with the receipt attached
instead of the plain receipt email; on failure record the error, send `renewal_failed`
naming the next try or that it was the last, and create the retry attempt or pause the
mandate. Every email is idempotent through the attempt's timestamps; a run twice in one
day sends nothing twice. The run returns a `RenewalRun` summary (`noticed`, `charged`,
`failed`, `paused`, `skipped`) and writes one `renewals.run` audit record.

**Reminders.** `reminders/services._skip_reason` gains `auto_renew`: a member with an
`active` or `pending`-with-attempts mandate is skipped for every reminder kind, because
the renewal emails cover that term. A `paused` or `canceled` mandate skips nothing.

**The member's controls.** `GET /me/renewal` (the mandate or `null`), `POST
/me/renewal/setup`, `POST /me/renewal/confirm`, `PATCH /me/renewal {contribution_cents}`,
`DELETE /me/renewal` (204; `renewal_canceled` email). `POST /payments/checkout` gains
`auto_renew` (default false; 400 keyed by `auto_renew` for a lifetime plan or the manual
provider). An administrator cancels with `DELETE /admin/renewals/{id}` (audit
`renewal.cancel`, the member is emailed).

**Imported members** whose CiviCRM record says auto-renew was on have no mandate here;
they re-authorize from the portal. `renewals.rst` says so.

### 5.9 Reports: chosen columns, CSV and PDF

- `apps/payments/reports.py` gains a column registry, the pattern `members/reports.py` uses: `PAYMENT_REPORT_COLUMNS: tuple[ReportColumn, ...]` where each column has `key`, `label`, `default: bool` and a value function. Keys: `paid_on`, `receipt_number`, `name`, `email`, `plan`, `kind`, `plan_amount`, `contribution`, `total`, `fee`, `net`, `refunded`, `provider`, `wallet`, `status`, `provider_ref`, `received_on`, `reconciled_on`, `note`, `membership_starts`, `membership_ends`. Defaults: everything except `receipt_number`, `received_on`, `note`, `membership_starts`, `membership_ends`.
- `GET /admin/payments/columns` answers `[{key, label, default}]`, so the screen's column chooser is data-driven.
- `GET /admin/payments/export.csv` and `export.pdf` take `?columns=a,b,c` (default columns when absent; 400 keyed by `columns` for an unknown key), honor every list filter **and** `?ordering=` (the payments export stops being the one that ignores it), and carry the date in the filename: `caldart-payments-<YYYY-MM-DD>.{csv,pdf}`. The PDF subtitle names the filters applied, through `filter_summary`.
- `GET /admin/payments/contributions?year=` — one row per member with a succeeded contribution that year: `user_id`, `name`, `email`, `count`, `contribution_cents`, `refunded_cents`, `net_contribution_cents`; CSV and PDF; the year-end acknowledgment list.
- Filters on the list, summary and exports: the existing five plus `plan` (slug), `kind`, `reconciled`, `member` (user id), `min_cents`, `max_cents`, `wallet`.
- Ordering fields gain `fee_cents`, `net_cents`, `reconciled_on`.

### 5.10 API surface

All under `/api/v1/`. "Finance" means `IsFinance` (`treasurer` or `account_admin`;
`system_admin` passes everything).

| Endpoint | Who | Package |
| --- | --- | --- |
| `POST /payments/checkout` (+ `auto_renew`) | authenticated | auto-renew-backend |
| `GET /me/payments` (fuller rows) | owner | fees-and-receipts |
| `GET /me/payments/{id}/receipt.pdf` | owner | fees-and-receipts |
| `GET /me/payments/statements` | owner | fees-and-receipts |
| `GET /me/payments/statements/{year}.pdf` | owner | fees-and-receipts |
| `GET /me/renewal`, `POST /me/renewal/setup`, `POST /me/renewal/confirm`, `PATCH /me/renewal`, `DELETE /me/renewal` | owner | auto-renew-backend |
| `GET /admin/payments` (+ filters), `GET /admin/payments/summary` (+ fee/net/refunds) | finance | treasurer-reports |
| `GET /admin/payments/columns`, `export.csv`, `export.pdf` | finance | treasurer-reports |
| `GET /admin/payments/reconciliation`, `reconciliation/export.{csv,pdf}` | finance | treasurer-reports |
| `GET /admin/payments/contributions`, `contributions/export.{csv,pdf}` | finance | treasurer-reports |
| `GET /admin/payments/ledger/{user_id}` | finance | treasurer-reports |
| `POST /admin/payments/record` | finance | treasurer-reports |
| `GET /admin/payments/{id}`, `PATCH /admin/payments/{id}` | finance | treasurer-reports |
| `POST /admin/payments/{id}/receipt` | finance | fees-and-receipts |
| `GET /admin/payments/{id}/receipt.pdf`, `GET /admin/payments/ledger/{user_id}/statements/{year}.pdf` | finance | fees-and-receipts |
| `POST /admin/payments/{id}/refunds` | finance | refunds |
| `GET /admin/renewals`, `GET /admin/renewals/{id}`, `DELETE /admin/renewals/{id}`, `GET /admin/renewals/attempts` | finance | auto-renew-backend |
| `POST /system/renewals/run` | `system_admin` | auto-renew-backend |
| `POST /payments/stripe/webhook` (+ `charge.refunded`, `charge.updated`) | signature | refunds, fees-and-receipts |
| `POST /payments/paypal/webhook` (+ `PAYMENT.CAPTURE.REFUNDED`) | signature | refunds |

`GET /admin/payments/{id}` is the full finance row: every `Payment` field of §5.2 plus
`user_email`, `kind`, `refunded_cents`, `refunds[]`, `membership` (`{id, starts_on,
ends_on, status}` or null), `renewal_attempt` (`{id, scheduled_on, outcome}` or null when
the payment was not an automatic charge), and `receipt_number`. The list row is the same
minus `refunds`, `raw` never.

The ledger, `GET /admin/payments/ledger/{user_id}`: `{user: {id, name, email, membership},
totals: {paid_cents, contribution_cents, fee_cents, refunded_cents}, payments: [finance
rows], mandate: <as GET /me/renewal> | null, statement_years: [int]}`.

The existing `payments/api/urls.py` becomes an includer of five modules the packages own
separately: `checkout_urls.py` (existing routes), `receipt_urls.py`, `refund_urls.py`,
`renewal_urls.py`, `report_urls.py`. The finance-model package creates the four new
modules with empty `urlpatterns`.

### 5.11 Emails

All in `backend/templates/emails/`, `.txt` and `.html`, sent through a new
`caldart/mail.py` (`send_templated(*, to, subject, template, context, attachments)` plus
`org_name()` / `contact_email()` moved out of `reminders/services.py`, which then imports
them). Subjects in the house voice, no exclamation marks, `{org}` prefix.

| Template | When |
| --- | --- |
| `receipt` | every succeeded payment (PDF attached) |
| `refund` | a refund succeeds; states amount, what it was for, and whether the membership term was canceled |
| `renewal_enabled` | a mandate becomes active; states the plan, the amount, the method and the next charge date |
| `renewal_notice` | `NOTICE_DAYS` before a charge; amount, date, method, "turn it off" link |
| `renewal_card_expiring` | the card on file expires before the next charge |
| `renewal_charged` | the charge succeeded; new expiry date; receipt attached |
| `renewal_failed` | a charge failed; the reason, when it will be tried again, or that it was the last try and reminders resume |
| `renewal_canceled` | the member or an administrator turned it off |

Every email links to `SITE_URL/portal/payments`.

### 5.12 Portal screens

**Member.** A new feature `frontend/src/portal/features/payments/` and route
`/payments`, nav entry "Payments" in the Membership group after "My aircraft":

- an **Automatic renewal** card: off → "Turn on" (opens the setup flow inline: plan is the annual plan, a contribution amount, provider tabs as at checkout; Stripe renders the Payment Element in setup mode, PayPal its buttons on the setup token, mock a button); on → the method label, the next charge date and amount, "Change contribution", "Turn off" with a confirm; paused → the last error and a "Turn on again" that runs the setup flow;
- a **Payments** table: date, for, amount, refunded (when any), status, a "Receipt" link (PDF);
- **Contribution statements**: one button per year from `GET /me/payments/statements`.

The checkout gains an "Renew automatically each year" checkbox (shown for a plan with a
duration, hidden for the manual provider), with the sentence "We will email you 14 days
before charging this card, and you can turn it off at any time from Payments." The done
step says a receipt has been emailed. The dashboard's "Recent payments" card links to
`/payments` and shows one line for the renewal state.

**Finance.** `/admin/payments` becomes an area with a tab bar (Overview · Payments ·
Renewals · Reconciliation · Contributions), each tab a route:

- `/admin/payments` **Overview**: tiles (gross, fees, net, refunds; this month, year to date, last 12 months) and the period table with fee, net and refunds columns;
- `/admin/payments/list` **Payments**: the filter bar (live search, debounced as the member list is; date range, provider, status, plan, kind, reconciled, amount range), the table with fee/net/refunded columns, a **Columns** chooser that drives both the table and the exports, **Export CSV** and **Export PDF**, **Record a payment**; a row opens the detail;
- `/admin/payments/:id` **Payment detail**: everything on the row, the refunds beneath it, the term it bought (linked to the member record for an account admin), **Refund** (a form: amount, reason, note, cancel the term), **Resend receipt**, **Download receipt**, **Fetch fee from provider** when the fee is unknown, the reconciled toggle and the note, and a link to the member's ledger;
- `/admin/payments/record`: the manual payment form with a live member search (the members list's search behavior);
- `/admin/payments/members/:userId` **Member ledger**: totals, the mandate (with cancel), the payment rows, statement downloads;
- `/admin/payments/renewals` **Renewals**: mandates (status filter, next charge, method, member) with cancel, and the recent attempts with outcomes;
- `/admin/payments/reconciliation`: the period/provider table with the export buttons and a date range;
- `/admin/payments/contributions`: the year's acknowledgment list with exports and a statement PDF link per member.

**Account administrator's member record.** The Payments tab reads the ledger endpoint and
shows the same rows and the mandate card.

**System page.** A Renewals panel beside the Reminders one: run (with dry run), the last
result.

### 5.13 Seed

`apps/payments/seed.py` (deterministic under the shared `rng`): fees on every seeded
payment (Stripe 2.9% + 30¢, PayPal 3.49% + 49¢); `receipt_sent_at` on every succeeded
payment; `reconciled_on` on every payment older than 60 days; about eight manual
payments (checks); six refunds (two full, with the term canceled; four partial
contribution refunds); a dozen mandates — ten active with next charges spread across
the coming year, one paused after three failed attempts (last4 `0002`), one canceled —
with the matching attempts and, for the active ones whose charge is within `NOTICE_DAYS`,
a `noticed_at`. `seed_facts` adds the treasurer, one member with an active mandate, one
member with a refunded payment, and the count of manual payments, for the specs.

### 5.14 Testing against the real sandboxes

Everything above must be exercisable end to end against Stripe test mode and the PayPal
sandbox, not only the mock provider. The `sandbox-testing` package delivers:

- `manage.py payments_sandbox_check`: with the configured keys, retrieves the Stripe balance and lists the account's enabled payment methods, fetches a PayPal token and reads the sandbox account's name, reports which webhook secret is set, and prints what each provider will and will not be able to do (fees, refunds, off-session charges, vault) — so a developer knows their `.env` works before opening a browser. `make sandbox-check` runs it.
- A section of `payments-setup.rst`, "Testing against the sandboxes", that walks every flow: keys and `stripe listen` with the full event list (`payment_intent.succeeded`, `payment_intent.payment_failed`, `charge.refunded`, `charge.updated`, `setup_intent.succeeded`); the Stripe test cards for each path (success, decline, authentication required, and the `4000 0000 0000 0341` card that attaches but fails off-session); a PayPal sandbox business and personal account, enabling Vault on the REST app, refunding from the sandbox dashboard; a full drill: pay with auto-renew on, `manage.py run_auto_renewals --today` advanced to the notice date and then the charge date, see the emails in Mailpit, refund from the portal, refund from the dashboard and watch the webhook file it, record a check, reconcile, export.
- `.env.example` and `configuration.rst` complete for every variable the new code reads.

### 5.15 Audit actions

`caldart/audit.py` gains `PAYMENT_RECORD`, `PAYMENT_REFUND`, `PAYMENT_RECONCILE`,
`PAYMENT_RECEIPT_RESEND`, `PAYMENT_NOTE`, `RENEWAL_ENABLE`, `RENEWAL_CANCEL`,
`RENEWALS_RUN`; `deployment.rst`'s audit table lists them with their fields.

### 5.16 Docs pages

New: `docs/developer/api-finance.rst` (reports, ledger, record, reconcile, detail),
`docs/developer/api-refunds.rst`, `docs/developer/api-renewals.rst`,
`docs/developer/renewals.rst` (the subsystem: mechanism, schedule, scanner, emails,
reminders interplay, operations). Changed: `api-payments.rst` (checkout's `auto_renew`,
receipts and statements, the webhook events, the role summary), `reports.rst` (the
payments report gets columns, PDF and ordering; reconciliation and contributions
reports), `reminders.rst` (the `auto_renew` skip), `data-model.rst`, `api-reference.rst`
(matrix), `deployment.rst` (audit actions, the renewals timer), `configuration.rst`,
`payments-setup.rst`, `architecture.rst` (routes, the finance area), `roadmap.rst` (the
"Auto-renewing subscriptions", "Receipts" and "Refunds" entries are removed; the
non-goals paragraph no longer lists subscriptions), `docs/user/payments.rst` (rewritten:
for members, for treasurers and account administrators), `member-guide.rst`,
`account-administrator-guide.rst`, `overview.rst`, `system-administrator-guide.rst`,
`getting-started.rst` (the treasurer account), `faq.rst` (receipts, refunds, renewal).

## 6. Failure handling and the final report

- **A failing gate.** Three fix attempts within scope; then the PR stays open as a draft with a comment saying what failed, and the orchestrator carries on with every package that does not depend on it.
- **A rebase conflict outside the package's files.** Same.
- **CI red on `main`.** No new package starts until a fix PR restores it.
- **The final report** lists every PR merged, every ask of #175 and #173 with the PR that settled it, and every decision taken that §5 did not cover.
- **Archive.** The closeout PR moves this plan to `plans/archive/`.

## 7. Work packages

### Wave 1

#### finance-model (Opus)

- **Refs:** #175, #173
- **Branch:** `feature/finance-model`; database `caldart_finance_model`
- **Owns:** `backend/apps/accounts/roles.py`, `backend/apps/accounts/permissions.py#is-finance`, `backend/apps/accounts/migrations/0002_seed_roles.py`, `backend/apps/accounts/seed.py#treasurer`, `backend/apps/payments/models.py`, `backend/apps/payments/migrations/0001_initial.py`, `backend/apps/payments/admin.py`, `backend/apps/payments/api/urls.py`, `backend/apps/payments/api/checkout_urls.py` (new), `backend/apps/payments/api/receipt_urls.py` (new), `backend/apps/payments/api/refund_urls.py` (new), `backend/apps/payments/api/renewal_urls.py` (new), `backend/apps/payments/api/report_urls.py` (new), `backend/apps/payments/api/views.py#finance-permission`, `backend/apps/sysadmin/management/commands/seed_facts.py#treasurer`, `backend/caldart/audit.py`, `backend/tests/factories.py#finance`, `backend/tests/conftest.py#treasurer-fixtures`, `backend/tests/test_finance_model.py` (new), `backend/tests/test_roles_permissions.py#treasurer`, `backend/tests/test_permission_matrix.py#treasurer`, `frontend/e2e/helpers.ts#treasurer`, `frontend/src/portal/api/types.ts#roles`, `docs/developer/data-model.rst`, `docs/developer/api-reference.rst#matrix`, `docs/developer/deployment.rst#audit`, `docs/user/user-administrator.rst#roles`, `docs/user/getting-started.rst#accounts`, `README.rst#accounts`.
- **Steps:**
  1. The treasurer role (§5.1): slug, description, group in the seed-roles migration, `IsFinance`, the demo account, `seed_facts`, the e2e helper's key, the frontend `RoleSlug` union.
  2. The models of §5.2 with docstrings a black-box test can be written from; `payments/0001_initial.py` regenerated; Django admin registrations for `Refund`, `RenewalMandate` and `RenewalAttempt`; factories `RefundFactory`, `RenewalMandateFactory`, `RenewalAttemptFactory` and fixtures `treasurer`, `treasurer_client`, `refund_factory`, `mandate_factory`.
  3. Every `/admin/payments*` view that exists today moves from `IsAccountAdmin` to `IsFinance`, and the urls split of §5.10 (the four new modules hold empty `urlpatterns`; `urls.py` includes all five).
  4. The audit action names (§5.15) and the `deployment.rst` table rows.
  5. The permission-matrix rows for every endpoint in §5.10, with the treasurer column, and the data-model page.
- **Verify:** `make reset && make seed` from empty; `treasurer_client` gets 200 from `GET /admin/payments` and 403 from `GET /admin/members`; the matrix test covers the new column; `make check` clean.

#### shared-helpers (Opus)

- **Refs:** #175
- **Branch:** `feature/finance-shared-helpers`; database `caldart_shared_helpers`
- **Owns:** `backend/caldart/reports.py#columns-and-pdf-portrait`, `backend/caldart/receipts.py` (new), `backend/caldart/mail.py` (new), `backend/caldart/org.py` (new), `backend/apps/reminders/services.py#mail-helpers`, `backend/tests/test_reports.py#columns`, `backend/tests/test_receipts_pdf.py` (new), `backend/tests/test_mail.py` (new), `docs/developer/reports.rst#helpers`, `docs/developer/reminders.rst#mail-helpers`, `docs/developer/architecture.rst#caldart-modules`.
- **Steps:**
  1. `caldart/reports.py`: a `ReportColumn` dataclass (`key`, `label`, `default`, `value`) and `select_columns(columns, requested) -> list[ReportColumn]` raising `ValueError` naming the first unknown key; `pdf_table_response` and `build_pdf_table` learn `landscape=False` properly (portrait letter) and per-column relative widths (`widths: Sequence[float] | None`).
  2. `caldart/receipts.py`: `build_receipt_pdf(buffer, receipt: ReceiptData)` and `build_statement_pdf(buffer, statement: StatementData)` — typed dataclasses in, PDF out, house palette, portrait letter, the wording of §5.4. Pure functions with no model imports, so `payments` can call them without a cycle.
  3. `caldart/org.py`: `org_details() -> OrgDetails` (name, contact email, mailing address, EIN, site URL) with the inline `cms` import; `caldart/mail.py`: `send_templated` and the two helpers; `reminders/services.py` imports them instead of defining its own (`build_email` keeps its signature).
  4. Tests: the PDF decoder in `conftest.py` proves the receipt names the payer, the amount, the receipt number and the 501(c)(3) sentence, and the statement lists each contribution and the total.
- **Verify:** `make test docs`; the reminder emails' golden files are byte-identical.

### Wave 2

#### fees-and-receipts (Opus)

- **Refs:** #175
- **After:** finance-model, shared-helpers
- **Branch:** `feature/fees-and-receipts`; database `caldart_fees_receipts`
- **Owns:** `backend/apps/payments/services.py#fees-and-receipt`, `backend/apps/payments/receipts.py` (new), `backend/apps/payments/providers/stripe.py#fees`, `backend/apps/payments/providers/paypal.py#fees`, `backend/apps/payments/providers/mock.py#fees`, `backend/apps/payments/api/receipt_views.py` (new), `backend/apps/payments/api/receipt_urls.py`, `backend/apps/payments/api/serializers.py#receipts`, `backend/apps/members/api/profile_serializers.py#payment-summary`, `backend/apps/members/api/profile_views.py#my-payments`, `backend/templates/emails/receipt.{txt,html}` (new), `backend/apps/payments/seed.py#fees-receipts`, `backend/tests/test_payments_fees.py` (new), `backend/tests/test_receipts.py` (new), `backend/tests/test_payments_stripe.py#fees`, `backend/tests/test_payments_paypal.py#fees`, `backend/tests/golden/receipt*.txt` (new), `frontend/src/portal/api/types.ts#payments-member`, `docs/developer/api-payments.rst`, `docs/user/payments.rst#receipts`, `docs/user/faq.rst#receipts`.
- **Steps:** §5.3 and §5.4. `mark_succeeded(fee_cents=, net_cents=)`; the balance-transaction expand and the `charge.updated` handler; the PayPal breakdown; the mock fee; `backfill_fees`; the receipt email with the attached PDF from `mark_succeeded` (a mail failure is logged, never raised); the member and finance receipt and statement endpoints; the fuller `GET /me/payments`; Stripe's `receipt_email` dropped. The seed sets fees and `receipt_sent_at`.
- **Verify:** `make test`; a mock checkout in `make run` lands a receipt with a PDF in Mailpit; `GET /me/payments/statements/2026.pdf` for the seeded member decodes to the year's contributions.

#### refunds (Opus)

- **Refs:** #175
- **After:** finance-model, shared-helpers
- **Branch:** `feature/refunds`; database `caldart_refunds`
- **Owns:** `backend/apps/payments/refunds.py` (new), `backend/apps/payments/providers/stripe.py#refunds`, `backend/apps/payments/providers/paypal.py#refunds`, `backend/apps/payments/providers/mock.py#refunds`, `backend/apps/payments/providers/base.py#refund`, `backend/apps/payments/api/refund_views.py` (new), `backend/apps/payments/api/refund_urls.py`, `backend/apps/payments/api/serializers.py#refunds`, `backend/apps/members/services.py#cancel-term`, `backend/templates/emails/refund.{txt,html}` (new), `backend/apps/payments/seed.py#refunds`, `backend/tests/test_refunds.py` (new), `backend/tests/test_payments_stripe.py#refund-webhook`, `backend/tests/test_payments_paypal.py#refund-webhook`, `frontend/src/portal/api/types.ts#refunds`, `docs/developer/api-refunds.rst` (new), `docs/developer/index.rst#api-refunds`, `docs/user/payments.rst#refunds`, `docs/user/faq.rst#refunds`.
- **Steps:** §5.5. `Provider.refund(payment, refund) -> dict` on the base class with the three implementations; `issue_refund` with its validation, the status transitions, the term cancellation through a new `members.services.cancel_term(term, *, actor, note)`, the audit record and the email; the two webhook events; the endpoint; the seed's six refunds.
- **Verify:** `make test`; refunding more than remains is a 400 keyed by `amount_cents`; a signed `charge.refunded` for a payment with no refund row creates one and a second delivery creates none.

#### auto-renew-backend (Opus)

- **Refs:** #173
- **After:** finance-model, shared-helpers
- **Branch:** `feature/auto-renew-backend`; database `caldart_auto_renew`
- **Owns:** `backend/apps/payments/renewals.py` (new), `backend/apps/payments/services.py#mandates`, `backend/apps/payments/providers/base.py#mandates`, `backend/apps/payments/providers/stripe.py#mandates`, `backend/apps/payments/providers/paypal.py#mandates`, `backend/apps/payments/providers/mock.py#mandates`, `backend/apps/payments/api/renewal_views.py` (new), `backend/apps/payments/api/renewal_urls.py`, `backend/apps/payments/api/serializers.py#renewals`, `backend/apps/payments/api/views.py#checkout-auto-renew`, `backend/apps/payments/api/serializers.py#checkout-auto-renew`, `backend/apps/payments/management/commands/run_auto_renewals.py` (new), `backend/apps/sysadmin/api/views.py#renewals-run`, `backend/apps/sysadmin/api/urls.py#renewals-run`, `backend/apps/reminders/services.py#auto-renew-skip`, `backend/templates/emails/renewal_*.{txt,html}` (new), `deploy/systemd/caldart-renewals.service` (new), `deploy/systemd/caldart-renewals.timer` (new), `backend/apps/payments/seed.py#mandates`, `backend/apps/sysadmin/management/commands/seed_facts.py#mandate`, `backend/tests/test_renewals.py` (new), `backend/tests/test_renewals_api.py` (new), `backend/tests/test_renewals_providers.py` (new), `backend/tests/test_reminders.py#auto-renew-skip`, `backend/tests/golden/renewal_*.txt` (new), `frontend/src/portal/api/types.ts#renewals`, `docs/developer/renewals.rst` (new), `docs/developer/api-renewals.rst` (new), `docs/developer/index.rst#renewals`, `docs/developer/api-payments.rst#checkout-auto-renew`, `docs/developer/api-system.rst#renewals-run`, `docs/developer/reminders.rst#auto-renew`, `docs/developer/deployment.rst#renewals-timer`, `docs/user/payments.rst#auto-renewal`, `docs/user/system-administrator-guide.rst#renewals`, `docs/user/faq.rst#auto-renewal`.
- **Steps:** §5.8 and its emails (§5.11). `Provider.start_mandate`, `confirm_mandate`, `charge_mandate` on the base class and the three implementations (Stripe: customer, `setup_future_usage`, SetupIntent, off-session PaymentIntent; PayPal: vault attribute on the order, setup tokens, payment tokens, vault-sourced order plus capture; mock). The scanner with its constants, the attempt life cycle, the retry ladder, the pause, the emails keyed on attempt timestamps, the `RenewalRun` summary and audit record; the command with `--today` and `--dry-run`; the system endpoint; the reminders skip; the systemd pair; the seed's mandates and attempts. Tests drive the scanner through a frozen clock across a whole cycle: notice, charge, decline, three retries, pause, reminders resuming.
- **Verify:** `make test`; `manage.py run_auto_renewals --dry-run` on the seed reports the expected counts; `send_renewal_reminders --dry-run` skips every seeded mandate holder with `auto_renew`.

#### treasurer-reports (Opus)

- **Refs:** #175
- **After:** finance-model, shared-helpers
- **Branch:** `feature/treasurer-reports`; database `caldart_treasurer_reports`
- **Owns:** `backend/apps/payments/reports.py`, `backend/apps/payments/reconciliation.py` (new), `backend/apps/payments/manual.py` (new), `backend/apps/payments/api/views.py#reports`, `backend/apps/payments/api/report_views.py` (new), `backend/apps/payments/api/report_urls.py`, `backend/apps/payments/api/serializers.py#reports`, `backend/apps/payments/seed.py#manual-and-reconciled`, `backend/apps/sysadmin/management/commands/seed_facts.py#manual-count`, `backend/tests/test_payments_reports.py`, `backend/tests/test_payment_report_query.py`, `backend/tests/test_finance_api.py` (new), `backend/tests/test_reconciliation.py` (new), `backend/tests/test_manual_payments.py` (new), `backend/tests/golden/payments-export*.csv`, `frontend/src/portal/api/types.ts#finance`, `docs/developer/api-finance.rst` (new), `docs/developer/index.rst#api-finance`, `docs/developer/api-payments.rst#reports-moved`, `docs/developer/reports.rst#payments`, `docs/user/payments.rst#treasurer`, `docs/user/account-administrator-guide.rst#payments`.
- **Steps:** §5.6, §5.7, §5.9 and the finance rows of §5.10. The column registry and the two exports with `columns` and `ordering`; the extended filters; the summary's fee, net and refund sums; the reconciliation rows and exports; the contributions list and exports; the ledger; the detail and patch endpoints with their audit records; `record_manual_payment` and its endpoint; the seed's checks and reconciled dates. The report sections of `api-payments.rst` move to `api-finance.rst` (a `:doc:` pointer stays behind).
- **Verify:** `make test`; the CSV golden files; a PDF export decodes to its subtitle and first row; `GET /admin/payments/reconciliation?group=provider` on the seed sums to the same gross as the summary for the same range.

### Wave 3

#### portal-payments-page (Opus)

- **Refs:** #175, #173
- **After:** fees-and-receipts, refunds, auto-renew-backend, treasurer-reports
- **Branch:** `feature/portal-payments-page`; database `caldart_portal_payments`; e2e port 8141
- **Owns:** `frontend/src/portal/features/payments/**` (new), `frontend/src/portal/routes/payments.tsx` (new), `frontend/src/portal/routes/index.tsx#payments`, `frontend/src/portal/routes/index.test.tsx#payments`, `frontend/src/portal/nav.ts#payments`, `frontend/src/portal/nav.test.ts#payments`, `frontend/src/portal/features/checkout/**#auto-renew`, `frontend/src/portal/features/join/DoneStep.tsx#receipt`, `frontend/src/portal/features/join/RenewPage.tsx#auto-renew`, `frontend/src/portal/features/dashboard/**#payments-link`, `frontend/src/portal/features/profile/api.ts#my-payments`, `frontend/src/test/handlers.ts#payments`, `frontend/src/test/fixtures/payments.ts` (new), `frontend/e2e/member-self-service.spec.ts#payments`, `frontend/e2e/auto-renew.spec.ts` (new), `docs/user/payments.rst#member-screens`, `docs/user/member-guide.rst#payments`, `docs/developer/architecture.rst#routes-payments`.
- **Steps:** the member half of §5.12: the payments page with its three cards and the setup flow (Stripe Payment Element in setup mode through the existing `StripePanel` patterns, PayPal setup token through the existing buttons, mock), the checkout checkbox, the done-step sentence, the dashboard link. Component tests through msw for every state (off, pending setup, active, paused, canceled); the e2e spec pays with the mock provider with auto-renew on, sees the card on Payments, downloads a receipt (response is a PDF), turns renewal off and sees it gone.
- **Verify:** `make test e2e`; `make lint`.

#### finance-list-and-detail (Opus)

- **Refs:** #175
- **After:** fees-and-receipts, refunds, auto-renew-backend, treasurer-reports
- **Branch:** `feature/finance-list-and-detail`; database `caldart_finance_list`; e2e port 8142
- **Owns:** `frontend/src/portal/features/admin-payments/AdminPaymentsPage.tsx`, `frontend/src/portal/features/admin-payments/PaymentsListPage.tsx` (new), `frontend/src/portal/features/admin-payments/PaymentDetailPage.tsx` (new), `frontend/src/portal/features/admin-payments/RefundForm.tsx` (new), `frontend/src/portal/features/admin-payments/RecordPaymentPage.tsx` (new), `frontend/src/portal/features/admin-payments/MemberLedgerPage.tsx` (new), `frontend/src/portal/features/admin-payments/ColumnChooser.tsx` (new), `frontend/src/portal/features/admin-payments/FinanceTabs.tsx` (new), `frontend/src/portal/features/admin-payments/FilterBar.tsx`, `frontend/src/portal/features/admin-payments/SummaryTiles.tsx`, `frontend/src/portal/features/admin-payments/PeriodTable.tsx`, `frontend/src/portal/features/admin-payments/api.ts`, `frontend/src/portal/features/admin-payments/labels.ts`, `frontend/src/portal/features/admin-payments/*.test.tsx#list-detail`, `frontend/src/portal/features/admin-payments/admin-payments.css`, `frontend/src/portal/features/admin-members/MemberPaymentsTab.tsx`, `frontend/src/portal/features/admin-members/MemberDetailPage.test.tsx#payments-tab`, `frontend/src/portal/routes/admin-payments.tsx`, `frontend/src/portal/routes/index.test.tsx#finance`, `frontend/src/portal/nav.ts#finance`, `frontend/src/portal/nav.test.ts#finance`, `frontend/src/test/handlers.ts#finance`, `frontend/src/test/fixtures/finance.ts` (new), `frontend/e2e/payment-reports.spec.ts`, `frontend/e2e/finance.spec.ts` (new), `docs/user/payments.rst#finance-screens`, `docs/user/account-administrator-guide.rst#payments-tab`, `docs/developer/architecture.rst#routes-finance`.
- **Steps:** the Overview, Payments, detail, record and ledger screens of §5.12, the tab bar, the treasurer-visible nav entry, and the member record's Payments tab on the ledger endpoint. The e2e spec signs in as the treasurer, filters the list, chooses columns, downloads a CSV and a PDF, opens a payment, refunds part of it (mock), sees the status change, records a check for a member and finds it in the list.
- **Verify:** `make test e2e`; `make lint`; a `dart_leader` reaches none of the finance routes.

#### finance-reports-and-renewals (Opus)

- **Refs:** #175, #173
- **After:** fees-and-receipts, refunds, auto-renew-backend, treasurer-reports
- **Branch:** `feature/finance-reports-and-renewals`; database `caldart_finance_reports`; e2e port 8143
- **Owns:** `frontend/src/portal/features/admin-payments/ReconciliationPage.tsx` (new), `frontend/src/portal/features/admin-payments/ContributionsPage.tsx` (new), `frontend/src/portal/features/admin-payments/RenewalsPage.tsx` (new), `frontend/src/portal/features/admin-payments/reports-api.ts` (new), `frontend/src/portal/features/admin-payments/*.test.tsx#reports-renewals`, `frontend/src/portal/features/system/RenewalsPanel.tsx` (new), `frontend/src/portal/features/system/RenewalsPanel.test.tsx` (new), `frontend/src/portal/features/system/SystemPage.tsx#renewals`, `frontend/src/portal/features/system/api.ts#renewals`, `frontend/src/portal/routes/admin-payments.tsx#reports-renewals`, `frontend/src/test/handlers.ts#reports-renewals`, `frontend/e2e/finance-reports.spec.ts` (new), `docs/user/payments.rst#reports-screens`, `docs/user/system-administrator-guide.rst#renewals-panel`.
- **Steps:** the Renewals, Reconciliation and Contributions tabs of §5.12 and the system page's Renewals panel. This package's routes are added to `routes/admin-payments.tsx` under a `#reports-renewals` marker comment the list-and-detail package leaves in place. The e2e spec signs in as the treasurer, reads the reconciliation for the seeded months, exports it, opens Renewals, cancels the seeded paused mandate, then as the system admin runs a dry renewal scan and reads the counts.
- **Verify:** `make test e2e`; `make lint`.

#### sandbox-testing (Sonnet)

- **Refs:** #175, #173
- **After:** fees-and-receipts, refunds, auto-renew-backend
- **Branch:** `feature/sandbox-testing`; database `caldart_sandbox_testing`
- **Owns:** `backend/apps/payments/management/commands/payments_sandbox_check.py` (new), `backend/tests/test_sandbox_check.py` (new), `Makefile#sandbox-check`, `.env.example`, `docs/developer/payments-setup.rst`, `docs/developer/configuration.rst#payments`, `docs/developer/setup.rst#sandbox`.
- **Steps:** §5.14. The command's provider calls are mocked in tests (`respx` for PayPal, the fake Stripe client the Stripe tests use); the docs section is written against the real flows the wave-2 packages built, naming every endpoint, command and email by its real name.
- **Verify:** `make lint test docs`; `make sandbox-check` with blank keys prints what is missing and exits 1; with the orchestrator's sandbox keys (if any are configured on this machine) exits 0.

### Wave 4

#### closeout (Sonnet)

- **Closes:** #175, #173
- **After:** portal-payments-page, finance-list-and-detail, finance-reports-and-renewals, sandbox-testing
- **Branch:** `chore/payments-closeout`; database `caldart_payments_closeout`; e2e port 8144
- **Owns:** `docs/developer/roadmap.rst`, `docs/user/overview.rst#payments`, `docs/user/payments.rst#consistency`, `docs/**#residue`, `frontend/src/**#residue`, `backend/**#residue`, `plans/2026-09-24-payments-and-auto-renewal.md` (moves to `plans/archive/`).
- **Steps:** remove the roadmap's receipts, refunds and subscriptions entries and the non-goal; read `docs/user/payments.rst` top to bottom for a single voice and current facts; re-run every ask of #175 and #173 item by item against `main` and fix small residue in scope; the PR body lists every ask with the PR that settled it; move the plan to the archive.
- **Verify:** `make lint test check docs audit e2e` green.

## 8. Manifest

```json
[
  {"wave": 1, "package": "finance-model", "model": "opus", "branch": "feature/finance-model", "database": "caldart_finance_model", "e2e_port": null, "closes": [], "refs": [175, 173], "after": []},
  {"wave": 1, "package": "shared-helpers", "model": "opus", "branch": "feature/finance-shared-helpers", "database": "caldart_shared_helpers", "e2e_port": null, "closes": [], "refs": [175], "after": []},
  {"wave": 2, "package": "fees-and-receipts", "model": "opus", "branch": "feature/fees-and-receipts", "database": "caldart_fees_receipts", "e2e_port": null, "closes": [], "refs": [175], "after": ["finance-model", "shared-helpers"]},
  {"wave": 2, "package": "refunds", "model": "opus", "branch": "feature/refunds", "database": "caldart_refunds", "e2e_port": null, "closes": [], "refs": [175], "after": ["finance-model", "shared-helpers"]},
  {"wave": 2, "package": "auto-renew-backend", "model": "opus", "branch": "feature/auto-renew-backend", "database": "caldart_auto_renew", "e2e_port": null, "closes": [], "refs": [173], "after": ["finance-model", "shared-helpers"]},
  {"wave": 2, "package": "treasurer-reports", "model": "opus", "branch": "feature/treasurer-reports", "database": "caldart_treasurer_reports", "e2e_port": null, "closes": [], "refs": [175], "after": ["finance-model", "shared-helpers"]},
  {"wave": 3, "package": "portal-payments-page", "model": "opus", "branch": "feature/portal-payments-page", "database": "caldart_portal_payments", "e2e_port": 8141, "closes": [], "refs": [175, 173], "after": ["fees-and-receipts", "refunds", "auto-renew-backend", "treasurer-reports"]},
  {"wave": 3, "package": "finance-list-and-detail", "model": "opus", "branch": "feature/finance-list-and-detail", "database": "caldart_finance_list", "e2e_port": 8142, "closes": [], "refs": [175], "after": ["fees-and-receipts", "refunds", "auto-renew-backend", "treasurer-reports"]},
  {"wave": 3, "package": "finance-reports-and-renewals", "model": "opus", "branch": "feature/finance-reports-and-renewals", "database": "caldart_finance_reports", "e2e_port": 8143, "closes": [], "refs": [175, 173], "after": ["fees-and-receipts", "refunds", "auto-renew-backend", "treasurer-reports"]},
  {"wave": 3, "package": "sandbox-testing", "model": "sonnet", "branch": "feature/sandbox-testing", "database": "caldart_sandbox_testing", "e2e_port": null, "closes": [], "refs": [175, 173], "after": ["fees-and-receipts", "refunds", "auto-renew-backend"]},
  {"wave": 4, "package": "closeout", "model": "sonnet", "branch": "chore/payments-closeout", "database": "caldart_payments_closeout", "e2e_port": 8144, "closes": [175, 173], "refs": [], "after": ["portal-payments-page", "finance-list-and-detail", "finance-reports-and-renewals", "sandbox-testing"]}
]
```
