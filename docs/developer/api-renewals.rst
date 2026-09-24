======================
API: automatic renewal
======================

Every endpoint behind a membership that renews itself: the member's own standing
authority under ``/api/v1/me/renewal``, the finance screens under
``/api/v1/admin/renewals``, and the scan a system administrator can run by hand.
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

``amount_cents`` is what the next charge comes to: the plan's price now plus
``contribution_cents``.  ``status`` is ``pending``, ``active``, ``paused`` or
``canceled``.  ``next_charge_on`` is the day of the waiting charge, or the charge
date computed from the member's current term -- the day before it ends -- and is
``null`` for a mandate that is not active and for a member with no term that
needs renewing.  ``last_error``
carries the reason the most recent charge was refused, which is what a paused
mandate shows the member.  The provider's own references -- the Stripe customer
and payment method, the PayPal vault id -- are never sent to a browser.


A member's own renewal
======================

``GET /me/renewal``
-------------------

Any authenticated member, their own mandate only.

.. code-block:: json

   {"mandate": null}

The envelope is what carries the null: a member who has never turned automatic
renewal on has no mandate, and a bare ``null`` body cannot be told from an empty
one.  ``mandate`` is otherwise the object above, whatever its status, so the
portal can show a paused mandate's reason and offer to turn a canceled one back
on.

Statuses: **200**; **401** when anonymous.

``POST /me/renewal/setup``
--------------------------

Any authenticated member.  Start saving a payment method, without paying
anything.

.. code-block:: json

   {"plan": "annual", "contribution_cents": 2500, "provider": "stripe"}

Creates or resets the caller's ``pending`` mandate over that plan, contribution
and provider -- turning automatic renewal on again replaces whatever authority
was there -- and then asks the provider for what the browser needs.

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
naming ``auto_renew`` for a plan that never expires or a provider that cannot
charge a saved method, and naming ``detail`` when the provider refuses to start;
**401** when anonymous.

``POST /me/renewal/confirm``
----------------------------

Any authenticated member.  Save the method the browser has just collected and
make the mandate active.

.. code-block:: json

   {"setup_intent_id": "seti_1ABC..."}

``setup_intent_id`` is Stripe's; ``setup_token`` is PayPal's; the mock provider
needs neither.  The answer is the mandate envelope, now ``active``, and the
member is emailed that automatic renewal is on.

Statuses: **200**; **400** naming ``detail`` when the provider will not confirm
what it is given; **404** when the caller started no setup; **401** when
anonymous.

``PATCH /me/renewal``
---------------------

Any authenticated member.  Change the contribution renewed alongside the dues.

.. code-block:: json

   {"contribution_cents": 5000}

The dues are not settable: they are the plan's price at the time of each charge.
The answer is the mandate envelope.

Statuses: **200**; **400** naming ``contribution_cents`` for an amount outside
what a checkout would accept; **404** when the caller has no mandate; **401**
when anonymous.

``DELETE /me/renewal``
----------------------

Any authenticated member.  Turn automatic renewal off.  The mandate becomes
``canceled`` rather than being deleted, every charge still scheduled is dropped,
and the member is emailed.  The membership itself is untouched and runs to the
end of its term.

Statuses: **204** with an empty body; **404** when the caller has no mandate;
**401** when anonymous.


The finance screens
===================

``GET /admin/renewals``
-----------------------

Finance.  Every mandate, paginated, newest first.

``?status=`` narrows to ``pending``, ``active``, ``paused`` or ``canceled``;
``?search=`` matches a name, an email address or the method label; ``?ordering=``
takes ``created_at``, ``status`` or ``last_charged_at``, and a leading ``-``
reverses.

.. code-block:: json

   {"count": 12, "next": null, "previous": null, "results": [{"id": 12, "...": "..."}]}

Each row is the mandate object above.

Statuses: **200**; **400** naming ``status`` for a status outside the four;
**403** for any role but finance; **401** when anonymous.

``GET /admin/renewals/{id}``
----------------------------

Finance.  One mandate, including ``last_error`` -- the reason its most recent
charge was refused, which is what a support call turns on.

Statuses: **200**; **404** for an unknown id; **403** for any role but finance;
**401** when anonymous.

``DELETE /admin/renewals/{id}``
-------------------------------

Finance.  Turn a member's automatic renewal off on their behalf.  Every charge
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
``payment_id`` is ``null`` until the charge is made.  The three timestamps say
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
``charged`` the renewals taken, ``failed`` the charges refused, ``paused`` the
mandates whose retries ran out on this run, and ``skipped`` the mandates and
attempts that needed nothing doing.  Every run writes one ``renewals.run`` audit
record naming the caller.

Statuses: **200**; **403** for any role but ``system_admin``; **401** when
anonymous.


Role summary
============

====================================  ==========================================
Endpoint                              Who
====================================  ==========================================
``GET | PATCH | DELETE /me/renewal``  the member themselves
``POST /me/renewal/setup``            the member themselves
``POST /me/renewal/confirm``          the member themselves
``GET /admin/renewals``               ``treasurer``, ``account_admin``
``GET /admin/renewals/{id}``          ``treasurer``, ``account_admin``
``DELETE /admin/renewals/{id}``       ``treasurer``, ``account_admin``
``GET /admin/renewals/attempts``      ``treasurer``, ``account_admin``
``POST /system/renewals/run``         ``system_admin``
====================================  ==========================================
