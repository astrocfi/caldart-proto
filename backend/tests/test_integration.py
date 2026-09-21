"""Cross-feature agreements that no single feature's tests could assert.

Each test here pins down a rule that two features share and could otherwise
let drift apart: what "a complete profile" means, which serializer describes
an airplane, whether the reset really seeds the site, and where a reminder
email gets the organization's name from.
"""

from __future__ import annotations

from datetime import timedelta
from io import StringIO
from typing import TYPE_CHECKING, Any

import pytest
from django.core.management import call_command
from django.utils import timezone
from rest_framework.serializers import ListSerializer
from rest_framework.test import APIClient

from apps.accounts.api.serializers import UserSerializer
from apps.aircraft.api.serializers import AircraftSummarySerializer
from apps.members.api.profile_serializers import ProfileSerializer
from apps.members.models import MemberProfile
from apps.sysadmin.management.commands import db_reset as db_reset_command
from tests.factories import MemberProfileFactory, MembershipFactory, UserFactory

if TYPE_CHECKING:
    from apps.accounts.models import User as UserModel
    from apps.aircraft.models import Aircraft

pytestmark = pytest.mark.django_db


# ------------------------------------------------------- one completeness rule
def test_complete_fields_are_the_ones_the_plan_names() -> None:
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


def test_user_payload_delegates_to_the_model() -> None:
    """``profile_complete`` is the model's rule, not a second copy of it."""
    profile = MemberProfileFactory()
    assert UserSerializer(profile.user).data["profile_complete"] is True

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
def test_profile_embeds_the_aircraft_app_serializer() -> None:
    """The profile ``aircraft`` field is the aircraft app's own summary serializer."""
    field = ProfileSerializer().fields["aircraft"]
    assert isinstance(field, ListSerializer)
    assert isinstance(field.child, AircraftSummarySerializer)


def test_profile_aircraft_shape_matches_the_register(
    api_client: APIClient, aircraft: Aircraft
) -> None:
    """The profile API's ``aircraft`` entries match the summary serializer's fields."""
    profile = MemberProfileFactory()
    profile.aircraft.add(aircraft)
    api_client.force_login(profile.user)

    response = api_client.get("/api/v1/me/profile")

    assert response.status_code == 200
    assert set(response.data["aircraft"][0]) == set(AircraftSummarySerializer().fields)


# ------------------------------------------------------------ seeding is real
def test_db_reset_seed_propagates_a_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failure in any seed step propagates out of ``db_reset --seed``."""
    calls: list[str] = []

    def fake_call_command(name: str, *args: Any, **kwargs: Any) -> None:
        calls.append(name)
        if name == "seed_content":
            raise RuntimeError("the example site could not be built")

    monkeypatch.setattr(db_reset_command, "drop_schema", lambda: calls.append("drop_schema"))
    monkeypatch.setattr(db_reset_command, "call_command", fake_call_command)

    with pytest.raises(RuntimeError, match="example site"):
        call_command("db_reset", "--noinput", "--seed", stdout=StringIO())

    assert calls == ["drop_schema", "migrate", "seed_roles", "seed_demo", "seed_content"]


def test_seed_content_publishes_members_only_pages(api_client: APIClient) -> None:
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
def test_reminder_email_takes_its_name_from_site_settings() -> None:
    """A reminder email's subject and body carry the seeded site's organization name."""
    from apps.reminders.services import build_email

    call_command("seed_content", stdout=StringIO(), verbosity=0)

    profile = MemberProfileFactory()
    membership = MembershipFactory(
        user=profile.user, ends_on=timezone.localdate() + timedelta(days=30)
    )
    message = build_email(profile.user, membership, "t30", timezone.localdate())

    from apps.cms.models import get_site_settings

    site_settings = get_site_settings()
    assert site_settings is not None
    org_name = site_settings.org_name
    assert org_name != "CalDART"  # the seeded site uses the full name
    assert org_name in message.subject
    assert org_name in message.body


# ------------------------------------------------ editors can fix their 404s
def test_website_admin_may_manage_redirects(website_admin: UserModel) -> None:
    """Renaming a page changes its URL; the editor has to be able to fix it."""
    from apps.cms.permissions import grant_website_admin_permissions

    grant_website_admin_permissions()
    website_admin = type(website_admin).objects.get(pk=website_admin.pk)

    for codename in ("add_redirect", "change_redirect", "delete_redirect"):
        assert website_admin.has_perm(f"wagtailredirects.{codename}")


def test_a_plain_member_may_not_manage_redirects(member: UserModel) -> None:
    """A plain member holds none of the Wagtail redirect permissions."""
    assert not member.has_perm("wagtailredirects.add_redirect")


# ---------------------------------------------- an export says what it hides
def test_aircraft_export_subtitle_names_every_filter() -> None:
    """`is_active` was applied to the rows but left out of the PDF subtitle."""
    from rest_framework.request import Request
    from rest_framework.test import APIRequestFactory

    from apps.aircraft.api.views import AircraftExportPdfView

    view = AircraftExportPdfView()
    view.request = Request(APIRequestFactory().get("/", {"is_active": "true", "search": "N1"}))

    filters = view.applied_filters()

    assert filters["is_active"] == "true"
    assert filters["search"] == "N1"
    assert set(filters) == {
        "search",
        "make",
        "owner_type",
        "insurance",
        "expiring_within",
        "is_active",
        "ordering",
    }


def test_payment_filters_have_no_dead_describe() -> None:
    """It promised a PDF subtitle, but payments export only as CSV."""
    from apps.payments.reports import PaymentFilters

    assert not hasattr(PaymentFilters, "describe")
