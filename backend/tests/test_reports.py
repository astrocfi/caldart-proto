"""The shared report engine: columns, cells, periods, and the CSV and PDF it builds."""

from __future__ import annotations

import io
from collections.abc import Iterator, Sequence
from datetime import date
from typing import Any, cast

import pytest
from rest_framework.exceptions import ValidationError

from caldart.reports import (
    FIXED_COLUMNS_MESSAGE,
    PDF_MEDIA_TYPE,
    PERIODS,
    Money,
    Params,
    ReportColumn,
    ReportFormat,
    ReportQuery,
    ReportSpec,
    build_pdf_table,
    build_report,
    cell_text,
    chosen_columns,
    column_payload,
    csv_rows,
    filter_summary,
    keep_params,
    money_label,
    ordering_terms,
    period_bounds,
    report_response,
    resolve_period,
    select_columns,
)
from tests.conftest import PdfText, pdf_page_count, read_csv

HEADER: list[str] = ["name", "email", "n_number", "expires_on"]
ROWS: list[list[str | None]] = [
    ["Marta Reyes", "marta@example.org", "N172SP", "2027-01-31"],
    ["Owen Delgado", "owen@example.org", "N9021K", None],
    ['Quote "Q" & Co', "q@example.org", "N1", "2026-12-01"],
]

#: The subtitle line under the title, with the middle dot the summary joins on.
SUBTITLE = "status: current \u00b7 dart: Palo Alto"


def pdf_table(**kwargs: Any) -> bytes:
    """The PDF ``build_pdf_table`` draws from ``kwargs``, as bytes."""
    buffer = io.BytesIO()
    build_pdf_table(buffer, **kwargs)
    return buffer.getvalue()


def test_csv_rows_writes_the_header_the_rows_and_blank_cells() -> None:
    """The CSV is well formed: the header, then each row, with ``None`` as a blank."""
    parsed = "".join(csv_rows(HEADER, ROWS)).splitlines()
    assert parsed == [
        "name,email,n_number,expires_on",
        "Marta Reyes,marta@example.org,N172SP,2027-01-31",
        "Owen Delgado,owen@example.org,N9021K,",
        '"Quote ""Q"" & Co",q@example.org,N1,2026-12-01',
    ]


def test_csv_rows_is_lazy() -> None:
    """``csv_rows`` pulls from its source only as each row is consumed."""
    consumed: list[str | None] = []

    def source() -> Iterator[list[str | None]]:
        for row in ROWS:
            consumed.append(row[0])
            yield row

    stream = csv_rows(HEADER, source())
    next(stream)  # header only
    assert consumed == []
    next(stream)
    assert consumed == ["Marta Reyes"]


def test_build_pdf_table_writes_a_valid_one_page_pdf() -> None:
    """``build_pdf_table`` writes one well-formed page for a short table."""
    body = pdf_table(title="Membership report", subtitle=SUBTITLE, header=HEADER, rows=ROWS)
    assert body.startswith(b"%PDF-")
    assert body.rstrip().endswith(b"%%EOF")
    assert pdf_page_count(body) == 1


def test_pdf_draws_the_title_the_subtitle_and_every_cell(pdf_text: PdfText) -> None:
    """The page shows the title, the subtitle, the header and every non-empty cell."""
    body = pdf_table(title="Membership report", subtitle=SUBTITLE, header=HEADER, rows=ROWS)
    page = pdf_text(body)[0]
    assert page[:2] == ["Membership report", SUBTITLE]
    assert page[2:6] == HEADER
    # The ``None`` cell of the second row draws nothing at all.
    assert page[6:17] == [
        "Marta Reyes",
        "marta@example.org",
        "N172SP",
        "2027-01-31",
        "Owen Delgado",
        "owen@example.org",
        "N9021K",
        'Quote "Q" & Co',
        "q@example.org",
        "N1",
        "2026-12-01",
    ]


@pytest.mark.parametrize(
    ("landscape", "expected_pages"), [(True, 4), (False, 3)], ids=["landscape", "portrait"]
)
def test_pdf_paginates_100_rows_with_a_repeated_header(
    landscape: bool, expected_pages: int, pdf_text: PdfText
) -> None:
    """A 100-row table spans several pages, each continuation repeating the header."""
    rows = [[f"Member {i}", f"m{i}@example.org", f"N{i:04d}A", "2027-01-31"] for i in range(100)]
    body = pdf_table(title="Membership report", header=HEADER, rows=rows, landscape=landscape)
    pages = pdf_text(body)
    assert len(pages) == expected_pages
    # The title opens the first page; every later page opens with the header.
    assert pages[0][:5] == ["Membership report", *HEADER]
    assert [page[:4] for page in pages[1:]] == [HEADER] * (expected_pages - 1)
    assert "Member 0" in pages[0]
    assert "Member 99" in pages[-1]


def test_pdf_handles_an_empty_result_set(pdf_text: PdfText) -> None:
    """A table with no rows renders one page carrying the title and header alone."""
    pages = pdf_text(pdf_table(title="Membership report", header=HEADER, rows=[]))
    assert len(pages) == 1
    assert pages[0][:5] == ["Membership report", *HEADER]


def test_pdf_escapes_markup_in_cells(pdf_text: PdfText) -> None:
    """A cell containing HTML-like markup is drawn as the literal text it holds."""
    body = pdf_table(title="Report", header=["value"], rows=[["<b>not bold</b> & co"]])
    page = pdf_text(body)[0]
    # The paragraph splits at each angle bracket, so read the cell as one string.
    assert "".join(page[2:-2]) == "<b>not bold</b> & co"


def test_filter_summary_joins_the_active_filters_and_skips_the_empty_ones() -> None:
    """Active filters join with a middle dot; a filter with an empty value is dropped."""
    assert filter_summary({"status": "current", "dart": "", "expiring_within": 30}) == (
        "status: current \u00b7 expiring within: 30"
    )


def test_filter_summary_says_so_when_no_filter_is_active() -> None:
    """An empty filter mapping summarizes as "No filters applied"."""
    assert filter_summary({}) == "No filters applied"


#: A three-column registry over a ``(name, email, note)`` row, two columns on by default.
COLUMNS: tuple[ReportColumn[tuple[str, str, str]], ...] = (
    ReportColumn("name", "Name", True, lambda row: row[0]),
    ReportColumn("email", "Email", True, lambda row: row[1]),
    ReportColumn("note", "Note", False, lambda row: row[2]),
)


def test_select_columns_answers_the_defaults_when_nothing_is_requested() -> None:
    """No requested list means the columns whose ``default`` is true, in order."""
    assert [column.key for column in select_columns(COLUMNS, None)] == ["name", "email"]


def test_select_columns_answers_the_defaults_for_an_empty_request() -> None:
    """An empty requested list is read as "no choice made", not as "no columns"."""
    assert [column.key for column in select_columns(COLUMNS, [])] == ["name", "email"]


def test_select_columns_follows_the_requested_order() -> None:
    """The chosen columns come back in the order asked for, defaults ignored."""
    chosen = select_columns(COLUMNS, ["note", "name"])
    assert [column.key for column in chosen] == ["note", "name"]


def test_select_columns_rejects_the_first_unknown_key() -> None:
    """An unrecognized key raises ``ValueError`` naming that key and nothing else."""
    with pytest.raises(ValueError, match="Unknown column: shoe_size"):
        select_columns(COLUMNS, ["name", "shoe_size", "hat_size"])


def test_select_columns_rejects_a_key_asked_for_twice() -> None:
    """A repeated key raises ``ValueError`` naming it rather than repeating the column."""
    with pytest.raises(ValueError, match="Repeated column: name"):
        select_columns(COLUMNS, ["name", "email", "name"])


def test_a_column_defaults_to_an_even_share_of_the_width() -> None:
    """A column declared without a width asks for the same room as any other."""
    assert [column.width for column in COLUMNS] == [1.0, 1.0, 1.0]


def test_a_column_carries_the_relative_width_it_was_given() -> None:
    """``width`` is the share of the printable width the PDF gives the column."""
    wide: ReportColumn[tuple[str, str, str]] = ReportColumn(
        "note", "Note", True, lambda row: row[2], width=3.5
    )
    assert wide.width == 3.5


def test_column_payload_describes_every_column_for_the_chooser() -> None:
    """``column_payload`` answers one ``key``/``label``/``default`` entry per column."""
    assert column_payload(COLUMNS) == [
        {"key": "name", "label": "Name", "default": True},
        {"key": "email", "label": "Email", "default": True},
        {"key": "note", "label": "Note", "default": False},
    ]


def test_chosen_columns_reads_a_comma_separated_query_parameter() -> None:
    """``chosen_columns`` turns ``?columns=note,name`` into those columns, in order."""
    chosen = chosen_columns(COLUMNS, "note,name")
    assert [column.key for column in chosen] == ["note", "name"]


def test_chosen_columns_answers_the_defaults_for_an_absent_parameter() -> None:
    """An empty ``?columns=`` means the caller chose nothing, so the defaults apply."""
    assert [column.key for column in chosen_columns(COLUMNS, "")] == ["name", "email"]


def test_chosen_columns_refuses_an_unknown_key_keyed_by_columns() -> None:
    """A key no column carries is a 400 keyed ``columns`` naming that key."""
    with pytest.raises(ValidationError) as caught:
        chosen_columns(COLUMNS, "name,shoe_size")
    detail = cast("dict[str, list[str]]", caught.value.detail)
    assert detail["columns"] == ["Unknown column: shoe_size"]


def test_chosen_columns_refuses_a_repeated_key_keyed_by_columns() -> None:
    """A key asked for twice is a 400 keyed ``columns`` naming that key."""
    with pytest.raises(ValidationError) as caught:
        chosen_columns(COLUMNS, "name,name")
    detail = cast("dict[str, list[str]]", caught.value.detail)
    assert detail["columns"] == ["Repeated column: name"]


def test_report_column_reads_a_row_through_its_value_function() -> None:
    """A column's ``value`` turns one row into the cell the exports write."""
    column = select_columns(COLUMNS, ["email"])[0]
    assert column.label == "Email"
    assert column.value(("Marta Reyes", "marta@example.org", "check 1180")) == "marta@example.org"


@pytest.mark.parametrize(
    ("cents", "expected"),
    [(0, "$0.00"), (5, "$0.05"), (12345, "$123.45"), (100000000, "$1,000,000.00")],
    ids=["zero", "cents-only", "dollars-and-cents", "millions"],
)
def test_money_label_formats_integer_cents_for_a_reader(cents: int, expected: str) -> None:
    """Integer cents read as dollars with a thousands separator and two decimals."""
    assert money_label(cents) == expected


@pytest.mark.parametrize(
    ("cents", "expected"),
    [(0, "0.00"), (5, "0.05"), (12345, "123.45"), (100000000, "1000000.00")],
    ids=["zero", "cents-only", "dollars-and-cents", "millions"],
)
def test_money_label_without_currency_gives_a_number_a_spreadsheet_sums(
    cents: int, expected: str
) -> None:
    """``currency=False`` drops the sign and the separators, for a CSV cell."""
    assert money_label(cents, currency=False) == expected


@pytest.mark.parametrize(
    ("landscape", "expected_box"),
    [(True, b"/MediaBox [ 0 0 792 612 ]"), (False, b"/MediaBox [ 0 0 612 792 ]")],
    ids=["landscape", "portrait"],
)
def test_pdf_page_size_follows_the_landscape_flag(landscape: bool, expected_box: bytes) -> None:
    """``landscape`` chooses between US letter on its side and US letter upright."""
    assert expected_box in pdf_table(title="Report", header=HEADER, rows=ROWS, landscape=landscape)


def test_pdf_relative_widths_decide_how_much_room_each_column_gets(pdf_text: PdfText) -> None:
    """A column given the larger share of the width fits text that otherwise wraps."""
    sentence = "Palo Alto Airport disaster airlift standby"
    wide_first = pdf_table(
        title="Report", header=["note", "code"], rows=[[sentence, "A"]], widths=[9, 1]
    )
    narrow_first = pdf_table(
        title="Report", header=["note", "code"], rows=[[sentence, "A"]], widths=[1, 9]
    )
    assert sentence in pdf_text(wide_first)[0]
    assert sentence not in pdf_text(narrow_first)[0]


def test_pdf_rejects_widths_that_do_not_match_the_header() -> None:
    """One relative width per column, or ``ValueError`` before anything is drawn."""
    with pytest.raises(ValueError, match="4 columns but 2 widths"):
        pdf_table(title="Report", header=HEADER, rows=ROWS, widths=[1, 1])


# --------------------------------------------------------------------------
# Cells
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("value", "fmt", "expected"),
    [
        (Money(123456), "csv", "1234.56"),
        (Money(123456), "pdf", "$1,234.56"),
        (Money(100000000, drop_zero_cents=True), "csv", "1000000.00"),
        (Money(100000000, drop_zero_cents=True), "pdf", "$1,000,000"),
        (Money(100000050, drop_zero_cents=True), "pdf", "$1,000,000.50"),
        ("Marta Reyes", "pdf", "Marta Reyes"),
        (7, "csv", "7"),
        (None, "csv", ""),
    ],
    ids=[
        "money-csv",
        "money-pdf",
        "whole-dollars-csv",
        "whole-dollars-pdf",
        "odd-cents-keep-them",
        "text",
        "number",
        "nothing",
    ],
)
def test_cell_text_renders_a_value_for_the_format(
    value: object, fmt: ReportFormat, expected: str
) -> None:
    """Money is a plain number in a CSV and dollars in a PDF; anything else is text."""
    assert cell_text(value, fmt) == expected


# --------------------------------------------------------------------------
# Periods
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("token", "today", "expected"),
    [
        ("this_month", date(2026, 9, 25), (date(2026, 9, 1), date(2026, 9, 30))),
        ("last_month", date(2026, 9, 25), (date(2026, 8, 1), date(2026, 8, 31))),
        ("last_month", date(2026, 1, 15), (date(2025, 12, 1), date(2025, 12, 31))),
        ("this_month", date(2028, 2, 10), (date(2028, 2, 1), date(2028, 2, 29))),
        ("this_year", date(2026, 9, 25), (date(2026, 1, 1), date(2026, 12, 31))),
        ("last_year", date(2026, 1, 1), (date(2025, 1, 1), date(2025, 12, 31))),
    ],
    ids=[
        "this-month",
        "last-month",
        "last-month-across-a-year",
        "this-month-in-a-leap-february",
        "this-year",
        "last-year-on-new-years-day",
    ],
)
def test_period_bounds_answers_the_first_and_last_day(
    token: str, today: date, expected: tuple[date, date]
) -> None:
    """Each period token names a whole month or year, counted from ``today``."""
    assert period_bounds(token, today) == expected


def test_the_periods_are_the_four_the_reports_offer() -> None:
    """A subscription or a download picks one of exactly these four periods."""
    assert PERIODS == ("this_month", "last_month", "this_year", "last_year")


def test_period_bounds_refuses_an_unknown_token_keyed_by_period() -> None:
    """A token that is not a period is a 400 keyed ``period`` naming it."""
    with pytest.raises(ValidationError) as caught:
        period_bounds("next_week", date(2026, 9, 25))
    detail = cast("dict[str, list[str]]", caught.value.detail)
    assert detail["period"] == ["Unknown period 'next_week'."]


def expand_to_range(start: date, end: date) -> dict[str, str]:
    """The ``from`` and ``to`` params a period stands for in a dated report."""
    return {"from": start.isoformat(), "to": end.isoformat()}


def test_resolve_period_replaces_the_period_with_its_concrete_params() -> None:
    """``period`` is dropped and the params it stands for take its place."""
    resolved = resolve_period(
        {"period": "last_month", "provider": "stripe"}, date(2026, 9, 25), expand_to_range
    )
    assert resolved == {"provider": "stripe", "from": "2026-08-01", "to": "2026-08-31"}


def test_resolve_period_overrides_the_params_the_period_stands_for() -> None:
    """A period wins over an explicit range, so a subscription always means its period."""
    resolved = resolve_period(
        {"period": "this_year", "from": "2020-01-01"}, date(2026, 9, 25), expand_to_range
    )
    assert resolved == {"from": "2026-01-01", "to": "2026-12-31"}


@pytest.mark.parametrize("params", [{"from": "2026-02-01"}, {"from": "2026-02-01", "period": ""}])
def test_resolve_period_without_a_period_keeps_the_other_params(params: dict[str, str]) -> None:
    """No period, or a blank one, leaves the params as they are, less the blank."""
    assert resolve_period(params, date(2026, 9, 25), expand_to_range) == {"from": "2026-02-01"}


def test_keep_params_is_the_identity() -> None:
    """A report without dates resolves its params to themselves."""
    params = {"period": "this_year", "dart": "3"}
    assert keep_params(params, date(2026, 9, 25)) is params


def test_ordering_terms_splits_a_comma_separated_parameter() -> None:
    """Blank terms and the spaces around each term are dropped."""
    assert ordering_terms(" -name, email ,,") == ["-name", "email"]


def test_ordering_terms_of_an_empty_parameter_is_empty() -> None:
    """An absent ``ordering`` asks for no terms, so the report's default applies."""
    assert ordering_terms("") == []


# --------------------------------------------------------------------------
# build_report
# --------------------------------------------------------------------------
#: One row of the toy report: a name and an amount in cents.
type ToyRow = tuple[str, int]

TOY_COLUMNS: tuple[ReportColumn[ToyRow], ...] = (
    ReportColumn("name", "Name", True, lambda row: row[0], width=2.0),
    ReportColumn("amount", "Amount", True, lambda row: Money(row[1])),
    ReportColumn("note", "Note", False, lambda row: "=1+1"),
)

TOY_ROWS: tuple[ToyRow, ...] = (("Ada", 123456), ("Bo", 500))

#: The day every toy document is dated.
DAY = date(2026, 9, 25)


def toy_query(params: Params) -> ReportQuery[ToyRow]:
    """The toy rows, narrowed to one ``name`` when the params name one.

    ``fail`` in the params is refused the way a report refuses a bad filter.
    """
    if params.get("fail"):
        raise ValidationError({"fail": ["Not a filter."]})
    name = params.get("name", "")
    rows = [row for row in TOY_ROWS if name in {"", row[0]}]
    return ReportQuery(rows=rows, filters={"name": name})


TOY: ReportSpec[ToyRow] = ReportSpec(
    slug="toy",
    title="Toy report",
    filename_stem="caldart-toy",
    columns=TOY_COLUMNS,
    roles=("treasurer",),
    query=toy_query,
)

#: The same report with fixed columns on an upright page.
FIXED: ReportSpec[ToyRow] = ReportSpec(
    slug="fixed",
    title="Fixed report",
    filename_stem="caldart-fixed",
    columns=TOY_COLUMNS,
    roles=("treasurer",),
    query=toy_query,
    landscape=False,
    choosable=False,
)


def test_a_csv_document_is_named_for_the_day_and_typed_as_csv() -> None:
    """The file is ``<stem>-<YYYY-MM-DD>.csv`` and its media type is ``text/csv``."""
    document = build_report(TOY, {}, fmt="csv", today=DAY)
    assert (document.filename, document.media_type) == ("caldart-toy-2026-09-25.csv", "text/csv")


def test_a_csv_document_holds_the_default_columns_with_money_as_numbers() -> None:
    """The CSV is the default labels, then one line per row, money a plain number."""
    document = build_report(TOY, {}, fmt="csv", today=DAY)
    assert document.content == b"Name,Amount\r\nAda,1234.56\r\nBo,5.00\r\n"


def test_a_csv_cell_that_looks_like_a_formula_is_defused() -> None:
    """Every cell goes through the formula policy, chosen columns included."""
    document = build_report(TOY, {"columns": "note"}, fmt="csv", today=DAY)
    assert document.content == b"Note\r\n'=1+1\r\n'=1+1\r\n"


def test_the_columns_param_chooses_the_columns_and_their_order() -> None:
    """``columns`` picks which columns appear and where, as it does on every export."""
    document = build_report(TOY, {"columns": "amount,name"}, fmt="csv", today=DAY)
    assert document.content.splitlines()[0] == b"Amount,Name"


def test_the_filters_narrow_the_rows() -> None:
    """The params reach the report's query, which decides the rows."""
    document = build_report(TOY, {"name": "Bo"}, fmt="csv", today=DAY)
    assert document.content == b"Name,Amount\r\nBo,5.00\r\n"


def test_a_filter_the_query_refuses_is_a_validation_error() -> None:
    """The query's refusal reaches the caller, keyed by the param at fault."""
    with pytest.raises(ValidationError) as caught:
        build_report(TOY, {"fail": "yes"}, fmt="csv", today=DAY)
    detail = cast("dict[str, list[str]]", caught.value.detail)
    assert detail["fail"] == ["Not a filter."]


def test_an_unknown_column_is_refused_keyed_by_columns() -> None:
    """A key the report does not carry is refused before the query runs."""
    with pytest.raises(ValidationError) as caught:
        build_report(TOY, {"columns": "name,bogus"}, fmt="csv", today=DAY)
    detail = cast("dict[str, list[str]]", caught.value.detail)
    assert detail["columns"] == ["Unknown column: bogus"]


def test_a_fixed_report_refuses_a_column_choice() -> None:
    """A report whose columns are fixed says so rather than ignoring ``columns``."""
    with pytest.raises(ValidationError) as caught:
        build_report(FIXED, {"columns": "name"}, fmt="csv", today=DAY)
    detail = cast("dict[str, list[str]]", caught.value.detail)
    assert detail["columns"] == [FIXED_COLUMNS_MESSAGE]


def test_the_fixed_columns_message_is_the_documented_sentence() -> None:
    """The refusal reads as the API reference quotes it."""
    assert FIXED_COLUMNS_MESSAGE == "This report's columns are fixed."


def test_a_fixed_report_carries_every_column() -> None:
    """A fixed report prints every column it declares, in order."""
    document = build_report(FIXED, {"columns": ""}, fmt="csv", today=DAY)
    assert document.content.splitlines()[0] == b"Name,Amount,Note"


def test_the_params_are_resolved_before_the_query_sees_them() -> None:
    """``resolve`` runs first, with the day the report is built on."""
    seen: list[dict[str, str]] = []

    def recording_query(params: Params) -> ReportQuery[ToyRow]:
        seen.append(dict(params))
        return ReportQuery(rows=[], filters={})

    spec: ReportSpec[ToyRow] = ReportSpec(
        slug="dated",
        title="Dated report",
        filename_stem="caldart-dated",
        columns=TOY_COLUMNS,
        roles=("treasurer",),
        query=recording_query,
        resolve=lambda params, today: {"day": today.isoformat()},
    )
    build_report(spec, {"period": "this_year"}, fmt="csv", today=DAY)
    assert seen == [{"day": "2026-09-25"}]


def test_a_report_offers_periods_only_when_it_resolves_them() -> None:
    """``periods`` is true exactly when the spec's ``resolve`` is not the identity."""
    dated: ReportSpec[ToyRow] = ReportSpec(
        slug="dated",
        title="Dated report",
        filename_stem="caldart-dated",
        columns=TOY_COLUMNS,
        roles=("treasurer",),
        query=toy_query,
        resolve=lambda params, today: resolve_period(params, today, expand_to_range),
    )
    assert (TOY.periods, dated.periods) == (False, True)


def test_a_spec_describes_its_columns_for_the_chooser() -> None:
    """``column_choices`` is the registry as the columns endpoint answers it."""
    assert TOY.column_choices() == column_payload(TOY_COLUMNS)


def test_a_pdf_document_is_named_for_the_day_and_typed_as_pdf() -> None:
    """The file is ``<stem>-<YYYY-MM-DD>.pdf`` and its media type is PDF."""
    document = build_report(TOY, {}, fmt="pdf", today=DAY)
    assert (document.filename, document.media_type) == (
        "caldart-toy-2026-09-25.pdf",
        PDF_MEDIA_TYPE,
    )


def test_a_pdf_document_draws_the_title_the_filters_and_money_as_dollars(
    pdf_text: PdfText,
) -> None:
    """The PDF carries the spec's title, the applied filters and dollar amounts."""
    document = build_report(TOY, {"name": "Ada"}, fmt="pdf", today=DAY)
    assert pdf_text(document.content)[0][:6] == [
        "Toy report",
        "name: Ada",
        "Name",
        "Amount",
        "Ada",
        "$1,234.56",
    ]


@pytest.mark.parametrize(
    ("spec", "expected_box"),
    [(TOY, b"/MediaBox [ 0 0 792 612 ]"), (FIXED, b"/MediaBox [ 0 0 612 792 ]")],
    ids=["landscape", "portrait"],
)
def test_a_pdf_document_follows_the_spec_orientation(
    spec: ReportSpec[ToyRow], expected_box: bytes
) -> None:
    """``landscape`` on the spec decides the page, as it does on ``build_pdf_table``."""
    assert expected_box in build_report(spec, {}, fmt="pdf", today=DAY).content


def test_a_pdf_document_gives_each_column_its_registry_width(pdf_text: PdfText) -> None:
    """A wide column keeps a long cell on one line that an even share would wrap."""
    long_name = "Palo Alto Airport disaster airlift standby crew"

    def one_long_row(params: Params) -> ReportQuery[ToyRow]:
        return ReportQuery(rows=[(long_name, 1)], filters={})

    filler: list[ReportColumn[ToyRow]] = [
        ReportColumn(f"c{i}", f"C{i}", True, lambda row: "x") for i in range(11)
    ]
    columns: Sequence[ReportColumn[ToyRow]] = [
        ReportColumn("name", "Name", True, lambda row: row[0], width=12.0),
        *filler,
    ]
    spec: ReportSpec[ToyRow] = ReportSpec(
        slug="wide",
        title="Wide",
        filename_stem="caldart-wide",
        columns=columns,
        roles=("treasurer",),
        query=one_long_row,
    )
    assert long_name in pdf_text(build_report(spec, {}, fmt="pdf", today=DAY).content)[0]


@pytest.mark.parametrize(
    ("fmt", "content_type"),
    [("csv", "text/csv; charset=utf-8"), ("pdf", "application/pdf")],
    ids=["csv", "pdf"],
)
def test_report_response_is_a_named_download(fmt: ReportFormat, content_type: str) -> None:
    """The response carries the document, its type and its filename as an attachment."""
    document = build_report(TOY, {}, fmt=fmt, today=DAY)
    response = report_response(document)
    assert (response["Content-Type"], response["Content-Disposition"]) == (
        content_type,
        f'attachment; filename="caldart-toy-2026-09-25.{fmt}"',
    )


def test_report_response_carries_the_document_bytes() -> None:
    """The body is the document's content, byte for byte."""
    document = build_report(TOY, {}, fmt="csv", today=DAY)
    assert read_csv(report_response(document)) == [
        ["Name", "Amount"],
        ["Ada", "1234.56"],
        ["Bo", "5.00"],
    ]


def test_build_report_defaults_to_the_local_date(today: date) -> None:
    """Without ``today`` the document is dated the day it is built."""
    document = build_report(TOY, {}, fmt="csv")
    assert document.filename == f"caldart-toy-{today.isoformat()}.csv"


def test_rows_are_read_once_and_lazily(pdf_text: PdfText) -> None:
    """The query's rows may be a one-shot iterator, as a queryset iterator is."""

    def once(params: Params) -> ReportQuery[ToyRow]:
        def rows() -> Iterator[ToyRow]:
            yield from TOY_ROWS

        return ReportQuery(rows=rows(), filters={})

    spec: ReportSpec[ToyRow] = ReportSpec(
        slug="once",
        title="Once",
        filename_stem="caldart-once",
        columns=TOY_COLUMNS,
        roles=("treasurer",),
        query=once,
    )
    assert pdf_page_count(build_report(spec, {}, fmt="pdf", today=DAY).content) == 1
