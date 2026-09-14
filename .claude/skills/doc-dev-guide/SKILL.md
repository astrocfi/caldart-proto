---
name: doc-dev-guide
description: Format, layout, and completeness rules for the CalDART developer guide under docs/developer/, covering setup, architecture, the data model, subsystem chapters, extension recipes, and the hand-written API reference. Use when writing, editing, or reviewing the developer guide or API reference.
---

# Developer Guide

The developer guide is the manual for people who **modify, extend, test, or run** CalDART. It
explains how the code is organized, how the pieces cooperate, and how to work on it safely.
Build on `doc_python` (Sphinx, cross-references, prose, build discipline). Assume a competent
Python and TypeScript developer who is new to *this* codebase; favor architecture and
contracts over restating what the code already says.

## 1. File Layout

- Live under `docs/developer/` as reStructuredText.
- A single landing page (`docs/developer/index.rst`) holds a 1-2 sentence audience statement
  and captioned `toctree` directives listing the chapters in reading order: foundations
  (architecture, setup, configuration, data model, API reference), then subsystems, then
  building and running (testing, deployment, backup and restore, roadmap).
- Organize chapters by subsystem, plus cross-cutting chapters (architecture, setup,
  configuration, data model, testing). Name files in lowercase with hyphens; the API pages are
  `api-<area>.rst`, listed in the `toctree` of `api-reference.rst`.
- The landing page is reachable from the documentation root `toctree`.
- `architecture.rst` includes `PLAN.rst` verbatim; the plan is the specification every other
  page defers to. Change `PLAN.rst` itself rather than restating it, and keep the Architecture
  page's own title in a heading style `PLAN.rst` never uses, so the plan nests beneath it.

## 2. Required Chapters

- **Introduction** — who the guide is for, how it differs from the user guide, and a system
  overview (what it does, the runtime and key dependencies). `index.rst` and the plan's goals
  and stack sections (`PLAN.rst` §1-2) carry this.
- **Repository layout** — an annotated directory tree (a `::` literal block) with a one-line
  comment on each significant directory and top-level file. `PLAN.rst` §3 holds it; keep it in
  step with the tree.
- **Environment setup** — how to get a working development checkout (`setup.rst`,
  `configuration.rst`, `testing.rst`):
    - Clone, `make setup` (`uv sync`, `npm ci`, `.env`), `make up`, `make migrate`,
      `make seed`, and the per-worker `DATABASE_URL`.
    - Every environment variable needed to run, test, or build, with defaults.
    - How to run the application locally (`make run`, `make dev-frontend`), including a smoke
      test.
    - How to run the test suites: backend (`make test-backend`, a single file or test),
      frontend (`make test-frontend`), and end-to-end (`make e2e`); the shared fixtures and
      factories; any markers.
    - How to run the linters, formatters, checks, audits, and the docs build (`make lint`,
      `make format`, `make check`, `make audit`, `make docs`), plus the full tables of make
      targets and management commands.
    - The CI pipeline (what runs on which trigger) and how a server is upgraded
      (`deployment.rst`). There are no releases.
    - The contribution workflow ("Before you open a pull request" in `setup.rst`).
- **Architecture and data model** — see Section 3.
- **Per-subsystem chapters** — see Section 4.
- **Extending the system** — see Section 5.
- **Coding conventions** — the project's style and quality rules, or a pointer to where they
  live (`CLAUDE.md` and `.claude/rules/`).
- **API reference** — see Section 6.

## 3. Architecture and Diagrams

- Include at least one **entity-relationship diagram** (`data-model.rst`) showing the
  principal models, their key fields, and the relationships between them (foreign keys,
  one-to-one, many-to-many, "produces"/"consumes").
- Draw it with `.. graphviz::` inside `.. only:: graphviz`, and keep an ASCII equivalent inside
  `.. only:: not graphviz`, so the build passes on machines without Graphviz (`docs/conf.py`
  enables the extension only when `dot` is installed). Change both together.
- Mark abstract models (such as the CMS `BasePage`) and show the methods that define each
  abstract contract (such as the payment `Provider`).
- Follow every diagram with narrative prose that walks each group of models in turn — a
  diagram alone is not documentation.
- Name every model and class in the narrative in inline literals per `doc_python`
  (Cross-Reference Completeness); Python roles do not resolve here. Do NOT put markup inside
  the diagram block itself.
- Keep the diagram in sync with the code: a renamed or removed model invalidates the diagram
  and must be fixed in the same change.

## 4. Per-Subsystem Prose

Each subsystem chapter (`payments-setup.rst`, `cms.rst`, `theming.rst`, `reports.rst`,
`reminders.rst`, `backup-restore.rst`) MUST give a reader enough to navigate and modify that
code without reverse-engineering it. Include:

- **Overview** — the subsystem's responsibility and how it fits the overall flow, naming the
  code it documents (`backend/apps/<app>/`, `frontend/src/portal/features/<feature>/`).
- **Per-class / per-file description** — prose for each significant model, service, view, or
  component: its role, the contract it defines or implements (list the methods subclasses
  must provide and what each returns), notable fields, and how instances are created and
  used. Describe behavior and contracts, not a line-by-line restatement of the source.
- **Concrete implementations** — enumerate the shipping implementations of each abstract base
  and what distinguishes each (e.g. the Stripe, PayPal, and mock payment providers; the
  Wagtail page types).
- **Important invariants** — role and permission requirements, idempotency (payment webhooks,
  reminder deduplication, seed commands), money as integer cents, date rules, caching and
  shared mutable state, and ordering requirements. State these explicitly where they apply.
- **API-reference pointer** — end the chapter with a link to the `api-<area>` page(s) for the
  subsystem's endpoints.

## 5. Extending the System

- Provide a step-by-step recipe for each extension point: which base class or file to start
  from, which methods to implement and their contracts, where to put the file, and how to
  register it so the system discovers it. The extension points are:
    - **A payment provider** — subclass `Provider` in `backend/apps/payments/providers/`, set
      `slug`, implement `start`, `confirm`, and an idempotent `handle_webhook`, decorate the
      class with `@register`, import it in `providers/__init__.py` (importing the package
      registers every provider), and have `available_providers()` offer it when its settings
      are present.
    - **A Wagtail page type or StreamField block** — `backend/apps/cms/models.py` (subclass the
      abstract `BasePage`) and `backend/apps/cms/blocks.py`; `cms.rst` carries "Adding a page
      type" and "Adding a block".
    - **An API endpoint** — `backend/apps/<app>/api/urls.py` (already included by
      `caldart/api_urls.py`), the permission classes the matrix in `PLAN.rst` §5 requires, the
      matching type in `frontend/src/portal/api/types.ts`, and its `api-<area>.rst` page.
    - **A portal screen** — a `RouteObject[]` in `frontend/src/portal/routes/<feature>.tsx`
      added to `routes/index.tsx`, components in `frontend/src/portal/features/<feature>/`,
      and a `NAV_ITEMS` entry with its roles in `frontend/src/portal/nav.ts`.
    - **A management command** — `backend/apps/<app>/management/commands/<name>.py` with a
      `help` string, a row in the management-commands table in `setup.rst`, and a make target
      when operators run it routinely.
- Include a minimal, correct code skeleton for each recipe in a `.. code-block:: python` (or
  `tsx`) directive.
- Cross-reference the relevant subsystem chapter and name the base classes involved rather
  than duplicating their contracts.

## 6. API Reference

- The API reference is written by hand: nothing is generated from docstrings (no `autodoc`).
  `api-reference.rst` holds the conventions every endpoint shares (authentication, CSRF, URL
  shape, 401 versus 403, pagination, filtering, error shape, throttling, roles), the
  permission matrix, and the `toctree` of per-area pages; each `api-<area>.rst` documents the
  endpoints of one area of `PLAN.rst` §6.
- For each endpoint give the method and path as its heading, who may call it, the request body
  and query parameters, and every response with its status code and an example body in a
  `.. code-block:: json` directive.
- Cover the entire API: a new or changed endpoint updates its `api-<area>.rst` page in the
  same change, and the permission matrix when its roles change. An endpoint without a page of
  its own is listed in `api-reference.rst` with a link to the chapter that documents it.
- Keep the reference in exact agreement with the serializers, views, and `PLAN.rst` §6. A
  hand-written reference drifts silently, so review it with every API change.

## 7. Build Discipline

The developer guide is the heaviest user of cross-references, code blocks, and diagrams, so it
is the most prone to silent breakage. It MUST build clean under `make docs`
(`sphinx-build -n -W`: warnings as errors and nitpicky) per `doc_python` (Build Discipline)
before delivering — every cross-reference resolving, every code block lexing with its declared
language, and every diagram rendering both with and without Graphviz.
