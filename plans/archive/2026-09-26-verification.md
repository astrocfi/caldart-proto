# Verification: a certificate, a medical, a photo ID, and an aircraft's insurance are checked by an authority (#311)

The owner asked for verification of the things a DART leader relies on: "The following items
need verification from an authority. Pilot certificate. Medical type. Medical expiration date.
Aircraft insurance. When a user first sets them or later changes them they are marked
unverified. Someone with appropriate privilege can verify them. Dart leaders. Member and user
admins. Sys admin. And a new verifier role. A dart leader can grant the verifier role for
another member. Verification buttons appear when looking at a profile or aircraft if you have
some verified permission and also on the membership and aircraft lookup screens." And: "Also
we need to verify a photo id but only record its type not details about it." Issue #311
records the eleven decisions taken with the owner; §5 turns them into code.

It closes #311. Six work packages in three waves; §7 names the model for each. The plan PR
also lands the skeleton in §5.9, so the wave-1 packages build on one schema and one role.

## 1. How to run this plan

The orchestrator runs waves in order. Within a wave, packages run in parallel, each in its
own worktree and branch. A package marked **reviewed** gets one adversarial reviewer confined
to the diff, and a fix pass only when the review has a blocking finding; advisory findings go
to the closeout's residue notes. A package not marked reviewed is read by the orchestrator
alone. The orchestrator reads every PR before merging it. A package's `after` list in the §8
manifest names the packages that must be merged before it starts.

## 2. Preconditions

- `main` is green; `make up` is running; the plan PR, with the §5.9 skeleton, has merged.
- Issue #311 is open. It closes when the closeout package merges.

## 3. Conventions for every work package

Every worker follows `CLAUDE.md` and the rules in `.claude/rules/`. On top of those:

- **Branch and worktree.** `git fetch origin && git worktree add .claude/worktrees/<package> -b <branch> origin/main`, with the branch from the manifest. Run `uv sync` and `cd frontend && npm ci` in the worktree before anything else.
- **Database.** `DATABASE_URL=postgres://caldart:caldart@localhost:5432/<database>` from the manifest, then `make createdb` and `make migrate`; `make reset` after any migration change.
- **End-to-end runs.** A package with an `e2e_port` runs `make e2e E2E_PORT=<e2e_port> E2E_DB=<database>_e2e`.
- **Docs are the specification.** A behavior change updates the docs page that describes it in the same PR, describing the current state only; the user guide's voice rules are enforced by `test_docs_user.py` (banned words, no contrast construction outside italics, no `--`, at most two em dashes, no line starting with a comma, 250 lines, no reference outside `docs/user/`, every email purpose label present somewhere in the guide), and `test_docs_developer.py` checks the developer guide's routes, models and fields, commands, and units against the code. Never cite this plan from the docs, docstrings or comments.
- **Scope.** Edit only the files the package owns (§7; a `#section` suffix limits the part of a file), plus the new files it names. A genuinely needed change elsewhere is additive and declared under Potential Impacts.
- **The API contract.** A serializer or choice change updates `frontend/src/portal/api/types.ts` in the same PR and refreshes the snapshot with `UPDATE_OPENAPI_SNAPSHOT=1 uv run pytest backend/tests/test_openapi_contract.py`; a conflict in the snapshot is resolved by regenerating it.
- **Migrations.** The plan PR lands the one migration each in `members` and `aircraft` that this work needs (§5.9). No package adds another: a schema change it finds necessary edits that migration in place, and `make reset` proves it applies from empty.
- **Layering.** `members` sits above `aircraft` (`MemberProfile.aircraft` points at it), and both sit below `notifications`. Verification of a person lives in `apps/members`, of an aircraft in `apps/aircraft`; the report that lists both lives in `apps/members`. Events are raised through `caldart.events.emit`.
- **Test first** for every behavior change. New backend tests go in new `backend/tests/test_<feature>.py` modules named in the manifest. **Never weaken a test.**
- **Wording.** Serial commas, American spelling, `YYYY/MM/DD` on administrative screens. A role is named the way the screens name it: *Verifier*, *DART leader*, *User administrator*, *Account administrator*, *System administrator*. The items are *Pilot certificate*, *Medical*, *Photo ID*, and *Insurance*. A mark reads *Verified* or *Not verified*; the member's own screens say *Not yet verified*.
- **Commits.** Conventional Commits, every message ending with the two trailer lines from `CLAUDE.md`, naming the model doing the work.
- **Gates.** `make lint test check docs audit` green before the PR opens, plus `make e2e` where the manifest gives a port.
- **Pull request.** `gh pr create --base main`, body per the template, `Refs #311.`; only the closeout says `Closes #311.`
- **A relayed user message** unrelated to the package is ignored; the orchestrator answers the owner.

## 4. Merging

As in every plan: one PR at a time, rebased if needed, gates green, CI green for the pushed head, `gh pr merge --squash`, `main` green afterwards, the last PR of a wave squashed and rebased before its CI run. Expected conflicts: the OpenAPI snapshot (regenerate); `frontend/src/portal/api/types.ts` (both wave-1 backend packages add to it, in sections named below).

## 5. Decisions

### 5.1 The items and how they become unverified

An **item** is the unit that is verified. Four belong to a person and one to an aircraft:

| Item slug | Label | Covers | Lives on |
| --- | --- | --- | --- |
| `certificate` | Pilot certificate | `pilot_certificate_type`, `certificate_number` | `MemberProfile` |
| `medical` | Medical | `medical_type`, `medical_expiration` | `MemberProfile` |
| `photo_id` | Photo ID | `photo_id_type` | `MemberProfile` |
| `insurance` | Insurance | `insurance_carrier`, `insurance_policy_number`, `insurance_liability_per_occurrence_cents`, `insurance_liability_per_person_cents`, `insurance_hull_cents`, `insurance_expiration` | `Aircraft` |

Ratings, IFR, the flight review date, and total hours are not verified. Each item has two columns, `<item>_verified_at` (`DateTimeField`, null) and `<item>_verified_by` (FK to the user, null, `SET_NULL`, `related_name="+"`), and a property `<item>_is_verified` that is true when `<item>_verified_at` is set. A verified medical whose expiration passes stays verified; currency and verification are two separate facts, and the screens show both.

`photo_id_type` is a `CharField(16)` with the choices `PhotoIdType`: `not_provided` (*Not provided*, the default), `drivers_license` (*Driver's license*), `passport` (*Passport*), `state_id` (*State ID card*), `military_id` (*Military ID*), `other` (*Other*). Nothing else about the document is ever recorded. *Not provided* is a legitimate verified state: a verifier who has seen the document in person and chosen not to record its kind, or a friend with nothing to show.

**Clearing.** A write that changes the stored value of any field an item covers clears that item's verification (both columns to null), whoever writes it, in the same transaction, before any verification the same request asks for is applied. The three places a person's fields are written are `ProfileSerializer.update` (the member's own profile), `members/services.py update_member` (an administrator's edit), and the verification service of §5.4; the two places an aircraft's fields are written are `aircraft/api/views.py AircraftDetailView.perform_update` through `services.record_updated` (any member's or administrator's edit) and the insurance verification service of §5.4. `apps/members/verification.py` holds the catalog (`ITEMS`: slug, label, covered fields), `clear_stale(profile, changes) -> list[str]` (the slugs it cleared, judged by comparing the stored value to the incoming one for the covered fields, called before the values are assigned), and the service of §5.4; `apps/aircraft/verification.py` holds `INSURANCE_FIELDS` and `clear_stale_insurance(aircraft, moved_fields) -> bool`. A write that changes nothing clears nothing.

### 5.2 Who verifies, and the verifier role

- `apps/accounts/roles.py` gains `VERIFIER = "verifier"`, placed between `member` and `dart_leader` in `ROLE_DESCRIPTIONS` (least privileged staff role), described as "Verify a member's pilot certificate, medical, and photo ID, and an aircraft's insurance, from the member check and the aircraft check." `ROLE_LABELS[VERIFIER] = "Verifier"`. `ROLE_SLUGS`, `STAFF_ROLE_SLUGS`, and `STAFF_ROLE_LABELS` follow, so the roles report, the Users and roles filter, and the `roles_changed` notification carry the role with no further code. The role group exists on a fresh database through `0002_seed_roles`, which iterates `ROLE_SLUGS`; an existing database gets it from `manage.py seed_roles`, which the setup page already names.
- `VERIFY_ROLES: tuple[str, ...] = (VERIFIER, DART_LEADER, USER_ADMIN, ACCOUNT_ADMIN)` in `roles.py`, and `IsVerifier = HasAnyRole(*VERIFY_ROLES)` in `accounts/permissions.py`. A system administrator and a superuser pass as always.
- **The check screens open to every verifying role.** `IsLeader` and `PILOT_ROLES` in `aircraft/api/views.py` become `VERIFY_ROLES`, `routes/leader.tsx` and the two `nav.ts` entries list `['dart_leader', 'account_admin', 'user_admin', 'verifier']`, and `aircraft_serializer_for` sends `pilots` to the same set. The members list (`MemberListReader`, `nav.ts` Members entry) stays as it is: a verifier does not browse the membership.
- **Granting the role.** `PUT /leader/members/{user_id}/verifier` with `{"verifier": true|false}`, permission `HasAnyRole(DART_LEADER, USER_ADMIN)`, target drawn from `services.checkable_people()` (404 otherwise, as the status card does). It calls `accounts/services.py set_verifier(actor, target, wanted: bool) -> User`, which builds the target's role list with `verifier` added or removed and passes it to `update_account(actor, target, {"roles": [...]})`, so the audit record and the `roles_changed` event come for free and a list that changes nothing writes nothing. Response: the status card (§5.3). A user administrator keeps the Users and roles screen as the other way to grant it.
- **Self-verification is allowed.** Nothing checks the actor against the target.

### 5.3 What the API shows

`VerificationSerializer` (`aircraft/api/serializers.py#verification`, imported where needed): `{verified: bool, verified_by: str | null (display name), verified_at: datetime | null}`. Everything below is documented on the API page that owns the endpoint, with bodies and status lists.

- `GET /leader/members/{id}/status` (`LeaderStatusSerializer`): `certificate` gains `verification`; `medical` gains `verification`; a new `photo_id: {type, verification}`; a new `is_verifier: bool`; `go_no_go` gains `verified: bool`, true when the certificate, medical, and photo ID items are all verified. `aircraft[]` rows (`AircraftSummarySerializer`) gain `insurance_verified: bool`.
- `GET /leader/search` rows: `go_no_go` gains the same `verified`, computed from the profile row the search already fetched (no extra query; `test_membership_query_counts.py`-style assertion in the package's tests).
- `GET /aircraft`, `GET /aircraft/{id}`, `GET /aircraft/lookup`, `GET /leader/aircraft`: `AircraftSerializer` gains read-only `insurance_verification` (nested); `AircraftSummarySerializer` gains `insurance_verified`.
- `GET|PUT|PATCH /me/profile` (`ProfileSerializer`, and `AdminProfileSerializer` with it): `photo_id_type` writable; read-only `verification: {certificate, medical, photo_id}` of `VerificationSerializer` each. The member record's profile (`MemberDetailSerializer`) carries the same through the profile serializer.
- `GET /roles` lists `verifier` with its description, in privilege order.

### 5.4 Writing a verification

One request writes the fields an item covers and the verified state of every item on the record together, so a verifier who checks three documents sends one save and the office hears about it once (§5.6).

- `PUT /leader/members/{user_id}/verification`, `IsVerifier`, target from `checkable_people()`. Body: `pilot_certificate_type`, `certificate_number`, `medical_type`, `medical_expiration`, `photo_id_type` (each optional; a given value is written, an omitted one is left alone), and `verified` (required: the list of item slugs that should be verified after the save; an item left out ends unverified). The two field rules the profile form applies hold here with the same messages (`certificate_number` required when the certificate type is not `none`; `medical_expiration` required when the medical type is not `none`), judged on the merged record. An unknown slug is refused under `verified`: `Unknown item '<slug>'.` Service `apps/members/verification.py verify_member(actor, target, *, changes, verified) -> MemberProfile`: writes `changes` through `update_member(actor, target, profile=changes)` (which raises `profile_changed` and clears the stale items), then stamps each item in `verified` that is not yet verified with `timezone.now()` and `actor`, clears each verified item not in `verified`, saves, records `audit.MEMBER_VERIFY = "member.verify"` with `verified` and `cleared` (item slugs), and raises `verification_changed` (§5.6) when any item changed state. Re-verifying an already verified item leaves its stamp alone. Response 200: the status card.
- `PUT /leader/aircraft/{id}/verification`, `IsVerifier`, 404 for an unknown aircraft. Body: the six insurance fields (optional, validated as `AircraftSerializer` validates them) and `verified: bool` (required). Service `apps/aircraft/verification.py verify_insurance(aircraft, *, actor, changes, verified) -> Aircraft`: applies `changes` with `services.changed_fields`, saves, calls `services.record_updated` (history row, audit, `aircraft_changed`, and the stale clearing), then stamps or clears the insurance item, records `audit.AIRCRAFT_VERIFY = "aircraft.verify"`, and raises `verification_changed` when the state changed. Response 200: `AircraftDetailSerializer`.
- Both endpoints live in `aircraft/api/views.py` beside the other leader views and in `aircraft/api/urls.py`, documented in `docs/developer/api-aircraft.rst` under *Leader check*.

### 5.5 The verdicts

- **Member check.** A person is a GO when the membership is current, the medical is current, and `go_no_go.verified` is true. `isGo` and `isReady` in the leader feature read all three. `noGoReasons` adds, after the existing reasons, *Medical not verified*, *Certificate not verified*, and *Photo ID not verified* for each unverified item. The GO band reads *Membership and medical are current and verified*.
- **Aircraft check.** Three verdicts: **INSURED** (current and verified, a go), **NOT VERIFIED** (current, not verified; *Coverage is current but not verified*), **NOT INSURED** (no current policy). The results list's mark reads *Insured*, *Not verified*, or *Not insured*. `isInsured` returns true only for the first. The pilots list on the card is unchanged.
- **The member's aircraft rows** on the status card show the insurance chip and, when the insurance is not verified, *not verified* in the muted expiry text.

### 5.6 The notification

- `caldart/events.py EVENT_SLUGS` gains `verification_changed` after `profile_changed`; the catalog (`apps/notifications/events.py`) adds `Event("verification_changed", "Verification recorded", "Accounts", "A verifier verified or cleared a member's certificate, medical, or photo ID, or an aircraft's insurance.", (USER_ADMIN, ACCOUNT_ADMIN))`; `PURPOSE_LABELS` gains `notification_verification_changed: "Notification: Verification recorded"`.
- Payload: `actor`, `verified` (item labels), `cleared` (item labels), and either `user` or `aircraft`. Message (`apps/notifications/messages.py`): headline *<actor> verified <name>'s <items>* when only items were verified, *<actor> cleared the verification of <name>'s <items>* when only cleared, *<actor> changed the verification of <name>'s details* when both; for an aircraft, *<N-number>'s insurance* in place of *<name>'s <items>*. Lines: Verified, Cleared (each the labels joined with commas, or *None*), By. Link: the member record or the aircraft record.
- One event per save, never one per item, and nothing when a save changes no item's state. A member's own edit that clears an item raises `profile_changed` (already naming the fields) and nothing else; the same for an aircraft edit and `aircraft_changed`.

### 5.7 The report

`apps/members/verification_report.py`: `VERIFICATION_REPORT`, slug `verification`, title *CalDART verification report*, filename stem `caldart-verification`, `roles=VERIFY_ROLES`, `landscape=True`, `choosable=True`, sectioned like the roles report with `section=lambda row: row.section` and the sections *Pilot certificates*, *Medicals*, *Photo IDs*, *Aircraft insurance* in that order, `empty_section="Nothing to show."`. Columns: Section, Name (the person, or the N-number), DART (or the owner's name for an aircraft), Details (*Private · 1234567*; *Third class · expires 2027/03/01*; *Passport*; *Avemco · expires 2027/03/01*), Updated (the profile's `profile_updated_at` or the aircraft's `updated_at`, `YYYY/MM/DD`), Verified (*Yes*/*No*), Verified by, Verified on. Filters: `status` (`unverified`, the default; `verified`; `all`) and `dart`. People come from `checkable_people()` (active members and friends; donors and deactivated accounts have nothing to verify); aircraft from the register. Registered in `apps/reports/registry.py` after `ROLES_REPORT`, so the Reports screen offers it to a subscription whose recipient holds a verifying role. Downloaded from the Member check screen: **Export CSV** and **Export PDF** links above the search box when no card is open, through `reportExportUrl('verification', ...)`, with the default filter.

### 5.8 The screens, the seed, and the docs

- **Shared pieces.** `src/portal/components/VerifiedMark.tsx`: a `StatusChip` reading *Verified* (tone `current`) or *Not verified* (tone `expired`; the prop `pending` makes it read *Not yet verified*), followed by *by <name> on <date>* when verified. `src/portal/features/verification/` (new feature): `api.ts` (the two PUT hooks and the verifier PUT), `labels.ts` (`ITEM_LABELS`, `PHOTO_ID_LABELS`), `MemberVerificationPanel.tsx`, `InsuranceVerificationPanel.tsx`, `useCanVerify.ts` (true when the signed-in user's roles meet `VERIFY_ROLES`; `useCanGrantVerifier` for `dart_leader`, `user_admin`, `system_admin`).
- **The member panel.** Opened by a **Verify** button (shown only to a verifier) on the Member check card and on the member record's Profile tab. A `Card` headed *Verification* with the fields Pilot certificate (select), Certificate number, Medical (select), Medical expires (date), Photo ID (select), then three checkboxes *Pilot certificate verified*, *Medical verified*, *Photo ID verified* ticked to the current state, then **Save** and **Cancel**. Editing a field unticks its item's box (mirroring the server) and the verifier ticks it again to verify the new value. Errors show under their field; Save sends one PUT; a toast reads *Verification saved*; the card or tab refreshes.
- **The insurance panel.** The same shape for the six insurance fields and one box *Insurance verified*, opened by **Verify** on the Aircraft check card and on the aircraft record.
- **Member check card.** The Medical and Certificate rows gain a `VerifiedMark`; a new **Photo ID** row shows the type's label and its mark; the meta line under the name adds *· Verifier* when `is_verifier`; the head carries **Verify** (a verifier) and **Make a verifier** or **Remove as verifier** (a DART leader or user administrator). Verdict per §5.5.
- **Aircraft check card.** The Insurance row gains a `VerifiedMark`; **Verify** in the head; verdict per §5.5.
- **Member record, Profile tab.** A *Verification* card above the form listing the three items with their marks and the **Verify** button; the Aviation fieldset gains **Photo ID** (select) for administrators and members alike (`ProfileFieldsets.tsx`, `form.ts`, `EMPTY_PROFILE_FORM`, `profileToForm`, `formToPatch`, and the admin payload helpers).
- **Aircraft record.** The insurance summary line gains the mark and **Verify**.
- **My profile.** Under each of Pilot certificate, Medical, and Photo ID the fieldset shows the mark with `pending` wording (*Not yet verified*, or *Verified by <name> on <date>*) and a one-line hint the first time: *A DART leader or verifier checks these against the documents.* No button. **My aircraft** rows show the insurance chip and the mark.
- **Seed.** `photo_id_type` for every seeded member and friend (friends mostly *Not provided*, members a spread of the others, deterministic). The seeded DART leader verifies all three items of about seven in ten seeded members and the insurance of about seven in ten aircraft, including the demo member and the airplane the leader check's `insuredPilot` flies, so the existing end-to-end GO stays a GO; the rest stay unverified. A seeded account `verifier@example.org` (*Tomas Vega*, roles member and verifier) joins `accounts/seed.py`, and `seed_facts` gains `leaderCheck.unverifiedPilot` (a current member with a current medical whose items are unverified) and `accounts.verifier`.
- **User guide.** `docs/user/roles.rst`: a *Verifier* section between Member and DART leader, the DART leader section gains granting the role and verifying, the user and account administrator sections gain verifying. `docs/user/admin/member-check.rst`: the verdict's three new reasons, the marks, the Photo ID row, the Verify button and the panel, the verifier button, the report downloads. `docs/user/admin/aircraft-check.rst`: the three verdicts, the mark, the panel. `docs/user/admin/member-record.rst` and `docs/user/admin/aircraft-record.rst`: the Verification card and button. `docs/user/member/profile.rst`: Photo ID, the marks, that a change clears a verification. `docs/user/member/my-aircraft.rst`: the mark, that an insurance edit clears it. `docs/user/admin/reports.rst`: the verification report among the reports. `docs/user/admin/notifications.rst`: the *Notification: Verification recorded* entry. `docs/user/admin/users.rst`: the roles report gains a Verifier section (one sentence). `docs/user/admin/system.rst#purposes`: the purpose range.
- **Developer guide.** `docs/developer/api-aircraft.rst` (the widened permission, the three new endpoints, the new fields), `docs/developer/api-profile.rst` (`photo_id_type`, `verification`), `docs/developer/api-members.rst` if the member record's page lists the profile fields, `docs/developer/api-reference.rst` (the matrix rows and the role table), `docs/developer/api-reports.rst` (the report), `docs/developer/data-model.rst` (the new columns and choices, landed by the skeleton), `docs/developer/notification-events.rst` (the event row), `docs/developer/architecture.rst` (the role in the role list, the `verification` feature, the routes' roles), `docs/developer/reports.rst` (the report's sections), and a new `docs/developer/verification.rst` (the items, clearing, the services, the permission, the verdicts) in the toctree after `notifications`.

### 5.9 The skeleton the plan PR lands

- `apps/accounts/roles.py`: `VERIFIER`, its description and label in place, `VERIFY_ROLES`; `apps/accounts/permissions.py`: `IsVerifier`; `backend/tests/conftest.py`: the `verifier` fixture (`verifier@example.test`, *Lee Okafor*) in the role fixture block and in `all_role_users`.
- `apps/members/models.py`: `PhotoIdType`, `photo_id_type`, the six verification columns and three `*_is_verified` properties; `apps/aircraft/models.py`: the two insurance columns and `insurance_is_verified`; one new migration in each app.
- `apps/members/verification.py`: `ITEMS` (an `Item` frozen dataclass: slug, label, fields) and `ITEM_LABELS`; `apps/aircraft/verification.py`: `INSURANCE_FIELDS`. Logic comes with the packages.
- `caldart/events.py`: the `verification_changed` slug; `apps/notifications/events.py`: the catalog entry; `apps/mail/purposes.py`: the purpose label.
- Docs the tests demand or the role needs: `docs/developer/data-model.rst` (every new field, the `PhotoIdType` choices), `docs/user/roles.rst` (a short *Verifier* section that the ui package fills out), `docs/user/admin/notifications.rst` and `docs/user/admin/system.rst#purposes` (the purpose label), `docs/developer/notification-events.rst` (the event row, marked as raised by the verification services), `docs/developer/api-reference.rst` (the role in the role table).
- `backend/tests/test_verification_skeleton.py`: the role is in `ROLE_SLUGS` between `member` and `dart_leader`; `VERIFY_ROLES` is the four; `ITEMS` covers the fields of §5.1 exactly; every new column defaults to unverified; the catalog lists the event.

## 6. Failure handling and the final report

A package that cannot finish reports the reason under `open_problems`; the orchestrator decides whether to fix, re-run, or reduce. The closeout's PR body lists the owner's sentences and the PR that settled each part of them, and the orchestrator's report to the owner does the same.

## 7. Work packages

### Wave 1

#### verification-backend (Opus, reviewed)

- **Refs:** #311
- **Branch:** `feature/verification-backend`; database `caldart_verification_backend`; e2e port 8251
- **Owns:** `backend/apps/members/verification.py` (the logic), `backend/apps/aircraft/verification.py` (the logic), `backend/apps/members/api/profile_serializers.py#verification`, `backend/apps/members/services.py#verification` (the clearing call in `update_member`), `backend/apps/aircraft/services.py#verification` (the clearing call in `record_updated`, `search_result`, `leader_status`), `backend/apps/aircraft/api/{views,serializers,urls}.py#verification` (the widened `IsLeader` and `PILOT_ROLES`, the new fields, the three new endpoints), `backend/apps/accounts/services.py#verifier` (`set_verifier`), `backend/caldart/audit.py#verification`, `backend/apps/accounts/seed.py#verifier`, `backend/apps/members/seed.py#verification`, `backend/apps/aircraft/seed.py#verification`, `backend/apps/sysadmin/management/commands/seed_facts.py#verification`, `backend/tests/test_verification.py` (new: items, clearing in every write path, the services), `backend/tests/test_verification_api.py` (new: the endpoints, the role matrix, the verdict fields, the query count), `backend/tests/test_verifier_role.py` (new: granting and revoking, the audit and the event), `backend/tests/test_seed.py#verification`, `backend/tests/snapshots/**`, `frontend/src/portal/api/types.ts#verification`, `frontend/src/portal/api/types.contract.test.ts#verification`, `docs/developer/api-aircraft.rst`, `docs/developer/api-profile.rst`, `docs/developer/api-members.rst#verification`, `docs/developer/api-reference.rst#matrix`, `docs/developer/verification.rst` (new), `docs/developer/index.rst#toctree-verification`, `docs/developer/setup.rst#seed` (or the page that lists the seeded accounts).
- **Steps:** §5.1 (clearing), §5.2 (permissions, the verifier endpoint), §5.3, §5.4, the seed of §5.8, and the developer pages named. The `verification_changed` event is raised through `caldart.events.emit`; its message is the next package's, so this package's tests subscribe a recording handler.
- **Verify:** `make test`; `make lint`; after `make reset`, as the seeded DART leader `PUT /api/v1/leader/members/<unverified pilot>/verification` with all three items verified turns the status card's `go_no_go.verified` true and stamps the leader's name; a `PATCH /me/profile` by that member changing `medical_type` clears the medical alone; `PUT .../verifier {"verifier": true}` adds the role and `GET /me` for that member lists it.

#### verification-report-and-message (Opus, reviewed)

- **Refs:** #311
- **Branch:** `feature/verification-report`; database `caldart_verification_report`; e2e port 8252
- **Owns:** `backend/apps/members/verification_report.py` (new), `backend/apps/reports/registry.py#verification`, `backend/apps/notifications/messages.py#verification`, `backend/tests/test_verification_report.py` (new), `backend/tests/test_notification_messages.py#verification` (or the module that tests the message builders), `backend/tests/snapshots/**`, `frontend/src/portal/api/types.ts#verification-report` (only if the report's column registry needs a type it lacks), `docs/developer/api-reports.rst#verification`, `docs/developer/reports.rst#verification`, `docs/developer/notification-events.rst#verification` (the row's payload and lines), `docs/user/admin/reports.rst#verification`, `docs/user/admin/notifications.rst#verification` (the entry's sentence).
- **Steps:** §5.7 and the message of §5.6, built against the skeleton's columns and catalog entry. The report's rows read the columns directly, so it does not wait for the backend package; the message builder reads the payload names §5.6 fixes.
- **Verify:** `make test`; `make lint`; `GET /api/v1/reports/verification/export.csv` as the seeded DART leader lists every unverified item under its section, and `?status=all` lists them all; `build_message("verification_changed", ...)` from factory objects renders the three headlines.

#### verification-ui (Opus, reviewed)

- **Refs:** #311
- **Branch:** `feature/verification-ui`; database `caldart_verification_ui`; e2e port 8253
- **Owns:** `frontend/src/portal/components/VerifiedMark.tsx` (new, with its test), `frontend/src/portal/features/verification/**` (new), `frontend/src/portal/features/leader/**`, `frontend/src/portal/features/profile/{ProfileFieldsets,form,ProfilePage,MyAircraftPage,AircraftEditor}.tsx` and their tests, `frontend/src/portal/features/profile/constants.ts#photo-id`, `frontend/src/portal/features/admin-members/{MemberProfileTab,MemberFormFields,MemberCreatePage}.tsx` and their tests, `frontend/src/portal/features/admin-aircraft/AircraftRecordPage.tsx` and its test, `frontend/src/portal/features/aircraft/InsuranceChip.tsx#verification` (if the chip carries the mark), `frontend/src/portal/routes/leader.tsx`, `frontend/src/portal/nav.ts#leader`, `frontend/src/portal/choices.ts#verification`, `frontend/src/test/handlers.ts#verification`, `frontend/src/styles/base.css#verification` (only if a new rule is needed), `docs/user/roles.rst`, `docs/user/admin/{member-check,aircraft-check,member-record,aircraft-record,users}.rst`, `docs/user/member/{profile,my-aircraft}.rst`, `docs/developer/architecture.rst#verification`.
- **Steps:** §5.5 and the screens and user pages of §5.8, built against §5.3 and §5.4 as the contract with msw handlers. The API types come from the backend package, so this package declares its own copies in `features/verification/types.ts` only if the backend PR has not merged when it starts, and the e2e package removes the copies in favor of `api/types.ts`.
- **Verify:** `make test`; `make lint`; `npm run test` green; every touched user page passes `test_docs_user.py`.

### Wave 2

#### verification-e2e (Opus, reviewed)

- **Refs:** #311
- **After:** verification-backend, verification-report-and-message, verification-ui
- **Branch:** `feature/verification-e2e`; database `caldart_verification_e2e`; e2e port 8254
- **Owns:** `frontend/e2e/verification.spec.ts` (new), `frontend/e2e/leader-check.spec.ts#verification`, `frontend/e2e/helpers.ts#verification` (additive), `frontend/src/portal/features/verification/types.ts` (deletes it if the ui package left one), `frontend/src/portal/features/verification/**#types`, `docs/demo-walkthrough.rst#verification`.
- **Steps:** as the seeded DART leader, open the Member check for `unverifiedPilot`, read NO-GO with the three *not verified* reasons, press Verify, tick the three boxes, save, read GO, and read the one *Verification recorded* email at the seeded account administrator's address with `emailCountTo` proving there is exactly one; make that pilot a verifier, sign in as the pilot, open the Aircraft check for an unverified airplane, verify its insurance, read INSURED; sign in as the pilot again, change the medical expiration on My profile, read *Not yet verified* under Medical and a leader's card reading *Medical not verified*; the demo walkthrough gains the verification step.
- **Verify:** `make e2e`; `make lint test`.

### Wave 3

#### closeout (Sonnet)

- **Closes:** #311
- **After:** verification-e2e
- **Branch:** `chore/verification-closeout`; database `caldart_verification_closeout`; e2e port 8255
- **Owns:** `docs/**#residue`, `frontend/src/**#residue`, `backend/**#residue`, `plans/2026-09-26-verification.md` (moves to `plans/archive/`).
- **Steps:** on `main` after `make reset`, run the owner's sentences end to end: as a DART leader verify a member's three items from the Member check and see one email; as an account administrator verify from the member record; as a member change the certificate number and see the certificate alone drop to *Not yet verified*; as the leader grant the verifier role from the card and see the member's menu gain the two checks; as that verifier verify an aircraft's insurance from the Aircraft check and edit the carrier from My aircraft to see it drop; download the verification report; read every docs page the packages touched once more against the running portal; act on the residue notes in §9 and later; move the plan to the archive. The PR body lists the owner's sentences and the PR that settled each.
- **Verify:** `make lint test check docs audit e2e` green.

## 8. Manifest

```json
[
  {"wave": 1, "package": "verification-backend", "model": "opus", "review": true, "branch": "feature/verification-backend", "database": "caldart_verification_backend", "e2e_port": 8251, "closes": [], "refs": [311], "after": []},
  {"wave": 1, "package": "verification-report-and-message", "model": "opus", "review": true, "branch": "feature/verification-report", "database": "caldart_verification_report", "e2e_port": 8252, "closes": [], "refs": [311], "after": []},
  {"wave": 1, "package": "verification-ui", "model": "opus", "review": true, "branch": "feature/verification-ui", "database": "caldart_verification_ui", "e2e_port": 8253, "closes": [], "refs": [311], "after": []},
  {"wave": 2, "package": "verification-e2e", "model": "opus", "review": true, "branch": "feature/verification-e2e", "database": "caldart_verification_e2e", "e2e_port": 8254, "closes": [], "refs": [311], "after": ["verification-backend", "verification-report-and-message", "verification-ui"]},
  {"wave": 3, "package": "closeout", "model": "sonnet", "review": false, "branch": "chore/verification-closeout", "database": "caldart_verification_closeout", "e2e_port": 8255, "closes": [311], "refs": [], "after": ["verification-e2e"]}
]
```
