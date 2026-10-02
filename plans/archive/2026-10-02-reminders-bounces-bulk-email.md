# Reminder schedule, bounce detection, and bulk email

Issues #151 (editable reminder offsets), #266 (detect bounced emails), and #267 (bulk
email to filtered lists with a dry run).

Owner decisions (2026-10-02):

- The reminder schedule is edited by a **system administrator only**. An account
  administrator sees it read-only.
- Bounces come back through a **bounce mailbox read over IMAP**. There is no provider
  webhook: the site sends through plain SMTP.
- Bulk email is sent by a **new role, "CalDART management"**. A system administrator
  passes, as for every role.
- Bulk email has **no opt-out**. Typed bulk email with a per-type opt-out and
  per-type sender roles is #402, outside this plan; build nothing for it here.

Three packages run in parallel, each on its own branch and worktree with its own
database. Merge order: `reminder-schedule`, `bounces`, `bulk-email`. When `bounces`
merges, `bulk-email` rebases and adds the bounced-address skip (package C, step 6).

## Package A: `reminder-schedule` (#151)

Branch `feature/reminder-schedule`, database `caldart_reminder_schedule`.

1. The stages keep their meaning but lose the numbers in their names. Rename
   `ReminderKind` to `first`, `second`, `final`, `expired`, and `lapsed`. That covers the
   slugs, the templates `reminder_<kind>`, the purposes `reminder_<kind>`, the purpose
   labels, the frontend `ReminderKind` union, and `KIND_LABELS`. Regenerate the migration
   in place, since this repo keeps no backwards compatibility.
2. Add a singleton `ReminderSchedule`, modeled on `AircraftCoveragePolicy` (`load()`,
   `pk=1`, `updated_by`, `updated_at`). It holds four whole-day fields:
   - `first_days_before` (default 60).
   - `second_days_before` (default 30).
   - `final_days_before` (default 7).
   - `lapsed_days_after` (default 30).

   The day-of stage stays at 0. The validation:
   - `365 >= first > second > final >= 1`.
   - `7 <= lapsed <= 365`, which keeps the day-of stage's six-day reach clear of it.

   Each error names the field and the rule.
3. `stage_span` and everything else that reads `REMINDER_OFFSETS` read the stored
   schedule instead, and `REMINDER_OFFSETS` goes away. Spans still tile:
   - A stage before expiry reaches back to the day after the next stage.
   - The lapsed stage's reach stays 30 days.

   `ReminderLog`'s once-per-kind constraint is unchanged, so editing the schedule never
   resends a stage the member already received.
4. API:
   - `GET /admin/reminders/schedule` for account administrators and system
     administrators.
   - `PUT` on the same path for system administrators only.
   - The answer carries the four fields plus `updated_by` and `updated_at`.

   The labels a screen prints ("60 days before expiry") are built from the schedule
   wherever they appear: the reminder log, the email log's purpose labels, the run
   results, and the reports.
5. UI:
   - On the system administrator's Scheduled page, beside the reminders panel, add a
     **Reminder schedule** card with four number fields, Save, and the stored by/at line.
   - The account administrator's Reminders page shows the same schedule read-only.
   - Replace the hard-coded "60, 30, and 7 days" copy in `RemindersPanel.tsx` and
     `AdminRemindersPage.tsx` with the stored values.
6. Docs:
   - The developer docs: `reminders.rst`, which drops the claim that changing the
     schedule is a code change, plus `data-model.rst`, `api-system.rst`, `email.rst`, and
     the `api-reference.rst` matrix.
   - The user guide: `member/renew.rst`, `admin/reminders.rst`, `admin/scheduled.rst`,
     `admin/sent-emails.rst`, and `overview.rst`.

     State the defaults and say that a system administrator can change them. The member
     guide must say exactly when each reminder arrives, as the issue asks.
7. Tests:
   - Validation, both sides of each bound.
   - An edited schedule moves the spans.
   - Editing the schedule never resends a stage.
   - The role matrix for GET and PUT.
   - Frontend tests for the card and for the read-only view.

## Package B: `bounces` (#266)

Branch `feature/bounces`, database `caldart_bounces`.

1. Sending (`caldart/mail.py`):
   - Every message gets a `Message-ID` from `make_msgid`, stored on its `EmailLog` row.
     Add a new indexed `message_id` field for it.
   - A new optional setting `BOUNCE_ADDRESS` becomes the SMTP envelope sender (the
     Return-Path) while the `From` header stays `DEFAULT_FROM_EMAIL`. Use Django's
     header-versus-`from_email` split, and verify against the Django 6 mailer API in
     use.
   - Left empty, the envelope sender is `DEFAULT_FROM_EMAIL` as today.
2. `EmailLog`:
   - `EmailStatus` gains `bounced`.
   - Add `bounced_at` and `bounce_detail`. The detail is the DSN status code and the
     diagnostic text, trimmed to a sane length.
3. `User`:
   - Add `email_bounced_at` and `email_bounce_detail`.
   - Both are cleared when the address changes, when it is verified, and by a **Clear
     bounce** action on the Users and roles user screen. That action is for user
     administrators, with a confirmation, and it is audited.
4. The checker: a new management command `check_bounces [--dry-run]` with a service
   function behind it.
   - It reads unseen messages from `BOUNCE_IMAP_URL`, in the form
     `imaps://user:password@host[:port]/MAILBOX`, using stdlib `imaplib` only. Left
     empty, bounce checking is off and the run says so.
   - It parses RFC 3464 delivery-status reports (`multipart/report`,
     `message/delivery-status`). Only permanent failures count: `Action: failed` and
     status `5.x.x`. Delays and `4.x.x` are ignored.
   - It matches a report to an `EmailLog` row by the original `Message-ID`, taken from
     the attached headers or message. The fallback is `Final-Recipient` against the
     latest row for that address within 7 days.
   - A match marks the row bounced and flags the row's user, or the user whose current
     address equals the recipient.
   - Each processed message is marked seen, and a dry run changes nothing anywhere.
   - The run returns a `RunAction` result in the shared shape (bounced, unmatched,
     ignored), like the other runs, and is audited.
5. Running it:
   - Add a `deploy/systemd/caldart-bounces.{service,timer}` pair that runs hourly.
   - `deploy/install.sh` gains `--bounce-imap-url` and `--bounce-address`, written to the
     env file. Keep shellcheck and the dry-run install tests green.
   - Add `make bounces` for development.
   - Add `POST /system/bounces/run {dry_run}` for system administrators, with a
     **Bounces** panel on the Scheduled page beside the other runs.
6. Showing it:
   - The email log report and the Sent Emails screen gain the Bounced status filter
     value and a bounced date and detail column.
   - On the member record header and the Users and roles user screen, add a **Bounced
     <MM/DD/YYYY>** chip next to the address, with the detail.
   - Add an **Email bounced** filter on Users and roles.
   - Expose `email_bounced_at` on the member detail and admin user serializers, and in
     `types.ts`.
7. Docs:
   - The developer docs: `email.rst`, which replaces "Bounces are not detected" with how
     detection works and how to set up the mailbox. Check the stale #268 sentence in
     "Receiving" there too, since the `signed_up` notification exists.
   - Also `configuration.rst`, `deployment.rst`, `deploy/README.rst`,
     `deploy/caldart.env.example`, `api-system.rst`, `api-members.rst`,
     `api-auth.rst` or whichever page documents the user serializer, `data-model.rst`,
     and the `api-reference.rst` matrix.
   - The user guide: `admin/sent-emails.rst`, `admin/scheduled.rst`,
     `admin/member-record.rst`, and `admin/user-record.rst`.
8. Tests:
   - DSN parsing, using real-shaped fixtures for a hard bounce, a delay, an
     auto-reply, and a report without the original headers.
   - Matching, by Message-ID and by the fallback.
   - Dry run changes nothing.
   - Bounce checking off when the setting is empty.
   - The flag clears on an address change, on verification, and on Clear bounce.
   - The envelope sender is set when `BOUNCE_ADDRESS` is set.
   - A fake IMAP connection, injected with monkeypatch and never touching the network.
   - The role matrix.
   - Frontend tests for the chip, the filter, the panel, and Clear bounce.

## Package C: `bulk-email` (#267)

Branch `feature/bulk-email`, database `caldart_bulk_email`.

1. The role:
   - Add `management` to `roles.py`, labeled **CalDART management**, with a
     description. It goes after `account_admin` in privilege order.
   - Wire it everywhere a role appears: the seed's demo user
     `management@example.org`, the roles report, Users and roles, `types.ts`, `nav.ts`,
     `docs/user/roles.rst`, the guide's `:roles:` fields and roles.json, the
     `api-reference.rst` matrix, `test_roles_permissions`, `test_permission_matrix`, and
     `test_docs_user`.
   - Follow how `treasurer` is threaded through the code base.
2. The model:
   - `BulkEmail`: subject, body (plain text, with blank-line paragraphs), filters (the
     query parameters, as `ReportSubscription.filters` stores them), sender, created and
     sent timestamps, and counts.
   - `BulkEmailRecipient`: the bulk email, the user, the address, the name, the status
     (sent, failed, or skipped), and the reason.

   A dry run builds the recipients without storing a `BulkEmail`.
3. The recipients:
   - The member list's filters through `member_report_queryset(params)`, the same
     filters and the same `FilterBar` the member list uses, kind included, so friends can
     be reached.
   - Deactivated accounts are always skipped, and so are addresses that are blank or
     invalid. Each skip carries a reason.
   - Addresses are de-duplicated case-insensitively.
4. The API, for `management` and system administrators:
   - `POST /bulk-email/preview {subject, body, filters}` validates the message and
     returns the recipient list and the skips. It sends nothing.
   - `POST /bulk-email/send` takes the same body and sends to the list rebuilt at send
     time. Each message goes through `send_templated` with purpose `bulk_email`, a label
     in `purposes.py`, and a new `bulk_email.{txt,html}` template pair. It stores the
     `BulkEmail` with every per-recipient result, is audited, and survives a failed send.
   - `GET /bulk-email` (history), `GET /bulk-email/{id}` (with its results), and
     `GET /bulk-email/{id}/recipients.csv`.
   - `GET /bulk-email/preview.csv` with the same filters, so the list can be downloaded
     before sending.
5. The screen:
   - A nav entry **Bulk Email**, for `management`.
   - The screen reads top to bottom: the FilterBar, Subject, Body, a **Preview
     recipients** button, then the recipient list (names, addresses, skips with reasons,
     and the count) with a **Download list** link.
   - **Send to N people** goes behind `ConfirmButton`.
   - Then the per-recipient results in `RunActionsTable`, and a history list with each
     past send's results and CSV.
   - Use the admin UI conventions: MM/DD/YYYY dates, one-line rows, and the column
     chooser where a table is wide.
6. After `bounces` merges, an address with `email_bounced_at` set is skipped with the
   reason "Address bounced". The orchestrator will say when.
7. Docs:
   - A user guide page `admin/bulk-email.rst` with `:roles: management`, plus
     `roles.rst`.
   - The developer docs: a new `api-bulk-email.rst` (in the toctree), `data-model.rst`,
     `email.rst` (the purpose), and the `api-reference.rst` matrix.
8. Tests:
   - Recipient building against each filter family.
   - Skips and de-duplication.
   - Preview sends nothing.
   - Send logs every recipient and survives one failure.
   - The CSVs, with an exact filename.
   - The role matrix.
   - Frontend tests for the screen flow.
   - An e2e spec: sign in as management, filter, preview, send, and see the results.

## Every package

- TDD. `make lint`, `make test`, `make check`, `make docs`, and `make audit` pass.
- `make e2e` passes both plain and with `E2E_URL_PREFIX`.
- Don't touch `uv.lock` or `package-lock.json`.
- Open the PR with `Closes #N`.
