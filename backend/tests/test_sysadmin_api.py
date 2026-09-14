"""The system health and backup endpoints — ``system_admin`` only.

The download route gets the most attention here: it takes a file name straight
off the URL, so every way of pointing it outside ``BACKUP_DIR`` has a test.
"""

from __future__ import annotations

import gzip
import subprocess

import pytest

from apps.accounts.roles import (
    ACCOUNT_ADMIN,
    DART_LEADER,
    MEMBER,
    SYSTEM_ADMIN,
    USER_ADMIN,
    WEBSITE_ADMIN,
)
from apps.sysadmin import services

pytestmark = pytest.mark.django_db

HEALTH_URL = "/api/v1/system/health"
BACKUPS_URL = "/api/v1/system/backups"


def download_url(name: str) -> str:
    return f"{BACKUPS_URL}/{name}/download"


@pytest.fixture
def backup_dir(tmp_path, settings):
    """A throwaway ``BACKUP_DIR`` so tests never touch the repository's."""
    settings.BACKUP_DIR = tmp_path / "backups"
    return services.backup_dir()


@pytest.fixture
def a_backup(backup_dir):
    """One dump on disk, with known contents."""
    path = backup_dir / "caldart-20260601-090000.sql.gz"
    with gzip.open(path, "wb") as handle:
        handle.write(b"-- caldart dump\n")
    return path


@pytest.fixture
def fake_pg_dump(monkeypatch):
    """Make ``create_backup`` produce a dump without a database server."""
    monkeypatch.setattr(services, "_pg_command", lambda tool: [tool])
    monkeypatch.setattr(
        services,
        "_run_pg",
        lambda argv, **kw: subprocess.CompletedProcess(argv, 0, b"-- generated dump\n", b""),
    )


ROLE_MATRIX = [
    (MEMBER, False),
    (DART_LEADER, False),
    (USER_ADMIN, False),
    (ACCOUNT_ADMIN, False),
    (WEBSITE_ADMIN, False),
    (SYSTEM_ADMIN, True),
]


# ---------------------------------------------------------------- role matrix
@pytest.mark.parametrize(("role", "allowed"), ROLE_MATRIX)
def test_health_role_matrix(api_client, all_role_users, backup_dir, role, allowed):
    api_client.force_login(all_role_users[role])
    assert api_client.get(HEALTH_URL).status_code == (200 if allowed else 403)


@pytest.mark.parametrize(("role", "allowed"), ROLE_MATRIX)
def test_backup_list_role_matrix(api_client, all_role_users, backup_dir, role, allowed):
    api_client.force_login(all_role_users[role])
    assert api_client.get(BACKUPS_URL).status_code == (200 if allowed else 403)


@pytest.mark.parametrize(("role", "allowed"), ROLE_MATRIX)
def test_backup_create_role_matrix(
    api_client, all_role_users, backup_dir, fake_pg_dump, role, allowed
):
    api_client.force_login(all_role_users[role])
    assert api_client.post(BACKUPS_URL).status_code == (201 if allowed else 403)


@pytest.mark.parametrize(("role", "allowed"), ROLE_MATRIX)
def test_backup_download_role_matrix(api_client, all_role_users, a_backup, role, allowed):
    api_client.force_login(all_role_users[role])
    response = api_client.get(download_url(a_backup.name))
    # The test client closes a streamed response only once its content is read, and
    # closing it is what closes the dump file FileResponse opened.
    response.close()
    assert response.status_code == (200 if allowed else 403)


@pytest.mark.parametrize("url", [HEALTH_URL, BACKUPS_URL])
def test_system_endpoints_need_a_session(api_client, backup_dir, url):
    assert api_client.get(url).status_code == 401


def test_download_needs_a_session(api_client, a_backup):
    assert api_client.get(download_url(a_backup.name)).status_code == 401


# ------------------------------------------------------------------- health
def test_health_payload(api_client, system_admin, backup_dir):
    api_client.force_login(system_admin)

    body = api_client.get(HEALTH_URL).json()

    assert set(body) == {
        "db",
        "pending_migrations",
        "disk_free_mb",
        "last_backup",
        "version",
        "debug",
    }
    assert body["db"] == "ok"
    assert body["pending_migrations"] == 0
    assert body["disk_free_mb"] > 0
    assert body["last_backup"] is None
    assert body["debug"] is False
    assert body["version"] == services.app_version()


def test_health_reports_the_newest_backup(api_client, system_admin, a_backup):
    api_client.force_login(system_admin)

    assert api_client.get(HEALTH_URL).json()["last_backup"] is not None


# ------------------------------------------------------------------ backups
def test_backup_list_is_empty_to_start(api_client, system_admin, backup_dir):
    api_client.force_login(system_admin)

    assert api_client.get(BACKUPS_URL).json() == []


def test_backup_list_entries(api_client, system_admin, a_backup):
    api_client.force_login(system_admin)

    (entry,) = api_client.get(BACKUPS_URL).json()

    assert entry["name"] == a_backup.name
    assert entry["size_bytes"] == a_backup.stat().st_size
    assert entry["created_at"]


def test_create_backup_writes_a_file_and_returns_its_entry(
    api_client, system_admin, backup_dir, fake_pg_dump
):
    api_client.force_login(system_admin)

    response = api_client.post(BACKUPS_URL)

    assert response.status_code == 201
    entry = response.json()
    written = backup_dir / entry["name"]
    assert written.is_file()
    assert entry["name"].startswith("caldart-")
    assert entry["name"].endswith(".sql.gz")
    with gzip.open(written, "rb") as handle:
        assert handle.read() == b"-- generated dump\n"
    assert [row["name"] for row in api_client.get(BACKUPS_URL).json()] == [entry["name"]]


def test_create_backup_surfaces_a_pg_dump_failure(
    api_client, system_admin, backup_dir, monkeypatch
):
    monkeypatch.setattr(services, "_pg_command", lambda tool: None)
    api_client.force_login(system_admin)

    response = api_client.post(BACKUPS_URL)

    assert response.status_code == 400
    assert "pg_dump" in str(response.json())


# ----------------------------------------------------------------- download
def test_download_streams_the_dump(api_client, system_admin, a_backup):
    api_client.force_login(system_admin)

    response = api_client.get(download_url(a_backup.name))

    assert response.status_code == 200
    assert response["Content-Type"] == "application/gzip"
    assert a_backup.name in response["Content-Disposition"]
    assert "attachment" in response["Content-Disposition"]
    body = b"".join(response.streaming_content)
    assert gzip.decompress(body) == b"-- caldart dump\n"


def test_download_404s_for_a_name_that_is_not_there(api_client, system_admin, backup_dir):
    api_client.force_login(system_admin)

    assert api_client.get(download_url("caldart-19700101-000000.sql.gz")).status_code == 404


@pytest.mark.parametrize(
    "name",
    [
        "../secret.sql.gz",
        "../../etc/passwd",
        "..%2F..%2Fsecret.sql.gz",
        "/etc/passwd",
        "..",
        ".hidden.sql.gz",
        "notes.txt",
        "caldart.sql.gz.txt",
        "caldart-20260601-090000.sql.gz/../../secret.sql.gz",
    ],
)
def test_download_rejects_path_traversal(api_client, system_admin, backup_dir, tmp_path, name):
    """Nothing outside ``BACKUP_DIR`` is reachable, whatever the name looks like."""
    outside = tmp_path / "secret.sql.gz"
    with gzip.open(outside, "wb") as handle:
        handle.write(b"-- not yours\n")
    api_client.force_login(system_admin)

    response = api_client.get(download_url(name))

    assert response.status_code == 404
    assert b"not yours" not in response.content


def test_download_refuses_a_symlink_out_of_the_backup_directory(
    api_client, system_admin, backup_dir, tmp_path
):
    outside = tmp_path / "elsewhere.sql.gz"
    with gzip.open(outside, "wb") as handle:
        handle.write(b"-- not yours\n")
    (backup_dir / "link.sql.gz").symlink_to(outside)
    api_client.force_login(system_admin)

    assert api_client.get(download_url("link.sql.gz")).status_code == 404


# ------------------------------------------------------------------ services
def test_resolve_backup_returns_a_real_dump(a_backup):
    assert services.resolve_backup(a_backup.name) == a_backup.resolve()


@pytest.mark.parametrize("name", ["../x.sql.gz", "x.txt", "", "a/b.sql.gz"])
def test_resolve_backup_rejects_bad_names(backup_dir, name):
    with pytest.raises(services.BackupError, match="Not a backup file name"):
        services.resolve_backup(name)


def test_app_version_comes_from_pyproject(settings):
    import tomllib
    from pathlib import Path

    services.app_version.cache_clear()
    with (Path(settings.REPO_ROOT) / "pyproject.toml").open("rb") as handle:
        expected = tomllib.load(handle)["project"]["version"]

    assert services.app_version() == expected


def test_app_version_falls_back_when_pyproject_is_missing(settings, tmp_path):
    services.app_version.cache_clear()
    settings.REPO_ROOT = tmp_path
    try:
        assert services.app_version() == settings.CALDART_VERSION
    finally:
        services.app_version.cache_clear()
