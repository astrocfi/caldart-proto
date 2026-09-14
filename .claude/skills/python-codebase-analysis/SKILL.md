---
name: python-codebase-analysis
description: Analyzes the CalDART Django backend and produces high-level recommendations for restructuring, refactoring, and alignment with modern best practices. Use when the user asks to analyze the codebase, audit code quality, suggest improvements, refactoring ideas, or assess maintainability, performance, testability, security, deployment configuration, or technical debt.
---

# Python Codebase Analysis

Produce a structured analysis and recommendations report. Do not implement changes unless the user asks; focus on **high-level findings and actionable suggestions**.

## Workflow

1. **Scope**: Confirm or infer scope (whole backend, one Django app, or a path). Default to `backend/`. The React frontend (`frontend/`) is out of scope unless the user asks; then assess it against `javascript_typescript_best_practices`.
2. **Explore**: Scan layout (apps, key config files), entry points (URLconfs, management commands), tests, docs, and `deploy/`. Use Glob and Grep (or an Explore subagent for broad sweeps); avoid reading every file.
3. **Assess**: Evaluate each dimension below. Note evidence (file paths, patterns) and severity (critical / high / medium / low).
4. **Synthesize**: Write the report using the output template. Prioritize by impact and effort; group related items.

## Dimensions to Assess

### 1. Structure and layout

- App boundaries: each Django app under `backend/apps/<app>/` owns its models, `api/`, `admin.py`, `seed.py`, and management commands; project-level code lives in `backend/caldart/`. Look for circular imports between apps and code that sits in the wrong app.
- File and module size: modules > ~500–1000 lines; single-file "god" modules (e.g. one views module serving every endpoint of an app).
- Naming: consistent with language norms (e.g. Python: lowercase_with_underscores, TitleCase for classes).
- Dead or orphaned code: unused modules, commented-out blocks, unreachable branches, endpoints nothing calls.
- Duplication: copy-paste, similar logic that could be shared (DRY).

**Evidence**: Paths, line counts, import graphs if available.

### 2. Best practices alignment

Compare against project rules (`.claude/rules/python.md`). Check:

- Naming (builtin shadowing, private `_` prefix, ALL_CAPS for module-level constants).
- Explicit checks vs exception-based control flow; falsy checks (`is None`, `len(x) == 0`).
- Imports: top of file, grouped and sorted; no wildcard imports.
- Function shape: ≤3 positional args, keyword-only for the rest. Return an object rather than a tuple of many results.
- Constants: no magic numbers/strings; Django settings or env for tunables.
- Error handling: narrow try/except; no bare except.
- Layering: request validation in DRF serializers and forms (see `security`); thin views; domain logic in each app's `services.py`, as `PLAN.rst` §4 lays out for members and payments.
- Management commands and application code: user-facing command output through `self.stdout` / `self.stderr`, failures through `CommandError`; no `print()` or `sys.exit()` anywhere else; diagnostics through a module-level `logging.getLogger(__name__)`.
- Error message quality: exceptions include enough context to diagnose (`ValueError("x must be positive, got -3")` not `ValueError("bad value")`). Domain exceptions (e.g. the payment providers' `PaymentVerificationError`, `ProviderNotConfigured`) where callers need to tell failures apart. API error responses carry a clear message.
- Encoding and I/O: explicit `encoding='utf-8'` on `open()` calls (platform default varies). Consistent use of `pathlib.Path` over `os.path` string manipulation. Context managers for all files and connections.

**Evidence**: Rule name or quote, example file:line or pattern. Grep for `print(`, `sys.exit`, `sys.stdout`, `open(` without `encoding=`.

### 3. Types and static checks

- Type coverage: annotations on new and modified code (the `python` rule requires them); share of annotated functions; use of `Any`.
- Linting: the Ruff rule set in `pyproject.toml` (see `python` Section 7); consistent formatting (`ruff format`); Django system checks (`manage.py check --fail-level WARNING` in `make check`).
- Docstrings: presence, format (Google style with `Parameters:`), consistency with signatures and behavior.

**Evidence**: Config files, sample of annotated vs unannotated code.

### 4. Testing

- Structure: tests in `backend/tests/test_<feature>.py`, shared fixtures in `backend/tests/conftest.py` and factories in `backend/tests/factories.py` (see `python_testing`); naming (`test_*`).
- Coverage: approximate line/branch coverage (`uv run --with pytest-cov pytest --cov=backend --cov-report=term-missing`, Postgres up); untested apps or critical paths.
- Quality: one assertion per test; no tests that ignore results or swallow exceptions; use of parametrize/fixtures; independence.
- Gaps: missing edge cases, error paths, permission allow/deny cases, or the coverage `PLAN.rst` §15 requires.

**Evidence**: `pyproject.toml` pytest config, coverage output, example test file. For a deep dive, run the `critique-test-suite` skill.

### 5. Performance and resource use

- Queries: N+1 patterns (related objects read per row in serializers, templates, and CSV/PDF exports) without `select_related` / `prefetch_related`; queries inside loops; missing indexes on filtered or ordered fields; unbounded querysets where the `PLAN.rst` §6 pagination (default 25, max 200) should apply.
- Hot paths: unnecessary work in loops, repeated allocations, O(n²) or worse algorithms where it matters.
- I/O: missing timeouts on outbound HTTP (payment providers); large exports built in memory.
- Caching: repeated computation or lookups that could be cached or memoized.
- Dependencies: heavy or unused libraries; optional features that could be lazy-loaded.
- Concurrency and thread safety: module-level mutable state (dicts, lists, caches) shared across requests without locking; lazy-initialized globals that are not thread-safe under the gunicorn workers `deploy/gunicorn.conf.py` configures; reentrancy issues in functions that modify shared state.

**Evidence**: File:line or function name; no profiling required unless user provides data. pytest-django's `django_assert_num_queries` fixture can confirm a suspected N+1. Grep for module-level mutable assignments (e.g. `_cache = {}`, `_registry = []`).

### 6. Maintainability and extensibility

- Coupling: tight dependencies between apps; hard-coded dependencies instead of injection.
- Cohesion: modules/classes with a single responsibility; clear boundaries.
- Extensibility: adding features without editing many files (e.g. the payment provider registry in `apps/payments/providers/`); use of hooks, registries, or strategy-style patterns where appropriate.
- Configuration access: settings read through `django.conf.settings`, with environment variables read only in `caldart/settings/`.
- Documentation quality: README accuracy (make targets, demo accounts, URLs); docs build health (`make docs`, `sphinx-build -n -W`); the hand-written API reference (`docs/developer/api-*.rst`) matches each app's `api/urls.py` and serializers; `PLAN.rst` agrees with the code (`CLAUDE.md`).

**Evidence**: Import structure, example functions or classes. Compare `docs/developer/api-*.rst` against the URLconfs and serializers. Check README commands against the Makefile.

### 7. Security and robustness

- Permissions: every endpoint enforces the role matrix in `PLAN.rst` §5 through its DRF permission classes, plus the object-level rules noted in §6. Note views with no explicit permission classes or with `AllowAny`.
- Input validation: external input (request data, uploads, webhooks, management-command arguments, env) validated at boundaries (DRF serializers, forms); amounts and roles computed on the server.
- CSRF and sessions: session authentication with the CSRF token flow in `PLAN.rst` §6; note `csrf_exempt` outside payment webhooks.
- Webhooks: payment webhook signatures verified where configured; handlers idempotent.
- Secrets: no credentials in code or logs; use of env or secret managers.
- Dependency hygiene: known vulnerable deps (`make audit`); minimum versions with exact pins only in lock files.
- Paths and execution: path traversal risks (backup, restore, exports); subprocess/shell usage and injection.

**Evidence**: Grep for patterns (e.g. `permission_classes`, `AllowAny`, `csrf_exempt`, `password`, `secret`, `eval`, `subprocess` with `shell=True`).

### 8. Dependencies and tooling

- Declared deps: single source of truth (`pyproject.toml` with `uv.lock`; `frontend/package.json` with its lock file); dev tooling in the `dev` dependency group (see `dependency_management`).
- Version policy: minimum versions in `pyproject.toml`, exact pins only in lock files.
- Tooling: consistent formatter and linter; CI (`.github/workflows/ci.yml`) calls the same make targets the Makefile defines (see `environment`). Note any CI step that runs a command no target defines, or a target CI skips.
- Configuration consistency: tool configs in `pyproject.toml` (ruff, pytest) are consistent with each other and with project rules. No stale config sections for tools no longer used (e.g. `[tool.black]` or `[tool.isort]` when ruff handles both). Ruff's `line-length` and `target-version` agree with `requires-python`, `.python-version`, the Prettier `printWidth`, and the rules.

**Evidence**: `pyproject.toml`, `Makefile`, `.github/workflows/ci.yml`. Grep for stale `[tool.*]` sections.

### 9. Technical debt and risk

- Deprecations: use of deprecated Django, Wagtail, or DRF APIs; the `filterwarnings` ignores in `pyproject.toml` that could be hiding our own deprecated calls; the next major versions the upper bounds in `pyproject.toml` hold back.
- Migrations: this prototype regenerates migrations rather than stacking fix-ups (`CLAUDE.md`); note chains of small fix-up migrations or data migrations that no longer serve a purpose.
- Complexity: deeply nested conditionals; long functions; high cyclomatic complexity in critical code (membership status math, checkout, reminders).
- TODOs/FIXMEs: concentration in one area; unlinked or vague items.
- Compatibility: platform assumptions (e.g. paths, encoding, tooling that only works inside the Docker containers).

**Evidence**: Grep for deprecation warnings, TODO/FIXME; example complex function.

### 10. Deployment and configuration

- Settings split: `caldart/settings/base.py`, `dev.py`, `prod.py`, and `test.py`. Each setting is defined once in `base.py` and overridden only where an environment genuinely differs; production defaults are safe (e.g. `PAYMENTS_MOCK_ENABLED` is off unless the environment turns it on).
- Environment variables: every variable read through django-environ appears in `.env.example` (and in the `PLAN.rst` §14 list); required ones fail fast with a clear error.
- Production audit: `uv run backend/manage.py check --deploy` is clean under `caldart.settings.prod` with the real environment file (`docs/developer/configuration.rst`).
- Static files: whitenoise serves the `collectstatic` output (`backend/staticfiles/`), including the Vite bundle from `frontend/dist`; django-vite dev mode is off in production.
- `deploy/`: `gunicorn.conf.py`, the systemd units (`caldart-web.service`, `caldart-reminders.service` and `.timer`), and the Apache and nginx configs agree with the settings (ports, paths, environment file, static root) and with the management commands they run.
- Operations: backups (`make backup` / `db_backup`) and the health command (`manage.py health`) cover what an operator needs.

**Evidence**: Settings modules, `.env.example`, files under `deploy/`, `check --deploy` output. Compare `env(...)` reads against `.env.example`.

## Output template

Use this structure for the report. Omit sections with no findings; keep each item concise with location and suggested direction.

```markdown
# Codebase analysis: [project or path]

## Summary
[2–4 sentences: overall health, top 2–3 priorities.]

## 1. Structure and layout
- **Finding**: [what]. **Evidence**: [where]. **Suggestion**: [action].
[Repeat as needed.]

## 2. Best practices alignment
[Same pattern; reference project rules if present.]

## 3. Types and static checks
...

## 4. Testing
...

## 5. Performance and resource use
...

## 6. Maintainability and extensibility
...

## 7. Security and robustness
...

## 8. Dependencies and tooling
...

## 9. Technical debt and risk
...

## 10. Deployment and configuration
...

## Recommended priorities
1. [Highest impact, feasible first step]
2. [Next]
3. [Next]
```

## Severity and wording

- **Critical**: Security or data integrity risk; blocks testing or deployment; pervasive violation of a core rule.
- **High**: Significant maintainability or bug risk; large refactor needed if left as-is.
- **Medium**: Clear improvement; can be scheduled with normal work.
- **Low**: Nice to have; style or minor consistency.

Use "Consider…", "Prefer…", "Avoid…" for suggestions. For critical/high, state the impact (e.g. "increases risk of…", "makes testing difficult because…").

## Project-specific rules

Treat the rule files (`.claude/rules/*.md`, always loaded) and standards skills (`.claude/skills/<name>/SKILL.md`, loaded on demand) as the authoritative standard for the matching dimension. When a finding reinforces or contradicts a rule, cite the rule or skill by name; prefer referencing the rule file over repeating its text.

| Dimension(s) | Rule file(s) / skill(s) |
|--------------|--------------|
| 1 Structure and layout, 2 Best practices alignment, 3 Types and static checks, 9 Technical debt | `python.md` |
| 4 Testing | `python_testing.md`; or run the `critique-test-suite` skill for a deep test audit |
| 6 Maintainability (documentation quality) | `doc_python.md`; skills `doc-readme`, `doc-user-guide`, `doc-dev-guide`, `doc-how-to` — or run the `critique-documentation` skill for a deep documentation audit |
| 7 Security and robustness | `security.md` |
| 8 Dependencies and tooling, 10 Deployment and configuration | `dependency_management.md`, `environment.md` |
| Process (commits, pull requests, bug reports) | skills `git-workflow`, `pull-request`, `bug-report` |
| Frontend (only when the user asks) | `javascript_typescript_best_practices.md` |

If a referenced rule file does not exist, skip the corresponding part of the analysis rather than inventing a standard or reporting the rule's absence as a finding.

## Reference

For example findings and severity phrasing, see [reference.md](reference.md).

## Scope and depth

- Prefer breadth first: touch all dimensions, then go deeper only where impact is high or the user asks.
- For large codebases, sample by app or layer (e.g. models and services vs API vs management commands vs tests) and call out areas not reviewed.
- If the user asks for "quick" or "high-level" analysis, limit to summary + 1–2 findings per dimension and a short priority list.
