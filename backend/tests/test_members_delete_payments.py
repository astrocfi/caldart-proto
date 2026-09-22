"""Deleting a member never deletes their payments.

``Payment.user`` is ``PROTECT``, so a payment outlives the account that made it.
``DELETE /admin/members/{user_id}`` refuses a member who has any payment,
whatever its status, and the accounts reports read the same before and after a
refusal.  The Wagtail users admin refuses the same delete, one account at a time
or in bulk, rather than raising a server error.  An account that never paid is
still hard-deleted, profile and membership terms included.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

import pytest
from django.contrib.messages import get_messages
from django.db.models import ProtectedError
from django.test import Client
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import ACCOUNT_ADMIN, MEMBER, SYSTEM_ADMIN
from apps.members.models import MemberProfile, Membership, MembershipPlan
from apps.payments.models import Payment, PaymentStatus
from apps.payments.wagtail_hooks import MAX_REFUSALS_SHOWN
from tests.factories import (
    MemberProfileFactory,
    MembershipFactory,
    PaymentFactory,
    UserFactory,
)

if TYPE_CHECKING:
    # django.test.Client.post() and .get() are typed to return this class, but it
    # exists only in the stub: Django monkey-patches the WSGI response at runtime
    # rather than defining a real subclass.
    from django.test.client import _MonkeyPatchedWSGIResponse as DjangoResponse

pytestmark = pytest.mark.django_db

LIST_URL = "/api/v1/admin/members"
SUMMARY_URL = "/api/v1/admin/payments/summary"
WAGTAIL_DELETE_URL = "/admin/users/delete/{pk}/"
WAGTAIL_BULK_DELETE_URL = "/admin/bulk/accounts/user/delete/"

REFUSAL_ONE_PAYMENT = (
    "Ana Bracco has 1 payment record, which must be kept. Deactivate the account instead."
)
REFUSAL_THREE_PAYMENTS = (
    "Ana Bracco has 3 payment records, which must be kept. Deactivate the account instead."
)


def detail_url(user: User) -> str:
    """Return the members-admin detail URL for ``user``."""
    return f"{LIST_URL}/{user.pk}"


def bulk_delete_url(users: Iterable[User]) -> str:
    """The Wagtail users listing's bulk ``Delete`` URL, selecting ``users``."""
    selection = "&".join(f"id={user.pk}" for user in users)
    return f"{WAGTAIL_BULK_DELETE_URL}?{selection}"


def admin_messages(response: DjangoResponse) -> list[str]:
    """The Wagtail admin messages queued on ``response``, rendered."""
    return [str(message) for message in get_messages(response.wsgi_request)]


@pytest.fixture
def payer(db: None, annual_plan: MembershipPlan) -> User:
    """A plain member, Ana Bracco, with a profile and a membership term."""
    user = UserFactory(email="payer@example.test", first_name="Ana", last_name="Bracco")
    MemberProfileFactory(user=user, phone="415-555-0100")
    MembershipFactory(user=user, plan=annual_plan)
    return user


@pytest.fixture
def wagtail_client(client: Client, superuser: User) -> Client:
    """The Wagtail admin as a superuser, the only role that may delete a user there."""
    client.force_login(superuser)
    return client


@pytest.fixture
def crowded_batch(db: None, annual_plan: MembershipPlan) -> list[User]:
    """Two more paying accounts than a refused bulk delete names one by one."""
    users = []
    for index in range(MAX_REFUSALS_SHOWN + 2):
        user = UserFactory(email=f"payer{index}@example.test")
        PaymentFactory(user=user, plan=annual_plan, provider_ref=f"bulk-{index}")
        users.append(user)
    return users


# --------------------------------------------------------------------------
# The refusal
# --------------------------------------------------------------------------
@pytest.mark.parametrize("status_value", PaymentStatus.values)
def test_delete_is_refused_whatever_the_payment_status(
    account_admin_client: APIClient, payer: User, annual_plan: MembershipPlan, status_value: str
) -> None:
    """A single payment blocks the delete, pending or failed rows included."""
    payment = PaymentFactory(user=payer, plan=annual_plan, status=status_value)

    response = account_admin_client.delete(detail_url(payer))

    assert response.status_code == 403
    assert response.json()["detail"] == REFUSAL_ONE_PAYMENT
    assert User.objects.filter(pk=payer.pk).exists()
    assert Payment.objects.filter(pk=payment.pk).exists()


def test_the_refusal_counts_every_payment(
    account_admin_client: APIClient, payer: User, annual_plan: MembershipPlan
) -> None:
    """The message names the number of rows, pluralized."""
    for index in range(3):
        PaymentFactory(user=payer, plan=annual_plan, provider_ref=f"ref-{index}")

    response = account_admin_client.delete(detail_url(payer))

    assert response.json()["detail"] == REFUSAL_THREE_PAYMENTS


def test_the_refusal_keeps_the_profile_and_the_membership_terms(
    account_admin_client: APIClient, payer: User, annual_plan: MembershipPlan
) -> None:
    """A refused delete leaves the profile and every membership term in place."""
    PaymentFactory(user=payer, plan=annual_plan)

    assert account_admin_client.delete(detail_url(payer)).status_code == 403
    assert MemberProfile.objects.filter(user_id=payer.pk).exists()
    assert Membership.objects.filter(user_id=payer.pk).count() == 1


def test_a_system_admin_is_refused_too(
    api_client: APIClient, system_admin: User, payer: User, annual_plan: MembershipPlan
) -> None:
    """The guard is about the records, not about the caller's privilege."""
    PaymentFactory(user=payer, plan=annual_plan)
    api_client.force_login(system_admin)

    response = api_client.delete(detail_url(payer))

    assert response.status_code == 403
    assert response.json()["detail"] == REFUSAL_ONE_PAYMENT


def test_the_self_delete_guard_still_comes_first(
    api_client: APIClient, annual_plan: MembershipPlan
) -> None:
    """An administrator with payments is refused for being themselves."""
    admin = UserFactory(
        email="selfpayer@example.test",
        first_name="Cyd",
        last_name="Ng",
        roles=[MEMBER, ACCOUNT_ADMIN],
    )
    PaymentFactory(user=admin, plan=annual_plan)
    api_client.force_login(admin)

    response = api_client.delete(detail_url(admin))

    assert response.json()["detail"] == "You cannot delete your own account."


# --------------------------------------------------------------------------
# The reports are untouched
# --------------------------------------------------------------------------
def test_the_payment_summary_is_unchanged_after_a_refusal(
    account_admin_client: APIClient, payer: User, annual_plan: MembershipPlan
) -> None:
    """A refused delete leaves the accounts reading exactly as they did."""
    PaymentFactory(
        user=payer,
        plan=annual_plan,
        amount_cents=6_500,
        plan_amount_cents=4_500,
        contribution_cents=2_000,
        status=PaymentStatus.SUCCEEDED,
    )
    before = account_admin_client.get(SUMMARY_URL).json()

    assert account_admin_client.delete(detail_url(payer)).status_code == 403

    after = account_admin_client.get(SUMMARY_URL).json()
    assert after == before
    assert len(after) == 1
    assert after[0]["total_cents"] == 6_500
    assert after[0]["contribution_cents"] == 2_000


# --------------------------------------------------------------------------
# A member who never paid
# --------------------------------------------------------------------------
def test_a_member_without_payments_is_deleted_with_the_profile_and_terms(
    account_admin_client: APIClient, payer: User
) -> None:
    """An account with no payments is hard-deleted, along with its profile and terms."""
    pk = payer.pk

    assert account_admin_client.delete(detail_url(payer)).status_code == 204
    assert not User.objects.filter(pk=pk).exists()
    assert not MemberProfile.objects.filter(user_id=pk).exists()
    assert not Membership.objects.filter(user_id=pk).exists()


# --------------------------------------------------------------------------
# The database itself
# --------------------------------------------------------------------------
def test_the_model_refuses_the_delete_and_keeps_the_payment(
    payer: User, annual_plan: MembershipPlan
) -> None:
    """``PROTECT`` guards every path, the Django admin and a shell included."""
    payment = PaymentFactory(user=payer, plan=annual_plan)

    with pytest.raises(ProtectedError, match=r"referenced through protected foreign keys"):
        payer.delete()

    assert Payment.objects.filter(pk=payment.pk).exists()


def test_a_system_admin_role_does_not_bypass_the_database_guard(
    annual_plan: MembershipPlan,
) -> None:
    """The protection is on the foreign key, so no role escapes it."""
    root = UserFactory(email="root-payer@example.test", roles=[MEMBER, SYSTEM_ADMIN])
    PaymentFactory(user=root, plan=annual_plan)

    with pytest.raises(ProtectedError, match=r"'Payment\.user'"):
        root.delete()


# --------------------------------------------------------------------------
# The Wagtail admin
# --------------------------------------------------------------------------
def test_the_wagtail_admin_refuses_the_delete(
    wagtail_client: Client, payer: User, annual_plan: MembershipPlan
) -> None:
    """The users admin turns the delete back rather than raising a server error."""
    payment = PaymentFactory(user=payer, plan=annual_plan)

    response = wagtail_client.post(WAGTAIL_DELETE_URL.format(pk=payer.pk))

    assert response.status_code == 302
    assert User.objects.filter(pk=payer.pk).exists()
    assert Payment.objects.filter(pk=payment.pk).exists()


def test_the_wagtail_admin_explains_the_refusal(
    wagtail_client: Client, payer: User, annual_plan: MembershipPlan
) -> None:
    """The operator reads the same sentence the API answers with."""
    PaymentFactory(user=payer, plan=annual_plan)

    response = wagtail_client.post(WAGTAIL_DELETE_URL.format(pk=payer.pk))

    assert REFUSAL_ONE_PAYMENT in admin_messages(response)[0]


def test_the_wagtail_delete_page_refuses_before_it_is_confirmed(
    wagtail_client: Client, payer: User, annual_plan: MembershipPlan
) -> None:
    """A protected account never reaches the confirmation form."""
    PaymentFactory(user=payer, plan=annual_plan)

    response = wagtail_client.get(WAGTAIL_DELETE_URL.format(pk=payer.pk))

    assert response.status_code == 302


def test_the_wagtail_admin_deletes_an_account_that_never_paid(
    wagtail_client: Client, payer: User
) -> None:
    """The guard is silent about an account the ledger does not hold."""
    pk = payer.pk

    assert wagtail_client.post(WAGTAIL_DELETE_URL.format(pk=pk)).status_code == 302
    assert not User.objects.filter(pk=pk).exists()


def test_the_wagtail_bulk_delete_refuses_the_whole_batch(
    wagtail_client: Client, payer: User, annual_plan: MembershipPlan
) -> None:
    """One protected account keeps every account in the batch: the delete is one query."""
    PaymentFactory(user=payer, plan=annual_plan)
    bystander = UserFactory(email="bystander@example.test")

    response = wagtail_client.post(bulk_delete_url([payer, bystander]))

    assert response.status_code == 302
    assert User.objects.filter(pk=payer.pk).exists()
    assert User.objects.filter(pk=bystander.pk).exists()


def test_the_wagtail_bulk_delete_names_the_account_that_refused(
    wagtail_client: Client, payer: User, annual_plan: MembershipPlan
) -> None:
    """The batch's error message says which account must be kept, and why."""
    PaymentFactory(user=payer, plan=annual_plan)
    bystander = UserFactory(email="bystander@example.test")

    response = wagtail_client.post(bulk_delete_url([payer, bystander]))

    assert REFUSAL_ONE_PAYMENT in admin_messages(response)[0]


def test_the_wagtail_bulk_delete_caps_the_accounts_it_names(
    wagtail_client: Client, crowded_batch: list[User]
) -> None:
    """Selecting a whole listing cannot bury the admin in one banner per account."""
    response = wagtail_client.post(bulk_delete_url(crowded_batch))

    assert len(admin_messages(response)) == MAX_REFUSALS_SHOWN + 1


def test_the_wagtail_bulk_delete_counts_the_accounts_it_did_not_name(
    wagtail_client: Client, crowded_batch: list[User]
) -> None:
    """The closing banner counts the protected accounts the named ones left out."""
    response = wagtail_client.post(bulk_delete_url(crowded_batch))

    assert (
        "2 further selected accounts hold payment records, which must be kept. "
        "Deactivate the accounts instead." in admin_messages(response)[-1]
    )


def test_the_wagtail_bulk_delete_still_deletes_accounts_that_never_paid(
    wagtail_client: Client, payer: User
) -> None:
    """A batch the ledger does not hold goes through untouched."""
    pk = payer.pk

    assert wagtail_client.post(bulk_delete_url([payer])).status_code == 302
    assert not User.objects.filter(pk=pk).exists()
