"""Email preferences: a person's own choice of bulk email, and an administrator's change.

The behavior is documented in ``docs/developer/api-email-types.rst``.
"""

from __future__ import annotations

import logging

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import ACCOUNT_ADMIN, ROLE_SLUGS, SYSTEM_ADMIN
from apps.mail.models import EmailOptOut, EmailType, OptOutSource
from apps.mail.types import is_opted_out
from apps.members.services import TOMBSTONE_CHANGE_REFUSED, tombstone_for
from tests.conftest import audit_messages, role_matrix
from tests.factories import EmailOptOutFactory, EmailTypeFactory

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("no_email_types")]

ME_URL = "/api/v1/me/email-preferences"


def member_url(user: User | int) -> str:
    """``/admin/members/{id}/email-preferences`` for ``user`` or a bare id."""
    pk = user if isinstance(user, int) else user.pk
    return f"/api/v1/admin/members/{pk}/email-preferences"


@pytest.fixture
def mission(no_email_types: None) -> EmailType:
    """Mission email, which a person may turn off."""
    return EmailTypeFactory(name="Mission", description="Pilots wanted.", position=1)


@pytest.fixture
def operational(no_email_types: None) -> EmailType:
    """Operational email, which nobody may turn off."""
    return EmailTypeFactory(name="Operational", allow_opt_out=False, position=2)


@pytest.fixture
def member_client(api_client: APIClient, member: User) -> APIClient:
    """A client signed in as the ``member`` fixture."""
    api_client.force_login(member)
    return api_client


def change(email_type: EmailType, *, opted_out: bool) -> list[dict[str, object]]:
    """A ``PUT`` body changing one type."""
    return [{"email_type": email_type.pk, "opted_out": opted_out}]


# -- a person's own preferences ---------------------------------------------
@pytest.mark.usefixtures("operational")
def test_only_types_that_may_be_turned_off_are_listed(
    member_client: APIClient, mission: EmailType
) -> None:
    """A type that does not allow opting out is not offered."""
    response = member_client.get(ME_URL)

    assert response.json() == [
        {
            "email_type": mission.pk,
            "name": "Mission",
            "description": "Pilots wanted.",
            "opted_out": False,
        }
    ]


def test_a_new_account_starts_opted_in_to_every_type(member_client: APIClient) -> None:
    """With no opt-out recorded, every type is on."""
    EmailTypeFactory.create_batch(3)

    response = member_client.get(ME_URL)

    assert [row["opted_out"] for row in response.json()] == [False, False, False]


def test_a_person_turns_a_type_off(
    member_client: APIClient, member: User, mission: EmailType
) -> None:
    """The answer shows the change, and the opt-out is recorded from the profile."""
    response = member_client.put(ME_URL, change(mission, opted_out=True), format="json")

    assert response.json()[0]["opted_out"] is True
    assert EmailOptOut.objects.get(user=member, email_type=mission).source == (OptOutSource.PROFILE)


def test_a_person_turns_a_type_back_on(member_client: APIClient, member: User) -> None:
    """Opting back in removes the opt-out."""
    opt_out = EmailOptOutFactory(user=member)

    response = member_client.put(ME_URL, change(opt_out.email_type, opted_out=False), format="json")

    assert response.json()[0]["opted_out"] is False
    assert not EmailOptOut.objects.filter(pk=opt_out.pk).exists()


def test_a_type_left_out_of_the_body_is_left_alone(
    member_client: APIClient, member: User, mission: EmailType
) -> None:
    """Only the types the body names change."""
    other = EmailOptOutFactory(user=member)

    member_client.put(ME_URL, change(mission, opted_out=True), format="json")

    assert EmailOptOut.objects.filter(pk=other.pk).exists()


def test_turning_a_type_off_is_audited(
    member_client: APIClient,
    member: User,
    mission: EmailType,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """One ``email.opt_out`` line names the person, the type, and the source."""
    member_client.put(ME_URL, change(mission, opted_out=True), format="json")

    assert audit_messages(audit_log) == [
        f"action=email.opt_out actor={member.pk} target={member.pk} "
        f"email_type={mission.pk} source=profile"
    ]


def test_turning_a_type_back_on_is_audited(
    member_client: APIClient, member: User, audit_log: pytest.LogCaptureFixture
) -> None:
    """One ``email.opt_in`` line names the person, the type, and the source."""
    opt_out = EmailOptOutFactory(user=member)

    member_client.put(ME_URL, change(opt_out.email_type, opted_out=False), format="json")

    assert audit_messages(audit_log) == [
        f"action=email.opt_in actor={member.pk} target={member.pk} "
        f"email_type={opt_out.email_type.pk} source=profile"
    ]


def test_asking_for_the_state_already_held_writes_nothing(
    member_client: APIClient, mission: EmailType, audit_log: pytest.LogCaptureFixture
) -> None:
    """Opting in while opted in changes nothing and is not audited."""
    member_client.put(ME_URL, change(mission, opted_out=False), format="json")

    assert audit_messages(audit_log) == []


def test_a_type_that_cannot_be_turned_off_is_refused(
    member_client: APIClient, member: User, mission: EmailType, operational: EmailType
) -> None:
    """The whole change is refused, the allowed part included."""
    body = [*change(mission, opted_out=True), *change(operational, opted_out=True)]

    response = member_client.put(ME_URL, body, format="json")

    assert response.status_code == 400
    assert response.json() == {
        "email_type": ["That email type does not exist, or cannot be turned off."]
    }
    assert not EmailOptOut.objects.filter(user=member).exists()


def test_an_unknown_type_is_refused(member_client: APIClient) -> None:
    """An id no type carries is a 400 on ``email_type``."""
    response = member_client.put(
        ME_URL, [{"email_type": 999_999, "opted_out": True}], format="json"
    )

    assert response.status_code == 400
    assert response.json() == {
        "email_type": ["That email type does not exist, or cannot be turned off."]
    }


def test_a_type_named_twice_is_refused(
    member_client: APIClient, member: User, mission: EmailType
) -> None:
    """A list naming one type twice is refused, and nothing changes."""
    body = [*change(mission, opted_out=True), *change(mission, opted_out=False)]

    response = member_client.put(ME_URL, body, format="json")

    assert response.status_code == 400
    assert response.json() == {"email_type": ["Name each email type once."]}
    assert not EmailOptOut.objects.filter(user=member).exists()


def test_a_body_that_is_not_a_list_is_refused(member_client: APIClient) -> None:
    """The body is a list of changes."""
    response = member_client.put(ME_URL, {"email_type": 1, "opted_out": True}, format="json")

    assert response.status_code == 400


# -- whether an opt-out applies ---------------------------------------------
def test_an_opt_out_applies_while_the_type_allows_it(member: User) -> None:
    """A recorded opt-out of a type that allows opting out holds."""
    opt_out = EmailOptOutFactory(user=member)

    assert is_opted_out(member, opt_out.email_type) is True


def test_an_opt_out_waits_while_the_type_does_not_allow_it(member: User) -> None:
    """An opt-out recorded earlier does not apply once the type stops allowing one."""
    opt_out = EmailOptOutFactory(user=member)
    opt_out.email_type.allow_opt_out = False
    opt_out.email_type.save()

    assert is_opted_out(member, opt_out.email_type) is False


# -- an account administrator on the member record --------------------------
def test_an_administrator_reads_a_members_preferences(
    account_admin_client: APIClient, member: User
) -> None:
    """The member record shows the same rows the member's own screen does."""
    opt_out = EmailOptOutFactory(user=member)

    response = account_admin_client.get(member_url(member))

    assert response.json() == [
        {
            "email_type": opt_out.email_type.pk,
            "name": opt_out.email_type.name,
            "description": opt_out.email_type.description,
            "opted_out": True,
        }
    ]


def test_an_administrator_turns_a_type_off_for_a_member(
    account_admin_client: APIClient, member: User, mission: EmailType
) -> None:
    """The opt-out is recorded as the administrator's."""
    account_admin_client.put(member_url(member), change(mission, opted_out=True), format="json")

    assert EmailOptOut.objects.get(user=member, email_type=mission).source == OptOutSource.ADMIN


def test_an_administrators_change_is_audited_under_them(
    account_admin_client: APIClient,
    account_admin: User,
    member: User,
    mission: EmailType,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """The administrator is the actor and the member the target."""
    account_admin_client.put(member_url(member), change(mission, opted_out=True), format="json")

    assert audit_messages(audit_log) == [
        f"action=email.opt_out actor={account_admin.pk} target={member.pk} "
        f"email_type={mission.pk} source=admin"
    ]


def test_a_deleted_members_record_refuses_a_change(
    account_admin_client: APIClient,
    member: User,
    mission: EmailType,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """The record that keeps a deleted member's payments cannot be changed."""
    tombstone = tombstone_for(member)

    response = account_admin_client.put(
        member_url(tombstone), change(mission, opted_out=True), format="json"
    )

    assert response.status_code == 400
    assert response.json() == {"detail": TOMBSTONE_CHANGE_REFUSED}
    assert not EmailOptOut.objects.filter(user=tombstone).exists()


def test_a_refusal_on_a_deleted_member_is_audited_as_each_change(
    account_admin_client: APIClient,
    account_admin: User,
    member: User,
    mission: EmailType,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """Each change asked for is a WARNING line under its own action, naming the type."""
    tombstone = tombstone_for(member)
    other = EmailTypeFactory(name="Board")
    body = [*change(mission, opted_out=True), *change(other, opted_out=False)]

    account_admin_client.put(member_url(tombstone), body, format="json")

    assert audit_messages(audit_log, logging.WARNING) == [
        f"action=email.opt_out actor={account_admin.pk} target={tombstone.pk} "
        f"email_type={mission.pk} reason=tombstone",
        f"action=email.opt_in actor={account_admin.pk} target={tombstone.pk} "
        f"email_type={other.pk} reason=tombstone",
    ]


def test_an_unknown_member_is_a_404(account_admin_client: APIClient) -> None:
    """An id no account carries is not found."""
    assert account_admin_client.get(member_url(999_999)).status_code == 404


# -- permissions -------------------------------------------------------------
@pytest.mark.parametrize(("slug", "allowed"), role_matrix(*ROLE_SLUGS))
def test_every_signed_in_person_reads_their_own_preferences(
    api_client: APIClient, all_role_users: dict[str, User], slug: str, allowed: bool
) -> None:
    """Every role has its own Email preferences."""
    api_client.force_login(all_role_users[slug])
    assert api_client.get(ME_URL).status_code == (200 if allowed else 403)


@pytest.mark.parametrize(("slug", "allowed"), role_matrix(*ROLE_SLUGS))
def test_every_signed_in_person_changes_their_own_preferences(
    api_client: APIClient,
    all_role_users: dict[str, User],
    mission: EmailType,
    slug: str,
    allowed: bool,
) -> None:
    """Every role may turn a type off for themselves."""
    api_client.force_login(all_role_users[slug])
    response = api_client.put(ME_URL, change(mission, opted_out=True), format="json")
    assert response.status_code == (200 if allowed else 403)


@pytest.mark.parametrize(("slug", "allowed"), role_matrix(ACCOUNT_ADMIN, SYSTEM_ADMIN))
def test_reading_a_members_preferences_is_the_account_administrators(
    api_client: APIClient,
    all_role_users: dict[str, User],
    member: User,
    slug: str,
    allowed: bool,
) -> None:
    """Only an account or system administrator reads someone else's preferences."""
    api_client.force_login(all_role_users[slug])
    assert api_client.get(member_url(member)).status_code == (200 if allowed else 403)


@pytest.mark.parametrize(("slug", "allowed"), role_matrix(ACCOUNT_ADMIN, SYSTEM_ADMIN))
def test_changing_a_members_preferences_is_the_account_administrators(
    api_client: APIClient,
    all_role_users: dict[str, User],
    member: User,
    mission: EmailType,
    slug: str,
    allowed: bool,
) -> None:
    """Only an account or system administrator changes someone else's preferences."""
    api_client.force_login(all_role_users[slug])
    response = api_client.put(member_url(member), change(mission, opted_out=True), format="json")
    assert response.status_code == (200 if allowed else 403)


def test_an_anonymous_caller_has_no_preferences(api_client: APIClient) -> None:
    """No session is a 401."""
    assert api_client.get(ME_URL).status_code == 401


def test_an_anonymous_caller_reads_no_members_preferences(
    api_client: APIClient, member: User
) -> None:
    """No session is a 401 on the member record's preferences."""
    assert api_client.get(member_url(member)).status_code == 401
