# Portal usability review (2026-10-04)

This review asks one question of the member portal: could a CalDART volunteer with little
technical skill use it, and does it read as one finished, professional product? It covers
every portal screen (`/portal/`) as each of the eleven demo roles: member, expired, friend,
leader, verifier, useradmin, treasurer, accountadmin, management, webadmin, and sysadmin.
The public site and the Wagtail CMS were out of scope.

Checked against `main` at `80d4867e` (2026-10-04).

**Who reviewed.** Five independent review passes. Four took one area each, and the fifth
took the whole portal for voice, naming, formats, and shared components.

| Pass | Signed in as | Screens |
| --- | --- | --- |
| Member | member, expired, friend, and two accounts made through the join wizard | sign-in, join, dashboard, profile, aircraft, payments, donate, renew, messages, preferences |
| Administration | accountadmin, useradmin, sysadmin, leader | Members, member record, aircraft, DARTs, users |
| Finance | treasurer, accountadmin | payments, renewals, reconciliation, contributions, donors, subscriptions, reminders, notifications |
| Operations and system | leader, verifier, sysadmin, and a leader account with no DART | Member check, Aircraft check, verification, System screens, Email types |
| Voice | sysadmin, management, member | every route, plus the 3,368 visible strings in 316 source files |

**Widths and themes.** Every screen at 1920, 820, and 390 px, in the default theme. The
`night`, `flight-deck`, and `sectional` themes were spot-checked by setting `data-theme`
in the page, and the finance pass measured the red confirm button in all 14 themes.

**Method.**

- Playwright walks through each screen, with full-page screenshots looked at one by one.
- Keyboard walks (Tab, Enter, and Escape), tracking where focus lands after each action.
- axe-core where it ran:
  - the member pass ran `@axe-core/playwright` on every route and on opened states;
  - the administration pass injected `axe-core` into each page;
  - the screenshot script ran it on every role and route at 1920 in the default theme.

  The finance and voice passes checked focus, names, and contrast by hand.
- The user guide read beside each screen. Help was rechecked on every route after the
  guide was built on the review server.

**Screenshots.** The route screenshots are reproducible with `make screenshots`. It runs
`frontend/scripts/screenshots.mjs`, which writes 726 screenshots (206 role-route pages at
three widths) to `frontend/screenshots/<role>/<slug>@<width>.png`, with `manifest.json`
and `axe.json` beside them. The reviewers' interaction screenshots (panels open, errors
shown, phone menus) are not in the repository. Each finding still names its screenshot as
`<area>/<file>`, where the area is `member`, `admin`, `finance`, `ops`, or `voice`, so a
reader with the review set can find it.

**Limits.**

- The seeded donors have no password, so nobody saw what a donor sees.
- No demo account has any messages, so Messages was seen only empty.
- The finance pass recorded a $1.00 cash payment, CALDART-000087, for Lucia Ferreira. It
  appears in the October totals on the review server.

**How findings are labeled.** Severity is **blocking** (a person cannot finish the task),
**major**, or **minor**. Cross-cutting findings are numbered `C1` onward, and screen
findings `M` (member), `A` (administration), `F` (finance), and `O` (operations and
system). Each finding names the reviewer's own numbering it came from, such as
`admin #7`, `ops L1`, or `voice F8`.

---

## Overall judgment

**What works.** The portal is calm, plainly typeset, and mostly well written.

- The default theme looks professional, and the dark themes hold up.
- Nothing scrolls sideways on the member screens at 390 px, and focus rings are visible.
- Errors written in the browser sound like a person ("Give the DART a name.").
- The sign-in, forgot-password, and join flows are short.
- Member check and Aircraft check are the strongest screens in the portal: one search box,
  and a GO or NO-GO verdict a pilot can read on the ramp.
- The finance report tables keep their filters in the address bar, export to CSV and PDF,
  and save column sets.
- Help opens the matching guide page from every signed-in screen.

**What a volunteer would struggle with most.** Three problems run through every area.

- **Tables on narrow screens.** On a phone, the Members list shrinks every name to "A.",
  and Email types shrinks its description to nothing. DARTs, Users, Renewals, and the
  payment list push their Edit buttons, money, and status off the right edge, with no sign
  that they scroll and no way to scroll by keyboard. On a tablet, Renewals has no visible
  Turn off button and the payment list has no visible Total.
- **Forms that fail silently.** After Save or Create at the foot of a long form, the errors
  land out of sight and focus falls to the page body. Focus also drops after almost every
  other action, and Escape closes almost nothing.
- **One thing, many names.**
  - "Payments" means four things in one menu.
  - "Kind" means three.
  - Giving has five names.
  - A plain member's own mail sits under a "Bulk Email" heading.
  - The two pre-flight checks disagree about the same airplane's insurance.

On the money screens, Checkout is a card inside a card, Donate opens on "No thank you",
and Renew does not tell a member that automatic renewal already covers them.

**Does it read as one finished product?** Not yet. At 1920 it looks finished screen by
screen, but it reads as several products built at different times:

- destructive actions use six confirmation patterns;
- pagination is built five ways;
- status is drawn four ways;
- times appear in two clock formats;
- content width changes between screens and between cards on one page.

The Bulk Email screens are the most consistent: they share `DeleteButton` and
`ConfirmButton`, write their own errors, and give empty states a next step. The older
administration, finance, and system screens fall short of them on each point. The System
screens still read like a developer's console ("dumps", `BACKUP_DIR`, `manage.py
db_restore`, "DEBUG"), and raw server text such as "This field may not be blank." shows
on several forms. Most of what keeps the portal from looking finished lives in a handful
of shared components: `DataTable` and `tableFit`, `FilterBar`, `ConfirmButton`,
`StatusChip`, the page frame, and `nav.ts`. Fixing those once fixes most screens.

---

## Totals

After de-duplication. The reviewers reported 7 blocking, 117 major, and 125 minor
findings, 249 in all. Merging the same problem reported by several reviewers leaves the
counts below. Most of that merging went into the cross-cutting findings.

| Area | Blocking | Major | Minor | Total |
| --- | ---: | ---: | ---: | ---: |
| Cross-cutting (C) | 3 | 43 | 15 | 61 |
| Member (M) | 0 | 16 | 25 | 41 |
| Administration (A) | 1 | 12 | 13 | 26 |
| Finance (F) | 0 | 8 | 11 | 19 |
| Operations and system (O) | 0 | 10 | 13 | 23 |
| **Total** | **4** | **89** | **77** | **170** |

The four blocking findings are:

- C1: columns shrink to nothing at phone width (the Members list and Email types);
- C2: DARTs hides its Edit button off-screen on a phone;
- C5: a refused submit leaves the errors out of sight;
- A3: New member refuses an account without a phone number, though the guide says only the
  email is required.

---

## Cross-cutting findings

### Tables at narrow widths and column fitting

#### C1. Columns shrink to nothing at narrow widths

- **Severity:** blocking. **Component:** `DataTable`, `tableFit.ts`; the column lists in
  `MembersListPage.tsx` and `AircraftRegisterPage.tsx`.
- **Screens:**
  - Members, as accountadmin and leader.
  - Aircraft register.
  - Email types.
  - Notifications.
- **Seen:**
  - **Members, at 390.** Name is 35 px wide, so every name reads "A.". Email is 0 px and
    DART 29 px, while the ✓/✗ and date columns keep their width. Nobody can be found on a
    phone.
  - **Aircraft register, at 390.** Make and Model are 19 px and Owner is 0 px.
  - **Email types, at 390.** "What it is for" is 0 px, each row is 1,808 px tall, and the
    page is 5,284 px long. At 820 it is 66 px and breaks words ("CalDA / RT"). The guide
    promises the description "read[s] in full".
  - **Notifications, at 390.** Events is 0 px, and Recipient is centered, unlike every
    other table.
  - `memberColumns` uses fixed percentage widths with no `dropOrder` or `minWidth`, so
    `tableFit` never runs.
- **Should:** never let a column shrink below a readable minimum. The identifying column
  (name, N-number, description) keeps its width first, then the actions. The others drop
  in a stated order (on Members: Email, then DART). Left-align Recipient.
- **Screenshots:** `admin/aa-members@phone.png`, `admin/crops/aircraft-phone-table.png`,
  `ops/leader-members@390.png`, `ops/sys-types@390.png`, `ops/sys-types@820.png`,
  `finance/accountadmin-notifications@390.png`, `voice/sa-admin_members@p.png`.
- **Reported in:** admin #1, #26; ops L1, E1; finance #38; voice F8.

#### C2. Wide tables scroll sideways with no cue, hiding actions, money, and status

- **Severity:** blocking. **Component:** `DataTable` (`.table-wrap`), `tableFit.ts`; the raw
  `<table>` at `DashboardPage.tsx:153`; `PaymentsTable.tsx`; `RunActionsTable`.
- **Screens:**
  - DARTs.
  - Users and roles.
  - The member record's Memberships and Payments tabs.
  - Dashboard Recent payments.
  - The member's Payments.
  - Finance: Overview, Payments, Renewals, Contributions, Donors, Subscriptions,
    Notifications, and a member's money history.
  - Sent emails.
  - Scheduled.
- **Seen:**
  - **DARTs, at 390.** Members, Status, and Edit are off-screen, so the only way to change a
    DART is invisible on a phone.
  - **Member screens, at 390.**
    - Recent payments clips its status to "Succ".
    - The member's Payments hides Status and Receipt.
  - **Administration, at 390.**
    - The member record hides Edit, Status, and every amount.
    - Users and roles hides Status and Edit.
  - **Finance, at 820.**
    - Overview hides Net, Refunded, and Total. The guide tells the treasurer to "read
      down the **Total** column".
    - The payment list hides Total, Fee, Net, and Status.
    - Renewals hides Status and the Turn off button.
    - Contributions clips its Statement buttons.
    - Donors hides Given and Net.
  - **Finance, at 390.** The payment list shows only Date, Name, and Email, and Renewals
    shows only Member and Kind.
  - **Operations and system, at 390.**
    - Sent emails scrolls 704 px inside 308 px, cutting off To and hiding Status and
      Bounce.
    - Scheduled's result tables hide "Report or DART".
    - Notifications hides Edit, Pause, and the trashcan.
  - **Keyboard.** axe reports `scrollable-region-focusable` on `.table-wrap` (the member
    pass, and three tables on Scheduled), so a keyboard user cannot scroll these tables at
    all.
- **Should:**
  - Apply one narrow-screen rule in `DataTable`: the identifying column keeps its width
    first, then actions, status, and the total. Other columns drop or stack.
  - Stack a payment as a card at phone width, or drop columns.
  - Where a table still scrolls, show a scroll cue and make the wrapper focusable, with
    `tabindex="0"`, a role, and a label.
  - Put Total next to Month on the overview at phone width, and keep `keepInSight` on
    DARTs' Edit.
- **Screenshots:**
  - Administration: `admin/aa-darts@phone.png`, `admin/aa-record-Memberships@phone.png`,
    `admin/aa-record-Payments@phone.png`.
  - Member: `member/member-dash-p.png`, `member/member-payments-p.png`.
  - Finance: `finance/treasurer-overview@820.png`, `finance/treasurer-overview@390.png`,
    `finance/treasurer-list@820.png`, `finance/treasurer-list@390.png`,
    `finance/treasurer-renewals@820.png`, `finance/treasurer-contributions@820.png`,
    `finance/treasurer-donors@820.png`.
  - Operations and system: `ops/sys-emails@390.png`, `ops/sys-sched-reports@390.png`.
  - Voice: `voice/sa-admin_darts@p.png`, `voice/sa-admin_users@p.png`,
    `voice/sa-dashboard@p.png`.
- **Reported in:** admin #18, #34; member #31; finance #4, #5, #23, #28, #30, #38;
  ops S2, C8; voice F8.

#### C3. The default columns overflow even at desktop width, and values wrap mid-token

- **Severity:** major. **Component:** `DataTable`, `tableFit.ts`, and the default column
  lists.
- **Screens:** Payments (finance), a member's money history, Donors, Reconciliation, and
  Email types.
- **Seen:**
  - **The payment list, at 1920.**
    - Reference and Reconciled are cut off at the right edge.
    - Name wraps onto two lines while Email takes the space.
    - "Membership and contribution" wraps onto three lines.
  - **Values that break mid-token.**
    - Receipt numbers break as "CALDART-/000016" on a member's money history at 390.
    - Phone numbers break as "415-/555-/0006" on Donors at 820 and 390.
    - "May 2024" wraps on Reconciliation at 820 and 390.
- **Should:**
  - Show fewer columns by default. Plan and Kind repeat each other, and Reference and
    Method are rarely needed.
  - Never wrap a name, receipt number, phone number, or month (`white-space: nowrap`).
  - Keep Total and Status on the first screen at every width.
- **Screenshots:** `finance/treasurer-list@1920.png`, `finance/treasurer-ledger@390.png`,
  `finance/treasurer-donors@820.png`.
- **Reported in:** finance #5, #21, #27, #30; ops E1.

#### C4. The inline delete confirmation is clipped in narrow Actions columns, and the Actions column moves

- **Severity:** major. **Component:** `DeleteButton.tsx`, `DataTable.tsx`, `tableFit.ts`.
- **Screens:** Email types (measured); Drafts, Templates, and Groups are at risk.
- **Seen:**
  - The Actions cell is 112 px wide with `overflow: hidden`, and the Delete and Keep pair
    needs 133 px, so it reads "Delet" and "Keep".
  - The Actions column sits second on Drafts, Email types, Templates, and Groups, and last
    on DARTs and Renewals.
  - It has no header on Subscriptions and Notifications, which is axe's
    `empty-table-header`.
- **Should:**
  - Size the Actions column for its open confirmation.
  - Put it last on every table.
  - Give it a header, visible or for screen readers only, such as "Actions".
- **Screenshots:** `voice/crop-types-delete-confirm@d.png`.
- **Reported in:** voice F2; axe `empty-table-header`.

### Focus after actions, and Escape on panels

#### C5. A refused submit leaves the errors out of sight and focus on the page body

- **Severity:** blocking. **Component:** the form pages (`MemberCreatePage.tsx`, the member
  record, `AircraftEditor.tsx`, `ProfileForm.tsx`, `DartForm.tsx`, `RefundForm.tsx`, the user
  record). A shared error-summary or focus-first-invalid helper belongs in
  `src/portal/components/`.
- **Screens:** New member, the member record's Save changes, Add aircraft (administration),
  My profile, the DART form, the user record, and Refund.
- **Seen:**
  - **New member.** After Create member at the foot of a 2,700 px form, the errors appear
    near the top, out of sight. The page does not scroll, focus falls to `<body>`, and
    nothing by the button says anything failed.
  - **The member record and Add aircraft** behave the same way.
  - **My profile.** After a failed save, focus stays on Save while the red fields are a
    screen or more above. The only sign nearby is "Check the highlighted fields and try
    again."
  - **Refund.** A refused amount is read out, but focus falls to the page body.
- **Should:** on a refused submit, move focus to the first invalid field, or show an error
  summary above the buttons that links to each field.
- **Screenshots:** `admin/aa-new-submit-viewport@wide.png`,
  `admin/aa-record-save-error-viewport@wide.png`,
  `admin/aa-aircraft-new-empty-viewport@wide.png`,
  `member/own-friend-profile-badsave-viewport-d.png`,
  `finance/i-detail-refund-error@1920.png`.
- **Reported in:** admin #7 and its shared-component list; member #36; finance #12.

#### C6. Focus falls to the page body after almost every action

- **Severity:** major. **Component:** each screen's action handlers. `ConfirmButton`
  already returns focus correctly and is the model; `DeleteButton` focuses its panel
  correctly.
- **Screens:** every area.
- **Seen.** Focus falls to the page body after:
  - **Member:**
    - opening or closing Make me a friend (`KindSwitch`) and the member's Payments Turn
      off (`AutoRenewalCard`);
    - a successful Save profile;
    - adding a plane from the results, Add a new aircraft, and Save aircraft.

    The keyboard user must Tab through the header and all 15 menu links to reach the
    panel.
  - **Administration:**
    - Grant term; Edit, Save, and Cancel on a term; Save changes; Deactivate; Reactivate;
      Delete;
    - DART Edit, which opens the form at the top of the page while focus stays in the
      table.
  - **Finance:**
    - opening, canceling, or failing a refund;
    - Turn off and Keep it on Renewals;
    - picking a member on Record a payment, and arriving on the payment after recording
      it;
    - Save on Matched on;
    - New subscription, Save, Send now, and Delete.
  - **Operations and system:**
    - opening a card on Member check, Verify (whose button disappears), Save, Cancel, Back
      to search, and Make a verifier;
    - Create backup;
    - four of the five Run now presses on Scheduled;
    - Add, Edit, and Cancel on Email types.
- **Should:**
  - When a panel opens, focus its first field or heading.
  - When it closes, return focus to the control that opened it, as `ConfirmButton`'s
    docstring promises.
  - After a save, keep focus on the button.
  - After an add, focus the added row.
  - After a pick, focus the next field.
- **Screenshots:** `member/member-dash-makefriend-d.png`, `finance/i-detail-refund@1920.png`,
  `finance/i-renewals-turnoff@1920.png`, `ops/leader-mc-verify@1920.png`.
- **Reported in:** member #25, #36, #45; admin #20, #39; finance #12, #18, #22, #33;
  ops M4, H3, C1, E2.

#### C7. Escape closes almost nothing

- **Severity:** major. **Component:** the phone menu in `PortalLayout.tsx`, and each
  hand-built panel. `ConfirmButton` and `PanelButton` already handle Escape.
- **Screens:** every screen (the menu); My aircraft; the member record; Aircraft register;
  DARTs; the user record; one payment; Renewals; Subscriptions; Member check; Aircraft
  check; Scheduled; Email types.
- **Seen:**
  - **The Menu drawer** does not close on Escape at 390 or at 1920. `aria-expanded` stays
    `true`, and the button still reads "Menu" while the drawer is open.
  - **Other panels that ignore Escape:**
    - My aircraft's edit panel;
    - the member record's Verify panel and inline term edit;
    - Add aircraft (New aircraft turns into Close, and focus stays on it);
    - the aircraft and DART delete confirmations, and DART edit;
    - the user record's confirmations;
    - the refund form;
    - Renewals' Turn off;
    - the subscription forms;
    - the Verify panels on both checks;
    - the real-charge confirmation;
    - the email type form.
  - **Escape works** only on the DART person row and on the `ConfirmButton` and
    `DeleteButton` panels.
- **Should:** Escape acts as Cancel on every panel, inline edit, and form opened in place,
  and returns focus to the control that opened it. The phone menu closes on Escape,
  returns focus to Menu, and reads "Close menu" while open.
- **Screenshots:** `member/member-menu-open-viewport-p.png`,
  `admin/aa-record-verify-after-esc@wide.png`.
- **Reported in:** member #33, #45; admin #15, #21, #23, #28, #39, #49; finance #12, #22,
  #33; ops G3, M4, C2, E2.

#### C8. Forms open far from the control that opened them

- **Severity:** major. **Component:** `SubscriptionsCard`, `SubscriptionForm`,
  `NotificationSubscriptionsCard`, the DART form, and the email type form.
- **Screens:** Email types, Subscriptions, Notifications, and DARTs.
- **Seen:**
  - **Email types.** Add and Edit open the form at the top of the page. On a phone, after
    "Edit Mission", the person is 3,369 px down the page and sees nothing change.
  - **Subscriptions.** New subscription opens its form above the table and Edit opens it
    below.
  - **Notifications.** The New subscription form opens below.
  - **DARTs.** Edit opens the form at the top of the page while focus stays in the table.
- **Should:** open each form in one predictable place (beside or below what asked for it),
  or scroll to it and focus its first field.
- **Screenshots:** `finance/i-subs-new@1920.png`, `finance/i-subs-edit@1920.png`.
- **Reported in:** ops E2; finance #33; admin #39.

#### C9. Success is confirmed four ways, or not at all

- **Severity:** major. **Component:** the shared toast, `SubscriptionsCard`, and
  `EmailPreferencesPage.tsx`.
- **Screens:** Subscriptions, Email preferences, Member check, and the payment screens.
- **Seen:**
  - **Payment screens** confirm with pop-up toasts.
  - **Subscriptions.** Save shows nothing. Send now prints a bare line, "Sent to Lucia
    Ferreira.", squeezed between the button and the table.
  - **Email preferences.** "Saved." appears as plain gray text at the foot of the card, not
    by the switch and not as the toast My profile uses.
  - **Member check.** Make a verifier shows only a toast after it has already acted (see
    O3).
- **Should:** confirm every save and send with the same shared toast.
- **Screenshots:** `finance/i-subs-sent@1920.png`, `member/own-prefs-toggled-d.png`.
- **Reported in:** finance #33 and its shared-component list; member #60.

#### C10. Errors do not clear when the person corrects them

- **Severity:** major. **Component:** `auth/form.tsx`, `DartForm.tsx`, the user record, and
  the shared field error handling.
- **Screens:** Change password, the DART form, the user record, and the administration
  forms.
- **Seen:**
  - **Change password.** After an empty submit, the person fills all three fields with
    mismatched new passwords and submits again. "This field may not be blank." still shows
    under the filled boxes, beside "The two passwords do not match."
  - **DART form.** "Give the DART a name." stays under a filled Name box until a successful
    submit, because `nameError` clears only in `handleSubmit`.
  - **User record.** Reset form leaves the server's refusal on screen.
- **Should:** clear a field's error when the person edits that field, and clear the
  server's errors on every resubmit.
- **Screenshots:** `member/own-chpw-mismatch-d.png`, `admin/aa-darts-add3-viewport@wide.png`.
- **Reported in:** member #57; admin #35, #46, and its shared-component list.

### Confirmations

#### C11. Destructive actions use six confirmation patterns, and "cancel" has five words

- **Severity:** major. **Component:**
  - `ConfirmButton` and `DeleteButton`;
  - the hand-built confirmations at `RenewalsPage.tsx:185-204`,
    `AutoRenewalCard.tsx:165-173`, `AircraftRecordPage.tsx:201-217`,
    `DartForm.tsx:477-490`, and `RenewalsPanel.tsx:98`.
- **Screens:** Renewals, the member's Payments, the aircraft record, DARTs, the user record,
  the member record, Scheduled, Bulk Email, and saved column sets.
- **Seen.** The six patterns:
  1. `DeleteButton`, "Delete" / "Keep": Email types, Subscriptions, Templates, Groups,
     Drafts, and My aircraft.
  2. Hand-built "Yes, turn it off" / "Keep it": Renewals. The member's Payments uses "Keep
     it on".
  3. "Yes, delete it" / "Keep it", with the question in small red text under the last
     card: the aircraft record.
  4. "Delete for good" / "Keep": DARTs.
  5. A `ConfirmButton` panel with "Cancel": Deactivate, Block reactivation, Make a friend,
     and the Bulk Email stop and send-the-rest.
  6. A typed confirmation: the member record's Danger zone, and a large send.

  Scheduled adds "Yes, charge what is due" / "Cancel". The dismiss button reads Keep, Keep
  it, Keep it on, Cancel, or Go back.
- **Should:**
  - Use `DeleteButton` for deletes, and `ConfirmButton` for everything else that cannot be
    undone.
  - The confirm button is red and names the act. The other button is always "Cancel".
  - Escape cancels, and focus returns to the trigger.
- **Screenshots:** `voice/renewals-turnoff-confirm@d.png`, `voice/aircraft-delete-confirm@d.png`,
  `voice/dart-delete-confirm@d.png`, `voice/user-deactivate-confirm@d.png`,
  `voice/member-danger@d.png`.
- **Reported in:** voice F3; admin #21; member shared-component list; finance #22 and its
  shared-component list.

#### C12. A danger button turns navy under the pointer

- **Severity:** major. **Component:** `styles/base.css:394` and `:423` (`.button--danger`).
- **Screens:** every destructive confirmation.
- **Seen:**
  - `.button--danger` has no hover rule, so `.button:hover:not(:disabled)` paints it navy
    at the moment of the click.
  - The computed color is red (`rgb(179, 38, 30)`) until the pointer reaches it.
  - The administration pass saw DARTs' "Delete for good" in navy rather than red, which is
    this rule.
- **Should:** add a `.button--danger:hover` rule with a darker red.
- **Screenshots:** `voice/dart-delete-confirm@d.png`, `voice/crop-types-delete-confirm@d.png`.
- **Reported in:** voice F1; admin #21.

#### C13. Danger buttons fail contrast in three dark themes

- **Severity:** major. **Component:** `base.css` (`.button--danger`) and
  `frontend/scripts/theme-contrast.mjs`.
- **Screens:** every danger button. Examples: Delete this aircraft, Refund inside the form,
  "Yes, turn it off", and Delete.
- **Seen:**
  - The text is always white, whatever the theme's red.
  - The text contrast is below the 4.5:1 minimum in three themes:

    | Theme | Contrast |
    | --- | --- |
    | `night` | 2.74:1 |
    | `flight-deck` | 2.51:1 to 2.94:1 (the two passes measured different buttons) |
    | `monterey-night` | 2.96:1 |

  - The other 11 themes pass at 5.5:1 to 6.5:1.
- **Should:** take the text color from a theme token (for example `--color-on-bad`), and add
  that pair to the `theme-contrast.mjs` gate.
- **Screenshots:** `finance/theme-night-detail@1920.png`,
  `admin/theme-night-record@wide.png`.
- **Reported in:** admin #31; finance #40.

#### C14. Inline confirmation panels break the button row they open in

- **Severity:** major. **Component:** `KindSwitch` and the user record's Danger zone, both
  built on `ConfirmButton`.
- **Screens:** Dashboard, My profile, and the user record.
- **Seen:**
  - **Dashboard.** Make me a friend opens its panel inside the button row. **Renew** is
    left floating, vertically centered, beside a paragraph-wide panel.
  - **User record.**
    - Opening Deactivate pushes Block reactivation to float alone at x=885.
    - Opening Block's confirmation indents its explanation over the Deactivate button.
- **Should:** open a confirmation below its row, at full width, leaving the other buttons in
  place.
- **Screenshots:** `member/member-dash-makefriend-d.png`.
- **Reported in:** member #23; admin #48.

### Filter bars, column chooser, pagination, and sorting

#### C15. The filter bar is ragged

- **Severity:** major. **Component:** `FilterBar.tsx` (`:160`) and `MultiSelect`.
- **Screens:** Members, Payments, Donors, Reconciliation, Renewals, Sent emails, Overview,
  and the subscription forms.
- **Seen:**
  - **Alignment.**
    - Labels in one row sit 3 to 5 px apart vertically. From and To sit higher than the
      dropdown labels, and on Donors the DART label sits lower than County.
    - Search and County sit 3 to 4 px higher than the selects, at a different height.
    - County is a custom dropdown with its own height, arrow, and label position.
  - **Reset.** "Reset to Defaults" is a small button that lines up with neither the top
    nor the bottom of the fields, and on Sent emails it floats between rows.
  - **Button rows.** At 1920, Columns / Load columns / Save columns and Export CSV /
    Export PDF each take a row of their own. On a phone, the filters fill about 700 px
    before the first table row, and they wrap raggedly.
  - **Cut-off placeholders.**
    - "Name, email, phone, or c" (Members).
    - "Name, email, reference," (Payments).
    - "Name, email, or the save" (Renewals).
- **Should:**
  - Give every control one height, and align them along the bottom.
  - Make Reset the same height as the fields, and name it "Reset filters".
  - Put the column and export buttons on one row at the right, as Reconciliation and
    Contributions already do.
  - Shorten the placeholders to "Name, email, or phone" and "Name, email, or reference".
  - Match County to the other dropdowns.
- **Screenshots:** `admin/aa-members@wide.png`, `finance/treasurer-list@1920.png`,
  `finance/treasurer-donors@1920.png`, `finance/i-donors-county@1920.png`,
  `voice/sa-system_emails@d.png`.
- **Reported in:** admin #2; finance #7, #25, #30; ops L4, S3; voice F6.

#### C16. Some lists use FilterBar, others hand-build their filters, and the "no filter" choice has three words

- **Severity:** major. **Component:** `FilterBar`; `UsersListPage.tsx:158-250`,
  `RenewalsPage.tsx:247-314`, `ReminderLog.tsx:83`, and `reports/definitions.ts`.
- **Screens:** Users and roles, Renewals, Reminders, Callouts, and the Bulk Email delivery
  report.
- **Seen:**
  - **FilterBar is used** on Members, Aircraft, Payments, Reconciliation, Contributions,
    Donors, Sent emails, Compose, and Group detail.
  - **Hand-built filters elsewhere.**
    - Users has a row of role buttons, "Every kind", "Active only", and "Any address",
      with the exports pushed far right.
    - Renewals has no Reset, no Columns, and no export buttons.
    - Reminders says "All kinds".
    - Callouts and the delivery report say "Every answer" and "Every result".
  - **The role filter** reads "Any role" on Users and "Every role" in the report
    definitions.
- **Should:** use FilterBar on every list, with "Any …" as the no-filter choice. Give
  Renewals the same Columns and export buttons as the other finance tabs.
- **Screenshots:** `voice/sa-admin_users@d.png`, `voice/sa-admin_payments_renewals@d.png`.
- **Reported in:** voice F5; finance #25.

#### C17. The Columns panel changes only the download, is clipped, and lets focus escape

- **Severity:** major. **Component:** `ColumnChooser.tsx` (`:87`, `:104`, `:124`, `:135`) and
  `PanelButton`.
- **Screens:** Members, Users, Aircraft, Payments, Donors, Sent emails, and the subscription
  forms.
- **Seen:**
  - **What it changes.** The panel is titled "COLUMNS TO EXPORT" and has Phone, Status,
    Kind, and Certificate checked. None of those are in the table behind it, and changing
    them changes nothing on screen. "Load columns" and "Save columns" are opaque.
  - **Clipping.**
    - Its heading wraps onto two lines, and the first line sits above the panel's border.
    - The panel is capped at 320 px, so "Reset to the default columns" is hidden until
      the person scrolls inside it, with no sign it scrolls.
  - **Focus.** Tabbing past the last checkbox moves focus to Export CSV, hidden under the
    panel, and the panel stays open.
- **Should:**
  - Name it for what it does ("Columns in the download"), or make it change the table too.
  - Make the panel wide enough for its heading, and keep Reset visible.
  - Close the panel, or keep focus inside it, when focus leaves.
- **Screenshots:** `voice/members-columns-open@d.png`, `voice/users-columns-open@d.png`,
  `finance/i-list-columns-crop@1920.png`, `finance/i-list-columns-tabbed@1920.png`,
  `ops/leader-members-columns@1920.png`.
- **Reported in:** voice F7; finance #8; ops L5.

#### C18. Pagination is built five ways

- **Severity:** major. **Component:** `DataTable`, which has no pagination of its own.
- **Screens:** Members, Users, Payments, Renewals, Aircraft register, Sent emails, and the
  Bulk Email delivery report.
- **Seen:**
  - **The five versions.**
    - Members: "Showing 1–25 of 53 [Previous] [Next]", inside the card.
    - Users: "59 accounts · page 1 of 3" above the table, and "[Previous] Page 1 of 3
      [Next]" below it, outside any card.
    - Payments and Renewals: "Page 1 of 4".
    - Aircraft register: "← Previous … Next →".
    - Sent emails: "Showing … of …". The delivery report has "Show all N".
  - **On Members,** Next leaves the window scrolled to the bottom of the next page, and
    the disabled Previous button looks almost enabled.
- **Should:** one pagination control inside `DataTable`. It scrolls to the top of the table
  on a page change and draws a disabled button clearly disabled.
- **Screenshots:** `voice/sa-admin_members@d.png`, `voice/sa-admin_users@d.png`,
  `voice/sa-admin_payments_list@d.png`.
- **Reported in:** voice F4; admin #5.

#### C19. Sorting gives the wrong cues

- **Severity:** minor. **Component:** `DataTable`.
- **Screens:** Members, Payments, Reconciliation, Contributions, Donors, and DARTs.
- **Seen:**
  - **No arrow on the default sort.** Members is sorted by name, but no arrow shows and
    every header reads `aria-sort="none"`.
  - **Unsortable headings look sortable.** On Payments, Kind, Dues, Refunded, Method, and
    Reference do not sort, yet look like the headings that do. The guide says "Click a
    column heading to sort by it".
  - **Money headings sit left of their figures.** Right-aligned sortable headings end
    about 13 px left of their numbers, because space is held for the arrow. This affects
    Total, Fee, and Net, and every money column on Reconciliation, Contributions, and
    Donors.
  - **DARTs** left-aligns its numeric headers over right-aligned numbers.
- **Should:**
  - Show the default sort's arrow, and set `aria-sort` to match.
  - Make every column sortable, or make the difference visible, and fix the guide either
    way.
  - Put the arrow on the left of a right-aligned heading.
- **Reported in:** admin #4, #38; finance #9, #10.

#### C20. Empty tables draw a stray rule and give no way forward

- **Severity:** minor. **Component:** `EmptyState` inside a `DataTable` card; `SentPage.tsx:60-65`.
- **Screens:** Messages, Sent, Templates, Groups, Callouts, Drafts, Members, Reconciliation,
  and Bulk Email Sent (as management).
- **Seen:**
  - **A stray rule.** An empty `DataTable` draws a rule, or an empty toolbar rule, at the
    top of its card.
  - **No way forward.**
    - Sent, as management, shows a title only.
    - Callouts and Groups name Compose but give no button.
    - Members and Reconciliation say "clear the filters", but there is no button there,
      and the button that exists is called "Reset to Defaults".
- **Should:** drop the rule when the table is empty, and offer the next action as a button
  in every empty state ("Reset filters", "Write an email").
- **Screenshots:** `voice/mgmt-bulk-email_sent@d.png`, `voice/sa-bulk-email_callouts@d.png`,
  `voice/sa-bulk-email_templates@d.png`, `ops/nodart-drafts@1920.png`.
- **Reported in:** voice F9, E4; ops N3; member #59; admin #3; finance #27.

### The page frame

#### C21. A plain member's own mail sits under a "Bulk Email" heading

- **Severity:** major. **Component:** `nav.ts`; `docs/user/member/dashboard.rst`.
- **Screens:** every screen, for every role.
- **Seen:**
  - The member sees MEMBERSHIP, then BULK EMAIL holding Messages and Email preferences.
    Those pages carry the eyebrow "YOUR EMAIL", and a member sends no bulk email.
  - `dashboard.rst` lists the menu groups as Membership, Operations, Administration, and
    System, and leaves this group out.
- **Should:** head the member's two entries "Your email", keep "Bulk email" for the sending
  tools, and update `dashboard.rst`.
- **Screenshots:** `voice/mem-dashboard@d.png`, `voice/sa-email-preferences@d.png`.
- **Reported in:** member #32; voice A1.

#### C22. Eyebrows do not match the menu group

- **Severity:** major. **Component:** the `eyebrow` prop at `LeaderLookup.tsx:94`,
  `ContributionsPage.tsx:97`, `DonorsPage.tsx:158`, `ReconciliationPage.tsx:106`,
  `RenewalsPage.tsx:334`, `PaymentDetailPage.tsx:216`, and `DashboardPage.tsx:65`.
- **Screens:** Dashboard, Member check, Aircraft check, every finance tab, and the user
  record.
- **Seen:**
  - **Dashboard** says "MEMBER PORTAL".
  - **Member check and Aircraft check** say "DART LEADER" for every role, though they sit
    in the Operations group and verifiers and administrators use them.
  - **Finance** uses four eyebrows:
    - FINANCE on Overview, Payments, Record a payment, and the payment page;
    - PAYMENTS on Renewals, Reconciliation, Contributions, and Donors;
    - TREASURER on the reconciliation card;
    - MEMBER LEDGER on a member's money history.
  - **The user record** says "USERS AND ROLES" where the menu says "Users & roles".
- **Should:** the eyebrow is always the menu group's name: "Operations" on both checks,
  "Finance" across the finance area.
- **Screenshots:** `voice/sa-dashboard@d.png`, `voice/sa-leader@d.png`,
  `voice/sa-admin_payments@d.png`, `voice/sa-admin_payments_renewals@d.png`,
  `ops/verifier-mc-card@1920.png`.
- **Reported in:** voice A2; finance #2, #20; ops M2.

#### C23. Menu labels mix Title Case with sentence case, and some differ from their pages

- **Severity:** minor. **Component:** `nav.ts`, `FilterBar.tsx`.
- **Screens:** the menu on every screen; Health and database; Sent emails; Users and roles;
  Aircraft register; Renew; every filter bar.
- **Seen:**
  - **Title Case.** "Health & Database", "Sent Emails", the group "Bulk Email", and
    FilterBar's "Reset to Defaults" are Title Case, while everything else is sentence
    case.
  - **Labels that differ from their pages.**
    - "Users & roles" opens "Users and roles".
    - "Aircraft" opens "Aircraft register".
    - "Renew" opens "Contribute to CalDART" for a life member.
- **Should:**
  - "Health and database", "Sent emails", "Bulk email", and "Reset filters".
  - Use "and", not "&".
  - Make each menu label match its page title.
- **Screenshots:** `voice/sa-dashboard@d.png`, `voice/sa-system_emails@d.png`.
- **Reported in:** voice A3, F6; ops S4; admin #3.

#### C24. The Menu button does nothing at desktop width

- **Severity:** major. **Component:** `layout/PortalLayout.tsx` and `portal.css`.
- **Screens:** every screen, every role, at 1920.
- **Seen:**
  - "Menu" shows beside the CalDART name though the sidebar is always open. Pressing it
    only flips `aria-expanded`.
  - The `.portal__drawer-toggle { display: none }` rule in `portal.css` loses to the
    `.button` display rule.
- **Should:** hide the button above the drawer breakpoint.
- **Screenshots:** `member/member-menu-open-d.png`, `ops/leader-mc-empty@1920.png`,
  `voice/menu-pressed@d.png`.
- **Reported in:** member #34; admin #51; finance shared-component list; ops G1; voice A5.

#### C25. The sidebar hides the current entry and its last groups

- **Severity:** major. **Component:** `layout/PortalLayout.tsx`, `portal.css`.
- **Screens:** every screen for a role with a long menu (sysadmin most of all), at 1920 by
  1080 and on a phone.
- **Seen:**
  - The sidebar scrolls on its own (1,313 px of links in a 992 px box), with nothing to
    say there is more.
  - On Health and database, it stops at "Reminders", so the current page and the whole
    System group are out of view.
  - Subscriptions, Notifications, the System group, and "User guide" sit below its fold.
  - On a phone, "Scheduled" is 1,232 px down the drawer.
- **Should:** scroll the current entry into view on every page, and show that the list
  continues. Collapsing groups is another way.
- **Screenshots:** `ops/sys-rail-viewport@1920.png`, `ops/sys-drawer@390.png`,
  `voice/sa-admin_members@d.png`.
- **Reported in:** ops G2; voice A5.

#### C26. Every page has the same browser title

- **Severity:** major. **Component:** the route definitions (`routes/index.tsx`) or `Page`.
- **Screens:** every route.
- **Seen:** the title is always "Member portal · CalDART", so browser tabs, history, and
  screen readers cannot tell screens apart (WCAG 2.4.2).
- **Should:** give each route its own title, for example "Member check · CalDART".
- **Reported in:** ops G4.

#### C27. A screen that fails to load shows a developer error, and the error pages draw an empty band

- **Severity:** major. **Component:** `routes/index.tsx` (no route has an `errorElement`), and
  `Page`'s header when there is no subtitle.
- **Screens:**
  - any route whose code fails to load (seen on Drafts, as a leader with no DART);
  - Page not found;
  - Not allowed.
- **Seen:**
  - **A failed load.** The page became React Router's "Unexpected Application Error! …
    Hey developer 👋". Reloading fixed it.
  - **Page not found, signed out.** A signed-out visitor reads "head back to your
    dashboard" and gets **Go to the dashboard**, which leads to sign-in.
  - **Both error pages** draw an empty band between two rules where the subtitle would
    go.
- **Should:**
  - Add an error page that says "This page did not load", with a Reload button.
  - Signed out, the not-found page says "Go to the CalDART home page".
  - Draw no subtitle band when there is no subtitle.
- **Screenshots:** `ops/nodart-drafts@1920.png`, `member/out-404-d.png`,
  `finance/treasurer-reminders@1920.png`, `finance/accountadmin-donors@1920.png`.
- **Reported in:** ops G5; member #61; finance shared-component list.

#### C28. Content width changes between screens, and between cards on one page

- **Severity:** major. **Component:** `portal.css`, `Card` with `DataTable`, and `Page`'s
  header actions.
- **Screens:** most screens. Measured on Profile, Donate, Payments, My aircraft, Mail
  delivery, Email preferences, Members, Drafts, Sent, Templates, Email types,
  Subscriptions, Sent emails, Messages, Compose, Recipient groups, Reminders, Scheduled,
  Health and database, New member, the member record, one payment, and a member's money
  history.
- **Seen:**
  - **Narrow cards.** At 1920, cards stop near 1,520 px on Profile, Donate, Payments, My
    aircraft, Mail delivery, and Email preferences.
  - **Wide cards.** They run to 1,904 px on Members, Drafts, Sent, Templates, Email types,
    Subscriptions, Sent emails, and Messages.
  - **Pages that mix the two.**
    - Compose has a wide first card and narrow second and third cards.
    - Health and database goes 1,215, then 1,600, then 1,215 px.
    - Recipient groups, Reminders, and Scheduled each mix a wide card with narrower ones.
    - The member record mixes 1,904 and 1,520 px cards.
    - The Refunds card on one payment, and the History card on a member's money history,
      are full width beside narrower cards.
  - **Header actions out of line.** They sit at the 1,904 px page edge while the cards stop
    at 1,520 px. Examples: Back to members on New member, and the My aircraft button on My
    profile.
  - **The cause.** A card holding a table loses the width limit.
- **Should:** one maximum width for the page body, and header actions aligned to it.
- **Screenshots:** `voice/sa-bulk-email_compose@d.png`, `voice/sa-bulk-email_groups@d.png`,
  `voice/sa-system_scheduled@d.png`, `voice/sa-system_health@d.png`,
  `ops/sys-health@1920.png`.
- **Reported in:** voice E1; ops H2; member #39, #59; admin #11, #24, and its
  shared-component list; finance #15, #37.

#### C29. Change password and Change email look like sign-in pages

- **Severity:** major. **Component:** `AuthShell` in `features/auth/ChangePasswordPage.tsx`
  and `ChangeEmailPage.tsx`.
- **Screens:** Change password and Change email, for every role.
- **Seen:** both pages use the sign-in layout inside the portal: a centered heading, no
  eyebrow, a narrow card, a full-width button, and "Back to the dashboard". Every other
  portal page uses the left-aligned page frame.
- **Should:** use the portal `Page` layout.
- **Screenshots:** `member/member-chpw-d.png`, `member/member-chemail-d.png`,
  `voice/sa-change-password@d.png`.
- **Reported in:** member #56; voice A6.

#### C30. Card eyebrows, card headings, and table captions follow no rule

- **Severity:** minor. **Component:** `Card`, `DataTable` captions, and `Page`.
- **Screens:** My aircraft, My profile, the member record, the aircraft record,
  Subscriptions, DARTs, Donors, and Email types.
- **Seen:**
  - **Eyebrows.**
    - On one page, some cards have eyebrows and some do not (My aircraft, My profile).
    - Every member-record card has an eyebrow and a heading that say nearly the same
      thing (TERMS / Membership history; DANGER ZONE / Account).
    - The aircraft record uses "LAST UPDATED 10/04/2026" as an eyebrow.
  - **Repeated titles.**
    - Subscriptions repeats the page title as its card title, and again in the BY EMAIL
      label.
    - Email types draws an "Email types" caption under a stray line.
  - **Captions.** Some are a title ("DARTs", "Donors") and some a count. Count captions
    such as "6 donors" are the better form.
- **Should:** an eyebrow only where it adds something; never repeat the page title; table
  captions are always a count.
- **Screenshots:** `voice/sa-profile_aircraft@d.png`, `voice/sa-admin_reports@d.png`.
- **Reported in:** voice E4; admin #24, #38; finance #30, #31; ops E4.

#### C31. Header buttons float, tabs are drawn two ways, and red marks the selection

- **Severity:** minor. **Component:** `Page` and the tab styles.
- **Screens:** most screens; the member record; finance; Users and roles.
- **Seen:**
  - **Header buttons.** The header action aligns with the last line of the introduction,
    so its height changes from page to page.
  - **A duplicate button.** Finance's filled "All payments" button does the same thing as
    the Payments tab beside it.
  - **Two tab styles.** Finance tabs are underlined. Member record tabs are small outlined
    buttons with a **red** outline on the current one, and they wrap on a phone.
  - **Red for the selection.** The pressed role filter on Users and roles also has a red
    outline.
- **Should:** align header actions to the heading; remove "All payments" (or make it a plain
  link); draw every tab bar the finance way; use the accent color, not red, for a selection.
- **Screenshots:** `voice/sa-bulk-email_templates@d.png`, `voice/sa-admin_payments@d.png`,
  `voice/member-record@d.png`.
- **Reported in:** voice E5; admin #22, #43; finance #3.

#### C32. The header shows a truncated email address instead of the person's name

- **Severity:** minor. **Component:** `layout/PortalLayout.tsx`, `portal.css`.
- **Screens:** every screen.
- **Seen:**
  - The header shows "member@exampl…", truncated even at 1920, where the person's name
    would fit.
  - The menu's right border stops about 590 px down instead of running full height.
- **Should:** show the person's name, and run the border the full height.
- **Reported in:** member #35; admin #51.

### Wording and voice

#### C33. British words in an American portal

- **Severity:** major. **Component:** the strings below; `.codespell-dictionary.txt`.
- **Screens:** My profile, the join wizard, New member, the member record, the DART form,
  Rosters, Reports, Renewals, Reconciliation, Email preferences, and the guide.
- **Seen:**

  | Seen | Where |
  | --- | --- |
  | "Tick anything you would be willing to help with." | profile, join, New member |
  | "Tick as many counties as you like." | `reports/definitions.ts:104,306` |
  | "Active — untick to make the DART inactive…" | `DartForm.tsx:451` |
  | "each of its people ticked to receive it" | `RostersCard.tsx:73`, `ReportsPanel.tsx:50` |
  | "nobody ticked" | `admin-reports/labels.ts:51` |
  | "The scan schedules a charge a fortnight before it is taken." | `RenewalsPage.tsx:374` |
  | "Takings by month" | `ReconciliationPage.tsx:121` |
  | "at the foot of a CalDART email" | `EmailPreferencesPage.tsx:33` |
  | "tick", "in date" | `admin/members.rst:25,97-99`, `member/profile.rst:92`, `quick-start.rst:93` |

  codespell catches none of these.
- **Should:**
  - "Check any you would help with" on the member's own forms, and "What they would help
    with." on an administrator's.
  - "check", "uncheck", and "checked" elsewhere; "two weeks"; "Money in by month"; "at
    the bottom".
  - Add `fortnight->two weeks` (and the tick forms) to `.codespell-dictionary.txt`.
- **Screenshots:** `voice/sa-profile@d.png`, `voice/sa-admin_reports@d.png`, `voice/crop-dart-empty.png`.
- **Reported in:** voice B1; member #19; admin #9, #40; finance #27.

#### C34. Raw server messages show beside hand-written ones

- **Severity:** major. **Component:** `api/client.ts:39-42`, `auth/form.tsx` (`fieldError`),
  and the serializers' `error_messages`.
- **Screens:** the join account step, Change password, Templates, Email types,
  Notifications, and any screen that hits a server error.
- **Seen:**
  - **"This field may not be blank."**
    - Under First name and Last name on the join wizard.
    - Twice on Change password.
    - On a template with no name.
    - On an email type with no description.
    - On a notification address left empty.
  - **The same mistake, worded by hand,** on other screens: My profile says "Your first
    name is required." and the DART form says "Give the DART a name.".
  - **The fallbacks** in `api/client.ts` are "Request failed (500)." and "Not found.".
- **Should:**
  - A message for each field, such as:
    - "Enter your first name." / "Enter your current password.";
    - "Say in one sentence what this email is for." (email type);
    - "Enter the address to email." (notifications).
  - A plain fallback, "That didn't save. Try again in a moment."
- **Screenshots:** `member/out-join-emptynames-d.png`, `voice/crop-changepw.png`,
  `voice/template-empty-submit@d.png`, `ops/sys-types-dup@1920.png`.
- **Reported in:** member #7; voice B3; ops E3; finance #39.

#### C35. Jargon a volunteer meets

- **Severity:** major. **Component:** the strings below. The role descriptions are A24, and
  the System screens' server terms are O15.
- **Screens:** Bulk Email (Compose, Groups), Subscriptions, Scheduled, Renew, Donate,
  Become a member, the member record, the user record, Renewals, and Reminders.
- **Seen, and what to write instead:**

  | Seen | Write instead |
  | --- | --- |
  | "batch" throughout Bulk Email: Add to batch, Clear the batch, Nobody is in the batch yet, The batch: 12 | "recipient list": "Add these people", "Remove everyone" |
  | "Reply-To" as a field label | "Replies go to" |
  | "{first_name}" with its braces in the Subject hint | the field chip the editor already draws |
  | "Dry run (send/charge/change nothing)" | "Practice run: show what would happen, send nothing" |
  | "This deployment has no live payment keys…", "This deployment offers no renewing plan…" (`RenewalSetup.tsx:94`), shown to members | "Online payment isn't set up yet" |
  | "Danger zone" as a tab and an eyebrow | "Delete or deactivate" |
  | "the scan" for the nightly job | "the nightly check" |

- **Screenshots:** `voice/sa-bulk-email_compose@d.png`, `voice/user-deactivate-confirm@d.png`,
  `voice/member-record@d.png`.
- **Reported in:** voice B4.

#### C36. Help text that narrates the buttons beside it, and coined headings

- **Severity:** major. **Component:** the introductions and card headings below.
- **Screens:** Rosters, Subscriptions, Notifications, Reminders, Scheduled, Email types,
  Renew, the member record, the aircraft record, Bulk Email Sent, and Mail delivery.
- **Seen, and what to write instead:**

  | Seen | Write instead |
  | --- | --- |
  | Rosters: "Early each month every active DART's roster goes as a PDF to each of its people ticked to receive it who has an email address. A roster lists the DART's members and friends, its Kind column saying which each one is, and never a deactivated account." | "Early each month, each DART's roster goes out as a PDF to the people checked to receive it. It lists the DART's members and friends." |
  | Subscriptions: "…**Edit** changes its filters, columns, formats, and schedule; **Send now** sends it at once without moving its next date." | "CalDART emails each report to one address on the schedule you choose." |
  | Notifications: "Edit changes its events; Pause stops the emails without forgetting the events." | "Pause stops the emails and keeps the settings." |
  | Reminders: "Each member gets one email per membership per kind. This is the record of what renewal emails were sent to each member." | "Nobody gets the same reminder twice for one membership." |
  | Scheduled: all five cards end "Running it again is harmless: …" | "Safe to run twice." once, in the page introduction |
  | Email types: "A grayed trashcan marks a type a bulk email has used, which cannot be deleted. Take the senders off it instead to stop it being sent." | "A type that has been used can't be deleted. To retire it, remove its senders." |
  | Headings: "Who hears about what", "Where you stand", "Where this account stands", "Where it stands", "Can our email be trusted?" | "Notification emails", "Your membership", "Membership", "Sending progress", "Mail delivery checks" |

  Several of these introductions also touch the button below them, with no gap: the
  Subscriptions introduction, for one.
- **Screenshots:** `voice/sa-admin_reports@d.png`, `voice/sa-system_scheduled@d.png`,
  `voice/sa-admin_reminders@d.png`, `voice/sa-bulk-email_types@d.png`.
- **Reported in:** voice B2; finance #34; ops C7.

#### C37. Failure messages come in five shapes, and about fifteen of them say "Please"

- **Severity:** minor. **Component:** `admin-members/errors.ts:38`, `RecordPaymentPage.tsx:152`,
  `RefundForm.tsx:95`, `PaymentDetailPage.tsx:209`, and the Bulk Email screens.
- **Screens:** the administration, finance, profile, and Bulk Email screens.
- **Seen:**
  - "Something went wrong. Please try again."
  - "Something went wrong. Try again."
  - "…Try again in a moment."
  - "That did not work. Try again." (five places in Bulk Email)
  - "Please reload the page, or contact CalDART…" next to "Try again, or contact CalDART…"
- **Should:** one pattern that names what failed, without "Please". For example: "The
  payment wasn't recorded. Try again in a moment."
- **Reported in:** voice B5.

#### C38. Hints that are whimsical, and numbers and hints that disagree

- **Severity:** minor. **Component:** `features/profile/ProfileFieldsets.tsx`, the aircraft
  forms, the Verify panels, and the checkout and payment copy.
- **Screens:** My profile, the join wizard, New member, the member record, My aircraft,
  Aircraft check, the DART form, the join pay step, and Payments.
- **Seen, and what to write instead:**

  | Seen | Write instead |
  | --- | --- |
  | "Ten digits; the dashes write themselves" | "10 digits, such as 415-555-0100" |
  | "US dollars; commas write themselves." on four fields, repeated under three fields of one Verify panel, while other money fields say "Dollars" | "In US dollars.", once per form |
  | "Three characters, omit the leading K", while the DART form says "Paste KCRQ and the K comes off." | "Leave off the leading K: PAO, not KPAO" |
  | "14 days" on the pay step, "fourteen days" on Payments | one form, "14 days" |
  | "At least 8 characters" in one place, "At least eight characters" in another | "At least 8 characters" |

- **Screenshots:** `voice/sa-profile@d.png`, `ops/leader-ac-verify@820.png`.
- **Reported in:** voice B6, B8; member #16, #19; admin #10; ops A5.

#### C39. Comma slips that change the meaning

- **Severity:** minor. **Component:** the strings below.
- **Screens:** Users and roles, Dashboard, and the finance Overview.
- **Seen:**
  - "Search accounts, grant, or remove roles, and send a password reset." The serial
    comma splits "grant or remove".
  - "All payments, receipts and renewal" is missing the serial comma and should say
    "renewals".
  - The period table caption reads "…the fees, the net and what was refunded".
- **Should:**
  - "Find an account, grant or remove roles, and send a password reset."
  - "All payments, receipts, and renewals."
  - "…the fees, the net, and what was refunded".
- **Screenshots:** `voice/sa-admin_users@d.png`, `voice/sa-dashboard@d.png`.
- **Reported in:** voice B7; member #27.

#### C40. Hints written to the member appear on administrator and verifier forms

- **Severity:** major. **Component:** `features/profile/ProfileFieldsets.tsx`,
  `MemberVerificationPanel.tsx`.
- **Screens:** New member, the member record, and the Verify panel on Member check.
- **Seen, and what to write instead:**

  | Seen | Write instead |
  | --- | --- |
  | "Your primary DART" | "Their main DART" |
  | "I fly rented or borrowed aircraft" | "Flies rented or borrowed aircraft" |
  | "Tick anything you would be willing to help with." | "What they would help with." |
  | "Give your pilot certificate number." (to a verifier checking someone else) | "Enter the pilot certificate number." |

- **Screenshots:** `voice/member-record@d.png`, `ops/verifier-verify-error@1920.png`.
- **Reported in:** admin #9; voice B8; ops M9.

#### C41. Placeholders look like real answers

- **Severity:** minor. **Component:** `features/profile/ProfileFieldsets.tsx` and the aircraft
  form.
- **Screens:** the join profile step, My profile, New member, and the member record.
- **Seen:**
  - "415-555-0100", "95035", "W6ABC", "XXX", and "N172SP" sit in mid-gray in empty boxes
    and look filled in.
  - The N-number error says "for example N172SP" under a box already showing N172SP in
    gray.
- **Should:** remove the placeholders, and give the examples in the hints.
- **Reported in:** member #17; admin #10.

#### C42. Errors and hints sit in different orders, and disagree

- **Severity:** minor. **Component:** `Field.tsx`, the join `AccountStep.tsx`,
  `ChangePasswordPage.tsx`, `AircraftEditor.tsx`, and `RecordPaymentPage.tsx:170`.
- **Screens:** the join account step, Change password, My aircraft, Record a payment, and
  the DART form.
- **Seen:**
  - **Order.** The red error sits above the gray hint.
  - **Password hints.**
    - On the join wizard, the hint "At least eight characters, and not one of the obvious
      ones." stays under the error "This password is too short. It must contain at least
      8 characters."
    - Change password's hint says "not a password you have used elsewhere".
  - **N-number.** The hint "Digits, then up to two letters" contradicts the error "N, then
    digits, then at most two letters".
  - **Record a payment.** The hint "Leave blank for a contribution on its own" sits under
    a select that has no blank choice. Its first option is "No membership".
- **Should:**
  - Put the hint under the label and the error under the field, and hide the hint while
    the error shows.
  - Use one password hint everywhere: "At least 8 characters. Avoid common passwords such
    as password1."
  - Make the N-number hint and error say the same thing.
  - On Record a payment, write "Choose No membership for a gift on its own."
- **Screenshots:** `member/join-member-d-1-short-pw.png`, `voice/recordpay-empty-submit@d.png`.
- **Reported in:** voice F10; member #9, #47; finance #19.

### One thing with several names

#### C43. "Kind" means three different things

- **Severity:** major. **Component:** the column and filter labels on the screens below.
- **Screens:** Members, Users, Compose, Groups, Payments (finance), and Renewals.
- **Seen:**
  - **Three meanings.**
    - Member, Friend, or Donor on Members, Users, Compose, and Groups.
    - Membership or Contribution on the payment list.
    - Automatic renewal or Recurring donation on Renewals.
  - **One filter, three labels.** The same filter reads "Kind: All", "Kind of account:
    Every kind", and "Kind: Any kind".
- **Should:** keep "Kind" for member, friend, or donor. Use "For" on Payments (its filter
  already says "For"), and "Type" on Renewals.
- **Screenshots:** `voice/sa-admin_payments_list@d.png`, `voice/sa-admin_payments_renewals@d.png`,
  `voice/sa-admin_users@d.png`.
- **Reported in:** voice C1.

#### C44. "Payments" means four different things

- **Severity:** major. **Component:** `nav.ts`, `AdminPaymentsPage.tsx`.
- **Screens:** the menu, the finance area, and the member's Payments.
- **Seen:**
  - **Two menu entries.** The menu shows "Payments" under Membership (the person's own) and
    under Administration (the finance area). The account administrator's sidebar lists it
    twice.
  - **A heading that matches neither tab.** The finance area's heading is "Payments" while
    the Overview tab is selected.
  - **The next tab** is also "Payments".
  - **The member's own page** is titled "Payments" too.
- **Should:** call the Administration menu entry and the area heading "Finance", and title
  the first tab "Money overview", which is what the guide already calls it.
- **Screenshots:** `finance/treasurer-overview@1920.png`, `finance/treasurer-mypayments@1920.png`.
- **Reported in:** finance #1; admin #51.

#### C45. "Subscriptions" sounds like membership subscriptions

- **Severity:** major. **Component:** `nav.ts`, `SubscriptionsCard`,
  `NotificationSubscriptionsCard`.
- **Screens:** Subscriptions (`/admin/reports`) and Notifications.
- **Seen:**
  - Under Administration, a volunteer will read "Subscriptions" as membership
    subscriptions, but it means emailed reports.
  - Notifications has its own "New subscription" button.
- **Should:** rename the screen "Emailed reports", with the button "Email a report". On
  Notifications, write "Add an address".
- **Reported in:** finance #31.

#### C46. Giving has five names, and checkout talks about dues to people who pay none

- **Severity:** major. **Component:** `ContributionChooser.tsx:59,63`, `DonatePage.tsx`, the
  finance payment list.
- **Screens:** Donate, the join pay step (friend), Payments, Renew, Become a member, and
  Payments (finance).
- **Seen:**
  - **Donate.**
    - The menu says "Donate", the lede says "gift", and the card is "Make a
      contribution" with the legend "ADD A CONTRIBUTION".
    - It says "a contribution on top of your dues is tax deductible", on a page with no
      dues in sight. A friend on the join pay step reads the same line, though friends pay
      no dues.
  - **The member's Payments** has the eyebrow "GIVING" over "Recurring donation".
  - **Finance.**
    - It has "Contributions" and "Donors" tabs.
    - The payment list's "For" filter defaults to "Dues or gifts", while its own options
      and the guide say Membership and Contribution.
    - A gift-only row reads Plan "Contribution only" and Kind "Contribution", the same
      fact twice.
- **Should:**
  - Say "donation" wherever a member gives, and keep "contribution" for checkout add-ons
    and tax statements.
  - Drop "on top of your dues" where there are no dues: "Gifts to CalDART, a 501(c)(3),
    are tax deductible."
  - Default "For" to "Membership or contribution".
  - Show a dash under Plan when no plan was bought.
- **Screenshots:** `voice/sa-donate@d.png`, `voice/sa-renew@d.png`, `voice/sa-payments@d.png`,
  `member/join-friend-p-4-pay.png`.
- **Reported in:** voice C2; finance #6; member #15, #51.

#### C47. Register, registry, and aircraft database

- **Severity:** major. **Component:** `AircraftRegisterPage.tsx`, `MyAircraftPage.tsx`, and the
  Health page.
- **Screens:** Aircraft register, My aircraft, and Health and database.
- **Seen:**
  - **Aircraft register.** The header reads "Aircraft register … Registry as of
    10/04/2026". The first is CalDART's own list, and the second is the FAA download, but
    nothing says which.
  - **My aircraft.** "Search the aircraft register" (CalDART's list) sits next to the "FAA
    registry".
  - **Health and database** calls the FAA data "Aircraft database".
- **Should:** "FAA data as of 10/04/2026"; "Search CalDART's aircraft list"; and "FAA aircraft
  data" on the System page.
- **Screenshots:** `voice/sa-admin_aircraft@d.png`, `voice/sa-system_health@d.png`.
- **Reported in:** voice C3; member #46; admin #27.

#### C48. Renewal states, reminder stages, and event names differ from screen to screen

- **Severity:** major. **Component:** `reminderSchedule.ts:21-22,42`, `RenewalsPage.tsx`, the
  member ledger page, `ReminderLog.tsx`, and the notification event catalog.
- **Screens:** Renewals, a member's money history, Reminders, Scheduled, and Notifications.
- **Seen:**
  - **Renewal states.**
    - The guide's states for a member's money history are "Waiting for the first
      payment", "Paused after failed charges", and "Turned off".
    - Renewals uses "Awaiting a method", "Paused", and "Off".
    - The money history's "Current" chip does not say what is current.
  - **Reminder stages.**
    - One stage is called Expired, Lapsed, and Lapsed reminder.
    - Reminders says the last stage goes "30 days after", while Scheduled says "through
      the six days after".
    - The Reminders filter calls the stages "kinds": "All kinds", and "one email per
      membership per kind".
  - **Event names.** Notifications says "Automatic payment turned on/off/declined", while
    Renewals says Automatic renewal and Recurring donation.
- **Should:**
  - Use one set of renewal state names, matching the guide.
  - Label the chip "Membership: Current".
  - Call the reminder steps "stages", with one name each, and "Any reminder" in the
    filter.
  - Use Renewals' names in the notification events.
- **Screenshots:** `finance/treasurer-ledger@1920.png`, `finance/accountadmin-reminders@1920.png`.
- **Reported in:** finance #20, #36, #39; voice C4.

#### C49. "Succeeded" where a volunteer would say "Paid"

- **Severity:** major. **Component:** `StatusChip` labels for payment status.
- **Screens:** the member record's Payments tab, Dashboard Recent payments, the member's
  Payments, and one payment.
- **Seen:**
  - The payment status chip says "Succeeded", the card processor's word.
  - The payment page's subtitle "John Freeman · Succeeded" repeats the chip beside it.
- **Should:** "Paid" on every screen, and drop the status from the subtitle.
- **Reported in:** admin #19; finance #14.

#### C50. Smaller naming splits

- **Severity:** minor. **Component:** the labels below.
- **Screens:** Payments (finance), one payment, Sent emails, Reports, Health and database,
  Mail delivery, Renewals, the aircraft record, and Aircraft check.
- **Seen:**
  - **Reconciled and Matched.** The filter "Reconciled: Matched or not", the field
    "Matched on", and the note "reconciled date".
  - **The email log.** It is "Sent Emails" in the menu, "Email log" as a report, and
    "Filter the email log".
  - **Health words.** Health says OK, Warning, and Attention, while Mail delivery says
    Good, Warning, and Problem.
  - **Refused and Failed.** Renewals says "Refused" and "Last refusal" where other screens
    say "Failed".
  - **Pilots.** "Pilots who fly this aircraft" against "Members who fly it".
- **Should:** pick one word for each and use it everywhere.
- **Reported in:** voice C4.

#### C51. Button verbs and back links vary for the same act

- **Severity:** minor. **Component:** the buttons below and `Page`'s back control.
- **Screens:** New member, New aircraft, Add a DART, Templates, Groups, Subscriptions, Email
  types, Compose, Record a payment, the member record, the aircraft record, and the user
  record.
- **Seen:**
  - **Opening a form:** New member, New aircraft, New template, New group, New
    subscription, Add a DART, Add an email type, and Write a new email.
  - **Submitting it:** Add DART, Add aircraft, Add type, Make the group, Create member, and
    Save template (for a fresh template).
  - **Saving and leaving.**
    - There are eight versions of Save.
    - "Reset form" stands in for Cancel.
    - Record a payment has no Cancel at all.
  - **Back links** appear ten ways: a button on the member record, a text link on the user
    record, missing on the aircraft record, "Back to X", "See every X", "All recipient
    groups", and "← Back to search".
  - **Where the form opens.** New aircraft and Add a DART open inline.
- **Should:**
  - "New X" opens a form, "Add X" submits it, "Save changes" saves an edit, and "Cancel"
    leaves.
  - Every back link is a link reading "Back to X".
- **Screenshots:** `voice/user-deactivate-confirm@d.png`, `voice/recordpay-empty-submit@d.png`.
- **Reported in:** voice C5; admin #28, #50, and its shared-component list; finance #19.

### Dates, times, money, and status display

#### C52. Two clock formats, and times with no time zone

- **Severity:** major. **Component:** `DateText.tsx` (`formatDateTime` and `formatDateAt`).
- **Screens:** Dashboard, Payments, Renewals, Sent emails, Mail delivery, Reminders, the
  Bulk Email schedules, and Drafts.
- **Seen:**
  - **24-hour, with no zone:** Dashboard "05/04/2026 16:38", Renewals "05:29", and Sent
    emails "05:33".
  - **12-hour:** Mail delivery "10/04/2026 at 5:34 AM", and the Bulk Email schedules.
  - **Reminders** text says "07:00".
  - **Drafts** alone labels its time column "(Pacific time)".
  - **The same payment.** It shows "04/28/2026 19:52" on the Dashboard and the date only
    on Payments.
- **Should:** "10/04/2026 at 5:33 AM" Pacific everywhere, with `formatDateTime` delegating
  to `formatDateAt`. In prose, write "7:00 AM".
- **Screenshots:** `voice/sa-dashboard@d.png`, `voice/sa-admin_payments_renewals@d.png`,
  `voice/sa-system_emails@d.png`, `voice/sa-bulk-email_mail-delivery@d.png`.
- **Reported in:** voice D1; member #26; finance #37.

#### C53. Monospace digits in headlines and mid-sentence

- **Severity:** minor. **Component:** the number and date styles in `base.css`.
- **Screens:** Dashboard, the finance Overview, Users and roles, Members, My aircraft, and
  Mail delivery.
- **Seen:**
  - **Typewriter font.** Dates and money are set in a typewriter font:
    - the Dashboard's large "EXPIRES 04/27/2027";
    - the Payments overview tiles;
    - mid-sentence in "…is on: $145.00 on 04/27/2027."
  - **Inconsistent between screens.**
    - Emails are monospace on Users and proportional on Members.
    - My aircraft and Mail delivery use proportional digits.
  - **The effect.** It reads like a terminal.
- **Should:** use the body font with `tabular-nums`, which keeps columns of money aligned.
- **Screenshots:** `voice/mem-dashboard@d.png`, `voice/sa-admin_payments@d.png`.
- **Reported in:** voice D2.

#### C54. Status is shown four ways, one of them by color alone

- **Severity:** major. **Component:** `StatusChip.tsx`, `StatusDot`,
  `SubscriptionsCard.tsx:140`, and `NotificationSubscriptionsCard.tsx:98`.
- **Screens:** Members, Aircraft register, Drafts, Email types, Users and roles, DARTs,
  Payments, Renewals, Dashboard, My aircraft, Sent emails, Subscriptions, Notifications,
  and the member record's Payments tab.
- **Seen:**
  - **Four ways.**
    - A bare dot and its value: Members, Aircraft register, Drafts, and Email types.
    - A boxed chip: Users and roles, DARTs, Payments, Renewals, Dashboard, and My
      aircraft.
    - A plain word: Sent emails.
    - A dot with no word: the Subscriptions and Notifications "Active" columns, where
      paused and active differ only by color.
  - **The project convention is dots,** not chips.
  - **Users and roles** gives every row three or four chips: a gray Member role chip, the
    membership chip, and a green Active chip.
- **Should:**
  - `StatusDot` with its word, everywhere.
  - On Users and roles, drop the Member and Active chips, and show membership with the dot
    as Members does.
- **Screenshots:** `voice/sa-admin_members@d.png`, `voice/sa-admin_users@d.png`,
  `voice/sa-system_emails@d.png`, `voice/crop-subs-delete-confirm@d.png`.
- **Reported in:** voice E2; admin #38, #42, and its shared-component list.

#### C55. The status chip fails contrast on striped rows

- **Severity:** major. **Component:** `StatusChip`'s translucent background over the
  zebra-striped `DataTable` rows.
- **Screens:** DARTs, the aircraft record, Users and roles, the payment list, Renewals, one
  payment, and a member's money history.
- **Seen:**
  - The Active chip measures 4.06:1 on striped rows (4.46:1 in `sectional`).
  - It fails on the aircraft record, and 20 times on Users and roles.
  - axe's `color-contrast` findings on these screens are this chip (see the axe results
    below).
- **Should:** give the chip an opaque background, or text dark enough to pass on both row
  colors. C54 removes most chips anyway.
- **Reported in:** admin #37; axe `color-contrast`.

### Verification marks

#### C56. Marks and checks appear where there is nothing to verify

- **Severity:** major. **Component:** the verification card on the member record,
  `VerifiedMark.tsx`, `MemberStatusCard.tsx`, and `MemberVerificationPanel.tsx`.
- **Screens:** My profile, the member record, the aircraft record, and Member check.
- **Seen:**
  - **My profile.** A green Verified mark sits under "Pilot certificate: Not a pilot", and
    under an empty "Medical expires" with Medical "None". `profile.rst` says an item marked
    not held "shows no mark".
  - **Red "Not verified" on nothing.** The member record shows three red **Not verified**
    chips on a record with nothing to check: *Not a pilot*, *None*, and *Not provided*. The
    aircraft record does the same for "Insurance: Not on file".
  - **Member check.**
    - A non-pilot shows "Not a pilot · Not verified" and "None · Not verified".
    - The band lists "Certificate not verified" and "Medical not verified" beside "No
      medical on file".
    - The Verify panel offers "Pilot certificate verified".
    - Another card shows "None · Verified".
- **Should:** show no mark and no checkbox for an item that is not held, as `profile.rst`
  says. Give the band one reason.
- **Screenshots:** `member/member-profile-d.png`, `admin/crops/record-top.png`.
- **Reported in:** member #37; admin #13; ops M7.

#### C57. A lapsed medical reads as Verified, and a pending check reads as an alarm

- **Severity:** major. **Component:** `VerifiedMark.tsx` and the verification card.
- **Screens:** the member record, My profile, and My aircraft.
- **Seen:**
  - **Member record.** "BasicMed · expires 02/02/2025" sits beside a green **Verified**
    chip, with no expired marker. The Members list shows a red ✗ for the same person.
  - **My profile and My aircraft.** "Not yet verified" is drawn in alarm red, though it is
    the normal waiting state. Waiting states elsewhere are gray or amber.
- **Should:** show **Expired** beside a lapsed date, whatever its verification. Draw a
  pending check in neutral or amber.
- **Screenshots:** `admin/crops/record-top.png`, `voice/sa-profile@d.png`.
- **Reported in:** admin #12; voice E3; member #44.

#### C58. Member check and Aircraft check disagree about the same pilot and airplane

- **Severity:** major. **Component:** `MemberStatusCard.tsx`, `AircraftStatusCard.tsx`;
  `docs/user/admin/aircraft-check.rst`.
- **Screens:** Member check and Aircraft check.
- **Seen:**
  - **Insurance.** On a member card, N100ML shows a green "Insured" chip with a small gray
    "not verified" after it. Aircraft check shows the same airplane as red NOT VERIFIED.
  - **Friends shown as expired.** On Aircraft check, "Members who fly it" shows Collin
    Hill, Frances Lee, and Ryan King as "Member expired", though they are friends on
    Members.
  - **Unverified medicals.** "Medical current" is green even when nobody has verified the
    medical, so a pilot can look cleared on Aircraft check and be NO-GO on Member check.
- **Should:**
  - Use one rule on both screens, for example an amber "Not verified" chip on the member
    card.
  - On Aircraft check, show "Friend", use Member check's GO or NO-GO, and link each name to
    their card.
  - Update `aircraft-check.rst`.
- **Screenshots:** `ops/verifier-go-card@390.png`, `ops/verifier-ac-N100ML@1920.png`,
  `ops/leader-ac-card@1920.png`.
- **Reported in:** ops M8, A2.

### Duplicate accessible names

#### C59. Rows of buttons and links that all have the same name

- **Severity:** major. **Component:** each table's action cells. The fix is an
  `aria-label` (or visually hidden text) naming the row.
- **Screens:** My aircraft, My profile, Payments (member), the member record, DARTs,
  Renewals, Contributions, Subscriptions, Notifications, Health and database, and
  Scheduled.
- **Seen, and the name to give instead:**

  | Screen | Seen | Name instead |
  | --- | --- | --- |
  | My aircraft | every "Edit" (the trashcans are correctly "Remove N1049X") | "Edit N1049X" |
  | My profile | three boxes all "ext." | "Phone extension", "Alternate phone extension", "Emergency contact phone extension" |
  | Payments (member) | every "Receipt", which downloads a PDF silently | "Receipt for 04/28/2026 (PDF)" |
  | Member record | every term row's "Edit" | the term's dates |
  | Member record, Payments tab | the statement button reads only "2024" | see A10 |
  | DARTs | 16 "Edit", 16 "Visit", member counts "2", "3" | "Edit Napa", "Napa's website", "Napa: 1 member" |
  | DARTs | person rows "Remove person 1" | the person's name |
  | Renewals | 13 "Turn off" | "Turn off automatic renewal for Charles Roberts" |
  | Contributions | 19 "Statement" under a STATEMENT column | "2026 statement for Joseph Smith", column "Download" |
  | Subscriptions, Notifications | Edit, Send now, Pause, and "Delete subscription" on every row | the report or address |
  | Health and database | every "Download" | the file's name |
  | Scheduled | five "Run now" | "Run renewal reminder emails now", and so on |

- **Reported in:** member #38, #45, #49; admin #23, #36, #40; finance #22, #28, and its
  shared-component list; ops H3, C9.

### The guide

#### C60. Help on the signed-out screens leads back to sign-in

- **Severity:** major. **Component:** the guide's login gate in Django, and the header's Help
  link.
- **Screens:** Sign in, Forgot password, and Join.
- **Seen:** Help opens `/docs/member/sign-in/` in a new tab. The guide needs the person to be
  signed in, so the tab shows `/portal/login?next=/docs/member/sign-in/`. The person who
  cannot sign in is sent to sign in again.
- **Should:** serve the signed-out guide pages (sign-in, forgot password, reset password,
  join, and verify email) without sign-in, or show the help inline.
- **Screenshots:** `member/out-help-login-viewport-d.png`.
- **Reported in:** member #1.

#### C61. Guide pages that contradict the screen

- **Severity:** minor. **Component:** `docs/user/`.
- **Screens:** Scheduled. The index below covers every other screen.
- **Seen:**
  - `admin/scheduled.rst` says the Reminder schedule card sits "beside" the reminders; it sits
    below them.
  - `scheduled.rst` says the Bounces panel shows "Bounce checking is off"; that appears
    only after Run now (see O20).
  - `admin/notifications.rst` promises five notification event groups, including Callouts; the account
    administrator sees four.
  - The guide uses "tick" and "in date" (C33).
- **Should:** fix these pages, and fix the guide in the same change as each finding below.
  In the third column, **guide** means the guide is the thing to change, **screen** means
  the guide is right and the screen should follow it, and **both** means both change.

  | Guide page | Finding | Change |
  | --- | --- | --- |
  | `member/dashboard.rst` | M17 (lapsed member content), C21 (menu groups) | guide |
  | `member/profile.rst` | C56 (marks on items not held) | screen |
  | `member/renew.rst` | M36 (a lapsed membership renews from today) | screen |
  | `admin/new-member.rst` | A3 (only the email required) | both |
  | `admin/member-record.rst` | A9 (raw status and source words) | guide |
  | `admin/user-record.rst` | A22 ("recorded under your name", with no history shown) | screen |
  | `finance/payment-list.rst` | C19 ("Click a column heading to sort by it") | either |
  | `finance/member-ledger.rst` | C48 (renewal state names) | screen |
  | `finance/renewals.rst` | F9 (decline reason in the member's words) | both |
  | `admin/subscriptions.rst` | F14 (contributions periods) | both |
  | `admin/aircraft-check.rst` | C58 | guide |
  | `bulk-email/email-types.rst` | C1 (the description "read[s] in full") | screen |
  | `admin/new-member.rst` | O13 (a created account "can sign in now") | either |

- **Reported in:** ops C10; finance #39; voice B1; and the findings in the table.

---

## Findings by screen

Each finding below is specific to one screen and is not covered above.

### Member

#### Sign in (`/portal/login`), signed out

**M1. Sign in checks only the email.**
- *Minor, consistency.*
- With both boxes empty, Sign in flags the email but not the password
  (`member/out-login-empty-d.png`).
- **Should:** check both fields and show both errors (`LoginPage.tsx`).

**M2. The sign-in page is bare, and its header offers Sign in.**
- *Minor, appearance and obviousness.*
- **Seen:**
  - The header shows a **Sign in** button on the sign-in page, on Forgot password, and on
    its sent state.
  - At 1920 the page is a small form in a sea of gray, and nothing says what CalDART or
    the portal is.
- **Screenshots:** `member/out-login-d.png`, `voice/signin-login@d.png`.
- **Should:** hide the header button on these screens, and add one line saying what the
  portal is for.

#### Forgot password and its sent state

**M3. No gap between paragraphs.**
- *Minor, layout.*
- "…expires in a few days." runs straight into "Nothing arrived?…"
  (`member/out-forgot-sent-d.png`).
- **Should:** fix the `AuthShell` paragraph margins.

**M4. The expiry is vague.**
- *Minor, wording.*
- The page says "expires in a few days", while the email says 3 days.
- **Should say:** "The link works once and expires in 3 days."

#### Join wizard (`/portal/join/*`), signed out

**M5. The unselected option card looks disabled.**
- *Major, appearance.*
- **Seen:**
  - The unselected card has a darker gray fill than the selected one, so "Join as a
    friend", the "Life" plan, and "I changed my mind…" all read as unavailable.
  - axe flags the muted text on these cards (`.join-kind__description.muted`,
    `.plan-card__term.muted`) at 4.24:1.
  - The same cards appear on Renew, Become a member, and Payments → Change.
- **Screenshots:** `member/out-join-d.png`, `member/join-member-d-4-pay.png`.
- **Should:** draw unselected cards white with a border, and tint the selected one
  (`join.css`, checkout's `plan-card`).

**M6. Errors arrive one round at a time.**
- *Minor, consistency.*
- With everything empty, only the email is flagged. The missing names appear only after a
  second press (`member/join-member-d-1-empty-submit.png`).
- **Should:** check every field at once (`AccountStep.tsx`).

**M7. "Already a member? Sign in" leaves out friends.**
- *Minor, wording.*
- **Should say:** "Already have an account? Sign in".

**M8. The lede and the member card disagree.**
- *Minor, voice.*
- **Seen:**
  - The lede says "Membership is annual or for life; the pay step shows the prices. It
    takes about three minutes."
  - The card below says "Pay annual dues now".
- **Should say:**
  - In the lede: "Joining takes about three minutes."
  - On the card: "Pay yearly or lifetime dues and you are a member right away."

**M9. The step is shown twice, and the card changes width.**
- *Minor, layout.*
- **Seen:**
  - The step indicator and the eyebrow "STEP 2 OF 5 · JOINING AS A MEMBER" say the same
    thing.
  - On the account and verify steps, the card's left edge sits at 720 px against the
    header's 592 px. It then goes full width on the profile and pay steps.
- **Should:** drop the eyebrow, and use one width for every step.

**M10. The pay step is a card inside a card, with repeated headings.**
- *Major, layout.*
- **Seen:**
  - H1 "Join CalDART", then a card titled "Pay your dues", then an inner card with
    "MEMBERSHIP / Join CalDART / MEMBERSHIP".
  - At 390 the two layers of padding squeeze the text to about 230 px.
  - The same embedded Checkout appears on Renew, Become a member, and Donate.
- **Screenshots:** `member/join-member-d-4-pay.png`, `member/join-member-p-4-pay.png`.
- **Should:** when Checkout is embedded, drop its own card, eyebrow, and title
  (`features/checkout`).

**M11. "I changed my mind, I just want to be a friend" looks like a price plan.**
- *Major, wording.*
- It is a third price card in large serif type, and it wraps over three lines on a phone.
- **Should:** make it a quiet link under the plans: "Join as a friend instead (no dues)".

**M12. The friend's pay step points nowhere.**
- *Major, obviousness.*
- **Seen:**
  - "No thank you" is preselected, the total is $0.00, and the page says "Choose a
    contribution to continue."
  - Yet the only button is "Not now".
- **Screenshots:** `member/join-friend-p-4-pay.png`.
- **Should:** with "No thank you" chosen, show **Continue without a gift**. The wording
  about dues is C46.

**M13. "Charging this card" before any card is chosen.**
- *Minor, wording.*
- "We will email you 14 days before charging this card" shows before any card is chosen,
  and even when PayPal may be used.
- **Should say:** "…before each charge to your card or PayPal account". The number's
  spelling is C38.

**M14. State and county contradict each other.**
- *Major, wording.*
- State defaults to "CA — California", while California county defaults to "Not in
  California" (`member/join-member-d-3-profile.png`).
- **Should:** default the county to "Choose a county" (`ProfileFieldsets.tsx`).

**M15. The profile step's lede runs straight into the "CONTACT" legend, with no space.**
- *Minor, layout.*

**M16. A friend leaves the wizard early.**
- *Minor, obviousness.*
- A friend gets the menu from the pay step on, and reloading the pay step jumps to Done
  (`member/join-friend-p-4-pay.png`).
- **Should:** keep the friend in the wizard until they press Not now or pay.

#### Dashboard (`/portal/`), member, expired, and friend

**M17. Lapsed members are told nothing is published.**
- *Major, obviousness. The guide must change too.*
- **Seen:**
  - The expired member's Member content card says "Nothing published yet. Members-only
    pages will appear here as soon as CalDART publishes them."
  - The current member sees three pages in the same card.
  - It is untrue and gives no way forward. `dashboard.rst` documents it as intended.
- **Screenshots:** `member/expired-dash-d.png`, `member/member-dash-d.png`.
- **Should say:** "Members-only pages are open to current members. Renew to read them
  again.", with a **Renew** link. Fix `dashboard.rst` in the same change.

**M18. "Stop it" is ambiguous.**
- *Major, wording.*
- The Make me a friend panel (Dashboard and My profile) offers "Keep the contribution",
  "Stop it", and "Cancel". "Stop it" reads as "stop this change"
  (`member/member-profile-makefriend-viewport-d.png`).
- **Should say:** "Become a friend and keep giving $100 a year", "Become a friend and stop
  the $100", and "Cancel".

**M19. Recent payments and Payments name the same payment differently.**
- *Minor, consistency.*
- Recent payments shows Plan "Annual" for a $345.00 payment that Payments calls "Annual
  and contribution".
- **Should:** use Payments' wording. The date format is C52.

**M20. The auto-renewal line is clumsy, and a friend sees renewal wording.**
- *Minor, wording.*
- **Seen:**
  - "Automatic renewal and contribution is on: $145.00 on 04/27/2027."
  - A friend sees "Automatic renewal is off." and "All payments, receipts and renewal",
    though a friend has nothing to renew.
- **Should say:** "Automatic renewal is on: $145.00 will be charged on 04/27/2027." Hide
  the renewal wording for friends.

**M21. The friend's card repeats its heading.**
- *Minor, wording.*
- The heading "You are a friend of CalDART" is repeated word for word in the text below
  it.

**M22. Quick links repeat the whole menu.**
- *Major, appearance.*
- **Seen:**
  - The card repeats the menu entry for entry. For sysadmin that is all 33 entries, about
    two-thirds of the 2,823 px page at 1920 and most of the page at 390.
  - The two-column grid leaves a 130 px gutter and ends 380 px short of the header rule.
  - The members-only links use the CMS's Title Case ("Members Only", "Documents and
    Links").
- **Screenshots:** `voice/sa-dashboard@d.png`, `voice/sa-dashboard@p.png`.
- **Should:** drop Quick links, or replace them with three to five next steps chosen by role
  (`DashboardPage.tsx:187`).

**M23. A downgrade sits beside the main action.**
- *Minor, obviousness.*
- **Make me a friend** sits beside **Renew** as an equal button.
- **Should:** make it a quiet link, or keep it on My profile only.

#### My profile (`/portal/profile`)

**M24. Loose alignment and a duplicate link.**
- *Minor, layout.*
- **Seen:**
  - The deactivation password box is full width, while every other field is half width.
  - "The planes you commonly fly are kept on My aircraft." floats between cards and
    duplicates the **My aircraft** button.
  - At 820 the extension boxes wrap under their phone fields.
- **Should:** align these with the other fields, and drop the sentence. The button's
  position is C28.

**M25. One Save at the foot of a long form.**
- *Minor, obviousness.*
- The form is about 2,860 px tall on desktop and 4,550 px on a phone, with one Save at the
  bottom.
- **Should:** add a save bar that stays on screen once anything changes.

#### My aircraft (`/portal/profile/aircraft`)

**M26. Edit is a dead end for most planes.**
- *Major, obviousness.*
- **Seen:**
  - Every plane has Edit. For a plane picked from the list (one someone else added), it
    says "Someone else added this aircraft. Ask a CalDART account administrator to correct
    it."
  - A member cannot update the insurance on the plane they fly, and is not told how to
    reach an administrator.
- **Screenshots:** `member/own-aircraft-edit-d.png`.
- **Should:** hide Edit on those planes, or let a member update insurance on any plane in
  their list. Name the administrator, or give a contact link.

**M27. A registry pick is refused only at the end.**
- *Major, obviousness.*
- In **Add a new aircraft**, the FAA registry list offers N30075, which CalDART already
  has. The form fills in, the person completes it, and only then gets "An aircraft with
  this N-number is already on file." (`member/own-newac-added-d.png`).
- **Should:** at the moment of the pick, say "N30075 is already on file" and offer **Add it
  to my list**.

**M28. The add form copies the search text.**
- *Major, obviousness.*
- Searching "piper" puts "PIPER" in N-number, which then fails on save
  (`member/own-aircraft-new-errors-d.png`).
- **Should:** copy only text that looks like an N-number.

**M29. Two names for each insurance state, and unlabeled amounts.**
- *Major, wording.*
- **Seen:**
  - The search list says Insured, Insurance expired, and No insurance on file.
  - The person's own list says Current and Not on file.
  - "$2,000,000 / $100,000 · exp 06/17/2028" has no labels.
- **Should:**
  - Use one set of names in both lists.
  - Write "Liability $2,000,000 per occurrence, $100,000 per person · insured to
    06/17/2028".
  - The red "Not yet verified" is C57.

**M30. The list's heading and instruction are unclear, and Enter does nothing.**
- *Minor, wording.*
- **Seen:**
  - The list is headed "Attached aircraft".
  - "Click on an aircraft to add it to your list" is the only instruction.
  - Enter in the search box does nothing.
- **Should:** say "Your aircraft", and let Enter add the only match. The register wording is
  C47.

**M31. The results list and saved values don't line up.**
- *Minor, layout.*
- **Seen:**
  - The results list is 545 px wide inside a 1,190 px card.
  - Blank liability boxes come back as "0" after saving (`member/own-newac-editown-d.png`).
- **Should:** run the results the card's width, and keep blank values blank. The hint that
  contradicts its error is C42.

#### Payments (`/portal/payments`), member

**M32. Muddled wording.**
- *Minor, wording.*
- **Seen, and what to write instead:**
  - The lede "Your recurring donation, whether CalDART renews your membership for you, your
    receipts, and your contribution statements." lists the cards out of order. Write
    "Your automatic renewal, recurring donation, payments and receipts, and tax
    statements."
  - "Contribution renewed with it" is an awkward label. Write "Yearly contribution".
  - "Set one up on the Donate screen" sits next to a **Set up** button that goes there.
    Drop the sentence.
  - "the 501(c)(3) wording" is jargon. Write "the wording your tax preparer needs".

**M33. Change opens a radio group with one option.**
- *Minor, obviousness.*
- Change opens a "Membership" radio group whose only option is Annual
  (`member/member-payments-change-d.png`).
- **Should:** show the plan as plain text when there is nothing to choose.

#### Donate (`/portal/donate`)

**M34. Donate opens on "No thank you".**
- *Major, obviousness.*
- On a page whose only job is giving, "No thank you" is preselected, the total is $0.00,
  and the text says "Choose a contribution to continue." (`member/member-donate-d.png`).
- **Should:** drop "No thank you" here and preselect nothing. The wording about dues is
  C46.

**M35. The "Other amount" hint wraps above the box.**
- *Minor, layout.*
- The hint wraps into a 220 px column above the box, while every other screen puts hints
  below (`member/member-donate-other3-d.png`).

#### Renew (`/portal/renew`)

**M36. Expired members get wrong advice.**
- *Major, wording.*
- The page says "A renewal starts the day after your current term ends, so there is no
  penalty for renewing early." `renew.rst` says a lapsed membership renews from today
  (`member/expired-renew-d.png`).
- **Should say,** for a lapsed member: "Your new year starts today."

**M37. Renew doesn't mention automatic renewal.**
- *Major, obviousness.*
- A member with automatic renewal on sees the full checkout, with "Renew automatically each
  year" unchecked, and no mention that $145.00 will be charged on 04/27/2027. They may pay
  twice (`member/member-renew-d.png`).
- **Should say:** "Automatic renewal is on: we will charge $145.00 on 04/27/2027. You do
  not need to do anything." Put the checkout behind **Renew now anyway**.

**M38. The "Where you stand" card is centered and narrower than the page.**
- *Major, layout.*
- Its left edge is at 736 px, while the checkout card's is at 304 px
  (`member/member-renew-d.png`).
- **Should:** left-align it at full width.

#### Change email

**M39. Change email never shows the current address.**
- *Minor, obviousness.*
- **Should say:** "Your address is member@example.org. We will send a link to the new one;
  sign in with it after you open the link."

#### Messages (`/portal/messages`)

**M40. The lede is awkward.**
- *Minor, wording.*
- It reads "The emails CalDART has sent you along with other members and friends, to read
  again here."
- **Should say:** "Copies of the emails CalDART sent to members and friends." The empty
  state's stray rule is C20, and the width is C28.

#### Email preferences (`/portal/email-preferences`)

**M41. A missing gap, and a jargon type name.**
- *Minor, consistency and wording.*
- **Seen:**
  - The footnote paragraph runs into the last item, with no gap
    (`member/own-prefs-toggled-d.png`).
  - The type name "Operational" is jargon.
- **Should:** add the gap, and suggest a plainer default name such as "Meetings and
  training". An administrator names these types. The "Saved." message is C9.

### Administration

#### Members list (`/portal/admin/members`), account administrator and DART leader

**A1. The count and one column header use the wrong words.**
- *Minor, wording.*
- **Seen:**
  - "51 members match these filters" (53 for a leader) also counts friends.
  - "Membership Exp." is an abbreviation.
- **Should say:** "51 people match", and "Expires". Reset and the empty state are C23 and
  C20.

**A2. A leader has no direct way to their own roster.**
- *Minor, obviousness.* Leader.
- A leader's roster is this list filtered to their DART, but the DART filter starts at
  "Any" (53 people).
- **Should:** default the filter to the leader's DART, or add a "My DART" choice.

#### New member (`/portal/admin/members/new`), account administrator

**A3. A member with only an email and a name is refused.**
- *Blocking, obviousness. The guide must change too.*
- **Seen:**
  - The empty, unmarked Phone box turns red with "Use a ten-digit number like
    415-555-0100.", and the API returns 400.
  - The guide says "Only the email address is required".
- **Screenshots:** `admin/crops/dup-phone.png`.
- **Should:** either accept a blank phone for an account an administrator creates, or mark
  Phone required with "Enter their phone number.". Make `new-member.rst` match either way.
- **Where:** `backend/apps/members/api/profile_serializers.py` (`phone` is required), and
  `MemberCreatePage.tsx`.

**A4. Empty required fields get a format message.**
- *Major, wording.*
- An empty Email box gets "Use an email address like name@example.org.", and an empty
  Phone box gets the same kind of sentence.
- **Should say:** "Enter their email address." and "Enter their phone number."

**A5. The fieldsets are spaced unevenly.**
- *Minor, layout.*
- The Account fieldset's row gaps (38 to 50 px) are larger than the Contact fieldset's,
  and the Ratings divider is dotted while the others are solid.

#### Member record (`/portal/admin/members/:id`), account administrator

**A6. The summary strip says Friend for a member without a term.**
- *Major, wording.*
- **Seen:**
  - A member created without a term reads **Friend** · "expires –" · "joined –", while
    Kind of account says Member.
  - A deactivated paying member also turns to **Friend**.
  - "never edited" stands alone.
- **Should say:**
  - "No membership yet: grant a term on Memberships" for a member without a term.
  - "Membership set aside while deactivated" for a deactivated one.
  - "Profile never edited".

**A7. Verify opens a second editor.**
- *Major, obviousness.*
- Verify opens a second editor for certificate, medical, and photo ID, while the same
  fields stay editable in the form below (`admin/aa-record-verify-panel@wide.png`).
- **Should:** make Verify mark items as checked, and leave editing to the form. Escape and
  focus are C6 and C7.

**A8. The member's aircraft are buried at the foot of the form.**
- *Major, obviousness.*
- The aircraft appear only as "Aircraft on file: N52678", beside Save changes at the foot
  of a 3,600 px form.
- **Should:** add an Aircraft card near the top.

**A9. Membership history prints raw values.**
- *Major, wording. The guide must change too.*
- **Seen:**
  - Status shows as `active`, `expired`, and `canceled`, and Source as `payment` and
    `manual`.
  - The row's edit select says "Active".
  - `member-record.rst` documents the lower-case words.
- **Should say:** *Active*, *Paid online*, and *Granted by hand*. Fix `member-record.rst` in
  the same change.

**A10. The statement button is labeled only with the year.**
- *Major, wording.* Payments tab.
- The button reads just "2024".
- **Should say:** "Download 2024 statement". "Succeeded" is C49.

**A11. Three small gaps.**
- *Minor, obviousness.*
- **Seen:**
  - Grant term is grayed out until a plan is chosen, with no hint why.
  - The Danger zone buttons have no explanation until pressed.
  - Make a friend's text says the automatic renewal "is canceled", for a member who has
    none.
- **Should:** add a hint by Grant term, a line under each Danger zone button, and only
  mention automatic renewal when there is one.

#### Aircraft register (`/portal/admin/aircraft`), account administrator and system administrator

**A12. "No policy" shows as a gray dot and a dash.**
- *Minor, wording.*
- **Should say:** "Not on file". "Registry as of…" is C47.

**A13. The Coverage policy values don't line up.**
- *Minor, layout.* System administrator.
- In the Coverage policy card, one value starts at 221 px and the next at 229 px.

#### Aircraft record (`/portal/admin/aircraft/:id`), account administrator

**A14. There is no way back to the register.**
- *Major, obviousness.*
- The only way back is the sidebar. *Back to the register* exists only on the "No such
  aircraft" page (`AircraftRecordPage.tsx`, around line 77).
- **Should:** add Back to the register to the page header.

**A15. An all-caps eyebrow, a contradictory history, and an all-caps owner.**
- *Minor, appearance and wording.*
- **Seen:**
  - "LAST UPDATED … BY CURTIS WHITFIELD" is set as an all-caps eyebrow.
  - A seed record says "Last updated" above "No change is recorded".
  - An owner filled from the registry stays in all caps.
- **Should:** move the update line out of the eyebrow, hide it when no change is recorded,
  and title-case the owner.

**A16. The Pilots chips wrap unevenly.**
- *Minor, layout.*
- In the Pilots card, the chips wrap unevenly inside a 600 px column.

#### DARTs (`/portal/admin/darts`), account administrator

**A17. After a refused submit, the first press of Add DART often does nothing.**
- *Major, obviousness.*
- **Seen:**
  - Leaving Airports clears its error line, the button jumps up about 20 px, and the
    click misses. Nothing is sent, and a second press works.
  - Reproduced in the administration pass's scripts.
- **Screenshots:** `admin/aa-darts-add3-viewport@wide.png`.
- **Should:** keep the button in place while errors clear. Airports re-validates on blur in
  `DartForm.tsx`. The Name error that stays is C10.

**A18. The Active checkbox's label carries its hint.**
- *Minor, wording.*
- The label reads "Active — untick to make the DART inactive without losing its history".
- **Should:** split it into the label "Active" and the hint "Uncheck to make the DART
  inactive without losing its history."

#### Users and roles (`/portal/admin/users`), user administrator

**A19. Donor rows contradict themselves.**
- *Major, wording.*
- Donor rows show Kind *Donor* and Membership *Friend*.
- **Should:** show no membership for a donor.

**A20. The filters have several small problems.**
- *Minor, accessibility and consistency.*
- **Seen:**
  - Role descriptions are only in hover tooltips.
  - The role filter is not kept in the address.
  - The empty state blames the role filter even when Kind is the cause.
  - The grayed buttons explain themselves only on hover.
- **Should:** show the descriptions and the reasons in text, keep the role filter in the
  address, and name the filter that emptied the list. The red outline is C31.

**A21. Row heights are uneven at 390.**
- *Minor, responsive.*
- At 390 px, the hidden chip columns leave rows of uneven height.

#### User record (`/portal/admin/users/:id`), user administrator

**A22. There is no history of role or account changes.**
- *Major, obviousness. Screen and guide disagree.*
- **Seen:**
  - Nothing shows who granted or removed a role, or who deactivated or blocked the
    account, or when.
  - The guide says these changes are "recorded under your name".
- **Should:** add a History card like the aircraft record's.

**A23. A refused role change shows the raw slug.**
- *Major, wording.*
- **Seen:**
  - A user administrator can tick System administrator and save, then gets "Only a system
    administrator can grant or revoke the system_admin role."
  - Reset form leaves the error on screen (C10).
- **Should:** gray the box out, with a hint saying only a system administrator can change
  it.

**A24. The role descriptions use technical terms.**
- *Major, wording.*
- The same text is in the role-filter tooltips on Users and roles.

  | Shown | Write instead |
  | --- | --- |
  | "Wagtail admin: …" | "Edits the public website: pages, pictures, documents, and site settings." |
  | "…reminder runs and Django superuser access." | "…plus the server's health, backups, and scheduled jobs." |
  | "trigger password resets" | "send password reset emails" |
  | "reconcile periods" | (drop it) |

**A25. Two identical red buttons, with nothing to tell them apart.**
- *Minor, obviousness.*
- Deactivate and Block reactivation look the same, and no line explains how they differ.
- **Should:** add one line under each. Escape is C7.

**A26. A text back link, a crowded button, and a tacked-on word.**
- *Minor, consistency.*
- **Seen:**
  - Back to users is a text link, where the member record uses a button (C51).
  - Resend verification touches the ROLES rule below it.
  - "Unverified" is tacked onto the end of the email hint.
- **Should:** add space under Resend verification, and show "Unverified" as the email's
  status rather than in its hint.

### Finance

#### One payment (`/admin/payments/:id`), treasurer and account administrator

**F1. The three buttons under the payment are styled three ways.**
- *Major, consistency.*
- **Seen:**
  - Refund, which starts the most destructive action on the screen, is the filled main
    button, and comes first.
  - Resend receipt has a blue outline, and Download receipt a gray one.
- **Screenshots:** `finance/treasurer-detail@1920.png`.
- **Should:** give the three buttons one style, and make Refund a quiet or red-outline
  button placed last.

**F2. A pre-ticked box ends the membership without saying so.**
- *Major, obviousness.*
- **Seen:**
  - "Cancel the membership term this payment bought" is checked by default.
  - Nothing says this ends John Freeman's membership today.
  - The checkbox touches its label.
- **Should say:** "Also end John Freeman's membership (09/26/2026 to 09/25/2027) today",
  and leave it unchecked for a partial refund.

**F3. Several entries on the payment card are odd or repeated.**
- *Minor, wording.*
- **Seen, and the fix for each:**
  - "Method: PayPal · PayPal" repeats itself.
  - "Automatic renewal: Paid by a person" → "No, paid by the member".
  - "09/26/2026 to 09/25/2027 · active" → capitalize "Active".
  - "Term: None" next to "Reference: —" → use the dash for both.
  - The empty Refunds card says a refund "appears in this table", but no table is shown →
    "Refunds made here or in the provider's dashboard are listed here."
  - The Note hint "A check number, or why this entry exists" → "Anything worth keeping
    with this payment".
  - That Note, typed on Record a payment, sits in a card labeled TREASURER, which the
    account administrator also sees.

**F4. The "Matched on" field is too wide, and its line touches Save.**
- *Minor, layout.*
- **Seen:**
  - The "Matched on" date field is 1,166 px wide.
  - "Matched by Lucia Ferreira." touches the Save button.
- **Should:** give date fields a date-sized width, and put a gap before the button. The
  Refunds card width is C28.

**F5. Two member links sit side by side, with nothing to tell them apart.**
- *Minor, obviousness.* Account administrator.
- "John Freeman john.freeman03@… Member record" is two links in a row
  (`finance/accountadmin-detail@1920.png`).
- **Should:** label the first link "Money history".

#### Record a payment (`/admin/payments/record`), treasurer and account administrator

**F6. The form never shows what will be recorded.**
- *Major, obviousness.*
- Choosing Annual shows no dues amount and no total, so the treasurer cannot check the
  figure against the check before pressing "Record the payment"
  (`finance/i-record-filled@1920.png`).
- **Should:** show "Dues $45.00 + contribution $0.00 = $45.00" above the button.

**F7. The member search behaves unlike every other search box.**
- *Major, accessibility.*
- **Seen:**
  - It is built by hand (`MemberPicker` in `RecordPaymentPage.tsx`), not with the shared
    `Typeahead`.
  - The arrow keys do nothing.
  - Enter submits the whole form, which shows "Choose the member this payment is for."
    while the matches are on screen.
- **Screenshots:** `finance/i-record-typeahead@1920.png`.
- **Should:** use the shared `Typeahead`, and move focus to Plan after a pick.

**F8. The wording and sizing need tidying.**
- *Minor, wording.*
- **Seen, and the fix for each:**
  - The subtitle "A check, cash or a bank transfer: the term is activated and the receipt
    emailed." → "Record a check, cash, or a bank transfer. The membership starts and the
    member is emailed a receipt."
  - The "Dollars" hint → a "$" shown in front of the field.
  - "The check number, or the transfer's own" → "Check number or bank transfer
    reference."
  - At 1920 every field stretches to 1,166 px.
  - There is no Cancel button (C51).

#### Renewals (`/admin/payments/renewals`), treasurer and account administrator

**F9. The decline reason is written to the member, not the treasurer.**
- *Major, wording.*
- **Seen:**
  - "Your card was declined" appears under Paused and in the Reason column.
  - The guide says this is deliberately the member's own email wording, but the person
    reading this screen is the treasurer.
- **Should say:** "Card declined", or "Card declined (member was told: …)". Fix the guide to
  match.

**F10. Renewals lacks the links and order of the other finance tabs.**
- *Minor, consistency.*
- **Seen:**
  - Member names do not link to their money history.
  - "Auto-renewal status" also covers recurring donations.
  - Recent charges lists April 2027 rows above October 2026 ones, and those 2027 rows
    already show as refused.
- **Should:** link the names, call the column "Status", and sort Recent charges by Tried,
  newest first. Columns, export, and Reset are C16.

#### Reconciliation (`/admin/payments/reconciliation`), treasurer and account administrator

**F11. A period that isn't fully matched leads nowhere.**
- *Major, obviousness.*
- **Seen:**
  - A row reads "0 of 4" matched, but nothing links to those four payments.
  - The treasurer has to open the Payments tab, re-type the dates, and choose Reconciled:
    Not matched.
- **Screenshots:** `finance/treasurer-reconciliation@1920.png`.
- **Should:** make the Matched figure a link to the payment list, filtered to that period
  and to Not matched.

**F12. The rows run the other way from the overview, and there is no totals row.**
- *Minor, consistency.*
- **Seen:**
  - Rows run oldest first, while the overview runs newest first.
  - There is no totals row, which the treasurer needs to check against a bank statement.
- **Should:** sort newest first, and add a totals row. "Takings" is C33.

#### Contributions (`/admin/payments/contributions`), treasurer and account administrator

**F13. Emails and names behave differently from the payment list.**
- *Minor, consistency.*
- **Seen:**
  - Email addresses are plain text here, but links on the payment list.
  - Member names do not link to their money history.
- **Should:** make both links.

#### Subscriptions (`/admin/reports`), treasurer and account administrator

**F14. Two reports cannot be scheduled sensibly.**
- *Major, obviousness. The guide must change too.*
- **Seen:**
  - The reconciliation report offers only fixed From and To dates, with no Period, so a
    monthly reconciliation email cannot cover "last month".
  - The contributions report shows both "Year: This year" and "Period: The year chosen",
    two controls for one choice.
  - The guide says contributions offers This month, Last month, This year, and Last year.
    The screen offers The year chosen, This year, and Last year.
- **Screenshots:** `finance/i-subs-new-reconciliation@1920.png`,
  `finance/i-subs-new-contributions@1920.png`.
- **Should:** give reconciliation a Period choice, merge the contributions Year and Period
  controls, and make the guide match.

**F15. The report names don't match the tabs, and Save is disabled without a reason.**
- *Minor, voice.*
- **Seen:**
  - The reports are named "CalDART payments / CalDART reconciliation / CalDART
    contributions / Donors".
  - Save stays disabled until a report is chosen, with no hint why.
- **Should:** use the tab names (Payments, Reconciliation, Contributions, Donors), and add a
  hint by Save.

**F16. The roster button comes before the box that changes what it does.**
- *Minor, obviousness.* Account administrator.
- **Seen:**
  - "Send rosters now" sits left of "Dry run (send nothing)", so the button is read before
    the option that changes it.
  - The dry-run results table has When and Amount columns that are always empty for
    rosters.
- **Screenshots:** `finance/i-rosters-dryrun@1920.png`.
- **Should:** put the box first, label the button "Preview rosters" while it is checked,
  and hide columns that are empty in every row (`RunActionsTable`).

#### Reminders (`/admin/reminders`), account administrator

**F17. The reminder schedule is written three ways on one screen.**
- *Major, wording.*
- **Seen:**
  - The intro and the empty-table message both spell out "60, 30, and 7 days before…, on
    the day it ends, and 30 days after". That text is fixed, so it becomes wrong once a
    system administrator changes the schedule.
  - The "Reminder schedule" card lists four stages and leaves out the "on the day" one.
- **Screenshots:** `finance/accountadmin-reminders@1920.png`.
- **Should:** build the sentence from the saved schedule, and show all five stages in the
  card. Stage naming is C48.

**F18. The wording is mechanical, and the layout uneven.**
- *Minor, voice.*
- **Seen, and the fix for each:**
  - "The scan runs every morning at 07:00 and mails a member…" → "Every morning at 7:00
    AM, CalDART emails members whose membership is ending."
  - "The default schedule: nobody has changed it." gives no next step. Add "A system
    administrator can change it."
  - The Reminder filter label touches the paragraph above it.
  - Both cards carry the small label MEMBERSHIP. The card widths are C28.

#### Notifications (`/admin/notifications`), account administrator

**F19. The wording is vague, and the events list is hidden in a tooltip.**
- *Minor, wording.*
- **Seen:**
  - The subtitle "Email addresses that receive notification of system changes" has no
    period and uses jargon.
  - The full events list is only in a tooltip that appears on mouse hover, which keyboard
    and phone users cannot reach.
- **Should:**
  - Write "Who is emailed when something happens, such as a sign-up, a payment, or a
    refund."
  - Show the events in the row.
- The raw error, the event names, and the guide's five groups are C34, C48, and C61.

### Operations and system

#### Member check (`/portal/leader`), leader, verifier, and system administrator

**O1. The verdict band and list rows stop partway across the card.**
- *Major, appearance.*
- **Seen:**
  - At 820 and 1920, these all end about 545 px across a card 788 or 1,600 px wide:
    - the red or green GO band;
    - the Aircraft heading rule;
    - the aircraft and "Members who fly it" rows;
    - the search results.
  - The band is a `<p>`, the rows are `<li>`, and `base.css` sets
    `p, li { max-width: var(--measure) }`.
- **Screenshots:** `ops/leader-mc-card@820.png`, `ops/leader-mc-card@1920.png`,
  `ops/leader-ac-card@1920.png`.
- **Should:** set `max-width: none` on `.leader-verdict`, `.leader-search__result`, and the
  aircraft rows.

**O2. People with the same name look identical in the results.**
- *Major, obviousness.*
- **Seen:**
  - Each result shows only a name and GO or NO-GO, so two "John Smith"s cannot be told
    apart.
  - Picking the wrong one before a flight is a costly mistake.
  - The search API already returns each person's DART and email.
- **Screenshots:** `ops/verifier-dupnames@1920.png`.
- **Should:** show the DART and email on each line (`LeaderSearchPage.tsx` `renderRow`).

**O3. "Make a verifier" grants a role in one click.**
- *Major, consistency.* Leader and system administrator.
- **Seen:**
  - It sits beside Verify, in the same style, and grants the role at once, with only a
    toast afterwards.
  - On Users and roles, a role change needs Save changes.
- **Should:** ask first with the shared `ConfirmButton`, or move the button away from Verify.

**O4. The DART isn't labeled, and the leader role isn't shown.**
- *Minor, wording.*
- **Seen:**
  - The line under the name reads "Monterey · phone · email", without saying Monterey is a
    DART.
  - It shows "Verifier" but never "DART leader".
- **Screenshots:** `ops/leader-nodart-card@1920.png`.
- **Should:** write "Monterey DART", and show every operational role.

**O5. "That member could not be loaded" uses jargon and has two identical buttons.**
- *Minor, wording.*
- **Seen:**
  - It reads "No member with that id. They may have been removed."
  - It offers both "Back to search" and "Search again".
- **Screenshots:** `ops/leader-mc-missing@390.png`.
- **Should:** write "We could not find that person. Their account may have been deleted.",
  and keep one button.

**O6. The Verify panel is cramped.**
- *Minor, layout.*
- **Seen:**
  - The "Verification" heading touches the first label.
  - Save touches the last checkbox.
  - The panel is 1,215 px wide under a 545 px band.
- **Screenshots:** `ops/leader-mc-verify@1920.png`.
- **Should:** add space around the heading and Save, and give the panel the band's width
  once O1 is fixed.

#### Verification report (Export CSV and Export PDF on Member check)

**O7. It lists people who have nothing to verify.**
- *Minor, obviousness.*
- Non-pilots ("None") appear under Pilot certificates, and people with no medical under
  Medicals (`ops/verif-report-1.png`).
- **Should:** leave them out (`apps/aircraft/verification_report.py`).

**O8. It has redundant columns and raw wording.**
- *Minor, appearance.*
- **Seen:**
  - The Section column repeats each heading on every row.
  - Verified, Verified by, and Verified on are always "No" or empty in a report of
    unverified items.
  - The filter line reads "status: unverified".
  - The Medicals heading sits alone at the foot of page 1.
- **Should:** drop those columns by default, write "Not yet verified", and keep each heading
  with its rows.

**O9. Nothing explains what the report is.**
- *Minor, obviousness.*
- It is a gray "Verification report" label beside two buttons above the search.
- **Should say:** "Everything nobody has checked yet:".

#### Aircraft check (`/portal/leader/aircraft`)

**O10. The search label undersells the box.**
- *Minor, wording.*
- **Seen:**
  - The label says "Search by N-number", but "Cessna" works too.
  - The placeholder is "N12345", and the box uses a monospace font.
- **Should:** label it "N-number, make, model, or owner".

**O11. "Not in the register" sends leaders to a screen they cannot open.**
- *Minor, wording.*
- It says "…or add it from the aircraft register", which leaders and verifiers cannot open
  (`ops/leader-ac-missing@390.png`).
- **Should say:** "Ask the pilot to add it on My aircraft, or ask an account administrator."

**O12. Contact details behave differently from the member card.**
- *Minor, consistency.*
- The owner's phone and email are plain text, and member names open nothing. On the member
  card they are links.
- **Should:** make them links.

#### A DART leader with no DART

**O13. An account created with a password must still join and pay.**
- *Major, obviousness. The guide must change too.*
- **Seen:**
  - The guide says such a person "can sign in now".
  - Instead, their first sign-in goes through verify email, profile, and "Pay your dues",
    with $45 chosen.
  - The only way past without paying turned the leader into a friend.
  - This crosses into New member (administration).
- **Screenshots:** `ops/nodart-landing@1920.png`, `ops/nodart-after@1920.png`,
  `ops/nodart-pay@1920.png`.
- **Should:** skip the payment step for accounts an administrator creates, or say so on New
  member.

**O14. The "no DART" message is inconsistent.**
- *Minor, consistency.*
- **Seen:**
  - The Dashboard says nothing about the missing DART.
  - Compose shows the notice as plain text, and Drafts as a boxed notice.
  - Callouts tells the leader to "open Compose", which is a dead end without a DART.
- **Should:** show the same notice, with a link to My profile, on the Dashboard and every
  Bulk Email screen.

#### Health and database (`/portal/system/health`), system administrator

**O15. Server jargon, and restoring is a single line of it.**
- *Major, wording.*
- **Seen:**
  - The screen says "database dumps", and "Dumps are written to BACKUP_DIR on the server.
    Restoring one is a command-line job: manage.py db_restore."
  - It also says "No dump has been taken on this machine." and "DEBUG must be off in
    production."
  - Values show raw as "ok", "never", and "on", and a toast reads "Wrote
    caldart-…sql.gz".
  - There is no restore screen at all, only that sentence.
- **Screenshots:** `ops/sys-health@1920.png`, `ops/sys-backup-done@1920.png`.
- **Should:** use the guide's words: "There is no restore button. To restore a backup, ask
  the person who installed the site." Write "No backup yet" and "Backup taken."

#### Sent emails (`/portal/system/emails`), system administrator

**O16. An email cannot be opened.**
- *Major, obviousness.*
- **Seen:**
  - There is no detail view.
  - The subject is not on screen; it appears only in the export.
  - The page exists to answer "what did we send this person?".
- **Screenshots:** `ops/sys-emails@1920.png`.
- **Should:** add at least a Subject column, and ideally a detail view with the subject,
  error, and message.

#### Scheduled (`/portal/system/scheduled`), system administrator

**O17. Run now moves after it is pressed.**
- *Major, accessibility.*
- Results appear above the button, so after a dry run of Scheduled reports, Run now sits
  below a 35-row table.
- **Should:** put results below the controls, and move focus to the results heading. Focus
  is also C6.

**O18. The real-charge confirmation focuses the charge button.**
- *Major, consistency.*
- **Seen:**
  - Clear Dry run on Automatic renewal charges and press Run now: focus lands on the red
    "Yes, charge what is due".
  - Escape does nothing, and Cancel drops focus to the page body.
  - Pressing Enter twice charges every member who is due.
- **Screenshots:** `ops/sys-sched-charge-confirm@1920.png`.
- **Should:** reuse `ConfirmButton`'s behavior, as Email types' delete does: focus Cancel,
  and close on Escape.

**O19. The reminder log contradicts the dry run above it.**
- *Major, wording.*
- The dry run says "Would send 2 emails", and the log underneath says "No member has
  reached a reminder yet."
- **Should say:** "No reminders have been sent yet.", with the log under its own heading
  below Run now.

**O20. Bounces' Run now does nothing when bounce checking is off.**
- *Major, obviousness.*
- **Seen:**
  - The button stays enabled, and pressing it produces no result.
  - The only sign of the problem is a line, "Bounce checking is off…", that appears after
    the press.
- **Should:** show that line when the page loads, and disable the button. Write "Ask the
  person who installed the site to set up a bounce mailbox."

**O21. The Dry run box comes after the button it controls.**
- *Minor, obviousness.*
- On Year-end statements, the Year field also sits between them.
- **Should:** put the box and Year first, then Run now.

**O22. Each panel is laid out differently.**
- *Minor, layout.*
- **Seen:**
  - The "Reminder" filter label touches the results table.
  - "What this run would do" is larger than the card's own title.
  - The bulk email sender's button touches its description.
  - Only that button is labeled "Run the bulk email sender now".
- **Should:** lay out every panel the same way.

**O23. The results say the same thing twice, and the jobs are unnamed.**
- *Minor, voice.*
- **Seen:**
  - "Worked on 0 bulk emails: sent 0, failed 0, and skipped 0." sits on top of "Nothing
    was due".
  - "The sender runs every morning" does not say which sender.
  - "next morning's scan" is jargon.
- **Should:** show only "Nothing was due.", and name each job. The repeated "Running it again
  is harmless" is C36.

---

## Accepted as is

- **Help opened a debug 404 on the administration pass's server** (admin, environment
  note). The guide had not been built there. The finance and operations passes rebuilt it,
  and every Help link landed on the right page.
- **Donors cannot sign in** (member, environment note). A donor has no portal account by
  design, so there is no donor view to review.
- **New member is its own page while New aircraft and Add a DART open inline** (admin #28,
  in part). A 2,700 px form warrants a page of its own, while a short form can open in
  place. The rest of admin #28 (Escape, focus, and the button that turns into Close)
  stands in C7 and C51.
- **The theme is set for the whole site, not per person** (member, environment note).
  Themes are a site setting in Wagtail, and the reviewer did not report this as a defect.

---

## The axe results

`make screenshots` runs axe once per role and route, at 1920 in the default theme: 206
role-route pages, of which 170 are clean.

| Rule | Impact | Role-route pages | Nodes | Screens |
| --- | --- | ---: | ---: | --- |
| `color-contrast` | serious | 36 | 148 | Become a member (`/membership/join`) and Renew, 9 roles each, 2 nodes; Users and roles, 2 roles, 17 nodes; Payments (finance), 3 roles, 12 nodes; DARTs, 2 roles, 8 nodes; Renewals, 3 roles, 6 nodes; one payment and a member's money history, 3 roles each, 1 node; the aircraft record, 2 roles, 1 node |
| `empty-table-header` | minor | 5 | 5 | Subscriptions (`/admin/reports`), 3 roles; Notifications, 2 roles |

**How these relate to the findings above.**

- **`color-contrast`** is mostly two things:
  - the muted text on the option cards, on Become a member and Renew (M5);
  - the translucent status chips on striped rows, on Users and roles, DARTs, the finance
    screens, and the aircraft record (C55).
- **`empty-table-header`** is the unlabeled Actions column (C4).
- **What axe at 1920 cannot see.** It does not run at phone width, so the
  `scrollable-region-focusable` failures behind C2 do not appear here; the reviewers'
  own axe runs at 390 found them. It does not run in the dark themes, so the danger-button
  contrast in C13 does not appear either.
