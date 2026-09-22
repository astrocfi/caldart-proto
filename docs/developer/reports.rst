=======
Reports
=======

CalDART exports data as CSV, for a spreadsheet, and as PDF, for a board pack.
There are three reports — membership, aircraft and payments — and all three
are built on one set of helpers in ``backend/caldart/reports.py``.

.. list-table::
   :header-rows: 1
   :widths: 22 20 24 34

   * - Report
     - Formats
     - Code
     - Endpoints
   * - Membership
     - CSV, PDF
     - ``apps/members/reports.py``
     - ``/admin/members/export.{csv,pdf}``
   * - Aircraft
     - CSV, PDF
     - ``apps/aircraft/reports.py``
     - ``/admin/aircraft/export.{csv,pdf}``
   * - Payments
     - CSV only
     - ``apps/payments/reports.py``
     - ``/admin/payments/export.csv``

All five endpoints are ``account_admin`` (and therefore ``system_admin``); none
of them is paginated.

One rule holds everywhere:

**An export is the list you are looking at.**  The export endpoints take the
same filters as the list they belong to, so a download always matches the
screen it came from.  ``?ordering=`` is the one exception: the members and
aircraft exports honor it, and the payments export ignores it and always
sorts by payment date, newest first.


Shared helpers
==============

``backend/caldart/reports.py`` holds the house style so no app has to reinvent
it:

``csv_response(filename, header, rows)``
   A ``StreamingHttpResponse``, ``text/csv; charset=utf-8``, with a download
   disposition.  Rows are consumed lazily — pass a generator or a queryset
   iterator and the whole table never sits in memory at once.  ``None`` is
   written as an empty cell; quoting is the ``csv`` module's problem.  Each
   cell first passes through ``csv_cell``, which applies the formula policy
   below.
``csv_cell(value)``
   One value as a CSV cell: ``None`` as an empty string, a formula-looking
   string with a leading apostrophe, everything else unchanged.
``pdf_table_response(filename, *, title, subtitle, header, rows, landscape)``
   A reportlab table in the CalDART palette: hairline rules instead of boxes,
   zebra rows, the header repeated on every page, and a footer carrying
   "CalDART · generated <timestamp>" and "Page n of m".  ``landscape`` defaults
   to true, which is landscape US letter (792 × 612 points).  Unlike the CSV
   path this returns an ordinary ``HttpResponse``: reportlab needs the whole
   document before it can write any of it, so a PDF export does hold its rows
   in memory.
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


.. _reports-untrusted-values:

Values a member typed
=====================

Most cells in an export — a name, a city, a certificate number, the search
term a filter carried — are text somebody typed into the portal.  Two rules
keep that text from being read as something other than text.

**CSV: no cell can become a formula.**  A spreadsheet treats a cell opening
with ``=``, ``+``, ``-``, ``@``, a tab or a carriage return as a formula, so a
member whose first name is ``=HYPERLINK("http://evil.test","click")`` would run
code on the administrator's machine.  ``csv_cell`` prefixes such a string with
a single apostrophe, the OWASP treatment: every spreadsheet strips it on
import, and the cell reads as the text it always was.  Only strings are
treated this way; a number or a date passes through untouched.

The money columns are strings — each report formats its cents into dollars
itself — and they still never pick up an apostrophe, because the fields behind
them (``amount_cents``, ``contribution_cents``, the insurance amounts) are
positive integer fields, so a formatted amount never opens with a sign and
always sums correctly in the spreadsheet.  A value a member typed is the case
the policy is for: a phone number entered as ``+1 707 555 0134`` opens with
``+``, so it exports with an apostrophe in front and reads as the text it is.

**PDF: no heading or cell can become markup.**  reportlab parses a paragraph's
text as XML, so ``<b`` in a name or in a filter would abort the export with a
parse error.  ``escape_markup`` turns ``&``, ``<`` and ``>`` into entities, and
``build_pdf_table`` runs the title, the subtitle and every cell through it.


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
* Extend ``DOCUMENTED_COLUMNS`` in ``backend/tests/test_members_reports.py``.  It is
  a deliberate copy of the column table above, and the test that compares it
  with ``MEMBER_REPORT_HEADER`` is what stops the report and this page drifting
  apart.

The PDF divides the page width evenly between columns, so each new column
makes them all narrower.  Sixteen columns is comfortable on landscape letter
at 7.5pt; past about twenty, drop a column or split the report rather than
shrinking the type.


The aircraft report
===================

Served by ``GET /api/v1/admin/aircraft/export.csv`` and ``export.pdf`` to
``account_admin``.  Filenames carry the date: ``caldart-aircraft-2026-09-04.csv``.
Both formats render from one row builder in ``backend/apps/aircraft/reports.py``,
so they cannot disagree about the data — but unlike the membership report they
do **not** share a header tuple or a money format:

.. list-table::
   :header-rows: 1
   :widths: 20 40 40

   * -
     - CSV (``HEADER``)
     - PDF (``PDF_HEADER``)
   * - Column names
     - machine names: ``n_number``, ``liability_per_occurrence``, …
     - human titles: "N-number", "Liability / occurrence", …
   * - Money
     - plain decimals, ``1000000.00``
     - currency, ``$1,000,000``

That split is deliberate — one file is parsed and the other is read — and it
is the reason ``_dollars(cents, *, currency)`` takes a keyword.

The twelve columns, in order: ``n_number``, ``make``, ``model``, ``owner``,
``owner_type``, ``insurance_carrier``, ``liability_per_occurrence``,
``liability_per_person``, ``hull``, ``insurance_expiration``,
``insurance_current``, and ``pilots`` — the display names of the members who
have attached the airplane, from ``apps.aircraft.services.pilot_names``.

Both exports take the register's full filter set: ``search``, ``make``,
``owner_type``, ``insurance`` (``current`` / ``expired`` / ``missing``),
``expiring_within``, ``is_active`` and ``ordering``.  The PDF subtitle names
every one of them, through ``AircraftExportMixin.applied_filters``.


The payments report
===================

Served by ``GET /api/v1/admin/payments/export.csv`` to ``account_admin``.
Three things set it apart from the other two:

* **CSV only.**  There is no PDF export; the account-administrator screen has
  a period table on it instead, and a board pack takes a screenshot of that or
  a spreadsheet built from this file.
* **The filename has no date in it** — it is always ``caldart-payments.csv``.
* **It ignores ``?ordering=``** and always sorts by payment date, newest
  first, even though the list endpoint beside it honors ten ordering fields.

Columns, from ``CSV_HEADER`` in ``backend/apps/payments/reports.py``:
``paid_on``, ``name``, ``email``, ``plan``, ``plan_amount``, ``contribution``,
``total``, ``provider``, ``wallet``, ``status``, ``provider_ref``.  Money is a
plain decimal; ``plan`` is empty for a pure donation.

Filters are ``from``, ``to``, ``provider``, ``status`` and ``search``.  The
export includes **every** status, while ``GET /admin/payments/summary`` counts
only ``succeeded`` rows — so an export and a period total will differ whenever
there are failed attempts in the range, which is expected rather than a fault.

``paid_on`` comes from the ``paid_at`` annotation,
``Coalesce(completed_at, created_at)``.  The list, the summary and this export
all key off it, which is what stops the three answering "when was this paid?"
differently.


Testing a report
================

``backend/tests/test_reports.py`` covers the shared helpers: streaming,
laziness, download headers, escaping, pagination and an empty result set.

``backend/tests/test_members_reports.py`` covers the membership report and is
the pattern to copy.  Assertions worth keeping:

* the header equals the column list documented above, verbatim;
* a fully populated member's row, cell by cell;
* the lifetime and "nothing on file" conventions above;
* each filter narrows the export, and ``?ordering=`` reorders it;
* the export is not paginated;
* the PDF is valid (``%PDF-`` … ``%%EOF``), is landscape letter — assert on
  ``/MediaBox [0 0 792 612]`` — and paginates a long report.

PDF page content is compressed, so you cannot grep the bytes for a cell.  Test
what the document *says* at the level above instead: the subtitle is
``filter_summary(applied_filters(request))``, and both are ordinary functions.

Related
=======

The export endpoints themselves are documented on the page for each app:
:doc:`api-members`, :doc:`api-aircraft` and :doc:`api-payments`.
