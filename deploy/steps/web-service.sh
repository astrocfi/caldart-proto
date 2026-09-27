#!/usr/bin/env bash
#
# CalDART install step 7 - gunicorn under systemd.
#
# Installs caldart-web.service into /etc/systemd/system with the deploy root
# written in, enables it, and restarts it: a restart starts a stopped unit and
# picks up new code on an upgrade.  Then waits up to 30 seconds for gunicorn on
# 127.0.0.1:8001 to answer 200 for the hostname, and on a timeout prints the
# unit's last 30 journal lines and fails.
#
# Usage:
#   sudo deploy/steps/web-service.sh [--dry-run]
#
# Options:
#   --dry-run   print every state-changing command instead of running it
#   --help      show this help

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=deploy/lib.sh
source "$ROOT/deploy/lib.sh"

readonly WEB_READY_SECONDS=30
readonly GUNICORN_URL=http://127.0.0.1:8001/

# True when gunicorn answers 200 for the hostname.  The Host header must be in
# ALLOWED_HOSTS, and X-Forwarded-Proto keeps SECURE_SSL_REDIRECT from answering 301.
web_answers() {
    [[ "$(web_probe)" == 200 ]]
}

# The status gunicorn answers for the hostname.
web_probe() {
    curl -sI -o /dev/null -w '%{http_code}' -H "Host: $CALDART_HOSTNAME" \
        -H 'X-Forwarded-Proto: https' "$GUNICORN_URL"
}

web_service_step() {
    require_hostname
    log "Installing and restarting $WEB_UNIT.service"
    render_file "$ROOT/deploy/systemd/$WEB_UNIT.service" "$SYSTEMD_DIR/$WEB_UNIT.service"
    run systemctl daemon-reload
    run systemctl enable "$WEB_UNIT.service"
    run systemctl restart "$WEB_UNIT.service"
    if is_dry_run; then
        run curl -sI -H "Host: $CALDART_HOSTNAME" -H 'X-Forwarded-Proto: https' "$GUNICORN_URL"
        return 0
    fi
    if ! wait_for "$WEB_READY_SECONDS" web_answers; then
        journalctl -u "$WEB_UNIT" -n 30 --no-pager >&2 || true
        die "$WEB_UNIT did not answer 200 on $GUNICORN_URL within ${WEB_READY_SECONDS} seconds"
    fi
}

web_service_main() {
    parse_step_flags "${BASH_SOURCE[0]}" "$@"
    require_root
    load_record
    web_service_step
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    web_service_main "$@"
fi
