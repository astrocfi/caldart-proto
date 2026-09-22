"""What "a complete profile" means, at the model and at the user payload.

``MemberProfile.COMPLETE_FIELDS`` is the single rule; the join wizard, the
``profile_complete`` flag on the user payload and the portal's dashboard all read
it, so it is pinned here once rather than in each of their test modules.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.api.serializers import UserSerializer
from apps.members.models import MemberProfile
from tests.factories import MemberProfileFactory, UserFactory

pytestmark = pytest.mark.django_db

PROFILE_URL = "/api/v1/me/profile"
ME_URL = "/api/v1/auth/me"


def test_complete_fields_are_the_five_documented_ones() -> None:
    """These five alone decide ``profile_complete`` (``docs/developer/api-auth.rst``)."""
    assert MemberProfile.COMPLETE_FIELDS == (
        "phone",
        "address_line1",
        "city",
        "postal_code",
        "pilot_certificate_type",
    )


def test_a_filled_in_profile_is_complete() -> None:
    """A profile with every ``COMPLETE_FIELDS`` value set is complete."""
    assert MemberProfileFactory().is_complete is True


@pytest.mark.parametrize("field", MemberProfile.COMPLETE_FIELDS)
def test_every_named_field_is_needed(field: str) -> None:
    """Blanking any single field in ``COMPLETE_FIELDS`` makes the profile incomplete."""
    profile = MemberProfileFactory()
    setattr(profile, field, "")
    assert profile.is_complete is False


def test_state_is_not_part_of_the_rule() -> None:
    """``is_complete`` does not require ``state`` to be set."""
    profile = MemberProfileFactory(state="")
    assert profile.is_complete is True


def test_not_a_pilot_still_counts_as_complete() -> None:
    """A ground-team volunteer has answered the question, so they are done."""
    profile = MemberProfileFactory(
        pilot_certificate_type="none", certificate_number="", ifr_rated="na", ratings=[]
    )
    assert profile.is_complete is True


def test_the_user_payload_reports_a_complete_profile_as_complete() -> None:
    """``profile_complete`` is true on the user payload of a filled-in profile."""
    profile = MemberProfileFactory()
    assert UserSerializer(profile.user).data["profile_complete"] is True


def test_the_user_payload_follows_the_model_when_a_field_is_cleared() -> None:
    """Clearing a required field flips ``profile_complete`` on the user payload too."""
    profile = MemberProfileFactory()
    profile.address_line1 = ""
    profile.save(update_fields=["address_line1"])
    profile.user.refresh_from_db()
    assert UserSerializer(profile.user).data["profile_complete"] is False


def test_a_user_without_a_profile_is_not_complete() -> None:
    """A user with no ``MemberProfile`` at all is reported as profile-incomplete."""
    assert UserSerializer(UserFactory(email="fresh@example.test")).data["profile_complete"] is False


def test_the_wizard_can_finish_what_the_api_accepts(api_client: APIClient) -> None:
    """Saving only the required fields must satisfy ``profile_complete``.

    Otherwise the join wizard's step 2 succeeds and step 3 sends the visitor
    straight back to it.
    """
    user = UserFactory(email="joiner@example.test")
    api_client.force_login(user)

    response = api_client.patch(
        PROFILE_URL,
        {
            "phone": "650-555-0101",
            "address_line1": "1 Airport Way",
            "city": "San Carlos",
            "postal_code": "94070",
            "pilot_certificate_type": "none",
        },
        format="json",
    )
    assert response.status_code == 200

    me = api_client.get(ME_URL)
    assert me.status_code == 200
    assert me.json()["profile_complete"] is True
