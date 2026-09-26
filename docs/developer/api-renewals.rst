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
     "last_charged_at": "2026-03-14T18:22:05Z",
     "canceled_at": null,
     "created_at": "2025-03-14T18:21:58Z"
   }

``kind`` is ``renewal`` when the mandate names a plan and no contribution,
``both`` when it names a plan and a contribution, and ``contribution`` when it
names no plan at all -- a recurring donation, which renews nothing and gives the
contribution on its own cadence.  ``plan`` and ``plan_name`` are ``null`` for
that kind.  ``cadence`` is ``monthly``, ``quarterly`` or ``yearly``; an automatic
renewal's is always ``yearly``.

``amount_cents`` is what the next charge comes to: the plan's price now, when
there is a plan, plus ``contribution_cents``.  ``status`` is ``pending``,
``active``, ``paused`` or ``canceled``.  ``next_charge_on`` is the day of the
waiting charge, and failing that the day stored on the mandate -- the day the
member chose -- or ``today`` when that has already gone by, because the next scan
is what takes a charge the scanner missed.  It is ``null`` only for a mandate that
is not active.  ``last_error`` carries the reason the most recent charge was
refused, which is what a paused mandate shows the member.  The provider's own
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
renewal on has no mandate, and a bare ``null`` body cannot be told from an empty
one.  ``mandate`` is otherwise the object above, whatever its status, so the
portal can show a paused mandate's reason and offer to turn a canceled one back
on.

Statuses: **200**; **401** when anonymous.

``POST /me/renewal/setup`` and ``POST /me/donation/setup``
----------------------------------------------------------

Any authenticated member or friend.  Start saving a payment method, without
paying anything.

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
``contribution_cents`` must be above zero, and ``cadence`` is ``monthly``,
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
renewal that takes a contribution while the caller holds a recurring donation,
naming ``auto_renew`` for a renewal with no plan or with one that never expires,
for a life member who names a plan, for a donation of nothing, and for a provider
that cannot charge a saved method, and naming ``detail`` when the provider refuses
to start; **400** ``{"detail": ..., "code": "renewal_contribution"}`` for a
donation while the caller's renewal takes a contribution and the body does not
carry ``remove_renewal_contribution: true``; **401** when anonymous.  A 400
writes nothing: the caller's mandates, and a renewal's contribution, stay as they
were.

``POST /me/renewal/confirm`` and ``POST /me/donation/confirm``
--------------------------------------------------------------

Any authenticated member or friend.  Save the method the browser has just
collected and make the mandate of that kind active.

.. code-block:: json

   {"setup_intent_id": "seti_1ABC..."}

``setup_intent_id`` is Stripe's; ``setup_token`` is PayPal's; the mock provider
needs neither.  The answer is the mandate envelope, now ``active``, and the
caller is emailed that the authority is on.  A Stripe setup that sends the
browser to a bank returns to ``/portal/payments``, with ``mandate=donation`` in
the query string for a donation, and that card confirms it.

Statuses: **200**; **400** naming ``detail`` when the provider will not confirm
what it is given; **404** when the caller started no setup of that kind; **401**
when anonymous.

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
``plan`` is not read, and ``cadence`` changes how often it charges; leaving it out
leaves it alone.  ``next_charge_on`` moves the next charge, and leaving it out leaves the stored day
alone; a charge already scheduled keeps its day, so a member who moves the date
inside the fourteen-day notice window is still charged on the day the waiting
charge was written for, which is the date the envelope answers.  The dues are not
settable: they are the plan's price at the time of each charge.  The answer is the
mandate envelope.

What the authority may become is the rule the setup endpoint applies, so a patch
that would leave a mandate nothing to charge again is refused.

Statuses: **200**; **400** naming ``contribution_cents`` for an amount outside
what a checkout would accept, and for a contribution on a renewal while the
caller holds a recurring donation (``You already have a recurring donation.
Change it on the Donate screen.``), naming ``next_charge_on`` for a day that has
already gone by, naming ``plan`` for a slug no active plan carries, naming
``cadence`` for a renewal on any cadence but ``yearly``, and naming
``auto_renew`` when a life member names a plan, when a donation gives nothing,
and when the plan named never expires; **404** when the caller has no mandate of
that kind; **401** when anonymous.

``DELETE /me/renewal`` and ``DELETE /me/donation``
--------------------------------------------------

Any authenticated member or friend.  Turn that authority off.  The mandate
becomes ``canceled`` rather than being deleted, every charge still scheduled is
dropped, and the caller is emailed.  The other authority, if they hold one, is
untouched, and so is the membership, which runs to the end of its term.

Statuses: **204** with an empty body; **404** when the caller has no mandate of
that kind; **401** when anonymous.


The finance screens
===================

``GET /admin/renewals``
-----------------------

Finance.  Every mandate of both kinds, paginated, newest first.

``?status=`` narrows to ``pending``, ``active``, ``paused`` or ``canceled``;
``?kind=`` narrows to ``renewal``, ``both`` or ``contribution`` (the recurring
donations), the values each row's ``kind`` carries; ``?search=`` matches a name, an email address or the method label; ``?ordering=``
takes ``created_at``, ``status`` or ``last_charged_at``, and a leading ``-``
reverses.

.. code-block:: json

   {"count": 12, "next": null, "previous": null, "results": [{"id": 12, "...": "..."}]}

Each row is the mandate object above.

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

Finance.  Every scheduled charge, paginated, latest first.

.. code-block:: json

   {
     "id": 87,
     "mandate_id": 12,
     "membership_id": 455,
     "payment_id": 901,
     "user_id": 34,
     "user_name": "Maria Alvarez",
     "scheduled_on": "2027-03-14",
     "outcome": "succeeded",
     "error": "",
     "noticed_at": "2027-02-28T06:30:11Z",
     "attempted_at": "2027-03-14T06:30:09Z",
     "result_emailed_at": "2027-03-14T06:30:12Z",
     "created_at": "2027-02-28T06:30:11Z"
   }

``outcome`` is ``scheduled``, ``succeeded``, ``failed`` or ``skipped``.
``membership_id`` is ``null`` for a recurring donation's charge, which renews no
term.  ``payment_id`` is ``null`` until the charge is made.  The three timestamps say
which emails have gone out; ``error`` carries the provider's decline reason.

``?outcome=`` narrows to one outcome, ``?search=`` matches an email address, a
surname or the error text, and ``?ordering=`` takes ``scheduled_on`` or
``outcome``.

Statuses: **200**; **400** naming ``outcome`` for an outcome outside the four;
**403** for any role but finance; **401** when anonymous.


Running the scan
================

``POST /system/renewals/run``
-----------------------------

``system_admin`` only.  Run the automatic-renewal scan now, rather than waiting
for the daily timer.

.. code-block:: json

   {"dry_run": true}

``dry_run`` defaults to ``false``.  A dry run changes no mandate, emails nobody
and charges nobody, and reports the counts the same scan would produce; the
rehearsal itself is recorded in the audit log.

.. code-block:: json

   {"noticed": 2, "warned": 0, "charged": 1, "failed": 0, "paused": 0, "skipped": 3}

``noticed`` counts the advance warnings, ``warned`` the card-expiry warnings,
``charged`` the renewals and donations taken, ``failed`` the charges refused, ``paused`` the
mandates whose retries ran out on this run, and ``skipped`` the mandates and
attempts that needed nothing doing.  Every run writes one ``renewals.run`` audit
record naming the caller.

Statuses: **200**; **403** for any role but ``system_admin``; **401** when
anonymous.


Role summary
============

======================================  ==========================================
Endpoint                                Who
======================================  ==========================================
``GET | PATCH | DELETE /me/renewal``    the member themselves
``POST /me/renewal/setup``              the member themselves
``POST /me/renewal/confirm``            the member themselves
``GET | PATCH | DELETE /me/donation``   the member or friend themselves
``POST /me/donation/setup``             the member or friend themselves
``POST /me/donation/confirm``           the member or friend themselves
``GET /admin/renewals``                 ``treasurer``, ``account_admin``
``GET /admin/renewals/{id}``            ``treasurer``, ``account_admin``
``DELETE /admin/renewals/{id}``         ``treasurer``, ``account_admin``
``GET /admin/renewals/attempts``        ``treasurer``, ``account_admin``
``POST /system/renewals/run``           ``system_admin``
======================================  ==========================================
