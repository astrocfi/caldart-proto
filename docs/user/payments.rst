=============================
Paying, renewing, and reports
=============================

How money moves through CalDART for a member or a friend: what you see when you
join, renew, or give, what happens to your membership the moment a payment
clears, how to give on a schedule, and how to find a receipt or a statement
afterwards.  The other side of the ledger — every
payment, refunds, reconciliation, and the financial reports — is the
:doc:`treasurer's screens <finance/index>`.


For members
===========

Joining
-------

Joining is a five-step wizard — account, verify, profile, pay, done.  From
**Join** on the public site, or ``/portal/join`` directly, you create an
account, verify its email address, and fill in your profile, and the fourth step
is where the money is.  This page is about that fourth step; the others are in
:doc:`member-guide`.

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
contribution tiers with no membership to buy.  **Make this a recurring
donation** under it gives the same amount on a schedule (see
:ref:`recurring-donations`).  |org| refuses a membership plan from a life member
wherever one is sent.

Giving
------

**Donate** in the portal menu (``/portal/donate``) is where any member or friend
gives to |org|, whatever their membership: a gift buys no membership and needs
none.  The screen is the checkout's contribution form: the tiers, **Other
amount**, and the running **Total today**, then the payment tabs.  A gift taken
now thanks you, emails the receipt, and takes you to the Payments screen.

Under the amount, **Make this a recurring donation** turns the gift into one
that repeats (see :ref:`recurring-donations`).  If you already give on a
schedule, the screen says so above the form, with how much and how often, and a
**Go to Payments** button: change your donation there with **Change**, because a
recurring donation set up here replaces the one you have.

The Payments screen
-------------------

**Payments** in the portal menu is where your money lives.  Its cards come in
the order they matter:

**Automatic renewal** says whether |org| will renew your membership for you, when
the next charge falls and what it comes to, and carries the buttons that change
that.  A life member and a friend have no membership to renew, so they do not see
it unless they still hold an automatic renewal that is not turned off, which the
card then shows so they can turn it off.  :ref:`renewing-automatically` covers it.

**Recurring donation** says whether you give on a schedule, how much, how often,
and when the next charge falls, with **Change**, **Turn off**, and **Set up**,
which goes to the Donate screen.  :ref:`recurring-donations` covers it.

**Your payments** lists everything you have paid |org|, newest first: the date,
what it bought, the amount, what has been refunded if anything has, the status,
and a **Receipt** link.  The link downloads the same PDF the receipt email
carried.  A payment that never settled -- one that failed, or one still in
flight -- has no receipt, because no money arrived.

**Contribution statements** offers one button per calendar year you contributed
in.

Your dashboard's **Recent payments** card shows the last five and links here for
the rest; the line above them names the authority -- **Automatic renewal** or
**Automatic renewal and contribution**, and a life member's **Recurring
donation** -- says whether it is on, and when it is, what the next charge comes
to and when.

.. _renewing-automatically:

Renewing automatically
----------------------

You can ask |org| to renew your Annual membership for you, so it never lapses
because a reminder arrived in a busy week.

**Turning it on.**  Tick **Renew automatically each year** at the checkout, and
the card or PayPal account you pay with is saved for next time.  Automatic renewal
is always yearly.

Or turn it on without paying anything: **Turn on** on the **Automatic renewal**
card opens the same choices the checkout offers -- the plan that will renew, the
contribution to renew beside it, and a tab per payment method -- and saves the
method without charging it.  The card then states what the charge will come to and
the day it falls on before you save anything, and promises the warning email:
*CalDART will charge <amount> on <date>, and each year after that. We will email
you fourteen days before every charge.*

**The day you are charged on.**  It is yours to choose.  **First charge on**, the
date box between the choosers and that sentence, opens on the day your membership
runs out, which is the day most people want, or on today when you hold no current
term.  The box takes any day from today on.
An earlier day than the one it opens on charges you — and renews you — before the
term you hold has run out, so the months still to run are not the ones you get
back.  A later day leaves your membership lapsed from the day it runs out until
the charge comes round; the card says so on its **Next charge** row, and the
warning email says so too.  A day that has already gone by is refused: *The next
charge cannot be in the past.*

**What happens then.**  On that day |org| charges the saved method for that year's
dues plus your contribution, and your coverage carries straight on — the new term
starts the day after the current one ends.  You are never charged while a whole
year of coverage still remains.

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
charge already scheduled or the day you chose for the next one, and when it falls
after your term ends the row adds *after your membership runs out on* that day.
**Change** opens the choosers the setup flow shows -- the plan that renews, the
contribution beside it, and **Next charge on** -- under the heading **Change your
renewal**, and saves all three; the dues themselves are whatever the chosen plan
costs on the day.  A charge already scheduled keeps its own day, whatever you set
here, so a day you set while one is waiting is the day of the charge after it.
After each charge the day moves to the end of the term that charge bought, so a
day you choose is the day of one charge, not of every charge after it.  **Turn off** asks you to confirm and
then stops it, immediately: nothing further is charged, the saved method is
dropped, and your membership still runs to the end of the term you have paid for.
The ordinary reminders resume.

**If a charge is refused.**  You get an email saying why — "Your card was
declined", or whatever the bank told us — and |org| tries again the next day,
three days after that, and a week after that.  If all four attempts are refused,
automatic renewal switches itself off, you are told so, and the ordinary renewal
reminders take over.  Nothing about your current membership changes; it simply
runs to its end date as it would have anyway.  The card on the Payments screen
then reads **Stopped** and repeats the reason the last charge was refused;
**Turn on again** saves another method and starts it up.

**If a charge is late.**  If |org| misses your charge date — the overnight job
was not running, say — the next run catches up: the charge is taken on the spot
and the email tells you it is happening that day.  The new term starts on the day
the money arrives, so the days you were not covered stay in the record.  If you
have been lapsed for more than a month, |org| does not charge you out of the blue:
automatic renewal switches itself off, you are told why, and you renew by hand
from the Payments screen.

**If you are a life member or a friend.**  Nothing of yours renews, so there is
no automatic renewal to turn on.  To give on a schedule, set up a recurring
donation instead.

**If your record came from the old CiviCRM system** with automatic renewal
switched on, it did not come across: the card was never handed to |org|.  Turn
it on again from the Payments screen, and until you do you will get the ordinary
reminders.

.. _recurring-donations:

Recurring donations
-------------------

A recurring donation gives the same amount to |org| monthly, quarterly, or
yearly, from a card or PayPal account saved for the purpose.  Any member, life
member, or friend may hold one, beside an automatic renewal or without one, and
it charges whatever your membership: it renews nothing and buys no term.

**Setting one up.**  On the Donate screen, choose the amount and tick **Make this
a recurring donation**.  Choose **Monthly**, **Quarterly**, or **Yearly**, and the
**First charge on** day, which opens on today and takes no day before it.  The
line under them says what will happen, for example *CalDART charges $20.00 today,
and each month after that.*

* **First charge today.**  The gift is paid now, through the payment tabs, and the
  card or account you pay with is saved for the charges after it.  The next one
  falls a month, three months, or a year on.
* **First charge on a later day.**  Nothing is paid today, and **Total today**
  reads $0.00.  The tabs save a card or PayPal account instead, as setting up an
  automatic renewal does, and the first charge falls on the day you chose.

**What you hear about it.**  A yearly donation gets the fourteen-day warning email
before every charge, exactly as a renewal does.  A monthly or quarterly one sends
no warning: the email that says it was taken, with the receipt attached, is the
one message per charge.  A card that will expire before the next charge earns a
warning in time to save another.

**The schedule.**  Each charge moves the next one on by the cadence from the day
the charge was due, keeping its day of the month where the month has it:
a monthly donation that started on 31 January is next charged on 28 February.

**Changing or stopping it.**  The **Recurring donation** card on the Payments
screen shows the method, the amount, **How often**, and the next charge.
**Change** opens the amount, the cadence, and **Next charge on** under the heading
**Change your recurring donation**, and waits for an amount: *Choose an amount to
give.*  **Turn off** asks you to confirm, then stops it at once and drops the
saved method.  **Set up** takes you to the Donate screen to start one again.  A
refused charge is retried and the donation paused after four refusals, exactly as
a renewal is; the card then reads **Stopped** with the reason.

**One contribution, one place.**  An automatic renewal can carry a contribution
beside the dues, and a recurring donation is a contribution of its own, so you
hold one or the other, never both.  Setting up a recurring donation while your
renewal takes a contribution first asks: *Your automatic renewal already
includes a contribution of $X a year. Set up a recurring donation and that
contribution comes off the renewal; your dues still renew automatically.*
The question comes in place of the payment options, before anything is charged
or saved.  **Continue** agrees to move it and brings the payment options back;
pay or save the card as before, and the renewal keeps renewing your dues while
the donation gives from then on.  While you hold a recurring donation, a contribution on your
renewal is refused with *You already have a recurring donation. Change it on the
Donate screen.*

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
