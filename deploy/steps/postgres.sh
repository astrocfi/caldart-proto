#!/usr/bin/env bash
#
# CalDART install step - Postgres in Docker.
#
# Starts the compose "db" service from the repository's docker-compose.yml (the
# database alone; Mailpit is a development container and never starts on a
# server), published on 127.0.0.1 at the install record's CALDART_DB_PORT
# (default 5432), and waits up to 60 seconds for it to accept connections.  On a
# run that creates the container, it first stops when something on this machine
# already listens on that port, such as another Postgres; install.sh --db-port
# moves CalDART's to a free one.  During the first run of install.sh, before
# the environment file exists, it also replaces the development password with
# a generated one, handing the statement to psql on standard input so the
# password never appears on a command line, and passes the password to the
# configure step in a shell variable.  Run alone, or once the environment file
# exists, it only starts the service and waits: the password is whatever that
# file says.
#
# Usage:
#   sudo deploy/steps/postgres.sh [--dry-run]
#
# Options:
#   --dry-run   print every state-changing command instead of running it
#   --help      show this help

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=deploy/lib.sh
source "$ROOT/deploy/lib.sh"

readonly DB_READY_SECONDS=60
# What Compose names the db service's container in the project "caldart".
readonly DB_CONTAINER=caldart-db-1

# The password configure.sh writes into DATABASE_URL; set here on a first install.
DB_PASSWORD="${DB_PASSWORD:-}"

# Stop when the port is taken and the container that would take it does not
# exist yet.  A container that exists already holds the port itself.
postgres_check_port() {
    docker container inspect "$DB_CONTAINER" >/dev/null 2>&1 && return 0
    port_in_use "$CALDART_DB_PORT" || return 0
    die "port $CALDART_DB_PORT is already in use on this machine; run install.sh --db-port PORT to put CalDART's Postgres on another port"
}

postgres_step() {
    log "Starting Postgres on 127.0.0.1:$CALDART_DB_PORT"
    postgres_check_port
    run cd "$ROOT"
    run docker compose up -d db
    wait_for "$DB_READY_SECONDS" docker compose exec -T db pg_isready -U caldart -d caldart \
        || die "Postgres did not accept connections within ${DB_READY_SECONDS} seconds"
}

# Replace the development password with a generated one and keep it in
# DB_PASSWORD for configure.sh.  install.sh calls this only while the
# environment file does not exist yet.
postgres_set_password() {
    log "Setting a generated database password"
    DB_PASSWORD="$(generate_secret "$DB_PASSWORD_BYTES")"
    run_stdin "ALTER USER caldart WITH PASSWORD '${DB_PASSWORD}';" \
        docker compose exec -T db psql -q -v ON_ERROR_STOP=1 -U caldart -d postgres
}

postgres_main() {
    parse_step_flags "${BASH_SOURCE[0]}" "$@"
    require_root
    load_record
    postgres_step
    if ! have_env_file; then
        note "The database password is set by deploy/install.sh, together with $ENV_FILE."
    fi
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    postgres_main "$@"
fi
