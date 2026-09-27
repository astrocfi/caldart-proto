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
E2E_MAIL_DIR := $(abspath frontend/e2e/.mail)
# The run cannot call Geoapify, so a static file server on the next port answers
# every address-suggestion request with the one recorded response in this directory.
E2E_GEOAPIFY_PORT ?= $(shell expr $(E2E_PORT) + 1)
E2E_GEOAPIFY_DIR := $(abspath frontend/e2e/geoapify)

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
#   EMAIL_URL          the file backend, writing each message into
#                      frontend/e2e/.mail/: CI has no Mailpit, a password reset
#                      must not fail on a refused SMTP connection, and a spec
#                      follows a verification link by reading the file.  Four
#                      slashes, because django-environ drops the first slash of
#                      the path.
#   AUTH_THROTTLE_*    the specs sign in, register, follow verification links
#                      and give on the donation page far more often in an hour
#                      than a person ever would; every anonymous rate is
#                      lifted, since one run registers more than ten accounts
#                      from one address.
#   GEOAPIFY_*         a key, so address suggestions are on, and the stub's
#                      URL in place of Geoapify's; the stub answers every query
#                      with frontend/e2e/geoapify/autocomplete.json.  The
#                      suggestion rate is lifted with the others.
#   FAA_REGISTRY_URL   the registry fixture's directory, so Run now on the
#                      System screen imports the fixture instead of downloading
#                      the FAA's registry.
E2E_ENV := DJANGO_SETTINGS_MODULE=caldart.settings.dev \
           DATABASE_URL="$(E2E_DATABASE_URL)" \
           SECRET_KEY=e2e-insecure-secret-key \
           DEBUG=false \
           ALLOWED_HOSTS='localhost,127.0.0.1,[::1]' \
           SITE_URL="http://localhost:$(E2E_PORT)" \
           CSRF_TRUSTED_ORIGINS="http://localhost:$(E2E_PORT)" \
           EMAIL_URL=filemail:///$(E2E_MAIL_DIR) \
           DJANGO_VITE_DEV_MODE=false \
           PAYMENTS_MOCK_ENABLED=true \
           AUTH_THROTTLE_LOGIN=1000/min \
           AUTH_THROTTLE_REGISTER=1000/min \
           AUTH_THROTTLE_PASSWORD_RESET=1000/min \
           AUTH_THROTTLE_VERIFY=1000/min \
           AUTH_THROTTLE_VERIFY_RESEND=1000/min \
           AUTH_THROTTLE_DONATE=1000/min \
           GEOAPIFY_API_KEY=e2e-stub-key \
           GEOAPIFY_URL="http://127.0.0.1:$(E2E_GEOAPIFY_PORT)/autocomplete.json" \
           ADDRESS_SUGGEST_THROTTLE_RATE=1000/min \
           FAA_REGISTRY_URL="$(abspath backend/apps/aircraft/fixtures/faa)"

# `make rehearse-deploy` runs the real installer in a throwaway systemd
# container: deploy/bootstrap.sh, then deploy/upgrade.sh, deploy/install.sh a
# second time, and deploy/uninstall.sh --yes --purge, with every scheduled job
# started once after the install.  Slow and opt-in, like `make e2e`; CI does
# not run it.
#
#   REHEARSE_WEB_SERVER  apache or nginx, what the installer is told to use
#   REHEARSE_KEEP        a switch: keep the container and its volumes afterwards
#
# It installs HEAD, never the working tree, because bootstrap.sh clones the
# checkout: commit before rehearsing.  A git worktree's .git is a file naming a
# directory under the main repository's .git, so the common git directory is
# mounted too, read-only, at the path it has here, where that file points.  The
# inner Docker keeps /var/lib/docker and /var/lib/containerd on volumes of this
# Docker, since overlayfs inside overlayfs fails with "invalid argument"; the
# volumes are named after the web server, so two rehearsals never share one.
REHEARSE_WEB_SERVER ?= apache
REHEARSE_IMAGE := jrei/systemd-ubuntu:24.04
REHEARSE_NAME = caldart-rehearsal-$(REHEARSE_WEB_SERVER)
REHEARSE_GIT_COMMON = $(abspath $(shell git rev-parse --git-common-dir))
# The branch HEAD is on, or the commit when HEAD is detached.
REHEARSE_REF = $(shell git symbolic-ref -q --short HEAD || git rev-parse HEAD)
REHEARSE_KEEP_FLAG = $(call flag,REHEARSE_KEEP,keep)

.PHONY: help setup up down wait-db createdb migrate makemigrations seed reset run \
        dev-frontend build test test-backend test-frontend coverage coverage-backend \
        coverage-frontend e2e rehearse-deploy \
        lint lint-backend lint-shell \
        lint-frontend lint-spelling format check check-backend check-deploy check-frontend \
        audit audit-backend audit-frontend backup restore reminders sandbox-check docs guide shell \
        superuser read-docs collectstatic clean

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

coverage: coverage-backend coverage-frontend ## Backend + frontend coverage reports

coverage-backend: ## pytest-cov over production code only; writes backend/htmlcov/
	$(UV) run pytest --cov=backend/apps --cov=backend/caldart \
	  --cov-report=term-missing --cov-report=html:backend/htmlcov

coverage-frontend: ## vitest with coverage; writes frontend/coverage/
	cd frontend && $(NPM) run coverage

e2e: ## Playwright end-to-end tests (own database, own server, mock payments)
	@# CI creates the database with psql, having no compose services to exec into.
	@test -n "$(SKIP_CREATEDB)" \
	  || $(MAKE) --no-print-directory createdb DATABASE_URL="$(E2E_DATABASE_URL)"
	@# Every run starts with an empty mailbox, so a spec only ever reads its own mail.
	rm -rf "$(E2E_MAIL_DIR)" && mkdir -p "$(E2E_MAIL_DIR)"
	$(E2E_ENV) $(MANAGE) db_reset --seed --noinput
	@# The specs read this instead of copying the seed's own values into a spec.
	$(E2E_ENV) $(MANAGE) seed_facts > frontend/e2e/seed-facts.json
	cd frontend && $(NPM) run build
	$(E2E_ENV) $(MANAGE) collectstatic --noinput
	$(MAKE) --no-print-directory guide
	@set -e; \
	  $(UV) run python -m http.server $(E2E_GEOAPIFY_PORT) --bind 127.0.0.1 \
	    --directory "$(E2E_GEOAPIFY_DIR)" > /dev/null 2>&1 & \
	  geoapify=$$!; \
	  $(E2E_ENV) $(MANAGE) runserver 0.0.0.0:$(E2E_PORT) --noreload > $(E2E_LOG) 2>&1 & \
	  server=$$!; \
	  trap 'pkill -P $$server >/dev/null 2>&1; kill $$server >/dev/null 2>&1; \
	        pkill -P $$geoapify >/dev/null 2>&1; kill $$geoapify >/dev/null 2>&1; true' EXIT INT TERM; \
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

rehearse-deploy: ## Rehearse the server install in a throwaway systemd container (REHEARSE_WEB_SERVER=apache|nginx)
	@case "$(REHEARSE_WEB_SERVER)" in apache|nginx) ;; \
	  *) echo "REHEARSE_WEB_SERVER=$(REHEARSE_WEB_SERVER) is not apache or nginx" >&2; exit 2 ;; esac
	@test -z "$$(git status --porcelain)" \
	  || echo "note: the rehearsal installs HEAD; uncommitted changes are not in it" >&2
	@set -euo pipefail; \
	  name=$(REHEARSE_NAME); keep="$(REHEARSE_KEEP_FLAG)"; started=$$(date +%s); \
	  inside() { docker exec "$$name" "$$@"; }; \
	  cleanup() { \
	    status=$$?; \
	    echo "==> rehearsal on $(REHEARSE_WEB_SERVER) took $$(( $$(date +%s) - started ))s and exited $$status"; \
	    if [ -n "$$keep" ]; then \
	      echo "==> kept $$name; docker exec -it $$name bash to look inside"; \
	    else \
	      docker rm -f "$$name" >/dev/null 2>&1 || true; \
	      docker volume rm "$$name-docker" "$$name-containerd" >/dev/null 2>&1 || true; \
	    fi; \
	  }; \
	  if docker inspect "$$name" >/dev/null 2>&1; then \
	    echo "==> Removing the previous $$name"; \
	  fi; \
	  docker rm -f "$$name" >/dev/null 2>&1 || true; \
	  docker volume rm "$$name-docker" "$$name-containerd" >/dev/null 2>&1 || true; \
	  trap cleanup EXIT; \
	  echo "==> Starting $$name from $(REHEARSE_IMAGE)"; \
	  docker run -d --name "$$name" --privileged --cgroupns=host \
	    -v /sys/fs/cgroup:/sys/fs/cgroup:rw --tmpfs /run --tmpfs /run/lock \
	    -v "$$name-docker:/var/lib/docker" -v "$$name-containerd:/var/lib/containerd" \
	    -v "$(CURDIR):/mnt/caldart:ro" \
	    -v "$(REHEARSE_GIT_COMMON):$(REHEARSE_GIT_COMMON):ro" \
	    $(REHEARSE_IMAGE) >/dev/null; \
	  state=$$(inside systemctl is-system-running --wait || true); \
	  case "$$state" in running|degraded) ;; \
	    *) echo "systemd in $$name did not start: $$state" >&2; exit 1 ;; esac; \
	  echo "==> Installing git and curl in the container"; \
	  inside env DEBIAN_FRONTEND=noninteractive apt-get update -qq; \
	  inside env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq git curl >/dev/null; \
	  : "The rehearsal container only: root clones a checkout another uid owns."; \
	  inside git config --system safe.directory '*'; \
	  inside bash /mnt/caldart/deploy/bootstrap.sh --repo /mnt/caldart --ref "$(REHEARSE_REF)" \
	    --hostname caldart.test --tls self-signed --web-server $(REHEARSE_WEB_SERVER) \
	    --email-url smtp://localhost:25 --admin-email admin@caldart.test; \
	  : "The install started the registry import itself; it downloads the FAA file."; \
	  echo "==> Running every other scheduled job once, hardening and all"; \
	  inside systemctl start caldart-backup.service caldart-reports.service \
	    caldart-renewals.service caldart-reminders.service caldart-statements.service; \
	  echo "==> Rehearsing an upgrade that changes nothing"; \
	  inside /opt/caldart/deploy/upgrade.sh; \
	  echo "==> Rehearsing a second install with no flags"; \
	  before=$$(inside sha256sum /etc/caldart/caldart.env /etc/caldart/install.conf); \
	  inside /opt/caldart/deploy/install.sh; \
	  after=$$(inside sha256sum /etc/caldart/caldart.env /etc/caldart/install.conf); \
	  [ "$$before" = "$$after" ] \
	    || { echo "error: a no-flag install changed the environment file or the install record" >&2; exit 1; }; \
	  echo "==> Rehearsing the uninstall"; \
	  inside /opt/caldart/deploy/uninstall.sh --yes --purge; \
	  inside test ! -e /opt/caldart; \
	  inside test ! -e /etc/caldart; \
	  echo "==> The rehearsal on $(REHEARSE_WEB_SERVER) passed"

# ----------------------------------------------------------------- lint
lint: lint-backend lint-shell lint-frontend lint-spelling ## ruff + mypy + shellcheck + tsc + eslint + prettier + contrast + codespell

lint-backend: ## ruff check + ruff format --check + mypy
	$(UV) run ruff check .
	$(UV) run ruff format --check .
	$(UV) run mypy backend

# Every shell script: the server installer under deploy/ and the developer
# conveniences under scripts/.  shellcheck comes from the shellcheck-py wheel in
# the dev group, so no system package is needed.  --external-sources follows
# the `source` lines the installer uses to share deploy/lib.sh.
lint-shell: ## shellcheck over deploy/ and scripts/
	$(UV) run shellcheck --external-sources deploy/*.sh deploy/steps/*.sh scripts/*.sh

# American spelling and common typos, everywhere prose and code are written.
# `plans/` stays out: the archived plans are frozen, and a live plan may quote
# the very words a fix replaces.  `--check-hidden` is what reaches .github and
# .claude, which codespell would otherwise skip for their leading dot.
lint-spelling: ## codespell over docs, prose and code
	$(UV) run codespell --check-hidden README.rst CLAUDE.md docs backend frontend/src \
	  frontend/e2e frontend/scripts scripts .github deploy .claude

lint-frontend: ## tsc --noEmit + eslint + prettier --check
	cd frontend && $(NPM) run typecheck
	cd frontend && $(NPM) run lint
	cd frontend && $(NPM) run format:check
	cd frontend && $(NPM) run theme-contrast

format: ## Auto-format Python and TypeScript
	$(UV) run ruff format .
	$(UV) run ruff check --fix .
	cd frontend && $(NPM) run format

# ---------------------------------------------------------------- check
# The gates that are neither lint nor tests: Django's system checks (a warning
# fails too), a model change without its migration, the deployment-only checks
# against the production settings, and the production build.
check: check-backend check-deploy check-frontend ## Django system checks, missing migrations, deployment checks, production build

# `backend/openapi.json` is a build artifact, not a source file, and its path is
# fixed rather than a variable: this target writes it and the frontend's
# `schema` script reads it from there, so the two must never disagree.
check-backend: ## Django system checks + missing-migration check + OpenAPI schema
	$(MANAGE) check --settings caldart.settings.test --fail-level WARNING
	$(MANAGE) makemigrations --check --dry-run --settings caldart.settings.test
	$(MANAGE) spectacular --settings caldart.settings.test --format openapi-json \
	  --file backend/openapi.json

# `--deploy` adds Django's deployment-only checks to the default set, and those
# carry exactly four tags: security, caches, async_support and mail.  Naming
# all four runs every deployment-only check while leaving out the default ones
# `check-backend` already covers -- among them the staticfiles/django_vite
# check, which needs a `frontend/dist` this gate never builds (the backend CI
# job does not run `check-frontend`).  The environment is a throwaway one set
# inline: no real secret is at risk, and it carries only what prod.py requires
# outright.  No secure flag is pinned here -- every one of them comes from
# prod.py's own default, so flipping a default off fails this gate instead of
# being masked by a value the recipe supplies.
check-deploy: ## Production deployment checks (manage.py check --deploy)
	SECRET_KEY="throwaway-check-deploy-key-not-a-real-secret-0123456789" \
	  ALLOWED_HOSTS="check-deploy.example.com" \
	  DATABASE_URL="postgres://caldart:caldart@localhost:5432/caldart" \
	  SITE_URL="https://check-deploy.example.com" \
	  EMAIL_URL="smtp://localhost:1025" \
	  $(MANAGE) check --deploy --tag security --tag caches --tag async_support \
	    --tag mail --fail-level WARNING --settings caldart.settings.prod

# `typecheck` regenerates frontend/src/portal/api/schema.d.ts from the schema
# `check-backend` wrote, then type-checks the portal against it: that is where a
# serializer change the portal's types have not followed fails.
check-frontend: ## Portal types against the OpenAPI schema, then the production build
	cd frontend && $(NPM) run typecheck
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

sandbox-check: ## Verify Stripe and PayPal sandbox credentials without moving money
	$(MANAGE) payments_sandbox_check

# ----------------------------------------------------------------- docs
docs: guide ## Build the Sphinx documentation and the user guide (nitpicky; warnings are errors)
	$(UV) run sphinx-build -n -W -b html docs docs/_build/html
	@echo "Docs at docs/_build/html/index.html"

# The user guide alone, as the site serves it at /docs/ to signed-in users:
# docs/user is the source tree, docs/conf.py the configuration, and the guide
# tag tells conf.py which build this is.  The dirhtml builder gives every page
# a directory, so the URLs read /docs/member/profile/ rather than
# /docs/member/profile.html, and the portal's Help button opens those.  Both
# builds ship docs/_static (the figure toolbar), found relative to conf.py.
# USER_GUIDE_ROOT points Django at the output.
guide: ## Build the user guide the site serves at /docs/ into docs/_build/guide
	$(UV) run sphinx-build -n -W -b dirhtml -t guide -c docs docs/user docs/_build/guide

read-docs: ## Build the documentation and open it in a browser
	./scripts/read-docs.sh

clean: ## Remove build artifacts
	rm -rf docs/_build frontend/dist backend/staticfiles
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
