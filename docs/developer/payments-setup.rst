==============
Payments setup
==============

CalDART takes money through three providers: **Stripe** (card, Apple Pay,
Google Pay and Link, all through one Payment Element), **PayPal** (Orders v2),
and a **mock** provider for development and tests.  Each is optional.
``GET /api/v1/payments/config`` reports only the providers whose keys are
actually set, and the checkout screen shows a tab for each — so a machine with
no keys at all still runs the whole join flow against the mock provider.

This page is the recipe for setting the real ones up.


Environment variables
=====================

In development everything lives in ``.env`` at the repository root (copy
``.env.example`` if you have not already).  In production the same names live
in ``/etc/caldart/caldart.env``, which the systemd units load as an
``EnvironmentFile`` — and nothing re-reads it while the process is up, so
``systemctl restart caldart-web`` after every edit.  Either way
``backend/caldart/settings/base.py`` reads each one, except the production-only
mock switch, which ``backend/caldart/settings/prod.py`` reads.

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Variable
     - What it is
   * - ``STRIPE_PUBLISHABLE_KEY``
     - ``pk_test_…`` / ``pk_live_…``; sent to the browser, safe to expose.
   * - ``STRIPE_SECRET_KEY``
     - ``sk_test_…`` / ``sk_live_…``; server only.  **Never** commit it.
   * - ``STRIPE_WEBHOOK_SECRET``
     - ``whsec_…``; signs webhook payloads.
   * - ``STRIPE_APPLE_PAY_DOMAIN_ASSOCIATION``
     - Absolute path to the association file Stripe issues for Apple Pay.
   * - ``PAYPAL_CLIENT_ID``
     - REST app client id; sent to the browser to load the PayPal SDK.
   * - ``PAYPAL_CLIENT_SECRET``
     - REST app secret; server only.
   * - ``PAYPAL_ENV``
     - ``sandbox`` (default) or ``live``.
   * - ``PAYPAL_WEBHOOK_ID``
     - Optional.  Set it and the PayPal webhook verifies its signature; leave
       it blank and the webhook only records payloads.
   * - ``PAYMENTS_MOCK_ENABLED``
     - ``true`` in development and tests.  ``prod.py`` does not read it.
   * - ``PAYMENTS_MOCK_ENABLED_IN_PRODUCTION``
     - The only switch that turns the mock provider on under ``prod.py``.
       Leave it unset unless you mean to demonstrate the checkout without keys.

Both Stripe keys must be present for Stripe to appear in the provider list;
both PayPal credentials must be present for PayPal.  Restart Django after
editing ``.env`` — the settings module reads it once at import.


Stripe
======

Create the account
------------------

1. Sign up at https://dashboard.stripe.com/register.  A brand-new account is
   already in **test mode**; the toggle is at the top right of the dashboard.
   You do not need to activate the account (submit business details) to build
   and test everything on this page.
2. Set the account name to *CalDART* under **Settings → Business details**.
   It is what appears on the Payment Element and on receipts.

Get the keys
------------

**Developers → API keys** (test mode) gives you:

* *Publishable key* → ``STRIPE_PUBLISHABLE_KEY``
* *Secret key* (click "Reveal") → ``STRIPE_SECRET_KEY``

.. code-block:: ini

   STRIPE_PUBLISHABLE_KEY=pk_test_51ABC...
   STRIPE_SECRET_KEY=sk_test_51ABC...

Switching to live mode later means swapping both keys **and** the webhook
secret; the ``pk_live_``/``sk_live_`` prefixes make a mismatch obvious.

Enable the payment methods
--------------------------

**Settings → Payments → Payment methods**.  Turn on:

* **Cards** (on by default)
* **Apple Pay**
* **Google Pay**
* **Link** (optional; it is Stripe's own one-click wallet)

Because the server creates the PaymentIntent with
``automatic_payment_methods: {enabled: true}``, anything enabled here shows up
in the Payment Element automatically — there is no code change to make.

Set up the webhook
------------------

The webhook is a safety net: the browser normally confirms the payment
directly (``POST /api/v1/payments/stripe/confirm``), but a redirect-based
method can complete after the browser has wandered off.  Both paths call the
same idempotent service, so a payment is never counted twice.

For local development use the Stripe CLI:

.. code-block:: console

   $ brew install stripe/stripe-cli/stripe     # or see stripe.com/docs/stripe-cli
   $ stripe login
   $ stripe listen --forward-to localhost:8000/api/v1/payments/stripe/webhook

``stripe listen`` prints a signing secret the first time it runs:

.. code-block:: text

   > Ready! Your webhook signing secret is whsec_1a2b3c4d... (^C to quit)

Put that in ``.env`` as ``STRIPE_WEBHOOK_SECRET`` and restart Django.  Trigger
a test event in another terminal:

.. code-block:: console

   $ stripe trigger payment_intent.succeeded

.. note::

   ``stripe trigger`` builds an intent of its own, with no
   ``metadata.payment_id``, so the endpoint finds no payment to match and
   answers ``{"received": true, "handled": false}`` while logging that the
   event "referenced an unknown payment".  That is the *correct* response and
   it proves the route, the signature and the secret — but it is not a test of
   activation.  For that, take a real checkout through the Payment Element and
   watch the second, matching event arrive.

Both webhook views are ``csrf_exempt`` with no authentication and no
permission classes: the provider's signature over the body is the whole gate.
Make sure the reverse proxy passes ``/api/v1/payments/stripe/webhook`` and
``/api/v1/payments/paypal/webhook`` through unauthenticated, and does not
strip the ``Stripe-Signature`` or ``Paypal-*`` headers.

In production, create the endpoint in the dashboard instead
(**Developers → Webhooks → Add endpoint**), pointing at
``https://<your-domain>/api/v1/payments/stripe/webhook`` and subscribing to:

* ``payment_intent.succeeded``
* ``payment_intent.payment_failed``

The dashboard shows the endpoint's signing secret once it exists.

Without a correct secret every delivery is rejected with **400 Invalid Stripe
signature** — which is the intended behavior, since an unverified webhook
must never grant a membership.

Test cards
----------

Use any future expiry date, any three-digit CVC and any postcode.

===========================  =========================================
Number                       What happens
===========================  =========================================
``4242 4242 4242 4242``      Succeeds immediately.
``4000 0025 0000 3155``      Requires 3-D Secure authentication; a
                             modal appears, and "Complete" succeeds.
``4000 0000 0000 9995``      Declined (insufficient funds).
``4000 0000 0000 0002``      Declined (generic card decline).
===========================  =========================================

The full list is at https://docs.stripe.com/testing.

Apple Pay
---------

Apple Pay needs the domain registered with Stripe *and* a verification file
served from that domain.

1. **Settings → Payments → Payment methods → Apple Pay → Add new domain**.
   Enter the domain the portal is served from (``caldart.example.org``).
   Apple Pay cannot be tested from ``localhost``; use a real hostname over
   HTTPS, or a tunnel such as ``stripe listen``'s companion tooling or ngrok.
2. Stripe offers a file to download:
   ``apple-developer-merchantid-domain-association``.  Save it anywhere the
   Django process can read, and point ``.env`` at it:

   .. code-block:: ini

      STRIPE_APPLE_PAY_DOMAIN_ASSOCIATION=/etc/caldart/apple-developer-merchantid-domain-association

3. CalDART serves it from
   ``/.well-known/apple-developer-merchantid-domain-association``
   (``apps/payments/views.py``).  Check it:

   .. code-block:: console

      $ curl -i https://caldart.example.org/.well-known/apple-developer-merchantid-domain-association

   A 404 means the variable is unset or the path is wrong; Apple Pay then
   simply never appears, which is why this is a 404 and not a 500.

   The view answers ``GET`` and ``HEAD`` only, serves ``text/plain``, and sets
   ``Cache-Control: public, max-age=3600``.  That last one is the usual reason
   a path that has just been fixed still looks broken: give it an hour, or ask
   for it past any intermediate cache, before concluding the file is wrong.

4. Click **Verify** in the Stripe dashboard.

To try it: open the portal in **Safari on macOS or iOS**, signed in to an
Apple ID with a card in Wallet.  In Stripe test mode Apple Pay uses your real
card in the Wallet UI but **never charges it** — Stripe substitutes a test
token.  The Apple Pay button appears in the Payment Element only when all of
domain registration, HTTPS, Safari and an available card line up.

Google Pay
----------

Google Pay needs nothing beyond enabling it in **Payment methods**: no domain
registration, no extra file.  Test it in **Chrome**, signed in to a Google
account with a saved card (``pay.google.com``).  As with Apple Pay, test mode
never charges the card.

If the button does not appear, it is nearly always one of: not Chrome, no
saved card on the Google account, or the page is not on HTTPS.

How the flow works
------------------

#. ``POST /api/v1/payments/checkout`` with ``provider: "stripe"`` creates the
   pending payment, then ``providers/stripe.py`` creates a PaymentIntent for
   the server-computed amount with ``automatic_payment_methods`` enabled.  Its
   metadata carries ``payment_id``, ``user_id`` and the plan slug (empty for a
   pure donation), and the response hands the browser the intent's
   ``client_secret``.
#. The checkout mounts the Payment Element, which offers card, Apple Pay,
   Google Pay and Link as each becomes eligible, and calls
   ``stripe.confirmPayment`` with ``redirect: "if_required"``, so the common
   methods finish without leaving the page.
#. The browser posts the PaymentIntent id to
   ``POST /api/v1/payments/stripe/confirm``.  The server retrieves the intent,
   checks it as described below, and activates the membership before it
   answers: the member is current by the time the page moves on.
#. A method that insists on a redirect returns to the ``return_url``,
   ``/portal/join/done?payment_id=<id>``, renewals included.  The join
   wizard's return step makes the same confirm call, then polls
   ``GET /api/v1/payments/<id>`` for up to ten seconds while the payment
   settles.
#. The ``payment_intent.succeeded`` webhook covers a browser that never comes
   back.  Success is idempotent, so the confirm call and the webhook cannot
   activate two terms.

What CalDART verifies
---------------------

The client is never trusted with an amount.  On confirmation the server
re-retrieves the PaymentIntent and refuses to activate a membership unless
Stripe agrees about all of:

* ``status == "succeeded"``;
* ``amount`` equals the payment row's ``amount_cents``;
* ``currency`` equals the payment row's currency; and
* ``metadata.payment_id`` names that same payment.

The wallet stored against the payment comes from
``latest_charge.payment_method_details``: ``card.wallet.type`` of ``apple_pay``
or ``google_pay``, a payment method whose own ``type`` is ``link``, else plain
``card``.  When the charge or its details are missing altogether the wallet is
recorded as ``unknown`` rather than guessed at.

How long a call may take
------------------------

Every Stripe call goes through a client the provider builds itself, with a
20-second timeout and one network retry, so the worst case is 40 seconds.  That
has to stay below each timeout in front of Django — gunicorn's ``timeout``,
nginx's ``proxy_read_timeout`` and Apache's ``ProxyTimeout``, all 60 seconds in
``deploy/`` (:doc:`deployment`) — otherwise a slow Stripe reaches the browser
as a gateway error while the request is still running.  ``stripe`` defaults to
80 seconds and two retries, which would allow four minutes.  A backend test
reads the three deployment files and fails if the budget stops fitting under
them, so raise the budget and the proxy timeouts together or not at all.

PayPal is called over ``httpx`` with the same 20-second timeout and no retries.

Creating a PaymentIntent sends the idempotency key
``caldart-payment-<payment id>-start``, so starting the same payment row twice
returns the intent Stripe already has rather than creating a second one.


PayPal
======

Create the accounts
-------------------

1. Sign up for a developer account at https://developer.paypal.com.
2. Go to **Testing Tools → Sandbox Accounts**.  PayPal creates two for you:

   * a **business** account — the sandbox merchant that receives the money;
   * a **personal** account — the sandbox buyer you will pay with.

   Note the personal account's email address, and use **⋯ → Change password**
   to set a password you will remember: that pair is what you type into the
   PayPal window when testing.

Create the REST app
-------------------

**Apps & Credentials → Sandbox → Create App**.  Name it *CalDART*, link it to
the sandbox business account, and copy:

* *Client ID* → ``PAYPAL_CLIENT_ID``
* *Secret* (click "Show") → ``PAYPAL_CLIENT_SECRET``

.. code-block:: ini

   PAYPAL_CLIENT_ID=AXy1...
   PAYPAL_CLIENT_SECRET=EFz2...
   PAYPAL_ENV=sandbox

``PAYPAL_ENV`` selects the API host: ``sandbox`` uses
``https://api-m.sandbox.paypal.com``, ``live`` uses
``https://api-m.paypal.com``.  Going live means repeating this under the
**Live** tab for real credentials, and flipping ``PAYPAL_ENV=live``.

How the flow works
------------------

In the browser, ``PayPalScriptProvider`` loads PayPal's JavaScript SDK with
the client id, ``currency: "USD"`` and ``intent: "capture"``, and renders the
PayPal buttons.  Their ``createOrder`` callback calls
``POST /api/v1/payments/checkout`` with ``provider: "paypal"``, so the order is
created on the server for the server-computed amount and the browser only
receives its ``order_id``.  ``onApprove`` calls
``POST /api/v1/payments/paypal/capture``, and the capture is what activates
the membership.

On the server, CalDART calls the Orders v2 REST API directly with ``httpx`` —
no SDK.  Three calls, in ``backend/apps/payments/providers/paypal.py``:

1. ``POST /v1/oauth2/token`` with the client id and secret, for a bearer token
   that is cached in-process until shortly before it expires;
2. ``POST /v2/checkout/orders`` with ``intent=CAPTURE``, the server-computed
   amount, ``custom_id`` set to our payment id, and the CalDART brand name;
3. ``POST /v2/checkout/orders/{id}/capture`` when the buyer approves.

A capture only activates a membership when PayPal answers ``COMPLETED`` *and*
the captured amount, currency and ``custom_id`` all match our own record.

Testing it
----------

Choose the **PayPal** tab in the checkout, click the button, and sign in with
the sandbox **personal** account.  The sandbox behaves exactly like the live
site, with fake money.  Both sides of the transaction show up under
**Testing Tools → Sandbox Accounts → View/Edit account**.

Webhooks
--------

The capture call is authoritative, so the PayPal webhook is optional.  Set one
up if you want a belt-and-braces record:

1. **Apps & Credentials → your app → Add Webhook**, URL
   ``https://<your-domain>/api/v1/payments/paypal/webhook``, subscribed to
   ``PAYMENT.CAPTURE.COMPLETED``, ``PAYMENT.CAPTURE.DENIED`` and
   ``PAYMENT.CAPTURE.REVERSED``.
2. Copy the webhook id PayPal shows into ``PAYPAL_WEBHOOK_ID``.

With that id set, each delivery is verified through
``POST /v1/notifications/verify-webhook-signature``, and a verified
``PAYMENT.CAPTURE.COMPLETED`` for the right amount activates the membership.
**Without** it the endpoint still accepts and records the payload against the
payment, but changes nothing — an unverifiable notification is not evidence
that money moved.


The mock provider
=================

With ``PAYMENTS_MOCK_ENABLED=true`` (the default in development and tests) the
checkout offers a **Test payment** tab with *Succeed* and *Fail* buttons.
Succeeding runs exactly the same activation path as a real payment, so
membership terms, renewal dates and the payment reports all behave normally —
the only difference is that no provider is involved.

Production ignores that variable entirely: ``prod.py`` never reads it, so an
environment file copied from a development machine cannot hand out free
memberships on a live site.  The one switch that works there is
``PAYMENTS_MOCK_ENABLED_IN_PRODUCTION``, which appears in no template — set it
only to demonstrate the checkout on a box with no payment keys.  With the
provider off the endpoint answers 404, not 403: a production deployment should
not even advertise that a way to grant yourself a membership exists.

The end-to-end tests use this provider, which is why the five headline flows
run with no payment keys at all.  ``seed_demo`` does not: its two years of
history is dealt out between ``stripe`` and ``paypal`` in a 70 / 30 split with
plausible wallets, so the payment reports have something realistic to group
by.


The provider interface
======================

Each provider is a class in ``backend/apps/payments/providers/`` that
subclasses ``Provider`` from ``providers/base.py``:

``slug``
    The name stored in ``Payment.provider`` and sent by the checkout:
    ``stripe``, ``paypal`` or ``mock``.
``start(payment) -> dict``
    Called by ``POST /payments/checkout`` once the pending payment exists.
    Returns what the browser needs to show the payment UI:
    ``{"client_secret": ...}`` for Stripe, ``{"order_id": ...}`` for PayPal,
    ``{}`` for the mock.
``confirm(payment, **kwargs) -> bool``
    Verifies the payment with the provider, on the server, and marks it
    succeeded or failed through ``payments.services``.  Returns whether it
    succeeded.
``handle_webhook(request) -> HttpResponse``
    Processes an asynchronous notification.  It must be idempotent: a
    provider may deliver the same event more than once, and it may arrive
    after the browser's own confirmation.

``@register`` files a class under its ``slug``, and ``providers/__init__.py``
imports every provider module, so importing the package registers them all.
``get_provider(slug)`` returns an instance (``ValueError`` for an unknown
slug), and ``available_providers()`` lists the slugs whose settings are
present, which is what ``GET /payments/config`` offers the checkout.  A
provider signals trouble by raising ``PaymentError``, which the API answers
with HTTP 400.  It has three subclasses: ``ProviderNotConfigured`` (missing
keys), ``PaymentVerificationError`` (the provider's record disagrees with
ours), and ``ProviderUnavailable`` (the call never completed, or the provider
reported a failure of its own).  A provider must convert its library's and its
transport's own exceptions into one of these, so that an outage is a 400 with
"try again" rather than a 500 — at checkout the pending payment row is then
deleted, and at confirmation it is left ``pending`` for another attempt.

Adding a provider therefore means a registered subclass in a module of its
own, an import in ``providers/__init__.py``, a branch in
``available_providers()`` for its settings, a value in the ``Payment.provider``
choices (and its migration), and a panel in
``frontend/src/portal/features/checkout/``.


Going live: checklist
=====================

.. code-block:: text

   [ ] Stripe account activated (business details submitted and approved)
   [ ] STRIPE_PUBLISHABLE_KEY / STRIPE_SECRET_KEY swapped to pk_live_ / sk_live_
   [ ] Live-mode webhook endpoint created; STRIPE_WEBHOOK_SECRET is the live one
   [ ] Apple Pay: production domain registered, association file deployed,
       /.well-known/... returns 200 over HTTPS, dashboard shows "Verified"
   [ ] Google Pay enabled in live-mode payment methods
   [ ] PayPal live REST app created; PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET
       swapped; PAYPAL_ENV=live
   [ ] PAYPAL_WEBHOOK_ID set if the PayPal webhook is in use
   [ ] PAYMENTS_MOCK_ENABLED_IN_PRODUCTION unset, so the mock provider is off
   [ ] DEBUG=false, HTTPS enforced, SITE_URL and ALLOWED_HOSTS correct
   [ ] Secrets are in /etc/caldart/caldart.env, not in git
   [ ] systemctl restart caldart-web after the last edit to that file
   [ ] Both webhook paths reachable unauthenticated through the proxy
   [ ] One real payment taken, refunded in the provider's dashboard, and the
       membership term corrected by hand (CalDART does not record refunds)
   [ ] One real payment made and refunded from the Stripe dashboard
   [ ] Receipt email arrives (Stripe sends it to the PaymentIntent's
       receipt_email, which is the member's address)

Two things bite people at go-live: forgetting that the Apple Pay domain
registration is per-mode *and* per-domain, and leaving a test webhook secret
in place so every live delivery 400s.  Both show up in the Stripe dashboard's
webhook delivery log.


Troubleshooting
===============

**The provider tab is missing.**
  ``GET /api/v1/payments/config`` lists only providers whose keys are all set.
  Check ``.env`` and restart Django.

**"'stripe' is not configured." on checkout.**
  One of the two Stripe keys is empty.  ``available_providers()`` needs both
  ``STRIPE_SECRET_KEY`` and ``STRIPE_PUBLISHABLE_KEY``, and the checkout
  endpoint rejects an unconfigured provider with a 400 before it ever reaches
  the provider class — deliberately, so a half-configured deployment fails
  with a sentence rather than a traceback.

**Webhook deliveries 400.**
  The signing secret does not match the endpoint.  ``stripe listen`` prints a
  *different* secret from the dashboard endpoint; they are not interchangeable.

**Apple Pay never appears.**
  In order of likelihood: not Safari, not HTTPS, domain not registered for the
  current mode, association file not served, no card in Wallet.

**A payment succeeded but the membership did not activate.**
  Look at the payment row in the Django admin: ``status``, ``completed_at``
  and ``raw`` hold the provider's last payload.  Both the confirm endpoint and
  the webhook call the same idempotent ``mark_succeeded``, so re-delivering
  the webhook from the Stripe dashboard is a safe way to repair it.
