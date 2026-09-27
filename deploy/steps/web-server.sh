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
#
# With the existing TLS mode a web server here already serves the hostname over
# HTTPS, and this step obtains no certificate and installs no vhost.  It writes
# a snippet instead, for the URL prefix in the install record:
# deploy/apache/caldart-attach.conf to /etc/apache2/conf-available/caldart.conf,
# or deploy/nginx/caldart-attach.conf to /etc/nginx/snippets/caldart.conf with
# the upstream it proxies to in /etc/nginx/conf.d/caldart-upstream.conf.  With
# an attached vhost file in the record (install.sh --attach-to), it inserts the
# one line that includes the snippet before the end of every HTTPS block in
# that file (every block, when none serves HTTPS), keeping a copy of the file
# from before the first insertion at FILE.caldart.bak; a file that carries the
# line already is left alone.  Without one it prints the line and where it
# goes.  Either way it then checks the configuration and reloads the server;
# when the check fails it takes out the line this run inserted, so the existing
# site's vhost is as it was, and stops.
#
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
# Where the existing TLS mode puts the snippet, and the line that includes it.
readonly APACHE_SNIPPET=/etc/apache2/conf-available/caldart.conf
readonly APACHE_INCLUDE='Include conf-available/caldart.conf'
# The modules the Apache snippet needs; an existing HTTPS site has ssl already.
readonly APACHE_SNIPPET_MODULES=(proxy proxy_http headers expires)
readonly NGINX_SNIPPET=/etc/nginx/snippets/caldart.conf
readonly NGINX_UPSTREAM=/etc/nginx/conf.d/caldart-upstream.conf
readonly NGINX_INCLUDE='include snippets/caldart.conf;'
# The suffix of the copy of an attached vhost from before the first insertion.
readonly ATTACH_BACKUP_SUFFIX=.caldart.bak

# Set once this run has written the bootstrap host, so a dry run removes it too.
BOOTSTRAP_WRITTEN=no
# Set once this run has inserted the include line, so a failed check takes it out.
INCLUDE_INSERTED=no

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
    check_web_server_config
    restart_web_server
}

# Check the configuration of the web server in use.
check_web_server_config() {
    if [[ "$CALDART_WEB_SERVER" == apache ]]; then
        run apachectl configtest
    else
        run nginx -t
    fi
}

restart_web_server() {
    if [[ "$CALDART_WEB_SERVER" == apache ]]; then
        run systemctl reload-or-restart apache2
    else
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

# The line that includes the snippet, for the web server in use.
include_line() {
    if [[ "$CALDART_WEB_SERVER" == apache ]]; then
        printf '%s\n' "$APACHE_INCLUDE"
    else
        printf '%s\n' "$NGINX_INCLUDE"
    fi
}

# The numbers of the lines of vhost file $1 that close a block to include the
# snippet in: every Apache <VirtualHost> or nginx server block that terminates
# TLS, or every such block when none does.  A block terminates TLS when it
# names a certificate, turns TLS on, or listens on port 443: certbot's Apache
# vhost gets its SSLEngine from an included options file, so SSLEngine alone
# would miss it and put the line in the plain-HTTP block too.  Nginx blocks are
# found by counting braces outside comments, so a block must not open and
# close on one line.
closing_lines() {
    # The $ signs below are awk's, not the shell's.
    # shellcheck disable=SC2016
    awk -v server="$CALDART_WEB_SERVER" '
        function finish(line) {
            closing[++count] = line
            tls[count] = has_tls
            if (has_tls) any_tls = 1
            inside = 0
        }
        {
            text = $0
            sub(/#.*/, "", text)
        }
        server == "apache" {
            text = tolower(text)
            if (text ~ /^[ \t]*<virtualhost[ \t>]/) {
                inside = 1; has_tls = (text ~ /:443([ \t>]|$)/)
            }
            else if (inside && text ~ /^[ \t]*(sslengine[ \t]+on|sslcertificatefile[ \t])/) has_tls = 1
            else if (inside && text ~ /^[ \t]*<\/virtualhost>/) finish(NR)
            next
        }
        {
            if (!inside && text ~ /^[ \t]*server[ \t]*\{/) {
                inside = 1; has_tls = 0; outer = depth
            }
            if (inside && text ~ /(^|[ \t;])listen[ \t][^;]*[ \t]ssl([ \t;]|$)/) has_tls = 1
            if (inside && text ~ /(^|[ \t;])listen[ \t]+([^;]*[ \t:])?443([ \t;]|$)/) has_tls = 1
            if (inside && text ~ /(^|[ \t;])ssl_certificate[ \t]/) has_tls = 1
            depth += gsub(/\{/, "{", text) - gsub(/\}/, "}", text)
            if (inside && depth == outer) finish(NR)
        }
        END {
            for (i = 1; i <= count; i++) {
                if (tls[i] || !any_tls) print closing[i]
            }
        }
    ' "$1"
}

# Insert the include line into the vhost file $1, before the end of each block
# closing_lines names, indented one level deeper than the line that closes it.
# Keeps FILE.caldart.bak from before the first insertion, and leaves a file
# that carries the line already alone.
attach_include() {
    local file=$1 include block
    include="$(include_line)"
    if [[ "$CALDART_WEB_SERVER" == apache ]]; then block='<VirtualHost>'; else block=server; fi
    if [[ ! -f "$file" ]]; then
        if is_dry_run; then
            note "dry run: $file does not exist here; the real run inserts '$include' before the end of each HTTPS block in it"
            run cp -p "$file" "$file$ATTACH_BACKUP_SUFFIX"
            return 0
        fi
        die "$file does not exist; --attach-to names the vhost file of the existing site"
    fi
    if grep -qE "^[[:space:]]*${include//./\\.}[[:space:]]*\$" "$file"; then
        printf '    %s already includes the snippet\n' "$file"
        return 0
    fi
    local lines=() line indent expressions=()
    mapfile -t lines < <(closing_lines "$file")
    ((${#lines[@]})) || die "$file holds no $block block to include the snippet in"
    for line in "${lines[@]}"; do
        indent="$(sed -n "${line}{s/[^[:space:]].*//;p}" "$file")"
        expressions+=(-e "${line}i\\${indent}    ${include}")
    done
    if [[ ! -e "$file$ATTACH_BACKUP_SUFFIX" ]]; then
        run cp -p "$file" "$file$ATTACH_BACKUP_SUFFIX"
    fi
    run sed -i --follow-symlinks "${expressions[@]}" "$file"
    INCLUDE_INSERTED=yes
}

# Check the configuration with the snippet in place.  When the check fails and
# this run inserted the include line into the vhost file $1, take the line out
# again (the file carried none before this run, or nothing would have been
# inserted), so the existing site keeps a configuration that passes its check,
# then stop.
check_or_detach() {
    local file=$1 include
    check_web_server_config && return 0
    [[ "$INCLUDE_INSERTED" == yes ]] ||
        die "web-server step: the configuration check failed with the snippet in place"
    include="$(include_line)"
    run sed -i --follow-symlinks "\#^[[:space:]]*${include//./\\.}[[:space:]]*\$#d" "$file"
    die "web-server step: the configuration check failed with the snippet included; $file is back as it was before this run"
}

# Print the include line and where it goes, for an operator adding it by hand.
print_include_instructions() {
    local where
    if [[ "$CALDART_WEB_SERVER" == apache ]]; then
        where="inside the <VirtualHost *:443> block that serves $CALDART_HOSTNAME, before its </VirtualHost>"
    else
        where="inside the server block that serves $CALDART_HOSTNAME over HTTPS, before its closing }"
    fi
    printf '    No --attach-to was given.  Add this line %s:\n' "$where"
    printf '\n    %s\n\n' "$(include_line)"
    printf '    then reload the web server.  The checks fail until the line is there.\n'
}

# Take out a vhost and a bootstrap host an earlier certbot or self-signed install
# wrote: the existing site answers for the hostname now.
remove_own_vhost() {
    local site
    for site in caldart caldart-acme; do
        if [[ "$CALDART_WEB_SERVER" == apache ]]; then
            [[ -e "$APACHE_SITES/$site.conf" ]] || continue
            run a2dissite "$site"
            run rm -f "$APACHE_SITES/$site.conf"
        else
            [[ -e "$NGINX_SITES/$site" ]] || continue
            run rm -f "$NGINX_ENABLED/$site" "$NGINX_SITES/$site"
        fi
    done
}

# The existing TLS mode: the snippet, the include line, and a reload.
install_snippet() {
    log "Installing the $CALDART_WEB_SERVER snippet for $(site_url)/"
    remove_own_vhost
    if [[ "$CALDART_WEB_SERVER" == apache ]]; then
        run a2enmod "${APACHE_SNIPPET_MODULES[@]}"
        render_snippet "$ROOT/deploy/apache/caldart-attach.conf" "$APACHE_SNIPPET"
    else
        run install -d "$(dirname "$NGINX_SNIPPET")" "$(dirname "$NGINX_UPSTREAM")"
        render_snippet "$ROOT/deploy/nginx/caldart-upstream.conf" "$NGINX_UPSTREAM"
        render_snippet "$ROOT/deploy/nginx/caldart-attach.conf" "$NGINX_SNIPPET"
    fi
    if [[ -n "$CALDART_ATTACH_TO" ]]; then
        log "Including the snippet in $CALDART_ATTACH_TO"
        attach_include "$CALDART_ATTACH_TO"
    else
        print_include_instructions
    fi
    check_or_detach "$CALDART_ATTACH_TO"
    restart_web_server
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

    if [[ "$CALDART_TLS" == existing ]]; then
        install_snippet
        return 0
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
