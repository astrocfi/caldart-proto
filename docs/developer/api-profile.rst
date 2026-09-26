========================
API: member self-service
========================

The member self-service half of the API, plus the pair of endpoints that
attach an aircraft to the member's profile and detach it (the rest of the
aircraft API is in :doc:`api-aircraft`).  Every ``/me/...`` endpoint acts on the
signed-in user and no one else; ``/darts`` and ``/plans`` are public so the
join wizard can render before the visitor has an account.

Conventions are the ones in :doc:`api-reference`: session authentication,
``X-CSRFToken`` on unsafe methods, ISO-8601 dates, DRF error bodies.  An
unauthenticated request to a protected endpoint returns **401**, not 403 —
unless it is an unsafe method carrying no CSRF token, which is refused with
**403** before the permission check.  Both answers are the same on every
``/me/...`` endpoint and are not repeated in the status lists below.


Summary
=======

===========================================  =======================  ===============
Endpoint                                     Methods                  Who
===========================================  =======================  ===============
``/api/v1/me/profile``                       ``GET PUT PATCH``        any signed-in user
``/api/v1/me/profile/aircraft``              ``POST``                 any signed-in user
``/api/v1/me/profile/aircraft/{id}``         ``DELETE``               any signed-in user
``/api/v1/me/membership``                    ``GET``                  any signed-in user
``/api/v1/me/payments``                      ``GET``                  any signed-in user
``/api/v1/darts``                            ``GET``                  public
``/api/v1/plans``                            ``GET``                  public
===========================================  =======================  ===============

There is no role check beyond authentication: the resource *is* the caller,
so there is no id to tamper with.  A member with no ``MemberProfile`` row
gets an empty one created on first read or first attach, which keeps
accounts created outside the registration flow usable.  A method outside the
column above is a **405** — ``DELETE /me/profile`` among them, because a member
may empty their profile but not remove it.


``GET /me/profile``
===================

Returns every ``MemberProfile`` field except the admin-only ``notes`` and
``how_heard``, creating an empty profile row first if the account has none.

.. code-block:: json

   {
     "phone": "650-555-0101",
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
     "dart": {"id": 9, "name": "San Carlos"},
     "air_care_alliance_number": "",
     "pilot_certificate_type": "private",
     "certificate_number": "3141592",
     "ifr_rated": "yes",
     "ratings": ["instrument"],
     "medical_type": "third",
     "medical_expiration": "2029-05-31",
     "medical_is_current": true,
     "flight_review_date": null,
     "total_hours": 750,
     "aircraft": [
       {
         "id": 7,
         "n_number": "N12345",
         "make": "Cessna",
         "model": "182T Skylane",
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
     "vol_newsletter": false
   }

Read-only fields
  ``dart`` (a ``{id, name}`` stub — write ``dart_id`` instead),
  ``aircraft`` (maintained through the attach/detach endpoints) and
  ``medical_is_current`` (a property: the expiration date is on or after
  today, for BasicMed and class medicals alike; ``medical_type: "none"``
  is always ``false``).

Statuses:

* **200** — the profile above.


``PUT /me/profile``
===================

A **genuine full update**: any writable field left out of the body is reset to
its model default, so a cleared text box really is cleared, an unticked
checkbox really is unticked, and an omitted ``dart_id`` clears the DART.

.. code-block:: json

   {
     "phone": "650-555-0101",
     "address_line1": "1 Embarcadero",
     "city": "San Carlos",
     "state": "ca",
     "postal_code": "94070",
     "dart_id": 9,
     "pilot_certificate_type": "private",
     "certificate_number": "3141592",
     "ratings": ["instrument"],
     "medical_type": "third",
     "medical_expiration": "2029-05-31",
     "vol_ground_team": true
   }

That reset is a deliberate departure from DRF's default, which ignores absent
optional fields even on a full update and would make the two verbs identical.
The portal always sends the complete form on ``PUT``.  The response is the
stored profile in the ``GET`` shape above, so ``state`` comes back upper-cased
and ``dart`` as its ``{id, name}`` stub.

Statuses:

* **200** — the updated profile.
* **400** — ``phone`` missing, or any rule in :ref:`profile-validation`
  refused.  Nothing is written.


``PATCH /me/profile``
=====================

Changes only the fields the body names and leaves the rest of the row alone.

.. code-block:: json

   {"medical_type": "basicmed", "medical_expiration": "2030-04-30"}

The two cross-field rules are evaluated against the row as it *would be* after
the write, so a ``PATCH`` that sets only ``medical_type`` is rejected unless an
expiration date is already stored.  The response is the stored profile in the
``GET`` shape above.

Statuses:

* **200** — the updated profile.
* **400** — a blank ``phone``, or any rule in :ref:`profile-validation`
  refused.  Nothing is written.

.. _profile-validation:

Validation
----------

``dart_id`` is the write side of ``dart``.  It accepts the id of an **active**
``Dart`` or ``null``; an inactive or unknown id is a 400 on ``dart_id``.

===========================  ===========================================================
Field                        Rule
===========================  ===========================================================
``phone``                    Required on ``PUT``; never blank on ``PATCH``.  Stored
                             as ``XXX-XXX-XXXX``: ``+1``, spaces, dots and brackets
                             are accepted and none of them are kept, and anything
                             that is not ten digits is refused.
``phone_alt``,               The same rule, and both may be blank.
``emergency_contact_phone``
``phone_extension``,         Up to six digits if given.  Each number has an
``phone_alt_extension``,     extension of its own, so nobody appends one to a
``emergency_contact_``       number and breaks the stored format.
``phone_extension``
``home_airport_identifier``  Three letters or digits if given, upper-cased on the
                             way in.  The four-letter ICAO spelling is accepted
                             and trimmed, so ``KCRQ`` is stored as ``CRQ``; a
                             three-character identifier that begins with ``K``
                             is left alone, because Kelso really is ``KLS``.
``state``                    One of the two-letter codes, and required: the fifty
                             states, DC, and the territories with USPS codes.
``postal_code``              Five digits if given.  ZIP+4 is refused: five reach
                             anybody, and are one thing to keep right.
``county``                   One of California's fifty-eight, or blank for a member
                             who lives elsewhere.
``total_hours``              ``0`` to ``99999`` if given.  A larger number is a typo:
                             the highest civil totals on record are under 60,000.
``ratings``                  Each value from ``asel, amel, ases, ames, helicopter,
                             instrument, cfi, cfii, mei``; repeats are dropped and the
                             order is kept.
``medical_expiration``       Required once ``medical_type`` is anything but ``none``.
``certificate_number``       Required once ``pilot_certificate_type`` is anything but
                             ``none``.
===========================  ===========================================================

A rejection is a normal DRF 400, keyed on the field it belongs to, and both
cross-field complaints are raised together when both apply:

.. code-block:: json

   {
     "medical_expiration": ["Give the expiration date of your medical certificate."],
     "certificate_number": ["Give your pilot certificate number."]
   }

The field-level sentences are "Use a ten-digit number like 415-555-0100." for
each of the three phone fields, "An extension is digits only, for example
4021.", "Use a five-digit ZIP code like 95035.", and "Use a three-character
identifier like PAO, E16, or KLS."  ``state`` and ``county``
are choice fields, so an unknown value is DRF's own "is not a valid choice".

The portal's form applies the same rules before it sends anything, and on top
of them marks as required the six fields that make a profile complete
(:ref:`profile-completeness`).  The server stays authoritative: only ``phone``
is required there, so an API client may store a partial profile.

.. _profile-completeness:

Profile completeness
--------------------

A profile is complete when ``phone``, ``address_line1``, ``city``, ``state``,
``postal_code``, and ``pilot_certificate_type`` all have a value.  That list is
``MemberProfile.COMPLETE_FIELDS``.  The certificate box always holds a value,
and *Not a pilot* counts; ``state`` is a list that defaults to ``CA``.

One list serves every reader of it:

- ``profile_complete`` on the user payload (:doc:`api-auth`) is
  ``MemberProfile.is_complete`` over those six fields.  It is what the
  dashboard nudge and the join wizard's step gating key off.
- The portal's profile form requires exactly the same six
  (``REQUIRED_PROFILE_FIELDS`` in
  ``frontend/src/portal/features/profile/form.ts``), so a profile the form
  saves is a profile the server calls complete.
- This endpoint requires only ``phone``, so an API client — or an account
  administrator creating a member through
  :doc:`api-members` — can store a profile that is not yet complete.


``POST /me/profile/aircraft``
=============================

Attaches an aircraft to the caller's "planes commonly flown" and answers with
the whole list, so the client never has to re-read the profile.

.. code-block:: json

   {"aircraft_id": 7}

.. code-block:: json

   {
     "aircraft": [
       {
         "id": 7,
         "n_number": "N12345",
         "make": "Cessna",
         "model": "182T Skylane",
         "insurance_is_current": true,
         "insurance_expiration": "2027-03-01",
         "insurance_summary": "$1,000,000 / $100,000 · exp 2027-03-01"
       }
     ]
   }

Idempotent — attaching twice is a no-op that returns the same list.

Statuses:

* **200** — the caller's aircraft list, including the one just attached.
* **400** — ``aircraft_id`` is missing, reported as
  ``{"aircraft_id": ["This field is required."]}``, or is present but not an
  integer, reported as ``{"aircraft_id": ["A valid integer is required."]}``.
* **404** — no aircraft has that id.


``DELETE /me/profile/aircraft/{aircraft_id}``
=============================================

Detaches the aircraft again, with an empty body.  Only the caller's link is
removed — the ``Aircraft`` row and other members' links to it are untouched.

Statuses:

* **204** — the link is gone, and also when the caller never had it.
* **404** — no aircraft has that id.


``GET /me/membership``
======================

The ``membership_status`` dict (see :doc:`data-model`) plus the caller's
full term history, newest first.

.. code-block:: json

   {
     "status": "current",
     "expires_on": "2027-06-30",
     "plan": "Annual",
     "is_lifetime": false,
     "history": [
       {"id": 12, "plan": "Annual", "starts_on": "2026-07-01",
        "ends_on": "2027-06-30", "status": "active", "source": "payment"}
     ]
   }

``status`` is ``current``, ``new``, ``expired``, ``none``, or ``friend``.
``expires_on`` is the end of the member's *unbroken* coverage, so a renewal
bought today shows next year's date immediately; it is ``null`` for a lifetime
membership.  A member who has never held a term gets ``status: "none"`` and an
empty ``history`` rather than a 404.

A friend of CalDART (:ref:`kinds of account <account-kinds>`) gets ``status: "friend"`` with
``expires_on`` and ``plan`` null and ``is_lifetime`` false, whatever terms they
held as a member; those terms are still listed in ``history``.  So does a member
whose ``friend_on`` date has arrived, before the nightly run writes the change
down.

Statuses:

* **200** — the dict above.


``GET /me/payments``
====================

The caller's payments, newest first, unpaginated.

.. code-block:: json

   [
     {"id": 31, "plan": "Annual", "amount_cents": 6500,
      "contribution_cents": 2000, "provider": "stripe",
      "status": "succeeded", "completed_at": "2026-07-01T18:22:05.601884-07:00"}
   ]

``plan`` is ``null`` for a payment that was a pure contribution, and
``completed_at`` is ``null`` for one that never succeeded.  Datetimes are
rendered in the server's configured ``TIME_ZONE``, so they carry an offset
rather than a trailing ``Z``.  An administrator
reading the same payments through :doc:`api-members` sees more fields; this
shape is the member's own.

Statuses:

* **200** — the array above, empty when the member has never paid.


``GET /darts``
==============

Public.  Active DARTs only, in their configured ``sort_order`` then name.
Unpaginated.

.. code-block:: json

   [{"id": 9, "name": "San Carlos", "airport_identifiers": "SQL", "city": "San Carlos"}]

Statuses:

* **200** — the array above, for a signed-in caller and an anonymous one
  alike.


``GET /plans``
==============

Public.  Active membership plans only, in their configured order.
Unpaginated.  ``duration_days`` is ``null`` for a lifetime plan.

.. code-block:: json

   [
     {"slug": "annual", "name": "Annual", "price_cents": 4500,
      "duration_days": 365, "description": "One year of CalDART membership..."},
     {"slug": "life", "name": "Life", "price_cents": 65000,
      "duration_days": null, "description": "A lifetime membership..."}
   ]

Statuses:

* **200** — the array above, for a signed-in caller and an anonymous one
  alike.


Where the code lives
====================

==========================================================  ==========================
Module                                                      Holds
==========================================================  ==========================
``backend/apps/members/api/profile_serializers.py``         every serializer and rule
``backend/apps/members/api/serializers.py``                 the plan and membership
                                                            shapes, shared with the
                                                            accounts and payments APIs
``backend/apps/members/api/profile_views.py``               the views
``backend/apps/members/api/actors.py``                      the signed-in account
                                                            behind a request
``backend/apps/members/api/profile_urls.py``                the routes
``backend/tests/test_profile_api.py``                       profile, membership,
                                                            payments, catalogs
``backend/tests/test_profile_aircraft_api.py``              attach and detach
``frontend/src/portal/features/profile/api.ts``             the TanStack Query hooks
==========================================================  ==========================

``AircraftSummarySerializer`` comes from ``apps.aircraft.api.serializers``,
and ``PlanSerializer`` from ``apps.members.api.serializers``: both shapes are
declared once and matched by ``AircraftSummary`` and ``Plan`` in
``portal/api/types.ts``.
