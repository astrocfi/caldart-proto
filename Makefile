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
# The proxy's own log, so its writes never interleave with runserver's in E2E_LOG:
# runserver truncates its log at the start of each run, and a shared file appended
# to by both processes would corrupt whichever wrote second.
E2E_PROXY_LOG := $(E2E_LOG).proxy
E2E_MAIL_DIR := $(abspath frontend/e2e/.mail)
# The run cannot call Geoapify, so a static file server on the next port answers
# every address-suggestion request with the one recorded response in this directory.
E2E_GEOAPIFY_PORT ?= $(shell expr $(E2E_PORT) + 1)
E2E_GEOAPIFY_DIR := $(abspath frontend/e2e/geoapify)
# `make e2e E2E_URL_PREFIX=/caldart-proto` runs the same specs with the site under
# a URL prefix.  frontend/e2e/prefix_proxy.py takes E2E_PORT and plays the web
# server in front of a prefixed deployment: it strips the prefix and forwards to
# runserver on E2E_PORT + 2, and answers 404 for any path outside the prefix, so
# a URL built without the prefix fails the run.  The proxy is Python kept beside
# the specs it serves, where ruff and mypy (see lint-backend) still check it.
E2E_URL_PREFIX ?=
E2E_ORIGIN := http://localhost:$(E2E_PORT)
E2E_SITE_URL := $(E2E_ORIGIN)$(E2E_URL_PREFIX)
E2E_SERVER_PORT := $(if $(E2E_URL_PREFIX),$(shell expr $(E2E_PORT) + 2),$(E2E_PORT))
E2E_PROXY := frontend/e2e/prefix_proxy.py

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
#   URL_PREFIX         E2E_URL_PREFIX, empty unless the run is under a prefix;
#                      SITE_URL carries it too, since a prefixed site's links
#                      and emails name it.
E2E_ENV := DJANGO_SETTINGS_MODULE=caldart.settings.dev \
           DATABASE_URL="$(E2E_DATABASE_URL)" \
           SECRET_KEY=e2e-insecure-secret-key \
           DEBUG=false \
           ALLOWED_HOSTS='localhost,127.0.0.1,[::1]' \
           URL_PREFIX="$(E2E_URL_PREFIX)" \
           SITE_URL="$(E2E_SITE_URL)" \
           CSRF_TRUSTED_ORIGINS="$(E2E_ORIGIN)" \
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
# container: deploy/bootstrap.sh, with every scheduled job started once after
# the install, then deploy/reset-database.sh and deploy/seed.sh --content twice,
# deploy/upgrade.sh, deploy/install.sh a second time, and deploy/uninstall.sh
# --yes --purge.  Slow and opt-in, like `make e2e`; CI does not run it.
#
#   REHEARSE_WEB_SERVER  apache or nginx, what the installer is told to use
#   REHEARSE_URL_PREFIX  a URL prefix such as /caldart-proto: install behind an
#                        existing site instead of on a host of its own
#   REHEARSE_GUNICORN_PORT
#                        a port such as 8101 for the installer's --gunicorn-port,
#                        where the web server's proxy reaches gunicorn (default:
#                        empty, the installer's own default)
#   REHEARSE_DB_PORT     a port such as 5433 for the installer's --db-port, where
#                        Postgres is published (default: empty, meaning 5432)
#   REHEARSE_SEED        content, demo, or all: pass --seed-content (the example
#                        website alone), --seed-demo (the demo accounts alone), or
#                        both to the install
#   REHEARSE_KEEP        a switch: keep the container and its volumes afterwards
#
# With REHEARSE_URL_PREFIX the recipe first stands up the existing site: the web
# server, a self-signed certificate for caldart.test, and the HTTPS vhost from
# frontend/e2e/rehearsal/ serving a one-line page at /.  Then it installs with
# --tls existing --url-prefix --attach-to that vhost --email local, asserts the
# note that nothing listens on port 25 (the container has no postfix), and that
# the stand-in page and the redirect of the bare prefix still answer; after the
# uninstall the vhost must no longer include the snippet and must still load.
#
# After the install the recipe checks the layout: /opt/caldart/caldart is a git
# checkout, /opt/caldart/backups holds the first dump, /opt/caldart/media exists
# and belongs to the caldart user, nothing the site writes sits inside the
# checkout (no /opt/caldart/backend, and git status in the checkout names
# nothing), and the uninstall leaves no /opt/caldart.
#
# With REHEARSE_GUNICORN_PORT, the web server's configuration must proxy to
# 127.0.0.1 on that port and name 8001 nowhere, the environment file must carry
# the port, gunicorn must answer 200 there, and the site must answer through the
# proxy.  With REHEARSE_DB_PORT the database container must be published on
# 127.0.0.1 at that port.  Both checks run three times: after the install, after
# the upgrade, and after the second install with no flags, so an upgrade or a
# rerun that dropped a recorded port fails.  With REHEARSE_SEED=content
# the install loads the example website alone, and the recipe checks that a
# seeded page answers.  With REHEARSE_SEED=demo it loads the demo accounts alone
# (all loads both); since the demo mandates use the mock payment provider and
# production leaves it off, the recipe also turns it on, so caldart-renewals
# (step 2) has a provider to charge against, and asserts that manage.sh health
# --json still passes and that the sign-in page still answers.  Either seed gives
# the jobs mail to send (the website seed creates the DARTs whose rosters
# caldart-reports mails) and the container has no mail transport of its own, so
# with any seed the recipe installs postfix too, so
# seeding disturbed neither.
#
# After every install the portal page must load its entry script under exactly the
# name in Vite's manifest: the lazy chunks import it by that name, and a second name
# would run it twice (caldart.storage).
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
REHEARSE_URL_PREFIX ?=
REHEARSE_GUNICORN_PORT ?=
REHEARSE_DB_PORT ?=
REHEARSE_SEED ?=
# A prefix rehearsal gets its own container and volumes, so it can run beside
# a plain one on the same web server.
REHEARSE_NAME = caldart-rehearsal-$(REHEARSE_WEB_SERVER)$(if $(REHEARSE_URL_PREFIX),-prefix)$(if $(REHEARSE_GUNICORN_PORT),-port)$(if $(REHEARSE_DB_PORT),-db)$(if $(REHEARSE_SEED),-seed-$(REHEARSE_SEED))
# The directory the web server in the container reads its configuration from.
REHEARSE_CONFIG_DIR_apache := /etc/apache2
REHEARSE_CONFIG_DIR_nginx := /etc/nginx
REHEARSE_CONFIG_DIR = $(REHEARSE_CONFIG_DIR_$(REHEARSE_WEB_SERVER))
# Where the stand-in for the existing site's vhost goes, per web server.
REHEARSE_STANDIN_apache := /etc/apache2/sites-available/standin.conf
REHEARSE_STANDIN_nginx := /etc/nginx/sites-available/standin
REHEARSE_STANDIN = $(REHEARSE_STANDIN_$(REHEARSE_WEB_SERVER))
# The line of the stand-in page, which must still answer at / with CalDART installed.
REHEARSE_STANDIN_PAGE := The existing site at caldart.test
REHEARSE_GIT_COMMON = $(abspath $(shell git rev-parse --git-common-dir))
# The branch HEAD is on, or the commit when HEAD is detached.
REHEARSE_REF = $(shell git symbolic-ref -q --short HEAD || git rev-parse HEAD)
REHEARSE_KEEP_FLAG = $(call flag,REHEARSE_KEEP,keep)

.PHONY: help setup up down wait-db createdb migrate makemigrations seed reset run \
        dev-frontend build test test-backend test-frontend coverage coverage-backend \
        coverage-frontend e2e rehearse-deploy \
        lint lint-backend lint-shell \
        lint-frontend lint-spelling format check check-backend check-deploy check-frontend \
        audit audit-backend audit-frontend backup restore reminders bounces sandbox-check \
        docs guide shell \
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

seed: ## Seed roles, plans, demo data and example content
	$(MANAGE) seed_roles
	$(MANAGE) seed_plans
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

e2e: ## Playwright end-to-end tests (own database, own server, mock payments; E2E_URL_PREFIX=/path)
	@case "$(E2E_URL_PREFIX)" in \
	  '') ;; \
	  */) echo "E2E_URL_PREFIX=$(E2E_URL_PREFIX) must not end with /" >&2; exit 2 ;; \
	  /*) ;; \
	  *) echo "E2E_URL_PREFIX=$(E2E_URL_PREFIX) must start with /" >&2; exit 2 ;; \
	esac
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
	  $(E2E_ENV) $(MANAGE) runserver 0.0.0.0:$(E2E_SERVER_PORT) --noreload > $(E2E_LOG) 2>&1 & \
	  server=$$!; \
	  proxy=; \
	  if test -n "$(E2E_URL_PREFIX)"; then \
	    : > $(E2E_PROXY_LOG); \
	    $(UV) run python $(E2E_PROXY) --port $(E2E_PORT) --upstream-port $(E2E_SERVER_PORT) \
	      --prefix "$(E2E_URL_PREFIX)" >> $(E2E_PROXY_LOG) 2>&1 & \
	    proxy=$$!; \
	  fi; \
	  trap 'pkill -P $$server >/dev/null 2>&1; kill $$server >/dev/null 2>&1; \
	        pkill -P $$geoapify >/dev/null 2>&1; kill $$geoapify >/dev/null 2>&1; \
	        test -z "$$proxy" || { pkill -P $$proxy >/dev/null 2>&1; kill $$proxy >/dev/null 2>&1; }; \
	        true' EXIT INT TERM; \
	  logs="$(E2E_LOG)"; test -z "$$proxy" || logs="$$logs and $(E2E_PROXY_LOG)"; \
	  dump_logs() { tail -n "$$1" $(E2E_LOG); test -z "$$proxy" || tail -n "$$1" $(E2E_PROXY_LOG); }; \
	  for i in $$(seq 1 60); do \
	    curl -sf -o /dev/null "$(E2E_SITE_URL)/portal/login" && break; \
	    sleep 1; \
	    test $$i -lt 60 || { echo "Django did not start; see $$logs" >&2; dump_logs 20 >&2; exit 1; }; \
	  done; \
	  bundle=$$(curl -s "$(E2E_SITE_URL)/portal/login" \
	    | sed -n 's#.*src="\($(E2E_URL_PREFIX)/static/[^"]*\.js\)".*#\1#p' | head -1); \
	  test -n "$$bundle" \
	    || { echo "The portal shell names no bundle; see $$logs" >&2; dump_logs 20 >&2; exit 1; }; \
	  curl -sf -o /dev/null "$(E2E_ORIGIN)$$bundle" \
	    || { echo "The portal bundle $$bundle is not served — the SPA would never start." >&2; \
	         dump_logs 20 >&2; exit 1; }; \
	  cd frontend && E2E_BASE_URL="$(E2E_SITE_URL)" $(NPM) run e2e \
	    || { echo; echo "==== last 100 lines of $$logs ===="; dump_logs 100; exit 1; }

rehearse-deploy: ## Rehearse the server install in a throwaway systemd container (REHEARSE_WEB_SERVER=apache|nginx, REHEARSE_URL_PREFIX=/path, REHEARSE_GUNICORN_PORT=port, REHEARSE_DB_PORT=port, REHEARSE_SEED=content|demo|all)
	@case "$(REHEARSE_WEB_SERVER)" in apache|nginx) ;; \
	  *) echo "REHEARSE_WEB_SERVER=$(REHEARSE_WEB_SERVER) is not apache or nginx" >&2; exit 2 ;; esac
	@case "$(REHEARSE_URL_PREFIX)" in ''|/*) ;; \
	  *) echo "REHEARSE_URL_PREFIX=$(REHEARSE_URL_PREFIX) does not start with /" >&2; exit 2 ;; esac
	@for pair in "REHEARSE_GUNICORN_PORT=$(REHEARSE_GUNICORN_PORT)" "REHEARSE_DB_PORT=$(REHEARSE_DB_PORT)"; do \
	  case "$${pair#*=}" in ''|[1-9]|[1-9][0-9]|[1-9][0-9][0-9]|[1-9][0-9][0-9][0-9]|[1-9][0-9][0-9][0-9][0-9]) ;; \
	    *) echo "$$pair is not a port number" >&2; exit 2 ;; esac; \
	done
	@case "$(REHEARSE_SEED)" in ''|content|demo|all) ;; \
	  *) echo "REHEARSE_SEED=$(REHEARSE_SEED) is not content, demo, or all" >&2; exit 2 ;; esac
	@test -z "$$(git status --porcelain)" \
	  || echo "note: the rehearsal installs HEAD; uncommitted changes are not in it" >&2
	@set -euo pipefail; \
	  name=$(REHEARSE_NAME); keep="$(REHEARSE_KEEP_FLAG)"; started=$$(date +%s); \
	  prefix="$(REHEARSE_URL_PREFIX)"; standin="$(REHEARSE_STANDIN)"; \
	  port="$(REHEARSE_GUNICORN_PORT)"; dbport="$(REHEARSE_DB_PORT)"; \
	  seed="$(REHEARSE_SEED)"; \
	  log=$$(mktemp); \
	  inside() { docker exec "$$name" "$$@"; }; \
	  configtest() { \
	    if [ "$(REHEARSE_WEB_SERVER)" = apache ]; then inside apachectl configtest; else inside nginx -t; fi; \
	  }; \
	  site() { inside curl -sk --resolve caldart.test:443:127.0.0.1 "$$@"; }; \
	  check_ports() { \
	    if [ -n "$$port" ]; then \
	      echo "==> Checking that the web server proxies to gunicorn on port $$port $$1"; \
	      inside grep -rqF "127.0.0.1:$$port" $(REHEARSE_CONFIG_DIR) \
	        || { echo "error: nothing in $(REHEARSE_CONFIG_DIR) proxies to 127.0.0.1:$$port $$1" >&2; exit 1; }; \
	      if inside grep -rqF "127.0.0.1:8001" $(REHEARSE_CONFIG_DIR); then \
	        echo "error: $(REHEARSE_CONFIG_DIR) still proxies to 127.0.0.1:8001 $$1" >&2; exit 1; \
	      fi; \
	      inside grep -qx "CALDART_GUNICORN_PORT=$$port" /etc/caldart/caldart.env \
	        || { echo "error: /etc/caldart/caldart.env does not set CALDART_GUNICORN_PORT=$$port $$1" >&2; exit 1; }; \
	      direct=$$(inside curl -s -o /dev/null -w '%{http_code}' -H 'Host: caldart.test' \
	        -H 'X-Forwarded-Proto: https' "http://127.0.0.1:$$port/"); \
	      [ "$$direct" = 200 ] \
	        || { echo "error: gunicorn on 127.0.0.1:$$port answered $$direct, not 200, $$1" >&2; exit 1; }; \
	      site -o /dev/null -w '%{http_code}\n' "https://caldart.test$$prefix/" | grep -qx 200 \
	        || { echo "error: the site does not answer 200 through the proxy $$1" >&2; exit 1; }; \
	    fi; \
	    if [ -n "$$dbport" ]; then \
	      echo "==> Checking that Postgres is published on port $$dbport $$1"; \
	      inside docker port caldart-db-1 5432 | grep -qx "127.0.0.1:$$dbport" \
	        || { echo "error: the database container is not published on 127.0.0.1:$$dbport $$1" >&2; exit 1; }; \
	    fi; \
	  }; \
	  cleanup() { \
	    status=$$?; \
	    rm -f "$$log"; \
	    echo "==> rehearsal on $(REHEARSE_WEB_SERVER)$${prefix:+ under $$prefix}$${port:+ with gunicorn on $$port}$${dbport:+ and Postgres on $$dbport}$${seed:+, seeded ($$seed)} took $$(( $$(date +%s) - started ))s and exited $$status"; \
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
	  if [ -n "$$prefix" ]; then \
	    echo "==> Standing in for an existing $(REHEARSE_WEB_SERVER) site at https://caldart.test/"; \
	    server_package=$$([ "$(REHEARSE_WEB_SERVER)" = apache ] && echo apache2 || echo nginx); \
	    inside env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq openssl "$$server_package" >/dev/null; \
	    inside mkdir -p /etc/ssl/standin /var/www/standin; \
	    inside openssl req -x509 -newkey rsa:2048 -nodes -days 30 -subj /CN=caldart.test \
	      -addext subjectAltName=DNS:caldart.test \
	      -keyout /etc/ssl/standin/privkey.pem -out /etc/ssl/standin/fullchain.pem 2>/dev/null; \
	    inside sh -c 'echo "$(REHEARSE_STANDIN_PAGE)" > /var/www/standin/index.html'; \
	    inside cp /mnt/caldart/frontend/e2e/rehearsal/$(REHEARSE_WEB_SERVER).conf "$$standin"; \
	    if [ "$(REHEARSE_WEB_SERVER)" = apache ]; then \
	      inside a2enmod -q ssl; inside a2ensite -q standin; \
	    else \
	      inside ln -sfn "$$standin" /etc/nginx/sites-enabled/standin; \
	    fi; \
	    configtest; \
	    inside systemctl reload-or-restart "$$server_package"; \
	    site https://caldart.test/ | grep -qF "$(REHEARSE_STANDIN_PAGE)" \
	      || { echo "error: the stand-in site does not answer" >&2; exit 1; }; \
	    set -- --tls existing --url-prefix "$$prefix" --attach-to "$$standin" --email local; \
	  else \
	    set -- --tls self-signed --email-url smtp://localhost:25; \
	  fi; \
	  if [ -n "$$port" ]; then set -- "$$@" --gunicorn-port "$$port"; fi; \
	  if [ -n "$$dbport" ]; then set -- "$$@" --db-port "$$dbport"; fi; \
	  case "$$seed" in content) set -- "$$@" --seed-content ;; demo) set -- "$$@" --seed-demo ;; \
	    all) set -- "$$@" --seed-demo --seed-content ;; esac; \
	  inside bash /mnt/caldart/deploy/bootstrap.sh --repo /mnt/caldart --ref "$(REHEARSE_REF)" \
	    --hostname caldart.test --web-server $(REHEARSE_WEB_SERVER) \
	    --admin-email admin@caldart.test "$$@" 2>&1 | tee "$$log"; \
	  if [ -n "$$prefix" ]; then \
	    echo "==> Checking the note about port 25, the stand-in page, and the bare prefix"; \
	    grep -qF "Nothing listens on port 25 on this machine" "$$log" \
	      || { echo "error: the install printed no note about port 25" >&2; exit 1; }; \
	    site https://caldart.test/ | grep -qF "$(REHEARSE_STANDIN_PAGE)" \
	      || { echo "error: the stand-in site no longer answers at /" >&2; exit 1; }; \
	    bare=$$(site -o /dev/null -w '%{http_code} %{redirect_url}' "https://caldart.test$$prefix"); \
	    [ "$$bare" = "301 https://caldart.test$$prefix/" ] \
	      || { echo "error: https://caldart.test$$prefix answered $$bare, not a redirect to $$prefix/" >&2; exit 1; }; \
	  fi; \
	  echo "==> Checking the layout: the checkout in /opt/caldart/caldart, the data beside it"; \
	  inside test -e /opt/caldart/caldart/.git \
	    || { echo "error: /opt/caldart/caldart is not a git checkout" >&2; exit 1; }; \
	  inside sh -c 'ls /opt/caldart/backups/*.sql.gz' >/dev/null 2>&1 \
	    || { echo "error: /opt/caldart/backups holds no dump after the install" >&2; exit 1; }; \
	  [ "$$(inside stat -c %U:%G /opt/caldart/media)" = caldart:caldart ] \
	    || { echo "error: /opt/caldart/media is missing or not owned by caldart" >&2; exit 1; }; \
	  for inner in /opt/caldart/backend /opt/caldart/caldart/backups /opt/caldart/caldart/backend/media; do \
	    if inside test -e "$$inner"; then echo "error: $$inner exists; the data belongs beside the checkout" >&2; exit 1; fi; \
	  done; \
	  [ -z "$$(inside git -C /opt/caldart/caldart status --porcelain)" ] \
	    || { echo "error: the install left files in the checkout that git sees" >&2; exit 1; }; \
	  check_ports "after the install"; \
	  if [ -n "$$seed" ]; then \
	    echo "==> Installing postfix, so the seeded jobs have a mail transport"; \
	    : "Either seed gives the scheduled jobs mail to send (the website seed"; \
	    : "creates the DARTs whose rosters caldart-reports mails), and the"; \
	    : "container has no mail transport of its own."; \
	    inside bash -c "printf '%s\n' 'postfix postfix/main_mailer_type select Internet Site' \
	      'postfix postfix/mailname string caldart.test' | debconf-set-selections"; \
	    inside env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq postfix >/dev/null; \
	    inside systemctl start postfix; \
	  fi; \
	  if [ "$$seed" = demo ] || [ "$$seed" = all ]; then \
	    echo "==> Enabling mock payments, so the seeded renewals can run for real"; \
	    : "seed_demo's renewal mandates use the mock provider so the scheduled jobs"; \
	    : "have something to do; production leaves it off, so the demo needs it named"; \
	    : "here, the same way an operator demonstrating checkout would."; \
	    inside sh -c 'echo PAYMENTS_MOCK_ENABLED_IN_PRODUCTION=true >> /etc/caldart/caldart.env'; \
	    echo "==> Checking that the demo accounts did not disturb health or sign-in"; \
	    inside /opt/caldart/caldart/deploy/manage.sh health --json >/dev/null \
	      || { echo "error: manage.sh health --json failed after seeding" >&2; exit 1; }; \
	    site -o /dev/null -w '%{http_code}\n' "https://caldart.test$$prefix/portal/login" | grep -qx 200 \
	      || { echo "error: the sign-in page does not answer after seeding" >&2; exit 1; }; \
	  fi; \
	  if [ "$$seed" = content ] || [ "$$seed" = all ]; then \
	    echo "==> Checking that the example website is there, photograph included"; \
	    site -o /dev/null -w '%{http_code}\n' "https://caldart.test$$prefix/about/" | grep -qx 200 \
	      || { echo "error: the seeded About Us page does not answer 200" >&2; exit 1; }; \
	    hero=$$(site "https://caldart.test$$prefix/" | grep -o 'src="[^"]*/media/[^"]*"' | head -1 | cut -d'"' -f2); \
	    [ -n "$$hero" ] || { echo "error: the seeded home page carries no photograph from /media/" >&2; exit 1; }; \
	    site -o /dev/null -w '%{http_code}\n' "https://caldart.test$$hero" | grep -qx 200 \
	      || { echo "error: the home page's photograph $$hero does not answer 200" >&2; exit 1; }; \
	  fi; \
	  if [ "$$seed" = content ]; then \
	    echo "==> Checking that the website seed created no demo account"; \
	    inside /opt/caldart/caldart/deploy/manage.sh shell -c \
	      'from apps.accounts.models import User; import sys; sys.exit(0 if User.objects.count() == 1 else 1)' \
	      || { echo "error: a website-only install holds more than the administrator's account" >&2; exit 1; }; \
	  fi; \
	  echo "==> Checking that the portal loads its entry under the name Vite gave it"; \
	  entry=$$(inside python3 -c 'import json; print(json.load(open("/opt/caldart/caldart/frontend/dist/.vite/manifest.json"))["src/portal/main.tsx"]["file"])'); \
	  site "https://caldart.test$$prefix/portal/login" | grep -qF "static/$$entry\"" \
	    || { echo "error: the portal page does not load its entry as $$entry, the name its chunks import" >&2; exit 1; }; \
	  : "The install started the registry import itself; it downloads the FAA file."; \
	  echo "==> Running every other scheduled job once, hardening and all"; \
	  inside systemctl start caldart-backup.service caldart-reports.service \
	    caldart-renewals.service caldart-reminders.service caldart-statements.service \
	    caldart-bounces.service; \
	  echo "==> Rehearsing a database reset"; \
	  inside /opt/caldart/caldart/deploy/reset-database.sh --yes --admin-email admin@caldart.test; \
	  inside /opt/caldart/caldart/deploy/manage.sh shell -c \
	    'from apps.accounts.models import User; import sys; sys.exit(0 if User.objects.count() == 1 else 1)' \
	    || { echo "error: the reset left more than the administrator's account" >&2; exit 1; }; \
	  inside /opt/caldart/caldart/deploy/manage.sh health --json >/dev/null \
	    || { echo "error: manage.sh health --json failed after the reset" >&2; exit 1; }; \
	  site -o /dev/null -w '%{http_code}\n' "https://caldart.test$$prefix/portal/login" | grep -qx 200 \
	    || { echo "error: the sign-in page does not answer after the reset" >&2; exit 1; }; \
	  site -o /dev/null -w '%{http_code}\n' "https://caldart.test$$prefix/about/" | grep -qx 404 \
	    || { echo "error: the reset left the example website's About Us page" >&2; exit 1; }; \
	  echo "==> Rehearsing the website seed, twice"; \
	  pages() { inside /opt/caldart/caldart/deploy/manage.sh shell -c \
	    'from wagtail.models import Page; print(Page.objects.count())' | tr -d '\r'; }; \
	  inside /opt/caldart/caldart/deploy/seed.sh --content; \
	  first=$$(pages); \
	  inside /opt/caldart/caldart/deploy/seed.sh --content; \
	  [ "$$first" = "$$(pages)" ] \
	    || { echo "error: a second website seed changed the page count from $$first" >&2; exit 1; }; \
	  site -o /dev/null -w '%{http_code}\n' "https://caldart.test$$prefix/about/" | grep -qx 200 \
	    || { echo "error: the seeded About Us page does not answer 200 after the reset" >&2; exit 1; }; \
	  echo "==> Rehearsing an upgrade that changes nothing"; \
	  inside /opt/caldart/caldart/deploy/upgrade.sh; \
	  check_ports "after the upgrade"; \
	  echo "==> Rehearsing a second install with no flags"; \
	  before=$$(inside sha256sum /etc/caldart/caldart.env /etc/caldart/install.conf); \
	  inside /opt/caldart/caldart/deploy/install.sh; \
	  after=$$(inside sha256sum /etc/caldart/caldart.env /etc/caldart/install.conf); \
	  [ "$$before" = "$$after" ] \
	    || { echo "error: a no-flag install changed the environment file or the install record" >&2; exit 1; }; \
	  check_ports "after the second install"; \
	  echo "==> Rehearsing the uninstall"; \
	  inside /opt/caldart/caldart/deploy/uninstall.sh --yes --purge; \
	  inside test ! -e /opt/caldart; \
	  inside test ! -e /etc/caldart; \
	  if [ -n "$$prefix" ]; then \
	    echo "==> Checking the stand-in vhost after the uninstall"; \
	    if inside grep -q 'caldart\.conf' "$$standin"; then \
	      echo "error: $$standin still includes the snippet" >&2; exit 1; \
	    fi; \
	    configtest; \
	  fi; \
	  echo "==> The rehearsal on $(REHEARSE_WEB_SERVER)$${prefix:+ under $$prefix}$${port:+ with gunicorn on $$port}$${dbport:+ and Postgres on $$dbport}$${seed:+, seeded ($$seed)} passed"

# ----------------------------------------------------------------- lint
lint: lint-backend lint-shell lint-frontend lint-spelling ## ruff + mypy + shellcheck + tsc + eslint + prettier + contrast + codespell

lint-backend: ## ruff check + ruff format --check + mypy
	$(UV) run ruff check .
	$(UV) run ruff format --check .
	$(UV) run mypy backend $(E2E_PROXY)

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

bounces: ## Read the bounce mailbox and mark what bounced (make bounces DRY_RUN=1)
	$(MANAGE) check_bounces $(call flag,DRY_RUN,--dry-run)

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
