#!/usr/bin/env bash
#
# CalDART install step - gunicorn under systemd.
#
# Installs caldart-web.service into /etc/systemd/system with the deploy root
# written in, enables it, and restarts it: a restart starts a stopped unit and
# picks up new code, or a new port, on an upgrade or a later install.  Then
# waits up to 30 seconds for gunicorn on 127.0.0.1 at the recorded gunicorn
# port (8001 unless install.sh --gunicorn-port says otherwise) to answer 200 for
# the hostname, and on a timeout prints the unit's last 30 journal lines and
# fails.
#
# Before the unit is installed, a port something already listens on stops the
# step with an error naming --gunicorn-port.  Once it is installed, the listener
# is gunicorn itself, and the step does not look.
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

# The address gunicorn answers on, from the recorded port.
gunicorn_url() {
    printf 'http://127.0.0.1:%s/\n' "$CALDART_GUNICORN_PORT"
}

# True when caldart-web.service is installed, so the port's listener is gunicorn.
web_unit_installed() {
    [[ -e "$SYSTEMD_DIR/$WEB_UNIT.service" ]]
}

# Stop when a service unit not yet installed would start on a port another
# program holds: gunicorn would fail to bind, and the wait would time out.
check_gunicorn_port() {
    web_unit_installed && return 0
    port_in_use "$CALDART_GUNICORN_PORT" || return 0
    die "port $CALDART_GUNICORN_PORT is already in use on this machine; run install.sh --gunicorn-port PORT to put gunicorn on another port"
}

# True when gunicorn answers 200 for the hostname.  The Host header must be in
# ALLOWED_HOSTS, and X-Forwarded-Proto keeps SECURE_SSL_REDIRECT from answering 301.
web_answers() {
    [[ "$(web_probe)" == 200 ]]
}

# The status gunicorn answers for the hostname.
web_probe() {
    curl -sI -o /dev/null -w '%{http_code}' -H "Host: $CALDART_HOSTNAME" \
        -H 'X-Forwarded-Proto: https' "$(gunicorn_url)"
}

web_service_step() {
    require_hostname
    check_gunicorn_port
    log "Installing and restarting $WEB_UNIT.service"
    render_file "$ROOT/deploy/systemd/$WEB_UNIT.service" "$SYSTEMD_DIR/$WEB_UNIT.service"
    run systemctl daemon-reload
    run systemctl enable "$WEB_UNIT.service"
    run systemctl restart "$WEB_UNIT.service"
    if is_dry_run; then
        run curl -sI -H "Host: $CALDART_HOSTNAME" -H 'X-Forwarded-Proto: https' "$(gunicorn_url)"
        return 0
    fi
    if ! wait_for "$WEB_READY_SECONDS" web_answers; then
        journalctl -u "$WEB_UNIT" -n 30 --no-pager >&2 || true
        die "$WEB_UNIT did not answer 200 on $(gunicorn_url) within ${WEB_READY_SECONDS} seconds"
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
