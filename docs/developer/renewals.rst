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
provider's handles on the saved method, the label the member reads, and a status:

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

.. _renewals-schedule:

The schedule
============

Four constants in ``apps/payments/renewals.py`` set the cadence:

====================================  =========  =============================
Constant                              Value      Meaning
====================================  =========  =============================
``CHARGE_LEAD_DAYS``                  3          Days before a term's ``ends_on``
                                                 that its renewal is charged.
``NOTICE_DAYS``                       14         Days before that charge that the
                                                 advance warning goes out.
``RETRY_OFFSETS``                     (1, 3, 7)  Days after a failed charge that
                                                 each retry is scheduled for.
``CARD_EXPIRY_WARNING_DAYS``          30         How close to a card's expiry the
                                                 member is warned it will not last.
====================================  =========  =============================

The lead exists so a decline has room: a charge three days out that fails is
retried the next day, and again three days later, before coverage lapses.  When
all three retries are refused the mandate is paused, the member is told automatic
renewal is off, and the reminders take over.

.. _renewals-scanner:

The scan
========

``run_auto_renewals(*, today, dry_run, actor)`` is the one entry point.  The
management command, ``POST /system/renewals/run`` and the systemd timer all call
it, and it does three things in order.

1. **Notice.**  For every ``active`` mandate, find the member's active term that
   runs furthest into the future.  If its charge date -- ``ends_on`` less
   ``CHARGE_LEAD_DAYS`` -- is within ``NOTICE_DAYS``, and no attempt exists for
   that term yet, create a ``scheduled`` attempt for that date and send
   ``renewal_notice``.  A member holding a lifetime term has no term to renew and
   is skipped as ``no_term``.

2. **Card expiry.**  If the saved card expires before the next charge, and its
   expiry is within ``CARD_EXPIRY_WARNING_DAYS``, send ``renewal_card_expiring``.
   The expiry the warning was sent for is recorded on the mandate, so the warning
   goes out once rather than every morning.

3. **Charge.**  For every ``scheduled`` attempt due today or earlier: create the
   payment from the plan's current price plus the mandate's contribution, then
   ask the provider to charge the saved method off-session.

   On success the payment goes through the same ``mark_succeeded`` path as a
   checkout, so the next term is activated starting the day after the current one
   ends; the mandate's failure count is cleared, the attempt is ``succeeded`` and
   ``renewal_charged`` goes out.

   On a decline the payment is marked failed, the provider's reason is stored on
   the attempt, the failure count rises, and ``renewal_failed`` goes out naming
   either the day of the next try or that it was the last.  A mandate with
   retries left gets the next attempt from ``RETRY_OFFSETS``; one whose retries
   are exhausted is paused.

   An attempt whose mandate is no longer active, and one whose member has renewed
   by some other means in the meantime, is closed as ``skipped`` and charges
   nothing.

The run returns a summary -- ``noticed``, ``warned``, ``charged``, ``failed``,
``paused``, ``skipped`` -- and writes one ``renewals.run`` audit record.  A dry
run writes nothing, emails nobody and charges nobody; it reports the counts the
same scan would produce.

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
                           the date, the method and how to turn it off.
``renewal_card_expiring``  The saved card expires before the next charge.
``renewal_charged``        A charge succeeded, with the new expiry date.
``renewal_failed``         A charge was refused: the reason, and either when it
                           will be tried again or that it was the last try and
                           the reminders resume.
``renewal_canceled``       The member or an administrator turned it off.
=========================  ====================================================

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

Members whose records were imported from CiviCRM with automatic renewal switched
on have no mandate here: the payment method was never handed to CalDART, and
there is nothing to charge.  They re-authorize from the portal's Payments screen,
and until they do the ordinary renewal reminders cover them.

Changing the cadence means changing the four constants in
``apps/payments/renewals.py`` and this page together.  A shorter
``CHARGE_LEAD_DAYS`` leaves less room for a retry before coverage lapses; a
longer one charges further ahead of the term the member is paying for.
