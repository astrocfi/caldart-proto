=============
API: payments
=============

Every endpoint under ``/api/v1/payments/``: checkout and its confirmation for
each provider, the webhooks, and the receipts and contribution statements a
member downloads for themselves.  The finance area under
``/api/v1/admin/payments`` is in :doc:`api-finance`.  General API conventions
— session authentication, the CSRF header, pagination, error shapes — are in
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
     ],
     "max_contribution_cents": 9999900
   }

``providers`` lists only providers whose keys are all configured, plus
``mock`` when ``PAYMENTS_MOCK_ENABLED`` is on.  The two key fields are
publishable values, safe in a browser; they are empty strings when unset.
``plans`` covers active plans only, and ``max_contribution_cents`` is the
largest contribution checkout accepts, which the form uses to bound its
"other amount" box.

Statuses: **200**; **401** when anonymous.

``POST /payments/checkout``
---------------------------

Any authenticated user.  Creates a ``pending`` payment and starts it with the
chosen provider.

.. code-block:: json

   {"plan": "annual", "contribution_cents": 10000, "provider": "stripe",
    "auto_renew": true}

``plan`` may be ``null`` for a contribution on its own, in which case no
membership term is created when it succeeds.  There is no amount field; one
sent anyway is ignored.  ``contribution_cents`` runs from ``0`` to
``9999900`` ($99,999.00) inclusive -- inside every provider's per-charge
ceiling, so an amount the API accepts is one the provider will take.  Anything
outside that range is refused before a payment row is created.

``auto_renew`` defaults to ``false``.  When it is true the payer is given a
``pending`` standing authority before the provider is started -- Stripe needs a
customer on the intent and PayPal a vault instruction on the order, and neither
can be added afterwards -- and the method they pay with becomes the one CalDART
renews from once the payment succeeds.  It is refused, with a 400 naming
``auto_renew``, for a plan that never expires, for a checkout that buys no plan
at all, and for a provider that cannot charge a saved method, which is every
provider but ``stripe``, ``paypal`` and ``mock``.  Turning automatic renewal on
again replaces whatever authority was there.  :doc:`api-renewals` covers the
mandate that results and :doc:`renewals` the scan that acts on it.

**201 Created**:

.. code-block:: json

   {"payment_id": 412, "provider": "stripe", "client": {"client_secret": "pi_3..._secret_..."}}

The body is discriminated on ``provider``: ``client`` carries exactly the fields the
chosen provider's browser SDK needs, and no others.

============  ==============================================
Provider      ``client``
============  ==============================================
``stripe``    ``{"client_secret": "..."}`` for the Payment
              Element.
``paypal``    ``{"order_id": "..."}`` for the PayPal buttons.
``mock``      ``{}``
============  ==============================================

**400** for an unknown or inactive plan, a contribution outside the accepted
range, a total of zero, an automatic renewal that could never be charged again,
an unknown provider, a provider that is not
configured (``{"provider": "'x' is not configured."}``), a provider that
refuses the request, or a provider that cannot be reached — a timeout, a
refused connection or an error on the provider's own side, all of which answer
``{"detail": "<provider> could not be reached. Please try again."}``.  Nothing
is left behind in the database when the provider rejects it or fails.

Statuses: **201**; **400** for any of the above; **401** when anonymous.

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
``google_pay``, ``link``, or ``card``.

**200**:

.. code-block:: json

   {"status": "succeeded",
    "membership": {"status": "current", "expires_on": "2027-03-14",
                   "plan": "Annual", "is_lifetime": false}}

A ``canceled`` or ``requires_payment_method`` intent marks the payment
``failed`` and answers 200 with ``"status": "failed"``.  A mismatch, or an
intent still ``processing``, is a **400** with the reason in ``detail``.  A
provider that cannot be reached is a **400** too, and the payment stays
``pending`` so the member can try again.  A payment the caller does own but
that was started with another provider is a **400** keyed by ``payment_id``:
``{"payment_id": "That payment is not a stripe payment."}``.

Statuses: **200** for a verified intent and for one Stripe reports as failed;
**400** for a missing field, a payment started with another provider, a
mismatch against our row, an intent still in flight, or Stripe being
unreachable; **401** when anonymous; **404** when the payment is not the
caller's, an unknown id included.

``POST /payments/paypal/capture``
---------------------------------

The payment's owner only.

.. code-block:: json

   {"payment_id": 413, "order_id": "5O190127TN364715T"}

Captures the order through Orders v2 and requires ``status == "COMPLETED"``,
at least one completed capture, a captured total equal to ``amount_cents`` and
the same currency.  ``custom_id`` is checked only when the capture carries one:
a capture that names a payment is required to name *this* one, and a capture
with no ``custom_id`` at all is accepted on the amount, the currency and the
order id.  Capturing an already-succeeded payment is a no-op that answers 200
without calling PayPal again.

.. code-block:: json

   {"status": "succeeded",
    "membership": {"status": "current", "expires_on": "2027-03-14",
                   "plan": "Annual", "is_lifetime": false}}

A capture that completes for the wrong amount or currency, or that names
another payment in ``custom_id``, is refused with a **400**, and a call that
fails in transit answers the same **400** with the payment left ``pending``.
PayPal may already hold the money in both cases, so each one writes an
``ERROR`` log record for an administrator to reconcile in the PayPal
dashboard: the mismatch names the payment and both amounts, and the call that
never completed names the payment and the amount at stake.

Statuses: **200** for a completed capture and for a payment that had already
succeeded; **400** for a missing field, a payment started with another
provider (``{"payment_id": "That payment is not a paypal payment."}``), a
capture PayPal did not complete, a mismatch, or PayPal being unreachable;
**401** when anonymous; **404** when the payment is not the caller's.

``POST /payments/mock/complete``
--------------------------------

The payment's owner only, and only while ``PAYMENTS_MOCK_ENABLED`` is on —
otherwise **404**, so production never advertises the route.

.. code-block:: json

   {"payment_id": 414, "outcome": "succeed"}

``outcome`` is ``succeed`` or ``fail``.  Succeeding takes exactly the same
activation path as a real payment, and the response is the same
``{status, membership}`` body the two real confirm endpoints answer with:

.. code-block:: json

   {"status": "succeeded",
    "membership": {"status": "current", "expires_on": "2027-03-14",
                   "plan": "Annual", "is_lifetime": false}}

Statuses: **200**; **400** for a missing field, an ``outcome`` outside those
two, or a payment started with another provider; **401** when anonymous;
**404** when the payment is not the caller's and when
``PAYMENTS_MOCK_ENABLED`` is off.

``GET /payments/{id}``
----------------------

The payment's **owner**, or a finance role (``treasurer`` or
``account_admin``).  Used to poll after a redirect-based payment.

.. code-block:: json

   {"status": "pending",
    "membership": {"status": "none", "expires_on": null,
                   "plan": null, "is_lifetime": false}}

``status`` is ``pending``, ``succeeded``, ``failed``, ``partially_refunded``
or ``refunded``.

Statuses: **200**; **401** when anonymous; **403** for a signed-in caller who
neither owns the payment nor holds a finance role; **404** for an unknown
id.


Receipts and statements
=======================

CalDART sends its own receipt for every payment that succeeds, whoever took
the money, with the PDF attached, and stamps ``receipt_sent_at`` on the
payment when it goes.  Stripe is not asked to send a receipt of its own: the
member gets one, and it carries the 501(c)(3) wording a donor needs.  A mail
server that refuses the message is logged and leaves ``receipt_sent_at`` null,
so resending it is the retry.

A receipt exists only for money that arrived.  A pending or failed payment has
none, and every endpoint below answers **404** for one, exactly as it does for
an id nobody holds.

``GET /me/payments``
--------------------

Any authenticated user, over their own payments, newest first.  Each row
carries everything the payments screen draws, so it needs no second call per
row:

.. code-block:: json

   [{"id": 414, "plan": "Annual", "kind": "both",
     "amount_cents": 14500, "plan_amount_cents": 4500,
     "contribution_cents": 10000, "refunded_cents": 2500,
     "provider": "stripe", "wallet": "card", "status": "partially_refunded",
     "paid_on": "2026-03-14", "completed_at": "2026-03-14T18:02:11Z",
     "receipt_sent_at": "2026-03-14T18:02:13Z",
     "membership": {"id": 87, "starts_on": "2026-03-14",
                    "ends_on": "2027-03-13"}}]

``kind`` is ``membership``, ``contribution`` or ``both``, read from the plan
and the contribution.  ``paid_on`` is the ledger date: the day a check was
received, or the local date the provider settled, and null while the payment
has not completed.  ``membership`` is the term the payment activated, or null
when it bought none.

``GET /me/payments/{id}/receipt.pdf``
-------------------------------------

The payment's **owner only** — an account administrator reading somebody
else's receipt uses the finance route below.  Answers the receipt as
``application/pdf``, attached as ``caldart-receipt-CALDART-000414.pdf``.

Statuses: **200**; **401** when anonymous; **404** for an unknown payment, for
one belonging to somebody else, and for one whose money never arrived.

``GET /me/payments/statements``
-------------------------------

Any authenticated user.  The calendar years the caller may download a
contribution statement for, newest first:

.. code-block:: json

   {"years": [2026, 2025]}

A year appears only when the member made at least one contribution in it that
settled.  A member who has never contributed gets an empty list, not a 404.

Statuses: **200**; **401** when anonymous.

``GET /me/payments/statements/{year}.pdf``
-------------------------------------------

Any authenticated user, over their own giving.  One upright page listing every
contribution that settled in ``year``, each netted against whatever of it came
back, the year's total, and the 501(c)(3) wording.  A refund is applied to the
contribution before the dues, because a member asking for part of a payment
back is asking for the gift back.  Attached as
``caldart-contributions-2026.pdf``.

Statuses: **200**; **401** when anonymous; **404** for a year the member
contributed nothing in.

``GET /admin/payments/{id}/receipt.pdf``
-----------------------------------------

Finance — a ``treasurer`` or an ``account_admin``.  The same receipt, for any
member's payment.

Statuses: **200**; **401** when anonymous; **403** for any other role;
**404** for an unknown payment or one whose money never arrived.

``POST /admin/payments/{id}/receipt``
--------------------------------------

Finance.  Builds the receipt afresh and emails it to the payer with its PDF
attached.  The body is empty.

.. code-block:: json

   {"sent": true, "receipt_sent_at": "2026-03-15T09:14:02Z"}

``sent`` says whether the mail server took the message.  A refusal answers
``{"sent": false, "receipt_sent_at": null}`` with the stamp unchanged, so the
same call is the retry.  Writes a ``payment.receipt_resend`` audit record
either way.

Statuses: **200**; **401** when anonymous; **403** for any other role;
**404** for an unknown payment or one whose money never arrived.

``GET /admin/payments/ledger/{user_id}/statements/{year}.pdf``
---------------------------------------------------------------

Finance.  Any member's contribution statement for one year, as the member's
own route renders it.

Statuses: **200**; **401** when anonymous; **403** for any other role;
**404** for an unknown member and for a year they contributed nothing in.


Fees and net amounts
====================

Every payment records what it cost: ``fee_cents``, what the provider kept, and
``net_cents``, what reached CalDART's balance — both exactly as the provider
reported them, never computed from a published rate.

Stripe
   ``payment_intents.retrieve`` expands ``latest_charge.balance_transaction``,
   and the transaction's ``fee`` and ``net`` are already integer cents.
PayPal
   ``seller_receivable_breakdown.paypal_fee.value`` and ``.net_amount.value``
   from the capture, converted from PayPal's decimal strings.
Mock
   2.9% rounded half up to the cent, plus 30 cents — the shape of a card fee,
   so seeded and test data look real.
Recorded by hand
   Zero fee; the net is the whole amount.

Some payment methods settle after the charge, and until they do there is no
fee to record: the payment keeps ``fee_cents`` and ``net_cents`` at zero, and
Stripe's ``charge.updated`` webhook fills them in when the balance transaction
appears.  A payment whose ``net_cents`` is zero against a non-zero amount is
one whose fee nobody has reported yet.


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
  verification as the confirm endpoint, then marks the payment succeeded,
  recording the fee when the event carries an expanded balance transaction;
* ``payment_intent.payment_failed`` — marks it failed;
* ``charge.updated`` — fills in a fee that did not exist when the money
  arrived.  The figures are taken from the event when it carries an expanded
  balance transaction, and read back from Stripe otherwise.  A payment whose
  fee is already recorded is left alone, so a re-delivery changes nothing.
  Stripe orders no deliveries, so this event is acted on whatever state the
  payment is in: a fee that arrives before the ``payment_intent.succeeded``
  that settles the row is kept when the row settles;
* ``charge.refunded`` — records every succeeded refund on the charge that is
  not already on file, as :ref:`api-refunds-webhooks` describes.

Everything else is acknowledged and ignored.  The response says what happened:

.. code-block:: json

   {"received": true, "handled": true}

``handled`` is false for an event about a payment this installation does not
have, for a ``payment_intent.succeeded`` that fails the same verification the
confirm endpoint applies, for a ``charge.updated`` whose fee is already known
or still unreadable, and for every event type above that is not listed.
It is idempotent, so it is safe for it to race the browser's confirm call or
to be re-delivered from the Stripe dashboard.

Statuses: **200** whether or not the event was acted on; **400** for a
signature that does not check out; **405** for any method but ``POST``.

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
``PAYMENT.CAPTURE.DENIED`` and ``PAYMENT.CAPTURE.REVERSED`` mark it failed; and
a verified ``PAYMENT.CAPTURE.REFUNDED`` records the refund, as
:ref:`api-refunds-webhooks` describes.
Without verification nothing changes — an unverifiable notification is not
evidence that money moved.  A notification about a payment this installation
does not have is received but not filed.

Statuses: **200** whether or not the notification was verified or acted on;
**400** ``{"detail": "Malformed JSON."}`` for a body that is not JSON;
**405** for any method but ``POST``.


The finance reports
===================

The payment list, the period summary, the exports, the reconciliation table,
the contributions list, the member ledger, the payment detail and recording a
payment taken by hand are all in :doc:`api-finance`.  They are read by the
``treasurer`` and ``account_admin`` roles rather than by a member, and they
share one filter set of their own.


Other payment routes
====================

``GET /.well-known/apple-developer-merchantid-domain-association``
------------------------------------------------------------------

Not part of the JSON API, and served from the site root rather than
``/api/v1/``.  Returns the file at ``STRIPE_APPLE_PAY_DOMAIN_ASSOCIATION`` as
``text/plain`` so Stripe can verify the domain for Apple Pay.  See
:doc:`payments-setup`.

The response carries ``Cache-Control: max-age=3600, public``, since the file
changes only when the domain is re-registered.

Statuses: **200** with the file's contents, for anybody; **404** when
``STRIPE_APPLE_PAY_DOMAIN_ASSOCIATION`` is empty or names a file that is not
there; **405** for any method but ``GET`` or ``HEAD``.


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
``GET /payments/{id}``                 Owner, ``treasurer`` or
                                       ``account_admin``
``GET /me/payments``                   Any authenticated user, own rows
``GET /me/payments/{id}/receipt.pdf``  The payment's owner
``GET /me/payments/statements*``       Any authenticated user, own giving
``POST /payments/*/webhook``           Nobody — signature verified instead
``GET /admin/payments*``               See :doc:`api-finance`
=====================================  ==========================================

``system_admin`` passes every role check, as everywhere else in the API.  The
three confirm endpoints are ownership checks, not role checks, so no role, not
even ``system_admin``, confirms somebody else's payment.
