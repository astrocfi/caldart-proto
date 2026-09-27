#!/usr/bin/env bash
#
# CalDART install step - the environment file.
#
# Writes /etc/caldart/caldart.env once, root:caldart, mode 0640, from the
# production template deploy/caldart.env.example.  The five variables the
# template leaves commented out are uncommented and set: SECRET_KEY generated,
# ALLOWED_HOSTS from the hostname (and its www. form), SITE_URL, EMAIL_URL from
# --email-url, and DATABASE_URL with the password the Postgres step set.  It
# also sets CSRF_TRUSTED_ORIGINS for the same hosts, DEFAULT_FROM_EMAIL,
# BACKUP_DIR and USER_GUIDE_ROOT under the deploy root, DB_BACKUP_VIA_DOCKER=false,
# BACKUP_RETENTION_DAYS=30, and, with self-signed TLS, SECURE_HSTS_SECONDS=0.
# Everything else, comments included, stays as the template has it.
#
# When the file exists this step leaves it alone: edit it with sudoedit, then
# run systemctl restart caldart-web.  Run alone rather than from install.sh, the
# step has no database password handed to it and writes a generated one the
# database does not have.
#
# Usage:
#   sudo deploy/steps/configure.sh [options]
#
# Options:
#   --hostname HOST        the public hostname (default: the install record's)
#   --www, --no-www        also answer for www.HOST (default: the record's, or --www)
#   --tls MODE             certbot or self-signed (default: the record's, or certbot)
#   --email-url URL        EMAIL_URL; required when the file does not exist
#   --from-email ADDRESS   DEFAULT_FROM_EMAIL (default: CalDART <noreply@HOST>)
#   --dry-run              print every state-changing command instead of running it
#   --help                 show this help
#
# Environment:
#   CALDART_ETC   the directory to write caldart.env into (default /etc/caldart);
#                 any other directory skips the root check and the ownership

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=deploy/lib.sh
source "$ROOT/deploy/lib.sh"

readonly TEMPLATE="$ROOT/deploy/caldart.env.example"
readonly SECRET_KEY_BYTES=64

EMAIL_URL="${EMAIL_URL:-}"
FROM_EMAIL="${FROM_EMAIL:-}"
DB_PASSWORD="${DB_PASSWORD:-}"

# Join the remaining arguments with the separator $1.
join_by() {
    local separator=$1 first=$2
    shift 2
    printf '%s' "$first" "${@/#/$separator}"
}

# Print the template with each KEY=value from the arguments written over the
# line that sets or comments out KEY.  awk reads the values from its
# environment, so no character in them needs escaping.
fill_template() {
    local pairs=("$@") names=() pair
    for pair in "${pairs[@]}"; do
        names+=("${pair%%=*}")
    done
    # The $ signs below are awk's, not the shell's.
    # shellcheck disable=SC2016
    env "${pairs[@]/#/FILL_}" FILL_NAMES="${names[*]}" awk '
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
}

configure_step() {
    if have_env_file; then
        log "Leaving $ENV_FILE alone: it exists"
        [[ -z "$EMAIL_URL" ]] || printf '    --email-url is ignored: edit the file with sudoedit\n'
        [[ -z "$FROM_EMAIL" ]] || printf '    --from-email is ignored: edit the file with sudoedit\n'
        return 0
    fi
    [[ -n "$CALDART_HOSTNAME" ]] || usage_error "--hostname is required to write $ENV_FILE"
    [[ -n "$EMAIL_URL" ]] || usage_error "--email-url is required to write $ENV_FILE"

    log "Writing $ENV_FILE"
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
        "SITE_URL=https://$CALDART_HOSTNAME"
        "EMAIL_URL=$EMAIL_URL"
        "DATABASE_URL=postgres://caldart:${DB_PASSWORD}@localhost:5432/caldart"
        "CSRF_TRUSTED_ORIGINS=$(join_by , "${origins[@]}")"
        "DEFAULT_FROM_EMAIL=${FROM_EMAIL:-CalDART <noreply@$CALDART_HOSTNAME>}"
        "BACKUP_DIR=$ROOT/backups"
        "DB_BACKUP_VIA_DOCKER=false"
        "BACKUP_RETENTION_DAYS=30"
        "USER_GUIDE_ROOT=$ROOT/docs/_build/guide"
    )
    # A browser must not remember HSTS for a hostname the box does not own.
    if [[ "$CALDART_TLS" == self-signed ]]; then
        values+=("SECURE_HSTS_SECONDS=0")
    fi

    local owner=()
    if [[ "$ETC_DIR" == "$DEFAULT_ETC" ]]; then
        owner=(root "$SERVICE_USER")
    fi
    local content
    content="$(fill_template "${values[@]}")"
    printf '%s\n' "$content" | write_file "$ENV_FILE" 0640 "${owner[@]}"
}

configure_main() {
    while (($#)); do
        case "$1" in
            --hostname)
                CALDART_HOSTNAME="$(option_value "$1" "${2:-}")"
                shift
                ;;
            --www) CALDART_WWW=yes ;;
            --no-www) CALDART_WWW=no ;;
            --tls)
                CALDART_TLS="$(option_value "$1" "${2:-}")"
                shift
                ;;
            --email-url)
                EMAIL_URL="$(option_value "$1" "${2:-}")"
                shift
                ;;
            --from-email)
                FROM_EMAIL="$(option_value "$1" "${2:-}")"
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
    [[ "$ETC_DIR" == "$DEFAULT_ETC" ]] && require_root
    configure_step
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    configure_main "$@"
fi
