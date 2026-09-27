#!/usr/bin/env bash
#
# CalDART - fetch the site onto a fresh server and install it.
#
# Clones the repository into the deploy root (or, when a checkout is already
# there, fetches and checks out the ref), then runs deploy/install.sh from that
# checkout with every other flag passed through untouched.  It is the one file
# a server needs before the repository is there, so it is meant to be piped
# into bash:
#
#   curl -fsSL https://raw.githubusercontent.com/astrocfi/caldart-proto/main/deploy/bootstrap.sh \
#       | sudo bash -s -- --hostname caldart.example.org --certbot-email ops@example.org \
#           --email-url smtp+tls://user:password@smtp.example.org:587 --admin-email you@example.org
#
# Usage:
#   sudo deploy/bootstrap.sh [--repo URL-OR-PATH] [--ref REF] [install options]
#
# Options:
#   --repo URL-OR-PATH   what to clone (default https://github.com/astrocfi/caldart-proto.git)
#   --ref REF            the branch, tag, or commit to install (default main)
#   --dry-run            print every state-changing command instead of running it
#   --help               show this help
#   Every other option goes to deploy/install.sh; see its --help.
#
# Environment:
#   CALDART_ROOT   the deploy root to clone into (default /opt/caldart)

set -euo pipefail

readonly DEFAULT_REPO=https://github.com/astrocfi/caldart-proto.git
readonly DEFAULT_REF=main
readonly DEPLOY_ROOT="${CALDART_ROOT:-/opt/caldart}"
# The install options that take a value, so their values are passed through too.
readonly VALUE_OPTIONS=" --hostname --web-server --tls --certbot-email --db-port --email-url --email --from-email --admin-email "

REPO="$DEFAULT_REPO"
REF="$DEFAULT_REF"
DRY_RUN="${CALDART_DRY_RUN:-0}"
PASSTHROUGH=()

# The lines this script prints match deploy/lib.sh's, which it cannot source:
# when it starts, the repository is not on the machine yet.
log() {
    printf '==> %s\n' "$*"
}

die() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

usage_error() {
    printf 'error: %s\n' "$*" >&2
    printf "Run '%s --help' for the options.\n" "$0" >&2
    exit 2
}

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

shell_quote() {
    if [[ "$1" =~ ^[A-Za-z0-9_./:=@%+,-]+$ ]]; then
        printf '%s' "$1"
    else
        printf "'%s'" "${1//\'/\'\\\'\'}"
    fi
}

# Print a command shell-quoted, one line, with the value of --email-url, which
# can carry the mail relay's password, masked.
quote_command() {
    local word first=1 masked=0
    for word in "$@"; do
        [[ $first == 1 ]] || printf ' '
        if [[ $masked == 1 ]]; then
            word='<email-url>'
        fi
        shell_quote "$word"
        first=0
        masked=0
        [[ "$word" != --email-url ]] || masked=1
    done
}

run() {
    if [[ "$DRY_RUN" == 1 ]]; then
        printf '+ %s\n' "$(quote_command "$@")"
        return 0
    fi
    "$@"
}

parse_flags() {
    while (($#)); do
        case "$1" in
            --repo | --ref)
                [[ -n "${2:-}" ]] || usage_error "$1 needs a value"
                if [[ "$1" == --repo ]]; then REPO=$2; else REF=$2; fi
                shift
                ;;
            --dry-run)
                DRY_RUN=1
                PASSTHROUGH+=("$1")
                ;;
            --help)
                # Piped into bash there is no file to read the header from.
                if [[ -f "${BASH_SOURCE[0]}" ]]; then
                    print_help "${BASH_SOURCE[0]}"
                else
                    printf 'Usage: bootstrap.sh [--repo URL-OR-PATH] [--ref REF] [install options]\n'
                fi
                exit 0
                ;;
            --*)
                case "$VALUE_OPTIONS" in
                    *" $1 "*)
                        [[ -n "${2:-}" ]] || usage_error "$1 needs a value"
                        PASSTHROUGH+=("$1" "$2")
                        shift
                        ;;
                    *)
                        case "$1" in
                            --www | --no-www | --certbot-staging | --seed-content) PASSTHROUGH+=("$1") ;;
                            *) usage_error "unknown option $1" ;;
                        esac
                        ;;
                esac
                ;;
            *) usage_error "unknown option $1" ;;
        esac
        shift
    done
}

# True when the ref names a branch on the remote, which a checkout leaves
# behind its remote until it is pulled.
ref_is_branch() {
    git -C "$DEPLOY_ROOT" show-ref --verify --quiet "refs/remotes/origin/$REF"
}

fetch_code() {
    if [[ -d "$DEPLOY_ROOT/.git" ]]; then
        log "Updating the checkout at $DEPLOY_ROOT"
        run git -C "$DEPLOY_ROOT" fetch origin
        run git -C "$DEPLOY_ROOT" checkout "$REF"
        if ref_is_branch; then
            run git -C "$DEPLOY_ROOT" pull --ff-only
        fi
        return 0
    fi
    if [[ -e "$DEPLOY_ROOT" ]] && [[ -n "$(ls -A "$DEPLOY_ROOT")" ]]; then
        die "$DEPLOY_ROOT exists and is not a checkout; move it aside first"
    fi
    log "Cloning $REPO into $DEPLOY_ROOT"
    run git clone "$REPO" "$DEPLOY_ROOT"
    run git -C "$DEPLOY_ROOT" checkout "$REF"
}

main() {
    parse_flags "$@"
    if [[ "$DRY_RUN" != 1 && "$(id -u)" != 0 ]]; then
        die "run this as root (sudo bash)"
    fi
    if ! command -v git >/dev/null 2>&1; then
        log "Installing git"
        run env DEBIAN_FRONTEND=noninteractive apt-get update
        run env DEBIAN_FRONTEND=noninteractive apt-get install -y git
    fi
    fetch_code

    local installer="$DEPLOY_ROOT/deploy/install.sh"
    if [[ "$DRY_RUN" == 1 && ! -f "$installer" ]]; then
        run bash "$installer" "${PASSTHROUGH[@]}"
        return 0
    fi
    exec bash "$installer" "${PASSTHROUGH[@]}"
}

main "$@"
