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

The code lives in ``backend/apps/members/``:

``api/admin_views.py``
   The views.
``api/admin_serializers.py``
   Request and response shapes, and the invitation email.  The profile, term
   and payment serializers extend the member-facing ones in
   ``api/profile_serializers.py``, so an administrator and a member see one
   definition of a profile and one set of validation rules.
``api/admin_filters.py``
   The filter set, the ordering backend, and the SQL membership annotations.
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


List members
============

``GET /admin/members`` — paginated with the project's standard
``?page=&page_size=`` (25 by default, 200 at most).

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
somebody who has never had one.

Filters
-------

``search``
   Case-insensitive substring of the full name, the email address, either
   phone number, or the pilot certificate number.  The full name is matched as
   one string, so ``Ana Bracco`` works.
``status``
   ``current`` | ``expired`` | ``none``.  The three partition the table.
``certificate``
   A ``pilot_certificate_type`` value: ``none``, ``student``, ``sport``,
   ``recreational``, ``private``, ``commercial``, ``atp``.
``medical``
   A ``medical_type`` value: ``none``, ``basicmed``, ``first``, ``second``,
   ``third``.
``dart``
   A DART id, or a case-insensitive substring of a DART name.
``role``
   A role slug.  This matches the group actually assigned, so ``role=member``
   does not include a system administrator who lacks the ``member`` group.
``expiring_within``
   A number of days.  Selects current members whose computed expiry falls on
   or before ``today + N``.  Lifetime members are never matched.
``is_active``
   ``true`` or ``false``.

Ordering
--------

``?ordering=`` takes ``name``, ``email``, ``expires_on`` or ``joined``, each
optionally prefixed with ``-``.  ``name`` expands to surname, forename, email.
The two date sorts keep rows with no date at the end in both directions, so
lifetime members do not crowd out the answer to "who expires next".  Anything
else falls back to ``name``.


Computed membership status
==========================

``members.services.membership_status`` is the single source of truth for "is
this person a current member".  It works in Python: it finds the term covering
today and then walks forward through terms that start no later than the day
after the previous one ends, so an early renewal shows the new expiry
immediately.

The admin list has to *filter* and *order* on that, which Python cannot do
before pagination.  ``api/admin_filters.membership_annotations`` therefore
states the same rules as correlated subqueries on the user queryset:

``covers_today``
   ``EXISTS`` an active term with ``starts_on <= today`` and ``ends_on``
   either null or ``>= today``.  This is what ``?status=current`` filters on.
``has_started_term``
   ``EXISTS`` a non-cancelled term with ``starts_on <= today``.  Paired with
   ``covers_today`` it separates the other two statuses: not covering but
   started is ``expired``, neither is ``none``.
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
   The most recent non-cancelled term that has started, reported when nothing
   covers today.
``joined_on``
   The earliest term's ``starts_on``.
``full_name``
   ``first_name`` and ``last_name`` concatenated, so ``?search=`` can match a
   full name in one ``icontains``.

One more annotation is derived from those, in ``derived_annotations()``:

``effective_expiry``
   ``coverage_end`` when ``covers_today``, else ``past_end``.  This is the
   column ``?ordering=expires_on`` actually sorts on, with ``NULL`` — lifetime
   members and people who never joined — forced to the end in both directions.

``membership_payload(user)`` reads those annotations back into the
``membership_status`` dictionary, and the whole page costs one query.

Two implementations of one rule can drift, so
``backend/tests/test_members_admin_status.py`` builds fourteen histories —
early renewals, three-term chains, gaps, overlaps, cancellations, a lifetime
plan bought to follow an annual one, a term ending exactly today — and asserts
the SQL and the service agree on every one.  **Change one and you must change
the other**; that test is what tells you.


Create a member
===============

``POST /admin/members``:

.. code-block:: json

   {
     "email": "nova@example.org",
     "first_name": "Nova",
     "last_name": "Ito",
     "password": "optional",
     "profile": {"phone": "408-555-0199", "dart_id": 3, "ratings": ["instrument"]}
   }

Only ``email`` is required — an administrator records what they were told,
which on the day somebody joins at an airshow may be no more than a name.  The
response is the full member record (below) with **201**.

``profile`` is ``AdminProfileSerializer``, which extends the ``/me/profile``
serializer: the same fields (``dart`` reads nested and is written as
``dart_id``), the same rules — a two-letter state, a well-formed ZIP code, an
expiry date whenever a medical class is given, a number whenever a certificate
is — plus ``notes`` and ``how_heard``, and nothing mandatory.

The user is granted the ``member`` role and given an empty ``MemberProfile``
populated from ``profile``.  With no ``password`` the account gets an unusable
password and ``send_password_invitation`` emails a link to
``{SITE_URL}/portal/reset-password?uid=…&token=…``, which the portal posts back
to ``/auth/password/reset/confirm`` (:doc:`api-auth`).  The mail is queued with
``transaction.on_commit``, so a failed create never sends one — and a test has
to use ``django_capture_on_commit_callbacks`` to see it.

**400** on a duplicate email address (compared case-insensitively), a password
that fails Django's validators, or an unknown rating.


Retrieve, update, delete
========================

``GET /admin/members/{user_id}`` returns the whole record: the account, its
roles, the computed membership, the profile *including* ``notes`` and
``how_heard``, every membership term newest first, and every payment.

``PATCH /admin/members/{user_id}`` takes ``email``, ``first_name``,
``last_name``, ``is_active`` and a partial ``profile`` object, and returns the
updated record.  A profile is created if the account somehow has none.  ``PUT``
is not offered (**405**).

The nested profile serializer is bound to the stored row before validation, so
a partial update is judged against the whole profile: sending only
``medical_type`` does not trip the "a medical class needs an expiry date" rule
when the record already has one.

``DELETE /admin/members/{user_id}`` hard-deletes: the cascade takes the
profile, the membership terms and the payments.  It is refused with **403**
when the target is

* the caller — you cannot delete your own account, whatever roles you hold; or
* a ``system_admin``, unless the caller is a ``system_admin``.


Membership terms
================

``POST /admin/members/{user_id}/memberships``:

.. code-block:: json

   {"plan": "annual", "starts_on": null, "note": "Cheque 1041"}

``plan`` is a ``MembershipPlan`` slug and must be active.  The term is created
through ``members.services.activate_term`` with ``source="manual"`` and
``granted_by`` set to the caller, so a manual grant obeys the same start-date
rule as a payment: the day after the current expiry for a current member, today
otherwise, and no end date for a lifetime plan.  Pass ``starts_on`` to override
it.  **201** with the new term; **404** for an unknown member; **400** for an
unknown or inactive plan.

``PATCH /admin/memberships/{id}`` edits ``ends_on``, ``status`` and ``note``
only — the plan, the start date, the source and the payment link are read-only,
because rewriting them would falsify the history rather than correct it.
**400** if ``ends_on`` would fall before ``starts_on``.  Setting ``status`` to
``cancelled`` removes the term from the membership calculation while leaving
the row in place.


Exports
=======

``GET /admin/members/export.csv`` and ``export.pdf`` take **every filter and
ordering parameter the list takes** and apply them to the whole result set —
they are not paginated.  The CSV streams, so a report over the entire member
table never materialises in memory.  The PDF prints the applied filters under
its title.  Columns, style and how to add one: :doc:`reports`.


Tests
=====

``backend/tests/test_members_admin.py``
   The role matrix on every endpoint (401 anonymous, 403 for ``member``,
   ``dart_leader``, ``user_admin`` and ``website_admin``, 200 for
   ``account_admin`` and ``system_admin``), every filter against a mixed
   fixture, ordering, creation with and without a password, nested profile
   updates, the delete rules and the grant-term arithmetic.
``backend/tests/test_members_admin_status.py``
   The SQL annotations against ``membership_status``.
``backend/tests/test_members_reports.py``
   The two exports.

On the front end, ``frontend/src/portal/features/admin-members/`` holds a test
per page: filters to query parameters, export hrefs, the grant-term form and
the typed delete confirmation.
