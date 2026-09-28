#!/usr/bin/env bash
#
# CalDART - run a management command on the server.
#
# Runs backend/manage.py the way caldart-web.service runs gunicorn: as the
# caldart user, from backend/, with /etc/caldart/caldart.env loaded by systemd,
# DJANGO_SETTINGS_MODULE=caldart.settings.prod, and UMask=0027, as a transient
# systemd unit that is collected when it exits.  The command's exit status is
# this script's.  A terminal is passed through when one is attached, so
# interactive commands such as the db_restore prompt work; redirected output
# gets plain pipes.
#
# Usage:
#   sudo deploy/manage.sh [--dry-run] COMMAND [ARGUMENTS...]
#
# Options (before COMMAND; everything from COMMAND on goes to manage.py):
#   --dry-run   print the systemd-run command instead of running it
#   --help      show this help
#
# Examples:
#   sudo deploy/manage.sh migrate
#   sudo deploy/manage.sh db_backup
#   sudo deploy/manage.sh health --json

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
    (($#)) || usage_error "name the management command to run"
    require_root
    # The environment file, not the environment of the calling shell: systemd
    # keeps interior whitespace in an unquoted value such as DEFAULT_FROM_EMAIL,
    # where a shell would split it.  UMask=0027 keeps a database dump from
    # landing world-readable under systemd's default 0022.
    run systemd-run --quiet --wait --collect --pty --pipe \
        --uid="$SERVICE_USER" --gid="$SERVICE_USER" \
        --working-directory="$CHECKOUT/backend" \
        --property=EnvironmentFile="$DEFAULT_ETC/caldart.env" \
        --property=UMask=0027 \
        --setenv=DJANGO_SETTINGS_MODULE=caldart.settings.prod \
        "$CHECKOUT/.venv/bin/python" manage.py "$@"
}

main "$@"
