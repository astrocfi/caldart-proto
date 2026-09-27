#!/usr/bin/env bash
#
# CalDART - remove the site from this server.
#
# Stops and disables caldart-web and the six timers, removes their unit files,
# removes the vhost and any bootstrap host from the web server the install
# record names and reloads it, and removes the certbot renewal hook.  With
# --purge it also removes /etc/caldart (the environment file and the install
# record), the Postgres container and its caldart_pgdata volume, and the deploy
# root itself.  Each removal prints what it removed; anything already absent is
# skipped.  Certificates under /etc/letsencrypt are left alone either way, and
# so are the packages.
#
# Usage:
#   sudo deploy/uninstall.sh --yes [--purge] [--dry-run]
#
# Options:
#   --yes       confirm; without it nothing runs
#   --purge     also remove the configuration, the database, and the deploy root
#   --dry-run   print every state-changing command instead of running it
#   --help      show this help

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=deploy/lib.sh
source "$ROOT/deploy/lib.sh"

readonly APACHE_SITES=/etc/apache2/sites-available
readonly APACHE_ENABLED=/etc/apache2/sites-enabled
readonly NGINX_SITES=/etc/nginx/sites-available
readonly NGINX_ENABLED=/etc/nginx/sites-enabled
readonly RENEWAL_HOOK="$LETSENCRYPT_DIR/renewal-hooks/deploy/reload-web-server"

CONFIRMED=no
PURGE=no

parse_flags() {
    while (($#)); do
        case "$1" in
            --yes) CONFIRMED=yes ;;
            --purge) PURGE=yes ;;
            --dry-run) enable_dry_run ;;
            --help)
                print_help "${BASH_SOURCE[0]}"
                exit 0
                ;;
            *) usage_error "unknown option $1" ;;
        esac
        shift
    done
    [[ "$CONFIRMED" == yes ]] || usage_error "--yes is required: this removes the site"
}

# Remove the file or directory $1 when it exists, saying so.
remove() {
    [[ -e "$1" || -L "$1" ]] || return 0
    run rm -rf "$1"
    is_dry_run || printf 'removed %s\n' "$1"
}

remove_units() {
    local unit file
    log "Removing the systemd units"
    for unit in "$WEB_UNIT.service" "${JOB_UNITS[@]/%/.timer}"; do
        if [[ -e "$SYSTEMD_DIR/$unit" ]]; then
            run systemctl disable --now "$unit"
        fi
    done
    for unit in "$WEB_UNIT" "${JOB_UNITS[@]}"; do
        for file in "$SYSTEMD_DIR/$unit.service" "$SYSTEMD_DIR/$unit.timer"; do
            remove "$file"
        done
    done
    run systemctl daemon-reload
}

remove_vhost() {
    log "Removing the $CALDART_WEB_SERVER vhost"
    if [[ "$CALDART_WEB_SERVER" == apache ]]; then
        local site
        for site in caldart caldart-acme; do
            if [[ -e "$APACHE_ENABLED/$site.conf" ]]; then
                run a2dissite "$site"
            fi
            remove "$APACHE_SITES/$site.conf"
        done
        if systemctl is-active --quiet apache2 2>/dev/null; then
            run systemctl reload apache2
        fi
    else
        remove "$NGINX_ENABLED/caldart"
        remove "$NGINX_ENABLED/caldart-acme"
        remove "$NGINX_SITES/caldart"
        remove "$NGINX_SITES/caldart-acme"
        if systemctl is-active --quiet nginx 2>/dev/null; then
            run systemctl reload nginx
        fi
    fi
    remove "$RENEWAL_HOOK"
}

purge() {
    log "Removing the configuration, the database, and $ROOT"
    remove "$ETC_DIR"
    run cd "$ROOT"
    # -v removes the caldart_pgdata volume: every row of the database.
    run docker compose down -v
    run cd /
    remove "$ROOT"
}

main() {
    parse_flags "$@"
    require_root
    load_record
    remove_units
    remove_vhost
    if [[ "$PURGE" == yes ]]; then
        purge
    fi
    log "Uninstalled"
}

# Everything above is a function, so removing the deploy root, this file
# included, cannot change what the running copy does.
main "$@"
exit
