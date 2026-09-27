#!/usr/bin/env bash
#
# CalDART install step - the web server and the certificate.
#
# For the web server the install record names (Apache or nginx; the other
# one's configuration is never touched), in the only order that works, since
# neither server loads a vhost naming a certificate file that does not exist:
#
#   1. with certbot, and until the certificate exists, a bootstrap port-80 host
#      that serves only /.well-known/acme-challenge/ from /var/www/certbot;
#   2. the certificate: certbot certonly --webroot, or with self-signed TLS an
#      openssl certificate for each name in /etc/caldart/tls/; skipped when it
#      exists;
#   3. certbot's TLS options file (and nginx's DH parameters), written into
#      /etc/letsencrypt/ by preparing certbot's plugin, in both modes;
#   4. the shipped vhost in place of the bootstrap host, with the hostname,
#      the deploy root, and the certificate paths written in.  The vhost is
#      configuration, so this step rewrites it on every run.
#
# With certbot it also installs a renewal hook that reloads the web server.
# It refuses to run while both apache2 and nginx are active.
#
# Usage:
#   sudo deploy/steps/web-server.sh [--dry-run]
#
# Options:
#   --dry-run   print every state-changing command instead of running it
#   --help      show this help

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=deploy/lib.sh
source "$ROOT/deploy/lib.sh"

readonly APACHE_SITES=/etc/apache2/sites-available
readonly APACHE_MODULES=(proxy proxy_http headers ssl rewrite deflate expires http2)
readonly NGINX_SITES=/etc/nginx/sites-available
readonly NGINX_ENABLED=/etc/nginx/sites-enabled
# The first nginx that understands `http2 on;`.
readonly NGINX_HTTP2_DIRECTIVE=1.25.1
readonly RENEWAL_HOOK="$LETSENCRYPT_DIR/renewal-hooks/deploy/reload-web-server"
readonly SELF_SIGNED_DAYS=3650

# Set once this run has written the bootstrap host, so a dry run removes it too.
BOOTSTRAP_WRITTEN=no

# The bootstrap host's file, for the web server in use.
bootstrap_site() {
    if [[ "$CALDART_WEB_SERVER" == apache ]]; then
        printf '%s/caldart-acme.conf\n' "$APACHE_SITES"
    else
        printf '%s/caldart-acme\n' "$NGINX_SITES"
    fi
}

# The bootstrap host: port 80, the challenge directory, nothing else.
bootstrap_config() {
    local names
    names="$(site_names | tr '\n' ' ')"
    names=${names% }
    if [[ "$CALDART_WEB_SERVER" == apache ]]; then
        printf '<VirtualHost *:80>\n'
        printf '    ServerName %s\n' "$CALDART_HOSTNAME"
        [[ "$CALDART_WWW" != yes ]] || printf '    ServerAlias www.%s\n' "$CALDART_HOSTNAME"
        printf '    Alias /.well-known/acme-challenge/ %s/.well-known/acme-challenge/\n' \
            "$CERTBOT_WEBROOT"
        printf '    <Directory "%s/.well-known/acme-challenge">\n' "$CERTBOT_WEBROOT"
        printf '        Require all granted\n'
        printf '    </Directory>\n'
        printf '</VirtualHost>\n'
    else
        printf 'server {\n'
        printf '    listen 80;\n'
        printf '    listen [::]:80;\n'
        printf '    server_name %s;\n' "$names"
        printf '    location /.well-known/acme-challenge/ {\n'
        printf '        root %s;\n' "$CERTBOT_WEBROOT"
        printf '    }\n'
        printf '    location / {\n'
        printf '        return 404;\n'
        printf '    }\n'
        printf '}\n'
    fi
}

# Check the configuration and reload the web server in use.  reload-or-restart
# also starts a stopped server, which a plain reload refuses: a package install
# need not leave it running (a policy-rc.d can forbid that), nor need the
# operator.
reload_web_server() {
    if [[ "$CALDART_WEB_SERVER" == apache ]]; then
        run apachectl configtest
        run systemctl reload-or-restart apache2
    else
        run nginx -t
        run systemctl reload-or-restart nginx
    fi
}

# Enable the site named $1 (caldart or caldart-acme).
enable_site() {
    if [[ "$CALDART_WEB_SERVER" == apache ]]; then
        run a2ensite "$1"
    else
        run ln -sfn "$NGINX_SITES/$1" "$NGINX_ENABLED/$1"
    fi
}

write_bootstrap_host() {
    log "Serving the ACME challenge over plain HTTP"
    run install -d "$CERTBOT_WEBROOT"
    bootstrap_config | write_file "$(bootstrap_site)" 0644
    enable_site caldart-acme
    reload_web_server
    BOOTSTRAP_WRITTEN=yes
}

remove_bootstrap_host() {
    local site
    site="$(bootstrap_site)"
    [[ -e "$site" || "$BOOTSTRAP_WRITTEN" == yes ]] || return 0
    if [[ "$CALDART_WEB_SERVER" == apache ]]; then
        run a2dissite caldart-acme
    else
        run rm -f "$NGINX_ENABLED/caldart-acme"
    fi
    run rm -f "$site"
}

request_certificate() {
    local names=() args=() name
    mapfile -t names < <(site_names)
    for name in "${names[@]}"; do
        args+=(-d "$name")
    done
    log "Requesting the certificate from Let's Encrypt"
    args+=(--non-interactive --agree-tos -m "$CALDART_CERTBOT_EMAIL")
    [[ "$CALDART_CERTBOT_STAGING" != yes ]] || args+=(--staging)
    run certbot certonly --webroot -w "$CERTBOT_WEBROOT" "${args[@]}"
}

make_self_signed_certificate() {
    local names=() alt=() name
    mapfile -t names < <(site_names)
    for name in "${names[@]}"; do
        alt+=("DNS:$name")
    done
    log "Making a self-signed certificate"
    run install -d -m 0750 -o root -g root "$TLS_DIR"
    run openssl req -x509 -newkey rsa:2048 -nodes -days "$SELF_SIGNED_DAYS" \
        -subj "/CN=$CALDART_HOSTNAME" -addext "subjectAltName=$(IFS=,; printf '%s' "${alt[*]}")" \
        -keyout "$TLS_DIR/privkey.pem" -out "$TLS_DIR/fullchain.pem"
    run chmod 0640 "$TLS_DIR/privkey.pem"
    run chown root:root "$TLS_DIR/privkey.pem"
}

# Have certbot's plugin write the TLS options the vhost includes.  Preparing
# the plugin writes files and contacts no one, so it runs in both TLS modes.
prepare_tls_options() {
    local needed=()
    log "Writing certbot's TLS options"
    run certbot plugins --init --prepare --installers
    if [[ "$CALDART_WEB_SERVER" == apache ]]; then
        needed=("$LETSENCRYPT_DIR/options-ssl-apache.conf")
    else
        needed=("$LETSENCRYPT_DIR/options-ssl-nginx.conf" "$LETSENCRYPT_DIR/ssl-dhparams.pem")
    fi
    is_dry_run && return 0
    local file
    for file in "${needed[@]}"; do
        [[ -f "$file" ]] || die "certbot did not write $file"
    done
}

# True when the installed nginx is older than the one that reads `http2 on;`.
nginx_needs_http2_on_listen() {
    local version
    if ! command -v nginx >/dev/null 2>&1; then
        is_dry_run && note "dry run: nginx is not installed, so its version is checked on the real run"
        return 1
    fi
    version="$(nginx -v 2>&1)"
    version=${version#*nginx/}
    version=${version%% *}
    [[ "$version" != "$NGINX_HTTP2_DIRECTIVE" ]] &&
        [[ "$(printf '%s\n%s\n' "$version" "$NGINX_HTTP2_DIRECTIVE" | sort -V | head -1)" == "$version" ]]
}

install_vhost() {
    local dest
    log "Installing the $CALDART_WEB_SERVER vhost for $CALDART_HOSTNAME"
    remove_bootstrap_host
    if [[ "$CALDART_WEB_SERVER" == apache ]]; then
        dest="$APACHE_SITES/caldart.conf"
        run a2enmod "${APACHE_MODULES[@]}"
        render_vhost "$ROOT/deploy/apache/caldart.conf" "$dest" \
            "$CALDART_HOSTNAME" "$CALDART_WWW" "$CALDART_TLS"
    else
        dest="$NGINX_SITES/caldart"
        render_vhost "$ROOT/deploy/nginx/caldart.conf" "$dest" \
            "$CALDART_HOSTNAME" "$CALDART_WWW" "$CALDART_TLS"
        if nginx_needs_http2_on_listen; then
            run sed -i -e '/^ *http2 *on;/d' \
                -e 's/listen\( *\)443 ssl;/listen\1443 ssl http2;/' \
                -e 's/listen\( *\)\[::\]:443 ssl;/listen\1[::]:443 ssl http2;/' \
                "$dest"
        fi
    fi
    enable_site caldart
    reload_web_server
}

install_renewal_hook() {
    log "Reloading the web server after each certificate renewal"
    run install -d "$(dirname "$RENEWAL_HOOK")"
    printf '#!/bin/sh\nsystemctl reload apache2 2>/dev/null || systemctl reload nginx\n' |
        write_file "$RENEWAL_HOOK" 0755
}

web_server_step() {
    require_hostname
    case "$CALDART_WEB_SERVER" in
        apache | nginx) ;;
        *) die "unknown web server $CALDART_WEB_SERVER in $RECORD_FILE" ;;
    esac
    if systemctl is-active --quiet apache2 2>/dev/null && systemctl is-active --quiet nginx 2>/dev/null; then
        die "apache2 and nginx are both running; stop the one CalDART does not use"
    fi

    local certificate
    certificate="$(certificate_path)"
    if [[ "$CALDART_TLS" == certbot ]]; then
        [[ -n "$CALDART_CERTBOT_EMAIL" ]] || die "no certbot email recorded; run install.sh --certbot-email ADDRESS"
        if [[ ! -f "$certificate" ]]; then
            write_bootstrap_host
            request_certificate
        fi
    elif [[ ! -f "$certificate" ]]; then
        make_self_signed_certificate
    fi
    prepare_tls_options
    install_vhost
    if [[ "$CALDART_TLS" == certbot ]]; then
        install_renewal_hook
    fi
}

web_server_main() {
    parse_step_flags "${BASH_SOURCE[0]}" "$@"
    require_root
    load_record
    web_server_step
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    web_server_main "$@"
fi
