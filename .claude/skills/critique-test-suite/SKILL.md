---
name: critique-test-suite
description: Analyze the backend test suite for consistency, completeness, redundancy, parallel safety, and assertion quality. Produces a comprehensive report (no test modifications). Use when the user asks to critique tests, review the test suite, or generate a report for fixing tests.
---

# Critique Test Suite

Analyze all backend tests and produce a **report only**—do not modify any test files. The report is intended to be used as a prompt for an AI agent (or developer) to fix the tests later.

## Scope

- **Tests:** All files under `backend/tests/` (pytest + pytest-django, running against Postgres).
- **Fixtures:** Include `backend/tests/conftest.py` (shared fixtures such as `api_client`, `user_factory`, the per-role fixtures, and the plan/dart/aircraft fixtures) and `backend/tests/factories.py` (factory_boy factories) in the analysis.
- **Code under test:** The Django apps in `backend/apps/<app>/` and the project package `backend/caldart/`.
- **Specification:** `PLAN.rst` is the authoritative spec; §15 lists what the backend suite must cover.
- **Out of scope unless the user asks:** the frontend vitest tests (`frontend/src/**/*.test.tsx`) and the Playwright specs (`frontend/e2e/`). When asked, critique them against `javascript_typescript_best_practices` instead.

## Project rules

Treat the rule files in `.claude/rules/` as the authoritative standard and cite them by filename in findings:

- `python_testing.md` — the **primary** standard for this critique (pytest usage, test layout, fixtures, parametrization, markers, TDD, hygiene). Map the checklist items below to it wherever they overlap.
- `python.md` — general coding standards that apply to test code as well (naming, type annotations, docstrings, DRY, line length).
- `security.md` — the input-validation and secrets standards the security checks (section 8) validate against.

If a referenced rule file does not exist, ignore the corresponding part of the critique instead of inventing a standard.

## Checklist for Analysis

Apply these criteria when reviewing each test file and each test case.

### 1. Return values and assertions

- **Explicit values:** Assert exact expected values where known (e.g. `assert result == expected`, not just `assert result` or `assert result is not None`).
- **Dynamic values:** When the value is dynamic (IDs, timestamps), assert **type** and **format** (e.g. regex, enum membership) rather than only existence.
- **Collections:** Prefer asserting **exact length** (e.g. `assert len(items) == 2`) when the expected count is known; avoid only `assert len(items) >= 1` unless the count truly varies.
- **Shape:** For dicts, API responses, or structured return values, assert expected keys or shape where the contract is defined (PLAN §6 defines the API contract, including the `{count, next, previous, results}` pagination envelope).

### 2. Success and failure conditions

- **Success paths:** Every behavior under test should have at least one test that asserts the happy-path result (return value, response, or side effect).
- **Failure paths:** For each operation, consider: invalid input (400 from serializer validation), unauthenticated (401/403), wrong role (403), missing objects (404), domain-specific errors. Note missing failure cases in the report.
- **Permission matrix:** PLAN §15 requires every endpoint × role combination to be covered at least for allow/deny against the matrix in PLAN §5. Note endpoints or roles without allow/deny tests.
- **Edge cases:** Empty collections, None/optional values, boundary values (min/max length, zero, negative where invalid, edge dates for membership status).

### 3. Consistency

- **Naming:** Test names should follow a consistent style (e.g. `test_<action>_<condition>_<expected>` or `test_<function>_returns_<value>_when_<condition>`).
- **Structure:** Similar units (e.g. endpoints in the same app) should have similar test structure (success, validation error, permission denial, edge case).
- **Fixtures:** Same concepts (e.g. "a member with a current membership") should be reused via fixtures and factories; avoid duplicating setup logic.
- **Assertion style:** Prefer one logical assertion per concept; group related assertions consistently across files.

### 4. Completeness

- **Coverage map:** For each app or API area, list which behaviors are tested and which are missing.
- **Parameters:** Arguments, query parameters, and filters that affect behavior should have at least one test (valid and, where relevant, invalid).
- **Specification:** Note gaps between `PLAN.rst` (especially §6 and §15) or docstrings and the tests.

### 5. Redundancy

- **Duplicate coverage:** Identify tests that assert the same behavior in the same way; suggest merging or removing duplicates.
- **Overlap:** Note tests that are subsets of others (e.g. one test checks the status code only, another checks status code and body for the same case).
- **Fixtures:** Flag repeated inline setup that could be a shared fixture or factory.

### 6. Parallel execution

- **Isolation:** Tests must not depend on global state, shared mutable objects, or execution order. Note any use of module/class-level mutable state or singletons.
- **Resources:** Note any shared files, caches, or external services that could make tests flaky or collide between branches running at the same time (each branch has its own database, `test_caldart_<slug>`, but shares the Postgres and Mailpit containers).
- **Database:** pytest-django wraps each test in a transaction that is rolled back. Note tests that bypass it (`django_db(transaction=True)`, `live_server`, raw connections) and commit data that could leak into other tests.

### 7. Mocking and dependency isolation

- **External services:** Stripe, PayPal, and any other HTTP calls should be mocked in unit tests (`respx` for `httpx`; PLAN §15); note tests that make real external calls.
- **Time-sensitive logic:** Tests involving `timezone.now()`, `date.today()`, or expiration (membership status, reminders) should freeze time (`freezegun`) for determinism.
- **Pure logic:** Unit tests for pure business logic should not require a database or network; note functions that could be unit-tested but only have integration tests.
- **Environment variables:** Tests should not depend on real `.env` or env values; note tests that would fail with different env configs. Use the `settings` fixture to override Django settings.
- **Patch target location:** `mock.patch` must target where the name is *looked up*, not where it is *defined*. The Stripe provider does `from apps.payments.services import mark_succeeded`, so a test stubbing it for the provider patches `apps.payments.providers.stripe.mark_succeeded`, not `apps.payments.services.mark_succeeded`. Note patches that target the wrong module.
- **`monkeypatch` vs `mock.patch` usage:** Prefer a consistent default per test file, but allow either tool where it is the clearer fit (e.g., env/process state with `monkeypatch`, call assertions/spies with `mock.patch`). Flag only inconsistent usage that reduces clarity.
- **Patch scope:** Decorator-level `mock.patch` applies for the whole test; context-manager form limits scope. Note patches broader than needed or too narrow (missing setup/teardown).
- **Mock return values:** Mocks that return `MagicMock()` by default can hide type bugs (a function expected to return `str` returns a `MagicMock` and downstream code doesn't fail because it's truthy). Note mocks in critical paths without explicit `return_value` or `side_effect`.

### 8. Security and input validation

- **Input validation:** Endpoints and forms that accept user or external input should have tests for invalid input (wrong type, out-of-range, malicious patterns). Note missing validation tests.
- **Server-computed values:** Amounts, prices, and roles must come from the server; note missing tests that a client-supplied amount or role is ignored or rejected.
- **Webhooks:** Payment webhooks should have tests for signature verification and replay/idempotency (PLAN §15).
- **Sensitive data:** Verify that tests do not log or assert on real secrets; test data should not contain real credentials. Note any exposure risk.
- **Path traversal / injection:** If the code handles paths (backup, restore, exports) or structured input, note missing tests for path traversal or injection where relevant.

### 9. Parameterization and data-driven tests

- **`@pytest.mark.parametrize`:** Similar test cases (e.g. multiple invalid inputs, one role per case) should be parameterized instead of copy-pasted; note repeated test bodies that differ only in input.
- **Boundary values:** For numeric, date, or length-sensitive fields, test min, max, and off-by-one values; note missing boundary tests.
- **Factories:** Test data should be created via factories or fixtures where it reduces duplication or collision risk; note tests with hard-coded values that could be shared.

### 10. Async (if the project uses async)

- **Async fixtures:** Fixtures returning async resources should use `@pytest_asyncio.fixture`; note misuse or sync fixtures in async test files.
- **Timeouts:** Long-running async operations should have explicit timeouts in tests; note tests that could hang.
- **Isolation:** For code that modifies shared state, note whether concurrent access is tested if relevant.

### 11. Output and contract

- **Return shape:** Where the API or a service defines a return shape (serializer output, dataclass, TypedDict), tests should assert that shape or key fields; note tests that only spot-check.
- **Exceptions:** Verify that documented or expected exceptions are raised with correct types; note tests that only check "no exception" without testing failure paths.
- **Exception message contents:** When testing exceptions that have defined messages (e.g. validation errors), tests must assert on the **contents** of the exception message or error body, not only that the exception was raised or the status code. Use `pytest.raises(SomeError) as exc_info` and assert on `str(exc_info.value)`. Note tests that only check exception type.

### 12. Error handling and messages

- **Error specificity:** Different error conditions should be distinguishable (e.g. by exception type, status code, or message); note tests that only check "an exception was raised" without verifying which one.
- **Exception propagation:** For unit tests of code that raises, verify that exceptions are raised with correct types and messages; note missing exception tests.
- **Message assertion:** When exceptions have defined messages, assert on message content (e.g. `pytest.raises(...) as exc_info`, then `assert "expected substring" in str(exc_info.value)`).

### 13. State and workflow

- **State transitions:** For code with status or lifecycle (membership status, payment status, checkout → confirm → activation), test valid and invalid transitions; note missing transition tests.
- **Idempotency:** Operations that should be idempotent should be tested for repeated calls (PLAN §15 names payment success and the seed commands); note missing idempotency tests.
- **Side effects:** Actions that trigger side effects (emails, reminder logs, file writes) should verify those occur; note untested side effects.

### 14. Test data and fixtures

- **Realistic data:** Test data should be realistic enough to catch edge cases (e.g. Unicode names, long strings); note tests using only trivial data.
- **Cleanup:** Tests that create external resources (files, temp dirs) must clean up; note tests that leak state.
- **Fixture scope:** Fixtures should use the narrowest appropriate scope (`function` > `class` > `module` > `session`); note overly broad scopes that could cause isolation issues.
- **Conftest hierarchy:** Shared fixtures live in `backend/tests/conftest.py`; a fixture used by only one test file belongs in that file. Note fixtures in the wrong place and fixtures duplicated across files that belong in conftest.
- **Autouse fixtures:** `@pytest.fixture(autouse=True)` hides dependencies — a test silently depends on setup it doesn't request. Note autouse fixtures and whether they're justified (e.g. DB cleanup is reasonable; injecting test data for every test is not).
- **Fixture depth:** Deep fixture-depends-on-fixture chains (3+ levels) are hard to trace and debug; note such chains.

### 15. Flakiness indicators

- **Time-based assertions:** Tests asserting on wall-clock time are flaky; note and suggest freezing time.
- **Order dependence:** Tests that pass only when run in a specific order indicate shared state; note such patterns.
- **External dependencies:** Tests depending on network, file system state, or external services are flaky in CI; note and suggest mocking.
- **Random data:** Tests using `random`, `uuid4`, or Faker-generated values for assertions without seeding are non-deterministic; note and suggest seeding or fixed values.

### 16. Regression and documentation

- **Bug reference:** Tests written to reproduce bugs should reference the issue in a comment; note regression tests that lack context.
- **Spec alignment:** Tests should map to documented behavior (`PLAN.rst`, docstrings); note tests for undocumented behavior or missing tests for documented behavior.
- **Deprecation warnings:** If deprecated APIs exist, tests should verify warnings are emitted using `pytest.warns(DeprecationWarning)` (or `FutureWarning`). Note deprecated APIs that lack warning-emission tests.
- **`filterwarnings` configuration:** `pyproject.toml` sets `filterwarnings` with `"error"` first. Check that every later `ignore::` entry is narrowly scoped to third-party code and carries a comment explaining why.
- **Warning noise:** Note warnings suppressed inside tests (`warnings.catch_warnings`, `pytest.mark.filterwarnings`) without a reason.

### 17. Other good practices

- **Independence:** Each test should be runnable in isolation; document any hidden dependencies (e.g. "must run after X").
- **Clarity:** Test names and docstrings should describe intent; report tests whose purpose is unclear.
- **Speed:** Note slow tests (e.g. many I/O calls, sleeps, PDF rendering in loops) that could be sped up with mocks or smaller scope.
- **Assertion messages:** Use clear messages where it helps (e.g. `assert x == y, f"Expected {x} to equal {y}"`); note assertions that would be hard to debug on failure.
- **Single responsibility:** Each test should verify one behavior; note tests that assert unrelated things or have multiple "acts".
- **Arrange-Act-Assert:** Tests should follow AAA pattern; note tests with interleaved setup and assertions.
- **Keep test logic minimal:** Avoid complex control flow in tests. Simple loops and branching are acceptable when they improve clarity (e.g., table-driven checks); flag only logic that obscures intent or masks failures.

### 18. Code coverage

- **Target:** At least 90% line coverage for the code under test. No gate enforces it; report against it.
- **Scope:** Coverage should cover almost all non-exception lines; exception branches may be excluded from the percentage but should still be tested where they represent distinct behavior.
- **Measurement:** `pytest-cov` is not a project dependency, so measure ad hoc over the **entire suite** (not a subset): `uv run --with pytest-cov pytest --cov=backend --cov-report=term-missing`. Postgres must be up (`make up`). Note if 90% is met.
- **Report:** List apps or modules below the target or with significant uncovered non-exception lines (ignore `migrations/`).

### 19. Pytest markers and registration

- **Marker registration:** All custom marks must be registered in `pyproject.toml` under `[tool.pytest.ini_options] markers = [...]`. `--strict-markers` is enabled, so an unregistered mark fails the run; note any marks used that the config does not describe clearly.
- **`--strict-config`:** Check that it is still enabled so config typos fail fast.
- **`xfail` audit:** `@pytest.mark.xfail` should document a known issue with a linked ticket and use `strict=True` where the failure is expected to persist. Note `xfail` tests that now pass (missing `strict=True`) or that lack an issue reference — they may be masking real bugs.
- **`skip`/`skipif` audit:** Check whether skip conditions are still valid (e.g. a skip for a frontend build that CI always produces). Note stale skips.
- **Categorization marks:** Note whether slow tests are marked so developers can run fast subsets (`pytest -m "not slow"`). If all tests run at the same speed this is not needed, but if some tests are noticeably slower, suggest marking them.

### 20. Test boundary (public API vs internals)

- **Importing private names:** Tests that import `_`-prefixed modules, classes, or functions are tightly coupled to implementation details and break on refactors. Note such imports.
- **Testing through the public surface:** For this app the public surface is the HTTP API (exercised through the `api_client` fixture) and each app's service functions (`apps/<app>/services.py`). Tests that only exercise internals give false confidence — the API could be broken while internal tests pass. Note areas where only internals are tested.
- **Over-mocking:** Tests that mock so many internals that they're testing the mock setup, not the code. Note tests where more than half the function's collaborators are mocked, especially if the function under test is small.

### 21. Logging assertions

- **`caplog` usage:** Code that logs errors, warnings, or important info (e.g. the payment providers) should have tests verifying log output via `caplog`. Note `log.error()` or `log.warning()` calls that have no corresponding `caplog` assertion in tests.
- **Log level verification:** When testing logged output, verify the message is at the expected level (e.g. an error condition logs at `ERROR`, not `INFO`). Note tests that check message text but not level.
- **Absence of logging:** Some code paths should explicitly *not* produce warnings or errors during normal operation. Note where this is important but untested.

### 22. Pytest configuration

- **`pyproject.toml` `[tool.pytest.ini_options]`:** Check that `testpaths`, `pythonpath`, and `DJANGO_SETTINGS_MODULE` are set so a bare `uv run pytest` works. Check `python_files`, `python_classes`, `python_functions` if non-standard naming is used.
- **Plugin inventory:** Note installed pytest plugins that are unused (slow startup) and useful plugins that are missing (e.g. `pytest-xdist` for parallelism, `pytest-randomly` for order-independence testing).
- **`addopts`:** Are default options sensible (`--strict-markers`, `--strict-config`, `-ra`)?
- **Config conflicts:** Note if a `pytest.ini`, `setup.cfg`, or `conftest.py`-level config competes with `[tool.pytest.ini_options]` in `pyproject.toml`.

### 23. Snapshot and golden-file testing

- **Complex output:** Functions that return large dicts, serialized formats (JSON, CSV), or rendered output (PDF reports, emails) are hard to assert inline. Note where snapshot testing (e.g. `syrupy`) would be more maintainable than dozens of field-level assertions.
- **Golden file management:** If snapshot or golden files exist, check: are they committed to the repo? Is there a CI step to detect stale snapshots? Note missing update procedures.
- **Over-use:** Snapshot tests can become "approve and forget." Note if snapshots are used extensively but there is no evidence of intentional review on change.

## Output: Report Format

Produce a single markdown report with the following structure. Do **not** edit any test files; only write the report.

```markdown
# Test Suite Critique Report

**Generated:** [date]
**Scope:** backend/tests/ (conftest.py, factories.py)

## Executive summary
- Overall assessment (strengths, main gaps).
- **Coverage:** At least 90% and almost all non-exception lines; measured by running the **entire test suite** with `uv run --with pytest-cov pytest --cov=backend --cov-report=term-missing`. Note if met.
- **Permission matrix:** Whether every endpoint × role is covered for allow/deny (PLAN §5, §15).
- **Exception messages:** When testing exceptions with defined messages, tests must assert on message contents (e.g. `pytest.raises(...) as exc_info`, `str(exc_info.value)`), not only that the exception was raised.
- High-priority fixes vs. nice-to-have.

## 1. Return values and assertions
[Existence-only asserts; exact length vs >=; shape checks.]

## 2. Success and failure conditions
[Per app/area: what's tested, what's missing (validation, permissions, exceptions, edge cases).]

## 3. Consistency
[Naming, structure, fixture usage, assertion style.]

## 4. Completeness
[Coverage map; PLAN.rst/docstring gaps.]

## 5. Redundancy
[Duplicate or overlapping tests with file:test references.]

## 6. Parallel execution
[Global state, order dependence, shared resources, committed data.]

## 7. Mocking and dependency isolation
[Real external calls, time-sensitive tests, env dependencies, patch targets, mock return values.]

## 8. Security and input validation
[Missing validation tests, server-computed values, webhooks, sensitive data, injection/traversal.]

## 9. Parameterization
[Tests that could be parameterized; missing boundary tests.]

## 10. Async (if applicable)
[Async fixture issues, timeouts, isolation.]

## 11. Output and contract
[Return shape, exception types, message assertions.]

## 12. Error handling
[Error specificity; exception message content assertions.]

## 13. State and workflow
[Transitions, idempotency, side effects.]

## 14. Test data and fixtures
[Realistic data, cleanup, fixture scope, conftest placement, autouse, fixture depth.]

## 15. Flakiness indicators
[Time, order, external deps, randomness.]

## 16. Regression and documentation
[Bug references, spec alignment, deprecation warnings, filterwarnings entries.]

## 17. Other
[Clarity, speed, assertion messages, AAA, logic in tests.]

## 18. Code coverage
[Target 90%; full-suite measurement; apps/modules below target.]

## 19. Pytest markers
[Marker registration, strict options, xfail audit, stale skips, categorization.]

## 20. Test boundary
[Private imports, API/service coverage, over-mocking.]

## 21. Logging assertions
[caplog usage, log level checks, absence-of-logging tests.]

## 22. Pytest configuration
[testpaths, plugins, addopts, config conflicts.]

## 23. Snapshot and golden-file testing
[Complex output candidates, golden file management, over-use.]

## Prompt for an AI agent to fix tests

[Self-contained prompt for an AI to apply the fixes. Include:
- Report sections as context.
- **Coverage:** Measure coverage over the entire suite with `uv run --with pytest-cov pytest --cov=backend --cov-report=term-missing`; ensure at least 90% and cover almost all non-exception lines.
- **Exception messages:** When testing exceptions with defined messages, assert on message contents (e.g. `pytest.raises(...) as exc_info`, `str(exc_info.value)`).
- **Layout:** Keep tests in `backend/tests/test_<feature>.py` and shared setup in `backend/tests/conftest.py` / `factories.py` (see `python_testing.md`).
- Instruction to fix tests according to the report without changing production code.
- Instruction to preserve existing passing behavior and only add/change assertions and test structure.]
```

## Execution steps

1. **Gather:** List all test files under `backend/tests/`, plus `conftest.py` and `factories.py`. Read the pytest config (`[tool.pytest.ini_options]` in `pyproject.toml`) for markers, addopts, and filterwarnings. For plugins, check the `dev` dependency group, the PYTEST_PLUGINS environment variable, and any `pytest_plugins` references in `conftest.py`.
2. **Read:** For each file, read test names, docstrings, assertion patterns (focus on `assert`, response checks, fixtures, marks, `mock.patch`, `monkeypatch`, `respx`, `freezegun`, `caplog`, `pytest.warns`).
3. **Classify:** For each criterion (1–23), note specific file names, test names, and line references or short quotes.
4. **Write:** Produce the full report in the format above, including the "Prompt for an AI agent" section at the end.
5. **Do not:** Change, add, or remove any line in any test, conftest, or factories file.

## When to use this skill

- User asks to "critique the test suite", "review the tests", "analyze tests", or "generate a report to fix tests".
- User wants a "prompt for an AI to fix the tests" based on the current test suite.
