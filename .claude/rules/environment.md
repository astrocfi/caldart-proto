---
description: Git, CI/CD (GitHub Actions), the make-based check runner, environment isolation, and secrets.
---

# Environment Best Practices

## 1. Source Control

- ALWAYS use **git** for all source code.
- Commit early and often with meaningful messages (see the `git-workflow` skill), following the
  commit and PR conventions in `CLAUDE.md`.

## 2. CI/CD

- ALWAYS use **GitHub Actions** (`.github/workflows/ci.yml`) for continuous integration.
- The Makefile targets (Section 3) are the **single source of truth** for which checks the
  repository runs. CI runs those checks by calling the targets themselves -- no more, no less --
  so that the AI, CI, and the Makefile stay consistent.
- Every PR MUST pass that set of checks before merge.
- When the set changes, change the Makefile first, then bring CI into step with it in the same
  change.
- Pin action versions to a major tag (e.g., `actions/checkout@v4`) to balance stability and
  security updates.

## 3. Local Check Runner

The Makefile runs the project's quality gates, so contributors can reproduce the CI result
locally before pushing. `make help` lists every target. `lint`, `test`, `check`, and `audit` also
have `-backend` and `-frontend` halves for iterating on one side.

| Scope | Target | Runs |
|-------|--------|------|
| Code | `make lint` | `ruff check`, `ruff format --check`, `mypy backend`, `tsc --noEmit`, ESLint (`--max-warnings 0`), `prettier --check`, `codespell` |
| Tests | `make test` | pytest (needs `make up`; warnings are errors) and vitest |
| System | `make check` | Django system checks (`--fail-level WARNING`), missing-migration check, production deployment security check (`check --deploy --tag security` against `caldart.settings.prod`), production frontend build |
| Docs | `make docs` | `sphinx-build -n -W` |
| Dependencies | `make audit` | `uv audit` (Python, from `uv.lock`) and `npm audit` (frontend) |
| End-to-end (opt-in) | `make e2e` | Playwright against its own database and server |

- `make lint`, `make test`, `make check`, `make docs`, and `make audit` must all be green before
  opening a PR. `make e2e` is the slow, environment-dependent tier: opt-in locally, always run
  by CI.
- Warnings are errors in every gate that has them: pytest, Django's system checks, ESLint, and
  Sphinx (see `doc_python`).

## 4. Environment Isolation

- `uv` manages the project virtual environment (`.venv`); `uv sync` creates and updates it and
  `uv run` runs tools inside it. NEVER install project dependencies into the system Python, and
  never `pip install` into `.venv` by hand (see `dependency_management`).
- The supported Python version is recorded in `pyproject.toml` (`requires-python = ">=3.12"`)
  and pinned to 3.12 in `.python-version`, which CI uses.
- Frontend dependencies install with `npm ci` in `frontend/`; CI uses Node 22.

## 5. Secrets and Configuration

- NEVER commit secrets, tokens, or credentials. Use environment variables or GitHub Secrets.
- Use `.env` files for local development only; `.env` is in `.gitignore`.
- Validate required environment variables at startup with clear error messages.
