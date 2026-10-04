"""Whether bounce checking is set up, read before anyone presses Run now.

``GET /system/bounces`` answers ``{"enabled": <bool>}``, true when a bounce mailbox is
configured (``BOUNCE_IMAP_URL``), so the Scheduled screen can say bounce checking is off
and hold its Run now back from the start.
"""

from __future__ import annotations

import pytest
from pytest_django import Settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import SYSTEM_ADMIN
from tests.conftest import role_matrix

pytestmark = pytest.mark.django_db

STATUS_URL = "/api/v1/system/bounces"


@pytest.mark.parametrize(("role", "allowed"), role_matrix(SYSTEM_ADMIN))
def test_only_a_system_administrator_reads_the_bounce_status(
    api_client: APIClient, all_role_users: dict[str, User], role: str, allowed: bool
) -> None:
    """Every other role is refused with a 403."""
    api_client.force_login(all_role_users[role])
    assert api_client.get(STATUS_URL).status_code == (200 if allowed else 403)


@pytest.mark.parametrize(
    ("url", "enabled"),
    [("", False), ("imaps://bounce:secret@mail.example.test/INBOX", True)],
    ids=["no-mailbox", "mailbox"],
)
def test_the_status_says_whether_a_bounce_mailbox_is_set_up(
    system_admin_client: APIClient, settings: Settings, url: str, enabled: bool
) -> None:
    """``enabled`` follows ``BOUNCE_IMAP_URL``, and nothing is read from the mailbox."""
    settings.BOUNCE_IMAP_URL = url
    assert system_admin_client.get(STATUS_URL).json() == {"enabled": enabled}
