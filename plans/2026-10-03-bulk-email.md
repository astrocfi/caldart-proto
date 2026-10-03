# Bulk email: types, batches, background sending, and everything around them

The twenty-two open bulk email issues: #402, #408, and #416 through #435. This plan is
the specification every package builds from. Where it and an issue differ, this plan
wins; where it is silent, the issue wins; where both are silent, the worker decides and
says so in the PR.

Owner decisions (2026-10-03):

- Email types, and whether each allows opt-out, are configurable by a system
  administrator on an **Email types** screen. The seed creates **Operational**,
  **Fundraising**, and **Mission**, all opt-out-able.
- A new account starts opted in to every type.
- An account administrator sees and changes a member's opt-outs on the member record;
  every change is audited.
- No fundraising role. CalDART management sends all three seeded types. A DART leader
  sends Operational and Mission to their own DART. A system administrator can change
  which roles send each type.
- A DART leader's DART is the DART on their own member profile.
- Every bulk email screen lives in a **Bulk Email** group of the portal sidebar, between
  Operations and Administration.
- The background sender is a `send_bulk_emails` management command started every
  minute by a systemd timer, like the other scheduled jobs.
- The Mail delivery (DNS) check is visible to CalDART management and system
  administrators.
- Rejected, do not build: second-person approval, SMS, open or click tracking, a "show
  to everyone" archive option, members seeing their transactional mail.
- Store each recipient's field values at send time, so the archive, View in browser,
  and the delivery report show every copy exactly as sent.

## 0. How the work runs

### Packages, waves, and merge order

| Wave | Package | Branch | Issues | Model |
| --- | --- | --- | --- | --- |
| 1 | P1 `bulk-core` | `feature/bulk-core` | #435, #419, #408, #422, #423, #424, #425 | Opus |
| 1 | P2 `email-types` | `feature/email-types` | #402, #420 | Opus |
| 1 | P3 `mail-dns` | `feature/mail-dns` | #421 | Sonnet |
| 1 | P4 `rich-text` | `feature/rich-text` | #416, #418 | Opus |
| 2 | P5 `send-checks` | `feature/send-checks` | #417, #426, #430 | Opus |
| 2 | P6 `reuse` | `feature/reuse` | #427, #428, #429 | Opus |
| 2 | P7 `delivery` | `feature/delivery` | #433, #434 | Opus |
| 2 | P8 `leaders` | `feature/leaders` | #432 | Opus |
| 3 | P9 `callouts` | `feature/callouts` | #431 | Opus |
| 3 | P10 `closeout` | `feature/bulk-closeout` | docs sweep, residue | Sonnet |

Wave 1 runs four branches in parallel. P2, P3, and P4 build their **standalone** parts
first (nothing under `apps/bulk_email/` or `features/bulk-email/`), open their PR, and
then wait. P1 merges first. Each of the others then rebases on `main`, does its
**integration** step (marked below), reruns every gate, and pushes; its PR gets a fresh
CI run before it merges. Integration merge order: P3, P4, P2.

Wave 2 starts when wave 1 is fully merged, four branches in parallel; merge order P8,
P5, P7, P6, each rebased on the one before. Wave 3 is P9, then P10.

### Every package

- Branch from a fresh `origin/main` into a worktree `.claude/worktrees/<package>`, with
  its own database `DATABASE_URL=postgres://caldart:caldart@localhost:5432/caldart_<slug>`
  and its own `E2E_PORT` and `E2E_DB` (the orchestrator assigns them).
- Read the docs pages that cover what you change before you write code. The docs are
  the specification; fix the docs or the code in the same PR when they disagree.
- Tests first. Backend tests go in `backend/tests/test_<package-topic>.py`, new files
  per package (listed under each package), never in a file another package owns.
  Frontend tests sit beside what they test. Every endpoint gets its role matrix through
  `role_matrix`. Every screen gets vitest coverage; every flow the issue names gets an
  e2e spec.
- Prototype rules: no backwards compatibility, no shims, no fix-up migrations. Edit the
  model and regenerate the app's migration in place when yours is the first package to
  touch that app in this plan; add a new migration when a merged package already
  regenerated it.
- `make lint`, `make test`, `make check`, `make docs`, `make audit`, `make e2e`, and
  `make e2e E2E_URL_PREFIX=/caldart` must all be green before the PR opens, and again
  after every rebase.
- Docstrings on everything, wrapped at 90; Oxford commas; no time-anchored words in the
  docs; MM/DD/YYYY dates through `DateText.tsx` and `caldart/dates.py`; one-line table
  rows; dots not badges; every trashcan confirms.
- The PR body says what, why, and how it was tested, and ends with `Closes #N` for each
  issue it finishes. Commits end with the two trailer lines from `CLAUDE.md`.
- Packages that touch the backend, a shared component, CSS, or an e2e spec get an
  adversarial review; a fix pass runs only on blocking findings. P10 gets no reviewer.

### Shared files

These are edited additively, and every package that touches one says so in its PR:

- `frontend/src/portal/nav.ts`: P1 adds `'Bulk Email'` to `NavItem['group']` and to
  `NAV_GROUPS` between `'Operations'` and `'Administration'`, and removes the
  Administration entry. P3 adds the same group line if P1 has not merged yet (identical
  text, so the rebase is trivial). Every package adds its own entries in the order of
  the table in §3.
- `frontend/src/portal/help.ts`: each package maps its routes to its guide pages.
- `frontend/src/portal/api/types.ts`: each package adds its own interfaces.
- `frontend/src/portal/routes/bulk-email.tsx`: P1 rewrites it; later packages add
  routes. Member-facing routes (`/messages`, `/email-preferences`) go in
  `routes/membership.tsx`.
- `backend/caldart/mail.py`: P1 adds `headers: Mapping[str, str] | None = None` and
  `reply_to: str = ""` keyword parameters to `send_templated` (merged into the message's
  headers and `reply_to`). Nobody else edits this file.
- `backend/caldart/settings/base.py` and `.env.example`: each package adds its settings
  (listed under the package) with a comment, and documents them in
  `docs/developer/configuration.rst`.
- `docs/developer/api-reference.rst`: the permission matrix gains every endpoint.
- `docs/developer/data-model.rst`: each package documents its models, the diagram
  (both the Graphviz and the ASCII form), the FK table, and any choices section.
- `docs/user/index.rst`, `docs/user/overview.rst`, `docs/user/roles.rst`: P1 adds the
  Bulk Email group and the `docs/user/bulk-email/` directory; later packages add pages.

### Module layout

P1 turns `apps/bulk_email/` into this shape, and later packages add files rather than
growing one:

```
apps/bulk_email/
  models.py            BulkEmail, BatchAdd, BulkEmailRecipient, the choices
  batch.py             adding filter sets, skip reasons, the batch list and its CSV
  drafts.py            create or reuse a draft, edit rules, queue, cancel, stop, resume
  job.py               the sender: claim, freeze, paced send loop, backoff, progress
  render.py            render_copy(): subject, text, html, headers for one recipient
  fields.py            P4: the field catalog, substitution, validation, values_for()
  richtext.py          P4: sanitize(), html_to_text()
  images.py            P4: image upload, scaling, storage
  checks.py            P5: pre-send checks, link check with SSRF guard
  tests_send.py        P5: the test copy
  templates.py         P6: saved templates
  groups.py            P6: saved recipient groups
  delivery.py          P7: bounce linkage, retry, a recipient's copy
  archive.py           P7: the member-facing archive
  callouts.py          P9
  api/urls.py
  api/drafts.py        P1: draft endpoints       api/batch.py    P1: batch endpoints
  api/history.py       P1: sent list and detail  api/serializers.py
  api/<package>.py     later packages add their own view modules
  management/commands/send_bulk_emails.py
```

```
frontend/src/portal/features/bulk-email/
  api.ts  status.ts  bulk-email.css
  ComposePage.tsx      loads one draft, owns the autosave, lays out the three cards
  RecipientsCard.tsx   filters, Add to batch, the batch table, Download, Clear
  MessageCard.tsx      type (P2), subject, Reply-To (P5), the editor (P4)
  SendCard.tsx         checks (P5), preview (P4), Send/Schedule, confirm, countdown, progress
  DraftsPage.tsx  SentPage.tsx  SentDetailPage.tsx
  <later packages add their own files here>
frontend/src/portal/features/email-types/      P2 (system administrator screen)
frontend/src/portal/features/email-preferences/ P2 (member screen)
frontend/src/portal/features/mail-delivery/    P3
frontend/src/portal/features/messages/         P7
frontend/src/portal/features/callouts/         P9
frontend/src/portal/components/RichTextEditor.tsx  P4
```

## 1. The data model after this plan

### `mail.EmailType` and `mail.EmailOptOut` (P2)

```
EmailType       name (unique, 60), slug (unique, from the name), description (text),
                allow_opt_out (bool, default true), sender_roles (JSON list of role
                slugs), position (int); ordering by position then name
EmailOptOut     user FK CASCADE, email_type FK CASCADE, source (profile | unsubscribe |
                admin), created_at; unique (user, email_type)
```

A type in use by a bulk email cannot be deleted (`PROTECT`); the screen says so.

### `bulk_email.BulkEmail` (P1, extended by later packages)

```
subject (200)            body (text; HTML after P4)
status                   draft | queued | sending | sent | stopped
sender FK SET_NULL       the owner of the draft and the sender of the send
email_type FK PROTECT    P2; null while a draft, required to send
reply_to (254, blank)    P5
dart FK SET_NULL         P8; the DART a leader's send is limited to; null for management
is_callout (bool)        P9; a one-to-one Callout row carries the rest
hidden_from_archive      P7 (bool)
start_at                 when the send begins: now + undo window, or the scheduled time
scheduled (bool)         true when the sender chose the time, for the labels
started_at, sent_at, stopped_at, stopped_by FK SET_NULL
stop_requested (bool)    the job reads it between copies
sent_count, failed_count, skipped_count
confirm_count            the count the sender confirmed (null below the threshold)
```

### `bulk_email.BatchAdd` (P1)

One press of **Add to batch**: `bulk_email FK CASCADE`, `filters` (JSON, the given
filters), `group FK SET_NULL` (P6, null for a filter add), `added_count`,
`already_count`, `created_at`. The compose screen labels each add by its filters
("Kind: Members, DART: Marin") or by its group's name.

### `bulk_email.BulkEmailRecipient` (P1, extended)

```
bulk_email FK CASCADE    user FK SET_NULL
name (301), email (254), kind (member | friend), dart_name (60)   snapshots at add time
added_by FK BatchAdd SET_NULL   null for a copy a retry or a callout reminder made
round (small int)        0 for the original copies, n for the n-th reminder (P9)
status                   batched | pending | sent | failed | skipped | stopped | bounced
reason (200)             why skipped, failed, stopped, or bounced; blank otherwise
values (JSON)            P4: the field values filled into this copy, token to value
message_id (255)         the Message-ID the copy went out with, blank until sent
tried_at                 when the copy was last tried
```

`batched` is a row of a draft: its skip reason is computed live and not stored. At the
moment the job starts a send it freezes the batch: each `batched` row becomes
`skipped` with its reason or `pending`. `bounced` is set by P7 from a later bounce.

### Later models

`bulk_email.BulkEmailImage` (P4), `bulk_email.EmailTemplate` and
`bulk_email.RecipientGroup` with `RecipientGroupMember` and `RecipientGroupFilter`
(P6), `bulk_email.BulkEmailRetry` (P7), `bulk_email.Callout` and `CalloutAnswer` (P9).
Each is specified under its package.

## 2. The send: states and the job (P1)

```
draft --Send--> queued --(start_at reached, job claims)--> sending --> sent
  ^               |                                          |
  +---Cancel------+                                          +--Stop--> stopped --Send the rest--> queued
```

- **Send** (`POST /bulk-email/{id}/send`) checks: a type is chosen (after P2), the
  subject and body are not blank, the batch has at least one person who can receive a
  copy, the confirmed count matches when the count is above
  `BULK_EMAIL_CONFIRM_ABOVE`, and the schedule, if given, is in the future and within a
  year. It sets `status=queued`, `start_at` (now plus `BULK_EMAIL_UNDO_SECONDS`, or the
  scheduled time), `scheduled`, and `confirm_count`. Nothing is sent in the request.
- **Cancel** returns a queued email to `draft` with its batch and content intact. It is
  refused with *This email has started sending.* once the job has claimed it.
- A queued email can still be edited (content and batch) and rescheduled, so a
  scheduled newsletter can be fixed on Monday. Editing a queued email never changes its
  `start_at`; rescheduling does.
- **The job** (`job.run_sender(now)`, the `send_bulk_emails` command): claims every
  `queued` email whose `start_at` has arrived, one at a time, with
  `select_for_update(skip_locked=True)` in a short transaction that sets
  `status=sending` and `started_at`, then freezes the batch (skip reasons as of now,
  including opt-outs after P2 and the DART limit after P8), then sends every `pending`
  row in surname order, paced, over one connection per `BULK_EMAIL_BATCH_SIZE` copies.
  Each row and the counts are saved as soon as the copy is tried. When no row is
  pending, `status=sent` and `sent_at` are set and one `bulk_email.send` audit line is
  written. A `sending` email with pending rows that the job finds at the start of a run
  (a crashed earlier run) is simply resumed.
- **Pacing**: at most `BULK_EMAIL_RATE_PER_MINUTE` copies a minute, by sleeping the
  remainder of each 60 / rate interval. A temporary refusal (SMTP 4xx: `421`, `450`,
  `451`, `452`) is retried after 5, 15, and 45 seconds, then recorded `failed` with
  *Temporarily refused, gave up after 3 retries*. A permanent refusal (5xx, or any other
  transport error) is `failed` at once with *Refused by the mail server*.
- **Progress**: `GET /bulk-email/{id}` carries `sent_count`, `failed_count`,
  `skipped_count`, `remaining` (pending rows), and `estimated_finish_at` (now plus
  remaining / rate) while sending.
- **Stop** sets `stop_requested`; the job reads it between copies, marks every pending
  row `stopped` with *Stopped by <name>*, and sets `status=stopped`, `stopped_at`,
  `stopped_by`. **Send the rest** (`resume`) turns the stopped rows back to `pending`
  and queues the email to start now, with no undo window.
- The job is a oneshot started every minute by `caldart-bulk-email.timer`; systemd
  does not start a second instance while one is running, and the claim lock guards the
  rest. `TimeoutStartSec=0`. `deploy/steps/timers.sh` installs it, and the rehearsal
  (`make rehearse-deploy`) starts it once like the others.
- The system administrator's Scheduled page gets a **Bulk email sender** panel with
  **Run now** (`POST /system/bulk-email/run`), which runs the job once in the request
  and reports what it sent; the e2e specs use it, and so does a developer with no timer.
  `make e2e` sets `BULK_EMAIL_UNDO_SECONDS=0` so a send is ready for the next run at
  once; the undo countdown is covered by vitest and by a backend test with a frozen
  clock.

Settings (P1): `BULK_EMAIL_RATE_PER_MINUTE` (30), `BULK_EMAIL_BATCH_SIZE` (50),
`BULK_EMAIL_UNDO_SECONDS` (120), `BULK_EMAIL_CONFIRM_ABOVE` (50).

## 3. The sidebar and the routes

`NAV_GROUPS`: Membership, Operations, **Bulk Email**, Administration, System. The group's
entries, in order (P1 adds the group and its first three; each later package adds its
own):

| Entry | Path | Roles | Package |
| --- | --- | --- | --- |
| Compose | `/bulk-email/compose` | management (+ dart_leader after P8) | P1 |
| Drafts & scheduled | `/bulk-email/drafts` | management (+ dart_leader) | P1 |
| Sent | `/bulk-email/sent` | management (+ dart_leader) | P1 |
| Templates | `/bulk-email/templates` | management | P6 |
| Recipient groups | `/bulk-email/groups` | management | P6 |
| Callouts | `/bulk-email/callouts` | management, dart_leader | P9 |
| Email types | `/bulk-email/types` | system_admin | P2 |
| Mail delivery | `/bulk-email/mail-delivery` | management, system_admin | P3 |
| Messages | `/messages` | any signed-in user | P7 |
| Email preferences | `/email-preferences` | any signed-in user | P2 |

`/bulk-email/compose` opens the sender's one empty draft if they have one (no subject,
no body, no batch), otherwise creates a new draft, and navigates to
`/bulk-email/drafts/:id`, which is the compose screen. `/admin/bulk-email` goes away.

The user guide gets a `docs/user/bulk-email/` group (`index.rst` with the toctree, one
page per screen, each with its `:roles:`), plus `docs/user/member/messages.rst` and
`docs/user/member/email-preferences.rst`. Every route is mapped in `help.ts`.

## 4. The compose screen (P1 lays it out; later packages add to it)

The screen is for someone with little technical skill. It reads top to bottom as three
numbered cards, each with one sentence of plain-language guidance, and the draft saves
itself (debounced, a quiet *Saved* note; never a Save button to forget).

1. **Who gets it**: the member-list filter bar, then one big **Add to batch** button,
   then the batch. After each add, a status line: *Added 12 people; 3 were already in
   the batch.* The batch table: name, email, kind, DART, *Added by* (the add's label),
   and *Will receive?* (a dot and *Yes*, or the skip reason in words). Above it the
   count sentence: *38 people will receive this email; 4 are skipped.* Under it
   **Download list** (CSV) and **Clear batch** (confirms). Each row has a trashcan
   (confirms). P6 adds **Add a saved group** beside **Add to batch**.
2. **What it says**: type (P2, radio list with each type's description), subject,
   Reply-To (P5), the message (plain textarea until P4 replaces it with the editor and
   the **Insert field** menu). P5 adds **Send me a test** at the bottom of the card; P6
   adds **Start from a template** and **Save as a template**.
3. **Check and send**: P5's checks list and P4's per-recipient preview sit at the top.
   Then **Send to 38 people** (primary) and **Schedule for later** (secondary; a date
   and time in the site's time zone, MM/DD/YYYY and hh:mm). The confirmation says what
   goes to how many, when; above `BULK_EMAIL_CONFIRM_ABOVE` it asks the sender to type
   the count before the Send button enables. After Send, the card shows *Sending in
   1:58* with a progress bar counting down and **Cancel**; then *Sending… 12 of 38 sent,
   about 1 minute left* with **Stop**; then the result line with a link to the Sent
   detail. The whole screen polls `GET /bulk-email/{id}` every 3 seconds while queued
   or sending and holds the form read-only once sending starts.

A draft that was sent is read-only everywhere, with a notice and a link to its Sent
detail. A queued email (undo or scheduled) opens in the same screen with a banner:
*Scheduled for 04/07/2026 8:00 AM. You can still change it. Cancel the schedule* /
*Starts sending in 1:12. Cancel*.

## P1: `bulk-core` (#435, #419, #408, #422, #423, #424, #425)

Branch `feature/bulk-core`, database `caldart_bulk_core`.

1. Models and migration as in §1 (regenerate `0001_initial` in place), the module
   layout in §0, and the state machine and job in §2.
2. `batch.py`: `add_filters(bulk, filters, *, actor)` runs the member-list filters
   exactly as today's `selected_accounts` and inserts a `batched` row for every account
   not already in the batch (by `user_id`), with the snapshots and the `BatchAdd`;
   returns the added and already-present counts. `batch_rows(bulk)` lists the batch
   with each row's live skip reason (`skip_reason(account, seen)` keeps today's order:
   deactivated, no address, invalid, bounced, duplicate address; P2 and P8 add theirs).
   `remove(bulk, recipient_id)`, `clear(bulk)`, and `batch_document(bulk)` (CSV: Name,
   Email, Kind, DART, Membership status, Added by, Will receive, Reason).
3. `drafts.py`: `open_draft(sender)` (reuse the empty one or create), the edit rule
   (`draft` and `queued` only; anything else is `DomainError` *This email has been
   sent and cannot be changed.*), `queue(bulk, *, confirm_count, start_at)`, `cancel`,
   `stop`, `resume`, with the refusals in §2 as `DomainValidationError` keyed by field
   (`confirm_count`: *The batch has changed: it now holds 52 people. Type the new
   count.*; `start_at`: *Choose a time in the future.* / *Choose a time within a year.*).
4. `render.py`: `render_copy(bulk, recipient) -> RenderedCopy(subject, text, html,
   headers)` from `emails/bulk_email.{txt,html}` as today (plain text, `linebreaks`).
   The job sends through `send_templated(..., headers=copy.headers)` with the rendered
   bodies passed in the context; the row stores the `Message-ID`.
5. API, all `management` (P8 widens it), under `/api/v1`:
   - `POST /bulk-email/drafts` (open or reuse; 201 or 200), `GET /bulk-email/drafts`
     (the caller's `draft` and `queued` emails; management sees everyone's, with the
     sender), `GET /bulk-email/sent` (`sending`, `sent`, `stopped`; newest first;
     unpaginated as today).
   - `GET /bulk-email/{id}` (everything the screen needs, including the batch counts,
     `remaining`, `estimated_finish_at`, and `can_edit`), `PATCH /bulk-email/{id}`
     (subject, body; later packages add fields), `DELETE /bulk-email/{id}` (drafts
     only).
   - `GET /bulk-email/{id}/batch`, `GET /bulk-email/{id}/batch.csv`,
     `POST /bulk-email/{id}/batch/add` (`{"filters": {...}}` → `{"added": 12,
     "already_present": 3, "count": 41}`), `DELETE /bulk-email/{id}/batch/{rid}`,
     `DELETE /bulk-email/{id}/batch`.
   - `POST /bulk-email/{id}/send` (`{"confirm_count": 52, "start_at": null}`),
     `POST .../cancel`, `POST .../stop`, `POST .../resume`.
   - `GET /bulk-email/{id}/recipients.csv` (results, as today plus Kind and DART).
   - `POST /system/bulk-email/run` (system_admin): runs the job once, answers the run
     summary like the other run endpoints.
   The old `preview`, `preview.csv`, and `send` endpoints go away.
6. Frontend: the sidebar group (§3), the routes, the compose screen (§4 without the
   later packages' pieces), the Drafts & scheduled page (one row per draft or queued
   email: subject, status in words, *Scheduled for* or *Starts in*, batch count, last
   edited; Open, Cancel schedule, trashcan), the Sent page (as today's history plus
   status, with **Stop** on a sending row and **Send the rest** on a stopped one), and
   the Sent detail page (counts, the results table, CSV). The Scheduled page panel.
   `DateText` for every date; a small `countdown.ts` helper for the mm:ss label.
7. Deployment: `deploy/systemd/caldart-bulk-email.{service,timer}` (every minute,
   `AccuracySec=1s`, no randomized delay), `deploy/steps/timers.sh`, the rehearsal's
   list, `docs/developer/deployment.rst`.
8. Docs: rewrite `docs/developer/api-bulk-email.rst`; a new `docs/developer/bulk-email.rst`
   chapter (states, the job, pacing, rendering, the extension points later packages
   fill); `data-model.rst`; `configuration.rst`; `email.rst`; `roadmap.rst` (drop the
   background-job item). User guide: `docs/user/bulk-email/index.rst`, `compose.rst`,
   `drafts.rst`, `sent.rst`; remove `docs/user/admin/bulk-email.rst`; update
   `admin/scheduled.rst`, `admin/index.rst`, `overview.rst`, `roles.rst`, and
   `quick-start.rst` where they name the old screen.
9. Tests: `test_bulk_batch.py` (adds, union without duplicates, counts, case-folded
   duplicate addresses, remove, clear, CSV, skip reasons, draft privacy, the frozen
   batch), `test_bulk_drafts.py` (open or reuse, edit rules, queue, cancel before and
   after the start, confirm count, past and far schedule, role matrix),
   `test_bulk_job.py` (frozen clock: nothing before `start_at`, sends at it; pacing with
   a fake mailer and a patched sleep; 4xx retried then succeeds, retried then fails; 5xx
   not retried; stop leaves the right statuses; resume; crash recovery; progress;
   audit), `test_bulk_command.py`, `test_bulk_history.py`. Vitest for every card and
   page, the countdown, and the confirm dialog. `frontend/e2e/bulk-email.spec.ts`
   rewritten: build a batch from two filter sets, download it, send, run the sender
   from the Scheduled page, see the result; a second test cancels a scheduled send.

## P2: `email-types` (#402, #420)

Branch `feature/email-types`, database `caldart_email_types`.

Standalone part:

1. `mail.EmailType` and `mail.EmailOptOut` (§1), a new `apps/mail` migration, the seed
   (`apps/mail/seed.py`, called from `seed_demo`: Operational for management and
   dart_leader, Fundraising for management, Mission for management and dart_leader),
   `apps/mail/types.py` (the services: list, create, update, delete with the PROTECT
   refusal, `sendable_types(user)`, `opt_outs(user)`, `set_opt_out(user, type, *,
   opted_out, source, actor)` audited as `email.opt_out` / `email.opt_in` with the
   source).
2. Unsubscribe: `apps/mail/unsubscribe.py` makes and reads a token
   (`django.core.signing`, salt `mail.unsubscribe`, payload user id and type id, max
   age `UNSUBSCRIBE_TOKEN_MAX_AGE`, default 180 days). Two Django views (not DRF) at
   `/mail/unsubscribe/<token>`: `GET` renders a small page in the public site shell
   with the type's name and one **Unsubscribe** button (a form POST); `POST` records
   the opt-out (source `unsubscribe`) and renders *You will no longer receive <type>
   email from CalDART*, with a link to sign in and change it. The POST is CSRF-exempt
   (one-click posts come from mail providers; the signed token is the authorization) and
   says so in a comment. A bad or expired token is a 400 page that says the link has
   expired and how to change preferences after signing in. A type that no longer
   allows opt-out still records nothing and says so.
3. `headers_for(user, email_type) -> dict[str, str]`: `List-Unsubscribe` with the HTTPS
   link (on `SITE_URL`, prefix included) and, when a contact address is set, a
   `mailto:` to it with `subject=unsubscribe`; `List-Unsubscribe-Post:
   List-Unsubscribe=One-Click`. Empty for a type that does not allow opt-out.
   `footer_for(user, email_type)` → the visible link text, or the type's "why you
   receive this" line.
4. API: `GET/POST /email-types`, `PUT/DELETE /email-types/{id}` (system_admin);
   `GET /email-types/sendable` (any signed-in user: the types the caller may send,
   system_admin all); `GET/PUT /me/email-preferences` (every signed-in user; only
   types that allow opt-out; PUT takes `[{"email_type": 2, "opted_out": true}]`);
   `GET/PUT /admin/members/{id}/email-preferences` (account_admin; source `admin`).
5. Frontend: `features/email-types/EmailTypesPage.tsx` (a table with name,
   description, who may send it as role labels, opt-out allowed; add, edit, delete with
   confirm; the delete refusal shown plainly), `features/email-preferences/
   EmailPreferencesPage.tsx` (one switch per type with its description, saving at
   once, *Saved* note; a sentence explaining what each type is for), and an **Email
   preferences** section on the member record (`features/admin-members`) with the same
   switches. Nav entries, routes, help mapping.
6. Docs: `docs/developer/api-email-types.rst` (new), `email.rst` (unsubscribe headers
   and the token), `data-model.rst`, `configuration.rst`, the roles docs; user guide
   `docs/user/bulk-email/email-types.rst`, `docs/user/member/email-preferences.rst`, and
   the member record page.
7. Tests: `test_email_types.py` (CRUD, unique names, PROTECT, sendable by role,
   matrix), `test_email_preferences.py` (self and admin, audit, matrix),
   `test_unsubscribe.py` (GET records nothing, POST records, tampered and expired
   tokens, a type without opt-out), `test_email_headers.py` (headers present for an
   opt-out type, absent otherwise, absent from transactional mail). Vitest for the
   three screens. An e2e spec: a member opts out on Email preferences; a system
   administrator edits a type.

Integration (after P1 merges; rebase first):

8. `BulkEmail.email_type` (new bulk_email migration), `PATCH /bulk-email/{id}` takes
   `email_type`, the compose screen's type radio list from `/email-types/sendable`
   (with *Choose what kind of email this is* when none is chosen; Send refuses without
   one: *Choose a type.*), the skip reason *Opted out of <type>* in `batch.skip_reason`
   (live in the batch list and at freeze time), the headers and footer in
   `render_copy`, the type on the Drafts, Sent, and detail screens and in the CSVs.
   Tests: `test_bulk_types.py` (skip reason, headers on a bulk copy, the type stored
   and shown, send refused without a type). Docs: `api-bulk-email.rst`, `bulk-email.rst`,
   the compose guide page.

Settings: `UNSUBSCRIBE_TOKEN_MAX_AGE`.

## P3: `mail-dns` (#421)

Branch `feature/mail-dns`, database `caldart_mail_dns`. Sonnet.

1. `uv add dnspython`. `apps/mail/dns_check.py`: `check_mail_dns(*, now) ->
   DnsReport` with one `DnsFinding(name, status pass|warn|fail, detail, fix)` per line:
   SPF (TXT at the domain of `DEFAULT_FROM_EMAIL`; parses; authorizes the resolved
   `EMAIL_HOST` through `include:`, `a`, `mx`, `ip4`, `ip6`; the `~all`/`-all` policy;
   `+all` or no `all` warns), DKIM (`DKIM_SELECTOR` setting; TXT at
   `<selector>._domainkey.<domain>` with `p=`; no selector → warn *No DKIM selector is
   configured*), DMARC (`_dmarc.<domain>`, policy `none` warns, `quarantine` or
   `reject` passes, `rua`/`ruf` listed), envelope alignment (when `BOUNCE_ADDRESS` is
   on another domain: pass when it is a subdomain of the From domain, else warn). Each
   lookup has a 3-second timeout; a resolver error is a `fail` with the error name.
   The report is cached in Django's cache for 5 minutes (`DnsReport.checked_at`).
2. `GET /mail/delivery-check` (management, system_admin): the report, with `refresh=true`
   to bypass the cache. `check_mail_dns` command: prints the report, exits 1 on any
   `fail`. `deploy/install.sh`'s finishing summary mentions the command.
3. `features/mail-delivery/MailDeliveryPage.tsx`: one row per finding with a dot and
   the status word, the detail, and the fix sentence; a *Checked at* line and
   **Check again**. Plain language throughout: a management reader does not know what
   SPF is, so each row's detail says what the record does in one sentence.
4. Docs: `docs/developer/deployment.rst` (a DNS section with the three records and
   how to verify them), `configuration.rst` (`DKIM_SELECTOR`), `api-system.rst` (the
   endpoint), `email.rst` (a pointer); user guide `docs/user/bulk-email/mail-delivery.rst`.
5. Tests: `test_mail_dns.py` with `dns.resolver` patched: each record present and
   good, missing, malformed, not authorizing the host, DMARC `p=none`, no selector, the
   cache, the command's exit status, and the matrix. Vitest for the page.
6. Nav: the entry in the Bulk Email group (add the group if P1 has not merged).

## P4: `rich-text` (#416, #418)

Branch `feature/rich-text`, database `caldart_rich_text`.

Standalone part:

1. `uv add nh3`. `apps/bulk_email/richtext.py`: `sanitize(html) -> str` with the
   allow-list `p, br, strong, em, b, i, u, s, h1, h2, h3, ul, ol, li, a[href, title],
   img[src, alt, width, height], blockquote, hr` and URL schemes `http`, `https`,
   `mailto` on `href` and `http`, `https` on `src`; every style, class, id, and event
   attribute is stripped. `html_to_text(html) -> str`: paragraphs separated by blank
   lines, list items as `- `, links as `text (url)`, images as their alt text, headings
   on their own line.
2. `apps/bulk_email/fields.py`: the catalog as a tuple of `Field(token, label,
   description, value(user) -> str)`: `first_name`, `last_name`, `full_name`, `email`,
   `dart_name`, `plan`, `membership_status`, `expiration` (MM/DD/YYYY), `home_airport`.
   `find_tokens(text) -> list[Token(name, fallback)]` with the syntax `{name}` and
   `{name|fallback}` (lowercase names, underscores; anything else is left alone, so
   `{{ x }}` and `{% y %}` arrive literally); `unknown_tokens(text)`;
   `values_for(user, tokens) -> dict[str, str]`; `substitute(text, values, *,
   escape)`, which HTML-escapes each value when `escape` is true and applies fallbacks
   for empty values. Substitution is a lookup, never template rendering.
3. `apps/bulk_email/images.py` and `BulkEmailImage` (`uploaded_by FK SET_NULL`, `file`
   under `MEDIA_ROOT/bulk-email/<uuid>.<ext>`, `width`, `height`, `created_at`):
   `store(upload, *, actor)` checks the type (PNG, JPEG, GIF, WebP by content, with
   Pillow), the size (`BULK_EMAIL_IMAGE_MAX_BYTES`, 5 MB), scales to at most
   `BULK_EMAIL_IMAGE_MAX_WIDTH` (1200) wide, and answers the absolute URL on
   `SITE_URL`. Confirm that `MEDIA_URL` is served without sign-in in dev and in the
   deploy configurations (Apache and nginx serve `MEDIA_ROOT` directly); document it.
   `POST /bulk-email/images` (management; multipart `image`) → `{"id", "url",
   "width", "height"}`. `GET /bulk-email/fields` → the catalog.
4. `components/RichTextEditor.tsx` on TipTap (`@tiptap/react`, `@tiptap/starter-kit`,
   `@tiptap/extension-link`, `@tiptap/extension-image`): a toolbar with labeled icon
   buttons (Bold, Italic, Heading, Bulleted list, Numbered list, Link, Image, and a
   slot for extra buttons) and the editing area, `value`/`onChange` as HTML; the Link
   button asks for the address in a small dialog; the Image button opens a file
   picker, uploads through a prop, asks for alt text (required), and inserts the image.
   `features/bulk-email/InsertFieldMenu.tsx`: a menu button listing the catalog by
   label with its description, inserting the token at the cursor (into the subject
   input or the editor, whichever has focus last). Record the editor choice in
   `docs/developer/architecture.rst`.
5. Tests: `test_bulk_richtext.py` (scripts, event handlers, `javascript:` links,
   disallowed tags, styles; text derivation), `test_bulk_fields.py` (every field,
   fallback, unknown token, escaping, literal template syntax), `test_bulk_images.py`
   (type, size, scaling, permission, URL). Vitest for the editor's toolbar actions and
   the menu.

Integration (after P1 merges; rebase first):

6. `BulkEmail.body` holds HTML (`sanitize` on every save, preview, and send).
   `render_copy` becomes: sanitize the body, substitute the recipient's values
   (escaped) into the HTML, build the text part with `html_to_text` and the raw values,
   substitute the subject, and store `values` on the row at send time (only the tokens
   the message uses). An unknown token is a 400 naming it on save of the body, on
   preview, and on send. `POST /bulk-email/{id}/preview` (`{"recipient_id": 12}`,
   default the first batch row, or the sender when the batch is empty) answers
   `{"subject", "html", "text", "recipient": {...}}`; the Check and send card shows the
   HTML in a sandboxed iframe (`srcdoc`, `sandbox=""`) with *Previewing as Ann Able* and
   previous/next arrows. The compose screen's editor and menu replace the textarea; the
   Sent detail shows the rendered message. `recipients.csv` and the history are
   unchanged. Tests: `test_bulk_render.py` (values stored at send time, a rebuilt copy
   after the profile changed, the preview per recipient). An e2e spec composes with
   bold text, a link, and an image, previews, and sends.

Settings: `BULK_EMAIL_IMAGE_MAX_BYTES`, `BULK_EMAIL_IMAGE_MAX_WIDTH`.

## P5: `send-checks` (#417, #426, #430)

Branch `feature/send-checks`, database `caldart_send_checks`.

1. Reply-To (#430): `BulkEmail.reply_to`; `BULK_EMAIL_REPLY_TO` setting (blank means
   the sender's own address); the Message card's **Reply-To** field prefilled with the
   default and explained in one sentence; `validate_email` on save and send; the header
   through `send_templated(reply_to=...)`; shown on the Sent detail.
2. Test copy (#417): `tests_send.send_test(bulk, *, actor)` renders the draft as it
   stands for the actor (their own field values), subject prefixed `[Test] `, sends to
   the actor's own address under the purpose `bulk_email_test` (added to
   `apps/mail/purposes.py`), records no bulk rows, and raises `MailRefusedError` through
   to a 503 with *The mail server refused the test. Try again in a minute.*
   `POST /bulk-email/{id}/test` → `{"to": "pat@example.org"}`. The button **Send me a
   test** sits under the message with the confirmation *A test went to
   pat@example.org* after each press; every press sends again.
3. Checks (#426): `checks.run_checks(bulk) -> list[Finding(code, level error|warning,
   message)]`: empty subject or body (error), unknown token (error, from P4), a token
   empty for more than half the batch (warning, with the counts), links that do not
   load (HEAD then GET with `httpx`, 5-second timeout, warn on 4xx, 5xx, timeout, or a
   non-HTTPS link; `mailto:` skipped; after resolving, refuse private, loopback,
   link-local, and reserved addresses as *Links into a private network are not
   checked*), images without alt text or larger than `BULK_EMAIL_IMAGE_MAX_WIDTH`,
   placeholder text (`TODO`, `XXX`, `lorem ipsum`, `[insert`, case-insensitive).
   `POST /bulk-email/{id}/checks` answers the findings; the send endpoint runs them too
   and refuses on any error with the findings under `checks`. The Check and send card
   runs them when opened and before the confirmation, lists them with a dot per level,
   and enables Send only when there is no error; warnings read *You can still send.*
4. Docs: `api-bulk-email.rst` (three endpoints, the header), `bulk-email.rst`,
   `email.rst` (the test purpose), `configuration.rst`; the compose guide page.
5. Tests: `test_bulk_test_send.py`, `test_bulk_checks.py` (each check passing and
   failing, `respx` for the links including a private-address refusal, errors block and
   warnings do not), `test_bulk_reply_to.py`. Vitest for the button, the checks list,
   and the field.

## P6: `reuse` (#427, #428, #429)

Branch `feature/reuse`, database `caldart_reuse`.

1. `EmailTemplate` (`name` unique 80, `subject`, `body`, `email_type FK SET_NULL`,
   `reply_to`, `created_by`, `updated_at`), CRUD at `/bulk-email/templates`, and
   `POST /bulk-email/{id}/apply-template` (`{"template": 3}`, fills a draft).
   The Templates page: a table (name, type, last edited), **New template** (opens an
   editor using the same Message card pieces), rename, edit, delete with confirm. The
   compose screen's Message card gets **Start from a template** (a picker; refuses to
   overwrite a non-empty draft without confirming) and **Save as a template** (asks for
   a name).
2. `RecipientGroup` (`name` unique 80, `kind` fixed|live, `created_by`, `updated_at`),
   `RecipientGroupMember` (`group`, `user` FK CASCADE; fixed groups),
   `RecipientGroupFilter` (`group`, `filters` JSON, `position`; live groups). CRUD at
   `/bulk-email/groups`, `GET /bulk-email/groups/{id}/members` (the live count and
   list), `GET .../members.csv`, `POST /bulk-email/{id}/batch/add-group` (`{"group":
   5}` → the same counts as a filter add; the `BatchAdd` names the group).
   `POST /bulk-email/{id}/save-group` saves the current batch as a fixed group, or its
   adds' filters as a live group. The Recipient groups page: table (name, kind, count,
   last edited), open, rename, delete with confirm, CSV; a fixed group's page lists its
   people with add (typeahead on the member list) and remove; a live group's page lists
   its filter sets with add and remove.
3. Duplicate (#427): `POST /bulk-email/{id}/duplicate` (`{"copy_recipients": false}`)
   creates a draft owned by the caller with the subject, body, type, and Reply-To; with
   `copy_recipients` the original's recipients join as one `BatchAdd` labeled
   *Copied from "<subject>"*. **Duplicate** on the Sent page and the Sent detail, with
   the option in its confirmation; the new draft opens.
4. Docs: `api-bulk-email.rst`, `data-model.rst`, `bulk-email.rst`; user guide
   `templates.rst`, `groups.rst`, and the compose and sent pages.
5. Tests: `test_bulk_templates.py`, `test_bulk_groups.py` (fixed unchanged, live
   re-runs, merge deduplicates, deleting a group leaves history, CSV, matrix),
   `test_bulk_duplicate.py`. Vitest for both pages and the compose additions; an e2e
   spec saves a group and a template and starts a draft from both.

## P7: `delivery` (#433, #434)

Branch `feature/delivery`, database `caldart_delivery`.

1. Bounce linkage: in `apps/bulk_email/apps.py` `ready()`, connect a `post_save`
   receiver on `mail.EmailLog` that, when `status` is `bounced`, marks the
   `BulkEmailRecipient` with that `message_id` as `bounced` with the bounce detail and
   moves the counts (`bounced_count` on `BulkEmail`). `delivery.retry_failed(bulk, *,
   actor)`: every `failed` row back to `pending`, a `BulkEmailRetry(bulk_email,
   requested_by, requested_at, count)`, the email queued to start now. `POST
   /bulk-email/{id}/retry`. `GET /bulk-email/{id}/recipients/{rid}/copy` answers the
   copy as sent (`render_copy` with the stored `values`).
2. The Sent detail becomes the delivery report: counts (sent, failed, skipped, bounced,
   and retried), a filter by result, the per-recipient table with the reason and
   *Tried at*, **Retry failed** (confirms; disabled when nothing failed), **View copy**
   per row (a dialog with the sandboxed HTML), CSV with the new columns, and the
   retries listed with their times. Sent Emails (`features/system`) rows for the
   `bulk_email` purpose link to the bulk email.
3. Archive (#434): `archive.messages_for(user)` lists the sent bulk emails (not
   hidden, not a callout) where a recipient row with `user=user` has status `sent` or
   `bounced`, newest first. `GET /messages`, `GET /messages/{id}` (the reader's own copy
   rendered from their stored values; 404 for anyone else's). The Messages page: a
   list (date, subject, from), each opening the message in the sandboxed view. `View
   in browser` footer link in `render_copy` to `<SITE_URL>/portal/messages/{id}`
   (prefix-aware); a callout links to its answer page instead (P9 fills that in).
   `POST /bulk-email/{id}/hide` (`{"hidden": true}`), **Hide from Messages** / **Show in
   Messages** on the Sent detail.
4. Docs: `api-bulk-email.rst`, `email.rst` (bounces tie back to the bulk copy),
   `bulk-email.rst`; user guide `sent.rst`, `docs/user/member/messages.rst`, and
   `admin/sent-emails.rst`.
5. Tests: `test_bulk_delivery.py` (a later bounce marks the copy, retry only failed,
   bounced and skipped untouched, counts, CSV, the copy as sent, matrix),
   `test_bulk_archive.py` (recipient sees, non-recipient 404, transactional mail absent,
   values as sent after a profile change, never another's values, hidden gone but
   history stays, the link under `URL_PREFIX`, matrix). Vitest; an e2e spec reads a
   received message under Messages.

## P8: `leaders` (#432)

Branch `feature/leaders`, database `caldart_leaders`.

1. `apps/bulk_email/senders.py`: `SenderContext(user, is_management, dart)`;
   `sender_context(user)` gives management (or system_admin) everything, a
   `dart_leader` their profile's DART, and a leader without one `can_send=False` with
   the reason *Your profile names no DART, so there is nobody to send to. Set your DART
   on My profile.* `IsBulkSender` replaces `IsManagement` on every bulk email endpoint
   except Templates and Recipient groups (management only). A leader's queryset is
   their own emails; management's is everyone's.
2. `BulkEmail.dart` set from the context at creation. `batch.add_filters` forces
   `dart=<their dart>` for a leader and refuses any other `dart` value with *You can
   only send to your own DART.*; the freeze step skips anybody no longer in the DART
   with *Not in your DART*. `GET /bulk-email/sender` answers the context for the compose
   screen, which shows the reason instead of the form when `can_send` is false and
   hides the DART filter otherwise (showing *Sending to the Marin DART* as a fixed
   value).
3. Types: a leader's `/email-types/sendable` already follows `sender_roles`; nothing
   more.
4. Nav and routes: `dart_leader` on Compose, Drafts & scheduled, and Sent. The Sent
   page for management gains Sender and DART columns. `ROLE_DESCRIPTIONS` for
   `dart_leader` and `management` say so; `docs/user/roles.rst`.
5. Docs: `api-bulk-email.rst`, `api-reference.rst`; user guide
   `docs/user/bulk-email/dart-leaders.rst`.
6. Tests: `test_bulk_leaders.py` (never outside the DART through a crafted filter or
   id, no DART cannot send, drafts and sends private, management sees all, matrix).
   Vitest for the fixed DART and the no-DART notice; an e2e spec sends as a leader.

## P9: `callouts` (#431)

Branch `feature/callouts`, database `caldart_callouts`.

1. `Callout` (`bulk_email` one-to-one, `closes_at`, `closed_at`, `closed_by`),
   `CalloutAnswer` (`callout`, `user` FK CASCADE, `answer` available | limited |
   unavailable, `note` 500, `answered_at`; unique per user). The Message card gets
   **This is a mission callout** (a switch; defaults the type to Mission when that
   type exists and the sender may send it) and **Answers close** (date and time,
   default 48 hours ahead). `PATCH /bulk-email/{id}` takes `is_callout` and
   `closes_at`.
2. The email: three buttons (Available, Available with limits, Not available) above the
   footer, each a link to `/mail/callout/<token>?answer=<kind>`, token signed per
   recipient (salt `bulk_email.callout`, payload callout id and user id, no max age:
   the close time rules). `GET` renders a page in the public shell with the callout's
   subject, the three choices (the query's preselected), a note field, and **Send
   answer**; `POST` records or updates the answer. After `closes_at` or `closed_at`
   both show *This callout has closed* and record nothing. A tampered token is a 400
   page. The GET records nothing. The archive's View in browser for a callout points
   here.
3. The Callouts page (management; a leader for their DART): a table (sent, subject,
   closes, answers by kind, non-responders). The detail: counts, a filter by answer,
   one row per recipient (name, answer, note, answered at, DART, home airport,
   aircraft, go/no-go as the member check shows it), CSV, **Remind non-responders**
   (confirms; a new round of rows, `round` n, for everyone with no answer, sent by the
   job with the same message and fresh values), **Close now** (confirms).
   `GET /bulk-email/callouts`, `GET /bulk-email/callouts/{id}`, `GET .../answers.csv`,
   `POST .../remind`, `POST .../close`.
4. Notification event `callout.answer` in the catalog (`apps/notifications/events.py`):
   raised on each new or changed answer, with the callout subject, the person, and the
   answer, for the roles that can see the callout.
5. Docs: `data-model.rst`, `api-bulk-email.rst`, `notification-events.rst`,
   `bulk-email.rst`; user guide `callouts.rst` (sender) and
   `docs/user/member/callouts.rst` (what the email looks like and how to answer).
6. Tests: `test_bulk_callouts.py` (record, change, tampered and expired, closed records
   nothing, GET records nothing, remind reaches only non-responders, counts, CSV,
   matrix including a leader limited to their DART, the event). Vitest for the page
   and detail; an e2e spec sends a callout, answers from the email link, and reminds.

## P10: `closeout`

Branch `feature/bulk-closeout`, database `caldart_bulk_closeout`. Sonnet, no reviewer.

1. Read every page under `docs/user/bulk-email/` and the two member pages in one
   sitting and make them read as one guide: consistent names for every button, a
   first paragraph on `index.rst` that walks a new management member through their
   first send in five sentences, and the `quick-start.rst` and `overview.rst`
   navigation descriptions.
2. `docs/developer/bulk-email.rst` reads as one chapter; `roadmap.rst` is current;
   `README.rst` mentions bulk email where it lists what the site does.
3. The nav tests, help mapping test, and `App.test.tsx` cover every entry.
4. Residue: every advisory review finding the orchestrator passed along, as small fixes
   or as filed issues.
5. Move this plan to `plans/archive/`.

## Design and UI review

After P1 merges, and again after wave 2, the orchestrator runs a usability review: a
reviewer reads the compose, drafts, and sent screens as a volunteer with little
technical skill would, against the seeded data, and reports blocking findings (a step
with no guidance, an action with no confirmation or no result message, a word a member
would not know, a control that cannot be reached by keyboard, a table that overflows
on a phone). Blocking findings go back to the owning package before the next wave;
the rest go to P10.
