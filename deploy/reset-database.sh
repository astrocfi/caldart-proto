#!/usr/bin/env bash
#
# CalDART - empty the site's database and start it again from nothing.
#
# Takes a backup, stops caldart-web and the scheduled jobs, drops every table
# (manage.py db_reset), runs the database step again (the migrations, the cache
# table, the role groups, the membership plans, the static files, and, with the
# flags below, the administrator and the seed data), then starts the site and
# the timers again and starts an import of the FAA registry, whose table is
# empty too.  What is left is the database of a fresh install: no accounts, no
# payments, no pages but the blank home page.  The environment file, the
# install record, the web server, the backups, and the uploads in media/ are
# not touched; the uploads stay on disk with nothing in the database naming
# them.  To undo a reset, restore the backup it took (deploy/README.rst,
# Restoring).
#
# Without --admin-email or --seed-demo nobody can sign in afterwards; create an
# administrator then with sudo deploy/manage.sh create_admin --email ADDRESS.
#
# Usage:
#   sudo deploy/reset-database.sh --yes [--admin-email ADDRESS] [--seed-content]
#                                 [--seed-demo] [--dry-run]
#
# Options:
#   --yes                   confirm; without it nothing runs
#   --admin-email ADDRESS   create the administrator with this address and print
#                           the one-time link that sets its password
#   --seed-content          load the example website (see deploy/seed.sh)
#   --seed-demo             load the demo accounts (see deploy/seed.sh)
#   --dry-run               print every state-changing command instead of running it
#   --help                  show this help

set -euo pipefail

CHECKOUT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=deploy/lib.sh
source "$CHECKOUT/deploy/lib.sh"

readonly MANAGE="$CHECKOUT/deploy/manage.sh"
# The job that refills the FAA registry's table.
readonly REGISTRY_UNIT=caldart-registry

CONFIRMED=no
ADMIN_EMAIL=""
DATABASE_FLAGS=()

parse_flags() {
    while (($#)); do
        case "$1" in
            --yes) CONFIRMED=yes ;;
            --admin-email)
                ADMIN_EMAIL="$(option_value "$1" "${2:-}")"
                DATABASE_FLAGS+=(--admin-email "$ADMIN_EMAIL")
                shift
                ;;
            --seed-content | --seed-demo) DATABASE_FLAGS+=("$1") ;;
            --dry-run) enable_dry_run ;;
            --help)
                print_help "${BASH_SOURCE[0]}"
                exit 0
                ;;
            *) usage_error "unknown option $1" ;;
        esac
        shift
    done
    [[ "$CONFIRMED" == yes ]] || usage_error "--yes is required: this deletes every row in the database"
}

# The site and every timer, so nothing writes while the tables go.
site_units() {
    printf '%s\n' "$WEB_UNIT.service" "${JOB_UNITS[@]/%/.timer}"
}

main() {
    parse_flags "$@"
    require_root
    local units=()
    mapfile -t units < <(site_units)

    log "Taking a database backup"
    "$MANAGE" db_backup

    log "Stopping the site and the scheduled jobs"
    # The job services too: a job the timer already started must not run on.
    run systemctl stop "${units[@]}" "${JOB_UNITS[@]/%/.service}"

    log "Emptying the database"
    "$MANAGE" db_reset --noinput

    # A separate process, as the upgrade runs it; it prints the administrator's link.
    "$CHECKOUT/deploy/steps/database.sh" "${DATABASE_FLAGS[@]}"

    log "Starting the site and the scheduled jobs"
    run systemctl start "${units[@]}"
    log "Refilling the FAA registry in the background"
    run systemctl start --no-block "$REGISTRY_UNIT.service"

    if [[ -z "$ADMIN_EMAIL" && " ${DATABASE_FLAGS[*]} " != *" --seed-demo "* ]]; then
        note "no account can sign in yet; create an administrator with:" \
            "sudo $MANAGE create_admin --email ADDRESS"
    fi
    log "Database reset"
}

main "$@"
