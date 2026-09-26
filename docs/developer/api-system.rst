.. _api-reminders-system:

================================
API: reminders, system, and site
================================

The endpoints that keep the installation running and the one the portal calls
before it has a user: ``GET /admin/reminders/log`` and
``POST /system/reminders/run`` from ``apps.reminders``,
``POST /system/reports/run`` from ``apps.reports``,
``GET /system/emails`` and ``GET /system/emails/purposes`` from ``apps.mail``, the health, backup and
renewal-scan routes under ``/system/`` from ``apps.sysadmin``, and
``GET /site/config`` from ``apps.cms``.  :doc:`api-reference` covers the conventions they share —
session authentication, the CSRF header, pagination, and the error shapes.

The subsystem chapters behind them are :doc:`reminders` (what the scan sends
and when), :doc:`scheduled-reports` (which reports and rosters go out, and
when), :doc:`renewals` (what the automatic-renewal scan charges and when),
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
``kind``           One of the five stages ``t60``, ``t30``, ``t7``,
                   ``expired``, ``post30``.  Anything else is a 400 on
                   ``kind``.
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

   {
     "sent": 4,
     "skipped": 12,
     "failed": 0,
     "skipped_by_reason": {"already_sent": 10, "auto_renew": 2},
     "actions": [
       {"kind": "t30", "member": "Maria Alvarez", "email": "maria@example.org",
        "on": "2026-10-14", "amount_cents": null, "detail": ""},
       {"kind": "t7", "member": "Sam Ochoa", "email": "sam@example.org",
        "on": "2026-09-21", "amount_cents": null, "detail": ""}
     ]
   }

``actions`` names the member behind every reminder: ``kind`` is the reminder
kind, ``member`` and ``email`` who it went to, and ``on`` the day their term runs
out.  A live run lists what it sent; a dry run lists what it would have sent, so
an operator can read who is about to be written to before letting the scan write
to them.  ``amount_cents`` is always ``null`` here, because a reminder moves no
money.

``sent`` counts the reminders the run mailed and ``skipped`` those it decided
against — a member who has already had that stage, or whose membership renews
itself.  ``skipped_by_reason`` breaks that number down, with one entry per
reason that occurred and nothing for a reason that did not: the keys are
``already_sent``, ``inactive_user``, ``no_email``, ``lifetime``, ``auto_renew``
and ``renewed``.  ``failed`` counts the sends the mail server refused, which
are in neither of the other two counts and are logged at ERROR with the ids;
between them the three numbers say why a thin run was thin.

A dry run writes nothing at all: no email, no log rows and no membership status
flips.  Its ``sent`` is therefore a count of candidates, not of outcomes: every
member the scan would try to mail lands in it, including ones a live run would
end up recording as a failure, or as skipped because a concurrent run got there
first.  The breakdown per stage is what ``manage.py send_renewal_reminders``
prints; see :doc:`reminders`.

Statuses: **200**; **400** when ``dry_run`` is not a boolean; **401** when
anonymous; **403** for any other role.


.. _api-reports-run:

Scheduled reports
=================

``POST /system/reports/run``
----------------------------

Runs the report sender immediately instead of waiting for the daily timer: every
report subscription that is due, then every DART roster not yet sent this month,
exactly as ``manage.py send_scheduled_reports`` sends them (see
:doc:`scheduled-reports`).  ``system_admin`` only.  The body is optional;
``dry_run`` defaults to ``false``.

.. code-block:: json

   {"dry_run": true}

.. code-block:: json

   {
     "sent": 3,
     "skipped": 1,
     "failed": 0,
     "skipped_by_reason": {"no_recipients": 1},
     "actions": [
       {"kind": "report", "member": "Curtis Whitfield",
        "email": "accountadmin@example.org", "on": null, "amount_cents": null,
        "detail": "CalDART membership report, PDF"},
       {"kind": "roster", "member": "Dana Lee", "email": "dana@example.org",
        "on": null, "amount_cents": null, "detail": "Bay Area DART"}
     ]
   }

Each action is one email: kind ``report`` names the subscription's recipient,
with the report's title and formats in ``detail``, and kind ``roster`` names a
person ticked to receive a DART's roster, with the DART in ``detail``.  ``on``
and ``amount_cents`` are always ``null``.  ``skipped_by_reason`` holds one entry
per reason that occurred: ``not_permitted`` (the subscription's account may no
longer read the report, so it was paused), ``no_recipients`` (a DART with nobody
ticked who has an address) and ``no_email`` (one ticked person without an
address).  ``failed`` counts the emails the mail server refused, and the reports
the stored filters could no longer build; each of them stays due.

A dry run writes nothing: no email, no pause, no stamp, and no date moves on.  The
caller is the actor on the ``reports.run`` audit line.

Statuses: **200**; **400** when ``dry_run`` is not a boolean; **401** when
anonymous; **403** for any other role.


.. _api-email-log:

The email log
=============

``GET /system/emails``
----------------------

Every email the installation has tried to send, paginated, and newest first.
``system_admin`` only: the rows carry every address written to, which is
operations work rather than membership work.  Each row is written by the shared
mail funnel after the send, so a refusal is on the list beside the messages that
went out -- which is the point of it, and true for a renewal reminder too.  A
refused reminder has its ``ReminderLog`` row deleted, so the reminder stays
due, but the send itself is on this list with a ``failed`` status; the
reminder run's ``failed`` count reports it as well.

.. code-block:: json

   {
     "count": 412,
     "next": "http://localhost:8000/api/v1/system/emails?page=2",
     "previous": null,
     "results": [
       {"id": 903, "to_email": "marta.reyes@example.org", "user_id": 37,
        "user_name": "Marta Reyes", "purpose": "receipt", "purpose_label": "Receipt",
        "subject": "CalDART: your receipt for $95.00",
        "sent_at": "2026-01-08T09:00:02-08:00", "status": "sent", "error": "",
        "attachments": "receipt-2026-0041.pdf"}
     ]
   }

``purpose``
   The template the body came from, which is what the message was for:
   ``reminder_t60``, ``reminder_t30``, ``reminder_t7``, ``reminder_expired``,
   ``reminder_post30``, ``renewal_enabled``, ``renewal_notice``,
   ``renewal_card_expiring``, ``renewal_charged``, ``renewal_failed``,
   ``renewal_canceled``, ``receipt``, ``refund``, ``member_invitation``,
   ``password_reset``, ``scheduled_report`` or ``dart_roster``.

``purpose_label``
   The purpose in words, such as ``Renewal reminder (30 days)`` for
   ``reminder_t30``, from ``PURPOSE_LABELS`` in ``apps/mail/purposes.py``.  A
   purpose that dictionary does not name reads as the purpose itself, so a
   template added without a label still shows up.

``user_id``, ``user_name``
   ``user_id`` is the account the email concerned, ``null`` for a message sent
   to an address with no account behind it and for one whose account has since
   been deleted.  ``user_name`` is the recipient's name as it was at send
   time -- a DART contact's own name, for example, which needs no account --
   falling back to the linked account's current name when that was not
   recorded, and empty when neither names anybody.

``status``, ``error``
   ``sent`` for a message the mail server took, and ``failed`` with the
   exception class in ``error`` for one it refused.  ``error`` is blank on a
   send that went out.

``attachments``
   The filenames that rode along, comma-separated, and blank when none did.

=================  ============================================================
Parameter          Effect
=================  ============================================================
``purpose``        An exact purpose, as listed above.  An unknown value answers
                   an empty page rather than a 400: the purposes are the
                   template names, not a fixed enumeration.
``status``         ``sent`` or ``failed``.  Anything else is a 400 on
                   ``status``.
``from``, ``to``   ``YYYY-MM-DD``, compared against the date part of
                   ``sent_at``: ``from`` is on or after, ``to`` on or before.
``q``              Case-insensitive match on the address written to, the name
                   recorded on the row, and the recipient account's first and
                   last name.
``ordering``       ``sent_at``, with a ``-`` prefix for descending.  An
                   unrecognized field is ignored.  Sends in the same instant
                   follow their ``id`` in the same direction, as they do in the
                   ``emails`` report.
``page``,          Standard pagination (25 by default, 200 at most).
``page_size``
=================  ============================================================

The log records the message, not the delivery: a mail server that accepts a
message and bounces it later is a ``sent`` row.  ``ReminderLog`` is not replaced
by any of this -- it is the key that keeps a reminder stage from repeating, and
``GET /admin/reminders/log`` still answers "was this member ever told?" for an
account administrator, who does not hold ``system_admin``.

The filters are ``EmailLogFilterSet`` in ``apps/mail/filters.py``, which the
``emails`` report shares: ``/reports/emails/export.csv`` and ``export.pdf`` take
the same parameters and download every matching row rather than one page (see
:doc:`api-reports`).

Statuses: **200**; **400** for an unknown ``status`` or an unparseable date;
**401** when anonymous; **403** for every other role.

``GET /system/emails/purposes``
-------------------------------

The purposes the portal's purpose filter offers, one ``{value, label}`` per
entry of ``PURPOSE_LABELS``, in that dictionary's order.  Unpaginated;
``system_admin`` only, as the log is.

.. code-block:: json

   [
     {"value": "reminder_t60", "label": "Renewal reminder (60 days)"},
     {"value": "reminder_t30", "label": "Renewal reminder (30 days)"},
     {"value": "receipt", "label": "Receipt"}
   ]

``value`` is what ``?purpose=`` takes and ``label`` the words the table shows
for it, the same ``purpose_label`` a row carries.

Statuses: **200**; **401** when anonymous; **403** for every other role.


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
changes no mandate, emails nobody and charges nobody, and is itself recorded in
the audit log.

.. code-block:: json

   {
     "noticed": 2, "warned": 0, "charged": 1, "failed": 0, "paused": 0, "skipped": 3,
     "actions": [
       {"kind": "renewal_notice", "member": "Maria Alvarez", "email": "maria@example.org",
        "on": "2026-10-14", "amount_cents": null, "detail": ""},
       {"kind": "charge", "member": "Sam Ochoa", "email": "sam@example.org",
        "on": "2026-09-24", "amount_cents": 4500, "detail": ""}
     ]
   }

``actions`` names the member behind every email the scan sent and every charge it
took.  ``kind`` is the email template, or ``charge`` for the money itself;
``member`` and ``email`` are who it concerned; ``on`` is the date the action
turns on; ``amount_cents`` is integer cents for a charge and ``null`` otherwise;
and ``detail`` carries anything else worth printing, such as a decline reason.  A
dry run lists what a live run would do, and, since it cannot ask the provider
whether a charge would be taken, reports the message a charge that succeeds
sends.

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

``backend/tests/test_mail_log.py``
   The funnel writing one row per send, a refused send recorded and re-raised,
   every kind of email the application sends landing in the log, and the
   endpoint's filters and role matrix.

``backend/tests/test_sysadmin_api.py``
   The health payload field by field, the backup list and create paths, and
   every way ``resolve_backup`` refuses a name — traversal, an absolute path
   and a symlink out of the directory included.

``backend/tests/test_site_config.py``
   The payload with and without a settings row, the navigation entries, and
   that ``members_pages`` is empty for a caller who may not read them.
