=============
API: DARTs
=============

The teams themselves: the public catalog every "which DART?" box reads, and
the account administrator's screen for keeping it.  A DART is more than a
column on a member's record — it has airports, a website and the people who
run it — so it is its own app.

The code lives in ``backend/apps/darts/``:

``models.py``
   ``Dart`` and ``DartContact``, and the airport-identifier rules both the
   catalog and a member's home airport are judged by.
``api/serializers.py``
   ``DartSerializer`` (the public catalog), ``DartRefSerializer`` (the
   ``{id, name}`` stub nested in a profile), ``DartContactSerializer`` and
   ``DartAdminSerializer``.
``api/views.py``
   The catalog view and the three administrator views.
``api/urls.py``
   Routes, included from ``caldart/api_urls.py``.


Endpoints
=========

::

  GET    /api/v1/darts
  GET    /api/v1/admin/darts
  POST   /api/v1/admin/darts
  GET    /api/v1/admin/darts/{id}
  PATCH  /api/v1/admin/darts/{id}
  DELETE /api/v1/admin/darts/{id}

``GET /darts`` is public and unpaginated: the join form reads it before
anybody has signed in.  Everything under ``/admin/`` needs ``account_admin``;
``system_admin`` passes every role check, so a system administrator has them
too.  An unauthenticated request gets **401**, an authenticated one without
the role **403**, and an unsafe method with no ``X-CSRFToken`` **403** before
either check.


``GET /darts``
==============

Active DARTs in alphabetical order, each with the people who run it.

.. code-block:: json

   [
     {
       "id": 3,
       "name": "Contra Costa",
       "airport_identifiers": "CCR, C83",
       "website_url": "https://contra-costa.caldart.example.org/",
       "contacts": [
         {
           "id": 7,
           "name": "Helen Marchetti",
           "title": "DART leader",
           "phone": "707-555-0133",
           "email": "helen.marchetti@caldart.example.org"
         }
       ]
     }
   ]


``GET /admin/darts``
====================

Every DART, retired ones included, in the same order and also unpaginated:
the list is a page long and the screen shows all of it.  Each row adds
``is_active`` and the two counts the delete warning reads — ``member_count``,
the profiles naming this DART, and ``page_count``, the website pages linked
to it.


``POST`` and ``PATCH /admin/darts``
===================================

Both take ``name``, ``airport_identifiers``, ``website_url``, ``is_active``
and ``contacts``:

=========================  =============================================================
Field                      Rule
=========================  =============================================================
``name``                   Required, and unique across DARTs.  A blank one is
                           refused with "Give the DART a name." and a repeat with
                           "A DART with that name already exists."
``airport_identifiers``    Required: every DART flies from somewhere.  One or more
                           three-character identifiers, separated by commas or
                           spaces, stored upper-cased as ``"CCR, C83"``.  The
                           four-letter ICAO spelling is accepted and trimmed, so
                           ``KCRQ`` is stored as ``CRQ`` and one airport reads
                           the same everywhere; a three-character identifier
                           that begins with ``K`` is left alone.  An empty list,
                           a repeat, more than ``MAX_AIRPORT_IDENTIFIERS`` of
                           them, or an identifier of the wrong shape are each
                           refused with their own sentence.
``website_url``            The team's own site, or blank.  A URL, checked as one.
``contacts``               Up to ``MAX_DART_CONTACTS`` people, each with a
                           ``name``, a ``title``, and an optional ``phone`` and
                           ``email``.  The order given is the order stored --
                           ``sort_order`` follows the position in the list --
                           and it is the order the public catalog and the
                           team's own page print them in.  The list given
                           **replaces** the list
                           stored, because that is how the screen edits it; a
                           body that leaves ``contacts`` out keeps what is there,
                           so renaming a DART cannot lose its officers by
                           omission.  A phone number follows the same rule as a
                           member's, stored as ``XXX-XXX-XXXX``.
``is_active``              Whether the DART is offered to members.  Turning it off
                           retires the DART without touching the profiles on it.
=========================  =============================================================

A refused contact is keyed by its position in the list::

  {"contacts": {"0": {"phone": ["Use a ten-digit number like 415-555-0100."]}}}


``DELETE /admin/darts/{id}``
============================

Removes the DART and answers **204**.  Nothing blocks it: both relations that
point at a DART are ``SET_NULL``, so the members on it become unaffiliated and
keep every other thing about their record, and a website page linked to it
keeps its own content and loses its DART.  The team's people go with it, since
a ``DartContact`` belongs to its DART.

The delete cannot be undone, so the screen's confirmation counts what it will
leave behind, from the ``member_count`` and ``page_count`` the list already
carries.  A DART that should stop taking members but keep its history is
turned inactive instead, with ``is_active``.


Audit
=====

Each write records one line — ``dart.create``, ``dart.update`` or
``dart.delete``, the last carrying ``members`` and ``pages``, the counts it
unaffiliated and unlinked.  See :doc:`deployment` for the journal.


Tests
=====

``backend/tests/test_darts_admin.py``
   The role matrix on the list, create and delete; the counts each row
   carries; the fields a row carries, and that a town is not among them;
   the airport rules, including several airports on one team and both
   identifier forms; the people, their phone rule and the replace-on-write
   behavior; the website link; retiring a DART; and the guard that refuses to
   delete one somebody is still on.
