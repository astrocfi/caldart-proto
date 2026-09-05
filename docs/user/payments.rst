============================
Paying, renewing and reports
============================

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
anything above your dues is tax deductible and goes towards training, fuel and
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

Life members have nothing to renew.

Receipts
--------

Stripe emails a receipt to the address on your CalDART account as soon as the
payment settles.  PayPal emails its own receipt.  CalDART itself keeps a
record of every payment against your account: your dashboard shows what you
paid, when, and what it bought.

For a tax letter covering your contributions, ask an account administrator —
the payment report gives them the exact figures.

If something goes wrong
-----------------------

*The card was declined.*
   Nothing was charged.  Try another card, or the PayPal tab.

*"Your payment is still being processed."*
   Some payment methods settle a few seconds later than the browser does.  It
   is safe to close the page: the membership activates on its own when the
   payment clears, and your dashboard will show it.

*You were charged but do not look like a member.*
   Contact |org| with the date and amount.  An administrator can find the
   payment and put it right; the system is built so that a payment is never
   counted twice, so there is no risk in asking.


For account administrators
==========================

**Administration → Payments** in the portal is the money screen.  It needs the
``account_admin`` role.

The headline figures
--------------------

Three tiles across the top, all covering every payment on the system:

* **This month** — the calendar month you are in;
* **Year to date** — 1 January to today;
* **Last 12 months** — a rolling twelve-month window.

Each shows the total taken and how many payments made it up.  Only successful
payments count: a declined attempt was never revenue.

Payments by period
------------------

Below the tiles, a table of totals with a **Month** / **Year** toggle.  For
each period it shows the number of payments, how much was dues, how much was
contributions, a column per payment provider, and the total.  Newest first.

This is the answer to "how are we doing compared to last year?" — switch to
**Year** and read down the total column.

The payment list
----------------

The bottom half is every individual payment, with a filter bar:

* **From** / **To** — the date the money arrived;
* **Provider** — Stripe, PayPal or Test;
* **Status** — succeeded, pending, failed or refunded;
* **Search** — a member's name or email, or a provider's own reference
  (a Stripe PaymentIntent id or a PayPal order id, useful when someone
  forwards you a receipt).

Click a column heading to sort by it; sorting and paging apply to the whole
report, not just the page on screen.

**Export CSV** downloads exactly what the filters describe, one row per
payment: date, name, email, plan, dues, contribution, total, provider, wallet,
status and provider reference.  It opens in any spreadsheet, which is the
easiest route to a year-end summary or a treasurer's report.

Refunds
-------

Refunds are issued in the provider's own dashboard (Stripe or PayPal), not in
CalDART, and **CalDART never finds out**.  Nothing in the system sets a payment
to *Refunded*: the row goes on reading *succeeded*, the money is counted in
every total, and the **Status → Refunded** filter will never match anything.

So a refund is two jobs, not one:

#. Refund in the provider's dashboard.
#. Correct CalDART by hand — edit or cancel the membership term under
   **Administration → Members**, and note in the term why, since the payment
   row cannot tell the story itself.

Keep your own record of refunds until CalDART can record them; see
:doc:`../developer/roadmap`.


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
   only *succeeded* payments while the CSV export includes every status;
   refunds are invisible here (above); and the tiles use the date the payment
   completed, which can fall a day either side of the provider's own
   settlement date.

**A provider column is empty.**
   Only providers that were configured when a payment was taken can appear
   against it.  A demonstration database has everything under *Test*.

**"No payments match these filters."**
   Usually the date range.  **Clear** empties the whole bar.
