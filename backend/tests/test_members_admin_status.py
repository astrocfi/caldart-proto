"""The SQL membership annotations must agree with ``membership_status``.

``apps.members.services`` states the membership rule twice: once in Python, in
``membership_status``, and once as correlated subqueries, in
``membership_annotations``, so a list can filter, order and paginate on a
computed status.  Two implementations of one rule is a standing invitation to
drift, so this module builds every awkward history it can think of and asserts
the two agree, row by row.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from apps.accounts.models import AccountKind, User
from apps.members.filters import MemberAdminFilterSet, member_admin_queryset
from apps.members.models import Membership, MembershipPlan, MembershipStatusChoices
from apps.members.services import (
    membership_of,
    membership_payload,
    membership_status,
    with_membership,
)
from tests.factories import MembershipFactory, UserFactory

pytestmark = pytest.mark.django_db


def build_histories(annual: MembershipPlan, life: MembershipPlan, today: date) -> dict[str, User]:
    """``{label: user}`` covering the cases the two implementations must share."""
    day = timedelta(days=1)

    def user(label: str) -> User:
        return UserFactory(email=f"{label}@example.test", roles=["member"])

    def term(
        owner: User,
        plan: MembershipPlan,
        starts_on: date,
        ends_on: date | None,
        status: str = MembershipStatusChoices.ACTIVE,
    ) -> Membership:
        return MembershipFactory(
            user=owner, plan=plan, starts_on=starts_on, ends_on=ends_on, status=status
        )

    histories: dict[str, User] = {}

    histories["never"] = user("never")

    current = user("current")
    term(current, annual, today - 100 * day, today + 200 * day)
    histories["current"] = current

    expired = user("expired")
    term(expired, annual, today - 500 * day, today - 100 * day, MembershipStatusChoices.EXPIRED)
    histories["expired"] = expired

    # An active row nobody has flipped to "expired" yet still reads as expired.
    stale = user("stale")
    term(stale, annual, today - 500 * day, today - day)
    histories["stale-active"] = stale

    # Early renewal: the new term starts the day after the old one ends.
    renewed = user("renewed")
    term(renewed, annual, today - 300 * day, today + 10 * day)
    term(renewed, annual, today + 11 * day, today + 375 * day)
    histories["renewed-early"] = renewed

    chained = user("chained")
    term(chained, annual, today - 700 * day, today - 336 * day)
    term(chained, annual, today - 335 * day, today + 29 * day)
    term(chained, annual, today + 30 * day, today + 394 * day)
    histories["three-back-to-back"] = chained

    # A term that starts after a gap does not extend the current coverage.
    gapped = user("gapped")
    term(gapped, annual, today - 100 * day, today + 10 * day)
    term(gapped, annual, today + 40 * day, today + 400 * day)
    histories["future-term-after-a-gap"] = gapped

    lifetime = user("lifetime")
    term(lifetime, life, today - 900 * day, None)
    histories["lifetime"] = lifetime

    # Annual now, life bought to follow it: current, and already lifetime.
    upgraded = user("upgraded")
    term(upgraded, annual, today - 100 * day, today + 20 * day)
    term(upgraded, life, today + 21 * day, None)
    histories["annual-then-life"] = upgraded

    canceled = user("canceled")
    term(
        canceled,
        annual,
        today - 100 * day,
        today + 100 * day,
        MembershipStatusChoices.CANCELED,
    )
    histories["canceled-only"] = canceled

    future = user("future")
    term(future, annual, today + 5 * day, today + 369 * day)
    histories["starts-in-the-future"] = future

    overlapping = user("overlapping")
    term(overlapping, annual, today - 100 * day, today + 30 * day)
    term(overlapping, annual, today - 50 * day, today + 90 * day)
    histories["overlapping"] = overlapping

    expired_then_future = user("expiredfuture")
    term(
        expired_then_future,
        annual,
        today - 500 * day,
        today - 30 * day,
        MembershipStatusChoices.EXPIRED,
    )
    term(expired_then_future, annual, today + 60 * day, today + 424 * day)
    histories["expired-with-a-future-term"] = expired_then_future

    ends_today = user("endstoday")
    term(ends_today, annual, today - 364 * day, today)
    histories["ends-today"] = ends_today

    # A deactivated account whose only term is suspended: nothing covers it, and
    # nothing has run out, so it reads as a friend until the term is restored.
    suspended = user("suspended")
    term(
        suspended,
        annual,
        today - 100 * day,
        today + 265 * day,
        MembershipStatusChoices.SUSPENDED,
    )
    histories["suspended-only"] = suspended

    # A friend is a friend whatever terms they held, lapsed or even live.
    friend = user("friend")
    friend.kind = AccountKind.FRIEND
    friend.save(update_fields=["kind"])
    term(friend, annual, today - 500 * day, today - 100 * day, MembershipStatusChoices.EXPIRED)
    histories["friend-once-a-member"] = friend

    live_friend = user("livefriend")
    live_friend.kind = AccountKind.FRIEND
    live_friend.save(update_fields=["kind"])
    term(live_friend, annual, today - 100 * day, today + 200 * day)
    histories["friend-with-a-live-term"] = live_friend

    # A member whose conversion to friend has come but is not yet written down.
    converting = user("converting")
    term(converting, annual, today - 400 * day, today - day)
    converting.friend_on = today
    converting.save(update_fields=["friend_on"])
    histories["friend-on-today"] = converting

    # A member whose conversion is still ahead is current until then.
    pending = user("pending")
    term(pending, annual, today - 300 * day, today + 30 * day)
    pending.friend_on = today + 31 * day
    pending.save(update_fields=["friend_on"])
    histories["friend-on-ahead"] = pending

    return histories


@pytest.fixture
def histories(
    annual_plan: MembershipPlan, life_plan: MembershipPlan, today: date
) -> dict[str, User]:
    """The histories every test in this module checks the two implementations against."""
    return build_histories(annual_plan, life_plan, today)


def test_annotations_match_the_membership_status_service(histories: dict[str, User]) -> None:
    """Every annotated row's payload matches ``membership_status`` for the same user."""
    annotated = {user.pk: user for user in member_admin_queryset()}
    for label, user in histories.items():
        expected = membership_status(user)
        actual = membership_payload(annotated[user.pk])
        assert actual == expected, label


@pytest.mark.parametrize(
    ("label", "expected_status", "is_lifetime"),
    [
        ("never", "friend", False),
        ("current", "current", False),
        ("expired", "expired", False),
        ("stale-active", "expired", False),
        ("renewed-early", "current", False),
        ("three-back-to-back", "current", False),
        ("future-term-after-a-gap", "current", False),
        ("lifetime", "current", True),
        ("annual-then-life", "current", True),
        ("canceled-only", "friend", False),
        ("starts-in-the-future", "friend", False),
        ("overlapping", "current", False),
        ("expired-with-a-future-term", "expired", False),
        ("ends-today", "current", False),
        ("suspended-only", "friend", False),
        ("friend-once-a-member", "friend", False),
        ("friend-with-a-live-term", "friend", False),
        ("friend-on-today", "friend", False),
        ("friend-on-ahead", "current", False),
    ],
)
def test_expected_status_per_history(
    histories: dict[str, User], label: str, expected_status: str, is_lifetime: bool
) -> None:
    """Each history lands on the status and lifetime flag its label promises."""
    user = member_admin_queryset().get(pk=histories[label].pk)
    payload = membership_payload(user)
    assert payload["status"] == expected_status
    assert payload["is_lifetime"] is is_lifetime


def test_coverage_stops_at_a_gap(histories: dict[str, User], today: date) -> None:
    """A term starting after a break is not part of today's coverage."""
    user = member_admin_queryset().get(pk=histories["future-term-after-a-gap"].pk)
    assert membership_payload(user)["expires_on"] == today + timedelta(days=10)


def test_early_renewal_shows_the_new_expiry(histories: dict[str, User], today: date) -> None:
    """An early renewal reports the new term's end date, not the old one's."""
    user = member_admin_queryset().get(pk=histories["renewed-early"].pk)
    assert membership_payload(user)["expires_on"] == today + timedelta(days=375)


def test_three_back_to_back_terms_chain_to_the_last(
    histories: dict[str, User], today: date
) -> None:
    """Three back-to-back terms chain to the last one's end date."""
    user = member_admin_queryset().get(pk=histories["three-back-to-back"].pk)
    assert membership_payload(user)["expires_on"] == today + timedelta(days=394)


def test_lifetime_reports_the_life_plan(
    histories: dict[str, User], life_plan: MembershipPlan
) -> None:
    """A member who upgraded to a lifetime plan reports it, with no expiry."""
    user = member_admin_queryset().get(pk=histories["annual-then-life"].pk)
    payload = membership_payload(user)
    assert payload["expires_on"] is None
    assert payload["plan"] == life_plan.name


def test_joined_on_is_the_earliest_term_start(histories: dict[str, User], today: date) -> None:
    """``joined_on`` is the earliest term's start date, or ``None`` with no terms."""
    user = member_admin_queryset().get(pk=histories["three-back-to-back"].pk)
    assert user.joined_on == today - timedelta(days=700)
    assert member_admin_queryset().get(pk=histories["never"].pk).joined_on is None


def test_membership_of_reads_the_annotations(histories: dict[str, User]) -> None:
    """An annotated row is answered from the annotations, and answered right."""
    annotated = {user.pk: user for user in with_membership(User.objects.all())}
    for label, user in histories.items():
        assert membership_of(annotated[user.pk]) == membership_status(user), label


@pytest.mark.parametrize("label", ["renewed-early", "expired", "lifetime", "never"])
def test_membership_of_falls_back_to_the_service(histories: dict[str, User], label: str) -> None:
    """A row fetched without the annotations still gets the same answer."""
    plain = User.objects.get(pk=histories[label].pk)
    assert membership_of(plain) == membership_status(histories[label])


@pytest.mark.parametrize(
    ("status", "labels"),
    [
        (
            "friend",
            {
                "never",
                "canceled-only",
                "starts-in-the-future",
                "suspended-only",
                "friend-once-a-member",
                "friend-with-a-live-term",
                "friend-on-today",
            },
        ),
        (
            "current",
            {
                "current",
                "renewed-early",
                "three-back-to-back",
                "future-term-after-a-gap",
                "lifetime",
                "annual-then-life",
                "overlapping",
                "ends-today",
                "friend-on-ahead",
            },
        ),
        (
            "expired",
            {"expired", "stale-active", "expired-with-a-future-term"},
        ),
    ],
)
def test_the_status_filter_puts_every_friend_under_friend(
    histories: dict[str, User], status: str, labels: set[str]
) -> None:
    """``?status=friend`` lists the friends, and no other status lists any of them."""
    by_pk = {user.pk: label for label, user in histories.items()}
    queryset = MemberAdminFilterSet({"status": status}, queryset=member_admin_queryset()).qs
    assert {by_pk[user.pk] for user in queryset if user.pk in by_pk} == labels
