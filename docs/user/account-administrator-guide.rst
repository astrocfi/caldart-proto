===========================
Account administrator guide
===========================

Account administrators look after the people in |org|: who is a member, when
their membership runs out, what is on their record, and what the organisation
can prove about all of it in a spreadsheet or a PDF.

You need the ``account_admin`` role to use any of the screens on this page.
System administrators have it implicitly.  Everything lives under **Members**
in the portal menu, at ``/portal/admin/members``.


The member list
===============

The list shows everyone with a CalDART account — ``member`` is granted the
moment someone registers, so "accounts" and "members" are the same set of
people — one row each:

**Member**
   Their name, which links to the full record, followed by their DART, pilot
   certificate and, when they hold one, their medical class with a chip saying
   whether it is still current.  A deactivated account says so here.

**Email**
   A ``mailto:`` link, so you can write to someone straight from the list.

**Membership**
   A status chip and the expiry date behind it.  The chip is green while the
   membership is current, amber in the last 30 days, red once it has run out
   and grey for someone who has never been a member.  Lifetime members show
   "Lifetime member" and no date.

**Joined**
   The start of their first membership term, which is blank for someone who
   has never had one.

The expiry date is the end of the member's *unbroken* coverage.  Somebody who
renews in March for a term that starts in July already shows next July's date,
because their cover runs without a break — you never have to add the terms up
yourself.

Click any column heading to sort by it; click again to reverse the order.  The
sort, like the filters, is part of the page's address, so a sorted and filtered
list is a link you can bookmark or send to somebody else.


Filtering
---------

The filter bar sits above the table.  The dropdowns apply the moment you change
them; the **Search** and **Expiring within** boxes apply when you press Enter
or the **Apply** button, so a half-typed name never runs a search.  **Clear**
empties the whole bar.

**Search**
   Matches a name, an email address, either phone number or a pilot
   certificate number.  Full names work: ``Ana Bracco`` finds her.

**Membership**
   *Current* (a term covers today), *Expired* (a term has run out) or *Never a
   member* (nobody has ever granted or sold them a term).  The three between
   them account for every account exactly once.

**Certificate** and **Medical**
   The pilot certificate and medical class on the member's profile.

**DART**
   The team the member belongs to.

**Role**
   People who hold a particular role.  This is the role actually assigned to
   the account: a system administrator is *not* listed under every other role
   even though they can do everything.

**Expiring within**
   A number of days.  It uses the computed expiry, so a member who has already
   renewed drops out of the window immediately, and lifetime members never
   appear in it.

Filters combine.  "Current members of the Napa DART whose membership expires
within 30 days" is three dropdowns and a number.


Adding a member
===============

**New member** opens a form in two halves.  Only the email address is
required; everything else can be filled in later, by you or by the member.

* **Account** — email address, first and last name, and an optional password.
* **Profile** — contact details, aviation details (DART, certificate, medical,
  ratings, hours), volunteer interests, and the administrator-only fields.

Leave the password box empty unless you have a particular reason not to.  The
account is then created with no usable password and the new member is emailed
a link to choose one for themselves.  If you do type a password, no email is
sent and you have to tell them what it is.

Either way the account is granted the ``member`` role and an empty profile is
created.  Creating a member does **not** give them a membership: grant a term,
or let them pay online.


The member record
=================

Clicking a name opens that person's record.  A summary strip at the top
carries their membership chip, plan, expiry and join date; below it are four
tabs.  Arrow keys move between the tabs, and the tab you are on is part of the
address, so you can send a colleague straight to somebody's payment history.

Profile
-------

The same fields as the new-member form, plus:

* **Account is active** — clearing it stops the member signing in without
  deleting anything.
* **How they heard about CalDART** and **Administrator notes** — visible only
  to account administrators.  Members never see them, on any screen.

**Save changes** writes the account and the profile in one request.

Memberships
-----------

The history table lists every term: plan, start, end, status, where it came
from (a payment, a manual grant or the demo seed), the note, and who granted
it.

**Edit** on a row lets you correct that term's end date, status or note — for
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

Fill the start date in only when you are recording something that happened on
a particular day — a cheque that arrived last month, say.

Payments
--------

Everything this member has paid: date, what it was for, the membership portion,
any contribution on top, the total, the provider and the outcome.

Terms you grant by hand have no payment attached, so they do not appear here.
For the organisation-wide ledger and the month-by-month and year-by-year
totals, use **Payments** in the menu.

Danger zone
-----------

Deleting a member is permanent and takes their profile, every membership term
and their whole payment history with them.  There is no undo and no archive.

The delete button stays disabled until you type the member's email address
into the confirmation box.  Two deletions are refused outright:

* your own account; and
* a system administrator's account, unless you are a system administrator
  yourself.

If somebody has simply left, clearing **Account is active** on the Profile tab
is almost always the better answer: it stops them signing in and keeps the
record for the accounts.


Reports
=======

**Export CSV** and **Export PDF** sit at the top right of the member list and
export *exactly what the list is showing* — the same filters, the same order,
every matching member and not just the page in front of you.

* **CSV** opens in a spreadsheet.  Use it for mail merges, board packs and
  anything you want to sort or total yourself.
* **PDF** is a landscape letter table, ready to print, with the filters you
  applied printed under the title and the date and page numbers at the foot.
  It is the one to attach to minutes, because it says on its face what it is a
  list of.

Both carry the same sixteen columns: name, email, phone, DART, status, plan,
expiry, certificate and its number, IFR, medical class and expiry, aircraft,
city, state and join date.  A lifetime member has no expiry date, so that cell
is empty and the plan column says *Life*.

The columns are listed field by field in the developer documentation under
:doc:`../developer/reports`.


Common tasks
============

**Who is about to lapse?**
   Membership *Current*, Expiring within ``30``.  Export the CSV for the
   renewal mail-out.  Automatic reminders go out at 60, 30 and 7 days before
   expiry, on the day itself, and 30 days after.

**Who has lapsed and not come back?**
   Membership *Expired*, sort by Membership to see the longest-lapsed first.

**How big is a DART?**
   DART, then Membership *Current*.  The caption under the filter bar gives
   the count.

**Somebody paid by cheque.**
   Open their record, Memberships, Grant a term, choose the plan, and note the
   cheque number.  Leave the start date blank unless the cheque should be
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
   that record instead of creating a second one.  Capitalisation is ignored,
   so ``Marta@`` and ``marta@`` collide.

**The new member never got their "set your password" email.**
   It is only sent when you leave the password box **empty**.  If you typed a
   password, no email went out and you have to tell them what it is.  If you
   did leave it empty, ask a user administrator to send a password reset from
   ``/portal/admin/users``, which does the same job.

**"You cannot delete your own account."**
   Exactly what it says.  Ask another administrator.

**"Only a system administrator can delete a system administrator."**
   Deleting an administrator is deliberately harder than deleting a member.
   Ask a system administrator, or deactivate the account instead — which keeps
   the history and locks them out just as effectively.

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
   It should not: the export carries the filters the screen has.  Check that
   you pressed **Apply** after typing in the Search or Expiring-within box —
   the dropdowns apply immediately, those two do not.

**A deletion took the payments with it.**
   Deleting a member is a hard delete: the profile, the membership history and
   the payment records all go, and nothing recovers them short of a database
   restore.  Deactivate rather than delete unless you are certain.
