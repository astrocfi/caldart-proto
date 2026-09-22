---
description: JavaScript and TypeScript coding standards for correct, readable, maintainable, and well-typed code. Use for all JS/TS in frontend/.
---

# JavaScript / TypeScript Best Practices

Apply these rules to ALL new and modified JavaScript and TypeScript code in `frontend/` (Vite +
React 19 + TypeScript).

## 1. Naming and Style

- **Functions and variables**: Use `camelCase`. Use `SCREAMING_SNAKE_CASE` only for true constants (e.g. config flags, enum-like values).
- **Classes, types, interfaces, and React components**: Use `PascalCase`.
- **Module-internal**: Do not export it. Do not prefix it with an underscore: a leading `_` is reserved for intentionally unused variables and parameters, which ESLint allows. Use `#` private class fields for private class members.
- **Event handlers (UI)**: Prefix with `handle` (e.g. `handleClick`, `handleSubmit`). For callbacks passed as props use `on` (e.g. `onClick`, `onChange`). ESLint's `react/jsx-handler-names` enforces the `handle*` side: whatever value is wired to an `onX` JSX prop — a local function, a destructured prop, a hook's return value — must be named `handle*` at that point, even if that takes a destructuring alias (`onRetry: handleRetry`) or an inline arrow (`onClick={() => signOut()}`).
- **Boolean variables**: Use `is`, `has`, `should`, `can` (e.g. `isLoading`, `hasError`, `shouldRetry`).
- **Maximum line length**: 100 characters, enforced by Prettier. Break long lines at logical points.
- **Falsy checks**: Be explicit. Use `x === null` or `x === undefined` (or `x == null` for both) when that is the intent; avoid relying on truthiness when `0`, `""`, or `false` are valid. For optional chaining prefer `?.` over manual null checks where it improves readability.
- **Immutability**: Prefer `const`; use `let` only when reassignment is needed. Avoid mutating arguments; copy before mutating when necessary. Prefer spread and new arrays/objects over in-place mutation.

## 2. General Coding

- ALWAYS write simple, clear code; avoid unnecessary complexity.
- NEVER include backwards-compatibility code (e.g. for old browsers) unless explicitly requested.
- ALWAYS apply DRY. Extract repeated logic into named functions or shared modules; parameterize to generalize. Check `src/portal/components/` for an existing primitive before writing a new one.
- ALWAYS make the minimal changes necessary. Do NOT refactor or “clean up” code outside the scope of the task.
- Prefer **early returns** and guard clauses over deep nesting. Put the happy path last when it improves readability.
- Prefer **functional style** (pure functions, `map`/`filter`/`reduce`, no side effects in helpers) unless an imperative style is clearly simpler.
- Use **constants** for magic strings and numbers; define them at module scope or in a shared config. Add types for constants.
- Keep **files and functions** focused. Split large files (e.g. > 300–400 lines) into smaller modules. Prefer single responsibility per function.
- **Function ordering**: Place higher-level or orchestrating functions above the helpers they call, or group by concern so the file reads top-to-bottom.

## 3. Types (TypeScript)

- **Strict** mode is on in `tsconfig.json` (plus `noUncheckedIndexedAccess` and `verbatimModuleSyntax`). Keep it on.
- ALWAYS annotate **function parameters and return types** for exported functions. Use inference for obvious local variables.
- Prefer **`interface`** for object shapes; use **`type`** for unions, intersections, and mapped types.
- Avoid **`any`**. Use **`unknown`** when the type is truly unknown and narrow with type guards. Use **`never`** for exhaustive checks.
- Use **discriminated unions** for state or result types (e.g. `{ status: 'loading' } | { status: 'error'; error: Error }`).
- Use **generic constraints** instead of `any` when types are parameterized. Prefer `Record<string, unknown>` over `Record<string, any>` for generic objects.
- API object shapes are declared once in `src/portal/api/types.ts`; use those types rather than redeclaring them. They are held to the backend's OpenAPI schema by `src/portal/api/types.contract.test.ts`, which pairs each interface with its generated component and asserts the two are mutually assignable, so a serializer change the types have not followed fails `tsc --noEmit`. Change an interface only together with the serializer behind it, and regenerate the schema with `npm run schema` (`npm run typecheck` and `npm run test` do it for you). `src/portal/api/schema.d.ts` is generated output: never edit or commit it.
- In **JSDoc**, use `@param`, `@returns`, and `@throws` where they add value; keep types in TypeScript syntax.

## 4. Modules and Imports

- Use **ES modules** (`import`/`export`). Use **named exports** in `src/`; default exports appear only where a tool requires them (e.g. `vite.config.ts`, `eslint.config.js`).
- Import type-only symbols with a separate `import type` statement (ESLint's `consistent-type-imports` and `verbatimModuleSyntax` require it).
- Group imports: (1) standard/library, (2) third-party, (3) local/aliased (`@/…`). Separate groups with a blank line. Sort alphabetically within groups.
- Import a shared component or module by the file that defines it, never through a barrel. `src/portal/components/` has no `index.ts`; name the file (`@/portal/components/Button`), not the directory.
- Stay within the importing feature (`src/portal/features/<feature>/`) with a relative import (`./form`, `./ProfileFieldsets`); reach anything outside it — another feature (`@/portal/features/profile/api`), `src/portal/components/`, `src/portal/api/`, `src/test/` — through the `@/` alias (or `@test/` for the test helpers). ESLint's `no-restricted-imports` enforces this with two patterns: files under `src/portal/features/**` may not import a specifier starting with `../` at all, since one level up is already a sibling feature; everywhere else in `src/` a single `../` is allowed (`../components/Button` from `src/portal/routes/`) but `../../` is not. Every feature is a flat directory today; a feature that grows a subdirectory adds a `files` entry to `eslint.config.js` exempting that subdirectory, so its files can still reach the feature root with `../`.
- `src/portal/api/queries.ts` holds a query hook more than one feature reads (the plan catalog, the DART list, site chrome); a hook only its own feature uses stays in that feature's `api.ts`.
- Avoid **barrel files** that re-export everything; they can hurt tree-shaking and clarity. Re-export only the public API surface when needed.
- Do NOT use **circular dependencies**. If A imports B and B imports A, extract shared code to a third module or invert the dependency.

## 5. Functions and Control Flow

- Keep **parameter lists short** (e.g. ≤ 3–4). For more options, use a single **options object** with typed properties.
- Prefer **arrow functions** for callbacks and when `this` binding is not needed; use **function declarations** for top-level or named functions that benefit from hoisting.
- Use **optional chaining** (`?.`) and **nullish coalescing** (`??`) instead of long conditional chains where they improve readability.
- Use **template literals** for string interpolation; avoid string concatenation with `+` for dynamic strings.
- Use **destructuring** for function parameters and return values when it reduces noise (e.g. `function run({ env, timeout }: Options)`).

## 6. Error Handling and Async

- Prefer **try/catch** for synchronous code that can throw; catch at the smallest scope needed. Do NOT swallow errors: log and/or rethrow or return a typed error result.
- For **async code**, use **async/await** over raw Promises. Use `Promise.all` or `Promise.allSettled` for concurrent work; avoid sequential awaits when operations are independent.
- Handle **rejected promises**: ensure async entry points (e.g. event handlers, effects) use try/catch or `.catch()` so unhandled rejections do not escape.
- Use **typed Error** subclasses or **result types** (e.g. `{ ok: true; data: T } | { ok: false; error: Error }`) when callers need to handle errors explicitly.

## 7. Comments and Documentation

- ALWAYS write **self-documenting code**: clear names, small functions, minimal nesting.
- NEVER add comments that only restate the code, reference user requests, or describe modification history.
- ADD comments when they explain **rationale**, **non-obvious behavior**, or **trade-offs**. Keep them short and accurate.
- Use **JSDoc** for all **exported** functions and components: `@param`, `@returns`, and `@throws` (or equivalent) where useful. The types in the signature are the source of truth; JSDoc adds description and examples.
- UPDATE or remove comments when code changes. Remove stale or misleading comments.

## 8. Lint and Format

- ALWAYS run `make lint-frontend` (`tsc --noEmit`, ESLint with `--max-warnings 0`, `prettier --check`) on changed code and fix every error and warning before delivering; `make format` applies Prettier.
- Use the project’s ESLint config (`frontend/eslint.config.js`). Do not disable rules that enforce project conventions (e.g. no `any`, React hooks rules) without a documented exception.
- The config extends `typescript-eslint`'s `recommendedTypeChecked` with `parserOptions.projectService`, so type-aware rules run on every file `tsconfig.json` includes. Fix what they report rather than suppressing it: mark a promise nobody awaits with the `void` operator (React Router's `navigate` is the common case), wrap an async function before handing it to an attribute that expects a void return, and narrow an `any` at its source instead of asserting it away. A `eslint-disable` comment is acceptable only where a library's types force one, and it must say which library and why.
- The config extends `eslint-plugin-jsx-a11y`'s `recommended` flat config. Fix an accessibility finding in the markup — give the image an `alt`, put the keyboard handler on the focusable element, drop the `autoFocus` — rather than suppressing the rule.
- Quoting (single), semicolons (on), and trailing commas (all) are set in the Prettier config; do not fight the formatter.
- The React hooks rules (`react-hooks/rules-of-hooks`, `react-hooks/exhaustive-deps`) are enabled; follow them rather than suppressing them.

## 9. Testing

- ALWAYS write **tests** for new behavior and when fixing bugs. Prefer **unit tests** for pure logic; use **component tests** where behavior depends on DOM or I/O.
- Use Vitest with Testing Library. Put `Foo.test.tsx` beside `Foo.tsx`, render through `src/test/render.tsx`, and mock the API with the msw server in `src/test/server.ts` rather than stubbing `fetch`. End-to-end flows are Playwright specs in `frontend/e2e/` (`make e2e`).
- Vitest runs with `globals: false` and `tsconfig.json`'s `types` lists only `vite/client`, so ALWAYS import `describe`, `it`, `expect`, `vi` and the lifecycle hooks from `vitest` at the top of the test file. The jest-dom matchers are typed once in `src/test/setup.ts` through `@testing-library/jest-dom/vitest`; do not import them per file, and do not put the test globals back into `types`.
- Prefer **one logical assertion per test** (or one behavior); avoid testing multiple unrelated things in one test.
- Name tests **descriptively** (e.g. `it('returns 404 when resource is missing', ...)`). Test **edge cases** and **error paths**, not only the happy path.
- Prefer **isolated tests**: no shared mutable state, no reliance on order. Mock external dependencies (APIs, time) when appropriate.
- NEVER change a test to make it pass by weakening assertions or ignoring failures. If the implementation is wrong, fix the implementation.

## 10. React and UI

- Prefer **function components** and **hooks**. Use **custom hooks** to encapsulate stateful logic; keep components focused on rendering and composition.
- Keep **components small** and composable. Extract subcomponents or hooks when a single component grows large or has multiple responsibilities.
- Use **key** correctly in lists (stable, unique identity); avoid array index as key when list order can change.
- Prefer **controlled components** for form state when you need to validate or transform input; use local state for truly uncontrolled UI.
- Do NOT mutate **state** or **props**. Update state via the setter (e.g. `setState`, `useState` updater); copy objects/arrays when updating nested state.

## 11. Debugging and TODOs

- Fix **bugs** as soon as they are found. If a fix is deferred, create a **tracked issue** and reference it in a short comment (e.g. `// TODO(#123): ...`) instead of a bare TODO.
- Do NOT guess at bug causes. Use **logging**, **breakpoints**, and **reproduction steps** to identify root cause. If stuck, revert and re-approach from first principles.

## Summary: Quick Reference

| Area | Do | Avoid |
|------|----|--------|
| Naming | camelCase (vars/fns), PascalCase (classes/types/components), handle* (handlers) | any, vague names, mutating params |
| Types | strict TS, explicit return types on exports, unknown over any | any, untyped exports |
| Style | const, early returns, small functions, explicit null checks | Deep nesting, magic values, large files |
| Async | async/await, Promise.all for concurrency, catch at boundary | Unhandled rejections, sequential awaits when parallel is possible |
| Tests | One behavior per test, descriptive names, msw for the API | Weakening assertions to make tests pass |
