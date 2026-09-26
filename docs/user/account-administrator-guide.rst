===========================
Account administrator guide
===========================

Account administrators look after the people in |org|: who is a member, when
their membership runs out, what is on their record, and what the organization
can prove about all of it in a spreadsheet or a PDF.

You need the ``account_admin`` role to use any of the screens on this page.
System administrators have it implicitly.  The role also opens **Payments**
and **Aircraft** under *Administration* in the portal menu, and **Member
check** and **Aircraft check** under *Operations* — the pre-flight currency
checks described in :doc:`dart-leader-guide`.  This page covers **Members**,
at ``/portal/admin/members``, **DARTs**, at ``/portal/admin/darts``,
**Reminders**, at ``/portal/admin/reminders``, and **Reports**, at
``/portal/admin/reports``.


The member list
===============

The list shows every member and every friend of CalDART, one row each.  A donor
who has only given through the public site is never on it: donors are the
treasurer's (see :doc:`treasurer-guide`).  Deactivated accounts are left out
until you tick **Include deactivated**.  DART leaders open the same list, filter it the same
way, and download the same report (see :doc:`dart-leader-guide`); the
**New member** button and the member record behind each name are yours alone.

**Pilot**
   A green tick when the member holds a pilot certificate and their medical is
   in date, a red cross when the medical has lapsed, and a dash for somebody
   who is not a pilot.  It answers the question the list is most often opened
   for: who can fly today.

**Name**
   Their name, which links to the full record.  A deactivated account says so
   here.

**DART**
   Their team, or "Unaffiliated".

**Membership Exp.**
   A colored dot and the expiry date.  The dot is green while the membership is
   current, amber in the last 30 days, red once it has run out, blue for
   somebody who has joined but not paid, and gray for somebody who has never
   been a member and for a friend of CalDART, who pays no dues and never
   expires.  A lifetime membership reads "Never", and a friend's reads
   "Friend".

**Email**
   A ``mailto:`` link, so you can write to someone straight from the list.

A member's name opens their record wherever it is listed, and an N-number
opens the aircraft record: on the payment list, on an aircraft record's list of
the members who fly it, and among the aircraft on a member's profile.

The expiry date is the end of the member's *unbroken* coverage.  Somebody who
renews in March for a term that starts in July already shows next July's date,
because their cover runs without a break — you never have to add the terms up
yourself.

Click any column heading to sort by it; click again to reverse the order.
**Pilot** sorts the way its marks read: a current medical first, then a lapsed
one, then everybody who is not a pilot.  Members who tie on the column you
sorted by fall into name order, so a sorted list reads the same every time you
open it.  The sort, like the filters, is part of the page's address, so a sorted
and filtered list is a link you can bookmark or send to somebody else.

The five columns keep the table readable on a phone; the downloads carry as many
as you like, under *Reports* below.


Filtering
---------

The filter bar sits above the table.  The dropdowns, the county list, and the
checkbox apply the moment you change them, and the table narrows as you type in **Search** or
**Expiring within (days)** — it follows a short pause, so it does not chase
every keystroke.  **Expiring within (days)** takes digits only.  There is no
Apply button.  **Reset to Defaults** empties the whole bar and leaves the sort
alone.

**Kind**
   *All*, the default, lists members and friends together; *Members only* and
   *Friends only* list one kind.  A member who has asked to become a friend at
   the end of their term is a member until that day comes.

**Search**
   Matches a name, an email address, either phone number or a pilot
   certificate number, and narrows the list as you type.  Full names work:
   ``Ana Bracco`` finds her.

**Membership**
   *Current* (a term covers today), *Unpaid* (an account whose only term was
   never paid for), *Expired* (a paid term has run out), *No membership*
   (nobody has ever granted or sold them a term), or *Friend* (a friend of
   CalDART, whatever terms they once held).  The five between them account for
   every account exactly once, and the member report's own **Status** column
   prints the same five words.

**Certificate** and **Medical**
   The pilot certificate and medical class on the member's profile.
   **Certificate** also offers *Any licensed*, which is every certificate a
   pilot may act on alone — sport through ATP, and neither a student nor "not a
   pilot".  **Medical** also offers *Has any medical*, which is everyone with a
   medical of any class on file.  Each list's blank entry reads *Any*, and an
   *Any* filter takes in the people who answered "none" as well.

**DART**
   The team the member belongs to.

**County**
   The California counties on the members' profiles.  The list box shows six
   counties at a time; hold Ctrl (Command on a Mac) and click to choose more
   than one, and the list shows the members of any county you chose.  Click a
   chosen county with Ctrl held to take it back.  With no county chosen the
   filter narrows nothing, and a member who has not given a county is listed
   only then.

**Role**
   People who hold a particular role.  This is the role actually assigned to
   the account: a system administrator is *not* listed under every other role
   even though they can do everything.

**Expiring within**
   A number of days.  It uses the computed expiry, so a member who has already
   renewed drops out of the window immediately, and lifetime members never
   appear in it.

**Include deactivated**
   Off at first, so the list leaves out the accounts that have been
   deactivated.  Tick it to list them too, each with "account deactivated"
   beside the name.  The downloads never carry a deactivated account, ticked or
   not.

Filters combine.  "Current members of the Napa DART whose membership expires
within 30 days" is three dropdowns and a number.


Adding a member
===============

**New member** opens a form in two halves.  Only the email address is
required; everything else can be filled in later, by you or by the member.

* **Account** — email address, first and last name, the **Kind of account**
  (*Member*, the default, or *Friend*: see :ref:`kinds-of-account`), and an
  optional password.
* **Profile** — contact details, aviation details (DART, certificate, medical,
  ratings, hours), volunteer interests, and the administrator-only fields.

Leave the password box empty unless you have a particular reason not to.  The
account is then created with no usable password and the new member is emailed
a link to choose one for themselves.  Using that link also verifies their email
address, since only the owner of the address could have received it.  If you do
type a password, you have to tell them what it is, and the new member is emailed
a verification message instead: their address stays **unverified** until they
open the link in it.

Either way the account is granted the ``member`` role and an empty profile is
created.  Creating a member does **not** give them a membership: grant a term,
or let them pay online.  A friend needs neither: a friend pays no dues.


The member record
=================

Clicking a name opens that person's record.  A summary strip at the top
carries their membership chip, plan, expiry, join date, and the date their
profile information was last written — "updated 2026/08/11", or "never edited"
for a profile that predates the stamp, such as one loaded by the demo data.  A
profile created in the portal, or by an administrator, carries the date it was
created.  A payment, a renewal, or a membership grant is not an edit to the
profile, so the date answers "how current are these details?" rather than "when
did anything happen to this member?"

Below the strip are four tabs.  Arrow keys move between the tabs, and the tab
you are on is part of the address, so you can send a colleague straight to
somebody's payment history.

Profile
-------

The same fields as the new-member form, plus:

* **Kind of account** — *Member* or *Friend*.  Saving a change of kind makes it
  at once: a member made a friend reads **Friend** from that moment, whatever
  their terms say, and any change to friend the member had pending for the end
  of a term is dropped.  A donor's record has no such field and carries a
  **Donor** chip in its summary strip instead: a donor becomes a member or a
  friend only by registering, and the server refuses the change otherwise.
* **Account is active** — clearing it stops the member signing in without
  deleting anything.
* **How they heard about CalDART** and **Administrator notes** — visible only
  to account administrators.  Members never see them, on any screen.

Under the email field, the record shows **Verified** with the date it was
confirmed, or **Unverified**, with no button to resend from here: a user
administrator can send a fresh message from the Users & roles screen, or the
member can send themselves one from their own dashboard.

**Save changes** writes the account and the profile in one request.

Two of those fields are guarded, because between them they are enough to take an
account over: the email address is where a password reset link is sent, and the
Active box locks somebody out.  You may change them only on an account whose
roles you hold yourself — every ordinary member, and anybody else whose roles
you already have.  Any role you lack is enough to put a record out of reach, not
just the administrative ones: as an account administrator you can edit an
ordinary member's address and Active box, and another account administrator's,
but not a DART leader's, a treasurer's, a website administrator's, a user
administrator's or a system administrator's.  On one of those the save is refused and nothing on the
record changes, profile fields included.  You cannot clear **Account is active**
on your own record either.  Names, DART, phone numbers and every profile field
stay editable on any record you can open.

A refused email address says so under the field.  A refused Active box does not:
this screen has no message under the checkbox, so **Save changes** simply leaves
the record as it was.  If a save appears to do nothing, check whether you moved
the Active box on a record you may not deactivate, put it back, and save again.

Memberships
-----------

The history table lists every term: plan, start, end, status, where it came
from (a payment, a manual grant or the demo seed), the note, and who granted
it.

**Edit** on a row lets you correct that term's end date, status, or note — for
a refund, a goodwill extension, or a term that was entered wrongly.  Setting a
term to *Canceled* takes it out of the membership calculation entirely; the
row stays in the history.

**Grant a term** below the table gives somebody a membership by hand.  Choose
a plan and, optionally, a start date and a note explaining why.

Leave the start date blank and the term starts itself correctly:

* a **current** member's new term starts the day after their present one ends,
  so granting a year to somebody with four months left gives them sixteen
  months, not twelve;
* a **lapsed** member's, or a new member's, starts today;
* a **lifetime** plan has no end date at all.

Granting a term to a friend makes them a member, exactly as paying for one
does.

Fill the start date in only when you are recording something that happened on
a particular day — a check that arrived last month, say.

Payments
--------

This member's whole money history, the same one the finance area shows: what
they have paid, given and been charged in fees over every year; their automatic
renewal, if they hold one, with the saved method and the next charge date;
every payment with what was refunded out of it, each linking to its own record;
and a button for every year they can be sent a contribution statement for.

Terms you grant by hand have no payment attached, so they do not appear here.
For the organization-wide ledger, the period totals, the reconciliation table
and the year-end contributions list, use **Payments** in the menu.  That area
is also open to a treasurer, who reaches the money without reaching this
record.

Danger zone
-----------

**A member who has ever paid cannot be deleted.**  Payments are the
organization's financial record: a membership fee or a donation stays in the
ledger, the period totals and the exports whatever happens to the person who
made it.  The tab says so instead of offering the form, and names
how many payment records the account carries.  Deactivate the account instead,
as below.

For an account with no payments — a duplicate, a spam sign-up, a test record —
the delete is permanent and takes the profile and every membership term with
it.  There is no undo and no archive.

The delete button — a trashcan and the words **Delete member**, as every
delete in the portal is — stays disabled until you type the member's email
address into the confirmation box.  Two further deletions are refused outright:

* your own account; and
* a system administrator's account, unless you are a system administrator
  yourself.  An account carrying Django superuser access counts as a system
  administrator's here even if the role itself was never granted.

If somebody has simply left, clearing **Account is active** on the Profile tab
is the answer: it stops them signing in and keeps the record for the accounts.
That box is guarded like the email address, so on a record carrying a role you
do not hold — a DART leader's, say — the save is refused; ask a system
administrator, or a colleague who holds every role that account holds.


Reports
=======

**Export CSV** and **Export PDF** sit at the top right of the member list and
export *exactly what the list is showing* — the same filters, the same order,
every matching member and not just the page in front of you.  The one exception
is **Include deactivated**: a report never lists a deactivated account.

* **CSV** opens in a spreadsheet.  Use it for mail merges, board packs and
  anything you want to sort or total yourself.
* **PDF** is a landscape letter table, ready to print, with the filters you
  applied printed under the title and the date and page numbers at the foot.
  Several counties print as a list: "county: Alameda, Marin".
  It is the one to attach to minutes, because it says on its face what it is a
  list of.

Both carry the same eleven columns unless you ask for others: name, email,
phone, DART, status, kind, expiry, certificate, medical class and expiry, and
aircraft.  **Kind** reads *Member* or *Friend*.  A lifetime member has no expiry
date, so that cell is empty and the plan column says *Life*; a friend's is empty
too, and their status reads *Friend*.

.. _member-report-columns:

Choosing the columns
--------------------

**Columns**, beside the filters, opens a chooser that drives both downloads.
Twenty columns are on offer; the eleven above are on to begin with.  The nine
that are off — *Plan*, *Certificate number*, *IFR*, *City*, *State*, *County*,
*Joined* (the day the first term on file began), *Member since* (the day the
member says they joined), and *Profile updated* (the day profile information
was last written) — are the ones a roster or an audit wants and an everyday
report does not.  **Reset to the default columns**, under the boxes, ticks the
eleven again.

The chooser feeds the downloads, not the table: the list on screen keeps its
five columns however many you tick.  The last column cannot be unticked, since a
report of nothing helps nobody.  The eleven default columns are sized so no cell
has to wrap on a landscape page; add enough columns and the PDF will start
wrapping, which is the point at which the CSV is the better file.

Beside **Columns**, **Load columns** lists the sets of columns you have saved
for the member report.  Pick a name and its columns are applied; the list
closes.  The trashcan beside a name deletes that set.  **Save columns** keeps
the boxes as they stand: type a name of up to 60 characters and press **Save**,
or press Enter.  Saving under a name you already use replaces that set, and
loading a set puts its name in the box, so a set you load and change is saved
again under the same name.  Each of the three buttons opens its own panel under
itself, which a click outside it or Escape puts away.  Your saved sets are
yours alone, and each report keeps its own.

The columns are listed field by field in the developer documentation under
:doc:`/developer/reports`.


DARTs
=====

**DARTs**, under *Administration*, is the list of teams a member can join.
Everything on it shows up in the **DART** box on the join form, on a member's
profile, and in the DART filter on the member list, so adding a team here is
all it takes to start putting people on it.

The table gives each DART's name, its airports, its website, how many people
run it, how many of them receive the roster (**Roster**), how many members are
on it and whether it is *Active* or *Inactive*.
Click a
column heading to sort, and click a member count to open the member list
filtered to that team.

**Adding one**
   **Add a DART** opens a short form: the **Name** members will see, the
   **Airports** the team flies from as three-character identifiers separated by
   commas (``PAO``, or ``CCR, C83`` for a team with two fields — paste ``KCRQ``
   and the leading ``K`` comes off), and the team's own **Website** if it has
   one.  A DART is identified by the fields it flies from, so there is no town
   to fill in.

**The people who run it**
   **DART management** holds as many people as the team needs, each with a
   name and a job title.  A phone number and an email address are both
   optional.  **Add a person** adds a row; it is grayed out while the last row
   has no name, so give the person above a name first.  Tick **Roster** on the
   row of each person who receives the team's roster by email.  The **Roster**
   count in the table counts only the ticked people who have an email address,
   since a roster cannot reach anyone else.  The arrows at the head of each row
   put the people in order, and that order is the order the team's page on the
   public website lists them in, so the leader comes first.  A row with no name
   cannot be put in order: its arrows are grayed out, and so are the arrows of
   its neighbors that would move past it.  The trashcan at the end of a row
   takes that person off the list.  The people are saved with the rest of the
   form, so clearing a row really does take that person off the list.

**Changing one**
   **Edit** opens the same form on an existing DART.  Renaming one is safe:
   the members on it stay on it.

**Making one inactive**
   Untick **Active** and save.  The DART disappears from the join form and from
   a member's profile box, and everybody already on it stays on it, so the
   history and the reports still read correctly.  Tick it again to bring the
   team back.

**Deleting one**
   **Delete this DART**, at the foot of the edit form, deletes the team for
   good, and it asks before it acts.  The confirmation says what the delete
   leaves behind: the members on the DART come off it and stay members, with
   nothing else on their record touched, and a DART page on the public website
   keeps its own words and loses only its link to the team.  Deleting is
   permanent, so a team that has simply stopped flying is better made inactive.

   One thing a delete cannot reach is an unpublished draft of that website page:
   the draft still names the deleted team, and publishing it fails.  Ask the
   website administrator to open the page, clear its **DART** field, and publish
   again.

A DART's own page on the public website is a separate thing, kept by a website
administrator in the Wagtail editor (:doc:`website-administrator-guide`); the
**DART** field on that page is what ties the two together.


Reminders
=========

**Reminders**, under *Administration*, lists one row per renewal email CalDART
has sent, newest first, with the date and time it went out, which reminder it
was, the member it went to and the address it was sent to.  Each member gets
one email per membership per kind.  This is the record of what renewal emails
were sent to each member.

The **Reminder** box above the table narrows it to one kind: *60 days before*,
*30 days before*, *7 days before*, *Expired* or *30 days after*.  *All
kinds* puts them back.  Sort by clicking a column heading.

The scan that sends them runs every morning at 07:00 and needs nobody to start
it; :doc:`overview` explains which email a member gets when.  Running it by
hand is a system administrator's control and lives on their System page, so
there is no button for it here.

An empty table means no term has reached a reminder stage yet — on a fresh
installation, or when every member renewed early.


Reports by email
================

**Reports**, under *Administration*, is where CalDART is told to email a report
on a schedule, and where each DART's monthly roster is sent from.  A treasurer
opens the same screen for the money reports (:doc:`treasurer-guide`); the DART
rosters are yours alone.

Subscriptions
-------------

A subscription emails one report, filtered and with the columns chosen when it
was set up, to one address, on its schedule.  The table lists every
subscription for a report you may read: the **Report**, the **Recipient** (the
account's name, or the bare address for somebody outside CalDART), the
**Schedule** (*Weekly on Monday*, *Monthly*, *Quarterly* or *Yearly*), the
**Formats** attached (*CSV*, *PDF* or *Both*), when it was **Last sent**, when it
is due **Next**, and a dot in **Active**, green while it is being sent and gray
while it is paused.  Each row carries three controls:

**Send now**
   Sends it at once, whatever the date, and leaves its next date where it was.
   The line above the table says *Sent to* the recipient, or why it was not: the
   report could not be built or the mail server refused it, or the recipient no
   longer holds a role that may read the report, in which case the subscription
   is paused.

**Pause** and **Resume**
   A paused subscription is kept, with everything it was set up with, and sent
   nothing until it is resumed.  Resuming one whose account may no longer read
   the report is refused, and the line above the table says why.

**The trashcan**
   Deletes the subscription.

**New subscription** opens the form:

1. **Report** offers the reports you may read.  Choosing one draws the same
   filters its own list page has, plus **Period** on the payments and
   contributions reports: *This month*, *Last month*, *This year* or *Last
   year*, worked out on the day each email goes, so a monthly subscription for
   *Last month* always carries the month before the one it is sent in.
2. **Columns** chooses the columns, as on the list page; left alone, the report
   carries its default columns.  The reconciliation and contributions reports
   have fixed columns and offer no chooser.
3. **Formats** attaches a CSV, a PDF, or both.
4. **Schedule** is weekly, monthly, quarterly or yearly; a weekly one asks for
   the **Day** it goes.  A monthly subscription goes on the first of the month,
   a quarterly one on the first of January, April, July and October, and a
   yearly one on the first of January.
5. **Recipient email** is where it goes.

**Save** checks the recipient.  An address that belongs to a CalDART account
is refused, under the address, when that account holds no role that may read
the report: a treasurer cannot be sent the membership report, whose medical and
certificate details are not theirs to read.  An address no account holds is
refused until you tick **This address is outside CalDART and may receive this
report**, which appears under the address once CalDART asks for it.  A filter
the report cannot use is named, with the reason, under the filters.

The emails go out every morning at 06:00.  A subscription that could not be
sent is tried again the next morning; one whose recipient has lost the role is
paused instead.

DART rosters
------------

Early each month every active DART's roster, the member report of that DART
by name with each person's phone, email, certificate, medical, aircraft,
expiry, and kind, goes as a PDF to each of the DART's people ticked **Roster** under
**DARTs** who has an email address.  The table lists each active DART, its
**Recipients** (the ticked people with an address), and when its roster was
**Last sent**.  A roster lists the DART's members and friends alike, its
**Kind** column saying which each one is, and never a deactivated account or
a donor.  A DART with nobody
ticked is sent nothing.

**Send rosters now** sends every DART's roster at once, whatever the date.
Leave **Dry run (send nothing)** ticked the first time: the line under the table
says how many emails a live run *would* send and how many DARTs or people it
would skip, and a table names each person, their address and their DART.
Clear the box and press the button again to send them for real; the table then
says what the run did.


Common tasks
============

**Who is about to lapse?**
   Membership *Current*, Expiring within ``30``.  Export the CSV for the
   renewal mail-out.  Automatic reminders go out at five stages: two months
   before expiry, a month before, in the last week, once the term has run out,
   and once a month later.

**Who has lapsed and not come back?**
   Membership *Expired*, sort by Membership to see the longest-lapsed first.

**How big is a DART?**
   DART, then Membership *Current*.  The caption under the filter bar gives
   the count.

**A new team wants to join CalDART.**
   **DARTs**, **Add a DART**, name and airport.  It appears on the join form
   immediately, so the new team's pilots can pick it the same day.

**A team has folded.**
   Open it in **DARTs**, untick **Active**, and save.  Nobody new can pick it,
   and everyone on it keeps their record.

**Somebody paid by check.**
   Open their record, Memberships, Grant a term, choose the plan, and note the
   check number.  Leave the start date blank unless the check should be
   backdated.

**A member says they renewed but the site says expired.**
   Open their record and read the Memberships tab.  The status is worked out
   from the terms listed there, so a missing or canceled term is the answer;
   the Payments tab shows whether the money arrived.


When something goes wrong
=========================

**"An account with that email address already exists."**
   Somebody already has an account on that address — very often the person in
   front of you, from a previous membership.  Search the list for it and edit
   that record instead of creating a second one.  Capitalization is ignored,
   so ``Marta@`` and ``marta@`` collide.

**The new member never got their "set your password" email.**
   It is only sent when you leave the password box **empty**.  If you typed a
   password, no email went out and you have to tell them what it is.  If you
   did leave it empty, ask a user administrator to send a password reset from
   ``/portal/admin/users``, which does the same job.

**"You cannot change the email address of an account that holds roles you do not hold."**
   The record carries a role you do not have — ``dart_leader``,
   ``treasurer``, ``website_admin``, ``user_admin``, or ``system_admin``.  Moving an address is
   enough to take an account over, so it is reserved for somebody who already
   holds every role that account holds.  Ask a system administrator, or a
   colleague who holds them all.

**Save changes did nothing, and said nothing.**
   The Active box is guarded the same way the email address is — on a record
   carrying any role you lack, and on your own, where nobody may clear it — but
   the Profile tab has no message under the checkbox, so a refusal there is
   silent and the whole save is discarded.  Put the box back the way you found
   it and save again; ask a system administrator, or a colleague who holds every
   role that account holds, if it really has to be deactivated.

**"You cannot delete your own account."**
   Exactly what it says.  Ask another administrator.

**"Only a system administrator can delete a system administrator."**
   Deleting an administrator is deliberately harder than deleting a member.
   Ask a system administrator, or deactivate the account instead — which keeps
   the history and locks them out just as effectively.

**"… has N payment records, which must be kept. Deactivate the account instead."**
   The Danger zone hides the delete form for a member who has paid, so this
   answer only comes back when a payment landed while you had the page open.
   Reload the record and deactivate instead.

**You cannot change somebody's roles from the member record.**
   Roles live on the user-administration screen, behind the ``user_admin``
   role, not on the member record.  See :doc:`user-administrator`.

**A term you granted starts later than you expected.**
   That is correct.  A term granted to somebody whose membership is still
   current starts the day *after* their present one ends, so they get the
   whole year they paid for.  To override it, set the start date explicitly
   when you grant the term.

**"The end date cannot be before the start date."**
   You are editing a term's expiry to a date before it began.  Correct the end
   date, or cancel the term and grant a fresh one.

**A membership term is wrong and you cannot edit its plan or start date.**
   Only the end date, the status and the note are editable.  Rewriting a
   term's plan or start date would falsify history rather than correct it —
   cancel the wrong term and grant the right one, with a note saying why.

**An export downloads far more rows than the screen shows.**
   It should not: the export carries the filters the screen has.  A box you
   have just typed in applies after a short pause, so wait for the table to
   narrow before you download.

**The Danger zone will not let me delete a member.**
   Read what it says.  An account with any payment against it cannot be
   deleted at all, because the payment records are kept: clear **Account is
   active** on the Profile tab instead, which stops the sign-in and leaves
   everything else in place.  An account with no payments is still refused if
   it is your own, or a system administrator's and you are not one.

**I deleted the wrong member.**
   Deleting an account with no payments is a hard delete: the profile and the
   membership history go with it, and nothing recovers them short of a
   database restore.  Deactivate rather than delete unless you are certain.
