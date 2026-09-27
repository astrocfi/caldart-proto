"""The aircraft types: the models, the display names, the aliases, and the search.

``docs/developer/data-model.rst`` describes the models; the naming, alias and search
rules are those the aircraft type picker relies on, so one type always reads one way
however it was typed.
"""

from __future__ import annotations

import pytest
from django.db.models import ProtectedError

from apps.accounts.models import User
from apps.aircraft.aliases import ALIASES, write_aliases
from apps.aircraft.models import (
    AircraftType,
    AircraftTypeAlias,
    RegistrantType,
    Registration,
    RegistrationStatus,
    RegistryImport,
)
from apps.aircraft.naming import MAKE_NAMES, display_make, display_model
from apps.aircraft.seed import AIRFRAMES
from apps.aircraft.types import search_types
from tests.factories import AircraftFactory, AircraftTypeFactory

pytestmark = pytest.mark.django_db

#: (FAA make, FAA model, seats) of the handful of types the search tests look through.
VOCABULARY: tuple[tuple[str, str, int], ...] = (
    ("CESSNA", "172S", 4),
    ("CESSNA", "182T", 4),
    ("PIPER", "PA-28-181", 4),
    ("CIRRUS DESIGN CORP", "SR22", 4),
    ("BEECH", "A36", 6),
    ("AEROPRO CZ", "EUROFOX", 2),
    ("MOONEY", "M20J", 4),
)


@pytest.fixture
def vocabulary() -> dict[str, AircraftType]:
    """The types of :data:`VOCABULARY` with their display names, and their aliases.

    Returns the types keyed by ``<make> <model>`` display name.  The aliases are written
    from ``ALIASES`` by ``write_aliases``, as the registry import writes them.
    """
    types = {}
    for faa_make, faa_model, seats in VOCABULARY:
        created = AircraftTypeFactory(
            faa_make=faa_make,
            faa_model=faa_model,
            make=display_make(faa_make),
            model=display_model(faa_model),
            seats=seats,
        )
        types[str(created)] = created
    write_aliases()
    return types


def _leading(query: str) -> str:
    """The display name of the first type ``search_types`` answers ``query`` with."""
    return str(search_types(query)[0])


# -- the models ---------------------------------------------------------------


def test_an_aircraft_type_reads_as_its_make_and_model() -> None:
    """``str()`` of a type is its display make and model."""
    assert str(AircraftTypeFactory(make="Cessna", model="172S")) == "Cessna 172S"


def test_an_aircraft_type_is_an_faa_entry_unless_marked_custom() -> None:
    """A type is not custom until an account administrator adds it as one."""
    created = AircraftType.objects.create(
        faa_code="2072738", faa_make="CESSNA", faa_model="172S", make="Cessna", model="172S"
    )
    assert created.is_custom is False


def test_aircraft_types_sort_by_make_then_model() -> None:
    """The vocabulary lists in make, then model, order."""
    AircraftTypeFactory(make="Piper", model="PA-28-181")
    AircraftTypeFactory(make="Cessna", model="182T")
    AircraftTypeFactory(make="Cessna", model="172S")
    assert [str(entry) for entry in AircraftType.objects.all()] == [
        "Cessna 172S",
        "Cessna 182T",
        "Piper PA-28-181",
    ]


def test_an_aircraft_reads_its_make_and_model_from_its_type() -> None:
    """``Aircraft.make`` and ``Aircraft.model`` are the type's display names."""
    aircraft = AircraftFactory(make="Cirrus", model="SR22")
    assert (aircraft.make, aircraft.model) == ("Cirrus", "SR22")


def test_a_type_an_aircraft_points_at_cannot_be_deleted() -> None:
    """Deleting a type an aircraft uses is refused rather than orphaning the aircraft."""
    aircraft = AircraftFactory(make="Cirrus", model="SR22")
    with pytest.raises(ProtectedError, match="protected foreign keys"):
        aircraft.type.delete()


def test_a_type_a_registration_points_at_cannot_be_deleted() -> None:
    """Deleting a type a registration uses is refused too."""
    registration = Registration.objects.create(
        n_number="N172SP", type=AircraftTypeFactory(make="Cessna", model="172S")
    )
    with pytest.raises(ProtectedError, match="protected foreign keys"):
        registration.type.delete()


def test_deleting_a_type_deletes_its_aliases() -> None:
    """An alias lives and dies with the type it names."""
    entry = AircraftTypeFactory(make="Cessna", model="172S")
    AircraftTypeAlias.objects.create(alias="c172", type=entry)
    entry.delete()
    assert AircraftTypeAlias.objects.count() == 0


def test_an_alias_is_stored_lower_case_and_stripped() -> None:
    """``C172 `` is kept as ``c172``, the form a search compares against."""
    alias = AircraftTypeAlias.objects.create(
        alias=" C172 ", type=AircraftTypeFactory(make="Cessna", model="172S")
    )
    assert alias.alias == "c172"


def test_an_alias_reads_as_itself() -> None:
    """``str()`` of an alias is the alias."""
    alias = AircraftTypeAlias(alias="skyhawk")
    assert str(alias) == "skyhawk"


def test_a_registration_stores_its_n_number_normalized() -> None:
    """A registration keeps the canonical ``N`` form, as the register does."""
    registration = Registration.objects.create(
        n_number="172sp", type=AircraftTypeFactory(make="Cessna", model="172S")
    )
    assert registration.n_number == "N172SP"


def test_a_registration_reads_as_its_n_number() -> None:
    """``str()`` of a registration is its N-number."""
    registration = Registration(n_number="N172SP")
    assert str(registration) == "N172SP"


def test_a_registration_defaults_to_a_valid_one_of_unknown_registrant() -> None:
    """A registration written without them is valid and of unknown registrant type."""
    registration = Registration.objects.create(
        n_number="N172SP", type=AircraftTypeFactory(make="Cessna", model="172S")
    )
    assert (registration.status, registration.registrant_type) == (
        RegistrationStatus.VALID,
        RegistrantType.UNKNOWN,
    )


def test_a_registry_import_starts_unfinished_and_not_ok() -> None:
    """A fresh import row has no finish time, no counts, and is not ok."""
    run = RegistryImport.objects.create(source="https://example.test/registry.zip")
    assert (
        run.finished_at,
        run.ok,
        run.types_written,
        run.registrations_written,
        run.types_folded,
    ) == (None, False, 0, 0, 0)


def test_a_registry_import_reads_as_its_start_and_outcome() -> None:
    """``str()`` of an import names when it started and whether it succeeded."""
    run = RegistryImport.objects.create(source="fixture")
    assert str(run) == f"registry import {run.started_at:%Y-%m-%d %H:%M} (not ok)"


def test_a_registry_import_outlives_the_account_that_started_it(member: User) -> None:
    """Deleting the system administrator who pressed Run now keeps the import row."""
    run = RegistryImport.objects.create(source="fixture", started_by=member)
    member.delete()
    run.refresh_from_db()
    assert run.started_by is None


# -- display names ------------------------------------------------------------


@pytest.mark.parametrize(
    ("faa_make", "expected"),
    [
        ("CESSNA", "Cessna"),
        ("CESSNA AIRCRAFT CO", "Cessna"),
        ("BEECH", "Beechcraft"),
        ("HAWKER BEECHCRAFT CORP", "Beechcraft"),
        ("CIRRUS DESIGN CORP", "Cirrus"),
        ("DIAMOND AIRCRAFT IND INC", "Diamond"),
        ("AEROPRO CZ", "Aeropro"),
        ("AEROPRO S R O", "Aeropro"),
        ("GRUMMAN AMERICAN AVN CORP", "Grumman American"),
        ("AMERICAN GENERAL ACFT CORP", "Grumman American"),
        ("VANS", "Van's"),
        ("CUBCRAFTERS", "CubCrafters"),
        ("  cessna  ", "Cessna"),
        ("FOO AIRCRAFT CORP", "Foo Aircraft"),
        ("BAR AVIATION INC.", "Bar Aviation"),
        ("QUUX AEROSPACE S R O", "Quux Aerospace"),
        ("AEROPRO CZ S R O", "Aeropro"),
        ("MOONEY AIRCRAFT CORP.", "Mooney"),
        ("GRUMMAN AMERICAN AVN. CORP.", "Grumman American"),
        ("ROBINSON HELICOPTER COMPANY", "Robinson"),
        ("DEHAVILLAND", "de Havilland"),
        ("COSTRUZIONI AERONAUTICHE TECNA", "Tecnam"),
        ("PIPISTREL D O O", "Pipistrel"),
    ],
)
def test_display_make_gives_one_name_per_manufacturer(faa_make: str, expected: str) -> None:
    """Every FAA spelling of a maker reads as one name; an unknown one is tidied."""
    assert display_make(faa_make) == expected


@pytest.mark.parametrize(
    ("faa_model", "expected"),
    [
        ("172S", "Cessna"),
        ("T206H", "Cessna"),
        ("525C", "Cessna"),
        ("G36", "Beechcraft"),
        ("G58", "Beechcraft"),
        ("B200GT", "Beechcraft"),
        ("B300", "Beechcraft"),
        ("C90GTI", "Beechcraft"),
        ("3000 (AT-6C)", "Beechcraft"),
    ],
)
def test_textron_aviation_reads_as_the_maker_of_the_model(faa_model: str, expected: str) -> None:
    """``TEXTRON AVIATION INC`` builds Cessnas and Beechcrafts; the model says which."""
    assert display_make("TEXTRON AVIATION INC", faa_model) == expected


@pytest.mark.parametrize(
    ("faa_model", "expected"),
    [
        ("172S", "172S"),
        ("SKYHAWK", "Skyhawk"),
        ("172S SKYHAWK", "172S Skyhawk"),
        ("PA-28-181", "PA-28-181"),
        ("SR22", "SR22"),
        ("M20J", "M20J"),
        ("DA 40", "DA 40"),
        ("A36", "A36"),
        ("EUROFOX", "Eurofox"),
        ("TRI-PACER", "Tri-Pacer"),
        ("  172S   SKYHAWK ", "172S Skyhawk"),
    ],
)
def test_display_model_keeps_designators_and_title_cases_names(
    faa_model: str, expected: str
) -> None:
    """A token with a digit or of three characters stays; a longer word is title-cased."""
    assert display_model(faa_model) == expected


@pytest.mark.parametrize("airframe", AIRFRAMES, ids=lambda airframe: airframe[0])
def test_every_seeded_manufacturer_has_a_make_name(airframe: tuple[str, str]) -> None:
    """Each manufacturer the seed flies is one of the names ``MAKE_NAMES`` gives."""
    assert airframe[0] in set(MAKE_NAMES.values())


# -- aliases ------------------------------------------------------------------


def test_every_alias_is_lower_case_and_fits_the_column() -> None:
    """Each ``ALIASES`` key is what an alias row stores: lower-case, 40 characters."""
    bad = [alias for alias in ALIASES if alias != alias.strip().lower() or len(alias) > 40]
    assert bad == []


@pytest.mark.parametrize(
    ("alias", "expected"),
    [
        ("c172", "Cessna 172S"),
        ("skyhawk", "Cessna 172S"),
        ("c182", "Cessna 182T"),
        ("p28a", "Piper PA-28-181"),
        ("archer", "Piper PA-28-181"),
        ("cherokee", "Piper PA-28-181"),
        ("sr22", "Cirrus SR22"),
        ("be36", "Beechcraft A36"),
        ("eurofox", "Aeropro Eurofox"),
    ],
)
def test_an_alias_resolves_to_the_type_it_names(
    vocabulary: dict[str, AircraftType], alias: str, expected: str
) -> None:
    """``write_aliases`` points each alias at the type whose make and model it names."""
    assert str(AircraftTypeAlias.objects.get(alias=alias).type) == expected


def test_an_alias_naming_no_type_is_skipped(vocabulary: dict[str, AircraftType]) -> None:
    """An alias whose type is not in the vocabulary writes no row."""
    assert not AircraftTypeAlias.objects.filter(alias="r44").exists()


def test_an_alias_picks_the_shortest_matching_model() -> None:
    """Of the types a prefix matches, the alias names the one with the shortest model."""
    AircraftTypeFactory(make="Cessna", model="172S Skyhawk SP")
    AircraftTypeFactory(make="Cessna", model="172S")
    write_aliases()
    assert str(AircraftTypeAlias.objects.get(alias="c172").type) == "Cessna 172S"


def test_writing_the_aliases_twice_writes_the_same_rows(
    vocabulary: dict[str, AircraftType],
) -> None:
    """``write_aliases`` is idempotent: a second run leaves the same alias rows."""
    before = sorted(AircraftTypeAlias.objects.values_list("alias", "type_id"))
    write_aliases()
    assert sorted(AircraftTypeAlias.objects.values_list("alias", "type_id")) == before


# -- search -------------------------------------------------------------------


@pytest.mark.parametrize("query", ["cesna 172", "CESSNA 172", "c172", "CESSNA", "skyhawk"])
def test_every_spelling_of_a_cessna_172_leads_with_it(
    vocabulary: dict[str, AircraftType], query: str
) -> None:
    """However badly the type is typed, the Cessna 172 comes first."""
    assert _leading(query) == "Cessna 172S"


def test_a_foreign_type_is_found_by_its_name(vocabulary: dict[str, AircraftType]) -> None:
    """``eurofox`` finds the Aeropro Eurofox, a type built outside the United States."""
    assert _leading("eurofox") == "Aeropro Eurofox"


def test_a_misspelled_foreign_type_is_found(vocabulary: dict[str, AircraftType]) -> None:
    """``euro fox`` still finds the Eurofox, by trigram similarity."""
    assert "Aeropro Eurofox" in [str(entry) for entry in search_types("euro fox")]


def test_a_query_with_digits_finds_the_model_holding_them(
    vocabulary: dict[str, AircraftType],
) -> None:
    """``x182`` resembles no name, but its digits find the Cessna 182T."""
    assert [str(entry) for entry in search_types("x182")] == ["Cessna 182T"]


@pytest.mark.parametrize("query", ["", "   "])
def test_a_blank_query_finds_nothing(vocabulary: dict[str, AircraftType], query: str) -> None:
    """Nothing is searched for until something is typed."""
    assert search_types(query) == []


def test_a_search_never_repeats_a_type(vocabulary: dict[str, AircraftType]) -> None:
    """A type found by its alias, its name, and its digits is listed once."""
    found = [entry.pk for entry in search_types("c172")]
    assert len(found) == len(set(found))


def test_a_search_answers_at_most_the_limit(vocabulary: dict[str, AircraftType]) -> None:
    """``limit`` caps the answer."""
    assert len(search_types("cessna", limit=1)) == 1


def test_equally_similar_types_lead_with_the_most_registered() -> None:
    """Of two types a query resembles equally, the more registered one leads."""
    AircraftTypeFactory(make="Cessna", model="150")
    popular = AircraftTypeFactory(make="Cessna", model="172")
    Registration.objects.create(n_number="N172AB", type=popular)
    assert _leading("cesna") == "Cessna 172"


def test_equally_similar_and_registered_types_lead_by_name() -> None:
    """With nothing else to tell them apart, types list by make and model."""
    AircraftTypeFactory(make="Cessna", model="172")
    AircraftTypeFactory(make="Cessna", model="150")
    assert _leading("cesna") == "Cessna 150"


def test_a_nonsense_query_finds_nothing(vocabulary: dict[str, AircraftType]) -> None:
    """A query resembling no type answers an empty list."""
    assert search_types("zzqx") == []
