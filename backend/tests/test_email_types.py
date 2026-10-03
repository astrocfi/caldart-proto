"""The email types: a system administrator's screen, and which types each sender may use.

The behavior is documented in ``docs/developer/api-email-types.rst``.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.db.models import ProtectedError
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import DART_LEADER, MANAGEMENT, MEMBER, ROLE_SLUGS, SYSTEM_ADMIN
from apps.mail.models import EmailOptOut, EmailType
from tests.conftest import audit_messages, role_matrix
from tests.factories import EmailOptOutFactory, EmailTypeFactory, UserFactory

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("no_email_types")]

LIST_URL = "/api/v1/email-types"
SENDABLE_URL = "/api/v1/email-types/sendable"


def detail_url(email_type: EmailType | int) -> str:
    """``/email-types/{id}`` for ``email_type`` or a bare id."""
    pk = email_type if isinstance(email_type, int) else email_type.pk
    return f"{LIST_URL}/{pk}"


def payload(**overrides: Any) -> dict[str, Any]:
    """A valid body for ``POST /email-types``, with ``overrides`` applied."""
    body: dict[str, Any] = {
        "name": "Newsletter",
        "description": "The quarterly newsletter.",
        "allow_opt_out": True,
        "sender_roles": [MANAGEMENT],
    }
    return {**body, **overrides}


@pytest.fixture
def seeded_types(no_email_types: None) -> dict[str, EmailType]:
    """Operational, Fundraising, and Mission, with the seed's senders, by name."""
    return {
        "Operational": EmailTypeFactory(
            name="Operational", position=1, sender_roles=[DART_LEADER, MANAGEMENT]
        ),
        "Fundraising": EmailTypeFactory(name="Fundraising", position=2, sender_roles=[MANAGEMENT]),
        "Mission": EmailTypeFactory(
            name="Mission", position=3, sender_roles=[DART_LEADER, MANAGEMENT]
        ),
    }


# -- reading ---------------------------------------------------------------
def test_the_list_is_in_position_order_then_by_name(system_admin_client: APIClient) -> None:
    """Types sharing a position fall back to their names."""
    EmailTypeFactory(name="Zulu", position=1)
    EmailTypeFactory(name="Alpha", position=2)
    EmailTypeFactory(name="Mike", position=1)

    response = system_admin_client.get(LIST_URL)

    assert [row["name"] for row in response.json()] == ["Mike", "Zulu", "Alpha"]


def test_a_listed_type_carries_every_setting(system_admin_client: APIClient) -> None:
    """A row is the id, name, slug, description, opt-out flag, senders, and place."""
    email_type = EmailTypeFactory(
        name="Mission Requests",
        description="Pilots wanted.",
        allow_opt_out=False,
        sender_roles=[DART_LEADER],
        position=4,
    )

    response = system_admin_client.get(LIST_URL)

    assert response.json() == [
        {
            "id": email_type.pk,
            "name": "Mission Requests",
            "slug": "mission-requests",
            "description": "Pilots wanted.",
            "allow_opt_out": False,
            "sender_roles": [DART_LEADER],
            "position": 4,
        }
    ]


# -- creating --------------------------------------------------------------
def test_a_created_type_answers_201_with_its_slug(system_admin_client: APIClient) -> None:
    """The slug is made from the name."""
    response = system_admin_client.post(LIST_URL, payload(name="Board News"), format="json")

    assert response.status_code == 201
    assert response.json()["slug"] == "board-news"


def test_a_created_type_goes_after_every_other(system_admin_client: APIClient) -> None:
    """Without a position, a type takes the place after the highest."""
    EmailTypeFactory(position=7)

    response = system_admin_client.post(LIST_URL, payload(), format="json")

    assert response.json()["position"] == 8


def test_the_first_type_takes_position_one(system_admin_client: APIClient) -> None:
    """With no other type, a new one is first."""
    response = system_admin_client.post(LIST_URL, payload(), format="json")

    assert response.json()["position"] == 1


def test_a_given_position_is_kept(system_admin_client: APIClient) -> None:
    """A position in the body is used as given."""
    response = system_admin_client.post(LIST_URL, payload(position=0), format="json")

    assert response.json()["position"] == 0


def test_sender_roles_are_stored_once_each_in_role_order(
    system_admin_client: APIClient,
) -> None:
    """Roles given twice or out of order come back once each, leader first."""
    response = system_admin_client.post(
        LIST_URL,
        payload(sender_roles=[MANAGEMENT, DART_LEADER, MANAGEMENT]),
        format="json",
    )

    assert response.json()["sender_roles"] == [DART_LEADER, MANAGEMENT]


def test_creating_a_type_is_audited(
    system_admin_client: APIClient, system_admin: User, audit_log: pytest.LogCaptureFixture
) -> None:
    """One ``email_type.create`` line names the administrator and the new type."""
    response = system_admin_client.post(LIST_URL, payload(), format="json")

    assert audit_messages(audit_log) == [
        f"action=email_type.create actor={system_admin.pk} target={response.json()['id']}"
    ]


@pytest.mark.parametrize(
    "name",
    ["Mission", "mission", "MISSION!"],
    ids=["same", "lower-case", "punctuated"],
)
def test_a_name_another_type_holds_is_refused(system_admin_client: APIClient, name: str) -> None:
    """Two types cannot share a name, whatever its case or punctuation."""
    EmailTypeFactory(name="Mission")

    response = system_admin_client.post(LIST_URL, payload(name=name), format="json")

    assert response.status_code == 400
    assert response.json() == {"name": ["Another email type already has this name."]}


def test_a_name_with_no_letters_is_refused(system_admin_client: APIClient) -> None:
    """A name must carry a letter or a digit to make a slug from."""
    response = system_admin_client.post(LIST_URL, payload(name="!!!"), format="json")

    assert response.status_code == 400
    assert response.json() == {"name": ["Use at least one letter or digit in the name."]}


@pytest.mark.parametrize("role", [MEMBER, SYSTEM_ADMIN, "pilot"])
def test_a_role_that_cannot_send_bulk_email_is_refused(
    system_admin_client: APIClient, role: str
) -> None:
    """Only a DART leader or CalDART management can be named as a sender."""
    response = system_admin_client.post(LIST_URL, payload(sender_roles=[role]), format="json")

    assert response.status_code == 400
    assert list(response.json()) == ["sender_roles"]


def test_a_type_needs_a_description(system_admin_client: APIClient) -> None:
    """The description is what a member reads beside the switch, so it is required."""
    response = system_admin_client.post(LIST_URL, payload(description=""), format="json")

    assert response.status_code == 400
    assert list(response.json()) == ["description"]


# -- changing --------------------------------------------------------------
def test_a_rename_moves_the_slug(system_admin_client: APIClient) -> None:
    """The slug follows the name on every save."""
    email_type = EmailTypeFactory(name="Mission")

    response = system_admin_client.put(
        detail_url(email_type), payload(name="Mission Calls"), format="json"
    )

    assert response.json()["slug"] == "mission-calls"


def test_a_type_may_keep_its_own_name(system_admin_client: APIClient) -> None:
    """Saving a type unchanged is not a clash with itself."""
    email_type = EmailTypeFactory(name="Mission")

    response = system_admin_client.put(
        detail_url(email_type), payload(name="Mission"), format="json"
    )

    assert response.status_code == 200


def test_an_edit_without_a_position_keeps_the_place(system_admin_client: APIClient) -> None:
    """Leaving the position out leaves it where it was."""
    email_type = EmailTypeFactory(position=5)

    response = system_admin_client.put(detail_url(email_type), payload(), format="json")

    assert response.json()["position"] == 5


def test_an_edit_takes_another_types_name_only_if_free(system_admin_client: APIClient) -> None:
    """Renaming a type to a name another holds is refused."""
    EmailTypeFactory(name="Fundraising")
    email_type = EmailTypeFactory(name="Mission")

    response = system_admin_client.put(
        detail_url(email_type), payload(name="fundraising"), format="json"
    )

    assert response.status_code == 400
    assert response.json() == {"name": ["Another email type already has this name."]}


def test_turning_opt_out_off_keeps_the_recorded_opt_outs(system_admin_client: APIClient) -> None:
    """The opt-outs wait, unapplied, for opting out to be allowed again."""
    opt_out = EmailOptOutFactory()

    system_admin_client.put(
        detail_url(opt_out.email_type),
        payload(name=opt_out.email_type.name, allow_opt_out=False),
        format="json",
    )

    assert EmailOptOut.objects.filter(pk=opt_out.pk).exists()


def test_changing_a_type_is_audited(
    system_admin_client: APIClient, system_admin: User, audit_log: pytest.LogCaptureFixture
) -> None:
    """One ``email_type.update`` line names the administrator and the type."""
    email_type = EmailTypeFactory()

    system_admin_client.put(detail_url(email_type), payload(), format="json")

    assert audit_messages(audit_log) == [
        f"action=email_type.update actor={system_admin.pk} target={email_type.pk}"
    ]


def test_changing_an_unknown_type_is_a_404(system_admin_client: APIClient) -> None:
    """An id no type carries is not found."""
    assert system_admin_client.put(detail_url(999_999), payload(), format="json").status_code == (
        404
    )


# -- deleting --------------------------------------------------------------
def test_deleting_a_type_removes_its_opt_outs(system_admin_client: APIClient) -> None:
    """The opt-outs of a deleted type go with it."""
    opt_out = EmailOptOutFactory()

    response = system_admin_client.delete(detail_url(opt_out.email_type))

    assert response.status_code == 204
    assert not EmailOptOut.objects.filter(pk=opt_out.pk).exists()


def test_deleting_a_type_is_audited(
    system_admin_client: APIClient, system_admin: User, audit_log: pytest.LogCaptureFixture
) -> None:
    """One ``email_type.delete`` line names the administrator and the type's old id."""
    email_type = EmailTypeFactory()
    pk = email_type.pk

    system_admin_client.delete(detail_url(email_type))

    assert audit_messages(audit_log) == [
        f"action=email_type.delete actor={system_admin.pk} target={pk}"
    ]


@pytest.fixture
def protected_delete(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every type delete raise ``ProtectedError``, as one a bulk email names does."""

    def refuse(self: EmailType, *args: object, **kwargs: object) -> None:
        """Raise what Django raises for a row a ``PROTECT`` key still points at."""
        raise ProtectedError("A bulk email names this type.", set())

    monkeypatch.setattr(EmailType, "delete", refuse)


@pytest.mark.usefixtures("protected_delete")
def test_a_type_in_use_cannot_be_deleted(
    system_admin_client: APIClient, audit_log: pytest.LogCaptureFixture
) -> None:
    """The refusal names the type and says what to do instead, and nothing is audited."""
    email_type = EmailTypeFactory(name="Fundraising")

    response = system_admin_client.delete(detail_url(email_type))

    assert response.status_code == 400
    assert response.json() == {
        "detail": (
            "Fundraising has been used for a bulk email, so it cannot be deleted. To stop "
            "anyone sending it, take every role off it instead."
        )
    }
    assert audit_messages(audit_log) == []


def test_deleting_an_unknown_type_is_a_404(system_admin_client: APIClient) -> None:
    """An id no type carries is not found."""
    assert system_admin_client.delete(detail_url(999_999)).status_code == 404


# -- who may send what -----------------------------------------------------
@pytest.mark.parametrize(
    ("roles", "expected"),
    [
        ([MEMBER], []),
        ([MEMBER, DART_LEADER], ["Operational", "Mission"]),
        ([MEMBER, MANAGEMENT], ["Operational", "Fundraising", "Mission"]),
        ([MEMBER, DART_LEADER, MANAGEMENT], ["Operational", "Fundraising", "Mission"]),
        ([MEMBER, SYSTEM_ADMIN], ["Operational", "Fundraising", "Mission"]),
    ],
    ids=["member", "dart-leader", "management", "leader-and-management", "system-admin"],
)
@pytest.mark.usefixtures("seeded_types")
def test_a_sender_is_offered_the_types_their_roles_send(
    api_client: APIClient, roles: list[str], expected: list[str]
) -> None:
    """Each type lists the roles that send it; a system administrator sends them all."""
    api_client.force_login(UserFactory(roles=roles))

    response = api_client.get(SENDABLE_URL)

    assert [row["name"] for row in response.json()] == expected


def test_a_type_nobody_is_named_for_is_the_system_administrators_alone(
    api_client: APIClient, management: User, system_admin: User
) -> None:
    """A type with no sender roles is offered to a system administrator only."""
    EmailTypeFactory(name="Board", sender_roles=[])

    api_client.force_login(management)
    assert api_client.get(SENDABLE_URL).json() == []
    api_client.force_login(system_admin)
    assert [row["name"] for row in api_client.get(SENDABLE_URL).json()] == ["Board"]


def test_a_sendable_type_carries_what_the_compose_screen_shows(
    api_client: APIClient, management: User
) -> None:
    """A row is the type's id, name, description, and opt-out flag."""
    email_type = EmailTypeFactory(name="Mission", description="Pilots wanted.")
    api_client.force_login(management)

    response = api_client.get(SENDABLE_URL)

    assert response.json() == [
        {
            "id": email_type.pk,
            "name": "Mission",
            "description": "Pilots wanted.",
            "allow_opt_out": True,
        }
    ]


# -- permissions -----------------------------------------------------------
@pytest.mark.parametrize(("slug", "allowed"), role_matrix(SYSTEM_ADMIN))
def test_reading_the_types_is_the_system_administrators(
    api_client: APIClient, all_role_users: dict[str, User], slug: str, allowed: bool
) -> None:
    """Only a system administrator lists the types."""
    api_client.force_login(all_role_users[slug])
    assert api_client.get(LIST_URL).status_code == (200 if allowed else 403)


@pytest.mark.parametrize(("slug", "allowed"), role_matrix(SYSTEM_ADMIN))
def test_creating_a_type_is_the_system_administrators(
    api_client: APIClient, all_role_users: dict[str, User], slug: str, allowed: bool
) -> None:
    """Only a system administrator adds a type."""
    api_client.force_login(all_role_users[slug])
    response = api_client.post(LIST_URL, payload(), format="json")
    assert response.status_code == (201 if allowed else 403)


@pytest.mark.parametrize(("slug", "allowed"), role_matrix(SYSTEM_ADMIN))
def test_changing_a_type_is_the_system_administrators(
    api_client: APIClient, all_role_users: dict[str, User], slug: str, allowed: bool
) -> None:
    """Only a system administrator changes a type."""
    email_type = EmailTypeFactory()
    api_client.force_login(all_role_users[slug])
    response = api_client.put(detail_url(email_type), payload(), format="json")
    assert response.status_code == (200 if allowed else 403)


@pytest.mark.parametrize(("slug", "allowed"), role_matrix(SYSTEM_ADMIN))
def test_deleting_a_type_is_the_system_administrators(
    api_client: APIClient, all_role_users: dict[str, User], slug: str, allowed: bool
) -> None:
    """Only a system administrator deletes a type."""
    email_type = EmailTypeFactory()
    api_client.force_login(all_role_users[slug])
    assert api_client.delete(detail_url(email_type)).status_code == (204 if allowed else 403)


@pytest.mark.parametrize(("slug", "allowed"), role_matrix(*ROLE_SLUGS))
def test_every_signed_in_caller_reads_their_sendable_types(
    api_client: APIClient, all_role_users: dict[str, User], slug: str, allowed: bool
) -> None:
    """Any role may ask which types it sends; most are told none."""
    api_client.force_login(all_role_users[slug])
    assert api_client.get(SENDABLE_URL).status_code == (200 if allowed else 403)


def test_an_anonymous_caller_is_refused_the_types(api_client: APIClient) -> None:
    """No session is a 401 on the list."""
    assert api_client.get(LIST_URL).status_code == 401


def test_an_anonymous_caller_is_refused_the_sendable_types(api_client: APIClient) -> None:
    """No session is a 401 on the sendable list."""
    assert api_client.get(SENDABLE_URL).status_code == 401
