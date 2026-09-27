#!/usr/bin/env bash
#
# CalDART - functions every installer script shares.
#
# Sourced, never run: logging, the dry run, the root check, the install record,
# and copying files out of deploy/ with the deploy root and the hostname
# written in.  docs/developer/deployment.rst describes the scripts that use it.
#
# Usage:
#   source "$ROOT/deploy/lib.sh"
#
# Environment:
#   CALDART_DRY_RUN    1 prints every state-changing command instead of running it
#   CALDART_ETC        the configuration directory (default /etc/caldart); the
#                      tests point it at a temporary directory
#   CALDART_OS_RELEASE the os-release file to read (default /etc/os-release)

# The constants below are read by the scripts that source this file, which a
# check of this file alone cannot see.
# shellcheck disable=SC2034

# Sourcing twice (install.sh sources every step, and every step sources this)
# must not redeclare the read-only constants below.
[[ -n "${CALDART_LIB_LOADED:-}" ]] && return 0
CALDART_LIB_LOADED=1

# The path every shipped file names, replaced by the real root as it is copied.
readonly SHIPPED_ROOT=/srv/caldart
# The hostname every shipped vhost names, replaced by the real one.
readonly SHIPPED_HOSTNAME=caldart.example.org
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
)
# Random bytes behind the generated database password.
readonly DB_PASSWORD_BYTES=32
readonly LETSENCRYPT_DIR=/etc/letsencrypt
readonly CERTBOT_WEBROOT=/var/www/certbot

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
# read, one KEY=value per line, and the file is never executed.
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

# Copy $1 to $2 with /srv/caldart replaced by the deploy root, plus any further
# sed arguments.  A dry run prints the pipeline.
render_file() {
    local source=$1 dest=$2
    shift 2
    local sed_command=(sed -e "s#${SHIPPED_ROOT}#${ROOT}#g" "$@" "$source")
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
