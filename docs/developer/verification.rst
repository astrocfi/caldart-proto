============
Verification
============

A DART leader relies on a pilot's certificate, medical, and photo ID, and on the
insurance of the airplane they fly.  Anybody can type those into a profile or the
aircraft register, so CalDART records separately whether an authority has checked
each one against the document.  That check is **verification**; the person who
makes it is a **verifier** (the role of that name, or any other role allowed to
verify).  This page covers what is verified, when a verification is cleared, who
may verify, and how the member check and the aircraft check read it.  The
endpoints are in :doc:`api-aircraft` and :doc:`api-profile`, and the columns in
:doc:`data-model`.


The items
=========

An **item** is the unit that is verified: a group of fields an authority checks
against one document.  A person has three and an aircraft one:

=================  ===================  ===================================================  ===================
Slug               Label                Fields it covers                                     Lives on
=================  ===================  ===================================================  ===================
``certificate``    Pilot certificate    ``pilot_certificate_type``, ``certificate_number``   ``MemberProfile``
``medical``        Medical              ``medical_type``, ``medical_expiration``             ``MemberProfile``
``photo_id``       Photo ID             ``photo_id_type``                                    ``MemberProfile``
``insurance``      Insurance            ``insurance_carrier``,                               ``Aircraft``
                                        ``insurance_policy_number``,
                                        ``insurance_liability_per_occurrence_cents``,
                                        ``insurance_liability_per_person_cents``,
                                        ``insurance_hull_cents``,
                                        ``insurance_expiration``
=================  ===================  ===================================================  ===================

Ratings, the instrument rating, the flight review date, and total hours are not
verified.  ``apps/members/verification.py`` holds the person's catalog,
``ITEMS`` (each an ``Item`` with its slug, label, and fields) and
``ITEM_LABELS``; ``apps/aircraft/verification.py`` holds ``INSURANCE_FIELDS`` and
``INSURANCE_LABEL``.

Each item is two columns, ``<item>_verified_at`` and ``<item>_verified_by`` (the
account, ``SET_NULL`` if it is deleted), and a property ``<item>_is_verified``
that is true when ``<item>_verified_at`` is set.  Both columns are ``NULL`` while
the item is unverified.

The photo ID records only the kind of document — *Not provided*, *Driver's
license*, *Passport*, *State ID card*, *Military ID*, or *Other* — and nothing
else about it.  A verifier who saw a document of a kind not listed records *Other*.

An item the person does not hold has nothing to verify: a pilot certificate of
``none``, a medical of ``none``, or a photo ID of ``not_provided``.  Each ``Item``
carries the coded field that says so (its first field) and that field's ``none``
value, and ``is_held(profile, slug)`` answers it.  Such an item is never stamped, a
stamp on one counts for nothing, and every screen draws it with no mark and the
panel with no box.  Insurance with no ``insurance_expiration`` is no policy on file
and is likewise never stamped.

A verified medical whose expiration passes stays verified, and so does verified
insurance whose policy lapses.  Currency and verification are two separate facts,
and the screens show both.


Clearing
========

A write that changes the stored value of any field an item covers clears that
item — both columns back to ``NULL`` — whoever writes it, in the same transaction.
A field resent at its stored value clears nothing, so a form that sends every
field it shows clears only what really moved.  The places those fields are
written each clear:

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Write
     - How it clears
   * - The member's own ``PUT`` or ``PATCH /me/profile``
     - ``ProfileSerializer.update`` calls ``members.verification.clear_stale``
       before the values are assigned
   * - An administrator's edit (``PATCH /admin/members/{id}``)
     - ``members.services.update_member`` calls ``clear_stale`` the same way
   * - Any aircraft edit (``PUT`` or ``PATCH /aircraft/{id}``)
     - ``aircraft.services.record_updated`` calls
       ``aircraft.verification.clear_stale_insurance`` with the columns the
       write moved
   * - The two verification endpoints
     - through the same two services, before the verification the request asks
       for is applied

``clear_stale(profile, changes)`` compares the incoming values with the stored
ones and returns the slugs of the verified items it cleared;
``clear_stale_insurance(aircraft, moved_fields)`` returns whether it cleared the
insurance.  An edit that clears an item raises no event of its own:
``profile_changed`` or ``aircraft_changed`` already names the fields
(:doc:`notification-events`).


Who verifies
============

``VERIFY_ROLES`` in ``apps/accounts/roles.py`` is ``verifier``, ``dart_leader``,
``user_admin``, and ``account_admin``, and ``IsVerifier`` in
``apps/accounts/permissions.py`` is ``HasAnyRole(*VERIFY_ROLES)``.  A system
administrator and a superuser pass as everywhere.  The same roles open the member
check and the aircraft check (``IsLeader`` and ``PILOT_ROLES`` in
``apps/aircraft/api/views.py``), so everybody who may verify can find what to
verify.  The member list stays closed to a verifier: the role finds people by the
member check's search, not by browsing the membership.

``verifier`` is the least privileged staff role, between ``member`` and
``dart_leader``.  A DART leader or a user administrator grants or revokes it from
the member check with ``PUT /leader/members/{user_id}/verifier``, which goes
through ``accounts.services.set_verifier`` and so through ``update_account``: the
change is audited as ``account.roles`` and raised as ``roles_changed``.  A user
administrator can also grant it from the Roles screen.

Anybody who may verify may verify their own record; nothing compares the verifier
with the person.


The services
============

One request writes the fields an item covers and the verified state of every item
on the record together, so a verifier who checks three documents sends one save
and the office hears about it once.

``members.verification.verify_member(actor, target, *, changes, verified)``
    Writes ``changes`` through ``update_member`` (raising ``profile_changed`` and
    clearing what moved), then stamps each item in ``verified`` that is held and not
    yet verified with the time and ``actor``, and clears each verified item that is
    not in ``verified`` or that the saved profile does not hold.  Re-verifying an already verified item keeps its stamp.  It
    records ``member.verify`` with ``verified`` (the items it stamped) and
    ``cleared`` (the items verified before the save and not after), and raises
    ``verification_changed`` when either list is not empty.

``aircraft.verification.verify_insurance(aircraft, *, actor, changes, verified)``
    Writes ``changes``, calls ``record_updated`` (the history row, the audit
    record, ``aircraft_changed``, and the clearing), then stamps or clears the
    insurance.  Insurance with no expiry date on file ends unverified whatever the
    request asks.  It records ``aircraft.verify`` with ``verified`` and raises
    ``verification_changed`` when the insurance was stamped or cleared.

``verification_changed`` is raised once per save, never once per item, and not at
all when a save changes no item's state.  Its payload is ``actor``, ``verified``
and ``cleared`` (item labels), and either ``user`` or ``aircraft``.


The verdicts
============

The status card's ``go_no_go`` carries ``membership``, ``medical``, and
``verified``, the last true when the person holds a pilot certificate, a medical,
and a photo ID and all three are verified (``is_fully_verified``); each of the
three also carries its own ``verification``, and ``photo_id`` its kind.  A person
is a GO when all three booleans are true.  A search row and each pilot on the
aircraft card carry the same ``go_no_go``, built by one helper (``_go_no_go`` in
``apps/aircraft/services.py``) from the profile row already fetched, so the member
check and the aircraft check never disagree about one person and neither costs a
query per row.

An aircraft is insured when its policy is current and its insurance verified;
current but unverified coverage reads *Not verified*, and no current policy reads
*Not insured*.  Every aircraft payload says so: the register record carries
``insurance_verification`` (``{verified, verified_by, verified_at}``) and the short
form on a profile or a status card carries ``insurance_verified``.


The demo data
=============

``seed_demo`` gives every profile a photo ID (friends mostly *Not provided*), and
the seeded DART leader verifies each item held by about seven in ten members and
the insurance of about seven in ten aircraft; the rest stay unverified, and no item
a member does not hold is stamped.  ``seed_facts`` names an insured pilot verified
on every count (``leaderCheck.insuredPilot``) and a current pilot with a current
medical, all three items held, and nothing verified
(``leaderCheck.unverifiedPilot``), and ``accounts.verifier`` is
the seeded verifier.  See :doc:`setup`.


Tests
=====

``backend/tests/test_verification.py`` covers the items, the clearing in every
write path, and both services; ``test_verification_api.py`` the endpoints, their
role matrices, the fields the reads carry, and the query counts;
``test_verifier_role.py`` granting and revoking the role;
``test_verification_skeleton.py`` the role, the catalog, and the columns; and
``test_verification_held_items.py`` the items a person does not hold and the
aircraft card's pilot verdicts.
