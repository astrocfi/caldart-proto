.. _api-reminders-system:

================================
API: reminders, system, and site
================================

The endpoints that keep the installation running and the one the portal calls
before it has a user: ``GET /admin/reminders/log`` and
``POST /system/reminders/run`` from ``apps.reminders``, the health, backup and
renewal-scan routes under ``/system/`` from ``apps.sysadmin``, and
``GET /site/config`` from ``apps.cms``.  :doc:`api-reference` covers the conventions they share —
session authentication, the CSRF header, pagination, and the error shapes.

The subsystem chapters behind them are :doc:`reminders` (what the scan sends
and when), :doc:`renewals` (what the automatic-renewal scan charges and when),
:doc:`backup-restore` (what a dump contains and how to restore one) and
:doc:`cms` (where the navigation and the members-only pages come from).


Reminders
=========

``GET /admin/reminders/log``
----------------------------

The reminder emails that have gone out, paginated, and newest first.
``account_admin`` and ``system_admin`` both reach it: the question it answers
is "was this member ever told?", which is membership work as much as
operations.  The rows are the log the scan writes, so a row exists only for a
mail the server handed to the mail server successfully.

.. code-block:: json

   {
     "count": 143,
     "next": "http://localhost:8000/api/v1/admin/reminders/log?page=2",
     "previous": null,
     "results": [
       {"id": 88, "user_id": 37, "user_name": "Marta Reyes", "membership_id": 51,
        "kind": "t30", "sent_at": "2026-01-08T09:00:00-08:00",
        "to_email": "marta.reyes@example.org"}
     ]
   }

=================  ============================================================
Parameter          Effect
=================  ============================================================
``kind``           One of ``t60``, ``t30``, ``t7``, ``expired``, ``post30``.
                   Anything else is a 400 on ``kind``.
``from``, ``to``   ``YYYY-MM-DD``, compared against the date part of
                   ``sent_at``: ``from`` is on or after, ``to`` on or before.
``search``         Case-insensitive match on the recipient address and on the
                   member's email, first name and last name.
``ordering``       ``sent_at`` or ``kind``, with a ``-`` prefix for
                   descending.  An unrecognized field is ignored.
``page``,          Standard pagination (25 by default, 200 at most).
``page_size``
=================  ============================================================

``kind`` is a filterset choice, so an unknown value is refused rather than
answered with an empty page.  ``from`` is a Python keyword and therefore cannot
be a class attribute; it is added to the filter set after the class is built,
which is why it behaves exactly like ``to`` despite being declared elsewhere.

Statuses: **200**; **400** for an unknown ``kind`` or an unparseable date;
**401** when anonymous; **403** for a signed-in caller holding neither role.

``POST /system/reminders/run``
------------------------------

Runs the renewal scan immediately instead of waiting for the daily timer,
and answers with what it did.  ``system_admin`` only.  The body is optional;
``dry_run`` defaults to ``false``.

.. code-block:: json

   {"dry_run": true}

.. code-block:: json

   {"sent": 4, "skipped": 12}

``sent`` counts the reminders the run mailed and ``skipped`` those it decided
against — a member who has already had that reminder, or who is outside the
cohort.  A dry run writes nothing at all: no email, no log rows and no
membership status flips.  Its ``sent`` is therefore a count of candidates, not
of outcomes: every member the scan would try to mail lands in it, including
ones a live run would end up recording as a failure, or as skipped because a
concurrent run got there first.  Sends the mail server refuses are logged at
ERROR and left out of both counts, so a run whose numbers look thin is worth
reading the log for.
The full breakdown per kind and per skip reason is what
``manage.py send_renewal_reminders`` prints; see :doc:`reminders`.

Statuses: **200**; **400** when ``dry_run`` is not a boolean; **401** when
anonymous; **403** for any other role.


System
======

All five routes are ``system_admin`` only, and every one of them is behind
``/portal/system`` in the portal.  Restoring a dump is deliberately not among
them: wiping the database is ``manage.py db_restore``, not a browser tab
(:doc:`backup-restore`).

``GET /system/health``
----------------------

One object describing the box: whether the database answers, whether the code
on disk is ahead of the schema, how much room is left for the next dump, and
what is running.

.. code-block:: json

   {"db": "ok", "pending_migrations": 0, "disk_free_mb": 41231,
    "last_backup": "2026-01-08T02:00:04-08:00", "version": "0.1.0",
    "debug": false}

``db``
   ``ok`` when a ``SELECT 1`` succeeds, and ``error: <message>`` when it does
   not.  The endpoint still answers 200 in that case: it reports the fault
   rather than becoming one.

``pending_migrations``
   How many migrations on disk are unapplied, and ``-1`` when ``db`` is not
   ``ok``, since the answer is unknowable without the database.

``disk_free_mb``
   Free space in whole mebibytes on the filesystem holding ``BACKUP_DIR``.
   That is the one that has to have room for the next ``pg_dump``.

``last_backup``
   The modification time of the newest dump, or ``null`` when the directory
   holds none.

``version``
   The ``[project] version`` from ``pyproject.toml``, falling back to the
   ``CALDART_VERSION`` setting when that file cannot be read.

``debug``
   Whether the server runs with ``DEBUG`` on, which it must not in production.

Statuses: **200**; **401** when anonymous; **403** for every other role.

``GET /system/backups``
-----------------------

Every dump in ``BACKUP_DIR``, newest first, as a bare array — the directory is
small and bounded, so this list is not paginated.

.. code-block:: json

   [{"name": "caldart-20260108-020000.sql.gz", "size_bytes": 4718592,
     "created_at": "2026-01-08T02:00:04-08:00"}]

Statuses: **200**; **401** when anonymous; **403** for every other role.

``POST /system/backups``
------------------------

Takes a dump immediately.  The body is empty; the name is generated from the
site clock as ``caldart-<YYYYMMDD-HHMMSS>.sql.gz``.

.. code-block:: json

   {"name": "caldart-20260108-141133.sql.gz", "size_bytes": 4718592,
    "created_at": "2026-01-08T14:11:35-08:00"}

The dump runs ``pg_dump --no-owner --no-privileges`` and gzips the output.
When neither ``pg_dump`` nor docker is on the path, or ``pg_dump`` exits
non-zero, nothing is written and the reason comes back as the ``detail``
string::

    400 {"detail": "Neither pg_dump nor docker is available; install postgresql-client or start the compose stack."}

A dump that succeeds writes a ``backup.create`` audit record naming the
caller, the file and its size (:ref:`deploy-audit-log`).

Statuses: **201**; **400** when the dump cannot be taken; **401** when
anonymous; **403** for every other role.

``GET /system/backups/{name}/download``
---------------------------------------

Streams one dump as an attachment with content type ``application/gzip`` and
the dump's own file name.  It is a plain link rather than an API call, so the
body never reaches the portal's fetch wrapper.

``name`` goes through ``apps.sysadmin.services.resolve_backup``, which requires
it to match ``^[A-Za-z0-9][A-Za-z0-9._-]*\.sql\.gz$`` **and** re-checks that
the resolved path's parent is exactly ``BACKUP_DIR``.  That second test is what
defeats ``..``, an absolute path and a symlink pointing out of the directory.
The route is declared with ``<path:name>`` rather than ``<str:name>`` on
purpose: a traversal attempt then reaches the view and is refused there with a
message, instead of 404ing at the URL resolver where no test could tell it from
a typo.

Both refusals are 404 and both name what was wrong::

    404 {"detail": "Not a backup file name: '../secret.sql.gz'"}
    404 {"detail": "No such backup: caldart-19700101-000000.sql.gz"}

A refusal writes a WARNING ``backup.download`` audit record with the reason
``no_such_backup``; the refused name itself is not recorded, because it came
off the URL.  A download that goes through writes the same record at INFO with
the file name.

Statuses: **200**; **401** when anonymous; **403** for every other role;
**404** for a name that is not a backup file name, and for one that is but
matches no file.

``POST /system/renewals/run``
-----------------------------

Runs the automatic-renewal scan immediately instead of waiting for the 06:30
timer: it schedules the charges for terms running out, sends the advance
notices, charges the renewals due, and retries or pauses the ones the provider
refused.  The body is optional and ``dry_run`` defaults to ``false``; a dry run
writes nothing, emails nobody and charges nobody.

.. code-block:: json

   {"noticed": 2, "warned": 0, "charged": 1, "failed": 0, "paused": 0, "skipped": 3}

The full description of the request, the counts and what each one means is on
:doc:`api-renewals`, and :doc:`renewals` is the subsystem chapter behind it.

Statuses: **200**; **400** when ``dry_run`` is not a boolean; **401** when
anonymous; **403** for any other role.


Site
====

``GET /site/config``
--------------------

The chrome the portal needs before it knows who is asking: the organization
name, the active theme, the contact address, the same navigation the
server-rendered site shows, and the members-only pages this caller may open.
It is the one API call the SPA makes with no session, so it is ``AllowAny``.

.. code-block:: json

   {
     "org_name": "CalDART",
     "theme": "duty",
     "contact_email": "info@caldart.org",
     "nav": [
       {"title": "About", "url": "/about/", "active": false, "kind": "page"},
       {"title": "Join", "url": "/portal/join", "active": false, "kind": "portal"},
       {"title": "Sign in", "url": "/portal/login", "active": false, "kind": "portal"}
     ],
     "members_pages": []
   }

``nav`` entries carry a ``kind`` of ``page`` or ``portal``, which is how the
public templates render content pages as links and Join and Members as
buttons.  Wagtail pages come first; Join is always offered, and the last entry
is Members for a signed-in reader and Sign in for everybody else.  ``active`` is
true when the request path starts with the entry's URL, which never marks the
home page.

``members_pages`` lists ``{title, url}`` for every live members-only page, and
is empty for a caller who fails the same test the members-only wall applies —
an empty list rather than a 403, so nobody learns which pages exist by asking.
See :doc:`cms` for that test and for where the settings come from.

Before ``migrate`` has created the site settings row, ``org_name`` falls back
to ``CalDART``, ``theme`` to ``duty`` and ``contact_email`` to an empty
string; a settings row with no theme chosen falls back to ``duty`` too.

Statuses: **200**, for anybody.


Tests
=====

``backend/tests/test_reminders_api.py``
   The role matrix on both reminder endpoints, the log filters, and that a dry
   run writes nothing while still counting the candidates it found.

``backend/tests/test_sysadmin_api.py``
   The health payload field by field, the backup list and create paths, and
   every way ``resolve_backup`` refuses a name — traversal, an absolute path
   and a symlink out of the directory included.

``backend/tests/test_site_config.py``
   The payload with and without a settings row, the navigation entries, and
   that ``members_pages`` is empty for a caller who may not read them.
