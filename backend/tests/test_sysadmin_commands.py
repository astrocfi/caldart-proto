"""``db_backup``, ``db_restore`` and ``db_reset``.

``pg_dump``/``psql`` are mocked out and ``BACKUP_DIR`` points at ``tmp_path``,
so nothing here touches a real database or the repository's ``backups/``.
"""

from __future__ import annotations

import gzip
import subprocess
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.sysadmin import services
from apps.sysadmin.management.commands import db_reset as db_reset_command

pytestmark = pytest.mark.django_db


@pytest.fixture
def backup_dir(tmp_path, settings):
    settings.BACKUP_DIR = tmp_path / "backups"
    return services.backup_dir()


@pytest.fixture
def pg_calls(monkeypatch):
    """Record every pg invocation instead of running one; returns the list."""
    calls: list[dict] = []

    def fake_run(argv, **kwargs):
        calls.append({"argv": argv, "input": kwargs.get("input")})
        return subprocess.CompletedProcess(argv, 0, b"-- dump body\n", b"")

    monkeypatch.setattr(services, "_pg_command", lambda tool: [tool])
    monkeypatch.setattr(services, "_run_pg", fake_run)
    return calls


@pytest.fixture
def no_schema_drop(monkeypatch, pg_calls):
    """Record ``DROP SCHEMA`` rather than issuing it against the test database."""
    monkeypatch.setattr(services, "drop_schema", lambda: pg_calls.append({"argv": ["DROP SCHEMA"]}))
    return pg_calls


# ----------------------------------------------------------------- db_backup
def test_db_backup_writes_a_gzipped_dump(backup_dir, pg_calls):
    out = StringIO()

    call_command("db_backup", stdout=out)

    (written,) = list(backup_dir.iterdir())
    assert written.name.startswith("caldart-")
    assert written.name.endswith(".sql.gz")
    with gzip.open(written, "rb") as handle:
        assert handle.read() == b"-- dump body\n"
    assert "Wrote" in out.getvalue()


def test_db_backup_honours_an_explicit_name(backup_dir, pg_calls):
    call_command("db_backup", "--name", "before-upgrade.sql.gz", stdout=StringIO())

    assert (backup_dir / "before-upgrade.sql.gz").is_file()


def test_db_backup_passes_the_database_url_to_pg_dump(backup_dir, pg_calls, settings):
    call_command("db_backup", stdout=StringIO())

    argv = pg_calls[0]["argv"]
    assert argv[0] == "pg_dump"
    assert "--no-owner" in argv and "--no-privileges" in argv
    assert settings.DATABASES["default"]["NAME"] in argv[argv.index("--dbname") + 1]


def test_db_backup_creates_the_directory(tmp_path, settings, pg_calls):
    settings.BACKUP_DIR = tmp_path / "nested" / "backups"

    call_command("db_backup", stdout=StringIO())

    assert (tmp_path / "nested" / "backups").is_dir()


def test_db_backup_reports_a_failure(backup_dir, monkeypatch):
    monkeypatch.setattr(services, "_pg_command", lambda tool: [tool])
    monkeypatch.setattr(
        services,
        "_run_pg",
        lambda argv, **kw: subprocess.CompletedProcess(argv, 1, b"", b"could not connect"),
    )

    with pytest.raises(CommandError, match="could not connect"):
        call_command("db_backup", stdout=StringIO())

    assert list(backup_dir.iterdir()) == []


def test_db_backup_needs_pg_dump_or_docker(backup_dir, monkeypatch):
    monkeypatch.setattr(services, "_pg_command", lambda tool: None)

    with pytest.raises(CommandError, match="Neither pg_dump nor docker"):
        call_command("db_backup", stdout=StringIO())


# ------------------------------------------------------- tool discovery
def test_pg_command_prefers_docker_when_configured(settings, monkeypatch):
    settings.DB_BACKUP_VIA_DOCKER = True
    monkeypatch.setattr(services.shutil, "which", lambda tool: f"/usr/bin/{tool}")

    assert services._pg_command("pg_dump")[:3] == ["docker", "compose", "exec"]


def test_pg_command_uses_the_local_binary_when_docker_is_not_forced(settings, monkeypatch):
    settings.DB_BACKUP_VIA_DOCKER = False
    monkeypatch.setattr(services.shutil, "which", lambda tool: f"/usr/bin/{tool}")

    assert services._pg_command("pg_dump") == ["pg_dump"]


def test_pg_command_falls_back_to_docker_without_a_local_binary(settings, monkeypatch):
    settings.DB_BACKUP_VIA_DOCKER = False
    monkeypatch.setattr(services.shutil, "which", lambda tool: None if tool != "docker" else "/d")

    assert services._pg_command("psql")[0] == "docker"


def test_pg_command_gives_up_with_neither(settings, monkeypatch):
    settings.DB_BACKUP_VIA_DOCKER = False
    monkeypatch.setattr(services.shutil, "which", lambda tool: None)

    assert services._pg_command("psql") is None


def test_the_container_url_points_at_the_container_localhost():
    docker = services._dbname_url_for(["docker", "compose", "exec", "-T", "db", "pg_dump"])
    local = services._dbname_url_for(["pg_dump"])

    assert "@localhost:5432/" in docker
    assert local == services.database_url()


# ---------------------------------------------------------------- db_restore
@pytest.fixture
def a_dump(backup_dir):
    path = backup_dir / "caldart-20260601-090000.sql.gz"
    with gzip.open(path, "wb") as handle:
        handle.write(b"-- restore me\n")
    return path


def test_db_restore_drops_the_schema_then_replays_the_dump(a_dump, no_schema_drop):
    out = StringIO()

    call_command("db_restore", str(a_dump), "--yes", stdout=out)

    assert [call["argv"][0] for call in no_schema_drop] == ["DROP SCHEMA", "psql"]
    assert no_schema_drop[1]["input"] == b"-- restore me\n"
    assert "Restored" in out.getvalue()


def test_db_restore_accepts_a_bare_name_inside_the_backup_directory(a_dump, no_schema_drop):
    call_command("db_restore", a_dump.name, "--yes", stdout=StringIO())

    assert no_schema_drop[-1]["argv"][0] == "psql"


def test_db_restore_rejects_a_missing_file(backup_dir, no_schema_drop):
    with pytest.raises(CommandError, match="No such backup"):
        call_command("db_restore", "nope.sql.gz", "--yes", stdout=StringIO())

    assert no_schema_drop == []


def test_db_restore_asks_before_destroying_anything(a_dump, no_schema_drop, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt="": "no")

    with pytest.raises(CommandError, match="Aborted"):
        call_command("db_restore", str(a_dump), stdout=StringIO())

    assert no_schema_drop == []


def test_db_restore_proceeds_when_the_answer_is_yes(a_dump, no_schema_drop, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt="": "yes")

    call_command("db_restore", str(a_dump), stdout=StringIO())

    assert [call["argv"][0] for call in no_schema_drop] == ["DROP SCHEMA", "psql"]


def test_db_restore_reports_a_psql_failure(a_dump, monkeypatch):
    monkeypatch.setattr(services, "drop_schema", lambda: None)
    monkeypatch.setattr(services, "_pg_command", lambda tool: [tool])
    monkeypatch.setattr(
        services,
        "_run_pg",
        lambda argv, **kw: subprocess.CompletedProcess(argv, 1, b"", b"syntax error"),
    )

    with pytest.raises(CommandError, match="syntax error"):
        call_command("db_restore", str(a_dump), "--yes", stdout=StringIO())


def test_restore_can_skip_the_drop(a_dump, monkeypatch, pg_calls):
    dropped = []
    monkeypatch.setattr(services, "drop_schema", lambda: dropped.append(True))

    services.restore_backup(a_dump, drop_first=False)

    assert dropped == []
    assert pg_calls[0]["argv"][0] == "psql"


# ------------------------------------------------------------------ db_reset
@pytest.fixture
def reset_calls(monkeypatch):
    """Capture what ``db_reset`` orchestrates instead of running it."""
    calls: list[str] = []
    monkeypatch.setattr(db_reset_command, "drop_schema", lambda: calls.append("drop_schema"))
    monkeypatch.setattr(db_reset_command, "call_command", lambda name, *a, **kw: calls.append(name))
    return calls


def test_db_reset_migrates_and_seeds_roles(reset_calls):
    call_command("db_reset", "--noinput", stdout=StringIO())

    assert reset_calls == ["drop_schema", "migrate", "seed_roles"]


def test_db_reset_seed_flag_runs_the_seeders(reset_calls):
    call_command("db_reset", "--noinput", "--seed", stdout=StringIO())

    assert reset_calls == [
        "drop_schema",
        "migrate",
        "seed_roles",
        "seed_demo",
        "seed_content",
    ]


def test_db_reset_asks_first(reset_calls, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt="": "no thanks")

    with pytest.raises(CommandError, match="Aborted"):
        call_command("db_reset", stdout=StringIO())

    assert reset_calls == []


def test_db_reset_names_the_database_it_will_destroy(reset_calls, monkeypatch, settings):
    prompts: list[str] = []

    def fake_input(prompt=""):
        prompts.append(prompt)
        return "yes"

    monkeypatch.setattr("builtins.input", fake_input)

    call_command("db_reset", stdout=StringIO())

    assert settings.DATABASES["default"]["NAME"] in prompts[0]
