---
name: doc-user-guide
description: Format, layout, and completeness rules for the CalDART user guide under docs/user/, covering per-role chapters, screens and workflows, and the operator command reference. Use when writing, editing, or reviewing the user guide.
---

# User Guide

The user guide is the manual for people who **use** CalDART without reading its source:
members, DART leaders, and the user, account, website, and system administrators. Build on
`doc_python` (Sphinx, cross-references, prose, build discipline). Write for someone
comfortable with a web browser but unfamiliar with the system's internals; never require the
reader to read source code to accomplish a documented task.

## 1. File Layout

- Live under `docs/user/` as reStructuredText, keeping the user manual self-contained and
  parallel to the developer guide in `docs/developer/`.
- A single landing page (`docs/user/index.rst`) holds a 1-2 sentence introduction and the
  `toctree` directives listing the chapters, captioned by audience (for members, for leaders
  and administrators, reference). It contains no other prose.
- `getting-started.rst` comes first. After it, one chapter per role (`member-guide.rst`,
  `dart-leader-guide.rst`, `user-administrator.rst`, `account-administrator-guide.rst`,
  `website-administrator-guide.rst`, `system-administrator-guide.rst`), plus task chapters
  shared across roles (`payments.rst`, `aircraft.rst`). Roles are additive (an account
  administrator who is also a DART leader reads both guides), so each role chapter covers what
  that role adds rather than repeating the member guide.
- Name files in lowercase with hyphens.
- Put reference material that would clutter the main chapters (the FAQ, lookup tables) on its
  own page under the reference caption.
- The landing page is reachable from the documentation root `toctree` (`docs/index.rst` lists
  `user/index`).
- Because the chapters live in a subdirectory, references to pages OUTSIDE it (the demo
  walkthrough, the developer guide) must use absolute `:doc:` targets (a leading `/`, e.g.
  `` :doc:`/developer/backup-restore` ``); references among the user-guide chapters themselves
  stay relative.

## 2. Required Content

The guide as a whole MUST cover:

- **Introduction / purpose** — what CalDART is for and the value it delivers to each kind of
  user, stated before any mechanics.
- **Overview** — the high-level workflow: joining and paying, the membership term and its
  renewal reminders, the profile and aircraft a DART leader checks before a flight, and what
  each administrator looks after. A diagram helps when the flow has more than two stages.
- **Getting started** — creating an account, signing in, forgotten and changed passwords,
  sign-in throttling, and how roles decide what the reader sees. End users install nothing;
  installing the server belongs to the developer guide (`docs/developer/deployment.rst`).
- **Configuration** — what administrators can change from the browser (Wagtail site
  settings, roles on the users screen, the backup and reminder actions on the system screen)
  and the defaults. For server-side settings, point to `docs/developer/configuration.rst`
  rather than repeating them.
- **Screens and workflows** — for each role, the common tasks as numbered steps naming the
  screen and the control, with the expected result (what the reader sees, which email
  arrives, which file downloads).
- **Reference for every operator command** — see Section 3.
- **Examples** — realistic end-to-end examples for the common workflows. The demo walkthrough
  (`docs/demo-walkthrough.rst`) drives the five flows in `PLAN.rst` §1 on seeded demo data;
  link to it rather than duplicating it.

## 3. Documenting Operator Commands

The command-line programs a user runs are the management commands and make targets a system
administrator uses on the server: `health`, `db_backup`, `db_restore`, `db_reset`, and
`send_renewal_reminders`, and the `make backup`, `make restore`, and `make reminders` wrappers.
The system administrator guide lists the jobs that need the server and links to the developer
pages that document each one in full (`backup-restore.rst`, `reminders.rst`,
`deployment.rst`); `docs/developer/setup.rst` holds the complete tables of make targets and
management commands.

For EACH command documented:

- State its name, one-line purpose, and the basic invocation syntax in a code block (e.g.
  `manage.py db_restore FILE [--yes]`, `make restore FILE=... [YES=1]`).
- Document EVERY option: the exact flag and its argument placeholder, what it does, its
  default, and any environment-variable or make-variable equivalent it corresponds to (e.g.
  `BACKUP_DIR`, `TODAY=`, `DRY_RUN=`).
- Note positional vs. optional arguments, and mark the destructive commands (`db_restore`,
  `db_reset`) and how each asks for confirmation.
- Show at least one complete, runnable example invocation.
- When a command consumes or emits a structured file (a backup dump, `health --json`
  output), document that file's format in the chapter that owns the command.
- Keep option lists and defaults in exact agreement with the command's `add_arguments` and the
  Makefile. When the code changes, update the documentation in the same change.

## 4. Style

- Lead each chapter with purpose and context, then mechanics; explain *why* before *how*.
- Name every screen, menu entry, and button exactly as the portal or the Wagtail admin shows
  it. Provide a code block for every command shown; never make the reader reconstruct an
  invocation from prose.
- Cross-reference other chapters and the developer guide per `doc_python`
  (Cross-Reference Completeness) rather than duplicating their content.
- State expected results: what the user should see, which email arrives (Mailpit catches
  every email in development), and what file downloads and what it contains.
- Keep roles, permissions, and screen contents in exact agreement with the permission matrix
  (`PLAN.rst` §5) and the portal navigation (`frontend/src/portal/nav.ts`). When the code
  changes, update the guide in the same change.
- For step-by-step task walkthroughs that warrant their own article, follow the `doc-how-to`
  skill and link to it from the relevant chapter.
