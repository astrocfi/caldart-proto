=============================
Paying, renewing, and reports
=============================

How money moves through CalDART: what a member sees when they join or renew,
what happens to their membership the moment a payment clears, and what an
account administrator can see afterwards.


For members
===========

Joining
-------

Joining is a four-step wizard — account, profile, pay, done.  From **Join** on
the public site, or ``/portal/join`` directly, you create an account and fill
in your profile, and the third step is where the money is.  This page is about
that third step; the other three are in :doc:`member-guide`.

**1. Choose a membership.**  |org| offers two:

* **Annual** — $45.00, one year;
* **Life** — $650.00, one payment and you are a member for life.

Annual is selected for you.

**2. Add a contribution, if you would like to.**  |org| is a 501(c)(3), so
anything above your dues is tax deductible and goes towards training, fuel, and
equipment.  The named tiers are:

===============  ==========
Tier             Amount
===============  ==========
Participating    $20
Bronze           $100
Silver           $300
Gold             $1,000
Diamond          $3,000
Platinum         $10,000
===============  ==========

Choose one, type your own figure under **Other amount**, or take **No thank
you** — the membership costs the same either way.  The running total updates
as you choose.

**3. Pay.**  A tab appears for each payment method this site accepts:

*Card · Apple Pay · Google Pay*
   Handled by Stripe.  Type a card number, or — if your browser and device
   support it — tap the **Apple Pay** or **Google Pay** button that appears
   above the card fields and confirm with Face ID, Touch ID or your Google
   account.  Your card details go straight to Stripe; CalDART never sees them.

*PayPal*
   Opens a secure PayPal window.  Sign in, approve, and you come straight
   back.

*Test payment*
   Only on development sites, which take no real money.

Some cards ask your bank to confirm the payment.  If that happens you may be
sent to your bank's page and returned to CalDART afterwards; the screen says
**Confirming your payment…** for a moment while we check with the provider,
and then tells you you are in.

**Your membership starts immediately.**  As soon as the payment clears, the
term is created and the members-only pages open up — there is nothing to wait
for and nobody to chase.

Renewing
--------

**Renew** in the portal menu, or the **Renew** button on your dashboard, opens
the same screen with Annual already chosen.

If your membership is still current, renewing does **not** waste the time you
have left: the new term starts the day *after* your current one ends.  Renew
on 1 March with an expiry of 30 June and your new expiry is 30 June the
following year.  Your dashboard shows the new date straight away.

If your membership has already lapsed, the new term starts today.

Life members have nothing to renew, so **Renew** shows them
**Contribute to CalDART** instead: the page says *As a life member you have
nothing to renew. A contribution keeps the DARTs flying.*, the card above the
form reads **You are a life member. Thank you.**, and the form offers the
contribution tiers with no membership to buy.  **Contribute this amount
automatically each year** under it takes the same amount every year.  |org|
refuses a membership plan from a life member wherever one is sent.

The Payments screen
-------------------

**Payments** in the portal menu is where your money lives.  It has three cards,
in the order they matter:

**Automatic renewal** says whether |org| will renew your membership for you, and
carries the buttons that change that.  A life member's card is headed
**Automatic contribution**, because nothing of theirs renews.  The next section
covers both.

**Your payments** lists everything you have paid |org|, newest first: the date,
what it bought, the amount, what has been refunded if anything has, the status,
and a **Receipt** link.  The link downloads the same PDF the receipt email
carried.  A payment that never settled -- one that failed, or one still in
flight -- has no receipt, because no money arrived.

**Contribution statements** offers one button per calendar year you contributed
in.

Your dashboard's **Recent payments** card shows the last five and links here for
the rest; the line above them names the authority -- **Automatic renewal**,
**Automatic contribution**, or **Automatic renewal and contribution** -- says
whether it is on, and when it is, what the next charge comes to and when.

Renewing automatically
----------------------

You can ask |org| to renew your Annual membership for you, so it never lapses
because a reminder arrived in a busy week.

**Turning it on.**  Tick **Renew automatically each year** at the checkout, and
the card or PayPal account you pay with is saved for next time.  A life member
sees **Contribute this amount automatically each year** in its place, since
nothing of theirs renews.

Or turn it on without paying anything: **Turn on** on the **Automatic renewal**
card opens the same choices the checkout offers -- the plan that will renew, the
contribution to renew beside it, and a tab per payment method -- and saves the
method without charging it.  The card then states what each year's charge will
come to before you save anything, and promises the warning email: *We will email
you fourteen days before every charge.*

**What happens then.**  The day before your membership runs out, |org| charges
the saved method for that year's dues plus your contribution, and your coverage
carries straight on — the new term starts the day the current one ends.  You are
never charged while a whole year of coverage still remains.

You are never charged without warning:

* **Fourteen days before every charge** you get an email saying the amount, the
  date, and which card or account will be used.
* If the card on file expires before the next charge is due, you get an email
  about that too, in time to save another one.
* When the charge goes through, you get an email confirming it and your new
  expiry date, with the receipt PDF attached.

While automatic renewal is on you do not get the ordinary renewal reminders —
the renewal emails cover that term instead.

**Changing or stopping it.**  The **Automatic renewal** card on the Payments
screen shows the method, the plan, the contribution, the next charge date and
the amount.  The date is always there while it is on: it is either the day of a
charge already scheduled or the day the next one falls due.  **Change
contribution** opens the choosers the setup flow shows -- the plan that renews
and the contribution beside it -- and saves both; the dues themselves are
whatever the chosen plan costs on the day.  **Turn off**
asks you to confirm and then stops it, immediately: nothing further is charged,
the saved method is dropped, and your membership still runs to the end of the
term you have paid for.  The ordinary reminders resume.

**If a charge is refused.**  You get an email saying why — "Your card was
declined", or whatever the bank told us — and |org| tries again the next day,
three days after that, and a week after that.  If all four attempts are refused,
automatic renewal switches itself off, you are told so, and the ordinary renewal
reminders take over.  Nothing about your current membership changes; it simply
runs to its end date as it would have anyway.  The card on the Payments screen
then reads **Stopped** and repeats the reason the last charge was refused;
**Turn on again** saves another method and starts it up.

**If a charge is late.**  If |org| misses a charge date — the overnight job was
not running, say — the next run catches up: your membership is renewed on the
spot and the email tells you the charge is happening that day.  The new term
starts on the day the money arrives, so the days you were not covered stay in
the record.  If you have been lapsed for more than a month, |org| does not
charge you out of the blue: automatic renewal switches itself off, you are told
why, and you renew by hand from the Payments screen.

**If you are a life member.**  Your membership never runs out, so there is
nothing to renew — but you can still ask |org| to take a contribution for you
once a year.  The card is headed **Automatic contribution**, the emails say
"contribution" and never "renewal", and the charge falls on the anniversary of
the day you turned it on, or of the last contribution taken.  **Turn on** offers
the contribution tiers and nothing else, and waits for an amount: *Choose a
contribution to charge each year.*  **Change contribution** adjusts the amount;
there is no plan to choose.

**If your record came from the old CiviCRM system** with automatic renewal
switched on, it did not come across: the card was never handed to |org|.  Turn
it on again from the Payments screen, and until you do you will get the ordinary
reminders.

Receipts
--------

|org| emails you a receipt the moment a payment clears, whether you paid by
card, through PayPal, or by a check somebody entered for you.  The PDF is
attached to the message: it carries the organization's name, address and EIN,
a receipt number, the date, what you paid for, and the total.  An automatic
renewal earns one email, not two: the message telling you the membership was
renewed is the one carrying the receipt.

A receipt that covers a contribution also carries the sentence *No goods or
services were provided in exchange for this contribution* — the wording your
accountant looks for.  Membership dues are shown as dues, because a membership
is something you received.

The join wizard's last step says the receipt is on its way, and links to the
Payments screen.  If the email never arrived, or you deleted it, every receipt
can be downloaded again from the **Receipt** link on its row there.  Ask the
office to send one again if you would rather have it in your inbox.

Contribution statements
-----------------------

A statement gathers a whole calendar year of contributions onto one page: the
date, receipt number and amount of each, anything that was refunded, and the
year's total, with the same 501(c)(3) wording.  It is what you file with a tax
return.

**Payments** in the portal offers one button per year you contributed in.  A
year in which you paid dues and gave nothing has no statement, because dues are
not a gift.  If part of a payment was refunded, the refund comes off the
contribution first, and the statement shows the amount, the refund and the net.
A refund that covered the dues rather than the gift is taken off the
contribution all the same, so a statement for a year in which dues came back
understates what was given: check it against the receipts before filing it, and
ask the office to confirm the figure.

If something goes wrong
-----------------------

*The card was declined.*
   Nothing was charged.  Try another card, or the PayPal tab.

*You closed the PayPal window without paying.*
   Nothing was charged.  A note says **Payment canceled**, and the checkout is
   exactly as you left it: the same plan, the same contribution, the same tabs.

*PayPal would not open, and a message says why.*
   The message is CalDART's own — a plan that has closed to new members, say.
   Nothing was charged.  Fix what it names, or pay from another tab.

*"Your payment is still being processed."*
   Some payment methods settle a few seconds later than the browser does.  It
   is safe to close the page: the membership activates on its own when the
   payment clears, and your dashboard will show it.

*You were charged but do not look like a member.*
   Contact |org| with the date and amount.  An administrator can find the
   payment and put it right; the system is built so that a payment is never
   counted twice, so there is no risk in asking.


For treasurers and account administrators
=========================================

**Administration → Payments** in the portal is the money screen.  It needs the
``treasurer`` role or the ``account_admin`` role.  A treasurer sees the money
and nothing else: the member records, with their medical and certificate
details, stay closed to them.  An account administrator holds both.

Moving around the area
----------------------

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

The headline figures
--------------------

Three tiles across the top, all covering every payment on the system:

* **This month** — the calendar month you are in;
* **Year to date** — 1 January to today;
* **Last 12 months** — a rolling twelve-month window.

Each shows the gross taken, what the payment providers kept in fees, what
reached |org|'s bank, and how much has gone back in refunds.  A declined
attempt was never revenue and is not counted; a payment since refunded was, and
is counted with what went back beside it.

Payments by period
------------------

Below the tiles, a table of totals with a **Month** / **Year** toggle.  For
each period it shows the number of payments, how much was dues, how much was
contributions, the fees, the net, the refunds, a column per payment provider,
and the total.

This is the answer to "how are we doing compared to last year?" — switch to
**Year** and read down the total column.

The payment list
----------------

Every individual payment, with a filter bar:

* **From** / **To** — the date the money arrived;
* **Provider** — Stripe, PayPal, Test, or Recorded by hand;
* **Status** — succeeded, pending, failed, partially refunded, or refunded;
* **Plan** and **Kind** — what the payment bought: dues, a contribution, or
  both;
* **Method** — card, Apple Pay, check, cash, and the rest;
* **Reconciled** — matched to a bank statement, or still outstanding;
* **Amount** — a lower and an upper bound on the total;
* **Search** — a member's name or email, a provider's own reference (a Stripe
  PaymentIntent id or a PayPal order id, useful when someone forwards you a
  receipt), or a note you wrote on a payment.

Click a column heading to sort by it; sorting and paging apply to the whole
report, not just the page on screen.

Choosing the columns
--------------------

**Columns** opens a chooser that drives both the table and the exports.
Twenty-one columns are on offer; sixteen of them are on to begin with.  The
five that are off — the receipt number, the day a check was received, your own
note, and the two dates of the term a payment bought — are the ones an audit
wants and an everyday list does not.  Click anywhere outside the chooser, or
press Escape, to put it away.

**Export CSV** and **Export PDF** download exactly what the filters and the
column chooser describe, in the order the table is sorted in.  Both files carry
the day they were run in their name, so two exports never overwrite one
another.  The CSV writes money as a plain number a spreadsheet adds up; the PDF
prints it with a dollar sign and names the filters underneath the title.

One payment's record
--------------------

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
---------------------------------

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
------------------------------------

The **Reconciliation** tab answers, for a range you choose, what the books say
arrived: one row per month, per year, or per provider, with the gross, the
fees, the net, what went back, the net after refunds, and how many of that
period's payments you have already matched.  A **Month** / **Year** /
**Provider** toggle chooses which of the three you are looking at, and **From**,
**To** and **Provider** bound what is counted.

Two dating rules make the rows line up with a statement.  A payment counts in
the period the money arrived.  A refund counts in the period it was *taken*, so
a January payment refunded in February appears in February — which is where the
bank put it.  A month in which money only went back still gets a row.

Open a payment and set its **Reconciled** date once you have found it on the
statement; |org| records that it was you.  Filtering the list to **Reconciled →
No** is then the list of what is left to do.

Both reconciliation exports are named for the range they cover.

Contributions and the year-end list
-----------------------------------

The **Contributions** tab is one row per member who gave something in a
calendar year, largest giver first: how many payments they made, what they
gave, what went back, and the difference.  That last figure is the one an
acknowledgment letter quotes.  Export it as a CSV for a mail merge, or as a PDF
for the board.

Each row carries a **Statement** link, which downloads that member's
contribution statement for the year on screen -- the same document the member
can download for themselves.

A member's ledger
-----------------

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
------------------

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
-------

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
   Widen the date filter first — it does not default to all time.  Then search
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
   Usually the date range.  **Clear** empties the whole bar.
