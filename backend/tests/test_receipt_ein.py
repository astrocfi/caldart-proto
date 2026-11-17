"""The EIN on every receipt and contribution statement, and the health check for it.

A receipt or statement a person keeps for their taxes carries CalDART's EIN, which a
website administrator enters in Site settings.  The PDFs print it in the letterhead
(``test_receipts_pdf.py``); the emails print it in their footer.  Because a blank field
leaves the line out, the system health page warns while it is blank.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from django.core.mail import EmailMultiAlternatives
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.cms.models import SiteSettings
from apps.members.models import MembershipPlan
from apps.payments.models import Payment, PaymentStatus
from apps.payments.receipts import send_receipt
from apps.payments.statements import send_year_statements
from tests.factories import PaymentFactory

pytestmark = pytest.mark.django_db

EIN = "83-1407209"
HEALTH_URL = "/api/v1/system/health"
YEAR = 2026


@pytest.fixture
def with_ein(site_settings: SiteSettings) -> SiteSettings:
    """Site settings holding :data:`EIN`."""
    site_settings.ein = EIN
    site_settings.save()
    return site_settings


@pytest.fixture
def without_ein(site_settings: SiteSettings) -> SiteSettings:
    """Site settings with a blank EIN."""
    site_settings.ein = ""
    site_settings.save()
    return site_settings


def _paid(member: User, *, plan: MembershipPlan | None, contribution_cents: int) -> Payment:
    """A succeeded payment from ``member``, settled in :data:`YEAR`."""
    plan_cents = plan.price_cents if plan is not None else 0
    payment = PaymentFactory(
        user=member,
        plan=plan,
        plan_amount_cents=plan_cents,
        contribution_cents=contribution_cents,
        amount_cents=plan_cents + contribution_cents,
        status=PaymentStatus.SUCCEEDED,
    )
    Payment.objects.filter(pk=payment.pk).update(
        completed_at=datetime(YEAR, 6, 15, 12, 0, tzinfo=UTC)
    )
    payment.refresh_from_db()
    return payment


def _bodies(message: EmailMultiAlternatives) -> tuple[str, str]:
    """The plain-text body and the HTML body of ``message``."""
    html = message.alternatives[0][0]
    assert isinstance(html, str)
    return str(message.body), html


@pytest.mark.usefixtures("with_ein")
@pytest.mark.parametrize("part", [0, 1], ids=["text", "html"])
def test_a_receipt_for_dues_alone_prints_the_ein(
    member: User,
    annual_plan: MembershipPlan,
    mailoutbox: list[EmailMultiAlternatives],
    part: int,
) -> None:
    """A receipt for dues, without a contribution, still names the EIN."""
    send_receipt(_paid(member, plan=annual_plan, contribution_cents=0))
    assert f"EIN {EIN}" in _bodies(mailoutbox[0])[part]


@pytest.mark.usefixtures("with_ein")
@pytest.mark.parametrize("part", [0, 1], ids=["text", "html"])
def test_a_receipt_for_a_gift_prints_the_ein(
    member: User, mailoutbox: list[EmailMultiAlternatives], part: int
) -> None:
    """A receipt for a contribution alone names the EIN."""
    send_receipt(_paid(member, plan=None, contribution_cents=2_500))
    assert f"EIN {EIN}" in _bodies(mailoutbox[0])[part]


@pytest.mark.usefixtures("with_ein")
@pytest.mark.parametrize("part", [0, 1], ids=["text", "html"])
def test_a_contribution_statement_email_prints_the_ein(
    member: User, mailoutbox: list[EmailMultiAlternatives], part: int
) -> None:
    """The yearly statement's email names the EIN."""
    _paid(member, plan=None, contribution_cents=2_500)
    send_year_statements(YEAR)
    assert f"EIN {EIN}" in _bodies(mailoutbox[0])[part]


@pytest.mark.usefixtures("without_ein")
def test_a_receipt_leaves_the_ein_line_out_while_it_is_blank(
    member: User, mailoutbox: list[EmailMultiAlternatives]
) -> None:
    """A blank EIN doesn't print an empty ``EIN`` line."""
    send_receipt(_paid(member, plan=None, contribution_cents=2_500))
    assert "EIN" not in _bodies(mailoutbox[0])[0]


@pytest.mark.usefixtures("with_ein", "backup_dir")
def test_health_reports_the_ein_as_entered(api_client: APIClient, system_admin: User) -> None:
    """``ein_set`` is true while Site settings hold an EIN."""
    api_client.force_login(system_admin)
    assert api_client.get(HEALTH_URL).json()["ein_set"] is True


@pytest.mark.usefixtures("without_ein", "backup_dir")
def test_health_reports_a_blank_ein(api_client: APIClient, system_admin: User) -> None:
    """``ein_set`` is false while the EIN is blank, so the health page can warn."""
    api_client.force_login(system_admin)
    assert api_client.get(HEALTH_URL).json()["ein_set"] is False
