"""Attaching and detaching "planes I commonly fly"."""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.aircraft.models import Aircraft
from apps.members.models import MemberProfile
from tests.factories import AircraftFactory, MemberProfileFactory, UserFactory

pytestmark = pytest.mark.django_db

ATTACH_URL = "/api/v1/me/profile/aircraft"


def detach_url(aircraft_id: int) -> str:
    """Build the URL that detaches the aircraft with the given id."""
    return f"{ATTACH_URL}/{aircraft_id}"


def test_attach_adds_the_aircraft_and_returns_the_list(
    api_client: APIClient, member: User, profile: MemberProfile, aircraft: Aircraft
) -> None:
    """Attaching an aircraft adds it to the profile and returns it in the response."""
    api_client.force_login(member)

    response = api_client.post(ATTACH_URL, {"aircraft_id": aircraft.id}, format="json")

    assert response.status_code == 200
    assert [row["id"] for row in response.json()["aircraft"]] == [aircraft.id]
    assert response.json()["aircraft"][0]["n_number"] == aircraft.n_number
    assert list(profile.aircraft.values_list("id", flat=True)) == [aircraft.id]


def test_attach_is_idempotent(
    api_client: APIClient, member: User, profile: MemberProfile, aircraft: Aircraft
) -> None:
    """Attaching the same aircraft twice leaves exactly one attachment."""
    api_client.force_login(member)
    api_client.post(ATTACH_URL, {"aircraft_id": aircraft.id}, format="json")

    response = api_client.post(ATTACH_URL, {"aircraft_id": aircraft.id}, format="json")

    assert response.status_code == 200
    assert profile.aircraft.count() == 1


def test_attach_creates_the_profile_when_there_is_none(
    api_client: APIClient, member: User, aircraft: Aircraft
) -> None:
    """Attaching an aircraft for a member with no profile yet creates the profile."""
    api_client.force_login(member)
    response = api_client.post(ATTACH_URL, {"aircraft_id": aircraft.id}, format="json")
    assert response.status_code == 200
    assert member.profile.aircraft.count() == 1


def test_attach_404s_on_an_unknown_aircraft(
    api_client: APIClient, member: User, profile: MemberProfile
) -> None:
    """Attaching an aircraft id that does not exist returns 404."""
    api_client.force_login(member)
    assert api_client.post(ATTACH_URL, {"aircraft_id": 999_999}, format="json").status_code == 404


def test_attach_validates_the_body(
    api_client: APIClient, member: User, profile: MemberProfile
) -> None:
    """Posting without ``aircraft_id`` returns 400 with that field named in the errors."""
    api_client.force_login(member)
    response = api_client.post(ATTACH_URL, {}, format="json")
    assert response.status_code == 400
    assert "aircraft_id" in response.json()


def test_attach_only_touches_the_callers_profile(
    api_client: APIClient, member: User, profile: MemberProfile, aircraft: Aircraft
) -> None:
    """Attaching an aircraft never adds it to another member's profile."""
    stranger = MemberProfileFactory.create(user=UserFactory.create(email="stranger@example.test"))
    api_client.force_login(member)

    api_client.post(ATTACH_URL, {"aircraft_id": aircraft.id}, format="json")

    assert stranger.aircraft.count() == 0


def test_detach_removes_the_aircraft(
    api_client: APIClient, member: User, profile: MemberProfile, aircraft: Aircraft
) -> None:
    """Detaching a previously attached aircraft removes it from the profile."""
    profile.aircraft.add(aircraft)
    api_client.force_login(member)

    response = api_client.delete(detach_url(aircraft.id))

    assert response.status_code == 204
    assert profile.aircraft.count() == 0


def test_detach_is_a_no_op_when_it_was_never_attached(
    api_client: APIClient, member: User, profile: MemberProfile, aircraft: Aircraft
) -> None:
    """Detaching an aircraft that was never attached still returns 204."""
    api_client.force_login(member)
    assert api_client.delete(detach_url(aircraft.id)).status_code == 204


def test_detach_404s_on_an_unknown_aircraft(
    api_client: APIClient, member: User, profile: MemberProfile
) -> None:
    """Detaching an aircraft id that does not exist returns 404."""
    api_client.force_login(member)
    assert api_client.delete(detach_url(999_999)).status_code == 404


def test_detach_leaves_the_aircraft_record_alone(
    api_client: APIClient, member: User, profile: MemberProfile, aircraft: Aircraft
) -> None:
    """Detaching an aircraft from a profile does not deactivate the aircraft record."""
    profile.aircraft.add(aircraft)
    api_client.force_login(member)

    api_client.delete(detach_url(aircraft.id))

    aircraft.refresh_from_db()
    assert aircraft.is_active is True


def test_detach_does_not_affect_another_members_attachment(
    api_client: APIClient, member: User, profile: MemberProfile, aircraft: Aircraft
) -> None:
    """Detaching an aircraft from the caller leaves another member's attachment alone."""
    stranger = MemberProfileFactory.create(user=UserFactory.create(email="stranger@example.test"))
    stranger.aircraft.add(aircraft)
    profile.aircraft.add(aircraft)
    api_client.force_login(member)

    api_client.delete(detach_url(aircraft.id))

    assert stranger.aircraft.count() == 1


def test_several_aircraft_can_be_attached(
    api_client: APIClient, member: User, profile: MemberProfile
) -> None:
    """Attaching two different aircraft leaves both listed on the profile."""
    first = AircraftFactory.create(n_number="N111AA")
    second = AircraftFactory.create(n_number="N222BB")
    api_client.force_login(member)

    api_client.post(ATTACH_URL, {"aircraft_id": first.id}, format="json")
    response = api_client.post(ATTACH_URL, {"aircraft_id": second.id}, format="json")

    assert {row["n_number"] for row in response.json()["aircraft"]} == {"N111AA", "N222BB"}


def test_every_role_may_manage_their_own_aircraft(
    api_client: APIClient, all_role_users: dict[str, User], aircraft: Aircraft
) -> None:
    """Every role can attach and detach its own aircraft without a permission error."""
    for user in all_role_users.values():
        api_client.force_login(user)
        assert (
            api_client.post(ATTACH_URL, {"aircraft_id": aircraft.id}, format="json").status_code
            == 200
        )
        assert api_client.delete(detach_url(aircraft.id)).status_code == 204
        api_client.logout()
