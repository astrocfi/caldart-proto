"""The SQL membership annotations must agree with ``membership_status``.

``apps.members.api.admin_filters`` re-expresses ``members.services`` as
correlated subqueries so the admin list can filter and order on a computed
status.  Two implementations of one rule is a standing invitation to drift, so
this module builds every awkward history it can think of and asserts the two
agree, row by row.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model

from apps.members.api.admin_filters import member_admin_queryset, membership_payload
from apps.members.models import MembershipStatusChoices
from apps.members.services import membership_status
from tests.factories import MembershipFactory, UserFactory

pytestmark = pytest.mark.django_db

User = get_user_model()


def build_histories(annual, life, today):
    """``{label: user}`` covering the cases the two implementations must share."""
    day = timedelta(days=1)

    def user(label: str):
        return UserFactory(email=f"{label}@example.test", roles=["member"])

    def term(owner, plan, starts_on, ends_on, status=MembershipStatusChoices.ACTIVE):
        return MembershipFactory(
            user=owner, plan=plan, starts_on=starts_on, ends_on=ends_on, status=status
        )

    histories: dict = {}

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

    cancelled = user("cancelled")
    term(
        cancelled,
        annual,
        today - 100 * day,
        today + 100 * day,
        MembershipStatusChoices.CANCELLED,
    )
    histories["cancelled-only"] = cancelled

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

    return histories


@pytest.fixture
def histories(annual_plan, life_plan, today):
    return build_histories(annual_plan, life_plan, today)


def test_annotations_match_the_membership_status_service(histories):
    annotated = {user.pk: user for user in member_admin_queryset()}
    for label, user in histories.items():
        expected = membership_status(user)
        actual = membership_payload(annotated[user.pk])
        assert actual == expected, label


@pytest.mark.parametrize(
    ("label", "expected_status", "is_lifetime"),
    [
        ("never", "none", False),
        ("current", "current", False),
        ("expired", "expired", False),
        ("stale-active", "expired", False),
        ("renewed-early", "current", False),
        ("three-back-to-back", "current", False),
        ("future-term-after-a-gap", "current", False),
        ("lifetime", "current", True),
        ("annual-then-life", "current", True),
        ("cancelled-only", "none", False),
        ("starts-in-the-future", "none", False),
        ("overlapping", "current", False),
        ("expired-with-a-future-term", "expired", False),
        ("ends-today", "current", False),
    ],
)
def test_expected_status_per_history(histories, label, expected_status, is_lifetime):
    user = member_admin_queryset().get(pk=histories[label].pk)
    payload = membership_payload(user)
    assert payload["status"] == expected_status
    assert payload["is_lifetime"] is is_lifetime


def test_coverage_stops_at_a_gap(histories, today):
    """A term starting after a break is not part of today's coverage."""
    user = member_admin_queryset().get(pk=histories["future-term-after-a-gap"].pk)
    assert membership_payload(user)["expires_on"] == today + timedelta(days=10)


def test_early_renewal_shows_the_new_expiry(histories, today):
    user = member_admin_queryset().get(pk=histories["renewed-early"].pk)
    assert membership_payload(user)["expires_on"] == today + timedelta(days=375)


def test_three_back_to_back_terms_chain_to_the_last(histories, today):
    user = member_admin_queryset().get(pk=histories["three-back-to-back"].pk)
    assert membership_payload(user)["expires_on"] == today + timedelta(days=394)


def test_lifetime_reports_the_life_plan(histories, life_plan):
    user = member_admin_queryset().get(pk=histories["annual-then-life"].pk)
    payload = membership_payload(user)
    assert payload["expires_on"] is None
    assert payload["plan"] == life_plan.name


def test_joined_on_is_the_earliest_term_start(histories, today):
    user = member_admin_queryset().get(pk=histories["three-back-to-back"].pk)
    assert user.joined_on == today - timedelta(days=700)
    assert member_admin_queryset().get(pk=histories["never"].pk).joined_on is None
