"""The FAA registry: reading the Releasable Aircraft Database and importing it.

The FAA publishes the whole US civil registry as one zip.  Two of its files matter:
``ACFTREF.txt``, the aircraft reference, whose rows become the aircraft types, and
``MASTER.txt``, one row per N-number, whose rows become the registrations.  Both are
comma-separated with a header row, fixed-width, and space-padded; every value is
stripped as it is read.  No address is kept.

:func:`import_registry` reads a source (a URL it downloads, a local zip, or a directory
holding the two files), upserts the types, folds away any hand-added type the FAA now
lists, upserts the registrations and deletes those the file no longer holds, writes the
aliases, and records the run as a ``RegistryImport``.  ``manage.py import_faa_registry``
wraps it, and :func:`start_import` starts that command from the System screen.
"""

from __future__ import annotations

import csv
import io
import logging
import subprocess
import sys
import tempfile
import zipfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import IO, NamedTuple
from urllib.parse import urlparse
from urllib.request import url2pathname

import httpx
from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.aircraft.aliases import write_aliases
from apps.aircraft.models import (
    Aircraft,
    AircraftType,
    AircraftTypeAlias,
    RegistrantType,
    Registration,
    RegistrationStatus,
    RegistryImport,
    normalize_n_number,
)
from apps.aircraft.naming import display_make, display_model

log = logging.getLogger(__name__)

#: The fixture cut from one real download: what the seed, the tests, and the
#: end-to-end run import.
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "faa"

#: The aircraft reference file and the master file, as the zip names them.
REFERENCE_FILE = "ACFTREF.txt"
MASTER_FILE = "MASTER.txt"

#: The reference columns the import reads.
REFERENCE_COLUMNS: tuple[str, ...] = ("CODE", "MFR", "MODEL", "NO-ENG", "NO-SEATS")

#: The master columns the import reads.  The address columns are never read.
MASTER_COLUMNS: tuple[str, ...] = (
    "N-NUMBER",
    "MFR MDL CODE",
    "YEAR MFR",
    "TYPE REGISTRANT",
    "NAME",
    "STATUS CODE",
    "CERT ISSUE DATE",
    "EXPIRATION DATE",
)

#: How many rows each upsert writes at once.
BATCH_SIZE = 5_000

#: How long the download may take, in seconds.
DOWNLOAD_TIMEOUT_SECONDS = 600

#: How the download introduces itself.
USER_AGENT = "CalDART registry import"

#: The error a run started from the System screen is closed with once it is older than
#: ``REGISTRY_IMPORT_STALE_MINUTES`` without finishing.
DID_NOT_FINISH = "Did not finish."

#: The answer to a second Run now while one import is under way.
ALREADY_RUNNING = "An import is already running."

#: The error a Run now row is closed with when the subprocess itself fails to start.
COULD_NOT_START = "Could not start the import."

#: Sets the registry import's advisory lock apart from every other one on the database.
IMPORT_LOCK_KEY = 318_000_318

#: The ``TYPE REGISTRANT`` codes; a blank or any other code is ``unknown``.
REGISTRANT_TYPES: dict[str, str] = {
    "1": RegistrantType.INDIVIDUAL,
    "2": RegistrantType.PARTNERSHIP,
    "3": RegistrantType.CORPORATION,
    "4": RegistrantType.CO_OWNED,
    "5": RegistrantType.GOVERNMENT,
    "7": RegistrantType.LLC,
    "8": RegistrantType.NON_CITIZEN_CORPORATION,
    "9": RegistrantType.NON_CITIZEN_CO_OWNED,
}

#: The ``STATUS CODE`` values that are not ``other``: a valid registration (``V``, a
#: manufacturer's dealer certificate ``M``, a trainee's ``T``); a pending one (``R`` and
#: the N-numbers assigned but not yet registered); one revoked or deemed invalid; and
#: one expired.  Sale reported, renewal notices, reserved N-numbers, and the rest are
#: ``other``.
STATUSES: dict[str, str] = {
    **dict.fromkeys(("V", "M", "T"), RegistrationStatus.VALID),
    **dict.fromkeys(("R", "2", "3", "4", "10", "11", "12", "19"), RegistrationStatus.PENDING),
    **dict.fromkeys(("E", "W", "9", "21", "22"), RegistrationStatus.REVOKED),
    **dict.fromkeys(("D", "13", "16", "23", "27", "29"), RegistrationStatus.EXPIRED),
}

#: The length of a registry date, ``YYYYMMDD``.
DATE_LENGTH = 8


class RegistryFormatError(ValueError):
    """A source that is not the registry: a file or a column is missing."""


class ImportAlreadyRunningError(Exception):
    """Run now was pressed while an import started from the System screen still runs."""


class TypeRow(NamedTuple):
    """One aircraft reference row: the code, the FAA's names, seats, and engines."""

    faa_code: str
    faa_make: str
    faa_model: str
    seats: int | None
    engines: int | None


class RegistrationRow(NamedTuple):
    """One master row, reduced to what the registry keeps."""

    n_number: str
    faa_code: str
    year: int | None
    registrant_name: str
    registrant_type: str
    status: str
    certificate_issued_on: date | None
    expires_on: date | None


class ImportCounts(NamedTuple):
    """What one import wrote."""

    types_written: int
    registrations_written: int
    types_folded: int


#: Opens one file of a source by name, as bytes.
type Opener = Callable[[str], IO[bytes]]


# -- the codes ------------------------------------------------------------------


def registrant_type_for(code: str) -> str:
    """The registrant type the FAA's ``TYPE REGISTRANT`` code means, else ``unknown``."""
    return REGISTRANT_TYPES.get(code.strip(), RegistrantType.UNKNOWN)


def status_for(code: str) -> str:
    """The registration status the FAA's ``STATUS CODE`` means, else ``other``."""
    return STATUSES.get(code.strip(), RegistrationStatus.OTHER)


def parse_date(value: str) -> date | None:
    """The date a registry ``YYYYMMDD`` value names; ``None`` when blank or malformed."""
    text = value.strip()
    if len(text) != DATE_LENGTH or not text.isdigit():
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _parse_int(value: str) -> int | None:
    """The whole number ``value`` holds (``"004"`` is 4); ``None`` when it holds none."""
    text = value.strip()
    return int(text) if text.isdigit() else None


# -- the parser ------------------------------------------------------------------


def _rows(stream: IO[bytes], name: str, columns: tuple[str, ...]) -> Iterator[dict[str, str]]:
    """Each data row of the registry file ``name`` in ``stream``, as stripped ``columns``.

    The file is read as UTF-8 with or without a byte-order mark, and ``stream`` is
    closed once the rows are read.  Header names are
    stripped before they are matched, and a blank row is skipped.  Raises
    :class:`RegistryFormatError` naming the first of ``columns`` the header lacks.
    """
    with io.TextIOWrapper(stream, encoding="utf-8-sig", errors="replace") as text:
        reader = csv.reader(text)
        header = [cell.strip() for cell in next(reader, [])]
        for column in columns:
            if column not in header:
                raise RegistryFormatError(f"{name} has no {column} column.")
        positions = {column: header.index(column) for column in columns}
        for row in reader:
            if not any(cell.strip() for cell in row):
                continue
            yield {
                column: row[index].strip() if index < len(row) else ""
                for column, index in positions.items()
            }


def read_types(stream: IO[bytes]) -> Iterator[TypeRow]:
    """Each row of an ``ACFTREF.txt`` in ``stream``, as a :class:`TypeRow`.

    Seats and engines are ``None`` when the row leaves them blank.
    """
    for row in _rows(stream, REFERENCE_FILE, REFERENCE_COLUMNS):
        yield TypeRow(
            faa_code=row["CODE"],
            faa_make=row["MFR"],
            faa_model=row["MODEL"],
            seats=_parse_int(row["NO-SEATS"]),
            engines=_parse_int(row["NO-ENG"]),
        )


def read_registrations(stream: IO[bytes]) -> Iterator[RegistrationRow]:
    """Each row of a ``MASTER.txt`` in ``stream``, as a :class:`RegistrationRow`.

    The N-number gains its leading ``N`` (``172SP`` is ``N172SP``); the registrant type
    and status are mapped by :func:`registrant_type_for` and :func:`status_for`; the
    year and the two dates are ``None`` when blank.  A row without an N-number is
    skipped.
    """
    for row in _rows(stream, MASTER_FILE, MASTER_COLUMNS):
        n_number = normalize_n_number(row["N-NUMBER"])
        if not n_number:
            continue
        yield RegistrationRow(
            n_number=n_number,
            faa_code=row["MFR MDL CODE"],
            year=_parse_int(row["YEAR MFR"]),
            registrant_name=row["NAME"],
            registrant_type=registrant_type_for(row["TYPE REGISTRANT"]),
            status=status_for(row["STATUS CODE"]),
            certificate_issued_on=parse_date(row["CERT ISSUE DATE"]),
            expires_on=parse_date(row["EXPIRATION DATE"]),
        )


# -- the source ------------------------------------------------------------------


@contextmanager
def _opened_source(source: str) -> Iterator[Opener]:
    """An opener for the registry files ``source`` holds, open for the ``with`` block.

    ``source`` is an ``http`` or ``https`` URL of the zip, which is downloaded to a
    temporary file first; a ``file://`` URL or a path of a local zip; or a ``file://``
    URL or a path of a directory holding the two files.  Raises
    :class:`RegistryFormatError` when a local ``source`` is neither.
    """
    parsed = urlparse(source)
    if parsed.scheme in ("http", "https"):
        with tempfile.TemporaryDirectory() as scratch:
            archive_path = Path(scratch) / "registry.zip"
            _download(source, archive_path)
            with zipfile.ZipFile(archive_path) as archive:
                yield _zip_opener(archive, source)
        return
    path = Path(url2pathname(parsed.path)) if parsed.scheme == "file" else Path(source)
    if path.is_dir():
        yield _directory_opener(path, source)
        return
    if path.is_file() and zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            yield _zip_opener(archive, source)
        return
    raise RegistryFormatError(f"{source} is neither a directory nor a zip of the registry.")


def _download(url: str, target: Path) -> None:
    """Stream the zip at ``url`` into ``target``; raise ``httpx.HTTPError`` on failure."""
    with httpx.stream(
        "GET",
        url,
        timeout=DOWNLOAD_TIMEOUT_SECONDS,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    ) as response:
        response.raise_for_status()
        with target.open("wb") as out:
            for chunk in response.iter_bytes():
                out.write(chunk)


def _directory_opener(directory: Path, source: str) -> Opener:
    """Open a registry file by name from ``directory``."""

    def open_file(name: str) -> IO[bytes]:
        """Open ``name``, or raise :class:`RegistryFormatError` when it is absent."""
        path = directory / name
        if not path.is_file():
            raise RegistryFormatError(f"{name} is not in {source}.")
        return path.open("rb")

    return open_file


def _zip_opener(archive: zipfile.ZipFile, source: str) -> Opener:
    """Open a registry file by name from ``archive``, matching the name in any case."""
    members = {Path(member).name.upper(): member for member in archive.namelist()}

    def open_file(name: str) -> IO[bytes]:
        """Open ``name``, or raise :class:`RegistryFormatError` when it is absent."""
        if name.upper() not in members:
            raise RegistryFormatError(f"{name} is not in {source}.")
        return archive.open(members[name.upper()])

    return open_file


# -- importing -------------------------------------------------------------------


def import_registry(
    source: str, *, types_only: bool = False, run: RegistryImport | None = None
) -> RegistryImport:
    """Import the registry at ``source`` and return the ``RegistryImport`` row for it.

    ``run`` is the row to fill in (the one the System screen wrote); without it, one is
    created under the same advisory lock :func:`start_import` takes, refusing with
    :class:`ImportAlreadyRunningError` while another import runs, so the nightly timer
    and Run now can never overlap.  Its ``source`` is set to ``source``.  The source is
    opened -- downloaded first when it names an ``http`` or ``https`` URL -- before
    anything commits, so a slow download holds no transaction open; the write phase
    that follows commits together: the aircraft types from the reference file,
    upserted by ``faa_code`` and never deleted; the hand-added types the FAA now lists,
    folded into the FAA's entry; unless ``types_only``, the registrations from the
    master file, upserted by N-number in batches of :data:`BATCH_SIZE`, with every
    registration the file no longer holds deleted; and the aliases.  On success the row
    is finished, ``ok``, and carries the counts.  On any failure nothing is written,
    the row is finished, not ``ok``, with the error, and the exception is raised again.
    """
    if run is None:
        run = _claim_unattended_run(source)
    else:
        run.source = source
        run.save(update_fields=["source"])
    try:
        counts = _import(source, types_only=types_only)
    except Exception as exc:
        run.ok = False
        run.error = str(exc) or type(exc).__name__
        run.finished_at = timezone.now()
        run.save(update_fields=["ok", "error", "finished_at"])
        log.error("Registry import %s failed: %s", run.pk, run.error)
        raise
    run.types_written, run.registrations_written, run.types_folded = counts
    run.ok = True
    run.error = ""
    run.finished_at = timezone.now()
    run.save()
    log.info(
        "Registry import %s wrote %d types and %d registrations, and folded %d hand-added types.",
        run.pk,
        *counts,
    )
    return run


def _claim_unattended_run(source: str) -> RegistryImport:
    """Create the run row for a call with no ``run`` of its own, from ``source``.

    Guards the path :func:`start_import` does not: a call with no pre-written row, as
    the nightly timer makes through ``manage.py import_faa_registry`` without
    ``--import-id``.  Takes the same advisory lock :func:`start_import` takes before
    checking :func:`is_running`, so the timer and a Run now press can never both start
    an import at once; raises :class:`ImportAlreadyRunningError` when one already runs.
    """
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [IMPORT_LOCK_KEY])
        if is_running():
            raise ImportAlreadyRunningError(ALREADY_RUNNING)
        return RegistryImport.objects.create(source=source)


def _import(source: str, *, types_only: bool) -> ImportCounts:
    """Open ``source``, then write the types, the fold, the registrations, and aliases.

    The source opens first -- performing the download for a URL source -- and only the
    writes that follow run inside a transaction, so a slow or failed download never
    holds one open.
    """
    with _opened_source(source) as open_file, transaction.atomic():
        with open_file(REFERENCE_FILE) as stream:
            types_written = _write_types(read_types(stream))
        folded = _fold_custom_types()
        registrations_written = 0
        if not types_only:
            with open_file(MASTER_FILE) as stream:
                registrations_written = _write_registrations(read_registrations(stream))
        write_aliases()
    return ImportCounts(types_written, registrations_written, folded)


def _write_types(rows: Iterator[TypeRow]) -> int:
    """Upsert an FAA ``AircraftType`` for each of ``rows``; return how many were written.

    A code repeated in the file keeps its last row.
    """
    entries: dict[str, AircraftType] = {}
    for row in rows:
        entries[row.faa_code] = AircraftType(
            faa_code=row.faa_code,
            faa_make=row.faa_make[:120],
            faa_model=row.faa_model[:60],
            make=display_make(row.faa_make, row.faa_model)[:120],
            model=display_model(row.faa_model)[:60],
            seats=row.seats,
            engines=row.engines,
            is_custom=False,
        )
    AircraftType.objects.bulk_create(
        list(entries.values()),
        batch_size=BATCH_SIZE,
        update_conflicts=True,
        unique_fields=["faa_code"],
        update_fields=["faa_make", "faa_model", "make", "model", "seats", "engines", "is_custom"],
    )
    return len(entries)


def _fold_custom_types() -> int:
    """Fold each hand-added type the FAA now lists into the FAA's entry; return how many.

    A custom type is folded when an FAA type has the same display make and model,
    compared case-insensitively (the first by ``faa_code`` when several do): its
    aircraft and aliases are pointed at the FAA type, and it is deleted.
    """
    folded = 0
    for custom in AircraftType.objects.filter(is_custom=True):
        twin = (
            AircraftType.objects.filter(
                is_custom=False, make__iexact=custom.make, model__iexact=custom.model
            )
            .order_by("faa_code")
            .first()
        )
        if twin is None:
            continue
        Aircraft.objects.filter(type=custom).update(type=twin)
        AircraftTypeAlias.objects.filter(type=custom).update(type=twin)
        Registration.objects.filter(type=custom).update(type=twin)
        custom.delete()
        folded += 1
    return folded


def _write_registrations(rows: Iterator[RegistrationRow]) -> int:
    """Upsert a ``Registration`` for each of ``rows``; return how many were written.

    A row whose type code the reference file does not hold is skipped and counted in
    the log.  Every registration the rows do not name is deleted afterwards.
    """
    type_ids = dict(AircraftType.objects.filter(is_custom=False).values_list("faa_code", "id"))
    stamp = timezone.now()
    written = skipped = 0
    batch: dict[str, Registration] = {}
    for row in rows:
        if row.faa_code not in type_ids:
            skipped += 1
            continue
        batch[row.n_number] = Registration(
            n_number=row.n_number,
            type_id=type_ids[row.faa_code],
            year=row.year,
            registrant_name=row.registrant_name[:160],
            registrant_type=row.registrant_type,
            status=row.status,
            certificate_issued_on=row.certificate_issued_on,
            expires_on=row.expires_on,
            imported_at=stamp,
        )
        if len(batch) >= BATCH_SIZE:
            written += _flush_registrations(batch)
    written += _flush_registrations(batch)
    Registration.objects.exclude(imported_at=stamp).delete()
    if skipped > 0:
        log.warning("Registry import skipped %d registrations naming no known type.", skipped)
    return written


def _flush_registrations(batch: dict[str, Registration]) -> int:
    """Upsert ``batch``'s registrations by N-number, empty it, and return the count."""
    count = len(batch)
    Registration.objects.bulk_create(
        list(batch.values()),
        update_conflicts=True,
        unique_fields=["n_number"],
        update_fields=[
            "type",
            "year",
            "registrant_name",
            "registrant_type",
            "status",
            "certificate_issued_on",
            "expires_on",
            "imported_at",
        ],
    )
    batch.clear()
    return count


# -- the registry's state, and Run now ------------------------------------------------


def _stale_before() -> datetime:
    """The start time before which an unfinished import counts as stale."""
    return timezone.now() - timedelta(minutes=settings.REGISTRY_IMPORT_STALE_MINUTES)


def is_running() -> bool:
    """True while an import has started, not finished, and is not yet stale."""
    return RegistryImport.objects.filter(
        finished_at__isnull=True, started_at__gte=_stale_before()
    ).exists()


def as_of() -> datetime | None:
    """When the newest successful import finished: the date the registry is as of.

    ``None`` before any import has succeeded, and also whenever the registrations table
    is empty whatever the import log says: a backup leaves the registrations out, so
    after a restore the registry reads as not imported until the next import refills it.
    """
    if not Registration.objects.exists():
        return None
    newest = (
        RegistryImport.objects.filter(ok=True, finished_at__isnull=False)
        .order_by("-finished_at")
        .first()
    )
    return None if newest is None else newest.finished_at


def start_import(actor: User) -> RegistryImport:
    """Start ``import_faa_registry`` in its own process on behalf of ``actor``.

    Writes the ``RegistryImport`` row (source ``FAA_REGISTRY_URL``, started by
    ``actor``, not finished) and hands its id to :func:`launch_import`.  Raises
    :class:`ImportAlreadyRunningError` while another import is running; an unfinished
    import older than ``REGISTRY_IMPORT_STALE_MINUTES`` is closed as failed with the
    error :data:`DID_NOT_FINISH` instead, and a fresh one starts.  Two presses at once
    are serialized by an advisory lock, so only one of them starts an import.  When
    ``launch_import`` itself fails to start the subprocess (an ``OSError``), the row is
    closed at once as failed with :data:`COULD_NOT_START` instead of sitting unfinished
    until the stale timeout, and the exception is raised again.
    """
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [IMPORT_LOCK_KEY])
        if is_running():
            raise ImportAlreadyRunningError(ALREADY_RUNNING)
        RegistryImport.objects.filter(finished_at__isnull=True).update(
            ok=False, error=DID_NOT_FINISH, finished_at=timezone.now()
        )
        run = RegistryImport.objects.create(source=settings.FAA_REGISTRY_URL, started_by=actor)
    try:
        launch_import(run)
    except OSError:
        run.ok = False
        run.error = COULD_NOT_START
        run.finished_at = timezone.now()
        run.save(update_fields=["ok", "error", "finished_at"])
        log.error("Registry import %s could not start: %s", run.pk, COULD_NOT_START)
        raise
    return run


def launch_import(run: RegistryImport) -> None:
    """Start ``manage.py import_faa_registry --import-id <run>`` and return at once.

    The command runs in its own session under the server's Python, so it outlives the
    request, and writes to the server's own output.  The child is never waited on: it
    is a child of the web service, not of the request, so it dies if the service
    restarts mid-import, and either way its own exit is not reaped here.  When it
    finishes normally, or is killed, the row it was given is the only trace of it; the
    stale rule (:data:`DID_NOT_FINISH`) is what notices a child that never finishes.
    Raises ``OSError`` when the subprocess itself cannot be started.
    """
    manage = Path(settings.BASE_DIR) / "manage.py"
    subprocess.Popen(  # noqa: S603 - the server's own Python running the project's manage.py
        [sys.executable, str(manage), "import_faa_registry", "--import-id", str(run.pk)],
        start_new_session=True,
    )
