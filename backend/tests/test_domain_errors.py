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
from tests.conftest import ME_URL

pytestmark = pytest.mark.django_db


UNKNOWN_PLAN = "Unknown membership plan 'platinum'."
SELF_DELETE = "You cannot delete your own account."


def test_domain_validation_error_carries_its_field_and_message() -> None:
    """A ``DomainValidationError`` exposes the field name it was raised for."""
    error = DomainValidationError("plan", UNKNOWN_PLAN)
    assert error.field == "plan"


def test_domain_validation_error_stringifies_as_its_message() -> None:
    """Stringifying a ``DomainValidationError`` yields its message alone."""
    assert str(DomainValidationError("plan", UNKNOWN_PLAN)) == UNKNOWN_PLAN


def test_domain_permission_error_is_a_domain_error() -> None:
    """``DomainPermissionError`` is a subclass of ``DomainError``."""
    assert isinstance(DomainPermissionError(SELF_DELETE), DomainError)


def test_a_validation_error_becomes_a_400_keyed_by_its_field() -> None:
    """The handler turns a ``DomainValidationError`` into a 400 response."""
    response = caldart_exception_handler(DomainValidationError("plan", UNKNOWN_PLAN), {})
    assert response is not None
    assert response.status_code == 400


def test_a_validation_error_body_lists_the_message_under_the_field() -> None:
    """The 400 body maps the error's field name to a list holding its message."""
    response = caldart_exception_handler(DomainValidationError("plan", UNKNOWN_PLAN), {})
    assert response is not None
    # The handler returns an unrendered DRF ``Response``, so read ``data`` directly.
    assert response.data == {"plan": [UNKNOWN_PLAN]}


def test_a_permission_error_becomes_a_403() -> None:
    """The handler turns a ``DomainPermissionError`` into a 403 response."""
    response = caldart_exception_handler(DomainPermissionError(SELF_DELETE), {})
    assert response is not None
    assert response.status_code == 403


def test_a_permission_error_body_is_a_bare_detail() -> None:
    """The 403 body is ``{"detail": <message>}`` with no field key."""
    response = caldart_exception_handler(DomainPermissionError(SELF_DELETE), {})
    assert response is not None
    assert response.data == {"detail": SELF_DELETE}


def test_an_exception_the_handler_does_not_know_is_left_to_django() -> None:
    """A bug must still reach Django's 500 handling rather than become a 400."""
    assert caldart_exception_handler(RuntimeError("boom"), {}) is None


def test_an_unauthenticated_request_is_still_401(api_client: APIClient) -> None:
    """A request with no session cookie gets a 401 from the ``me`` endpoint."""
    assert api_client.get(ME_URL).status_code == 401
