==============================
API: aircraft and leader check
==============================

The ``apps.aircraft`` part of the ``/api/v1/`` contract: the aircraft
register and the DART leader check.  The register's CSV and PDF downloads are
the aircraft report, served by :doc:`api-reports` and described in
:doc:`reports`.  Conventions from :doc:`api-reference` apply throughout — session
authentication, ``X-CSRFToken`` on unsafe methods, DRF error bodies, and
``401`` (not ``403``) for an unauthenticated request that reaches the
permission check.  An unsafe method with no CSRF token is refused with ``403``
before it, signed in or not.  Those two answers are the same on every endpoint
below and are not repeated in the status lists.


N-number normalization
======================

``apps.aircraft.models.normalize_n_number`` is the single rule: strip
everything that is not a letter or a digit, upper-case the rest, and prefix
``N`` when the result starts with a digit.

=================  ===========
Input              Stored
=================  ===========
``12345``          ``N12345``
``n12345``         ``N12345``
``N-12345``        ``N12345``
``  n-172 sp ``    ``N172SP``
``c-gabc``         ``CGABC``
``---``            ``""``
=================  ===========

It runs in three places:

- ``Aircraft.save()``, so nothing reaches the table in another form;
- ``NNumberField.to_internal_value`` in the serializer.  DRF runs a field's
  validators on whatever ``to_internal_value`` returns, so the uniqueness
  check sees the canonical value and ``n-12345`` collides with an existing
  ``N12345`` as it should;
- the ``n_number`` query parameter of both lookup endpoints.

The frontend mirrors it in ``features/aircraft/insurance.ts`` so the canonical
form can be shown before the round trip.  Change one, change both — the rule
is covered by ``test_aircraft_models.py`` and ``insurance.test.ts``.


Aircraft register
=================

``GET /aircraft``
-----------------

The register, open to any authenticated user, paginated with ``?page=`` and
``?page_size=`` (25 rows by default, 200 maximum).

.. code-block:: json

   {
     "count": 34,
     "next": "http://localhost:8000/api/v1/aircraft?page=2",
     "previous": null,
     "results": [
       {
         "id": 12,
         "n_number": "N172SP",
         "make": "Cessna",
         "model": "172S Skyhawk",
         "year": 2008,
         "owner_type": "club",
         "owner_name": "Palo Alto Flying Club",
         "owner_contact": "ops@example.org",
         "seats": 4,
         "insurance_carrier": "Avemco",
         "insurance_policy_number": "AV-00012345",
         "insurance_liability_per_occurrence_cents": 100000000,
         "insurance_liability_per_person_cents": 10000000,
         "insurance_hull_cents": 14500000,
         "insurance_expiration": "2027-03-01",
         "insurance_is_current": true,
         "insurance_summary": "$1,000,000 / $100,000 · exp 2027-03-01",
         "notes": "",
         "created_by": 7,
         "updated_at": "2026-09-20T17:04:11.512Z",
         "is_active": true
       }
     ]
   }

``insurance_is_current`` and ``insurance_summary`` are model properties, not
columns: the summary reads ``No insurance on file`` when neither a liability
figure nor an expiry date is recorded.  ``created_by`` is the id of the member
who added the record, or ``null`` for an airframe the seed created.
``updated_at`` is when the record was last written, by anybody.

===================  ============================================================
Parameter            Meaning
===================  ============================================================
``search``           ``icontains`` over ``n_number``, ``make``, ``model``, and
                     ``owner_name``, plus the normalized form of the term
                     against ``n_number``
``make``             ``icontains`` on ``make``
``owner_type``       ``individual`` | ``fbo`` | ``club``
``insurance``        ``current`` (expiry ≥ today) | ``expired`` (expiry <
                     today) | ``missing`` (no expiry recorded)
``expiring_within``  Integer days: ``today ≤ expiry ≤ today + n``.  Excludes
                     policies that have already lapsed.  Clamped to
                     ``MAX_EXPIRING_WINDOW_DAYS`` (ten years), because
                     ``today + timedelta(days=999999999)`` raises
                     ``OverflowError`` and a query string must not be able to
                     produce a 500
``is_active``        ``true`` | ``false``.  The register lists both by
                     default; the member-facing picker asks for ``true`` so an
                     airframe an administrator has taken out of service is not
                     offered as one to fly
``ordering``         ``n_number``, ``make``, ``model``, ``owner_name``,
                     ``insurance_expiration``; prefix ``-`` to reverse.
                     Defaults to ``n_number``
===================  ============================================================

Ordering goes through ``NullsLastOrderingFilter``, which does two things.
Postgres sorts ``NULL`` first on a descending order, which would put every
airplane with no policy at the top of "latest expiry", so empty values are
pushed to the bottom in both directions.  And every ordering ends in the
primary key: sorting by a column many rows share — ``make``, or the expiry
date a whole club renews on — otherwise leaves ties in an undefined order, and
page two of a ``LIMIT``/``OFFSET`` query can then repeat or skip rows.

Statuses:

* **200** — the page of rows.
* **400** — ``owner_type`` or ``insurance`` carried a value outside its choice
  list, or ``expiring_within`` was not a number.  An unrecognized ``ordering``
  falls back to ``n_number`` and an unrecognized ``is_active`` narrows nothing;
  neither is refused.

``POST /aircraft``
------------------

Adds an airframe to the register.  Any authenticated user may do so — the
register is filled in by the members who fly the airplanes.

.. code-block:: json

   {
     "n_number": "n-172sp",
     "make": "Cessna",
     "model": "172S Skyhawk",
     "year": 2008,
     "owner_type": "club",
     "owner_name": "Palo Alto Flying Club",
     "seats": 4,
     "insurance_carrier": "Avemco",
     "insurance_liability_per_occurrence_cents": 100000000,
     "insurance_liability_per_person_cents": 10000000,
     "insurance_expiration": "2027-03-01"
   }

``created_by`` and ``updated_by`` are taken from the session and cannot be set
by the client, and ``updated_at`` is the clock's.
``n_number`` is required and stored normalized, ``make`` and ``model`` are
required and may not be blank, the three money fields are integer cents and
must be ``>= 0``, and everything else is optional.

Statuses:

* **201** — the stored record, in the row shape above.
* **400** — a missing or blank ``n_number``, ``make``, or ``model``; a
  registration that normalizes to nothing, refused with ``{"n_number": ["Enter
  a registration, for example N12345."]}``; a registration already on file,
  refused with ``{"n_number": ["An aircraft with this N-number is already on
  file."]}``; or a negative money field, refused with ``Enter an amount of $0
  or more.``

``GET /aircraft/{id}``
----------------------

One register record, open to any authenticated user.  For a ``dart_leader``,
``account_admin``, or ``system_admin`` the response also carries ``pilots``:

.. code-block:: json

   {
     "id": 12,
     "n_number": "N172SP",
     "make": "Cessna",
     "model": "172S Skyhawk",
     "year": 2008,
     "owner_type": "club",
     "owner_name": "Palo Alto Flying Club",
     "owner_contact": "ops@example.org",
     "seats": 4,
     "insurance_carrier": "Avemco",
     "insurance_policy_number": "AV-00012345",
     "insurance_liability_per_occurrence_cents": 100000000,
     "insurance_liability_per_person_cents": 10000000,
     "insurance_hull_cents": 14500000,
     "insurance_expiration": "2027-03-01",
     "insurance_is_current": true,
     "insurance_summary": "$1,000,000 / $100,000 · exp 2027-03-01",
     "notes": "",
     "created_by": 7,
     "updated_at": "2026-09-20T17:04:11.512Z",
     "is_active": true,
     "updated_by": {"id": 4, "name": "Marta Reyes"},
     "pilots": [
       {
         "user_id": 11,
         "name": "Ana Bracco",
         "email": "ana@example.org",
         "membership_status": "current",
         "medical_is_current": true
       }
     ]
   }

``pilots`` lists the members who name the airplane on their profile, sorted by
surname then forename.  ``aircraft_pilots()`` fetches them in one query, with
the membership annotations aboard (see :ref:`membership-status-sql`), so a
popular airplane costs no more than a rarely-flown one.

``updated_by`` is the account that last wrote the record, as ``{"id", "name"}``,
or ``null`` for one nobody has written since the seed created it.

Both keys are **absent** for anyone else.  ``pilots`` is other members' email
addresses, membership state and medical currency, and ``updated_by`` names
another member — exactly what the leader check below keeps to DART leaders and
account administrators — so serving them
from the register to every
signed-in member would walk around that gate.  ``aircraft_serializer_for()``
in ``views.py`` picks the serializer per request, and the same rule applies to
``/aircraft/lookup``.

Statuses:

* **200** — the record above, with or without ``pilots`` and ``updated_by``.
* **404** — no aircraft has that id.

Object rules
------------

``PUT``, ``PATCH``, and ``DELETE`` all go through
``apps/aircraft/api/permissions.py``:

============  ============================================================
Method        Allowed
============  ============================================================
``GET``       Any authenticated user
``PUT``       ``created_by == request.user``, or ``account_admin``
``PATCH``     ``created_by == request.user``, or ``account_admin``
``DELETE``    ``account_admin`` only
============  ============================================================

``GET /aircraft/{id}/changes`` is ``account_admin`` only and is not part of that
object-level rule: the history names accounts, so the record's own creator does
not read it.

``system_admin`` (and any superuser) passes every check, through
``accounts.permissions.user_has_any_role``.  An airplane created by the seed
has ``created_by = None`` and so belongs to nobody: only an administrator can
change it.  A refusal carries the sentence the permission sets — "Only the
member who added this aircraft, or an administrator, can change it." for a
write, and "Only an account administrator can delete an aircraft." for a
delete.

``PUT /aircraft/{id}``
----------------------

Replaces the record.  Every required field must be present: a ``PUT`` without
``n_number``, ``make``, and ``model`` is refused rather than merged into the
stored row, and the optional fields it leaves out keep the values they have.
The response is the record in the same shape ``GET /aircraft/{id}`` returns,
``pilots`` included when the caller is entitled to it.

.. code-block:: json

   {
     "n_number": "N172SP",
     "make": "Cessna",
     "model": "172S Skyhawk",
     "insurance_carrier": "Avemco",
     "insurance_expiration": "2028-03-01"
   }

Statuses:

* **200** — the updated record.
* **400** — a missing ``n_number``, ``make``, or ``model``, or any of the
  validation refusals ``POST /aircraft`` lists.  The uniqueness check skips
  the record being edited, so resending its own registration is not a clash.
* **403** — the caller neither created the record nor holds ``account_admin``.
* **404** — no aircraft has that id.

``PATCH /aircraft/{id}``
------------------------

Changes only the fields the body names, under the same object rules and with
the same response shape as ``PUT``.

.. code-block:: json

   {"insurance_expiration": "2028-03-01", "insurance_policy_number": "AV-00099999"}

Statuses:

* **200** — the updated record.
* **400** — a field the validation above refuses.
* **403** — the caller neither created the record nor holds ``account_admin``.
* **404** — no aircraft has that id.

``DELETE /aircraft/{id}``
-------------------------

Removes the airframe from the register, and its history with it, with an empty
body.  Only an account
administrator may do it: deleting an aircraft can orphan another member's
profile entry, so it is not left to whoever happened to add the record.
Taking an airplane out of service without losing its history is
``PATCH`` with ``is_active`` false.

Statuses:

* **204** — the record is gone.
* **403** — the caller does not hold ``account_admin``.
* **404** — no aircraft has that id.

``GET /aircraft/{id}/changes``
------------------------------

The record's history, newest first, for an account administrator.  A register
record is shared by every member who flies the airframe, so an edit to its
insurance is an edit to everybody's answer; the history says who last touched
it and which columns they touched.

.. code-block:: json

   [
     {
       "id": 42,
       "changed_at": "2026-09-20T17:04:11.512Z",
       "changed_by": {"id": 4, "name": "Marta Reyes"},
       "kind": "updated",
       "fields": ["insurance_carrier", "insurance_expiration"]
     },
     {
       "id": 17,
       "changed_at": "2026-04-02T09:12:00.004Z",
       "changed_by": null,
       "kind": "created",
       "fields": []
     }
   ]

``kind`` is ``created`` or ``updated``.  ``fields`` names the columns the write
moved and is empty on a ``created`` entry, where the whole record is the change,
and on a save that altered nothing.  ``changed_by`` is ``null`` for a change no
signed-in account made.  The list is unpaginated: an aircraft has few changes.
Every write through ``POST /aircraft``, ``PUT``, and ``PATCH`` adds one entry
and stamps ``updated_at`` and ``updated_by`` on the record, and deleting the
record deletes its history with it.

A ``dart_leader`` is refused: a leader reads the insurance card, not the trail
of who changed it.  So is the member who created the record — editing one is
not the same right as seeing who else has edited it.

Statuses:

* **200** — the array above, empty for a record nobody has written.
* **403** — the caller does not hold ``account_admin``.
* **404** — no aircraft has that id.

``GET /aircraft/lookup?n_number=``
----------------------------------

Exact match *after* normalization — not a prefix search — open to any
authenticated user.  This is what makes the picker's search-as-you-type land
on one record.  The response is the ``GET /aircraft/{id}`` shape, ``pilots``
included on the same terms.

Statuses:

* **200** — the matching record.
* **400** — ``n_number`` missing or normalizing to nothing, answered
  ``{"n_number": "Enter a registration, for example N12345."}``.
* **404** — the register has never seen that registration.


The aircraft report
===================

``GET /reports/aircraft/export.csv`` and ``export.pdf``, ``account_admin`` only,
download the register: they accept exactly the filter and ordering parameters of
``GET /aircraft`` and are not paginated.  Money is plain decimal dollars
(``1000000.00``) in the CSV and currency (``$1,000,000``) in the PDF, and
``pilots`` — off by default — is the attached members' display names joined
with ``"; "``.  The endpoints, ``?columns=`` and the refusals are in
:doc:`api-reports`; the columns are in :doc:`reports`.


Leader check
============

All three endpoints require ``dart_leader``, ``account_admin``, or
``system_admin``; a signed-in member without one of those gets **403**.

``GET /leader/search?q=``
-------------------------

Up to 20 members, matched on:

- first name, last name or email (``icontains``);
- a two-part term as a full name, in either order — ``Marta Reyes`` and
  ``Reyes, Marta`` find the same person;
- an N-number, exact after normalization *or* contained in the registration,
  through ``MemberProfile.aircraft``.

The N-number branch only runs when the term contains a digit
(``looks_like_registration``).  Without that guard, searching for "Nate"
normalizes to ``NATE`` and matches every US registration on file.

.. code-block:: json

   [
     {
       "user_id": 11,
       "name": "Ana Bracco",
       "email": "ana@example.org",
       "dart": "Palo Alto",
       "membership_status": "current",
       "go_no_go": {"membership": true, "medical": true}
     }
   ]

``membership_status`` is the ``current`` / ``expired`` / ``friend`` string of the
``members.services`` membership summary; a member who has never paid reads
``friend``.

``go_no_go`` is computed by the same rule the status card uses, so a leader
reads the verdict off the list and opens the card for the detail rather than
for the answer.  A member with no profile row is a no-go on both counts.

Every field comes from the row the search already fetched: the membership
summary rides along as annotations (see :ref:`membership-status-sql`) and the
profile is selected with the user, so twenty matches cost the same number of
queries as one.  The list is unpaginated, and a blank or missing ``q`` returns
``[]``.

Statuses:

* **200** — the array above, empty when nothing matches.

``GET /leader/members/{user_id}/status``
----------------------------------------

The pre-flight status card for one member.

.. code-block:: json

   {
     "name": "Ana Bracco",
     "email": "ana@example.org",
     "phone": "415-555-0100",
     "dart": "Palo Alto",
     "membership": {
       "status": "current",
       "expires_on": "2027-06-30",
       "plan": "Annual"
     },
     "certificate": {
       "type": "private",
       "number": "3181234",
       "ifr_rated": "yes",
       "ratings": ["instrument"]
     },
     "medical": {
       "type": "third",
       "expiration": "2026-12-01",
       "is_current": true
     },
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
     "go_no_go": {"membership": true, "medical": true}
   }

``go_no_go`` is deliberately two booleans rather than one verdict: a leader is
entitled to see *why* a member is a no-go.  The overall verdict is their
conjunction, and the portal renders it as the GO / NO-GO band.  Insurance is
reported per airplane and never folded into ``go_no_go``, because a member
may be current in one airplane and not another.

A user with no ``MemberProfile`` — an account created by a user administrator
before the member has filled anything in — is handled rather than 500ing:
empty phone, ``dart: null``, certificate ``none``, medical ``none``, no
aircraft, and ``go_no_go.medical`` false.  ``membership`` is unaffected,
because it is computed from the account's membership terms and a profile plays
no part in it: a member with a current term and no profile reads ``status:
"current"`` and ``go_no_go.membership`` true.

Statuses:

* **200** — the card above.
* **404** — no account has that ``user_id``.

``GET /leader/aircraft?n_number=``
----------------------------------

The insurance card for one airplane, keyed by normalized registration.  The
shape is ``GET /aircraft/{id}``'s, and ``pilots`` is always present here
because the endpoint is role-gated already.

Statuses:

* **200** — the matching record, ``pilots`` included.
* **400** — ``n_number`` missing or normalizing to nothing, answered
  ``{"n_number": "Enter a registration, for example N12345."}``.
* **404** — the register has never seen that registration.


Where the code lives
====================

=====================================  ======================================
File                                   Contents
=====================================  ======================================
``apps/aircraft/models.py``            ``Aircraft``, ``AircraftChange``,
                                       ``normalize_n_number``
``apps/aircraft/services.py``          ``record_change``, ``changed_fields``,
                                       leader search, status card, insurance
                                       querysets
``apps/aircraft/reports.py``           The aircraft report: columns, query
``apps/aircraft/api/serializers.py``   ``NNumberField`` and the API shapes
``apps/aircraft/filters.py``           ``AircraftFilter``,
                                       ``NullsLastOrderingFilter``
``apps/aircraft/api/permissions.py``   ``AircraftPermission``
``apps/aircraft/api/views.py``         The routes above
=====================================  ======================================

Tests: ``backend/tests/test_aircraft_api.py`` (CRUD, permissions,
normalization, every filter), ``test_aircraft_history.py`` (the change rows the
register's writes leave and the history endpoint),
``test_aircraft_exports.py`` (the aircraft report: CSV content, PDF
validity, subtitle), ``test_leader_api.py`` (search, the membership ×
medical × insurance truth table), and ``test_aircraft_models.py`` from the
foundation.
