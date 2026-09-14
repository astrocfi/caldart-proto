"""Backup, restore and health helpers.

The ``/system/...`` API wraps these, and so do the ``db_backup``,
``db_restore``, ``db_reset`` and ``health`` management commands.
"""

from __future__ import annotations

import gzip
import re
import shutil
import subprocess
import tomllib
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from django.db import connection
from django.utils import timezone

BACKUP_SUFFIX = ".sql.gz"

#: A backup file name we are willing to open.  No directory separators, no
#: leading dot, and the suffix we write — which is what makes
#: ``GET /system/backups/<name>/download`` safe against path traversal.
BACKUP_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.sql\.gz$")


class BackupError(RuntimeError):
    """Raised when pg_dump or psql cannot be reached, or fails."""


@dataclass(frozen=True)
class BackupFile:
    name: str
    path: Path
    size_bytes: int
    created_at: datetime

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "size_bytes": self.size_bytes,
            "created_at": self.created_at.isoformat(),
        }


def backup_dir() -> Path:
    path = Path(settings.BACKUP_DIR)
    if not path.is_absolute():
        path = settings.REPO_ROOT / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def database_url() -> str:
    """The DATABASE_URL for the configured default connection."""
    db = settings.DATABASES["default"]
    user = db.get("USER") or "caldart"
    password = db.get("PASSWORD") or ""
    host = db.get("HOST") or "localhost"
    port = db.get("PORT") or 5432
    name = db.get("NAME") or "caldart"
    return f"postgres://{user}:{password}@{host}:{port}/{name}"


def _pg_command(tool: str) -> list[str] | None:
    """The argv prefix that runs ``tool``, locally or inside docker compose.

    ``DB_BACKUP_VIA_DOCKER`` forces the compose container, which is what a
    machine with no ``postgresql-client`` installed needs.  Otherwise prefer
    the local binary and fall back to the container.
    """
    in_container = ["docker", "compose", "exec", "-T", "db", tool]
    has_docker = shutil.which("docker") is not None

    if settings.DB_BACKUP_VIA_DOCKER and has_docker:
        return in_container
    if shutil.which(tool):
        return [tool]
    return in_container if has_docker else None


def _run_pg(argv: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a pg tool from the repository root so compose finds its file."""
    return subprocess.run(  # noqa: S603 - argv is built from settings, not user input
        argv,
        cwd=settings.REPO_ROOT,
        capture_output=True,
        check=False,
        **kwargs,
    )


def _dbname_url_for(argv: list[str]) -> str:
    """The connection URL to hand the tool, rewritten for in-container runs."""
    url = database_url()
    if argv[0] != "docker":
        return url
    # Inside the compose network the server listens on localhost:5432.
    parsed = urlparse(url)
    return f"postgres://{parsed.username}:{parsed.password}@localhost:5432{parsed.path}"


def _backup_file(path: Path) -> BackupFile:
    stat = path.stat()
    return BackupFile(
        name=path.name,
        path=path,
        size_bytes=stat.st_size,
        created_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.get_current_timezone()),
    )


def list_backups() -> list[BackupFile]:
    """Existing dumps, newest first."""
    files = [_backup_file(path) for path in backup_dir().glob(f"*{BACKUP_SUFFIX}")]
    return sorted(files, key=lambda f: f.created_at, reverse=True)


def resolve_backup(name: str) -> Path:
    """The path of the dump called ``name`` inside ``BACKUP_DIR``.

    Rejects anything that is not a plain ``*.sql.gz`` file name, and then
    re-checks the resolved path really is a direct child of the backup
    directory, so ``../``, an absolute path or a symlink out of the directory
    can never be downloaded.
    """
    if not BACKUP_NAME_RE.fullmatch(name):
        raise BackupError(f"Not a backup file name: {name!r}")

    root = backup_dir().resolve()
    path = (root / name).resolve()
    if path.parent != root:
        raise BackupError(f"Not a backup file name: {name!r}")
    if not path.is_file():
        raise BackupError(f"No such backup: {name}")
    return path


def create_backup(name: str | None = None) -> BackupFile:
    """Dump the database to ``backups/caldart-<timestamp>.sql.gz``."""
    argv = _pg_command("pg_dump")
    if argv is None:
        raise BackupError(
            "Neither pg_dump nor docker is available; install postgresql-client "
            "or start the compose stack."
        )

    stamp = timezone.localtime().strftime("%Y%m%d-%H%M%S")
    target = backup_dir() / (name or f"caldart-{stamp}{BACKUP_SUFFIX}")

    result = _run_pg([*argv, "--no-owner", "--no-privileges", "--dbname", _dbname_url_for(argv)])
    if result.returncode != 0:
        raise BackupError(result.stderr.decode(errors="replace").strip() or "pg_dump failed")

    with gzip.open(target, "wb") as handle:
        handle.write(result.stdout)

    return _backup_file(target)


def restore_backup(path: Path, *, drop_first: bool = True) -> None:
    """Restore a gzipped dump over the current database.

    ``pg_dump`` writes ``CREATE TABLE`` without ``DROP``, so the schema has to
    go first or every statement collides with what is already there.
    ``drop_first=False`` is for restoring into an empty database.
    """
    if not path.is_file():
        raise BackupError(f"No such backup: {path}")

    argv = _pg_command("psql")
    if argv is None:
        raise BackupError("Neither psql nor docker is available.")

    opener = gzip.open if path.name.endswith(".gz") else open
    with opener(path, "rb") as handle:
        sql = handle.read()

    if drop_first:
        drop_schema()

    result = _run_pg([*argv, "--quiet", "--dbname", _dbname_url_for(argv)], input=sql)
    if result.returncode != 0:
        raise BackupError(result.stderr.decode(errors="replace").strip() or "psql failed")


def drop_schema() -> None:
    """``DROP SCHEMA public CASCADE; CREATE SCHEMA public;``."""
    with connection.cursor() as cursor:
        cursor.execute("DROP SCHEMA public CASCADE;")
        cursor.execute("CREATE SCHEMA public;")


def pending_migrations() -> list[tuple[str, str]]:
    """Migrations that exist on disk but are not applied."""
    from django.db.migrations.executor import MigrationExecutor

    executor = MigrationExecutor(connection)
    targets = executor.loader.graph.leaf_nodes()
    return [migration.key for migration, _backwards in executor.migration_plan(targets)]


@lru_cache(maxsize=1)
def app_version() -> str:
    """``[project] version`` from ``pyproject.toml``.

    The deployed tree always has the file next to it, so the version reported by
    ``/system/health`` is the one that was actually installed.  Falls back to
    ``settings.CALDART_VERSION`` if the file is missing or unreadable.
    """
    path = Path(settings.REPO_ROOT) / "pyproject.toml"
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)["project"]["version"]
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        return settings.CALDART_VERSION


def health() -> dict:
    """The payload behind ``GET /system/health``.

    Disk space is measured on ``BACKUP_DIR``: that is the filesystem that fills
    up first, and the one that has to have room for the next ``pg_dump``.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        db_status = "ok"
    except Exception as exc:  # pragma: no cover - only on a broken database
        db_status = f"error: {exc}"

    usage = shutil.disk_usage(backup_dir())
    backups = list_backups()

    return {
        "db": db_status,
        "pending_migrations": len(pending_migrations()) if db_status == "ok" else -1,
        "disk_free_mb": usage.free // (1024 * 1024),
        "last_backup": backups[0].created_at.isoformat() if backups else None,
        "version": app_version(),
        "debug": settings.DEBUG,
    }
