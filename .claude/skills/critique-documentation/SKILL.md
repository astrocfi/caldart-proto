---
name: critique-documentation
description: Analyze the CalDART documentation (README.rst, the user guide, the developer guide and hand-written API reference, how-to articles, docstrings, and the Sphinx setup) against the project's documentation rules and produce a report (no edits). Use when the user asks to critique, review, or audit the documentation, or to generate a report for fixing the docs.
---

# Critique Documentation

Analyze all of the project's documentation and produce a **report only** — do not modify any
documentation files. The report is intended to be used as a prompt for an AI agent (or
developer) to fix the documentation later.

## Scope

- **README** (`README.rst`) and `PLAN.rst`, the specification that
  `docs/developer/architecture.rst` includes verbatim.
- **Narrative docs** under `docs/` (reStructuredText): the user guide (`docs/user/`), the
  developer guide (`docs/developer/`), the demo walkthrough, and any how-to articles.
- **API reference**: the hand-written `docs/developer/api-reference.rst` and `api-<area>.rst`
  pages, checked against the endpoints in `backend/apps/*/api/urls.py` and `PLAN.rst` §6.
- **Code documentation**: docstrings in `backend/` and JSDoc on exported functions and
  components in `frontend/src/`. They are not rendered into the docs.
- **Sphinx setup**: `docs/conf.py`, the documentation `toctree` structure, and the build
  (`make docs`, which is warnings-as-errors and nitpicky).

## Project rules

Treat these documentation standards as authoritative and cite them by name in findings. The
rules are in `.claude/rules/` (always loaded); the skills are in `.claude/skills/` (read each
`SKILL.md` directly):

- `doc_python` (`.claude/rules/doc_python.md`) — the **foundation**: documentation system,
  prose conventions, the minimal `conf.py`, cross-reference completeness (`:doc:`/`:ref:`
  links, code symbols in inline literals), build discipline (`-W` warnings-as-errors **and**
  `-n` nitpicky), and change discipline. Every other doc rule builds on it.
- `python` (`.claude/rules/python.md`, Docstrings) and
  `javascript_typescript_best_practices` (Comments and Documentation) — the docstring and
  JSDoc standards.
- `doc-readme` (`.claude/skills/doc-readme/SKILL.md`) — `README.rst`: required sections,
  quick start, and consistency with `docs/index.rst`.
- `doc-user-guide` (`.claude/skills/doc-user-guide/SKILL.md`) — the user guide: layout,
  per-role chapters, required content, and the operator command reference.
- `doc-dev-guide` (`.claude/skills/doc-dev-guide/SKILL.md`) — the developer guide: layout,
  required chapters, the entity-relationship diagram, per-subsystem prose, extension recipes,
  and the hand-written API reference.
- `doc-how-to` (`.claude/skills/doc-how-to/SKILL.md`) — task-focused how-to articles:
  structure, prerequisites, numbered steps, expected results, and troubleshooting.

Not every project ships every rule. **If a referenced rule file does not exist, ignore the
corresponding part of the critique** instead of inventing a standard, and do not report the
rule's absence as a finding. Critique only against the doc rules that are actually present.

## Checklist for Analysis

Apply these criteria to the documentation set. Map each finding to the rule file it supports
(above) and skip any area whose rule is absent.

### 1. Documentation system and build (`doc_python`)

- **Single source tree:** All docs live under `docs/` with one `conf.py`; build outputs
  (`docs/_build/`) are not committed.
- **Sphinx config:** `conf.py` stays minimal (the `furo` theme, and `sphinx.ext.graphviz` only
  when `dot` is installed); any added extension builds on a machine without extra system
  packages. Note `nitpick_ignore` entries that suppress targets the project owns or that lack
  a comment.
- **Build cleanliness:** `make docs` (`sphinx-build -n -W`) passes with zero warnings. Note any
  warnings, broken `toctree` entries, documents not in any `toctree`, and unresolved `:doc:` or
  `:ref:` targets. Note any `.. graphviz::` without an ASCII equivalent in
  `.. only:: not graphviz`.
- **Prose conventions:** American spelling; one space after sentence-ending periods; terms
  defined on first use; **no time-anchored or migration framing** ("new", "legacy", "now",
  "recently", "backwards compatible"). No unicode smart quotes/em-dashes/arrows inside `.py`
  files.

### 2. Docstrings and code documentation (`python`, `javascript_typescript_best_practices`)

- **Coverage:** Every module, class, method, and function in `backend/` has a docstring, and
  every exported frontend function and component has JSDoc. Note missing or one-line-only
  docstrings on non-trivial code.
- **Content and format:** Per the `python` rule's Docstrings section: observable behavior
  detailed enough to write a black-box test, no change history or ticket numbers, wrapped to
  the project width.
- Nothing is generated from docstrings, so review them as code documentation, not as a
  published API surface.

### 3. Cross-reference completeness (`doc_python`)

- **Links:** Pages link other pages with `:doc:` and labeled sections with `:ref:`; no page
  refers to another by bare title or file path in prose. Code symbols, endpoints, file paths,
  settings, and environment variables are in inline literals. Note any Python role (`:class:`,
  `:func:`, ...) in `docs/` or `PLAN.rst`, which cannot resolve here.
- **Resolution:** All references resolve under nitpicky mode. Note stale references to renamed
  or removed pages, labels, endpoints, settings, or files, and cross-directory `:doc:` targets
  that are not absolute (`doc-user-guide`).

### 4. README (`doc-readme`)

- **Format:** reStructuredText with a single top-level title. It is not included into Sphinx,
  so its introduction and feature list must agree with `docs/index.rst`.
- **Required sections (in order):** title, introduction, features, requirements and setup,
  quick start (URLs and demo accounts), everyday commands, documentation (local build),
  contributing pointer, license.
- **Content:** Every command runs as written from the repository root; versions agree with
  `pyproject.toml`, `.python-version`, and CI; every make target named exists in the Makefile;
  the demo accounts match the seed; all links resolve. The README is a summary and entry
  point, not a manual.

### 5. User guide (`doc-user-guide`)

- **Layout:** `docs/user/` with a landing page holding a short introduction and captioned
  `toctree` directives; getting started first; one chapter per role plus shared task
  chapters; reference material (the FAQ) on its own page; cross-directory `:doc:` targets
  absolute, intra-guide ones relative.
- **Required content:** introduction/purpose; an overview of the workflow; getting started
  (accounts, sign-in, passwords, roles); what administrators configure from the browser, with a
  pointer to server configuration; screens and workflows per role with expected results;
  examples (or links to the demo walkthrough).
- **Role accuracy:** Each role chapter matches the permission matrix (`PLAN.rst` §5) and
  `frontend/src/portal/nav.ts`. Note screens a role can reach that the guide omits, and
  documented actions the role cannot perform.
- **Operator commands:** For each management command and operator make target — name,
  purpose, syntax, EVERY option with its default and environment- or make-variable
  equivalent, whether it is destructive, a runnable example, and the format of any file it
  reads or writes. Note options that drift from the command's `add_arguments` or the Makefile.

### 6. Developer guide and API reference (`doc-dev-guide`)

- **Layout:** `docs/developer/` with a landing page holding an audience statement and captioned
  `toctree` directives in reading order; API pages `api-<area>.rst` in the `toctree` of
  `api-reference.rst`; `architecture.rst` includes `PLAN.rst` with the plan nested under the
  page title.
- **Required chapters:** introduction; the annotated repository layout (`PLAN.rst` §3) matching
  the tree; environment setup (setup sequence, per-worker `DATABASE_URL`, every environment
  variable, running locally, the test suites, the lint/check/audit/docs commands, CI, upgrading
  a server, the contribution workflow); architecture and data model; subsystem chapters;
  extending; a coding-conventions pointer; the API reference.
- **Diagram:** The entity-relationship diagram in `data-model.rst` shows the principal models
  and relationships, matches the models, and has an ASCII equivalent.
- **Per-subsystem prose:** Each subsystem chapter gives an overview naming its code, contracts,
  concrete implementations, invariants (permissions, idempotency, integer cents, dates), and a
  pointer to its API page.
- **Extending:** A recipe with a code skeleton for each extension point (payment provider,
  Wagtail page type or block, API endpoint, portal screen, management command).
- **API reference:** Every endpoint in `backend/apps/*/api/urls.py` is documented (method and
  path, who may call it, request, responses with status codes and example JSON), and every
  documented endpoint exists. The permission matrix matches `PLAN.rst` §5 and the permission
  classes.

### 7. How-to articles (`doc-how-to`)

- **Structure:** Action-oriented title; 1-3 sentence intro; prerequisites (role, state,
  environment); numbered steps (one action each, with the exact screen and control or command
  and the observed result); an expected-results summary consistent with the per-step
  observations; troubleshooting of common failures; related-material links.
- **Placement and consistency:** Each how-to sits in the `toctree` of the guide it serves.
  Written for a reader unfamiliar with internals; where a how-to and a guide cover the same
  workflow, they are consistent and link to each other rather than duplicating detail.

### 8. Diagrams and figures (`doc-how-to`, `doc-dev-guide`)

- **Use and rendering:** Diagrams are used where a visual is clearer than prose (workflows,
  data flows, architecture), placed inline near the relevant section, render in the docs build
  with and without Graphviz, and images have descriptive filenames and alt text.

### 9. Change discipline and consistency (`doc_python`)

- **Stale docs:** Documentation matches the current code — no docs for removed features, no
  references to renamed pages, endpoints, or settings, and commands that still run. Note
  versions, commands, settings, or role descriptions that disagree across `README.rst`, the
  guides, `PLAN.rst`, the Makefile, and `docs/developer/configuration.rst` versus
  `backend/caldart/settings/`.
- **Plan agreement:** `PLAN.rst` is the specification. Note where the docs or the code
  disagree with it.
- **Same-change updates:** New or changed endpoints have their API pages updated, new screens
  appear in the user guide, and renamed things have every reference updated.

## Output: Report Format

Produce a single markdown report with the following structure. Do **not** edit any
documentation files; only write the report. Omit sections whose rule file is absent, and say
so briefly under "Rules applied".

```markdown
# Documentation Critique Report

**Generated:** [date]
**Scope:** README.rst, PLAN.rst, docs/ (user guide, developer guide and API reference, how-tos), docstrings and JSDoc, Sphinx setup
**Rules applied:** [list the doc rule files found; note any absent and therefore skipped]

## Executive summary
- Overall assessment (strengths, main gaps).
- **Build health:** Does `make docs` (`-n -W`) pass? Summarize warning count and categories.
- High-priority fixes vs. nice-to-have.

## 1. Documentation system and build
[conf.py, source tree, build cleanliness, Graphviz fallbacks, prose conventions.]

## 2. Docstrings and code documentation
[Missing or thin docstrings and JSDoc; content and format.]

## 3. Cross-reference completeness
[Bare titles or paths in prose; Python roles in docs; unresolved or stale :doc:/:ref: targets.]

## 4. README
[Sections present/missing; runnable commands; links; consistency with docs/index.rst and the metadata.]

## 5. User guide
[Layout; required content; role accuracy; operator command coverage.]

## 6. Developer guide and API reference
[Layout; required chapters; diagram; per-subsystem prose; extension recipes; endpoint coverage and permission matrix.]

## 7. How-to articles
[Structure; placement; prerequisites; steps with observed results; troubleshooting; consistency with the guides.]

## 8. Diagrams and figures
[Appropriate use, rendering with and without Graphviz, naming, alt text.]

## 9. Change discipline and consistency
[Stale docs, cross-document disagreements, disagreements with PLAN.rst, missing same-change updates.]

## Recommended priorities
1. [Highest impact, feasible first step]
2. [Next]
3. [Next]

## Prompt for an AI agent to fix the documentation

[Self-contained prompt for an AI to apply the fixes. Include:
- The report sections as context.
- **Build gate:** `make docs` (`sphinx-build -n -W`) must pass with zero warnings before the work is considered done.
- Instruction to fix documentation according to the report and the present documentation standards (`.claude/rules/doc_python.md` and the `.claude/skills/doc-*/SKILL.md` skills), without changing production code behavior.
- Instruction to update every cross-reference, the README, and the guides in the same change when a page, endpoint, or setting is renamed or moved.]
```

## Execution steps

1. **Inventory rules:** List which of `.claude/rules/doc_python.md` and
   `.claude/skills/doc-*/SKILL.md` exist. Critique only against those; record which are absent
   so their checklist areas are skipped.
2. **Gather docs:** List `README.rst`, `PLAN.rst`, and the `docs/` tree (note the `toctree`
   structure and which pages are user guide vs. developer guide vs. API reference vs. how-to).
   Read `docs/conf.py`.
3. **Build:** Run `make docs` (warnings-as-errors and nitpicky) and capture warnings. If the
   docs cannot be built in this environment, say so and critique statically.
4. **Read:** Sample `README.rst`, each guide landing page and representative chapters, the API
   pages against `backend/apps/*/api/urls.py`, a how-to, and a cross-section of docstrings and
   JSDoc. Grep for stale references, Python roles in `docs/`, and time-anchored phrasing.
5. **Classify:** For each checklist area (1-9), note specific files, sections, and line
   references or short quotes, and cite the supporting doc rule.
6. **Write:** Produce the full report in the format above, including the "Prompt for an AI
   agent" section at the end.
7. **Do not:** Change, add, or remove any line in any documentation, source, or config file.

## When to use this skill

- User asks to "critique the documentation", "review the docs", "audit the docs", or "generate
  a report to fix the documentation".
- User wants a "prompt for an AI to fix the docs" based on the current documentation.
- Use the `python-codebase-analysis` skill instead for a whole-codebase audit, and
  `critique-test-suite` for the test suite; this skill is the documentation-specific deep dive.
