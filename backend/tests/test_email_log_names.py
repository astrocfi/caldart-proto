"""The email log's recipient name: ``to_name``, and where each kind of send gets it.

``EmailLog.to_name`` carries the recipient's name as it was at the moment the email
went, so a report or a search can show who a message was for even when the
recipient holds no account -- a DART contact, most often.  ``caldart.mail._record``
fills it in from the linked account's ``display_name`` when a caller names only
``user_id``, and :attr:`~apps.mail.models.EmailLog.recipient_name` falls back the
same way for a row written before the field existed.  These tests drive the funnel
directly for that storage behavior, then the two senders that pass their own name
explicitly: the DART roster (the contact's own name) and a report subscription
(the recipient account's display name, or nothing for a bare address).  ``GET
/system/emails`` reading the name back is covered in ``test_mail_log.py``, and the
report's ``Name`` column in ``test_email_log_report.py``.
"""

from __future__ import annotations

import datetime as dt

import pytest
from django.core.mail import EmailMessage
from django.utils import timezone

from apps.accounts.roles import ACCOUNT_ADMIN
from apps.mail.models import EmailLog
from apps.members.models import MembershipPlan
from apps.reminders.services import send_renewal_reminders
from apps.reports.services import run_scheduled_reports
from caldart.mail import send_templated
from tests.factories import (
    DartContactFactory,
    DartFactory,
    EmailLogFactory,
    MembershipFactory,
    ReportSubscriptionFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db

#: The day the scheduled-report runs below are made on.
TODAY = dt.date(2026, 10, 1)


# --------------------------------------------------------------------------
# The funnel stores the name
# --------------------------------------------------------------------------
def test_a_caller_provided_name_is_stored_as_given(email_template: str) -> None:
    """``to_name`` is recorded exactly as the caller passes it."""
    send_templated(
        to="lee@example.test",
        subject="CalDART: hello",
        template=email_template,
        to_name="Lee Park",
    )

    assert EmailLog.objects.get().to_name == "Lee Park"


def test_a_caller_with_no_name_but_an_account_gets_its_display_name_stored(
    email_template: str,
) -> None:
    """A caller naming only ``user_id`` has the account's own name written in."""
    member = UserFactory(email="marta@example.org", first_name="Marta", last_name="Reyes")

    send_templated(
        to=member.email,
        subject="CalDART: hello",
        template=email_template,
        user_id=member.pk,
    )

    assert EmailLog.objects.get().to_name == "Marta Reyes"


def test_a_caller_with_no_name_and_no_account_stores_a_blank_name(email_template: str) -> None:
    """A message to a bare address with no account behind it stores no name at all."""
    send_templated(to="stranger@example.org", subject="CalDART: hello", template=email_template)

    assert EmailLog.objects.get().to_name == ""


# --------------------------------------------------------------------------
# recipient_name
# --------------------------------------------------------------------------
def test_recipient_name_falls_back_to_the_accounts_display_name_when_blank() -> None:
    """A row written before ``to_name`` existed reads by the linked account's name."""
    member = UserFactory(first_name="Marta", last_name="Reyes")
    row = EmailLogFactory(user=member, to_name="")

    assert row.recipient_name == "Marta Reyes"


def test_recipient_name_is_blank_with_neither_a_name_nor_an_account() -> None:
    """A row naming nobody at all reads as an empty name, not a guess."""
    row = EmailLogFactory(user=None, to_name="")

    assert row.recipient_name == ""


def test_recipient_name_keeps_the_name_recorded_over_the_accounts_current_one() -> None:
    """A member who has since been renamed still shows under the name they had."""
    member = UserFactory(first_name="Marta", last_name="Reyes")
    row = EmailLogFactory(user=member, to_name="Marta Prior")

    assert row.recipient_name == "Marta Prior"


# --------------------------------------------------------------------------
# The senders that pass their own name
# --------------------------------------------------------------------------
def test_a_roster_email_logs_the_contacts_name(mailoutbox: list[EmailMessage]) -> None:
    """The DART roster sender records the ticked contact's own name."""
    dart = DartFactory(name="Bay Area DART")
    DartContactFactory(dart=dart, name="Lee Park", email="lee@example.test", receives_roster=True)

    run_scheduled_reports(today=TODAY)

    row = EmailLog.objects.get(purpose="dart_roster")
    assert row.to_name == "Lee Park"


def test_a_subscription_to_an_outside_address_logs_an_empty_name(
    mailoutbox: list[EmailMessage],
) -> None:
    """A subscription bound to no account logs no name, only its bare address."""
    ReportSubscriptionFactory(next_due_on=TODAY)

    run_scheduled_reports(today=TODAY)

    row = EmailLog.objects.get(purpose="scheduled_report")
    assert row.to_name == ""


def test_a_subscription_to_an_account_logs_its_display_name(
    mailoutbox: list[EmailMessage],
) -> None:
    """A subscription bound to an account logs that account's own display name."""
    recipient = UserFactory(first_name="Nadia", last_name="Cole", roles=[ACCOUNT_ADMIN])
    ReportSubscriptionFactory(
        recipient_user=recipient, recipient_email=recipient.email, next_due_on=TODAY
    )

    run_scheduled_reports(today=TODAY)

    row = EmailLog.objects.get(purpose="scheduled_report")
    assert row.to_name == "Nadia Cole"


def test_a_reminder_logs_the_users_display_name_without_the_caller_passing_one(
    annual_plan: MembershipPlan, mailoutbox: list[EmailMessage]
) -> None:
    """A reminder never names ``to_name`` itself; the funnel fills it in regardless."""
    today = timezone.localdate()
    member = UserFactory(email="marta@example.org", first_name="Marta", last_name="Reyes")
    MembershipFactory(user=member, plan=annual_plan, ends_on=today + dt.timedelta(days=30))

    send_renewal_reminders(today=today)

    row = EmailLog.objects.get(purpose="reminder_t30")
    assert row.to_name == "Marta Reyes"
