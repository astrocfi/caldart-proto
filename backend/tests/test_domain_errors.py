"""The domain errors services raise, and the HTTP answers they become.

Services never import DRF: they refuse work by raising a ``DomainError``, and
``caldart.exceptions.caldart_exception_handler`` is the one place that turns
those refusals into a response.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from caldart.exceptions import (
    DomainError,
    DomainPermissionError,
    DomainValidationError,
    caldart_exception_handler,
)

pytestmark = pytest.mark.django_db

ME = "/api/v1/auth/me"

UNKNOWN_PLAN = "Unknown membership plan 'platinum'."
SELF_DELETE = "You cannot delete your own account."


def test_domain_validation_error_carries_its_field_and_message() -> None:
    error = DomainValidationError("plan", UNKNOWN_PLAN)
    assert error.field == "plan"


def test_domain_validation_error_stringifies_as_its_message() -> None:
    assert str(DomainValidationError("plan", UNKNOWN_PLAN)) == UNKNOWN_PLAN


def test_domain_permission_error_is_a_domain_error() -> None:
    assert isinstance(DomainPermissionError(SELF_DELETE), DomainError)


def test_a_validation_error_becomes_a_400_keyed_by_its_field() -> None:
    response = caldart_exception_handler(DomainValidationError("plan", UNKNOWN_PLAN), {})
    assert response.status_code == 400


def test_a_validation_error_body_lists_the_message_under_the_field() -> None:
    response = caldart_exception_handler(DomainValidationError("plan", UNKNOWN_PLAN), {})
    assert response.data == {"plan": [UNKNOWN_PLAN]}


def test_a_permission_error_becomes_a_403() -> None:
    response = caldart_exception_handler(DomainPermissionError(SELF_DELETE), {})
    assert response.status_code == 403


def test_a_permission_error_body_is_a_bare_detail() -> None:
    response = caldart_exception_handler(DomainPermissionError(SELF_DELETE), {})
    assert response.data == {"detail": SELF_DELETE}


def test_an_exception_the_handler_does_not_know_is_left_to_django() -> None:
    """A bug must still reach Django's 500 handling rather than become a 400."""
    assert caldart_exception_handler(RuntimeError("boom"), {}) is None


def test_an_unauthenticated_request_is_still_401(api_client: APIClient) -> None:
    assert api_client.get(ME).status_code == 401
