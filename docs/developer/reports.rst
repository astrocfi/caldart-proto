=======
Reports
=======

CalDART exports data as CSV, for a spreadsheet, and as PDF, for a board pack.
There are ten reports, and every one of them is built by the same code: each
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
   * - ``roles``
     - Roles
     - ``apps/members/roles_report.py``
     - ``user_admin``, ``account_admin``
   * - ``verification``
     - Verification
     - ``apps/aircraft/verification_report.py``
     - ``verifier``, ``dart_leader``, ``user_admin``, ``account_admin``
   * - ``aircraft``
     - Aircraft
     - ``apps/aircraft/reports.py``
     - ``account_admin``
   * - ``payments``
     - Payment list
     - ``apps/payments/reports.py``
     - ``treasurer``, ``account_admin``
   * - ``renewals``
     - Renewals list
     - ``apps/payments/renewals_report.py``
     - ``treasurer``, ``account_admin``
   * - ``reconciliation``
     - Reconciliation table
     - ``apps/payments/reconciliation.py``
     - ``treasurer``, ``account_admin``
   * - ``contributions``
     - Contributions list
     - ``apps/payments/reports.py``
     - ``treasurer``, ``account_admin``
   * - ``donors``
     - Donors
     - ``apps/payments/reports.py``
     - ``treasurer``
   * - ``emails``
     - Email log
     - ``apps/mail/reports.py``
     - ``system_admin``

A ``system_admin`` and a Django superuser read every report.
``apps/reports/registry.py`` gathers the ten specs into ``REPORTS``, keyed by
slug, and ``apps/reports/permissions.py`` decides who may read one with
``can_read_report(user, spec)``, which is ``user_has_any_role`` over the spec's
roles.

One rule holds everywhere:

**A download is the list you are looking at.**  Each report's query is the
filter and ordering code its list runs — the member list's filter set and
ordering, the register's, the payment list's query serializer, the email log's filter set — so the same
query string gives the same rows, in the same order, on the screen and in the
file.  ``?ordering=`` is honored with the list's own rules, and nothing is
paginated.  The roles report and the verification report, which no list backs,
are the exceptions: each reads its own filters and has a fixed order.  The roles
report (:ref:`reports-roles`) lists active accounts only; the verification report
(:ref:`reports-verification`) lists checkable people and active aircraft.


The engine
==========

``ReportSpec(slug, title, filename_stem, columns, roles, query, landscape=True, choosable=True, resolve=keep_params, section=None, empty_section="", section_column="", section_columns=())``
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
   true exactly when it is not ``keep_params``, the identity.  ``section(row)``
   names the section a row is drawn in, ``empty_section`` is the line the PDF
   draws under a section with no rows, ``section_column`` the column a default
   PDF leaves to its section headings, and ``section_columns`` the columns each
   section draws in the PDF (see `Sections`_ below).
``build_report(spec, params, *, fmt, today=None)``
   The whole job.  It resolves the parameters for ``today`` (the local date by
   default), chooses the columns — the ``columns`` parameter, or the defaults,
   through ``chosen_columns`` — runs the query, and turns every cell into text
   with ``cell_text``.  A CSV is the column labels and then one line per row,
   every cell through ``csv_cell``; a PDF is ``build_pdf_table`` with the spec's
   title and orientation, ``filter_summary`` of the applied filters as the
   subtitle, each column's registry width, and the table's sections when it has
   more than one or its one section has a title.  It answers a ``ReportDocument``:
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

Sections
--------

A report can group its rows under titled headings.  A spec whose ``section``
function is set names each row's section, and its query answers
``ReportQuery.sections``, every title in the order they are drawn, so a section no
row falls in still appears.  ``spec.table()`` answers a ``ReportTable`` whose
``rows`` are every row in the order the query answered them and whose ``sections``
are ``ReportSection(title, rows, header=None, widths=None)`` entries grouping the
same rows:

* with no ``section`` function, one section titled ``""`` holds every row, and the
  PDF is drawn exactly as a report without sections;
* with one and a list of titles, one section per listed title, in that order; a
  row whose title is not listed raises ``ValueError`` reading
  ``Row in unlisted section '<title>'``;
* with one and no list, the distinct titles in the order the rows first name them.

The CSV is one flat table, the header and then ``ReportTable.rows``, so a
sectioned report carries its section as a column too, and the spreadsheet loses
nothing.  The PDF draws each section's title in ``SECTION_STYLE`` (the subtitle's
Helvetica at 10pt, bold, in the house blue, 8pt above and 4pt below) and then that
section's own table, its header repeated on every page it runs onto.  A section
with no rows draws its title and then the spec's ``empty_section`` in italics, or
its title alone when ``empty_section`` is blank.  A spec's ``section_column`` names a
column that repeats each row's section title: the CSV prints it among the defaults, and
a PDF of the default columns leaves it out, since its headings say the same.  A title
with less than
``SECTION_KEEP_HEIGHT`` (an inch) left under it on the page starts the next page,
so a title is never left alone above a page break.

A section can draw its own columns in the PDF.  ``section_columns`` is a list of
``SectionColumns(title, keys, labels={})``: of the columns chosen for the report, the
section titled ``title`` draws those whose key is in ``keys``, in the chosen order, and
heads a column with ``labels[key]`` in place of its registry label.  Its
``ReportSection`` then carries that ``header``, the columns' registry ``widths`` (scaled
to fill the page as the table's are), and rows holding those columns' cells alone; a
section the list does not name keeps ``header`` and ``widths`` at ``None`` and is drawn
under every chosen column.  So the **Columns** chooser governs every section at once: a
column it leaves out is left out of each section that lists it, and a section left with
no column draws its title alone.  The CSV is never cut by section: ``ReportTable.header``
and ``ReportTable.rows`` keep every chosen column under its registry label, one header
row for the whole file, so a spreadsheet reads it as one table and a section's row
leaves blank the cells of the columns that section does not draw.

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
``Money(cents, drop_zero_cents=False)``, ``Marked(text, ok)``, and ``cell_text(value, fmt)``
   Money and a marked cell are the two the formats render differently.  A column
   whose value is a ``Money`` prints ``1234.56`` in a CSV, which a spreadsheet
   sums, and ``$1,234.56`` in a PDF, which a person reads; ``drop_zero_cents``
   leaves the cents off a round PDF amount, ``$1,000,000``.  A ``Marked`` cell
   prints its ``text`` alone in a CSV and, in a PDF, its text followed by a
   space and ``PDF_MARK_YES`` (✓) when ``ok`` or ``PDF_MARK_NO`` (✗) when not,
   so a printed table reads without color.  Helvetica has neither glyph, so
   reportlab draws the mark in ZapfDingbats, the standard font it substitutes
   for a character its base font lacks.  ``None`` is a blank cell and anything
   else its ``str``.
``money_label(cents, *, currency=True)``
   Integer cents as the dollars a reader sees: ``12345`` becomes ``$123.45``,
   with commas between thousands.  ``currency=False`` gives ``123.45``.  It is
   text for people either way; an amount bound for Stripe or PayPal is built by
   the provider module that speaks to that API.

**Dates in a report.**  A date column whose value is a ``date`` passes through
``cell_text`` as its ``str``, ISO-8601 (``YYYY-MM-DD``), in both formats, so a
spreadsheet sorts it: the membership, aircraft, and payments reports read that
way.  A column that describes rather than sorts writes its date through
``caldart.dates`` (:doc:`architecture`), the ``MM/DD/YYYY`` a screen shows: the
verification report's *Expires*, *Updated*, and *Verified on* cells, and the
email log's *Sent* cell (``MM/DD/YYYY at h:mm AM``).  The PDF footer stamps the
moment it was generated the same way.  A file's name keeps ``YYYY-MM-DD``.

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

``build_pdf_table(buffer, *, title, subtitle, header, rows, landscape, widths, sections, empty_section)``
   A reportlab table in the CalDART palette, written to any binary stream:
   hairline rules instead of boxes, zebra rows, the header repeated on every
   page, and a footer carrying "CalDART · generated MM/DD/YYYY at h:mm AM <zone>"
   (local time, through ``caldart.dates``) and "Page n of m".  ``landscape``
   defaults to true, which is landscape US letter (792 × 612 points);
   ``landscape=False`` is the same page upright (612 × 792).
   ``widths`` gives the columns relative shares of the printable width —
   ``[3, 1, 1]`` makes the first column three times either of the others — and
   is scaled to fill the page; without it every column is the same width.  One
   width per column, or ``ValueError``.  ``sections``, a list of ``ReportSection``
   entries, replaces ``rows`` with one titled table per section, drawn as
   `Sections`_ describes; a section with its own ``header`` is drawn under it and its
   own ``widths``, held to the same one-width-per-column rule.
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
list takes; see :doc:`api-members`.  Like the list it never holds a donor, and
unlike the list it never holds a deactivated account: ``member_report_query``
keeps ``is_active`` accounts whatever ``include_inactive`` says.

Columns, in order, from ``backend/apps/members/reports.py``.  The eleven marked
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
status               Status                  yes     ``Current``, ``Expired``, or
                                                     ``Friend`` -- the
                                                     ``MembershipState`` choice's
                                                     label, never its stored slug
kind                 Kind                    yes     ``Member`` or ``Friend``: the
                                                     effective kind for today, so a
                                                     member whose ``friend_on`` has come,
                                                     or who has never paid, reads
                                                     ``Friend``
plan                 Plan                    no      Plan behind that status, e.g.
                                                     ``Annual`` or ``Life``
expires_on           Expires                 yes     End of unbroken coverage; **blank for
                                                     a lifetime member**
certificate          Certificate             yes     Pilot certificate, e.g. ``Private``;
                                                     ``ATP`` for an airline transport
                                                     pilot; blank for none
certificate_number   Certificate number      no      Certificate number as entered
instrument           Instrument              no      ``Yes`` or ``No`` for a pilot, by
                                                     whether ``instrument`` is among the
                                                     ratings; blank for a non-pilot
medical_type         Medical                 yes     ``BasicMed``, ``Third class``, …;
                                                     blank for none
medical_expiration   Medical expires         yes     Medical expiry date
aircraft             Aircraft                yes     N-numbers of the planes the member
                                                     commonly flies, spaced
home_airport         Home airport            no      Home airport identifier, e.g. ``PAO``
secondary_airport    Secondary airport       no      Secondary airport identifier; blank
                                                     when none is on file
city                 City                    no      City from the profile
state                State                   no      Two-letter state
county               County                  no      California county from the profile
ham_callsign         Callsign                no      Amateur radio callsign; blank when
                                                     none is on file
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

Three conventions are worth knowing when you read a row:

* A **lifetime** member has no expiry date, so ``expires_on`` is empty while
  ``status`` says ``Current`` and ``plan`` says ``Life``.  That matches the
  API, where ``expires_on`` is ``null``.
* "Nothing on file" choices — a ``none`` certificate or medical — export as an
  empty cell rather than the word "None", which reads as a value in a
  spreadsheet.
* ``status`` always prints the ``MembershipState`` choice's label -- ``Current``,
  ``Expired``, or ``Friend`` -- never the stored slug the
  member list's ``?status=`` filter takes.  ``REPORT_CERTIFICATE_LABELS``
  overrides ``certificate`` the same way for one value: an airline transport
  pilot certificate exports as ``ATP`` rather than spelled out in full.

The PDF subtitle lists the filters that were applied.  Which query parameters
count is ``EXPORT_FILTER_PARAMS`` in ``filters.py``, ``kind`` first and never
``include_inactive``; ``applied_filters(params)`` picks out the ones actually
supplied, ignoring parameters left blank, and prints several counties as a
list: ``county=Alameda,Marin`` reads ``county: Alameda, Marin``.


.. _reports-roles:

The roles report
================

``roles``, for ``user_admin`` and ``account_admin``, titled "CalDART roles
report" and saved as ``caldart-roles-<YYYY-MM-DD>``.  ``ROLES_REPORT`` in
``backend/apps/members/roles_report.py`` declares it; it sits in the members app
because its rows read the membership state, which the accounts app sits below.
It is the sectioned report: one section per staff role, every role but
``member``, in the privilege order of ``ROLE_SLUGS`` (Verifier, DART leader, User
administrator, Treasurer, Account administrator, CalDART management, Website
administrator, System administrator), each drawn even when nobody holds that role, with the line
"Nobody holds this role." under an empty one.  ``ROLE_LABELS`` and
``STAFF_ROLE_LABELS`` in ``apps/accounts/roles.py`` name the roles, and the
section titles are those names.

A row is one role held by one account: ``role_holders`` finds every active
account in a staff role's group, and ``role_rows`` answers a ``RoleRow`` for each
staff role each of them holds, role by role.  A system administrator who is also
an account administrator is listed in both sections, and a deactivated account in
none, whatever roles it still holds.  Within a section the rows are ordered by
last name, first name, then address.

``RolesReportFilterSet``, in the same module, reads four filters, which the PDF
subtitle names when given a value:

``search``
   Every word must match part of the first name, the last name, or the address,
   case-insensitively, the way the users list's search matches.
``role``
   One staff role's slug.  The report then draws that role's section alone.  The
   member role, or any other slug, is refused with a 400 keyed by ``role``.
``kind``
   ``member`` or ``friend``, matched against the effective kind for today, the
   kind the **Kind** column prints.  This is not the users list's ``kind``, which
   matches the stored kind: an account stored as ``member`` with no started term is
   a member there and a friend here.  A donor never holds a role, so ``donor`` is
   refused with a 400 keyed by ``kind``.
``email_bounced``
   ``true`` keeps the accounts whose address has a bounce recorded
   (:ref:`email-bounces`), ``false`` the rest, as the users list's filter of the
   same name does; the users list's export links carry it.

Any other parameter is ignored, as the users list ignores it, apart from
``columns``.  The columns, in order:

============= ============== ======= =============================================
Key           Label          Default Contents
============= ============== ======= =============================================
role          Role           yes     The role's name, which is also its section's
                                     title, so the CSV keeps the grouping
name          Name           yes     Full name, or the address when no name is on
                                     file
email         Email          yes     Login address
phone         Phone          yes     Primary phone from the profile
dart          DART           yes     DART name, blank when unaffiliated
kind          Kind           yes     ``Member`` or ``Friend``: the effective kind
                                     for today, as the membership report reads it
membership    Membership     yes     ``Current``, ``Expired``, or ``Friend``, the
                                     ``MembershipState`` label the membership
                                     report's Status column prints
city          City           no      City from the profile
county        County         no      California county from the profile
home_airport  Home airport   no      Home airport identifier from the profile
============= ============== ======= =============================================

An account with no profile leaves the phone, DART, city, county, and airport
cells blank.  ``backend/tests/test_roles_report.py`` covers the report.


.. _reports-verification:

The verification report
=======================

``verification``, for the verifying roles (``verifier``, ``dart_leader``,
``user_admin``, and ``account_admin``, the tuple ``VERIFY_ROLES`` in
``apps/accounts/roles.py``), titled "CalDART verification report" and saved as
``caldart-verification-<YYYY-MM-DD>``.  ``VERIFICATION_REPORT`` in
``backend/apps/aircraft/verification_report.py`` declares it; it sits in the aircraft
app, which sits above the members app and already decides who the leader's member
check can find, because it lists both people and aircraft.  An item
is verified when its ``<item>_verified_at`` column is set; the columns are in
:doc:`data-model`.

It is sectioned, always in this order and each section drawn even when empty, with the
line "Nothing to show." under an empty one:

``People``
   One row per checkable person with a profile who holds at least one of a photo ID, a
   pilot certificate, and a medical: every active member and friend
   (``checkable_people()`` in ``apps/aircraft/services.py``).  Each of the three has a
   check column; an item the person does not hold (``is_held`` in
   ``apps/members/verification.py``: a photo ID of *Not provided*, a certificate of
   *Not a pilot*, a medical of *None*) has nothing to verify, and its check reads
   ``Not provided``, whatever stamp it carries.  A person who holds none of the three, a donor, a
   deactivated account, and an account with no profile are never listed.  The rows are
   ordered by last name, first name, then address.
``Aircraft insurance``
   One row per aircraft in service (``is_active``) with a policy on file (an
   ``insurance_expiration``), in N-number order.  An aircraft out of service, or with
   no policy, is never listed.

A row's held items decide its state: it is verified when every one of them carries a
stamp, and requires validation otherwise.  Two filters narrow the rows:

``status``
   ``unverified`` (the default, also when blank) keeps the rows that require
   validation, ``verified`` the verified ones, and ``all`` every row.  Any other value is
   refused with a 400,
   ``{"status": ["Select a valid choice. <value> is not one of the available choices."]}``.
``dart``
   A DART's id, or part of its name matched case-insensitively, as the membership
   report reads ``dart``.  It keeps that DART's people and the aircraft that at
   least one pilot on that DART flies, each aircraft once.

The PDF subtitle always names the status in words, since it has a default
(*Showing: Not yet verified*, *Verified*, or *Everything*), and then the DART when
one is given, by name for an id (*DART: Monterey*) and as given for part of a name.
Any other parameter is ignored, apart from ``columns``.  The default list is of rows
that require validation, and the check columns already say which items are verified, so
the three verification stamp columns are there to choose but off by default.  Section
is a default, which keeps the grouping in the flat CSV; the spec names it as its
``section_column``, so a PDF of the default columns leaves it to the section headings
and prints it only when ``columns`` asks for it.  Details is the one default column a
PDF row may wrap in; ``test_report_columns.py`` holds every other default cell of the
seeded data to one line.

The table below is the CSV's: one header row for both sections, in which an aircraft's
row leaves the three check cells blank.  In the PDF each section draws its own columns
(``VERIFICATION_SECTION_COLUMNS``, through the spec's ``section_columns``): *People*
draws every column but Section under the labels below, except ``dart``, headed
``DART``; *Aircraft insurance* draws ``name`` headed ``N-number``, ``dart`` headed
``Owner``, ``details`` headed ``Carrier``, Expires, and Updated, with no check columns.  Section and the three
stamp columns are drawn in either section when they are chosen.  In order:

============= ============== ======= =============================================
Key           Label          Default Contents
============= ============== ======= =============================================
section       Section        yes     The section's title, so the CSV keeps the
                                     grouping
name          Name           yes     The person's full name (or address), or the
                                     aircraft's N-number
dart          DART or owner  yes     The person's DART, or the aircraft's owner
photo_id      Photo ID       yes     ``Verified`` or ``Not verified``;
                                     ``Not provided`` when the person holds no
                                     photo ID, and blank on an aircraft's row
certificate   Certificate    yes     The same, for the pilot certificate
medical       Medical        yes     The same, for the medical
details       Details        yes     What is on file, in check-column order:
                                     ``Passport · Private · 1234567 · Third class``
                                     for a person, the held items only and a blank
                                     certificate number left out; the carrier,
                                     ``Avemco``, for an aircraft
expires       Expires        yes     ``MM/DD/YYYY`` of the medical's or the policy's
                                     expiration; blank without a medical
updated       Updated        yes     ``MM/DD/YYYY`` of the profile's
                                     ``profile_updated_at`` (its ``created_at``
                                     when nobody has edited it) or the aircraft's
                                     ``updated_at``
verified      Verified       no      ``Yes`` when every held item on the row is
                                     verified, else ``No``
verified_by   Verified by    no      The name of whoever made the row's most recent
                                     verification, blank when nothing on the row is
                                     verified or the verifier's account is gone
verified_on   Verified on    no      ``MM/DD/YYYY`` of that most recent
                                     verification, in local time
============= ============== ======= =============================================

``backend/tests/test_verification_report.py`` covers the report.


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
N-numbers) and ``joined_on``.  Four helpers keep the entries short:
``_iso(date)`` formats a date or gives ``""``, ``_value(profile, field)`` reads
a profile field safely, ``_display(profile, field)`` gives the human label
behind a ``choices`` field and blanks the "nothing on file" values, and
``_certificate_display(profile)`` is the same for ``pilot_certificate_type``
alone, with ``REPORT_CERTIFICATE_LABELS`` overriding the choice's own label
for a value that reads better abbreviated in a report cell.

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
category                 Category                no      Airplane, Helicopter, …
airworthiness            Airworthiness           no      Standard, Experimental, …
owner_name               Owner                   yes     Registered owner
owner_type               Owner type              no      Individual, flying club, FBO, …
insurance_carrier        Carrier                 yes     Insurer on the policy
liability_per_occurrence Liability / occurrence  yes     Liability limit per occurrence
liability_per_person     Liability / person      no      Liability limit per person
hull                     Hull                    yes     Hull value insured
insurance_expiration     Expires                 yes     Date the cover runs out; in a
                                                         PDF, a ✓ while it runs and a
                                                         ✗ once it has lapsed
covered                  Covered                 yes     ``Yes``, or ``No`` when the
                                                         coverage policy excludes the
                                                         category or airworthiness
pilots                   Pilots                  no      Display names of the members who
                                                         have attached the airplane, from
                                                         ``apps.aircraft.services``
                                                         ``.pilot_names``
======================== ======================= ======= ==============================

``GET /api/v1/reports/aircraft/columns`` answers the registry as JSON, for the
chooser on the register screen.  The pilot list is off by default because it is
as long as the number of members who fly the plane, which is the one cell no
width can promise to hold.

Each row is a ``RegisterRow``: the aircraft and whether the coverage policy
covers it, judged by one ``CoverageRule`` read before the first row, so the
**Covered** column costs no query per row.  The insured amounts are ``Money``
cells that drop round cents, and the expiry is a ``Marked`` cell:

.. list-table::
   :header-rows: 1
   :widths: 20 40 40

   * -
     - CSV
     - PDF
   * - Money
     - plain decimals, ``1000000.00``
     - currency, ``$1,000,000``
   * - Expires
     - the date, ``2027-04-29``
     - the date and its mark, ``2027-04-29 ✓``

The report takes the register's full filter set: ``search``, ``make``,
``owner_type``, ``insurance`` (``current`` / ``expired`` / ``missing``),
``expiring_within``, ``is_active``, and ``ordering``, plus ``?columns=``.  The
PDF subtitle names every one given a value, from ``EXPORT_FILTER_PARAMS`` in
``apps/aircraft/reports.py``.


The payments reports
====================

Five reports come out of ``backend/apps/payments/``, all of them for the
finance roles, with the tables they download documented in :doc:`api-finance` and,
for the renewals list, :doc:`api-renewals`.

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

The default columns are the date, the name, the email address, the plan, the total,
the fee, the net and the status, which are what the everyday list is read for; the
kind, the split into dues and contribution, the refund, the provider, the method, the
provider's reference, the reconciled date, the receipt number, the received date, the
note and the term's two dates are there to be asked for.

The renewals list
-----------------

``renewals``, declared in ``backend/apps/payments/renewals_report.py``: the Renewals
tab's table of standing authorities, automatic renewals and recurring donations alike.
``mandate_queryset`` narrows by ``status``, ``kind`` (``renewal``, ``both`` or
``contribution``) and ``search`` (every word in the member's email address, first name,
last name or the method label), newest first, and ``GET /admin/renewals`` narrows
through the same function, so the list and the download never disagree.  The default
columns are the tab's own: Member, Email, Kind, Plan, Next charge, Due, Method and
Status, the status in the tab's words (On, Awaiting a method, Paused, Off).  Cadence,
Failed charges and Started are off by default.  The subtitle names the filters given a
value.

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

The donors report
------------------

``donors``, for ``treasurer`` alone — the one report in the list an account
administrator does not read, since a donor's giving is money the treasurer
tracks rather than a member record.  ``donor_rows`` in
``backend/apps/payments/reports.py`` answers one row per account of kind
``donor`` with at least one settled contribution in the range: how many gifts,
the first and the last, what was given, what came back, the net, and the
account's contact details and DART.  ``county``, ``dart``, ``refunded`` and
``active`` are off by default; the everyday view is who gave, how much, and
when.

The filters are ``search`` (a name or address), ``county`` (several at once,
comma-separated, the same as the member list's), ``dart`` (by id or by a
fragment of its name), ``min_cents`` and ``max_cents`` (bounding a donor's
total giving over the range, not any one gift), and ``?period=``, which
resolves to ``from``/``to`` exactly as the payments report's does.
``GET /admin/payments/donors`` answers the same rows on screen, for the
Donors tab of the finance area (:doc:`api-finance`); the CSV and PDF downloads
are the same query.

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
                                  ``MM/DD/YYYY at h:mm AM``
purpose       Purpose     yes     The purpose's label from
                                  ``apps/mail/purposes.py``, or the template
                                  name when no label names it
to_email      To          yes     The address written to
user_name     Name        yes     The recipient's name as it was at send time,
                                  such as a DART contact's own name; blank when
                                  nobody was named
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

``backend/tests/test_report_sections.py`` covers sections, and
``backend/tests/test_report_section_headings.py`` the title kept with its rows.
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
