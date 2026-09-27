#!/usr/bin/env bash
#
# CalDART install step 11 - the checks, and the summary.
#
# Checks that caldart-web and the six timers are active, that the compose db
# service is healthy, that the site answers 200 over HTTPS on this machine for
# / and /portal/login, and that manage.py health reports DEBUG off and no
# pending migration.  Every miss is an error naming the check, and any miss
# fails the step.  Then prints the summary: the site's address, the
# environment file, the administrator's one-time link when one was created,
# the Stripe, PayPal, and Geoapify settings the environment file still leaves
# empty, and, with a self-signed certificate, that browsers warn until a real
# certificate replaces it.  A dry run prints the checks instead of running them.
#
# Usage:
#   sudo deploy/steps/check.sh [--dry-run]
#
# Options:
#   --dry-run   print the checks instead of running them
#   --help      show this help

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=deploy/lib.sh
source "$ROOT/deploy/lib.sh"

readonly SITE_PATHS=(/ /portal/login)
# The settings a site takes payments and suggests addresses with, left for the
# operator to fill in.
readonly OPTIONAL_KEYS_PATTERN='^(STRIPE_[A-Z_]*|PAYPAL_[A-Z_]*|GEOAPIFY_API_KEY)=$'
readonly HEALTH_CHECK='
import json, sys
report = json.load(sys.stdin)
problems = []
if report.get("debug") is not False:
    problems.append("DEBUG is on")
if report.get("pending_migrations") != 0:
    problems.append("migrations are pending")
print("; ".join(problems))
'

# The link database.sh kept when it created the administrator.
ADMIN_LINK="${ADMIN_LINK:-}"
FAILURES=0

fail_check() {
    printf 'error: check failed: %s\n' "$*" >&2
    FAILURES=$((FAILURES + 1))
}

site_status() {
    curl -sk -o /dev/null -w '%{http_code}' --resolve "$CALDART_HOSTNAME:443:127.0.0.1" \
        "https://$CALDART_HOSTNAME$1"
}

print_dry_run_checks() {
    local unit path
    for unit in "$WEB_UNIT.service" "${JOB_UNITS[@]/%/.timer}"; do
        run systemctl is-active --quiet "$unit"
    done
    run docker compose ps --format '{{.Health}}' db
    for path in "${SITE_PATHS[@]}"; do
        run curl -sk --resolve "$CALDART_HOSTNAME:443:127.0.0.1" "https://$CALDART_HOSTNAME$path"
    done
    "$ROOT/deploy/manage.sh" health --json
}

run_checks() {
    local unit path status health problems
    for unit in "$WEB_UNIT.service" "${JOB_UNITS[@]/%/.timer}"; do
        systemctl is-active --quiet "$unit" || fail_check "$unit is not active"
    done
    status="$(cd "$ROOT" && docker compose ps --format '{{.Health}}' db 2>/dev/null || true)"
    [[ "$status" == healthy ]] || fail_check "the compose db service is not healthy (${status:-not running})"
    for path in "${SITE_PATHS[@]}"; do
        status="$(site_status "$path" || true)"
        [[ "$status" == 200 ]] || fail_check "https://$CALDART_HOSTNAME$path answered ${status:-nothing}, not 200"
    done
    if health="$("$ROOT/deploy/manage.sh" health --json)"; then
        problems="$(printf '%s' "$health" | python3 -c "$HEALTH_CHECK" 2>&1 || printf 'unreadable report')"
        [[ -z "$problems" ]] || fail_check "manage.py health: $problems"
    else
        fail_check "manage.py health did not run"
    fi
}

print_summary() {
    local empty=()
    if [[ -r "$ENV_FILE" ]]; then
        mapfile -t empty < <(grep -E "$OPTIONAL_KEYS_PATTERN" "$ENV_FILE" | cut -d= -f1)
    fi
    printf '\nCalDART is running at https://%s/\n' "$CALDART_HOSTNAME"
    printf 'Settings: %s (edit with sudoedit, then systemctl restart caldart-web)\n' "$ENV_FILE"
    if [[ -n "$ADMIN_LINK" ]]; then
        printf "Set the administrator's password at: %s\n" "$ADMIN_LINK"
    fi
    if ((${#empty[@]})); then
        printf 'Still empty in the settings: %s\n' "${empty[*]}"
    fi
    if [[ "$CALDART_TLS" == self-signed ]]; then
        printf 'The certificate is self-signed: browsers warn until a real one replaces it.\n'
    fi
}

check_step() {
    require_hostname
    log "Checking the installation"
    if is_dry_run; then
        print_dry_run_checks
    else
        run_checks
        ((FAILURES == 0)) || die "$FAILURES check(s) failed"
    fi
    print_summary
}

check_main() {
    parse_step_flags "${BASH_SOURCE[0]}" "$@"
    require_root
    load_record
    check_step
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    check_main "$@"
fi
