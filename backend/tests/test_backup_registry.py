"""Backups leave the FAA registry's registrations out, and the registry date follows.

``docs/developer/backup-restore.rst`` is the contract: every dump carries the
``aircraft_registration`` table's schema but none of its rows, while the aircraft types,
their aliases, and the import log stay in.  ``docs/developer/aircraft-registry.rst``
says the registry reads as not imported while the registrations table is empty.
"""

from __future__ import annotations

import gzip
import shutil
from io import StringIO
from pathlib import Path
from typing import IO, Any

import pytest
from django.core.management import call_command
from django.utils import timezone
from pytest_django import Settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.aircraft import registry
from apps.aircraft.models import Registration, RegistryImport
from apps.sysadmin import services
from tests.factories import AircraftTypeFactory

pytestmark = pytest.mark.django_db

#: The ``pg_dump`` option that keeps the registrations table's rows out of a dump.
EXCLUSION = "--exclude-table-data=aircraft_registration"

BACKUPS_URL = "/api/v1/system/backups"
REGISTRY_URL = "/api/v1/aircraft/registry"

#: The two forms ``_pg_command`` builds: the local binary, and the compose container.
LOCAL_PREFIX = ["pg_dump"]
COMPOSE_PREFIX = ["docker", "compose", "exec", "-T", "-e", "PGPASSWORD", "db", "pg_dump"]


@pytest.fixture
def dump_argvs(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Record the argv of every pg tool the backup service runs instead of running it."""
    argvs: list[list[str]] = []

    def fake_stream(
        argv: list[str],
        tool: str,
        *,
        source: IO[bytes] | None = None,
        target: IO[bytes] | None = None,
    ) -> None:
        argvs.append(argv)
        if target is not None:
            target.write(b"-- dump body\n")

    monkeypatch.setattr(services, "_stream_pg", fake_stream)
    return argvs


@pytest.fixture
def local_pg_dump(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    """A machine with ``pg_dump`` installed and ``DB_BACKUP_VIA_DOCKER`` off."""
    settings.DB_BACKUP_VIA_DOCKER = False
    monkeypatch.setattr(shutil, "which", lambda tool: f"/usr/bin/{tool}")


# -- the argv ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("via_docker", "prefix"),
    [(False, LOCAL_PREFIX), (True, COMPOSE_PREFIX)],
    ids=["local", "compose"],
)
def test_the_dump_leaves_the_registration_rows_out(
    backup_dir: Path,
    dump_argvs: list[list[str]],
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    via_docker: bool,
    prefix: list[str],
) -> None:
    """Both forms of ``pg_dump`` carry ``--exclude-table-data`` for the registrations."""
    settings.DB_BACKUP_VIA_DOCKER = via_docker
    monkeypatch.setattr(shutil, "which", lambda tool: f"/usr/bin/{tool}")

    services.create_backup()

    assert dump_argvs[0] == [
        *prefix,
        "--no-owner",
        "--no-privileges",
        EXCLUSION,
        "--dbname",
        dump_argvs[0][-1],
    ]


def test_the_create_backup_button_leaves_the_registration_rows_out(
    backup_dir: Path,
    dump_argvs: list[list[str]],
    local_pg_dump: None,
    api_client: APIClient,
    system_admin: User,
) -> None:
    """``POST /system/backups``, behind **Create backup**, runs the same exclusion."""
    api_client.force_login(system_admin)

    response = api_client.post(BACKUPS_URL)

    assert response.status_code == 201
    assert EXCLUSION in dump_argvs[0]


def test_the_db_backup_command_leaves_the_registration_rows_out(
    backup_dir: Path, dump_argvs: list[list[str]], local_pg_dump: None
) -> None:
    """``manage.py db_backup``, which the backup timer runs, runs the same exclusion."""
    call_command("db_backup", stdout=StringIO())

    assert EXCLUSION in dump_argvs[0]


# -- a real dump ------------------------------------------------------------------------


@pytest.fixture
def real_dump(backup_dir: Path, settings: Settings) -> str:
    """The text of a real ``db_backup`` dump of a database holding one registration.

    The rows are committed, so ``pg_dump``'s own connection sees them.  The local
    binary is used when it is installed, the compose container otherwise.
    """
    settings.DB_BACKUP_VIA_DOCKER = False
    Registration.objects.create(n_number="N172SP", type=AircraftTypeFactory())

    call_command("db_backup", "--name", "registry.sql.gz", stdout=StringIO())

    with gzip.open(backup_dir / "registry.sql.gz", "rt") as handle:
        return handle.read()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    ("statement", "expected"),
    [
        ("CREATE TABLE public.aircraft_registration ", True),
        ("COPY public.aircraft_registration ", False),
        ("COPY public.aircraft_aircrafttype ", True),
    ],
    ids=["registration-schema", "no-registration-rows", "type-rows"],
)
def test_a_real_dump_keeps_the_registration_schema_and_the_types(
    real_dump: str, statement: str, expected: bool
) -> None:
    """The dump creates the registrations table empty and still copies the types."""
    assert (statement in real_dump) is expected


# -- the registry date ------------------------------------------------------------------


@pytest.fixture
def emptied_registry() -> RegistryImport:
    """A successful import whose registrations are gone, as after a restore."""
    finished = RegistryImport.objects.create(ok=True, finished_at=timezone.now())
    Registration.objects.all().delete()
    return finished


def test_as_of_is_none_while_the_registrations_table_is_empty(
    emptied_registry: RegistryImport,
) -> None:
    """A successful import in the log is no date when its rows are gone."""
    assert registry.as_of() is None


def test_as_of_is_the_import_date_once_the_table_holds_a_registration(
    emptied_registry: RegistryImport,
) -> None:
    """The date returns as soon as the table holds a registration again."""
    Registration.objects.create(n_number="N172SP", type=AircraftTypeFactory())

    assert registry.as_of() == emptied_registry.finished_at


def test_the_status_reads_not_imported_after_a_restore(
    emptied_registry: RegistryImport, api_client: APIClient, member: User
) -> None:
    """``GET /aircraft/registry`` answers ``as_of: null`` while the table is empty."""
    api_client.force_login(member)

    body: dict[str, Any] = api_client.get(REGISTRY_URL).json()

    assert body["as_of"] is None
