---
name: doc-readme
description: Format and completeness rules for the top-level README.rst of the CalDART web application, including requirements, quick start, demo accounts, and everyday commands. Use when writing, editing, or reviewing the README.
---

# README

`README.rst` is the project's front door: it renders on GitHub and is the first page a new
contributor or operator reads. Build on `doc_python` (Prose Conventions, Change Discipline).
Because it is the most widely seen page, keep it accurate, scannable, and free of internal
jargon.

## 1. Format

- Write the README in reStructuredText (`README.rst`), the same markup as the rest of the
  documentation, so it renders on GitHub.
- The README is not included into the Sphinx docs; `docs/index.rst` carries its own
  introduction and feature list ("What it does"). When the introduction or feature list
  changes, update both in the same change so they never disagree.
- Keep one top-level title (the project name, over- and underlined with `=`), and underline
  the sections below it with `=` only.

## 2. Required Sections (in order)

1. **Title** — the project name.
2. **Introduction** — 1-3 short paragraphs in plain prose: what the system does, the problem
   it solves, and who it is for. No code-object jargon. Say that `PLAN.rst` is the
   authoritative specification.
3. **Features** — a bulleted list with bold lead-ins summarizing the main capabilities at a
   glance, matching "What it does" in `docs/index.rst`.
4. **Requirements and setup** — the supported Python version, Node and npm, Docker with
   Compose, `uv`, and `make`, then the setup sequence (`make setup`, `make up`,
   `make migrate`, `make seed`) as a copy-pasteable `.. code-block:: console`. Point to
   `docs/developer/configuration.rst` for the settings in `.env` rather than listing them.
5. **Quick Start** — the shortest path to a running application: `make build` and `make run`,
   the URLs to open (public site, portal, Wagtail admin, Django admin, Mailpit), and the demo
   accounts `make seed` creates. Every command MUST run as written from the repository root.
6. **Everyday commands** — the make targets a contributor runs daily (tests, lint, checks,
   docs, end-to-end tests, audits, reset, backup), one line each, ending with `make help`.
7. **Documentation** — how to build the docs locally (`make docs`) and where the output lands
   (`docs/_build/html/index.html`). There is no hosted copy.
8. **Contributing** — a pointer to where the contribution conventions live: `CLAUDE.md` and the
   "Before you open a pull request" section of `docs/developer/setup.rst`.
9. **License** — the license name linking to the license file. While the repository has no
   license file, say plainly that the code is not licensed for redistribution.

Sections specific to this repository (end-to-end tests, the repository layout) may follow
Everyday commands; keep each short and link to the developer guide for the detail.

## 3. Content Rules

- The README is a summary and an entry point, NOT a manual. Do not document every target,
  setting, or workflow here — link to the relevant page under `docs/` for full references.
- Every make target or management command a contributor or operator needs on day one should
  be mentioned at least once with a pointer to its detailed documentation
  (`docs/developer/setup.rst` has the full tables of both).
- Keep the requirements, versions, commands, URLs, and demo accounts consistent with
  `pyproject.toml`, `.python-version`, CI (`.github/workflows/ci.yml`), the Makefile,
  `backend/apps/accounts/seed.py`, and the docs. When any of these change, update the README
  in the same change (`doc_python`, Change Discipline).
- Verify all links resolve.
