#!/usr/bin/env bash
#
# CalDART - install the site on this server.
#
# Runs every step under deploy/steps/ in order: the operating system packages,
# the service user, Postgres in Docker, the environment file, the build, the
# database, gunicorn under systemd, the web server and its certificate (or,
# behind an existing site, the snippet that site includes), the scheduled jobs,
# a first backup, and the checks.  Every step is idempotent,
# so running this again repairs or re-applies an install and never destroys
# data or overwrites a secret.  Each step also runs alone, as
# sudo deploy/steps/<step>.sh, reading what it needs from the install record.
#
# The values that describe the box are kept in /etc/caldart/install.conf, so a
# later run doesn't need any flags and a flag given later updates the record.
# --gunicorn-port given to a later run moves gunicorn: the run writes the port
# into the environment file, rewrites the vhost or snippet, restarts gunicorn,
# and reloads the web server, in that order.
# --email-url, --email, --from-email, --bounce-imap-url, --bounce-address,
# --admin-email, --seed-demo, and --seed-content are used by the run that writes
# the environment file or creates the administrator, and are not recorded.
#
# Usage:
#   sudo deploy/install.sh [options]
#
# Options:
#   --hostname HOST            the public hostname; required on the first run
#   --admin-email ADDRESS      create the first administrator with this address
#   --www, --no-www            also answer for www.HOST (default --www)
#   --web-server apache|nginx  which web server to install (default apache)
#   --tls certbot|self-signed|existing
#                              how the certificate is obtained (default certbot); existing
#                              means a web server here already serves HOST over HTTPS, and
#                              CalDART is included in its vhost instead of getting its own
#   --certbot-email ADDRESS    the Let's Encrypt account address (default --admin-email);
#                              certbot needs one or the other
#   --url-prefix PREFIX        serve the site under this path, such as /caldart-proto
#                              (default: the root of HOST, which / also names); must match
#                              URL_PREFIX once the environment file exists.  With certbot
#                              or self-signed, the root of HOST serves /var/www/HOST
#   --attach-to FILE           with --tls existing, the existing site's vhost file to
#                              include CalDART's snippet in (default: print the line to add)
#   --certbot-staging          use Let's Encrypt's staging directory
#   --db-port PORT             the host port Postgres listens on, 1024-65535 (default 5432);
#                              must match DATABASE_URL once the environment file exists
#   --gunicorn-port PORT       the port on 127.0.0.1 where the web server's proxy reaches
#                              gunicorn, 1024-65535 (default 8001); not the site's port,
#                              which is 80 and 443 on the web server
#   --email-url URL            EMAIL_URL; this or --email local is required while no
#                              environment file exists
#   --email local              send mail through the postfix on this machine
#                              (EMAIL_URL=smtp://localhost:25) instead of --email-url
#   --from-email ADDRESS       DEFAULT_FROM_EMAIL (default CalDART <noreply@HOST>)
#   --bounce-imap-url URL      BOUNCE_IMAP_URL, the mailbox the hourly bounce check reads,
#                              as imaps://user:password@host[:port]/MAILBOX with the
#                              credentials URL-encoded (default: bounce checking off)
#   --bounce-address ADDRESS   BOUNCE_ADDRESS, the bounce mailbox's plain address, such
#                              as bounces@caldart.example.org; the site adds a signed
#                              +<id>.<signature> tag to it for each message itself
#                              (default: DEFAULT_FROM_EMAIL)
#   --seed-demo                load the demo accounts (the shared password README.rst
#                              documents; a server seeded with them is a demonstration
#                              server)
#   --seed-content             load the example pages
#   --dry-run                  print every state-changing command instead of running it
#   --help                     show this help
#
# Environment:
#   CALDART_DRY_RUN     1 is the same as --dry-run
#   CALDART_ETC         the configuration directory (default /etc/caldart), for tests
#   CALDART_OS_RELEASE  the os-release file to read (default /etc/os-release), for tests

set -euo pipefail

CHECKOUT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=deploy/lib.sh
source "$CHECKOUT/deploy/lib.sh"
# shellcheck source=deploy/steps/packages.sh
source "$CHECKOUT/deploy/steps/packages.sh"
# shellcheck source=deploy/steps/user.sh
source "$CHECKOUT/deploy/steps/user.sh"
# shellcheck source=deploy/steps/postgres.sh
source "$CHECKOUT/deploy/steps/postgres.sh"
# shellcheck source=deploy/steps/configure.sh
source "$CHECKOUT/deploy/steps/configure.sh"
# shellcheck source=deploy/steps/build.sh
source "$CHECKOUT/deploy/steps/build.sh"
# shellcheck source=deploy/steps/database.sh
source "$CHECKOUT/deploy/steps/database.sh"
# shellcheck source=deploy/steps/web-service.sh
source "$CHECKOUT/deploy/steps/web-service.sh"
# shellcheck source=deploy/steps/web-server.sh
source "$CHECKOUT/deploy/steps/web-server.sh"
# shellcheck source=deploy/steps/timers.sh
source "$CHECKOUT/deploy/steps/timers.sh"
# shellcheck source=deploy/steps/backup.sh
source "$CHECKOUT/deploy/steps/backup.sh"
# shellcheck source=deploy/steps/check.sh
source "$CHECKOUT/deploy/steps/check.sh"

# Flags that update the record, applied over it once it is read.
declare -A RECORD_FLAGS=()

parse_flags() {
    while (($#)); do
        case "$1" in
            --hostname)
                RECORD_FLAGS[CALDART_HOSTNAME]="$(option_value "$1" "${2:-}")"
                shift
                ;;
            --www) RECORD_FLAGS[CALDART_WWW]=yes ;;
            --no-www) RECORD_FLAGS[CALDART_WWW]=no ;;
            --web-server)
                RECORD_FLAGS[CALDART_WEB_SERVER]="$(option_value "$1" "${2:-}")"
                shift
                ;;
            --tls)
                RECORD_FLAGS[CALDART_TLS]="$(option_value "$1" "${2:-}")"
                shift
                ;;
            --certbot-email)
                RECORD_FLAGS[CALDART_CERTBOT_EMAIL]="$(option_value "$1" "${2:-}")"
                shift
                ;;
            --certbot-staging) RECORD_FLAGS[CALDART_CERTBOT_STAGING]=yes ;;
            --db-port)
                RECORD_FLAGS[CALDART_DB_PORT]="$(option_value "$1" "${2:-}")"
                shift
                ;;
            --gunicorn-port)
                RECORD_FLAGS[CALDART_GUNICORN_PORT]="$(option_value "$1" "${2:-}")"
                shift
                ;;
            --url-prefix)
                RECORD_FLAGS[CALDART_URL_PREFIX]="$(option_value "$1" "${2:-}")"
                shift
                ;;
            --attach-to)
                RECORD_FLAGS[CALDART_ATTACH_TO]="$(option_value "$1" "${2:-}")"
                shift
                ;;
            --email-url)
                EMAIL_URL="$(option_value "$1" "${2:-}")"
                shift
                ;;
            --email)
                EMAIL_MODE="$(option_value "$1" "${2:-}")"
                shift
                ;;
            --from-email)
                FROM_EMAIL="$(option_value "$1" "${2:-}")"
                shift
                ;;
            --bounce-imap-url)
                BOUNCE_IMAP_URL="$(option_value "$1" "${2:-}")"
                shift
                ;;
            --bounce-address)
                BOUNCE_ADDRESS="$(option_value "$1" "${2:-}")"
                shift
                ;;
            --admin-email)
                ADMIN_EMAIL="$(option_value "$1" "${2:-}")"
                shift
                ;;
            --seed-demo) SEED_DEMO=yes ;;
            --seed-content) SEED_CONTENT=yes ;;
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

apply_record_flags() {
    local key
    for key in "${!RECORD_FLAGS[@]}"; do
        printf -v "$key" '%s' "${RECORD_FLAGS[$key]}"
    done
}

# Stop with one usage error that names every option a first run is missing, then
# check each value.
validate() {
    validate_email_flags
    require_first_install_options
    validate_hostname "$CALDART_HOSTNAME"
    case "$CALDART_WEB_SERVER" in
        apache | nginx) ;;
        *) usage_error "--web-server must be apache or nginx, not $CALDART_WEB_SERVER" ;;
    esac
    case "$CALDART_TLS" in
        certbot | self-signed | existing) ;;
        *) usage_error "--tls must be certbot, self-signed, or existing, not $CALDART_TLS" ;;
    esac
    if [[ -n "$CALDART_ATTACH_TO" ]]; then
        [[ "$CALDART_TLS" == existing ]] || usage_error "--attach-to is used only with --tls existing"
        [[ "$CALDART_ATTACH_TO" == /* && "$CALDART_ATTACH_TO" != *$'\n'* ]] ||
            usage_error "--attach-to must be an absolute path, not $CALDART_ATTACH_TO"
    fi
    validate_db_port "$CALDART_DB_PORT"
    validate_db_port_matches_env_file
    validate_gunicorn_port "$CALDART_GUNICORN_PORT"
    validate_url_prefix
    validate_url_prefix_matches_env_file
}

# The Let's Encrypt account address falls back to the administrator's, so a first
# install with certbot needs only --admin-email to have both.
default_certbot_email() {
    if [[ "$CALDART_TLS" == certbot && -z "$CALDART_CERTBOT_EMAIL" ]]; then
        CALDART_CERTBOT_EMAIL="$ADMIN_EMAIL"
    fi
}

# Stop with a usage error that lists, in one message, each option a first install
# needs and doesn't have: the hostname, an address for Let's Encrypt with certbot,
# and the mail relay until the environment file exists.
require_first_install_options() {
    local missing=()
    [[ -n "$CALDART_HOSTNAME" ]] ||
        missing+=("  --hostname HOST          the site's public name, such as caldart.example.org")
    if [[ "$CALDART_TLS" == certbot && -z "$CALDART_CERTBOT_EMAIL" ]]; then
        missing+=("  --admin-email ADDRESS    your address: the first administrator, and where"
            "                           Let's Encrypt sends certificate warnings")
    fi
    if [[ -z "$EMAIL_URL" && ! -f "$ENV_FILE" ]]; then
        missing+=("  --email-url URL          how the site sends mail: your SMTP relay,"
            "    or --email local       or the postfix on this machine")
    fi
    ((${#missing[@]} == 0)) && return 0
    usage_error "$(printf 'this install needs these options:\n'; printf '%s\n' "${missing[@]}")"
}

main() {
    parse_flags "$@"
    load_record
    apply_record_flags
    default_certbot_email
    validate
    require_root

    packages_step
    user_step
    log "Recording this install in $RECORD_FILE"
    write_record
    postgres_step
    if ! have_env_file; then
        postgres_set_password
    fi
    configure_step
    build_step
    database_step
    web_service_step
    web_server_step
    timers_step
    backup_step
    check_step
    log "Installed"
}

# Everything above is a function, so an upgrade that rewrites this file while
# it runs cannot change what the running copy does.
main "$@"
exit
