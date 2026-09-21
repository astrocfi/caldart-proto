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
signed in or not.

The code lives in ``backend/apps/members/``:

``api/admin_views.py``
   The views.
``api/admin_serializers.py``
   Request and response shapes.  The profile, term and payment serializers
   extend the member-facing ones in ``api/profile_serializers.py``, so an
   administrator and a member see one definition of a profile and one set of
   validation rules.
``api/serializers.py``
   The two shapes more than one app returns: ``MembershipStatusSerializer``
   over the dict ``services.membership_status`` builds, and ``PlanSerializer``
   over a ``MembershipPlan``.  The accounts, members and payments APIs all
   import them from here.
``api/admin_filters.py``
   The filter set, the ordering backend, and the queryset the list is served
   from.  The membership annotations it builds on live in ``services.py``.
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
before pagination.  ``members.services.membership_annotations`` therefore
states the same rules as correlated subqueries on the user queryset:

``covers_today``
   ``EXISTS`` an active term with ``starts_on <= today`` and ``ends_on``
   either null or ``>= today``.  This is what ``?status=current`` filters on.
``has_started_term``
   ``EXISTS`` a non-canceled term with ``starts_on <= today``.  Paired with
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
password and ``apps.accounts.services.send_password_invitation`` emails an
invitation whose subject is ``<organization name>: set your password``.  It
renders
``templates/emails/member_invitation.{txt,html}`` from the same context as the
reset email — organization name, contact address and link expiry from Wagtail's
site settings — and its link is ``build_reset_url``'s, so the portal posts it
back to ``/auth/password/reset/confirm`` unchanged (:doc:`api-auth`).  The mail
is queued with ``transaction.on_commit``, so a failed create never sends one —
and a test has to use ``django_capture_on_commit_callbacks`` to see it.

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

``email`` and ``is_active`` go through the same account-edit guard as
``PATCH /admin/users/{id}`` — see :ref:`account-edit-guard`.  An account
administrator may move a plain member's address, but not the address or the
active flag of an account holding a role they do not hold themselves, and may
not deactivate their own account.  A refusal is a **400** keyed on ``email`` or
``is_active``, and nothing is written at all — the profile half of the same
request included.

``DELETE /admin/members/{user_id}`` hard-deletes: the cascade takes the
profile and the membership terms.  It is refused with **403** when

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
payment, ``pending`` and ``failed`` rows included, and the ``detail`` reads::

   Ana Bracco has 3 payment records, which must be kept. Deactivate the account instead.

with ``payment record`` singular for a count of one.  Nothing is written — the
payments, the profile and the membership terms are all still there afterwards.

``Payment.user`` is ``PROTECT`` (:doc:`data-model`), so the protection is on
the foreign key rather than on this view alone: the Django admin, a management
command and a shell session all raise ``ProtectedError`` instead of cascading.
The view catches that error and answers with the same **403**.

Deactivation — ``PATCH`` with ``is_active`` false — is the tool for a member
who has left.  The hard delete is for accounts that never paid: duplicates,
spam and test accounts.


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
``canceled`` removes the term from the membership calculation while leaving
the row in place.


Exports
=======

``GET /admin/members/export.csv`` and ``export.pdf`` take **every filter and
ordering parameter the list takes** and apply them to the whole result set —
they are not paginated.  The CSV streams, so a report over the entire member
table never materializes in memory.  The PDF prints the applied filters under
its title.  Columns, style and how to add one: :doc:`reports`.


Tests
=====

``backend/tests/test_members_admin.py``
   The role matrix on every endpoint (401 anonymous, 403 for ``member``,
   ``dart_leader``, ``user_admin`` and ``website_admin``, 200 for
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

On the front end, ``frontend/src/portal/features/admin-members/`` holds a test
per page: filters to query parameters, export hrefs, the grant-term form, the
typed delete confirmation, and the Danger zone's explanation for a member whose
payments keep the account.
