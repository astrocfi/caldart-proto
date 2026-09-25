"""The email log as a report: ``/api/v1/reports/emails/export.csv`` and ``.pdf``.

The report reads the same filter set as ``GET /system/emails``, so these tests
prove each filter narrows the file the way it narrows the list, that the date range
bounds the local day a message went, that the rows come newest first unless asked
otherwise, that each column prints what a reader wants rather than a slug, and that
only a system administrator may download it.
"""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import SYSTEM_ADMIN
from apps.mail.models import EmailStatus
from apps.mail.reports import EMAIL_LOG_REPORT
from apps.reports.registry import REPORTS
from tests.conftest import PdfText, read_csv, role_matrix
from tests.factories import EmailLogFactory, UserFactory

pytestmark = pytest.mark.django_db

CSV_URL = "/api/v1/reports/emails/export.csv"
PDF_URL = "/api/v1/reports/emails/export.pdf"
COLUMNS_URL = "/api/v1/reports/emails/columns"
LIST_URL = "/api/v1/system/emails"

#: The installation's own timezone, in which ``Sent`` and the date range are read.
PACIFIC = ZoneInfo("America/Los_Angeles")

#: The labels of the columns the report carries when the caller chooses none.
DEFAULT_LABELS = ["Sent", "Purpose", "To", "Name", "Subject", "Status"]


def pacific(year: int, month: int, day: int, hour: int = 9, minute: int = 0) -> dt.datetime:
    """An aware instant at ``hour:minute`` on the given Pacific day."""
    return dt.datetime(year, month, day, hour, minute, tzinfo=PACIFIC)


@pytest.fixture
def system_admin_client(api_client: APIClient, system_admin: User) -> APIClient:
    """A DRF client signed in as the system administrator."""
    api_client.force_login(system_admin)
    return api_client


def column(rows: list[list[str]], label: str) -> list[str]:
    """The cells under ``label`` in a CSV read by ``read_csv``, header excluded."""
    index = rows[0].index(label)
    return [row[index] for row in rows[1:]]


# --------------------------------------------------------------------------
# The spec and who may read it
# --------------------------------------------------------------------------
def test_the_email_log_is_registered_under_emails() -> None:
    """``REPORTS["emails"]`` is the email log's own spec."""
    assert REPORTS["emails"] is EMAIL_LOG_REPORT


def test_the_email_log_is_titled_for_its_pdf() -> None:
    """The PDF heads the report ``CalDART email log``."""
    assert EMAIL_LOG_REPORT.title == "CalDART email log"


@pytest.mark.parametrize("url", [CSV_URL, PDF_URL, COLUMNS_URL])
@pytest.mark.parametrize(("role", "allowed"), role_matrix(SYSTEM_ADMIN))
def test_only_a_system_administrator_reads_the_email_log(
    api_client: APIClient, all_role_users: dict[str, User], url: str, role: str, allowed: bool
) -> None:
    """Every other role is refused the columns and both downloads with a 403."""
    api_client.force_login(all_role_users[role])
    assert api_client.get(url).status_code == (200 if allowed else 403)


def test_the_email_log_download_needs_a_session(api_client: APIClient) -> None:
    """An anonymous caller is a 401."""
    assert api_client.get(CSV_URL).status_code == 401


def test_the_columns_are_choosable_with_error_and_attachments_off(
    system_admin_client: APIClient,
) -> None:
    """Eight columns, the error and the attachments off by default."""
    assert system_admin_client.get(COLUMNS_URL).json() == [
        {"key": "sent_at", "label": "Sent", "default": True},
        {"key": "purpose", "label": "Purpose", "default": True},
        {"key": "to_email", "label": "To", "default": True},
        {"key": "user_name", "label": "Name", "default": True},
        {"key": "subject", "label": "Subject", "default": True},
        {"key": "status", "label": "Status", "default": True},
        {"key": "error", "label": "Error", "default": False},
        {"key": "attachments", "label": "Attachments", "default": False},
    ]


# --------------------------------------------------------------------------
# The cells
# --------------------------------------------------------------------------
def test_the_csv_header_is_the_default_labels(system_admin_client: APIClient) -> None:
    """With no ``columns`` the file carries the six default columns, in order."""
    assert read_csv(system_admin_client.get(CSV_URL))[0] == DEFAULT_LABELS


def test_a_row_reads_as_a_reader_would_say_it(system_admin_client: APIClient) -> None:
    """Local time to the minute, the purpose label, the address, the name, the subject."""
    member = UserFactory(email="marta@example.org", first_name="Marta", last_name="Reyes")
    EmailLogFactory(
        user=member,
        purpose="receipt",
        subject="CalDART: your receipt for $95.00",
        sent_at=pacific(2026, 1, 8, 9, 5),
    )

    rows = read_csv(system_admin_client.get(CSV_URL))

    assert rows[1] == [
        "2026-01-08 09:05",
        "Receipt",
        "marta@example.org",
        "Marta Reyes",
        "CalDART: your receipt for $95.00",
        "Sent",
    ]


def test_a_purpose_with_no_label_prints_its_slug(system_admin_client: APIClient) -> None:
    """A template the labels do not name still reads, by its own name."""
    EmailLogFactory(purpose="board_minutes")

    assert column(read_csv(system_admin_client.get(CSV_URL)), "Purpose") == ["board_minutes"]


def test_a_message_to_nobody_in_particular_has_a_blank_name(
    system_admin_client: APIClient,
) -> None:
    """A send to an address with no account behind it leaves ``Name`` empty."""
    EmailLogFactory(user=None, to_email="info@example.org")

    assert column(read_csv(system_admin_client.get(CSV_URL)), "Name") == [""]


def test_a_refused_send_reads_failed_with_its_error(system_admin_client: APIClient) -> None:
    """``Status`` is the label and ``Error`` the exception class the server raised."""
    EmailLogFactory(status=EmailStatus.FAILED, error="SMTPRecipientsRefused")

    rows = read_csv(system_admin_client.get(CSV_URL, {"columns": "status,error"}))

    assert rows[1] == ["Failed", "SMTPRecipientsRefused"]


def test_the_attachments_column_lists_the_filenames(system_admin_client: APIClient) -> None:
    """``attachments`` is the comma-separated filenames that rode along."""
    EmailLogFactory(purpose="receipt", attachments="receipt-2026-0041.pdf")

    rows = read_csv(system_admin_client.get(CSV_URL, {"columns": "attachments"}))

    assert rows == [["Attachments"], ["receipt-2026-0041.pdf"]]


def test_the_pdf_is_titled_and_names_its_filters(
    system_admin_client: APIClient, pdf_text: PdfText
) -> None:
    """The PDF carries the title and a subtitle naming the applied filters."""
    EmailLogFactory(purpose="refund", sent_at=pacific(2026, 3, 2))

    response = system_admin_client.get(PDF_URL, {"purpose": "refund", "from": "2026-03-01"})
    text = " ".join(pdf_text(response.content)[0])

    assert response.status_code == 200
    assert "CalDART email log" in text
    assert "purpose: refund" in text
    assert "from: 2026-03-01" in text


def test_the_file_is_named_for_the_email_log(
    system_admin_client: APIClient, today: dt.date
) -> None:
    """The download is ``caldart-emails-<YYYY-MM-DD>.csv``, dated the local day."""
    response = system_admin_client.get(CSV_URL)

    assert response["Content-Disposition"] == (
        f'attachment; filename="caldart-emails-{today.isoformat()}.csv"'
    )


# --------------------------------------------------------------------------
# The filters and the order
# --------------------------------------------------------------------------
def test_the_rows_come_newest_first(system_admin_client: APIClient) -> None:
    """With no ordering the latest send leads."""
    EmailLogFactory(subject="older", sent_at=pacific(2026, 1, 1))
    EmailLogFactory(subject="newer", sent_at=pacific(2026, 1, 2))

    assert column(read_csv(system_admin_client.get(CSV_URL)), "Subject") == ["newer", "older"]


def test_the_rows_can_come_oldest_first(system_admin_client: APIClient) -> None:
    """``ordering=sent_at`` turns the file round."""
    EmailLogFactory(subject="older", sent_at=pacific(2026, 1, 1))
    EmailLogFactory(subject="newer", sent_at=pacific(2026, 1, 2))

    rows = read_csv(system_admin_client.get(CSV_URL, {"ordering": "sent_at"}))

    assert column(rows, "Subject") == ["older", "newer"]


def test_an_unknown_ordering_is_ignored(system_admin_client: APIClient) -> None:
    """An ordering the list does not offer leaves the newest first, as the list does."""
    EmailLogFactory(subject="older", sent_at=pacific(2026, 1, 1))
    EmailLogFactory(subject="newer", sent_at=pacific(2026, 1, 2))

    rows = read_csv(system_admin_client.get(CSV_URL, {"ordering": "subject"}))

    assert column(rows, "Subject") == ["newer", "older"]


@pytest.mark.parametrize(
    ("ordering", "expected"),
    [("-sent_at", ["second", "first"]), ("sent_at", ["first", "second"])],
    ids=["newest-first", "oldest-first"],
)
def test_the_list_breaks_a_tie_in_sent_at_as_the_download_does(
    system_admin_client: APIClient, ordering: str, expected: list[str]
) -> None:
    """Sends in the same instant follow their ``id`` in the direction of ``sent_at``.

    The list and the file then agree row for row, and a page boundary between two
    same-instant sends neither repeats nor skips one.
    """
    instant = pacific(2026, 1, 1)
    EmailLogFactory(subject="first", sent_at=instant)
    EmailLogFactory(subject="second", sent_at=instant)

    body = system_admin_client.get(LIST_URL, {"ordering": ordering}).json()
    rows = read_csv(system_admin_client.get(CSV_URL, {"ordering": ordering}))

    assert [row["subject"] for row in body["results"]] == expected
    assert column(rows, "Subject") == expected


def test_the_purpose_filter_keeps_one_kind(system_admin_client: APIClient) -> None:
    """``purpose`` keeps only the messages sent from that template."""
    EmailLogFactory(purpose="receipt", subject="a receipt")
    EmailLogFactory(purpose="refund", subject="a refund")

    rows = read_csv(system_admin_client.get(CSV_URL, {"purpose": "refund"}))

    assert column(rows, "Subject") == ["a refund"]


def test_the_status_filter_keeps_the_failures(system_admin_client: APIClient) -> None:
    """``status=failed`` keeps only the refused sends."""
    EmailLogFactory(subject="went")
    EmailLogFactory(subject="refused", status=EmailStatus.FAILED, error="SMTPDataError")

    rows = read_csv(system_admin_client.get(CSV_URL, {"status": "failed"}))

    assert column(rows, "Subject") == ["refused"]


def test_an_unknown_status_is_a_400_keyed_status(system_admin_client: APIClient) -> None:
    """A status the log does not use is refused as the list refuses it."""
    response = system_admin_client.get(CSV_URL, {"status": "bounced"})

    assert response.status_code == 400
    assert list(response.json()) == ["status"]


def test_the_date_range_bounds_the_local_day_sent(system_admin_client: APIClient) -> None:
    """``from`` and ``to`` are inclusive and read the Pacific day, not the UTC one."""
    EmailLogFactory(subject="before", sent_at=pacific(2026, 2, 28, 23, 30))
    EmailLogFactory(subject="first day", sent_at=pacific(2026, 3, 1, 0, 10))
    EmailLogFactory(subject="last day late", sent_at=pacific(2026, 3, 31, 23, 50))
    EmailLogFactory(subject="after", sent_at=pacific(2026, 4, 1, 0, 5))

    rows = read_csv(system_admin_client.get(CSV_URL, {"from": "2026-03-01", "to": "2026-03-31"}))

    assert column(rows, "Subject") == ["last day late", "first day"]


def test_an_unparseable_date_is_a_400_keyed_by_it(system_admin_client: APIClient) -> None:
    """A ``from`` that is not a date is refused under ``from``."""
    response = system_admin_client.get(CSV_URL, {"from": "March"})

    assert response.status_code == 400
    assert list(response.json()) == ["from"]


def test_the_search_matches_the_address_or_the_name(system_admin_client: APIClient) -> None:
    """``q`` finds an address and an account's last name, case-insensitively."""
    reyes = UserFactory(email="m@example.org", first_name="Marta", last_name="Reyes")
    EmailLogFactory(user=reyes, subject="by name")
    EmailLogFactory(user=None, to_email="REYES.family@example.org", subject="by address")
    EmailLogFactory(user=None, to_email="someone@example.org", subject="neither")

    rows = read_csv(system_admin_client.get(CSV_URL, {"q": "reyes"}))

    assert sorted(column(rows, "Subject")) == ["by address", "by name"]


def test_a_download_carries_every_row_not_one_page(system_admin_client: APIClient) -> None:
    """``page`` and ``page_size`` do not narrow a file: all thirty rows are in it."""
    EmailLogFactory.create_batch(30)

    rows = read_csv(system_admin_client.get(CSV_URL, {"page": "2", "page_size": "10"}))

    assert len(rows) == 31
