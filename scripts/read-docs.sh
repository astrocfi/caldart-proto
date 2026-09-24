#!/usr/bin/env bash
#
# CalDART - build the Sphinx documentation and open it in a browser.
#
# Builds through `make docs`, which is the one place the Sphinx invocation
# lives: nitpicky (-n) with warnings as errors (-W), the same gate CI applies.
# Then opens docs/_build/html/index.html with the platform's default handler.
#
# Usage:
#   ./scripts/read-docs.sh           build, then open
#   ./scripts/read-docs.sh --open    open what is already built, without building
#   ./scripts/read-docs.sh --build   build without opening
#
# Environment:
#   MAKE     the make to build with (default: make)
#   BROWSER  a command to open the page with, instead of the platform default

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
HTML_INDEX="$PROJECT_ROOT/docs/_build/html/index.html"
MAKE="${MAKE:-make}"

should_build=yes
should_open=yes

case "${1:-}" in
    --open) should_build=no ;;
    --build) should_open=no ;;
    "") ;;
    *)
        echo "Usage: $0 [--open | --build]" >&2
        exit 2
        ;;
esac

open_html() {
    local path=$1

    if [ -n "${BROWSER:-}" ]; then
        "$BROWSER" "$path"
        return
    fi

    case "$(uname -s)" in
        Linux)
            # A headless shell has no handler to hand the page to; say where it
            # is rather than failing on a missing xdg-open or a missing DISPLAY.
            if [ -z "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ] || ! command -v xdg-open >/dev/null 2>&1; then
                echo "No browser to open here.  The documentation is at:"
                echo "  file://$path"
                return
            fi
            xdg-open "$path"
            ;;
        Darwin)
            open "$path"
            ;;
        CYGWIN* | MINGW* | MSYS*)
            if command -v cygpath >/dev/null 2>&1; then
                MSYS_NO_PATHCONV=1 cmd.exe //C start "" "$(cygpath -w "$path")"
            else
                cmd.exe //C start "" "$path"
            fi
            ;;
        *)
            echo "Unsupported platform $(uname -s).  The documentation is at:"
            echo "  file://$path"
            ;;
    esac
}

cd "$PROJECT_ROOT"

if [ "$should_build" = yes ]; then
    echo "Building the documentation (nitpicky, warnings are errors)..."
    "$MAKE" docs
fi

if [ ! -f "$HTML_INDEX" ]; then
    echo "Error: no built documentation at $HTML_INDEX" >&2
    echo "Run '$0' without --open to build it first." >&2
    exit 1
fi

if [ "$should_open" = yes ]; then
    open_html "$HTML_INDEX"
fi
