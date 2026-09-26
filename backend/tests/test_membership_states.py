"""The four membership states, and who counts as a friend.

A membership is Current, Expired, Friend, or Donor.  The stored ``kind`` is what the
person asked for; the effective kind is what they are: an account that chose to be a
member but holds no term that has started and was ever paid for, granted, or set
aside by a deactivation is a friend until one covers it.  These tests pin that rule
in both of its statements (``account_kind`` in Python and ``kind_annotation`` in SQL),
the four answers ``membership_status`` and ``membership_payload`` agree on, the member
list's status filter, and what the join wizard reads off ``/auth/me``.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta

import pytest
from django.contrib.auth.models import AnonymousUser
from rest_framework.test import APIClient

from apps.accounts.models import AccountKind, User
from apps.members.filters import MemberAdminFilterSet, member_admin_queryset
from apps.members.models import (
    MembershipPlan,
    MembershipState,
    MembershipStatusChoices,
)
from apps.members.services import (
    account_kind,
    activate_term,
    kind_annotation,
    membership_payload,
    membership_status,
)
from tests.conftest import ME_URL, REGISTER_URL, register_payload
from tests.factories import MembershipFactory, UserFactory

pytestmark = pytest.mark.django_db

#: Builds one account for a case, given the annual plan and today's date.
type Builder = Callable[[MembershipPlan, date], User]


def _user(label: str, kind: AccountKind = AccountKind.MEMBER) -> User:
    """A fresh account named after ``label`` with the stored ``kind``."""
    return UserFactory(email=f"{label}@example.test", kind=kind)


def _with_term(
    label: str,
    status: MembershipStatusChoices,
    *,
    starts_in: int,
    ends_in: int,
) -> Builder:
    """A builder for a member holding one term of ``status``, dated relative to today."""

    def build(plan: MembershipPlan, today: date) -> User:
        user = _user(label)
        MembershipFactory(
            user=user,
            plan=plan,
            starts_on=today + timedelta(days=starts_in),
            ends_on=today + timedelta(days=ends_in),
            status=status,
        )
        return user

    return build


def _no_term(plan: MembershipPlan, today: date) -> User:
    """A member who registered and never paid: no term at all."""
    return _user("unpaid")


def _friend(plan: MembershipPlan, today: date) -> User:
    """An account stored as a friend."""
    return _user("friend", AccountKind.FRIEND)


def _donor(plan: MembershipPlan, today: date) -> User:
    """A donor account, which gives but never signs in."""
    return _user("donor", AccountKind.DONOR)


def _pending_friend(plan: MembershipPlan, today: date) -> User:
    """A current member whose change to friend comes the day after the term ends."""
    user = _with_term("pending", MembershipStatusChoices.ACTIVE, starts_in=-30, ends_in=30)(
        plan, today
    )
    user.friend_on = today + timedelta(days=31)
    user.save(update_fields=["friend_on"])
    return user


def _due_friend(plan: MembershipPlan, today: date) -> User:
    """A member whose change to friend has come but is not yet written down."""
    user = _with_term("due", MembershipStatusChoices.ACTIVE, starts_in=-400, ends_in=-1)(
        plan, today
    )
    user.friend_on = today
    user.save(update_fields=["friend_on"])
    return user


#: ``(label, builder, effective kind, membership state)`` for every case the rule names.
CASES: list[tuple[str, Builder, AccountKind, MembershipState]] = [
    ("member-with-no-term", _no_term, AccountKind.FRIEND, MembershipState.FRIEND),
    (
        "canceled-only",
        _with_term("canceled", MembershipStatusChoices.CANCELED, starts_in=-10, ends_in=355),
        AccountKind.FRIEND,
        MembershipState.FRIEND,
    ),
    (
        "future-term",
        _with_term("future", MembershipStatusChoices.ACTIVE, starts_in=5, ends_in=369),
        AccountKind.FRIEND,
        MembershipState.FRIEND,
    ),
    (
        "suspended-only",
        _with_term("suspended", MembershipStatusChoices.SUSPENDED, starts_in=-10, ends_in=355),
        AccountKind.MEMBER,
        MembershipState.FRIEND,
    ),
    ("friend", _friend, AccountKind.FRIEND, MembershipState.FRIEND),
    ("pending-friend", _pending_friend, AccountKind.MEMBER, MembershipState.CURRENT),
    ("due-friend", _due_friend, AccountKind.FRIEND, MembershipState.FRIEND),
    ("donor", _donor, AccountKind.DONOR, MembershipState.DONOR),
    (
        "current",
        _with_term("current", MembershipStatusChoices.ACTIVE, starts_in=-10, ends_in=355),
        AccountKind.MEMBER,
        MembershipState.CURRENT,
    ),
    (
        "expired",
        _with_term("expired", MembershipStatusChoices.EXPIRED, starts_in=-400, ends_in=-35),
        AccountKind.MEMBER,
        MembershipState.EXPIRED,
    ),
    (
        "stale-active",
        _with_term("stale", MembershipStatusChoices.ACTIVE, starts_in=-400, ends_in=-1),
        AccountKind.MEMBER,
        MembershipState.EXPIRED,
    ),
]

CASE_IDS = [case[0] for case in CASES]


@pytest.fixture
def build(annual_plan: MembershipPlan, today: date) -> Callable[[Builder], User]:
    """Run a case's builder against the annual plan on the frozen ``today``."""
    return lambda builder: builder(annual_plan, today)


# --------------------------------------------------------------------------
# The choices
# --------------------------------------------------------------------------
def test_the_membership_states_are_current_expired_friend_and_donor() -> None:
    """``MembershipState`` holds exactly the four states, with their labels."""
    assert MembershipState.choices == [
        ("current", "Current"),
        ("expired", "Expired"),
        ("friend", "Friend"),
        ("donor", "Donor"),
    ]


def test_a_term_is_active_expired_canceled_or_suspended() -> None:
    """``MembershipStatusChoices`` has no unpaid state."""
    assert MembershipStatusChoices.values == ["active", "expired", "canceled", "suspended"]


# --------------------------------------------------------------------------
# The effective kind
# --------------------------------------------------------------------------
@pytest.mark.parametrize(("label", "builder", "kind", "state"), CASES, ids=CASE_IDS)
def test_account_kind_follows_the_effective_kind_rule(
    build: Callable[[Builder], User],
    today: date,
    label: str,
    builder: Builder,
    kind: AccountKind,
    state: MembershipState,
) -> None:
    """``account_kind`` answers the case's effective kind."""
    assert account_kind(build(builder), today) == kind


@pytest.mark.parametrize(("label", "builder", "kind", "state"), CASES, ids=CASE_IDS)
def test_kind_annotation_agrees_with_account_kind(
    build: Callable[[Builder], User],
    today: date,
    label: str,
    builder: Builder,
    kind: AccountKind,
    state: MembershipState,
) -> None:
    """The SQL statement of the rule gives the same kind as the Python one."""
    user = build(builder)
    row = User.objects.annotate(effective=kind_annotation(today)).get(pk=user.pk)
    assert row.effective == kind


def test_a_payment_makes_an_unpaid_joiner_a_member(
    annual_plan: MembershipPlan, today: date
) -> None:
    """The first term that covers a member-intent joiner makes them a member."""
    user = _user("joiner")
    activate_term(user, annual_plan)
    assert account_kind(user, today) == AccountKind.MEMBER


def test_a_payment_makes_a_friend_a_member(annual_plan: MembershipPlan, today: date) -> None:
    """A friend who pays dues is stored, and counts, as a member."""
    user = _user("paying-friend", AccountKind.FRIEND)
    activate_term(user, annual_plan)
    user.refresh_from_db()
    assert account_kind(user, today) == AccountKind.MEMBER


# --------------------------------------------------------------------------
# The four states, in Python and in SQL
# --------------------------------------------------------------------------
@pytest.mark.parametrize(("label", "builder", "kind", "state"), CASES, ids=CASE_IDS)
def test_membership_status_answers_the_case_state(
    build: Callable[[Builder], User],
    today: date,
    label: str,
    builder: Builder,
    kind: AccountKind,
    state: MembershipState,
) -> None:
    """``membership_status`` lands on the case's state."""
    assert membership_status(build(builder), today)["status"] == state


@pytest.mark.parametrize(("label", "builder", "kind", "state"), CASES, ids=CASE_IDS)
def test_membership_payload_agrees_with_membership_status(
    build: Callable[[Builder], User],
    today: date,
    label: str,
    builder: Builder,
    kind: AccountKind,
    state: MembershipState,
) -> None:
    """The annotated row answers exactly what the Python service answers."""
    user = build(builder)
    row = member_admin_queryset(today, include_donors=True).get(pk=user.pk)
    assert membership_payload(row) == membership_status(user, today)


@pytest.mark.parametrize("label", ["member-with-no-term", "friend", "suspended-only"])
def test_a_friend_reads_with_no_expiry_and_no_plan(
    build: Callable[[Builder], User], today: date, label: str
) -> None:
    """Every friend answer is the same shape: no expiry, no plan, never lifetime."""
    builder = {case[0]: case[1] for case in CASES}[label]
    assert membership_status(build(builder), today) == {
        "status": MembershipState.FRIEND,
        "expires_on": None,
        "plan": None,
        "is_lifetime": False,
    }


def test_a_donor_reads_donor(today: date) -> None:
    """A donor's membership is ``donor``, with no expiry, no plan, never lifetime."""
    assert membership_status(_user("giver", AccountKind.DONOR), today) == {
        "status": MembershipState.DONOR,
        "expires_on": None,
        "plan": None,
        "is_lifetime": False,
    }


def test_an_anonymous_caller_reads_as_a_friend(today: date) -> None:
    """A signed-out visitor, or nobody at all, is answered with the friend shape."""
    assert membership_status(AnonymousUser(), today)["status"] == MembershipState.FRIEND


# --------------------------------------------------------------------------
# The member list's status filter
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("status", "labels"),
    [
        ("current", {"pending-friend", "current"}),
        ("expired", {"expired", "stale-active"}),
        (
            "friend",
            {
                "member-with-no-term",
                "canceled-only",
                "future-term",
                "suspended-only",
                "friend",
                "due-friend",
            },
        ),
        ("donor", {"donor"}),
    ],
)
def test_the_status_filter_puts_every_account_under_its_state(
    annual_plan: MembershipPlan, today: date, status: str, labels: set[str]
) -> None:
    """Each of the four filter choices lists exactly the accounts in that state."""
    by_pk = {builder(annual_plan, today).pk: label for label, builder, _k, _s in CASES}
    queryset = MemberAdminFilterSet(
        {"status": status}, queryset=member_admin_queryset(today, include_donors=True)
    ).qs
    assert {by_pk[user.pk] for user in queryset if user.pk in by_pk} == labels


def test_the_member_list_never_lists_a_donor(
    account_admin_client: APIClient, annual_plan: MembershipPlan, today: date
) -> None:
    """``?status=donor`` on the member list finds nobody: donors are never listed."""
    _user("listed-donor", AccountKind.DONOR)
    response = account_admin_client.get("/api/v1/admin/members", {"status": "donor"})
    assert response.status_code == 200
    assert response.json()["count"] == 0


# --------------------------------------------------------------------------
# What the join wizard reads
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        ("member", {"kind": "member", "status": "friend"}),
        ("friend", {"kind": "friend", "status": "friend"}),
    ],
)
def test_a_new_account_keeps_its_intent_and_reads_as_a_friend(
    api_client: APIClient, kind: str, expected: dict[str, str]
) -> None:
    """A joiner's stored kind is what they chose; until they pay, they are a friend."""
    api_client.post(REGISTER_URL, register_payload(kind=kind))
    body = api_client.get(ME_URL).json()
    assert {"kind": body["kind"], "status": body["membership"]["status"]} == expected


def test_a_member_joiner_who_pays_reads_current(
    api_client: APIClient, annual_plan: MembershipPlan
) -> None:
    """The member-intent joiner's first payment makes the membership current."""
    api_client.post(REGISTER_URL, register_payload())
    activate_term(User.objects.get(email="new.member@example.test"), annual_plan)
    body = api_client.get(ME_URL).json()
    assert {"kind": body["kind"], "status": body["membership"]["status"]} == {
        "kind": "member",
        "status": "current",
    }
