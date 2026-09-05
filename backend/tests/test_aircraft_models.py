"""N-number normalisation and insurance properties (PLAN §4.3)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.aircraft.models import Aircraft, normalize_n_number
from tests.factories import AircraftFactory

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("n12345", "N12345"),
        ("N12345", "N12345"),
        ("12345", "N12345"),
        ("  n123ab  ", "N123AB"),
        ("n-123ab", "N123AB"),
        ("c-gabc", "CGABC"),
        ("737wt", "N737WT"),
        ("", ""),
        (None, ""),
        ("---", ""),
    ],
)
def test_normalize_n_number(raw, expected):
    assert normalize_n_number(raw) == expected


def test_save_normalises_the_n_number():
    aircraft = AircraftFactory(n_number="  n4 21 cd ")
    aircraft.refresh_from_db()
    assert aircraft.n_number == "N421CD"


def test_n_number_is_unique_after_normalisation():
    AircraftFactory(n_number="N999ZZ")
    with pytest.raises(IntegrityError):
        Aircraft.objects.create(n_number="999zz")


def test_insurance_is_current_today_counts():
    today = timezone.localdate()
    aircraft = AircraftFactory(n_number="N1AA", insurance_expiration=today)
    assert aircraft.insurance_is_current is True


def test_insurance_expired_yesterday():
    today = timezone.localdate()
    aircraft = AircraftFactory(n_number="N2AA", insurance_expiration=today - timedelta(days=1))
    assert aircraft.insurance_is_current is False


def test_missing_insurance_is_not_current():
    aircraft = AircraftFactory(n_number="N3AA", insurance_expiration=None)
    assert aircraft.insurance_is_current is False


def test_insurance_summary_format():
    aircraft = AircraftFactory(
        n_number="N4AA",
        insurance_liability_per_occurrence_cents=100_000_000,
        insurance_liability_per_person_cents=10_000_000,
        insurance_expiration=timezone.localdate().replace(month=3, day=1),
    )
    summary = aircraft.insurance_summary
    assert summary.startswith("$1,000,000 / $100,000 · exp ")


def test_insurance_summary_when_nothing_on_file():
    aircraft = AircraftFactory(
        n_number="N5AA",
        insurance_liability_per_occurrence_cents=0,
        insurance_liability_per_person_cents=0,
        insurance_expiration=None,
    )
    assert aircraft.insurance_summary == "No insurance on file"


def test_str_and_display_name():
    aircraft = AircraftFactory(n_number="N6AA", make="Piper", model="Archer")
    assert str(aircraft) == "N6AA (Piper Archer)"
    assert aircraft.display_name == "N6AA — Piper Archer"


def test_str_without_make_or_model():
    aircraft = AircraftFactory(n_number="N7AA", make="", model="")
    assert str(aircraft) == "N7AA"


def test_profile_aircraft_relation(profile, aircraft):
    profile.aircraft.add(aircraft)
    assert list(aircraft.pilots.all()) == [profile]
