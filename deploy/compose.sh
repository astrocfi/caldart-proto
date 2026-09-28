#!/usr/bin/env bash
#
# CalDART - run docker compose against the server's database container.
#
# Loads the install record, exports its CALDART_DB_PORT (the host port
# docker-compose.yml publishes Postgres on), changes to the checkout, and
# runs docker compose with the arguments given.  Running docker compose
# directly works too, but a command that starts the container without the
# variable publishes it on 5432 instead of the recorded port.  The command's
# exit status is this script's.
#
# Usage:
#   sudo deploy/compose.sh [--dry-run] COMMAND [ARGUMENTS...]
#
# Options (before COMMAND; everything from COMMAND on goes to docker compose):
#   --dry-run   print the docker compose command instead of running it
#   --help      show this help
#
# Examples:
#   sudo deploy/compose.sh ps
#   sudo deploy/compose.sh logs -f db
#   sudo deploy/compose.sh exec -T db psql -U caldart -d caldart

set -euo pipefail

CHECKOUT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=deploy/lib.sh
source "$CHECKOUT/deploy/lib.sh"

main() {
    while (($#)); do
        case "$1" in
            --dry-run) enable_dry_run ;;
            --help)
                print_help "${BASH_SOURCE[0]}"
                exit 0
                ;;
            *) break ;;
        esac
        shift
    done
    (($#)) || usage_error "name the docker compose command to run"
    require_root
    load_record
    if is_dry_run; then
        run cd "$CHECKOUT"
        run env "CALDART_DB_PORT=$CALDART_DB_PORT" docker compose "$@"
        return 0
    fi
    cd "$CHECKOUT"
    exec docker compose "$@"
}

main "$@"
