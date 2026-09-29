#!/usr/bin/env bash
#
# CalDART - load the seed data on the server, one seed at a time.
#
# Runs the seed commands named by the flags through deploy/manage.sh, in the
# order an install runs them: the role groups (--roles), the membership plans
# (--plans), the demo accounts (--demo), and the example website (--content).
# --all runs all four.  Every seed is idempotent: running one again updates the
# rows it made rather than duplicating them.  That also means a second run puts
# back what it seeds: --plans resets a plan's price and description, --content
# overwrites and republishes the example pages (pages made in the CMS are left
# alone), and --demo resets the demo accounts' names, roles, and password.  The
# site keeps running throughout.
#
# The demo accounts share the password README.rst documents, and their renewal
# mandates need the mock payment provider, which production leaves off: a
# server seeded with them is a demonstration server, never one holding real
# member data.
#
# Usage:
#   sudo deploy/seed.sh [--roles] [--plans] [--demo] [--content] [--all] [--dry-run]
#
# Options:
#   --roles     create the role groups (seed_roles)
#   --plans     create or update the membership plans (seed_plans)
#   --demo      load the demo accounts, members, and payments (seed_demo)
#   --content   load the example website, its photograph included (seed_content)
#   --all       all four
#   --dry-run   print every state-changing command instead of running it
#   --help      show this help
#
# Examples:
#   sudo deploy/seed.sh --content          # the example website alone
#   sudo deploy/seed.sh --demo --content   # a demonstration server

set -euo pipefail

CHECKOUT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=deploy/lib.sh
source "$CHECKOUT/deploy/lib.sh"

readonly MANAGE="$CHECKOUT/deploy/manage.sh"
# Every seed, in the order it runs: a later one may use the rows of an earlier one.
readonly SEEDS=(roles plans demo content)

declare -A CHOSEN=()

parse_flags() {
    local seed
    while (($#)); do
        case "$1" in
            --roles | --plans | --demo | --content) CHOSEN[${1#--}]=yes ;;
            --all)
                for seed in "${SEEDS[@]}"; do
                    CHOSEN[$seed]=yes
                done
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
    ((${#CHOSEN[@]})) || usage_error "name at least one seed: --roles, --plans, --demo, --content, or --all"
}

# The management command and the stage line for the seed $1.
seed_command() {
    case "$1" in
        roles) printf 'seed_roles\tCreating the role groups\n' ;;
        plans) printf 'seed_plans\tCreating the membership plans\n' ;;
        demo) printf 'seed_demo\tLoading the demo accounts\n' ;;
        content) printf 'seed_content\tLoading the example website\n' ;;
    esac
}

main() {
    parse_flags "$@"
    require_root
    local seed command stage
    for seed in "${SEEDS[@]}"; do
        [[ "${CHOSEN[$seed]:-}" == yes ]] || continue
        IFS=$'\t' read -r command stage < <(seed_command "$seed")
        log "$stage"
        "$MANAGE" "$command"
    done
    if [[ "${CHOSEN[demo]:-}" == yes ]]; then
        note "caution: the demo accounts share the password README.rst documents;" \
            "this is now a demonstration server"
    fi
    log "Seeded"
}

main "$@"
