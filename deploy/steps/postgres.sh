#!/usr/bin/env bash
#
# CalDART install step - Postgres in Docker.
#
# Starts the compose "db" service from the repository's docker-compose.yml (the
# database alone; Mailpit is a development container and never starts on a
# server) and waits up to 60 seconds for it to accept connections.  During the
# first run of install.sh, before the environment file exists, it also replaces
# the development password with a generated one, handing the statement to psql
# on standard input so the password never appears on a command line, and passes
# the password to the configure step in a shell variable.  Run alone, or once
# the environment file exists, it only starts the service and waits: the
# password is whatever that file says.
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

# The password configure.sh writes into DATABASE_URL; set here on a first install.
DB_PASSWORD="${DB_PASSWORD:-}"

postgres_step() {
    log "Starting Postgres"
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
    postgres_step
    if ! have_env_file; then
        note "The database password is set by deploy/install.sh, together with $ENV_FILE."
    fi
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    postgres_main "$@"
fi
