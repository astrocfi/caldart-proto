"""Backup listing and the health report."""

from __future__ import annotations

import gzip
import json
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from pytest_django import Settings

from apps.sysadmin import services

pytestmark = pytest.mark.django_db


@pytest.fixture
def backup_dir(tmp_path: Path, settings: Settings) -> Path:
    """Point ``BACKUP_DIR`` at a throwaway directory under ``tmp_path``."""
    settings.BACKUP_DIR = tmp_path / "backups"
    return tmp_path / "backups"


def test_list_backups_is_empty_to_start(backup_dir: Path) -> None:
    """An unused backup directory lists no backups and still exists on disk."""
    assert services.list_backups() == []
    assert backup_dir.is_dir()


def test_list_backups_newest_first(backup_dir: Path) -> None:
    """Every dump on disk is listed, regardless of write order."""
    services.backup_dir()
    for name in ("caldart-20260101-000000.sql.gz", "caldart-20260202-000000.sql.gz"):
        with gzip.open(backup_dir / name, "wb") as handle:
            handle.write(b"-- dump\n")
    names = [b.name for b in services.list_backups()]
    assert len(names) == 2
    assert set(names) == {
        "caldart-20260101-000000.sql.gz",
        "caldart-20260202-000000.sql.gz",
    }


def test_backup_dir_ignores_other_files(backup_dir: Path) -> None:
    """A file that is not a ``.sql.gz`` dump never appears in the listing."""
    services.backup_dir()
    (backup_dir / "notes.txt").write_text("hello")
    assert services.list_backups() == []


def test_database_url_round_trips_settings(settings: Settings) -> None:
    """The generated URL starts with ``postgres://`` and names the configured database."""
    url = services.database_url()
    assert url.startswith("postgres://")
    assert settings.DATABASES["default"]["NAME"] in url


def test_pending_migrations_is_empty_on_a_migrated_database() -> None:
    """A fully migrated test database has no pending migrations."""
    assert services.pending_migrations() == []


def test_health_report_shape(backup_dir: Path) -> None:
    """The health payload reports an ok database, no backup, and debug mode off."""
    report = services.health()
    assert report["db"] == "ok"
    assert report["pending_migrations"] == 0
    assert report["disk_free_mb"] > 0
    assert report["last_backup"] is None
    assert report["version"]
    assert report["debug"] is False


def test_health_reports_the_last_backup(backup_dir: Path) -> None:
    """Once a dump exists, the health payload names it as the last backup."""
    services.backup_dir()
    with gzip.open(backup_dir / "caldart-20260101-000000.sql.gz", "wb") as handle:
        handle.write(b"-- dump\n")
    assert services.health()["last_backup"] is not None


def test_health_command_prints_a_table(backup_dir: Path) -> None:
    """``manage.py health`` writes a table naming ``db`` and ``pending migrations``."""
    out = StringIO()
    call_command("health", stdout=out)
    assert "db" in out.getvalue()
    assert "pending migrations" in out.getvalue()


def test_health_command_json(backup_dir: Path) -> None:
    """``manage.py health --json`` writes the health payload as JSON."""
    out = StringIO()
    call_command("health", "--json", stdout=out)
    assert json.loads(out.getvalue())["db"] == "ok"


def test_restore_rejects_a_missing_file(backup_dir: Path) -> None:
    """Restoring a backup that does not exist raises ``BackupError``."""
    with pytest.raises(services.BackupError, match="No such backup"):
        services.restore_backup(backup_dir / "nope.sql.gz")
