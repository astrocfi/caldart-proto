=============
API: payments
=============

Every endpoint under ``/api/v1/payments/`` and ``/api/v1/admin/payments``:
checkout and its confirmation for each provider, the webhooks, and the
payment reports.  General API conventions — session
authentication, the CSRF header, pagination, error shapes — are in
:doc:`api-reference`; the two worth repeating here are that an
unauthenticated request that reaches the permission check gets **401** (not
403, which is reserved for a refused role and for a missing CSRF token), and
that money is always integer cents.

The rule that shapes all of this: **the server never trusts a client-supplied
amount**.  A checkout request names a plan slug and a contribution; the total
is recomputed from the plan's price every time, and again when the provider is
asked to confirm.


Checkout
========

``GET /payments/config``
------------------------

Any authenticated user.  What the checkout screen can offer.

.. code-block:: json

   {
     "providers": ["stripe", "paypal", "mock"],
     "stripe_publishable_key": "pk_test_51ABC...",
     "paypal_client_id": "AXy1...",
     "plans": [
       {"slug": "annual", "name": "Annual", "price_cents": 4500,
        "duration_days": 365, "description": "Membership for one year."},
       {"slug": "life", "name": "Life", "price_cents": 65000,
        "duration_days": null, "description": "One payment, membership for life."}
     ],
     "contribution_tiers": [
       {"label": "No contribution", "cents": 0},
       {"label": "Participating", "cents": 2000},
       {"label": "Bronze", "cents": 10000},
       {"label": "Silver", "cents": 30000},
       {"label": "Gold", "cents": 100000},
       {"label": "Diamond", "cents": 300000},
       {"label": "Platinum", "cents": 1000000}
     ]
   }

``providers`` lists only providers whose keys are all configured, plus
``mock`` when ``PAYMENTS_MOCK_ENABLED`` is on.  The two key fields are
publishable values, safe in a browser; they are empty strings when unset.
``plans`` covers active plans only.

``POST /payments/checkout``
---------------------------

Any authenticated user.  Creates a ``pending`` payment and starts it with the
chosen provider.

.. code-block:: json

   {"plan": "annual", "contribution_cents": 10000, "provider": "stripe"}

``plan`` may be ``null`` for a contribution on its own, in which case no
membership term is created when it succeeds.  There is no amount field; one
sent anyway is ignored.

**201 Created**:

.. code-block:: json

   {"payment_id": 412, "provider": "stripe", "client": {"client_secret": "pi_3..._secret_..."}}

``client`` is whatever the browser needs next:

============  ==============================================
Provider      ``client``
============  ==============================================
``stripe``    ``{"client_secret": "..."}`` for the Payment
              Element.
``paypal``    ``{"order_id": "..."}`` for the PayPal buttons.
``mock``      ``{}``
============  ==============================================

**400** for an unknown or inactive plan, a negative contribution, a total of
zero, an unknown provider, a provider that is not configured, a provider that
refuses the request, or a provider that cannot be reached — a timeout, a
refused connection or an error on the provider's own side, all of which answer
``{"detail": "<provider> could not be reached. Please try again."}``.  Nothing
is left behind in the database when the provider rejects it or fails.

``POST /payments/stripe/confirm``
---------------------------------

The payment's **owner** only — an administrator has no business finishing
somebody else's checkout.

.. code-block:: json

   {"payment_id": 412, "payment_intent_id": "pi_3NkP..."}

The server retrieves the PaymentIntent from Stripe (expanding
``latest_charge``) and refuses unless *all* of these hold:

* ``metadata.payment_id`` names this payment;
* ``amount`` equals the payment's ``amount_cents``;
* ``currency`` equals the payment's currency; and
* ``status`` is ``succeeded``.

On success the membership term is created immediately and the wallet is
recorded from ``latest_charge.payment_method_details`` — ``apple_pay``,
``google_pay``, ``link`` or ``card``.

**200**:

.. code-block:: json

   {"status": "succeeded",
    "membership": {"status": "current", "expires_on": "2027-03-14",
                   "plan": "Annual", "is_lifetime": false}}

A ``canceled`` or ``requires_payment_method`` intent marks the payment
``failed`` and answers 200 with ``"status": "failed"``.  A mismatch, or an
intent still ``processing``, is a **400** with the reason in ``detail``.  A
provider that cannot be reached is a **400** too, and the payment stays
``pending`` so the member can try again.  **404** if the payment is not the
caller's.

``POST /payments/paypal/capture``
---------------------------------

The payment's owner only.

.. code-block:: json

   {"payment_id": 413, "order_id": "5O190127TN364715T"}

Captures the order through Orders v2 and requires ``status == "COMPLETED"``,
at least one completed capture, a captured total equal to ``amount_cents``,
the same currency, and a ``custom_id`` naming this payment.  Response shape is
the same as the Stripe confirm.  Capturing an already-succeeded payment is a
no-op that answers 200 without calling PayPal again.

A capture that completes for the wrong amount, currency or ``custom_id`` is
refused with a **400**, and a call that fails in transit answers the same
**400** with the payment left ``pending``.  PayPal may already hold the money
in both cases, so each one writes an ``ERROR`` log record for an administrator
to reconcile in the PayPal dashboard: the mismatch names the payment and both
amounts, and the call that never completed names the payment and the amount at
stake.

``POST /payments/mock/complete``
--------------------------------

The payment's owner only, and only while ``PAYMENTS_MOCK_ENABLED`` is on —
otherwise **404**, so production never advertises the route.

.. code-block:: json

   {"payment_id": 414, "outcome": "succeed"}

``outcome`` is ``succeed`` or ``fail``.  Succeeding takes exactly the same
activation path as a real payment.

``GET /payments/{id}``
----------------------

The payment's **owner or an** ``account_admin``.  Used to poll after a
redirect-based payment.

.. code-block:: json

   {"status": "pending",
    "membership": {"status": "none", "expires_on": null,
                   "plan": null, "is_lifetime": false}}

``status`` is ``pending``, ``succeeded``, ``failed`` or ``refunded``.  **403**
for any other signed-in user, **401** when anonymous.


Webhooks
========

Both endpoints are unauthenticated and CSRF-exempt: the signature *is* the
authentication.

``POST /payments/stripe/webhook``
---------------------------------

Verifies the ``Stripe-Signature`` header against ``STRIPE_WEBHOOK_SECRET`` and
answers **400** ``{"detail": "Invalid Stripe signature."}`` when it does not
check out.  Handles:

* ``payment_intent.succeeded`` — re-runs the same amount/currency/metadata
  verification as the confirm endpoint, then marks the payment succeeded;
* ``payment_intent.payment_failed`` — marks it failed.

Everything else is acknowledged and ignored.  The response says what happened:

.. code-block:: json

   {"received": true, "handled": true}

It is idempotent, so it is safe for it to race the browser's confirm call or
to be re-delivered from the Stripe dashboard.

``POST /payments/paypal/webhook``
---------------------------------

The capture call is authoritative, so this endpoint is a recorder.  It files
the payload against the matching payment (found by ``custom_id``, then by
order id) and answers:

.. code-block:: json

   {"received": true, "verified": false, "handled": false}

``verified`` is true only when ``PAYPAL_WEBHOOK_ID`` is set *and* PayPal's
``verify-webhook-signature`` call passes.  A verified
``PAYMENT.CAPTURE.COMPLETED`` for the right amount activates the membership;
``PAYMENT.CAPTURE.DENIED`` and ``PAYMENT.CAPTURE.REVERSED`` mark it failed.
Without verification nothing changes — an unverifiable notification is not
evidence that money moved.  Malformed JSON is a **400**.


Reports — ``account_admin``
===========================

All three endpoints share one filter set, applied to ``paid_at``: the moment
the money arrived, which is ``completed_at`` when the payment settled and
``created_at`` otherwise.

===============  ====================================================
Parameter        Meaning
===============  ====================================================
``from``         ``YYYY-MM-DD``; payments on or after this date.
``to``           ``YYYY-MM-DD``; payments on or before this date.
``provider``     ``stripe``, ``paypal`` or ``mock``.
``status``       ``pending``, ``succeeded``, ``failed`` or
                 ``refunded``.
``search``       Member name, email, or the provider's reference.
``group``        ``month`` or ``year``; the summary's period.
===============  ====================================================

One serializer reads all six for all three endpoints, so each refuses the same
input the same way, with the complaint keyed by the parameter it came from.  An
empty parameter narrows nothing, and a date the calendar does not have — such as
``2026-02-30`` — is as much a **400** as ``last tuesday``:

.. code-block:: json

   {"from": ["Expected a date as YYYY-MM-DD."]}

``GET /admin/payments``
-----------------------

Paginated (``?page=&page_size=``, default 25, max 200), newest first.
``?ordering=`` accepts ``paid_at``, ``created_at``, ``completed_at``,
``amount_cents``, ``contribution_cents``, ``status``, ``provider``,
``plan__name``, ``user__last_name`` and ``user__email``, each with a ``-``
prefix for descending; anything else is a **400**.

.. code-block:: json

   {
     "count": 214,
     "next": "http://localhost:8000/api/v1/admin/payments?page=2",
     "previous": null,
     "results": [
       {"id": 412, "user_id": 37, "user_name": "Marta Reyes", "plan": "Annual",
        "amount_cents": 14500, "plan_amount_cents": 4500,
        "contribution_cents": 10000, "currency": "usd", "provider": "stripe",
        "wallet": "apple_pay", "provider_ref": "pi_3NkP...",
        "status": "succeeded", "created_at": "2026-01-08T20:00:00Z",
        "completed_at": "2026-01-08T20:00:05Z"}
     ]
   }

``GET /admin/payments/summary``
-------------------------------

``?group=`` defaults to ``month``, and the filters above apply.
**Succeeded payments only** — a failed attempt was never revenue.  Oldest
period first; periods with nothing in them are omitted.

.. code-block:: json

   [
     {"period": "2026-01", "count": 2, "total_cents": 21000,
      "plan_cents": 9000, "contribution_cents": 12000,
      "by_provider": {"stripe": 14500, "paypal": 6500}}
   ]

``period`` is ``YYYY-MM`` for months and ``YYYY`` for years, computed in the
site's time zone.  ``by_provider`` omits providers with nothing in that
period, so it is safe to iterate but not to index blindly.

``GET /admin/payments/export.csv``
----------------------------------

The filtered list as ``text/csv``, streamed, attachment
``caldart-payments.csv``.  Columns:

.. code-block:: text

   paid_on,name,email,plan,plan_amount,contribution,total,provider,wallet,status,provider_ref
   2026-01-08,Marta Reyes,marta@example.org,Annual,45.00,100.00,145.00,stripe,apple_pay,succeeded,pi_3NkP...

Money is decimal dollars here rather than cents, because the file is opened in
a spreadsheet.


Other payment routes
====================

``GET /.well-known/apple-developer-merchantid-domain-association``
------------------------------------------------------------------

Not part of the JSON API, and served from the site root rather than
``/api/v1/``.  Returns the file at ``STRIPE_APPLE_PAY_DOMAIN_ASSOCIATION`` as
``text/plain`` so Stripe can verify the domain for Apple Pay, or **404** when
the setting is empty or the file is missing.  See :doc:`payments-setup`.


Role summary
============

=====================================  ==========================================
Endpoint                               Who
=====================================  ==========================================
``GET /payments/config``               Any authenticated user
``POST /payments/checkout``            Any authenticated user
``POST /payments/stripe/confirm``      The payment's owner
``POST /payments/paypal/capture``      The payment's owner
``POST /payments/mock/complete``       The payment's owner, mock enabled
``GET /payments/{id}``                 Owner or ``account_admin``
``POST /payments/*/webhook``           Nobody — signature verified instead
``GET /admin/payments*``               ``account_admin``
=====================================  ==========================================

``system_admin`` passes every role check, as everywhere else in the API.  The
three confirm endpoints are ownership checks, not role checks, so no role, not
even ``system_admin``, confirms somebody else's payment.
