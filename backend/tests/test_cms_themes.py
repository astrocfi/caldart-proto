"""The shipped themes stay in step across the model, the migration and the stylesheets.

A theme is registered in four places: ``THEME_CHOICES`` in ``apps.cms.models``, the
``choices`` recorded on the ``SiteSettings.theme`` column by the initial migration,
``frontend/src/styles/themes/<slug>.css``, and the ``THEMES`` mirror in
``frontend/src/site/nav.ts``.  These tests fail the moment one of them drifts.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from apps.cms.models import DEFAULT_THEME, THEME_CHOICES, THEME_SLUGS, SiteSettings

REPO_ROOT = Path(__file__).resolve().parents[2]
THEMES_DIR = REPO_ROOT / "frontend" / "src" / "styles" / "themes"
NAV_TS = REPO_ROOT / "frontend" / "src" / "site" / "nav.ts"
INDEX_CSS = REPO_ROOT / "frontend" / "src" / "styles" / "index.css"
INITIAL_MIGRATION = REPO_ROOT / "backend" / "apps" / "cms" / "migrations" / "0001_initial.py"


def test_default_theme_is_registered() -> None:
    """``DEFAULT_THEME`` is one of the slugs the settings dropdown offers."""
    assert DEFAULT_THEME in THEME_SLUGS


def test_slugs_match_the_choices() -> None:
    """``THEME_SLUGS`` is exactly the first column of ``THEME_CHOICES``."""
    assert tuple(slug for slug, _ in THEME_CHOICES) == THEME_SLUGS


def test_every_slug_is_unique() -> None:
    """No slug is registered twice."""
    assert len(set(THEME_SLUGS)) == len(THEME_SLUGS)


def test_every_label_is_unique() -> None:
    """No two themes share a dropdown label."""
    labels = [label for _, label in THEME_CHOICES]
    assert len(set(labels)) == len(labels)


def test_the_model_field_carries_every_choice() -> None:
    """``SiteSettings.theme`` offers exactly ``THEME_CHOICES``."""
    field = SiteSettings._meta.get_field("theme")
    assert tuple(field.choices) == THEME_CHOICES


def test_every_slug_fits_the_column() -> None:
    """No slug is longer than the ``max_length`` of ``SiteSettings.theme``."""
    max_length = SiteSettings._meta.get_field("theme").max_length
    assert max(len(slug) for slug in THEME_SLUGS) <= max_length


def test_the_initial_migration_records_every_choice() -> None:
    """The migrated column's ``choices`` match the model's, so no fix-up migration is due.

    This prototype edits the migration that declares the field rather than stacking a
    second one, so the two can only agree by being kept in step by hand.
    """
    recorded = re.search(
        r"'theme', models\.CharField\(choices=(\[.*?\]), default=", INITIAL_MIGRATION.read_text()
    )
    assert recorded is not None
    choices = ast.literal_eval(recorded.group(1))
    assert tuple(tuple(pair) for pair in choices) == THEME_CHOICES


@pytest.mark.parametrize("slug", THEME_SLUGS)
def test_every_slug_has_a_stylesheet(slug: str) -> None:
    """``themes/<slug>.css`` exists and declares its own ``data-theme`` block."""
    assert f":root[data-theme='{slug}']" in (THEMES_DIR / f"{slug}.css").read_text()


@pytest.mark.parametrize("slug", THEME_SLUGS)
def test_every_stylesheet_is_imported(slug: str) -> None:
    """``index.css`` imports the theme, so the bundle carries it."""
    assert f"@import './themes/{slug}.css';" in INDEX_CSS.read_text()


@pytest.mark.parametrize("slug", THEME_SLUGS)
def test_every_slug_is_mirrored_in_nav_ts(slug: str) -> None:
    """The public site's ``THEMES`` list knows the slug, so ``?theme=`` previews it."""
    assert f"'{slug}'" in NAV_TS.read_text()


def test_no_stylesheet_is_unregistered() -> None:
    """Every file in ``themes/`` is a slug the settings dropdown offers."""
    on_disk = {path.stem for path in THEMES_DIR.glob("*.css")}
    assert on_disk == set(THEME_SLUGS)
