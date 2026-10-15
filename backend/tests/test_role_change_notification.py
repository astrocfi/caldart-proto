"""The ``roles_changed`` notification, whoever or whatever changed the roles.

A management command such as ``create_admin`` raises it like a signed-in administrator
does, and the email names *A command on the server* as the one who made the change.
System, user, and account administrators may subscribe to it.
"""

from __future__ import annotations

import pytest
from django.core.mail import EmailMessage
from django.core.management import call_command
from pytest_django.fixtures import DjangoCaptureOnCommitCallbacks
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import ACCOUNT_ADMIN, SYSTEM_ADMIN, USER_ADMIN, WEBSITE_ADMIN
from apps.notifications.messages import COMMAND_ACTOR_NAME, build_message
from apps.notifications.models import NotificationSubscription
from apps.notifications.services import account_may_receive
from caldart import audit
from tests.conftest import role_matrix

pytestmark = pytest.mark.django_db

#: The address subscribed to role changes.
WATCHER = "watch@example.test"


def test_the_message_names_a_command_as_the_actor(member: User) -> None:
    """A role change a server command made reads as the command's, not a person's."""
    message = build_message(
        "roles_changed",
        {"user": member, "added": [WEBSITE_ADMIN], "removed": [], "actor": audit.COMMAND_ACTOR},
    )

    assert message.headline == f"{COMMAND_ACTOR_NAME} changed Robin Ashby's roles"


def test_the_message_lists_what_a_command_added(member: User) -> None:
    """The lines are the same as for a person's change."""
    message = build_message(
        "roles_changed",
        {"user": member, "added": [WEBSITE_ADMIN], "removed": [], "actor": audit.COMMAND_ACTOR},
    )

    assert message.lines[:2] == (("Added", "Website administrator"), ("Removed", "None"))


def test_create_admin_mails_the_subscribers(
    capsys: pytest.CaptureFixture[str],
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """The first administrator's roles are a role change like any other."""
    NotificationSubscription.objects.create(recipient_email=WATCHER, events=["roles_changed"])
    with django_capture_on_commit_callbacks(execute=True):
        call_command("create_admin", email="new.admin@example.test")

    subjects = [message.subject for message in mailoutbox if message.to == [WATCHER]]
    assert subjects == [f"CalDART: {COMMAND_ACTOR_NAME} changed new.admin@example.test's roles"]


def test_a_portal_role_change_mails_the_subscribers(
    system_admin_client: APIClient,
    member: User,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """A change on the user record names the administrator who made it."""
    NotificationSubscription.objects.create(recipient_email=WATCHER, events=["roles_changed"])
    with django_capture_on_commit_callbacks(execute=True):
        system_admin_client.patch(
            f"/api/v1/admin/users/{member.pk}", {"roles": ["member", "treasurer"]}, format="json"
        )

    subjects = [message.subject for message in mailoutbox if message.to == [WATCHER]]
    assert subjects == ["CalDART: Avery Stroud changed Robin Ashby's roles"]


@pytest.mark.parametrize(("slug", "allowed"), role_matrix(USER_ADMIN, ACCOUNT_ADMIN, SYSTEM_ADMIN))
def test_who_may_receive_role_changes(
    all_role_users: dict[str, User], slug: str, allowed: bool
) -> None:
    """System, user, and account administrators hear of role changes."""
    assert account_may_receive(all_role_users[slug], "roles_changed") is allowed
