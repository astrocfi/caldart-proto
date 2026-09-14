---
name: doc-how-to
description: Format and completeness rules for task-focused how-to articles that walk a CalDART user, operator, or contributor through a single workflow with prerequisites, steps, and troubleshooting. Use when writing, editing, or reviewing a how-to article.
---

# How-To Articles

A how-to article walks a reader through ONE concrete task from start to finish. It complements
the reference material covered by the `doc-user-guide` and `doc-dev-guide` skills: the guides
document every screen, setting, and option, while a how-to picks one goal and shows the
shortest correct path to it. The closest existing page is `docs/demo-walkthrough.rst`, which
drives five flows on seeded demo data. Build on `doc_python` (Prose Conventions, Build
Discipline). Where a how-to and a guide describe the same workflow, keep them consistent and
link between them rather than duplicating detail.

## 1. Audience and Tone

- Write for the person who does the task: a member or administrator working in the portal or
  the Wagtail admin, an operator with a shell on the server, or a contributor with a
  development checkout. Assume they are unfamiliar with the system's internals.
- Use clear, direct, action-oriented language. Define CalDART terms on first use (e.g. DART),
  but not standard aviation terms such as N-number, BasicMed or flight review: the readers
  are pilots.
- Focus on what the reader must do and what they should observe.

## 2. Placement

- Put a how-to beside the guide it serves — `docs/user/` for users, `docs/developer/` for
  operators and contributors — and add it to that directory's `index.rst` `toctree`. A page
  outside every `toctree` fails `make docs`.

## 3. Required Elements

1. **Action-oriented title** — name the task as an action (e.g. "How to renew a membership",
   "How to restore a backup", not "Backup overview").
2. **Brief introduction** — 1-3 sentences on the purpose and value of the task.
3. **Prerequisites** — the role the reader needs and what must already be true (signed in, a
   current membership, provider keys configured); for operator and contributor tasks, the
   environment (`make up`, a shell on the server, the environment variables involved).
4. **Numbered steps** — one action per step in logical order, each with the exact screen and
   control, or the exact command, and a note of what the reader should see after it.
5. **Expected results** — a summary of the successful end state (what the screen shows, which
   emails are sent, which files are created). Keep this consistent with the per-step
   observations.
6. **Troubleshooting** — the common failure modes (a missing role or a 403, an expired
   membership, a declined payment, an email that never arrived, a command run against the
   wrong `DATABASE_URL`) and their fixes.
7. **Related material** — next steps and links to the relevant guide chapters or other how-to
   articles.

## 4. Structure

```rst
======================
How to <do the action>
======================

<1-3 sentence introduction explaining purpose and value.>

Prerequisites
=============

- The ``<role>`` role, signed in to the portal.
- <Anything else that must already be true.>

Steps
=====

#. Choose **<Menu entry>** in the sidebar. You should see <result>.
#. <Action>:

   .. code-block:: console

      $ make <target>

#. <Action>. You should see <result>.

Expected results
================

<Summary of the successful end state.>

Troubleshooting
===============

<Problem>
   <Solution>.

Related material
================

- :doc:`<guide chapter>`
```

## 5. Converting Technical Content

When turning code, tests, or internal notes into a how-to:

1. Identify the user-facing feature or workflow.
2. Determine the target audience (member, administrator, operator, contributor).
3. Extract the user actions from the technical steps.
4. Translate internal terminology into user-facing language.
5. Add runnable commands or exact screen steps, expected results, and troubleshooting.

## 6. Diagrams and Figures

- **When to use**: multi-step workflows, data flows, or architecture that is clearer as a
  visual.
- **Placement**: inline, immediately after the relevant step or section.
- **Format**: prefer text-based diagrams — `.. graphviz::` inside `.. only:: graphviz`, with an
  ASCII equivalent in a literal block inside `.. only:: not graphviz`, as
  `docs/developer/data-model.rst` does, because `docs/conf.py` enables Graphviz only when `dot`
  is installed. Use PNG/SVG for screenshots.
- **Naming**: descriptive filenames (e.g. `checkout-flow.svg`), with alt text (`:alt:`) for
  accessibility.
