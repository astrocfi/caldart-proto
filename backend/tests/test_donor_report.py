"""The donors report: who gave through the public donation page, and how much.

``donor_rows`` aggregates every settled contribution from a ``donor`` account,
one row per account, and ``GET /admin/payments/donors`` answers the same rows
on screen, for the treasurer alone.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import AccountKind, User
from apps.darts.models import Dart
from apps.members.models import MemberProfile
from apps.payments.models import PaymentStatus
from apps.payments.reports import (
    DonorFilters,
    DonorReportQuerySerializer,
    donor_report_query,
    donor_rows,
)
from tests.factories import (
    DartFactory,
    MemberProfileFactory,
    PaymentFactory,
    RefundFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db


def _donor(
    *, email: str = "donor@example.test", first_name: str = "Dana", last_name: str = "Doe"
) -> User:
    """A donor account, otherwise built like any other user."""
    return UserFactory(
        email=email, first_name=first_name, last_name=last_name, kind=AccountKind.DONOR
    )


def _settled_gift(
    user: User, *, cents: int, on: date, status: str = PaymentStatus.SUCCEEDED
) -> None:
    """A settled contribution-only payment from ``user``, completed on ``on``."""
    PaymentFactory(
        user=user,
        plan=None,
        status=status,
        contribution_cents=cents,
        plan_amount_cents=0,
        amount_cents=cents,
        completed_at=datetime(on.year, on.month, on.day, 12, 0, tzinfo=UTC),
    )


def test_donor_rows_include_only_donor_accounts_who_gave() -> None:
    """A member's contribution never appears in the donors report."""
    donor = _donor(email="donor@example.test")
    member = UserFactory(email="member@example.test", kind=AccountKind.MEMBER)
    _settled_gift(donor, cents=5_000, on=date(2026, 3, 1))
    _settled_gift(member, cents=5_000, on=date(2026, 3, 1))

    rows = donor_rows(DonorFilters())

    assert [row["user_id"] for row in rows] == [donor.pk]


def test_donor_rows_ignore_a_gift_that_never_settled() -> None:
    """A pending or failed payment is not giving, so it never appears."""
    donor = _donor()
    _settled_gift(donor, cents=5_000, on=date(2026, 3, 1), status=PaymentStatus.PENDING)

    assert donor_rows(DonorFilters()) == []


def test_donor_rows_aggregate_a_donors_gifts() -> None:
    """``gifts``, ``given_cents``, and the first and last gift dates all add up."""
    donor = _donor()
    _settled_gift(donor, cents=2_000, on=date(2026, 1, 10))
    _settled_gift(donor, cents=3_000, on=date(2026, 6, 20))

    [row] = donor_rows(DonorFilters())

    assert (row["gifts"], row["given_cents"]) == (2, 5_000)
    assert (row["first_gift"], row["last_gift"]) == (date(2026, 1, 10), date(2026, 6, 20))


def test_donor_rows_net_a_refund_against_the_contribution() -> None:
    """A refund comes off the total given, leaving the difference as ``net_cents``."""
    donor = _donor()
    payment = PaymentFactory(
        user=donor,
        plan=None,
        status=PaymentStatus.SUCCEEDED,
        contribution_cents=10_000,
        plan_amount_cents=0,
        amount_cents=10_000,
        completed_at=datetime(2026, 4, 1, 12, 0, tzinfo=UTC),
    )
    RefundFactory(payment=payment, amount_cents=4_000)

    [row] = donor_rows(DonorFilters())

    assert (row["given_cents"], row["refunded_cents"], row["net_cents"]) == (10_000, 4_000, 6_000)


def test_donor_rows_read_contact_and_dart_from_the_profile(dart: Dart) -> None:
    """Phone, city, state, county, and DART come from the donor's own profile."""
    donor = _donor()
    MemberProfileFactory(
        user=donor,
        phone="415-555-0100",
        city="Concord",
        state="CA",
        county="Contra Costa",
        dart=dart,
    )
    _settled_gift(donor, cents=1_000, on=date(2026, 2, 1))

    [row] = donor_rows(DonorFilters())

    assert (row["phone"], row["city"], row["state"], row["county"], row["dart"]) == (
        "415-555-0100",
        "Concord",
        "CA",
        "Contra Costa",
        dart.name,
    )


def test_donor_rows_read_a_blank_profile_gracefully() -> None:
    """A donor with no profile row at all reports blank contact fields, not an error."""
    donor = _donor()
    MemberProfile.objects.filter(user=donor).delete()
    _settled_gift(donor, cents=1_000, on=date(2026, 2, 1))

    [row] = donor_rows(DonorFilters())

    assert (row["phone"], row["city"], row["county"], row["dart"]) == ("", "", "", "")


def test_donor_rows_are_ordered_by_net_giving_then_name() -> None:
    """The largest net giver leads; ties break on name."""
    big = _donor(email="big@example.test", first_name="Big", last_name="Giver")
    small = _donor(email="small@example.test", first_name="Small", last_name="Giver")
    _settled_gift(small, cents=1_000, on=date(2026, 1, 1))
    _settled_gift(big, cents=9_000, on=date(2026, 1, 1))

    rows = donor_rows(DonorFilters())

    assert [row["user_id"] for row in rows] == [big.pk, small.pk]


def test_donor_rows_filter_by_search() -> None:
    """``search`` matches a donor's name or email address."""
    match = _donor(email="wanted@example.test", first_name="Wanda", last_name="Nedry")
    other = _donor(email="other@example.test", first_name="Otto", last_name="Osgood")
    _settled_gift(match, cents=1_000, on=date(2026, 1, 1))
    _settled_gift(other, cents=1_000, on=date(2026, 1, 1))

    rows = donor_rows(DonorFilters(search="Wanda"))

    assert [row["user_id"] for row in rows] == [match.pk]


def test_donor_rows_filter_by_several_counties() -> None:
    """``county`` narrows to any of several counties at once."""
    alameda = _donor(email="alameda@example.test")
    marin = _donor(email="marin@example.test")
    napa = _donor(email="napa@example.test")
    for user, county in [(alameda, "Alameda"), (marin, "Marin"), (napa, "Napa")]:
        MemberProfileFactory(user=user, county=county)
        _settled_gift(user, cents=1_000, on=date(2026, 1, 1))

    rows = donor_rows(DonorFilters(county=("Alameda", "Marin")))

    assert {row["user_id"] for row in rows} == {alameda.pk, marin.pk}


def test_donor_rows_filter_by_dart_id() -> None:
    """A digit ``dart`` value matches the DART's id."""
    napa = DartFactory(name="Napa County DART")
    donor = _donor()
    MemberProfileFactory(user=donor, dart=napa)
    other = _donor(email="elsewhere@example.test")
    MemberProfileFactory(user=other, dart=DartFactory(name="Solano County DART"))
    _settled_gift(donor, cents=1_000, on=date(2026, 1, 1))
    _settled_gift(other, cents=1_000, on=date(2026, 1, 1))

    rows = donor_rows(DonorFilters(dart=str(napa.pk)))

    assert [row["user_id"] for row in rows] == [donor.pk]


def test_donor_rows_filter_by_dart_name_fragment() -> None:
    """A non-digit ``dart`` value matches a case-insensitive fragment of the name."""
    napa = DartFactory(name="Napa County DART")
    donor = _donor()
    MemberProfileFactory(user=donor, dart=napa)
    _settled_gift(donor, cents=1_000, on=date(2026, 1, 1))

    rows = donor_rows(DonorFilters(dart="napa"))

    assert [row["user_id"] for row in rows] == [donor.pk]


def test_donor_rows_filter_by_given_cents_bounds() -> None:
    """``min_cents`` and ``max_cents`` bound a donor's total giving, not one gift."""
    small = _donor(email="small@example.test")
    big = _donor(email="big@example.test")
    _settled_gift(small, cents=1_000, on=date(2026, 1, 1))
    _settled_gift(big, cents=50_000, on=date(2026, 1, 1))

    rows = donor_rows(DonorFilters(min_cents=10_000))

    assert [row["user_id"] for row in rows] == [big.pk]


def test_donor_rows_filter_by_date_range() -> None:
    """``date_from``/``date_to`` bound the range gifts are counted in."""
    donor = _donor()
    _settled_gift(donor, cents=1_000, on=date(2025, 1, 1))
    _settled_gift(donor, cents=2_000, on=date(2026, 6, 1))

    rows = donor_rows(DonorFilters(date_from=date(2026, 1, 1)))

    assert [row["given_cents"] for row in rows] == [2_000]


def test_donor_report_query_serializer_refuses_an_unknown_county() -> None:
    """A county California does not have is a 400 naming it."""
    serializer = DonorReportQuerySerializer(data={"county": "Atlantis"})
    assert serializer.is_valid() is False
    assert serializer.errors["county"] == ["Unknown county 'Atlantis'."]


def test_donor_report_query_serializer_accepts_several_counties() -> None:
    """A comma-separated ``county`` splits into the filter's tuple, stripped."""
    serializer = DonorReportQuerySerializer(data={"county": "Alameda, Marin"})
    assert serializer.is_valid() is True
    assert serializer.to_filters().county == ("Alameda", "Marin")


def test_donor_report_query_joins_several_counties_in_the_subtitle() -> None:
    """Several counties read as a list in the PDF subtitle, not the bare URL value."""
    query = donor_report_query({"county": "Alameda,Marin"})
    assert query.filters["county"] == "Alameda, Marin"


def test_treasurer_reads_the_donors_screen(treasurer_client: APIClient) -> None:
    """``GET /admin/payments/donors`` answers a treasurer with the aggregated rows."""
    donor = _donor(email="giver@example.test", first_name="Gil", last_name="Giver")
    _settled_gift(donor, cents=2_500, on=date(2026, 3, 1))

    response = treasurer_client.get("/api/v1/admin/payments/donors")

    assert response.status_code == 200
    body = response.json()
    assert [row["user_id"] for row in body] == [donor.pk]
    assert body[0]["given_cents"] == 2_500


def test_an_account_administrator_may_not_read_the_donors_screen(
    account_admin_client: APIClient,
) -> None:
    """The Donors screen is the treasurer's own; an account administrator is refused."""
    assert account_admin_client.get("/api/v1/admin/payments/donors").status_code == 403


def test_a_system_administrator_reads_the_donors_screen(system_admin_client: APIClient) -> None:
    """``system_admin`` reaches every role-gated endpoint, this one included."""
    assert system_admin_client.get("/api/v1/admin/payments/donors").status_code == 200


def test_an_anonymous_caller_may_not_read_the_donors_screen(api_client: APIClient) -> None:
    """Signed out, the endpoint is a 401, not a 403."""
    assert api_client.get("/api/v1/admin/payments/donors").status_code == 401


def test_the_donors_screen_refuses_an_unknown_county(treasurer_client: APIClient) -> None:
    """A 400 naming the county the server does not recognize."""
    response = treasurer_client.get("/api/v1/admin/payments/donors", {"county": "Atlantis"})
    assert response.status_code == 400
    assert response.json() == {"county": ["Unknown county 'Atlantis'."]}
