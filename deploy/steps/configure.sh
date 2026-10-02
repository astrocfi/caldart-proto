#!/usr/bin/env bash
#
# CalDART install step - the environment file.
#
# Writes /etc/caldart/caldart.env once, root:caldart, mode 0640, from the
# production template deploy/caldart.env.example.  The five variables the
# template leaves commented out are uncommented and set: SECRET_KEY generated,
# ALLOWED_HOSTS from the hostname (and its www. form), SITE_URL (https://HOST and
# the URL prefix), EMAIL_URL from
# --email-url (or smtp://localhost:25 with --email local), and DATABASE_URL with
# the password the Postgres step set and the recorded database port.  It
# also sets CSRF_TRUSTED_ORIGINS for the same hosts, DEFAULT_FROM_EMAIL,
# BACKUP_DIR and MEDIA_ROOT in the deploy root (its backups and media
# directories, beside the checkout), USER_GUIDE_ROOT in the checkout,
# DB_BACKUP_VIA_DOCKER=false,
# BACKUP_RETENTION_DAYS=30, CALDART_GUNICORN_PORT from the install record (8001
# unless install.sh --gunicorn-port says otherwise), URL_PREFIX when the site
# has one, BOUNCE_IMAP_URL and BOUNCE_ADDRESS from --bounce-imap-url and
# --bounce-address when given, and, with self-signed TLS, SECURE_HSTS_SECONDS=0.  It prints the
# CALDART_GUNICORN_PORT line, the one line of the file a dry run shows.  Behind an existing site the HSTS
# default is left alone: that site owns HSTS for the host.
# Everything else, comments included, stays as the template has it.  With
# --email local, a note (not an error) says so when nothing listens on port 25:
# mail fails until postfix is installed and listening on localhost.
#
# When the file exists this step leaves it alone but for one line: it sets
# CALDART_GUNICORN_PORT to the recorded port, replacing the line or adding it,
# and rewrites nothing when the line already names that port.  For anything
# else, edit the file with sudoedit, then run systemctl restart caldart-web.  Run alone rather than from install.sh, the
# step has no database password handed to it and writes a generated one the
# database does not have.
#
# Usage:
#   sudo deploy/steps/configure.sh [options]
#
# Options:
#   --hostname HOST        the public hostname (default: the install record's)
#   --www, --no-www        also answer for www.HOST (default: the record's, or --www)
#   --tls MODE             certbot, self-signed, or existing (default: the record's, or
#                          certbot)
#   --url-prefix PREFIX    the path the site is served under (default: the record's, or
#                          none)
#   --email-url URL        EMAIL_URL; this or --email local is required when the
#                          file does not exist
#   --email local          send mail through the postfix on this machine
#   --from-email ADDRESS   DEFAULT_FROM_EMAIL (default: CalDART <noreply@HOST>)
#   --bounce-imap-url URL  BOUNCE_IMAP_URL, the mailbox the bounce check reads
#                          (imaps://user:password@host[:port]/MAILBOX); default: off
#   --bounce-address ADDRESS
#                          BOUNCE_ADDRESS, the envelope sender bounces return to
#                          (default: DEFAULT_FROM_EMAIL)
#   --dry-run              print every state-changing command instead of running it
#   --help                 show this help
#
# Environment:
#   CALDART_ETC   the directory to write caldart.env into (default /etc/caldart);
#                 any other directory skips the root check and the ownership

set -euo pipefail

CHECKOUT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=deploy/lib.sh
source "$CHECKOUT/deploy/lib.sh"

readonly TEMPLATE="$CHECKOUT/deploy/caldart.env.example"
readonly SECRET_KEY_BYTES=64
readonly SMTP_PORT=25

EMAIL_URL="${EMAIL_URL:-}"
# local when --email local was given, which stands for LOCAL_EMAIL_URL.
EMAIL_MODE="${EMAIL_MODE:-}"
FROM_EMAIL="${FROM_EMAIL:-}"
BOUNCE_IMAP_URL="${BOUNCE_IMAP_URL:-}"
BOUNCE_ADDRESS="${BOUNCE_ADDRESS:-}"
DB_PASSWORD="${DB_PASSWORD:-}"

# Join the remaining arguments with the separator $1.
join_by() {
    local separator=$1 first=$2
    shift 2
    printf '%s' "$first" "${@/#/$separator}"
}

# Print the template with each KEY=value from the arguments written over the
# line that sets or comments out KEY.  awk reads the values from its
# environment, so no character in them needs escaping, and they are exported
# by the shell's own export in a subshell rather than handed to env, so the
# secret key and the database password never appear in a program's arguments.
fill_template() (
    local pair names=()
    for pair in "$@"; do
        names+=("${pair%%=*}")
        export "FILL_${pair%%=*}=${pair#*=}"
    done
    export FILL_NAMES="${names[*]}"
    # The $ signs below are awk's, not the shell's.
    # shellcheck disable=SC2016
    exec awk '
        BEGIN { count = split(ENVIRON["FILL_NAMES"], names, " ") }
        {
            for (i = 1; i <= count; i++) {
                if (!(names[i] in done) && $0 ~ ("^#?" names[i] "=")) {
                    print names[i] "=" ENVIRON["FILL_" names[i]]
                    done[names[i]] = 1
                    next
                }
            }
            print
        }
        END {
            for (i = 1; i <= count; i++) {
                if (!(names[i] in done)) {
                    print "error: the template has no line for " names[i] > "/dev/stderr"
                    exit 1
                }
            }
        }
    ' "$TEMPLATE"
)

# Stop with a usage error on an --email other than local, or on --email local
# together with --email-url; otherwise let --email local set EMAIL_URL.
validate_email_flags() {
    [[ -n "$EMAIL_MODE" ]] || return 0
    [[ "$EMAIL_MODE" == local ]] || usage_error "--email takes only local, not $EMAIL_MODE"
    [[ -z "$EMAIL_URL" ]] || usage_error "give --email local or --email-url, not both"
    EMAIL_URL="$LOCAL_EMAIL_URL"
}

# Say so when --email local finds nothing to relay through.  The installer
# installs no mail server: the machine's own postfix is the operator's.
note_local_mail() {
    [[ "$EMAIL_MODE" == local ]] || return 0
    port_in_use "$SMTP_PORT" && return 0
    note "Nothing listens on port $SMTP_PORT on this machine: mail fails until postfix is" \
        "installed and listening on localhost."
}

# The owner and group the environment file is written with: root and the
# service's group in /etc/caldart, and whoever runs the step anywhere else.
env_file_owner() {
    if [[ "$ETC_DIR" == "$DEFAULT_ETC" ]]; then
        printf '%s\n' root "$SERVICE_USER"
    fi
}

# Print the environment file with every CALDART_GUNICORN_PORT line set to the
# recorded port, or the line added at the end when the file has none.  awk
# reads the port from its environment, as fill_template does.
env_file_with_gunicorn_port() {
    # The $ signs below are awk's, not the shell's.
    # shellcheck disable=SC2016
    FILL_PORT="$CALDART_GUNICORN_PORT" awk '
        /^CALDART_GUNICORN_PORT=/ { print "CALDART_GUNICORN_PORT=" ENVIRON["FILL_PORT"]; found = 1; next }
        { print }
        END { if (!found) print "CALDART_GUNICORN_PORT=" ENVIRON["FILL_PORT"] }
    ' "$ENV_FILE"
}

# Bring CALDART_GUNICORN_PORT in the existing environment file to the recorded
# port, so a port install.sh --gunicorn-port moved reaches gunicorn on its next
# start.  A file that names the port already is not written.
sync_gunicorn_port() {
    local line="CALDART_GUNICORN_PORT=$CALDART_GUNICORN_PORT"
    if [[ ! -r "$ENV_FILE" ]] && is_dry_run; then
        log "Leaving $ENV_FILE alone but for $line"
        note "dry run: $ENV_FILE is not readable here; the real run writes $line into it when it names another port"
        return 0
    fi
    if grep -qxF "$line" "$ENV_FILE"; then
        log "Leaving $ENV_FILE alone: it exists"
        return 0
    fi
    log "Setting $line in $ENV_FILE, leaving the rest of it alone"
    local owner=() content
    mapfile -t owner < <(env_file_owner)
    content="$(env_file_with_gunicorn_port)"
    printf '%s\n' "$content" | write_file "$ENV_FILE" 0640 "${owner[@]}"
}

configure_step() {
    if have_env_file; then
        sync_gunicorn_port
        if [[ "$EMAIL_MODE" == local ]]; then
            printf '    --email local is ignored: edit the file with sudoedit\n'
        elif [[ -n "$EMAIL_URL" ]]; then
            printf '    --email-url is ignored: edit the file with sudoedit\n'
        fi
        [[ -z "$FROM_EMAIL" ]] || printf '    --from-email is ignored: edit the file with sudoedit\n'
        [[ -z "$BOUNCE_IMAP_URL" ]] || printf '    --bounce-imap-url is ignored: edit the file with sudoedit\n'
        [[ -z "$BOUNCE_ADDRESS" ]] || printf '    --bounce-address is ignored: edit the file with sudoedit\n'
        return 0
    fi
    [[ -n "$CALDART_HOSTNAME" ]] || usage_error "--hostname is required to write $ENV_FILE"
    [[ -n "$EMAIL_URL" ]] || usage_error "--email-url or --email local is required to write $ENV_FILE"

    log "Writing $ENV_FILE"
    printf '    with CALDART_GUNICORN_PORT=%s\n' "$CALDART_GUNICORN_PORT"
    note_local_mail
    local names=() origins=() name
    mapfile -t names < <(site_names)
    for name in "${names[@]}"; do
        origins+=("https://$name")
    done
    if [[ -z "$DB_PASSWORD" ]]; then
        note "No database password was handed over by the Postgres step, so DATABASE_URL"
        note "carries a generated one the database does not have; install.sh runs both."
        DB_PASSWORD="$(generate_secret "$DB_PASSWORD_BYTES")"
    fi

    local values=(
        "SECRET_KEY=$(generate_secret "$SECRET_KEY_BYTES")"
        "ALLOWED_HOSTS=$(join_by , "${names[@]}")"
        "SITE_URL=$(site_url)"
        "EMAIL_URL=$EMAIL_URL"
        "DATABASE_URL=postgres://caldart:${DB_PASSWORD}@localhost:${CALDART_DB_PORT}/caldart"
        "CSRF_TRUSTED_ORIGINS=$(join_by , "${origins[@]}")"
        "DEFAULT_FROM_EMAIL=${FROM_EMAIL:-CalDART <noreply@$CALDART_HOSTNAME>}"
        "BACKUP_DIR=$ROOT/backups"
        "MEDIA_ROOT=$ROOT/media"
        "DB_BACKUP_VIA_DOCKER=false"
        "BACKUP_RETENTION_DAYS=30"
        "USER_GUIDE_ROOT=$CHECKOUT/docs/_build/guide"
        "CALDART_GUNICORN_PORT=$CALDART_GUNICORN_PORT"
    )
    if [[ -n "$CALDART_URL_PREFIX" ]]; then
        values+=("URL_PREFIX=$CALDART_URL_PREFIX")
    fi
    if [[ -n "$BOUNCE_IMAP_URL" ]]; then
        values+=("BOUNCE_IMAP_URL=$BOUNCE_IMAP_URL")
    fi
    if [[ -n "$BOUNCE_ADDRESS" ]]; then
        values+=("BOUNCE_ADDRESS=$BOUNCE_ADDRESS")
    fi
    # A browser must not remember HSTS for a hostname the box does not own.
    if [[ "$CALDART_TLS" == self-signed ]]; then
        values+=("SECURE_HSTS_SECONDS=0")
    fi

    local owner=() content
    mapfile -t owner < <(env_file_owner)
    content="$(fill_template "${values[@]}")"
    printf '%s\n' "$content" | write_file "$ENV_FILE" 0640 "${owner[@]}"
}

# Read the flags, then the install record, then apply the flags over it, so a
# step run alone knows the box and a flag given to it still wins.
configure_main() {
    local -A flags=()
    local key
    while (($#)); do
        case "$1" in
            --hostname)
                flags[CALDART_HOSTNAME]="$(option_value "$1" "${2:-}")"
                shift
                ;;
            --www) flags[CALDART_WWW]=yes ;;
            --no-www) flags[CALDART_WWW]=no ;;
            --tls)
                flags[CALDART_TLS]="$(option_value "$1" "${2:-}")"
                shift
                ;;
            --url-prefix)
                flags[CALDART_URL_PREFIX]="$(option_value "$1" "${2:-}")"
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
            --dry-run) enable_dry_run ;;
            --help)
                print_help "${BASH_SOURCE[0]}"
                exit 0
                ;;
            *) usage_error "unknown option $1" ;;
        esac
        shift
    done
    load_record
    for key in "${!flags[@]}"; do
        printf -v "$key" '%s' "${flags[$key]}"
    done
    [[ -z "$CALDART_HOSTNAME" ]] || validate_hostname "$CALDART_HOSTNAME"
    validate_url_prefix
    validate_email_flags
    if [[ "$ETC_DIR" == "$DEFAULT_ETC" ]]; then
        require_root
    fi
    configure_step
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    configure_main "$@"
fi
