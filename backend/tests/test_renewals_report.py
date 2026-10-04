"""The renewals report: the Renewals tab's table of standing authorities, as a file.

The role matrix, the columns endpoint, and the dated download are covered for every
report in ``test_report_endpoints.py``; this module covers what the renewals report
prints and how its filters narrow it, against the list it downloads.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.payments.models import MandateCadence, MandateStatus, RenewalMandate
from tests.conftest import read_csv
from tests.factories import RenewalMandateFactory, UserFactory

pytestmark = pytest.mark.django_db

EXPORT = "/api/v1/reports/renewals/export.csv"
LIST = "/api/v1/admin/renewals"

DEFAULT_HEADER = ["Member", "Email", "Type", "Plan", "Next charge", "Due", "Method", "Status"]


@pytest.fixture
def ada() -> User:
    """A member named Ada Byron, whose renewal the tests read."""
    return UserFactory(email="ada@example.test", first_name="Ada", last_name="Byron")


@pytest.fixture
def ada_renewal(ada: User) -> RenewalMandate:
    """Ada's automatic renewal of the annual plan, on, with a $10 contribution."""
    return RenewalMandateFactory(user=ada, contribution_cents=1_000)


@pytest.fixture
def grace_donation() -> RenewalMandate:
    """Grace Hopper's monthly recurring donation of $25, turned off."""
    grace = UserFactory(email="grace@example.test", first_name="Grace", last_name="Hopper")
    return RenewalMandateFactory(
        user=grace,
        plan=None,
        contribution_cents=2_500,
        cadence=MandateCadence.MONTHLY,
        status=MandateStatus.CANCELED,
        method_label="PayPal account grace@example.test",
    )


def test_the_download_carries_the_tabs_columns_by_default(
    treasurer_client: APIClient, ada_renewal: RenewalMandate
) -> None:
    """With no ``columns``, the file holds the Renewals tab's own eight columns."""
    assert read_csv(treasurer_client.get(EXPORT))[0] == DEFAULT_HEADER


def test_a_row_reads_as_the_renewal_reads_on_the_tab(
    treasurer_client: APIClient, ada_renewal: RenewalMandate
) -> None:
    """Name, address, kind, plan, amount, due day, method, and status, as listed."""
    listed = treasurer_client.get(LIST).json()["results"][0]
    row = read_csv(treasurer_client.get(EXPORT))[1]

    assert row == [
        "Ada Byron",
        "ada@example.test",
        "Automatic renewal and contribution",
        "Annual",
        "55.00",
        listed["next_charge_on"] or "",
        "Test card ending 4242, expires 12/2030",
        "On",
    ]


def test_a_recurring_donation_has_no_plan_and_names_its_cadence(
    treasurer_client: APIClient, grace_donation: RenewalMandate
) -> None:
    """A donation renews no plan; its cadence is a column to ask for."""
    rows = read_csv(treasurer_client.get(EXPORT, {"columns": "kind,plan,cadence,status"}))
    assert rows[1] == ["Recurring donation", "", "Monthly", "Turned off"]


@pytest.mark.parametrize(
    ("params", "names"),
    [
        ({"status": "canceled"}, ["Grace Hopper"]),
        ({"kind": "both"}, ["Ada Byron"]),
        ({"kind": "contribution"}, ["Grace Hopper"]),
        ({"search": "byron"}, ["Ada Byron"]),
        ({"search": "paypal grace"}, ["Grace Hopper"]),
        ({}, ["Grace Hopper", "Ada Byron"]),
    ],
    ids=["status", "renewal-and-contribution", "donation", "surname", "method-words", "none"],
)
def test_the_filters_narrow_the_download_as_they_narrow_the_list(
    treasurer_client: APIClient,
    ada_renewal: RenewalMandate,
    grace_donation: RenewalMandate,
    params: dict[str, str],
    names: list[str],
) -> None:
    """Status, kind, and every word of a search keep the same rows, newest first."""
    downloaded = [row[0] for row in read_csv(treasurer_client.get(EXPORT, params))[1:]]
    listed = [row["user_name"] for row in treasurer_client.get(LIST, params).json()["results"]]
    assert (downloaded, listed) == (names, names)


@pytest.mark.parametrize(
    ("params", "body"),
    [
        ({"status": "sleeping"}, {"status": ["Unknown status 'sleeping'."]}),
        ({"kind": "gift"}, {"kind": ["Unknown kind 'gift'."]}),
    ],
    ids=["status", "kind"],
)
def test_an_unknown_filter_value_is_a_400(
    treasurer_client: APIClient, params: dict[str, str], body: dict[str, list[str]]
) -> None:
    """A status or a kind outside the mandate's own is refused, keyed by the filter."""
    response = treasurer_client.get(EXPORT, params)
    assert (response.status_code, response.json()) == (400, body)
