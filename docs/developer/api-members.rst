===========================
API: members administration
===========================

The ``account_admin`` half of the members app, endpoint by endpoint, plus the
membership-status rules the list filters on.  The membership report downloads
the list below with the same filters and ordering; it is served by
:doc:`api-reports` and described in :doc:`reports`.

Every route below requires the ``account_admin`` role but one: ``GET
/admin/members``, the list, also admits ``dart_leader``, so a DART leader reads
the whole membership and downloads its report.  Creating a member, one member's
record, and the membership terms stay with the account administrator; a
treasurer reads none of them.  ``system_admin`` passes every role check, so a
system administrator has them too.  An
unauthenticated request gets **401** (``caldart.exceptions`` overrides DRF's
403 for session auth); an authenticated request without the role gets **403**.
An unsafe method with no ``X-CSRFToken`` gets **403** before either check,
signed in or not.  Those two answers are the same on every endpoint here and
are not repeated in the status lists below.

The DART catalog and the DART screen live in their own app; see
:doc:`api-darts`.  The code here lives in ``backend/apps/members/``:

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
``filters.py``
   The filter set, the ordering backend, and the queryset the list is served
   from.  The membership annotations it builds on live in ``services.py``.
``services.py``
   The member record itself: ``register_member``, ``create_member``,
   ``update_member``, and ``delete_member`` own the rules the endpoints below
   state, and the account half of each goes to ``accounts.services``.  The
   membership status, ``activate_term``, and ``grant_term`` live here too.  The
   notification events these raise are listed in :doc:`notification-events`.
``api/actors.py``
   ``acting_user(request)``, the signed-in account behind a request every
   view here has already gated on a role.
``api/admin_urls.py``
   Routes, included from ``api/urls.py``.
``reports.py``
   The membership report: its column list and the query it runs, which applies
   the list's filter set and ordering.


Endpoints
=========

::

  GET    /api/v1/admin/members
  POST   /api/v1/admin/members
  GET    /api/v1/admin/members/{user_id}
  PATCH  /api/v1/admin/members/{user_id}
  DELETE /api/v1/admin/members/{user_id}
  POST   /api/v1/admin/members/{user_id}/memberships
  POST   /api/v1/admin/members/{user_id}/friend
  POST   /api/v1/admin/members/{user_id}/deactivate
  POST   /api/v1/admin/members/{user_id}/reactivate
  PATCH  /api/v1/admin/memberships/{id}

``{user_id}`` is the **user's** id, not a profile id.  The list holds every
member and every friend: a donor is never listed, and a deactivated account
only on request (``include_inactive``).  The single record,
``GET /admin/members/{user_id}``, answers for any account, a donor's and a
deactivated one's included, so an administrator can reactivate an account and
an edit to a donor is refused with its reason rather than a 404.  A donor is on
no member list, so the portal opens a donor's record from the donors report, and
any account's from the **Member record** link on a payment, a member's ledger
(:doc:`api-finance`), and the user record, each shown to a reader holding
``account_admin``.  The record's ``DELETE`` removes a donor as it removes any
account, handing the gifts to the tombstone :ref:`described below
<api-members-delete>`; a donor is refused a granted term.  A tombstone's record
refuses every change (:ref:`api-members-tombstone`).


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
         "kind": "member",
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
         "joined_on": "2024-07-01",
         "profile_updated_at": "2026-08-11T09:14:02.100522-07:00",
         "certificate_number": "1234567",
         "instrument": true,
         "home_airport": "PAO",
         "secondary_airport": "",
         "city": "Palo Alto",
         "state": "CA",
         "county": "Santa Clara",
         "ham_callsign": "",
         "member_since": null
       }
     ]
   }

The row is ``MemberRow`` in ``frontend/src/portal/api/types.ts``.  ``kind`` is
``member`` or ``friend``, as stored (:ref:`kinds of account <account-kinds>`): a donor is
never a row.  An effective friend's ``membership.status`` is always ``friend``,
and that includes a row whose stored ``kind`` is ``member`` but who holds no
started term that is active, expired, or suspended: nobody is a member until a
paid or granted term has started.  A member whose only started terms are
suspended also reads ``friend``.  ``joined_on`` is the start of the earliest membership term, or ``null`` for
somebody who has never had one.  ``profile_updated_at`` is when profile
information was last written -- see :doc:`data-model` -- and ``null`` for a
profile nobody has edited, or for an account with none.  An account with no
``MemberProfile`` row still appears: ``phone`` is blank, ``dart``, and
``medical_expiration`` are ``null``, ``pilot_certificate_type``, and
``medical_type`` read ``none``, ``medical_is_current`` is false and
``aircraft`` is empty.

The row also carries every profile value the members report can add as a column,
so the list's table can show whatever its column chooser picks:
``certificate_number``, ``instrument`` (true or false for a pilot, by whether the
ratings hold an instrument rating, and ``null`` for somebody who holds no
certificate), ``home_airport`` and ``secondary_airport`` (identifiers), ``city``,
``state``, ``county``, ``ham_callsign``, and ``member_since`` (the day the member
says they joined, or ``null``).  Without a profile the text fields are blank and
``instrument`` and ``member_since`` are ``null``.

Statuses:

* **200** — the page of rows, empty ``results`` when nothing matches.
* **400** — ``kind``, ``status``, ``certificate``, ``medical``, ``county``, or ``role``
  carried a value outside its choice list, or ``expiring_within`` was not a number.  The
  body is keyed on the offending parameter, for example
  ``{"status": ["Select a valid choice. bogus is not one of the available
  choices."]}``.

Filters
-------

``kind``
   ``member`` | ``friend``, matched against the effective kind worked out for
   today: a member whose ``friend_on`` date has arrived is a ``friend``, and one
   whose date is still to come a ``member``; a member who has never paid or been
   granted a term is a ``friend``.  Absent or blank lists both;
   ``donor`` and anything else is a 400, since a donor is never listed.
``search``
   Case-insensitive substring of the full name, the email address, either
   phone number, or the pilot certificate number.  The full name is matched as
   one string, so ``Ana Bracco`` works.
``status``
   ``current`` | ``expired`` | ``friend`` | ``donor``.  The first three
   partition the table; ``donor`` is accepted and lists nobody, since a donor
   is never a row.  ``friend`` is every account whose effective kind is
   friend, whatever its terms, and also any member whose only started terms
   are suspended; no other status lists either.
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
``county``
   One or more of California's 58 counties, separated by commas
   (``county=Alameda,Marin``), each spelled as the profile stores it
   (``San Mateo``) and matched exactly: ``Santa Clara`` never lists Santa
   Barbara's members.  The list holds the members of any county named.  A blank
   value narrows nothing; a list naming any county outside California is a 400
   naming that county.
``role``
   A role slug.  This matches the group actually assigned, so ``role=member``
   does not include a system administrator who lacks the ``member`` group.
``expiring_within``
   A number of days.  Selects current members whose computed expiry falls on
   or before ``today + N``.  Lifetime members and friends are never matched,
   whatever terms a friend holds.  ``N`` is
   clamped to ``0..3650`` (ten years): a negative value behaves like ``0``,
   and a value past the limit like the limit, so an oversized or negative
   query string never produces a server error.
``include_inactive``
   ``true`` lists deactivated accounts beside the active ones.  Absent,
   ``false``, or any other value leaves them out: the list shows active
   accounts only unless asked.  The members report reads the same filters but
   never lists a deactivated account, whatever this says.

Ordering
--------

``?ordering=`` takes ``pilot``, ``name``, ``email``, ``dart``, ``expires_on``,
``joined`` or ``updated``, each optionally prefixed with ``-``.  Anything else
falls back to ``name`` rather than being refused.

Every alias ends in keys that settle a tie, so two rows the caller's sort cannot
separate — two members of one DART, two people whose membership runs out on the
same day — still come back in a stable, readable order:

============ ==================================================================
``ordering`` Sorts on, in order
============ ==================================================================
pilot        ``pilot_rank``, surname, forename
name         surname, forename, DART name, email
email        email, surname, forename
dart         DART name, surname, forename
expires_on   computed expiry, surname, forename
joined       start of the earliest term, surname, forename
updated      ``profile_updated_at``, surname, forename
============ ==================================================================

``pilot_rank`` ranks a current medical ahead of a lapsed one ahead of a
non-pilot, which is the order the list's Pilot column reads in.  The two date
sorts, ``updated``, and ``dart``, keep rows with no value at the end in both
directions, so lifetime members do not crowd out the answer to "who expires
next", and a profile nobody has ever edited does not crowd out "who was
touched most recently" — that question is ``-updated``, since ``updated``
follows the same positive-column, ``-`` reverses convention as every other
alias here and so sorts oldest edit first.


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
   suspended.  Paired with ``covers_today`` it separates the other statuses: a
   member not covering but started is ``expired``.  A member row with nothing
   covering today and no started term that is neither canceled nor suspended
   (only suspended terms) reads ``friend``.
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
   The most recent term that has started and is neither canceled nor
   suspended, reported when nothing covers today.
``joined_on``
   The earliest term's ``starts_on``.
``effective_kind``
   ``friend`` when the stored ``kind`` is ``friend``, ``friend_on`` has
   arrived, or the stored ``kind`` is ``member`` and no term that is active,
   expired, or suspended has started; the stored kind otherwise.  A ``friend`` row reads as ``friend``
   before any term annotation is looked at, and is what ``?status=friend``
   filters on.

``member_admin_queryset`` hangs those on the user table through
``members.services.with_membership`` and adds the two the list needs of its
own, in ``filters.derived_annotations()``:

``full_name``
   ``first_name`` and ``last_name`` concatenated, so ``?search=`` can match a
   full name in one ``icontains``.
``effective_expiry``
   ``NULL`` for a friend (whose row shows no date), else ``coverage_end`` when
   ``covers_today``, else ``past_end``.  This is the column
   ``?ordering=expires_on`` actually sorts on, with ``NULL`` — friends, lifetime
   members, and people with no started term — forced to the end in both
   directions.

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
``backend/tests/test_members_admin_status.py`` builds twenty histories —
early renewals, three-term chains, gaps, overlaps, cancellations, a lifetime
plan bought to follow an annual one, a term ending exactly today, friends with
lapsed and live terms, conversions to friend due and still ahead — and asserts
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
     "kind": "member",
     "profile": {"phone": "408-555-0199", "dart_id": 3, "ratings": ["instrument"]}
   }

Only ``email``, ``first_name``, and ``last_name`` are required — an administrator
records what they were told, which on the day somebody joins at an airshow may be no
more than a name and an address.  A missing or blank name is refused with "Enter a
first name." or "Enter a last name.", and every phone number in ``profile`` is
optional.
``kind`` is ``member`` (the default) or ``friend``; an administrator never
creates a donor, and ``donor`` is a 400 on ``kind``.

``profile`` is ``AdminProfileSerializer``, which extends the ``/me/profile``
serializer: the same fields except ``first_name`` and ``last_name``, which the
member record takes as account fields beside ``email`` (``dart`` reads nested
and is written as ``dart_id``), the same rules — a two-letter state, a well-formed ZIP code, an
expiry date whenever a medical class is given, a number whenever a certificate
is — plus ``notes`` and ``how_heard``, and nothing mandatory.

The user, of the kind posted, is granted the ``member`` role and given an empty
``MemberProfile``
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
Following the invitation's link proves the address, so it also marks the account
verified.  With a ``password`` no invitation is sent; the address is mailed a
verification link instead, on commit in the same way (see the email
verification section of :doc:`api-auth`).  A mail server that refuses either
message leaves the member created and the answer a 201: the failed send is on
the Sent emails page and the refusal is logged
(:ref:`refused sends <api-refused-send>`).

Statuses:

* **201** — the member record, in the detail shape below.
* **400** — a duplicate email address (compared case-insensitively, reported as
  ``{"email": ["An account with that email address already exists."]}``), a
  missing ``email``, a missing or blank ``first_name`` or ``last_name``
  (``{"first_name": ["Enter a first name."]}``), a password one of Django's
  validators refused, an unknown
  rating, or any profile rule the nested serializer states.  Nothing is
  written.


``GET /admin/members/{user_id}``
================================

The whole record: the account, its roles, the computed membership, the profile
*including* ``notes`` and ``how_heard``, every membership term newest first,
and every payment newest first.  ``email_verified_at`` is when the member last
proved the address by following a verification, reset, or invitation link sent
to it, and ``null`` while it is unverified.  ``email_bounced_at`` is when the
bounce check last found the address bouncing, and ``null`` while no bounce is
known; ``email_bounce_detail`` is that report's status code and diagnostic, or
``""`` (:ref:`email-bounces`).  Both are read-only: a user administrator clears
them from the user record (:ref:`api-clear-bounce`).

.. code-block:: json

   {
     "id": 11,
     "email": "ana@example.org",
     "first_name": "Ana",
     "last_name": "Bracco",
     "name": "Ana Bracco",
     "is_active": true,
     "reactivation_blocked": false,
     "kind": "member",
     "is_tombstone": false,
     "friend_on": null,
     "roles": ["member"],
     "created_at": "2024-07-01T16:04:11.318204-07:00",
     "email_verified_at": "2024-07-01T16:09:52.004117-07:00",
     "email_bounced_at": null,
     "email_bounce_detail": "",
     "joined_on": "2024-07-01",
     "profile_updated_at": "2026-08-11T09:14:02.100522-07:00",
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
       "ham_callsign": "",
       "home_airport_identifier": "SQL",
       "secondary_airport_identifier": "",
       "dart": {"id": 3, "name": "Palo Alto"},
       "air_care_alliance_number": "",
       "pilot_certificate_type": "private",
       "certificate_number": "3141592",
       "ratings": ["instrument"],
       "medical_type": "third",
       "medical_expiration": "2027-01-31",
       "medical_is_current": true,
       "flight_review_date": null,
       "total_hours": 750,
       "photo_id_type": "passport",
       "verification": {
         "certificate": {"verified": false, "verified_by": null, "verified_at": null},
         "medical": {"verified": false, "verified_by": null, "verified_at": null},
         "photo_id": {"verified": false, "verified_by": null, "verified_at": null}
       },
       "aircraft": [
         {
           "id": 7,
           "n_number": "N172SP",
           "make": "Cessna",
           "model": "172S Skyhawk",
           "type": {"id": 3, "make": "Cessna", "model": "172S Skyhawk", "seats": 4, "engines": 1, "is_custom": false},
           "insurance_is_current": true,
           "insurance_expiration": "2027-03-01",
           "insurance_summary": "$1,000,000 / $100,000 · exp 2027-03-01",
           "insurance_verified": false
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

``is_tombstone`` is true for a **Deleted member <id>** account
(:ref:`api-members-tombstone`), whose record the portal shows with no form, no
grant, and no delete.
``profile`` is ``null`` for an account that has no ``MemberProfile`` row.
Its ``photo_id_type`` and read-only ``verification`` are the ones
``GET /me/profile`` describes (:doc:`api-profile`).
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
     "profile": {"medical_type": "basicmed", "notes": "Moved to BasicMed."}
   }

The body takes ``email``, ``first_name``, ``last_name``, ``kind``, and a partial
``profile`` object; an ``is_active`` in it is ignored, since the account's status
changes only through ``/deactivate`` and ``/reactivate`` below.  A profile is created if the account
somehow has none.  ``PUT`` is not offered.

``first_name`` and ``last_name`` are stored as every write stores a name
(``caldart.casing.person_name``, :doc:`data-model`), so ``SMITH`` is saved, and
answered, as ``Smith``.  A name left out is left alone; one sent blank, or as spaces
only, is a **400** ``{"first_name": ["Enter a first name."]}`` or
``{"last_name": ["Enter a last name."]}``, and nothing is written.

``kind`` is ``member`` or ``friend``.  A kind other than the stored one makes
the account that kind at once through ``accounts.services.set_kind``: any
pending ``friend_on`` is cleared, and the change is audited as ``account.kind``
with ``to=<kind>`` under the administrator.  The stored kind sent again is no
change, so a pending ``friend_on`` survives a save that only corrects a phone
number; the portal sends ``kind`` only when the administrator changed it.  A donor's kind is never changed by hand — a donor
becomes a member or a friend only by registering — so ``kind`` on a donor's
record is a **400** ``{"kind": ["A donor becomes a member or a friend only by
registering."]}``, and ``donor`` is not a value the field takes.

The nested profile serializer is bound to the stored row before validation, so
a partial update is judged against the whole profile: sending only
``medical_type`` does not trip the "a medical class needs an expiry date" rule
when the record already has one.

A ``profile`` that moves a field a verified item covers clears that item, as a
member's own edit does (:doc:`verification`); ``verification`` itself is
read-only here too, and an item is verified only through the member check.

``profile_updated_at`` is stamped when the body carries ``profile``, or an
``email``, ``first_name`` or ``last_name`` -- the fields a member record shows
alongside the rest of the profile.  A request that only changes ``kind`` leaves
the stamp alone, and so does one for a target with no profile row to stamp.

A write that really changes ``email`` — compared stripped and
case-insensitively — clears ``email_verified_at`` and, once it commits, mails
the new address a verification link.  A refused link leaves the edit standing
and the answer unchanged (:ref:`refused sends <api-refused-send>`).

``email`` goes through the same account-edit guard as ``PATCH
/admin/users/{id}`` — see :ref:`account-edit-guard`.  An account administrator
may move a plain member's address, but not the address of an account holding a
role they do not hold themselves.  A refusal is a **400** keyed on ``email``, and
nothing is written at all — the profile half of the same request included.

Deactivation (``POST /admin/members/{user_id}/deactivate`` below) is the tool for
a member who has left.  The hard delete below is for duplicates, spam, test
accounts, and a person who asks to be removed; their payments stay in the books.

Statuses:

* **200** — the updated record, in the detail shape above.
* **400** — an email address another account already holds, a profile rule the
  nested serializer refused, an edit the account-edit guard refused, or a
  ``kind`` for a donor.  Any body at all for a tombstone is a **400**
  ``{"detail": "This record keeps a deleted member's payments in the books and
  cannot be changed."}`` (:ref:`api-members-tombstone`).  Nothing is written.
* **404** — no account has that id.
* **405** — the request used ``PUT``.


.. _api-members-delete:

``DELETE /admin/members/{user_id}``
===================================

Hard-deletes the account: the cascade takes the profile, the membership terms,
the automatic payments, and the contribution statements with it.  There is no
response body.

The delete is refused when

* the target is a tombstone, which holds a deleted account's payments
  (:ref:`api-members-tombstone`);
* the target is the caller — you cannot delete your own account, whatever roles
  you hold; or
* the target is a ``system_admin``, unless the caller is a ``system_admin``.

The two role tests read *effective* roles, so a Django superuser without the
role group counts as a system administrator on either side.  A refusal writes
nothing.

Payments are kept.  A payment is revenue or a donation, and the accounts must
not change after the fact, so ``Payment.user`` is ``PROTECT`` (:doc:`data-model`).
Before the account goes, in the same transaction, the view:

#. cancels every ``active`` or ``paused`` automatic payment of the member, as an
   administrator's cancellation (the ``renewal.cancel`` audit line ends in
   ``reason=member.delete``), so nothing is charged again and the member is
   emailed that it is off, and throws away a ``pending`` one, which has saved no
   payment method and told nobody.  The *Automatic renewal or recurring donation turned off*
   notification for an active one says the account was deleted
   (``how="deleted"``) and links to no member record;
#. when the member has any payment, whatever its status, creates a *tombstone*
   account — a deactivated ``donor`` with no password, no role, and a blank
   profile, named ``Deleted member <id>`` after the deleted account's id, with
   the address ``deleted-<id>@deleted.invalid``, or
   ``deleted-<id>-<8 hex digits>@deleted.invalid`` when another account already
   holds that one — and moves every payment to it,
   clearing each one's ``donor_fields``.  Refunds stay on their payments.

A payment still ``pending`` when it moves can settle later, when the provider or
the giver's browser confirms it.  It is then marked ``succeeded`` and nothing
more: a payment the tombstone holds applies no giver's details, grants no term,
raises no notification, and sends no receipt, so the tombstone keeps its name and
blank profile and never becomes a member.

The payment list, the ledger, and the donors report name the tombstone as the
payer; the member list and **Users and roles**, which show active accounts, do
not list it.  A member who never paid leaves no tombstone.

The delete is recorded as ``member.delete``, with ``payments=<n>
owner=<tombstone id>`` when payments moved.  This endpoint is the only way to
delete an account: the Wagtail admin's account screens are closed
(:ref:`cms-no-account-screens`).

Statuses:

* **204** — the account is gone, with an empty body.
* **400** — the target is a tombstone: ``{"detail": "This record keeps a deleted
  member's payments in the books and cannot be changed."}``.
* **403** — one of the two other refusals, as ``{"detail": "..."}``: "You cannot
  delete your own account." or "Only a system administrator can delete a
  system administrator."
* **404** — no account has that id.

.. _api-members-tombstone:

A tombstone's record
--------------------

``members.services.is_tombstone`` recognizes a tombstone: a deactivated donor
named **Deleted member** on the ``deleted.invalid`` domain.  Its name and address
are what keep a late-settling payment from buying a term or mailing a receipt,
so ``members.services.refuse_tombstone_change`` refuses every change to one,
with a **400** ``{"detail": "This record keeps a deleted member's payments in the
books and cannot be changed."}`` and nothing written:

* ``PATCH /admin/members/{user_id}`` and ``PATCH /admin/users/{id}``, whatever the
  body holds, audited as ``account.update``;
* ``DELETE /admin/members/{user_id}``, which would only move the payments to a
  second tombstone, audited as ``member.delete``;
* ``POST /admin/members/{user_id}/memberships``, audited as ``membership.grant``.

Each refusal is audited at WARNING with ``reason=tombstone``.  The deactivation,
reactivation, and make-a-friend actions refuse a tombstone already, as a donor.
The record (``is_tombstone``), the donors report, the payment list, and the
ledger flag a tombstone, so the portal links to its record from none of them and
shows the record without its controls.


The Delete or deactivate tab's account actions
==============================================

Three endpoints behind ``account_admin`` do for a member what the member does for
themselves.  Each answers 200 with the whole record, in the detail shape above;
``friend_on`` and ``reactivation_blocked`` there tell the portal what to offer.
An unknown ``user_id`` is a **404**.  A refusal changes nothing.

``POST /admin/members/{user_id}/friend``
----------------------------------------

What the member's own ``POST /me/kind/friend`` does (:ref:`api-kind-switch`),
with the caller recorded as the actor: ``payments.renewals.mandates.switch_to_friend``
with ``actor=<caller>`` keeps a current membership to its end and sets
``friend_on`` to the day after, or makes the account a friend at once; the
automatic renewal is canceled with the caller as ``canceled_by``; the
``account.kind`` audit line names the caller; and an immediate change raises
``became_friend`` with ``how="administrator"``.

.. code-block:: json

   {"keep_contribution": true}

The body is the member's: ``keep_contribution`` is required only when the
automatic renewal is active and takes a contribution, and true keeps it as a
yearly recurring donation.

* **400** ``{"keep_contribution": ["This field is required."]}`` — the renewal
  takes a contribution and the body did not say what becomes of it.
* **400** ``{"keep_contribution": ["They already have a recurring donation, so
  the contribution cannot be kept as one."]}`` — true while the member holds an
  active or paused recurring donation.
* **400** ``{"detail": "..."}`` — a friend ("You are already a friend of
  CalDART."), a current life member ("A lifetime member stays a member."), or a
  donor.

``POST /admin/members/{user_id}/deactivate``
--------------------------------------------

What ``POST /admin/users/{id}/deactivate`` does (:ref:`api-account-status`): the
account is deactivated and signed out everywhere, its mandates are canceled, and
every term with time left is suspended, all under the caller.  No body.

``POST /admin/members/{user_id}/reactivate``
--------------------------------------------

What ``POST /admin/users/{id}/reactivate`` does: the account is active again and
its suspended terms restored, under the caller, and an unverified address is
mailed a verification link, whose refusal leaves the answer unchanged
(:ref:`refused sends <api-refused-send>`).  No body.  An account a user
administrator has blocked from reactivating (:ref:`api-reactivation-block`) is
refused.

Both answer a refusal with **400** ``{"detail": "..."}``, in the sentences listed
under :ref:`account-edit-guard`: your own account, a donor, an account holding a
role you do not hold (a system administrator's included, unless you are one), a
blocked account, and an account already in the state asked for.

Statuses:

* **200** — the record, in the detail shape above.
* **400** — a refusal above.
* **401** when anonymous; **403** without ``account_admin``; **404** — no
  account has that id.


``POST /admin/members/{user_id}/memberships``
=============================================

Grants a membership term by hand — the endpoint behind "Grant a term" on the
member record — and records the grant in the audit log.

.. code-block:: json

   {"plan": "annual", "starts_on": null, "note": "Check 1041"}

``plan`` is a ``MembershipPlan`` slug and must be an active plan.
``starts_on`` and ``note`` are optional.  The view calls
``members.services.grant_term``, which creates the term through
``members.services.activate_term`` with ``source="manual"`` and ``granted_by``
set to the caller, so a manual grant is placed by the same rule a payment is.
A grant to a friend makes them a member, audited as ``account.kind`` under the
caller.  The grant raises the ``membership_granted`` event, and a friend's the
``became_member`` event too (:doc:`notification-events`).

With no ``starts_on``, that rule reads the largest ``ends_on`` across the
member's **active or suspended** terms — terms whose stored status is
``expired`` or ``canceled`` are ignored:

* if one of those terms is a lifetime term, and so has no end date, the grant
  starts **today**;
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

A grant to a deactivated account is created ``suspended`` rather than
``active``, exactly as a checkout confirmed after the payer deactivated is (see
:ref:`api-deactivation`): the account does not read as covered while nobody
can sign in to it, and the term becomes ``active`` when the account is
reactivated.

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

A donor holds no membership and becomes a member only by registering, so a
grant to a donor is refused before anything is written or raised: **400**
``{"detail": "A donor holds no membership, and becomes a member only by
registering."}``, audited as ``membership.grant`` with ``reason=donor_account``.
A tombstone, which is a donor too, is refused with its own sentence and
``reason=tombstone`` (:ref:`api-members-tombstone`).

Statuses:

* **201** — the granted term, in the shape above.
* **400** — ``plan`` missing, unknown, or naming a plan that is not active; or
  the account is a donor or a tombstone, as ``{"detail": "..."}``.
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


The membership report
=====================

``GET /reports/members/export.csv`` and ``export.pdf`` download the list above:
they take every filter and ordering parameter ``GET /admin/members`` takes, apply
them to the whole result set, and are not paginated.  ``dart_leader`` reads the
report as well as ``account_admin``.  The endpoints, ``?columns=`` and the
refusals are in :doc:`api-reports`; the columns are in :doc:`reports`.


Tests
=====

``backend/tests/test_members_admin.py``
   The role matrix on every endpoint (401 anonymous, 403 for ``member``,
   ``user_admin``, and ``website_admin``, 403 for ``dart_leader`` on every
   endpoint except the list, 200 for ``account_admin`` and ``system_admin``),
   every filter against a mixed
   fixture, ordering, creation with and without a password, nested profile
   updates, the delete rules and the grant-term arithmetic.
``backend/tests/test_member_county.py``
   The county filter on the list and on the membership report, one county and
   several, the 400 for a county outside California, the counties the PDF
   subtitle prints, and the ``County`` column: its place after ``state``, off by
   default, and the cell it prints.
``backend/tests/test_list_filters.py``
   The ``kind`` selector, ``include_inactive``, and the donor exclusion on the
   list, the report, and the DART leader's member check.
``backend/tests/test_member_list_leaders.py``
   The DART leader on the list: the allow and deny matrix for the list, the
   whole membership in the answer, the DART filter, the report download, and
   the refusal of creating a member, reading a member record, and granting a term.
``backend/tests/test_members_delete_payments.py``
   Deleting a member who paid: every payment status moving to the tombstone,
   the tombstone's kind, activity, name, address, and profile, the automatic
   payments canceled, refunds kept on their payments, a pending gift and a
   pending plan payment settling after the delete, the audit line, the
   payment list and member list afterwards, the Wagtail single and bulk paths,
   and the ``ProtectedError`` the model still raises on its own.
``backend/tests/test_donor_record.py``
   A donor's record as the donors report reaches it: the row's id, the kind,
   address, and gifts on the record, the gifts moving to the tombstone on a
   delete with the donors report's row and year totals unchanged, and the
   refused term grant with its audit line.
``backend/tests/test_tombstone_guard.py``
   A tombstone's record: the refused ``PATCH`` on both edit endpoints, the
   refused ``DELETE`` and grant, their audit lines, and the ``is_tombstone``
   flags on the record, the donors report, the payment list, and the ledger.
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
   The membership report in both formats.
``backend/tests/test_member_services.py``
   ``members.services`` on its own: atomic registration, the invitation sent
   only without a password and only on commit, the two halves of an update, and
   each delete guard.
``backend/tests/test_admin_account_actions.py``
   The Delete or deactivate tab's account actions and the user record's deactivation and
   reactivation: the role matrix, what each does to the account, its sessions,
   its mandates and its terms, the audit lines and events under the
   administrator, every refusal, and ``is_active`` ignored by both edits.
``backend/tests/test_reactivation_block.py``
   Blocking and unblocking: the role matrix, the deactivation a block brings,
   the refusals, and the closed account at sign-in, reactivation, reset, and
   registration.

On the front end, ``frontend/src/portal/features/admin-members/`` holds a test
per page: filters to query parameters, export hrefs, the grant-term form, the
typed delete confirmation, the Delete or deactivate tab's explanation for a member whose
payments keep the account, and the account actions in
``MemberAccountActions.test.tsx``: what each offers, the contribution question,
and every refusal drawn.
