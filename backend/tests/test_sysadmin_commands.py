"""``db_backup``, ``db_restore`` and ``db_reset``.

``pg_dump``/``psql`` are mocked out and ``BACKUP_DIR`` points at ``tmp_path``,
so nothing here touches a real database or the repository's ``backups/``.
"""

from __future__ import annotations

import gzip
import shutil
import subprocess
from io import StringIO
from pathlib import Path
from typing import Any

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from pytest_django import Settings

from apps.sysadmin import services
from apps.sysadmin.management.commands import db_reset as db_reset_command

pytestmark = pytest.mark.django_db


@pytest.fixture
def backup_dir(tmp_path: Path, settings: Settings) -> Path:
    """Point ``BACKUP_DIR`` at a throwaway directory under ``tmp_path``."""
    settings.BACKUP_DIR = tmp_path / "backups"
    return services.backup_dir()


@pytest.fixture
def pg_calls(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Record every pg invocation instead of running one; returns the list."""
    calls: list[dict[str, Any]] = []

    def fake_run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        calls.append({"argv": argv, "input": kwargs.get("input")})
        return subprocess.CompletedProcess(argv, 0, b"-- dump body\n", b"")

    monkeypatch.setattr(services, "_pg_command", lambda tool: [tool])
    monkeypatch.setattr(services, "_run_pg", fake_run)
    return calls


@pytest.fixture
def no_schema_drop(
    monkeypatch: pytest.MonkeyPatch, pg_calls: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Record ``DROP SCHEMA`` rather than issuing it against the test database."""
    monkeypatch.setattr(services, "drop_schema", lambda: pg_calls.append({"argv": ["DROP SCHEMA"]}))
    return pg_calls


# ----------------------------------------------------------------- db_backup
def test_db_backup_writes_a_gzipped_dump(backup_dir: Path, pg_calls: list[dict[str, Any]]) -> None:
    """``db_backup`` writes a gzipped dump named ``caldart-*.sql.gz`` and reports it."""
    out = StringIO()

    call_command("db_backup", stdout=out)

    (written,) = list(backup_dir.iterdir())
    assert written.name.startswith("caldart-")
    assert written.name.endswith(".sql.gz")
    with gzip.open(written, "rb") as handle:
        assert handle.read() == b"-- dump body\n"
    assert "Wrote" in out.getvalue()


def test_db_backup_honors_an_explicit_name(
    backup_dir: Path, pg_calls: list[dict[str, Any]]
) -> None:
    """``db_backup --name`` writes the dump under the given file name."""
    call_command("db_backup", "--name", "before-upgrade.sql.gz", stdout=StringIO())

    assert (backup_dir / "before-upgrade.sql.gz").is_file()


def test_db_backup_passes_the_database_url_to_pg_dump(
    backup_dir: Path, pg_calls: list[dict[str, Any]], settings: Settings
) -> None:
    """``pg_dump`` gets the database URL, ``--no-owner`` and ``--no-privileges``."""
    call_command("db_backup", stdout=StringIO())

    argv = pg_calls[0]["argv"]
    assert argv[0] == "pg_dump"
    assert "--no-owner" in argv and "--no-privileges" in argv
    assert settings.DATABASES["default"]["NAME"] in argv[argv.index("--dbname") + 1]


def test_db_backup_creates_the_directory(
    tmp_path: Path, settings: Settings, pg_calls: list[dict[str, Any]]
) -> None:
    """``db_backup`` creates ``BACKUP_DIR``, including missing parent directories."""
    settings.BACKUP_DIR = tmp_path / "nested" / "backups"

    call_command("db_backup", stdout=StringIO())

    assert (tmp_path / "nested" / "backups").is_dir()


def test_db_backup_reports_a_failure(backup_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A failing ``pg_dump`` raises ``CommandError`` with stderr; nothing is written."""
    monkeypatch.setattr(services, "_pg_command", lambda tool: [tool])
    monkeypatch.setattr(
        services,
        "_run_pg",
        lambda argv, **kw: subprocess.CompletedProcess(argv, 1, b"", b"could not connect"),
    )

    with pytest.raises(CommandError, match="could not connect"):
        call_command("db_backup", stdout=StringIO())

    assert list(backup_dir.iterdir()) == []


def test_db_backup_needs_pg_dump_or_docker(
    backup_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With neither ``pg_dump`` nor docker, ``db_backup`` raises ``CommandError``."""
    monkeypatch.setattr(services, "_pg_command", lambda tool: None)

    with pytest.raises(CommandError, match="Neither pg_dump nor docker"):
        call_command("db_backup", stdout=StringIO())


# ------------------------------------------------------- tool discovery
def test_pg_command_prefers_docker_when_configured(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With ``DB_BACKUP_VIA_DOCKER`` set, the command runs through ``docker compose``."""
    settings.DB_BACKUP_VIA_DOCKER = True
    monkeypatch.setattr(shutil, "which", lambda tool: f"/usr/bin/{tool}")

    argv = services._pg_command("pg_dump")
    assert argv is not None
    assert argv[:3] == ["docker", "compose", "exec"]


def test_pg_command_uses_the_local_binary_when_docker_is_not_forced(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With a local binary on ``PATH`` and docker not forced, that binary is used."""
    settings.DB_BACKUP_VIA_DOCKER = False
    monkeypatch.setattr(shutil, "which", lambda tool: f"/usr/bin/{tool}")

    assert services._pg_command("pg_dump") == ["pg_dump"]


def test_pg_command_falls_back_to_docker_without_a_local_binary(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no local binary but docker available, the command falls back to docker."""
    settings.DB_BACKUP_VIA_DOCKER = False
    monkeypatch.setattr(shutil, "which", lambda tool: None if tool != "docker" else "/d")

    argv = services._pg_command("psql")
    assert argv is not None
    assert argv[0] == "docker"


def test_pg_command_gives_up_with_neither(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With neither a local binary nor docker, ``_pg_command`` returns ``None``."""
    settings.DB_BACKUP_VIA_DOCKER = False
    monkeypatch.setattr(shutil, "which", lambda tool: None)

    assert services._pg_command("psql") is None


def test_the_container_url_points_at_the_container_localhost() -> None:
    """A container URL names ``localhost``; a local one matches ``database_url``."""
    docker = services._dbname_url_for(["docker", "compose", "exec", "-T", "db", "pg_dump"])
    local = services._dbname_url_for(["pg_dump"])

    assert "@localhost:5432/" in docker
    assert local == services.database_url()


# ---------------------------------------------------------------- db_restore
@pytest.fixture
def a_dump(backup_dir: Path) -> Path:
    """One gzipped dump on disk, ready to restore."""
    path = backup_dir / "caldart-20260601-090000.sql.gz"
    with gzip.open(path, "wb") as handle:
        handle.write(b"-- restore me\n")
    return path


def test_db_restore_drops_the_schema_then_replays_the_dump(
    a_dump: Path, no_schema_drop: list[dict[str, Any]]
) -> None:
    """``db_restore --yes`` drops the schema, then replays the dump through ``psql``."""
    out = StringIO()

    call_command("db_restore", str(a_dump), "--yes", stdout=out)

    assert [call["argv"][0] for call in no_schema_drop] == ["DROP SCHEMA", "psql"]
    assert no_schema_drop[1]["input"] == b"-- restore me\n"
    assert "Restored" in out.getvalue()


def test_db_restore_accepts_a_bare_name_inside_the_backup_directory(
    a_dump: Path, no_schema_drop: list[dict[str, Any]]
) -> None:
    """``db_restore`` accepts a bare file name and resolves it inside ``BACKUP_DIR``."""
    call_command("db_restore", a_dump.name, "--yes", stdout=StringIO())

    assert no_schema_drop[-1]["argv"][0] == "psql"


def test_db_restore_rejects_a_missing_file(
    backup_dir: Path, no_schema_drop: list[dict[str, Any]]
) -> None:
    """Restoring a missing name raises ``CommandError`` and drops nothing."""
    with pytest.raises(CommandError, match="No such backup"):
        call_command("db_restore", "nope.sql.gz", "--yes", stdout=StringIO())

    assert no_schema_drop == []


def test_db_restore_asks_before_destroying_anything(
    a_dump: Path, no_schema_drop: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """An answer other than ``yes`` aborts without dropping anything."""
    monkeypatch.setattr("builtins.input", lambda prompt="": "no")

    with pytest.raises(CommandError, match="Aborted"):
        call_command("db_restore", str(a_dump), stdout=StringIO())

    assert no_schema_drop == []


def test_db_restore_proceeds_when_the_answer_is_yes(
    a_dump: Path, no_schema_drop: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Answering ``yes`` at the prompt proceeds to drop the schema and replay the dump."""
    monkeypatch.setattr("builtins.input", lambda prompt="": "yes")

    call_command("db_restore", str(a_dump), stdout=StringIO())

    assert [call["argv"][0] for call in no_schema_drop] == ["DROP SCHEMA", "psql"]


def test_db_restore_reports_a_psql_failure(a_dump: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A failing ``psql`` raises ``CommandError`` carrying its stderr."""
    monkeypatch.setattr(services, "drop_schema", lambda: None)
    monkeypatch.setattr(services, "_pg_command", lambda tool: [tool])
    monkeypatch.setattr(
        services,
        "_run_pg",
        lambda argv, **kw: subprocess.CompletedProcess(argv, 1, b"", b"syntax error"),
    )

    with pytest.raises(CommandError, match="syntax error"):
        call_command("db_restore", str(a_dump), "--yes", stdout=StringIO())


def test_restore_can_skip_the_drop(
    a_dump: Path, monkeypatch: pytest.MonkeyPatch, pg_calls: list[dict[str, Any]]
) -> None:
    """``restore_backup(drop_first=False)`` replays without dropping the schema."""
    dropped: list[bool] = []
    monkeypatch.setattr(services, "drop_schema", lambda: dropped.append(True))

    services.restore_backup(a_dump, drop_first=False)

    assert dropped == []
    assert pg_calls[0]["argv"][0] == "psql"


# ------------------------------------------------------------------ db_reset
@pytest.fixture
def reset_calls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Capture what ``db_reset`` orchestrates instead of running it."""
    calls: list[str] = []
    monkeypatch.setattr(db_reset_command, "drop_schema", lambda: calls.append("drop_schema"))
    monkeypatch.setattr(db_reset_command, "call_command", lambda name, *a, **kw: calls.append(name))
    return calls


def test_db_reset_migrates_and_seeds_roles(reset_calls: list[str]) -> None:
    """``db_reset --noinput`` drops the schema, migrates, and seeds roles in order."""
    call_command("db_reset", "--noinput", stdout=StringIO())

    assert reset_calls == ["drop_schema", "migrate", "seed_roles"]


def test_db_reset_seed_flag_runs_the_seeders(reset_calls: list[str]) -> None:
    """``db_reset --seed`` also runs the demo and content seeders, after roles."""
    call_command("db_reset", "--noinput", "--seed", stdout=StringIO())

    assert reset_calls == [
        "drop_schema",
        "migrate",
        "seed_roles",
        "seed_demo",
        "seed_content",
    ]


def test_db_reset_asks_first(reset_calls: list[str], monkeypatch: pytest.MonkeyPatch) -> None:
    """Answering anything but ``yes`` at the prompt aborts and orchestrates nothing."""
    monkeypatch.setattr("builtins.input", lambda prompt="": "no thanks")

    with pytest.raises(CommandError, match="Aborted"):
        call_command("db_reset", stdout=StringIO())

    assert reset_calls == []


def test_db_reset_names_the_database_it_will_destroy(
    reset_calls: list[str], monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    """The confirmation prompt names the database that is about to be destroyed."""
    prompts: list[str] = []

    def fake_input(prompt: str = "") -> str:
        prompts.append(prompt)
        return "yes"

    monkeypatch.setattr("builtins.input", fake_input)

    call_command("db_reset", stdout=StringIO())

    assert settings.DATABASES["default"]["NAME"] in prompts[0]
