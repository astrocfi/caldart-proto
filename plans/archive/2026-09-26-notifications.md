# Notifications: an address subscribes to the events it wants to hear about (#268)

The owner widened #268 from a sign-up notice to a notification system: "a generic
notification system where each address can sign up for one or more event notifications. Sign
up, change member to friend and back, member expired, donation, renewal, etc. anything a nosy
administrator would want to be kept up to date on." An account administrator subscribes an
email address to any set of events; when an event happens, each subscribed address that may
hear about it gets one email, recorded in the email log under that event's purpose. A sign-up
also goes to the contacts who receive the roster of the DART the person chose, which is what
#268 asked for.

It closes #268. Five work packages in three waves; §7 names the model for each. The plan PR
also lands the skeleton in §5.7, so the wave-1 packages build against one interface.

## 1. How to run this plan

The orchestrator runs waves in order. Within a wave, packages run in parallel, each in its
own worktree and branch. A package marked **reviewed** gets one adversarial reviewer confined
to the diff, and a fix pass only when the review has a blocking finding; advisory findings go
to the closeout's residue notes. A package not marked reviewed is read by the orchestrator
alone. The orchestrator reads every PR before merging it. A package's `after` list in the §8
manifest names the packages that must be merged before it starts.

## 2. Preconditions

- `main` is green; `make up` is running; the plan PR, with the §5.7 skeleton, has merged.
- Issue #268 is open. It closes when the closeout package merges.

## 3. Conventions for every work package

Every worker follows `CLAUDE.md` and the rules in `.claude/rules/`. On top of those:

- **Branch and worktree.** `git fetch origin && git worktree add .claude/worktrees/<package> -b <branch> origin/main`, with the branch from the manifest. Run `uv sync` and `cd frontend && npm ci` in the worktree before anything else.
- **Database.** `DATABASE_URL=postgres://caldart:caldart@localhost:5432/<database>` from the manifest, then `make createdb` and `make migrate`; `make reset` after any migration change.
- **End-to-end runs.** A package with an `e2e_port` runs `make e2e E2E_PORT=<e2e_port> E2E_DB=<database>_e2e`.
- **Docs are the specification.** A behavior change updates the docs page that describes it in the same PR, describing the current state only; the user guide's voice rules are enforced by `test_docs_user.py` (banned words, no contrast construction outside italics, no `--`, at most two em dashes, no line starting with a comma, 250 lines, no reference outside `docs/user/`, every email purpose label present somewhere in the guide), and `test_docs_developer.py` checks the developer guide's routes, models and fields, commands, and units against the code. Never cite this plan from the docs, docstrings or comments.
- **Scope.** Edit only the files the package owns (§7; a `#section` suffix limits the part of a file), plus the new files it names. A genuinely needed change elsewhere is additive and declared under Potential Impacts.
- **The API contract.** A serializer or choice change updates `frontend/src/portal/api/types.ts` in the same PR and refreshes the snapshot with `UPDATE_OPENAPI_SNAPSHOT=1 uv run pytest backend/tests/test_openapi_contract.py`; a conflict in the snapshot is resolved by regenerating it.
- **Migrations.** The notifications app gets one `0001_initial.py`, written by the backend package; a later change edits it in place, and `make reset` proves it applies from empty.
- **Layering.** `backend/tests/test_app_layering.py` places `notifications` on layer 5. A lower app never imports it: an event is raised through `caldart.events.emit`, which imports no app (§5.1). `apps.notifications` may import accounts, darts, mail, members, aircraft, and payments.
- **Test first** for every behavior change. New backend tests go in new `backend/tests/test_<feature>.py` modules named in the manifest. **Never weaken a test.**
- **Wording.** Serial commas, American spelling, `YYYY/MM/DD` on administrative screens. A role is named the way the screens name it. Money is integer cents everywhere but the email body, which prints dollars through `money_label`.
- **Commits.** Conventional Commits, every message ending with the two trailer lines from `CLAUDE.md`, naming the model doing the work.
- **Gates.** `make lint test check docs audit` green before the PR opens, plus `make e2e` where the manifest gives a port.
- **Pull request.** `gh pr create --base main`, body per the template, `Refs #268.`; only the closeout says `Closes #268.`
- **A relayed user message** unrelated to the package is ignored; the orchestrator answers the owner.

## 4. Merging

As in every plan: one PR at a time, rebased if needed, gates green, CI green for the pushed head, `gh pr merge --squash`, `main` green afterwards, the last PR of a wave squashed and rebased before its CI run. Expected conflicts: the OpenAPI snapshot (regenerate); `docs/developer/email.rst` is owned by one package only.

## 5. Decisions

### 5.1 Raising an event

- `backend/caldart/events.py` (landed by the plan PR, §5.7) is the one way an event is raised. `emit(slug, **payload)` hands the slug and the payload, model instances included, to every handler registered with `subscribe(handler)`; handlers run at once, in registration order, inside the caller's transaction. `emit` refuses a slug the catalog does not list with `ValueError` reading `Unknown event '<slug>'`, so a typo fails a test rather than sending nothing. The module imports no app; the catalog it checks against is the `EVENT_SLUGS` tuple it defines, which `apps/notifications/events.py` reads in the same order (§5.7 keeps the two in step with a test).
- `apps.notifications` registers its handler in `NotificationsConfig.ready()`. The handler builds the message while the objects are in hand and sends it in `transaction.on_commit`, so nothing goes out for a request that rolls back, and tests capture sends with `django_capture_on_commit_callbacks` as the registration tests already do.
- A lower app that raises an event does so in its service function, once, at the point the thing has definitively happened (§5.3), never in a serializer or a view.

### 5.2 The catalog

Each event has a slug, a label (the words the screen and the email log use), a category, a one-sentence description for the screen, and the roles that may receive it (a system administrator and a superuser always may). Labels in the email log read `Notification: <label>`, and `PURPOSE_LABELS` in `apps/mail/purposes.py` carries one entry per event, keyed `notification_<slug>`, after `dart_roster`.

| Slug | Label | Category | May receive |
| --- | --- | --- | --- |
| `signed_up` | Sign-up | Membership | account_admin, user_admin |
| `member_added` | Member added by an administrator | Membership | account_admin, user_admin |
| `became_friend` | Member became a friend | Membership | account_admin, user_admin |
| `became_member` | Friend became a member | Membership | account_admin, user_admin |
| `membership_paid` | Membership paid | Membership | account_admin, user_admin |
| `membership_granted` | Membership granted by an administrator | Membership | account_admin, user_admin |
| `membership_expired` | Membership expired | Membership | account_admin, user_admin |
| `auto_renewal_on` | Automatic payment turned on | Money | treasurer, account_admin |
| `auto_renewal_off` | Automatic payment turned off | Money | treasurer, account_admin |
| `auto_renewal_declined` | Automatic payment declined | Money | treasurer, account_admin |
| `donation_received` | Donation received | Money | treasurer, account_admin |
| `payment_recorded` | Payment recorded by hand | Money | treasurer, account_admin |
| `payment_refunded` | Payment refunded | Money | treasurer, account_admin |
| `account_deactivated` | Account deactivated | Accounts | user_admin, account_admin |
| `account_reactivated` | Account reactivated | Accounts | user_admin, account_admin |
| `roles_changed` | Roles changed | Accounts | user_admin, account_admin |
| `email_changed` | Email address changed | Accounts | user_admin, account_admin |
| `profile_changed` | Profile changed | Accounts | user_admin, account_admin |
| `aircraft_added` | Aircraft added | Aircraft | account_admin |
| `aircraft_changed` | Aircraft changed | Aircraft | account_admin |
| `aircraft_removed` | Aircraft removed | Aircraft | account_admin |

"Automatic payment" covers both an automatic renewal and a recurring donation; the email says which.

### 5.3 Where each event is raised, and what its email says

Every email has a subject `<org name>: <headline>`, a headline, a few labeled lines, and one link, rendered from one template pair `emails/notification.{txt,html}` (HTML on `report_base.html`) with the purpose `notification_<slug>`. Names are the account's display name; a kind is Member or Friend; money is `money_label(cents)`; a date is `YYYY/MM/DD`. The link is `settings.SITE_URL` plus a portal route: the member record `/portal/admin/members/<id>` for a member or friend, the user record `/portal/admin/users/<id>` for an account event, the payment `/portal/admin/payments/<id>`, the aircraft `/portal/admin/aircraft/<id>`. The payload names below are the keyword arguments to `emit`.

| Slug | Raised in | Payload | Headline and lines |
| --- | --- | --- | --- |
| `signed_up` | `members/services.py` `register_member`, after the account is saved (also `upgrade_donor` in `accounts/services.py` when a donor joins) | `user`, `dart` (or `None`) | *<name> signed up as a <kind>*; Email, DART, Joined as; link to the member record. Also sent to `dart.roster_recipients()` (§5.4). |
| `member_added` | `members/services.py` `create_member` | `user`, `actor` | *<name> was added by <actor>*; Email, Kind, DART; member record |
| `became_friend` | `members/services.py` `become_friend` when the account becomes a friend at once, `convert_due_friends` for each converted account, `accounts/services.py` `update_account` when an administrator sets kind to friend | `user`, `how` (`chose`, `lapsed`, `administrator`) | *<name> is now a friend*; Email, How (chose to be a friend, membership lapsed, changed by an administrator); member record |
| `became_member` | `members/services.py` `activate_term` when `set_kind` returns True, `update_account` when an administrator sets kind to member | `user`, `how` (`paid`, `granted`, `administrator`) | *<name> is now a member*; Email, How; member record |
| `membership_paid` | `payments/services.py` `_complete`, when the payment activated or extended a term | `payment`, `term`, `automatic` (bool) | *<name> paid for membership through <date>* (or *renewed automatically*); Plan, Amount, Paid through, Contribution (when any); payment record |
| `membership_granted` | `members/api/admin_views.py` `MemberMembershipGrantView` calls a service in `members/services.py` `grant_term` (extracted if the view does the work today) | `user`, `term`, `actor` | *<actor> granted <name> membership through <date>*; Plan, Through; member record |
| `membership_expired` | `members/services.py` `expire_lapsed_memberships`: select the affected accounts before the bulk update, then one event per account | `user`, `term` | *<name>'s membership expired on <date>*; Email, Kind now; member record |
| `auto_renewal_on` | `payments/renewals.py` `save_method` when the mandate becomes active | `mandate` | *<name> turned on automatic <renewal or donation>*; Plan or Amount, Cadence, Next charge; member record |
| `auto_renewal_off` | `renewals.py` `cancel_mandate` and `_abandon` | `mandate`, `how` (`member`, `administrator`, `lapsed`, `deactivated`) | *<name>'s automatic <renewal or donation> is off*; How; member record |
| `auto_renewal_declined` | `renewals.py` `_record_failure` | `mandate`, `reason` | *<name>'s automatic <renewal or donation> was declined*; Reason, Next try; member record |
| `donation_received` | `payments/services.py` `_complete` for a public donation, a contribution-only payment, or a recurring donation charge; a membership payment with a contribution raises `membership_paid` alone | `payment` | *<name or donor name> gave <amount>*; From, Amount, Kind (one-time or recurring); payment record |
| `payment_recorded` | `payments/manual.py` `record_manual_payment` | `payment`, `actor` | *<actor> recorded a payment of <amount> for <name>*; Method, For; payment record |
| `payment_refunded` | `payments/refunds.py` where the refund is final (`issue_refund` and `record_dashboard_refund`) | `payment`, `refund_cents`, `actor` (or `None` for the provider dashboard) | *<amount> refunded to <name>*; Of, By, Membership canceled (when it was); payment record |
| `account_deactivated` | `accounts/services.py` `deactivate_own_account` and `update_account` on `ACCOUNT_DEACTIVATE` | `user`, `actor` (or `None` for self) | *<name>'s account was deactivated*; By; user record |
| `account_reactivated` | `reactivate_own_account` and `update_account` on `ACCOUNT_ACTIVATE` | `user`, `actor` | *<name>'s account was reactivated*; By; user record |
| `roles_changed` | `update_account` when roles were added or removed | `user`, `added`, `removed`, `actor` | *<actor> changed <name>'s roles*; Added, Removed, Now; user record |
| `email_changed` | `accounts/services.py` where the changed address is confirmed | `user`, `old_email` | *<name> changed their email address*; From, To; user record |
| `profile_changed` | `members/api/profile_serializers.py` `ProfileSerializer.update` and `members/services.py` `update_member`, with the labels of the fields that changed; a change that touched nothing raises nothing | `user`, `fields`, `actor` (or `None` for self) | *<name>'s profile changed*; Changed (the field labels), By; member record |
| `aircraft_added` / `aircraft_changed` / `aircraft_removed` | `aircraft/api/views.py` through a service in `aircraft/services.py` (extracted if the view writes the change today) | `aircraft` (for removed: `n_number`, `owner`), `fields` (changed), `actor` | *<N-number> added for <owner>*, *changed*, *removed*; Make and model, Changed; aircraft record (none for removed) |

A hook raises its event exactly once per occurrence, after the change is saved, inside the same transaction. The hooks package proves each with a test that subscribes a recording handler through `caldart.events` and asserts the slug and payload.

### 5.4 Who receives an event

- `NotificationSubscription` (`apps/notifications/models.py`, `TimestampedModel`): `recipient_user` (FK to the user, null, `SET_NULL`, related name `notification_subscriptions`), `recipient_email` (unique, stored lowercased), `events` (JSON list of slugs, in catalog order), `is_active` (default True), `created_by` (FK, null, `SET_NULL`). Ordering by `recipient_email`. `__str__` is `<email>: <n> events`.
- Binding as report subscriptions do: an address an account holds (compared without regard to case) binds the subscription to that account, and every chosen event must be one a role of that account may receive, else the request fails with `NOT_PERMITTED_MESSAGE` under `events` naming the first refused event: `<name> does not hold a role that may receive <label>.` An address no account holds needs `confirmed: true`, else `CONFIRM_MESSAGE` under `confirmed`: `Tick the box to confirm this address may receive these notifications.` A bare address is bound to whatever account later takes it, checked at send time as reports do (`refresh_recipient`).
- At send time an event goes to a subscription only when it is active, lists the event, and `recipient_may_receive(subscription, slug)`: a bare address always may; a bound account must be active and hold a role the event allows. An account that may not is skipped for that event and nothing is paused; a `PATCH` that would activate or add an event the account may not receive is refused as above.
- `signed_up` goes, in addition, to every address in `dart.roster_recipients()` when the person chose a DART, whether or not it is subscribed, once per address.
- Sending: one `send_templated` per recipient with `purpose="notification_<slug>"`, `user_id` of the bound account, and `to_name`. A failed send is logged and recorded by the email log, and the next recipient is still tried; the request that raised the event never fails because a notification did.

### 5.5 The API

All under `IsAccountAdmin`; a system administrator passes as always. Documented in `docs/developer/api-notifications.rst` with bodies and status lists, and in the permission matrix of `docs/developer/api-reference.rst`.

- `GET /notifications/events` → `[{slug, label, category, description, roles}]` in catalog order.
- `GET /notifications/subscriptions` → the list; `POST` with `{recipient_email, events, confirmed?}` → 201 the subscription; 400 keyed `recipient_email` (invalid or already subscribed: `This address already has a subscription.`), `events` (empty, unknown slug, or not permitted), or `confirmed`.
- `GET | PATCH | DELETE /notifications/subscriptions/{id}`; `PATCH` takes `events` and `is_active`; 204 on delete.
- The subscription body: `id, recipient_user, recipient_name, recipient_email, events, is_active, created_by_name, created_at, updated_at`.

### 5.6 The screen, the seed, and the docs

- **Screen.** `/admin/notifications`, **Notifications**, under Administration in `nav.ts` for `account_admin`, lazy route in `routes/admin-notifications.tsx`, help slug `admin/notifications` in `help.ts` and its test. A card headed *Who hears about what* lists subscriptions one per line: Recipient (name, or the bare address), Events (the labels joined with commas, cut with an ellipsis and the full list in the cell's `title`), Active (a dot), and the controls Edit, Pause or Resume, and the trashcan. **New subscription** opens the form under the table: Recipient email, then the events as checkboxes grouped under the four category headings with each description as the box's `title`, **Select all** and **Clear** per group, Save and Cancel. The outside-address tick appears when the server asks for it, as the report form does. Edit shows the recipient as plain text and edits the events. Errors show under their field. With none the table reads *Nobody is subscribed to a notification yet*.
- **Seed** (`apps/notifications/seed.py`, added to `SEED_APPS` after reports): the seeded account administrator subscribed to every Membership and Accounts event, the seeded treasurer to every Money event.
- **User guide.** `docs/user/admin/notifications.rst` (new, in `admin/index.rst` after `reports`): what a notification is, the screen, setting one up and changing it, who may receive what, and one short narrative entry per event saying when it goes and what it says, each naming the event's email-log label *Notification: <label>* so the purpose test is satisfied. `docs/user/admin/system.rst#purposes` lists the notification purposes in the email log's Purpose filter entry as *Notification: Sign-up through Notification: Aircraft removed*. `docs/user/roles.rst` names the screen under account administrator. `docs/user/admin/darts.rst` says a contact who receives the roster also hears of each sign-up for that DART.
- **Developer guide.** `docs/developer/notifications.rst` (new, in the developer toctree after `scheduled-reports`): the event mechanism, the recipient rule, sending, the model, testing; `docs/developer/notification-events.rst` (new, right after it): the catalog table with where each event is raised and what its email carries; `docs/developer/api-notifications.rst`; `docs/developer/email.rst` "What the site sends" gains the notification row(s); `docs/developer/data-model.rst` gains the `NotificationSubscription` section with every field and the model in the subscriptions diagram (graphviz and ASCII together, under 1000pt); `docs/developer/architecture.rst` names the screen and the app; `docs/developer/setup.rst` or wherever the seed's contents are listed, the two seeded subscriptions.

### 5.7 The skeleton the plan PR lands

- `backend/caldart/events.py`: `EVENT_SLUGS`, `emit`, `subscribe`, `Handler` type, with `backend/tests/test_events.py`.
- `backend/apps/notifications/`: `__init__.py`, `apps.py` (`NotificationsConfig`, `ready()` importing `.dispatch` and subscribing `dispatch.handle`), `events.py` (the §5.2 catalog as `Event` frozen dataclasses in `EVENTS`, keyed by slug, plus `CATEGORIES`), `dispatch.py` with `handle(slug, payload)` that does nothing yet, `api/__init__.py`, `api/urls.py` with `app_name = "notifications"` and empty `urlpatterns`, `migrations/__init__.py`. Registered in `LOCAL_APPS` after `apps.reports`, included in `caldart/api_urls.py` after reports, and placed on layer 5 in `test_app_layering.py`. `backend/tests/test_notification_catalog.py` asserts the catalog's slugs equal `EVENT_SLUGS` in order and every event has a label, category, description, and roles.

## 6. Failure handling and the final report

A package that cannot finish reports the reason under `open_problems`; the orchestrator decides whether to fix, re-run, or reduce. The closeout's PR body lists the owner's sentence and the PR that settled each part of it, and the orchestrator's report to the owner does the same.

## 7. Work packages

### Wave 1

#### notifications-backend (Opus, reviewed)

- **Refs:** #268
- **Branch:** `feature/notifications-backend`; database `caldart_notifications_backend`; e2e port 8241
- **Owns:** `backend/apps/notifications/**` except `events.py` and `api/urls.py#app-name` (it fills `urlpatterns`), `backend/apps/mail/purposes.py#notifications`, `backend/templates/emails/notification.{txt,html}`, `backend/apps/accounts/management/commands/seed_demo.py#seed-apps`, `backend/tests/test_notifications.py` (new), `backend/tests/test_notification_sending.py` (new), `backend/tests/test_notification_api.py` (new), `backend/tests/test_seed.py#notifications`, `backend/tests/snapshots/**`, `frontend/src/portal/api/types.ts#notifications`, `frontend/src/portal/api/types.contract.test.ts#notifications`, `docs/developer/notifications.rst` (new), `docs/developer/api-notifications.rst` (new), `docs/developer/index.rst#toctree` (both new pages), `docs/developer/api-reference.rst#matrix`, `docs/developer/email.rst#notifications`, `docs/developer/data-model.rst#notifications`, `docs/user/admin/system.rst#purposes`, `docs/developer/setup.rst#seed` (or the page that lists the seed).
- **Steps:** §5.4, §5.5, the seed and the developer pages of §5.6, and the email template of §5.3 (the per-event headline and lines are built in `apps/notifications/messages.py` from the payloads §5.3 names; a test per event renders it from factory objects).
- **Verify:** `make test`; `make lint`; after `make reset`, `GET /api/v1/notifications/subscriptions` as the seeded account administrator lists the two seeded subscriptions; `emit("signed_up", user=..., dart=...)` in a shell sends one email per subscribed and roster address, recorded with purpose `notification_signed_up`.

#### notifications-hooks (Opus, reviewed)

- **Refs:** #268
- **Branch:** `feature/notifications-hooks`; database `caldart_notifications_hooks`; e2e port 8242
- **Owns:** the `emit` call sites §5.3 names in `backend/apps/{accounts,members,payments,aircraft}/**` (each a `#hooks` section: add the call and, where the plan says so, extract a service function the view calls), `backend/tests/test_notification_hooks.py` (new), `docs/developer/notification-events.rst` (new), `docs/developer/index.rst#toctree-events` (that one page, placed right after `notifications`), and the existing developer pages that describe those services only where a sentence saying "raises the `<slug>` event" belongs (`#hooks` sections of `docs/developer/{membership,payments,renewals,accounts,aircraft}.rst` or however those pages are named).
- **Steps:** §5.3 in full: every event raised exactly once, at the point named, with the payload named. The dispatcher is the skeleton's no-op, so the tests subscribe a recording handler.
- **Verify:** `make test e2e`; `make lint`; a `grep -rn "emit(" backend/apps` lists one call per row of §5.3's table (`became_friend`, `became_member`, `auto_renewal_off`, `account_*` have the several call sites the table names).

#### notifications-ui (Opus, reviewed)

- **Refs:** #268
- **Branch:** `feature/notifications-ui`; database `caldart_notifications_ui`; e2e port 8243
- **Owns:** `frontend/src/portal/features/admin-notifications/**` (new), `frontend/src/portal/routes/admin-notifications.tsx` (new), `frontend/src/portal/routes/index.tsx#notifications`, `frontend/src/portal/nav.ts#notifications`, `frontend/src/portal/help.ts#notifications`, `frontend/src/portal/help.test.ts#notifications`, `frontend/src/test/handlers.ts#notifications`, `docs/user/admin/notifications.rst` (new), `docs/user/admin/index.rst`, `docs/user/roles.rst#notifications`, `docs/user/admin/darts.rst#sign-ups`, `docs/developer/architecture.rst#notifications`.
- **Steps:** the screen and the user pages of §5.6, built against §5.5 as the contract with msw handlers; the API types come from the backend package, so this package declares its own copies in `features/admin-notifications/types.ts` only if the backend PR has not merged when it starts, and the closeout removes the copies in favor of `api/types.ts`.
- **Verify:** `make test`; `make lint`; `npm run test -- help` green; the user page satisfies `test_docs_user.py` including every `Notification: <label>` label (assert by running `uv run pytest backend/tests/test_docs_user.py` against the merged purposes, or against the labels of §5.2 if the backend has not merged).

### Wave 2

#### notifications-e2e (Opus, reviewed)

- **Refs:** #268
- **After:** notifications-backend, notifications-hooks, notifications-ui
- **Branch:** `feature/notifications-e2e`; database `caldart_notifications_e2e`; e2e port 8244
- **Owns:** `frontend/e2e/notifications.spec.ts` (new), `frontend/e2e/helpers.ts#notifications` (additive), `frontend/src/portal/features/admin-notifications/types.ts` (deletes it if the ui package left one), `frontend/src/portal/features/admin-notifications/**#types`, `docs/demo-walkthrough.rst#notifications`.
- **Steps:** as the seeded account administrator, subscribe an outside address to Sign-up and Friend became a member, ticking the confirmation; register a new friend through the public join flow choosing a DART; read the sign-up email at the outside address and at the DART's roster contact with `latestEmailTo`; edit the subscription to drop Sign-up; deactivate the seeded member as the user administrator and confirm no email went to the address; the demo walkthrough gains the notifications step.
- **Verify:** `make e2e`; `make lint test`.

### Wave 3

#### closeout (Sonnet)

- **Closes:** #268
- **After:** notifications-e2e
- **Branch:** `chore/notifications-closeout`; database `caldart_notifications_closeout`; e2e port 8245
- **Owns:** `docs/**#residue`, `frontend/src/**#residue`, `backend/**#residue`, `plans/2026-09-26-notifications.md` (moves to `plans/archive/`).
- **Steps:** on `main` after `make reset`, run the owner's sentence end to end: subscribe an address to every event on the screen, then cause a sign-up, a friend becoming a member by paying (mock provider), an expiry (`send_renewal_reminders --today` past a seeded term), a donation, an automatic renewal (`run_auto_renewals --today`), a refund, a deactivation, and an aircraft change, and read one email per event in Mailpit with the right purpose in the email log; read every docs page the packages touched once more against the running portal; act on the residue notes in §9 and later; move the plan to the archive. The PR body lists the events and the PR that settled each.
- **Verify:** `make lint test check docs audit e2e` green.

## 8. Manifest

```json
[
  {"wave": 1, "package": "notifications-backend", "model": "opus", "review": true, "branch": "feature/notifications-backend", "database": "caldart_notifications_backend", "e2e_port": 8241, "closes": [], "refs": [268], "after": []},
  {"wave": 1, "package": "notifications-hooks", "model": "opus", "review": true, "branch": "feature/notifications-hooks", "database": "caldart_notifications_hooks", "e2e_port": 8242, "closes": [], "refs": [268], "after": []},
  {"wave": 1, "package": "notifications-ui", "model": "opus", "review": true, "branch": "feature/notifications-ui", "database": "caldart_notifications_ui", "e2e_port": 8243, "closes": [], "refs": [268], "after": []},
  {"wave": 2, "package": "notifications-e2e", "model": "opus", "review": true, "branch": "feature/notifications-e2e", "database": "caldart_notifications_e2e", "e2e_port": 8244, "closes": [], "refs": [268], "after": ["notifications-backend", "notifications-hooks", "notifications-ui"]},
  {"wave": 3, "package": "closeout", "model": "sonnet", "review": false, "branch": "chore/notifications-closeout", "database": "caldart_notifications_closeout", "e2e_port": 8245, "closes": [268], "refs": [], "after": ["notifications-e2e"]}
]
```
