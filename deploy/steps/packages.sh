#!/usr/bin/env bash
#
# CalDART install step 1 - operating system packages.
#
# Installs what the server needs from the distribution's own archive: git, curl,
# the Postgres client, Docker and its Compose v2 plugin, the web server named in
# the install record with certbot and certbot's plugin for it, Node 22 from
# NodeSource when the installed Node is missing or older, and uv into
# /usr/local/bin when it is missing.  Then starts Docker.  Debian and Ubuntu are
# supported; Debian's Compose v2 package is docker-compose, Ubuntu's is
# docker-compose-v2.
#
# Usage:
#   sudo deploy/steps/packages.sh [--dry-run]
#
# Options:
#   --dry-run   print every state-changing command instead of running it
#   --help      show this help
#
# Environment:
#   CALDART_OS_RELEASE  the os-release file to read (default /etc/os-release)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=deploy/lib.sh
source "$ROOT/deploy/lib.sh"

readonly BASE_PACKAGES=(git curl ca-certificates openssl postgresql-client docker.io)
readonly NODE_MAJOR=22
readonly NODESOURCE_SETUP="curl -fsSL https://deb.nodesource.com/setup_${NODE_MAJOR}.x | bash -"
readonly UV_BIN=/usr/local/bin/uv
readonly UV_INSTALL="curl -LsSf https://astral.sh/uv/install.sh | sh"

# Print the value of $1 in the os-release file, without quotes.
os_release_value() {
    local file="${CALDART_OS_RELEASE:-/etc/os-release}" line value
    while IFS= read -r line; do
        if [[ "$line" == "$1="* ]]; then
            value=${line#*=}
            value=${value#\"}
            printf '%s\n' "${value%\"}"
            return 0
        fi
    done <"$file"
}

# The Compose v2 package for the distribution this is.
compose_package() {
    local distro
    distro="$(os_release_value ID)"
    case "$distro" in
        debian) printf 'docker-compose\n' ;;
        ubuntu) printf 'docker-compose-v2\n' ;;
        *) die "${distro:-this distribution} is not supported; use Debian or Ubuntu" ;;
    esac
}

# The web server and the certbot packages for it.
web_server_packages() {
    case "$CALDART_WEB_SERVER" in
        apache) printf '%s\n' apache2 certbot python3-certbot-apache ;;
        nginx) printf '%s\n' nginx certbot python3-certbot-nginx ;;
        *) die "unknown web server $CALDART_WEB_SERVER in $RECORD_FILE" ;;
    esac
}

# True when node is missing or older than the build needs.
needs_node() {
    local version
    command -v node >/dev/null 2>&1 || return 0
    version="$(node -v)"
    version=${version#v}
    ((${version%%.*} < NODE_MAJOR))
}

apt_install() {
    run env DEBIAN_FRONTEND=noninteractive apt-get install -y "$@"
}

packages_step() {
    local compose web=()
    compose="$(compose_package)"
    mapfile -t web < <(web_server_packages)

    log "Installing the operating system packages"
    run env DEBIAN_FRONTEND=noninteractive apt-get update
    apt_install "${BASE_PACKAGES[@]}" "$compose" "${web[@]}"

    if needs_node; then
        log "Installing Node ${NODE_MAJOR} from NodeSource"
        run bash -c "$NODESOURCE_SETUP"
        apt_install nodejs
    fi

    if [[ ! -x "$UV_BIN" ]]; then
        log "Installing uv into $(dirname "$UV_BIN")"
        run env UV_INSTALL_DIR="$(dirname "$UV_BIN")" UV_NO_MODIFY_PATH=1 bash -c "$UV_INSTALL"
    fi

    log "Starting Docker"
    run systemctl enable --now docker
}

packages_main() {
    parse_step_flags "${BASH_SOURCE[0]}" "$@"
    require_root
    load_record
    packages_step
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    packages_main "$@"
fi
