"""Cross-feature agreements that no single Phase 2 branch could assert.

Each test here pins down a rule that two branches had written down separately
and that drifted apart as a result: what "a complete profile" means, which
serializer describes an aeroplane, whether the reset really seeds the site, and
where a reminder email gets the organisation's name from.
"""

from __future__ import annotations

from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.accounts.api.serializers import UserSerializer
from apps.aircraft.api.serializers import AircraftSummarySerializer
from apps.members.api.profile_serializers import ProfileSerializer
from apps.members.models import MemberProfile
from apps.sysadmin.management.commands import db_reset as db_reset_command
from tests.factories import MemberProfileFactory, MembershipFactory, UserFactory

pytestmark = pytest.mark.django_db


# ------------------------------------------------------- one completeness rule
def test_complete_fields_are_the_ones_the_plan_names():
    """PLAN §6.1 lists exactly these five for ``profile_complete``."""
    assert MemberProfile.COMPLETE_FIELDS == (
        "phone",
        "address_line1",
        "city",
        "postal_code",
        "pilot_certificate_type",
    )


def test_a_filled_in_profile_is_complete():
    assert MemberProfileFactory().is_complete is True


@pytest.mark.parametrize("field", MemberProfile.COMPLETE_FIELDS)
def test_every_named_field_is_needed(field):
    profile = MemberProfileFactory()
    setattr(profile, field, "")
    assert profile.is_complete is False


def test_state_is_not_part_of_the_rule():
    """The portal's form used to insist on it; PLAN §6.1 does not."""
    profile = MemberProfileFactory(state="")
    assert profile.is_complete is True


def test_not_a_pilot_still_counts_as_complete():
    """A ground-team volunteer has answered the question, so they are done."""
    profile = MemberProfileFactory(
        pilot_certificate_type="none", certificate_number="", ifr_rated="na", ratings=[]
    )
    assert profile.is_complete is True


def test_user_payload_delegates_to_the_model():
    """``profile_complete`` is the model's rule, not a second copy of it."""
    profile = MemberProfileFactory()
    assert UserSerializer(profile.user).data["profile_complete"] is True

    profile.address_line1 = ""
    profile.save(update_fields=["address_line1"])
    profile.user.refresh_from_db()
    assert UserSerializer(profile.user).data["profile_complete"] is False


def test_a_user_without_a_profile_is_not_complete():
    assert UserSerializer(UserFactory(email="fresh@example.test")).data["profile_complete"] is False


def test_the_wizard_can_finish_what_the_api_accepts(api_client):
    """Saving only the required fields must satisfy ``profile_complete``.

    Otherwise the join wizard's step 2 succeeds and step 3 sends the visitor
    straight back to it.
    """
    user = UserFactory(email="joiner@example.test")
    api_client.force_login(user)

    response = api_client.patch(
        "/api/v1/me/profile",
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

    me = api_client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.data["profile_complete"] is True


# ------------------------------------------------------ one aircraft summary
def test_profile_embeds_the_aircraft_app_serializer():
    """``apps.members`` used to carry its own copy of this shape."""
    field = ProfileSerializer().fields["aircraft"]
    assert isinstance(field.child, AircraftSummarySerializer)


def test_profile_aircraft_shape_matches_the_register(api_client, aircraft):
    profile = MemberProfileFactory()
    profile.aircraft.add(aircraft)
    api_client.force_login(profile.user)

    response = api_client.get("/api/v1/me/profile")

    assert response.status_code == 200
    assert set(response.data["aircraft"][0]) == set(AircraftSummarySerializer().fields)


# ------------------------------------------------------------ seeding is real
def test_db_reset_seed_no_longer_swallows_a_failure(monkeypatch):
    """The try/except that hid ``seed_content`` before the CMS landed is gone."""
    calls: list[str] = []

    def fake_call_command(name, *args, **kwargs):
        calls.append(name)
        if name == "seed_content":
            raise RuntimeError("the example site could not be built")

    monkeypatch.setattr(db_reset_command, "drop_schema", lambda: calls.append("drop_schema"))
    monkeypatch.setattr(db_reset_command, "call_command", fake_call_command)

    with pytest.raises(RuntimeError, match="example site"):
        call_command("db_reset", "--noinput", "--seed", stdout=StringIO())

    assert calls == ["drop_schema", "migrate", "seed_roles", "seed_demo", "seed_content"]


def test_seed_content_publishes_members_only_pages(api_client):
    """The dashboard's members-only list is empty until this has run."""
    call_command("seed_content", stdout=StringIO(), verbosity=0)

    member = MemberProfileFactory().user
    MembershipFactory(user=member, ends_on=timezone.localdate() + timedelta(days=30))
    api_client.force_login(member)

    config = api_client.get("/api/v1/site/config")

    assert config.status_code == 200
    assert config.data["org_name"]
    assert len(config.data["members_pages"]) > 0


# ------------------------------------------- reminders speak for the real org
def test_reminder_email_takes_its_name_from_site_settings():
    from apps.reminders.services import build_email

    call_command("seed_content", stdout=StringIO(), verbosity=0)

    profile = MemberProfileFactory()
    membership = MembershipFactory(
        user=profile.user, ends_on=timezone.localdate() + timedelta(days=30)
    )
    message = build_email(profile.user, membership, "t30", timezone.localdate())

    from apps.cms.models import get_site_settings

    org_name = get_site_settings().org_name
    assert org_name != "CalDART"  # the seeded site uses the full name
    assert org_name in message.subject
    assert org_name in message.body
