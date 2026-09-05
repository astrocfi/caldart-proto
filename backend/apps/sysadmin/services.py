"""Backup, restore and health helpers (PLAN §4.7).

``feat/ops`` owns this app and wraps these in the ``/system/...`` API; the
Makefile needs them from day one, so the commands live here already.
"""

from __future__ import annotations

import gzip
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from django.db import connection
from django.utils import timezone

BACKUP_SUFFIX = ".sql.gz"


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


def restore_backup(path: Path) -> None:
    """Restore a gzipped dump over the current database."""
    if not path.is_file():
        raise BackupError(f"No such backup: {path}")

    argv = _pg_command("psql")
    if argv is None:
        raise BackupError("Neither psql nor docker is available.")

    opener = gzip.open if path.name.endswith(".gz") else open
    with opener(path, "rb") as handle:
        sql = handle.read()

    result = _run_pg([*argv, "--quiet", "--dbname", _dbname_url_for(argv)], input=sql)
    if result.returncode != 0:
        raise BackupError(result.stderr.decode(errors="replace").strip() or "psql failed")


def drop_schema() -> None:
    """``DROP SCHEMA public CASCADE; CREATE SCHEMA public;`` (PLAN §4.7)."""
    with connection.cursor() as cursor:
        cursor.execute("DROP SCHEMA public CASCADE;")
        cursor.execute("CREATE SCHEMA public;")


def pending_migrations() -> list[tuple[str, str]]:
    """Migrations that exist on disk but are not applied."""
    from django.db.migrations.executor import MigrationExecutor

    executor = MigrationExecutor(connection)
    targets = executor.loader.graph.leaf_nodes()
    return [migration.key for migration, _backwards in executor.migration_plan(targets)]


def health() -> dict:
    """The payload behind ``GET /system/health`` (PLAN §6.9)."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        db_status = "ok"
    except Exception as exc:  # pragma: no cover - only on a broken database
        db_status = f"error: {exc}"

    usage = shutil.disk_usage(settings.REPO_ROOT)
    backups = list_backups()

    return {
        "db": db_status,
        "pending_migrations": len(pending_migrations()) if db_status == "ok" else -1,
        "disk_free_mb": usage.free // (1024 * 1024),
        "last_backup": backups[0].created_at.isoformat() if backups else None,
        "version": settings.CALDART_VERSION,
        "debug": settings.DEBUG,
    }
