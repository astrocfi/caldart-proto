"""People's names beyond the account's own are stored through ``person_name``.

An emergency contact, a DART contact, an individual aircraft owner, and a DART page's
leader are each saved in the casing ``caldart.casing.person_name`` gives, and
``manage.py normalize_casing`` rewrites the rows already stored
(``docs/developer/data-model.rst``).  An FBO's or a flying club's owner name is a
business name: typed in one case it is title-cased with ``caldart.casing.business_name``,
and typed in mixed case it is kept.
"""

from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.aircraft.models import Aircraft, OwnerType
from apps.cms.models import DartPage
from apps.darts.models import DartContact
from apps.members.models import MemberProfile
from tests.factories import (
    AircraftFactory,
    DartContactFactory,
    DartFactory,
    UserFactory,
    make_dart_index,
    make_dart_page,
    make_home_page,
)

pytestmark = pytest.mark.django_db


def run_normalize(*args: str) -> str:
    """Run ``normalize_casing`` with ``args`` and return what it printed."""
    out = StringIO()
    call_command("normalize_casing", *args, stdout=out)
    return out.getvalue()


def test_saving_a_profile_normalizes_the_emergency_contact_name() -> None:
    """An emergency contact typed in capitals is saved in title case."""
    profile = MemberProfile.objects.create(
        user=UserFactory(), emergency_contact_name="MARY O'BRIEN"
    )
    profile.refresh_from_db()
    assert profile.emergency_contact_name == "Mary O'Brien"


def test_saving_a_profile_keeps_a_mixed_case_emergency_contact() -> None:
    """An emergency contact typed in mixed case is kept as typed."""
    profile = MemberProfile.objects.create(
        user=UserFactory(), emergency_contact_name="DeAnna MacArthur"
    )
    profile.refresh_from_db()
    assert profile.emergency_contact_name == "DeAnna MacArthur"


def test_the_profile_endpoint_stores_the_emergency_contact_normalized(
    api_client: APIClient, member: User, profile: MemberProfile
) -> None:
    """``PATCH /me/profile`` stores a lower-case emergency contact in title case."""
    api_client.force_login(member)
    response = api_client.patch(
        "/api/v1/me/profile", {"emergency_contact_name": "jan van der berg"}, format="json"
    )
    assert response.status_code == 200, response.json()
    profile.refresh_from_db()
    assert profile.emergency_contact_name == "Jan van der Berg"


def test_saving_a_dart_contact_normalizes_the_name() -> None:
    """A DART contact's name typed in lower case is saved in title case."""
    contact = DartContactFactory(name="helen mcdonald")
    contact.refresh_from_db()
    assert contact.name == "Helen McDonald"


def test_saving_an_individual_owner_normalizes_the_owner_name() -> None:
    """An individual owner's name typed in capitals is saved in title case."""
    aircraft = AircraftFactory(owner_type=OwnerType.INDIVIDUAL, owner_name="JOHN SMITH")
    aircraft.refresh_from_db()
    assert aircraft.owner_name == "John Smith"


@pytest.mark.parametrize("owner_type", [OwnerType.FBO, OwnerType.CLUB], ids=["fbo", "club"])
def test_a_business_owner_name_in_capitals_is_title_cased(owner_type: OwnerType) -> None:
    """A business owner in capitals is title-cased, keeping ``LLC`` upper case."""
    aircraft = AircraftFactory(owner_type=owner_type, owner_name="SKYHAWK AVIATION LLC")
    aircraft.refresh_from_db()
    assert aircraft.owner_name == "Skyhawk Aviation LLC"


@pytest.mark.parametrize("owner_type", [OwnerType.FBO, OwnerType.CLUB], ids=["fbo", "club"])
def test_a_business_owner_name_in_mixed_case_is_kept_as_typed(owner_type: OwnerType) -> None:
    """A business name typed in mixed case, such as ``SkyWest``, is kept."""
    aircraft = AircraftFactory(owner_type=owner_type, owner_name="SkyWest Aviation")
    aircraft.refresh_from_db()
    assert aircraft.owner_name == "SkyWest Aviation"


def test_publishing_a_dart_page_normalizes_the_leader_name() -> None:
    """A DART page's leader typed in capitals is published in title case."""
    page = make_dart_page(
        make_dart_index(make_home_page()), DartFactory(), leader_name="HELEN MARCHETTI"
    )
    page.refresh_from_db()
    assert page.leader_name == "Helen Marchetti"


def test_cleaning_a_dart_page_normalizes_the_leader_name() -> None:
    """The editor's validation, which runs before a draft is saved, cases the leader."""
    page = DartPage(title="Team", slug="team", leader_name="helen marchetti")
    page.clean()
    assert page.leader_name == "Helen Marchetti"


def test_normalize_casing_rewrites_the_other_names_already_stored() -> None:
    """The command rewrites each kind of stored name, a business owner's included."""
    profile = MemberProfile.objects.create(user=UserFactory())
    MemberProfile.objects.filter(pk=profile.pk).update(emergency_contact_name="MARY LEE")
    contact = DartContactFactory()
    DartContact.objects.filter(pk=contact.pk).update(name="helen mcdonald")
    person = AircraftFactory(owner_type=OwnerType.INDIVIDUAL)
    Aircraft.objects.filter(pk=person.pk).update(owner_name="JOHN SMITH")
    club = AircraftFactory(owner_type=OwnerType.CLUB)
    Aircraft.objects.filter(pk=club.pk).update(owner_name="SKYHAWK AVIATION LLC")
    page = make_dart_page(make_dart_index(make_home_page()), DartFactory())
    DartPage.objects.filter(pk=page.pk).update(leader_name="HELEN MARCHETTI")

    run_normalize()

    stored = (
        MemberProfile.objects.get(pk=profile.pk).emergency_contact_name,
        DartContact.objects.get(pk=contact.pk).name,
        Aircraft.objects.get(pk=person.pk).owner_name,
        Aircraft.objects.get(pk=club.pk).owner_name,
        DartPage.objects.get(pk=page.pk).leader_name,
    )
    assert stored == (
        "Mary Lee",
        "Helen McDonald",
        "John Smith",
        "Skyhawk Aviation LLC",
        "Helen Marchetti",
    )


def test_normalize_casing_labels_each_kind_of_row() -> None:
    """A DART contact, an aircraft, and a DART page are named in the printed lines."""
    contact = DartContactFactory()
    DartContact.objects.filter(pk=contact.pk).update(name="helen mcdonald")
    person = AircraftFactory(owner_type=OwnerType.INDIVIDUAL, n_number="N123AB")
    Aircraft.objects.filter(pk=person.pk).update(owner_name="JOHN SMITH")
    page = make_dart_page(make_dart_index(make_home_page()), DartFactory())
    DartPage.objects.filter(pk=page.pk).update(leader_name="HELEN MARCHETTI")

    lines = run_normalize("--dry-run").splitlines()

    assert lines == [
        f'DART contact {contact.pk}: name "helen mcdonald" -> "Helen McDonald"',
        'aircraft N123AB: owner_name "JOHN SMITH" -> "John Smith"',
        f'DART page {page.pk}: leader_name "HELEN MARCHETTI" -> "Helen Marchetti"',
        "Would change 3 fields.",
    ]
