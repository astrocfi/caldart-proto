"""The email log: one row per email the system sends, and the endpoint that reads it.

Everything CalDART mails goes through ``caldart.mail.send_templated``, so these
tests drive that funnel directly for the shape of a row, then drive each kind of
email the application sends -- a reminder, a password link, an invitation, a
receipt, a refund and a renewal notice -- to prove every one of them is
recorded.  ``GET /system/emails`` is covered filter by filter and role by role,
and the Django admin's three refusals are checked as well.
"""

from __future__ import annotations

import datetime as dt
import smtplib

import pytest
from django.conf import settings
from django.contrib.admin.sites import site as admin_site
from django.core.mail import EmailMessage
from django.test import RequestFactory
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import SYSTEM_ADMIN
from apps.accounts.services import send_password_invitation, send_password_reset_email
from apps.mail.admin import EmailLogAdmin
from apps.mail.models import EmailLog, EmailStatus
from apps.mail.purposes import PURPOSE_LABELS
from apps.members.models import MembershipPlan
from apps.payments import receipts, refunds
from apps.payments.models import PaymentStatus, RefundReason
from apps.payments.renewals import send_mandate_email
from apps.reminders.services import send_renewal_reminders
from caldart.mail import send_templated
from tests.conftest import role_matrix
from tests.factories import (
    EmailLogFactory,
    MembershipFactory,
    PaymentFactory,
    RefundFactory,
    RenewalMandateFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db

EMAILS_URL = "/api/v1/system/emails"
PURPOSES_URL = "/api/v1/system/emails/purposes"


# --------------------------------------------------------------------------
# The funnel writes one row
# --------------------------------------------------------------------------
def test_a_send_writes_exactly_one_row(email_template: str, mailoutbox: list[EmailMessage]) -> None:
    """One call to ``send_templated`` is one email and one log row."""
    send_templated(to="marta@example.org", subject="CalDART: hello", template=email_template)

    assert EmailLog.objects.count() == 1


def test_the_row_carries_the_address_and_the_subject(email_template: str) -> None:
    """The row records who was written to and what the subject said."""
    send_templated(to="marta@example.org", subject="CalDART: hello", template=email_template)

    row = EmailLog.objects.get()
    assert row.to_email == "marta@example.org"
    assert row.subject == "CalDART: hello"


def test_the_purpose_defaults_to_the_template_name(email_template: str) -> None:
    """A caller that names no purpose gets the template's own name."""
    send_templated(to="marta@example.org", subject="CalDART: hello", template=email_template)

    assert EmailLog.objects.get().purpose == "statement_of_fact"


def test_a_caller_may_name_the_purpose_itself(email_template: str) -> None:
    """``purpose`` overrides the template name, for a template several kinds share."""
    send_templated(
        to="marta@example.org",
        subject="CalDART: hello",
        template=email_template,
        purpose="reminder_t30",
    )

    assert EmailLog.objects.get().purpose == "reminder_t30"


def test_a_successful_send_is_recorded_as_sent_with_no_error(email_template: str) -> None:
    """A send the mail server took reads ``sent``, and its error is blank."""
    send_templated(to="marta@example.org", subject="CalDART: hello", template=email_template)

    row = EmailLog.objects.get()
    assert row.status == EmailStatus.SENT
    assert row.error == ""


def test_the_row_records_when_the_email_went(email_template: str) -> None:
    """``sent_at`` is the moment of the send, not the moment the row is read."""
    before = timezone.now()

    send_templated(to="marta@example.org", subject="CalDART: hello", template=email_template)

    assert EmailLog.objects.get().sent_at >= before


def test_the_row_names_the_account_the_email_concerned(email_template: str) -> None:
    """``user_id`` is the account the caller named, so the log can be read per member."""
    member = UserFactory(email="marta@example.org")

    send_templated(
        to=member.email,
        subject="CalDART: hello",
        template=email_template,
        user_id=member.pk,
    )

    assert EmailLog.objects.get().user == member


def test_an_email_to_nobody_in_particular_has_no_account(email_template: str) -> None:
    """A caller that names no account leaves the row's account null, not a guess."""
    send_templated(to="stranger@example.org", subject="CalDART: hello", template=email_template)

    assert EmailLog.objects.get().user is None


def test_the_row_lists_the_attachment_filenames(email_template: str) -> None:
    """Every attachment's filename is recorded, comma-separated and in order."""
    send_templated(
        to="marta@example.org",
        subject="CalDART: your receipt",
        template=email_template,
        attachments=[
            ("receipt-0001.pdf", b"%PDF-1.4 fake", "application/pdf"),
            ("statement-2026.pdf", b"%PDF-1.4 fake", "application/pdf"),
        ],
    )

    assert EmailLog.objects.get().attachments == "receipt-0001.pdf, statement-2026.pdf"


def test_a_send_without_attachments_lists_none(email_template: str) -> None:
    """An email with nothing attached records an empty list, not a placeholder."""
    send_templated(to="marta@example.org", subject="CalDART: hello", template=email_template)

    assert EmailLog.objects.get().attachments == ""


# --------------------------------------------------------------------------
# A refusal is recorded and re-raised
# --------------------------------------------------------------------------
def test_a_refused_send_reaches_the_caller(email_template: str, refusing_mail_server: None) -> None:
    """The refusal still propagates: the funnel records it, it does not swallow it."""
    with pytest.raises(smtplib.SMTPException, match="Mailbox unavailable"):
        send_templated(to="marta@example.org", subject="CalDART: hello", template=email_template)


def test_a_refused_send_is_recorded_as_failed(
    email_template: str, refusing_mail_server: None
) -> None:
    """The row reads ``failed`` and names the exception class the server raised."""
    with pytest.raises(smtplib.SMTPException):
        send_templated(to="marta@example.org", subject="CalDART: hello", template=email_template)

    row = EmailLog.objects.get()
    assert row.status == EmailStatus.FAILED
    assert row.error == "SMTPException"


def test_a_refused_send_still_records_what_was_attempted(
    email_template: str, refusing_mail_server: None
) -> None:
    """A failed row carries the address and the subject, so the operator can retry."""
    with pytest.raises(smtplib.SMTPException):
        send_templated(to="marta@example.org", subject="CalDART: hello", template=email_template)

    row = EmailLog.objects.get()
    assert row.to_email == "marta@example.org"
    assert row.subject == "CalDART: hello"


# --------------------------------------------------------------------------
# Every kind of email the application sends
# --------------------------------------------------------------------------
def test_a_renewal_reminder_is_logged_under_its_stage(
    annual_plan: MembershipPlan, mailoutbox: list[EmailMessage]
) -> None:
    """A reminder is logged as ``reminder_<kind>``, naming the member it went to."""
    today = timezone.localdate()
    member = UserFactory(email="marta@example.org", first_name="Marta")
    MembershipFactory(user=member, plan=annual_plan, ends_on=today + dt.timedelta(days=30))

    send_renewal_reminders(today=today)

    row = EmailLog.objects.get()
    assert row.purpose == "reminder_t30"
    assert row.user == member


def test_a_password_reset_is_logged(site_settings: object, mailoutbox: list[EmailMessage]) -> None:
    """The reset link is logged as ``password_reset`` against the account."""
    member = UserFactory(email="marta@example.org")

    send_password_reset_email(member)

    row = EmailLog.objects.get()
    assert row.purpose == "password_reset"
    assert row.user == member


def test_an_invitation_is_logged(site_settings: object, mailoutbox: list[EmailMessage]) -> None:
    """The invitation to set a first password is logged as ``member_invitation``."""
    member = UserFactory(email="nova@example.org")

    send_password_invitation(member)

    row = EmailLog.objects.get()
    assert row.purpose == "member_invitation"
    assert row.user == member


def test_a_receipt_is_logged_with_its_attachment(
    annual_plan: MembershipPlan, mailoutbox: list[EmailMessage]
) -> None:
    """A receipt is logged as ``receipt`` and names the PDF that rode along."""
    payment = PaymentFactory(status=PaymentStatus.SUCCEEDED, plan=annual_plan)

    assert receipts.send_receipt(payment)

    row = EmailLog.objects.get()
    assert row.purpose == "receipt"
    assert row.attachments == receipts.receipt_filename(payment)


def test_a_refund_notice_is_logged(
    annual_plan: MembershipPlan, mailoutbox: list[EmailMessage]
) -> None:
    """The refund notice is logged as ``refund`` against the member refunded."""
    payment = PaymentFactory(status=PaymentStatus.REFUNDED, plan=annual_plan)
    refund = RefundFactory(payment=payment, reason=RefundReason.DUPLICATE)

    refunds.send_refund_email(refund, term_canceled=False)

    row = EmailLog.objects.get()
    assert row.purpose == "refund"
    assert row.user == payment.user


def test_a_renewal_email_is_logged_under_its_template(
    annual_plan: MembershipPlan, mailoutbox: list[EmailMessage]
) -> None:
    """A renewal email is logged under the template it rendered."""
    mandate = RenewalMandateFactory()

    assert send_mandate_email(mandate, "renewal_canceled")

    row = EmailLog.objects.get()
    assert row.purpose == "renewal_canceled"
    assert row.user == mandate.user


# --------------------------------------------------------------------------
# GET /system/emails
# --------------------------------------------------------------------------
@pytest.mark.parametrize(("role", "allowed"), role_matrix(SYSTEM_ADMIN))
def test_email_log_role_matrix(
    api_client: APIClient, all_role_users: dict[str, User], role: str, allowed: bool
) -> None:
    """Only ``system_admin`` reads the email log; every other role gets 403."""
    api_client.force_login(all_role_users[role])

    assert api_client.get(EMAILS_URL).status_code == (200 if allowed else 403)


def test_the_email_log_needs_a_session(api_client: APIClient) -> None:
    """An anonymous caller gets 401, not an empty page."""
    assert api_client.get(EMAILS_URL).status_code == 401


def test_the_log_is_paginated_newest_first(api_client: APIClient, system_admin: User) -> None:
    """The page carries the standard envelope, newest ``sent_at`` first."""
    now = timezone.now()
    EmailLogFactory(purpose="receipt", sent_at=now - dt.timedelta(days=2))
    EmailLogFactory(purpose="refund", sent_at=now)
    api_client.force_login(system_admin)

    body = api_client.get(EMAILS_URL).json()

    assert body["count"] == 2
    assert [row["purpose"] for row in body["results"]] == ["refund", "receipt"]


def test_a_row_carries_the_recipient_account(api_client: APIClient, system_admin: User) -> None:
    """A row names the account the email concerned as well as the address."""
    member = UserFactory(email="marta@example.org", first_name="Marta", last_name="Reyes")
    EmailLogFactory(user=member, purpose="receipt", subject="CalDART: your receipt")
    api_client.force_login(system_admin)

    row = api_client.get(EMAILS_URL).json()["results"][0]

    assert row["user_id"] == member.pk
    assert row["user_name"] == "Marta Reyes"


def test_a_row_for_an_unknown_address_names_no_account(
    api_client: APIClient, system_admin: User
) -> None:
    """A message to an address with no account reads ``null`` and an empty name."""
    EmailLogFactory(user=None, to_email="stranger@example.org")
    api_client.force_login(system_admin)

    row = api_client.get(EMAILS_URL).json()["results"][0]

    assert row["user_id"] is None
    assert row["user_name"] == ""


def test_a_failed_row_carries_its_error(api_client: APIClient, system_admin: User) -> None:
    """A refused send reads ``failed`` and names the exception class."""
    EmailLogFactory(status=EmailStatus.FAILED, error="SMTPException")
    api_client.force_login(system_admin)

    row = api_client.get(EMAILS_URL).json()["results"][0]

    assert row["status"] == "failed"
    assert row["error"] == "SMTPException"


def test_the_purpose_filter_selects_one_kind(api_client: APIClient, system_admin: User) -> None:
    """``?purpose=`` answers only the rows of that purpose."""
    EmailLogFactory(purpose="receipt")
    EmailLogFactory(purpose="reminder_t30")
    api_client.force_login(system_admin)

    body = api_client.get(f"{EMAILS_URL}?purpose=receipt").json()

    assert [row["purpose"] for row in body["results"]] == ["receipt"]


def test_an_unknown_purpose_answers_an_empty_page(
    api_client: APIClient, system_admin: User
) -> None:
    """A purpose the installation has never used is an empty page, not a 400."""
    EmailLogFactory(purpose="receipt")
    api_client.force_login(system_admin)

    response = api_client.get(f"{EMAILS_URL}?purpose=not_a_template")

    assert response.status_code == 200
    assert response.json()["count"] == 0


def test_the_status_filter_selects_the_failures(api_client: APIClient, system_admin: User) -> None:
    """``?status=failed`` answers the refused sends alone."""
    EmailLogFactory(purpose="receipt")
    EmailLogFactory(purpose="refund", status=EmailStatus.FAILED, error="SMTPException")
    api_client.force_login(system_admin)

    body = api_client.get(f"{EMAILS_URL}?status=failed").json()

    assert [row["purpose"] for row in body["results"]] == ["refund"]


def test_an_unknown_status_is_refused(api_client: APIClient, system_admin: User) -> None:
    """``?status=`` takes ``sent`` or ``failed``; anything else is a 400 on ``status``."""
    api_client.force_login(system_admin)

    response = api_client.get(f"{EMAILS_URL}?status=bounced")

    assert response.status_code == 400
    assert "status" in response.json()


def test_the_date_filters_bound_the_day_sent(api_client: APIClient, system_admin: User) -> None:
    """``from`` and ``to`` compare against the date part of ``sent_at``, inclusively."""
    now = timezone.now()
    EmailLogFactory(purpose="receipt", sent_at=now - dt.timedelta(days=5))
    EmailLogFactory(purpose="refund", sent_at=now)
    api_client.force_login(system_admin)
    from_date = (timezone.localtime(now) - dt.timedelta(days=1)).date().isoformat()

    body = api_client.get(f"{EMAILS_URL}?from={from_date}").json()

    assert [row["purpose"] for row in body["results"]] == ["refund"]


def test_the_to_filter_excludes_later_sends(api_client: APIClient, system_admin: User) -> None:
    """``to`` keeps the rows sent on or before that day."""
    now = timezone.now()
    EmailLogFactory(purpose="receipt", sent_at=now - dt.timedelta(days=5))
    EmailLogFactory(purpose="refund", sent_at=now)
    api_client.force_login(system_admin)
    to_date = (timezone.localtime(now) - dt.timedelta(days=1)).date().isoformat()

    body = api_client.get(f"{EMAILS_URL}?to={to_date}").json()

    assert [row["purpose"] for row in body["results"]] == ["receipt"]


def test_the_search_matches_the_address(api_client: APIClient, system_admin: User) -> None:
    """``?q=`` matches part of the address written to, ignoring case."""
    EmailLogFactory(user=None, to_email="marta@example.org", purpose="receipt")
    EmailLogFactory(user=None, to_email="sam@example.org", purpose="refund")
    api_client.force_login(system_admin)

    body = api_client.get(f"{EMAILS_URL}?q=MARTA").json()

    assert [row["purpose"] for row in body["results"]] == ["receipt"]


def test_the_search_matches_the_recipient_name(api_client: APIClient, system_admin: User) -> None:
    """``?q=`` also matches the recipient account's first and last name."""
    member = UserFactory(email="mr@example.org", first_name="Marta", last_name="Reyes")
    EmailLogFactory(user=member, purpose="receipt")
    EmailLogFactory(user=None, to_email="sam@example.org", purpose="refund")
    api_client.force_login(system_admin)

    body = api_client.get(f"{EMAILS_URL}?q=reyes").json()

    assert [row["purpose"] for row in body["results"]] == ["receipt"]


def test_the_log_can_be_read_oldest_first(api_client: APIClient, system_admin: User) -> None:
    """``?ordering=sent_at`` turns the list around."""
    now = timezone.now()
    EmailLogFactory(purpose="receipt", sent_at=now - dt.timedelta(days=2))
    EmailLogFactory(purpose="refund", sent_at=now)
    api_client.force_login(system_admin)

    body = api_client.get(f"{EMAILS_URL}?ordering=sent_at").json()

    assert [row["purpose"] for row in body["results"]] == ["receipt", "refund"]


# --------------------------------------------------------------------------
# Purpose labels and GET /system/emails/purposes
# --------------------------------------------------------------------------
def test_a_row_carries_its_purpose_label(api_client: APIClient, system_admin: User) -> None:
    """``purpose_label`` is the words a reader sees for the template."""
    EmailLogFactory(purpose="reminder_t30")
    api_client.force_login(system_admin)

    row = api_client.get(EMAILS_URL).json()["results"][0]

    assert row["purpose_label"] == "Renewal reminder (30 days)"


def test_an_unlabeled_purpose_reads_as_its_slug(api_client: APIClient, system_admin: User) -> None:
    """A template no label names is shown by its own name rather than hidden."""
    EmailLogFactory(purpose="board_minutes")
    api_client.force_login(system_admin)

    row = api_client.get(EMAILS_URL).json()["results"][0]

    assert row["purpose_label"] == "board_minutes"


@pytest.mark.parametrize(("role", "allowed"), role_matrix(SYSTEM_ADMIN))
def test_the_purposes_role_matrix(
    api_client: APIClient, all_role_users: dict[str, User], role: str, allowed: bool
) -> None:
    """Only ``system_admin`` reads the purposes, as only it reads the log."""
    api_client.force_login(all_role_users[role])

    assert api_client.get(PURPOSES_URL).status_code == (200 if allowed else 403)


def test_the_purposes_need_a_session(api_client: APIClient) -> None:
    """An anonymous caller gets 401."""
    assert api_client.get(PURPOSES_URL).status_code == 401


def test_the_purposes_are_every_labeled_template_in_order(
    api_client: APIClient, system_admin: User
) -> None:
    """One ``{value, label}`` per labeled purpose, in the order the filter offers them."""
    api_client.force_login(system_admin)

    body = api_client.get(PURPOSES_URL).json()

    assert body == [{"value": value, "label": label} for value, label in PURPOSE_LABELS.items()]


def test_the_purposes_name_every_template_the_application_sends() -> None:
    """Every email template on disk has a label, so no purpose reads as a bare slug."""
    templates = {path.stem for path in (settings.BASE_DIR / "templates" / "emails").glob("*.txt")}

    assert sorted(templates - set(PURPOSE_LABELS)) == []


# --------------------------------------------------------------------------
# The Django admin is read-only
# --------------------------------------------------------------------------
def test_the_admin_refuses_to_add_a_row(rf: RequestFactory, system_admin: User) -> None:
    """Nobody writes an email log row by hand: the funnel is the only author."""
    request = rf.get("/django-admin/mail/emaillog/")
    request.user = system_admin

    assert EmailLogAdmin(EmailLog, admin_site).has_add_permission(request) is False


def test_the_admin_refuses_to_change_a_row(rf: RequestFactory, system_admin: User) -> None:
    """An edited row would answer the operator's question dishonestly, so it is barred."""
    row = EmailLogFactory(purpose="receipt")
    request = rf.get("/django-admin/mail/emaillog/")
    request.user = system_admin

    assert EmailLogAdmin(EmailLog, admin_site).has_change_permission(request, row) is False


def test_the_admin_refuses_to_delete_a_row(rf: RequestFactory, system_admin: User) -> None:
    """The log is kept whole, so a row cannot be deleted from the admin either."""
    row = EmailLogFactory(purpose="receipt")
    request = rf.get("/django-admin/mail/emaillog/")
    request.user = system_admin

    assert EmailLogAdmin(EmailLog, admin_site).has_delete_permission(request, row) is False
