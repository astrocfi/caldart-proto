---
name: pull-request
description: PR structure, purpose, implementation details, testing evidence, and review checklist for the CalDART app. Use when writing a pull request title or description, opening a PR, or reviewing a pull request.
---

# Pull Request Standards

## Scope of review

Treat the PR as a **single unit of change**. The diff to review is the set of all commits on the current branch back to its **immediate root** (the merge-base with the target branch). Consider the net result of those commits together; do **not** comment on differences that exist only between commits within the PR (e.g. "you fixed X in a later commit" or "commit 2 undid part of commit 1"). Review the final state of the branch against the base. Do not explicitly word wrap lines; allow GitHub to flow them automatically.

## Principles

1. **Descriptive title** — Summarize the change in an imperative sentence (e.g., "Add caching to profile lookup").
2. **Purpose first** — Explain *why* the change is needed before *how* it was done.
3. **Scope** — One logical change per PR. Split unrelated changes into separate PRs.
4. **Testing evidence** — Document automated and manual testing performed.
5. **Impact assessment** — Note potential effects on the API contract, migrations, settings and environment variables, permissions, payments, performance, or deployment (Potential Impacts section).
6. **Linked issues** — Reference related GitHub issues using `Closes #NNN` syntax. Each issue must be listed separately like `Closes #NNN. Closes #MMM.`.

## Opening a PR

- Branch from a fresh `origin/main` and follow the `git-workflow` skill for commits.
- Before opening, `make lint test check docs audit` must all be green (see the `run-all-checks` skill), plus `make e2e` when the change touches the end-to-end flows.
- Open with `gh pr create --base main`. The description states what changed, why, and how it was tested (`CLAUDE.md`).

## Template

The PR template is in `.github/pull_request_template.md`. GitHub applies it automatically to PRs opened in the web UI; when opening with `gh pr create --base main --body-file <file>`, write the same sections into the body file. Fill out every section:

- **Purpose** — Why the change is needed; link issue with `Closes #NNN. Closes #MMM.`.
- **Changes / Implementation Details** — What changed and how it was implemented; technical approaches chosen and non-obvious design decisions.
- **Type of Change** — Tick every box that applies; flag breaking changes to the API contract.
- **Testing** — Describe tests changed and new tests added along with test results, and any manual verification (the demo account used and the pages visited).
- **Potential Impacts** — API contract, migrations, settings and environment variables, permissions, payment providers, performance, deployment; write "None" if straightforward.
- **Checklist** — Tick each item that holds; explain any unticked item in Notes.
- **Notes** — Optional; delete only if not needed (tricky areas, follow-up work).

## Guidance

- **Application-specific** — Call out in Potential Impacts:
    - API contract changes, with the matching updates to `src/portal/api/types.ts` and the `docs/developer/api-*.rst` pages.
    - New or regenerated migrations (per `CLAUDE.md`, regenerate rather than stack fix-ups).
    - New or changed settings and environment variables, added to `.env.example`.
    - Permission changes against the permission matrix in `docs/developer/api-reference.rst`.
    - Any change to a shared file (`CLAUDE.md`, "File ownership on parallel branches"), kept additive.
- **Spec** — The docs are the specification: if the change alters documented behavior, update the docs in the same PR (`CLAUDE.md`).
- **Required reviewers** — Tag maintainers for changes to the shared surfaces listed in `CLAUDE.md`.
- **Brevity vs. completeness** — Short enough that authors fill everything out; detailed enough for a reviewer with no other context. If understanding the context for the change requires substantial knowledge, include a discussion of the motivation for the change and its details that is suitable for a reviewer with limited knowledge of the codebase and the concepts being discussed.
