"""Every service raises its notification event once, where the thing happened.

A recording handler subscribes through ``caldart.events`` for the length of each
test, so what a service raised is read back as ``(slug, payload)`` pairs whatever
the notifications app does with them.  The catalog of events, where each is
raised, and what each payload carries is ``docs/developer/notification-events.rst``.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator, Mapping
from datetime import date, timedelta

import pytest
from django.core.mail import EmailMessage
from django.utils import timezone
from pytest_django.fixtures import DjangoCaptureOnCommitCallbacks, Settings
from rest_framework.test import APIClient

from apps.accounts.models import AccountKind, User
from apps.accounts.roles import DART_LEADER, MEMBER
from apps.accounts.services import (
    make_email_verification_token,
    update_account,
    verify_email,
)
from apps.aircraft.models import Aircraft
from apps.darts.models import Dart
from apps.members.labels import profile_field_label
from apps.members.lifecycle import become_friend, convert_due_friends, expire_lapsed_memberships
from apps.members.models import (
    MemberProfile,
    Membership,
    MembershipPlan,
    MembershipSource,
    MembershipStatusChoices,
)
from apps.members.services import (
    activate_term,
    register_member,
    update_member,
)
from apps.payments import refunds
from apps.payments.manual import record_manual_payment
from apps.payments.models import (
    MandateStatus,
    Payment,
    PaymentProvider,
    PaymentStatus,
    PaymentWallet,
    Refund,
    RefundReason,
    RenewalMandate,
)
from apps.payments.providers.base import ProviderUnavailableError
from apps.payments.providers.mock import (
    DECLINED_LAST4,
    DECLINED_MESSAGE,
    MockProvider,
    mock_method,
)
from apps.payments.renewals import RETRY_OFFSETS, cancel_mandate, run_auto_renewals, save_method
from apps.payments.services import mark_succeeded
from apps.reminders.services import send_renewal_reminders
from caldart import events
from tests.factories import (
    DEFAULT_PASSWORD,
    AircraftFactory,
    AircraftTypeFactory,
    MemberProfileFactory,
    MembershipFactory,
    PaymentFactory,
    RenewalMandateFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db

type Recorded = list[tuple[str, Mapping[str, object]]]

#: The address a joiner registers with.
NEWCOMER = "newcomer@example.test"

#: A ``PATCH /me/profile`` body that fills every field a complete profile needs.
COMPLETE_PROFILE = {
    "phone": "408-555-0134",
    "address_line1": "12 Runway Road",
    "city": "San Jose",
    "state": "CA",
    "postal_code": "95110",
    "pilot_certificate_type": "none",
}

#: What a verification link carries after ``token=``.
TOKEN_RE = re.compile(r"token=([^\s\"&<]+)")


@pytest.fixture
def recorded() -> Iterator[Recorded]:
    """Every event raised while the test runs, as ``(slug, payload)`` pairs."""
    seen: Recorded = []

    def record(slug: str, payload: Mapping[str, object]) -> None:
        seen.append((slug, dict(payload)))

    events.subscribe(record)
    yield seen
    events.unsubscribe(record)


@pytest.fixture(autouse=True)
def _mock_enabled(settings: Settings) -> None:
    """Enable the mock provider, which takes and refunds every payment here."""
    settings.PAYMENTS_MOCK_ENABLED = True


def raised(recorded: Recorded, slug: str) -> list[Mapping[str, object]]:
    """The payloads of every ``slug`` event recorded, in the order they were raised."""
    return [payload for name, payload in recorded if name == slug]


def current_term(user: User, plan: MembershipPlan, today: date) -> Membership:
    """Give ``user`` an active term on ``plan`` that ends on ``today``."""
    return MembershipFactory(
        user=user,
        plan=plan,
        starts_on=today - timedelta(days=364),
        ends_on=today,
        status=MembershipStatusChoices.ACTIVE,
    )


# --------------------------------------------------------------------------
# signed_up
# --------------------------------------------------------------------------
def register(api_client: APIClient, email: str = NEWCOMER) -> User:
    """Register ``email`` as a friend through ``POST /auth/register``, signed in.

    The address is then marked verified, as following the link would, since the join
    wizard's profile step and the API behind it open only to a verified address.
    """
    response = api_client.post(
        "/api/v1/auth/register",
        {
            "email": email,
            "password": DEFAULT_PASSWORD,
            "first_name": "Nell",
            "last_name": "Holt",
            "kind": "friend",
        },
    )
    assert response.status_code == 201
    User.objects.filter(email=email).update(email_verified_at=timezone.now())
    return User.objects.get(email=email)


def test_registering_raises_nothing_until_the_join_is_complete(
    api_client: APIClient, recorded: Recorded
) -> None:
    """The account alone is not a sign-up: the join wizard has not asked for the DART."""
    register(api_client)

    assert recorded == []


def test_completing_the_join_profile_raises_signed_up_with_the_chosen_dart(
    api_client: APIClient, recorded: Recorded, dart: Dart
) -> None:
    """The profile save that completes the join raises ``signed_up`` with its DART."""
    user = register(api_client)

    response = api_client.patch(
        "/api/v1/me/profile", {**COMPLETE_PROFILE, "dart_id": dart.pk}, format="json"
    )

    assert response.status_code == 200
    assert recorded == [("signed_up", {"user": user, "dart": dart})]


def test_completing_the_join_profile_with_no_dart_raises_signed_up_with_none(
    api_client: APIClient, recorded: Recorded
) -> None:
    """A joiner who picks no DART still signs up, with ``dart=None``."""
    user = register(api_client)

    api_client.patch("/api/v1/me/profile", COMPLETE_PROFILE, format="json")

    assert raised(recorded, "signed_up") == [{"user": user, "dart": None}]


def test_a_partial_join_profile_raises_neither_signed_up_nor_a_profile_change(
    api_client: APIClient, recorded: Recorded
) -> None:
    """A save that leaves the profile incomplete is the join still under way."""
    register(api_client)

    response = api_client.patch("/api/v1/me/profile", {"phone": "408-555-0134"}, format="json")

    assert response.status_code == 200
    assert recorded == []


def test_editing_a_complete_profile_raises_no_signed_up(
    api_client: APIClient, member: User, profile: MemberProfile, recorded: Recorded
) -> None:
    """A member whose profile was complete already joined long ago."""
    api_client.force_login(member)

    api_client.patch("/api/v1/me/profile", {"city": "Fresno"}, format="json")

    assert raised(recorded, "signed_up") == []


def test_registering_with_a_donors_address_raises_nothing_yet(recorded: Recorded) -> None:
    """A donor's address waits for the verification link, so nobody has joined yet."""
    UserFactory(email="giver@example.test", kind=AccountKind.DONOR, roles=[])

    register_member(email="giver@example.test", password=DEFAULT_PASSWORD)

    assert raised(recorded, "signed_up") == []


def test_a_donor_verifying_their_registration_raises_no_signed_up_yet(
    recorded: Recorded,
) -> None:
    """The upgraded donor signs up, like anybody, when the join profile is complete."""
    donor = UserFactory(email="giver@example.test", kind=AccountKind.DONOR, roles=[])
    token = make_email_verification_token(
        donor, upgrade={"first_name": "Gil", "last_name": "Ives", "kind": "member"}
    )

    verify_email(token)

    assert raised(recorded, "signed_up") == []


# --------------------------------------------------------------------------
# member_added
# --------------------------------------------------------------------------
def test_an_administrator_adding_a_member_raises_member_added(
    account_admin_client: APIClient, account_admin: User, recorded: Recorded
) -> None:
    """``POST /admin/members`` raises ``member_added`` naming the administrator."""
    response = account_admin_client.post(
        "/api/v1/admin/members",
        {"email": "added@example.test", "first_name": "Ada", "kind": "member"},
        format="json",
    )

    assert response.status_code == 201
    user = User.objects.get(email="added@example.test")
    assert raised(recorded, "member_added") == [{"user": user, "actor": account_admin}]


# --------------------------------------------------------------------------
# became_friend and became_member
# --------------------------------------------------------------------------
def test_a_member_with_no_coverage_becoming_a_friend_raises_chose(
    member: User, recorded: Recorded
) -> None:
    """A member with nothing current is a friend at once, having chosen to be one."""
    become_friend(member)

    assert raised(recorded, "became_friend") == [{"user": member, "how": "chose"}]


def test_a_member_whose_change_waits_for_expiry_raises_nothing_yet(
    member: User, annual_plan: MembershipPlan, today: date, recorded: Recorded
) -> None:
    """A current member stays a member until the coverage runs out."""
    current_term(member, annual_plan, today + timedelta(days=30))

    become_friend(member)

    assert raised(recorded, "became_friend") == []


def test_a_due_conversion_raises_became_friend_as_lapsed(
    member: User, today: date, recorded: Recorded
) -> None:
    """The daily run converting a member whose day has come raises ``lapsed``."""
    member.friend_on = today - timedelta(days=1)
    member.save(update_fields=["friend_on"])

    convert_due_friends(today)

    assert raised(recorded, "became_friend") == [{"user": member, "how": "lapsed"}]


def test_an_administrator_making_a_member_a_friend_raises_administrator(
    user_admin: User, member: User, recorded: Recorded
) -> None:
    """An administrator setting the kind to friend raises ``administrator``."""
    update_account(user_admin, member, {"kind": AccountKind.FRIEND})

    assert raised(recorded, "became_friend") == [{"user": member, "how": "administrator"}]


def test_an_administrator_making_a_friend_a_member_raises_became_member(
    user_admin: User, friend: User, recorded: Recorded
) -> None:
    """An administrator setting the kind to member raises ``administrator``."""
    update_account(user_admin, friend, {"kind": AccountKind.MEMBER})

    assert raised(recorded, "became_member") == [{"user": friend, "how": "administrator"}]


def test_resending_the_kind_an_account_holds_raises_nothing(
    user_admin: User, member: User, recorded: Recorded
) -> None:
    """An edit that leaves the kind where it was changes nobody's kind."""
    update_account(user_admin, member, {"kind": AccountKind.MEMBER})

    assert recorded == []


def test_a_friend_paying_raises_became_member_as_paid(
    friend: User, annual_plan: MembershipPlan, recorded: Recorded
) -> None:
    """A friend whose payment buys a term becomes a member by paying."""
    mark_succeeded(PaymentFactory(user=friend, plan=annual_plan))

    assert raised(recorded, "became_member") == [{"user": friend, "how": "paid"}]


def test_a_friend_granted_a_term_raises_became_member_as_granted(
    friend: User, annual_plan: MembershipPlan, account_admin: User, recorded: Recorded
) -> None:
    """A friend given a term by hand becomes a member by the grant."""
    activate_term(friend, annual_plan, source=MembershipSource.MANUAL, granted_by=account_admin)

    assert raised(recorded, "became_member") == [{"user": friend, "how": "granted"}]


def test_a_member_renewing_raises_no_became_member(
    member: User, annual_plan: MembershipPlan, recorded: Recorded
) -> None:
    """A member already stored as one does not become one again."""
    mark_succeeded(PaymentFactory(user=member, plan=annual_plan))

    assert raised(recorded, "became_member") == []


# --------------------------------------------------------------------------
# membership_paid and donation_received
# --------------------------------------------------------------------------
def test_a_membership_payment_raises_membership_paid(
    member: User, annual_plan: MembershipPlan, recorded: Recorded
) -> None:
    """A payment that buys a term raises ``membership_paid`` with that term."""
    payment = mark_succeeded(PaymentFactory(user=member, plan=annual_plan))

    term = Membership.objects.get(payment=payment)
    assert raised(recorded, "membership_paid") == [
        {"payment": payment, "term": term, "automatic": False}
    ]


def test_a_membership_payment_with_a_contribution_raises_no_donation(
    member: User, annual_plan: MembershipPlan, recorded: Recorded
) -> None:
    """The contribution rides on the membership payment's own event."""
    mark_succeeded(
        PaymentFactory(
            user=member,
            plan=annual_plan,
            amount_cents=6_500,
            plan_amount_cents=4_500,
            contribution_cents=2_000,
        )
    )

    assert raised(recorded, "donation_received") == []


def test_a_payment_confirmed_twice_raises_membership_paid_once(
    member: User, annual_plan: MembershipPlan, recorded: Recorded
) -> None:
    """The webhook and the client confirmation racing raise one event between them."""
    payment = PaymentFactory(user=member, plan=annual_plan)

    mark_succeeded(payment)
    mark_succeeded(payment)

    assert len(raised(recorded, "membership_paid")) == 1


def test_a_contribution_raises_donation_received(member: User, recorded: Recorded) -> None:
    """A payment that buys no term is a gift."""
    payment = mark_succeeded(
        PaymentFactory(user=member, plan=None, amount_cents=2_500, plan_amount_cents=0)
    )

    assert raised(recorded, "donation_received") == [{"payment": payment}]


def test_an_automatic_renewal_raises_membership_paid_as_automatic(
    member: User, annual_plan: MembershipPlan, today: date, recorded: Recorded
) -> None:
    """The renewal scanner's charge is flagged as automatic."""
    current_term(member, annual_plan, today)
    RenewalMandateFactory(user=member, plan=annual_plan, next_charge_on=today)

    run_auto_renewals(today=today)

    payment = Payment.objects.get(status=PaymentStatus.SUCCEEDED)
    assert raised(recorded, "membership_paid") == [
        {"payment": payment, "term": Membership.objects.get(payment=payment), "automatic": True}
    ]


def test_a_recurring_donation_charge_raises_donation_received(
    member: User, today: date, recorded: Recorded
) -> None:
    """A recurring donation's charge is a gift like any other."""
    RenewalMandateFactory(user=member, plan=None, contribution_cents=1_500, next_charge_on=today)

    run_auto_renewals(today=today)

    payment = Payment.objects.get(status=PaymentStatus.SUCCEEDED)
    assert raised(recorded, "donation_received") == [{"payment": payment}]


# --------------------------------------------------------------------------
# membership_granted
# --------------------------------------------------------------------------
def test_granting_a_term_raises_membership_granted(
    account_admin_client: APIClient,
    account_admin: User,
    member: User,
    annual_plan: MembershipPlan,
    recorded: Recorded,
) -> None:
    """``POST /admin/members/{id}/memberships`` raises the grant with its term."""
    response = account_admin_client.post(
        f"/api/v1/admin/members/{member.pk}/memberships",
        {"plan": annual_plan.slug, "note": "Volunteer of the year"},
        format="json",
    )

    assert response.status_code == 201
    term = Membership.objects.get(pk=response.json()["id"])
    assert raised(recorded, "membership_granted") == [
        {"user": member, "term": term, "actor": account_admin}
    ]


# --------------------------------------------------------------------------
# membership_expired
# --------------------------------------------------------------------------
def test_a_term_running_out_raises_membership_expired(
    member: User, annual_plan: MembershipPlan, today: date, recorded: Recorded
) -> None:
    """The scan that flips a lapsed term raises one event for its member."""
    term = current_term(member, annual_plan, today - timedelta(days=1))

    expire_lapsed_memberships(today)

    assert raised(recorded, "membership_expired") == [{"user": member, "term": term}]


def test_two_lapsed_terms_raise_one_event_naming_the_later(
    member: User, annual_plan: MembershipPlan, today: date, recorded: Recorded
) -> None:
    """A member is expired once, on the day their last term ran out."""
    current_term(member, annual_plan, today - timedelta(days=400))
    later = current_term(member, annual_plan, today - timedelta(days=2))

    expire_lapsed_memberships(today)

    assert raised(recorded, "membership_expired") == [{"user": member, "term": later}]


def test_a_term_followed_by_a_renewal_raises_no_expiry(
    member: User, annual_plan: MembershipPlan, today: date, recorded: Recorded
) -> None:
    """A renewal bought early carries the member on, so nothing has expired."""
    current_term(member, annual_plan, today - timedelta(days=1))
    MembershipFactory(
        user=member, plan=annual_plan, starts_on=today, ends_on=today + timedelta(days=364)
    )

    expire_lapsed_memberships(today)

    assert raised(recorded, "membership_expired") == []


# --------------------------------------------------------------------------
# auto_renewal_on, auto_renewal_off and auto_renewal_declined
# --------------------------------------------------------------------------
def test_saving_a_method_raises_auto_renewal_on(
    member: User, annual_plan: MembershipPlan, recorded: Recorded
) -> None:
    """A pending mandate made active raises ``auto_renewal_on``."""
    mandate = RenewalMandateFactory(user=member, plan=annual_plan, status=MandateStatus.PENDING)

    save_method(mandate, mock_method(), actor=member)

    assert raised(recorded, "auto_renewal_on") == [{"mandate": mandate}]


def test_replacing_the_card_on_an_active_mandate_raises_nothing(
    member: User, annual_plan: MembershipPlan, recorded: Recorded
) -> None:
    """A mandate already on stays on, so it has not been turned on."""
    mandate = RenewalMandateFactory(user=member, plan=annual_plan)

    save_method(mandate, mock_method(), actor=member)

    assert raised(recorded, "auto_renewal_on") == []


def test_a_member_canceling_raises_auto_renewal_off_as_member(
    member: User, annual_plan: MembershipPlan, recorded: Recorded
) -> None:
    """The member turning their own renewal off is recorded as the member's doing."""
    mandate = RenewalMandateFactory(user=member, plan=annual_plan)

    cancel_mandate(mandate, actor=member)

    assert raised(recorded, "auto_renewal_off") == [{"mandate": mandate, "how": "member"}]


def test_an_administrator_canceling_raises_auto_renewal_off_as_administrator(
    member: User, treasurer: User, annual_plan: MembershipPlan, recorded: Recorded
) -> None:
    """Somebody else turning it off is an administrator's doing."""
    mandate = RenewalMandateFactory(user=member, plan=annual_plan)

    cancel_mandate(mandate, actor=treasurer)

    assert raised(recorded, "auto_renewal_off") == [{"mandate": mandate, "how": "administrator"}]


def test_canceling_a_canceled_mandate_raises_nothing(
    member: User, annual_plan: MembershipPlan, recorded: Recorded
) -> None:
    """A mandate already off is not turned off again."""
    mandate = RenewalMandateFactory(user=member, plan=annual_plan, status=MandateStatus.CANCELED)

    cancel_mandate(mandate, actor=member)

    assert recorded == []


def test_a_mandate_lapsed_too_long_raises_auto_renewal_off_as_lapsed(
    member: User, annual_plan: MembershipPlan, today: date, recorded: Recorded
) -> None:
    """The scanner pausing a mandate whose member lapsed long ago raises ``lapsed``."""
    ended = today - timedelta(days=40)
    current_term(member, annual_plan, ended)
    Membership.objects.filter(user=member).update(status=MembershipStatusChoices.EXPIRED)
    mandate = RenewalMandateFactory(user=member, plan=annual_plan, next_charge_on=ended)

    run_auto_renewals(today=today)

    assert raised(recorded, "auto_renewal_off") == [{"mandate": mandate, "how": "lapsed"}]


def test_deactivating_raises_auto_renewal_off_as_deactivated(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, recorded: Recorded
) -> None:
    """A mandate withdrawn because its member left is recorded as ``deactivated``."""
    mandate = RenewalMandateFactory(user=member, plan=annual_plan)
    api_client.force_login(member)

    api_client.post("/api/v1/auth/deactivate", {"current_password": DEFAULT_PASSWORD})

    assert raised(recorded, "auto_renewal_off") == [{"mandate": mandate, "how": "deactivated"}]


def test_a_declined_charge_raises_auto_renewal_declined(
    member: User, annual_plan: MembershipPlan, today: date, recorded: Recorded
) -> None:
    """A declined renewal names the provider's reason and the day of the next try."""
    current_term(member, annual_plan, today)
    mandate = RenewalMandateFactory(
        user=member, plan=annual_plan, next_charge_on=today, method_last4=DECLINED_LAST4
    )

    run_auto_renewals(today=today)

    assert raised(recorded, "auto_renewal_declined") == [
        {
            "mandate": mandate,
            "reason": DECLINED_MESSAGE,
            "next_on": today + timedelta(days=RETRY_OFFSETS[0]),
        }
    ]


def test_a_final_declined_charge_raises_auto_renewal_declined_with_no_next_try(
    member: User, annual_plan: MembershipPlan, today: date, recorded: Recorded
) -> None:
    """The decline that exhausts the retries pauses the mandate, so no try follows."""
    current_term(member, annual_plan, today)
    mandate = RenewalMandateFactory(
        user=member,
        plan=annual_plan,
        next_charge_on=today,
        method_last4=DECLINED_LAST4,
        failure_count=len(RETRY_OFFSETS),
    )

    run_auto_renewals(today=today)

    assert raised(recorded, "auto_renewal_declined") == [
        {"mandate": mandate, "reason": DECLINED_MESSAGE, "next_on": None}
    ]


def test_canceling_a_paused_mandate_raises_nothing(
    member: User, annual_plan: MembershipPlan, recorded: Recorded
) -> None:
    """A mandate the scanner paused was off already, and said so when it paused."""
    mandate = RenewalMandateFactory(user=member, plan=annual_plan, status=MandateStatus.PAUSED)

    cancel_mandate(mandate, actor=member)

    assert recorded == []


def rehearse_renewals(member: User, plan: MembershipPlan, today: date) -> None:
    """Rehearse the renewal scanner over a mandate whose member lapsed too long ago."""
    ended = today - timedelta(days=40)
    current_term(member, plan, ended)
    Membership.objects.filter(user=member).update(status=MembershipStatusChoices.EXPIRED)
    RenewalMandateFactory(user=member, plan=plan, next_charge_on=ended)
    run_auto_renewals(today=today, dry_run=True)


def rehearse_reminders(member: User, plan: MembershipPlan, today: date) -> None:
    """Rehearse the reminder run over a lapsed term and a friend whose day has come."""
    current_term(member, plan, today - timedelta(days=5))
    UserFactory(email="due@example.test", friend_on=today - timedelta(days=1))
    send_renewal_reminders(today=today, dry_run=True)


@pytest.mark.parametrize(
    "rehearse", [rehearse_renewals, rehearse_reminders], ids=["renewals", "reminders"]
)
def test_a_dry_run_raises_nothing(
    rehearse: Callable[[User, MembershipPlan, date], None],
    member: User,
    annual_plan: MembershipPlan,
    today: date,
    recorded: Recorded,
) -> None:
    """A rehearsal writes nothing, so nothing has happened to tell anybody about."""
    rehearse(member, annual_plan, today)

    assert recorded == []


# --------------------------------------------------------------------------
# payment_recorded and payment_refunded
# --------------------------------------------------------------------------
def test_recording_a_payment_by_hand_raises_payment_recorded(
    member: User, treasurer: User, annual_plan: MembershipPlan, today: date, recorded: Recorded
) -> None:
    """A check a treasurer enters raises ``payment_recorded`` naming the treasurer."""
    payment = record_manual_payment(
        user=member,
        plan_slug=annual_plan.slug,
        contribution_cents=0,
        method=PaymentWallet.CHECK,
        reference="1042",
        received_on=today,
        note="",
        actor=treasurer,
    )

    assert raised(recorded, "payment_recorded") == [{"payment": payment, "actor": treasurer}]


@pytest.fixture
def paid(member: User, annual_plan: MembershipPlan) -> Payment:
    """A succeeded 4,500-cent mock payment for ``annual_plan`` that bought a term."""
    return mark_succeeded(PaymentFactory(user=member, plan=annual_plan))


def test_issuing_a_refund_raises_payment_refunded(
    paid: Payment, treasurer: User, recorded: Recorded
) -> None:
    """A refund the treasurer issues raises the amount and whether the term went."""
    refunds.issue_refund(
        paid,
        amount_cents=4_500,
        reason=RefundReason.REQUESTED_BY_MEMBER,
        actor=treasurer,
        cancel_term=True,
    )

    assert raised(recorded, "payment_refunded") == [
        {"payment": paid, "refund_cents": 4_500, "actor": treasurer, "term_canceled": True}
    ]


def test_a_refund_the_provider_refuses_raises_nothing(
    paid: Payment, treasurer: User, recorded: Recorded, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Money that never went back is not a refund."""

    def refuse(self: MockProvider, payment: Payment, refund: Refund) -> dict[str, object]:
        raise ProviderUnavailableError("The provider could not be reached.")

    monkeypatch.setattr(MockProvider, "refund", refuse)

    with pytest.raises(ProviderUnavailableError, match="could not be reached"):
        refunds.issue_refund(
            paid, amount_cents=1_000, reason=RefundReason.REQUESTED_BY_MEMBER, actor=treasurer
        )

    assert raised(recorded, "payment_refunded") == []


def test_a_dashboard_refund_raises_payment_refunded_with_no_actor(
    paid: Payment, recorded: Recorded
) -> None:
    """A refund taken in the provider's dashboard was issued by nobody CalDART knows."""
    refunds.record_dashboard_refund(paid, amount_cents=1_000, provider_ref="re_1", raw={})

    assert raised(recorded, "payment_refunded") == [
        {"payment": paid, "refund_cents": 1_000, "actor": None, "term_canceled": False}
    ]


def test_a_dashboard_refund_delivered_twice_raises_once(paid: Payment, recorded: Recorded) -> None:
    """The second delivery of one webhook records nothing, and raises nothing."""
    refunds.record_dashboard_refund(paid, amount_cents=1_000, provider_ref="re_1", raw={})
    refunds.record_dashboard_refund(paid, amount_cents=1_000, provider_ref="re_1", raw={})

    assert len(raised(recorded, "payment_refunded")) == 1


# --------------------------------------------------------------------------
# account_deactivated and account_reactivated
# --------------------------------------------------------------------------
def test_deactivating_your_own_account_raises_account_deactivated_with_no_actor(
    api_client: APIClient, member: User, recorded: Recorded
) -> None:
    """A person leaving of their own accord has no administrator behind it."""
    api_client.force_login(member)

    api_client.post("/api/v1/auth/deactivate", {"current_password": DEFAULT_PASSWORD})

    assert raised(recorded, "account_deactivated") == [{"user": member, "actor": None}]


def test_an_administrator_deactivating_raises_account_deactivated(
    user_admin: User, member: User, recorded: Recorded
) -> None:
    """An administrator clearing **Account is active** is named as the actor."""
    update_account(user_admin, member, {"is_active": False})

    assert raised(recorded, "account_deactivated") == [{"user": member, "actor": user_admin}]


def test_reactivating_your_own_account_raises_account_reactivated_with_no_actor(
    api_client: APIClient, member: User, recorded: Recorded
) -> None:
    """``POST /auth/reactivate`` brings the person back of their own accord."""
    member.is_active = False
    member.save(update_fields=["is_active"])

    response = api_client.post(
        "/api/v1/auth/reactivate", {"email": member.email, "password": DEFAULT_PASSWORD}
    )

    assert response.status_code == 200
    assert raised(recorded, "account_reactivated") == [{"user": member, "actor": None}]


def test_an_administrator_reactivating_raises_account_reactivated(
    user_admin: User, member: User, recorded: Recorded
) -> None:
    """An administrator ticking **Account is active** is named as the actor."""
    member.is_active = False
    member.save(update_fields=["is_active"])

    update_account(user_admin, member, {"is_active": True})

    assert raised(recorded, "account_reactivated") == [{"user": member, "actor": user_admin}]


# --------------------------------------------------------------------------
# roles_changed and email_changed
# --------------------------------------------------------------------------
def test_changing_roles_raises_roles_changed(
    user_admin: User, member: User, recorded: Recorded
) -> None:
    """The roles added and removed are named in role order."""
    update_account(user_admin, member, {"roles": [DART_LEADER]})

    assert raised(recorded, "roles_changed") == [
        {"user": member, "added": [DART_LEADER], "removed": [MEMBER], "actor": user_admin}
    ]


def test_resending_the_roles_an_account_holds_raises_nothing(
    user_admin: User, member: User, recorded: Recorded
) -> None:
    """A role list that moves nothing changes nobody's roles."""
    update_account(user_admin, member, {"roles": [MEMBER]})

    assert recorded == []


def mailed_token(mailoutbox: list[EmailMessage]) -> str:
    """The verification token in the last message sent."""
    found = TOKEN_RE.search(str(mailoutbox[-1].body))
    assert found is not None
    return found.group(1)


def test_requesting_a_new_address_raises_nothing_until_it_is_confirmed(
    user_admin: User, member: User, recorded: Recorded
) -> None:
    """An address nobody has proved yet is not a change of address."""
    update_account(user_admin, member, {"email": "moved@example.test"})

    assert recorded == []


def test_confirming_a_changed_address_raises_email_changed(
    user_admin: User,
    member: User,
    recorded: Recorded,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """Following the link mailed to the new address raises it, with the old address."""
    with django_capture_on_commit_callbacks(execute=True):
        update_account(user_admin, member, {"email": "moved@example.test"})

    verify_email(mailed_token(mailoutbox))

    assert raised(recorded, "email_changed") == [
        {"user": member, "old_email": "member@example.test"}
    ]


def test_following_the_link_twice_raises_email_changed_once(
    user_admin: User,
    member: User,
    recorded: Recorded,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """The second visit finds the address verified already."""
    with django_capture_on_commit_callbacks(execute=True):
        update_account(user_admin, member, {"email": "moved@example.test"})
    token = mailed_token(mailoutbox)

    verify_email(token)
    verify_email(token)

    assert len(raised(recorded, "email_changed")) == 1


def test_verifying_a_new_account_raises_no_email_changed(recorded: Recorded, member: User) -> None:
    """A first verification proves the address the account always held."""
    User.objects.filter(pk=member.pk).update(email_verified_at=None)
    member.refresh_from_db()

    verify_email(make_email_verification_token(member))

    assert raised(recorded, "email_changed") == []


def test_changing_only_the_case_of_an_address_raises_nothing(
    user_admin: User, member: User, recorded: Recorded
) -> None:
    """The same address in capitals is the same address."""
    update_account(user_admin, member, {"email": "MEMBER@example.test"})

    assert recorded == []


def test_confirming_your_own_new_address_raises_email_changed(
    api_client: APIClient,
    member: User,
    recorded: Recorded,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """``POST /auth/email/change``, then its link, raises the caller's new address."""
    api_client.force_login(member)
    with django_capture_on_commit_callbacks(execute=True):
        response = api_client.post(
            "/api/v1/auth/email/change",
            {"email": "moved@example.test", "current_password": DEFAULT_PASSWORD},
        )
    assert response.status_code == 200

    verify_email(mailed_token(mailoutbox))

    assert raised(recorded, "email_changed") == [
        {"user": member, "old_email": "member@example.test"}
    ]


# --------------------------------------------------------------------------
# profile_changed
# --------------------------------------------------------------------------
def test_editing_your_own_profile_raises_profile_changed_with_no_actor(
    api_client: APIClient, member: User, profile: MemberProfile, recorded: Recorded
) -> None:
    """``PATCH /me/profile`` names the labels of the fields whose value moved."""
    api_client.force_login(member)

    response = api_client.patch(
        "/api/v1/me/profile",
        {"city": "Fresno", "air_care_alliance_number": "ACA-99999"},
        format="json",
    )

    assert response.status_code == 200
    assert raised(recorded, "profile_changed") == [
        {"user": member, "fields": ["City", "Air Care Alliance number"], "actor": None}
    ]


@pytest.mark.parametrize(
    ("name", "label"),
    [
        ("dart", "DART"),
        ("air_care_alliance_number", "Air Care Alliance number"),
        ("home_airport_identifier", "Home airport"),
        ("secondary_airport_identifier", "Secondary airport"),
        ("address_line1", "Address line 1"),
        ("first_name", "First name"),
        ("city", "City"),
        ("county", "California county"),
        ("flies_rented_aircraft", "Flies rented or borrowed aircraft"),
    ],
)
def test_a_changed_field_is_named_by_its_label(name: str, label: str) -> None:
    """A field reads as its own label, or as its model name with a capital letter."""
    assert profile_field_label(name) == label


def test_resending_a_profile_unchanged_raises_nothing(
    api_client: APIClient, member: User, profile: MemberProfile, recorded: Recorded
) -> None:
    """A save that moves no value is not a change."""
    api_client.force_login(member)

    response = api_client.patch("/api/v1/me/profile", {"city": profile.city}, format="json")

    assert response.status_code == 200
    assert recorded == []


def test_choosing_a_dart_names_it_among_the_changes(
    api_client: APIClient, member: User, recorded: Recorded, dart: Dart
) -> None:
    """The DART is written as ``dart_id`` and labeled DART."""
    MemberProfileFactory(user=member, dart=None)
    api_client.force_login(member)

    api_client.patch("/api/v1/me/profile", {"dart_id": dart.pk}, format="json")

    assert raised(recorded, "profile_changed") == [
        {"user": member, "fields": ["DART"], "actor": None}
    ]


def test_an_administrator_editing_a_profile_raises_profile_changed(
    account_admin: User, member: User, profile: MemberProfile, recorded: Recorded
) -> None:
    """An administrator's edit names the fields, the name among them, and the actor."""
    update_member(
        account_admin,
        member,
        account={"first_name": "Robyn"},
        profile={"city": "Fresno"},
    )

    assert raised(recorded, "profile_changed") == [
        {"user": member, "fields": ["First name", "City"], "actor": account_admin}
    ]


def test_an_administrator_changing_only_the_active_flag_raises_no_profile_change(
    account_admin: User, member: User, profile: MemberProfile, recorded: Recorded
) -> None:
    """The active flag has its own events; the profile is untouched."""
    update_member(account_admin, member, account={"is_active": False})

    assert raised(recorded, "profile_changed") == []


# --------------------------------------------------------------------------
# aircraft_added, aircraft_changed and aircraft_removed
# --------------------------------------------------------------------------
def test_adding_an_aircraft_raises_aircraft_added(
    api_client: APIClient, member: User, recorded: Recorded
) -> None:
    """``POST /aircraft`` raises the new record and who added it."""
    api_client.force_login(member)

    response = api_client.post(
        "/api/v1/aircraft",
        {
            "n_number": "N4321Q",
            "type_id": AircraftTypeFactory(make="Cirrus", model="SR22").pk,
            "year": 2019,
            "owner_type": "individual",
            "owner_name": "Marta Reyes",
            "seats": 4,
            "insurance_carrier": "Avemco",
            "insurance_liability_per_occurrence_cents": 100_000_000,
            "insurance_liability_per_person_cents": 10_000_000,
        },
        format="json",
    )

    assert response.status_code == 201
    aircraft = Aircraft.objects.get(n_number="N4321Q")
    assert raised(recorded, "aircraft_added") == [{"aircraft": aircraft, "actor": member}]


def test_editing_an_aircraft_raises_aircraft_changed(
    api_client: APIClient, account_admin: User, recorded: Recorded
) -> None:
    """``PATCH /aircraft/{id}`` names the columns that moved, as the history does."""
    aircraft = AircraftFactory(make="Cessna", seats=4)
    piper = AircraftTypeFactory(make="Piper", model="PA-28-181")
    api_client.force_login(account_admin)

    api_client.patch(
        f"/api/v1/aircraft/{aircraft.pk}", {"type_id": piper.pk, "seats": 4}, format="json"
    )

    assert raised(recorded, "aircraft_changed") == [
        {"aircraft": aircraft, "fields": ["type"], "actor": account_admin}
    ]


def test_resending_an_aircraft_unchanged_raises_nothing(
    api_client: APIClient, account_admin: User, recorded: Recorded
) -> None:
    """An edit that moves no column is not a change."""
    aircraft = AircraftFactory(make="Cessna")
    api_client.force_login(account_admin)

    response = api_client.patch(
        f"/api/v1/aircraft/{aircraft.pk}", {"type_id": aircraft.type_id}, format="json"
    )

    assert response.status_code == 200
    assert recorded == []


def test_deleting_an_aircraft_raises_aircraft_removed(
    api_client: APIClient, account_admin: User, recorded: Recorded
) -> None:
    """The record is gone, so the event carries its N-number and owner instead."""
    aircraft = AircraftFactory(n_number="N77AB", owner_name="Pat Ruiz")
    api_client.force_login(account_admin)

    response = api_client.delete(f"/api/v1/aircraft/{aircraft.pk}")

    assert response.status_code == 204
    assert raised(recorded, "aircraft_removed") == [
        {"n_number": "N77AB", "owner": "Pat Ruiz", "actor": account_admin}
    ]


def test_a_checkout_that_saves_its_card_raises_auto_renewal_on(
    member: User, annual_plan: MembershipPlan, recorded: Recorded
) -> None:
    """A payment that activates the pending mandate its checkout began turns it on."""
    RenewalMandateFactory(
        user=member, plan=annual_plan, status=MandateStatus.PENDING, provider=PaymentProvider.MOCK
    )

    mark_succeeded(PaymentFactory(user=member, plan=annual_plan))

    mandate = RenewalMandate.objects.get(user=member)
    assert raised(recorded, "auto_renewal_on") == [{"mandate": mandate}]
