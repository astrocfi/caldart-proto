#!/usr/bin/env bash
#
# CalDART install step - the scheduled jobs.
#
# Installs the eight service and timer pairs under deploy/systemd/ (the FAA
# registry import, the scheduled reports, the automatic renewals, the renewal
# reminders, the year-end statements, the hourly bounce check, the bulk email
# sender that runs every minute, and the nightly backup) into
# /etc/systemd/system with the checkout and the deploy root written in, enables and starts each
# timer, and starts one registry import at once so the aircraft type picker
# has its vocabulary before anybody opens it.  Reinstalling the units is how
# an upgrade picks up a changed one.
#
# Usage:
#   sudo deploy/steps/timers.sh [--dry-run]
#
# Options:
#   --dry-run   print every state-changing command instead of running it
#   --help      show this help

set -euo pipefail

CHECKOUT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=deploy/lib.sh
source "$CHECKOUT/deploy/lib.sh"

timers_step() {
    local unit suffix
    log "Installing the scheduled jobs"
    for unit in "${JOB_UNITS[@]}"; do
        for suffix in service timer; do
            render_file "$CHECKOUT/deploy/systemd/$unit.$suffix" "$SYSTEMD_DIR/$unit.$suffix"
        done
    done
    run systemctl daemon-reload
    for unit in "${JOB_UNITS[@]}"; do
        run systemctl enable --now "$unit.timer"
    done
    run systemctl start --no-block caldart-registry.service
}

timers_main() {
    parse_step_flags "${BASH_SOURCE[0]}" "$@"
    require_root
    timers_step
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    timers_main "$@"
fi
