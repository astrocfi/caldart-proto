#!/usr/bin/env bash
#
# CalDART - functions every installer script shares.
#
# Sourced, never run: logging, the dry run, the root check, the install record,
# and copying files out of deploy/ with the checkout, the deploy root, the
# hostname, and the URL prefix written in.  docs/developer/deployment.rst
# describes the scripts that use it.
#
# The script that sources it first sets CHECKOUT, the checkout its deploy/
# directory sits in; this file sets ROOT, the deploy root, to the checkout's
# parent.  The deploy root holds the checkout, the database dumps (backups/),
# and the uploads (media/).
#
# Sourcing it stops, with a pointer to 'Moving to the current layout' in
# deploy/README.rst, when the install record names the checkout itself as the
# deploy root, unless the script sets CALDART_ANY_LAYOUT=1 first.
#
# Usage:
#   CHECKOUT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
#   source "$CHECKOUT/deploy/lib.sh"
#
# Environment:
#   CALDART_DRY_RUN    1 prints every state-changing command instead of running it
#   CALDART_ETC        the configuration directory (default /etc/caldart); the
#                      tests point it at a temporary directory
#   CALDART_OS_RELEASE the os-release file to read (default /etc/os-release)
#   CALDART_DB_PORT    the host port of the Postgres container (default 5432);
#                      the install record's value wins once it is read
#   CALDART_GUNICORN_PORT
#                      the port on 127.0.0.1 the web server proxies to gunicorn on
#                      (default 8001); the install record's value wins once it is read

# The constants below are read by the scripts that source this file, which a
# check of this file alone cannot see.
# shellcheck disable=SC2034

# Sourcing twice (install.sh sources every step, and every step sources this)
# must not redeclare the read-only constants below.
[[ -n "${CALDART_LIB_LOADED:-}" ]] && return 0
CALDART_LIB_LOADED=1

# The paths every shipped file names, replaced by the real ones as it is copied:
# the deploy root, and the checkout inside it.
readonly SHIPPED_ROOT=/opt/caldart
readonly SHIPPED_CHECKOUT=$SHIPPED_ROOT/caldart
# A stand-in for the checkout while the deploy root is written in, so a checkout
# path that itself contains /opt/caldart is not rewritten twice.
readonly CHECKOUT_MARK=__CALDART_CHECKOUT__
# The hostname every shipped vhost names, replaced by the real one.
readonly SHIPPED_HOSTNAME=caldart.example.org
# The URL prefix every shipped snippet names, replaced by the real one (or by
# nothing, for a site at the root of its host).
readonly SHIPPED_PREFIX=__PREFIX__
# The port on 127.0.0.1 every shipped vhost, snippet, and upstream proxies to,
# replaced by the recorded one; also the port gunicorn listens on by default.
readonly SHIPPED_GUNICORN_PORT=8001
readonly DEFAULT_ETC=/etc/caldart
readonly SYSTEMD_DIR=/etc/systemd/system
readonly SERVICE_USER=caldart
readonly WEB_UNIT=caldart-web
# The scheduled jobs: each is a service and the timer that starts it.
readonly JOB_UNITS=(
    caldart-registry
    caldart-reports
    caldart-renewals
    caldart-reminders
    caldart-statements
    caldart-backup
)
# The keys install.conf holds, none of them secret.
readonly RECORD_KEYS=(
    CALDART_ROOT
    CALDART_HOSTNAME
    CALDART_WWW
    CALDART_WEB_SERVER
    CALDART_TLS
    CALDART_CERTBOT_EMAIL
    CALDART_CERTBOT_STAGING
    CALDART_DB_PORT
    CALDART_GUNICORN_PORT
    CALDART_URL_PREFIX
    CALDART_ATTACH_TO
)
# Random bytes behind the generated database password.
readonly DB_PASSWORD_BYTES=32
readonly LETSENCRYPT_DIR=/etc/letsencrypt
readonly CERTBOT_WEBROOT=/var/www/certbot
# The host port docker-compose.yml publishes the database on.
readonly DEFAULT_DB_PORT=5432
# The bounds of a port an option names: above the privileged ports, within
# TCP's range.
readonly MIN_PORT=1024
readonly MAX_PORT=65535
# A decimal port with no leading zero, which bash arithmetic would read as octal.
readonly PORT_PATTERN='^[1-9][0-9]{0,4}$'
# The mail relay --email local stands for: the postfix on this machine.
readonly LOCAL_EMAIL_URL=smtp://localhost:25
# One segment of a URL prefix, as the settings read URL_PREFIX: the characters a
# path segment carries unescaped.  The segments . and .. are refused as well.
readonly PREFIX_SEGMENT_PATTERN='^[A-Za-z0-9._~-]+$'

# The deploy root: the directory the checkout sits in.
ROOT="$(dirname "$CHECKOUT")"
ETC_DIR="${CALDART_ETC:-$DEFAULT_ETC}"
ENV_FILE="$ETC_DIR/caldart.env"
RECORD_FILE="$ETC_DIR/install.conf"
TLS_DIR="$ETC_DIR/tls"
DRY_RUN="${CALDART_DRY_RUN:-0}"

# The record's values, with the defaults a first run starts from.
CALDART_HOSTNAME="${CALDART_HOSTNAME:-}"
CALDART_WWW="${CALDART_WWW:-yes}"
CALDART_WEB_SERVER="${CALDART_WEB_SERVER:-apache}"
CALDART_TLS="${CALDART_TLS:-certbot}"
CALDART_CERTBOT_EMAIL="${CALDART_CERTBOT_EMAIL:-}"
CALDART_CERTBOT_STAGING="${CALDART_CERTBOT_STAGING:-no}"
# The path the site is served under on a host another site owns, such as
# /caldart-proto, or empty at the root of its host; and the existing site's vhost
# file the existing TLS mode includes the snippet in, or empty.
CALDART_URL_PREFIX="${CALDART_URL_PREFIX:-}"
CALDART_ATTACH_TO="${CALDART_ATTACH_TO:-}"
# Exported, so every docker compose a script runs publishes the recorded port:
# docker-compose.yml reads it, and a compose command without it would move the
# container back to the default.  load_record keeps the export as it assigns.
export CALDART_DB_PORT="${CALDART_DB_PORT:-$DEFAULT_DB_PORT}"
# Exported for the same reason: a record written before the key existed leaves
# the default in place, the port every earlier install used.
export CALDART_GUNICORN_PORT="${CALDART_GUNICORN_PORT:-$SHIPPED_GUNICORN_PORT}"

# A DNS name of at least two labels: letters, digits, and inner hyphens.  The
# hostname is written into sed expressions, the vhost, and line-based files, so
# nothing else may reach them.
readonly HOSTNAME_PATTERN='^[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?)+$'

# The stage the last log line announced, which a failing command is reported in.
CURRENT_STAGE=""

# Print one stage line on stdout.
log() {
    CURRENT_STAGE="$*"
    printf '==> %s\n' "$*"
}

# Report a command that failed under set -e with the stage it failed in.  Only
# the top-level shell reports, once a stage has begun: a failure inside a
# command substitution already printed its own error line, and one before the
# first stage is a usage error that did too.
report_failure() {
    local status=$1 command=$2
    [[ -n "$CURRENT_STAGE" ]] || return 0
    ((BASH_SUBSHELL == 0)) || return 0
    printf 'error: %s failed: %s exited with status %s\n' \
        "$CURRENT_STAGE" "$command" "$status" >&2
}

# errtrace carries the trap into functions, where every step's commands run.
set -E
trap 'report_failure "$?" "$BASH_COMMAND"' ERR

# Print a note on stderr that is not an error.
note() {
    printf '%s\n' "$*" >&2
}

# Print an error on stderr and exit 1.
die() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

# Print a usage error on stderr and exit 2.
usage_error() {
    printf 'error: %s\n' "$*" >&2
    printf "Run '%s --help' for the options.\n" "$0" >&2
    exit 2
}

# Print the header comment of the script at $1: every line after the shebang
# up to the first line that is not a comment, without its leading "# ".
print_help() {
    local line started=no
    while IFS= read -r line; do
        case "$line" in
            '#!'*) continue ;;
            '#') [[ "$started" == no ]] || printf '\n' ;;
            '# '*)
                started=yes
                printf '%s\n' "${line#'# '}"
                ;;
            *) return 0 ;;
        esac
    done <"$1"
}

# Turn the dry run on for this script and every script it starts.
enable_dry_run() {
    DRY_RUN=1
    export CALDART_DRY_RUN=1
}

# Parse the flags a step with no options of its own takes: --dry-run and
# --help, the latter printing the header of the script at $1.
parse_step_flags() {
    local script=$1
    shift
    while (($#)); do
        case "$1" in
            --dry-run) enable_dry_run ;;
            --help)
                print_help "$script"
                exit 0
                ;;
            *) usage_error "unknown option $1" ;;
        esac
        shift
    done
}

# Print the value $2 given to the option $1, or stop with a usage error when
# the option came last with no value.
option_value() {
    [[ -n "${2:-}" ]] || usage_error "$1 needs a value"
    printf '%s\n' "$2"
}

is_dry_run() {
    [[ "$DRY_RUN" == 1 ]]
}

# Quote one word for a shell, leaving plain words bare.
shell_quote() {
    if [[ "$1" =~ ^[A-Za-z0-9_./:=@%+,-]+$ ]]; then
        printf '%s' "$1"
    else
        printf "'%s'" "${1//\'/\'\\\'\'}"
    fi
}

# Print a command shell-quoted, one line.
quote_command() {
    local word first=1
    for word in "$@"; do
        [[ $first == 1 ]] || printf ' '
        shell_quote "$word"
        first=0
    done
}

# Run a state-changing command, or print it in a dry run.
run() {
    if is_dry_run; then
        printf '+ %s\n' "$(quote_command "$@")"
        return 0
    fi
    "$@"
}

# Run a command with $1 on its standard input, never on its command line.  A
# dry run prints the input after the command; secrets in it are already
# placeholders there.
run_stdin() {
    local input=$1
    shift
    if is_dry_run; then
        printf '+ %s <<< %s\n' "$(quote_command "$@")" "$(shell_quote "$input")"
        return 0
    fi
    printf '%s\n' "$input" | "$@"
}

# Write standard input to $1 with mode $2, owned by $3:$4 when both are given.
write_file() {
    local dest=$1 mode=$2 owner=${3:-} group=${4:-}
    local command=(install -m "$mode")
    if [[ -n "$owner" ]]; then
        command+=(-o "$owner" -g "$group")
    fi
    command+=(/dev/stdin "$dest")
    if is_dry_run; then
        cat >/dev/null
        printf '+ %s\n' "$(quote_command "${command[@]}")"
        return 0
    fi
    "${command[@]}"
}

# Stop unless running as root; a dry run changes nothing and needs no root.
require_root() {
    is_dry_run && return 0
    [[ "$(id -u)" == 0 ]] || die "run this as root (sudo $0)"
}

# Wait up to $1 seconds for a command to succeed, trying every two seconds.  In
# a dry run the command it waits on never ran, so it prints the wait instead.
wait_for() {
    local seconds=$1
    shift
    if is_dry_run; then
        printf '+ %s\n' "$(quote_command "$@")"
        return 0
    fi
    local waited=0
    until "$@" >/dev/null 2>&1; do
        ((waited >= seconds)) && return 1
        sleep 2
        waited=$((waited + 2))
    done
}

# Read install.conf into the CALDART_* variables.  Only the known keys are
# read, one KEY=value per line, and the file is never executed.  CALDART_ROOT,
# the deploy root, is recorded for the operator and never read back: every
# script finds the checkout from its own location and the deploy root from it.
load_record() {
    local line key value known
    if [[ ! -f "$RECORD_FILE" ]]; then
        is_dry_run && note "dry run: no install record at $RECORD_FILE; treating it as absent"
        return 0
    fi
    while IFS= read -r line; do
        [[ "$line" == *=* ]] || continue
        key=${line%%=*}
        value=${line#*=}
        for known in "${RECORD_KEYS[@]}"; do
            if [[ "$key" == "$known" && "$key" != CALDART_ROOT ]]; then
                printf -v "$key" '%s' "$value"
            fi
        done
    done <"$RECORD_FILE"
}

have_record() {
    [[ -f "$RECORD_FILE" ]]
}

# Write the CALDART_* variables to install.conf, root-owned and world-readable.
write_record() {
    local key
    {
        printf '# CalDART install record, written by deploy/install.sh.  No secrets.\n'
        for key in "${RECORD_KEYS[@]}"; do
            if [[ "$key" == CALDART_ROOT ]]; then
                printf '%s=%s\n' "$key" "$ROOT"
            else
                printf '%s=%s\n' "$key" "${!key}"
            fi
        done
    } | write_file "$RECORD_FILE" 0644 root root
}

# True when the environment file exists.  A dry run never writes it, so an
# absent file there is said out loud.
have_env_file() {
    if [[ -f "$ENV_FILE" ]]; then
        return 0
    fi
    is_dry_run && note "dry run: no environment file at $ENV_FILE; treating it as absent"
    return 1
}

# Stop with a usage error unless $1 is a DNS name.
validate_hostname() {
    [[ "$1" =~ $HOSTNAME_PATTERN ]] ||
        usage_error "--hostname must be a DNS name such as $SHIPPED_HOSTNAME, not $1"
}

# Stop with a usage error naming the option $1 unless $2 is a port from
# MIN_PORT to MAX_PORT.
validate_port() {
    local option=$1 value=$2
    if [[ "$value" =~ $PORT_PATTERN ]] && ((value >= MIN_PORT && value <= MAX_PORT)); then
        return 0
    fi
    usage_error "$option must be a port number from $MIN_PORT to $MAX_PORT, not $value"
}

# Stop with a usage error unless $1 is a port Postgres may be published on.
validate_db_port() {
    validate_port --db-port "$1"
}

# Stop with a usage error unless $1 is a port gunicorn may listen on.
validate_gunicorn_port() {
    validate_port --gunicorn-port "$1"
}

# The port DATABASE_URL in the environment file connects to: the port it names,
# 5432 when it names none, and nothing when the file or the line is missing or
# unreadable.
env_file_db_port() {
    [[ -r "$ENV_FILE" ]] || return 0
    local url
    url="$(sed -n 's/^DATABASE_URL=//p' "$ENV_FILE" | tail -n 1)"
    [[ -n "$url" ]] || return 0
    if [[ "$url" =~ @[^/@]*:([0-9]+)(/|$) ]]; then
        printf '%s\n' "${BASH_REMATCH[1]}"
    else
        printf '%s\n' "$DEFAULT_DB_PORT"
    fi
}

# Stop with a usage error when the environment file's DATABASE_URL connects to
# another port than CALDART_DB_PORT.  The install leaves an existing file alone,
# so moving the container without the file would leave the site connecting to a
# port nothing serves.
validate_db_port_matches_env_file() {
    local current
    current="$(env_file_db_port)"
    [[ -z "$current" || "$current" == "$CALDART_DB_PORT" ]] && return 0
    usage_error "--db-port $CALDART_DB_PORT differs from the port in DATABASE_URL in $ENV_FILE ($current); edit DATABASE_URL to use port $CALDART_DB_PORT first, then run install.sh again"
}

# Print the URL prefix $1 as /segment[/segment...], or nothing for none: one
# leading and one trailing slash are optional, as they are to the settings.
# Fails, printing nothing, for an empty segment, a . or .. segment, or any
# character a segment may not carry.
normalize_url_prefix() {
    local value=${1#/} segment segments=()
    value=${value%/}
    [[ -n "$value" ]] || return 0
    [[ "$value" != /* && "$value" != */ && "$value" != *//* ]] || return 1
    IFS=/ read -r -a segments <<<"$value"
    for segment in "${segments[@]}"; do
        [[ "$segment" =~ $PREFIX_SEGMENT_PATTERN && "$segment" != . && "$segment" != .. ]] ||
            return 1
    done
    # read stops at a newline, which no segment may carry.
    [[ "$(IFS=/; printf '%s' "${segments[*]}")" == "$value" ]] || return 1
    printf '/%s\n' "$value"
}

# Replace CALDART_URL_PREFIX with its normalized form, or stop with a usage error.
validate_url_prefix() {
    local normalized
    normalized="$(normalize_url_prefix "$CALDART_URL_PREFIX")" ||
        usage_error "--url-prefix must be a path such as /caldart-proto, not $CALDART_URL_PREFIX"
    CALDART_URL_PREFIX=$normalized
}

# Print the URL prefix the environment file serves under, normalized, when the
# file is readable: the value of URL_PREFIX, or nothing when that line is
# missing or commented out.  Fails when the file is missing or unreadable.
env_file_url_prefix() {
    [[ -r "$ENV_FILE" ]] || return 1
    local value
    value="$(sed -n 's/^URL_PREFIX=//p' "$ENV_FILE" | tail -n 1)"
    normalize_url_prefix "$value" || printf '%s\n' "$value"
}

# Stop with a usage error when the environment file serves under another prefix
# than CALDART_URL_PREFIX.  The install leaves an existing file alone, so moving
# the snippet without the file would leave Django writing links to the old path.
validate_url_prefix_matches_env_file() {
    local current
    current="$(env_file_url_prefix)" || return 0
    [[ "$current" == "$CALDART_URL_PREFIX" ]] && return 0
    usage_error "the URL prefix ${CALDART_URL_PREFIX:-(none)} differs from URL_PREFIX in $ENV_FILE (${current:-none}); set URL_PREFIX and the path of SITE_URL there to match first, then run install.sh again"
}

# The site's public address, no trailing slash: SITE_URL.
site_url() {
    printf 'https://%s%s\n' "$CALDART_HOSTNAME" "$CALDART_URL_PREFIX"
}

# The address gunicorn answers on: 127.0.0.1 at the recorded gunicorn port.
gunicorn_url() {
    printf 'http://127.0.0.1:%s/\n' "$CALDART_GUNICORN_PORT"
}

# Ask gunicorn itself, not the web server, for the site's front page, with the
# command word $1 in front: run, for a dry run that prints the request, or
# command, which sends it.  The
# Host header must be in ALLOWED_HOSTS, and X-Forwarded-Proto keeps
# SECURE_SSL_REDIRECT from answering 301.
gunicorn_probe() {
    "$1" curl -sI -H "Host: $CALDART_HOSTNAME" -H 'X-Forwarded-Proto: https' "$(gunicorn_url)"
}

# The HTTP status gunicorn answers the probe with, or nothing when it answers
# nothing.
gunicorn_status() {
    gunicorn_probe command | awk 'NR == 1 { print $2 }'
}

# True when something on this machine listens on TCP port $1.  Without ss
# there is no telling, and the answer is no.
port_in_use() {
    command -v ss >/dev/null 2>&1 || return 1
    [[ -n "$(ss -ltnH "sport = :$1")" ]]
}

# The hostname, or a placeholder in a dry run that has none.
require_hostname() {
    if [[ -n "$CALDART_HOSTNAME" ]]; then
        return 0
    fi
    if is_dry_run; then
        note "dry run: no hostname recorded; printing <hostname> in its place"
        CALDART_HOSTNAME='<hostname>'
        return 0
    fi
    die "no hostname recorded in $RECORD_FILE; run deploy/install.sh --hostname HOST"
}

# Every name the site answers for: the hostname and, with www, its www. form.
site_names() {
    printf '%s\n' "$CALDART_HOSTNAME"
    if [[ "$CALDART_WWW" == yes ]]; then
        printf 'www.%s\n' "$CALDART_HOSTNAME"
    fi
}

# The certificate and key the vhost reads, for the TLS mode in use.
certificate_path() {
    if [[ "$CALDART_TLS" == self-signed ]]; then
        printf '%s/fullchain.pem\n' "$TLS_DIR"
    else
        printf '%s/live/%s/fullchain.pem\n' "$LETSENCRYPT_DIR" "$CALDART_HOSTNAME"
    fi
}

# A random URL-safe secret of about 4/3 x $1 characters, or a placeholder in a
# dry run so no secret is ever printed.
generate_secret() {
    if is_dry_run; then
        printf '<generated>'
        return 0
    fi
    python3 -c "import secrets, sys; print(secrets.token_urlsafe(int(sys.argv[1])))" "$1"
}

# Copy $1 to $2 with /opt/caldart/caldart replaced by the checkout, then
# /opt/caldart by the deploy root, and gunicorn's shipped address by the
# recorded one, plus any further sed arguments.  A dry run prints the pipeline.
render_file() {
    local source=$1 dest=$2
    shift 2
    local sed_command=(
        sed -e "s#${SHIPPED_CHECKOUT}#${CHECKOUT_MARK}#g"
        -e "s#${SHIPPED_ROOT}#${ROOT}#g"
        -e "s#${CHECKOUT_MARK}#${CHECKOUT}#g"
        -e "s#127.0.0.1:${SHIPPED_GUNICORN_PORT}#127.0.0.1:${CALDART_GUNICORN_PORT}#g"
        "$@" "$source"
    )
    if is_dry_run; then
        printf '+ %s | %s\n' "$(quote_command "${sed_command[@]}")" \
            "$(quote_command install -m 0644 /dev/stdin "$dest")"
        return 0
    fi
    "${sed_command[@]}" | install -m 0644 /dev/stdin "$dest"
}

# Copy the vhost $1 to $2 for hostname $3, with $4 (yes or no) deciding the www.
# alias and $5 (certbot or self-signed) where the certificate lives.
render_vhost() {
    local source=$1 dest=$2 hostname=$3 www=$4 tls=$5
    local shipped="${SHIPPED_HOSTNAME//./\\.}"
    local args=()
    if [[ "$tls" == self-signed ]]; then
        args+=(-e "s#${LETSENCRYPT_DIR}/live/${shipped}/#${TLS_DIR}/#g")
    fi
    if [[ "$www" != yes ]]; then
        args+=(-e "/^ *ServerAlias www\\.${shipped}\$/d" -e "s/ www\\.${shipped}//g")
    fi
    args+=(-e "s/${shipped}/${hostname}/g")
    render_file "$source" "$dest" "${args[@]}"
}

# Copy the snippet $1 to $2 with the recorded hostname and URL prefix written in.
render_snippet() {
    local source=$1 dest=$2
    local shipped="${SHIPPED_HOSTNAME//./\\.}"
    render_file "$source" "$dest" \
        -e "s#${SHIPPED_PREFIX}#${CALDART_URL_PREFIX}#g" \
        -e "s/${shipped}/${CALDART_HOSTNAME}/g"
}

# The deploy root the install record names, or nothing when there is no record
# or it names none.
recorded_root() {
    [[ -f "$RECORD_FILE" ]] || return 0
    sed -n 's/^CALDART_ROOT=//p' "$RECORD_FILE" | tail -n 1
}

# True when the install record names the checkout itself as the deploy root: an
# install whose checkout is /opt/caldart, with its dumps and uploads inside it.
is_checkout_layout() {
    [[ "$(recorded_root)" == "$CHECKOUT" ]]
}

# Stop on an install that keeps its data inside the checkout.  Every path these
# scripts write names the checkout's parent, which on such an install is the
# machine's /opt, so running on would point the site at directories that are
# not there.
refuse_checkout_layout() {
    is_checkout_layout || return 0
    die "this install keeps its data inside the checkout at $CHECKOUT;" \
        "see 'Moving to the current layout' in deploy/README.rst"
}

# A script that is safe on either layout (the uninstaller, manage.sh, and
# compose.sh) sets CALDART_ANY_LAYOUT=1 before sourcing this file; every other
# script stops here on such an install, before it changes anything.
[[ "${CALDART_ANY_LAYOUT:-0}" == 1 ]] || refuse_checkout_layout
