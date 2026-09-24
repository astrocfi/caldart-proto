=================
Automatic renewal
=================

A member can ask CalDART to renew their membership for them: the payment method
they used is saved with the provider, and a daily scan charges it a few days
before each term runs out.  This page covers the mandate that authority is held
in, the scan that acts on it, the emails it sends, how it interacts with the
renewal reminders, and how to operate it.  :doc:`api-renewals` is the endpoint
reference, and :doc:`/user/payments` is what the member and the treasurer see.

.. _renewals-mechanism:

The mechanism
=============

The schedule lives here, not at the provider.  There is no Stripe subscription
and no PayPal billing plan: CalDART saves a payment method, keeps its own record
of what to charge and when, and confirms an ordinary payment off-session when
the day comes.  That keeps the plan, the price, the term arithmetic, the
reminder logic and the receipts in one place, and it means changing a plan's
price changes what renews without touching either provider.

A **mandate** (``RenewalMandate``) is one member's standing authority.  A member
has at most one: it is a ``OneToOneField`` on the account.  It carries the plan
it renews, the contribution renewed alongside the dues, the provider, the
provider's handles on the saved method, the label the member reads, and a status.
Its plan is null for a member who already holds a lifetime term, which is what
makes the authority a contribution rather than a renewal.  The statuses are:

``pending``
   created, but no method saved yet.  A checkout that asked for automatic
   renewal and has not been paid looks like this, and so does a setup the member
   started and abandoned.
``active``
   a method is saved and the scan will charge it.
``paused``
   a charge and all of its retries were refused.  Nothing further is charged and
   the ordinary renewal reminders resume.
``canceled``
   the member or an administrator turned it off.

A **renewal attempt** (``RenewalAttempt``) is one scheduled charge.  It names the
mandate, the membership term whose expiry it renews, the day it is due, the
payment it created once it ran, the provider's decline reason when it failed, and
three timestamps -- ``noticed_at``, ``attempted_at`` and ``result_emailed_at`` --
which are what make the emails idempotent.  A retry carries ``retry_of``, so a
ladder of attempts reads back as one renewal.

A lifetime plan can never hold a mandate: it does not expire, so there is nothing
to renew.  Neither can the ``manual`` provider: a check cannot be written again
without the member.  Both refusals are a 400 keyed by ``auto_renew``.

.. _renewals-kinds:

The three kinds
===============

What a mandate charges for is read off its plan and its contribution, and it is
what every email and every screen says:

===================  ==========================================================
``kind``             The mandate
===================  ==========================================================
``renewal``          names a plan and no contribution.  It renews the membership
                     and nothing else.
``both``             names a plan and a contribution.  It renews the membership
                     and takes the contribution in the same charge.
``contribution``     names no plan at all.  The member already holds a lifetime
                     term, so nothing of theirs renews; the authority is over the
                     contribution alone, charged once a year.
===================  ==========================================================

``mandate_kind(mandate)`` answers the kind and ``kind_label(kind)`` the words for
it in running prose -- ``renewal``, ``renewal and contribution``,
``contribution``.  A contribution-only mandate never says "renew" or "membership
renewal" to the member.

A life member can hold only a contribution-only authority.  Asking for a plan is
refused with ``A life member's membership does not renew; choose a contribution
instead.`` and asking for no contribution with ``A contribution to charge each
year is needed.``; both are a 400 keyed by ``auto_renew``, and both guard
``POST /me/renewal/setup``, ``PATCH /me/renewal`` and a checkout's ``auto_renew``
alike.  A checkout that tries to sell a life member a term is refused separately,
keyed by ``plan``.

.. _renewals-next-charge:

The next charge is never unknown
================================

``next_charge_on(mandate, today)`` is ``None`` only for a mandate that is not
``active``.  For one that is, it answers, in order:

1. the earliest ``scheduled`` attempt's own date, when one is waiting;
2. for a contribution-only mandate, ``contribution_charge_date(mandate, today)``;
3. for a member with a dated current term, that term's charge date;
4. otherwise ``today`` -- the term has already run out, and the next scan is what
   charges it.

``contribution_charge_date`` is one year after the local date of
``last_charged_at``, or of ``created_at`` when nothing has been charged yet.  An
anniversary of 29 February becomes 28 February, and one that has already gone by
is answered as ``today``.

So an active mandate always has a date to show, on the member's payments screen,
on the finance screens and in the emails that report a charge.

.. _renewals-schedule:

The schedule
============

Five constants in ``apps/payments/renewals.py`` set the cadence:

====================================  =========  =============================
Constant                              Value      Meaning
====================================  =========  =============================
``CHARGE_LEAD_DAYS``                  1          Days before a term's ``ends_on``
                                                 that its renewal is charged.
``NOTICE_DAYS``                       14         Days before that charge that the
                                                 advance warning goes out.
``RETRY_OFFSETS``                     (1, 3, 7)  Days after a failed charge that
                                                 each retry is scheduled for.
``CARD_EXPIRY_WARNING_DAYS``          30         How close to a card's expiry the
                                                 member is warned it will not last.
``CATCH_UP_DAYS``                     30         How long after a term ran out a
                                                 scan may still renew it.
====================================  =========  =============================

The lead is a single day because a member is never charged for the coming year
while a whole year of coverage still remains: the charge falls on the term's last
full day.  A decline is therefore retried after the term has run out -- the next
day, three days later, and a week after that -- and the term a late charge buys
starts on the day the money arrives, not on the old expiry, so the days nobody
was covered stay visible in the record.  When all three retries are refused the
mandate is paused, the member is told automatic renewal is off, and the reminders
take over.

.. _renewals-scanner:

The scan
========

``run_auto_renewals(*, today, dry_run, actor)`` is the one entry point.  The
management command, ``POST /system/renewals/run`` and the systemd timer all call
it, and it does three things in order.

1. **Notice.**  For every ``active`` mandate, find the member's active term that
   runs furthest into the future.  If its charge date -- ``ends_on`` less
   ``CHARGE_LEAD_DAYS`` -- is within ``NOTICE_DAYS``, and no attempt for that term
   is either waiting or already paid, create a ``scheduled`` attempt for that date
   and send ``renewal_notice``.  A mandate that names a plan but whose member has
   since been granted a lifetime term has no expiry left to renew and is skipped
   as ``lifetime``.

   A contribution-only mandate is treated the same way, with
   ``contribution_charge_date`` in place of the term's charge date: the notice
   goes out ``NOTICE_DAYS`` before it and schedules an attempt against the
   member's lifetime term.  A member who holds no lifetime term is skipped as
   ``no_term``.

   Only a ``scheduled`` or ``succeeded`` attempt stands in the way, so a mandate
   that was paused over a term and then turned back on is scheduled again rather
   than left to lapse.  An attempt that is waiting but whose notice the mail
   server refused is written to again on the next run.

   The notice is a window, not a day.  A charge date that has already gone by --
   because the scanner was not running on it -- is taken as today: the attempt is
   dated today and ``renewal_notice`` says the charge is happening today rather
   than naming a date the member has already passed.  A mandate whose member has
   no term left to renew at all goes to the catch-up rule below.

2. **Card expiry.**  If the saved card expires before the next charge, and its
   expiry is within ``CARD_EXPIRY_WARNING_DAYS``, send ``renewal_card_expiring``.
   The expiry the warning was sent for is recorded on the mandate, so the warning
   goes out once rather than every morning.

3. **Charge.**  For every ``scheduled`` attempt due today or earlier: claim the
   attempt, create the payment from the plan's current price plus the mandate's
   contribution, then ask the provider to charge the saved method off-session.

   The claim is a single conditional update that stamps ``attempted_at`` while the
   attempt is still ``scheduled`` and unstamped.  Two scans running at once -- the
   06:30 timer and an administrator pressing **Run now** -- therefore charge once
   between them: the run that loses the claim counts the attempt as ``in_flight``
   and moves on.

   On success the payment goes through the same ``mark_succeeded`` path as a
   checkout, so the next term is activated starting the day after the current one
   ends; the mandate's failure count is cleared, the attempt is ``succeeded`` and
   ``renewal_charged`` goes out.  It carries CalDART's receipt and its PDF, and
   stamps the payment's ``receipt_sent_at``: an automatic charge earns exactly
   one email, so ``mark_succeeded`` sends no plain receipt for a payment a
   renewal attempt owns.  A charge taken after the member has already
   expired starts its term on the day the money arrives, never back-dated to the
   old expiry, so the days nobody was covered stay visible in the record.

   On a decline the payment is marked failed, the provider's reason is stored on
   the attempt, the failure count rises, and ``renewal_failed`` goes out naming
   either the day of the next try or that it was the last.  A mandate with
   retries left gets the next attempt from ``RETRY_OFFSETS``; one whose retries
   are exhausted is paused.

   A provider that cannot be reached, or that is not configured, says nothing
   about the member's card: the pending payment is deleted, the claim is released,
   the attempt stays ``scheduled`` for the next scan, and the run counts it as
   ``provider_down``.  No retry rung is spent, no email goes out and the mandate
   stays ``active``.

   An attempt whose mandate is no longer active, and one whose member has renewed
   by some other means in the meantime, is closed as ``skipped`` and charges
   nothing.  A contribution-only charge extends no term, creates a payment with no
   plan, and can never be overtaken by a renewal, so the "already renewed" rule
   does not apply to it; the retry ladder and the pause do, unchanged.

The run returns a summary -- ``noticed``, ``warned``, ``charged``, ``failed``,
``paused``, ``skipped`` -- and writes one ``renewals.run`` audit record.  A dry
run changes no mandate, emails nobody and charges nobody; it reports the counts
the same scan would produce, and the rehearsal itself is still recorded in the
audit log.

.. _renewals-actions:

Who the run was about
=====================

Counts answer how much happened, never to whom.  Beside them the run carries
``actions``: one ``RunAction`` (``caldart/runs.py``, shared with the reminder
scan) for every email the scan sent and every charge it took.  Each names the
kind, the member, their address, the date the action turns on, the amount for a
charge, and a detail such as a decline reason.

A live run records what it did and a dry run what it would have done, so an
operator can rehearse the scan and read off who is about to be written to.  A
rehearsal cannot ask the provider whether a charge would be taken, so it reports
the charge and the message a charge that succeeds sends; a live run reports the
decline instead when the provider refuses.

A charge whose date has already come round is scheduled and taken by the same
scan.  A rehearsal writes no attempt for its charge step to find, so the notice
step hands the attempts it would have written straight to it, and a rehearsal
names every charge the live run of that date then takes.

``manage.py run_auto_renewals`` prints one line per action after the counts --
``would email renewal_notice to Maria Alvarez <maria@example.org> on
2026-10-14`` in a rehearsal, ``emailed ...`` in a live run -- and
``POST /system/renewals/run`` answers the same list as JSON.

Every email is keyed on a timestamp of the attempt it belongs to, so a scan run
twice in one day sends nothing twice.  One member's problem never stops the scan:
a decline, a provider that cannot be reached and a mail server that refuses a
message are each recorded against that member and the walk carries on.

.. _renewals-providers:

The providers
=============

Each provider implements four methods on ``Provider``:

``start_mandate(mandate)``
   the parameters the browser needs to collect a method, and whatever handle the
   provider issues is stored on the mandate.
``confirm_mandate(mandate, **kwargs)``
   read the saved method back, verified with the provider, as a ``MandateMethod``.
``charge_mandate(mandate, payment)``
   charge off-session; raises ``PaymentDeclinedError`` carrying the provider's own
   wording when the method is refused.
``method_from_payment(payment)``
   the method a succeeded checkout saved, so a checkout that asked for automatic
   renewal activates its mandate without a second round trip.

**Stripe.**  A Stripe Customer is created for the mandate the first time one is
needed, and its id kept in ``customer_ref``.  A checkout with ``auto_renew`` is
created against that customer with ``setup_future_usage="off_session"``.  Turning
renewal on without paying uses a SetupIntent with ``usage="off_session"``, which
the Payment Element renders in ``setup`` mode.  A charge is a PaymentIntent with
``off_session: true`` and ``confirm: true``, keyed so a repeated attempt cannot
charge twice; a ``CardError`` and an intent that comes back needing
authentication are both declines, because nobody is present to authenticate.

**PayPal.**  A checkout with ``auto_renew`` carries
``payment_source.paypal.attributes.vault`` with ``store_in_vault: ON_SUCCESS``
and ``usage_type: MERCHANT``, and the captured order's
``payment_source.paypal.attributes.vault.id`` becomes the ``method_ref``.
Turning renewal on without paying creates a vault setup token, which the buttons
approve and which is exchanged for a payment token.  A charge is an Orders v2
create carrying ``payment_source.paypal.vault_id``, captured in the same call.
The label is the payer's masked email address, such as ``PayPal
(m***@example.org)``.

**Mock.**  Saves one test card instantly, ``Test card ending 4242, expires
12/2030``.  A mandate whose ``method_last4`` is ``0002`` is refused every time it
is charged with "Your card was declined", which is how the decline, the retries
and the pause are demonstrated and tested; the seed uses it for its paused
mandate.

.. _renewals-emails:

The emails
==========

All six are template pairs under ``backend/templates/emails/``, sent through
``caldart/mail.py``, and all link to ``SITE_URL`` and ``/portal/payments``:

=========================  ====================================================
Template                   When
=========================  ====================================================
``renewal_enabled``        A mandate becomes active.  States the plan, the
                           amount, the method and the next charge date.
``renewal_notice``         ``NOTICE_DAYS`` before a charge.  States the amount,
                           the date, the method and how to turn it off.  A charge
                           taken the day it is found is worded as happening
                           today.
``renewal_card_expiring``  The saved card expires before the next charge.
``renewal_charged``        A charge succeeded: the new expiry date, and the
                           receipt PDF attached.
``renewal_failed``         A charge was refused: the reason, and either when it
                           will be tried again or that it was the last try and
                           the reminders resume.  Also the message a member gets
                           when their membership had lapsed too long to catch up.
``renewal_canceled``       The member or an administrator turned it off.
=========================  ====================================================

Every one of them is worded by the mandate's kind.  A ``renewal`` mandate's
emails read as they always have; a ``both`` mandate says "renew your membership
and take your contribution" where the verb falls and "renewal and contribution"
where the noun does; a ``contribution`` mandate never says "renew" or "membership
renewal" at all -- "we will take your contribution on ...", "thank you for your
contribution", "automatic contribution is on".  The templates read ``kind`` and
``kind_label`` out of the shared context.

``renewal_enabled`` and ``renewal_charged`` each carry ``next_charge_on`` and say
``Your next charge will be on <date>``.  It is never blank: the date reporting a
charge is computed after the term has been extended, so it is the charge after
this one.

``renewal_base.html`` is the shared HTML shell, the same table-and-inline-styles
layout the reminders use.  A mail server that refuses a message is logged at
ERROR and leaves the attempt's timestamp unset, so the next scan tries again.

.. _renewals-and-reminders:

Automatic renewal and the reminders
===================================

A member whose membership renews itself is skipped by the renewal reminder scan
for every kind, with the reason ``auto_renew``: the renewal emails already tell
them what is happening to their membership, and a "your membership expires in 30
days" alongside "we will renew it on the 17th" would only confuse.

The skip applies to an ``active`` mandate, and to a ``pending`` one that already
has a scheduled charge.  A ``paused`` or ``canceled`` mandate covers nothing, so
the ordinary reminders resume the moment automatic renewal stops.
:doc:`reminders` lists every reason a candidate is skipped.

The renewals timer runs at 06:30 and the reminder timer at 07:00, so a membership
renewed by one scan is never also nagged about by the other on the same morning.

.. _renewals-operating:

Operating it
============

Run the scan by hand, rehearse it, or run it as of another date::

  caldart_manage run_auto_renewals
  caldart_manage run_auto_renewals --dry-run
  caldart_manage run_auto_renewals --today 2026-10-03 --dry-run

The command prints the counts and exits non-zero when any charge was refused, so
the systemd unit goes to ``failed`` rather than reporting a clean run that took
no money.  A system administrator can run the same scan from the portal's System
page, which calls ``POST /system/renewals/run``.

The timer is installed with the rest of the units; see :ref:`deploy-renewals`.
What went out is in the journal::

  journalctl -u caldart-renewals -n 50
  journalctl -u caldart-renewals | grep 'action=renewals.run'

.. _renewals-catch-up:

Catching up after downtime
==========================

While a mandate is ``active`` the ordinary renewal reminders are skipped for its
member, so the scan is the only thing standing between them and a silent lapse.
A scanner that was down over a charge date must therefore not simply skip the
member it missed.

For an ``active`` mandate whose member holds no term left to renew, the scan
looks for the most recent ``active`` or ``expired`` term that has already run
out.  A term with an attempt already against it is on the retry ladder and is
left alone.  Otherwise:

* **Within** ``CATCH_UP_DAYS`` of its ``ends_on``, the renewal is taken now: an
  attempt dated today is created, ``renewal_notice`` goes out worded for a charge
  that happens today, and the charge step of the same run takes it.  The term the
  charge buys starts on the day the money arrives, so the gap is left in the
  record rather than papered over.
* **Longer ago than that**, the lapse is too long for an unannounced charge.  The
  mandate is paused, nothing is charged, and ``renewal_failed`` tells the member
  that renewal was not taken because the membership had lapsed for more than a
  month, with a link to renew by hand.  The run counts the mandate under
  ``paused``, and the ordinary reminders resume for that member.

A dry run reports both outcomes without making either.

Members whose records were imported from CiviCRM with automatic renewal switched
on have no mandate here: the payment method was never handed to CalDART, and
there is nothing to charge.  They re-authorize from the portal's Payments screen,
and until they do the ordinary renewal reminders cover them.

Changing the cadence means changing the five constants in
``apps/payments/renewals.py`` and this page together.  A longer
``CHARGE_LEAD_DAYS`` charges further ahead of the term the member is paying for,
which is the thing the one-day lead exists to avoid.
