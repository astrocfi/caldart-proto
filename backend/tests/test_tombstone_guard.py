"""A tombstone's record refuses every change, and the screens can tell one apart.

A tombstone, **Deleted member <id>**, keeps a deleted account's payments.  A real name
or address written onto it would make ``is_tombstone`` false, after which a gift
settling late would buy a term and mail a receipt; deleting it would only move the
payments to a second tombstone.  So the member record's ``PATCH``, ``DELETE`` and term
grant, and the users admin's ``PATCH``, refuse one with a 400 and change nothing.  The
donors report, the payment list, the ledger and the record each flag it, so the
portal offers no link or control that would try.
"""

from __future__ import annotations

from datetime import date

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import AccountKind, User
from apps.accounts.roles import ACCOUNT_ADMIN, MEMBER, TREASURER, USER_ADMIN
from apps.members.models import Membership, MembershipPlan
from apps.members.services import is_tombstone, tombstone_for
from apps.payments.models import Payment
from tests.conftest import audit_messages
from tests.factories import UserFactory, settled_gift

pytestmark = pytest.mark.django_db

MEMBERS_URL = "/api/v1/admin/members"

#: What every refused change to a tombstone answers with.
REFUSED = {
    "detail": "This record keeps a deleted member's payments in the books and cannot be changed."
}


@pytest.fixture
def admin_client(api_client: APIClient) -> APIClient:
    """A client signed in with every role the guarded endpoints and the flags need."""
    admin = UserFactory(
        email="guard-admin@example.test",
        roles=[MEMBER, USER_ADMIN, TREASURER, ACCOUNT_ADMIN],
    )
    api_client.force_login(admin)
    return api_client


@pytest.fixture
def tombstone(db: None) -> User:
    """**Deleted member <id>**, holding one settled gift its deleted owner gave."""
    stone = tombstone_for(UserFactory(email="gone@example.test"))
    settled_gift(stone, cents=4_000, on=date(2025, 4, 1))
    return stone


def _record_url(user: User) -> str:
    """The member record of ``user``."""
    return f"{MEMBERS_URL}/{user.pk}"


# --------------------------------------------------------------------------
# The refusals
# --------------------------------------------------------------------------
def test_editing_a_tombstones_record_is_refused(admin_client: APIClient, tombstone: User) -> None:
    """``PATCH`` with a real name is a 400 carrying the reason."""
    response = admin_client.patch(
        _record_url(tombstone), {"first_name": "Rosa", "last_name": "Delgado"}, format="json"
    )

    assert (response.status_code, response.json()) == (400, REFUSED)


def test_a_refused_edit_leaves_the_tombstone_a_tombstone(
    admin_client: APIClient, tombstone: User
) -> None:
    """Nothing is written, so ``is_tombstone`` still recognizes the account."""
    admin_client.patch(
        _record_url(tombstone),
        {"first_name": "Rosa", "email": "rosa@example.test"},
        format="json",
    )

    tombstone.refresh_from_db()
    assert is_tombstone(tombstone)


def test_a_refused_edit_is_audited_with_its_reason(
    admin_client: APIClient, tombstone: User, audit_log: pytest.LogCaptureFixture
) -> None:
    """The refusal is an ``account.update`` line ending in ``reason=tombstone``."""
    admin_client.patch(_record_url(tombstone), {"first_name": "Rosa"}, format="json")

    [line] = [line for line in audit_messages(audit_log) if "account.update" in line]
    assert line.endswith("reason=tombstone")


def test_editing_a_tombstone_from_the_users_admin_is_refused(
    admin_client: APIClient, tombstone: User
) -> None:
    """The user record's ``PATCH`` refuses a tombstone the same way."""
    response = admin_client.patch(
        f"/api/v1/admin/users/{tombstone.pk}", {"roles": [MEMBER]}, format="json"
    )

    assert (response.status_code, response.json()) == (400, REFUSED)


def test_deleting_a_tombstone_is_refused(admin_client: APIClient, tombstone: User) -> None:
    """``DELETE`` is a 400 carrying the reason."""
    response = admin_client.delete(_record_url(tombstone))

    assert (response.status_code, response.json()) == (400, REFUSED)


def test_a_refused_delete_keeps_the_payments_on_the_tombstone(
    admin_client: APIClient, tombstone: User
) -> None:
    """The gift stays where it was, and no second tombstone is made."""
    admin_client.delete(_record_url(tombstone))

    assert list(Payment.objects.values_list("user_id", flat=True)) == [tombstone.pk]


def test_a_refused_delete_is_audited_with_its_reason(
    admin_client: APIClient, tombstone: User, audit_log: pytest.LogCaptureFixture
) -> None:
    """The refusal is a ``member.delete`` line ending in ``reason=tombstone``."""
    admin_client.delete(_record_url(tombstone))

    [line] = [line for line in audit_messages(audit_log) if "member.delete" in line]
    assert line.endswith("reason=tombstone")


def test_granting_a_tombstone_a_term_is_refused(
    admin_client: APIClient, tombstone: User, annual_plan: MembershipPlan
) -> None:
    """A grant is a 400 carrying the tombstone's reason, not the donor's."""
    response = admin_client.post(
        f"{_record_url(tombstone)}/memberships", {"plan": annual_plan.slug}, format="json"
    )

    assert (response.status_code, response.json()) == (400, REFUSED)


def test_a_refused_grant_writes_no_term_on_the_tombstone(
    admin_client: APIClient, tombstone: User, annual_plan: MembershipPlan
) -> None:
    """The tombstone holds no term after the refusal."""
    admin_client.post(
        f"{_record_url(tombstone)}/memberships", {"plan": annual_plan.slug}, format="json"
    )

    assert not Membership.objects.filter(user=tombstone).exists()


def test_a_donor_who_is_not_a_tombstone_may_still_be_deleted(admin_client: APIClient) -> None:
    """The guard reads ``is_tombstone``, not the kind: a living donor is deleted."""
    donor = UserFactory(email="living@example.test", kind=AccountKind.DONOR)

    assert admin_client.delete(_record_url(donor)).status_code == 204


# --------------------------------------------------------------------------
# The flags the portal reads
# --------------------------------------------------------------------------
def test_the_record_flags_a_tombstone(admin_client: APIClient, tombstone: User) -> None:
    """The member record carries ``is_tombstone`` true."""
    assert admin_client.get(_record_url(tombstone)).json()["is_tombstone"] is True


def test_the_record_does_not_flag_a_member(admin_client: APIClient, member: User) -> None:
    """Anybody else's record carries ``is_tombstone`` false."""
    assert admin_client.get(_record_url(member)).json()["is_tombstone"] is False


def test_the_donors_report_flags_the_tombstones_row(
    admin_client: APIClient, tombstone: User
) -> None:
    """The row for **Deleted member <id>** carries ``is_tombstone`` true."""
    [row] = admin_client.get("/api/v1/admin/payments/donors").json()

    assert row["is_tombstone"] is True


def test_the_payment_list_flags_a_payment_the_tombstone_holds(
    admin_client: APIClient, tombstone: User
) -> None:
    """A payment row carries ``user_is_tombstone`` true for a tombstone's payment."""
    [row] = admin_client.get("/api/v1/admin/payments").json()["results"]

    assert row["user_is_tombstone"] is True


def test_the_ledger_flags_a_tombstone(admin_client: APIClient, tombstone: User) -> None:
    """The ledger's ``user`` carries ``is_tombstone`` true."""
    ledger = admin_client.get(f"/api/v1/admin/payments/ledger/{tombstone.pk}").json()

    assert ledger["user"]["is_tombstone"] is True
