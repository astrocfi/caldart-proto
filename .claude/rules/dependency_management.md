---
description: Standards for declaring, installing, and maintaining the project's Python (uv) and frontend (npm) dependencies.
---

# Dependency Management

## 1. Single Source of Truth

- Declare ALL Python dependencies in **`pyproject.toml`**: runtime dependencies under
  `[project]` (PEP 621), development tooling under `[dependency-groups]` (PEP 735). `uv.lock`
  records the exact resolved versions and is committed.
- Do NOT add a hand-written `requirements.txt`.
- Declare ALL frontend dependencies in `frontend/package.json`; `frontend/package-lock.json` is
  committed.

## 2. Dependency Groups

| Group | Section | Install command | Purpose |
|-------|---------|-----------------|---------|
| **Runtime** | `[project].dependencies` | `uv sync` | Required for the application to run. |
| **Docs** | `[dependency-groups].docs` | `uv sync` (`dev` includes it); `uv sync --no-dev --group docs` in production | Sphinx and its theme: the user guide is built on the server and served at `/docs/`. |
| **Dev** | `[dependency-groups].dev` | `uv sync` (installed by default) | Testing and linting, plus the `docs` group. |
| **Frontend** | `frontend/package.json` (`dependencies`, `devDependencies`) | `cd frontend && npm ci` | The portal SPA, public-site scripts, and their tooling. |

## 3. Version Constraints

- Specify **minimum** compatible versions for direct Python dependencies (e.g., `wagtail>=6.3`).
  Add an upper bound only for a known incompatibility.
- Do NOT pin exact versions (`==`) in `pyproject.toml`; exact pinning belongs in `uv.lock`.
- Frontend dependencies use caret ranges in `package.json`; exact versions live in
  `package-lock.json`.

## 4. Adding or Updating Dependencies

1. Python: `uv add <pkg>` (runtime) or `uv add --dev <pkg>`, which updates `pyproject.toml` and
   `uv.lock` together. Frontend: `npm install <pkg>` (or `--save-dev`) in `frontend/`.
2. Run `uv sync` / `npm ci` to verify installation.
3. Run the full test suite, lint, and the audit (`make test`, `make lint`, `make audit`) to
   confirm compatibility.
4. Commit the manifest and its lock file together with a `build:` commit type (see the
   `git-workflow` skill).

## 5. Security and Maintenance

- `make audit` checks every locked Python and npm package for known vulnerabilities; CI runs it
  on every push and pull request. Fix a finding by upgrading the affected package. Never apply
  `npm audit fix --force` blindly: it can resolve an advisory by downgrading a major version.
- Review update PRs for breaking changes before merging.
- Periodically remove unused dependencies to reduce attack surface.

## 6. Tooling Configuration

Consolidate Python tool configuration into `pyproject.toml` where supported:

| Tool | Section |
|------|---------|
| pytest | `[tool.pytest.ini_options]` |
| ruff | `[tool.ruff]`, `[tool.ruff.lint]` (see `python`) |
| uv | `[tool.uv]` |

Do NOT create separate config files (`.coveragerc`, `.mypy.ini`, `.flake8`, `setup.cfg`,
`pytest.ini`) when the tool supports `pyproject.toml`. Frontend tools keep their own config
files in `frontend/` (`tsconfig.json`, `eslint.config.js`, the Prettier config,
`vite.config.ts`).
