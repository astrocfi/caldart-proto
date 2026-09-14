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
unauthenticated request to a protected endpoint returns **401**, not 403.


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
accounts created outside the registration flow usable.


``GET /me/profile``
===================

Returns every ``MemberProfile`` field except the admin-only ``notes`` and
``how_heard``.

.. code-block:: json

   {
     "phone": "650-555-0101",
     "phone_alt": "",
     "address_line1": "1 Embarcadero",
     "address_line2": "",
     "city": "San Carlos",
     "state": "CA",
     "postal_code": "94070",
     "county": "San Mateo",
     "emergency_contact_name": "Dana Lee",
     "emergency_contact_phone": "650-555-0199",
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


``PUT`` and ``PATCH /me/profile``
=================================

``PUT`` is a **genuine full update**: any writable field left out of the
body is reset to its model default, so a cleared text box really is
cleared, an unticked checkbox really is unticked, and an omitted
``dart_id`` clears the DART.  ``PATCH`` changes only what it names.

That is a deliberate departure from DRF's default, which ignores absent
optional fields even on a full update and would make the two verbs
identical.  The portal always sends the complete form on ``PUT``.

``dart_id``
  The write side of ``dart``.  Accepts the id of an **active** ``Dart`` or
  ``null``; an inactive or unknown id is a 400 on ``dart_id``.

Validation
----------

===========================  ===========================================================
Field                        Rule
===========================  ===========================================================
``phone``                    Required on ``PUT``; never blank on ``PATCH``.
``state``                    Two letters if given; stored upper-cased (``ca`` → ``CA``).
``postal_code``              ``12345`` or ``12345-6789`` if given.
``ratings``                  Each value from ``instrument, multi_engine, cfi, cfii,
                             mei, seaplane, helicopter, glider``; repeats are dropped
                             and the order is kept.
``medical_expiration``       Required once ``medical_type`` is anything but ``none``.
``certificate_number``       Required once ``pilot_certificate_type`` is anything but
                             ``none``.
===========================  ===========================================================

The two cross-field rules are evaluated against the row as it *would be*
after the write, so a ``PATCH`` that sets only ``medical_type`` is rejected
unless an expiration date is already stored.

A rejection is a normal DRF 400:

.. code-block:: json

   {"medical_expiration": ["Give the expiration date of your medical certificate."]}

The portal's form applies the same rules before it sends anything, and marks
``phone``, ``address_line1``, ``city`` and ``postal_code`` as required on top
of them.  The server stays authoritative: only ``phone`` is required there, so
an API client may store a partial profile.

.. _profile-completeness:

Profile completeness
--------------------

A profile is complete when ``phone``, ``address_line1``, ``city``,
``postal_code`` and ``pilot_certificate_type`` all have a value.  That list is
``MemberProfile.COMPLETE_FIELDS``.  The certificate box always holds a value,
and *Not a pilot* counts.  ``state`` is not part of the rule.

One list serves every reader of it:

- ``profile_complete`` on the user payload (:doc:`api-auth`) is
  ``MemberProfile.is_complete`` over those five fields.  It is what the
  dashboard nudge and the join wizard's step gating key off.
- The portal's profile form requires exactly the same five
  (``REQUIRED_PROFILE_FIELDS`` in
  ``frontend/src/portal/features/profile/form.ts``), so a profile the form
  saves is a profile the server calls complete.
- This endpoint requires only ``phone``, so an API client — or an account
  administrator creating a member through
  :doc:`api-members` — can store a profile that is not yet complete.


``POST /me/profile/aircraft``
=============================

Attaches an aircraft to the caller's "planes commonly flown".

.. code-block:: text

   POST /api/v1/me/profile/aircraft
   {"aircraft_id": 7}

   200 OK
   {"aircraft": [ ...aircraft summaries... ]}

Idempotent — attaching twice is a no-op that returns the same list.  An
unknown ``aircraft_id`` is **404**; a missing one is **400**.


``DELETE /me/profile/aircraft/{aircraft_id}``
=============================================

Detaches it again and returns **204**.  Detaching something that was never
attached is a no-op, also 204; an unknown aircraft is **404**.  Only the
caller's link is removed — the ``Aircraft`` row and other members' links to
it are untouched.


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

``status`` is ``current``, ``expired`` or ``none``.  ``expires_on`` is the
end of the member's *unbroken* coverage, so a renewal bought today shows
next year's date immediately; it is ``null`` for a lifetime membership.


``GET /me/payments``
====================

The caller's payments, newest first, unpaginated.

.. code-block:: json

   [
     {"id": 31, "plan": "Annual", "amount_cents": 6500,
      "contribution_cents": 2000, "provider": "stripe",
      "status": "succeeded", "completed_at": "2026-07-01T18:22:05Z"}
   ]

``plan`` is ``null`` for a payment that was a pure contribution.


``GET /darts``
==============

Public.  Active DARTs only, in their configured ``sort_order`` then name.
Unpaginated.

.. code-block:: json

   [{"id": 9, "name": "San Carlos", "airport_identifier": "SQL", "city": "San Carlos"}]


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


Where the code lives
====================

==========================================================  ==========================
Module                                                      Holds
==========================================================  ==========================
``backend/apps/members/api/profile_serializers.py``         every serializer and rule
``backend/apps/members/api/profile_views.py``               the views
``backend/apps/members/api/profile_urls.py``                the routes
``backend/tests/test_profile_api.py``                       profile, membership,
                                                            payments, catalogs
``backend/tests/test_profile_aircraft_api.py``              attach and detach
``frontend/src/portal/features/profile/api.ts``             the TanStack Query hooks
==========================================================  ==========================

``AircraftSummarySerializer`` is declared in ``profile_serializers.py``
rather than imported from ``apps.aircraft`` so the members app does not
depend on a module owned by another branch; the shape is the one §6.5
specifies and matches ``AircraftSummary`` in ``portal/api/types.ts``.
