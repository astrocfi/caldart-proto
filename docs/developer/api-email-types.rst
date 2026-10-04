=========================================
API: email types and email preferences
=========================================

The kinds of bulk email, who may send each, and which of them each person
receives.  A system administrator keeps the types; every signed-in person turns
types off and on for themselves; an account administrator does it for a member
from the member record.  The unsubscribe link a bulk email carries, which turns a
type off without signing in, is a public page rather than an API route, and is
described in :ref:`email-unsubscribe`.

The code lives in ``backend/apps/mail/``:

``models.py``
   ``EmailType`` and ``EmailOptOut`` (see :ref:`data-model-email-type` and
   :ref:`data-model-email-opt-out`).
``types.py``
   The services: ``list_types``, ``create_type``, ``update_type``,
   ``delete_type``, ``sendable_types``, ``opt_out_records``, ``is_opted_out``, and
   ``set_opt_out``.  Every write is audited.
``api/type_serializers.py`` and ``api/email_types.py``
   The serializers and the five views.
``api/urls.py``
   Routes, included from ``caldart/api_urls.py``.


Endpoints
=========

::

  GET    /api/v1/email-types
  POST   /api/v1/email-types
  PUT    /api/v1/email-types/{id}
  DELETE /api/v1/email-types/{id}
  GET    /api/v1/email-types/sendable
  GET    /api/v1/me/email-preferences
  PUT    /api/v1/me/email-preferences
  GET    /api/v1/admin/members/{id}/email-preferences
  PUT    /api/v1/admin/members/{id}/email-preferences

``/email-types`` and ``/email-types/{id}`` need ``system_admin``.
``/email-types/sendable`` and ``/me/email-preferences`` answer every signed-in
caller.  ``/admin/members/{id}/email-preferences`` needs ``account_admin``, which a
``system_admin`` passes too.  An unauthenticated request gets **401**, an
authenticated one without the role **403**, and an unsafe method with no
``X-CSRFToken`` **403** before either check.  None is paginated: each list is a
handful of rows.


``GET /email-types``
====================

Every type, in ``position`` order and then by name.

.. code-block:: json

   [
     {
       "id": 1,
       "name": "Operational",
       "slug": "operational",
       "description": "News about how CalDART runs: meetings, training, exercises, and changes that affect members.",
       "allow_opt_out": true,
       "sender_roles": ["dart_leader", "management"],
       "position": 1,
       "in_use": true
     }
   ]

``slug`` is read-only and follows ``name``.  ``in_use`` is read-only and true once a
bulk email has the type, which then cannot be deleted; the Email types screen grays
that type's trashcan and says why.  ``sender_roles`` lists the roles
whose holders may send the type, from ``dart_leader`` and ``management``, once each
and in that order; an empty list leaves the type to system administrators, who send
every type whatever it names.


``POST /email-types`` and ``PUT /email-types/{id}``
===================================================

Both take the same body and answer one row of the shape above: **201** for a
``POST``, **200** for a ``PUT``.  Each is audited, as ``email_type.create`` or
``email_type.update``, naming the caller and the type.

=====================  ==============================================================
Field                  Rule
=====================  ==============================================================
``name``               Required, at most 60 characters.  A name another type holds,
                       ignoring case, or one whose slug another type's name already
                       makes (*Mission!* beside *Mission*), is refused with
                       *Another email type already has this name.*  A name with no
                       letter or digit is refused with *Use at least one letter or
                       digit in the name.*  On a ``PUT`` the type's own name is never
                       counted against it.
``description``        Required: the sentence a member reads beside the switch that
                       turns the type off.
``allow_opt_out``      Required.  Whether a recipient may turn the type off.  A type
                       that allows it carries the unsubscribe headers and footer
                       link; one that does not carries neither.  Turning it off
                       keeps every recorded opt-out, which applies again once it is
                       turned back on.
``sender_roles``       Required, possibly empty.  Each entry ``dart_leader`` or
                       ``management``; any other role is a **400** on
                       ``sender_roles``.
``position``           Optional, a whole number.  Left out, a new type goes after
                       every other and an edited one keeps its place.
=====================  ==============================================================

A refusal is a **400** keyed by the field.  An unknown ``{id}`` is a **404**.


``DELETE /email-types/{id}``
============================

**204** once the type is gone, with every opt-out of it, audited as
``email_type.delete``.  A type a bulk email names is protected by that email's
foreign key: the answer is **400** ``{"detail": "<name> has been used for a bulk
email, so it cannot be deleted. To keep DART leaders and CalDART management from
sending it, take their roles off it instead."}`` and nothing changes or is audited.
A system administrator can still send such a type.  An unknown ``{id}`` is a **404**.


``GET /email-types/sendable``
=============================

The types the caller may send: those whose ``sender_roles`` name one of the
caller's roles, or every type for a system administrator; an empty list for anybody
else.  Each row is ``{id, name, description, allow_opt_out}``, in the same order.

.. code-block:: json

   [
     {
       "id": 3,
       "name": "Mission",
       "description": "Requests for pilots and aircraft when a disaster or an exercise needs them.",
       "allow_opt_out": true
     }
   ]


``GET /me/email-preferences``
=============================

One row per type that allows opting out, in the types' order, with whether the
caller has turned it off.  A type that does not allow opting out is not listed,
whatever the caller chose while it did.  A new account has no opt-out recorded, so
every ``opted_out`` starts ``false``.

.. code-block:: json

   [
     {
       "email_type": 2,
       "name": "Fundraising",
       "description": "Appeals for donations and news about CalDART's fundraising events.",
       "opted_out": true,
       "opted_out_source": "unsubscribe",
       "opted_out_at": "2026-10-03T09:12:00-07:00"
     }
   ]

For a type turned off, ``opted_out_source`` says where that was recorded:
``profile`` (the person's own Email preferences), ``unsubscribe`` (the link in an
email, or a mail program's own unsubscribe button), or ``admin`` (an account
administrator on the member record); ``opted_out_at`` says when.  They are ``""``
and ``null`` for a type left on.  The member record shows them under the switch.


``PUT /me/email-preferences``
=============================

A list of changes, each ``{"email_type": <id>, "opted_out": <bool>}``; a type the
list leaves out is left alone.  The answer is **200** with every preference, as
``GET`` answers them.

.. code-block:: json

   [{"email_type": 2, "opted_out": false}]

Each real change is recorded with the source ``profile`` and audited as
``email.opt_out`` or ``email.opt_in``, naming the caller as the actor and the
target, the type as ``email_type``, and the ``source``.  Asking for the state the
caller is already in changes nothing and writes no audit line.  A type that does
not exist or does not allow opting out is a **400** ``{"email_type": ["That email
type does not exist, or cannot be turned off."]}``, a list that names one type twice
is a **400** ``{"email_type": ["Name each email type once."]}``, and in both cases
none of the list's changes is made.  A body that is not a list is a **400**.


``GET | PUT /admin/members/{id}/email-preferences``
===================================================

The same rows and the same body for member ``{id}``, for the account
administrator's member record.  A change is recorded with the source ``admin`` and
audited with the caller as the actor and the member as the target.  A **Deleted
member** record (the account that keeps a deleted member's payments) refuses a
``PUT`` with **400** ``{"detail": ...}``; each change the body asked for is audited
at WARNING as the ``email.opt_out`` or ``email.opt_in`` it would have been, naming the
type as ``email_type``, with the reason ``tombstone``.  An unknown ``{id}`` is a
**404**.
