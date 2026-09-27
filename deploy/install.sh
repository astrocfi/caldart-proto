#!/usr/bin/env bash
#
# CalDART - install the site on this server.
#
# Runs every step under deploy/steps/ in order: the operating system packages,
# the service user, Postgres in Docker, the environment file, the build, the
# database, gunicorn under systemd, the web server and its certificate, the
# scheduled jobs, a first backup, and the checks.  Every step is idempotent,
# so running this again repairs or re-applies an install and never destroys
# data or overwrites a secret.  Each step also runs alone, as
# sudo deploy/steps/<step>.sh, reading what it needs from the install record.
#
# The values that describe the box are kept in /etc/caldart/install.conf, so a
# later run needs no flags and a flag given later updates the record.
# --email-url, --from-email, --admin-email, and --seed-content are used by the
# run that writes the environment file or creates the administrator, and are
# not recorded.
#
# Usage:
#   sudo deploy/install.sh [options]
#
# Options:
#   --hostname HOST            the public hostname; required on the first run
#   --www, --no-www            also answer for www.HOST (default --www)
#   --web-server apache|nginx  which web server to install (default apache)
#   --tls certbot|self-signed  how the certificate is obtained (default certbot)
#   --certbot-email ADDRESS    the Let's Encrypt account address; required with certbot
#   --certbot-staging          use Let's Encrypt's staging directory
#   --email-url URL            EMAIL_URL; required while no environment file exists
#   --from-email ADDRESS       DEFAULT_FROM_EMAIL (default CalDART <noreply@HOST>)
#   --admin-email ADDRESS      create the first administrator with this address
#   --seed-content             load the example pages
#   --dry-run                  print every state-changing command instead of running it
#   --help                     show this help
#
# Environment:
#   CALDART_DRY_RUN     1 is the same as --dry-run
#   CALDART_ETC         the configuration directory (default /etc/caldart), for tests
#   CALDART_OS_RELEASE  the os-release file to read (default /etc/os-release), for tests

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=deploy/lib.sh
source "$ROOT/deploy/lib.sh"
# shellcheck source=deploy/steps/packages.sh
source "$ROOT/deploy/steps/packages.sh"
# shellcheck source=deploy/steps/user.sh
source "$ROOT/deploy/steps/user.sh"
# shellcheck source=deploy/steps/postgres.sh
source "$ROOT/deploy/steps/postgres.sh"
# shellcheck source=deploy/steps/configure.sh
source "$ROOT/deploy/steps/configure.sh"
# shellcheck source=deploy/steps/build.sh
source "$ROOT/deploy/steps/build.sh"
# shellcheck source=deploy/steps/database.sh
source "$ROOT/deploy/steps/database.sh"
# shellcheck source=deploy/steps/web-service.sh
source "$ROOT/deploy/steps/web-service.sh"
# shellcheck source=deploy/steps/web-server.sh
source "$ROOT/deploy/steps/web-server.sh"
# shellcheck source=deploy/steps/timers.sh
source "$ROOT/deploy/steps/timers.sh"
# shellcheck source=deploy/steps/backup.sh
source "$ROOT/deploy/steps/backup.sh"
# shellcheck source=deploy/steps/check.sh
source "$ROOT/deploy/steps/check.sh"

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
            --email-url)
                EMAIL_URL="$(option_value "$1" "${2:-}")"
                shift
                ;;
            --from-email)
                FROM_EMAIL="$(option_value "$1" "${2:-}")"
                shift
                ;;
            --admin-email)
                ADMIN_EMAIL="$(option_value "$1" "${2:-}")"
                shift
                ;;
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

# Stop with a usage error naming the flag a first run is missing, or a value
# no step can use.
validate() {
    [[ -n "$CALDART_HOSTNAME" ]] || usage_error "--hostname is required on the first run"
    validate_hostname "$CALDART_HOSTNAME"
    case "$CALDART_WEB_SERVER" in
        apache | nginx) ;;
        *) usage_error "--web-server must be apache or nginx, not $CALDART_WEB_SERVER" ;;
    esac
    case "$CALDART_TLS" in
        certbot)
            [[ -n "$CALDART_CERTBOT_EMAIL" ]] || usage_error "--certbot-email is required with --tls certbot"
            ;;
        self-signed) ;;
        *) usage_error "--tls must be certbot or self-signed, not $CALDART_TLS" ;;
    esac
    if [[ -z "$EMAIL_URL" && ! -f "$ENV_FILE" ]]; then
        usage_error "--email-url is required until $ENV_FILE exists"
    fi
}

main() {
    parse_flags "$@"
    load_record
    apply_record_flags
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
