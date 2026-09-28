#!/usr/bin/env bash
#
# CalDART install step - the service user and its directories.
#
# Creates the "caldart" system user when it is missing, with /home/caldart as
# its home (created with it) and no login shell, and moves an existing user's
# home there when it is somewhere else, the checkout for one; /etc/caldart,
# root-owned and readable by the caldart group; and the three directories the
# web unit may write, owned by the user: backups and media in the deploy root
# (the database dumps and the uploads, beside the checkout rather than in it),
# and backend/staticfiles in the checkout.  A reinstall keeps whatever backups
# and media already hold.  The home directory is never the checkout, and never
# has to hold anything: the units keep it out of reach (ProtectHome) and the
# services write only those three directories.  The user is not in the docker
# group: nothing the services run talks to Docker.
#
# Usage:
#   sudo deploy/steps/user.sh [--dry-run]
#
# Options:
#   --dry-run   print every state-changing command instead of running it
#   --help      show this help

set -euo pipefail

CHECKOUT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=deploy/lib.sh
source "$CHECKOUT/deploy/lib.sh"

# The home directory the service user gets: its own, never the checkout.
readonly SERVICE_HOME=/home/$SERVICE_USER

# The home directory the service user has now, or nothing when there is no user.
current_home() {
    getent passwd "$SERVICE_USER" | cut -d: -f6
}

user_step() {
    log "Creating the $SERVICE_USER user and its directories"
    if ! id -u "$SERVICE_USER" >/dev/null 2>&1; then
        run useradd --system --create-home --home-dir "$SERVICE_HOME" \
            --shell /usr/sbin/nologin "$SERVICE_USER"
    elif [[ "$(current_home)" != "$SERVICE_HOME" ]]; then
        # An install from before the home moved: give the user its own directory
        # and point the account at it, leaving the old home (the checkout) as it is.
        run install -d -o "$SERVICE_USER" -g "$SERVICE_USER" -m 0750 "$SERVICE_HOME"
        run usermod --home "$SERVICE_HOME" "$SERVICE_USER"
    fi
    run install -d -o root -g "$SERVICE_USER" -m 0750 "$ETC_DIR"
    run install -d -o "$SERVICE_USER" -g "$SERVICE_USER" \
        "$ROOT/backups" "$ROOT/media" "$CHECKOUT/backend/staticfiles"
    # The web server reads the uploads as its own user, so every directory under
    # media/ must let others in: the site creates new ones 0755, and this repairs
    # any an earlier run left 0750.
    run find "$ROOT/media" -type d -exec chmod 0755 '{}' +
}

user_main() {
    parse_step_flags "${BASH_SOURCE[0]}" "$@"
    require_root
    user_step
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    user_main "$@"
fi
