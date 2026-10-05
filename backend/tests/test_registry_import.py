"""The FAA registry import: the parser, ``import_registry``, and ``import_faa_registry``.

``docs/developer/aircraft-registry.rst`` describes the import.  Every test reads the
fixture cut from a real download (``apps/aircraft/fixtures/faa``) or a small file
written here; nothing downloads from the FAA.
"""

from __future__ import annotations

import logging
import shutil
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, timedelta
from io import StringIO
from pathlib import Path

import httpx
import pytest
import respx
from django.core.management import CommandError, call_command
from django.db import connection
from django.utils import timezone
from pytest_django import Settings

from apps.aircraft import registry
from apps.aircraft.aliases import ALIASES
from apps.aircraft.models import (
    AircraftCategory,
    AircraftType,
    AircraftTypeAlias,
    Airworthiness,
    RegistrantType,
    Registration,
    RegistrationStatus,
    RegistryImport,
)
from apps.aircraft.registry import (
    ALREADY_RUNNING,
    FIXTURE_DIR,
    ImportAlreadyRunningError,
    RegistryFormatError,
    import_registry,
    parse_date,
    read_registrations,
    read_types,
    registrant_type_for,
    status_for,
)
from apps.aircraft.seed import AIRFRAMES
from tests.factories import AircraftFactory, AircraftTypeFactory

pytestmark = pytest.mark.django_db

#: The reference and master rows the fixture holds.
FIXTURE_TYPES = 338
FIXTURE_REGISTRATIONS = 218

#: The header rows of the two files, as the FAA writes them.
REF_HEADER = (
    "CODE,MFR,MODEL,TYPE-ACFT,TYPE-ENG,AC-CAT,BUILD-CERT-IND,NO-ENG,NO-SEATS,AC-WEIGHT,"
    "SPEED,TC-DATA-SHEET,TC-DATA-HOLDER,"
)
MASTER_HEADER = (
    "N-NUMBER,SERIAL NUMBER,MFR MDL CODE,ENG MFR MDL,YEAR MFR,TYPE REGISTRANT,NAME,STREET,"
    "STREET2,CITY,STATE,ZIP CODE,REGION,COUNTY,COUNTRY,LAST ACTION DATE,CERT ISSUE DATE,"
    "CERTIFICATION,TYPE AIRCRAFT,TYPE ENGINE,STATUS CODE,MODE S CODE,FRACT OWNER,"
    "AIR WORTH DATE,OTHER NAMES(1),OTHER NAMES(2),OTHER NAMES(3),OTHER NAMES(4),"
    "OTHER NAMES(5),EXPIRATION DATE,UNIQUE ID,KIT MFR, KIT MODEL,MODE S CODE HEX,"
)


def _ref_row(code: str, mfr: str, model: str, *, engines: str = "01", seats: str = "004") -> str:
    """One ``ACFTREF.txt`` row, padded as the FAA pads it."""
    return (
        f"{code},{mfr:<30},{model:<20},4,1 ,1,0,{engines},{seats},CLASS 1,0120,{'':<15},{'':<50},"
    )


def _master_row(
    n_number: str,
    code: str,
    *,
    year: str = "2005",
    registrant: str = "1",
    name: str = "DOE JANE",
    status: str = "V",
    issued: str = "20200115",
    expires: str = "20270131",
) -> str:
    """One ``MASTER.txt`` row with the columns the import reads filled in."""
    columns = [
        f"{n_number:<5}",
        "12345",
        code,
        "17003",
        f"{year:<4}",
        registrant,
        f"{name:<50}",
        "",
        "",
        "",
        "CA",
        "",
        "4",
        "001",
        "US",
        "20230101",
        issued,
        "1",
        "4",
        "1 ",
        f"{status:<2}",
        "50000001",
        " ",
        "20000101",
        "",
        "",
        "",
        "",
        "",
        expires,
        "00000001",
        "",
        "",
        "A00001",
        "",
    ]
    return ",".join(columns)


def _write_registry(directory: Path, types: list[str], registrations: list[str]) -> Path:
    """Write ``ACFTREF.txt`` and ``MASTER.txt`` into ``directory`` with a BOM and CRLF."""
    directory.mkdir(parents=True, exist_ok=True)
    for name, header, rows in (
        ("ACFTREF.txt", REF_HEADER, types),
        ("MASTER.txt", MASTER_HEADER, registrations),
    ):
        text = "\r\n".join([header, *rows]) + "\r\n"
        (directory / name).write_text(text, encoding="utf-8-sig", newline="")
    return directory


@pytest.fixture
def small_registry(tmp_path: Path) -> Path:
    """A two-type, three-registration registry directory."""
    return _write_registry(
        tmp_path / "small",
        [_ref_row("2072439", "CESSNA", "172S"), _ref_row("060002B", "AEROPRO CZ", "EUROFOX")],
        [
            _master_row("172SP", "2072439"),
            _master_row("9EL", "060002B", registrant="7", name="FOX FLYERS LLC"),
            _master_row("12345", "2072439", status="R", year=""),
        ],
    )


def _zip_of(directory: Path, target: Path) -> Path:
    """A zip at ``target`` holding the two files of ``directory`` and an unrelated one."""
    with zipfile.ZipFile(target, "w") as archive:
        archive.write(directory / "ACFTREF.txt", "ACFTREF.txt")
        archive.write(directory / "MASTER.txt", "MASTER.txt")
        archive.writestr("ardata.pdf", b"%PDF-1.4")
    return target


# -- the codes ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("1", RegistrantType.INDIVIDUAL),
        ("2", RegistrantType.PARTNERSHIP),
        ("3", RegistrantType.CORPORATION),
        ("4", RegistrantType.CO_OWNED),
        ("5", RegistrantType.GOVERNMENT),
        ("7", RegistrantType.LLC),
        ("8", RegistrantType.NON_CITIZEN_CORPORATION),
        ("9", RegistrantType.NON_CITIZEN_CO_OWNED),
        ("", RegistrantType.UNKNOWN),
        ("6", RegistrantType.UNKNOWN),
    ],
)
def test_each_registrant_code_maps_to_its_choice(code: str, expected: str) -> None:
    """The FAA's registrant codes read as the registrant types; any other is unknown."""
    assert registrant_type_for(code) == expected


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("V", RegistrationStatus.VALID),
        ("M", RegistrationStatus.VALID),
        ("T", RegistrationStatus.VALID),
        ("R", RegistrationStatus.PENDING),
        ("2", RegistrationStatus.PENDING),
        ("19", RegistrationStatus.PENDING),
        ("9", RegistrationStatus.REVOKED),
        ("W", RegistrationStatus.REVOKED),
        ("22", RegistrationStatus.REVOKED),
        ("D", RegistrationStatus.EXPIRED),
        ("13", RegistrationStatus.EXPIRED),
        ("29", RegistrationStatus.EXPIRED),
        ("7", RegistrationStatus.OTHER),
        ("N", RegistrationStatus.OTHER),
        ("", RegistrationStatus.OTHER),
    ],
)
def test_each_status_code_maps_to_its_choice(code: str, expected: str) -> None:
    """The FAA's status codes read as valid, pending, revoked, expired, or other."""
    assert status_for(code) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [("20270131", date(2027, 1, 31)), ("", None), ("00000000", None), ("2027013", None)],
)
def test_a_registry_date_reads_as_a_date_or_nothing(value: str, expected: date | None) -> None:
    """``YYYYMMDD`` is a date; a blank or malformed value is none."""
    assert parse_date(value) == expected


# -- the parser -----------------------------------------------------------------


def test_the_reference_file_reads_as_stripped_types(small_registry: Path) -> None:
    """Each reference row: its code, stripped FAA names, counts, and category."""
    with (small_registry / "ACFTREF.txt").open("rb") as stream:
        rows = list(read_types(stream))
    assert rows[0] == ("2072439", "CESSNA", "172S", 4, 1, AircraftCategory.AIRPLANE)


def test_the_master_file_reads_as_normalized_registrations(small_registry: Path) -> None:
    """Each master row is a canonical N-number, the code, and the mapped values."""
    with (small_registry / "MASTER.txt").open("rb") as stream:
        rows = list(read_registrations(stream))
    assert rows[1] == (
        "N9EL",
        "060002B",
        2005,
        "FOX FLYERS LLC",
        RegistrantType.LLC,
        RegistrationStatus.VALID,
        date(2020, 1, 15),
        date(2027, 1, 31),
        Airworthiness.STANDARD,
    )


def test_a_blank_year_reads_as_none(small_registry: Path) -> None:
    """A master row without a year of manufacture has no year."""
    with (small_registry / "MASTER.txt").open("rb") as stream:
        rows = list(read_registrations(stream))
    assert rows[2].year is None


def test_a_file_missing_a_column_is_refused(tmp_path: Path) -> None:
    """A reference file without ``NO-SEATS`` names the missing column."""
    path = tmp_path / "ACFTREF.txt"
    path.write_text(
        "CODE,MFR,MODEL,TYPE-ACFT,NO-ENG\r\n2072439,CESSNA,172S,4,01\r\n", encoding="utf-8"
    )
    with (
        path.open("rb") as stream,
        pytest.raises(RegistryFormatError, match=r"ACFTREF\.txt has no NO-SEATS column\."),
    ):
        list(read_types(stream))


# -- importing -------------------------------------------------------------------


def test_the_fixture_imports_every_type_and_registration() -> None:
    """The fixture's 338 reference rows and 218 master rows all land."""
    run = import_registry(str(FIXTURE_DIR))
    assert (run.types_written, run.registrations_written) == (
        FIXTURE_TYPES,
        FIXTURE_REGISTRATIONS,
    )


def test_an_import_records_one_successful_run() -> None:
    """The run row is ok, finished, and names its source."""
    import_registry(str(FIXTURE_DIR))
    run = RegistryImport.objects.get()
    assert (run.ok, run.finished_at is not None, run.source, run.error) == (
        True,
        True,
        str(FIXTURE_DIR),
        "",
    )


def test_an_imported_type_carries_display_names(small_registry: Path) -> None:
    """The FAA spelling is kept beside the display names every screen prints."""
    import_registry(str(small_registry))
    entry = AircraftType.objects.get(faa_code="060002B")
    assert (entry.faa_make, entry.faa_model, entry.make, entry.model, entry.is_custom) == (
        "AEROPRO CZ",
        "EUROFOX",
        "Aeropro",
        "Eurofox",
        False,
    )


def test_an_imported_registration_points_at_its_type(small_registry: Path) -> None:
    """A registration's type is the reference entry its master row names."""
    import_registry(str(small_registry))
    assert str(Registration.objects.get(n_number="N172SP").type) == "Cessna 172S"


def test_an_import_stores_each_registrant_in_title_case(small_registry: Path) -> None:
    """The registry's capitals are stored as a person's name or a business's reads."""
    import_registry(str(small_registry))
    names = dict(Registration.objects.values_list("n_number", "registrant_name"))
    assert (names["N172SP"], names["N9EL"]) == ("Doe Jane", "Fox Flyers LLC")


def test_an_import_writes_the_aliases() -> None:
    """The aliases resolve against the imported vocabulary."""
    import_registry(str(FIXTURE_DIR))
    assert str(AircraftTypeAlias.objects.get(alias="eurofox").type) == "Aeropro Eurofox"


def test_a_zip_imports_as_its_directory_does(small_registry: Path, tmp_path: Path) -> None:
    """A local zip holding the two files is read without unpacking by hand."""
    run = import_registry(str(_zip_of(small_registry, tmp_path / "registry.zip")))
    assert (run.types_written, run.registrations_written) == (2, 3)


def test_a_file_url_imports_as_its_path_does(small_registry: Path) -> None:
    """``file://`` names a local directory."""
    run = import_registry(small_registry.as_uri())
    assert run.registrations_written == 3


def test_an_http_source_is_downloaded(small_registry: Path, tmp_path: Path) -> None:
    """An ``https`` source is downloaded as a zip and imported."""
    body = _zip_of(small_registry, tmp_path / "download.zip").read_bytes()
    url = "https://registry.example.test/ReleasableAircraft.zip"
    with respx.mock(assert_all_called=True) as router:
        router.get(url).mock(return_value=httpx.Response(200, content=body))
        run = import_registry(url)
    assert run.registrations_written == 3


def test_a_failed_download_is_recorded(tmp_path: Path) -> None:
    """A download the server refuses leaves a failed run naming the status."""
    url = "https://registry.example.test/ReleasableAircraft.zip"
    with respx.mock() as router:
        router.get(url).mock(return_value=httpx.Response(503))
        with pytest.raises(httpx.HTTPStatusError, match="503"):
            import_registry(url)
    run = RegistryImport.objects.get()
    assert (run.ok, "503" in run.error) == (False, True)


def test_the_source_opens_before_any_transaction(
    small_registry: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A slow or failed download never holds a database transaction open.

    Every test already runs inside pytest-django's own wrapping transaction, so a
    nested ``transaction.atomic()`` shows up as a new savepoint rather than a change
    in ``connection.in_atomic_block``; the write phase's savepoint should not exist yet
    when the source opens.
    """
    original = registry._opened_source
    baseline = len(connection.savepoint_ids)
    savepoints_when_opened: list[int] = []

    @contextmanager
    def spy(source: str) -> Iterator[registry.Opener]:
        savepoints_when_opened.append(len(connection.savepoint_ids) - baseline)
        with original(source) as opener:
            yield opener

    monkeypatch.setattr(registry, "_opened_source", spy)
    import_registry(str(small_registry))
    assert savepoints_when_opened == [0]


def test_a_call_with_no_row_refuses_while_one_is_running(small_registry: Path) -> None:
    """The nightly timer's own path -- no ``run`` passed in -- takes the same lock.

    So it can never overlap a Run now press: whichever gets there first runs.
    """
    RegistryImport.objects.create(started_at=timezone.now())
    with pytest.raises(ImportAlreadyRunningError, match=ALREADY_RUNNING):
        import_registry(str(small_registry))


def test_a_call_with_no_row_ignores_a_stale_one(small_registry: Path) -> None:
    """A run stuck past the stale limit does not block a fresh unattended one."""
    RegistryImport.objects.create(started_at=timezone.now() - timedelta(minutes=31))
    run = import_registry(str(small_registry))
    assert run.ok is True


def test_importing_twice_writes_the_same_rows() -> None:
    """A second import updates rather than duplicates."""
    import_registry(str(FIXTURE_DIR))
    import_registry(str(FIXTURE_DIR))
    assert (AircraftType.objects.count(), Registration.objects.count()) == (
        FIXTURE_TYPES,
        FIXTURE_REGISTRATIONS,
    )


def test_a_registration_gone_from_the_file_is_deleted(small_registry: Path) -> None:
    """An N-number the FAA no longer lists leaves the registry."""
    Registration.objects.create(
        n_number="N999ZZ", type=AircraftTypeFactory(make="Piper", model="PA-28-181")
    )
    import_registry(str(small_registry))
    assert not Registration.objects.filter(n_number="N999ZZ").exists()


def test_a_type_gone_from_the_file_stays(small_registry: Path) -> None:
    """A type the FAA drops is kept, since an aircraft may point at it."""
    kept = AircraftTypeFactory(faa_code="9999999", make="Piper", model="PA-28-181")
    import_registry(str(small_registry))
    assert AircraftType.objects.filter(pk=kept.pk).exists()


def test_a_reimport_refreshes_a_changed_registration(small_registry: Path) -> None:
    """A registration already held takes the file's values."""
    Registration.objects.create(
        n_number="N172SP", type=AircraftTypeFactory(make="Piper", model="PA-28-181"), year=1970
    )
    import_registry(str(small_registry))
    registration = Registration.objects.get(n_number="N172SP")
    assert (str(registration.type), registration.year) == ("Cessna 172S", 2005)


def test_a_registration_naming_an_unknown_type_is_skipped(tmp_path: Path) -> None:
    """A master row whose code the reference file lacks is left out, not fatal."""
    source = _write_registry(
        tmp_path / "gap",
        [_ref_row("2072439", "CESSNA", "172S")],
        [_master_row("172SP", "2072439"), _master_row("1AB", "0000000")],
    )
    run = import_registry(str(source))
    assert list(Registration.objects.values_list("n_number", flat=True)) == ["N172SP"]
    assert run.registrations_written == 1


def test_types_only_skips_the_master_file(small_registry: Path) -> None:
    """``types_only`` refreshes the vocabulary and leaves the registrations alone."""
    run = import_registry(str(small_registry), types_only=True)
    assert (run.types_written, Registration.objects.count()) == (2, 0)


def test_an_import_logs_counts_and_never_a_name(
    small_registry: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The log says how much was written, and nobody's name."""
    with caplog.at_level(logging.INFO, logger="apps.aircraft.registry"):
        import_registry(str(small_registry))
    assert ("3 registrations" in caplog.text, "FOX FLYERS" in caplog.text) == (True, False)


# -- folding hand-added types -------------------------------------------------------


@pytest.fixture
def custom_eurofox() -> AircraftType:
    """A hand-added Aeropro Eurofox with an aircraft and an alias pointing at it."""
    custom = AircraftType.objects.create(
        faa_code="CUSTOM-1",
        faa_make="AEROPRO",
        faa_model="EUROFOX",
        make="Aeropro",
        model="EUROFOX",
        is_custom=True,
    )
    AircraftFactory(n_number="N9EL", type=custom)
    AircraftTypeAlias.objects.create(alias="our fox", type=custom)
    return custom


def test_a_custom_type_the_faa_lists_is_folded_away(
    small_registry: Path, custom_eurofox: AircraftType
) -> None:
    """The hand-added entry is deleted once the FAA lists the same type."""
    run = import_registry(str(small_registry))
    assert (run.types_folded, AircraftType.objects.filter(pk=custom_eurofox.pk).exists()) == (
        1,
        False,
    )


def test_folding_moves_the_aircraft_to_the_faa_entry(
    small_registry: Path, custom_eurofox: AircraftType
) -> None:
    """An aircraft on the hand-added entry points at the FAA's afterwards."""
    import_registry(str(small_registry))
    assert AircraftType.objects.get(aircraft__n_number="N9EL").faa_code == "060002B"


def test_folding_moves_the_aliases_to_the_faa_entry(
    small_registry: Path, custom_eurofox: AircraftType
) -> None:
    """The hand-added entry's aliases move with its aircraft."""
    import_registry(str(small_registry))
    assert AircraftTypeAlias.objects.get(alias="our fox").type.faa_code == "060002B"


def test_a_custom_type_the_faa_does_not_list_stays(small_registry: Path) -> None:
    """A hand-added type with no FAA twin is kept."""
    custom = AircraftType.objects.create(
        faa_code="CUSTOM-2", faa_make="X", faa_model="Y", make="Zenith", model="CH 750"
    )
    custom.is_custom = True
    custom.save()
    run = import_registry(str(small_registry))
    assert (run.types_folded, AircraftType.objects.filter(pk=custom.pk).exists()) == (0, True)


# -- failure ------------------------------------------------------------------------


def test_a_source_missing_the_master_file_fails_and_says_why(tmp_path: Path) -> None:
    """A directory without ``MASTER.txt`` fails, and the run row says so."""
    source = tmp_path / "half"
    source.mkdir()
    shutil.copy(FIXTURE_DIR / "ACFTREF.txt", source / "ACFTREF.txt")
    with pytest.raises(RegistryFormatError, match=r"MASTER\.txt"):
        import_registry(str(source))
    run = RegistryImport.objects.get()
    assert (run.ok, run.finished_at is not None, "MASTER.txt" in run.error) == (False, True, True)


def test_a_failed_import_writes_nothing(tmp_path: Path) -> None:
    """A failure rolls back every type and registration the run wrote."""
    source = tmp_path / "half"
    source.mkdir()
    shutil.copy(FIXTURE_DIR / "ACFTREF.txt", source / "ACFTREF.txt")
    with pytest.raises(RegistryFormatError, match=r"MASTER\.txt"):
        import_registry(str(source))
    assert AircraftType.objects.count() == 0


# -- the command ----------------------------------------------------------------------


def test_the_command_imports_the_named_source(small_registry: Path) -> None:
    """``--source`` names what to read."""
    call_command("import_faa_registry", source=str(small_registry))
    assert Registration.objects.count() == 3


def test_the_command_reads_the_setting_without_a_source(
    small_registry: Path, settings: Settings
) -> None:
    """Without ``--source`` the command reads ``FAA_REGISTRY_URL``."""
    settings.FAA_REGISTRY_URL = str(small_registry)
    call_command("import_faa_registry")
    assert RegistryImport.objects.get().source == str(small_registry)


def test_the_command_takes_types_only(small_registry: Path) -> None:
    """``--types-only`` skips the master file."""
    call_command("import_faa_registry", source=str(small_registry), types_only=True)
    assert (AircraftType.objects.count(), Registration.objects.count()) == (2, 0)


def test_the_command_fills_in_the_row_it_is_given(small_registry: Path) -> None:
    """``--import-id`` fills in the row Health and database wrote, not another."""
    run = RegistryImport.objects.create(source="pending")
    call_command("import_faa_registry", source=str(small_registry), import_id=run.pk)
    run.refresh_from_db()
    assert (RegistryImport.objects.count(), run.ok, run.registrations_written) == (1, True, 3)


def test_the_command_fails_with_a_command_error(tmp_path: Path) -> None:
    """A failed import raises ``CommandError`` naming the reason."""
    with pytest.raises(CommandError, match=r"ACFTREF\.txt"):
        call_command("import_faa_registry", source=str(tmp_path))


def test_the_command_refuses_an_unknown_import_id(small_registry: Path) -> None:
    """``--import-id`` naming no row is refused before anything is read."""
    with pytest.raises(CommandError, match="No registry import 999999"):
        call_command("import_faa_registry", source=str(small_registry), import_id=999999)


def test_the_command_reports_its_counts(small_registry: Path) -> None:
    """The command says how many types and registrations it wrote."""
    out = StringIO()
    call_command("import_faa_registry", source=str(small_registry), stdout=out)
    assert "Imported 2 types and 3 registrations" in out.getvalue()


# -- the fixture ----------------------------------------------------------------------


def test_every_alias_resolves_against_the_fixture() -> None:
    """Each alias names a type the fixture holds, so the demo searches as production."""
    import_registry(str(FIXTURE_DIR))
    unresolved = sorted(
        set(ALIASES) - set(AircraftTypeAlias.objects.values_list("alias", flat=True))
    )
    assert unresolved == []


@pytest.mark.parametrize("airframe", AIRFRAMES, ids=" ".join)
def test_every_seeded_airframe_has_registrations_to_seed(airframe: tuple[str, str]) -> None:
    """The fixture holds at least three valid, dated registrations of each seeded type."""
    import_registry(str(FIXTURE_DIR))
    make, model = airframe
    held = Registration.objects.filter(
        type__make=make,
        type__model=model,
        status=RegistrationStatus.VALID,
        year__isnull=False,
    ).count()
    assert held >= 3
