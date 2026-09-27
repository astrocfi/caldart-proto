#!/usr/bin/env bash
#
# CalDART install step - the service user and its directories.
#
# Creates the "caldart" system user when it is missing, with the deploy root as
# its home and no login shell; /etc/caldart, root-owned and readable by the
# caldart group; and the three directories inside the checkout the web unit may
# write: backend/media, backend/staticfiles, and backups.  The user is not in
# the docker group: nothing the services run talks to Docker.
#
# Usage:
#   sudo deploy/steps/user.sh [--dry-run]
#
# Options:
#   --dry-run   print every state-changing command instead of running it
#   --help      show this help

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=deploy/lib.sh
source "$ROOT/deploy/lib.sh"

user_step() {
    log "Creating the $SERVICE_USER user and its directories"
    if ! id -u "$SERVICE_USER" >/dev/null 2>&1; then
        run useradd --system --home-dir "$ROOT" --shell /usr/sbin/nologin "$SERVICE_USER"
    fi
    run install -d -o root -g "$SERVICE_USER" -m 0750 "$ETC_DIR"
    run install -d -o "$SERVICE_USER" -g "$SERVICE_USER" \
        "$ROOT/backend/media" "$ROOT/backend/staticfiles" "$ROOT/backups"
}

user_main() {
    parse_step_flags "${BASH_SOURCE[0]}" "$@"
    require_root
    user_step
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    user_main "$@"
fi
