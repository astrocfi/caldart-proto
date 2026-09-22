"""Backup listing and the health report."""

from __future__ import annotations

import gzip
import json
import os
import shlex
import subprocess
from io import StringIO
from pathlib import Path
from typing import Any

import pytest
from django.core.management import call_command
from pytest_django import Settings

from apps.sysadmin import services

pytestmark = pytest.mark.django_db

# Modification times a month apart, set explicitly so the listing's order is decided by
# the timestamps rather than by whatever order the files happened to be written in.
OLDER_MTIME = 1767225600.0  # 2026-01-01T00:00:00Z
NEWER_MTIME = 1769990400.0  # 2026-02-02T00:00:00Z


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
    """The dumps on disk are listed by modification time, newest first."""
    services.backup_dir()
    for name, mtime in (
        ("caldart-20260101-000000.sql.gz", OLDER_MTIME),
        ("caldart-20260202-000000.sql.gz", NEWER_MTIME),
    ):
        with gzip.open(backup_dir / name, "wb") as handle:
            handle.write(b"-- dump\n")
        os.utime(backup_dir / name, (mtime, mtime))

    names = [b.name for b in services.list_backups()]

    assert names == [
        "caldart-20260202-000000.sql.gz",
        "caldart-20260101-000000.sql.gz",
    ]


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


# --------------------------------------------------------------- streaming
#
# The tools are stood in for by ``sh`` scripts, so these exercise the real
# pipes and exit codes without a database server.  ``_pg_command`` returns the
# argv prefix, and the caller appends its own arguments after it, which a
# ``sh -c`` script ignores.

#: Larger than a pipe buffer, so a dump that was not drained while ``pg_dump``
#: ran would block forever instead of finishing.
PIPE_BUFFER_BYTES = 1_000_000

#: Two megabytes of incompressible output, then a report of whether the gzip
#: file already holds bytes while the tool is still writing.  ``$0`` is the
#: target path, which a ``sh -c`` script takes as the first argument after it.
PROBE_SCRIPT = """
head -c 2000000 /dev/urandom
for _ in $(seq 20); do
  if [ -s "$0" ]; then printf streamed; exit 0; fi
  sleep 0.1
done
printf buffered
"""


def test_create_backup_writes_the_dump_while_pg_dump_is_still_running(
    backup_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The gzip file holds bytes before ``pg_dump`` exits, so nothing is buffered."""
    target = backup_dir / "caldart-probe.sql.gz"
    monkeypatch.setattr(
        services, "_pg_command", lambda tool: ["sh", "-c", PROBE_SCRIPT, str(target)]
    )

    services.create_backup(target.name)

    with gzip.open(target, "rb") as handle:
        assert handle.read()[2_000_000:] == b"streamed"


def test_create_backup_survives_a_dump_larger_than_a_pipe_buffer(
    backup_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A dump of a million bytes arrives whole, not truncated at the pipe buffer."""
    script = f"yes x | head -c {PIPE_BUFFER_BYTES}"
    monkeypatch.setattr(services, "_pg_command", lambda tool: ["sh", "-c", script])

    backup = services.create_backup("caldart-large.sql.gz")

    with gzip.open(backup.path, "rb") as handle:
        assert handle.read() == b"x\n" * (PIPE_BUFFER_BYTES // 2)


def test_create_backup_reports_the_tool_stderr_and_leaves_no_file(
    backup_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failing ``pg_dump`` raises with its stderr, and no half-written dump remains."""
    script = "echo 'could not connect to server' >&2; exit 1"
    monkeypatch.setattr(services, "_pg_command", lambda tool: ["sh", "-c", script])

    with pytest.raises(services.BackupError, match="could not connect to server"):
        services.create_backup("caldart-failed.sql.gz")

    assert list(backup_dir.iterdir()) == []


def test_restore_streams_the_whole_dump_into_the_tool(
    backup_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every byte of a dump larger than a pipe buffer reaches ``psql``'s stdin."""
    services.backup_dir()
    dump = backup_dir / "caldart-restore.sql.gz"
    body = b"x\n" * (PIPE_BUFFER_BYTES // 2)
    with gzip.open(dump, "wb") as handle:
        handle.write(body)
    received = tmp_path / "received.sql"
    monkeypatch.setattr(
        services, "_pg_command", lambda tool: ["sh", "-c", f"cat > {shlex.quote(str(received))}"]
    )

    services.restore_backup(dump, drop_first=False)

    assert received.read_bytes() == body


def test_restore_reports_the_tool_stderr(backup_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A failing ``psql`` raises ``BackupError`` carrying the message it printed."""
    services.backup_dir()
    dump = backup_dir / "caldart-restore.sql.gz"
    with gzip.open(dump, "wb") as handle:
        handle.write(b"-- dump\n")
    script = "cat >/dev/null; echo 'syntax error at or near' >&2; exit 1"
    monkeypatch.setattr(services, "_pg_command", lambda tool: ["sh", "-c", script])

    with pytest.raises(services.BackupError, match="syntax error at or near"):
        services.restore_backup(dump, drop_first=False)


def test_restore_reports_the_stderr_of_a_tool_that_never_reads_its_stdin(
    backup_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ``psql`` that fails before draining a large dump still raises with its stderr.

    The dump is larger than a pipe buffer, so the write into the tool's standard input
    hits a broken pipe; the tool's own message is what the operator needs to see.
    """
    services.backup_dir()
    dump = backup_dir / "caldart-restore.sql.gz"
    with gzip.open(dump, "wb") as handle:
        handle.write(b"x\n" * (PIPE_BUFFER_BYTES // 2))
    script = "echo 'connection to server failed' >&2; exit 2"
    monkeypatch.setattr(services, "_pg_command", lambda tool: ["sh", "-c", script])

    with pytest.raises(services.BackupError, match="connection to server failed"):
        services.restore_backup(dump, drop_first=False)


def test_restore_leaves_the_schema_alone_when_the_dump_cannot_be_read(
    backup_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A dump that is not valid gzip is refused before the schema is dropped."""
    services.backup_dir()
    dump = backup_dir / "caldart-corrupt.sql.gz"
    dump.write_bytes(b"not a gzip file at all")
    dropped: list[bool] = []
    monkeypatch.setattr(services, "drop_schema", lambda: dropped.append(True))
    monkeypatch.setattr(services, "_pg_command", lambda tool: ["sh", "-c", "cat >/dev/null"])

    with pytest.raises(services.BackupError, match=r"caldart-corrupt\.sql\.gz"):
        services.restore_backup(dump)

    assert dropped == []


class FailingSource:
    """A dump whose read fails part way through, the way a dying disk would."""

    def read(self, size: int = -1) -> bytes:
        """Raise instead of returning the next block."""
        raise OSError("the dump went away")


def test_a_dump_that_cannot_be_read_leaves_no_unreaped_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A read error while feeding the tool kills it and waits for it before raising.

    The stand-in blocks rather than exiting, so a tool that was neither killed nor
    waited for would still be running when the error reaches the caller, and the
    ``Popen`` left behind would raise a ``ResourceWarning`` when it was collected --
    a failure in whichever unrelated test happened to be running by then.
    """
    started: list[subprocess.Popen[bytes]] = []
    start_pg = services._start_pg

    def record(argv: list[str], **kwargs: Any) -> subprocess.Popen[bytes]:
        process = start_pg(argv, **kwargs)
        started.append(process)
        return process

    monkeypatch.setattr(services, "_start_pg", record)

    with pytest.raises(OSError, match="the dump went away"):
        services._stream_pg(["sh", "-c", "sleep 10"], "psql", source=FailingSource())

    assert started[0].returncode is not None
