============================================
Automatic renewal and recurring donations
============================================

A member can ask CalDART to renew their membership for them: the payment method
they used is saved with the provider, and a daily scan charges it on the day the
member chose, which is normally the day the term runs out.  Any member or friend
can also give on a schedule -- monthly, quarterly, or yearly -- through the same
machinery: a recurring donation.  This page covers the mandate that either
authority is held in, the scan that acts on it, the emails it sends, how it
interacts with the renewal reminders, and how to operate it.
:doc:`api-renewals` is the endpoint reference, and :doc:`/user/payments` is what
the member and the treasurer see.

.. _renewals-mechanism:

The mechanism
=============

The schedule lives here, not at the provider.  There is no Stripe subscription
and no PayPal billing plan: CalDART saves a payment method, keeps its own record
of what to charge and when, and confirms an ordinary payment off-session when
the day comes.  That keeps the plan, the price, the term arithmetic, the
reminder logic and the receipts in one place, and it means changing a plan's
price changes what renews without touching either provider.

A **mandate** (``RenewalMandate``) is one person's standing authority.  It
carries the plan it renews, the contribution, the ``cadence``, the day of the next
charge, the provider, the provider's handles on the saved method, the label the
person reads, and a status.  It comes in two kinds, told apart by its plan:

* an **automatic renewal** names a plan, renews the membership once a year, and
  carries the contribution taken beside the dues.  Its ``cadence`` is always
  ``yearly``.
* a **recurring donation** names no plan.  It gives ``contribution_cents`` alone,
  ``monthly``, ``quarterly`` or ``yearly``, and accompanies no membership: a
  member, a life member and a friend may each hold one.

``RenewalMandate.user`` is a foreign key (``related_name="renewal_mandates"``)
held to one of each kind by two conditional unique constraints:
``renewal_mandate_one_plan_per_user`` over the mandates with a plan and
``renewal_mandate_one_donation_per_user`` over those without.  The statuses
are:

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
mandate, the membership term whose expiry it renews (null for a recurring
donation, which renews nothing), the day it is due, the
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
``contribution``     names no plan at all: a recurring donation.  It gives the
                     contribution alone on its own cadence, whatever the giver's
                     membership.
===================  ==========================================================

``mandate_kind(mandate)`` answers the kind and ``kind_label(kind)`` the words for
it in running prose -- ``automatic renewal``, ``automatic renewal and
contribution``, ``recurring donation``.  A recurring donation never says "renew"
or "membership renewal" to the person giving it.

``check_renewable(plan, provider, *, user, contribution_cents)`` is the rule both
kinds are held to.  A recurring donation needs only an amount: one of nothing is
refused with ``A recurring donation needs an amount to give.``  An automatic
renewal needs a plan with a duration, and a life member may not hold one:
``A life member's membership does not renew; choose a contribution instead.``
All three are a 400 keyed by ``auto_renew``, and guard setup, the change
endpoints and a checkout's ``auto_renew`` alike.  A checkout that tries to sell a
life member a term is refused separately, keyed by ``plan``.

.. _renewals-one-contribution:

One contribution, one place
---------------------------

A renewal's contribution and a recurring donation are the same thing -- a gift on
a schedule -- so a person holds one or the other.  Asking for a recurring donation
(``POST /me/donation/setup``, or a checkout with ``auto_renew`` and no plan) while
the renewal, in any state but ``canceled``, takes a contribution is refused with
``400 {"detail": "Your automatic renewal already includes a contribution of $X a
year. Set up a recurring donation and that contribution comes off the renewal;
your dues still renew automatically.", "code": "renewal_contribution"}``.  The
same request with ``remove_renewal_contribution: true`` sets the renewal's
contribution to nothing first and records ``renewal.change`` in the audit log,
in the same transaction as the donation's start, so a provider that refuses to
start leaves the contribution on the renewal; the portal sends it when the
person presses **Continue**.  The other way round, a
contribution on a renewal (``PATCH /me/renewal``, ``POST /me/renewal/setup``, or a
checkout for a plan) while a recurring donation is held, in any state but
``canceled``, is refused with ``You already have a recurring donation. Change it
on the Donate screen.``, keyed by ``contribution_cents``.

.. _renewals-friend-switch:

When a member becomes a friend
------------------------------

A friend has no dues to renew, so ``switch_to_friend(user, *,
keep_contribution)`` ends the automatic renewal in the same transaction that sets
the kind (``POST /me/kind/friend``, :ref:`api-kind-switch`): a live renewal is
canceled through ``cancel_mandate`` under the member's name and a pending one is
deleted.  When the live renewal takes a contribution the member must say what
becomes of it.  ``keep_contribution`` true calls
``keep_renewal_contribution(renewal)`` after the cancellation: a recurring
donation of the same amount, yearly, on the renewal's provider, customer and
saved method, first charged on the renewal's ``next_charge_on`` (or today when that
has passed), begun with ``begin_mandate`` and made active with ``save_method``.
The renewal is canceled first, so the one-contribution rule above has nothing to
refuse.  A recurring donation already ``active`` or ``paused`` is left alone.
Undoing the change (``DELETE /me/kind/friend``) restores no mandate.  A friend who
still holds a renewal, which an administrator's change of kind can leave behind, is
skipped by the scan with the reason ``friend``.

.. _renewals-next-charge:

The day of the charge is the member's
=====================================

A mandate stores ``next_charge_on``, and every mandate has one.  It is the day the
member chose to be charged on.  A renewal's defaults to ``default_charge_date(user,
today)``:

* the ``ends_on`` of the member's current dated term, so the renewal falls on the
  day the membership runs out and the coverage carries straight on;
* today for a member who holds none, since there is no later day to wait for.

A recurring donation set up with no day of its own starts today.

A mandate begun at a checkout that named no day of its own is dated again when
that payment succeeds.  A renewal's is dated from the term the payment buys, so
the first automatic charge falls on the expiry of the term just bought rather than
of the one the member held while paying.  A recurring donation's payment is its
first gift, so the next one falls ``advance_by_cadence(today, cadence)``; a day
the giver chose that is not after today moves on the same way, since the payment
already covers it.

``POST /me/renewal/setup``, ``POST /me/donation/setup``, both ``PATCH`` endpoints
and ``POST /payments/checkout`` each take an optional ``next_charge_on``.  A day before today is refused with
``The next charge cannot be in the past.``, keyed by ``next_charge_on``.  Any
later day is allowed, including one after the membership runs out, in which case
the membership lapses until the charge comes round and the advance notice says so.
Moving the stored day does not move a charge already scheduled: the waiting attempt
keeps the day it was written for, which is the day ``charge_date`` answers until it
is taken.

``charge_date(mandate, today)`` is what the screens and the emails read.  It is
``None`` only for a mandate that is not ``active``; for one that is it answers the
earliest ``scheduled`` attempt's own date when a charge is waiting, and otherwise
the stored ``next_charge_on``, or ``today`` when that has already gone by --
because the next scan is what takes a charge the scanner missed.

A successful charge rolls the stored day forward: to the ``ends_on`` of the term
the charge bought for a renewal, and to ``advance_by_cadence(scheduled_on,
cadence)`` for a recurring donation, which renews no term.
``advance_by_cadence(day, cadence)`` adds one month for ``monthly``, three for
``quarterly`` and twelve for ``yearly``, clamping to the last day of a shorter
month: 31 January 2026 monthly becomes 28 February 2026, and 29 February 2028
yearly becomes 28 February 2029.  A refused charge leaves the stored day alone:
the retry lives on the attempt.

A term bought outside the scan rolls the stored day forward as well.  When a
payment extends the coverage the stored day was aimed at, the day moves on by the
same span, so a day stored on the expiry becomes the new expiry and a day the
member placed a fortnight early stays a fortnight early; a day already behind
becomes the new expiry itself.  Without that a member who renews by hand a month
before their expiry would be charged a second year on the day they had already
covered.  A charge already scheduled when the coverage arrived is skipped as
``already_renewed``, and rolls the stored day forward the same way.

So an active mandate always has a date to show, on the member's payments screen,
on the finance screens and in the emails that report a charge.

.. _renewals-schedule:

The schedule
============

Four constants in ``apps/payments/renewals.py`` set the timing around the day
the member chose:

====================================  =========  =============================
Constant                              Value      Meaning
====================================  =========  =============================
``NOTICE_DAYS``                       14         Days before a yearly charge that
                                                 the advance warning goes out.
``RETRY_OFFSETS``                     (1, 3, 7)  Days after a failed charge that
                                                 each retry is scheduled for.
``CARD_EXPIRY_WARNING_DAYS``          30         How close to a card's expiry the
                                                 member is warned it will not last.
``CATCH_UP_DAYS``                     30         How long after the stored charge
                                                 date a scan may still take it.
====================================  =========  =============================

A default charge falls on the term's ``ends_on``, which that term still covers, so
a member is never charged for the coming year while a whole year of coverage
remains.  A decline is retried after the term has run out -- the next day, three
days later, and a week after that -- and the term a late charge buys starts on the
day the money arrives, not on the old expiry, so the days nobody was covered stay
visible in the record.  When all three retries are refused the mandate is paused,
the member is told automatic renewal is off, and the reminders take over.

.. _renewals-scanner:

The scan
========

``run_auto_renewals(*, today, dry_run, actor)`` is the one entry point.  The
management command, ``POST /system/renewals/run`` and the systemd timer all call
it, and it does three things in order.

1. **Notice.**  For every ``active`` mandate, find the member's active term that
   runs furthest into the future.  If ``charge_date`` is within ``NOTICE_DAYS``,
   create a ``scheduled`` attempt for that day and send ``renewal_notice``.  A
   renewal whose member's effective kind is ``friend`` is skipped as ``friend``: a
   friend pays no dues.  One whose member has since been granted a lifetime term
   has no expiry left to renew and is skipped as ``lifetime``.

   A recurring donation charges whatever its giver's membership, and its attempt
   names no term.  A yearly one is treated like a renewal: the notice goes out
   ``NOTICE_DAYS`` before the stored day and schedules the attempt.  A monthly or
   quarterly one sends no notice: its attempt is written on the day of the charge
   (or the first scan after it), and the charge step of the same run takes it, so
   the charged email is the one message per charge.

   A mandate carries one charge at a time, so an attempt still ``scheduled`` --
   against this term or against the one before it, which is what a member who
   renewed by hand leaves behind -- is the charge the run announces rather than a
   reason to write another.  Beyond that only an attempt that has already
   ``succeeded`` against this very term stands in the way, so a mandate that was
   paused over a term and then turned back on is scheduled again rather than left
   to lapse.  An attempt that is waiting but whose notice the mail server refused
   is written to again on the next run.

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
   and moves on.  Nor can the two write the same charge twice: a mandate holds
   one ``scheduled`` attempt at a time (``renewal_attempt_one_scheduled_per_mandate``),
   so of two scans that both find none waiting, the one whose write is refused
   leaves the charge and its notice to the other.

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

   An attempt whose mandate is no longer active is closed as ``skipped`` and
   charges nothing, and so is a renewal's attempt whose member has become a friend
   (``friend``), been granted a lifetime term (``lifetime``), or renewed by some
   other means in the meantime (``already_renewed``).  A recurring donation's
   charge extends no term, creates a payment with no plan, and is skipped for none
   of those; it is skipped as ``already_charged`` when the mandate's next charge,
   read afresh, already lies beyond the day the attempt was for.  The retry ladder
   and the pause apply to it unchanged.

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
mandate.  The succeeding card seeds the three mandates the daily scan always
has work on -- two due for an ordinary renewal today, and one due for a catch-up
renewal -- and the two recurring donations: the account administrator's yearly
one, a month out, and one generated member's monthly one, nine days out.

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
``renewal_notice``         ``NOTICE_DAYS`` before a yearly charge.  States the
                           amount, the date, the method and how to turn it off.
                           A charge taken the day it is found is worded as
                           happening today.  A monthly or quarterly donation gets
                           none.
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
emails speak of renewing the membership; a ``both`` mandate says "renew your
membership and take your contribution" where the verb falls and "automatic
renewal and contribution" where the noun does; a ``contribution`` mandate, a
recurring donation, never says "renew" or "membership renewal" at all -- "we will
take your recurring donation on ...", "thank you for your recurring donation",
"your recurring donation is on" -- and says how often it charges ("each month")
where the amount is named.  The templates read ``kind``, ``kind_label``,
``cadence`` and ``cadence_label`` out of the shared context.

``renewal_enabled`` and ``renewal_charged`` each carry the charge date and say
``Your next charge will be on <date>``.  It is never blank: the date reporting a
charge is read after the stored day has been rolled forward, so it is the charge
after this one.

``renewal_base.html`` is the shared HTML shell, the same table-and-inline-styles
layout the reminders use.  A mail server that refuses a message is logged at
ERROR and leaves the attempt's timestamp unset, so the next scan tries again.

.. _renewals-and-reminders:

Automatic renewal and the reminders
===================================

A member whose membership renews itself is skipped by the renewal reminder scan
for every kind, with the reason ``auto_renew``.  Only a renewal counts -- a
recurring donation renews nothing, so it never silences a reminder: the renewal emails already tell
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
left alone.  Otherwise the stored ``next_charge_on`` decides:

* **Missed by no more than** ``CATCH_UP_DAYS``, the charge is taken now: an
  attempt dated today is created, ``renewal_notice`` goes out worded for a charge
  that happens today, and the charge step of the same run takes it.  The term the
  charge buys starts on the day the money arrives, so the gap is left in the
  record rather than papered over.
* **Missed by longer than that**, the lapse is too long for an unannounced charge.
  The mandate is paused, nothing is charged, and ``renewal_failed`` tells the
  member that renewal was not taken because the membership had lapsed for more
  than a month, with a link to renew by hand.  The run counts the mandate under
  ``paused``, and the ordinary reminders resume for that member.
* **Still to come**, because the member chose a day beyond their expiry, nothing
  happens until it is within ``NOTICE_DAYS``; the membership lapses in the
  meantime and the notice then goes out as usual.

A dry run reports both outcomes without making either.

The demo seed leaves both paths ready to exercise the day it runs: two
generated members have a term ending today with an ordinary renewal already
due, and one more has a term that lapsed ten days ago with no attempt against
it yet, so ``run_auto_renewals`` takes the catch-up path for that member and
charges all three.

Members whose records were imported from CiviCRM with automatic renewal switched
on have no mandate here: the payment method was never handed to CalDART, and
there is nothing to charge.  They re-authorize from the portal's Payments screen,
and until they do the ordinary renewal reminders cover them.

Changing the timing means changing the four constants in
``apps/payments/renewals.py`` and this page together; the months each cadence
adds are ``CADENCE_MONTHS`` beside them.  The day of the charge
itself is not a constant: it is stored on the mandate, and the member owns it.
