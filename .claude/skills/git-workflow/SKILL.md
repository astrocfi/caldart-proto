---
name: git-workflow
description: Conventional commits, required commit trailers, branching, and PR workflow for source control and code review. Use when writing a commit message, creating or naming a branch, or merging.
---

# Git Workflow

## 1. Commit Messages

Use the **Conventional Commits** format:

```
<type>[(<scope>)]: <imperative summary>   (50 chars max for subject)

[Optional body — wrap at 72 chars. Explain *what* and *why*, not *how*.]

[Optional footer — e.g., Closes #123, BREAKING CHANGE: description]
Co-Authored-By: ...
Claude-Session: ...
```

### Allowed types

| Type | When to use |
|------|-------------|
| `feat` | New user-facing feature or API endpoint. |
| `fix` | Bug fix. |
| `docs` | Documentation-only change. |
| `style` | Formatting, whitespace — no logic change. |
| `refactor` | Code restructure with no behavior change. |
| `perf` | Performance improvement. |
| `test` | Adding or updating tests only. |
| `build` | Build system or dependency change. |
| `ci` | CI/CD configuration change. |
| `chore` | Maintenance tasks that don't fit above. |

A scope, when used, names the Django app or frontend area touched (e.g. `feat(payments): ...`, `fix(portal): ...`).

### Rules

- Subject line MUST be imperative mood ("Add X", not "Added X" or "Adds X").
- Subject line MUST NOT exceed 50 characters.
- Do NOT end the subject line with a period.
- Separate subject from body with a blank line.
- Body lines MUST NOT exceed 72 characters.
- Reference related issues in the footer.
- Every commit message MUST end with the two trailer lines `CLAUDE.md` requires (`Co-Authored-By:` and `Claude-Session:`), after any other footer lines.
- Each commit MUST represent one logical change. Do NOT mix unrelated changes.

## 2. Branching Strategy

This project uses a simple two-tier branching model:

- **`main`** — Always deployable. Changes reach it only through a PR with passing CI.
- **`feature/<name>`** — New features or enhancements, branched from `main`.
- **`bugfix/<name>`** — Bug fixes, branched from `main`.

There are NO separate release, hotfix, or develop branches. All work merges back to `main` via pull request.

- ALWAYS branch from a fresh `origin/main` (`git fetch origin && git switch -c feature/<name> origin/main`).
- The branch name's slug also names the branch's database (`caldart_<branch-slug>`; see `CLAUDE.md`), so keep it short and filesystem-safe.

## 3. Pull Requests and Merging

- ALWAYS create a PR for merging into `main` (`gh pr create --base main`; see the `pull-request` skill); direct pushes are prohibited.
- PRs MUST pass all CI checks before merge: the make targets CI runs (`lint`, `test`, `check`, `docs`, `audit`, `e2e`; see the `run-all-checks` skill).
- Prefer **squash merge** to keep `main` history linear and readable.
- Delete the source branch after merge.
