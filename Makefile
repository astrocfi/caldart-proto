## CalDART developer tasks.
##
## Every target runs from the repository root.  `make help` lists them.

SHELL := /bin/bash
.DEFAULT_GOAL := help

UV      ?= uv
NPM     ?= npm
MANAGE  := $(UV) run backend/manage.py
COMPOSE := docker compose

# $(call flag,NAME,--option): --option when $(NAME) is 1, yes or true; nothing
# when it is 0, no, false, empty or unset; and an error naming the variable for
# any other value, so a mistyped switch stops make before the recipe runs
# instead of silently meaning its opposite.  The values are lower case only.
flag = $(if $(filter 1 yes true,$($(1))),$(2),$(if $(filter-out 0 no false,$($(1))),$(error $(1)=$($(1)) is not one of 1 yes true 0 no false)))

# Per-worker database, so parallel branches never collide.  Override on the
# command line or in .env:
#   make test DATABASE_URL=postgres://caldart:caldart@localhost:5432/caldart_payments
DATABASE_URL ?= $(shell sed -n 's/^DATABASE_URL=//p' .env 2>/dev/null | tail -1)
DATABASE_URL := $(if $(DATABASE_URL),$(DATABASE_URL),postgres://caldart:caldart@localhost:5432/caldart)
export DATABASE_URL

DB_NAME := $(shell printf '%s' "$(DATABASE_URL)" | sed -e 's#.*/##' -e 's/?.*//')

# `make e2e` runs against its own database and its own server, so it never
# disturbs the one you are developing against.
E2E_PORT ?= 8021
E2E_DB ?= caldart_e2e
E2E_DATABASE_URL ?= postgres://caldart:caldart@localhost:5432/$(E2E_DB)
E2E_LOG ?= /tmp/caldart-e2e-server.log

# The end-to-end server's whole environment, spelled out rather than inherited.
# The run has to behave the same on a laptop with a `.env` and on CI without
# one, and django-environ lets a real environment variable win over the file,
# so every setting the specs depend on is pinned here:
#
#   DEBUG=false        `runserver` only serves frontend/dist itself while DEBUG
#                      is on.  Rather than depend on that, the target runs
#                      collectstatic and whitenoise serves the bundle, exactly
#                      as in production.  (CI sets DEBUG=false anyway; that is
#                      how 21 of 22 specs met an empty SPA shell.)
#   EMAIL_URL          the console backend: CI has no Mailpit, and a password
#                      reset must not fail on a refused SMTP connection.
#   AUTH_THROTTLE_LOGIN the specs sign in far more often in a minute than a
#                      person ever would.
E2E_ENV := DJANGO_SETTINGS_MODULE=caldart.settings.dev \
           DATABASE_URL="$(E2E_DATABASE_URL)" \
           SECRET_KEY=e2e-insecure-secret-key \
           DEBUG=false \
           ALLOWED_HOSTS='localhost,127.0.0.1,[::1]' \
           SITE_URL="http://localhost:$(E2E_PORT)" \
           CSRF_TRUSTED_ORIGINS="http://localhost:$(E2E_PORT)" \
           EMAIL_URL=consolemail:// \
           DJANGO_VITE_DEV_MODE=false \
           PAYMENTS_MOCK_ENABLED=true \
           AUTH_THROTTLE_LOGIN=1000/min

.PHONY: help setup up down wait-db createdb migrate makemigrations seed reset run \
        dev-frontend build test test-backend test-frontend e2e lint lint-backend \
        lint-frontend lint-spelling format check check-backend check-deploy check-frontend \
        audit audit-backend audit-frontend backup restore reminders docs shell superuser \
        collectstatic clean

help: ## Show this help
	@grep -hE '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[1m%-16s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------- setup
setup: ## Install Python and Node dependencies, create .env if missing
	$(UV) sync
	cd frontend && $(NPM) ci
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example")

up: ## Start Postgres and Mailpit
	$(COMPOSE) up -d db mailpit
	@$(MAKE) --no-print-directory wait-db
	@$(MAKE) --no-print-directory createdb

down: ## Stop the containers (data survives in the caldart_pgdata volume)
	$(COMPOSE) down

wait-db: ## Internal helper: block until Postgres in the containers accepts connections
	@for i in $$(seq 1 60); do \
	  $(COMPOSE) exec -T db pg_isready -U caldart -d caldart >/dev/null 2>&1 && exit 0; \
	  sleep 1; \
	done; \
	echo "Postgres did not become ready" >&2; exit 1

createdb: ## Create the database named in DATABASE_URL if it does not exist
	@$(COMPOSE) exec -T db psql -U caldart -d postgres -tAc \
	    "SELECT 1 FROM pg_database WHERE datname='$(DB_NAME)'" | grep -q 1 \
	  || $(COMPOSE) exec -T db createdb -U caldart -O caldart "$(DB_NAME)"
	@echo "Database $(DB_NAME) ready"

# ------------------------------------------------------------- database
migrate: ## Apply database migrations
	$(MANAGE) migrate

makemigrations: ## Generate migrations for changed models
	$(MANAGE) makemigrations

seed: ## Seed roles, demo data and example content
	$(MANAGE) seed_roles
	$(MANAGE) seed_demo
	$(MANAGE) seed_content

reset: ## DESTROY the dev database, then migrate and re-seed
	@echo "Resetting $(DB_NAME) — every table will be dropped."
	$(MANAGE) db_reset --seed --noinput

backup: ## Write a gzipped pg_dump to backups/
	$(MANAGE) db_backup

restore: ## Restore a dump: make restore FILE=backups/caldart-....sql.gz [YES=1]
	@test -n "$(FILE)" || (echo "Usage: make restore FILE=backups/caldart-....sql.gz" >&2; exit 1)
	@echo "Restoring into $(DB_NAME) — every existing table is dropped first."
	$(MANAGE) db_restore $(FILE) $(call flag,YES,--yes)

# ---------------------------------------------------------------- serve
run: ## Run Django on :8000
	@echo "Public site  http://localhost:8000/"
	@echo "Portal       http://localhost:8000/portal/"
	@echo "Wagtail      http://localhost:8000/admin/"
	@echo "Mailpit      http://localhost:8025/"
	@echo
	@echo "For hot module reload, run 'make dev-frontend' in a second terminal"
	@echo "and set DJANGO_VITE_DEV_MODE=true in .env."
	$(MANAGE) runserver 0.0.0.0:8000

dev-frontend: ## Run the Vite dev server on :5173 (needs DJANGO_VITE_DEV_MODE=true)
	cd frontend && $(NPM) run dev

build: ## Build production frontend assets into frontend/dist
	cd frontend && $(NPM) run build

collectstatic: ## Collect static files into backend/staticfiles
	$(MANAGE) collectstatic --noinput

shell: ## Django shell
	$(MANAGE) shell

superuser: ## Create a Django superuser
	$(MANAGE) createsuperuser

# ----------------------------------------------------------------- test
test: test-backend test-frontend ## Run backend and frontend unit tests

test-backend: ## pytest (Postgres)
	$(UV) run pytest

test-frontend: ## vitest
	cd frontend && $(NPM) run test

e2e: ## Playwright end-to-end tests (own database, own server, mock payments)
	@# CI creates the database with psql, having no compose services to exec into.
	@test -n "$(SKIP_CREATEDB)" \
	  || $(MAKE) --no-print-directory createdb DATABASE_URL="$(E2E_DATABASE_URL)"
	$(E2E_ENV) $(MANAGE) db_reset --seed --noinput
	cd frontend && $(NPM) run build
	$(E2E_ENV) $(MANAGE) collectstatic --noinput
	@set -e; \
	  $(E2E_ENV) $(MANAGE) runserver 0.0.0.0:$(E2E_PORT) --noreload > $(E2E_LOG) 2>&1 & \
	  server=$$!; \
	  trap 'pkill -P $$server >/dev/null 2>&1; kill $$server >/dev/null 2>&1; true' EXIT INT TERM; \
	  for i in $$(seq 1 60); do \
	    curl -sf -o /dev/null "http://localhost:$(E2E_PORT)/portal/login" && break; \
	    sleep 1; \
	    test $$i -lt 60 || { echo "Django did not start; see $(E2E_LOG)" >&2; tail -20 $(E2E_LOG) >&2; exit 1; }; \
	  done; \
	  bundle=$$(curl -s "http://localhost:$(E2E_PORT)/portal/login" \
	    | sed -n 's/.*src="\(\/static\/[^"]*\.js\)".*/\1/p' | head -1); \
	  test -n "$$bundle" \
	    || { echo "The portal shell names no bundle; see $(E2E_LOG)" >&2; tail -20 $(E2E_LOG) >&2; exit 1; }; \
	  curl -sf -o /dev/null "http://localhost:$(E2E_PORT)$$bundle" \
	    || { echo "The portal bundle $$bundle is not served — the SPA would never start." >&2; \
	         tail -20 $(E2E_LOG) >&2; exit 1; }; \
	  cd frontend && E2E_BASE_URL="http://localhost:$(E2E_PORT)" $(NPM) run e2e \
	    || { echo; echo "==== last 100 lines of $(E2E_LOG) ===="; tail -100 $(E2E_LOG); exit 1; }

# ----------------------------------------------------------------- lint
lint: lint-backend lint-frontend lint-spelling ## ruff + mypy + tsc + eslint + prettier + codespell

lint-backend: ## ruff check + ruff format --check + mypy
	$(UV) run ruff check .
	$(UV) run ruff format --check .
	$(UV) run mypy backend

# American spelling and common typos, everywhere prose and code are written.
# `plans/` stays out: the archived plans are frozen, and a live plan may quote
# the very words a fix replaces.  `--check-hidden` is what reaches .github and
# .claude, which codespell would otherwise skip for their leading dot.
lint-spelling: ## codespell over docs, prose and code
	$(UV) run codespell --check-hidden README.rst CLAUDE.md docs backend frontend/src \
	  frontend/e2e .github deploy .claude

lint-frontend: ## tsc --noEmit + eslint + prettier --check
	cd frontend && $(NPM) run typecheck
	cd frontend && $(NPM) run lint
	cd frontend && $(NPM) run format:check

format: ## Auto-format Python and TypeScript
	$(UV) run ruff format .
	$(UV) run ruff check --fix .
	cd frontend && $(NPM) run format

# ---------------------------------------------------------------- check
# The gates that are neither lint nor tests: Django's system checks (a warning
# fails too), a model change without its migration, the production deployment
# security check, and the production build.
check: check-backend check-deploy check-frontend ## Django system checks, missing migrations, deploy security, production build

check-backend: ## Django system checks + missing-migration check
	$(MANAGE) check --settings caldart.settings.test --fail-level WARNING
	$(MANAGE) makemigrations --check --dry-run --settings caldart.settings.test

# `--deploy` adds Django's production security checks to the default set;
# `--tag security` narrows the run to those, so a `frontend/dist` this gate
# never builds (the backend CI job does not run `check-frontend`) does not
# fail it with an unrelated django_vite/staticfiles warning.  The environment
# is a throwaway one set inline: no real secret is at risk, and it carries only
# what prod.py requires outright.  No secure flag is pinned here -- every one of
# them comes from prod.py's own default, so flipping a default off fails this
# gate instead of being masked by a value the recipe supplies.
check-deploy: ## Production deployment security check (manage.py check --deploy)
	SECRET_KEY="throwaway-check-deploy-key-not-a-real-secret-0123456789" \
	  ALLOWED_HOSTS="check-deploy.example.com" \
	  DATABASE_URL="postgres://caldart:caldart@localhost:5432/caldart" \
	  SITE_URL="https://check-deploy.example.com" \
	  EMAIL_URL="smtp://localhost:1025" \
	  $(MANAGE) check --deploy --tag security --fail-level WARNING --settings caldart.settings.prod

check-frontend: ## Production frontend build
	cd frontend && $(NPM) run build

# ---------------------------------------------------------------- audit
audit: audit-backend audit-frontend ## Known vulnerabilities in Python and npm dependencies

# `uv audit` checks the versions pinned in uv.lock against the OSV database.
# It is a uv preview feature; the flag acknowledges that and silences the notice.
audit-backend: ## uv audit against the OSV database
	$(UV) audit --frozen --preview-features audit

audit-frontend: ## npm audit against known vulnerabilities
	cd frontend && $(NPM) audit

# ------------------------------------------------------------ scheduled
reminders: ## Send renewal reminders (make reminders TODAY=2027-01-01 DRY_RUN=1)
	$(MANAGE) send_renewal_reminders \
	  $(if $(TODAY),--today=$(TODAY),) \
	  $(call flag,DRY_RUN,--dry-run)

# ----------------------------------------------------------------- docs
docs: ## Build the Sphinx documentation (nitpicky; warnings are errors)
	$(UV) run sphinx-build -n -W -b html docs docs/_build/html
	@echo "Docs at docs/_build/html/index.html"

clean: ## Remove build artifacts
	rm -rf docs/_build frontend/dist backend/staticfiles
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
