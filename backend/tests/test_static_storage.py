"""The production static-file storage keeps Vite's build output under Vite's own names.

Vite already writes a content hash into every file it builds, and its chunks import one
another by those names.  If ``collectstatic`` renamed them again, a page would load the
portal's entry script under one name while its lazy chunks imported it under another,
so the browser would run the entry twice and mount two React roots on one element.
Every other static file (the admin's, Wagtail's, the site's own images) is still hashed.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from django.contrib.staticfiles import finders
from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.management import call_command
from pytest_django.fixtures import Settings

from caldart.storage import VITE_ASSETS_DIR

#: The storage the production settings name (``test_sysadmin_settings.py`` checks it).
PRODUCTION_STORAGE = "caldart.storage.ViteManifestStaticFilesStorage"

#: A name Django's manifest storage writes: the stem, twelve hex digits, the extension.
DJANGO_HASHED = re.compile(r"\.[0-9a-f]{12}\.")

#: The entry of the fake build, and the lazy chunk that imports it by name, as Vite
#: emits them.
ENTRY = "assets/portal-AbCd1234.js"
CHUNK = "assets/ProfilePage-XyZ98765.js"
STYLESHEET = "assets/portal-QwEr5678.css"
IMAGE = "assets/hero-LkJh4321.png"


@pytest.fixture
def built(tmp_path: Path, settings: Settings) -> Path:
    """Collect a small fake Vite build and one other file with the production storage.

    Returns the ``STATIC_ROOT`` the files were collected into.
    """
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    # Long enough to shrink under gzip: whitenoise keeps no copy that does not.
    padding = "".join(f"export const line{index} = {index};\n" for index in range(200))
    (dist / ENTRY).write_text(f'{padding}import("./ProfilePage-XyZ98765.js");\n')
    (dist / CHUNK).write_text(
        'import { answer } from "./portal-AbCd1234.js";\nconsole.log(answer);\n'
    )
    (dist / STYLESHEET).write_text('.hero { background: url("./hero-LkJh4321.png"); }\n')
    (dist / IMAGE).write_bytes(b"\x89PNG\r\n\x1a\n")
    extra = tmp_path / "extra"
    (extra / "img").mkdir(parents=True)
    (extra / "img" / "logo.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>\n")
    root = tmp_path / "static"
    settings.STATIC_ROOT = root
    settings.STATICFILES_DIRS = [dist, extra]
    settings.STATICFILES_FINDERS = ["django.contrib.staticfiles.finders.FileSystemFinder"]
    settings.STORAGES = {**settings.STORAGES, "staticfiles": {"BACKEND": PRODUCTION_STORAGE}}
    call_command("collectstatic", interactive=False, verbosity=0)
    return root


def _collected(root: Path) -> set[str]:
    """Every file under ``root``, as a path relative to it, without compressed copies."""
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.suffix not in {".gz", ".br"}
    }


def test_vite_output_keeps_the_names_vite_gave_it(built: Path) -> None:
    """No file under ``assets/`` gains a second hash, so its imports still resolve."""
    vite_files = {name for name in _collected(built) if name.startswith(VITE_ASSETS_DIR)}
    assert vite_files == {ENTRY, CHUNK, STYLESHEET, IMAGE}


def test_a_vite_entry_is_served_under_the_name_its_chunks_import(built: Path) -> None:
    """The URL a template writes for the entry is the one a lazy chunk imports it by."""
    assert staticfiles_storage.url(ENTRY) == f"/static/{ENTRY}"


def test_every_other_static_file_is_still_hashed(built: Path) -> None:
    """A file outside ``assets/`` is collected, and served, under Django's hashed name."""
    url = staticfiles_storage.url("img/logo.svg")
    assert DJANGO_HASHED.search(url) is not None


def test_a_vite_stylesheet_keeps_its_references_to_vite_files(built: Path) -> None:
    """A ``url()`` in a Vite stylesheet still names the image by Vite's name."""
    assert './hero-LkJh4321.png"' in (built / STYLESHEET).read_text()


def test_vite_output_is_compressed_for_whitenoise(built: Path) -> None:
    """A gzip copy is still written beside each Vite file, for whitenoise to serve."""
    assert (built / f"{ENTRY}.gz").is_file()


def test_no_installed_app_ships_static_files_under_the_vite_directory() -> None:
    """Only the Vite build owns ``assets/``, so nothing else escapes Django's hashing."""
    app_finder = finders.AppDirectoriesFinder()
    under_assets = [path for path, _storage in app_finder.list([]) if path.startswith("assets")]
    assert under_assets == []
