============
API: finance
============

The finance area: the payment list a treasurer works through, the period
summary, the two exports and their column chooser, the reconciliation table,
the year-end contributions list, one member's ledger, the full detail of a
single payment, and recording money that arrived by check or cash.

Every endpoint here is guarded by ``IsFinance`` — the ``treasurer`` and
``account_admin`` roles, with ``system_admin`` passing as it does everywhere.
A ``treasurer`` reaches the finance area and nothing else; in particular they
do not read ``/admin/members/*``, which carries medical and certificate data.
Checkout, the provider confirmations and the webhooks are in
:doc:`api-payments`; general API conventions — session authentication, the CSRF
header, pagination, error shapes — are in :doc:`api-reference`.

Money is always integer cents in the JSON.  Dollars appear only in a CSV cell,
a PDF cell and on screen.


Shared query parameters
=======================

The list, the summary and both exports read one parameter set, so they refuse
the same input the same way, with the complaint keyed by the parameter it came
from.  An empty parameter narrows nothing, which is what lets the filter bar
send every one of them on every request.

===============  ====================================================
Parameter        Meaning
===============  ====================================================
``from``         ``YYYY-MM-DD``; payments on or after this date.
``to``           ``YYYY-MM-DD``; payments on or before this date.
``provider``     ``stripe``, ``paypal``, ``mock`` or ``manual``.
``status``       ``pending``, ``succeeded``, ``failed``,
                 ``partially_refunded`` or ``refunded``.
``search``       Member name, email, the provider's reference, or the
                 treasurer's note.
``plan``         A membership plan slug.
``kind``         ``membership``, ``contribution`` or ``both``.
``wallet``       How the money was presented: ``card``, ``check``,
                 ``cash``, and the rest of the wallet choices.
``reconciled``   ``yes`` for payments matched to a statement, ``no``
                 for the ones still outstanding.
``member``       A member's id.
``min_cents``    Lower bound on the total charged.
``max_cents``    Upper bound on the total charged.
``group``        ``month`` or ``year``; the summary's period.
``columns``      Comma-separated export column keys.
===============  ====================================================

The date bounds are applied to ``paid_at`` — ``completed_at`` when the payment
settled and ``created_at`` otherwise — which is also what the summary groups
by.  A date the calendar does not have, such as ``2026-02-30``, is as much a
**400** as ``last tuesday``:

.. code-block:: json

   {"from": ["Expected a date as YYYY-MM-DD."]}

``?ordering=`` accepts ``paid_at``, ``created_at``, ``completed_at``,
``amount_cents``, ``contribution_cents``, ``fee_cents``, ``net_cents``,
``reconciled_on``, ``status``, ``provider``, ``plan__name``,
``user__last_name`` and ``user__email``, each with a ``-`` prefix for
descending; anything else is a **400**.  The list and both exports honor it.


``GET /admin/payments``
=======================

Paginated (``?page=&page_size=``, default 25, max 200), newest money first.

.. code-block:: json

   {
     "count": 214,
     "next": "http://localhost:8000/api/v1/admin/payments?page=2",
     "previous": null,
     "results": [
       {"id": 412, "user_id": 37, "user_name": "Marta Reyes",
        "user_email": "marta@example.org", "plan": "Annual", "kind": "both",
        "amount_cents": 14500, "plan_amount_cents": 4500,
        "contribution_cents": 10000, "fee_cents": 450, "net_cents": 14050,
        "refunded_cents": 0, "currency": "usd", "provider": "stripe",
        "wallet": "apple_pay", "provider_ref": "pi_3NkP...",
        "status": "succeeded", "receipt_number": "CALDART-000412",
        "receipt_sent_at": "2026-01-08T20:00:10-08:00",
        "paid_on": "2026-01-08", "received_on": null,
        "reconciled_on": "2026-02-02", "reconciled_by": "Lucia Ferreira",
        "recorded_by": null, "note": "",
        "membership": {"id": 88, "starts_on": "2026-01-09",
                       "ends_on": "2027-01-08", "status": "active"},
        "renewal_attempt": null,
        "created_at": "2026-01-08T20:00:00-08:00",
        "completed_at": "2026-01-08T20:00:05-08:00"}
     ]
   }

``kind`` is read from the payment: ``membership`` when it names a plan and
gives nothing beyond it, ``contribution`` when it names no plan, ``both`` when
it does the two at once.  ``paid_on`` is the ledger date — ``received_on`` for
a payment recorded by hand, the local date of ``completed_at`` for every other
provider, and ``null`` while the payment has not completed.  ``membership`` is
the term the payment bought, or ``null``; ``renewal_attempt`` is the automatic
charge it came from, or ``null`` when a person paid it.  ``raw``, the
provider's own payload, is never in the API.

Datetimes carry the site's own offset rather than ``Z``: DRF renders them in
``TIME_ZONE``, which is ``America/Los_Angeles``, so the same instant reads
``-08:00`` in winter and ``-07:00`` in summer.

Statuses: **200**; **400** for an unusable filter or ``?ordering=`` value;
**401** when anonymous; **403** without a finance role.


``GET /admin/payments/summary``
===============================

``?group=`` defaults to ``month``, and the filters above apply.  **Only money
that arrived counts**: a pending or failed attempt was never revenue, while a
payment since refunded was, and is reported with what went back.  Oldest period
first; periods with nothing in them are omitted.

.. code-block:: json

   [
     {"period": "2026-01", "count": 2, "total_cents": 21000,
      "plan_cents": 9000, "contribution_cents": 12000, "fee_cents": 639,
      "net_cents": 20361, "refunded_cents": 2500,
      "by_provider": {"stripe": 14500, "paypal": 6500}}
   ]

``period`` is ``YYYY-MM`` for months and ``YYYY`` for years, computed in the
site's time zone.  ``refunded_cents`` counts a refund against the period the
*payment* arrived in, which is the question an income statement asks; the
reconciliation table below dates refunds differently, and deliberately.
``by_provider`` omits providers with nothing in that period, so it is safe to
iterate but not to index blindly.

Statuses: **200**; **400** for an unusable filter or ``group``; **401** when
anonymous; **403** without a finance role.


``GET /admin/payments/columns``
===============================

The column registry both exports read, in export order, so the screen's column
chooser is data-driven rather than a list typed into the portal.

.. code-block:: json

   [{"key": "paid_on", "label": "Date", "default": true},
    {"key": "receipt_number", "label": "Receipt", "default": false}]

The keys, in order, are ``paid_on``, ``receipt_number``, ``name``, ``email``,
``plan``, ``kind``, ``plan_amount``, ``contribution``, ``total``, ``fee``,
``net``, ``refunded``, ``provider``, ``wallet``, ``status``, ``provider_ref``,
``received_on``, ``reconciled_on``, ``note``, ``membership_starts`` and
``membership_ends``.  Every one is a default column except ``receipt_number``,
``received_on``, ``note``, ``membership_starts`` and ``membership_ends``.

Statuses: **200**; **401** when anonymous; **403** without a finance role.


``GET /admin/payments/export.csv`` and ``export.pdf``
=====================================================

The filtered, ordered list as a download, attached as
``caldart-payments-<YYYY-MM-DD>.csv`` or ``.pdf``, dated the day the export was
run.  ``?columns=a,b,c`` chooses which columns appear and in which order;
leaving it out gives the default columns in registry order.  The PDF subtitle
names the filters that were applied.

.. code-block:: text

   Date,Name,Email,Plan,Kind,Dues,Contribution,Total,Fee,Net,Refunded,Provider,Method,Status,Reference,Reconciled
   2026-01-08,Marta Reyes,marta@example.org,Annual,both,45.00,100.00,145.00,4.50,140.50,0.00,stripe,apple_pay,succeeded,pi_3NkP...,2026-02-02

Money is decimal dollars here rather than cents, because the file is opened in
a spreadsheet; the PDF prints the same figures with a dollar sign, because it
is read by a person.  The exports include **every** status, while the summary
counts only money that arrived — so an export and a period total differ
whenever there are failed attempts in the range, which is expected rather than
a fault.

Statuses: **200**; **400** for an unusable filter or an unknown column key
(``{"columns": ["Unknown column: karma"]}``); **401** when anonymous; **403**
without a finance role.


``GET /admin/payments/reconciliation``
======================================

One row per period, or per provider, for matching the books against a bank or
provider statement.  Parameters: ``from``, ``to``, ``provider``, and ``group``,
which is ``month`` (the default), ``year`` or ``provider``.

.. code-block:: json

   [
     {"period": "2026-01", "count": 24, "gross_cents": 148000,
      "fee_cents": 4620, "net_cents": 143380, "refunded_cents": 2500,
      "net_after_refunds_cents": 140880, "reconciled_count": 22,
      "unreconciled_count": 2}
   ]

Succeeded, partially refunded and refunded payments all count: each one is a
line on the statement.  **Refunds are dated by** ``refunded_at`` — the day the
money went back — so a January payment refunded in February belongs to
February here, and a period in which money only went back still gets a row,
with a zero ``count``.  ``net_after_refunds_cents`` is ``net_cents`` less
``refunded_cents`` and can therefore be negative.

``reconciled_count`` and ``unreconciled_count`` split the period's payments by
whether a treasurer has set ``reconciled_on``.

``reconciliation/export.csv`` and ``reconciliation/export.pdf`` carry the same
rows, attached as ``caldart-reconciliation-<from>-<to>.csv`` or ``.pdf``.  An
open end of the range is spelled ``all`` in the filename.  The PDF is portrait
letter.

Statuses: **200**; **400** for an unusable range, provider or grouping
(``{"group": ["Expected 'month', 'year' or 'provider'."]}``); **401** when
anonymous; **403** without a finance role.


``GET /admin/payments/contributions``
=====================================

One row per member who gave something in a calendar year — the list the
year-end acknowledgments go out from.  ``?year=`` defaults to the current year;
a year the report will not look at is a **400**.

.. code-block:: json

   [
     {"user_id": 37, "name": "Marta Reyes", "email": "marta@example.org",
      "count": 2, "contribution_cents": 11000, "refunded_cents": 2500,
      "net_contribution_cents": 8500}
   ]

A payment counts in the year its ``paid_on`` falls in, so a check counts on the
day it was received.  ``refunded_cents`` is what went back against those
payments, whenever the refund was taken, capped at the contribution the payment
carried; ``net_contribution_cents`` is the difference, and is the figure an
acknowledgment quotes.  Rows are largest net giver first, ties broken by name.

``contributions/export.csv`` and ``contributions/export.pdf`` carry the same
rows, attached as ``caldart-contributions-<year>.csv`` or ``.pdf``.

Statuses: **200**; **400** for an unusable ``year``; **401** when anonymous;
**403** without a finance role.


``GET /admin/payments/ledger/{user_id}``
========================================

One member's whole money history, in a single call, for the finance area's
member screen and for the Payments tab of the member record.

.. code-block:: json

   {
     "user": {"id": 37, "name": "Marta Reyes", "email": "marta@example.org",
              "membership": {"status": "current", "expires_on": "2027-01-08",
                             "plan": "Annual", "is_lifetime": false}},
     "totals": {"paid_cents": 43500, "contribution_cents": 11000,
                "fee_cents": 1380, "refunded_cents": 2500},
     "payments": [],
     "mandate": {"id": 4, "plan": "Annual", "contribution_cents": 2000,
                 "provider": "stripe",
                 "method_label": "Visa ending 4242, expires 03/2028",
                 "status": "active", "failure_count": 0,
                 "last_charged_at": "2026-01-05T06:30:12-08:00",
                 "canceled_at": null},
     "statement_years": [2026, 2025]
   }

``payments`` holds the same rows as ``GET /admin/payments/{id}`` below, newest
money first, including the attempts that failed.  ``totals`` counts only money
that arrived.  ``mandate`` is ``null`` for a member with no standing renewal
authority.  ``statement_years`` names the years the member can download a
contribution statement for — a year qualifies when at least one payment
carrying a contribution arrived in it — newest first.

Statuses: **200**; **401** when anonymous; **403** without a finance role;
**404** for an unknown member.


``GET | PATCH /admin/payments/{id}``
====================================

``GET`` answers the full finance row plus ``refunds``, the refunds issued
against the payment, newest first:

.. code-block:: json

   {"id": 412, "refunds": [
      {"id": 9, "payment_id": 412, "amount_cents": 2500,
       "reason": "requested_by_member", "note": "", "status": "succeeded",
       "provider_ref": "re_3NkP...", "requested_by_id": 7,
       "refunded_at": "2026-02-14T11:02:00-08:00",
       "created_at": "2026-02-14T11:01:58-08:00"}]}

Each refund is the row :doc:`api-refunds` describes, so ``requested_by_id`` is
``null`` for a refund issued in the provider's own dashboard, which arrives by
webhook.

``PATCH`` takes ``reconciled_on`` — a date, or ``null`` to un-match the payment
— and ``note``, and answers the payment as it now stands.  Setting
``reconciled_on`` records the caller in ``reconciled_by``; clearing it clears
that name too.  Each field that really changes writes its own audit record,
``payment.reconcile`` or ``payment.note``, so resending an unchanged value
records nothing.  A body naming neither field is refused:

.. code-block:: json

   {"non_field_errors": ["Send reconciled_on, note, or both."]}

Statuses: **200**; **400** for a body the serializer refuses; **401** when
anonymous; **403** without a finance role; **404** for an unknown id.


``POST /admin/payments/record``
===============================

Money that arrived by check, cash or bank transfer.  The payment is created
already succeeded with provider ``manual``, a zero fee and a net equal to the
amount, and whatever term it bought is activated through the same service a
card checkout uses — which also emails the member their receipt.

.. code-block:: json

   {"user_id": 37, "plan": "annual", "contribution_cents": 0,
    "method": "check", "reference": "1041", "received_on": "2026-03-02",
    "note": "Mailed to the PO box"}

``plan`` is a plan slug, a lifetime plan included, or empty for a pure
contribution.  ``method`` is ``check``, ``cash``, ``bank_transfer`` or
``other``.  ``reference`` is the check number and is stored as the payment's
``provider_ref``; it may be empty, and two payments may both leave it blank.
``received_on`` is the day the money arrived and becomes the ledger date.

The response is the same body as ``GET /admin/payments/{id}``, and the act is
recorded as ``payment.record``.

Statuses: **201**; **400** keyed by the field at fault — an unknown ``method``,
a ``received_on`` in the future, a ``reference`` another recorded payment
carries, a ``plan`` that is not active, or a plan and contribution that come to
nothing; **401** when anonymous; **403** without a finance role; **404** for an
unknown member.


Role summary
============

=============================================  ==========================
Endpoint                                       Who
=============================================  ==========================
``GET /admin/payments``                        ``treasurer``,
                                               ``account_admin``
``GET /admin/payments/summary``                Finance
``GET /admin/payments/columns``                Finance
``GET /admin/payments/export.{csv,pdf}``       Finance
``GET /admin/payments/reconciliation``         Finance
``GET .../reconciliation/export.{csv,pdf}``    Finance
``GET /admin/payments/contributions``          Finance
``GET .../contributions/export.{csv,pdf}``     Finance
``GET /admin/payments/ledger/{user_id}``       Finance
``GET | PATCH /admin/payments/{id}``           Finance
``POST /admin/payments/record``                Finance
=============================================  ==========================

"Finance" is ``treasurer`` or ``account_admin``; ``system_admin`` passes every
row.  The full matrix is in :doc:`api-reference`, and the report internals — the
column registry, the shared CSV and PDF helpers — are in :doc:`reports`.
