## CalDART developer tasks (PLAN.rst §14).
##
## Every target runs from the repository root.  `make help` lists them.

SHELL := /bin/bash
.DEFAULT_GOAL := help

UV      ?= uv
NPM     ?= npm
MANAGE  := $(UV) run backend/manage.py
COMPOSE := docker compose

# Per-worker database (PLAN §17).  Override on the command line or in .env:
#   make test DATABASE_URL=postgres://caldart:caldart@localhost:5432/caldart_payments
DATABASE_URL ?= $(shell sed -n 's/^DATABASE_URL=//p' .env 2>/dev/null | tail -1)
DATABASE_URL := $(if $(DATABASE_URL),$(DATABASE_URL),postgres://caldart:caldart@localhost:5432/caldart)
export DATABASE_URL

DB_NAME := $(shell printf '%s' "$(DATABASE_URL)" | sed -e 's#.*/##' -e 's/?.*//')

.PHONY: help setup up down wait-db createdb migrate makemigrations seed reset run \
        dev-frontend build test test-backend test-frontend e2e lint lint-backend \
        lint-frontend format backup restore reminders docs shell superuser \
        collectstatic clean

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
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

wait-db:
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
	@# seed_content arrives with feat/cms-site; skip it cleanly until then.
	@$(MANAGE) help seed_content >/dev/null 2>&1 \
	  && $(MANAGE) seed_content \
	  || echo "seed_content not available yet (feat/cms-site) — skipped"

reset: ## DESTROY the dev database, then migrate and re-seed
	@echo "Resetting $(DB_NAME) — every table will be dropped."
	$(MANAGE) db_reset --seed --noinput

backup: ## Write a gzipped pg_dump to backups/
	$(MANAGE) db_backup

restore: ## Restore a dump: make restore FILE=backups/caldart-....sql.gz
	@test -n "$(FILE)" || (echo "Usage: make restore FILE=backups/caldart-....sql.gz" >&2; exit 1)
	$(MANAGE) db_restore $(FILE)

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

e2e: ## Playwright end-to-end tests
	cd frontend && $(NPM) run e2e

# ----------------------------------------------------------------- lint
lint: lint-backend lint-frontend ## ruff + eslint + tsc

lint-backend:
	$(UV) run ruff check .
	$(UV) run ruff format --check .

lint-frontend:
	cd frontend && $(NPM) run typecheck
	cd frontend && $(NPM) run lint
	cd frontend && $(NPM) run format:check

format: ## Auto-format Python and TypeScript
	$(UV) run ruff format .
	$(UV) run ruff check --fix .
	cd frontend && $(NPM) run format

# ------------------------------------------------------------ scheduled
reminders: ## Send renewal reminders (make reminders TODAY=2027-01-01 DRY_RUN=1)
	$(MANAGE) send_renewal_reminders \
	  $(if $(TODAY),--today=$(TODAY),) \
	  $(if $(DRY_RUN),--dry-run,)

# ----------------------------------------------------------------- docs
docs: ## Build the Sphinx documentation (warnings are errors)
	$(UV) run sphinx-build -W -b html docs docs/_build/html
	@echo "Docs at docs/_build/html/index.html"

clean: ## Remove build artefacts
	rm -rf docs/_build frontend/dist backend/staticfiles
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
