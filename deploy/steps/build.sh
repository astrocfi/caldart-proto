#!/usr/bin/env bash
#
# CalDART install step 5 - the build.
#
# From the deploy root: installs the exact Python packages uv.lock pins into
# .venv (without the development tools, with the Sphinx toolchain), with any
# Python uv downloads put in /opt/uv/python where the service user can read it;
# builds the frontend into frontend/dist; and builds the user guide the site
# serves at /docs/ into docs/_build/guide.  The checkout stays root-owned and
# world-readable.
#
# Usage:
#   sudo deploy/steps/build.sh [--dry-run]
#
# Options:
#   --dry-run   print every state-changing command instead of running it
#   --help      show this help

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=deploy/lib.sh
source "$ROOT/deploy/lib.sh"

readonly UV_PYTHON_DIR=/opt/uv/python

build_step() {
    log "Installing the Python packages"
    run cd "$ROOT"
    run env UV_PYTHON_INSTALL_DIR="$UV_PYTHON_DIR" uv sync --frozen --no-dev --group docs

    log "Building the frontend"
    run cd "$ROOT/frontend"
    run npm ci
    run npm run build

    # The virtualenv's sphinx-build, not `uv run`: that would first sync the
    # default dependency groups, development tools included.
    log "Building the user guide"
    run cd "$ROOT"
    run .venv/bin/sphinx-build -n -W -b dirhtml -t guide -c docs docs/user docs/_build/guide
}

build_main() {
    parse_step_flags "${BASH_SOURCE[0]}" "$@"
    require_root
    build_step
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    build_main "$@"
fi
