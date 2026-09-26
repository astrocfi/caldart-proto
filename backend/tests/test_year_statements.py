"""Year-end contribution statements: who is sent one, and the yearly run.

``send_year_statements`` reaches every active account -- member, friend or
donor -- with a settled contribution in a calendar year, once each: a rerun
for a year already sent reaches nobody again.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from io import StringIO
from typing import Any

import pytest
from django.core.mail import EmailMultiAlternatives
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import AccountKind, User
from apps.payments.models import Payment, PaymentStatus, YearStatement
from apps.payments.statements import givers_in_year, send_year_statements
from caldart.org import org_details
from caldart.receipts import CONTRIBUTIONS_NOTICE
from tests.conftest import audit_messages
from tests.factories import PaymentFactory, RefundFactory, UserFactory

pytestmark = pytest.mark.django_db

YEAR = 2026


def _giver(*, kind: str = AccountKind.MEMBER, **overrides: Any) -> User:
    """An active account of ``kind``, otherwise built like any other user."""
    overrides.setdefault("email", "giver@example.test")
    overrides.setdefault("first_name", "Gil")
    overrides.setdefault("last_name", "Giver")
    overrides.setdefault("is_active", True)
    return UserFactory(kind=kind, **overrides)


def _settled_gift(user: User, *, cents: int, year: int = YEAR) -> Payment:
    """A settled contribution-only payment from ``user``, completed in ``year``."""
    payment = PaymentFactory(
        user=user,
        plan=None,
        status=PaymentStatus.SUCCEEDED,
        contribution_cents=cents,
        plan_amount_cents=0,
        amount_cents=cents,
    )
    Payment.objects.filter(pk=payment.pk).update(
        completed_at=datetime(year, 6, 15, 12, 0, tzinfo=UTC)
    )
    payment.refresh_from_db()
    return payment


# --------------------------------------------------------------------------
# Who is a giver
# --------------------------------------------------------------------------
def test_givers_in_year_finds_a_member_a_friend_and_a_donor() -> None:
    """Any kind of active account with a settled gift that year is a giver."""
    member = _giver(kind=AccountKind.MEMBER, email="member@example.test")
    friend = _giver(kind=AccountKind.FRIEND, email="friend@example.test")
    donor = _giver(kind=AccountKind.DONOR, email="donor@example.test")
    for user in (member, friend, donor):
        _settled_gift(user, cents=1_000)

    assert {user.pk for user in givers_in_year(YEAR)} == {member.pk, friend.pk, donor.pk}


def test_givers_in_year_excludes_a_deactivated_account() -> None:
    """A deactivated account is never written to, however much it gave."""
    active = _giver(email="active@example.test")
    inactive = _giver(email="inactive@example.test", is_active=False)
    _settled_gift(active, cents=1_000)
    _settled_gift(inactive, cents=1_000)

    assert [user.pk for user in givers_in_year(YEAR)] == [active.pk]


def test_givers_in_year_excludes_a_gift_from_another_year() -> None:
    """Only a gift settled in the named year counts."""
    giver = _giver()
    _settled_gift(giver, cents=1_000, year=YEAR - 1)

    assert givers_in_year(YEAR) == []


def test_givers_in_year_finds_a_manual_gift_dated_by_its_received_on() -> None:
    """A payment recorded by hand is dated by ``received_on``, never ``completed_at``."""
    giver = _giver()
    PaymentFactory(
        user=giver,
        plan=None,
        provider="manual",
        status=PaymentStatus.SUCCEEDED,
        contribution_cents=1_000,
        plan_amount_cents=0,
        amount_cents=1_000,
        received_on=date(YEAR, 3, 1),
    )

    assert [user.pk for user in givers_in_year(YEAR)] == [giver.pk]


def test_givers_in_year_excludes_a_contribution_with_no_completion_timestamp() -> None:
    """A payment with no ``completed_at`` has no ledger date, so it is not a gift.

    ``apps.payments.reports.base_queryset``'s ``paid_date`` would fall back to
    ``created_at`` here, but
    :func:`apps.payments.receipts.contribution_payments` would not count the
    payment for any year, leaving such a giver a statement of nothing;
    ``givers_in_year`` must agree with the latter.
    """
    giver = _giver()
    PaymentFactory(
        user=giver,
        plan=None,
        status=PaymentStatus.SUCCEEDED,
        contribution_cents=1_000,
        plan_amount_cents=0,
        amount_cents=1_000,
        created_at=datetime(YEAR, 6, 15, 12, 0, tzinfo=UTC),
    )

    assert givers_in_year(YEAR) == []


def test_givers_in_year_excludes_an_unsettled_payment() -> None:
    """A pending contribution is not giving."""
    giver = _giver()
    payment = PaymentFactory(
        user=giver,
        plan=None,
        status=PaymentStatus.PENDING,
        contribution_cents=1_000,
        plan_amount_cents=0,
        amount_cents=1_000,
    )
    Payment.objects.filter(pk=payment.pk).update(
        completed_at=datetime(YEAR, 6, 15, 12, 0, tzinfo=UTC)
    )

    assert givers_in_year(YEAR) == []


# --------------------------------------------------------------------------
# The run
# --------------------------------------------------------------------------
def test_send_year_statements_emails_every_giver_with_the_pdf_attached(
    mailoutbox: list[EmailMultiAlternatives],
) -> None:
    """One email per giver, the statement PDF attached, the year named in the subject."""
    giver = _giver()
    _settled_gift(giver, cents=9_500)

    run = send_year_statements(YEAR)

    assert (run.sent, run.skipped, run.failed) == (1, 0, 0)
    assert len(mailoutbox) == 1
    message = mailoutbox[0]
    assert message.to == [giver.email]
    assert message.subject == f"{org_details().name}: your {YEAR} contribution statement"
    assert len(message.attachments) == 1
    filename, _content, mimetype = message.attachments[0]
    assert filename.endswith(".pdf")
    assert mimetype == "application/pdf"


def test_send_year_statements_names_the_total_given_in_the_body(
    mailoutbox: list[EmailMultiAlternatives],
) -> None:
    """The body carries the year's total and the tax-deductibility notice."""
    giver = _giver()
    _settled_gift(giver, cents=2_000)
    _settled_gift(giver, cents=3_000)

    send_year_statements(YEAR)

    assert "$50.00" in mailoutbox[0].body
    assert CONTRIBUTIONS_NOTICE in mailoutbox[0].body


def test_send_year_statements_omits_the_payments_link_for_a_donor(
    mailoutbox: list[EmailMultiAlternatives],
) -> None:
    """A donor cannot sign in, so the email never links to the portal."""
    donor = _giver(kind=AccountKind.DONOR)
    _settled_gift(donor, cents=1_000)

    send_year_statements(YEAR)

    assert "/portal/payments" not in mailoutbox[0].body


def test_send_year_statements_links_a_member_to_their_payments(
    mailoutbox: list[EmailMultiAlternatives],
) -> None:
    """A member or a friend can sign in, so the email links to Payments."""
    member = _giver(kind=AccountKind.MEMBER)
    _settled_gift(member, cents=1_000)

    send_year_statements(YEAR)

    assert "/portal/payments" in mailoutbox[0].body


def test_send_year_statements_writes_a_year_statement_row() -> None:
    """A sent statement is recorded, unique on the account and the year."""
    giver = _giver()
    _settled_gift(giver, cents=1_000)

    send_year_statements(YEAR)

    assert YearStatement.objects.filter(user=giver, year=YEAR).exists()


def test_send_year_statements_a_rerun_sends_nothing_twice(
    mailoutbox: list[EmailMultiAlternatives],
) -> None:
    """A giver already sent this year's statement is skipped, not emailed again."""
    giver = _giver()
    _settled_gift(giver, cents=1_000)
    send_year_statements(YEAR)

    run = send_year_statements(YEAR)

    assert (run.sent, run.skipped) == (0, 1)
    assert len(mailoutbox) == 1


def test_send_year_statements_does_not_double_send_within_one_run(
    monkeypatch: pytest.MonkeyPatch, mailoutbox: list[EmailMultiAlternatives]
) -> None:
    """Two claims on the same account in one pass raise no ``IntegrityError``.

    A giver appearing twice -- the shape a race between the timer and a
    System-screen click leaves behind when both compute their own snapshot of
    who is already sent before either claims a row -- is emailed once; the
    second claim is skipped rather than aborting the run.
    """
    giver = _giver()
    _settled_gift(giver, cents=1_000)
    monkeypatch.setattr("apps.payments.statements.givers_in_year", lambda year: [giver, giver])

    run = send_year_statements(YEAR)

    assert (run.sent, run.skipped, run.failed) == (1, 1, 0)
    assert len(mailoutbox) == 1


def test_send_year_statements_excludes_a_giver_from_another_year() -> None:
    """A gift in a different year is not this year's business."""
    giver = _giver()
    _settled_gift(giver, cents=1_000, year=YEAR - 1)

    run = send_year_statements(YEAR)

    assert run.sent == 0


def test_send_year_statements_reports_the_net_total_as_the_actions_amount() -> None:
    """A refund comes off the year's total the run's action reports."""
    giver = _giver()
    payment = _settled_gift(giver, cents=10_000)
    RefundFactory(payment=payment, amount_cents=4_000)

    run = send_year_statements(YEAR)

    assert run.actions[0].amount_cents == 6_000


# --------------------------------------------------------------------------
# Dry run
# --------------------------------------------------------------------------
def test_send_year_statements_dry_run_sends_and_writes_nothing(
    mailoutbox: list[EmailMultiAlternatives],
) -> None:
    """A rehearsal reports what a live run would do, and touches nothing."""
    giver = _giver()
    _settled_gift(giver, cents=1_000)

    run = send_year_statements(YEAR, dry_run=True)

    assert run.sent == 1
    assert mailoutbox == []
    assert not YearStatement.objects.filter(user=giver, year=YEAR).exists()


def test_send_year_statements_dry_run_counts_a_missing_address_as_failed() -> None:
    """A rehearsal agrees with the live run it rehearses: no address, no statement."""
    giver = _giver(email="")
    _settled_gift(giver, cents=1_000)

    run = send_year_statements(YEAR, dry_run=True)

    assert (run.sent, run.failed) == (0, 1)


# --------------------------------------------------------------------------
# A refused send
# --------------------------------------------------------------------------
def test_send_year_statements_counts_a_refused_send_as_failed(
    refusing_mail_server: None,
) -> None:
    """The mail server's refusal is counted, and writes no record."""
    giver = _giver()
    _settled_gift(giver, cents=1_000)

    run = send_year_statements(YEAR)

    assert (run.sent, run.failed) == (0, 1)
    assert not YearStatement.objects.filter(user=giver, year=YEAR).exists()


def test_send_year_statements_retries_a_failed_send_on_the_next_run(
    refusing_mail_server: None,
    monkeypatch: pytest.MonkeyPatch,
    mailoutbox: list[EmailMultiAlternatives],
) -> None:
    """Nothing is recorded for a failed send, so the next run tries again and succeeds."""
    giver = _giver()
    _settled_gift(giver, cents=1_000)
    send_year_statements(YEAR)

    monkeypatch.undo()  # The mail server is back up for the next run.
    run = send_year_statements(YEAR)

    assert run.sent == 1
    assert len(mailoutbox) == 1


# --------------------------------------------------------------------------
# The audit record
# --------------------------------------------------------------------------
def test_send_year_statements_writes_one_audit_record(audit_log: pytest.LogCaptureFixture) -> None:
    """One ``statements.run`` line carries the year, the mode, and the counts."""
    giver = _giver()
    _settled_gift(giver, cents=1_000)

    send_year_statements(YEAR)

    lines = audit_messages(audit_log)
    matching = [line for line in lines if "action=statements.run" in line]
    assert len(matching) == 1
    assert f"year={YEAR}" in matching[0]


# --------------------------------------------------------------------------
# The command
# --------------------------------------------------------------------------
def test_the_command_sends_and_reports(mailoutbox: list[EmailMultiAlternatives]) -> None:
    """The command defaults ``--year`` to the year before ``--today``."""
    giver = _giver()
    _settled_gift(giver, cents=1_000, year=2025)
    out = StringIO()

    call_command("send_year_statements", "--today=2026-01-15", stdout=out)

    assert "year             2025" in out.getvalue()
    assert "sent 1, skipped 0" in out.getvalue()
    assert len(mailoutbox) == 1


def test_the_command_accepts_an_explicit_year(mailoutbox: list[EmailMultiAlternatives]) -> None:
    """``--year`` overrides the default of the year before ``--today``."""
    giver = _giver()
    _settled_gift(giver, cents=1_000, year=2024)
    out = StringIO()

    call_command("send_year_statements", "--today=2026-01-15", "--year=2024", stdout=out)

    assert "year             2024" in out.getvalue()
    assert len(mailoutbox) == 1


def test_the_command_rehearses_with_dry_run(mailoutbox: list[EmailMultiAlternatives]) -> None:
    """``--dry-run`` says what it would send and sends nothing."""
    giver = _giver()
    _settled_gift(giver, cents=1_000, year=2025)
    out = StringIO()

    call_command("send_year_statements", "--today=2026-01-15", "--dry-run", stdout=out)

    assert "would send 1, skipped 0" in out.getvalue()
    assert mailoutbox == []


def test_the_command_refuses_a_bad_date() -> None:
    """``--today`` must be ``YYYY-MM-DD``."""
    with pytest.raises(CommandError, match="--today must be YYYY-MM-DD, not 'soon'"):
        call_command("send_year_statements", "--today=soon")


@pytest.mark.parametrize(
    "year", [0, -1, 10_000, 40_000], ids=["zero", "negative", "5-digit", "far"]
)
def test_the_command_refuses_a_year_out_of_range(year: int) -> None:
    """A ``--year`` Django cannot build a date from is a ``CommandError``."""
    with pytest.raises(CommandError, match=f"--year must be between 1900 and 9000, not {year}"):
        call_command("send_year_statements", f"--year={year}", "--dry-run")


def test_the_command_fails_when_a_send_is_refused(refusing_mail_server: None) -> None:
    """A refused send makes the command exit non-zero, so the timer's unit fails."""
    giver = _giver()
    _settled_gift(giver, cents=1_000, year=2025)

    with pytest.raises(CommandError, match="1 statement email could not be sent"):
        call_command("send_year_statements", "--today=2026-01-15", stdout=StringIO())


# --------------------------------------------------------------------------
# The endpoint
# --------------------------------------------------------------------------
def test_system_admin_runs_the_statements_endpoint(
    system_admin_client: APIClient, mailoutbox: list[EmailMultiAlternatives]
) -> None:
    """``POST /system/statements/run`` answers the counts, keyed by year."""
    giver = _giver()
    _settled_gift(giver, cents=1_000)

    response = system_admin_client.post(
        "/api/v1/system/statements/run", {"dry_run": False, "year": YEAR}, format="json"
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["year"], body["sent"], body["skipped"], body["failed"]) == (YEAR, 1, 0, 0)
    assert len(mailoutbox) == 1


def test_the_statements_endpoint_defaults_the_year_to_the_year_before_today(
    system_admin_client: APIClient, mailoutbox: list[EmailMultiAlternatives]
) -> None:
    """Without ``year``, the run covers the calendar year before today."""
    last_year = timezone.localdate().year - 1
    giver = _giver()
    _settled_gift(giver, cents=1_000, year=last_year)

    response = system_admin_client.post("/api/v1/system/statements/run", {}, format="json")

    assert response.json()["year"] == last_year


def test_the_statements_endpoint_refuses_a_year_below_the_range(
    system_admin_client: APIClient,
) -> None:
    """A year of 0 is a 400, not the 500 ``date(0, 1, 1)`` would raise."""
    response = system_admin_client.post(
        "/api/v1/system/statements/run", {"dry_run": True, "year": 0}, format="json"
    )

    assert response.status_code == 400
    assert response.json() == {"year": ["Ensure this value is greater than or equal to 1900."]}


def test_the_statements_endpoint_refuses_a_year_above_the_range(
    system_admin_client: APIClient,
) -> None:
    """A five-digit year is a 400, not the 500 ``date(40000, 1, 1)`` would raise."""
    response = system_admin_client.post(
        "/api/v1/system/statements/run", {"dry_run": True, "year": 40_000}, format="json"
    )

    assert response.status_code == 400
    assert response.json() == {"year": ["Ensure this value is less than or equal to 9000."]}


def test_a_treasurer_may_not_run_the_statements_endpoint(treasurer_client: APIClient) -> None:
    """Running a job by hand from the System screen is the system administrator's own."""
    response = treasurer_client.post("/api/v1/system/statements/run", {}, format="json")
    assert response.status_code == 403


def test_an_anonymous_caller_may_not_run_the_statements_endpoint(api_client: APIClient) -> None:
    """Signed out, the endpoint is a 401."""
    assert api_client.post("/api/v1/system/statements/run", {}, format="json").status_code == 401
