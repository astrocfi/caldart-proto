# caldart-proto

## GitHub credentials: this repo is always `astrocfi`

The machine's default GitHub account is `rfrenchseti`. This repo overrides that.
It is wired up already — **run `git` and `gh` normally, with no prefix.**

- `git` — repo-local credential helper reads `~/.git-credentials.astrocfi`
  (the inherited global `credential.helper=store` is cleared by an empty entry
  ahead of it). Commits use `user.email=rfrench@rfrench.org`.
- `gh` — `~/bin/gh` wraps the real `/usr/bin/gh`: it reads
  `git config --get gh.account` and injects `GH_TOKEN` for that account from gh's
  keyring. This repo sets `gh.account = astrocfi`.

Do **not** prefix commands with `GH_TOKEN=...`, and do **not** run
`gh auth switch` — that changes the global default and breaks other repos.
`gh auth status` intentionally still reports `rfrenchseti` as the *active*
account; that is expected and does not affect this repo.

## Working in this repo

`PLAN.rst` at the repository root is the **authoritative specification**. Read
the section that covers what you are building before you write code. If the
code and the plan disagree, fix one of them in the same PR.

### Layout

```
backend/                Django 5 + Wagtail 8
  manage.py
  caldart/              project: settings/{base,dev,prod,test}.py, urls.py,
                        api_urls.py, reports.py, pagination.py, exceptions.py
  apps/<app>/           accounts, members, aircraft, payments, reminders,
                        cms, sysadmin — each with models.py, admin.py,
                        api/urls.py, seed.py, management/commands/
  templates/            base.html (public shell), portal.html (SPA mount),
                        cms/, emails/
  tests/                ALL backend tests: conftest.py, factories.py,
                        test_<feature>.py
frontend/               Vite + React 19 + TypeScript (strict)
  src/styles/           tokens.css, base.css, themes/{sierra,pacific,night}.css
  src/site/main.ts      public-site enhancements
  src/portal/           main.tsx, App.tsx, api/{client,types}.ts, nav.ts,
                        routes/*.tsx, features/<feature>/, components/
  src/test/             msw server, handlers, render helpers
docs/                   Sphinx (user/ and developer/), built with -W
deploy/                 gunicorn.conf.py, systemd/, apache/, nginx/
```

### Make targets

`make help` lists them all. The ones you will use constantly:

| Target | Does |
| --- | --- |
| `make setup` | `uv sync`, `npm ci`, create `.env` |
| `make up` / `make down` | Postgres + Mailpit containers (project name `caldart`, shared by every worktree) |
| `make migrate` / `make seed` | schema, then demo data |
| `make reset` | destroy and rebuild the dev database |
| `make run` | Django on :8000 |
| `make dev-frontend` | Vite dev server on :5173 (set `DJANGO_VITE_DEV_MODE=true`) |
| `make build` | production frontend assets into `frontend/dist` |
| `make test` | `pytest` + `vitest` |
| `make lint` | `ruff check`, `ruff format --check`, `tsc`, `eslint`, `prettier` |
| `make docs` | `sphinx-build -W` |

### Running tests

Backend tests live in `backend/tests/` — **not** in per-app `tests/` packages.
`backend/tests/conftest.py` holds the shared fixtures (`api_client`,
`user_factory`, one fixture per role, plan/dart/aircraft fixtures) and
`backend/tests/factories.py` the factory_boy factories. Add your feature's
tests as `backend/tests/test_<feature>.py` so parallel branches never touch
the same file.

```
uv run pytest                       # everything
uv run pytest backend/tests/test_payments_mock_provider.py -x
cd frontend && npm run test         # vitest
```

Frontend tests sit next to what they test (`Foo.test.tsx` beside `Foo.tsx`)
and use `src/test/render.tsx` plus the msw server in `src/test/server.ts`.

### Per-worker database

Parallel branches must not share a database:

```
DATABASE_URL=postgres://caldart:caldart@localhost:5432/caldart_<branch-slug>
```

e.g. `caldart_payments` for `feat/payments`. `make up` creates the database
named in `DATABASE_URL` if it does not exist. Django names the test database
`test_caldart_<slug>`, so `pytest` runs stay isolated too. All worktrees share
one set of containers because `docker-compose.yml` pins `name: caldart`.

### File ownership on parallel branches

PLAN §17 assigns each Phase 2 branch a set of files. **Edit only your own.**
The shared surfaces were built in Phase 1 precisely so nobody has to:

- `caldart/api_urls.py` already includes every app's `api/urls.py` — add your
  endpoints in `apps/<yours>/api/urls.py`.
- `src/portal/routes/index.tsx` already concatenates every feature's route
  file — edit only `src/portal/routes/<yours>.tsx`.
- `src/portal/nav.ts` already declares every nav entry with its roles.
- `src/portal/api/types.ts` already types every object in PLAN §6.
- `src/portal/components/` holds the shared primitives; add to them rather
  than forking them.
- `caldart/reports.py` holds `csv_response` and `pdf_table_response`.
- `pyproject.toml` already lists every dependency Phase 2 needs.

If you genuinely must change a shared file, keep the change additive and say
so in the PR description.

### No backwards compatibility

This is a prototype. Change the schema freely: edit the model and regenerate
the migration rather than stacking fix-up migrations, and delete code that a
change makes dead. There is no data to migrate and no external API to keep
stable.

### Commits

Every commit message must end with these two trailer lines:

```
Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: <the session URL for the work>
```

Branch from a fresh `origin/main`, keep commits small and focused, and open
the PR with `gh pr create --base main` describing what, why and how tested.
`make test`, `make lint` and `make docs` must all be green first.
