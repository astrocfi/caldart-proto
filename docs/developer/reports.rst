=======
Reports
=======

CalDART exports data as CSV, for a spreadsheet, and as PDF, for a board pack.
There are six reports, and every one of them is built by the same code: each
app declares what its report is — its columns, who may read it, and the query
that finds its rows — as a ``ReportSpec``, and ``build_report`` in
``backend/caldart/reports.py`` turns any spec into either file.  The endpoints
that list the reports, answer their columns and download them are the same
three for every report, under ``/api/v1/reports/``; :doc:`api-reports`
documents them.

.. list-table::
   :header-rows: 1
   :widths: 16 22 30 32

   * - Slug
     - Report
     - Declared in
     - Readers
   * - ``members``
     - Membership
     - ``apps/members/reports.py``
     - ``dart_leader``, ``account_admin``
   * - ``aircraft``
     - Aircraft register
     - ``apps/aircraft/reports.py``
     - ``account_admin``
   * - ``payments``
     - Payment list
     - ``apps/payments/reports.py``
     - ``treasurer``, ``account_admin``
   * - ``reconciliation``
     - Reconciliation table
     - ``apps/payments/reconciliation.py``
     - ``treasurer``, ``account_admin``
   * - ``contributions``
     - Contributions list
     - ``apps/payments/reports.py``
     - ``treasurer``, ``account_admin``
   * - ``emails``
     - Email log
     - ``apps/mail/reports.py``
     - ``system_admin``

A ``system_admin`` and a Django superuser read every report.
``apps/reports/registry.py`` gathers the six specs into ``REPORTS``, keyed by
slug, and ``apps/reports/permissions.py`` decides who may read one with
``can_read_report(user, spec)``, which is ``user_has_any_role`` over the spec's
roles.

One rule holds everywhere:

**A download is the list you are looking at.**  Each report's query is the
filter and ordering code its list runs — the member list's filter set and
ordering, the register's, the payment list's query serializer, the email log's filter set — so the same
query string gives the same rows, in the same order, on the screen and in the
file.  ``?ordering=`` is honored with the list's own rules, and nothing is
paginated.


The engine
==========

``ReportSpec(slug, title, filename_stem, columns, roles, query, landscape=True, choosable=True, resolve=keep_params)``
   One report.  ``slug`` names it in every URL; ``title`` heads its PDF and
   labels it in the portal; ``filename_stem`` begins its file name
   (``caldart-members``).  ``columns`` is its registry of ``ReportColumn``
   entries, in export order.  ``roles`` are the role slugs that may read it.
   ``query(params)`` answers a ``ReportQuery`` — the rows, and the filters that
   were applied, named for the PDF subtitle — and raises DRF's
   ``ValidationError`` for a parameter it refuses, so a download answers 400 the
   way the list does.  ``landscape`` picks the PDF's orientation.
   ``choosable=False`` fixes the columns: every column is printed, and a
   ``columns`` parameter is refused with ``This report's columns are fixed.``
   ``resolve(params, today)`` turns the parameters into the ones the query
   reads; a dated report uses it for ``period`` (below), and ``spec.periods`` is
   true exactly when it is not ``keep_params``, the identity.
``build_report(spec, params, *, fmt, today=None)``
   The whole job.  It resolves the parameters for ``today`` (the local date by
   default), chooses the columns — the ``columns`` parameter, or the defaults,
   through ``chosen_columns`` — runs the query, and turns every cell into text
   with ``cell_text``.  A CSV is the column labels and then one line per row,
   every cell through ``csv_cell``; a PDF is ``build_pdf_table`` with the spec's
   title and orientation, ``filter_summary`` of the applied filters as the
   subtitle, and each column's registry width.  It answers a ``ReportDocument``:
   the ``filename`` (``<stem>-<YYYY-MM-DD>.<csv|pdf>``), the ``media_type``
   (``text/csv`` or ``application/pdf``) and the ``content`` bytes.  The whole
   file is built in memory: every report here fits, and one path to a file is
   worth more than a streamed one.
``report_response(document)``
   The document as a download: its bytes, ``text/csv; charset=utf-8`` or
   ``application/pdf``, and an ``attachment`` ``Content-Disposition`` carrying
   the file name.
``Report``
   The protocol every ``ReportSpec`` satisfies whatever its row type, which is
   what the registry holds and ``build_report`` takes.

Periods
-------

``PERIODS`` is ``this_month``, ``last_month``, ``this_year`` and ``last_year``,
and ``period_bounds(period, today)`` answers the first and last day of one,
counted from ``today``; any other value is refused with
``Unknown period '<value>'.``, keyed ``period``.  ``resolve_period(params,
today, expand)`` replaces ``period`` with the parameters ``expand`` builds from
those two days, which win over any the caller gave.  The payments report expands
a period into ``from`` and ``to``, and the contributions report into ``year``;
the other three reports keep their parameters as they are and ignore a
``period``.  Because ``build_report`` resolves first, ``?period=`` works on a
download as it does anywhere a report is built later, and "this year" means the
year the report is built in.

Columns and cells
-----------------

``ReportColumn(key, label, default, value, width=1.0)``
   One column: the stable ``key`` a caller asks for, the ``label`` both formats
   print, whether it is in the report by ``default``, the ``value`` function
   that turns one row into that row's cell, and the ``width`` share the PDF
   gives it relative to the other columns of the same report.  A fixed report's
   columns are all defaults.
``select_columns(columns, requested)``
   The columns to export.  A ``requested`` list that is ``None`` or empty means
   the caller chose nothing, and the answer is every column whose ``default``
   is true, in registry order; otherwise it is one column per requested key, in
   the order requested.  A key no column carries raises ``ValueError`` naming
   that key, and so does a key asked for twice.
``chosen_columns(columns, requested)``
   The same for the raw ``?columns=`` parameter — a comma-separated list of
   keys, or an empty string — raising DRF's ``ValidationError`` keyed by
   ``columns`` instead, so every report refuses a bad list the same way.
``column_payload(columns)``
   The registry as the chooser reads it: one ``{"key", "label", "default"}``
   entry per column, in registry order.  ``spec.column_choices()`` answers it
   for a spec, serialized by ``ReportColumnSerializer``.
``Money(cents, drop_zero_cents=False)`` and ``cell_text(value, fmt)``
   Money is the one cell the two formats render differently.  A column whose
   value is a ``Money`` prints ``1234.56`` in a CSV, which a spreadsheet sums,
   and ``$1,234.56`` in a PDF, which a person reads; ``drop_zero_cents`` leaves
   the cents off a round PDF amount, ``$1,000,000``.  ``None`` is a blank cell
   and anything else its ``str``.
``money_label(cents, *, currency=True)``
   Integer cents as the dollars a reader sees: ``12345`` becomes ``$123.45``,
   with commas between thousands.  ``currency=False`` gives ``123.45``.  It is
   text for people either way; an amount bound for Stripe or PayPal is built by
   the provider module that speaks to that API.

Filters
-------

``apply_filterset(filterset_class, params, queryset)``
   Narrows a queryset by a django-filter filter set over the parameters, and
   refuses a value the set refuses with DRF's ``ValidationError`` keyed by that
   filter — the same 400 the list's filter backend answers.
``given_params(params, keys=None)``
   The parameters that carry a value, optionally only those in ``keys``, in
   that order.  A blank value is "not given": a filter bar sends every parameter
   it has.  A report names its applied filters with it, and the payment query
   drops blanks with it before validating, so a blank bound narrows nothing
   whether the parameters came from a query string or a stored mapping.
``ordering_terms(raw)``
   The terms of a comma-separated ``?ordering=``, stripped.  Each report checks
   them against its own orderings.
``filter_summary(filters)``
   Renders ``{"status": "current", "dart": "Napa"}`` as
   ``status: current · dart: Napa``, dropping empty values, or "No filters
   applied".  It is what the PDF prints as its subtitle.

The house style
---------------

``build_pdf_table(buffer, *, title, subtitle, header, rows, landscape, widths)``
   A reportlab table in the CalDART palette, written to any binary stream:
   hairline rules instead of boxes, zebra rows, the header repeated on every
   page, and a footer carrying "CalDART · generated <timestamp>" and "Page n of
   m".  ``landscape`` defaults to true, which is landscape US letter (792 × 612
   points); ``landscape=False`` is the same page upright (612 × 792).
   ``widths`` gives the columns relative shares of the printable width —
   ``[3, 1, 1]`` makes the first column three times either of the others — and
   is scaled to fill the page; without it every column is the same width.  One
   width per column, or ``ValueError``.
``csv_rows(header, rows)`` and ``csv_cell(value)``
   The CSV lines, every cell through ``csv_cell``: ``None`` as an empty string,
   a formula-looking string with a leading apostrophe, everything else
   unchanged.

Fraunces and IBM Plex are web fonts and are not embedded in the PDFs; the
built-in Times and Helvetica families carry the same serif-display,
sans-supporting-text contrast.


.. _reports-receipts:

Receipts and statements
=======================

A receipt and an annual contribution statement are not tables of a list, so
they have their own builders in ``backend/caldart/receipts.py``.  Both are pure
functions — a typed dataclass in, a PDF written to a binary stream out — and
neither reads a model, so the app that holds the payments gathers the facts and
hands them over.

``build_receipt_pdf(buffer, receipt)``
   One upright US-letter page acknowledging one payment: the organization's
   letterhead, the receipt number and the date the money was received, who paid,
   a ``ReceiptLine`` per thing the payment bought with its amount in dollars, the
   total, and how the money arrived.  A line marked ``deductible`` — a
   contribution — also brings the sentence "No goods or services were provided in
   exchange for this contribution" onto the page.  Membership dues are printed as
   dues and never claim a deduction.
``build_statement_pdf(buffer, statement)``
   One upright page covering a member's contributions for a calendar year: a
   ``StatementLine`` per contribution with its date, receipt number, amount,
   refund and net, then the year's total net of refunds and the same 501(c)(3)
   wording in the plural.  Dues are not on it; a statement covers gifts alone.

The letterhead itself comes from ``org_details()`` in ``backend/caldart/org.py``,
which reads the organization's name, contact address, mailing address, EIN and
site URL from the Wagtail site settings a website administrator edits.  A field
nobody has filled in draws no line at all.


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

The money columns are text by the time they reach the CSV — ``cell_text``
renders a ``Money`` cell through ``money_label`` — and they still never pick up
an apostrophe, because the fields behind them (``amount_cents``,
``contribution_cents``, the insurance amounts) are positive integer fields, so a
formatted amount never opens with a sign and always sums correctly in the
spreadsheet.  A value a member typed is the case
the policy is for: a phone number entered as ``+1 707 555 0134`` opens with
``+``, so it exports with an apostrophe in front and reads as the text it is.

**PDF: no heading or cell can become markup.**  reportlab parses a paragraph's
text as XML, so ``<b`` in a name or in a filter would abort the export with a
parse error.  ``escape_markup`` turns ``&``, ``<`` and ``>`` into entities, and
``build_pdf_table`` runs the title, the subtitle and every cell through it.


The membership report
=====================

``members``, for ``dart_leader`` and ``account_admin``.  Its query is the member
list's: ``MemberAdminFilterSet`` over ``member_admin_queryset()``, ordered by
``MemberOrderingFilter.order_queryset``, which the list's ordering backend
calls too — both in ``apps/members/filters.py``.  It takes every filter the
list takes; see :doc:`api-members`.

Columns, in order, from ``backend/apps/members/reports.py``.  The ten marked
"default" are the report when the caller chooses none; the rest are there to be
asked for with ``?columns=``:

==================== ======================= ======= ======================================
Key                  Label                   Default Contents
==================== ======================= ======= ======================================
name                 Name                    yes     Full name, or the email address when
                                                     no name is on file
email                Email                   yes     Login address
phone                Phone                   yes     Primary phone from the profile
dart                 DART                    yes     DART name, blank when unaffiliated
status               Status                  yes     ``current``, ``new``, ``expired``, or
                                                     ``none``
plan                 Plan                    no      Plan behind that status, e.g.
                                                     ``Annual`` or ``Life``
expires_on           Expires                 yes     End of unbroken coverage; **blank for
                                                     a lifetime member**
certificate          Certificate             yes     Pilot certificate, e.g. ``Private``;
                                                     blank for none
certificate_number   Certificate number      no      Certificate number as entered
ifr                  IFR                     no      ``Yes``, ``No``, or ``Not applicable``
medical_type         Medical                 yes     ``BasicMed``, ``Third class``, …;
                                                     blank for none
medical_expiration   Medical expires         yes     Medical expiry date
aircraft             Aircraft                yes     N-numbers of the planes the member
                                                     commonly flies, spaced
city                 City                    no      City from the profile
state                State                   no      Two-letter state
county               County                  no      California county from the profile
joined_on            Joined                  no      Start of the earliest membership term
member_since         Member since            no      The day the member joined, as recorded
                                                     on their profile: the same date until
                                                     the terms before a gap, or before an
                                                     import, are missing
profile_updated      Profile updated         no      Day profile information was last
                                                     written; blank when never edited
==================== ======================= ======= ======================================

``GET /api/v1/reports/members/columns`` answers the same registry as JSON,
for the chooser on the member list.

Dates are ISO-8601 (``YYYY-MM-DD``) so a spreadsheet sorts them correctly.

Two conventions are worth knowing when you read a row:

* A **lifetime** member has no expiry date, so ``expires_on`` is empty while
  ``status`` says ``current`` and ``plan`` says ``Life``.  That matches the
  API, where ``expires_on`` is ``null``.
* "Nothing on file" choices — a ``none`` certificate or medical — export as an
  empty cell rather than the word "None", which reads as a value in a
  spreadsheet.

The PDF subtitle lists the filters that were applied.  Which query parameters
count is ``EXPORT_FILTER_PARAMS`` in ``filters.py``; ``applied_filters(params)``
picks out the ones actually supplied, ignoring parameters left blank.


How to add a column
===================

Everything about a column lives in one tuple.  In
``backend/apps/members/reports.py``:

.. code-block:: python

   MEMBER_REPORT_COLUMNS = (
       ReportColumn("name", "Name", True, lambda ctx: ctx["user"].display_name, width=2.6),
       ...
       ReportColumn("county", "County", False, lambda ctx: _value(ctx["profile"], "county")),
   )

Add an entry and everything picks it up: both headers are the labels,
``build_report`` builds each row by calling the value function of every chosen
column in order, and ``GET /reports/members/columns`` offers the new column to
the chooser.

The ``ctx`` dictionary a value function receives is built by ``_row_context``
and holds ``user``, ``profile`` (which may be ``None``), ``dart``,
``membership`` (the computed status dictionary), ``aircraft`` (a list of
N-numbers) and ``joined_on``.  Three helpers keep the entries short:
``_iso(date)`` formats a date or gives ``""``, ``_value(profile, field)`` reads
a profile field safely, and ``_display(profile, field)`` gives the human label
behind a ``choices`` field and blanks the "nothing on file" values.

Then:

* If the column needs data the queryset does not already carry, add it to
  ``member_admin_queryset`` in ``filters.py`` — as
  ``select_related``/``prefetch_related`` for a relation, or as an annotation.
  Do not fetch it inside the value function: the rows are read a chunk at a
  time, so a query there is a query per member.
* Update the column table above.
* Extend ``DOCUMENTED_COLUMNS`` in ``backend/tests/test_members_reports.py``.  It is
  a deliberate copy of the column table above, and the test that compares it
  with the registry's keys is what stops the report and this page drifting
  apart.

A money column returns a ``Money`` rather than formatting the cents itself, so
each format prints it its own way.

How to add a report
-------------------

Declare a ``ReportSpec`` in the app whose data it reports, next to its columns,
with a ``query`` that reuses the filter and ordering code of the list it
downloads, and add it to ``REPORTS`` in ``apps/reports/registry.py``.  The
endpoints, the role check and both formats follow; document it here and in
:doc:`api-reports`.

Widths and wrapping
-------------------

A column's ``width`` is its share of the printable width, and the shares of the
chosen columns are scaled to fill the page, so their units do not matter.  The
widths of the default columns are tuned so that no cell of the seeded data has
to wrap at the 7.5pt cell font, and
``backend/tests/test_report_columns.py`` measures every default cell of every
seeded row with reportlab's ``stringWidth`` and fails when one no longer fits.

A new default column therefore takes room from the others.  If the measurement
fails, re-tune the widths or make the column non-default; do not shrink the
font.  Adding a non-default column costs the defaults nothing, because a
caller who asks for it asks for a different set.

The aircraft report
===================

``aircraft``, for ``account_admin``.  Its query is the register's:
``AircraftFilter`` from ``apps/aircraft/filters.py``, ordered by
``order_register``, which shares ``nulls_last_order`` with the register's
ordering backend.  The columns, in order, from
``backend/apps/aircraft/reports.py``:

======================== ======================= ======= ==============================
Key                      Label                   Default Contents
======================== ======================= ======= ==============================
n_number                 N-number                yes     Registration, canonical form
make                     Make                    yes     Manufacturer
model                    Model                   yes     Model designation
owner_name               Owner                   yes     Registered owner
owner_type               Owner type              no      Individual, flying club, FBO, …
insurance_carrier        Carrier                 yes     Insurer on the policy
liability_per_occurrence Liability / occurrence  yes     Liability limit per occurrence
liability_per_person     Liability / person      no      Liability limit per person
hull                     Hull                    yes     Hull value insured
insurance_expiration     Expires                 yes     Date the cover runs out
insurance_current        Current                 yes     ``yes`` or ``no``
pilots                   Pilots                  no      Display names of the members who
                                                         have attached the airplane, from
                                                         ``apps.aircraft.services``
                                                         ``.pilot_names``
======================== ======================= ======= ==============================

``GET /api/v1/reports/aircraft/columns`` answers the registry as JSON, for the
chooser on the register screen.  The pilot list is off by default because it is
as long as the number of members who fly the plane, which is the one cell no
width can promise to hold.

The insured amounts are ``Money`` cells that drop round cents:

.. list-table::
   :header-rows: 1
   :widths: 20 40 40

   * -
     - CSV
     - PDF
   * - Money
     - plain decimals, ``1000000.00``
     - currency, ``$1,000,000``

The report takes the register's full filter set: ``search``, ``make``,
``owner_type``, ``insurance`` (``current`` / ``expired`` / ``missing``),
``expiring_within``, ``is_active``, and ``ordering``, plus ``?columns=``.  The
PDF subtitle names every one given a value, from ``EXPORT_FILTER_PARAMS`` in
``apps/aircraft/reports.py``.


The payments reports
====================

Three reports come out of ``backend/apps/payments/``, all of them for the
finance roles, with the tables they download documented in :doc:`api-finance`.

The payment list
----------------

``payments``.  ``PAYMENT_REPORT_COLUMNS`` in ``backend/apps/payments/reports.py``
is its registry, and its query is ``filtered_payments``, which the finance list
reads too: ``PaymentReportQuerySerializer`` validates the parameters and
``requested_ordering`` the ordering, both in the same module.  The report takes
every list filter **and** ``?ordering=``, and ``?period=`` becomes ``from`` and
``to``.  Money is a plain decimal in both formats — the columns format their
cents with ``money_label(cents, currency=False)`` — so the PDF lines up with the
spreadsheet.  The subtitle names the filters given a value.

The report includes **every** status, while ``GET /admin/payments/summary``
counts only money that arrived — so a download and a period total differ
whenever there are failed attempts in the range, which is expected rather than
a fault.

``paid_on`` is the ledger date: ``received_on`` for a payment recorded by hand,
the local date of ``completed_at`` otherwise.  ``base_queryset`` annotates the
same rule in SQL as ``paid_date``, and the filters, the period summary, the
reconciliation rows and the contributions list all key off it — which is what
stops them answering "when was this paid?" differently from the ``Date`` column.
A second annotation, ``paid_at``, keeps the moment the payment settled, for
``?ordering=paid_at`` and for breaking ties within one ledger day.

The reconciliation table
------------------------

``reconciliation``, declared in ``backend/apps/payments/reconciliation.py``
beside the rows it reports, with fixed columns — Period, Payments, Gross, Fees,
Net, Refunded, Net after refunds, Reconciled and Unreconciled — on an upright
page.  ``reconciliation_rows`` builds one row per month, year or provider: the
count, the gross, the fees, the net, what went back, the net after refunds, and
how many of the period's payments a treasurer has matched to a statement.  Two
dating rules make the rows add up against a bank statement: a payment is dated
by ``paid_date``, and a refund by ``refunded_at``, so a refund taken in a later
period belongs to that period.  A period in which money only went back still
gets a row.  The subtitle names the range, provider and grouping.

The contributions list
----------------------

``contributions``, with fixed columns — Name, Email, Payments, Contributed,
Refunded and Net — on an upright page.  ``contribution_rows(year)`` answers one
row per member who gave something in a calendar year, largest net giver first:
the count, what they gave, what went back, and the difference.  It is the list
the year-end acknowledgments go out from.  The year is ``?year=``, the year a
``?period=`` falls in, or the year the report is built in, and the subtitle always
names it.  A payment falls in the year of its ``paid_date``, so a check received in
December and keyed in January counts in the year it arrived, the same year the
period summary puts it in.

The period summary
------------------

``summarize`` groups by month or year and reports the gross, the split between
dues and contributions, the fees, the net, what went back, and a per-provider
breakdown of the gross.  It counts succeeded, partially refunded and refunded
payments: a payment since refunded was revenue that came and went.  It is a
screen, not a report: nothing downloads it.


The email log report
====================

``emails``, for ``system_admin`` alone, since the log lists every address the
installation has written to.  ``EMAIL_LOG_REPORT`` in ``backend/apps/mail/reports.py``
declares it, and its query is the one ``GET /system/emails`` runs:
``EmailLogFilterSet`` from ``apps/mail/filters.py`` over
``EmailLog.objects.select_related("user")``, newest ``sent_at`` first.
``?ordering=sent_at`` turns it round and ``-sent_at`` is the default; any other
ordering is ignored, as the list ignores it.  The columns, in order:

============= =========== ======= ==============================================
Key           Label       Default Contents
============= =========== ======= ==============================================
sent_at       Sent        yes     When the message went, local time,
                                  ``YYYY-MM-DD HH:MM``
purpose       Purpose     yes     The purpose's label from
                                  ``apps/mail/purposes.py``, or the template
                                  name when no label names it
to_email      To          yes     The address written to
user_name     Name        yes     The recipient account's name; blank for an
                                  address with no account behind it
subject       Subject     yes     The subject line
status        Status      yes     ``Sent`` or ``Failed``
error         Error       no      The exception class of a refused send
attachments   Attachments no      The attached filenames, comma-separated
============= =========== ======= ==============================================

The report takes the list's filters — ``purpose``, ``status``, ``from``, ``to``
(both inclusive, on the local date part of ``sent_at``) and ``q`` — plus
``ordering`` and ``?columns=``.  The PDF subtitle names every one given a value,
from ``EXPORT_FILTER_PARAMS`` in ``apps/mail/reports.py``.
``backend/tests/test_email_log_report.py`` covers it.


Testing a report
================

``backend/tests/test_reports.py`` covers the engine on a small report of its
own: cells, periods, the fixed-column refusal, both formats, the download
headers, escaping, pagination, and an empty result set.
``backend/tests/test_report_registry.py`` holds each report's query to its list
— the same parameters give the same rows in the same order — and
``backend/tests/test_report_endpoints.py`` proves the endpoints and the role
matrix for every report.

``backend/tests/test_members_reports.py`` covers the membership report and is
the pattern to copy.  Assertions worth keeping:

* the header equals the column list documented above, verbatim;
* a fully populated member's row, cell by cell;
* the lifetime and "nothing on file" conventions above;
* each filter narrows the download, and ``?ordering=`` reorders it;
* the download is not paginated;
* the PDF is valid (``%PDF-`` … ``%%EOF``), is landscape letter — assert on
  ``/MediaBox [0 0 792 612]`` — and paginates a long report.

PDF page content is compressed, so you cannot grep the bytes for a cell.  Read
it with the ``pdf_text`` fixture, which answers the strings each page draws, or
test what the document *says* at the level above instead: the subtitle is
``filter_summary(spec.query(params).filters)``, and both are ordinary functions.

Related
=======

The endpoints are documented in :doc:`api-reports`; the lists each report
downloads are on the page for each app: :doc:`api-members`, :doc:`api-aircraft`,
:doc:`api-finance` and :doc:`api-system`.
