---
description: Standards for the Sphinx documentation set, prose conventions, cross-references, and the docs build.
---

# Documentation Foundation

This rule defines the documentation system, prose conventions, cross-reference rules, and
Sphinx build requirements for all documentation in this repository. Docstring rules live in
`python` (Section 5).

## 1. Documentation System

- Use **Sphinx** for all project documentation. Keep all documentation source under the single
  `docs/` directory with one `conf.py`: end-user guides in `docs/user/`, contributor and
  operator guides in `docs/developer/`. Build outputs (`docs/_build/`) are never committed.
- Author pages in **reStructuredText** (`.rst`). `README.rst` is reStructuredText
  too.
- The docs stand alone and are the specification. Never cite a plan from `plans/`
  in the docs, docstrings or comments; state what the reader needs, or link the
  docs page that covers it.
- After ANY code or documentation change, rebuild the full tree and fix every warning and error
  before delivering (see Section 5).

## 2. Prose Conventions

- One space between a sentence-ending period and the next sentence.
- American spelling, not British (e.g. `color`, not `colour`). <!-- codespell:ignore colour -->
  `make lint` enforces this with `make lint-spelling`, which runs codespell over
  `README.rst`, `CLAUDE.md`, `docs/`, `backend/`, `frontend/src/`, `frontend/e2e/`,
  `frontend/scripts/`, `scripts/`, `.github/`, `deploy/` and `.claude/` with the
  `clear`, `rare` and `en-GB_to_en-US`
  dictionaries, plus the project dictionary `.codespell-dictionary.txt` at the repository
  root for British words those built-in dictionaries miss (e.g. `aeroplane->airplane`,
  `cheque->check`). To flag another such word, add a `word->correction` line to that file
  rather than widening `ignore-words-list` (which only silences a word, never corrects
  it). `plans/` is not checked: the archived plans are frozen, and a live plan
  may quote the very words a fix replaces. Nor is `.claude/worktrees/`, which holds
  nested checkouts with their own build output and their own copy of `plans/`. The
  configuration lives in `[tool.codespell]` in `pyproject.toml`, and ignores exactly two
  words repository-wide: `nnumber` (the `nNumber` identifier) and `unparseable` (a valid
  American spelling the `rare` dictionary flags). To keep any other flagged word on one
  line, such as the example above or an identifier a library imposes, end the line with a
  `codespell:ignore <word>` comment, or precede it with a
  `codespell:ignore-next-line <word>` comment where the formatter will not leave a
  trailing one. Do not widen `ignore-words-list`: an entry there silences the word
  everywhere.
- Define each CalDART-specific term on first use, such as DART. Don't define
  standard aviation terms (N-number, BasicMed, medical classes, flight review):
  the readers are pilots and DART volunteers.
- Describe the **current** state of the software only. Never anchor prose to a
  moment in time or to migration history: avoid "new", "legacy", "old",
  "now", "recently", "as before", "backwards compatible", and similar framing.
- Do not use unicode smart quotes, em-dashes, or arrows inside `.py` files
  (they are acceptable in `.rst` and `.md`).

## 3. Sphinx Configuration (`conf.py`)

- `docs/conf.py` is deliberately minimal: Sphinx and the `furo` theme, plus
  `sphinx.ext.graphviz` only when Graphviz's `dot` is installed. Add an extension only when a
  page needs it, and only one that builds on a machine without extra system packages, since
  `-W` turns a missing-tool warning into a failed build.
- Nothing is generated from docstrings (no `autodoc`). The API reference
  (`docs/developer/api-*.rst`) is written by hand.
- Use `nitpick_ignore` / `nitpick_ignore_regex` ONLY for targets that genuinely cannot resolve.
  Every entry MUST carry a comment explaining why. Never silence a nitpick warning for a target
  you own.

## 4. Cross-Reference Completeness

- Link other documentation pages with `:doc:` and labeled sections with `:ref:`. Never refer to
  another page by bare title or file path in prose.
- Python roles (`:class:`, `:func:`, `:mod:`, ...) cannot resolve in these docs because no API
  is generated from the code. Put code symbols, endpoints, file paths, settings, environment
  variables, and shell snippets in inline literals (` `` `` `).
- Cross-references are NOT required (and should be omitted) inside `.. code-block::`
  directives, `::` literal blocks, diagram blocks, and section titles.
- When a page, label, endpoint, or setting is added, removed, or renamed, every reference to it
  across the whole docs tree MUST be updated in the same change. A rename without reference
  updates is a documentation regression.

## 5. Build Discipline (warnings as errors AND nitpicky)

Documentation is correct only when it builds clean under BOTH gates, which `make docs` (and
therefore CI) applies together:

```bash
make docs    # sphinx-build -n -W -b html docs docs/_build/html
```

- `-W` promotes every warning (undefined label, duplicate target, malformed
  directive, broken toctree) to an error.
- `-n` (nitpicky) flags every cross-reference that does not resolve to a known
  target — the primary defense against the stale references in Section 4.
- The build MUST succeed with ZERO warnings before delivering. A doc change that breaks the
  build is not done.
- Diagrams: `docs/developer/data-model.rst` draws its diagram inside `.. only:: graphviz` with
  an ASCII equivalent inside `.. only:: not graphviz`. Change both together, and validate
  complex diagrams in their authoring tool before committing.

## 6. Change Discipline

- Any code change MUST update the affected docstrings, documentation pages, and the `README`
  in the same change.
- A new or changed API endpoint MUST update its `docs/developer/api-*.rst` page in the same
  change; a new user-facing feature needs its page under `docs/user/`.
- NEVER leave stale or contradictory documentation. If a feature is removed,
  remove its documentation; if it is renamed, rename every reference.
