"""CalDART's own receipt, the annual contribution statement, and their endpoints.

One receipt goes out for every payment that succeeds, whoever took the money,
with the PDF attached; a member downloads it again whenever they like, and a
calendar year of contributions gathers into a statement for a tax return.  The
finance roles reach any member's, and can send a receipt again.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone
from pytest_django.fixtures import Settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.members.models import MembershipPlan
from apps.payments import receipts
from apps.payments.models import Payment, PaymentProvider, PaymentStatus, PaymentWallet
from apps.payments.services import create_checkout, mark_succeeded
from caldart.receipts import CONTRIBUTION_NOTICE, CONTRIBUTIONS_NOTICE
from tests.conftest import PdfText, audit_messages
from tests.factories import PaymentFactory, RefundFactory, UserFactory

pytestmark = pytest.mark.django_db

MY_STATEMENTS = "/api/v1/me/payments/statements"
MY_PAYMENTS = "/api/v1/me/payments"


def drawn(pdf: bytes, pdf_text: PdfText) -> str:
    """Everything the first page of ``pdf`` draws, as one string.

    reportlab draws a paragraph as one string per line, so a value that shares a
    line with its label is found in the whole page's text rather than on its own.
    """
    return " ".join(pdf_text(pdf)[0])


@pytest.fixture(autouse=True)
def _mock_enabled(settings: Settings) -> None:
    """Enable the mock provider, which the payments here are taken through."""
    settings.PAYMENTS_MOCK_ENABLED = True


def succeeded_payment(
    member: User,
    plan: MembershipPlan | None = None,
    *,
    contribution_cents: int = 0,
    completed_at: dt.datetime | None = None,
    **fields: Any,
) -> Payment:
    """A succeeded mock payment for ``member``, settled on ``completed_at``.

    The row is written succeeded rather than charged through a provider, so a
    test can place it in any year without a clock to freeze.
    """
    plan_amount = plan.price_cents if plan is not None else 0
    payment = PaymentFactory(
        user=member,
        plan=plan,
        amount_cents=plan_amount + contribution_cents,
        plan_amount_cents=plan_amount,
        contribution_cents=contribution_cents,
        status=PaymentStatus.SUCCEEDED,
        **fields,
    )
    Payment.objects.filter(pk=payment.pk).update(completed_at=completed_at or timezone.now())
    payment.refresh_from_db()
    return payment


# --------------------------------------------------------------------------
# The receipt email
# --------------------------------------------------------------------------
def test_a_succeeded_payment_emails_the_payer_a_receipt(
    api_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    mailoutbox: list[EmailMultiAlternatives],
) -> None:
    """Completing a payment sends one receipt, to the member who paid."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.MOCK)
    api_client.force_login(member)

    api_client.post("/api/v1/payments/mock/complete", {"payment_id": payment.pk})

    assert [message.to for message in mailoutbox] == [[member.email]]


def test_the_receipt_carries_the_pdf_as_an_attachment(
    member: User, annual_plan: MembershipPlan, mailoutbox: list[EmailMultiAlternatives]
) -> None:
    """The receipt rides with its own PDF, named for the receipt number."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.MOCK)

    mark_succeeded(payment)

    filename, content, mimetype = mailoutbox[0].attachments[0]
    assert filename == f"caldart-receipt-{payment.receipt_number}.pdf"
    assert mimetype == "application/pdf"
    assert content.startswith(b"%PDF")


def test_the_receipt_subject_names_the_organization_and_the_amount(
    member: User, annual_plan: MembershipPlan, mailoutbox: list[EmailMultiAlternatives]
) -> None:
    """The subject reads as the house voice asks, with no exclamation."""
    payment = create_checkout(member, "annual", 1_000, PaymentProvider.MOCK)

    mark_succeeded(payment)

    assert mailoutbox[0].subject == "CalDART: your receipt for $55.00"


def test_the_receipt_stamps_when_it_was_sent(
    member: User, annual_plan: MembershipPlan, mailoutbox: list[EmailMultiAlternatives]
) -> None:
    """A receipt that went out is recorded on the payment."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.MOCK)

    mark_succeeded(payment)

    payment.refresh_from_db()
    assert payment.receipt_sent_at is not None


def test_a_second_confirmation_sends_no_second_receipt(
    member: User, annual_plan: MembershipPlan, mailoutbox: list[EmailMultiAlternatives]
) -> None:
    """A webhook racing the browser must not send the member two receipts."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.MOCK)
    mark_succeeded(payment)

    mark_succeeded(Payment.objects.get(pk=payment.pk))

    assert len(mailoutbox) == 1


def test_a_refused_receipt_leaves_the_payment_succeeded(
    member: User, annual_plan: MembershipPlan, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A mail server that will not take the receipt never undoes the membership."""

    def refuse(self: EmailMultiAlternatives, fail_silently: bool = False) -> int:
        raise OSError("the mail server said no")

    monkeypatch.setattr(EmailMultiAlternatives, "send", refuse)
    payment = create_checkout(member, "annual", 0, PaymentProvider.MOCK)

    mark_succeeded(payment)

    payment.refresh_from_db()
    assert payment.status == PaymentStatus.SUCCEEDED


def test_a_refused_receipt_leaves_the_stamp_unset(
    member: User, annual_plan: MembershipPlan, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The stamp is the record of a receipt that arrived, so a refusal leaves it null."""

    def refuse(self: EmailMultiAlternatives, fail_silently: bool = False) -> int:
        raise OSError("the mail server said no")

    monkeypatch.setattr(EmailMultiAlternatives, "send", refuse)
    payment = create_checkout(member, "annual", 0, PaymentProvider.MOCK)

    mark_succeeded(payment)

    payment.refresh_from_db()
    assert payment.receipt_sent_at is None


def test_a_payer_with_no_address_gets_no_receipt(
    annual_plan: MembershipPlan,
    user_factory: type[UserFactory],
    mailoutbox: list[EmailMultiAlternatives],
) -> None:
    """There is nowhere to send a receipt for a member with no email address."""
    nameless = user_factory(email="")
    payment = succeeded_payment(nameless, annual_plan)

    assert receipts.send_receipt(payment) is False
    assert mailoutbox == []


# --------------------------------------------------------------------------
# What the receipt PDF says
# --------------------------------------------------------------------------
def test_the_receipt_pdf_names_the_receipt_number(
    member: User, annual_plan: MembershipPlan, pdf_text: PdfText
) -> None:
    """The number a member quotes when they write in is on the page."""
    payment = succeeded_payment(member, annual_plan)

    assert f"Receipt {payment.receipt_number}" in drawn(
        receipts.render_receipt_pdf(payment), pdf_text
    )


def test_the_receipt_pdf_names_the_payer(
    member: User, annual_plan: MembershipPlan, pdf_text: PdfText
) -> None:
    """The receipt says who paid."""
    payment = succeeded_payment(member, annual_plan)

    assert member.email in drawn(receipts.render_receipt_pdf(payment), pdf_text)


def test_the_receipt_pdf_carries_the_501c3_sentence_for_a_contribution(
    member: User, annual_plan: MembershipPlan, pdf_text: PdfText
) -> None:
    """A gift needs the substantiation wording; that is what makes it usable."""
    payment = succeeded_payment(member, annual_plan, contribution_cents=10_000)

    assert CONTRIBUTION_NOTICE in drawn(receipts.render_receipt_pdf(payment), pdf_text)


def test_the_receipt_pdf_omits_the_501c3_sentence_for_dues_alone(
    member: User, annual_plan: MembershipPlan, pdf_text: PdfText
) -> None:
    """Dues are value received, not a gift, so no deduction is claimed for them."""
    payment = succeeded_payment(member, annual_plan)

    assert CONTRIBUTION_NOTICE not in drawn(receipts.render_receipt_pdf(payment), pdf_text)


def test_the_receipt_pdf_names_how_a_check_arrived(
    member: User, annual_plan: MembershipPlan, pdf_text: PdfText
) -> None:
    """A payment recorded by hand says so, and says what it came in as."""
    payment = succeeded_payment(
        member,
        annual_plan,
        provider=PaymentProvider.MANUAL,
        wallet=PaymentWallet.CHECK,
        provider_ref="",
    )

    assert "Paid with Recorded by hand (Check)" in drawn(
        receipts.render_receipt_pdf(payment), pdf_text
    )


# --------------------------------------------------------------------------
# The statement
# --------------------------------------------------------------------------
def test_a_year_with_no_contribution_offers_no_statement(
    member: User, annual_plan: MembershipPlan
) -> None:
    """Dues alone are not a gift, so they do not earn a statement."""
    succeeded_payment(member, annual_plan)

    assert receipts.statement_years(member) == []


def test_statement_years_are_newest_first(member: User, annual_plan: MembershipPlan) -> None:
    """The member is offered the most recent year first."""
    for year in (2024, 2026, 2025):
        succeeded_payment(
            member,
            annual_plan,
            contribution_cents=5_000,
            completed_at=timezone.make_aware(dt.datetime(year, 6, 1, 12, 0)),
        )

    assert receipts.statement_years(member) == [2026, 2025, 2024]


def test_the_statement_totals_the_year_it_covers(
    member: User, annual_plan: MembershipPlan, pdf_text: PdfText
) -> None:
    """Two gifts in one year add up on the page, and another year's stays out."""
    for amount, year in ((5_000, 2026), (2_500, 2026), (9_900, 2025)):
        succeeded_payment(
            member,
            annual_plan,
            contribution_cents=amount,
            completed_at=timezone.make_aware(dt.datetime(year, 6, 1, 12, 0)),
        )

    assert "$75.00" in drawn(receipts.render_statement_pdf(member, 2026), pdf_text)


def test_the_statement_carries_the_501c3_sentence(
    member: User, annual_plan: MembershipPlan, pdf_text: PdfText
) -> None:
    """A statement is substantiation, so it says what a donor's accountant needs."""
    succeeded_payment(member, annual_plan, contribution_cents=5_000)

    year = timezone.localdate().year

    assert CONTRIBUTIONS_NOTICE in drawn(receipts.render_statement_pdf(member, year), pdf_text)


def test_a_refund_against_the_contribution_nets_the_statement(
    member: User, annual_plan: MembershipPlan
) -> None:
    """A gift given back is not a gift the member may deduct."""
    payment = succeeded_payment(member, annual_plan, contribution_cents=10_000)
    RefundFactory(payment=payment, amount_cents=2_500)

    statement = receipts.statement_data(member, timezone.localdate().year)

    assert statement.total_cents == 7_500


def test_a_refund_larger_than_the_gift_nets_no_further(
    member: User, annual_plan: MembershipPlan
) -> None:
    """Once the whole gift is back, refunding the dues as well takes nothing more."""
    payment = succeeded_payment(member, annual_plan, contribution_cents=10_000)
    RefundFactory(payment=payment, amount_cents=payment.amount_cents)

    statement = receipts.statement_data(member, timezone.localdate().year)

    assert statement.contributions[0].refunded_cents == 10_000


# --------------------------------------------------------------------------
# A member's own endpoints
# --------------------------------------------------------------------------
def test_a_member_downloads_their_own_receipt(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """The receipt comes back as an attachment named for its number."""
    payment = succeeded_payment(member, annual_plan)
    api_client.force_login(member)

    response = api_client.get(f"/api/v1/me/payments/{payment.pk}/receipt.pdf")

    assert response.status_code == 200
    assert response["Content-Disposition"] == (
        f'attachment; filename="caldart-receipt-{payment.receipt_number}.pdf"'
    )


def test_a_member_cannot_download_someone_elses_receipt(
    api_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    user_factory: type[UserFactory],
) -> None:
    """Another member's payment is as invisible as one that does not exist."""
    stranger = user_factory(email="stranger@example.test")
    payment = succeeded_payment(stranger, annual_plan)
    api_client.force_login(member)

    assert api_client.get(f"/api/v1/me/payments/{payment.pk}/receipt.pdf").status_code == 404


def test_a_pending_payment_has_no_receipt(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """Money that has not arrived has bought nothing to acknowledge."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.MOCK)
    api_client.force_login(member)

    assert api_client.get(f"/api/v1/me/payments/{payment.pk}/receipt.pdf").status_code == 404


def test_an_anonymous_visitor_gets_no_receipt(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """Signing in is the whole permission check on a member's own receipt."""
    payment = succeeded_payment(member, annual_plan)

    assert api_client.get(f"/api/v1/me/payments/{payment.pk}/receipt.pdf").status_code == 401


def test_the_statement_years_endpoint_lists_what_can_be_downloaded(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """The screen's one button per year comes from this list."""
    succeeded_payment(
        member,
        annual_plan,
        contribution_cents=5_000,
        completed_at=timezone.make_aware(dt.datetime(2026, 2, 1, 12, 0)),
    )
    api_client.force_login(member)

    assert api_client.get(MY_STATEMENTS).json() == {"years": [2026]}


def test_a_member_who_never_gave_is_offered_no_year(api_client: APIClient, member: User) -> None:
    """An empty list, not a 404: there is simply nothing to download."""
    api_client.force_login(member)

    assert api_client.get(MY_STATEMENTS).json() == {"years": []}


def test_a_member_downloads_their_own_statement(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """The statement comes back as an attachment named for its year and the member."""
    member.first_name = "Marta"
    member.last_name = "Reyes"
    member.save(update_fields=["first_name", "last_name"])
    succeeded_payment(
        member,
        annual_plan,
        contribution_cents=5_000,
        completed_at=timezone.make_aware(dt.datetime(2026, 2, 1, 12, 0)),
    )
    api_client.force_login(member)

    response = api_client.get(f"{MY_STATEMENTS}/2026.pdf")

    assert response["Content-Disposition"] == (
        'attachment; filename="caldart-contributions-2026-marta-reyes.pdf"'
    )


def test_a_statement_for_a_member_with_no_usable_name_is_named_by_id(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A display name that slugifies to nothing falls back to the account id."""
    member.first_name = ""
    member.last_name = ""
    member.email = "@@@@@@@@"
    member.save(update_fields=["first_name", "last_name", "email"])
    succeeded_payment(
        member,
        annual_plan,
        contribution_cents=5_000,
        completed_at=timezone.make_aware(dt.datetime(2026, 2, 1, 12, 0)),
    )
    api_client.force_login(member)

    response = api_client.get(f"{MY_STATEMENTS}/2026.pdf")

    assert response["Content-Disposition"] == (
        f'attachment; filename="caldart-contributions-2026-{member.pk}.pdf"'
    )


def test_a_year_the_member_gave_nothing_in_has_no_statement(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A page of zeroes would be worse than saying there is nothing."""
    succeeded_payment(member, annual_plan, contribution_cents=5_000)
    api_client.force_login(member)

    assert api_client.get(f"{MY_STATEMENTS}/1999.pdf").status_code == 404


# --------------------------------------------------------------------------
# The finance roles' endpoints
# --------------------------------------------------------------------------
def test_a_treasurer_downloads_any_members_receipt(
    treasurer_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """Finance reaches every receipt, which is what answering a query needs."""
    payment = succeeded_payment(member, annual_plan)

    response = treasurer_client.get(f"/api/v1/admin/payments/{payment.pk}/receipt.pdf")

    assert response.status_code == 200


def test_a_member_cannot_reach_the_finance_receipt(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """The finance route is role-gated even over the caller's own payment."""
    payment = succeeded_payment(member, annual_plan)
    api_client.force_login(member)

    assert api_client.get(f"/api/v1/admin/payments/{payment.pk}/receipt.pdf").status_code == 403


def test_a_treasurer_sends_the_receipt_again(
    treasurer_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    mailoutbox: list[EmailMultiAlternatives],
) -> None:
    """Resending is how a receipt that never arrived is put right."""
    payment = succeeded_payment(member, annual_plan)

    response = treasurer_client.post(f"/api/v1/admin/payments/{payment.pk}/receipt")

    assert response.json()["sent"] is True
    assert [message.to for message in mailoutbox] == [[member.email]]


def test_resending_stamps_the_payment(
    treasurer_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """The response carries the stamp the payment now holds."""
    payment = succeeded_payment(member, annual_plan)

    body = treasurer_client.post(f"/api/v1/admin/payments/{payment.pk}/receipt").json()

    payment.refresh_from_db()
    assert body["receipt_sent_at"] is not None


def test_a_refused_resend_reports_that_it_did_not_go(
    treasurer_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The treasurer is told the truth, so they can try once the mail server is back."""

    def refuse(self: EmailMultiAlternatives, fail_silently: bool = False) -> int:
        raise OSError("the mail server said no")

    payment = succeeded_payment(member, annual_plan)
    monkeypatch.setattr(EmailMultiAlternatives, "send", refuse)

    body = treasurer_client.post(f"/api/v1/admin/payments/{payment.pk}/receipt").json()

    assert body == {"sent": False, "receipt_sent_at": None}


def test_a_resend_that_went_is_audited(
    treasurer_client: APIClient,
    treasurer: User,
    member: User,
    annual_plan: MembershipPlan,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """Sending a member's receipt again is a privileged act, so the log says who did."""
    payment = succeeded_payment(member, annual_plan)

    treasurer_client.post(f"/api/v1/admin/payments/{payment.pk}/receipt")

    assert audit_messages(audit_log) == [
        f"action=payment.receipt_resend actor={treasurer.pk} target={payment.pk} sent=true"
    ]


def test_a_resend_that_was_refused_is_audited(
    treasurer_client: APIClient,
    treasurer: User,
    member: User,
    annual_plan: MembershipPlan,
    audit_log: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The attempt is recorded even when the mail server turned it away."""

    def refuse(self: EmailMultiAlternatives, fail_silently: bool = False) -> int:
        raise OSError("the mail server said no")

    payment = succeeded_payment(member, annual_plan)
    monkeypatch.setattr(EmailMultiAlternatives, "send", refuse)

    treasurer_client.post(f"/api/v1/admin/payments/{payment.pk}/receipt")

    assert audit_messages(audit_log) == [
        f"action=payment.receipt_resend actor={treasurer.pk} target={payment.pk} sent=false"
    ]


def test_a_treasurer_downloads_any_members_statement(
    treasurer_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """Finance can hand a member the letter their accountant is asking for."""
    succeeded_payment(
        member,
        annual_plan,
        contribution_cents=5_000,
        completed_at=timezone.make_aware(dt.datetime(2026, 2, 1, 12, 0)),
    )

    url = f"/api/v1/admin/payments/ledger/{member.pk}/statements/2026.pdf"

    assert treasurer_client.get(url).status_code == 200


def test_a_statement_for_an_unknown_member_is_a_404(treasurer_client: APIClient) -> None:
    """An id nobody holds answers 404 rather than an empty statement."""
    url = "/api/v1/admin/payments/ledger/9999/statements/2026.pdf"

    assert treasurer_client.get(url).status_code == 404


# --------------------------------------------------------------------------
# GET /me/payments
# --------------------------------------------------------------------------
def test_a_payment_row_carries_the_term_it_bought(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """The payments screen shows the term without a second call per row."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.MOCK)
    mark_succeeded(payment)
    api_client.force_login(member)

    row = api_client.get("/api/v1/me/payments").json()[0]

    assert row["membership"]["starts_on"] == timezone.localdate().isoformat()


def test_a_contribution_only_payment_carries_no_term(api_client: APIClient, member: User) -> None:
    """A bare donation buys no membership, and says so rather than guessing."""
    payment = create_checkout(member, None, 5_000, PaymentProvider.MOCK)
    mark_succeeded(payment)
    api_client.force_login(member)

    row = api_client.get("/api/v1/me/payments").json()[0]

    assert row["membership"] is None


def test_a_payment_row_names_what_it_bought(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """Dues and a gift in one payment read as ``both``."""
    payment = create_checkout(member, "annual", 5_000, PaymentProvider.MOCK)
    mark_succeeded(payment)
    api_client.force_login(member)

    assert api_client.get("/api/v1/me/payments").json()[0]["kind"] == "both"


def test_a_payment_row_carries_what_has_come_back(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A member sees the refund against their payment on the same row."""
    payment = succeeded_payment(member, annual_plan, contribution_cents=5_000)
    RefundFactory(payment=payment, amount_cents=2_500)
    api_client.force_login(member)

    assert api_client.get("/api/v1/me/payments").json()[0]["refunded_cents"] == 2_500
