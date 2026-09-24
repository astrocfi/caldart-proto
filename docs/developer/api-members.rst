===========================
API: members administration
===========================

The ``account_admin`` half of the members app, endpoint by endpoint, plus the
membership-status rules the list filters on.  The exports these
endpoints serve are described in :doc:`reports`.

Every route below requires the ``account_admin`` role.  ``system_admin``
passes every role check, so a system administrator has them too.  An
unauthenticated request gets **401** (``caldart.exceptions`` overrides DRF's
403 for session auth); an authenticated request without the role gets **403**.
An unsafe method with no ``X-CSRFToken`` gets **403** before either check,
signed in or not.  Those two answers are the same on every endpoint here and
are not repeated in the status lists below.

The code lives in ``backend/apps/members/``:

``api/admin_views.py``
   The views.
``api/admin_serializers.py``
   Request and response shapes.  The profile, term, and payment serializers
   extend the member-facing ones in ``api/profile_serializers.py``, so an
   administrator and a member see one definition of a profile and one set of
   validation rules.
``api/serializers.py``
   The two shapes more than one app returns: ``MembershipStatusSerializer``
   over the dict ``services.membership_status`` builds, and ``PlanSerializer``
   over a ``MembershipPlan``.  The accounts, members, and payments APIs all
   import them from here.
``api/admin_filters.py``
   The filter set, the ordering backend, and the queryset the list is served
   from.  The membership annotations it builds on live in ``services.py``.
``services.py``
   The member record itself: ``register_member``, ``create_member``
   , ``update_member``, and ``delete_member`` own the rules the endpoints below
   state, and the account half of each goes to ``accounts.services``.  The
   membership status and ``activate_term`` live here too.
``api/actors.py``
   ``acting_user(request)``, the signed-in account behind a request every
   view here has already gated on a role.
``api/admin_urls.py``
   Routes, included from ``api/urls.py``.
``reports.py``
   The CSV and PDF column list.


Endpoints
=========

::

  GET    /api/v1/admin/members
  POST   /api/v1/admin/members
  GET    /api/v1/admin/members/{user_id}
  PATCH  /api/v1/admin/members/{user_id}
  DELETE /api/v1/admin/members/{user_id}
  POST   /api/v1/admin/members/{user_id}/memberships
  PATCH  /api/v1/admin/memberships/{id}
  GET    /api/v1/admin/members/export.csv
  GET    /api/v1/admin/members/export.pdf

``{user_id}`` is the **user's** id, not a profile id.  Everyone in the user
table is listed: ``member`` is granted at registration, so accounts and members
are one population, and ``?role=`` narrows it.


``GET /admin/members``
======================

The member table, filtered, ordered, and paginated with the project's standard
``?page=&page_size=`` (25 rows by default, 200 at most).

.. code-block:: json

   {
     "count": 47,
     "next": "http://localhost:8000/api/v1/admin/members?page=2",
     "previous": null,
     "results": [
       {
         "user_id": 11,
         "name": "Ana Bracco",
         "email": "ana@example.org",
         "phone": "415-555-0100",
         "dart": "Palo Alto",
         "is_active": true,
         "membership": {
           "status": "current",
           "expires_on": "2027-05-23",
           "plan": "Annual",
           "is_lifetime": false
         },
         "pilot_certificate_type": "private",
         "medical_type": "third",
         "medical_expiration": "2027-01-31",
         "medical_is_current": true,
         "aircraft": ["N172SP"],
         "joined_on": "2024-07-01"
       }
     ]
   }

The row is ``MemberRow`` in ``frontend/src/portal/api/types.ts``.
``joined_on`` is the start of the earliest membership term, or ``null`` for
somebody who has never had one.  An account with no ``MemberProfile`` row still
appears: ``phone`` is blank, ``dart``, and ``medical_expiration`` are ``null``
, ``pilot_certificate_type``, and ``medical_type`` read ``none``,
``medical_is_current`` is false and ``aircraft`` is empty.

Statuses:

* **200** — the page of rows, empty ``results`` when nothing matches.
* **400** — ``status``, ``certificate``, ``medical``, or ``role`` carried a
  value outside its choice list, or ``expiring_within`` was not a number.  The
  body is keyed on the offending parameter, for example
  ``{"status": ["Select a valid choice. bogus is not one of the available
  choices."]}``.

Filters
-------

``search``
   Case-insensitive substring of the full name, the email address, either
   phone number, or the pilot certificate number.  The full name is matched as
   one string, so ``Ana Bracco`` works.
``status``
   ``current`` | ``new`` | ``expired`` | ``none``.  The four partition the
   table.  ``new`` is a member whose only term is unpaid.
``certificate``
   A ``pilot_certificate_type`` value: ``none``, ``student``, ``sport``,
   ``recreational``, ``private``, ``commercial``, ``atp``; or ``licensed``,
   which is every certificate a pilot may act on alone -- the five from
   ``sport`` upward, and neither ``student`` nor ``none``.
``medical``
   A ``medical_type`` value: ``none``, ``basicmed``, ``first``, ``second``,
   ``third``; or ``any``, which is every account holding a medical of any
   class.  An account with no profile row holds none, so ``any`` leaves it
   out.
``dart``
   A DART id, or a case-insensitive substring of a DART name.
``role``
   A role slug.  This matches the group actually assigned, so ``role=member``
   does not include a system administrator who lacks the ``member`` group.
``expiring_within``
   A number of days.  Selects current members whose computed expiry falls on
   or before ``today + N``.  Lifetime members are never matched.  ``N`` is
   clamped to ``0..3650`` (ten years): a negative value behaves like ``0``,
   and a value past the limit like the limit, so an oversized or negative
   query string never produces a server error.
``is_active``
   ``true`` or ``false``.  A value that is neither — ``?is_active=maybe`` —
   narrows nothing rather than being refused.

Ordering
--------

``?ordering=`` takes ``pilot``, ``name``, ``email``, ``dart``, ``expires_on``
or ``joined``, each optionally prefixed with ``-``.  ``name`` expands to
surname, forename, email; ``pilot`` ranks a current medical ahead of a lapsed
one ahead of a non-pilot, which is the order the list's Pilot column reads in.
The two date sorts, and ``dart``, keep rows with no value at the end in both
directions, so lifetime members do not crowd out the answer to "who expires
next".  Anything
else falls back to ``name`` rather than being refused.


Computed membership status
==========================

``members.services.membership_status`` is the single source of truth for "is
this person a current member".  It works in Python: it finds the term covering
today and then walks forward through terms that start no later than the day
after the previous one ends, so an early renewal shows the new expiry
immediately.

The admin list has to *filter* and *order* on that, which Python cannot do
before pagination.  ``members.services.membership_annotations`` therefore
states the same rules as correlated subqueries on the user queryset:

``covers_today``
   ``EXISTS`` an active term with ``starts_on <= today`` and ``ends_on``
   either null or ``>= today``.  This is what ``?status=current`` filters on.
``has_started_term``
   ``EXISTS`` a term with ``starts_on <= today`` that is neither canceled nor
   ``new``.  Paired with ``covers_today`` it separates the other statuses: not
   covering but started is ``expired``.
``has_unpaid_term`` / ``unpaid_end`` / ``unpaid_plan``
   ``EXISTS`` a term stored as ``new``, and its end date and plan.  A row that
   covers nothing and has started nothing, but holds one of these, is ``new``:
   the member joined and has not paid.  With none of them it is ``none``.
``coverage_end`` / ``coverage_plan``
   The earliest active term ending on or after today that **no** other active
   term continues — where "continues" means starting no later than
   ``ends_on + 1 day`` and reaching further — and that term's plan name.
   Terms inside the chain always have a continuation, and terms after a gap
   always end later, so the earliest such boundary is exactly where the Python
   walk stops.  ``NULL`` means the chain reaches a lifetime term, or that
   nothing covers today.
``lifetime_plan``
   The plan name of an active term with no end date, read instead of
   ``coverage_plan`` when ``coverage_end`` is ``NULL`` — because a lifetime
   member has no boundary row to take a name from.
``past_end`` / ``past_plan``
   The most recent non-canceled term that has started, reported when nothing
   covers today.
``joined_on``
   The earliest term's ``starts_on``.

``member_admin_queryset`` hangs those on the user table through
``members.services.with_membership`` and adds the two the list needs of its
own, in ``api/admin_filters.derived_annotations()``:

``full_name``
   ``first_name`` and ``last_name`` concatenated, so ``?search=`` can match a
   full name in one ``icontains``.
``effective_expiry``
   ``coverage_end`` when ``covers_today``, else ``past_end``.  This is the
   column ``?ordering=expires_on`` actually sorts on, with ``NULL`` — lifetime
   members and people who never joined — forced to the end in both directions.

``members.services.membership_payload(user)`` reads those annotations back into
the ``membership_status`` dictionary, and the whole page costs one query.
``membership_of(user)`` is the reader for code that cannot be sure how the row
was fetched: it takes the annotations when they are present and calls
``membership_status`` when they are not.

Every list that shows a membership status is served this way — ``GET
/admin/members``, ``GET /admin/users`` (see :doc:`api-auth`), the leader search
and the ``pilots`` on an aircraft record (see :doc:`api-aircraft`) — so none of
them costs a query per row.  ``backend/tests/test_membership_query_counts.py``
drives each of them at three rows and at twenty and pins the count, which is
the same at both.

Two implementations of one rule can drift, so
``backend/tests/test_members_admin_status.py`` builds fourteen histories —
early renewals, three-term chains, gaps, overlaps, cancellations, a lifetime
plan bought to follow an annual one, a term ending exactly today — and asserts
the SQL and the service agree on every one.  **Change one and you must change
the other**; that test is what tells you.


``POST /admin/members``
=======================

Creates an account and its profile in one request, and answers with the full
member record ``GET /admin/members/{user_id}`` returns.

.. code-block:: json

   {
     "email": "nova@example.org",
     "first_name": "Nova",
     "last_name": "Ito",
     "password": "optional",
     "profile": {"phone": "408-555-0199", "dart_id": 3, "ratings": ["instrument"]}
   }

Only ``email`` is required — an administrator records what they were told,
which on the day somebody joins at an airshow may be no more than a name.

``profile`` is ``AdminProfileSerializer``, which extends the ``/me/profile``
serializer: the same fields (``dart`` reads nested and is written as
``dart_id``), the same rules — a two-letter state, a well-formed ZIP code, an
expiry date whenever a medical class is given, a number whenever a certificate
is — plus ``notes`` and ``how_heard``, and nothing mandatory.

The user is granted the ``member`` role and given an empty ``MemberProfile``
populated from ``profile``.  With no ``password`` the account gets an unusable
password and ``apps.accounts.services.send_password_invitation`` emails an
invitation whose subject is ``<organization name>: set your password``.  It
renders
``templates/emails/member_invitation.{txt,html}`` from the same context as the
reset email — organization name and contact address from Wagtail's site
settings, link expiry from ``PASSWORD_RESET_TIMEOUT`` in whole days — and its
link is ``build_reset_url``'s, so the portal posts it
back to ``/auth/password/reset/confirm`` unchanged (:doc:`api-auth`).  The mail
is queued with ``transaction.on_commit``, so a failed create never sends one —
and a test has to use ``django_capture_on_commit_callbacks`` to see it.

Statuses:

* **201** — the member record, in the detail shape below.
* **400** — a duplicate email address (compared case-insensitively, reported as
  ``{"email": ["An account with that email address already exists."]}``), a
  missing ``email``, a password one of Django's validators refused, an unknown
  rating, or any profile rule the nested serializer states.  Nothing is
  written.


``GET /admin/members/{user_id}``
================================

The whole record: the account, its roles, the computed membership, the profile
*including* ``notes`` and ``how_heard``, every membership term newest first,
and every payment newest first.

.. code-block:: json

   {
     "id": 11,
     "email": "ana@example.org",
     "first_name": "Ana",
     "last_name": "Bracco",
     "name": "Ana Bracco",
     "is_active": true,
     "roles": ["member"],
     "created_at": "2024-07-01T16:04:11.318204-07:00",
     "joined_on": "2024-07-01",
     "membership": {
       "status": "current",
       "expires_on": "2027-05-23",
       "plan": "Annual",
       "is_lifetime": false
     },
     "profile": {
       "phone": "415-555-0100",
       "phone_extension": "",
       "phone_alt": "",
       "phone_alt_extension": "",
       "address_line1": "1 Embarcadero",
       "address_line2": "",
       "city": "San Carlos",
       "state": "CA",
       "postal_code": "94070",
       "county": "San Mateo",
       "emergency_contact_name": "Dana Lee",
       "emergency_contact_phone": "650-555-0199",
       "emergency_contact_phone_extension": "",
       "home_airport_identifier": "SQL",
       "home_airport_city": "San Carlos",
       "dart": {"id": 3, "name": "Palo Alto"},
       "air_care_alliance_number": "",
       "pilot_certificate_type": "private",
       "certificate_number": "3141592",
       "ifr_rated": "yes",
       "ratings": ["instrument"],
       "medical_type": "third",
       "medical_expiration": "2027-01-31",
       "medical_is_current": true,
       "flight_review_date": null,
       "total_hours": 750,
       "aircraft": [
         {
           "id": 7,
           "n_number": "N172SP",
           "make": "Cessna",
           "model": "172S Skyhawk",
           "insurance_is_current": true,
           "insurance_expiration": "2027-03-01",
           "insurance_summary": "$1,000,000 / $100,000 · exp 2027-03-01"
         }
       ],
       "vol_ground_team": false,
       "vol_exercise_training": false,
       "vol_member_support": false,
       "vol_fundraising": false,
       "vol_social_media": false,
       "vol_newsletter": false,
       "notes": "Joined at the Palo Alto airshow.",
       "how_heard": "Airshow"
     },
     "memberships": [
       {
         "id": 12,
         "plan": "Annual",
         "plan_slug": "annual",
         "starts_on": "2026-05-24",
         "ends_on": "2027-05-23",
         "status": "active",
         "source": "payment",
         "note": "",
         "granted_by": null,
         "payment": 31,
         "created_at": "2026-05-20T18:22:05.601884-07:00"
       }
     ],
     "payments": [
       {
         "id": 31,
         "plan": "Annual",
         "amount_cents": 6500,
         "plan_amount_cents": 4500,
         "contribution_cents": 2000,
         "currency": "usd",
         "provider": "stripe",
         "wallet": "unknown",
         "provider_ref": "pi_3Q1example",
         "status": "succeeded",
         "created_at": "2026-05-20T18:21:40.114905-07:00",
         "completed_at": "2026-05-20T18:22:05.601884-07:00"
       }
     ]
   }

``profile`` is ``null`` for an account that has no ``MemberProfile`` row.
Datetimes are rendered in the server's configured ``TIME_ZONE``, so they carry
an offset rather than a trailing ``Z``.
``source`` is ``payment``, ``manual``, or ``seed``; ``granted_by`` is the
display name of the administrator behind a manual grant and ``null``
otherwise; ``payment`` is the id of the payment that bought the term, or
``null``.

Statuses:

* **200** — the record above.
* **404** — no account has that id.


``PATCH /admin/members/{user_id}``
==================================

Edits the account and its profile together, and answers with the whole record
however few fields the request carried.

.. code-block:: json

   {
     "email": "ana.bracco@example.org",
     "is_active": true,
     "profile": {"medical_type": "basicmed", "notes": "Moved to BasicMed."}
   }

The body takes ``email``, ``first_name``, ``last_name``, ``is_active``, and a
partial ``profile`` object.  A profile is created if the account somehow has
none.  ``PUT`` is not offered.

The nested profile serializer is bound to the stored row before validation, so
a partial update is judged against the whole profile: sending only
``medical_type`` does not trip the "a medical class needs an expiry date" rule
when the record already has one.

``email`` and ``is_active`` go through the same account-edit guard as
``PATCH /admin/users/{id}`` — see :ref:`account-edit-guard`.  An account
administrator may move a plain member's address, but not the address or the
active flag of an account holding a role they do not hold themselves, and may
not deactivate their own account.  A refusal is a **400** keyed on ``email`` or
``is_active``, and nothing is written at all — the profile half of the same
request included.

Deactivation — ``PATCH`` with ``is_active`` false — is the tool for a member
who has left.  The hard delete below is for accounts that never paid:
duplicates, spam, and test accounts.

Statuses:

* **200** — the updated record, in the detail shape above.
* **400** — an email address another account already holds, a profile rule the
  nested serializer refused, or an edit the account-edit guard refused.
  Nothing is written.
* **404** — no account has that id.
* **405** — the request used ``PUT``.


``DELETE /admin/members/{user_id}``
===================================

Hard-deletes the account: the cascade takes the profile and the membership
terms with it, and the audit log is the only trace left.  There is no response
body.

The delete is refused when

* the target is the caller — you cannot delete your own account, whatever roles
  you hold;
* the target is a ``system_admin``, unless the caller is a ``system_admin``; or
* the target has any payment.

The two role tests read *effective* roles, so a Django superuser without the
role group counts as a system administrator on either side.  They are applied
in that order, so an administrator who has paid is told they cannot delete
themselves rather than told about their payments.

The payment guard keeps the financial record: a payment is revenue or a
donation, and the accounts must not change after the fact.  It counts every
payment, ``pending``, and ``failed`` rows included, and the ``detail`` reads::

   Ana Bracco has 3 payment records, which must be kept. Deactivate the account instead.

with ``payment record`` singular for a count of one.  Nothing is written — the
payments, the profile and the membership terms are all still there afterwards.

``Payment.user`` is ``PROTECT`` (:doc:`data-model`), so the protection is on
the foreign key rather than on this view alone: the Django admin, a management
command and a shell session all raise ``ProtectedError`` instead of cascading.
The view catches that error and answers with the same **403**.

Statuses:

* **204** — the account is gone, with an empty body.
* **403** — one of the three refusals, as ``{"detail": "..."}``.  The sentences
  are "You cannot delete your own account.", "Only a system administrator can
  delete a system administrator." and the payment sentence above.
* **404** — no account has that id.


``POST /admin/members/{user_id}/memberships``
=============================================

Grants a membership term by hand — the endpoint behind "Grant a term" on the
member record — and records the grant in the audit log.

.. code-block:: json

   {"plan": "annual", "starts_on": null, "note": "Check 1041"}

``plan`` is a ``MembershipPlan`` slug and must be an active plan.
``starts_on`` and ``note`` are optional.  The term is created through
``members.services.activate_term`` with ``source="manual"`` and ``granted_by``
set to the caller, so a manual grant is placed by the same rule a payment is.

With no ``starts_on``, that rule reads the largest ``ends_on`` across the
member's **active** terms — terms whose stored status is ``expired`` or
``canceled`` are ignored:

* if one of those active terms is a lifetime term, and so has no end date, the
  grant starts **today**;
* otherwise, if the largest end date is today or later, the grant starts the
  **day after** it.  A term dated in the future therefore moves the start even
  though it is not covering the member today: granting an annual term to
  somebody whose term runs from next month to next spring starts the new one
  the day after next spring;
* otherwise — every term has run out, or there are none — the grant starts
  **today**.

``ends_on`` is then ``starts_on + duration_days - 1``, or ``null`` for a
lifetime plan.  Passing ``starts_on`` overrides the whole rule and the end date
is measured from the date given.

.. code-block:: json

   {
     "id": 18,
     "plan": "Annual",
     "plan_slug": "annual",
     "starts_on": "2027-05-24",
     "ends_on": "2028-05-23",
     "status": "active",
     "source": "manual",
     "note": "Check 1041",
     "granted_by": "Rae Okonkwo",
     "payment": null,
     "created_at": "2026-09-21T19:40:02.750311-07:00"
   }

Statuses:

* **201** — the granted term, in the shape above.
* **400** — ``plan`` missing, unknown, or naming a plan that is not active.
* **404** — no account has that ``user_id``.


``PATCH /admin/memberships/{id}``
=================================

Corrects a term that is already on file.  Only ``ends_on``, ``status``, and
``note`` are writable: the plan, the start date, the source and the payment
link are read-only, because rewriting them would falsify the history rather
than correct it.

.. code-block:: json

   {"ends_on": "2028-06-30", "status": "active", "note": "Extended by one month."}

Setting ``status`` to ``canceled`` removes the term from the membership
calculation while leaving the row in place.  The response is the term in the
same shape the grant endpoint returns, and the audit log records which fields
the correction actually changed.

Statuses:

* **200** — the corrected term.
* **400** — ``ends_on`` would fall before ``starts_on``, reported as
  ``{"ends_on": ["The end date cannot be before the start date."]}``, or
  ``status`` carried a value outside ``active``, ``expired``, and ``canceled``.
* **404** — no term has that id.
* **405** — the request used ``PUT``, ``GET``, or ``DELETE``.


``GET /admin/members/export.csv``
=================================

The filtered member list as a CSV download, streamed through
``caldart.reports.csv_response`` so a report over the entire member table never
materializes in memory.  It takes **every filter and ordering parameter the
list takes** and applies them to the whole result set — the export is not
paginated.  Columns, style, and how to add one: :doc:`reports`.

Statuses:

* **200** — ``text/csv``, with a ``Content-Disposition`` filename carrying
  today's date.
* **400** — the same filter refusals as the list.


``GET /admin/members/export.pdf``
=================================

The same rows as the CSV, rendered as a landscape-letter table with the
applied filters printed under the title.

Statuses:

* **200** — ``application/pdf``, with a ``Content-Disposition`` filename
  carrying today's date.
* **400** — the same filter refusals as the list.


Tests
=====

``backend/tests/test_members_admin.py``
   The role matrix on every endpoint (401 anonymous, 403 for ``member``,
   ``dart_leader``, ``user_admin``, and ``website_admin``, 200 for
   ``account_admin`` and ``system_admin``), every filter against a mixed
   fixture, ordering, creation with and without a password, nested profile
   updates, the delete rules and the grant-term arithmetic.
``backend/tests/test_members_delete_payments.py``
   The payment guard: a refusal for every payment status and its message, the
   payment summary before and after a refusal, the same refusal for a system
   administrator, the delete of a member who never paid, and the
   ``ProtectedError`` the model raises on its own.
``backend/tests/test_members_admin_status.py``
   The SQL annotations against ``membership_status``, and ``membership_of``
   answering the same either way.
``backend/tests/test_member_invitation.py``
   The invitation email: the link with and without a trailing slash on
   ``SITE_URL``, the subject, both bodies, and the mailed link being accepted
   by ``/auth/password/reset/confirm``.
``backend/tests/test_membership_query_counts.py``
   The pinned query count of every list that shows a membership status, at two
   page sizes.
``backend/tests/test_members_reports.py``
   The two exports.
``backend/tests/test_member_services.py``
   ``members.services`` on its own: atomic registration, the invitation sent
   only without a password and only on commit, the two halves of an update, and
   each delete guard.

On the front end, ``frontend/src/portal/features/admin-members/`` holds a test
per page: filters to query parameters, export hrefs, the grant-term form, the
typed delete confirmation, and the Danger zone's explanation for a member whose
payments keep the account.
