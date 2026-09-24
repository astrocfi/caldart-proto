============
API: refunds
============

Giving money back.  A refund is a record in its own right: it carries its own
amount, the reason the treasurer chose, an optional note, and the provider's
own reference for the refund once the provider has taken it.  A payment is
never edited to say "refunded" and nothing else — the refunds beneath it are
what the ledger is built from.

General API conventions — session authentication, the CSRF header, error
shapes — are in :doc:`api-reference`; the two worth repeating here are that an
unauthenticated request that reaches the permission check gets **401** (not
403, which is reserved for a refused role and for a missing CSRF token), and
that money is always integer cents.  Checkout and the payment rows themselves
are in :doc:`api-payments`.

.. _api-refunds-issue:

``POST /admin/payments/{id}/refunds``
=====================================

A ``treasurer`` or an ``account_admin``.  Refunds part or all of one payment.

.. code-block:: json

   {"amount_cents": 2000, "reason": "requested_by_member",
    "note": "Asked by phone on 3 March", "cancel_term": false}

===================  =========================================================
Field                Meaning
===================  =========================================================
``amount_cents``     What to give back, at least ``1`` and at most what the
                     payment has left unrefunded.  Required.
``reason``           ``requested_by_member``, ``duplicate``, ``error``,
                     ``fraudulent`` or ``other``.  Required.
``note``             At most 255 characters.  Defaults to ``""``.
``cancel_term``      Cancel the membership term this payment bought.
                     Defaults to ``false``.
===================  =========================================================

**201 Created**:

.. code-block:: json

   {"refund": {"id": 9, "payment_id": 412, "amount_cents": 2000,
               "reason": "requested_by_member", "note": "Asked by phone on 3 March",
               "status": "succeeded", "provider_ref": "re_3NkP...",
               "requested_by_id": 7, "refunded_at": "2026-03-03T18:04:11Z",
               "created_at": "2026-03-03T18:04:10Z"},
    "payment": {"id": 412, "amount_cents": 6500, "refunded_cents": 2000,
                "status": "partially_refunded"}}

``payment`` is the row as it now stands, so the screen that asked needs no
second request to redraw it.

Statuses: **201**; **400** for a body the refund will not act on (below);
**401** when anonymous; **403** for a signed-in caller holding neither finance
role; **404** for an unknown payment id.

What a refund refuses
---------------------

Each of these is **400**, keyed by the field it belongs to:

* ``amount_cents`` — ``"A refund must be for more than zero."``
* ``amount_cents`` — ``"Only $45.00 of this payment is left to refund."``, when
  the amount exceeds the payment's amount less its succeeded refunds.  A
  payment already given back in full is refused this way, with ``$0.00``.
* ``amount_cents`` — ``"That payment has not succeeded, so there is nothing to
  refund."``, for a payment that is ``pending`` or ``failed``.
* ``reason`` — a reason outside the five choices.
* ``detail`` — the sentence the provider gave, when the provider refuses the
  refund or cannot be reached.  The refund row is kept as ``failed``, so the
  attempt stays on the record; the payment's status does not move, because no
  money went back.

Nothing is written when the amount or the reason is refused.

What a succeeded refund does
----------------------------

#. The refund row is written ``pending``, the provider is asked, and the row
   becomes ``succeeded`` with the provider's reference and ``refunded_at``.
#. The payment's status follows the running total of its succeeded refunds:
   ``refunded`` once they come to its whole amount, ``partially_refunded``
   while they come to less.
#. With ``cancel_term``, the membership term the payment bought is canceled,
   with a note naming the refund.  A payment that bought no term — a
   contribution on its own — ignores the flag.
#. The member is emailed, with the amount, what the payment was for, and
   whether their membership ended with it.  A mail server that refuses the
   message is logged; the money has already gone back, so the refund stands.
#. One ``payment.refund`` line goes to the audit log, carrying the refund id,
   the amount, the reason and whether a term was canceled.  A cancellation
   writes its own ``membership.correct`` line.

Per provider
------------

==============  ===========================================================
Provider        The call
==============  ===========================================================
``stripe``      ``refunds.create`` against the payment's PaymentIntent, with
                the idempotency key ``caldart-refund-<refund id>``, so a call
                repeated after a timeout gives the money back once.
``paypal``      ``POST /v2/payments/captures/{capture_id}/refund``, where the
                capture id is read from the capture response stored on the
                payment.  A payment with no completed capture is a **400**.
``mock``        Succeeds at once, with no provider reference: no provider is
                holding a refund id.
``manual``      Nothing is called: a check or cash goes back the way it came,
                and the row is written with no provider reference.
==============  ===========================================================


.. _api-refunds-webhooks:

Refunds taken in the provider's dashboard
=========================================

Somebody can refund in Stripe's or PayPal's own dashboard, where CalDART has
no say.  Both webhooks (:doc:`api-payments`) record such a refund, so the
ledger is right whoever issued it.

============================  ================================
Event                         Endpoint
============================  ================================
``charge.refunded``           ``POST /payments/stripe/webhook``
``PAYMENT.CAPTURE.REFUNDED``  ``POST /payments/paypal/webhook``
============================  ================================

A refund recorded this way carries ``requested_by_id: null``, the reason
``other`` and the note ``Issued in the provider's dashboard``, and moves the
payment's status exactly as an issued refund does.

Three rules keep the ledger honest:

* **The provider's refund id is the key.**  A refund whose reference is
  already on file against that payment writes nothing, so a redelivered
  notification — and the notification for a refund CalDART itself issued —
  is a no-op.
* **Only a completed refund counts.**  Stripe's ``refunds.data`` entries are
  taken only where ``status`` is ``succeeded``; PayPal's resource only where
  its ``status`` is ``COMPLETED``.
* **No term is canceled by a webhook.**  A refund taken outside CalDART says
  nothing about whether the membership should end; a treasurer decides that
  on the payment's own screen.

PayPal acts on a notification only once its signature has been verified, which
needs ``PAYPAL_WEBHOOK_ID``; an unverified notification is filed against the
payment and nothing else.  Stripe's signature is checked on every delivery, so
a ``charge.refunded`` that verifies is always acted on.
