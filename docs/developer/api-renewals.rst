==================================================
API: automatic renewal and recurring donations
==================================================

Every endpoint behind a scheduled charge: the member's own automatic renewal
under ``/api/v1/me/renewal``, their recurring donation under
``/api/v1/me/donation``, the finance screens under ``/api/v1/admin/renewals``,
and the scan a system administrator can run by hand.
General API conventions -- session authentication, the CSRF header, pagination,
error shapes -- are in :doc:`api-reference`; the two worth repeating here are
that an unauthenticated request that reaches the permission check gets **401**,
and that money is always integer cents.

:doc:`renewals` is the subsystem chapter: what a mandate is, when the scan
charges, what each provider does and which emails go out.  Checkout itself,
including the ``auto_renew`` switch that creates a mandate while paying, is on
:doc:`api-payments`.

"Finance" below means a ``treasurer`` or an ``account_admin``; a
``system_admin`` passes every permission.


The mandate object
==================

Every endpoint that answers with a mandate answers with this shape.

.. code-block:: json

   {
     "id": 12,
     "user_id": 34,
     "user_name": "Maria Alvarez",
     "user_email": "maria@example.org",
     "plan": "annual",
     "plan_name": "Annual",
     "kind": "both",
     "cadence": "yearly",
     "contribution_cents": 2500,
     "amount_cents": 7000,
     "provider": "stripe",
     "method_label": "Visa ending 4242, expires 03/2028",
     "method_brand": "visa",
     "method_last4": "4242",
     "method_exp_month": 3,
     "method_exp_year": 2028,
     "status": "active",
     "failure_count": 0,
     "next_charge_on": "2027-03-14",
     "last_error": "",
     "last_charge_closed": false,
     "last_charged_at": "2026-03-14T18:22:05Z",
     "canceled_at": null,
     "created_at": "2025-03-14T18:21:58Z"
   }

``kind`` is ``renewal`` when the mandate names a plan without a contribution,
``both`` when it names a plan and a contribution, and ``contribution`` when it
doesn't name a plan at all -- a recurring donation, which doesn't renew anything
and gives the contribution on its own cadence.  ``plan`` and ``plan_name`` are ``null`` for
that kind.  ``cadence`` is ``monthly``, ``quarterly`` or ``yearly``; an automatic
renewal's is always ``yearly``.

``amount_cents`` is what the next charge comes to: the plan's price now, when
there is a plan, plus ``contribution_cents``.  ``status`` is ``pending``,
``active``, ``paused`` or ``canceled``.  ``next_charge_on`` is the day of the
waiting charge, and failing that the day stored on the mandate -- the day the
member chose -- or ``today`` when that has already gone by, because the next scan
is what takes a charge the scanner missed.  It is ``null`` only for a mandate that
is not active.  ``last_error`` carries the reason the most recent failed charge
failed, which is what a paused mandate shows the member.  ``last_charge_closed``
is true when that charge was one a treasurer closed as failed
(:ref:`renewals-in-doubt`), which was never refused: the member's own
``/me/renewal`` and ``/me/donation`` then read ``last_error`` as *The last charge
couldn't be completed.*, and the finance screens read what the attempt recorded.
The provider's own
references -- the Stripe customer and payment method, the PayPal vault id -- are
never sent to a browser.


A member's own renewal and donation
===================================

A person holds at most one automatic renewal and one recurring donation.
``/me/renewal`` and ``/me/donation`` are the same five endpoints over the two:
the same views and serializers, told which kind they serve.  What differs is
noted under each.

``GET /me/renewal`` and ``GET /me/donation``
--------------------------------------------

Any authenticated member or friend, their own mandate of that kind only.

.. code-block:: json

   {"mandate": null}

The envelope is what carries the null: a member who has never turned automatic
renewal on doesn't have a mandate, and a bare ``null`` body cannot be told from an
empty one.  ``mandate`` is otherwise the object above, whatever its status, so the
portal can show a paused mandate's reason and offer to turn a canceled one back
on.

Statuses: **200**; **401** when anonymous.

``POST /me/renewal/setup`` and ``POST /me/donation/setup``
----------------------------------------------------------

Any authenticated member or friend, under the ``payment_start`` rate that
``POST /payments/checkout`` shares (see :doc:`api-payments`).  Start saving a
payment method, without paying anything.

.. code-block:: json

   {"plan": "annual", "contribution_cents": 2500, "provider": "stripe",
    "next_charge_on": "2027-03-14"}

.. code-block:: json

   {"contribution_cents": 2500, "provider": "stripe", "cadence": "monthly",
    "next_charge_on": "2026-10-01", "remove_renewal_contribution": false}

Creates or resets the caller's ``pending`` mandate of that kind -- asking again
replaces whatever authority of that kind was there -- and then asks the provider
for what the browser needs.

For the renewal, ``plan`` must name a plan that has a duration, and the caller
must not be a life member; ``cadence`` may be left out, and anything but
``yearly`` is refused.  For the donation, ``plan`` is not read,
``contribution_cents`` must be above zero and at least ``DONATION_MINIMUM_CENTS``
(``500`` unless configured; see :doc:`configuration`), and ``cadence`` is ``monthly``,
``quarterly`` or ``yearly`` (the default).  ``remove_renewal_contribution`` is
read by the donation alone: see :ref:`renewals-one-contribution`.

``next_charge_on`` is the day of the first charge.  Leaving it out takes the day
the membership runs out for a renewal, and today for a donation.  A day before
today is refused; any later day is accepted, including one after the membership
runs out.

.. code-block:: json

   {"provider": "stripe", "client": {"client_secret": "seti_1ABC..._secret_xyz"}}

============  ===============================================
Provider      ``client``
============  ===============================================
``stripe``    ``{"client_secret": "<SetupIntent secret>"}``
``paypal``    ``{"setup_token": "<vault setup token>"}``
``mock``      ``{}``
============  ===============================================

Statuses: **200**; **400** naming ``plan`` for a slug no active plan carries,
naming ``next_charge_on`` for a day that has already gone by, naming ``cadence``
for a renewal on any cadence but ``yearly``, naming ``contribution_cents`` for a
renewal that takes a contribution while the caller holds a recurring donation and
for a donation under the minimum (``A donation must be at least $5.00.``),
naming ``auto_renew`` for a renewal without a plan or with one that never expires,
for a life member who names a plan, for a donation that doesn't give anything, and
for a provider that cannot charge a saved method, and naming ``detail`` when the
provider refuses to start; **400**
``{"detail": ..., "code": "renewal_contribution"}`` for a donation while the
caller's renewal takes a contribution and the body does not carry
``remove_renewal_contribution: true``; **401** when anonymous; **429** past the
caller's ``payment_start`` rate.  A 400 doesn't write anything: the caller's
mandates, and a renewal's contribution, stay as they were.

``POST /me/renewal/confirm`` and ``POST /me/donation/confirm``
--------------------------------------------------------------

Any authenticated member or friend, under the ``payment_confirm`` rate that the
payment confirms share (see :doc:`api-payments`).  Save the method the browser has
just collected and make the mandate of that kind active.

.. code-block:: json

   {"setup_intent_id": "seti_1ABC..."}

``setup_intent_id`` is Stripe's; ``setup_token`` is PayPal's; the mock provider
needs neither.  The answer is the mandate envelope, now ``active``, and the
caller is emailed that the authority is on.  A Stripe setup that sends the
browser to a bank returns to ``/portal/payments``, with ``mandate=donation`` in
the query string for a donation, and that card confirms it.

A Stripe SetupIntent that comes back ``requires_payment_method``, which is what a
declined card leaves, is canceled at Stripe as the confirm is refused, so its client
secret doesn't take another card; the portal calls this endpoint after every decline the
browser sees, then starts a fresh setup.  The ``setup_intent.setup_failed`` webhook
cancels a declined SetupIntent as well, and leaves the mandate as it is
(:doc:`payments-setup`).  Beginning a mandate again, at setup or at a checkout, and a
checkout that discards a pending mandate both cancel the SetupIntent the mandate
had open, so no SetupIntent CalDART has stopped tracking stays usable.

Statuses: **200**; **400** naming ``detail`` when the provider will not confirm
what it is given; **404** when the caller didn't start a setup of that kind; **401**
when anonymous; **429** past the caller's ``payment_confirm`` rate.

``PATCH /me/renewal`` and ``PATCH /me/donation``
------------------------------------------------

Any authenticated member or friend.  Change what the authority charges, how
often, and the day of the next charge.

.. code-block:: json

   {"plan": "annual", "contribution_cents": 5000, "next_charge_on": "2027-03-14"}

.. code-block:: json

   {"contribution_cents": 5000, "cadence": "quarterly", "next_charge_on": "2026-12-01"}

For the renewal, ``plan`` names the plan that renews from now on, and leaving it
out leaves the plan alone; ``cadence`` may only be ``yearly``.  For the donation,
``plan`` is not read, ``cadence`` changes how often it charges, and leaving it out
leaves it alone; its ``contribution_cents`` must be at least
``DONATION_MINIMUM_CENTS``, while a renewal's contribution, which rides on the dues,
takes any amount.  ``next_charge_on`` moves the next charge, and leaving it out leaves the stored day
alone; a charge already scheduled keeps its day, so a member who moves the date
inside the fourteen-day notice window is still charged on the day the waiting
charge was written for, which is the date the envelope answers.  The dues are not
settable: they are the plan's price at the time of each charge.  The answer is the
mandate envelope.

What the authority may become is the rule the setup endpoint applies, so a patch
that would leave a mandate without anything to charge again is refused.

Statuses: **200**; **400** naming ``contribution_cents`` for an amount outside
what a checkout would accept, for a donation under the minimum, and for a
contribution on a renewal while the
caller holds a recurring donation (``You already have a recurring donation.
Change it on the Donate screen.``), naming ``next_charge_on`` for a day that has
already gone by, naming ``plan`` for a slug no active plan carries, naming
``cadence`` for a renewal on any cadence but ``yearly``, and naming
``auto_renew`` when a life member names a plan, when a donation doesn't give
anything, and when the plan named never expires; **404** when the caller doesn't
have a mandate of that kind; **401** when anonymous.

``DELETE /me/renewal`` and ``DELETE /me/donation``
--------------------------------------------------

Any authenticated member or friend.  Turn that authority off.  The mandate
becomes ``canceled`` rather than being deleted, every charge still scheduled is
dropped, and the caller is emailed.  The other authority, if they hold one, is
untouched, and so is the membership, which runs to the end of its term.

Statuses: **204** with an empty body; **404** when the caller doesn't have a
mandate of that kind; **401** when anonymous.


The finance screens
===================

``GET /admin/renewals``
-----------------------

Finance.  Every mandate of both kinds, paginated, newest first.

``?status=`` narrows to ``pending``, ``active``, ``paused`` or ``canceled``;
``?kind=`` narrows to ``renewal``, ``both`` or ``contribution`` (the recurring
donations), the values each row's ``kind`` carries; ``?search=`` keeps a mandate when
every word of it appears in the member's email address, first name or last name, or in
the method label; ``?ordering=``
takes ``created_at``, ``status`` or ``last_charged_at``, and a leading ``-``
reverses.

.. code-block:: json

   {"count": 12, "next": null, "previous": null, "results": [{"id": 12, "...": "..."}]}

Each row is the mandate object above.  The same three filters download the list as the
``renewals`` report (:doc:`api-reports`).

Statuses: **200**; **400** naming ``status`` for a status outside the four, and
``kind`` for a kind outside the three (``Unknown kind '<value>'.``); **403** for
any role but finance; **401** when anonymous.

``GET /admin/renewals/{id}``
----------------------------

Finance.  One mandate, including ``last_error`` -- the reason its most recent
charge was refused, which is what a support call turns on.

Statuses: **200**; **404** for an unknown id; **403** for any role but finance;
**401** when anonymous.

``DELETE /admin/renewals/{id}``
-------------------------------

Finance.  Turn a member's automatic renewal or recurring donation off on their
behalf.  Every charge
still scheduled is dropped and the member is emailed.  The audit record names the
administrator and carries ``self_service=false``, so it is never mistaken for the
member's own decision.

Statuses: **204** with an empty body; **404** for an unknown id; **403** for any
role but finance; **401** when anonymous.

``GET /admin/renewals/attempts``
--------------------------------

Finance.  Every scheduled charge, paginated: the charges not yet tried first, latest
scheduled first, then every tried charge by ``attempted_at``, newest first.

.. code-block:: json

   {
     "id": 87,
     "mandate_id": 12,
     "mandate_kind": "renewal",
     "membership_id": 455,
     "payment_id": 901,
     "user_id": 34,
     "user_name": "Maria Alvarez",
     "scheduled_on": "2027-03-14",
     "outcome": "succeeded",
     "error": "",
     "noticed_at": "2027-02-28T06:30:11Z",
     "attempted_at": "2027-03-14T06:30:09Z",
     "in_doubt": false,
     "flagged_at": null,
     "payment_amount_cents": 4500,
     "payment_sent_at": "2027-03-14T06:30:08Z",
     "result_emailed_at": "2027-03-14T06:30:12Z",
     "created_at": "2027-02-28T06:30:11Z"
   }

``outcome`` is ``scheduled``, ``succeeded``, ``failed``, or ``skipped``.  ``in_doubt``
is true for a ``scheduled`` charge the provider may have taken and cannot say about:
the scan doesn't charge anything more for it until a treasurer settles it, and
``error`` says why.  ``mandate_kind`` is what the charge's mandate charges for:
``renewal``, ``both``, or ``contribution``, as ``kind`` is for a mandate.
``flagged_at`` is when the treasurer was last told the charge needs checking, and
``null`` until then (:ref:`renewals-in-doubt`).
``payment_amount_cents`` is what the attempt's payment comes to and
``payment_sent_at`` when its charge was first sent to the provider; both are ``null``
before there is a payment.
``membership_id`` is ``null`` for a recurring donation's charge, which doesn't renew
a term.  ``payment_id`` is ``null`` until the charge is made.  The three timestamps say
which emails have gone out; ``error`` carries the provider's message, written for the
member for a card decline (the finance screen names it by kind: *Card declined*, *PayPal
refused the saved payment method*, *Payment could not be verified*, or *Charge
refused*).

``?outcome=`` narrows to one outcome, ``?search=`` matches an email address, a
surname or the error text, and ``?ordering=`` takes ``scheduled_on`` or
``outcome``.

Statuses: **200**; **400** naming ``outcome`` for an outcome outside the four;
**403** for any role but finance; **401** when anonymous.

``POST /admin/renewals/attempts/{id}/settle``
---------------------------------------------

Finance.  Settle a charge held in doubt, from what the provider's own dashboard
shows.

.. code-block:: json

   {"outcome": "paid", "reference": "8MC585209K746392H"}

``outcome`` is one of three answers, and the attempt is locked while it is applied:

``paid``
   The charge was taken.  ``reference``, the provider's id for it (a PayPal capture
   id), is required, and is checked with PayPal -- the capture must be completed and
   carry this payment's ``custom_id`` or ``invoice_id``, amount, and currency.  The
   payment succeeds from it, with its order as ``provider_ref``, and the attempt is
   settled at once as the scan settles one: the term renewed, and the member
   emailed after the answer has gone.
``released``
   The provider didn't take anything: the hold is released and the next scan charges the
   same payment again, under the same ``invoice_id``.
``failed``
   Neither: the attempt is closed as failed, so it isn't charged, the payment is
   marked failed, and an active mandate is paused.  Its member is emailed
   ``renewal_failed`` after the answer has gone: the charge couldn't be completed,
   the renewal or donation is paused, and where to pay by hand and turn it back on
   (:ref:`renewals-in-doubt`).  A mandate that was not active is left as it is, and
   the member isn't emailed.

Each clears ``flagged_at`` and writes a ``renewal.settle`` audit record naming the
caller, with the attempt, the payment, the outcome, and any reference.  The answer
is the attempt as it stands afterwards, shaped as in the list above, with four
fields more, so the treasurer who closed a charge can get in touch with the member:

.. code-block:: json

   {"user_email": "maria@example.org", "user_phone": "415-555-0142",
    "mandate_paused": true, "member_emailed": true}

For ``failed``, ``user_email`` is the member's address and ``user_phone`` the phone
number on their profile, an empty string when they don't have one; for ``paid``
and ``released`` both are ``null``.  ``mandate_paused`` is true for ``failed`` when
the mandate stands paused afterwards, whoever paused it, and false otherwise.
``member_emailed`` is true when the answer hands the member an email to send once
it has gone (``paid``, and ``failed`` on an active mandate) and the member has an
address; it is false otherwise.  The two are independent: a member without an
address isn't emailed, and their renewal is still paused.

The payment is locked with the attempt.  Once it has gone through, ``released`` and
``failed`` are refused: **400** ``{"outcome": ["This charge's payment has already gone
through; record it as paid instead."]}``.

Statuses: **200**; **400** keyed by ``outcome`` for any other answer, and for
``released`` or ``failed`` once the payment has gone through; **400** keyed by
``reference`` for ``paid`` without one; **400**
``{"attempt": ["This charge is not waiting to be checked."]}`` for an attempt that is
not in doubt; **400** keyed by ``reference`` for a reference on a charge that is not
PayPal's; **400** naming ``detail`` when PayPal will not confirm the reference or
cannot be reached; **404** for an unknown attempt; **403** for any role but finance;
**401** when anonymous.


Running the scan
================

``POST /system/renewals/run``
-----------------------------

``system_admin`` only.  Run the automatic-renewal scan now, rather than waiting
for the daily timer.

.. code-block:: json

   {"dry_run": true}

``dry_run`` defaults to ``false``.  A dry run never changes a mandate, emails
anybody, or charges anybody; it runs inside the request and answers 200 with the
counts the same scan would produce; the rehearsal itself is recorded in the audit log.

.. code-block:: json

   {"noticed": 2, "warned": 0, "charged": 1, "failed": 0, "paused": 0, "skipped": 3}

``noticed`` counts the advance warnings, ``warned`` the card-expiry warnings,
``charged`` the renewals and donations taken, ``failed`` the charges refused, ``paused`` the
mandates whose retries ran out on this run, and ``skipped`` the mandates and
attempts that didn't need anything doing, or whose charge was put off.  Every run writes
one ``renewals.run`` audit record naming the caller.

A live run charges cards, and each charge waits on the provider, so it does not
run inside the request: the server writes a ``RenewalScan`` row, starts the scan
in its own process, and answers 202 with the row, unfinished
(:ref:`renewals-run-now`).

.. code-block:: json

   {"id": 7, "started_at": "2026-10-14T13:31:00Z", "finished_at": null,
    "ok": false, "error": "", "result": null}

While another live scan started here is unfinished and younger than
``RENEWAL_STALE_MINUTES`` a live run is refused with **409** ``{"detail": "An
automatic renewal run is already under way."}`` and a WARNING ``renewals.run`` audit
record with the reason ``run_in_progress``; an unfinished row older than that is
closed as ``Did not finish.`` and does not block.

Statuses: **200** for a dry run; **202** for a live run; **409** while a live run is
under way; **400** when ``dry_run`` is not a boolean; **403** for any role but
``system_admin``; **401** when anonymous.

``GET /system/renewals/runs/{id}``
----------------------------------

``system_admin`` only.  How the live scan ``id`` is getting on.  ``finished_at`` is
``null`` while it runs.  When it ends, ``ok`` says whether it ran to its end and
``result`` carries its counts and ``actions``, shaped exactly as a dry run's answer;
``error`` says why one did not, and ``result`` stays ``null``.  A scan still
unfinished ``RENEWAL_STALE_MINUTES`` after it started has lost its process, and is
closed by this read with the error ``Did not finish.``

.. code-block:: json

   {"id": 7, "started_at": "2026-10-14T13:31:00Z",
    "finished_at": "2026-10-14T13:31:40Z", "ok": true, "error": "",
    "result": {"noticed": 0, "warned": 0, "charged": 2, "failed": 0, "paused": 0,
               "skipped": 0, "actions": []}}

Statuses: **200**; **404** ``{"detail": "No such renewal run."}`` for an id no
scan has; **403** for any role but ``system_admin``; **401** when anonymous.


Role summary
============

=============================================  ================================
Endpoint                                       Who
=============================================  ================================
``GET | PATCH | DELETE /me/renewal``           the member themselves
``POST /me/renewal/setup``                     the member themselves
``POST /me/renewal/confirm``                   the member themselves
``GET | PATCH | DELETE /me/donation``          the member or friend themselves
``POST /me/donation/setup``                    the member or friend themselves
``POST /me/donation/confirm``                  the member or friend themselves
``GET /admin/renewals``                        ``treasurer``, ``account_admin``
``GET /admin/renewals/{id}``                   ``treasurer``, ``account_admin``
``DELETE /admin/renewals/{id}``                ``treasurer``, ``account_admin``
``GET /admin/renewals/attempts``               ``treasurer``, ``account_admin``
``POST /admin/renewals/attempts/{id}/settle``  ``treasurer``, ``account_admin``
``POST /system/renewals/run``                  ``system_admin``
``GET /system/renewals/runs/{id}``             ``system_admin``
=============================================  ================================
