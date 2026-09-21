"""The query parameters the three payment-report endpoints share.

``GET /admin/payments``, ``/admin/payments/summary`` and
``/admin/payments/export.csv`` read the same parameters, so they refuse the same
input the same way, with the complaint keyed by the parameter it came from.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.django_db

LIST = "/api/v1/admin/payments"
SUMMARY = "/api/v1/admin/payments/summary"
EXPORT = "/api/v1/admin/payments/export.csv"
REPORTS = [LIST, SUMMARY, EXPORT]

DATE_MESSAGE = "Expected a date as YYYY-MM-DD."
IMPOSSIBLE_DATE = "2026-02-30"


@pytest.fixture
def report_client(api_client, account_admin):
    """An API client signed in as an account administrator."""
    api_client.force_login(account_admin)
    return api_client


@pytest.mark.parametrize("url", REPORTS)
def test_an_impossible_date_is_refused(report_client, url: str) -> None:
    """The 30th of February parses as a date and then fails: a 400, not a 500."""
    assert report_client.get(url, {"from": IMPOSSIBLE_DATE}).status_code == 400


@pytest.mark.parametrize("url", REPORTS)
def test_the_impossible_date_complaint_names_the_from_parameter(report_client, url: str) -> None:
    assert report_client.get(url, {"from": IMPOSSIBLE_DATE}).json() == {"from": [DATE_MESSAGE]}


@pytest.mark.parametrize("url", REPORTS)
def test_an_impossible_upper_bound_is_refused(report_client, url: str) -> None:
    assert report_client.get(url, {"to": IMPOSSIBLE_DATE}).json() == {"to": [DATE_MESSAGE]}


@pytest.mark.parametrize("url", REPORTS)
def test_an_unreadable_date_is_refused(report_client, url: str) -> None:
    assert report_client.get(url, {"from": "last tuesday"}).json() == {"from": [DATE_MESSAGE]}


@pytest.mark.parametrize("url", REPORTS)
def test_an_unknown_provider_is_refused(report_client, url: str) -> None:
    assert report_client.get(url, {"provider": "bitcoin"}).json() == {
        "provider": ["Unknown provider 'bitcoin'."]
    }


@pytest.mark.parametrize("url", REPORTS)
def test_an_unknown_status_is_refused(report_client, url: str) -> None:
    assert report_client.get(url, {"status": "chargeback"}).json() == {
        "status": ["Unknown status 'chargeback'."]
    }


@pytest.mark.parametrize("url", REPORTS)
def test_an_unknown_grouping_is_refused(report_client, url: str) -> None:
    assert report_client.get(url, {"group": "week"}).json() == {
        "group": ["Expected 'month' or 'year'."]
    }


@pytest.mark.parametrize("url", REPORTS)
def test_an_empty_date_is_no_bound_at_all(report_client, url: str) -> None:
    """The report screen sends every parameter, empty or not."""
    assert report_client.get(url, {"from": "", "to": ""}).status_code == 200


@pytest.mark.parametrize("url", REPORTS)
def test_an_empty_provider_and_status_are_no_filter(report_client, url: str) -> None:
    assert report_client.get(url, {"provider": "", "status": "", "group": ""}).status_code == 200


def test_a_real_date_range_still_filters(report_client, member, payment_factory) -> None:
    payment_factory(user=member)
    assert report_client.get(LIST, {"from": "2026-01-01"}).data["count"] == 1
