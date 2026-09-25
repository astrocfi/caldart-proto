.. _api-reports:

============
API: reports
============

Every report the portal downloads — the membership report, the aircraft
register, the payment list, the reconciliation table and the contributions list
— is served by the same three endpoints under ``/api/v1/reports/``, from
``apps.reports``.  A report is named by its **slug** in the URL; the reports,
their columns and the code that builds them are described in :doc:`reports`.
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
                   :doc:`api-aircraft` for ``aircraft``, and :doc:`api-finance`
                   for the three money reports.  A value the list refuses is
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
                   payments report turns it into ``from`` and ``to`` (the first
                   and last day of the period), the contributions report into
                   ``year``; either way the period wins over those parameters.
                   Any other value is
                   ``{"period": ["Unknown period '<value>'."]}``.  A report
                   without periods ignores the parameter.
=================  ============================================================

``page`` and ``page_size`` are ignored: a download carries every matching row.

The file is named ``<stem>-<YYYY-MM-DD>.<csv|pdf>``, dated the day it was built:
``caldart-members``, ``caldart-aircraft``, ``caldart-payments``,
``caldart-reconciliation`` or ``caldart-contributions``.

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


Tests
=====

``backend/tests/test_report_endpoints.py``
   The report list for every role, the role matrix on every report's columns
   and both formats, the 404 for an unknown report and format, the dated
   filenames and media types, and the refusals: a fixed report's columns, an
   unknown column, a refused filter and an unknown period.
``backend/tests/test_report_registry.py``
   The five reports' roles, titles, orientation and periods, and each report's
   query against its list: the same params give the same rows in the same
   order.
``backend/tests/test_reports.py``
   The engine on its own: cells, periods, the CSV and PDF it builds, and the
   download it answers with.
