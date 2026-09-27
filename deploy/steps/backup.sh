#!/usr/bin/env bash
#
# CalDART install step 10 - a backup now.
#
# Takes one database dump through deploy/manage.sh db_backup, so a fresh
# install has a dump before the nightly timer first runs.
#
# Usage:
#   sudo deploy/steps/backup.sh [--dry-run]
#
# Options:
#   --dry-run   print every state-changing command instead of running it
#   --help      show this help

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=deploy/lib.sh
source "$ROOT/deploy/lib.sh"

backup_step() {
    log "Taking a database backup"
    "$ROOT/deploy/manage.sh" db_backup
}

backup_main() {
    parse_step_flags "${BASH_SOURCE[0]}" "$@"
    require_root
    backup_step
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    backup_main "$@"
fi
