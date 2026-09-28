"""Deleting a member who has payments hands the payments to a tombstone account.

``Payment.user`` is ``PROTECT``, so a payment outlives the account that made it.
``DELETE /admin/members/{user_id}`` deletes a member whatever payments they hold:
the payments move, in the same transaction, to a new *tombstone* account named
**Deleted member <id>**, a deactivated donor that cannot sign in.  The member's
automatic payments are canceled first, and the accounts read the same afterwards.
The Wagtail users admin does the same, one account at a time or in bulk.  An
account that never paid is deleted with no tombstone.
"""

from __future__ import annotations

from collections.abc import Iterable

import pytest
from django.core import mail
from django.db.models import ProtectedError
from django.test import Client
from pytest_django.fixtures import DjangoCaptureOnCommitCallbacks
from rest_framework.test import APIClient

from apps.accounts.models import AccountKind, User
from apps.accounts.roles import ACCOUNT_ADMIN, MEMBER, SYSTEM_ADMIN
from apps.mail.models import EmailLog
from apps.members.models import MemberProfile, Membership, MembershipPlan
from apps.members.services import tombstone_for
from apps.payments.models import MandateStatus, Payment, PaymentStatus, RenewalMandate
from tests.conftest import audit_messages
from tests.factories import (
    MemberProfileFactory,
    MembershipFactory,
    PaymentFactory,
    RefundFactory,
    RenewalMandateFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db

LIST_URL = "/api/v1/admin/members"
PAYMENTS_URL = "/api/v1/admin/payments"
SUMMARY_URL = "/api/v1/admin/payments/summary"
WAGTAIL_DELETE_URL = "/admin/users/delete/{pk}/"
WAGTAIL_BULK_DELETE_URL = "/admin/bulk/accounts/user/delete/"


def detail_url(user: User) -> str:
    """Return the members-admin detail URL for ``user``."""
    return f"{LIST_URL}/{user.pk}"


def bulk_delete_url(users: Iterable[User]) -> str:
    """The Wagtail users listing's bulk ``Delete`` URL, selecting ``users``."""
    selection = "&".join(f"id={user.pk}" for user in users)
    return f"{WAGTAIL_BULK_DELETE_URL}?{selection}"


def tombstone_of(target_id: int) -> User:
    """The tombstone account made for the deleted account ``target_id``."""
    return User.objects.get(email=f"deleted-{target_id}@deleted.invalid")


def audit_lines(audit_log: pytest.LogCaptureFixture, action: str) -> list[str]:
    """Every captured audit message for ``action``, in order."""
    return [line for line in audit_messages(audit_log) if line.startswith(f"action={action} ")]


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


# --------------------------------------------------------------------------
# The payments move
# --------------------------------------------------------------------------
@pytest.mark.parametrize("status_value", PaymentStatus.values)
def test_every_payment_moves_to_the_tombstone_whatever_its_status(
    account_admin_client: APIClient, payer: User, annual_plan: MembershipPlan, status_value: str
) -> None:
    """A payment of any status, pending and failed rows included, is kept and moved."""
    payment = PaymentFactory(user=payer, plan=annual_plan, status=status_value)
    target_id = payer.pk

    assert account_admin_client.delete(detail_url(payer)).status_code == 204
    payment.refresh_from_db()
    assert payment.user_id == tombstone_of(target_id).pk


def test_every_one_of_several_payments_moves(
    account_admin_client: APIClient, payer: User, annual_plan: MembershipPlan
) -> None:
    """All of the member's payments move to the one tombstone."""
    for index in range(3):
        PaymentFactory(user=payer, plan=annual_plan, provider_ref=f"ref-{index}")
    target_id = payer.pk

    account_admin_client.delete(detail_url(payer))

    assert Payment.objects.filter(user=tombstone_of(target_id)).count() == 3


def test_the_account_its_profile_and_its_terms_are_gone(
    account_admin_client: APIClient, payer: User, annual_plan: MembershipPlan
) -> None:
    """The member's own account goes, with the profile and terms it held."""
    PaymentFactory(user=payer, plan=annual_plan)
    target_id = payer.pk

    account_admin_client.delete(detail_url(payer))

    assert not User.objects.filter(pk=target_id).exists()
    assert not MemberProfile.objects.filter(user_id=target_id).exists()
    assert not Membership.objects.filter(user_id=target_id).exists()


def test_a_refund_stays_attached_to_its_payment(
    account_admin_client: APIClient, payer: User, annual_plan: MembershipPlan
) -> None:
    """The refund follows the payment it reverses, which now belongs to the tombstone."""
    payment = PaymentFactory(user=payer, plan=annual_plan, status=PaymentStatus.SUCCEEDED)
    refund = RefundFactory(payment=payment)
    target_id = payer.pk

    account_admin_client.delete(detail_url(payer))

    refund.refresh_from_db()
    assert refund.payment.user_id == tombstone_of(target_id).pk


def test_a_member_who_never_paid_leaves_no_tombstone(
    account_admin_client: APIClient, payer: User
) -> None:
    """Without payments there is nothing to keep, so no tombstone is made."""
    target_id = payer.pk

    assert account_admin_client.delete(detail_url(payer)).status_code == 204
    assert not User.objects.filter(email=f"deleted-{target_id}@deleted.invalid").exists()


# --------------------------------------------------------------------------
# The tombstone
# --------------------------------------------------------------------------
def test_the_tombstone_reads_deleted_member_and_the_old_id(payer: User) -> None:
    """Its display name is ``Deleted member <id>``."""
    assert tombstone_for(payer).display_name == f"Deleted member {payer.pk}"


def test_the_tombstone_is_a_donor(payer: User) -> None:
    """A donor holds no password and no role, so the tombstone cannot sign in."""
    assert tombstone_for(payer).kind == AccountKind.DONOR


def test_the_tombstone_is_deactivated(payer: User) -> None:
    """It stays off every list that shows active accounts."""
    assert tombstone_for(payer).is_active is False


def test_the_tombstone_holds_no_usable_password(payer: User) -> None:
    """Nobody can sign in as the tombstone."""
    assert tombstone_for(payer).has_usable_password() is False


def test_the_tombstone_holds_no_role(payer: User) -> None:
    """Not even the member role that lets an account into the portal."""
    assert tombstone_for(payer).groups.count() == 0


def test_the_tombstone_has_an_undeliverable_address(payer: User) -> None:
    """The address is made from the old id on the reserved ``.invalid`` domain."""
    assert tombstone_for(payer).email == f"deleted-{payer.pk}@deleted.invalid"


def test_the_tombstone_has_a_blank_profile(payer: User) -> None:
    """A blank profile, so every screen that reads a payer's profile finds one."""
    profile = MemberProfile.objects.get(user=tombstone_for(payer))

    assert profile.phone == ""


# --------------------------------------------------------------------------
# Automatic payments
# --------------------------------------------------------------------------
@pytest.mark.parametrize("status_value", [MandateStatus.ACTIVE, MandateStatus.PAUSED])
def test_a_standing_automatic_payment_is_canceled_before_the_delete(
    account_admin_client: APIClient,
    account_admin: User,
    payer: User,
    annual_plan: MembershipPlan,
    audit_log: pytest.LogCaptureFixture,
    status_value: str,
) -> None:
    """The cancellation is recorded, with the delete as its reason."""
    PaymentFactory(user=payer, plan=annual_plan)
    RenewalMandateFactory(user=payer, plan=annual_plan, status=status_value)
    target_id = payer.pk

    account_admin_client.delete(detail_url(payer))

    assert audit_lines(audit_log, "renewal.cancel") == [
        f"action=renewal.cancel actor={account_admin.pk} target={target_id} "
        "provider=mock self_service=false reason=member.delete"
    ]


def test_the_mandates_go_with_the_account(
    account_admin_client: APIClient, payer: User, annual_plan: MembershipPlan
) -> None:
    """Once canceled, the mandate is deleted along with the account it belonged to."""
    PaymentFactory(user=payer, plan=annual_plan)
    RenewalMandateFactory(user=payer, plan=annual_plan)
    target_id = payer.pk

    account_admin_client.delete(detail_url(payer))

    assert not RenewalMandate.objects.filter(user_id=target_id).exists()


def test_the_member_is_told_their_automatic_payment_is_off(
    account_admin_client: APIClient,
    payer: User,
    annual_plan: MembershipPlan,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """The cancellation email goes to the member's address after the delete commits."""
    PaymentFactory(user=payer, plan=annual_plan)
    RenewalMandateFactory(user=payer, plan=annual_plan)

    with django_capture_on_commit_callbacks(execute=True):
        account_admin_client.delete(detail_url(payer))

    assert [message.to for message in mail.outbox] == [["payer@example.test"]]


def test_the_email_log_keeps_the_message_without_the_deleted_account(
    account_admin_client: APIClient,
    payer: User,
    annual_plan: MembershipPlan,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """The log row is written after the account is gone, so it names no account."""
    PaymentFactory(user=payer, plan=annual_plan)
    RenewalMandateFactory(user=payer, plan=annual_plan)

    with django_capture_on_commit_callbacks(execute=True):
        account_admin_client.delete(detail_url(payer))

    row = EmailLog.objects.get(to_email="payer@example.test")
    assert row.user_id is None


def test_a_canceled_mandate_is_not_canceled_again(
    account_admin_client: APIClient,
    payer: User,
    annual_plan: MembershipPlan,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """An authority already withdrawn needs nothing more."""
    PaymentFactory(user=payer, plan=annual_plan)
    RenewalMandateFactory(user=payer, plan=annual_plan, status=MandateStatus.CANCELED)

    account_admin_client.delete(detail_url(payer))

    assert audit_lines(audit_log, "renewal.cancel") == []


# --------------------------------------------------------------------------
# The audit line
# --------------------------------------------------------------------------
def test_the_audit_line_counts_the_payments_and_names_their_owner(
    account_admin_client: APIClient,
    account_admin: User,
    payer: User,
    annual_plan: MembershipPlan,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """``payments`` is how many moved, ``owner`` the tombstone they moved to."""
    PaymentFactory(user=payer, plan=annual_plan, provider_ref="one")
    PaymentFactory(user=payer, plan=annual_plan, provider_ref="two")
    target_id = payer.pk

    account_admin_client.delete(detail_url(payer))

    assert audit_lines(audit_log, "member.delete") == [
        f"action=member.delete actor={account_admin.pk} target={target_id} "
        f"payments=2 owner={tombstone_of(target_id).pk}"
    ]


def test_the_audit_line_of_a_member_who_never_paid_carries_no_owner(
    account_admin_client: APIClient,
    account_admin: User,
    payer: User,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """Nothing moved, so the line names only the actor and the target."""
    target_id = payer.pk

    account_admin_client.delete(detail_url(payer))

    assert audit_lines(audit_log, "member.delete") == [
        f"action=member.delete actor={account_admin.pk} target={target_id}"
    ]


# --------------------------------------------------------------------------
# The refusals that remain
# --------------------------------------------------------------------------
def test_the_self_delete_guard_still_applies_to_a_payer(
    api_client: APIClient, annual_plan: MembershipPlan
) -> None:
    """An administrator with payments is refused for being themselves."""
    admin = UserFactory(email="selfpayer@example.test", roles=[MEMBER, ACCOUNT_ADMIN])
    PaymentFactory(user=admin, plan=annual_plan)
    api_client.force_login(admin)

    response = api_client.delete(detail_url(admin))

    assert response.json()["detail"] == "You cannot delete your own account."


def test_a_refused_delete_moves_nothing(api_client: APIClient, annual_plan: MembershipPlan) -> None:
    """A refusal writes nothing: the payments stay with the account."""
    admin = UserFactory(email="selfpayer@example.test", roles=[MEMBER, ACCOUNT_ADMIN])
    payment = PaymentFactory(user=admin, plan=annual_plan)
    api_client.force_login(admin)

    api_client.delete(detail_url(admin))

    payment.refresh_from_db()
    assert payment.user_id == admin.pk


def test_the_database_still_protects_a_payment_from_a_raw_delete(
    payer: User, annual_plan: MembershipPlan
) -> None:
    """``PROTECT`` guards every path that does not hand the payments over first."""
    payment = PaymentFactory(user=payer, plan=annual_plan)

    with pytest.raises(ProtectedError, match=r"'Payment\.user'"):
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
# The reports
# --------------------------------------------------------------------------
def test_the_payment_summary_is_unchanged_by_the_delete(
    account_admin_client: APIClient, payer: User, annual_plan: MembershipPlan
) -> None:
    """The accounts read exactly as they did: the money is still in the books."""
    PaymentFactory(
        user=payer,
        plan=annual_plan,
        amount_cents=6_500,
        plan_amount_cents=4_500,
        contribution_cents=2_000,
        status=PaymentStatus.SUCCEEDED,
    )
    before = account_admin_client.get(SUMMARY_URL).json()

    account_admin_client.delete(detail_url(payer))

    assert account_admin_client.get(SUMMARY_URL).json() == before


def test_the_payment_list_names_the_tombstone_as_the_payer(
    account_admin_client: APIClient, payer: User, annual_plan: MembershipPlan
) -> None:
    """The payment list shows **Deleted member <id>** where the member's name was."""
    PaymentFactory(user=payer, plan=annual_plan)
    target_id = payer.pk

    account_admin_client.delete(detail_url(payer))

    rows = account_admin_client.get(PAYMENTS_URL).json()["results"]
    assert [row["user_name"] for row in rows] == [f"Deleted member {target_id}"]


def test_the_member_list_does_not_show_the_tombstone(
    account_admin_client: APIClient, payer: User, annual_plan: MembershipPlan
) -> None:
    """A deactivated donor is on none of the lists of people."""
    PaymentFactory(user=payer, plan=annual_plan)
    target_id = payer.pk

    account_admin_client.delete(detail_url(payer))

    emails = [row["email"] for row in account_admin_client.get(LIST_URL).json()["results"]]
    assert tombstone_of(target_id).email not in emails


# --------------------------------------------------------------------------
# The Wagtail admin
# --------------------------------------------------------------------------
def test_the_wagtail_admin_deletes_an_account_with_payments(
    wagtail_client: Client, payer: User, annual_plan: MembershipPlan
) -> None:
    """The users admin deletes the account rather than turning the delete back."""
    PaymentFactory(user=payer, plan=annual_plan)
    target_id = payer.pk

    assert wagtail_client.post(WAGTAIL_DELETE_URL.format(pk=target_id)).status_code == 302
    assert not User.objects.filter(pk=target_id).exists()


def test_the_wagtail_admin_hands_the_payments_to_the_tombstone(
    wagtail_client: Client, payer: User, annual_plan: MembershipPlan
) -> None:
    """The same tombstone the API makes keeps the payments."""
    payment = PaymentFactory(user=payer, plan=annual_plan)
    target_id = payer.pk

    wagtail_client.post(WAGTAIL_DELETE_URL.format(pk=target_id))

    payment.refresh_from_db()
    assert payment.user_id == tombstone_of(target_id).pk


def test_the_wagtail_confirmation_page_moves_nothing(
    wagtail_client: Client, payer: User, annual_plan: MembershipPlan
) -> None:
    """Only the confirmed delete moves the payments; opening the page does not."""
    payment = PaymentFactory(user=payer, plan=annual_plan)

    response = wagtail_client.get(WAGTAIL_DELETE_URL.format(pk=payer.pk))

    payment.refresh_from_db()
    assert response.status_code == 200
    assert payment.user_id == payer.pk


def test_the_wagtail_delete_is_recorded_with_the_owner(
    wagtail_client: Client,
    superuser: User,
    payer: User,
    annual_plan: MembershipPlan,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """The users admin writes the same ``member.delete`` line the API writes."""
    PaymentFactory(user=payer, plan=annual_plan)
    target_id = payer.pk

    wagtail_client.post(WAGTAIL_DELETE_URL.format(pk=target_id))

    assert audit_lines(audit_log, "member.delete") == [
        f"action=member.delete actor={superuser.pk} target={target_id} "
        f"payments=1 owner={tombstone_of(target_id).pk}"
    ]


def test_the_wagtail_admin_deletes_an_account_that_never_paid(
    wagtail_client: Client, payer: User
) -> None:
    """An account the ledger does not hold goes with no tombstone."""
    target_id = payer.pk

    assert wagtail_client.post(WAGTAIL_DELETE_URL.format(pk=target_id)).status_code == 302
    assert not User.objects.filter(email=f"deleted-{target_id}@deleted.invalid").exists()


def test_the_wagtail_bulk_delete_deletes_every_account(
    wagtail_client: Client, payer: User, annual_plan: MembershipPlan
) -> None:
    """A batch holding a payer goes through whole."""
    PaymentFactory(user=payer, plan=annual_plan)
    bystander = UserFactory(email="bystander@example.test")
    ids = [payer.pk, bystander.pk]

    assert wagtail_client.post(bulk_delete_url([payer, bystander])).status_code == 302
    assert not User.objects.filter(pk__in=ids).exists()


def test_the_wagtail_bulk_delete_gives_each_payer_a_tombstone(
    wagtail_client: Client, annual_plan: MembershipPlan
) -> None:
    """Every payer in the batch gets their own tombstone, named for their own id."""
    first = UserFactory(email="first@example.test")
    second = UserFactory(email="second@example.test")
    PaymentFactory(user=first, plan=annual_plan, provider_ref="first")
    PaymentFactory(user=second, plan=annual_plan, provider_ref="second")
    ids = [first.pk, second.pk]

    wagtail_client.post(bulk_delete_url([first, second]))

    owners = sorted(Payment.objects.values_list("user__last_name", flat=True))
    assert owners == sorted(str(pk) for pk in ids)


def test_the_wagtail_bulk_delete_is_recorded_per_account(
    wagtail_client: Client,
    superuser: User,
    payer: User,
    annual_plan: MembershipPlan,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """One ``member.delete`` line per account; only a payer's line names an owner."""
    PaymentFactory(user=payer, plan=annual_plan)
    bystander = UserFactory(email="bystander@example.test")
    payer_id, bystander_id = payer.pk, bystander.pk

    wagtail_client.post(bulk_delete_url([payer, bystander]))

    assert sorted(audit_lines(audit_log, "member.delete")) == sorted(
        [
            f"action=member.delete actor={superuser.pk} target={payer_id} "
            f"payments=1 owner={tombstone_of(payer_id).pk}",
            f"action=member.delete actor={superuser.pk} target={bystander_id}",
        ]
    )
