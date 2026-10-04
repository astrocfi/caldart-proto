.. _api-notifications:

==================
API: notifications
==================

The notification endpoints under ``/api/v1/notifications/``, from
``apps.notifications``, list the events an address may subscribe to and manage
the subscriptions that decide who is emailed about each one.  How an event is
raised and sent is :doc:`notifications`.  :doc:`api-reference` covers the
conventions these endpoints share: session authentication, the CSRF header, and
the error shapes.

Every endpoint here is the ``account_admin``'s, and a ``system_admin`` passes as
always.  Any other role is refused with **403**, and an anonymous caller with
**401**.


``GET /notifications/events``
=============================

Every event, in catalog order:

.. code-block:: json

   [
     {
       "slug": "signed_up",
       "label": "Sign-up",
       "category": "Membership",
       "description": "Somebody registered on the site, as a member or as a friend.",
       "roles": ["account_admin", "user_admin"]
     }
   ]

``slug`` names the event in a subscription's ``events``; ``label`` is the words
the screen and the email log use; ``category`` is ``Membership``, ``Money``,
``Accounts`` or ``Aircraft``, the heading the screen groups it under;
``description`` is one sentence saying when it happens; and ``roles`` are the
role slugs whose holders may receive it.  A ``system_admin`` and a Django
superuser may receive every event.


.. _api-notification-subscriptions:

Subscriptions
=============

``GET /notifications/subscriptions``
------------------------------------

Every subscription, unpaginated, ordered by address:

.. code-block:: json

   [
     {
       "id": 1,
       "recipient_user": 3,
       "recipient_name": "Curtis Whitfield",
       "recipient_email": "accountadmin@example.org",
       "events": ["signed_up", "member_added", "roles_changed"],
       "is_active": true,
       "created_by_name": "Curtis Whitfield",
       "created_at": "2026-09-26T09:00:00-07:00",
       "updated_at": "2026-09-26T09:00:00-07:00"
     }
   ]

``recipient_user`` is the account the notifications go to, or ``null`` for an
address outside CalDART, whose ``recipient_name`` is then blank.
``recipient_email`` is stored in lower case.  ``events`` are the event slugs, in
catalog order.  A subscription whose ``is_active`` is false is sent nothing.
``created_by_name`` is blank once the account that set it up is gone.

``POST /notifications/subscriptions``
-------------------------------------

Set one up:

.. code-block:: json

   {
     "recipient_email": "board@example.org",
     "events": ["signed_up", "became_member"],
     "confirmed": true
   }

``confirmed`` may be left out, and is then false.  The answer is **201** with the
subscription as ``GET`` lists it.  The events are stored once each, in catalog
order, whatever order they were sent in; the caller is recorded as the one who
set it up, and it starts active.

The recipient is named by address.  When an account holds that address,
compared without regard to case, the subscription is bound to the account and
keeps the account's own address, and every event chosen must be one a role of
that account may receive.  When no account holds it, the caller must confirm
the address with ``confirmed: true``.

Refusals, each **400**:

* ``{"recipient_email": ["This address already has a subscription."]}`` when
  a subscription holds the address already, compared without regard to case;
  an address that is not one is refused under ``recipient_email`` too;
* ``{"events": ["Choose at least one event."]}`` for an empty list;
* ``{"events": ["Unknown event '<slug>'."]}`` for a slug the catalog does not
  list, naming the first;
* ``{"events": ["<name> does not hold a role that may receive <label>."]}``
  for an account that may not receive one of the events, naming the account
  and the first such event in catalog order;
* ``{"confirmed": ["Check the box to confirm this address may receive these
  notifications."]}`` for an address no account holds, until it is confirmed.

``GET``, ``PATCH`` and ``DELETE /notifications/subscriptions/{id}``
-------------------------------------------------------------------

``GET /notifications/subscriptions/{id}`` answers the subscription as the list
does.

``PATCH /notifications/subscriptions/{id}`` changes ``events``, ``is_active``, or
both.  The events are checked as ``POST`` checks them.  The recipient is fixed
once set up, and other fields are ignored; before the check, a bare address an
account has since taken is bound to that account.  For a bound account, adding
an event its roles do not admit is refused, and so is resuming
(``is_active: true``) a paused subscription that lists one, both with **400**
under ``events`` and the message above.  Removing events is always allowed.

``DELETE /notifications/subscriptions/{id}`` answers **204**.

An id no subscription carries answers **404**, and ``PUT`` answers **405**.
