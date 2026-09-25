"""The finance area's single-record endpoints.

The payment detail and its reconciliation write, one member's ledger, and the
year-end contributions list with its two exports.
"""

from __future__ import annotations

import datetime as dt

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import ACCOUNT_ADMIN, SYSTEM_ADMIN, TREASURER
from apps.members.models import MembershipPlan
from apps.payments.dates import CLOCK_GRACE_DAYS
from apps.payments.models import Payment, PaymentProvider, PaymentStatus, RefundReason
from tests.conftest import PdfText, read_csv, role_matrix
from tests.factories import (
    MembershipFactory,
    PaymentFactory,
    RefundFactory,
    RenewalAttemptFactory,
    RenewalMandateFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db

CONTRIBUTIONS = "/api/v1/admin/payments/contributions"
CONTRIBUTIONS_CSV = "/api/v1/reports/contributions/export.csv"
CONTRIBUTIONS_PDF = "/api/v1/reports/contributions/export.pdf"


def detail_url(payment: Payment) -> str:
    """The finance detail endpoint of one payment."""
    return f"/api/v1/admin/payments/{payment.pk}"


def ledger_url(member: User) -> str:
    """The finance ledger endpoint of one member."""
    return f"/api/v1/admin/payments/ledger/{member.pk}"


def at_noon(year: int, month: int, day: int) -> dt.datetime:
    """Local noon on a date, which is unambiguous in every US time zone."""
    return timezone.make_aware(dt.datetime(year, month, day, 12, 0))


@pytest.fixture
def paid(member: User, annual_plan: MembershipPlan) -> Payment:
    """One succeeded $145 Stripe payment: $45 of dues and a $100 contribution."""
    return PaymentFactory(
        user=member,
        plan=annual_plan,
        amount_cents=14_500,
        plan_amount_cents=4_500,
        contribution_cents=10_000,
        fee_cents=450,
        net_cents=14_050,
        provider=PaymentProvider.STRIPE,
        provider_ref="pi_finance_1",
        status=PaymentStatus.SUCCEEDED,
        completed_at=at_noon(2026, 2, 3),
        created_at=at_noon(2026, 2, 3),
    )


# --------------------------------------------------------------------------
# The payment detail
# --------------------------------------------------------------------------
def test_the_detail_carries_the_fee_and_the_net(treasurer_client: APIClient, paid: Payment) -> None:
    """The finance row says what the provider kept and what reached the bank."""
    body = treasurer_client.get(detail_url(paid)).json()
    assert body["fee_cents"] == 450
    assert body["net_cents"] == 14_050


def test_the_detail_carries_the_receipt_number(treasurer_client: APIClient, paid: Payment) -> None:
    """The receipt number is the payment's id padded to six digits."""
    body = treasurer_client.get(detail_url(paid)).json()
    assert body["receipt_number"] == f"CALDART-{paid.pk:06d}"


def test_the_detail_lists_the_refunds_beneath_the_payment(
    treasurer_client: APIClient, paid: Payment
) -> None:
    """A treasurer reading a payment sees what has already gone back."""
    RefundFactory(payment=paid, amount_cents=2_500, reason=RefundReason.DUPLICATE)
    body = treasurer_client.get(detail_url(paid)).json()
    assert [refund["amount_cents"] for refund in body["refunds"]] == [2_500]


def test_the_detail_totals_what_has_gone_back(treasurer_client: APIClient, paid: Payment) -> None:
    """``refunded_cents`` is the sum of the succeeded refunds."""
    RefundFactory(payment=paid, amount_cents=2_500)
    RefundFactory(payment=paid, amount_cents=1_000)
    assert treasurer_client.get(detail_url(paid)).json()["refunded_cents"] == 3_500


def test_the_detail_names_the_term_the_payment_bought(
    treasurer_client: APIClient, paid: Payment, member: User, annual_plan: MembershipPlan
) -> None:
    """The row links the money to the coverage it paid for."""
    term = MembershipFactory(user=member, plan=annual_plan, payment=paid)
    body = treasurer_client.get(detail_url(paid)).json()
    assert body["membership"]["id"] == term.pk


def test_the_detail_carries_no_term_for_a_pure_contribution(
    treasurer_client: APIClient, member: User
) -> None:
    """A donation buys no coverage, so there is nothing to link."""
    payment = PaymentFactory(
        user=member, plan=None, plan_amount_cents=0, contribution_cents=5_000, amount_cents=5_000
    )
    assert treasurer_client.get(detail_url(payment)).json()["membership"] is None


def test_the_detail_names_the_automatic_charge_behind_it(
    treasurer_client: APIClient, paid: Payment, member: User, annual_plan: MembershipPlan
) -> None:
    """A renewal charge is marked as one, so nobody mistakes it for a checkout."""
    term = MembershipFactory(user=member, plan=annual_plan)
    mandate = RenewalMandateFactory(user=member, plan=annual_plan)
    attempt = RenewalAttemptFactory(mandate=mandate, membership=term, payment=paid)
    body = treasurer_client.get(detail_url(paid)).json()
    assert body["renewal_attempt"]["id"] == attempt.pk


def test_the_detail_carries_no_attempt_for_a_payment_a_person_made(
    treasurer_client: APIClient, paid: Payment
) -> None:
    """A checkout is not an automatic charge."""
    assert treasurer_client.get(detail_url(paid)).json()["renewal_attempt"] is None


def test_the_detail_never_carries_the_provider_payload(
    treasurer_client: APIClient, paid: Payment
) -> None:
    """``raw`` is the provider's own payload and stays out of the API."""
    assert "raw" not in treasurer_client.get(detail_url(paid)).json()


def test_an_unknown_payment_is_a_404(treasurer_client: APIClient) -> None:
    """An id nobody holds is a 404."""
    assert treasurer_client.get("/api/v1/admin/payments/9999").status_code == 404


# --------------------------------------------------------------------------
# Reconciling and noting a payment
# --------------------------------------------------------------------------
def test_marking_a_payment_reconciled_records_the_day(
    treasurer_client: APIClient, paid: Payment
) -> None:
    """The day a treasurer matched it to a statement is kept on the payment."""
    body = treasurer_client.patch(
        detail_url(paid), {"reconciled_on": "2026-03-01"}, format="json"
    ).json()
    assert body["reconciled_on"] == "2026-03-01"


def test_marking_a_payment_reconciled_records_who_did_it(
    treasurer_client: APIClient, paid: Payment, treasurer: User
) -> None:
    """A match is somebody's judgment, so the row says whose."""
    body = treasurer_client.patch(
        detail_url(paid), {"reconciled_on": "2026-03-01"}, format="json"
    ).json()
    assert body["reconciled_by"] == treasurer.display_name


def test_un_matching_a_payment_forgets_who_matched_it(
    treasurer_client: APIClient, paid: Payment
) -> None:
    """Clearing the date clears the name with it: nobody stands behind a match undone."""
    treasurer_client.patch(detail_url(paid), {"reconciled_on": "2026-03-01"}, format="json")
    body = treasurer_client.patch(detail_url(paid), {"reconciled_on": None}, format="json").json()
    assert body["reconciled_by"] is None


def test_a_match_cannot_be_dated_in_the_future(treasurer_client: APIClient, paid: Payment) -> None:
    """A statement that has not been issued cannot have been matched against."""
    too_late = timezone.localdate() + dt.timedelta(days=CLOCK_GRACE_DAYS + 1)
    response = treasurer_client.patch(
        detail_url(paid), {"reconciled_on": too_late.isoformat()}, format="json"
    )
    assert response.status_code == 400
    assert response.json() == {
        "reconciled_on": ["A payment cannot have been matched in the future."]
    }


def test_a_match_dated_by_a_clock_a_day_ahead_is_kept(
    treasurer_client: APIClient, paid: Payment
) -> None:
    """A browser already on tomorrow can still match a payment to today's statement."""
    tomorrow = timezone.localdate() + dt.timedelta(days=CLOCK_GRACE_DAYS)
    response = treasurer_client.patch(
        detail_url(paid), {"reconciled_on": tomorrow.isoformat()}, format="json"
    )
    assert response.status_code == 200
    assert response.json()["reconciled_on"] == tomorrow.isoformat()


def test_a_note_can_be_written_without_reconciling(
    treasurer_client: APIClient, paid: Payment
) -> None:
    """The note stands on its own: a treasurer may explain a payment they cannot match."""
    body = treasurer_client.patch(
        detail_url(paid), {"note": "Chased with the bank"}, format="json"
    ).json()
    assert body["note"] == "Chased with the bank"


def test_reconciling_writes_an_audit_record(
    treasurer_client: APIClient,
    paid: Payment,
    treasurer: User,
    member: User,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Matching a payment to a statement is recorded against the payer."""
    with caplog.at_level("INFO", logger="caldart.audit"):
        treasurer_client.patch(detail_url(paid), {"reconciled_on": "2026-03-01"}, format="json")
    assert f"action=payment.reconcile actor={treasurer.pk} target={member.pk}" in caplog.text


def test_writing_a_note_writes_its_own_audit_record(
    treasurer_client: APIClient, paid: Payment, treasurer: User, caplog: pytest.LogCaptureFixture
) -> None:
    """A note is a separate act from a match, and is recorded separately."""
    with caplog.at_level("INFO", logger="caldart.audit"):
        treasurer_client.patch(detail_url(paid), {"note": "Split check"}, format="json")
    assert "action=payment.note" in caplog.text


def test_a_patch_that_changes_nothing_records_nothing(
    treasurer_client: APIClient, paid: Payment, caplog: pytest.LogCaptureFixture
) -> None:
    """Resending the same note is not a second act."""
    treasurer_client.patch(detail_url(paid), {"note": "Split check"}, format="json")
    caplog.clear()
    with caplog.at_level("INFO", logger="caldart.audit"):
        treasurer_client.patch(detail_url(paid), {"note": "Split check"}, format="json")
    assert "action=payment.note" not in caplog.text


def test_a_patch_naming_neither_field_is_refused(
    treasurer_client: APIClient, paid: Payment
) -> None:
    """An empty body would change nothing, so it is a 400 rather than a no-op."""
    response = treasurer_client.patch(detail_url(paid), {}, format="json")
    assert response.json() == {"non_field_errors": ["Send reconciled_on, note, or both."]}


# --------------------------------------------------------------------------
# The member ledger
# --------------------------------------------------------------------------
def test_the_ledger_names_the_member_it_is_about(
    treasurer_client: APIClient, paid: Payment, member: User
) -> None:
    """The screen's heading comes from the ledger, not a second call."""
    body = treasurer_client.get(ledger_url(member)).json()
    assert body["user"]["email"] == member.email


def test_the_ledger_totals_the_whole_history(
    treasurer_client: APIClient, paid: Payment, member: User
) -> None:
    """The totals cover every payment that arrived, not just this year's."""
    body = treasurer_client.get(ledger_url(member)).json()
    assert body["totals"]["paid_cents"] == 14_500
    assert body["totals"]["contribution_cents"] == 10_000
    assert body["totals"]["fee_cents"] == 450


def test_the_ledger_leaves_a_failed_attempt_out_of_the_totals(
    treasurer_client: APIClient, paid: Payment, member: User, annual_plan: MembershipPlan
) -> None:
    """Money that never arrived was never paid."""
    PaymentFactory(user=member, plan=annual_plan, status=PaymentStatus.FAILED)
    assert treasurer_client.get(ledger_url(member)).json()["totals"]["paid_cents"] == 14_500


def test_the_ledger_lists_every_payment_newest_first(
    treasurer_client: APIClient, paid: Payment, member: User, annual_plan: MembershipPlan
) -> None:
    """A failed attempt is still part of the history, even out of the totals."""
    PaymentFactory(user=member, plan=annual_plan, status=PaymentStatus.FAILED)
    body = treasurer_client.get(ledger_url(member)).json()
    assert len(body["payments"]) == 2


def test_the_ledger_carries_another_members_payments_for_nobody(
    treasurer_client: APIClient, paid: Payment, user_factory: type[UserFactory]
) -> None:
    """A ledger is one member's money and nobody else's."""
    other = user_factory(email="wilma@example.test")
    assert treasurer_client.get(ledger_url(other)).json()["payments"] == []


def test_the_ledger_names_the_years_a_statement_can_be_downloaded_for(
    treasurer_client: APIClient, paid: Payment, member: User
) -> None:
    """A year qualifies when the member gave something in it."""
    assert treasurer_client.get(ledger_url(member)).json()["statement_years"] == [2026]


def test_a_year_with_dues_but_no_giving_earns_no_statement(
    treasurer_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A membership payment is not a deductible gift, so it buys no statement."""
    PaymentFactory(
        user=member,
        plan=annual_plan,
        contribution_cents=0,
        status=PaymentStatus.SUCCEEDED,
        completed_at=at_noon(2025, 5, 4),
        created_at=at_noon(2025, 5, 4),
    )
    assert treasurer_client.get(ledger_url(member)).json()["statement_years"] == []


def test_the_ledger_carries_the_members_renewal_mandate(
    treasurer_client: APIClient, paid: Payment, member: User, annual_plan: MembershipPlan
) -> None:
    """The finance screen can cancel a mandate from the ledger it is reading."""
    RenewalMandateFactory(user=member, plan=annual_plan)
    body = treasurer_client.get(ledger_url(member)).json()
    assert body["mandate"]["status"] == "active"


def test_the_ledger_carries_no_mandate_for_a_member_without_one(
    treasurer_client: APIClient, paid: Payment, member: User
) -> None:
    """Most members renew by hand, and their ledger says so with a null."""
    assert treasurer_client.get(ledger_url(member)).json()["mandate"] is None


def test_an_unknown_member_has_no_ledger(treasurer_client: APIClient) -> None:
    """A member id nobody holds is a 404."""
    assert treasurer_client.get("/api/v1/admin/payments/ledger/9999").status_code == 404


# --------------------------------------------------------------------------
# GET /admin/payments/contributions
# --------------------------------------------------------------------------
@pytest.fixture
def giving(member: User, user_factory: type[UserFactory], annual_plan: MembershipPlan) -> User:
    """Two members' contributions in 2026, and one in 2025 that must not count."""
    other = user_factory(email="wilma@example.test", first_name="Wilma", last_name="Voss")
    PaymentFactory(
        user=member,
        plan=annual_plan,
        amount_cents=14_500,
        plan_amount_cents=4_500,
        contribution_cents=10_000,
        status=PaymentStatus.SUCCEEDED,
        provider_ref="gave-1",
        completed_at=at_noon(2026, 2, 3),
        created_at=at_noon(2026, 2, 3),
    )
    PaymentFactory(
        user=other,
        plan=None,
        amount_cents=2_000,
        plan_amount_cents=0,
        contribution_cents=2_000,
        status=PaymentStatus.SUCCEEDED,
        provider_ref="gave-2",
        completed_at=at_noon(2026, 6, 1),
        created_at=at_noon(2026, 6, 1),
    )
    PaymentFactory(
        user=other,
        plan=None,
        amount_cents=9_000,
        plan_amount_cents=0,
        contribution_cents=9_000,
        status=PaymentStatus.SUCCEEDED,
        provider_ref="gave-3",
        completed_at=at_noon(2025, 6, 1),
        created_at=at_noon(2025, 6, 1),
    )
    return other


def test_the_contributions_list_holds_one_row_per_member(
    treasurer_client: APIClient, giving: User
) -> None:
    """The year-end acknowledgment list is by member, not by payment."""
    rows = treasurer_client.get(CONTRIBUTIONS, {"year": 2026}).json()
    assert len(rows) == 2


def test_the_contributions_list_is_largest_giver_first(
    treasurer_client: APIClient, giving: User, member: User
) -> None:
    """The order is the one the acknowledgment letters go out in."""
    rows = treasurer_client.get(CONTRIBUTIONS, {"year": 2026}).json()
    assert rows[0]["user_id"] == member.pk


def test_the_contributions_list_leaves_out_another_years_giving(
    treasurer_client: APIClient, giving: User
) -> None:
    """A statement covers one calendar year, so the list does too."""
    rows = treasurer_client.get(CONTRIBUTIONS, {"year": 2026}).json()
    assert next(row for row in rows if row["user_id"] == giving.pk)["contribution_cents"] == 2_000


def test_the_contributions_list_counts_the_payments(
    treasurer_client: APIClient, giving: User, member: User
) -> None:
    """A member who gave twice is one row with a count of two."""
    PaymentFactory(
        user=member,
        plan=None,
        amount_cents=1_000,
        plan_amount_cents=0,
        contribution_cents=1_000,
        status=PaymentStatus.SUCCEEDED,
        provider_ref="gave-4",
        completed_at=at_noon(2026, 8, 8),
        created_at=at_noon(2026, 8, 8),
    )
    rows = treasurer_client.get(CONTRIBUTIONS, {"year": 2026}).json()
    assert next(row for row in rows if row["user_id"] == member.pk)["count"] == 2


def test_a_refund_comes_off_the_net_contribution(
    treasurer_client: APIClient, giving: User, member: User
) -> None:
    """The figure the acknowledgment quotes is what the member actually gave."""
    payment = Payment.objects.get(provider_ref="gave-1")
    RefundFactory(payment=payment, amount_cents=2_500)
    rows = treasurer_client.get(CONTRIBUTIONS, {"year": 2026}).json()
    row = next(row for row in rows if row["user_id"] == member.pk)
    assert row["refunded_cents"] == 2_500
    assert row["net_contribution_cents"] == 7_500


def test_a_year_nobody_gave_in_is_an_empty_list(treasurer_client: APIClient, giving: User) -> None:
    """Nothing to acknowledge reads as nothing, not as an error."""
    assert treasurer_client.get(CONTRIBUTIONS, {"year": 2024}).json() == []


def test_a_year_before_the_calendar_began_is_refused(treasurer_client: APIClient) -> None:
    """A four-digit year the report will not look at is a 400."""
    assert treasurer_client.get(CONTRIBUTIONS, {"year": 1066}).status_code == 400


def test_the_contributions_csv_is_named_for_the_day_it_was_run(
    treasurer_client: APIClient, giving: User, today: dt.date
) -> None:
    """The file is dated the day it was built, like every report."""
    response = treasurer_client.get(CONTRIBUTIONS_CSV, {"year": 2026})
    assert (
        response["Content-Disposition"]
        == f'attachment; filename="caldart-contributions-{today.isoformat()}.csv"'
    )


def test_the_contributions_csv_carries_the_same_rows(
    treasurer_client: APIClient, giving: User
) -> None:
    """One header line and one line per contributing member."""
    rows = read_csv(treasurer_client.get(CONTRIBUTIONS_CSV, {"year": 2026}))
    assert rows[0] == ["Name", "Email", "Payments", "Contributed", "Refunded", "Net"]
    assert len(rows) == 3


def test_the_contributions_pdf_is_named_for_the_day_it_was_run(
    treasurer_client: APIClient, giving: User, today: dt.date
) -> None:
    """The PDF downloads under the same name as the CSV."""
    response = treasurer_client.get(CONTRIBUTIONS_PDF, {"year": 2026})
    assert (
        response["Content-Disposition"]
        == f'attachment; filename="caldart-contributions-{today.isoformat()}.pdf"'
    )


def test_the_contributions_pdf_names_the_year_under_its_title(
    treasurer_client: APIClient, giving: User, pdf_text: PdfText
) -> None:
    """A printed list says on its face which year it acknowledges."""
    page = pdf_text(treasurer_client.get(CONTRIBUTIONS_PDF, {"year": 2026}).content)[0]
    assert page[:2] == ["CalDART contributions", "year: 2026"]


def test_the_contributions_pdf_prints_money_with_its_currency(
    treasurer_client: APIClient, giving: User, pdf_text: PdfText
) -> None:
    """A PDF is read by a person, so its money cells carry the dollar sign."""
    page = pdf_text(treasurer_client.get(CONTRIBUTIONS_PDF, {"year": 2026}).content)[0]
    assert "$100.00" in page


# --------------------------------------------------------------------------
# Role matrix
# --------------------------------------------------------------------------
@pytest.mark.parametrize("url", [CONTRIBUTIONS])
@pytest.mark.parametrize(("slug", "allowed"), role_matrix(TREASURER, ACCOUNT_ADMIN, SYSTEM_ADMIN))
def test_the_contributions_report_is_for_the_finance_roles_only(
    api_client: APIClient,
    all_role_users: dict[str, User],
    url: str,
    slug: str,
    allowed: bool,
) -> None:
    """Only a treasurer, an account admin or a system admin reads who gave what."""
    api_client.force_login(all_role_users[slug])
    assert api_client.get(url).status_code == (200 if allowed else 403)


@pytest.mark.parametrize(("slug", "allowed"), role_matrix(TREASURER, ACCOUNT_ADMIN, SYSTEM_ADMIN))
def test_the_ledger_is_for_the_finance_roles_only(
    api_client: APIClient,
    all_role_users: dict[str, User],
    member: User,
    slug: str,
    allowed: bool,
) -> None:
    """A member's whole money history is finance-only reading."""
    api_client.force_login(all_role_users[slug])
    assert api_client.get(ledger_url(member)).status_code == (200 if allowed else 403)


def test_a_dart_leader_cannot_read_a_payment_detail(
    api_client: APIClient, dart_leader: User, paid: Payment
) -> None:
    """The finance area is closed to every role outside it."""
    api_client.force_login(dart_leader)
    assert api_client.get(detail_url(paid)).status_code == 403


def test_the_payer_still_reads_their_own_payment_status(
    api_client: APIClient, member: User, paid: Payment
) -> None:
    """Widening the payment status endpoint to finance leaves the owner's access alone."""
    api_client.force_login(member)
    assert api_client.get(f"/api/v1/payments/{paid.pk}").status_code == 200


def test_a_treasurer_reads_another_members_payment_status(
    api_client: APIClient, treasurer: User, paid: Payment
) -> None:
    """A treasurer keeps the books, so they see the state of any payment."""
    api_client.force_login(treasurer)
    assert api_client.get(f"/api/v1/payments/{paid.pk}").status_code == 200
