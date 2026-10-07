"""The API answers a missing or blank form field in plain words, not DRF's stock text.

Each case posts a form with one field left out or blank, the way a person leaves a box
empty, and reads back the sentence the screen shows under that box.
"""

from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from tests.conftest import CHANGE_URL, LOGIN_URL, REGISTER_URL, RESET_URL, register_payload

pytestmark = pytest.mark.django_db

TEMPLATES_URL = "/api/v1/bulk-email/templates"
GROUPS_URL = "/api/v1/bulk-email/groups"
EMAIL_TYPES_URL = "/api/v1/email-types"
NOTIFICATIONS_URL = "/api/v1/notifications/subscriptions"
REPORT_SUBSCRIPTIONS_URL = "/api/v1/reports/subscriptions"
COLUMN_SETS_URL = "/api/v1/reports/members/column-sets"
DEACTIVATE_URL = "/api/v1/auth/deactivate"
CHANGE_EMAIL_URL = "/api/v1/auth/email/change"
MEMBERS_URL = "/api/v1/admin/members"
DONATION_URL = "/api/v1/donations/checkout"


@pytest.fixture
def member_api(api_client: APIClient, member: User) -> APIClient:
    """An API client signed in as the plain member."""
    api_client.force_login(member)
    return api_client


@pytest.mark.parametrize(
    ("client_name", "url", "body", "field", "message"),
    [
        (
            "api_client",
            REGISTER_URL,
            register_payload(first_name=""),
            "first_name",
            "Enter your first name.",
        ),
        (
            "api_client",
            REGISTER_URL,
            register_payload(last_name=""),
            "last_name",
            "Enter your last name.",
        ),
        (
            "api_client",
            REGISTER_URL,
            register_payload(email=""),
            "email",
            "Enter your email address.",
        ),
        (
            "api_client",
            REGISTER_URL,
            register_payload(email="nora.example.test"),
            "email",
            "Enter an email address, such as name@example.org.",
        ),
        (
            "api_client",
            REGISTER_URL,
            register_payload(password=""),
            "password",
            "Choose a password.",
        ),
        (
            "api_client",
            LOGIN_URL,
            {"email": "", "password": "x"},
            "email",
            "Enter your email address.",
        ),
        ("api_client", LOGIN_URL, {"email": "a@example.org"}, "password", "Enter your password."),
        ("api_client", RESET_URL, {"email": ""}, "email", "Enter your email address."),
        (
            "member_api",
            CHANGE_URL,
            {"current_password": "", "new_password": "Sierra-Foothills-2027"},
            "current_password",
            "Enter your current password.",
        ),
        (
            "member_api",
            CHANGE_URL,
            {"current_password": "x", "new_password": ""},
            "new_password",
            "Choose a new password.",
        ),
        ("member_api", DEACTIVATE_URL, {}, "current_password", "Enter your current password."),
        (
            "member_api",
            CHANGE_EMAIL_URL,
            {"email": "", "current_password": "x"},
            "email",
            "Enter the new address.",
        ),
        (
            "member_api",
            CHANGE_EMAIL_URL,
            {"email": "nora.example.test", "current_password": "x"},
            "email",
            "Enter an email address, such as name@example.org.",
        ),
        (
            "member_api",
            CHANGE_EMAIL_URL,
            {"email": "nora@example.test", "current_password": ""},
            "current_password",
            "Enter your current password.",
        ),
        ("account_admin_client", MEMBERS_URL, {"email": ""}, "email", "Enter their email address."),
        (
            "api_client",
            DONATION_URL,
            {"first_name": "", "last_name": "Bright", "email": "nora@example.test"},
            "first_name",
            "Enter your first name.",
        ),
        (
            "api_client",
            DONATION_URL,
            {"first_name": "Nora", "last_name": "Bright", "email": ""},
            "email",
            "Enter your email address.",
        ),
        (
            "management_client",
            TEMPLATES_URL,
            {"name": "", "subject": "", "body": ""},
            "name",
            "Give the template a name.",
        ),
        (
            "management_client",
            GROUPS_URL,
            {"name": "", "kind": "fixed"},
            "name",
            "Give the group a name.",
        ),
        (
            "system_admin_client",
            EMAIL_TYPES_URL,
            {"name": "", "description": "x", "allow_opt_out": True, "sender_roles": []},
            "name",
            "Give the email type a name.",
        ),
        (
            "system_admin_client",
            EMAIL_TYPES_URL,
            {"name": "Board News", "description": "", "allow_opt_out": True, "sender_roles": []},
            "description",
            "Say in one sentence what this email is for.",
        ),
        (
            "account_admin_client",
            NOTIFICATIONS_URL,
            {"recipient_email": "", "events": ["member.joined"]},
            "recipient_email",
            "Enter the address to email.",
        ),
        (
            "account_admin_client",
            REPORT_SUBSCRIPTIONS_URL,
            {"report": "members", "recipient_email": "", "formats": "csv", "cadence": "monthly"},
            "recipient_email",
            "Enter the address to email.",
        ),
        (
            "account_admin_client",
            COLUMN_SETS_URL,
            {"name": "", "columns": ["name"]},
            "name",
            "Give the set of columns a name.",
        ),
    ],
    ids=[
        "register-first-name",
        "register-last-name",
        "register-email-blank",
        "register-email-malformed",
        "register-password",
        "login-email",
        "login-password",
        "reset-email",
        "change-current-password",
        "change-new-password",
        "deactivate-current-password",
        "change-email-blank",
        "change-email-malformed",
        "change-email-password",
        "new-member-email",
        "donation-first-name",
        "donation-email",
        "template-name",
        "group-name",
        "email-type-name",
        "email-type-description",
        "notification-address",
        "report-subscription-address",
        "column-set-name",
    ],
)
def test_a_missing_field_is_answered_in_plain_words(
    request: pytest.FixtureRequest,
    client_name: str,
    url: str,
    body: dict[str, Any],
    field: str,
    message: str,
) -> None:
    """The 400 names the field with the sentence written for it."""
    client: APIClient = request.getfixturevalue(client_name)
    response = client.post(url, body, format="json")
    assert response.status_code == 400
    assert response.json()[field] == [message]
