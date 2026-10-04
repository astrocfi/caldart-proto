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
- the ``n_number`` query parameter of both lookup endpoints, the
  ``n_number`` of ``GET /aircraft/registry/{n_number}``, and the ``q`` of
  ``GET /aircraft/registrations``.

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
         "type": {
           "id": 3,
           "make": "Cessna",
           "model": "172S Skyhawk",
           "seats": 4,
           "engines": 1,
           "category": "airplane",
           "is_custom": false
         },
         "year": 2008,
         "owner_type": "club",
         "owner_name": "Palo Alto Flying Club",
         "owner_contact": "ops@example.org",
         "seats": 4,
         "category": "airplane",
         "airworthiness": "standard",
         "coverage": {"excluded": false, "reason": ""},
         "insurance_carrier": "Avemco",
         "insurance_policy_number": "AV-00012345",
         "insurance_liability_per_occurrence_cents": 100000000,
         "insurance_liability_per_person_cents": 10000000,
         "insurance_hull_cents": 14500000,
         "insurance_expiration": "2027-03-01",
         "insurance_is_current": true,
         "insurance_summary": "$1,000,000 / $100,000 · exp 2027-03-01",
         "insurance_verification": {
           "verified": true,
           "verified_by": "Priya Raman",
           "verified_at": "2026-09-20T10:04:11.512000-07:00"
         },
         "notes": "",
         "created_by": 7,
         "updated_at": "2026-09-20T17:04:11.512Z",
         "is_active": true
       }
     ]
   }

``type`` is the aircraft's entry in the aircraft types (:doc:`data-model`):
its id, display make and model, ``seats`` and ``engines`` (``null`` when the
registry does not say), ``category`` (blank when the registry does not say,
always for a hand-added type), and ``is_custom``, true for a type an account
administrator added by hand.  ``make`` and ``model`` repeat the type's display
names, so every screen that prints them reads one spelling.  The type is
joined to the page's query, so it costs nothing per row.

``insurance_is_current`` and ``insurance_summary`` are model properties, not
columns: the summary reads ``No insurance on file`` when neither a liability
figure nor an expiry date is recorded.  ``insurance_verification`` says whether
an authority has checked the insurance against the policy: ``verified``, the
display name of the account that verified it, and when, both ``null`` while it
is unverified (:doc:`verification`).  Verified insurance whose expiry passes
stays verified; currency and verification are two separate facts.  The
verifier is joined to the page's query, so naming one costs nothing per row.  ``created_by`` is the id of the member
who added the record, or ``null`` for an airframe the seed created.
``updated_at`` is when the record was last written, by anybody.

``category`` is one of ``airplane``, ``helicopter``, ``gyroplane``, ``glider``,
``balloon``, ``airship``, ``powered_lift``, ``weight_shift``,
``powered_parachute``, and ``other``; ``airworthiness`` one of ``standard``,
``limited``, ``restricted``, ``experimental``, ``provisional``, ``multiple``,
``primary``, ``special_flight_permit``, and ``light_sport``.  Either is blank
(``""``) until somebody records it (:doc:`data-model`).

``coverage`` is whether the coverage policy (:ref:`api-coverage-policy`)
excludes the aircraft: ``excluded``, and ``reason``, the words the aircraft
check prints.  An excluded aircraft's reason reads ``Not covered: helicopters
are excluded by CalDART's policy``, naming the category that matched (or the
airworthiness, when only that matched) and the organization from the site
settings.  An aircraft with no category that is not otherwise excluded reads
``Category not recorded``, and every other reason is blank.  The policy is read
once per response, however many aircraft it carries.  The short form embedded
in profiles and the member check's status card carries ``category``,
``airworthiness``, and ``coverage`` too, with the two liability limits in cents
(``insurance_liability_per_occurrence_cents`` and
``insurance_liability_per_person_cents``, 0 when none is recorded) and
``created_by``, the id of the account that added the record or null, by which My
aircraft offers **Edit** on a member's own records alone.

===================  ============================================================
Parameter            Meaning
===================  ============================================================
``search``           ``icontains`` over ``n_number``, the type's ``make`` and
                     ``model``, and ``owner_name``, plus the normalized form
                     of the term against ``n_number``
``make``             ``icontains`` on the type's ``make``
``model``            ``icontains`` on the type's ``model``
``type``             The id of one aircraft type
``category``         One category, matched exactly; an unknown value is a
                     ``400``
``airworthiness``    One airworthiness classification, matched exactly; an
                     unknown value is a ``400``
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
                     ``make`` and ``model`` sort on the type's
                     (``type__make``, ``type__model``).  Defaults to
                     ``n_number``
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
     "type_id": 3,
     "year": 2008,
     "owner_type": "club",
     "owner_name": "Palo Alto Flying Club",
     "seats": 4,
     "category": "airplane",
     "airworthiness": "standard",
     "coverage": {"excluded": false, "reason": ""},
     "insurance_carrier": "Avemco",
     "insurance_liability_per_occurrence_cents": 100000000,
     "insurance_liability_per_person_cents": 10000000,
     "insurance_expiration": "2027-03-01"
   }

``created_by`` and ``updated_by`` are taken from the session and cannot be set
by the client, and ``updated_at`` is the clock's.
``n_number`` is required and stored normalized.  ``type_id`` is required: the
id of an entry of the aircraft types, which ``GET /aircraft/types`` finds.
``make``, ``model``, ``type``, and ``coverage`` are read-only and a body naming
them changes nothing.  ``category`` and ``airworthiness`` are optional choices
and may be blank.  The three money fields are integer cents and must be ``>= 0``, and
everything else is optional.

Statuses:

* **201** — the stored record, in the row shape above.
* **400** — a missing or blank ``n_number``; a missing, ``null``, or unknown
  ``type_id``, refused with ``{"type_id": ["Pick the aircraft type from the
  list."]}``; a registration that normalizes to nothing, refused with ``{"n_number": ["Enter
  a registration, for example N12345."]}``; a registration already on file,
  refused with ``{"n_number": ["An aircraft with this N-number is already on
  file."]}``; or a negative money field, refused with ``Enter an amount of $0
  or more.``

``GET /aircraft/{id}``
----------------------

One register record, open to any authenticated user.  For a holder of a
verifying role (``verifier``, ``dart_leader``, ``user_admin``, or
``account_admin``) or a ``system_admin`` the response also carries ``pilots``:

.. code-block:: json

   {
     "id": 12,
     "n_number": "N172SP",
     "make": "Cessna",
     "model": "172S Skyhawk",
     "type": {
       "id": 3,
       "make": "Cessna",
       "model": "172S Skyhawk",
       "seats": 4,
       "engines": 1,
       "category": "airplane",
       "is_custom": false
     },
     "year": 2008,
     "owner_type": "club",
     "owner_name": "Palo Alto Flying Club",
     "owner_contact": "ops@example.org",
     "seats": 4,
     "category": "airplane",
     "airworthiness": "standard",
     "coverage": {"excluded": false, "reason": ""},
     "insurance_carrier": "Avemco",
     "insurance_policy_number": "AV-00012345",
     "insurance_liability_per_occurrence_cents": 100000000,
     "insurance_liability_per_person_cents": 10000000,
     "insurance_hull_cents": 14500000,
     "insurance_expiration": "2027-03-01",
     "insurance_is_current": true,
     "insurance_summary": "$1,000,000 / $100,000 · exp 2027-03-01",
     "insurance_verification": {
       "verified": false,
       "verified_by": null,
       "verified_at": null
     },
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
         "medical_is_current": true,
         "go_no_go": {"membership": true, "medical": true, "verified": false}
       }
     ]
   }

``pilots`` lists the members and friends who name the airplane on their profile,
sorted by surname then forename.  ``membership_status`` is ``friend`` for a friend of
CalDART, and ``go_no_go`` is the member check's own verdict for the person, the same
three booleans its search row and status card carry (below), so the two checks never
disagree.  ``aircraft_pilots()`` fetches them in one query, with
the membership annotations aboard (see :ref:`membership-status-sql`), so a
popular airplane costs no more than a rarely-flown one.

``updated_by`` is the account that last wrote the record, as ``{"id", "name"}``,
or ``null`` for one nobody has written since the seed created it.

Both keys are **absent** for anyone else.  ``pilots`` is other members' email
addresses, membership state and medical currency, and ``updated_by`` names
another member — exactly what the leader check below keeps to the verifying
roles — so serving them
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
``n_number`` and ``type_id`` is refused rather than merged into the stored row, and the optional fields it leaves out keep the values they have.
The response is the record in the same shape ``GET /aircraft/{id}`` returns,
``pilots`` included when the caller is entitled to it.

.. code-block:: json

   {
     "n_number": "N172SP",
     "type_id": 3,
     "insurance_carrier": "Avemco",
     "insurance_expiration": "2028-03-01"
   }

Statuses:

* **200** — the updated record.
* **400** — a missing ``n_number`` or ``type_id``, or any of the
  validation refusals ``POST /aircraft`` lists.  The uniqueness check skips
  the record being edited, so resending its own registration is not a clash.
* **403** — the caller neither created the record nor holds ``account_admin``.
* **404** — no aircraft has that id.

``PATCH /aircraft/{id}``
------------------------

Changes only the fields the body names, under the same object rules and with
the same response shape as ``PUT``.

A ``PUT`` or ``PATCH`` that moves any insurance field — ``insurance_carrier``,
``insurance_policy_number``, the three money fields, or
``insurance_expiration`` — clears a verified insurance in the same transaction,
whoever writes it; one that moves no insurance field, or resends one at its
stored value, leaves the verification alone.  The clearing raises no event of
its own: ``aircraft_changed`` already names the columns
(:doc:`notification-events`).

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

``GET /aircraft/types?q=``
--------------------------

The aircraft types matching ``q``, best first, at most ten, open to any
authenticated user.  This is what the aircraft forms search to pick a type.

.. code-block:: json

   [
     {
       "id": 3,
       "make": "Cessna",
       "model": "172S",
       "seats": 4,
       "engines": 1,
       "category": "airplane",
       "is_custom": false
     }
   ]

``search_types()`` in ``apps/aircraft/types.py`` answers it: first the type an
alias names exactly (``c172``, ``skyhawk``), then the types whose
``make || ' ' || model``, or whose ``make`` alone, is similar to ``q`` by
trigram (most similar first, then the one more aircraft are registered as,
then by name), then, when ``q`` holds at least two digits, the types whose
model contains them.  Two types with the same display make and model collapse
into the one with more registrations.  So ``cesna 172``, ``CESSNA``, ``cesna``,
``c172``, and ``skyhawk`` all lead with the Cessna 172.  :doc:`aircraft-registry`
describes the rule in full.

Statuses:

* **200** — the array above; ``[]`` when ``q`` is missing or blank, or nothing
  resembles it.

``POST /aircraft/types``
------------------------

Adds an aircraft type the FAA has never registered — a homebuilt, or a type
built abroad that no US owner has registered yet — so an aircraft of that type
can go on the register.  Every type the FAA has registered is already in the
vocabulary, so this is the exception, and only ``account_admin`` (and
``system_admin``) may do it.

.. code-block:: json

   {"make": "zenith", "model": "ch 750", "seats": 2, "engines": 1}

``make`` and ``model`` are required; ``seats`` (at least 1) and ``engines`` (at
least 0) are optional.  The names are written as the registry's own would be:
``make`` through ``display_make`` and ``model`` through ``display_model`` of its
upper-cased form, so ``cessna aircraft co`` is stored ``Cessna`` and ``ch 750
sport`` is ``CH 750 Sport``.  The type is stored with ``is_custom`` true and
the FAA code ``CUSTOM-<id>``.  When the FAA later lists the same make and model,
the nightly import folds the hand-added type into the FAA's entry
(:doc:`aircraft-registry`).  The answer is the new type, in the shape
``GET /aircraft/types`` answers.

Statuses:

* **201** — the type added.
* **400** — ``make`` or ``model`` missing or blank, a number out of range, a
  name that normalizes to nothing (a corporate suffix alone, or bare
  punctuation) answered under that field
  ``{"make": ["Enter a name, not only a corporate suffix or punctuation."]}``,
  or a make and model already listed (compared case-insensitively, after the
  normalization above), answered
  ``{"model": ["That aircraft type is already listed."]}``.
* **403** — the caller does not hold ``account_admin``.


The FAA registry
================

The FAA's Releasable Aircraft Database, imported nightly, answers a lookup by
N-number and a search by the start of one; :doc:`aircraft-registry` describes
the data and the import.  All three endpoints are open to any authenticated
user.  Starting an import by hand is
``POST /admin/system/registry-import`` (:doc:`api-system`).

The aircraft forms prefill the category from the registration's type, or from
a type picked in the type picker, and the airworthiness from the registration;
the person filling the form may change either.

``GET /aircraft/registry/{n_number}``
-------------------------------------

The registration for ``n_number``, normalized as above, so ``n128sc`` and
``N-128-SC`` find ``N128SC``.  It serves anything that reads one registration
by its N-number; the aircraft form's N-number box searches with
``GET /aircraft/registrations`` instead.

.. code-block:: json

   {
     "n_number": "N128SC",
     "type": {"id": 41, "make": "Cessna", "model": "172S", "seats": 4,
              "engines": 1, "category": "airplane",
              "is_custom": false},
     "year": 1999,
     "registrant_name": "EXAMPLE FLYING CLUB INC",
     "registrant_type": "corporation",
     "status": "valid",
     "certificate_issued_on": "2021-03-02",
     "expires_on": "2028-03-31",
     "airworthiness": "standard",
     "imported_at": "2026-09-27T04:31:12Z"
   }

``registrant_type`` is one of ``individual``, ``partnership``,
``corporation``, ``co_owned``, ``government``, ``llc``,
``non_citizen_corporation``, ``non_citizen_co_owned``, and ``unknown``;
``status`` is one of ``valid``, ``pending``, ``revoked``, ``expired``, and
``other``; ``airworthiness`` is a classification as on the register, blank when
the registry records no certificate.  ``year``, ``certificate_issued_on``, and ``expires_on`` are null
when the registry leaves them blank.  ``imported_at`` is when the import that
wrote the row ran.

Statuses:

* **200** — the registration.
* **400** — ``n_number`` normalizing to nothing, answered
  ``{"n_number": "Enter a registration, for example N12345."}``.
* **404** — the registry does not hold it, answered
  ``{"detail": "No registration for N12345 in the registry."}``.

``GET /aircraft/registrations?q=``
----------------------------------

The registrations whose N-number starts with ``q``: the aircraft form's N-number
box asks it as the box is typed into, and lists the answer under the box.  ``q``
is normalized as above, so the leading ``N`` is optional and case and
punctuation do not matter: ``n17``, ``17``, and ``N-17`` all ask for ``N17``.
At most eight registrations come back, in N-number order, each in the shape
``GET /aircraft/registry/{n_number}`` answers.

.. code-block:: text

   GET /api/v1/aircraft/registrations?q=n128s

.. code-block:: json

   [
     {
       "n_number": "N128SC",
       "type": {"id": 41, "make": "Cessna", "model": "172S", "seats": 4,
                "engines": 1, "category": "airplane",
              "is_custom": false},
       "year": 1999,
       "registrant_name": "EXAMPLE FLYING CLUB INC",
       "registrant_type": "corporation",
       "status": "valid",
       "certificate_issued_on": "2021-03-02",
       "expires_on": "2028-03-31",
       "airworthiness": "standard",
       "imported_at": "2026-09-27T04:31:12Z"
     }
   ]

A ``q`` shorter than two characters after normalizing (``N`` alone, or none at
all) answers an empty list rather than an error, so the box may ask on every
keystroke.  The prefix match is served by the ``varchar_pattern_ops`` index
Django builds for the unique ``n_number`` (:doc:`aircraft-registry`).

Statuses:

* **200** — the matches, possibly none.

``GET /aircraft/registry``
--------------------------

The date the registry is as of, whether an import is running, and the newest
import.  The register's header and the Health and database page's *Aircraft
database* panel read it; that page polls it every five seconds while ``running``.

.. code-block:: json

   {
     "as_of": "2026-09-27T04:31:12Z",
     "running": false,
     "last": {
       "started_at": "2026-09-27T04:30:40Z",
       "finished_at": "2026-09-27T04:31:12Z",
       "ok": true,
       "error": "",
       "types_written": 94077,
       "registrations_written": 316992,
       "types_folded": 0,
       "source": "https://registry.faa.gov/database/ReleasableAircraft.zip"
     }
   }

``as_of`` is when the newest successful import finished, null before one has
and null whenever the registry holds no registration, as after a restore from a
backup, which leaves the registrations out (:ref:`registry-backups`).
``running`` is true while an import has started, not finished, and started less
than ``REGISTRY_IMPORT_STALE_MINUTES`` ago.  ``last`` is the newest import of any
outcome, null before the first: ``finished_at`` is null while it runs, ``ok``
says whether it succeeded, and ``error`` why not.

Statuses:

* **200** — the object above.


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

Every endpoint here but ``PUT /leader/members/{user_id}/verifier`` is open to
the verifying roles — ``verifier``, ``dart_leader``, ``user_admin``, and
``account_admin`` — and to ``system_admin`` (``IsLeader`` and ``IsVerifier``, both
``HasAnyRole(*VERIFY_ROLES)``); a signed-in member without one of those gets
**403**.  The verifier role is granted from here by a DART leader or a user
administrator.  What verification means, which fields each item covers, and
when an item is cleared are in :doc:`verification`.

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
       "go_no_go": {"membership": true, "medical": true, "verified": true}
     }
   ]

``membership_status`` is the ``current`` / ``expired`` / ``friend`` string of the
``members.services`` membership summary; a member who has never paid reads
``friend``.

``go_no_go`` is computed by the same rule the status card uses, so a leader
reads the verdict off the list and opens the card for the detail rather than
for the answer: ``verified`` is true when the member holds a pilot certificate, a
medical, and a photo ID and all three are verified.  A member with no profile row
is a no-go on every count.

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
       "ratings": ["instrument"],
       "verification": {
         "verified": true,
         "verified_by": "Priya Raman",
         "verified_at": "2026-09-20T10:04:11.512000-07:00"
       }
     },
     "medical": {
       "type": "third",
       "expiration": "2026-12-01",
       "is_current": true,
       "verification": {
         "verified": true,
         "verified_by": "Priya Raman",
         "verified_at": "2026-09-20T10:04:11.512000-07:00"
       }
     },
     "photo_id": {
       "type": "drivers_license",
       "verification": {"verified": false, "verified_by": null, "verified_at": null}
     },
     "is_dart_leader": false,
     "is_verifier": false,
     "aircraft": [
       {
         "id": 7,
         "n_number": "N172SP",
         "make": "Cessna",
         "model": "172S Skyhawk",
         "type": {
           "id": 3,
           "make": "Cessna",
           "model": "172S Skyhawk",
           "seats": 4,
           "engines": 1,
           "category": "airplane",
           "is_custom": false
         },
         "category": "airplane",
         "airworthiness": "standard",
         "coverage": {"excluded": false, "reason": ""},
         "insurance_is_current": true,
         "insurance_expiration": "2027-03-01",
         "insurance_summary": "$1,000,000 / $100,000 · exp 2027-03-01",
         "insurance_verified": true
       }
     ],
     "go_no_go": {"membership": true, "medical": true, "verified": false}
   }

``go_no_go`` is deliberately separate booleans rather than one verdict: a leader
is entitled to see *why* a member is a no-go.  ``verified`` is true when the
member holds a pilot certificate, a medical, and a photo ID (none of them ``none``
or ``not_provided``) and all three are verified; each of the
three carries its own ``verification`` (``{verified, verified_by,
verified_at}``), so the card says which one is missing.  A verified medical
whose expiration passes stays verified: ``is_current`` and ``verification`` are
two separate facts.  The overall verdict is the conjunction of the three
booleans, and the portal renders it as the GO / NO-GO band.  ``photo_id``
carries only the kind of document (``not_provided``, ``drivers_license``,
``passport``, ``state_id``, ``military_id``, or ``other``); nothing else about
it is recorded.  ``is_dart_leader`` and ``is_verifier`` say whether the member
holds the DART leader role and the verifier role.  Each airplane's ``insurance_verified`` says whether its insurance is
verified.  Insurance is
reported per airplane and never folded into ``go_no_go``, because a member
may be current in one airplane and not another.

A user with no ``MemberProfile`` — an account created by a user administrator
before the member has filled anything in — is handled rather than 500ing:
empty phone, ``dart: null``, certificate ``none``, medical ``none``, photo ID
``not_provided``, nothing verified, no aircraft, and ``go_no_go.medical`` and
``go_no_go.verified`` false.  ``membership`` is unaffected,
because it is computed from the account's membership terms and a profile plays
no part in it: a member with a current term and no profile reads ``status:
"current"`` and ``go_no_go.membership`` true.

Statuses:

* **200** — the card above.
* **404** — no account has that ``user_id``, or it is a donor or deactivated.

``PUT /leader/members/{user_id}/verification``
----------------------------------------------

Writes a member's covered fields and the verified state of all three items in
one request, so a verifier who checks three documents sends one save and the
office hears of it once.

.. code-block:: json

   {
     "medical_expiration": "2028-03-31",
     "photo_id_type": "passport",
     "verified": ["certificate", "medical", "photo_id"]
   }

``pilot_certificate_type``, ``certificate_number``, ``medical_type``,
``medical_expiration``, and ``photo_id_type`` are each optional: a given value is
written and an omitted one is left alone.  ``verified`` is required and lists the
items that should be verified after the save — ``certificate``, ``medical``,
``photo_id`` — and an item left out ends unverified.  The write goes through
``apps.members.verification.verify_member``:

#. the fields go through ``members.services.update_member`` under the caller,
   which raises ``profile_changed`` and clears every verified item whose fields
   moved; a body with no field leaves the profile, and ``profile_updated_at``,
   alone;
#. each listed item not yet verified is stamped with the time and the caller,
   and one already verified keeps its stamp, so re-verifying names whoever
   verified it first; an item the saved profile does not hold (a certificate or
   medical of ``none``, a photo ID of ``not_provided``) ends unverified even when
   listed, since there is nothing to verify;
#. the audit log records ``member.verify`` with ``verified`` (the items stamped)
   and ``cleared`` (the items verified before and not after), by slug;
#. when either list is not empty, ``verification_changed`` is raised once, with
   ``user``, ``verified`` and ``cleared`` as item labels, and ``actor``
   (:doc:`notification-events`).  A save that changes no item's state raises
   nothing.

A change and its re-verification may come together: a new
``medical_expiration`` with ``medical`` in ``verified`` clears the medical and
stamps it again under the caller.  Self-verification is allowed; nothing
compares the caller with the member.  The profile is created if the account has
none.

The profile form's two rules hold, judged on the record the write would leave:
``certificate_number`` is required once the certificate is not ``none`` and
``medical_expiration`` once the medical is not ``none``, with the same
sentences :ref:`profile-validation` gives.  A slug outside the three is refused
under ``verified``:

.. code-block:: json

   {"verified": ["Unknown item 'hours'."]}

Statuses:

* **200** — the status card, in the ``GET .../status`` shape above.
* **400** — ``verified`` missing, an unknown item, a choice outside its list, or
  a profile rule refused.  Nothing is written.
* **404** — no account has that ``user_id``, or it is a donor or deactivated.

``PUT /leader/members/{user_id}/verifier``
------------------------------------------

Grants or revokes the verifier role, for a ``dart_leader``, a ``user_admin``,
or a ``system_admin`` — not a ``verifier`` or an ``account_admin``.

.. code-block:: json

   {"verifier": true}

``accounts.services.set_verifier`` rebuilds the member's role list with
``verifier`` added or removed and writes it through
``accounts.services.update_account``, so the change is audited as
``account.roles`` and raised as ``roles_changed``, the member's other roles are
kept, and a list that changes nothing writes nothing.  A user administrator can
grant the role from ``PATCH /admin/users/{id}`` too (:doc:`api-auth`).

Statuses:

* **200** — the status card, whose ``is_verifier`` reads the result.
* **400** — ``verifier`` missing or not a boolean.
* **403** — the caller holds none of the three roles.
* **404** — no account has that ``user_id``, or it is a donor or deactivated.

``GET /leader/aircraft?n_number=``
----------------------------------

The insurance card for one airplane, keyed by normalized registration.  The
shape is ``GET /aircraft/{id}``'s, and ``pilots`` is always present here
because the endpoint is role-gated already.  The portal reads ``coverage``
before the insurance: an excluded aircraft is a no-go, *NOT COVERED* with the
reason (less its ``Not covered:`` prefix), whatever its insurance.

Statuses:

* **200** — the matching record, ``pilots`` included.
* **400** — ``n_number`` missing or normalizing to nothing, answered
  ``{"n_number": "Enter a registration, for example N12345."}``.
* **404** — the register has never seen that registration.

``PUT /leader/aircraft/{id}/verification``
------------------------------------------

Writes an aircraft's insurance fields and whether its insurance is verified.

.. code-block:: json

   {"insurance_expiration": "2028-03-01", "verified": true}

The six insurance fields — ``insurance_carrier``, ``insurance_policy_number``,
``insurance_liability_per_occurrence_cents``,
``insurance_liability_per_person_cents``, ``insurance_hull_cents``, and
``insurance_expiration`` — are each optional and validated as ``POST /aircraft``
validates them (integer cents, ``>= 0``); a given value is written and an
omitted one is left alone.  Any other register field in the body is ignored.
``verified`` is required.  The write goes through
``apps.aircraft.verification.verify_insurance``: the fields are saved and
``aircraft.services.record_updated`` records the write under the caller (the
history row, ``aircraft.update``, ``aircraft_changed`` when a column moved, and
the clearing of a verification the change made stale); then the insurance is
stamped with the time and the caller when ``verified`` is true and it is not
yet verified (verified insurance keeps its stamp), or cleared when ``verified``
is false or the saved record has no ``insurance_expiration``, which is no policy
to verify.  The audit log records ``aircraft.verify`` with whether the insurance
ends verified, and
``verification_changed`` is raised once, with ``aircraft``, ``verified`` and
``cleared`` as item labels and ``actor``, when the insurance was stamped or
cleared; a save that changes nothing raises nothing.

Statuses:

* **200** — the record, in the ``GET /aircraft/{id}`` shape with ``pilots``.
* **400** — ``verified`` missing, or a field the register's validation refuses,
  such as ``{"insurance_hull_cents": ["Enter an amount of $0 or more."]}``.
  Nothing is written.
* **404** — no aircraft has that id.


.. _api-coverage-policy:

Coverage policy
===============

``GET /aircraft/coverage-policy``
---------------------------------

The one policy saying which aircraft CalDART's insurance does not cover, open to
any authenticated user; My aircraft reads its ``note``.

.. code-block:: json

   {
     "excluded_categories": ["helicopter"],
     "excluded_airworthiness": [],
     "note": "Helicopters are not covered; talk to your DART leader before offering one."
   }

Before a system administrator has written one, the policy excludes nothing
and its note is blank.

Statuses:

* **200** — the policy.

``PUT /aircraft/coverage-policy``
---------------------------------

Replaces the policy; ``system_admin`` (or a Django superuser) only.  The body
carries all three fields.  Each list takes values of its choice set (the
categories and airworthiness classifications above) and is stored in the
order of that set, without repeats; ``note`` is plain text of at most 1,000
characters, stripped, and may be blank.  The caller is recorded as the
policy's ``updated_by``.  Every aircraft's ``coverage`` follows the new policy at
once.

Statuses:

* **200** — the stored policy, in the ``GET`` shape.
* **400** — a list value outside its choices, such as
  ``{"excluded_categories": {"0": ["\"spaceship\" is not a valid choice."]}}``,
  or a note over 1,000 characters.  Nothing is written.
* **403** — the caller is not a system administrator, an account administrator
  included.


Where the code lives
====================

=====================================  ======================================
File                                   Contents
=====================================  ======================================
``apps/aircraft/models.py``            ``Aircraft``, ``AircraftChange``,
                                       ``AircraftType``,
                                       ``AircraftTypeAlias``,
                                       ``Registration``,
                                       ``RegistryImport``,
                                       ``AircraftCoveragePolicy``,
                                       ``AircraftCategory``,
                                       ``Airworthiness``,
                                       ``normalize_n_number``
``apps/aircraft/coverage.py``          ``CoverageRule``, ``current_rule``:
                                       the coverage rule
``apps/aircraft/naming.py``            ``display_make``, ``display_model``,
                                       ``MAKE_NAMES``
``apps/aircraft/aliases.py``           ``ALIASES``, ``write_aliases``
``apps/aircraft/types.py``             ``search_types``
``apps/aircraft/registry.py``          the registry parser,
                                       ``import_registry``, the fold,
                                       ``start_import``, ``launch_import``;
                                       the ``import_faa_registry`` command
                                       in ``management/commands/`` wraps it
``apps/aircraft/services.py``          ``record_change``, ``changed_fields``,
                                       ``record_added``, ``record_updated``,
                                       ``delete_aircraft`` (each raising its
                                       event, :doc:`notification-events`),
                                       leader search, status card, insurance
                                       querysets
``apps/aircraft/verification.py``      ``INSURANCE_FIELDS``,
                                       ``clear_stale_insurance``,
                                       ``verify_insurance``
``apps/aircraft/reports.py``           The aircraft report: columns, query
``apps/aircraft/api/serializers.py``   ``NNumberField`` and the API shapes
``apps/aircraft/filters.py``           ``AircraftFilter``,
                                       ``NullsLastOrderingFilter``
``apps/aircraft/api/permissions.py``   ``AircraftPermission``
``apps/aircraft/api/views.py``         The routes above
=====================================  ======================================

Tests: ``backend/tests/test_aircraft_api.py`` (CRUD, permissions,
normalization, every filter), ``test_aircraft_types.py`` (the aircraft types,
their display names, aliases, and search), ``test_registry_import.py`` (the
parser, the import, the fold, and the command), ``test_registry_api.py`` (the
type search against the fixture, New aircraft type, the lookup, and the status),
``test_registry_search.py`` (the N-number prefix search and its index), ``test_aircraft_history.py`` (the change rows the
register's writes leave and the history endpoint),
``test_aircraft_exports.py`` (the aircraft report: CSV content, PDF
validity, subtitle), ``test_aircraft_categories.py`` (the category and
airworthiness: the import's codes, the record, filters, and exports),
``test_aircraft_coverage_policy.py`` (the policy endpoint, the rule, and where
it is shown), ``test_leader_api.py`` (search, the membership ×
medical × insurance truth table), ``test_verification.py``,
``test_verification_api.py``, and ``test_verifier_role.py`` (verification:
see :doc:`verification`), and ``test_aircraft_models.py`` from the
foundation.
