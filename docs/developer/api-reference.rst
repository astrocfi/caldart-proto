=============
API reference
=============

Everything the portal talks to lives under ``/api/v1/``.  This page is the
contract's front matter — authentication, CSRF, status codes, pagination,
filtering, errors, and which role reaches which endpoint.  The pages it links
to document each app's endpoints in detail, request body by response body.

.. toctree::
   :maxdepth: 1

   api-auth
   api-profile
   api-members
   api-aircraft
   api-payments

Reminder, system and site endpoints have no page of their own; they are
covered by :doc:`reminders`, :doc:`backup-restore` and :doc:`cms`
respectively, and all of them appear in the :ref:`permission matrix
<api-permission-matrix>` below.

Conventions
===========

Authentication
--------------

**Session authentication, same origin, and nothing else.**
``DEFAULT_AUTHENTICATION_CLASSES`` is exactly
``rest_framework.authentication.SessionAuthentication``.  There is no token,
no API key and no JWT anywhere in the project, and no plan to add one — the
only client is a SPA served from the same origin as the API.

Signing in with ``POST /auth/login`` sets the session cookie; the browser sends
it automatically thereafter.  The portal's fetch wrapper
(``frontend/src/portal/api/client.ts``) sets ``credentials: "same-origin"`` on
every request for the same reason.

``DEFAULT_PERMISSION_CLASSES`` is ``IsAuthenticated``, but every view in the
project declares its own ``permission_classes``, so the default is never
load-bearing — read the matrix, not the default.

.. _api-csrf-bootstrap:

CSRF bootstrap
--------------

Session authentication means DRF enforces CSRF on every unsafe method.  A
client that has not yet made a request has no ``csrftoken`` cookie, so the API
offers one endpoint whose only job is to issue it:

.. code-block:: text

   GET /api/v1/auth/csrf   →  204 No Content, Set-Cookie: csrftoken=…

Call it whenever you hold no ``csrftoken`` cookie, then send the cookie's value
back in the ``X-CSRFToken`` header on every ``POST``, ``PUT``, ``PATCH`` and
``DELETE``.  The cookie is the only thing worth caching: a client that treats
one successful call as permission to stop asking locks itself out of every
write as soon as the cookie is missing or rotated.  The cookie is deliberately
**not** ``HttpOnly`` — JavaScript has to read it to echo it — while the session
cookie is; see the reasoning in ``caldart/settings/prod.py``.

A request from a signed-in caller that arrives without a usable token is
refused before the view runs, with ``403`` and a ``detail`` that starts
``CSRF Failed``.  That refusal is safe to repeat: fetch a token again and
resend the request once.

From ``curl``, that is two steps:

.. code-block:: console

   $ curl -s -c jar -o /dev/null http://localhost:8000/api/v1/auth/csrf
   $ curl -s -b jar -c jar -X POST http://localhost:8000/api/v1/auth/login \
       -H "Content-Type: application/json" \
       -H "X-CSRFToken: $(awk '/csrftoken/ {print $7}' jar)" \
       -H "Referer: http://localhost:8000/" \
       -d '{"email":"member@example.org","password":"caldart-demo"}'

The ``Referer`` header matters over HTTPS: Django checks it against
``CSRF_TRUSTED_ORIGINS`` for secure requests.

The two payment webhooks are the exception.  They are ``csrf_exempt`` with
``authentication_classes = []`` and ``permission_classes = []``, because the
caller is Stripe or PayPal, not a browser.  Their authentication is the
provider's own signature over the payload.

URL shape
---------

Routes are declared **without a trailing slash** — ``/api/v1/auth/me``, not
``/api/v1/auth/me/``.  Django's ``APPEND_SLASH`` only ever *adds* a slash, so a
request with one 404s.  Public site pages, in contrast, do end in a slash
(``WAGTAIL_APPEND_SLASH``).

JSON is the only representation: ``DEFAULT_RENDERER_CLASSES`` is
``JSONRenderer`` alone, so there is no browsable API and no ``?format=``.
Dates are ISO-8601 (``2027-03-01``); datetimes are ISO-8601 with an offset.

Every successful response is therefore either a JSON body or nothing at all:
an endpoint with nothing to say answers **204** with no body and no
``Content-Type``.  A client may treat any other 2xx body as a fault — an HTML
maintenance or proxy page served with status 200, say — rather than as data.
The exceptions are the routes that stream a file — the CSV and PDF exports and
``GET /system/backups/{name}/download`` — and those are followed as plain
links, so their bodies never reach the API client.

401 versus 403
--------------

DRF's default turns an unauthenticated request into **403** under session
authentication, because there is no ``WWW-Authenticate`` challenge to send.
The contract promises 401, and the portal keys "your session ended, sign in
again" off it, so ``caldart/exceptions.py`` installs an exception handler that
rewrites ``NotAuthenticated`` to 401.  The rule is therefore:

.. list-table::
   :header-rows: 1
   :widths: 14 86

   * - Status
     - Means
   * - **401**
     - Nobody is signed in.  Sign in and retry.
   * - **403**
     - Somebody is signed in, and the request was refused.  Retrying will not
       help, unless the ``detail`` starts ``CSRF Failed``.

Four deliberate departures are worth knowing:

- A **403** whose ``detail`` starts ``CSRF Failed`` is the one worth
  repeating.  It comes from CSRF enforcement, before any permission class
  runs, so the caller's roles are not what was refused: fetch a token again
  and resend the request once (see :ref:`api-csrf-bootstrap`).
- ``POST /auth/login`` answers **400** for wrong credentials (``{"detail":
  "Incorrect email address or password."}``) and **403** for a known but
  deactivated account.  It is an authentication endpoint; a 401 from it would
  be ambiguous with "your session expired".
- ``POST /payments/stripe/confirm``, ``/payments/paypal/capture`` and
  ``/payments/mock/complete`` answer **404** for a payment that is not yours.
  They look the payment up filtered by ``user=request.user``, so somebody
  else's payment does not exist as far as the caller is concerned — a 403
  would confirm that the id is real.
- ``POST /payments/mock/complete`` answers **404**, not 403, when
  ``PAYMENTS_MOCK_ENABLED`` is off.  The route exists but does not advertise
  itself in production.

Pagination
----------

Every paginated list uses ``caldart.pagination.StandardPagination``:

.. list-table::
   :header-rows: 1
   :widths: 26 74

   * - Parameter
     - Meaning
   * - ``page``
     - 1-based page number; past the end is a 404
   * - ``page_size``
     - default **25**, maximum **200**; a larger value is clamped

The envelope is DRF's standard::

    {"count": 137, "next": "…?page=3", "previous": "…?page=1", "results": [ … ]}

Five endpoints are deliberately **unpaginated** and return a bare JSON array,
because the whole list is small and bounded: ``GET /darts``, ``GET /plans``,
``GET /roles``, ``GET /leader/search`` (hard-capped at 20 results) and
``GET /system/backups``.  ``GET /me/membership`` and ``GET /me/payments``
return whole objects and arrays for the same reason, as does
``GET /admin/payments/summary``.  The CSV and PDF exports stream every matching
row and ignore ``page`` entirely.

Filtering, search and ordering
------------------------------

``DEFAULT_FILTER_BACKENDS`` is ``DjangoFilterBackend``, ``OrderingFilter`` and
``SearchFilter``, and most list endpoints use them with a ``filterset_class``.
Two do not, for reasons worth knowing:

- ``GET /admin/members`` uses a custom ``MemberOrderingFilter`` because its
  sort keys are computed annotations rather than columns (see
  :ref:`membership-status-sql`).
- ``GET /admin/payments`` switches the backends off entirely and filters by
  hand, because its date filtering keys off a ``paid_at`` annotation —
  ``Coalesce(completed_at, created_at)`` — that the list, the summary and the
  CSV export all share, so the three can never disagree about when a payment
  happened.

``?ordering=`` takes a field name, optionally ``-`` prefixed for descending.
Endpoints differ in how strict they are: ``/admin/payments`` **rejects** an
unknown field with 400 ``{"ordering": "Cannot order by 'x'."}``, while
``/admin/members`` and the aircraft list silently ignore one.  Both aircraft
and member orderings force ``NULL`` to the end in both directions, and the
aircraft list appends the primary key as a tiebreaker so paging a non-unique
sort cannot repeat or skip rows.

Error shape
-----------

Errors are DRF-standard JSON.  Field errors are keyed by field name with a
list of messages; non-field errors use ``detail`` or ``non_field_errors``:

.. code-block:: json

   {"email": ["An account already uses that email address. Sign in, or reset your password."]}

.. code-block:: json

   {"detail": "You do not have permission to perform this action."}

Validation failures are **400**, permission failures **403**, missing objects
**404**, and a method a view does not implement **405** (several detail views
restrict ``http_method_names``, so ``PUT`` where only ``PATCH`` is offered is a
405 rather than a silent full replace).

Two endpoints return a bare dict rather than the standard envelope:
``GET /aircraft/lookup`` and ``GET /leader/aircraft`` answer a missing or
unparseable registration with ``{"n_number": "Enter a registration, for example
N12345."}``.

Throttling
----------

There is no project-wide throttle.  Three anonymous auth endpoints are rate
limited by client IP address, with the rates read from the environment:

.. list-table::
   :header-rows: 1
   :widths: 34 26 40

   * - Endpoint
     - Scope
     - Variable (default)
   * - ``POST /auth/login``
     - ``auth_login``
     - ``AUTH_THROTTLE_LOGIN`` (``20/min``)
   * - ``POST /auth/register``
     - ``auth_register``
     - ``AUTH_THROTTLE_REGISTER`` (``10/hour``)
   * - ``POST /auth/password/reset`` and ``…/reset/confirm``
     - ``auth_password_reset``
     - ``AUTH_THROTTLE_PASSWORD_RESET`` (``10/hour``)

Setting a rate to empty turns that throttle off; the test settings do exactly
that for all three.  The classes subclass ``AnonRateThrottle`` but override
``get_cache_key`` so they bucket by address even for an authenticated caller —
registration signs the new account in, and every request after the first would
otherwise go uncounted.  Exceeding a rate is **429**.

Roles
-----

Roles are Django groups whose name is the slug (see :doc:`data-model`).  Two
rules govern every gate in the matrix below:

- **``system_admin`` passes every role check.**  ``user_has_any_role`` returns
  true for it before looking at the required list.
- **A Django superuser passes every role check too**, by the same
  short-circuit.  The one exception is ``AdminUserSerializer.validate_roles``,
  which asks ``has_role("system_admin")`` directly, so granting or revoking the
  ``system_admin`` role needs the role itself and not merely ``is_superuser``.
- **Neither passes an ownership check.**  ``POST /payments/stripe/confirm``,
  ``POST /payments/paypal/capture`` and ``POST /payments/mock/complete`` look
  the payment up filtered by ``user=request.user``, so they confirm only the
  caller's own payment, whatever roles the caller holds; anyone else's is a
  **404**.

Views declare their gates with the permission classes in
``apps/accounts/permissions.py``.  ``HasRole(slug)`` and ``HasAnyRole(*slugs)``
are factories that return a DRF permission class; ``IsUserAdmin``,
``IsAccountAdmin`` and ``IsSystemAdmin`` are ready-made ones, and
``HasAnyRole(DART_LEADER, ACCOUNT_ADMIN)`` guards the leader check.  Every one
of them runs its test through ``user_has_any_role``, so an anonymous caller
always fails and the two rules above always hold.  Object-level rules, such
as who may edit an aircraft record, are separate classes in the owning app
(``apps/aircraft/api/permissions.py``).

``website_admin`` grants **no API endpoint at all**.  It exists to give its
holder Wagtail admin permissions, which are enforced by Wagtail, not by DRF.

.. _api-permission-matrix:

Permission matrix
=================

Who may call what.  ``·`` means no access, ✓ means access.  ``system_admin``
is omitted from the columns because it passes every row except the three
payment-confirmation rows, which are owner-only for everybody.

*Anonymous* means no session at all; anything it cannot reach answers **401**.

.. list-table::
   :header-rows: 1
   :widths: 34 10 10 10 10 10 16

   * - Endpoint
     - anon
     - member
     - dart_leader
     - user_admin
     - account_admin
     - Notes
   * - ``GET /auth/csrf``
     - ✓
     - ✓
     - ✓
     - ✓
     - ✓
     - 204, sets the cookie
   * - ``POST /auth/register``
     - ✓
     - ✓
     - ✓
     - ✓
     - ✓
     - throttled; signs the caller in
   * - ``POST /auth/login``
     - ✓
     - ✓
     - ✓
     - ✓
     - ✓
     - throttled
   * - ``POST /auth/logout``
     - ✓
     - ✓
     - ✓
     - ✓
     - ✓
     - 204 even when anonymous
   * - ``GET /auth/me``
     - ·
     - ✓
     - ✓
     - ✓
     - ✓
     -
   * - ``POST /auth/password/change``
     - ·
     - ✓
     - ✓
     - ✓
     - ✓
     - keeps the session alive
   * - ``POST /auth/password/reset``
     - ✓
     - ✓
     - ✓
     - ✓
     - ✓
     - always 204, throttled
   * - ``POST /auth/password/reset/confirm``
     - ✓
     - ✓
     - ✓
     - ✓
     - ✓
     - throttled
   * - ``GET /roles``
     - ·
     - ✓
     - ✓
     - ✓
     - ✓
     - any signed-in caller
   * - ``GET /admin/users``
     - ·
     - ·
     - ·
     - ✓
     - ·
     -
   * - ``GET | PATCH /admin/users/{id}``
     - ·
     - ·
     - ·
     - ✓
     - ·
     - ``PUT`` → 405
   * - ``POST /admin/users/{id}/send-password-reset``
     - ·
     - ·
     - ·
     - ✓
     - ·
     -
   * - ``GET /darts``, ``GET /plans``
     - ✓
     - ✓
     - ✓
     - ✓
     - ✓
     - public, unpaginated, active only
   * - ``GET /site/config``
     - ✓
     - ✓
     - ✓
     - ✓
     - ✓
     - ``members_pages`` gated on content access
   * - ``GET | PUT | PATCH /me/profile``
     - ·
     - ✓
     - ✓
     - ✓
     - ✓
     - always your own; ``PUT`` genuinely replaces
   * - ``POST /me/profile/aircraft``
     - ·
     - ✓
     - ✓
     - ✓
     - ✓
     - 200 with the new list
   * - ``DELETE /me/profile/aircraft/{id}``
     - ·
     - ✓
     - ✓
     - ✓
     - ✓
     - 204 even if never attached
   * - ``GET /me/membership``, ``GET /me/payments``
     - ·
     - ✓
     - ✓
     - ✓
     - ✓
     -
   * - ``GET | POST /admin/members``
     - ·
     - ·
     - ·
     - ·
     - ✓
     -
   * - ``GET | PATCH | DELETE /admin/members/{id}``
     - ·
     - ·
     - ·
     - ·
     - ✓
     - ``PUT`` → 405; delete is a hard delete
   * - ``POST /admin/members/{id}/memberships``
     - ·
     - ·
     - ·
     - ·
     - ✓
     - grants a term
   * - ``PATCH /admin/memberships/{id}``
     - ·
     - ·
     - ·
     - ·
     - ✓
     - only ``ends_on``, ``status``, ``note``
   * - ``GET /admin/members/export.{csv,pdf}``
     - ·
     - ·
     - ·
     - ·
     - ✓
     -
   * - ``GET | POST /aircraft``
     - ·
     - ✓
     - ✓
     - ✓
     - ✓
     - any member may add an airframe
   * - ``GET /aircraft/lookup``
     - ·
     - ✓
     - ✓
     - ✓
     - ✓
     - ``pilots`` only for leaders/admins
   * - ``GET /aircraft/{id}``
     - ·
     - ✓
     - ✓
     - ✓
     - ✓
     - ``pilots`` only for leaders/admins
   * - ``PATCH | PUT /aircraft/{id}``
     - ·
     - creator
     - creator
     - creator
     - ✓
     - object-level
   * - ``DELETE /aircraft/{id}``
     - ·
     - ·
     - ·
     - ·
     - ✓
     - never the creator alone
   * - ``GET /admin/aircraft/export.{csv,pdf}``
     - ·
     - ·
     - ·
     - ·
     - ✓
     - not ``dart_leader``
   * - ``GET /leader/search``
     - ·
     - ·
     - ✓
     - ·
     - ✓
     - param is ``q``; max 20
   * - ``GET /leader/members/{id}/status``
     - ·
     - ·
     - ✓
     - ·
     - ✓
     -
   * - ``GET /leader/aircraft``
     - ·
     - ·
     - ✓
     - ·
     - ✓
     - always includes ``pilots``
   * - ``GET /payments/config``
     - ·
     - ✓
     - ✓
     - ✓
     - ✓
     - signed-in only
   * - ``POST /payments/checkout``
     - ·
     - ✓
     - ✓
     - ✓
     - ✓
     - server recomputes the total
   * - ``POST /payments/stripe/confirm``
     - ·
     - owner
     - owner
     - owner
     - owner
     - owner only, whatever the role; 404 for anyone else's
   * - ``POST /payments/paypal/capture``
     - ·
     - owner
     - owner
     - owner
     - owner
     - owner only, whatever the role; 404 for anyone else's
   * - ``POST /payments/mock/complete``
     - ·
     - owner
     - owner
     - owner
     - owner
     - owner only, whatever the role; 404 unless ``PAYMENTS_MOCK_ENABLED``
   * - ``GET /payments/{id}``
     - ·
     - owner
     - owner
     - owner
     - ✓
     - 403 for a non-owner without the role
   * - ``POST /payments/{stripe,paypal}/webhook``
     - ✓
     - ✓
     - ✓
     - ✓
     - ✓
     - unauthenticated; signature is the gate
   * - ``GET /admin/payments``
     - ·
     - ·
     - ·
     - ·
     - ✓
     -
   * - ``GET /admin/payments/summary``
     - ·
     - ·
     - ·
     - ·
     - ✓
     - succeeded payments only
   * - ``GET /admin/payments/export.csv``
     - ·
     - ·
     - ·
     - ·
     - ✓
     - all statuses
   * - ``GET /admin/reminders/log``
     - ·
     - ·
     - ·
     - ·
     - ✓
     - also ``system_admin``
   * - ``POST /system/reminders/run``
     - ·
     - ·
     - ·
     - ·
     - ·
     - ``system_admin`` only
   * - ``GET /system/health``
     - ·
     - ·
     - ·
     - ·
     - ·
     - ``system_admin`` only
   * - ``GET | POST /system/backups``
     - ·
     - ·
     - ·
     - ·
     - ·
     - ``system_admin`` only
   * - ``GET /system/backups/{name}/download``
     - ·
     - ·
     - ·
     - ·
     - ·
     - ``system_admin`` only

Reading the matrix:

**"creator"**
    ``AircraftPermission`` allows a write when ``obj.created_by`` is the
    caller.  A record whose ``created_by`` is ``NULL`` — imported or seeded —
    is administrator-only.  ``DELETE`` is never granted to the creator, only to
    ``account_admin``.

**"owner"**
    The payment's ``user`` is the caller.  On the three confirm endpoints
    that is enforced by filtering the lookup, so a non-owner gets **404**; on
    ``GET /payments/{id}`` it is an object permission that also admits
    ``account_admin``, so a non-owner without that role gets **403**.

**Serializer switching on aircraft.**  ``GET /aircraft/{id}`` and
``GET /aircraft/lookup`` return the ``pilots`` array — other members' names,
emails, membership state and medical currency — only to ``dart_leader``,
``account_admin`` or ``system_admin``.  Plain members get the aeroplane alone.
``GET /aircraft`` (the list) never includes it for anybody.  That is what stops
the register from being a way around the leader-check gate.

**Restricted methods.**  ``/admin/users/{id}`` accepts ``GET`` and ``PATCH``;
``/admin/members/{id}`` accepts ``GET``, ``PATCH`` and ``DELETE``;
``/admin/memberships/{id}`` accepts ``PATCH`` only.  Everything else on those
paths is 405.

Endpoints without a page of their own
=====================================

.. _api-reminders-system:

Reminders and system
--------------------

.. code-block:: text

   GET  /admin/reminders/log?kind=&from=&to=&search=&ordering=
        → paginated {id, user_id, user_name, membership_id, kind, sent_at, to_email}
   POST /system/reminders/run   {dry_run: bool}   → 200 {sent, skipped}
   GET  /system/health   → {db, pending_migrations, disk_free_mb, last_backup,
                            version, debug}
   GET  /system/backups  → [{name, size_bytes, created_at}]
   POST /system/backups  → 201 {name, size_bytes, created_at}
   GET  /system/backups/{name}/download   → application/gzip

``kind`` is one of ``t60``, ``t30``, ``t7``, ``expired``, ``post30``.  ``from``
and ``to`` compare against ``sent_at__date``; ``from`` is injected into the
filterset after class creation because it is a Python keyword.  Ordering is
over ``sent_at`` and ``kind``, defaulting to newest first.

The download route is declared with ``<path:name>`` rather than ``<str:name>``
on purpose, so a traversal attempt reaches the view and is rejected there with
a message, instead of 404ing at the URL resolver where no test could tell it
from a typo.  ``resolve_backup`` requires the name to match
``^[A-Za-z0-9][A-Za-z0-9._-]*\.sql\.gz$`` **and** re-checks that the resolved
path's parent is exactly ``BACKUP_DIR``, which defeats ``..``, absolute paths
and symlinks out of the directory.

**Restore is deliberately absent from the API.**  Wiping the database is not
something to do from a browser tab; it is ``manage.py db_restore``.  See
:doc:`backup-restore`.

Site config
-----------

.. code-block:: text

   GET /site/config → {org_name, theme, contact_email, nav, members_pages}

The one call the SPA makes before it has a user, so it is ``AllowAny``.  ``nav``
entries carry a ``kind`` of ``page`` or ``portal``, which is how the public
templates render content pages as links and Join / Members as buttons.
``members_pages`` is populated only when the caller passes the same
``can_access_members_content`` test the members-only wall uses; everyone else
gets an empty list rather than a 403.  See :doc:`cms`.

Testing the API
===============

Every endpoint has role-matrix coverage — allow *and* deny — in
``backend/tests/``.  ``conftest.py`` provides an ``api_client`` fixture, one
user fixture per role (``member``, ``dart_leader``, ``user_admin``,
``account_admin``, ``website_admin``, ``system_admin``) and an
``all_role_users`` dict keyed by slug, so a new endpoint's permission test is a
short parametrized loop over the roles that should pass and the roles that
should not.  See :doc:`testing`.
