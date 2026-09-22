"""The pytest hooks in ``conftest.py``: temp-directory cleanup and the bundle guard."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pytest
from pytest_django.fixtures import Settings

from caldart.settings.test import STATIC_ROOT_PREFIX
from tests import conftest

#: A manifest path that exists nowhere, standing in for the build CI forgot to
#: make.  The guard only ever puts it in a message.
MISSING_MANIFEST = Path("/nowhere/frontend/dist/.vite/manifest.json")

#: Any path at all: the guard reads this one only to learn that the stub
#: manifest fallback fired.
STUB_MANIFEST = Path("/nowhere/stub/manifest.json")

#: What the guard did with an item.
GuardAction = Literal["run", "skip", "fail"]


@dataclass(frozen=True)
class GuardOutcome:
    """What ``pytest_runtest_setup`` did with an item, and the reason it gave."""

    action: GuardAction
    reason: str


def run_guard(item: pytest.Item) -> GuardOutcome:
    """Call the guard on ``item`` and report what it did.

    ``pytest_runtest_setup`` signals its verdict by raising, which would end
    the calling test; catching both outcomes turns the verdict into a value a
    test can assert on.
    """
    try:
        conftest.pytest_runtest_setup(item)
    except pytest.skip.Exception as exc:
        return GuardOutcome("skip", str(exc))
    except pytest.fail.Exception as exc:
        return GuardOutcome("fail", str(exc))
    return GuardOutcome("run", "")


@pytest.fixture
def unbuilt_frontend(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pretend ``pytest_configure`` fell back to the stub manifest."""
    monkeypatch.setattr(conftest, "_stub_manifest_path", STUB_MANIFEST)
    monkeypatch.setattr(conftest, "_missing_manifest_path", MISSING_MANIFEST)


@pytest.fixture
def marked_item(request: pytest.FixtureRequest) -> pytest.Item:
    """This test's own item, carrying the ``needs_frontend_build`` marker.

    Adding the marker after setup has run gives the hook a real item to inspect
    without changing how the test itself is collected or reported.
    """
    request.node.add_marker(pytest.mark.needs_frontend_build)
    item: pytest.Item = request.node
    return item


def test_unconfigure_removes_the_temporary_static_root(
    tmp_path: Path,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    pytestconfig: pytest.Config,
) -> None:
    """The directory ``caldart.settings.test`` creates does not outlive the session."""
    monkeypatch.setattr(conftest, "_stub_manifest_dir", None)
    static_root = tmp_path / f"{STATIC_ROOT_PREFIX}abc123"
    static_root.mkdir()
    settings.STATIC_ROOT = static_root

    conftest.pytest_unconfigure(pytestconfig)

    assert not static_root.exists()


def test_unconfigure_leaves_a_static_root_it_did_not_create(
    tmp_path: Path,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    pytestconfig: pytest.Config,
) -> None:
    """A ``STATIC_ROOT`` without the test settings' prefix is never removed."""
    monkeypatch.setattr(conftest, "_stub_manifest_dir", None)
    static_root = tmp_path / "staticfiles"
    static_root.mkdir()
    settings.STATIC_ROOT = static_root

    conftest.pytest_unconfigure(pytestconfig)

    assert static_root.exists()


def test_unconfigure_removes_the_stub_manifest_directory(
    tmp_path: Path,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    pytestconfig: pytest.Config,
) -> None:
    """The stub manifest directory goes with it."""
    stub_dir = tmp_path / "caldart-vite-manifest-abc123"
    stub_dir.mkdir()
    (stub_dir / "manifest.json").write_text("{}")
    monkeypatch.setattr(conftest, "_stub_manifest_dir", stub_dir)
    settings.STATIC_ROOT = tmp_path / "staticfiles"

    conftest.pytest_unconfigure(pytestconfig)

    assert not stub_dir.exists()


def test_needs_frontend_build_fails_in_ci_without_a_bundle(
    unbuilt_frontend: None, marked_item: pytest.Item, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CI must not go green by skipping the tests that assert on the bundle."""
    monkeypatch.setenv(conftest.CI_ENV_VAR, "true")

    outcome = run_guard(marked_item)

    assert outcome.action == "fail"
    assert str(MISSING_MANIFEST) in outcome.reason


def test_needs_frontend_build_skips_locally_without_a_bundle(
    unbuilt_frontend: None, marked_item: pytest.Item, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A developer who has not run ``make build`` gets a skip naming the path."""
    monkeypatch.delenv(conftest.CI_ENV_VAR, raising=False)

    outcome = run_guard(marked_item)

    assert outcome.action == "skip"
    assert str(MISSING_MANIFEST) in outcome.reason


def test_needs_frontend_build_runs_when_a_bundle_is_configured(
    marked_item: pytest.Item, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With a real manifest the hook stands aside, in CI as much as locally."""
    monkeypatch.setattr(conftest, "_stub_manifest_path", None)
    monkeypatch.setenv(conftest.CI_ENV_VAR, "true")

    assert run_guard(marked_item).action == "run"


def test_an_unmarked_test_is_never_touched(
    unbuilt_frontend: None, request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only the marker asks for a bundle; everything else runs without one."""
    monkeypatch.setenv(conftest.CI_ENV_VAR, "true")
    item: pytest.Item = request.node

    assert run_guard(item).action == "run"
