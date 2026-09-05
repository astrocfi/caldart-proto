==============================
API: aircraft and leader check
==============================

The ``apps.aircraft`` half of the ``/api/v1/`` contract: the aircraft register
(PLAN §6.5), its CSV and PDF exports (PLAN §11), and the DART leader check
(PLAN §6.6).  Conventions from :doc:`api-reference` apply throughout — session
authentication, ``X-CSRFToken`` on unsafe methods, DRF error bodies, and
``401`` (never ``403``) for an unauthenticated request.

.. contents:: On this page
   :local:
   :depth: 2


N-number normalisation
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

Any authenticated user.  Paginated (``page``, ``page_size``; 25 by default,
200 maximum).

===================  ============================================================
Parameter            Meaning
===================  ============================================================
``search``           ``icontains`` over ``n_number``, ``make``, ``model`` and
                     ``owner_name``, plus the normalised form of the term
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
aeroplane with no policy at the top of "latest expiry", so empty values are
pushed to the bottom in both directions.  And every ordering ends in the
primary key: sorting by a column many rows share — ``make``, or the expiry
date a whole club renews on — otherwise leaves ties in an undefined order, and
page two of a ``LIMIT``/``OFFSET`` query can then repeat or skip rows.

A result row::

  {"id": 12, "n_number": "N172SP", "make": "Cessna", "model": "172S Skyhawk",
   "year": 2008, "owner_type": "club", "owner_name": "Palo Alto Flying Club",
   "owner_contact": "ops@example.org", "seats": 4,
   "insurance_carrier": "Avemco", "insurance_policy_number": "AV-00012345",
   "insurance_liability_per_occurrence_cents": 100000000,
   "insurance_liability_per_person_cents": 10000000,
   "insurance_hull_cents": 14500000,
   "insurance_expiration": "2027-03-01",
   "insurance_is_current": true,
   "insurance_summary": "$1,000,000 / $100,000 · exp 2027-03-01",
   "notes": "", "created_by": 7, "is_active": true}

``POST /aircraft``
------------------

Any authenticated user.  ``created_by`` is taken from the session and cannot
be set by the client.  Validation:

- ``n_number`` required, normalised, unique after normalisation;
- ``make`` and ``model`` required and non-blank;
- the three money fields are integer cents and must be ``>= 0``;
- everything else optional.

``GET /aircraft/{id}``
----------------------

Any authenticated user.  For a ``dart_leader``, ``account_admin`` or
``system_admin`` the response also carries ``pilots``: the members who list
the aeroplane on their profile, each as
``{user_id, name, email, membership_status, medical_is_current}``.

The key is **absent** for anyone else.  ``pilots`` is other members' email
addresses, membership state and medical currency — exactly what PLAN §6.6
gates behind ``dart_leader`` — so serving it from the register to every
signed-in member would walk around that gate.  ``aircraft_serializer_for()``
in ``views.py`` picks the serializer per request, and the same rule applies to
``/aircraft/lookup``.

``PATCH /aircraft/{id}`` and ``DELETE /aircraft/{id}``
------------------------------------------------------

Object rules live in ``apps/aircraft/api/permissions.py``:

============  ============================================================
Method        Allowed
============  ============================================================
``GET``       Any authenticated user
``PATCH``     ``created_by == request.user``, or ``account_admin``
``DELETE``    ``account_admin`` only
============  ============================================================

``system_admin`` (and any superuser) passes every check, through
``accounts.permissions.user_has_any_role``.  An aeroplane created by the seed
has ``created_by = None`` and so belongs to nobody: only an administrator can
change it.

``GET /aircraft/lookup?n_number=``
----------------------------------

Any authenticated user.  Exact match *after* normalisation — not a prefix
search — returning the detail shape, ``404`` when the register has never seen
the registration, or ``400`` when the parameter normalises to nothing.  This
is what makes the picker's search-as-you-type land on one record.


Exports
=======

``GET /admin/aircraft/export.csv`` and ``GET /admin/aircraft/export.pdf``,
both ``account_admin`` only, both accepting exactly the filter and ordering
parameters of the list endpoint, and neither paginated.  Columns (PLAN §11)::

  n_number, make, model, owner, owner_type, insurance_carrier,
  liability_per_occurrence, liability_per_person, hull,
  insurance_expiration, insurance_current, pilots

Rows come from ``apps/aircraft/reports.py``, which both formats share so they
cannot drift apart.  Money is rendered as plain decimal dollars for the CSV
(``1000000.00``) and as currency for the PDF (``$1,000,000``); ``pilots`` is
the attached members' display names joined with ``"; "``.  The CSV streams
through ``caldart.reports.csv_response``; the PDF is a landscape-letter table
from ``pdf_table_response`` with the applied filters in the subtitle.


Leader check
============

All three endpoints require ``dart_leader``, ``account_admin`` or
``system_admin``.

``GET /leader/search?q=``
-------------------------

Up to 20 members, matched on:

- first name, last name or email (``icontains``);
- a two-part term as a full name, in either order — ``Marta Reyes`` and
  ``Reyes, Marta`` find the same person;
- an N-number, exact after normalisation *or* contained in the registration,
  through ``MemberProfile.aircraft``.

The N-number branch only runs when the term contains a digit
(``looks_like_registration``).  Without that guard, searching for "Nate"
normalises to ``NATE`` and matches every US registration on file.

Rows are ``{user_id, name, email, dart, membership_status}`` where
``membership_status`` is the ``current`` / ``expired`` / ``none`` string from
``members.services.membership_status``.

``GET /leader/members/{user_id}/status``
----------------------------------------

The status card::

  {"name": "...", "email": "...", "phone": "...", "dart": "Palo Alto",
   "membership": {"status": "current", "expires_on": "2027-06-30",
                  "plan": "Annual"},
   "certificate": {"type": "private", "number": "3181234",
                   "ifr_rated": "yes", "ratings": ["instrument"]},
   "medical": {"type": "third", "expiration": "2026-12-01",
               "is_current": true},
   "aircraft": [<aircraft summary>, ...],
   "go_no_go": {"membership": true, "medical": true}}

``go_no_go`` is deliberately two booleans rather than one verdict: a leader is
entitled to see *why* a member is a no-go.  The overall verdict is their
conjunction, and the portal renders it as the GO / NO-GO band.  Insurance is
reported per aeroplane and never folded into ``go_no_go``, because a member
may be current in one aeroplane and not another.

A user with no ``MemberProfile`` — an account created by a user administrator
before the member has filled anything in — is handled rather than 500ing:
empty phone, ``dart: null``, certificate ``none``, medical ``none``, no
aircraft, and both ``go_no_go`` flags false.  An unknown ``user_id`` is a
``404``.

``GET /leader/aircraft?n_number=``
----------------------------------

The same detail shape as ``GET /aircraft/{id}``, keyed by normalised
registration: ``404`` when unknown, ``400`` when the parameter is empty.
``pilots`` is always present here, because the endpoint is role-gated already.


Where the code lives
====================

=====================================  ======================================
File                                   Contents
=====================================  ======================================
``apps/aircraft/models.py``            ``Aircraft``, ``normalize_n_number``
``apps/aircraft/services.py``          Leader search, status card, insurance
                                       querysets
``apps/aircraft/reports.py``           Export columns and rows
``apps/aircraft/api/serializers.py``   ``NNumberField`` and the API shapes
``apps/aircraft/api/filters.py``       ``AircraftFilter``,
                                       ``NullsLastOrderingFilter``
``apps/aircraft/api/permissions.py``   ``AircraftPermission``
``apps/aircraft/api/views.py``         The eight endpoints above
=====================================  ======================================

Tests: ``backend/tests/test_aircraft_api.py`` (CRUD, permissions,
normalisation, every filter), ``test_aircraft_exports.py`` (CSV content, PDF
validity, role matrix), ``test_leader_api.py`` (search, the membership ×
medical × insurance truth table), and ``test_aircraft_models.py`` from the
foundation.
