=======
Reports
=======

CalDART exports data as CSV, for a spreadsheet, and as PDF, for a board pack.
PLAN §11 defines three reports: membership, aircraft and payments.  This page
covers the shared machinery and the membership report; the other two are built
on the same helpers by ``feat/aircraft-leader`` and ``feat/payments``.

Two rules hold for every report:

1. **An export is the list you are looking at.**  The export endpoints take the
   same filters and the same ``?ordering=`` as the list they belong to, and
   they are not paginated: you get every matching row, not the page on screen.
2. **One column list per report.**  The CSV and the PDF read the same
   definition, so they cannot disagree about what a column means.


Shared helpers
==============

``backend/caldart/reports.py`` holds the house style so no app has to reinvent
it:

``csv_response(filename, header, rows)``
   A ``StreamingHttpResponse`` with a download disposition.  Rows are consumed
   lazily — pass a generator or a queryset iterator and the whole table never
   sits in memory at once.  ``None`` is written as an empty cell; quoting is
   the ``csv`` module's problem.
``pdf_table_response(filename, *, title, subtitle, header, rows, landscape)``
   A reportlab table in the CalDART palette: hairline rules instead of boxes,
   zebra rows, the header repeated on every page, and a footer carrying
   "CalDART · generated <timestamp>" and "Page n of m".  ``landscape`` defaults
   to true, which is landscape US letter (792 × 612 points).
``build_pdf_table(buffer, …)``
   The same, into any writable binary stream, for tests and for anything that
   is not an HTTP response.
``filter_summary(filters)``
   Renders ``{"status": "current", "dart": "Napa"}`` as
   ``status: current · dart: Napa``, dropping empty values, or "No filters
   applied".  It is what the PDF prints as its subtitle.

Fraunces and IBM Plex are web fonts and are not embedded in the PDFs; the
built-in Times and Helvetica families carry the same serif-display,
sans-supporting-text contrast.


The membership report
=====================

Served by ``GET /api/v1/admin/members/export.csv`` and ``export.pdf`` to
``account_admin`` and ``system_admin`` — see :doc:`api-members` for the
filters.  The filenames carry the date: ``caldart-members-2026-09-04.csv``.

Columns, in order, from ``backend/apps/members/reports.py``:

==================== ==========================================================
Column               Contents
==================== ==========================================================
name                 Full name, or the email address when no name is on file
email                Login address
phone                Primary phone from the profile
dart                 DART name, blank when unaffiliated
status               ``current``, ``expired`` or ``none``
plan                 Plan behind that status, e.g. ``Annual`` or ``Life``
expires_on           End of unbroken coverage; **blank for a lifetime member**
certificate          Pilot certificate, e.g. ``Private``; blank for none
certificate_number   Certificate number as entered
ifr                  ``Yes``, ``No`` or ``Not applicable``
medical_type         ``BasicMed``, ``Third class``, …; blank for none
medical_expiration   Medical expiry date
aircraft             N-numbers of the planes the member commonly flies, spaced
city                 City from the profile
state                Two-letter state
joined_on            Start of the earliest membership term
==================== ==========================================================

Dates are ISO-8601 (``YYYY-MM-DD``) so a spreadsheet sorts them correctly.

Two conventions are worth knowing when you read a row:

* A **lifetime** member has no expiry date, so ``expires_on`` is empty while
  ``status`` says ``current`` and ``plan`` says ``Life``.  That matches the
  API, where ``expires_on`` is ``null``.
* "Nothing on file" choices — a ``none`` certificate or medical — export as an
  empty cell rather than the word "None", which reads as a value in a
  spreadsheet.

The PDF subtitle lists the filters that were applied.  Which query parameters
count as filters is ``EXPORT_FILTER_PARAMS`` in ``api/admin_filters.py``;
``applied_filters(request)`` picks out the ones actually supplied, ignoring
parameters left blank.


How to add a column
===================

Everything about a column lives in one tuple.  In
``backend/apps/members/reports.py``:

.. code-block:: python

   MEMBER_REPORT_COLUMNS = (
       ("name", lambda ctx: ctx["user"].display_name),
       ...
       ("county", lambda ctx: _value(ctx["profile"], "county")),
   )

Add an entry and both exports pick it up: ``MEMBER_REPORT_HEADER`` is derived
from it, and ``member_report_rows`` builds each row by calling every value
function in order.

The ``ctx`` dictionary a value function receives is built by ``_row_context``
and holds ``user``, ``profile`` (which may be ``None``), ``dart``,
``membership`` (the computed status dictionary), ``aircraft`` (a list of
N-numbers) and ``joined_on``.  Three helpers keep the entries short:
``_iso(date)`` formats a date or gives ``""``, ``_value(profile, field)`` reads
a profile field safely, and ``_display(profile, field)`` gives the human label
behind a ``choices`` field and blanks the "nothing on file" values.

Then:

* If the column needs data the queryset does not already carry, add it to
  ``member_admin_queryset`` in ``api/admin_filters.py`` — as
  ``select_related``/``prefetch_related`` for a relation, or as an annotation.
  Do not fetch it inside the value function: the export streams row by row, so
  a query there is a query per member.
* Update the column table above.
* Extend ``PLAN_COLUMNS`` in ``backend/tests/test_members_reports.py``.  It is
  a deliberate copy of PLAN §11, and the test that compares it with
  ``MEMBER_REPORT_HEADER`` is what stops the report and the specification
  drifting apart — so update PLAN.rst in the same commit.

The PDF divides the page width evenly between columns, so each new column
makes them all narrower.  Sixteen columns is comfortable on landscape letter
at 7.5pt; past about twenty, drop a column or split the report rather than
shrinking the type.


Testing a report
================

``backend/tests/test_reports.py`` covers the shared helpers: streaming,
laziness, download headers, escaping, pagination and an empty result set.

``backend/tests/test_members_reports.py`` covers the membership report and is
the pattern to copy.  Assertions worth keeping:

* the header equals PLAN §11's column list, verbatim;
* a fully populated member's row, cell by cell;
* the lifetime and "nothing on file" conventions above;
* each filter narrows the export, and ``?ordering=`` reorders it;
* the export is not paginated;
* the PDF is valid (``%PDF-`` … ``%%EOF``), is landscape letter — assert on
  ``/MediaBox [0 0 792 612]`` — and paginates a long report.

PDF page content is compressed, so you cannot grep the bytes for a cell.  Test
what the document *says* at the level above instead: the subtitle is
``filter_summary(applied_filters(request))``, and both are ordinary functions.
