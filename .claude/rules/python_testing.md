---
description: Testing standards for the Django backend — pytest, fixtures, parametrization, TDD, and test hygiene.
---

# Python Testing

Apply these rules to ALL backend tests. They complement `python` (the same naming, typing,
docstring, and DRY rules apply to test code) and `dependency_management` (test tooling is
declared in the `dev` dependency group and configured in `pyproject.toml`). Tests are
first-class code: hold them to the same standard as the code they exercise. Frontend tests
follow `javascript_typescript_best_practices`.

## 1. Test-Driven Development

- Use **test-driven development**: write the test first, then implement.
  Red -> green -> refactor.
- Derive tests from stated requirements (`PLAN.rst` is the specification) BEFORE
  implementation. If the requirements are unclear, ask rather than guessing.
- Run the new tests to confirm they FAIL for the right reason, then implement,
  re-run, and fix until green.
- After it passes, review the tests and strengthen coverage (edge cases,
  boundaries, error paths) before refactoring.

## 2. Framework and Tooling

- ALWAYS use `pytest` with `pytest-django`. Do not write `unittest.TestCase` classes (including
  Django's `TestCase`) for new tests.
- Run the suite with `uv run pytest` (or `make test-backend`). It needs the Postgres container
  from `make up` and a per-branch `DATABASE_URL` (see `CLAUDE.md`).
- ALWAYS put type annotations on test functions (parameters and `-> None`),
  exactly as on application code.
- ALWAYS write tests that are independent and order-agnostic: no reliance on execution order,
  no shared mutable state between tests, no dependence on artifacts another test produced.

## 3. Layout and Naming

- ALL backend tests live in `backend/tests/` — not in per-app `tests/` packages.
- Name test files `backend/tests/test_<feature>.py` and test functions `test_*`, and keep one
  focused area of behavior per file, so parallel branches never touch the same test file.
- Shared fixtures (`api_client`, `user_factory`, one fixture per role, plan/dart/aircraft
  fixtures) live in `backend/tests/conftest.py`, and the factory_boy factories in
  `backend/tests/factories.py`. Reuse and extend them; do not copy near-identical setup into
  every file.

## 4. Configuration (`pyproject.toml`)

pytest is configured under `[tool.pytest.ini_options]`; do not add separate `pytest.ini` /
`setup.cfg` files.

- `--strict-markers` and `--strict-config` are on, so an unregistered marker or a config typo
  fails fast instead of silently doing nothing. Register every custom marker in a `markers`
  table with a one-line description.
- Warnings are errors (`filterwarnings = ["error"]`). Fix a warning that comes from our own
  code. Add a narrowly-scoped `ignore::` / `default::` entry after `"error"` ONLY for a warning
  from third-party code you cannot fix, with a comment explaining why.
- Separate slow or environment-dependent tests (those needing network, external data, or
  special services) behind a marker and exclude them from the default run via `addopts` (e.g.
  `-m "not <marker>"`), so the default suite stays fast and hermetic and the heavy tier is
  opt-in.

## 5. Fixtures and Isolation

- Prefer pytest fixtures over setup/teardown methods; request them by parameter
  name and scope them (`function`, `module`, `session`) to the broadest reuse
  that is still safe.
- Use the built-in fixtures instead of hand-rolling isolation:
    - `tmp_path` / `tmp_path_factory` for filesystem work — never write into the
      repo or a fixed temp path.
    - `monkeypatch` for environment variables, attributes, and `sys` state — it
      auto-reverts after the test.
    - `settings` (pytest-django) to override Django settings for one test — it
      auto-reverts after the test.
    - `capsys` (or `capfd`) to capture and assert on stdout/stderr.
- If a test must mutate global or class state that no fixture manages, restore
  the original value in a fixture teardown or a `try`/`finally` so it cannot
  leak into other tests.

## 6. Parametrization

- Use `@pytest.mark.parametrize` for table-driven tests instead of looping
  inside one test or copy-pasting near-identical test bodies; each case then
  reports as a separate pass/fail.
- Give parametrized cases readable `ids` when the values alone are not
  self-explanatory.
- Choose distinct inputs across cases to maximize branch coverage, deliberately
  including edge cases and boundary values.

## 7. Assertions and Correctness

- NEVER write a test whose only purpose is to execute a code path without
  asserting on the result. Every test asserts observable correctness.
- Each `assert` MUST check exactly one condition — no `and` joining two checks
  in one assertion (split them so failures pinpoint the cause).
- Assert precise expected values, not ranges, types, or mere existence, unless
  the contract genuinely specifies a range.
- For floating-point results, compare with `pytest.approx` (or an explicit
  tolerance) rather than `==`; state the tolerance when the default is unsuitable.
  Money is integer cents or `Decimal`, compared exactly.
- When testing errors, ALWAYS use `pytest.raises` as a context manager AND
  assert on the exception **message content** (via `match=` or the captured
  value), not just the exception type. For API errors, assert on the status code
  and the response body.
- If two tests drive the same code path but assert on different parts of the
  result, combine them; if one test would need `and` to cover two behaviors,
  split it.

## 8. Mocking and Test Doubles

- Mock or fake genuinely external dependencies (network, clock, filesystem
  beyond `tmp_path`, third-party services such as Stripe and PayPal) so tests are
  deterministic and hermetic; keep a minimal fake defined once in `conftest.py`
  rather than re-mocking in each test. The `dev` group provides `freezegun` for the
  clock and `respx` for `httpx` calls.
- Do NOT mock the code under test or so much of its collaborators that the test
  no longer exercises real behavior. Prefer real objects (including the real test
  database) when they are cheap and deterministic.

## 9. Hygiene and Debugging

- NEVER write a test that passes by ignoring an incorrect result or swallowing
  an exception. If the code is wrong, leave the failing test and explain why.
- Keep test comments to short (1-2 sentence) summaries useful to a future
  maintainer; never include line numbers, verbose rationale, or change history.
- When a test fails, NEVER guess at the cause. Use the traceback, the captured
  output, and targeted assertions. If stuck in a fix loop, revert and re-approach
  from first principles; ask for help when needed.
