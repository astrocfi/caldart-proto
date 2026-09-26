.. _api-reports:

============
API: reports
============

Every report the portal downloads — the membership report, the aircraft
register, the payment list, the reconciliation table, the contributions list,
the donors report and the email log — is served by the same three endpoints under ``/api/v1/reports/``, from
``apps.reports``.  A report is named by its **slug** in the URL; the reports,
their columns and the code that builds them are described in :doc:`reports`.
The same app keeps each account's saved sets of a report's columns
(:ref:`api-report-column-sets`), the subscriptions that email a report on a
schedule (:ref:`api-report-subscriptions`), and each DART's monthly roster
(:ref:`api-report-rosters`); how those are sent is :doc:`scheduled-reports`.
:doc:`api-reference` covers the conventions these endpoints share — session
authentication, the CSRF header, and the error shapes.

Each report names the roles that may read it; a ``system_admin`` and a Django
superuser read every one:

.. list-table::
   :header-rows: 1
   :widths: 18 28 30 12 12

   * - Slug
     - Title
     - Roles
     - Columns
     - Periods
   * - ``members``
     - CalDART membership report
     - ``dart_leader``, ``account_admin``
     - chosen
     - no
   * - ``aircraft``
     - CalDART aircraft register
     - ``account_admin``
     - chosen
     - no
   * - ``payments``
     - CalDART payments
     - ``treasurer``, ``account_admin``
     - chosen
     - yes
   * - ``reconciliation``
     - CalDART reconciliation
     - ``treasurer``, ``account_admin``
     - fixed
     - no
   * - ``contributions``
     - CalDART contributions
     - ``treasurer``, ``account_admin``
     - fixed
     - yes
   * - ``donors``
     - Donors
     - ``treasurer``
     - chosen
     - yes
   * - ``emails``
     - CalDART email log
     - ``system_admin``
     - chosen
     - no

A slug the registry does not hold answers **404** to every signed-in caller,
before any role is checked; a caller the report's roles do not admit answers
**403**; an anonymous caller answers **401**.


``GET /reports``
================

The reports the caller may read, in the order of the table above.  Any
signed-in user may ask; a member who may read no report gets an empty list.
Unpaginated::

  [
    {"slug": "payments", "title": "CalDART payments", "choosable": true, "periods": true},
    {"slug": "reconciliation", "title": "CalDART reconciliation", "choosable": false,
     "periods": false},
    {"slug": "contributions", "title": "CalDART contributions", "choosable": false,
     "periods": true}
  ]

``choosable`` says whether ``?columns=`` may choose the report's columns, and
``periods`` whether the report takes ``?period=``.

Statuses: **200**; **401** when anonymous.


``GET /reports/{slug}/columns``
===============================

Every column the report can carry, in export order, so the screen's column
chooser is data-driven.  One entry per column::

  [{"key": "name", "label": "Name", "default": true}, ...]

``key`` is what ``?columns=`` names, ``label`` is the header both formats print,
and ``default`` says whether the column is in the report when the caller chooses
none.  Every column of a report whose columns are fixed is a default.  The full
registries are in :doc:`reports`.

Statuses: **200**; **401** when anonymous; **403** for a caller the report does
not admit; **404** for an unknown slug.


``GET /reports/{slug}/export.csv`` and ``export.pdf``
=====================================================

The report as a file.  The format is the extension; any other extension is a
**404**.  The query string carries:

=================  ============================================================
Parameter          Effect
=================  ============================================================
The report's       Exactly the filters the report's own list takes, applied the
filters            same way: :doc:`api-members` for ``members``,
                   :doc:`api-aircraft` for ``aircraft``, :doc:`api-finance`
                   for the four money reports, and :doc:`api-system` for
                   ``emails``.  A value the list refuses is
                   refused here with the same **400**, keyed by the parameter.
``ordering``       The list's own ordering, with the list's own rules: the
                   payments report refuses an unknown field as the payment list
                   does, and the other reports ignore one.
``columns``        A comma-separated list of column keys, choosing both which
                   columns appear and in what order.  Leaving it out, or
                   leaving it blank, gives the default columns.  An unknown key
                   is ``{"columns": ["Unknown column: <key>"]}``, a repeated one
                   ``{"columns": ["Repeated column: <key>"]}``, and any key at
                   all on a report whose columns are fixed
                   ``{"columns": ["This report's columns are fixed."]}``.
``period``         ``this_month``, ``last_month``, ``this_year`` or
                   ``last_year``, counted from the day the report is built.  The
                   payments and donors reports turn it into ``from`` and ``to``
                   (the first and last day of the period), the contributions
                   report into ``year``; either way the period wins over those
                   parameters.  Any other value is
                   ``{"period": ["Unknown period '<value>'."]}``.  A report
                   without periods ignores the parameter.
=================  ============================================================

``page`` and ``page_size`` are ignored: a download carries every matching row.

The file is named ``<stem>-<YYYY-MM-DD>.<csv|pdf>``, dated the day it was built:
``caldart-members``, ``caldart-aircraft``, ``caldart-payments``,
``caldart-reconciliation``, ``caldart-contributions``, ``caldart-donors`` or
``caldart-emails``.

Statuses:

* **200** — ``text/csv; charset=utf-8`` or ``application/pdf``, with a
  ``Content-Disposition`` of ``attachment`` and that filename.
* **400** — a parameter the report refuses, keyed by that parameter.
* **401**, **403**, **404** — as above.

From ``curl``, signed in as the demo account administrator (see
:doc:`api-reference` for the sign-in):

.. code-block:: console

   $ curl -s -b jar -o members.pdf \
       "http://localhost:8000/api/v1/reports/members/export.pdf?dart=1"
   $ curl -s -b jar -o giving.csv \
       "http://localhost:8000/api/v1/reports/contributions/export.csv?period=last_year"


.. _api-report-column-sets:

Saved column sets
=================

A caller may name a choice of a report's columns and keep it, to load again the
next time they download that report.  The sets are the caller's own: nobody
else sees or changes them.  Any caller the report admits may keep sets of its
columns, and the checks on the slug are those above: **404** for an unknown
report, **403** for a caller it does not admit.  A report whose columns are
fixed keeps no sets.

``GET /reports/{slug}/column-sets``
-----------------------------------

The caller's own sets for the report, by name, unpaginated::

  [{"id": 4, "name": "Roster", "columns": ["name", "phone", "dart"]}]

``columns`` holds the keys, in the order the report prints them.

Statuses: **200**; **401**, **403**, **404** as above.

``POST /reports/{slug}/column-sets``
------------------------------------

Save the columns under a name.  The body is ``{"name": "Roster", "columns":
["name", "phone", "dart"]}``.  A name the caller has not used for this report
creates a set; a name they have used replaces that set's columns and keeps its
id, so saving under an existing name is an overwrite.  The name is compared
exactly: ``roster`` and ``Roster`` are two sets.  Either way the answer is
**201** with the set, as ``GET`` lists it.

The body is refused with **400**:

* ``{"name": ["This field may not be blank."]}``, or the length refusal, for a
  name that is blank or longer than 60 characters;
* ``{"columns": ["Choose at least one column."]}`` for an empty list;
* ``{"columns": ["Unknown column: <key>"]}`` and
  ``{"columns": ["Repeated column: <key>"]}`` as a download refuses them;
* ``{"columns": ["This report's columns are fixed."]}`` for a report whose
  columns are fixed.

``DELETE /reports/{slug}/column-sets/{id}``
-------------------------------------------

Remove one of the caller's sets: **204**.  A set that belongs to another
account, or to another report, answers **404** and is left alone.


.. _api-report-subscriptions:

Subscriptions
=============

A subscription emails one report to one address on a schedule, as a CSV, a PDF
or both, built exactly as the download is.  The daily run that sends them, the
schedule and the safety rule are :doc:`scheduled-reports`.

Every subscription endpoint is for the finance roles, ``treasurer`` and
``account_admin`` (a ``system_admin`` passes too); anyone else gets **403**.
Within that, a caller sees and touches only the subscriptions for reports they
may read: a treasurer sees those of the three money reports and never one of the
membership report, and one they may not see answers **404**.

``GET /reports/subscriptions``
------------------------------

Every subscription the caller may see, ordered by report and then by address,
unpaginated::

  [
    {
      "id": 2,
      "report": "payments",
      "report_title": "CalDART payments",
      "recipient_user": 5,
      "recipient_name": "Lucia Ferreira",
      "recipient_email": "treasurer@example.org",
      "filters": {"period": "this_year"},
      "columns": [],
      "formats": "csv",
      "cadence": "quarterly",
      "weekday": 0,
      "is_active": true,
      "created_by_name": "Curtis Whitfield",
      "last_sent_at": null,
      "next_due_on": "2027-01-01"
    }
  ]

``recipient_user`` is the account the report goes to, or ``null`` for an
address outside CalDART, whose ``recipient_name`` is then blank.
``filters`` holds the report's own params, ``period`` included; ``columns`` the
chosen keys, empty for the report's defaults.  ``weekday`` (0 Monday to 6
Sunday) is read by the ``weekly`` cadence alone.  ``created_by_name`` is blank
once the account that set it up is gone.

``POST /reports/subscriptions``
-------------------------------

Set one up:

.. code-block:: json

   {
     "report": "members",
     "recipient_email": "board@example.org",
     "filters": {"dart": "3"},
     "columns": ["name", "phone", "email"],
     "formats": "pdf",
     "cadence": "weekly",
     "weekday": 0,
     "confirmed": true
   }

``filters``, ``columns``, ``weekday`` and ``confirmed`` may be left out: no
filters, the default columns, Monday, and not confirmed.  The answer is **201**
with the subscription as ``GET`` lists it; the caller is recorded as the one
who set it up, and it is first due on its schedule's next day after today.

The recipient is named by address.  When an account holds that address,
compared without regard to case, the subscription is bound to the account and
keeps the account's own address; an account that holds no role that may read
the report, or that has been deactivated, is refused.  When no account holds it,
the caller must confirm the address with ``confirmed: true``.

Refusals:

* **403** when the caller may not read the report named, before anything else
  is checked;
* **400** ``{"recipient_email": ["<name> does not hold a role that may read
  this report."]}`` for an account that may not read it, confirmed or not;
* **400** ``{"confirmed": ["Tick the box to confirm this address may receive
  this report."]}`` for an address no account holds, until it is confirmed;
* **400** ``{"report": ["\"<slug>\" is not a valid choice."]}`` for an unknown
  report, and likewise for ``formats`` and ``cadence``; ``weekday`` outside 0
  to 6 is refused under ``weekday``;
* **400** under ``columns`` for a column list the report refuses, with the
  messages a download gives (an unknown or repeated key, or any key at all for
  a report whose columns are fixed);
* **400** under ``filters``, keyed by the filter, for a filter value the report
  refuses — the report is built from the filters exactly as a download builds
  it, so ``{"filters": {"period": ["Unknown period 'someday'."]}}`` — and
  ``{"filters": {"columns": ["Choose columns with the columns field, not as a
  filter."]}}`` for a ``columns`` entry among the filters.

``GET | PATCH | DELETE /reports/subscriptions/{id}``
----------------------------------------------------

``GET /reports/subscriptions/{id}`` answers the subscription as the list does.
``PATCH /reports/subscriptions/{id}`` changes any of ``is_active``,
``filters``, ``columns``, ``formats``, ``cadence``, and ``weekday``, checked as
``POST`` checks them; the filters and columns are checked only when the edit
changes one of them, so a subscription whose stored filters the report no
longer takes can still be paused.  The report and the recipient are fixed once
set up, and other fields are ignored.  Changing the cadence or the
weekday moves ``next_due_on`` to the schedule's next day after today; any other
edit leaves it.  Resuming (``is_active: true``) a subscription whose account may
no longer read the report is refused with **400** under ``is_active``, with the
same message as above.  ``DELETE /reports/subscriptions/{id}`` answers
**204**.

``POST /reports/subscriptions/{id}/send``
-----------------------------------------

Send it now, whatever its date, and answer **200** with the result of that one
send, shaped as :ref:`api-reports-run` describes::

  {"sent": 1, "skipped": 0, "failed": 0, "skipped_by_reason": {},
   "actions": [{"kind": "report", "member": "board@example.org",
                "email": "board@example.org", "on": null,
                "amount_cents": null,
                "detail": "CalDART membership report, PDF"}]}

``last_sent_at`` is stamped and ``next_due_on`` stays where it was.  The
recipient is brought up to date first, as the daily run does
(:doc:`scheduled-reports`).  A recipient who may no longer read the report is skipped as ``not_permitted`` and
the subscription is paused; a send the mail server refuses is counted in
``failed``, as is a report the stored filters no longer build.  One
``report.send`` audit line names the caller and the
subscription.  The body is empty.


.. _api-report-rosters:

DART rosters
============

Each active DART is emailed its roster once a month, to the people on its list
ticked to receive it (``receives_roster``, see :doc:`api-darts`).  These two
endpoints are ``account_admin`` only (and ``system_admin``).

``GET /reports/rosters``
------------------------

One row per active DART, by name, unpaginated::

  [{"dart_id": 3, "name": "Bay Area DART", "roster_recipients": 2,
    "roster_sent_at": "2026-10-01T06:02:11-07:00"}]

``roster_recipients`` counts the people ticked to receive the roster who have an
email address; ``roster_sent_at`` is when the last roster went out, or ``null``.

``POST /reports/rosters/send``
------------------------------

Send every active DART's roster now, whatever the date, and answer **200** with
the run result (:ref:`api-reports-run`).  The body is optional:
``{"dry_run": true}`` sends nothing and answers who would be sent one.  A DART
whose roster went to everyone ticked is stamped, which counts as its roster for
the month.  A live send writes one ``report.send`` audit line per DART.
**400** when ``dry_run`` is not a boolean.


Tests
=====

``backend/tests/test_email_log_report.py``
   The email log report: its columns and their cells, each filter and the date
   range against the rows downloaded, the order, the refusals, the file name,
   and the ``system_admin``-only role matrix.
``backend/tests/test_report_endpoints.py``
   The report list for every role, the role matrix on every report's columns
   and both formats, the 404 for an unknown report and format, the dated
   filenames and media types, and the refusals: a fixed report's columns, an
   unknown column, a refused filter and an unknown period.
``backend/tests/test_report_registry.py``
   The registry's six reports by slug and, for all but the email log, the
   roles, titles, orientation and periods, and the query against its list: the
   same params give the same rows in the same order.
``backend/tests/test_reports.py``
   The engine on its own: cells, periods, the CSV and PDF it builds, and the
   download it answers with.
``backend/tests/test_saved_column_sets.py``
   Saved column sets: the caller's own only, the overwrite by name, the
   checks on the columns and the name, and the role matrix.
``backend/tests/test_report_subscriptions.py``
   Subscriptions: who may manage them and which they see, binding a recipient
   by address, the refusals, editing, and sending one now.
``backend/tests/test_scheduled_reports.py``
   The schedule over every cadence, the daily run on a frozen clock, the
   command, the timer and ``POST /system/reports/run``.
``backend/tests/test_dart_rosters.py``
   The roster's due rule across months, who is sent it and who is skipped, the
   attachment and the email, and the two roster endpoints.
