"""Notification subscriptions, who may receive an event, and what each email says.

A subscription names an address and the events it hears about.  One bound to an
account is sent an event only while the account is active and holds a role the event
allows; a bare address always may, and is bound to the account that later takes it.
Each event's email is a headline, a few labeled lines, and one link into the portal,
built from the objects the event was raised with.  The sending itself is covered by
``test_notification_sending.py`` and the endpoints by ``test_notification_api.py``.
"""

from __future__ import annotations

from datetime import date

import pytest
from django.db import IntegrityError

from apps.accounts.models import AccountKind, User
from apps.accounts.roles import ACCOUNT_ADMIN, MEMBER, SYSTEM_ADMIN, TREASURER, USER_ADMIN
from apps.darts.models import Dart
from apps.members.models import Membership, MembershipPlan, MembershipStatusChoices
from apps.notifications.messages import Message, build_message
from apps.notifications.models import NotificationSubscription
from apps.notifications.services import recipient_may_receive, refresh_recipient
from apps.payments.models import (
    MandateCadence,
    MandateStatus,
    PaymentProvider,
    PaymentStatus,
    PaymentWallet,
)
from tests.factories import (
    AircraftFactory,
    MemberProfileFactory,
    MembershipFactory,
    PaymentFactory,
    RenewalMandateFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db

#: Where every link in a test email starts: the test settings' ``SITE_URL``.
SITE = "http://localhost:8000/portal"


def subscribe(email: str, events: list[str], **fields: object) -> NotificationSubscription:
    """A saved subscription of ``email`` to ``events``, with any other ``fields``."""
    return NotificationSubscription.objects.create(recipient_email=email, events=events, **fields)


def slash_date(day: date) -> str:
    """``day`` as the administrative screens print it: ``YYYY/MM/DD``."""
    return day.strftime("%Y/%m/%d")


# -- the model ------------------------------------------------------------------
def test_a_subscription_reads_as_its_address_and_how_many_events() -> None:
    """``str()`` names the address and counts the events."""
    subscription = subscribe("ops@example.test", ["signed_up", "became_member"])

    assert str(subscription) == "ops@example.test: 2 events"


def test_a_subscription_stores_its_address_lowercased() -> None:
    """The address is kept in lower case, whatever case it was typed in."""
    subscription = subscribe("Ops@Example.TEST", ["signed_up"])

    subscription.refresh_from_db()
    assert subscription.recipient_email == "ops@example.test"


def test_one_address_holds_one_subscription() -> None:
    """A second subscription for the same address is refused by the database."""
    subscribe("ops@example.test", ["signed_up"])

    with pytest.raises(IntegrityError, match="recipient_email"):
        subscribe("OPS@example.test", ["became_member"])


def test_subscriptions_are_listed_by_address() -> None:
    """The default ordering is the address, alphabetically."""
    subscribe("zed@example.test", ["signed_up"])
    subscribe("amy@example.test", ["signed_up"])

    emails = list(NotificationSubscription.objects.values_list("recipient_email", flat=True))

    assert emails == ["amy@example.test", "zed@example.test"]


def test_a_new_subscription_is_active() -> None:
    """``is_active`` defaults to true."""
    assert subscribe("ops@example.test", ["signed_up"]).is_active is True


# -- who may receive an event ---------------------------------------------------
def test_a_bare_address_may_receive_every_event() -> None:
    """An address no account holds was confirmed when it was set up and always may."""
    subscription = subscribe("outside@example.test", ["aircraft_added"])

    assert recipient_may_receive(subscription, "aircraft_added") is True


@pytest.mark.parametrize(
    ("role", "slug", "allowed"),
    [
        (ACCOUNT_ADMIN, "signed_up", True),
        (USER_ADMIN, "signed_up", True),
        (TREASURER, "signed_up", False),
        (TREASURER, "donation_received", True),
        (USER_ADMIN, "donation_received", False),
        (USER_ADMIN, "roles_changed", True),
        (USER_ADMIN, "aircraft_added", False),
        (ACCOUNT_ADMIN, "aircraft_added", True),
        (SYSTEM_ADMIN, "aircraft_added", True),
        (MEMBER, "signed_up", False),
    ],
    ids=lambda value: str(value),
)
def test_a_bound_account_may_receive_the_events_its_roles_allow(
    role: str, slug: str, allowed: bool
) -> None:
    """The event's roles decide, and a system administrator may receive every event."""
    user = UserFactory(email="staff@example.test", roles=[MEMBER, role])
    subscription = subscribe(user.email, [slug], recipient_user=user)

    assert recipient_may_receive(subscription, slug) is allowed


def test_a_superuser_may_receive_every_event() -> None:
    """A Django superuser passes whatever roles the event names."""
    user = UserFactory(email="root@example.test", roles=[], is_superuser=True)
    subscription = subscribe(user.email, ["payment_refunded"], recipient_user=user)

    assert recipient_may_receive(subscription, "payment_refunded") is True


def test_a_deactivated_account_may_receive_nothing(account_admin: User) -> None:
    """An inactive account is skipped even for an event its roles allow."""
    account_admin.is_active = False
    account_admin.save(update_fields=["is_active"])
    subscription = subscribe(account_admin.email, ["signed_up"], recipient_user=account_admin)

    assert recipient_may_receive(subscription, "signed_up") is False


def test_refreshing_binds_a_bare_address_to_the_account_that_took_it() -> None:
    """An address an account has since taken, in any case, binds to that account."""
    subscription = subscribe("later@example.test", ["signed_up"])
    user = UserFactory(email="Later@Example.test")

    changed = refresh_recipient(subscription)

    assert (changed, subscription.recipient_user) == (True, user)


def test_refreshing_leaves_an_unclaimed_bare_address_alone() -> None:
    """With no account at the address nothing changes."""
    subscription = subscribe("outside@example.test", ["signed_up"])

    assert refresh_recipient(subscription) is False


def test_refreshing_follows_a_bound_account_to_its_new_address(account_admin: User) -> None:
    """A bound subscription takes its account's current address."""
    subscription = subscribe(account_admin.email, ["signed_up"], recipient_user=account_admin)
    account_admin.email = "moved@example.test"
    account_admin.save(update_fields=["email"])

    refresh_recipient(subscription)

    assert subscription.recipient_email == "moved@example.test"


# -- what each email says --------------------------------------------------------
@pytest.fixture
def pat() -> User:
    """A member named Pat Quill, the subject of most events."""
    return UserFactory(email="pat@example.test", first_name="Pat", last_name="Quill")


@pytest.fixture
def boss() -> User:
    """An administrator named Lee Boss, the actor of most events."""
    return UserFactory(
        email="boss@example.test", first_name="Lee", last_name="Boss", roles=[ACCOUNT_ADMIN]
    )


@pytest.fixture
def north() -> Dart:
    """The DART Pat chose."""
    return Dart.objects.create(name="North Bay DART", airport_identifiers="KSTS")


def member_link(user: User) -> str:
    """The portal's member record of ``user``."""
    return f"{SITE}/admin/members/{user.pk}"


def user_link(user: User) -> str:
    """The portal's user record of ``user``."""
    return f"{SITE}/admin/users/{user.pk}"


def test_the_subject_is_the_organization_name_and_the_headline(pat: User, north: Dart) -> None:
    """Every email's subject reads ``<org name>: <headline>``."""
    message = build_message("signed_up", {"user": pat, "dart": north})

    assert message.subject == "CalDART: Pat Quill signed up as a member"


def test_signed_up(pat: User, north: Dart) -> None:
    """A sign-up names the email, the DART and the kind, and links the member record."""
    message = build_message("signed_up", {"user": pat, "dart": north})

    assert message == Message(
        subject="CalDART: Pat Quill signed up as a member",
        headline="Pat Quill signed up as a member",
        lines=(
            ("Email", "pat@example.test"),
            ("DART", "North Bay DART"),
            ("Joined as", "Member"),
        ),
        link=member_link(pat),
    )


def test_a_sign_up_with_no_dart_says_none() -> None:
    """A friend who chose no DART reads ``None`` on the DART line."""
    friend = UserFactory(
        email="fran@example.test", first_name="Fran", last_name="Hale", kind=AccountKind.FRIEND
    )

    message = build_message("signed_up", {"user": friend, "dart": None})

    assert message.lines == (
        ("Email", "fran@example.test"),
        ("DART", "None"),
        ("Joined as", "Friend"),
    )


def test_member_added(pat: User, boss: User, north: Dart) -> None:
    """An administrator's addition names the actor, the kind and the profile's DART."""
    MemberProfileFactory(user=pat, dart=north)

    message = build_message("member_added", {"user": pat, "actor": boss})

    assert (message.headline, message.lines, message.link) == (
        "Pat Quill was added by Lee Boss",
        (("Email", "pat@example.test"), ("Kind", "Member"), ("DART", "North Bay DART")),
        member_link(pat),
    )


@pytest.mark.parametrize(
    ("how", "words"),
    [
        ("chose", "Chose to be a friend"),
        ("lapsed", "Membership lapsed"),
        ("administrator", "Changed by an administrator"),
    ],
)
def test_became_friend(pat: User, how: str, words: str) -> None:
    """Becoming a friend says how it came about."""
    message = build_message("became_friend", {"user": pat, "how": how})

    assert (message.headline, message.lines) == (
        "Pat Quill is now a friend",
        (("Email", "pat@example.test"), ("How", words)),
    )


@pytest.mark.parametrize(
    ("how", "words"),
    [
        ("paid", "Paid for membership"),
        ("granted", "Granted by an administrator"),
        ("administrator", "Changed by an administrator"),
    ],
)
def test_became_member(pat: User, how: str, words: str) -> None:
    """Becoming a member says how it came about."""
    message = build_message("became_member", {"user": pat, "how": how})

    assert (message.headline, message.lines, message.link) == (
        "Pat Quill is now a member",
        (("Email", "pat@example.test"), ("How", words)),
        member_link(pat),
    )


def paid_term(user: User, plan: MembershipPlan, **payment_fields: object) -> Membership:
    """A payment by ``user`` for ``plan`` and the term it bought.

    The payment has succeeded unless ``payment_fields`` gives another ``status``.
    """
    fields: dict[str, object] = {"status": PaymentStatus.SUCCEEDED, **payment_fields}
    payment = PaymentFactory(user=user, plan=plan, **fields)
    return MembershipFactory(user=user, plan=plan, payment=payment)


def test_membership_paid(pat: User, annual_plan: MembershipPlan) -> None:
    """A payment names the plan, the amount, the end of the term, and the contribution."""
    term = paid_term(pat, annual_plan, amount_cents=5_500, contribution_cents=1_000)
    assert term.ends_on is not None
    through = slash_date(term.ends_on)

    message = build_message(
        "membership_paid", {"payment": term.payment, "term": term, "automatic": False}
    )

    assert (message.headline, message.lines, message.link) == (
        f"Pat Quill paid for membership through {through}",
        (
            ("Plan", "Annual"),
            ("Amount", "$55.00"),
            ("Paid through", through),
            ("Contribution", "$10.00"),
        ),
        f"{SITE}/admin/payments/{term.payment_id}",
    )


def test_an_automatic_renewal_says_so_and_leaves_out_a_missing_contribution(
    pat: User, annual_plan: MembershipPlan
) -> None:
    """An automatic payment reads as a renewal, and no contribution means no line."""
    term = paid_term(pat, annual_plan)
    assert term.ends_on is not None
    through = slash_date(term.ends_on)

    message = build_message(
        "membership_paid", {"payment": term.payment, "term": term, "automatic": True}
    )

    assert (message.headline, message.lines) == (
        f"Pat Quill renewed automatically through {through}",
        (("Plan", "Annual"), ("Amount", "$45.00"), ("Paid through", through)),
    )


def test_a_lifetime_term_is_paid_for_life(pat: User, life_plan: MembershipPlan) -> None:
    """A term with no end reads as a lifetime membership."""
    term = paid_term(pat, life_plan, amount_cents=65_000, plan_amount_cents=65_000)

    message = build_message(
        "membership_paid", {"payment": term.payment, "term": term, "automatic": False}
    )

    assert (message.headline, message.lines[2]) == (
        "Pat Quill paid for a lifetime membership",
        ("Paid through", "Lifetime"),
    )


def test_membership_granted(pat: User, boss: User, annual_plan: MembershipPlan) -> None:
    """A grant names the actor, the plan and the end of the term."""
    term = MembershipFactory(user=pat, plan=annual_plan)
    assert term.ends_on is not None
    through = slash_date(term.ends_on)

    message = build_message("membership_granted", {"user": pat, "term": term, "actor": boss})

    assert (message.headline, message.lines, message.link) == (
        f"Lee Boss granted Pat Quill membership through {through}",
        (("Plan", "Annual"), ("Through", through)),
        member_link(pat),
    )


def test_membership_expired(pat: User, annual_plan: MembershipPlan) -> None:
    """An expiry names the day it ran out and the kind the person counts as now.

    A lapsed member is still a member, with an expired membership, until they
    renew or become a friend.
    """
    ended = date(2026, 3, 31)
    term = MembershipFactory(
        user=pat,
        plan=annual_plan,
        starts_on=date(2025, 4, 1),
        ends_on=ended,
        status=MembershipStatusChoices.EXPIRED,
    )

    message = build_message("membership_expired", {"user": pat, "term": term})

    assert (message.headline, message.lines, message.link) == (
        "Pat Quill's membership expired on 2026/03/31",
        (("Email", "pat@example.test"), ("Kind now", "Member")),
        member_link(pat),
    )


def test_auto_renewal_on_for_a_renewal(pat: User, annual_plan: MembershipPlan) -> None:
    """Turning on automatic renewal names the plan, the cadence and the next charge."""
    mandate = RenewalMandateFactory(user=pat, plan=annual_plan, next_charge_on=date(2027, 1, 5))

    message = build_message("auto_renewal_on", {"mandate": mandate})

    assert (message.headline, message.lines, message.link) == (
        "Pat Quill turned on automatic renewal",
        (("Plan", "Annual"), ("Cadence", "Yearly"), ("Next charge", "2027/01/05")),
        member_link(pat),
    )


def test_auto_renewal_on_for_a_donation(pat: User) -> None:
    """Turning on a recurring donation names the amount in place of a plan."""
    mandate = RenewalMandateFactory(
        user=pat,
        plan=None,
        contribution_cents=2_500,
        cadence=MandateCadence.MONTHLY,
        next_charge_on=date(2026, 11, 1),
    )

    message = build_message("auto_renewal_on", {"mandate": mandate})

    assert (message.headline, message.lines) == (
        "Pat Quill turned on automatic donation",
        (("Amount", "$25.00"), ("Cadence", "Monthly"), ("Next charge", "2026/11/01")),
    )


@pytest.mark.parametrize(
    ("how", "words"),
    [
        ("member", "Turned off by the member"),
        ("administrator", "Turned off by an administrator"),
        ("lapsed", "Membership lapsed"),
        ("deactivated", "Account deactivated"),
    ],
)
def test_auto_renewal_off(pat: User, annual_plan: MembershipPlan, how: str, words: str) -> None:
    """Turning automatic payment off says how it came about."""
    mandate = RenewalMandateFactory(user=pat, plan=annual_plan, status=MandateStatus.CANCELED)

    message = build_message("auto_renewal_off", {"mandate": mandate, "how": how})

    assert (message.headline, message.lines, message.link) == (
        "Pat Quill's automatic renewal is off",
        (("How", words),),
        member_link(pat),
    )


def test_auto_renewal_declined_with_a_retry_to_come(pat: User) -> None:
    """A decline quotes the reason and the day of the next try, from the payload."""
    mandate = RenewalMandateFactory(user=pat, plan=None, contribution_cents=1_000)

    message = build_message(
        "auto_renewal_declined",
        {"mandate": mandate, "reason": "Card declined", "next_on": date(2026, 9, 30)},
    )

    assert (message.headline, message.lines) == (
        "Pat Quill's automatic donation was declined",
        (("Reason", "Card declined"), ("Next try", "2026/09/30")),
    )


def test_auto_renewal_declined_for_the_last_time(pat: User, annual_plan: MembershipPlan) -> None:
    """A decline with no ``next_on`` says no try is left, regardless of the mandate."""
    mandate = RenewalMandateFactory(user=pat, plan=annual_plan, status=MandateStatus.PAUSED)

    message = build_message(
        "auto_renewal_declined", {"mandate": mandate, "reason": "Expired", "next_on": None}
    )

    assert message.lines == (
        ("Reason", "Expired"),
        ("Next try", "None: automatic renewal is paused"),
    )


def test_donation_received_one_time(pat: User) -> None:
    """A gift names the giver, the amount and that it was given once."""
    payment = PaymentFactory(
        user=pat,
        plan=None,
        amount_cents=10_000,
        plan_amount_cents=0,
        contribution_cents=10_000,
        status=PaymentStatus.SUCCEEDED,
    )

    message = build_message("donation_received", {"payment": payment})

    assert (message.headline, message.lines, message.link) == (
        "Pat Quill gave $100.00",
        (("From", "Pat Quill"), ("Amount", "$100.00"), ("Kind", "One-time")),
        f"{SITE}/admin/payments/{payment.pk}",
    )


def test_donation_received_recurring(pat: User) -> None:
    """A gift charged by a recurring donation reads as recurring."""
    mandate = RenewalMandateFactory(user=pat, plan=None, contribution_cents=2_000)
    payment = PaymentFactory(
        user=pat,
        plan=None,
        amount_cents=2_000,
        plan_amount_cents=0,
        contribution_cents=2_000,
        status=PaymentStatus.SUCCEEDED,
    )
    mandate.attempts.create(scheduled_on=date(2026, 9, 1), payment=payment)

    message = build_message("donation_received", {"payment": payment})

    assert message.lines[2] == ("Kind", "Recurring")


def test_payment_recorded(pat: User, boss: User, annual_plan: MembershipPlan) -> None:
    """A payment taken by hand names the actor, the method and what it bought."""
    payment = PaymentFactory(
        user=pat,
        plan=annual_plan,
        provider=PaymentProvider.MANUAL,
        wallet=PaymentWallet.CHECK,
        status=PaymentStatus.SUCCEEDED,
    )

    message = build_message("payment_recorded", {"payment": payment, "actor": boss})

    assert (message.headline, message.lines, message.link) == (
        "Lee Boss recorded a payment of $45.00 for Pat Quill",
        (("Method", "Check"), ("For", "Membership")),
        f"{SITE}/admin/payments/{payment.pk}",
    )


def test_payment_refunded_by_an_administrator(
    pat: User, boss: User, annual_plan: MembershipPlan
) -> None:
    """A refund names the payment's amount and who gave it back."""
    payment = PaymentFactory(user=pat, plan=annual_plan, status=PaymentStatus.PARTIALLY_REFUNDED)

    message = build_message(
        "payment_refunded",
        {"payment": payment, "refund_cents": 1_500, "actor": boss, "term_canceled": False},
    )

    assert (message.headline, message.lines, message.link) == (
        "$15.00 refunded to Pat Quill",
        (("Of", "$45.00"), ("By", "Lee Boss")),
        f"{SITE}/admin/payments/{payment.pk}",
    )


def test_a_full_refund_from_the_dashboard_names_the_canceled_membership(
    pat: User, annual_plan: MembershipPlan
) -> None:
    """A refund with no actor came from the provider's dashboard and may cancel a term."""
    payment = PaymentFactory(user=pat, plan=annual_plan, status=PaymentStatus.REFUNDED)

    message = build_message(
        "payment_refunded",
        {"payment": payment, "refund_cents": 4_500, "actor": None, "term_canceled": True},
    )

    assert message.lines == (
        ("Of", "$45.00"),
        ("By", "The payment provider's dashboard"),
        ("Membership canceled", "Yes"),
    )


def test_account_deactivated_by_the_person(pat: User) -> None:
    """A self-deactivation is by the account holder, and links the user record."""
    message = build_message("account_deactivated", {"user": pat, "actor": None})

    assert (message.headline, message.lines, message.link) == (
        "Pat Quill's account was deactivated",
        (("By", "Pat Quill themselves"),),
        user_link(pat),
    )


def test_account_reactivated(pat: User, boss: User) -> None:
    """A reactivation names who did it."""
    message = build_message("account_reactivated", {"user": pat, "actor": boss})

    assert (message.headline, message.lines, message.link) == (
        "Pat Quill's account was reactivated",
        (("By", "Lee Boss"),),
        user_link(pat),
    )


def test_roles_changed(pat: User, boss: User) -> None:
    """A role change lists what was added, what was removed, and what is held now."""
    pat.add_role(MEMBER)
    pat.add_role(TREASURER)

    message = build_message(
        "roles_changed",
        {"user": pat, "added": [TREASURER], "removed": [USER_ADMIN], "actor": boss},
    )

    assert (message.headline, message.lines, message.link) == (
        "Lee Boss changed Pat Quill's roles",
        (
            ("Added", "Treasurer"),
            ("Removed", "User administrator"),
            ("Now", "Member, Treasurer"),
        ),
        user_link(pat),
    )


def test_roles_changed_with_nothing_removed_says_none(pat: User, boss: User) -> None:
    """An empty side of the change reads ``None``."""
    message = build_message(
        "roles_changed", {"user": pat, "added": [MEMBER], "removed": [], "actor": boss}
    )

    assert message.lines[1] == ("Removed", "None")


def test_email_changed(pat: User) -> None:
    """A changed address names the old one and the new one."""
    message = build_message("email_changed", {"user": pat, "old_email": "old@example.test"})

    assert (message.headline, message.lines, message.link) == (
        "Pat Quill changed their email address",
        (("From", "old@example.test"), ("To", "pat@example.test")),
        user_link(pat),
    )


def test_profile_changed(pat: User, boss: User) -> None:
    """A profile edit lists the labels of the fields that changed and who changed them."""
    message = build_message(
        "profile_changed", {"user": pat, "fields": ["Phone", "Home airport"], "actor": boss}
    )

    assert (message.headline, message.lines, message.link) == (
        "Pat Quill's profile changed",
        (("Changed", "Phone, Home airport"), ("By", "Lee Boss")),
        member_link(pat),
    )


def test_aircraft_added(boss: User) -> None:
    """An added aircraft names its owner, its make and model, and who added it."""
    aircraft = AircraftFactory(n_number="N123AB", owner_name="Pat Quill", make="Piper")

    message = build_message("aircraft_added", {"aircraft": aircraft, "fields": [], "actor": boss})

    assert (message.headline, message.lines, message.link) == (
        "N123AB added for Pat Quill",
        (("Make and model", "Piper 182T Skylane"), ("By", "Lee Boss")),
        f"{SITE}/admin/aircraft/{aircraft.pk}",
    )


def test_aircraft_changed_names_the_fields_in_words(boss: User) -> None:
    """The changed columns read as their labels."""
    aircraft = AircraftFactory(n_number="N123AB", owner_name="Pat Quill")

    message = build_message(
        "aircraft_changed",
        {"aircraft": aircraft, "fields": ["insurance_carrier", "seats"], "actor": boss},
    )

    assert (message.headline, message.lines) == (
        "N123AB changed for Pat Quill",
        (
            ("Make and model", "Cessna 182T Skylane"),
            ("Changed", "Insurance carrier, Seats"),
            ("By", "Lee Boss"),
        ),
    )


def test_aircraft_removed_has_no_link(boss: User) -> None:
    """A removed aircraft is gone, so its email links nowhere."""
    message = build_message(
        "aircraft_removed",
        {"n_number": "N123AB", "owner": "Pat Quill", "fields": [], "actor": boss},
    )

    assert (message.headline, message.lines, message.link) == (
        "N123AB removed for Pat Quill",
        (("By", "Lee Boss"),),
        "",
    )


def test_an_aircraft_with_no_owner_on_file_is_named_alone(boss: User) -> None:
    """With no owner name the headline names the aircraft alone."""
    aircraft = AircraftFactory(n_number="N9Z", owner_name="")

    message = build_message("aircraft_added", {"aircraft": aircraft, "fields": [], "actor": boss})

    assert message.headline == "N9Z added"


def test_a_payload_missing_its_object_raises_type_error() -> None:
    """A hook that raised an event without the objects it needs fails loudly."""
    with pytest.raises(TypeError, match="'user'"):
        build_message("signed_up", {"dart": None})
