#!/usr/bin/env bash
#
# CalDART - upgrade the site on this server to newer code.
#
# Takes a backup, refuses a checkout with local changes, brings the code up to
# date (git pull --ff-only, or with --ref a fetch and a checkout of that
# branch, tag, or commit), then runs the steps that depend on the code, each as
# the freshly checked-out script: the build, the database (migrations, the
# cache table, the roles, and the static files), gunicorn under systemd (which
# reinstalls the unit and restarts it), the scheduled jobs (which reinstalls
# their units), and the checks.  It never touches the environment file or the
# web server's configuration, and it takes no --gunicorn-port or --db-port:
# each step reads the install record, so gunicorn stays on the recorded port and
# every docker compose command runs with the recorded CALDART_DB_PORT exported.
# install.sh --gunicorn-port and --db-port are what move them.
#
# Rolling back is --ref with the previous commit, plus, when the schema moved,
# sudo deploy/manage.sh db_restore with the backup this run took.
#
# Usage:
#   sudo deploy/upgrade.sh [--ref REF] [--dry-run]
#
# Options:
#   --ref REF   the branch, tag, or commit to run (default: pull the current branch)
#   --dry-run   print every state-changing command instead of running it
#   --help      show this help

set -euo pipefail

CHECKOUT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=deploy/lib.sh
source "$CHECKOUT/deploy/lib.sh"

# The steps an upgrade re-runs, in order.
readonly UPGRADE_STEPS=(build database web-service timers check)

REF=""

parse_flags() {
    while (($#)); do
        case "$1" in
            --ref)
                REF="$(option_value "$1" "${2:-}")"
                shift
                ;;
            --gunicorn-port | --db-port)
                usage_error "upgrade.sh keeps the recorded ports; run install.sh $1 PORT to move one"
                ;;
            --dry-run) enable_dry_run ;;
            --help)
                print_help "${BASH_SOURCE[0]}"
                exit 0
                ;;
            *) usage_error "unknown option $1" ;;
        esac
        shift
    done
}

# True when REF names a branch, which a checkout leaves behind its remote.
ref_is_branch() {
    git -C "$CHECKOUT" show-ref --verify --quiet "refs/heads/$REF" ||
        git -C "$CHECKOUT" show-ref --verify --quiet "refs/remotes/origin/$REF"
}

update_code() {
    log "Updating the code"
    [[ -z "$(git -C "$CHECKOUT" status --porcelain)" ]] ||
        die "the checkout at $CHECKOUT has local changes; commit, stash, or discard them first"
    run cd "$CHECKOUT"
    if [[ -z "$REF" ]]; then
        run git pull --ff-only
        return 0
    fi
    run git fetch origin
    run git checkout "$REF"
    if ref_is_branch; then
        run git pull --ff-only
    fi
}

main() {
    parse_flags "$@"
    require_root
    git -C "$CHECKOUT" rev-parse --git-dir >/dev/null 2>&1 || die "$CHECKOUT is not a git checkout"
    # A rollback with --ref leaves HEAD detached, where git pull has no branch
    # to pull; say so before the backup rather than failing inside git.
    if [[ -z "$REF" ]] && ! git -C "$CHECKOUT" symbolic-ref -q HEAD >/dev/null; then
        die "the checkout is on a detached HEAD; run upgrade.sh --ref <branch>"
    fi

    log "Taking a database backup"
    "$CHECKOUT/deploy/manage.sh" db_backup
    update_code

    # Each step runs as a separate process, so it is the updated script.
    local step
    for step in "${UPGRADE_STEPS[@]}"; do
        "$CHECKOUT/deploy/steps/$step.sh"
    done
    log "Upgraded to $(git -C "$CHECKOUT" rev-parse --short HEAD)"
}

# Everything above is a function, so the git update rewriting this file while
# it runs cannot change what the running copy does.
main "$@"
exit
