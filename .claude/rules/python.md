---
description: Python coding standards for writing correct, readable, maintainable, and well-tested code in the Django backend.
---

# Python Best Practices

Apply these rules to ALL new and modified Python code. The backend (`backend/`) is a Django 5 +
Wagtail web application, not a published library. **Minimum Python version: 3.12.**

## 1. Naming and Style

- **Maximum line length**: 100 characters. Enforce via Ruff; use editor rulers at 80 and 90 as visual guides.
- **Functions and local variables**: Use `lowercase_with_underscores`.
- **Class names**: Use `TitleCase`.
- **Module-level constants (global variables)**: Use `ALL_CAPS_WITH_UNDERSCORES`.
- **Private names**: Prepend a single underscore for names that are not meant to be used outside their module: private attributes (e.g. `_cache`), module-private global variables, and non-public helper functions (e.g. `_parse_header`).
- **Built-in names**: Do NOT use variable or function names that shadow Python built-ins (e.g. `float`, `filter`, `id`, `list`, `type`). If you must use such a name, append a single underscore (e.g. `filter_`, `type_`).
- **Falsy checks**: Be explicit about what you are testing. Do NOT rely on truthiness when the intent could be ambiguous. Prefer:
  - `if x is None:` for None checks (not `if not x:` when 0 or [] could occur).
  - `if len(seq) == 0:` when you explicitly mean "empty sequence" and other falsy values (0, None) are not possible.
  - For dicts: `if key in d:` then use `d[key]`; avoid `d.get(key)` when you need to distinguish "missing" from "present with a falsy value" unless that is the intent.
- **Explicit checks over exceptions**: Prefer explicit membership or presence checks over catching exceptions for control flow. Example: use `if "a" in b: x = b["a"]` (or a clear `get` with a sentinel) rather than `try: x = b["a"]` / `except KeyError: ...` for normal flow. Use exceptions for genuinely exceptional conditions.

## 2. General Coding

- NEVER include backwards-compatibility code unless explicitly requested.
- ALWAYS keep modules under 1000 lines. Split larger modules into a package with multiple files.
- ALWAYS write simple, clear code; avoid unnecessary complexity.
- NEVER hardcode magic constants. Define them as module-level constants or in Django settings (`caldart/settings/`), reading anything environment-specific from environment variables.
- ALWAYS catch exceptions at the smallest granularity possible. Do NOT wrap large blocks in a single `try`/`except`.
- Let exceptions propagate unless you are adding context, converting to a domain-specific exception (as the payment providers do with `PaymentVerificationError`), or the exception represents a recoverable internal state. When re-raising, use `raise ... from` to preserve the full traceback for debugging.
- Do not let uncaught exceptions escape unlogged. Requests rely on Django/DRF's top-level exception handling rather than broad `try`/`except` in views; management commands raise `CommandError` for failures the operator can act on. In every case, ALWAYS provide full exception information for debugging (e.g. traceback, `raise ... from` when re-raising).
- ALWAYS include meaningful, structured logging that can be disabled or redirected: a module-level `log = logging.getLogger(__name__)`. NEVER use bare `print()` for diagnostic output; management commands write user-facing output with `self.stdout` / `self.stderr`.
- Avoid mutable global variables. If unavoidable, document purpose and limit scope. Prefer module-level constants (ALL_CAPS) or dependency injection.
- ALWAYS prefer comprehensions (list, dict, set, generator) over manual loops when the result is a new collection and the expression remains readable.
- ALWAYS make the minimal changes necessary. NEVER modify code outside the scope of the current task.
- ALWAYS apply DRY. NEVER duplicate code. Place reusable logic in a utility module. Search existing utilities before writing new functions. Parameterize utility functions to increase generality.
- ALWAYS place imports at the top of the file in three alphabetically-sorted groups separated by a blank line: (1) standard library, (2) third-party, (3) local project (`caldart`, `apps`). When adding new code or tests, add new imports to the appropriate group at the top; do not place them adjacent to the new code. Inline imports are permitted only to avoid heavy optional dependencies or import cycles between Django apps.
- Positional parameters are the values a caller naturally supplies together: one logical group, in an obvious order. Usually that is at most three, but four or five positional parameters are correct when they form a single logical unit (e.g. `self, pos_x, pos_y, pos_z`) -- NEVER split such a group with `*` just to satisfy a count. Optional and configuration parameters MUST be keyword-only (after `*`). If the leading logical group is larger than about five parameters, make all parameters (after `self`) keyword-only instead.
- Use the Receive-an-Object, Return-an-Object (RORO) pattern when a function takes or returns more than a few related values: accept a dataclass or TypedDict and return one, rather than long positional tuples.
- NEVER use `getattr` just as a defensive measure if it is guaranteed that the object has the attribute. ALWAYS reference the attribute directly unless there is a specific reason to know the attribute may not be present. NEVER use getattr to reference the result of an `argparse` namespace (or a management command's `options`) when the argument name is a constant string.

## 3. Comments

- ALWAYS write self-documenting code: meaningful names, simple structure, limited nesting.
- NEVER write a comment whose ONLY content is a restatement of the code, a user request, or modification history. A comment must earn its place by describing behavior or rationale the code itself cannot show.
- An issue/ticket number is welcome AS A REFERENCE once a comment already describes the behavior or rationale. Good: `# Cap the tier when the fit is rank-deficient: an unobservable axis is an assumption, not a measurement (#221).` — it explains the behavior and cites the issue for further context. Not acceptable: `# Fix for #221.` — that is only historical.
- ALWAYS include comments that explain the **rationale** behind non-obvious or complex logic.
- ALWAYS preserve existing comments that are still accurate and relevant. Remove or update stale comments.

## 4. Types and Linting

### Types

- ALWAYS annotate all function/method parameters and return values, including `-> None` for functions (and `__init__`) that return nothing.
- Use modern generic syntax (`list[str]`, `dict[str, int]`, `X | None`) for Python 3.12+.

### Ruff

- `ruff` is in the `dev` dependency group.
- ALWAYS run `ruff check` and `ruff format` on the full codebase after changes (`make lint` checks both; `make format` applies fixes). Fix all errors.
- Follow PEP 8 for all formatting and naming conventions.
- Use the project's explicit Ruff rule set in `pyproject.toml` (see Section 7). Do not disable categories that enforce project conventions.

## 5. Docstrings

- ALWAYS include a docstring for every module, class, function, and method.
- Follow **PEP 257** using **Google style**. Use `Parameters:` (not `Args:`).
- Include `Returns:`, `Raises:`, and any important behavioral notes.
- NEVER mention backwards compatibility, a user request, change history, or an issue/ticket number in a docstring. Docstrings are usage documentation, not a place to explain the code's provenance; describe only observable behavior. (Issue references are allowed in inline `#` code comments per Section 3, and in commit messages and PR descriptions. Citing the specification, e.g. `PLAN §10`, is fine.)
- Docstrings MUST be detailed enough to write a black-box test from the docstring alone.
- Wrap docstring text to **90** characters.
- ALWAYS update docstrings when the associated code changes.

## 6. Testing

- All testing standards live in `python_testing` (pytest, fixtures, parametrization, TDD, and
  test hygiene). Tests are first-class code and MUST follow the naming, typing, docstring, and
  DRY rules in this file as well.

## 7. Ruff Rule Categories

`pyproject.toml` enables these categories, excludes `**/migrations/*`, and ignores `B008` and
`DJ001`:

| Code | Source | Purpose |
|------|--------|---------|
| **E**, **W** | pycodestyle | Style and formatting (indent, whitespace, line length). |
| **F** | Pyflakes | Unused imports, undefined names, syntax issues. |
| **I** | isort | Import sorting and grouping. |
| **UP** | pyupgrade | Prefer modern Python (3.12+ syntax). |
| **B** | flake8-bugbear | Common bugs (mutable defaults, assert, loop vars). |
| **DJ** | flake8-django | Django conventions (model `__str__`, form fields, `null` on text fields). |
| **C4** | flake8-comprehensions | Prefer comprehensions over loops where clear. |

**A** (builtin shadowing) and **N** (naming) are not enabled, so those rules in Section 1 are
enforced by review rather than by Ruff. Categories to consider adding: **A**, **N**, **SIM**,
**PT**, **RUF**, **D**/**DOC** (docstrings), **PTH**, **RET**, **PERF**. Enable one only if the
team agrees to fix or ignore the resulting diagnostics.
