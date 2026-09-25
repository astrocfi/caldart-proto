===============
Treasurer guide
===============

This guide is for people who hold the ``treasurer`` role: the money, and
nothing else.  **Administration → Payments** in the portal is your screen; it
needs the ``treasurer`` role or the ``account_admin`` role.  A treasurer sees
every payment, fee, refund, and automatic renewal, and the member records, with
their medical and certificate details, stay closed to them.  An account
administrator holds both and reads this guide for the money side of the job.
What a member sees when they pay is in :doc:`payments`.

**Administration → Reports** is open to you too: it emails the payments,
reconciliation and contributions reports on a schedule, to you or to anyone
else who may read them, and it is described under *Reports by email* in
:doc:`account-administrator-guide`.

Moving around the area
======================

A tab bar sits at the top of every finance screen:

* **Overview** (``/portal/admin/payments``) — the headline figures and the
  period table;
* **Payments** (``/portal/admin/payments/list``) — every payment, with the
  filters, the column chooser and the exports;
* **Renewals** — the automatic renewals members have set up and the charges against them;
* **Reconciliation** — the period table built for a bank statement;
* **Contributions** — the year-end acknowledgment list.

Opening one payment, one member's ledger or the form that records a check
leaves the bar in place, with **Payments** marked, so you always know where in
the area you are standing.

Every table in this area fills the width of your browser window: widen the
window and the table widens with it, so more columns fit without scrolling. A
table still wider than the window scrolls sideways on its own, inside its own
frame, rather than crowding the rest of the page.

The headline figures
====================

Three tiles across the top, all covering every payment on the system:

* **This month** — the calendar month you are in;
* **Year to date** — 1 January to today;
* **Last 12 months** — a rolling twelve-month window.

Each shows the gross taken, what the payment providers kept in fees, what
reached |org|'s bank, and how much has gone back in refunds.  A declined
attempt was never revenue and is not counted; a payment since refunded was, and
is counted with what went back beside it.

Payments by period
==================

Below the tiles, a table of totals with a **Month** / **Year** toggle.  For
each period it shows the number of payments, how much was dues, how much was
contributions, the fees, the net, the refunds, a column per payment provider,
and the total.

This is the answer to "how are we doing compared to last year?" — switch to
**Year** and read down the total column.

Above the table, **From**, **To**, **Provider**, **Status**, and **Search**
narrow what the table adds up, exactly as they do on the payment list.  The
tiles ignore them: "this month" is this month whatever the table shows.

The payment list
================

Every individual payment, with a filter bar:

* **From** / **To** — the date the money arrived;
* **Provider** — Stripe, PayPal, Test, or Recorded by hand;
* **Status** — succeeded, pending, failed, partially refunded, or refunded;
* **Plan** and **Kind** — what the payment bought: dues, a contribution, or
  both;
* **Method** — card, Apple Pay, check, cash, and the rest;
* **Reconciled** — matched to a bank statement, or still outstanding;
* **At least** / **At most** — a lower and an upper bound on the total, in
  whole dollars;
* **Search** — a member's name or email, a provider's own reference (a Stripe
  PaymentIntent id or a PayPal order id, useful when someone forwards you a
  receipt), or a note you wrote on a payment.

Each filter applies as soon as you set it; a typed one applies once you pause.
**Reset to Defaults** empties them all.  The filters, the sort order, and the page you are
on are kept in the page's address, so a filtered list can be bookmarked or sent
to another treasurer, and the browser's back button steps back through the
filters you applied.  The Overview, Reconciliation, and Contributions tabs keep
their filters in the address the same way.

Click a column heading to sort by it; sorting and paging apply to the whole
report, not just the page on screen.

Choosing the columns
====================

**Columns** opens a list of checkboxes that drives both the table and the
exports.
Twenty-one columns are on offer; sixteen of them are on to begin with.  The
five that are off — the receipt number, the day a check was received, your own
note, and the two dates of the term a payment bought — are the ones an audit
wants and an everyday list does not.  **Reset to the default columns**, under
the boxes, ticks those sixteen again.

Beside **Columns**, **Load columns** lists the sets of columns you have saved
for the payments report.  Pick a name and its columns are applied; the list
closes.  The trashcan beside a name deletes that set.  **Save columns** keeps
the boxes as they stand: type a name of up to 60 characters and press **Save**,
or press Enter.  Saving under a name you already use replaces that set, and
loading a set puts its name in the box, so a set you load and change is saved
again under the same name.  Each of the three buttons opens its own panel under
itself, which a click outside it or Escape puts away.  Your saved sets are
yours alone, and each report keeps its own.

**Export CSV** and **Export PDF** download exactly what the filters and the
column chooser describe, in the order the table is sorted in.  Both files carry
the day they were run in their name, so two exports never overwrite one
another.  The CSV writes money as a plain number a spreadsheet adds up; the PDF
prints it with a dollar sign and names the filters underneath the title.

One payment's record
====================

Clicking a member's name in the list opens the payment itself: who paid, what
for, the dues and the contribution separately, the total, the provider's fee
and the net, what has been refunded, the reference the provider gave it, when
the receipt was emailed, the term it bought, and a row -- labeled
**Automatic renewal**, **Automatic contribution**, or **Automatic renewal and
contribution** by what the payment was for -- naming the day it was charged
automatically, or saying it was paid by somebody at a keyboard.  Beneath that
are the refunds against it, and beneath those the two fields that are yours:
the day you matched the payment to a statement, and a note — the check
number, or why the entry exists.

Four actions sit under the record:

* **Refund** opens the refund form described below;
* **Resend receipt** emails the member their receipt again, and the screen
  stamps the moment it went;
* **Download receipt** gives you the PDF, for attaching to something else;
* **Fetch fee from provider** appears only while the fee is still unknown.
  Stripe and PayPal report what they kept a moment after the money arrives, and
  sometimes later than that; this asks again.  A payment nobody can price — one
  recorded by hand, one that never succeeded — says so rather than reporting a
  fee of nothing.

A link at the foot opens everything that member has paid.

Recording a payment taken by hand
=================================

**Record a payment** is for money that never passed through a card: a check in
the mail, cash at a meeting, a bank transfer.  Search for the member, choose
the plan (or none, for a pure contribution), name the method, type the check
number, and set the day the money arrived.

|org| records it as already paid, with no provider fee, activates whatever term
it bought, and emails the member the same receipt a card payment earns.  The
day you set is the one the payment is dated by everywhere in the books — the
day the check arrived, not the day you keyed it in.  A check number another
recorded payment already carries is refused, which is what stops the same check
being entered twice.

Reconciling against a bank statement
====================================

The **Reconciliation** tab answers, for a range you choose, what the books say
arrived: one row per month, per year, or per provider, with the gross, the
fees, the net, what went back, the net after refunds, and how many of that
period's payments you have already matched.  **Rows** chooses which of the
three you are looking at, by month unless you choose by year or by provider,
and **From**, **To**, and **Provider** bound what is counted.

Two dating rules make the rows line up with a statement.  A payment counts in
the period the money arrived.  A refund counts in the period it was *taken*, so
a January payment refunded in February appears in February — which is where the
bank put it.  A month in which money only went back still gets a row.

Open a payment and set its **Reconciled** date once you have found it on the
statement; |org| records that it was you.  Filtering the list to **Reconciled →
No** is then the list of what is left to do.

**Export CSV** and **Export PDF** carry the rows on screen, grouped the same
way.  Like every report, each file is named for the day it was run; the PDF
prints the range it covers under its title.

Contributions and the year-end list
===================================

The **Contributions** tab is one row per member who gave something in a
calendar year, largest giver first: how many payments they made, what they
gave, what went back, and the difference.  That last figure is the one an
acknowledgment letter quotes.  **Year** shows this year until you choose one of
the nine before it.  Export it as a CSV for a mail merge, or as a PDF
for the board.

Each row carries a **Statement** link, which downloads that member's
contribution statement for the year on screen -- the same document the member
can download for themselves.

A member's ledger
=================

Opening a member from a payment gives their whole money history in one place:
what they have paid, given, and been charged in fees over every year; their
standing renewal authority, if they have one -- the card is titled
**Automatic renewal**, **Automatic contribution**, or **Automatic renewal and
contribution** by what it charges for, and reads **Contribution** where a
life member's authority renews no plan -- with the saved method, the next
charge date and the reason the last charge was refused; every payment,
including the attempts that failed, each linking to its own record; and a
button for every year they can be sent a contribution statement for.

An account administrator reaches the same cards from the Payments tab of the
member record; a treasurer, who does not open member records, reaches them
here.

Automatic renewals
==================

The **Renewals** tab lists every member who has asked |org| to renew their
membership, contribute automatically, or both: the plan -- **Contribution**
for a life member's standing authority, which renews no plan -- what the next
charge comes to, the day it falls due, the card or PayPal account it will be
taken from, and the state of the authority itself -- on, paused, awaiting a
method, or off.  Filter by state, or search by name, email address, or the
saved method.

A paused renewal shows the reason its last charge was refused beneath its
state.  That is the answer to "why was I not renewed?", and it is the wording
the member was emailed.

**Turn off** ends a member's standing authority on their behalf.  It asks you
to confirm, because the member is emailed when it happens, and the toast that
follows names what was turned off -- automatic renewal, automatic
contribution, or both -- by what the authority charged for.  Every charge
still scheduled is dropped and the membership itself runs to the end of its
term; the authority stays on the list, marked off, rather than disappearing.
A member can turn it on again themselves from their own **Payments** screen.

Beneath the authorities, **Recent charges** is one row per scheduled charge: the
day it was due, the member, whether it was charged, refused, skipped, or is
still waiting, when it was tried, and the reason a provider gave for refusing.
Filter by outcome to read a run's refusals on their own.

Refunds
=======

A refund is issued from CalDART, on the payment itself, and the record stays
with the payment: the amount, the reason, your note, and the date.

Open the payment, choose **Refund**, and fill in three things:

* **Amount** — prefilled with everything the payment has left unrefunded.
  Type a smaller figure to give back part of it, such as a contribution while
  the dues stand.
* **Reason** — requested by the member, duplicate payment, charged in error,
  fraudulent, or other.
* **Cancel the membership term** — prefilled on when the amount covers the
  dues, off when it does not.  Leave it off for a contribution refund; the
  membership is untouched either way unless you say so.

CalDART asks the payment provider for the money, and the member is emailed
with the amount, what it was for, and whether their membership ended with it.
The money goes back to the card or account they paid with, and their bank
decides how quickly it appears — usually a few working days.

The payment's status then reads **Partially refunded** while some of it has
gone back and **Refunded** once all of it has, and the reports count refunds
separately from what was taken.

A payment recorded by hand is refunded the same way, except that nobody is
called: write the check, record the refund, and the ledger matches.

**If the provider refuses.**  The refund is kept with the status *failed* and
the reason the provider gave, and no money moved.  Try again, or take it up in
the provider's dashboard.

**Refunds made in Stripe or PayPal directly.**  CalDART hears about those too:
the provider's notification creates the refund record, marked *Issued in the
provider's dashboard*.  What it does **not** do is end anybody's membership —
no notification decides that.  If the refund should end the term, cancel it
yourself on the payment's screen.


When something goes wrong
=========================

**A member says they paid and you cannot find the payment.**
   Clear the date filter first: a range left from an earlier search, or carried
   in a link somebody sent you, hides every payment outside it.  Then search
   by their email address rather than their name, since a payment carries the
   account's address.  If the money is on their card statement and there is no
   row here at all, the provider took it without CalDART hearing back; the
   provider's dashboard has the truth, and the member's membership needs
   granting by hand.

**A payment shows as succeeded but the member is not current.**
   Open the member's record and look at the Memberships tab.  A payment
   activates a term at the moment it succeeds, so a succeeded payment with no
   term behind it is a fault worth reporting — grant the term manually in the
   meantime.

**The totals do not match the provider's dashboard.**
   Three ordinary reasons before you suspect a fault: the period tiles count
   only money that arrived while the exports include every status, failed
   attempts and all; the tiles report the gross, and a provider's dashboard
   often shows you the net; and the tiles use the date the payment completed,
   which can fall a day either side of the provider's own settlement date.
   The **Reconciliation** tab is the screen built for this comparison, since it
   shows the gross, the fees and the net side by side.

**A provider column is empty.**
   Only providers that were configured when a payment was taken can appear
   against it.  A demonstration database has everything under *Test*.

**"No payments match these filters."**
   Usually the date range.  **Reset to Defaults** empties the whole bar.
