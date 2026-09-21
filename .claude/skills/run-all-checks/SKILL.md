---
name: run-all-checks
description: Run every quality gate the Makefile defines (lint, tests, Django system and migration checks, production build, docs, dependency audit), check for errors and warnings, then fix any problems found. Use when the user asks to run checks, verify the build, run CI locally, or fix lint/type/test/docs/audit errors.
---

# Run All Checks

Execute all project checks (lint, tests, Django and build checks, docs, dependency audit) and fix any errors found. This skill aligns with the Makefile targets and this repository's layout (`backend/`, `frontend/`, `docs/`).

## The Makefile controls which checks are enabled

The Makefile is the **single source of truth** for which checks this repo runs (see the `environment` rule). The set of checks MUST be consistent across this skill (the AI), CI (`.github/workflows/ci.yml`, which calls the same make targets), and the Makefile — and the Makefile is authoritative.

- Run the checks the make targets actually run, and **only** those. Do not run out-of-band tools (mypy, PyMarkdown, a coverage gate) that no target enables.
- Treat the commands in this skill as a description of the targets. When the Makefile and this skill disagree, follow the Makefile (`make help` lists every target).
- If you believe a check should be added or removed, change it in the Makefile first (and keep CI in step with it in the same change), rather than running an out-of-band check from the skill.

## Quick Start

1. Start Postgres (`make up`) and point `DATABASE_URL` at this branch's database (see `CLAUDE.md`).
2. Run all checks: `make lint test check docs audit`.
3. Review output for errors and warnings.
4. Fix any issues found.
5. Re-run checks to verify fixes.

## Check Commands

Run from the **project root**. The targets run Python tools through `uv run` inside the project virtual environment (`uv sync` creates it) and frontend tools through `npm` in `frontend/` (`npm ci` installs them); nothing needs activating by hand.

```bash
make lint test check docs audit     # everything a PR must pass
```

### Code (`make lint`)

```bash
make lint-backend    # ruff check, ruff format --check
make lint-frontend   # tsc --noEmit, eslint --max-warnings 0, prettier --check
```

`make format` applies the ruff and Prettier fixes.

### Tests (`make test`)

```bash
make test-backend    # pytest: filterwarnings = error, --strict-markers, --strict-config
make test-frontend   # vitest
```

The backend suite runs against Postgres, so it needs `make up`. Run a single file with `uv run pytest backend/tests/test_<feature>.py -x`.

### Django and build checks (`make check`)

```bash
make check-backend   # manage.py check --fail-level WARNING; makemigrations --check --dry-run
make check-deploy    # manage.py check --deploy --fail-level WARNING
make check-frontend  # production build (npm run build)
```

Both `check-backend` commands run with `caldart.settings.test`. `check-deploy` runs with `caldart.settings.prod` under a throwaway environment the Makefile recipe sets inline, and names every tag Django's deployment-only checks carry (`security`, `caches`, `async_support`, `mail`).

### Documentation (`make docs`)

```bash
make docs            # sphinx-build -n -W
```

Warnings are treated as errors (`-W`), and nitpicky mode (`-n`) reports every cross-reference that doesn't resolve.

### Dependency audit (`make audit`)

```bash
make audit-backend   # uv audit against uv.lock
make audit-frontend  # npm audit in frontend/
```

Both query advisory databases, so they need network access.

### End-to-end (`make e2e`, opt-in)

`make e2e` runs the Playwright flows against their own database and server. It is the slow, environment-dependent tier: run it locally when a change touches those flows. CI always runs it.

## Execution Workflow

```
Check Progress:
- [ ] Postgres up (make up) and a per-branch DATABASE_URL
- [ ] make lint (ruff check, ruff format --check, tsc, eslint, prettier)
- [ ] make test (pytest, vitest)
- [ ] make check (Django system checks, missing migrations, production build)
- [ ] make docs (sphinx-build -n -W)
- [ ] make audit (uv audit, npm audit)
- [ ] make e2e, if the change touches the end-to-end flows
- [ ] All errors fixed
- [ ] Re-verify all checks pass
```

### Step 1: Run Checks

Run the targets above. `make` stops at the first failing command; add `-k` (`make -k lint test check docs audit`) to see every failure in one pass. Fix any non-zero exit codes.

### Step 2: Analyze Results

- **Errors**: Must be fixed (non-zero exit).
- **Warnings**: Warnings fail the gates too. pytest turns every warning into an error, ESLint allows zero warnings, Django system checks fail at `WARNING`, and Sphinx runs with `-n -W`. Fix the cause; add a narrowly-scoped ignore only for a third-party warning you cannot fix, with a comment explaining why (see `python_testing`).

Common error types:

| Check | Error pattern | Typical fix |
|-------|---------------|-------------|
| ruff | `F401` unused import | Remove import |
| ruff | `DJ008` model does not define `__str__` | Add the method the Django rule names |
| ruff format | `Would reformat: <file>` | Run `make format` |
| tsc | `TS2322` type not assignable / `TS18048` possibly `undefined` | Fix the type or narrow it (`noUncheckedIndexedAccess` is on) |
| eslint | `react-hooks/exhaustive-deps` | Add the missing dependency or restructure the effect; do not suppress |
| eslint | `@typescript-eslint/consistent-type-imports` | Move the type into a separate `import type` |
| prettier | `Code style issues found` | Run `make format` |
| pytest | `FAILED` / `ERROR` | Fix test or code under test |
| pytest | A warning raised as an error (`DeprecationWarning`, `RuntimeWarning`, ...) | Fix our code; for an unfixable third-party warning add a narrow `filterwarnings` entry with a comment |
| pytest | `'<name>' not found in markers configuration option` | Register the marker in `[tool.pytest.ini_options] markers` |
| pytest | `Unknown config option` | Fix the key in `[tool.pytest.ini_options]` |
| pytest | `OperationalError` connecting to Postgres | `make up`; check `DATABASE_URL` |
| manage.py check | `(<app>.W<nnn>) ...` | Fix the setting, model, or field it names |
| makemigrations --check | `Migrations for '<app>':` | Generate the migration (see below) |
| npm run build | Vite/Rollup error | Fix the import or syntax error it names |
| sphinx | `undefined label` / `unknown document` | Fix the `:ref:` / `:doc:` target |
| sphinx | `reference target not found` (nitpicky) | Fix the reference; Python roles cannot resolve here (no autodoc), so use an inline literal (see `doc_python`) |
| uv audit | Package, version, and advisory ID | Raise the minimum version in `pyproject.toml`, or `uv lock --upgrade-package <pkg>` when the range already allows the fixed version |
| npm audit | Package, severity, and advisory URL | `npm audit fix` within existing ranges, or raise the range in `frontend/package.json` (see below) |

### Step 3: Fix Issues

For each error: read the message, open the file and line, apply the fix. Re-run the failing target to confirm.

### Step 4: Re-verify

Run `make lint test check docs audit` again; every target should exit 0.

## Common Fixes Reference

### Missing migration

After editing a model, run `make makemigrations`. This is a prototype (see `CLAUDE.md`, "No backwards compatibility"): when a model change revises a migration that has not shipped anywhere, edit the model and regenerate that migration rather than stacking a fix-up migration on top.

### A warning that fails pytest

Fix the warning at its source when it comes from our code. When it comes from a third-party package and nothing we call can avoid it, add a narrow entry after `"error"`:

```toml
filterwarnings = [
    "error",
    # <package> emits this from <module> on import; no call of ours can avoid it.
    "ignore:<message regex>:DeprecationWarning:<module>",
]
```

### npm audit

- `npm audit fix` upgrades within the ranges in `package.json` and is safe to try first.
- NEVER run `npm audit fix --force` blindly. It applies breaking changes, including downgrades: for an advisory against vitest it proposed installing vitest 2.0.5. Read the advisory, upgrade the affected package deliberately, then re-run `make test lint check`.

## Success Criteria

All checks pass when:

- `ruff check` → All checks passed!
- `ruff format --check` → files already formatted, none to reformat
- `tsc --noEmit` and `eslint --max-warnings 0` → no output, exit 0
- `prettier --check` → All matched files use Prettier code style!
- `pytest` and `vitest` → all tests pass, no warnings
- `manage.py check --fail-level WARNING` → System check identified no issues
- `makemigrations --check --dry-run` → No changes detected
- `npm run build` → exit 0
- `sphinx-build -n -W` → build succeeded, exit 0
- `uv audit` → no known vulnerabilities, exit 0
- `npm audit` → found 0 vulnerabilities
