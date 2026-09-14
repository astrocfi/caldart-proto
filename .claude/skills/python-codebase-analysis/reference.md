# Codebase analysis – reference

Use this when you need concrete examples for a dimension or wording guidance. The findings below are illustrative: `<app>` and `example` stand for whichever app or module the real finding concerns.

## Example findings (by dimension)

**Structure**
- **Finding**: `apps/<app>/api/views.py` is 1,200 lines and mixes list, detail, export, and admin endpoints. **Evidence**: `backend/apps/<app>/api/views.py`. **Suggestion**: Split into an `api/views/` package by resource (`members.py`, `exports.py`, ...) and keep `api/urls.py` importing from it.
- **Finding**: `apps/aircraft` imports from `apps.members.api.serializers`, and `apps.members` imports back from `apps.aircraft`. **Evidence**: the two import sites. **Suggestion**: Move the shared logic into one app's `services.py` and have the other depend on it one way.

**Best practices**
- **Finding**: Several functions use `except Exception` and pass, hiding failures. **Evidence**: `backend/apps/<app>/services.py` lines 45, 89. **Suggestion**: Catch specific exceptions, log with `log.exception`, and re-raise or return a sentinel where appropriate.
- **Finding**: A view computes the charge amount and activates the membership inline instead of calling the service. **Evidence**: `backend/apps/<app>/api/views.py` `confirm()`. **Suggestion**: Move the domain logic into `services.py` (as `PLAN.rst` §4 lays out) so the view only validates, calls, and responds.

**Best practices – management commands and logging**
- **Finding**: A management command uses `print()` for progress and `sys.exit(1)` on bad arguments. **Evidence**: `backend/apps/<app>/management/commands/example.py` lines 12, 40. **Suggestion**: Write output with `self.stdout.write(...)` and raise `CommandError("...")` so Django reports the failure and exits non-zero.
- **Finding**: A module calls `logging.basicConfig()` at import time. **Evidence**: `backend/apps/<app>/example.py` line 5. **Suggestion**: Remove it; use a module-level `log = logging.getLogger(__name__)` and leave handler configuration to Django's `LOGGING` setting.

**Best practices – error messages**
- **Finding**: Exceptions raised with no context: `raise ValueError("invalid input")`. **Evidence**: `backend/apps/<app>/services.py` lines 30, 55. **Suggestion**: Include the actual value and constraint: `raise ValueError(f"amount must be positive, got {amount}")`.
- **Finding**: Callers cannot tell a misconfigured provider from a declined payment because both raise `RuntimeError`. **Evidence**: grep for `raise RuntimeError` under `apps/payments/`. **Suggestion**: Raise the domain exceptions (`ProviderNotConfigured`, `PaymentVerificationError`) so the API can answer 400 vs 402/409 appropriately.

**Best practices – encoding and I/O**
- **Finding**: `open()` calls omit `encoding`; relies on platform default. **Evidence**: `backend/apps/<app>/management/commands/example.py` lines 18, 42. **Suggestion**: Add `encoding='utf-8'` (or the appropriate encoding) to all `open()` calls.

**Types**
- **Finding**: Service functions in `apps/<app>/services.py` have no parameter or return annotations, although other apps' services are annotated. **Evidence**: `def` lines without `->` in that module. **Suggestion**: Annotate them the next time they change, as the `python` rule requires for new and modified code.

**Testing**
- **Finding**: Coverage is ~45% for `apps/<app>/`; the CSV export has no direct tests. **Evidence**: `uv run --with pytest-cov pytest --cov=backend --cov-report=term-missing`; no `backend/tests/test_<app>_exports.py`. **Suggestion**: Add tests for the export's content and filters; aim for ≥90%.
- **Finding**: No test checks that a `member` is refused the admin list endpoint. **Evidence**: `backend/tests/test_<app>_api.py` covers only the allowed role. **Suggestion**: Parametrize allow/deny over every role in the `PLAN.rst` §5 matrix.

**Performance**
- **Finding**: The member list endpoint issues one query per row for the member's DART and current membership. **Evidence**: the serializer's method fields in `apps/<app>/api/serializers.py`; the queryset in the view has no `select_related`. **Suggestion**: Add `select_related` / `prefetch_related` to the queryset and pin the count with `django_assert_num_queries` in a test.
- **Finding**: A PDF export loads every payment into memory before rendering. **Evidence**: `backend/apps/<app>/reports.py` `export_pdf()`. **Suggestion**: Iterate the queryset with `.iterator()` or paginate the rendering.

**Performance – concurrency and thread safety**
- **Finding**: Module-level mutable cache `_cache = {}` is written from multiple functions with no locking. **Evidence**: `backend/apps/<app>/example.py` line 8 and functions `register()`, `lookup()`. **Suggestion**: Protect with `threading.Lock`, move the cache to Django's cache framework, or document that it is safe only under single-threaded workers.

**Maintainability**
- **Finding**: `os.environ` is read directly in five modules outside `caldart/settings/`. **Evidence**: grep for `os.environ` / `env(` under `backend/apps/`. **Suggestion**: Read each variable once in settings and import it from `django.conf.settings`.

**Maintainability – documentation quality**
- **Finding**: `docs/developer/api-<app>.rst` documents a `?status=` filter the view no longer accepts. **Evidence**: the page vs the filterset in `apps/<app>/api/`. **Suggestion**: Update the page in the same change as the endpoint (`doc_python`, Change Discipline).
- **Finding**: The README lists a make target the Makefile no longer defines. **Evidence**: `README.rst` "Everyday commands" vs `make help`. **Suggestion**: Keep the README's command list in step with the Makefile.

**Security**
- **Finding**: An endpoint declares no `permission_classes` and relies on the project default. **Evidence**: `backend/apps/<app>/api/views.py` `ExampleView`. **Suggestion**: Declare the permission classes the `PLAN.rst` §5 matrix requires, and add allow/deny tests.
- **Finding**: Subprocess is invoked with `shell=True` and a user-supplied file name. **Evidence**: `backend/apps/<app>/management/commands/example.py` line 67. **Suggestion**: Use list form of arguments and avoid `shell=True`; resolve and validate the path.

**Dependencies**
- **Finding**: A hand-written `requirements.txt` duplicates `pyproject.toml` with different versions. **Evidence**: `requirements.txt` pins `django==5.1.2`; `pyproject.toml` says `django>=5.1,<6.0`. **Suggestion**: Delete it; `pyproject.toml` with `uv.lock` is the single source of truth (`dependency_management`).

**Dependencies – CI/CD consistency**
- **Finding**: CI runs a check in a raw `run:` step that no make target defines. **Evidence**: `.github/workflows/ci.yml` vs `make help`. **Suggestion**: Add the check to a make target and have CI call the target (`environment`).

**Dependencies – configuration consistency**
- **Finding**: Ruff is configured with `line-length = 88` while Prettier's `printWidth` and the project rules say 100. **Evidence**: `pyproject.toml` `[tool.ruff]` vs the Prettier config and `.claude/rules/python.md`. **Suggestion**: Align the line length across tools and rules.
- **Finding**: Stale `[tool.black]` section remains in `pyproject.toml` after migration to Ruff. **Evidence**: `pyproject.toml` line 45. **Suggestion**: Remove the `[tool.black]` section; Ruff format replaces Black.

**Technical debt**
- **Finding**: 40+ TODO comments with no issue links or owners. **Evidence**: `grep -r TODO backend`. **Suggestion**: Link TODOs to issues, or triage and remove obsolete ones.
- **Finding**: An app has six migrations that each adjust one field of a model added in the first. **Evidence**: `backend/apps/<app>/migrations/`. **Suggestion**: Regenerate a single migration for the model, per the prototype's no-backwards-compatibility policy (`CLAUDE.md`).

**Deployment and configuration**
- **Finding**: `STRIPE_WEBHOOK_SECRET` is read in settings but missing from `.env.example`. **Evidence**: `caldart/settings/base.py` vs `.env.example`. **Suggestion**: Add it to `.env.example` with a placeholder and a comment.
- **Finding**: `manage.py check --deploy` under `caldart.settings.prod` reports `security.W004` (`SECURE_HSTS_SECONDS` unset). **Evidence**: command output. **Suggestion**: Set HSTS in `prod.py` once HTTPS is confirmed end to end.
- **Finding**: The nginx config serves `/static/` from a directory `collectstatic` does not write to. **Evidence**: `deploy/nginx/caldart.conf` vs `STATIC_ROOT`. **Suggestion**: Point the alias at `STATIC_ROOT`, or let whitenoise serve static files and drop the alias.

## Severity phrasing

- Critical: "must be addressed before…", "exposes…", "prevents…"
- High: "significantly increases…", "will make it difficult to…"
- Medium: "recommended to…", "would improve…"
- Low: "consider…", "optional:…"

## When project rules exist

- "Per project rule in `.claude/rules/python.md`, …"
- "This conflicts with the project's convention that …"
- "Align with project rule: … (see python.md)."
