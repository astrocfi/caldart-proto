---
name: doc-user-guide
description: Format, layout, and completeness rules for the CalDART user guide under docs/user/, covering one page per screen, the groups that hold them, and the Help button that opens each one. Use when writing, editing, or reviewing the user guide.
---

# User Guide

The user guide is the manual for people who **use** CalDART without reading its source:
members, friends, DART leaders, and the account, treasurer, website, and system
administrators. Build on `doc_python` (Sphinx, cross-references, prose, build discipline).
Write for a pilot or DART volunteer who is comfortable with a web browser but is not a
computer expert; never require the reader to read source code, a shell, or a file to
accomplish a documented task.

## 1. File Layout

- Live under `docs/user/` as reStructuredText, one page per screen of the portal or one view
  of the public site, grouped by who uses the screen.
- Root pages, directly under `docs/user/`: `index` (what CalDART's site is, how the guide is
  arranged, that every screen has a **Help** button, and the toctree), `quick-start` (the
  first things most people do, each as a short numbered walk naming the exact buttons),
  `overview` (the public site and the portal, the three kinds of person the site knows, what
  membership means, and the roles in one paragraph each), `roles` (what each role can see and
  do, naming every screen it reaches in bold, each linked to its page), and `faq` (short
  answers, each linking to the page that covers it in full).
- Four screen groups, each its own directory with an `index.rst` (a title, one or two
  sentences, and a toctree, and no other prose):
    - `member/` — the screens every signed-in person has, and the public site as a visitor
      sees it.
    - `admin/` — a DART leader, a user administrator, an account administrator, and a system
      administrator.
    - `finance/` — the treasurer's screens.
    - `website/` — the website administrator's editing screens, which open from the public
      site's own Wagtail admin rather than the member portal.
- A page's slug is its path under `docs/user/` without the extension (`member/profile`,
  `admin/system`). The slug is binding: it is the **Help** button's target
  (`frontend/src/portal/help.ts`'s `HELP_PAGES`) and the `:doc:` target every other page uses
  to reach it. Adding, renaming, or removing a page updates `HELP_PAGES`, the group's toctree,
  and every `:doc:` reference to it, in the same change.
- Name files and directories in lowercase with hyphens.
- Roles are additive (an account administrator who is also a DART leader reaches both sets of
  screens), so a page never repeats what another role's screen already covers; it links to it
  instead (Section 4).

## 2. What Each Page Covers

A screen's page is self-contained: a reader who lands on it from the **Help** button, with no
other context, can act on it.

- Open with what the screen is for, in one or two sentences.
- Then, in order: what you see, what you can do, and what happens next (which screen it leads
  to, which email arrives and its subject line, what downloads and what it contains).
- Close with one paragraph headed "If something looks wrong" that covers the screen's common
  failure or confusion, and where to go next.
- No page runs longer than 250 lines; split a screen with several tabs or states into more
  than one page, or move detail the reader rarely needs to the FAQ, before a page grows past
  that.
- Every email a person can receive is described on the page for the screen that causes it, by
  its exact subject line.

## 3. Voice and Style

- Second person, present tense, short sentences.
- A screen name, button, menu entry, or field label appears in **bold**, copied from the
  running code, never from memory. A message the software shows appears in *italics*, copied
  the same way.
- Name a role in words (a DART leader, the treasurer, a user administrator), never by its code
  (`dart_leader`).
- Nothing in the user guide names a shell command, an environment variable, a file path, an
  HTTP status code, JSON, an API path, or a code identifier. A system administrator who needs
  those reads the developer guide, which the user guide never names or links; the one address
  the guide may print is the site's own.
- These words do not appear, in any case: honest, honestly, load-bearing, load bearing,
  surface, surfaces, surfaced, gate, gates, gated, gating, robust, seamless, leverage, delve,
  crucial.
- Avoid the contrast construction "X, not Y", "X — not Y", and "X rather than Y": state what
  is true in its own sentence. The one exception is a message or a label the software shows
  verbatim, set in italics or bold, which may contain the words the sentence around it avoids.
- Serial commas. Sentences end and new ones begin instead of an em dash; an em dash appears at
  most twice on a page, and `--` never appears at all. No prose line begins with a comma (an
  underline made entirely of `-` or `~`, and a `.. code-block::` body, are not prose).
- Standard aviation terms (N-number, BasicMed, medical classes, flight review) are not
  explained; the readers are pilots and DART volunteers. CalDART's own terms (DART, friend,
  roster) are explained in half a sentence where they first appear on a page.
- American spelling and one space after a sentence-ending period, as in `doc_python`.

## 4. Cross-References and Duplication

- A fact lives on one page; every other page links to it rather than repeating it. Link with a
  relative `:doc:` target: from within a group, name the sibling page (`:doc:`profile``) or
  reach another group with its slug (`:doc:`admin/members``); from a root page, always use the
  slug.
- `roles.rst` is the map: every screen a role reaches is named in bold there, each linked to
  its page, so a reader can find a screen from the role that opens it as well as from its
  group's index.
- `faq.rst` answers link to the page that covers the question in full; a question about a
  screen outside the guide's own group of the asker (a member's question about an
  administrator's screen, say) links to that group's index rather than guessing which of its
  pages answers it best.
- `quick-start.rst` links to every page whose screen it walks through, once the walk reaches
  that screen.
- A user page links only to another page under `docs/user/`: never to the developer guide,
  `docs/demo-walkthrough.rst`, or `docs/index.rst`, and never by bare title or file path.
  `backend/tests/test_docs_user.py` fails the build on a reference that leaves the guide or a
  page that names "the developer guide," so Sphinx's build needs no special case for it either.

## 5. Keeping the Guide Complete

- Nothing a signed-in person or a visitor can do goes undocumented. When a screen, a button, a
  field, or an email changes, update the page that covers it in the same change.
- `frontend/src/portal/help.test.ts` checks that every route in `routes/index.tsx` has a
  `HELP_PAGES` entry and that every slug in `HELP_PAGES` is a file under `docs/user/`; keep the
  two in step whenever a screen's route or slug changes.
- `backend/tests/test_docs_user.py` (Section 4) and `make docs` (which builds the guide with
  `-n -W` before the full documentation tree) must stay green; see `doc_python` for the build
  discipline both share.
