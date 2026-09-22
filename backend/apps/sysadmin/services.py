"""Backup, restore and health helpers.

The ``/system/...`` API wraps these, and so do the ``db_backup``,
``db_restore``, ``db_reset`` and ``health`` management commands.
"""

from __future__ import annotations

import gzip
import os
import re
import shutil
import subprocess
import tomllib
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import quote

from django.conf import settings
from django.db import connection
from django.utils import timezone

from caldart import audit

BACKUP_SUFFIX = ".sql.gz"

#: A backup file name we are willing to open.  No directory separators, no
#: leading dot, and the suffix we write — which is what makes
#: ``GET /system/backups/<name>/download`` safe against path traversal.
BACKUP_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.sql\.gz$")


class BackupError(RuntimeError):
    """Raised when pg_dump or psql cannot be reached, or fails."""


@dataclass(frozen=True)
class BackupFile:
    """One dump on disk: its name, path, size, and modification time."""

    name: str
    path: Path
    size_bytes: int
    created_at: datetime

    def as_dict(self) -> dict[str, Any]:
        """Return ``{name, size_bytes, created_at}``, with ``created_at`` as ISO 8601."""
        return {
            "name": self.name,
            "size_bytes": self.size_bytes,
            "created_at": self.created_at.isoformat(),
        }


def backup_dir() -> Path:
    """The backup directory, creating it if it does not exist.

    ``settings.BACKUP_DIR`` is resolved against ``settings.REPO_ROOT`` when it is
    relative.
    """
    path = Path(settings.BACKUP_DIR)
    if not path.is_absolute():
        path = settings.REPO_ROOT / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def database_password() -> str:
    """The password of the default connection, empty when there is none.

    It reaches ``pg_dump`` and ``psql`` through ``PGPASSWORD`` rather than through
    the connection URL, so it never appears in a command line that ``ps`` or a
    shell history would show.
    """
    password: str = settings.DATABASES["default"].get("PASSWORD") or ""
    return password


def database_url(*, host: str | None = None, port: int | str | None = None) -> str:
    """The connection URL for the configured default connection.

    The user name and the database name are percent-encoded, so a user called
    ``ann marie@caldart`` produces a URL a client can still parse.  The password
    is deliberately absent; see :func:`database_password`.  ``host`` and ``port``
    override the configured ones, which is what an in-container run needs.
    """
    db = settings.DATABASES["default"]
    user = db.get("USER") or "caldart"
    name = db.get("NAME") or "caldart"
    host = host or db.get("HOST") or "localhost"
    port = port or db.get("PORT") or 5432
    return f"postgres://{quote(str(user), safe='')}@{host}:{port}/{quote(str(name), safe='')}"


def _pg_command(tool: str) -> list[str] | None:
    """The argv prefix that runs ``tool``, locally or inside docker compose.

    ``DB_BACKUP_VIA_DOCKER`` forces the compose container, which is what a
    machine with no ``postgresql-client`` installed needs.  Otherwise prefer
    the local binary and fall back to the container.

    The compose form names ``PGPASSWORD`` without a value, so compose copies it
    from our own environment and the password never enters an argument list.
    """
    in_container = ["docker", "compose", "exec", "-T", "-e", "PGPASSWORD", "db", tool]
    has_docker = shutil.which("docker") is not None

    if settings.DB_BACKUP_VIA_DOCKER and has_docker:
        return in_container
    if shutil.which(tool):
        return [tool]
    return in_container if has_docker else None


def _run_pg(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
    """Run a pg tool from the repository root so compose finds its file.

    The password goes into the child's ``PGPASSWORD`` rather than into ``argv``.
    An empty password is left out entirely, so a ``.pgpass`` file or a trust
    connection still works.
    """
    env = dict(os.environ)
    password = database_password()
    if password:
        env["PGPASSWORD"] = password
    return subprocess.run(  # noqa: S603 - argv is built from settings, not user input
        argv,
        cwd=settings.REPO_ROOT,
        capture_output=True,
        check=False,
        env=env,
        **kwargs,
    )


def _dbname_url_for(argv: list[str]) -> str:
    """The connection URL to hand the tool, rewritten for in-container runs."""
    if argv[0] != "docker":
        return database_url()
    # Inside the compose network the server listens on localhost:5432.
    return database_url(host="localhost", port=5432)


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

    A restore only ever runs from the command line, so the audit record it
    writes on success names ``command`` as the actor and the dump's file name.
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

    audit.record(audit.BACKUP_RESTORE, actor=audit.COMMAND_ACTOR, file=audit.safe_slug(path.name))


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
    return [
        (migration.app_label, migration.name)
        for migration, _backwards in executor.migration_plan(targets)
    ]


@lru_cache(maxsize=1)
def app_version() -> str:
    """``[project] version`` from ``pyproject.toml``.

    The deployed tree always has the file next to it, so the version reported by
    ``/system/health`` is the one that was actually installed.  Falls back to
    ``settings.CALDART_VERSION`` when the file is missing, unreadable or not valid
    TOML, when it declares no ``[project] version``, and when that key holds
    anything other than a string.  The result is computed once and cached.
    """
    path = Path(settings.REPO_ROOT) / "pyproject.toml"
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
        version = data["project"]["version"]
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        return settings.CALDART_VERSION
    return version if isinstance(version, str) else settings.CALDART_VERSION


def health() -> dict[str, Any]:
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
