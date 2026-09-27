#!/usr/bin/env bash
#
# CalDART install step - operating system packages.
#
# Installs what the server needs from the distribution's own archive: git, curl,
# the Postgres client, Docker and its Compose v2 plugin, the web server named in
# the install record with certbot and certbot's plugin for it (no certbot with
# the existing TLS mode, where the existing site holds the certificate), Node 22
# from NodeSource when the installed Node is missing or older, and uv into
# /usr/local/bin when it is missing.  Then starts Docker.  Debian and Ubuntu are
# supported; Debian's Compose v2 package is docker-compose, Ubuntu's is
# docker-compose-v2.  A Docker already installed is left as it is: docker.io is
# skipped when docker --version works, and the Compose package too when docker
# compose version works, so a Docker from Docker's own repository (docker-ce),
# which docker.io would conflict with, is never replaced.
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

readonly BASE_PACKAGES=(git curl ca-certificates openssl postgresql-client)
readonly DOCKER_PACKAGE=docker.io
readonly NODE_MAJOR=22
# pipefail, so a download that fails fails the step instead of piping nothing
# into a shell that exits 0.
readonly NODESOURCE_SETUP="set -o pipefail; curl -fsSL https://deb.nodesource.com/setup_${NODE_MAJOR}.x | bash -"
readonly UV_BIN=/usr/local/bin/uv
readonly UV_INSTALL="set -o pipefail; curl -LsSf https://astral.sh/uv/install.sh | sh"

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

# The web server and, unless the existing site holds the certificate, the
# certbot packages for it.
web_server_packages() {
    local server plugin
    case "$CALDART_WEB_SERVER" in
        apache) server=apache2 plugin=python3-certbot-apache ;;
        nginx) server=nginx plugin=python3-certbot-nginx ;;
        *) die "unknown web server $CALDART_WEB_SERVER in $RECORD_FILE" ;;
    esac
    printf '%s\n' "$server"
    if [[ "$CALDART_TLS" != existing ]]; then
        printf '%s\n' certbot "$plugin"
    fi
}

# The Docker packages this machine still needs: the engine unless docker runs,
# and the Compose v2 plugin unless docker compose runs.
docker_packages() {
    docker --version >/dev/null 2>&1 || printf '%s\n' "$DOCKER_PACKAGE"
    docker compose version >/dev/null 2>&1 || compose_package
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
    local docker=() web=()
    # compose_package refuses an unsupported distribution even when the
    # machine's Docker needs nothing from the archive.
    compose_package >/dev/null
    mapfile -t docker < <(docker_packages)
    mapfile -t web < <(web_server_packages)

    log "Installing the operating system packages"
    run env DEBIAN_FRONTEND=noninteractive apt-get update
    apt_install "${BASE_PACKAGES[@]}" "${docker[@]}" "${web[@]}"

    if needs_node; then
        log "Installing Node ${NODE_MAJOR} from NodeSource"
        run bash -c "$NODESOURCE_SETUP"
        apt_install nodejs
        if ! is_dry_run && needs_node; then
            die "the packages step installed $(node -v 2>/dev/null || printf 'no Node'), not Node ${NODE_MAJOR}; check the NodeSource repository"
        fi
    fi

    if [[ ! -x "$UV_BIN" ]]; then
        log "Installing uv into $(dirname "$UV_BIN")"
        run env UV_INSTALL_DIR="$(dirname "$UV_BIN")" UV_NO_MODIFY_PATH=1 bash -c "$UV_INSTALL"
        if ! is_dry_run && [[ ! -x "$UV_BIN" ]]; then
            die "the packages step did not install $UV_BIN; check the uv installer's output above"
        fi
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
