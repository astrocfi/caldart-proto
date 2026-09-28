#!/usr/bin/env bash
#
# CalDART - remove the site from this server.
#
# Stops and disables caldart-web and the six timers, removes their unit files,
# removes the vhost and any bootstrap host from the web server the install
# record names, and, behind an existing site, the snippet and the line that
# includes it (from the attached vhost file, or from every file under the web
# server's sites-available that carries it), leaving the rest of that file as
# it is; then reloads the server and removes the certbot renewal hook.  With
# --purge it also removes /etc/caldart (the environment file and the install
# record), the Postgres container and its caldart_pgdata volume, and what the
# install made in the deploy root: the checkout, the database dumps in
# backups/, and the uploads in media/, then the deploy root itself when nothing
# else is in it.  Without --purge all three stay.  On an install that keeps its
# dumps and uploads inside the checkout, the purge removes the checkout alone.
# Each removal prints what it removed; anything already absent is skipped.
# Certificates under /etc/letsencrypt are left alone either way, and so are the
# packages.
#
# Usage:
#   sudo deploy/uninstall.sh --yes [--purge] [--dry-run]
#
# Options:
#   --yes       confirm; without it nothing runs
#   --purge     also remove the configuration, the database, and the checkout,
#               the backups, and the uploads in the deploy root
#   --dry-run   print every state-changing command instead of running it
#   --help      show this help

set -euo pipefail

CHECKOUT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Read by lib.sh: this script is safe on an install that keeps its data inside
# the checkout.
# shellcheck disable=SC2034
CALDART_ANY_LAYOUT=1
# shellcheck source=deploy/lib.sh
source "$CHECKOUT/deploy/lib.sh"

readonly APACHE_SITES=/etc/apache2/sites-available
readonly APACHE_ENABLED=/etc/apache2/sites-enabled
readonly NGINX_SITES=/etc/nginx/sites-available
readonly NGINX_ENABLED=/etc/nginx/sites-enabled
readonly RENEWAL_HOOK="$LETSENCRYPT_DIR/renewal-hooks/deploy/reload-web-server"
# What the existing TLS mode writes, and the include line, as a sed address.
readonly APACHE_SNIPPET=/etc/apache2/conf-available/caldart.conf
readonly APACHE_INCLUDE_ADDRESS='\#^[[:space:]]*Include conf-available/caldart\.conf[[:space:]]*$#'
readonly NGINX_SNIPPET=/etc/nginx/snippets/caldart.conf
readonly NGINX_UPSTREAM=/etc/nginx/conf.d/caldart-upstream.conf
readonly NGINX_INCLUDE_ADDRESS='\#^[[:space:]]*include snippets/caldart\.conf;[[:space:]]*$#'

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

# The files that include the snippet: the attached vhost when the record names
# one, or every file in sites-available that carries the line.
files_including_snippet() {
    local address=$1 sites=$2 pattern
    # The sed address without its delimiters is the grep pattern.
    pattern=${address#\\#}
    pattern=${pattern%#}
    if [[ -n "$CALDART_ATTACH_TO" ]]; then
        [[ -f "$CALDART_ATTACH_TO" ]] && grep -qE "$pattern" "$CALDART_ATTACH_TO" &&
            printf '%s\n' "$CALDART_ATTACH_TO"
        return 0
    fi
    [[ -d "$sites" ]] || return 0
    grep -rlE "$pattern" "$sites" || true
}

# Take the include line out of every file that carries it, then the snippet.
remove_snippet() {
    local address sites files=() file
    if [[ "$CALDART_WEB_SERVER" == apache ]]; then
        address=$APACHE_INCLUDE_ADDRESS sites=$APACHE_SITES
    else
        address=$NGINX_INCLUDE_ADDRESS sites=$NGINX_SITES
    fi
    mapfile -t files < <(files_including_snippet "$address" "$sites")
    for file in "${files[@]}"; do
        run sed -i --follow-symlinks -e "${address}d" "$file"
        is_dry_run || printf 'removed the include line from %s\n' "$file"
    done
    remove "$APACHE_SNIPPET"
    remove "$NGINX_SNIPPET"
    remove "$NGINX_UPSTREAM"
}

remove_vhost() {
    log "Removing the $CALDART_WEB_SERVER vhost"
    remove_snippet
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

# Print the first entry of the deploy root that the install did not make: not
# the checkout, backups/, or media/.  Nothing when there is none.
foreign_entry() {
    find "$ROOT" -mindepth 1 -maxdepth 1 ! -name "$(basename "$CHECKOUT")" \
        ! -name backups ! -name media -print -quit
}

# Remove what the install made in the deploy root, and the root once it is
# empty.  On an install that keeps its data inside the checkout, the checkout
# is all of it: the directory above belongs to the machine.
remove_deploy_root() {
    local layout=$1 foreign
    if [[ "$layout" == checkout ]]; then
        remove "$CHECKOUT"
        return 0
    fi
    foreign="$(foreign_entry)"
    remove "$CHECKOUT"
    remove "$ROOT/backups"
    remove "$ROOT/media"
    if [[ -n "$foreign" ]]; then
        note "kept $ROOT: it holds more than the checkout, the backups, and the uploads"
        return 0
    fi
    run rmdir "$ROOT"
    is_dry_run || printf 'removed %s\n' "$ROOT"
}

purge() {
    # Decided before the configuration goes, since the record says which it is.
    local layout=root
    if is_checkout_layout; then
        layout=checkout
        log "Removing the configuration, the database, and $CHECKOUT (the checkout, with the backups and the uploads inside it)"
    else
        log "Removing the configuration, the database, and $ROOT (the checkout, the backups, and the uploads)"
    fi
    remove "$ETC_DIR"
    run cd "$CHECKOUT"
    # -v removes the caldart_pgdata volume: every row of the database.
    run docker compose down -v
    run cd /
    remove_deploy_root "$layout"
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

# Everything above is a function, so removing the checkout, this file
# included, cannot change what the running copy does.
main "$@"
exit
