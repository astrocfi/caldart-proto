#!/usr/bin/env bash
#
# CalDART install step - the database and the static files.
#
# Through deploy/manage.sh: applies the migrations, creates the cache table,
# creates the roles, and collects the static files.  With --seed-demo it also
# loads the demo accounts (the same data development seeds with make seed),
# with --seed-content it loads the example pages, and with --admin-email it
# creates the first administrator (or gives an existing account the
# administrator's roles) and keeps the one-time password-reset link
# create_admin prints for the summary.
#
# Usage:
#   sudo deploy/steps/database.sh [options]
#
# Options:
#   --admin-email ADDRESS   create the first administrator with this address
#   --seed-demo             load the demo accounts
#   --seed-content          load the example pages
#   --dry-run               print every state-changing command instead of running it
#   --help                  show this help

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=deploy/lib.sh
source "$ROOT/deploy/lib.sh"

readonly MANAGE="$ROOT/deploy/manage.sh"

ADMIN_EMAIL="${ADMIN_EMAIL:-}"
SEED_DEMO="${SEED_DEMO:-no}"
SEED_CONTENT="${SEED_CONTENT:-no}"
# The link create_admin printed, for check.sh's summary.
ADMIN_LINK="${ADMIN_LINK:-}"

database_step() {
    log "Preparing the database"
    "$MANAGE" migrate
    "$MANAGE" createcachetable
    "$MANAGE" seed_roles
    if [[ "$SEED_DEMO" == yes ]]; then
        "$MANAGE" seed_demo
    fi
    if [[ "$SEED_CONTENT" == yes ]]; then
        "$MANAGE" seed_content
    fi

    log "Collecting the static files"
    "$MANAGE" collectstatic --noinput

    if [[ -n "$ADMIN_EMAIL" ]]; then
        log "Creating the administrator $ADMIN_EMAIL"
        if is_dry_run; then
            "$MANAGE" create_admin --email "$ADMIN_EMAIL"
            ADMIN_LINK='<the one-time link create_admin prints>'
        else
            ADMIN_LINK="$("$MANAGE" create_admin --email "$ADMIN_EMAIL" | tr -d '\r')"
        fi
    fi
}

database_main() {
    while (($#)); do
        case "$1" in
            --admin-email)
                ADMIN_EMAIL="$(option_value "$1" "${2:-}")"
                shift
                ;;
            --seed-demo) SEED_DEMO=yes ;;
            --seed-content) SEED_CONTENT=yes ;;
            --dry-run) enable_dry_run ;;
            --help)
                print_help "${BASH_SOURCE[0]}"
                exit 0
                ;;
            *) usage_error "unknown option $1" ;;
        esac
        shift
    done
    require_root
    database_step
    if [[ -n "$ADMIN_LINK" ]]; then
        printf 'Set the administrator'\''s password at: %s\n' "$ADMIN_LINK"
    fi
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    database_main "$@"
fi
