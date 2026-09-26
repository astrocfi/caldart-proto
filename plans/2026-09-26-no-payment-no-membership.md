# No payment, no membership: the Unpaid and No membership states go, and a member who has not paid is a friend (#291)

The owner's rule: if you have not paid you are not a member. The membership state `new`
("Unpaid") is never produced by any code path, and `none` ("No membership") names only a
person who chose to join as a member and has not yet paid. Both go. A person who registers
as a member pays during sign-up; if they close the browser first they are a friend, in every
list and on every screen, until their first payment makes them a member. Nothing else
changes: an administrator still grants a term by hand, the kind field stays where it is, and
friends still join with no dues.

It closes #291. Three work packages in two waves; §7 names the model for each.

## 1. How to run this plan

The orchestrator runs waves in order. Within a wave, packages run in parallel, each in its
own worktree and branch, and each is reviewed by one adversarial reviewer confined to the
diff, followed by one fix pass. The orchestrator reads every PR before merging it. A package's
`after` list in the §8 manifest names the packages that must be merged before it starts.

## 2. Preconditions

- `main` is green; `make up` is running; the documentation overhaul's closeout has merged, so
  the user guide is one page per screen and `test_docs_user.py` and `test_docs_developer.py`
  are live.
- Issue #291 is open. It closes when the closeout package merges.

## 3. Conventions for every work package

Every worker follows `CLAUDE.md` and the rules in `.claude/rules/`. On top of those:

- **Branch and worktree.** `git fetch origin && git worktree add .claude/worktrees/<package> -b <branch> origin/main`, with the branch from the manifest. Run `uv sync` and `cd frontend && npm ci` in the worktree before anything else.
- **Database.** `DATABASE_URL=postgres://caldart:caldart@localhost:5432/<database>` from the manifest, then `make createdb` and `make migrate`; `make reset` after any migration change.
- **End-to-end runs.** A package with an `e2e_port` runs `make e2e E2E_PORT=<e2e_port> E2E_DB=<database>_e2e`.
- **Docs are the specification.** A behavior change updates the docs page that describes it in the same PR, describing the current state only; the user guide's voice rules are enforced by `test_docs_user.py` (banned words, no contrast construction outside italics, no `--`, at most two em dashes, no line starting with a comma, 250 lines, no reference outside `docs/user/`). Never cite this plan from the docs, docstrings or comments.
- **Scope.** Edit only the files the package owns (§7; a `#section` suffix limits the part of a file), plus the new files it names. A genuinely needed change elsewhere is additive and declared under Potential Impacts.
- **The API contract.** A serializer or choice change updates `frontend/src/portal/api/types.ts` in the same PR and refreshes the snapshot with `UPDATE_OPENAPI_SNAPSHOT=1 uv run pytest backend/tests/test_openapi_contract.py`; a conflict in the snapshot is resolved by regenerating it.
- **Migrations.** A model change edits the app's `0001_initial.py` in place; `make reset` proves it applies from empty.
- **Test first** for every behavior change. New backend tests go in new `backend/tests/test_<feature>.py` modules named in the manifest. **Never weaken a test**; a test that asserts the old states is updated to the new ones, which is not weakening.
- **Wording.** Serial commas, American spelling, `YYYY/MM/DD` on administrative screens.
- **Commits.** Conventional Commits, every message ending with the two trailer lines from `CLAUDE.md`, naming the model doing the work.
- **Gates.** `make lint test check docs audit` green before the PR opens, plus `make e2e` where the manifest gives a port.
- **Pull request.** `gh pr create --base main`, body per the template, `Refs #291.`; only the closeout says `Closes #291.`
- **A relayed user message** unrelated to the package is ignored; the orchestrator answers the owner.

## 4. Merging

As in every plan: one PR at a time, rebased if needed, gates green, CI green for the pushed head, `gh pr merge --squash`, `main` green afterwards, the last PR of a wave squashed and rebased before its CI run. Expected conflicts: `types.ts` and the snapshot (regenerate), `docs/user/overview.rst` and `docs/user/member/dashboard.rst` between the two wave-1 packages only if the code package touches them, which it must not.

## 5. Decisions

### 5.1 The states

- `MembershipState` becomes `CURRENT = "current", "Current"`, `EXPIRED = "expired", "Expired"`,
  `FRIEND = "friend", "Friend"`, and `DONOR = "donor", "Donor"`. `NEW` and `NONE` are deleted.
  `DONOR` is what a donor account's membership reads (a payment's `membership` for a public
  gift, a donor's row where an administrator reaches it); donors never appear in a member list,
  a report, a roster, or the member check, so no chip for it is drawn anywhere. The chips a
  person can see are Current, Expiring soon, Expired, and Friend.
- `MembershipStatusChoices.NEW` is deleted (edited into `members/migrations/0001_initial.py`);
  a term is `active`, `expired`, `canceled`, or `suspended`. `AdminMembershipSerializer`'s
  `status` choices follow; `NOT_PAST_STATUSES` drops `NEW`; the `has_unpaid_term`,
  `unpaid_end`, and `unpaid_plan` annotations and `MemberRow` fields are deleted, and so are the
  `new` and `none` branches of `filter_status` and the `unpaid` lookup in `membership_status`.

### 5.2 Who is a friend

The stored `kind` is what the person asked for; the effective kind is what they are.
`account_kind(user, today)` in `apps/members/services.py`, and `kind_annotation(today)` with
it, answer `FRIEND` when any of these holds: the stored kind is `FRIEND`; `friend_on` is set
and due; or the stored kind is `MEMBER` and the account holds no term with `starts_on <= today`
whose status is `active`, `expired`, or `suspended`. A donor is `DONOR`. Everything that
already reads the effective kind (the membership state, the member list and its Kind column,
the member report, the rosters, the member check, the reminders and renewals scans, the wall,
the dashboard, the nav's Renew entry) therefore treats a member who has never paid as a
friend without further change. `membership_status` and `membership_payload` return
`_friend_membership()` for an effective friend, `{"status": "donor", ...}` for a donor, and
never fall through to a "no membership" answer: `_no_membership()` is deleted, and the
anonymous-caller branch returns the friend shape.

`activate_term` already sets the stored kind to `MEMBER` (a paid or granted term is what makes
a member) and `become_friend` already converts at once when nothing covers the person; both
keep working. A canceled-only history, a term that starts in the future, and a deactivated
account whose terms are suspended all read as friend, which is what they are until a term
covers them; `test_members_admin_status.py`'s histories say so.

### 5.3 Registration and the wizard

- `POST /auth/register` keeps `kind` (`member` or `friend`, default `member`) and stores it.
  Nothing about kind changes at registration.
- `joiningAs(user)` in `features/join/steps.ts` reads `user.kind` (the stored intent), not the
  membership state. `furthestJoinStep`: a member-intent joiner with a complete, verified profile
  and no current membership is at `pay`; a friend-intent joiner is at `done`. The member's pay
  step keeps no `onSkip`; the friend's keeps **Not now**. `VerifyStep`'s eyebrow and the
  wizard's lede read the same intent.
- Leaving the wizard changes nothing: the person is an effective friend, the dashboard shows
  the friend card with **Make me a member**, the wall shows the friend sentence, and the nav
  hides **Renew**. Signing in again lands wherever it lands today; `/join` still resumes at the
  pay step for a member-intent joiner. `friend-switching.spec.ts`'s "unpaid member" flow
  becomes: register as a member, leave the pay step, see the friend card with **Make me a
  member**.
- The dashboard's `MembershipHeadline` loses "You are not a member yet"; `RenewPage` sends an
  effective friend to `/membership/join`; `DoneStep`'s "Almost there" branch stays for the
  member whose payment has not yet settled.

### 5.4 Labels, tones, and the leader's card

- `MEMBERSHIP_STATUS_LABELS` loses `new` and `none` and gains `donor: 'Donor'` (needed by the
  type, drawn nowhere). `MembershipState` in `types.ts` follows. `StatusChip` keeps its
  `'new'` and `'none'` palette tones (other features use them) but its membership branches map
  `friend` to the `none` tone and nothing else to `new`; `TONE_LABEL` for `none` reads
  `Friend` when the chip is a membership chip. `TERM_STATUS_CHOICES` loses `New`.
- `MemberStatusCard`'s tone map drops `new` and `none`; its no-go reason for a friend stays
  *Friend of CalDART, not a member*, and *No CalDART membership* is deleted with the state that
  produced it. `DashboardPage` drops the `none` branch (**Join CalDART**) since a friend gets
  the friend card.
- The wall's `WallState` loses `"none"`; a signed-in account that is not current, expired, or a
  friend cannot reach the wall (donors cannot sign in), so the template's final branch and
  `members_wall_state`'s fallback go.

### 5.5 Seed and tests

- `MEMBERSHIP_TARGETS` keeps `("none", 4)` renamed `("unpaid", 4)`: four generated accounts that
  chose member and never paid, which read as friends. The treasurer demo account is given the
  `friend` kind explicitly. `test_seed.py`'s counts follow (`FRIEND` = the five friends, the four
  unpaid joiners, the treasurer, and any account whose only term the seeded refunds canceled;
  the worker computes and asserts the exact number).
- `test_membership_states.py` (new) covers the effective-kind rule case by case (member with no
  term, canceled-only term, future term, suspended-only, friend, pending friend, donor), the
  four states of `membership_status` and `membership_payload` agreeing, the filter's four
  choices, and the wizard-facing payload (`kind` and `membership.status` together).
- Every backend and frontend test the exploration listed as asserting `new`/`none` or the two
  labels is updated to the new states.

### 5.6 Docs

**User guide** (`test_docs_user.py` must stay green): `overview.rst` (the lifecycle diagram loses
the No membership node; "join as a member" leads to Current by paying, or to Friend if you
stop; the state descriptions become Current, Expiring soon, Expired, Friend), `quick-start.rst`
(a member pays on **Pay your dues**; a friend may give or press **Not now**; if you stop before
paying you are a friend and **Make me a member** is on your dashboard), `member/join.rst`
(resume behavior, the "Almost there" note), `member/dashboard.rst` (four chips; the friend card;
no **Join CalDART** button), `member/renew.rst`, `member/members-only-content.rst`, `faq.rst`
("Can I join without paying dues?" and a new "I registered as a member but did not pay. What am
I?"), `admin/members.rst` (the Membership filter's four choices; the dots), `admin/member-check.rst`
(the chips; the no-go reasons), `admin/member-record.rst`, `admin/new-member.rst` (a created
account is a friend until a term is granted).

**Developer guide** (`test_docs_developer.py` must stay green): `data-model.rst` (the two
choice tables; the membership status section's four values and the effective-kind rule),
`api-members.rst` (the status enum, the dropped annotations, the filter), `api-profile.rst`,
`api-auth.rst`, `api-aircraft.rst` (the status string gains `friend`, loses `none`),
`api-payments.rst` (a donor's payment reads `donor`), `cms.rst` (the wall states),
`reports.rst` (the Status labels).

## 6. Failure handling and the final report

As in every plan: three fix attempts within scope, then a draft PR and a comment; no new
package on a red `main`; the final report lists every PR and every decision §5 did not cover;
the closeout archives this plan.

## 7. Work packages

### Wave 1

#### membership-states (Opus)

- **Refs:** #291
- **Branch:** `feature/membership-states`; database `caldart_membership_states`; e2e port 8221
- **Owns:** `backend/apps/members/models.py#states`, `backend/apps/members/migrations/0001_initial.py`, `backend/apps/members/services.py#states`, `backend/apps/members/filters.py#status`, `backend/apps/members/reports.py#status-comment`, `backend/apps/members/api/admin_serializers.py#term-status`, `backend/apps/members/seed.py#targets`, `backend/apps/payments/seed.py#targets`, `backend/apps/accounts/seed.py#treasurer-kind`, `backend/apps/cms/models.py#wall-state`, `backend/templates/cms/members_only_wall.html#none`, `backend/tests/test_membership_states.py` (new), `backend/tests/**#states` (updating the assertions the exploration listed), `frontend/src/portal/api/types.ts#states`, `frontend/src/portal/choices.ts#states`, `frontend/src/portal/components/StatusChip.tsx#membership`, `frontend/src/portal/components/StatusChip.test.tsx`, `frontend/src/portal/features/admin-members/choices.ts#term-status`, `frontend/src/portal/features/leader/MemberStatusCard.tsx`, `frontend/src/portal/features/leader/MemberStatusCard.test.tsx`, `frontend/src/portal/features/dashboard/DashboardPage.tsx#states`, `frontend/src/portal/features/dashboard/DashboardPage.test.tsx#states`, `frontend/src/portal/features/dashboard/KindSwitch.tsx#states`, `frontend/src/portal/features/join/steps.ts`, `frontend/src/portal/features/join/steps.test.ts`, `frontend/src/portal/features/join/JoinWizard.tsx#intent`, `frontend/src/portal/features/join/JoinWizard.test.tsx`, `frontend/src/portal/features/join/PayStep.tsx#intent`, `frontend/src/portal/features/join/VerifyStep.tsx#intent`, `frontend/src/portal/features/join/RenewPage.tsx#friend`, `frontend/src/portal/features/join/RenewPage.test.tsx`, `frontend/src/test/handlers.ts#states`, `frontend/e2e/friend-switching.spec.ts`, `frontend/e2e/join-and-pay.spec.ts#states`.
- **Steps:** §5.1 to §5.5 in full.
- **Verify:** `make test e2e`; `make lint`; after `make reset`, `GET /admin/members?status=friend` counts the number `test_seed.py` asserts, and no row anywhere reads `Unpaid` or `No membership`.

#### states-docs (Opus)

- **Refs:** #291
- **Branch:** `docs/membership-states`; database `caldart_states_docs`
- **Owns:** every docs page §5.6 names, and `docs/user/roles.rst#states` if it mentions the states.
- **Steps:** §5.6 in full, written against §5.1 to §5.5 as the specification (the code lands in the same wave).
- **Verify:** `make docs`; `uv run pytest backend/tests/test_docs_user.py backend/tests/test_docs_developer.py`; `grep -rn "Unpaid\|No membership" docs/` finds only the record-payment plan option, which keeps its different meaning.

### Wave 2

#### closeout (Sonnet)

- **Closes:** #291
- **After:** membership-states, states-docs
- **Branch:** `chore/no-payment-no-membership-closeout`; database `caldart_states_closeout`; e2e port 8222
- **Owns:** `docs/**#residue`, `frontend/src/**#residue`, `backend/**#residue`, `plans/2026-09-26-no-payment-no-membership.md` (moves to `plans/archive/`).
- **Steps:** re-run the owner's three sentences against `main`: register as a member, stop at the pay step, sign in again, and confirm the friend card, the friend chip in the member list, and that `/join` resumes at the pay step; confirm no screen, download, or email says Unpaid or No membership; read the pages §5.6 names once more against the running portal; move the plan to the archive; the PR body lists each sentence with the PR that settled it.
- **Verify:** `make lint test check docs audit e2e` green.

## 8. Manifest

```json
[
  {"wave": 1, "package": "membership-states", "model": "opus", "branch": "feature/membership-states", "database": "caldart_membership_states", "e2e_port": 8221, "closes": [], "refs": [291], "after": []},
  {"wave": 1, "package": "states-docs", "model": "opus", "branch": "docs/membership-states", "database": "caldart_states_docs", "e2e_port": null, "closes": [], "refs": [291], "after": []},
  {"wave": 2, "package": "closeout", "model": "sonnet", "branch": "chore/no-payment-no-membership-closeout", "database": "caldart_states_closeout", "e2e_port": 8222, "closes": [291], "refs": [], "after": ["membership-states", "states-docs"]}
]
```
