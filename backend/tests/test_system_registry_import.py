"""``POST /admin/system/registry-import``: Run now for the FAA registry import.

``docs/developer/api-system.rst`` is the contract.  The process launcher is replaced
by a recorder, so no test starts a real import.
"""

from __future__ import annotations

import subprocess
from datetime import timedelta

import pytest
from django.utils import timezone
from pytest_django import Settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import SYSTEM_ADMIN
from apps.aircraft import registry
from apps.aircraft.models import RegistryImport
from tests.conftest import audit_messages, role_matrix

pytestmark = pytest.mark.django_db

RUN_URL = "/api/v1/admin/system/registry-import"

#: The source the tests point ``FAA_REGISTRY_URL`` at.
SOURCE = "https://registry.example.test/ReleasableAircraft.zip"


@pytest.fixture
def launched(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> list[int]:
    """The ids of the import rows handed to the launcher, which starts nothing."""
    settings.FAA_REGISTRY_URL = SOURCE
    settings.REGISTRY_IMPORT_STALE_MINUTES = 30
    started: list[int] = []
    monkeypatch.setattr(registry, "launch_import", lambda run: started.append(run.pk))
    return started


def test_run_now_answers_202_with_the_unfinished_row(
    system_admin_client: APIClient, launched: list[int]
) -> None:
    """The row is written before the answer: started, not finished, from the setting."""
    response = system_admin_client.post(RUN_URL)
    body = response.json()
    assert (response.status_code, body["finished_at"], body["ok"], body["source"]) == (
        202,
        None,
        False,
        SOURCE,
    )


def test_run_now_launches_the_import_it_recorded(
    system_admin_client: APIClient, launched: list[int]
) -> None:
    """The launcher is handed the row the answer describes."""
    system_admin_client.post(RUN_URL)
    assert launched == [RegistryImport.objects.get().pk]


def test_run_now_records_who_pressed_it(
    system_admin_client: APIClient, system_admin: User, launched: list[int]
) -> None:
    """``started_by`` is the system administrator."""
    system_admin_client.post(RUN_URL)
    assert RegistryImport.objects.get().started_by == system_admin


def test_a_second_press_while_one_runs_is_refused(
    system_admin_client: APIClient, launched: list[int]
) -> None:
    """While an import runs, Run now answers 409 and launches nothing more."""
    system_admin_client.post(RUN_URL)
    response = system_admin_client.post(RUN_URL)
    assert (response.status_code, response.json(), len(launched)) == (
        409,
        {"detail": "An import is already running."},
        1,
    )


def test_a_stale_import_is_closed_as_failed(
    system_admin_client: APIClient, launched: list[int]
) -> None:
    """An unfinished import older than the stale limit is closed: ``Did not finish.``."""
    stale = RegistryImport.objects.create(started_at=timezone.now() - timedelta(minutes=31))
    system_admin_client.post(RUN_URL)
    stale.refresh_from_db()
    assert (stale.ok, stale.error, stale.finished_at is not None) == (
        False,
        "Did not finish.",
        True,
    )


def test_a_stale_import_does_not_block_a_fresh_one(
    system_admin_client: APIClient, launched: list[int]
) -> None:
    """Once the stale run is closed, a fresh one starts."""
    RegistryImport.objects.create(started_at=timezone.now() - timedelta(minutes=31))
    assert system_admin_client.post(RUN_URL).status_code == 202


def test_a_finished_import_does_not_block_a_fresh_one(
    system_admin_client: APIClient, launched: list[int]
) -> None:
    """A run that finished, however it ended, leaves Run now free."""
    RegistryImport.objects.create(finished_at=timezone.now(), ok=True)
    assert system_admin_client.post(RUN_URL).status_code == 202


def test_run_now_is_audited(
    system_admin_client: APIClient,
    system_admin: User,
    launched: list[int],
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """The press writes one ``system.registry_import`` audit line naming the run."""
    system_admin_client.post(RUN_URL)
    run = RegistryImport.objects.get()
    assert audit_messages(audit_log) == [
        f"action=system.registry_import actor={system_admin.pk} target={run.pk}"
    ]


def test_a_refused_press_is_audited_as_refused(
    system_admin_client: APIClient,
    system_admin: User,
    launched: list[int],
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """A press refused because one runs writes a WARNING line, ``import_running``."""
    system_admin_client.post(RUN_URL)
    system_admin_client.post(RUN_URL)
    assert audit_messages(audit_log)[-1] == (
        f"action=system.registry_import actor={system_admin.pk} target=- reason=import_running"
    )


@pytest.mark.parametrize(("slug", "allowed"), role_matrix(SYSTEM_ADMIN))
def test_role_matrix_for_run_now(
    api_client: APIClient,
    all_role_users: dict[str, User],
    launched: list[int],
    slug: str,
    allowed: bool,
) -> None:
    """Only the system administrator presses Run now; every other role gets 403."""
    api_client.force_login(all_role_users[slug])
    assert api_client.post(RUN_URL).status_code == (202 if allowed else 403)


def test_the_launcher_starts_the_command_in_its_own_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``launch_import`` runs ``import_faa_registry --import-id <id>`` detached."""
    calls: list[tuple[list[str], bool]] = []

    def record(argv: list[str], *, start_new_session: bool) -> None:
        calls.append((argv, start_new_session))

    monkeypatch.setattr(subprocess, "Popen", record)
    run = RegistryImport.objects.create()
    registry.launch_import(run)
    argv, detached = calls[0]
    assert (argv[-3:], argv[1].endswith("manage.py"), detached) == (
        ["import_faa_registry", "--import-id", str(run.pk)],
        True,
        True,
    )
