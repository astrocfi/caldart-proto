===================
Notification events
===================

Something an administrator wants to hear about (somebody signs up, a
membership runs out, a refund goes back) is an **event**.  The service that
makes the change raises the event once, at the point the change has
definitively happened, and never needs to know who listens.  This page lists
every event: where it is raised, and what it carries.  See :doc:`notifications`
for how an event reaches a subscribed address: the recipient rule, sending, and
the data behind the screen.

How an event is raised
======================

``caldart/events.py`` is the one way an event is raised.  A service calls
``emit(slug, **payload)``; ``emit`` hands the slug and the payload, model
instances included, to every handler registered with ``subscribe(handler)``,
at once, in registration order, inside the caller's transaction.  A slug
outside ``EVENT_SLUGS`` raises ``ValueError`` reading ``Unknown event
'<slug>'`` before any handler runs, so a misspelled event fails a test instead
of reaching nobody.  The module imports no app, so a service on any layer may
raise an event without importing the notifications app (``apps/notifications``),
which registers its handler when it starts and does the sending.

The rules every call site keeps:

* **In the service, once.**  An event is raised in the service function that
  makes the change, never in a serializer's validation or in a view, so a
  management command, the Django admin, and the API raise it alike.  A view
  whose change needs an event calls a service that writes it
  (``members.services.grant_term``, and ``record_added``, ``record_updated``,
  and ``delete_aircraft`` in ``aircraft.services``).
* **After the save, inside the transaction.**  The row the event describes is
  written before the event is raised, and a request that rolls back takes the
  event's consequences with it: a handler that acts on the outside world waits
  for the commit.
* **Only for a real change.**  An edit that resends the value a field already
  holds, a second delivery of the same webhook, and a payment confirmed twice
  raise nothing the second time.

``backend/tests/test_notification_hooks.py`` proves each call site: it
subscribes a recording handler through ``caldart.events`` for the length of a
test and asserts the slug and the payload that one action raised.

The events
==========

The payload names are the keyword arguments to ``emit``.  ``user`` is the
``User`` the event is about and ``actor`` the ``User`` who made the change,
``None`` where the person acted for themselves or nobody CalDART knows did.

Membership
----------

.. list-table::
   :header-rows: 1
   :widths: 18 42 40

   * - Slug
     - Raised in
     - Payload
   * - ``signed_up``
     - ``ProfileSerializer.update`` in ``members/api/profile_serializers.py``, for
       the ``PUT`` or ``PATCH /me/profile`` that turns an incomplete profile
       complete: the join wizard's profile step, which comes after the account
       exists and is where the DART is chosen
     - ``user``; ``dart``, the profile's DART, or ``None`` when none was chosen
   * - ``member_added``
     - ``members.services.create_member``
     - ``user``, ``actor``
   * - ``became_friend``
     - ``members.lifecycle.become_friend`` when the account is a friend at once
       (``how="chose"``, or ``how="administrator"`` when an account administrator
       made the switch from the member record);
       ``members.lifecycle.convert_due_friends`` for each account
       it converts (``how="lapsed"``); ``accounts.services.update_account`` when an
       administrator sets the kind to friend (``how="administrator"``)
     - ``user``, ``how``
   * - ``became_member``
     - ``members.services.activate_term`` when the term makes the account a member
       (``how="paid"`` for a term a payment bought, ``how="granted"`` otherwise);
       ``accounts.services.update_account`` when an administrator sets the kind to
       member (``how="administrator"``)
     - ``user``, ``how``
   * - ``membership_paid``
     - ``payments.services._complete``, for a succeeded payment that names a plan,
       whatever contribution it also carries
     - ``payment``; ``term``, the term it bought; ``automatic``, true when the
       renewal scanner took the payment
   * - ``membership_granted``
     - ``members.services.grant_term``, which ``POST /admin/members/{id}/memberships``
       calls
     - ``user``, ``term``, ``actor``
   * - ``membership_expired``
     - ``members.lifecycle.expire_lapsed_memberships``, once per account whose terms
       it flipped and that no other term still covers
     - ``user``; ``term``, the flipped term that ended last

Registering (``POST /auth/register``) raises nothing, because the account
exists before the wizard asks for the DART.  A donor who registers joins the
same way: following the verification link makes the donor a member or a friend,
and completing the profile raises ``signed_up``.  So does the first profile an
account completes for itself when an administrator added it with a blank one.
A profile an administrator completes through ``update_member`` raises
``profile_changed``, not ``signed_up``.

Money
-----

.. list-table::
   :header-rows: 1
   :widths: 18 42 40

   * - Slug
     - Raised in
     - Payload
   * - ``auto_renewal_on``
     - ``payments.renewals.save_method`` when the mandate was not already active:
       a checkout that saves its card, a card saved from the portal, and a
       renewal's contribution kept as a recurring donation
     - ``mandate``
   * - ``auto_renewal_off``
     - ``payments.renewals.cancel_mandate`` for a mandate that was active (``how``
       is ``member`` when the actor is the mandate's own member, ``administrator``
       for anybody else, and
       ``deactivated`` from ``cancel_all_mandates`` when the member deactivates
       their account, and ``deleted`` from ``members.services.hand_over_payments``
       when their account is deleted); the scanner's ``_abandon`` when it pauses a mandate whose
       member lapsed too long ago (``how="lapsed"``)
     - ``mandate``, ``how``
   * - ``auto_renewal_declined``
     - ``payments.renewals._record_failure``, for every declined charge
     - ``mandate``; ``reason``, the provider's words; ``next_on``, the day of the
       retry, or ``None`` when the retries are exhausted and the mandate is paused
   * - ``donation_received``
     - ``payments.services._complete``, for a succeeded payment that names no plan:
       a gift on the public donation page, a contribution, or a recurring
       donation's charge
     - ``payment``
   * - ``payment_recorded``
     - ``payments.manual.record_manual_payment``, after the payment has succeeded
     - ``payment``, ``actor``
   * - ``payment_refunded``
     - ``payments.refunds.issue_refund`` once the provider has given the money back,
       and ``payments.refunds.record_dashboard_refund`` for a refund taken in the
       provider's own dashboard
     - ``payment``; ``refund_cents``; ``actor`` (``None`` for the dashboard);
       ``term_canceled``, true when the term the payment bought ended with it

Canceling a paused mandate raises nothing: it was off already.

A payment recorded by hand raises two events: ``payment_recorded``, and the
``membership_paid`` or ``donation_received`` its money earns, since it succeeds
through the same ``_complete`` a card payment does.  A refused refund raises
nothing: no money went back.

Accounts
--------

.. list-table::
   :header-rows: 1
   :widths: 18 42 40

   * - Slug
     - Raised in
     - Payload
   * - ``account_deactivated``
     - ``accounts.status.deactivate_own_account`` (``actor=None``), and
       ``accounts.status.deactivate_account`` when an administrator deactivates the
       account, from the member record or the user record, or blocks an active one
     - ``user``, ``actor``
   * - ``account_reactivated``
     - ``accounts.status.reactivate_own_account``, which ``POST /auth/reactivate``
       and a completed password reset both reach (``actor=None``), and
       ``accounts.status.reactivate_account`` when an administrator reactivates it
     - ``user``, ``actor``
   * - ``roles_changed``
     - ``accounts.services.update_account`` when the role list really changes
     - ``user``; ``added`` and ``removed``, lists of role slugs in privilege order;
       ``actor``
   * - ``email_changed``
     - ``accounts.services.verify_email``, when the link mailed to a changed
       address stamps the account verified; ``update_account`` signs the old
       address into that link whenever an edit really alters the address (a change
       of case does not): an administrator's edit and the member's own
       ``POST /auth/email/change`` alike
     - ``user``; ``old_email``, the address the account held before, since the
       account holds only the new one
   * - ``profile_changed``
     - ``ProfileSerializer.update`` in ``members/api/profile_serializers.py`` for
       the member's own ``PUT`` or ``PATCH /me/profile`` (``actor=None``), and
       ``members.services.update_member`` for an administrator's edit
     - ``user``; ``fields``, the labels of the fields whose value moved; ``actor``
   * - ``verification_changed``
     - the verification services, ``members.verification.verify_member`` for a
       member's pilot certificate, medical, and photo ID, and
       ``aircraft.verification.verify_insurance`` for an aircraft's insurance, once
       per save and only when an item's verified state changes
     - ``actor``; ``verified`` and ``cleared``, lists of item labels; and either
       ``user`` or ``aircraft``

``profile_changed`` names each field by
``members.labels.profile_field_label``: DART, Home airport, Secondary airport,
Address line 1, First name, and so on, and otherwise the model field's verbose name with a
capital letter (City, California county).  An administrator's edit lists the
first and last name before the profile fields; the address, the active flag,
and the kind raise their own events and are not listed.

``verification_changed`` reads, for a member, *Lee Boss verified Pat Quill's pilot
certificate, medical, and photo ID* when the save only verified items, *Lee Boss
cleared the verification of Pat Quill's medical* when it only cleared them, and *Lee
Boss changed the verification of Pat Quill's details* when it did both; for an
aircraft, *N123AB's insurance* (or *N123AB's details*) takes the member's place.  The
items are the labels in ``verified`` or ``cleared``, each with a lower-case first
letter, listed with a serial comma.  Its lines are ``Verified`` and ``Cleared``, each
the labels joined with commas or ``None``, and ``By``, the actor; it links the member
record, or the aircraft record when the payload names an ``aircraft``.

Aircraft
--------

.. list-table::
   :header-rows: 1
   :widths: 18 42 40

   * - Slug
     - Raised in
     - Payload
   * - ``aircraft_added``
     - ``aircraft.services.record_added``, which ``POST /aircraft`` calls after the
       save
     - ``aircraft``, ``actor``
   * - ``aircraft_changed``
     - ``aircraft.services.record_updated``, which ``PATCH /aircraft/{id}`` calls
       after the save, when any column moved
     - ``aircraft``; ``fields``, the column names that moved, as the aircraft's
       history records them; ``actor``
   * - ``aircraft_removed``
     - ``aircraft.services.delete_aircraft``, which ``DELETE /aircraft/{id}`` calls
     - ``n_number`` and ``owner`` (the owner's name as the record gave it), since
       the record is gone; ``actor``
