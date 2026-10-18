---
description: Standards for the Sphinx documentation set, prose conventions, cross-references, and the docs build.
---

# Documentation Foundation

This rule defines the documentation system, prose conventions, cross-reference rules, and
Sphinx build requirements for all documentation in this repository. Docstring rules live in
`python` (Section 5).

## 1. Documentation System

- Use **Sphinx** for all project documentation. Keep all documentation source under the single
  `docs/` directory with one `conf.py`: end-user guides in `docs/user/`, contributor and
  operator guides in `docs/developer/`. Build outputs (`docs/_build/`) are never committed.
- Author pages in **reStructuredText** (`.rst`). `README.rst` is reStructuredText
  too.
- The docs stand alone and are the specification. Never cite a plan from `plans/`
  in the docs, docstrings or comments; state what the reader needs, or link the
  docs page that covers it.
- After ANY code or documentation change, rebuild the full tree and fix every warning and error
  before delivering (see Section 5).
- The site serves `docs/user/` alone, at `/docs/`, to signed-in users, except the pages a
  person needs before signing in (sign-in, forgot password, reset password, join, verify
  email, and two-factor sign-in), which carry `:signed-out: yes` and are public. `make
  guide` builds that copy from the same `conf.py` (the `guide` tag, the `dirhtml` builder),
  and `make docs` runs it first. A user page links only to other user pages, with a relative
  `:doc:` target: a reference into `docs/developer/`, `demo-walkthrough.rst`, or `index.rst`
  is not resolvable in that build and fails it, and `backend/tests/test_docs_user.py` fails
  on it first.

## 2. Prose Conventions

- One space between a sentence-ending period and the next sentence.
- American spelling, not British (e.g. `color`, not `colour`). <!-- codespell:ignore colour -->
  `make lint` enforces this with `make lint-spelling`, which runs codespell over
  `README.rst`, `CLAUDE.md`, `docs/`, `backend/`, `frontend/src/`, `frontend/e2e/`,
  `frontend/scripts/`, `scripts/`, `.github/`, `deploy/` and `.claude/` with the
  `clear`, `rare` and `en-GB_to_en-US`
  dictionaries, plus the project dictionary `.codespell-dictionary.txt` at the repository
  root for British words those built-in dictionaries miss (e.g. `aeroplane->airplane`,
  `cheque->check`). To flag another such word, add a `word->correction` line to that file
  rather than widening `ignore-words-list` (which only silences a word, never corrects
  it). `plans/` is not checked: the archived plans are frozen, and a live plan
  may quote the very words a fix replaces. Nor is `.claude/worktrees/`, which holds
  nested checkouts with their own build output and their own copy of `plans/`. The
  configuration lives in `[tool.codespell]` in `pyproject.toml`, and ignores exactly two
  words repository-wide: `nnumber` (the `nNumber` identifier) and `unparseable` (a valid
  American spelling the `rare` dictionary flags). To keep any other flagged word on one
  line, such as the example above or an identifier a library imposes, end the line with a
  `codespell:ignore <word>` comment, or precede it with a
  `codespell:ignore-next-line <word>` comment where the formatter will not leave a
  trailing one. Do not widen `ignore-words-list`: an entry there silences the word
  everywhere.
- Put a negation on the verb, never on its object, its complement, or the object of a
  preposition. Write "doesn't have a portal account", "didn't take anything", "doesn't
  charge anyone", "there isn't a payment", "isn't any help", or "without a term" (or
  "who doesn't have a term"), or a plain finding such as "No payment found", in place of
  these:
  "has no portal account", "took nothing", "charges nobody", <!-- wording:ignore -->
  "there is no payment", "is no help", "with no term", "for no reason". <!-- wording:ignore -->
  A negative subject is fine ("Nobody changes their own roles", "Nothing is due", "so no
  email was sent"), and so are the idioms "no longer", "no matter", and "no later than".
  This holds for UI labels, messages, emails, docs, docstrings, comments, and test names
  alike. `make lint` enforces it with `make lint-wording`, which runs
  `scripts/check_wording.py` over the tree codespell scans (minus generated files, lock
  files, and binaries): it flags a verb from `FLAGGED_VERBS`, a form of "be" or a
  preposition from `FLAGGED_WORDS`, a contraction of "be" or "have" ("there's",
  "we're", "you've", "they'd"), or an unlisted `-ed` word, followed by `no`, `nothing`,
  `nobody`, `none`, `no one`, or `nobody's` or `no one's` as a determiner, with at most
  one pronoun or adverb between them, and prints a suggested rewrite where the word is
  simple. A quote that opens or closes a string literal never joins the word beside it,
  so a test name or a message is checked to its first and last word; the join between
  two string literals (a closing quote, an optional `+` and line break, and an opening
  quote) reads as a space, so a split message is read whole; and bold or italic markup
  (`**`, `*`, `<b>`, `<strong>`, `<em>`, `<i>`) reads as part of the space. An inline
  literal stays a value. The word lists live in `scripts/wording_words.py`. Its
  `ALLOWED_WORDS` records the words deliberately left alone, in four groups: the
  modals; the conjunctions, relative words, and adverbs, after which a negative is a
  subject; "than", which compares with zero; and the pronouns and articles, which aren't
  verbs. The check doesn't catch everything. Its known gaps are a noun between the verb
  and the negative; a coordinated object after "and", "or", or "but" (a negative object
  in "gets 400 and ..."), which the rule covers but the check can't tell from a new
  negative subject, so `--coordinated` lists those candidates for review by hand; text
  inside a literal or code-block body, which a marker can't reach; "nobody's" before an
  `-ing`, `-ed`, or base-form participle, which is read from the next word alone; a
  contracted "'s" or "'d", read as "is" or "had", so a possessive before a negative is
  flagged; and a literal join through a typographic quote or a backtick. To keep text
  that must stay verbatim, such as a third party's error message, a test that pins one,
  or a bold UI label that starts with a negative, end the line with a `wording:ignore`
  comment, or precede it with a `wording:ignore-next-line` comment; in
  reStructuredText, a comment line holding only `.. wording:ignore-next-line`, followed
  by a blank line, covers the whole next paragraph. The check fails on any hit and
  prints each one with its suggestion; `--path <dir>` limits it, or `--coordinated`, to
  a subtree.
- Write the way people talk: never hang a negative clause off a noun. A noun followed by
  a clause whose subject is "no X", "nobody", "nothing", "none", or "no one" reads as a
  puzzle, and nobody says it aloud, with or without a "that" or a "which" between them:
  "refuse a day no statement can have carried yet", "an id no row has", "a caller <!-- wording:ignore -->
  nobody has signed in", "a draft nobody has touched", "a DART nobody is on", <!-- wording:ignore -->
  "a corporate name that nobody uses", "Operational email, which nobody may turn off". <!-- wording:ignore -->
  Say it plainly, preferring an adjective or a plain statement of what the code does,
  read from the code itself: "refuse a future date" (the check is `is_in_the_future`),
  "an unknown id", "a signed-out caller", "an untouched draft", "an empty DART", "a
  corporate name not used by anybody", "Operational email, which can't be turned off".
  When the sentence is still hard to follow, use simpler sentence construction: break it
  into short sentences, each saying one thing ("when that document hasn't been checked
  yet"). A positive relative clause is fine when no plain word fits ("an id that doesn't
  match a row"), and a negative subject that starts a clause of its own is fine too ("On
  any failure nothing is written", "the filters stay when nothing matches", "That way
  nothing is lost", "the note that nothing listens on port 25"). Never trade one awkward
  construction for another: a rewrite that keeps a negative puts it on the verb.
- After a verb of telling (tell, warn, show, remind, assure, promise, inform, notify)
  and its object, put "that" before a negative subject: "The banner tells the member
  that nothing is due", "Tell them that nobody can sign in", in place of <!-- wording:ignore -->
  "tells the member nothing is due" or "Tell them nobody can sign in". <!-- wording:ignore -->
- `make lint-wording` flags both. It flags a determiner, at most one adjective, and a
  noun, or a bare plural or an indefinite pronoun ("everything"), followed by a negative
  subject and its verb, with the suggestion "rewrite as an adjective or 'that doesn't
  ...'"; a noun followed by "that", "which", "who", or "whom" (or a preposition and
  "which" or "whom"), or a comma followed by "which", "who", or "whom", then a negative
  subject and its verb, with the suggestion "say it plainly ('not used by anybody') or in
  short sentences"; and a verb of telling, its object (a pronoun, or a noun after a
  determiner and at most one adjective), and a negative subject and its verb, with the
  suggestion to add "that". It passes over "no longer" and "no matter"; a negative after
  a comma, a colon, a semicolon, or a conjunction; a noun phrase led by a preposition
  that opens its sentence, paragraph, list item, or clause; a noun that says when, how,
  or why ("That way", "Every time", "The day") after any determiner but "a" or "an"; a
  noun that states the content of a "that" clause ("the note that ..."); and a quoted
  label or a value. Its known gaps, which `docs/developer/testing.rst` lists too, are a
  relative clause inside a sentence-opening lead-in ("For a type" followed by a negative
  subject); a noun with two adjectives or a possessive; a "nobody's" subject; a bare
  noun that is also a verb form before "that" ("limits" followed by "that nobody
  recorded"), or a bracket between the noun and "that"; and a verb of telling whose
  object is a name or has two adjectives. Read those by hand.
- Define each CalDART-specific term on first use, such as DART. Don't define
  standard aviation terms (N-number, BasicMed, medical classes, flight review):
  the readers are pilots and DART volunteers.
- Describe the **current** state of the software only. Never anchor prose to a
  moment in time or to migration history: avoid "new", "legacy", "old",
  "now", "recently", "as before", "backwards compatible", and similar framing.
- Do not use unicode smart quotes, em-dashes, or arrows inside `.py` files
  (they are acceptable in `.rst` and `.md`).

## 3. Sphinx Configuration (`conf.py`)

- `docs/conf.py` is deliberately minimal: Sphinx and the `furo` theme, the local
  `guide_roles` extension in `docs/_ext/` (pure Python; it reads each user page's `:roles:`
  field and writes `roles.json`), plus
  `sphinx.ext.graphviz` only when Graphviz's `dot` is installed. Add an extension only when a
  page needs it, and only one that builds on a machine without extra system packages, since
  `-W` turns a missing-tool warning into a failed build.
- Nothing is generated from docstrings (no `autodoc`). The API reference
  (`docs/developer/api-*.rst`) is written by hand.
- Use `nitpick_ignore` / `nitpick_ignore_regex` ONLY for targets that genuinely cannot resolve.
  Every entry MUST carry a comment explaining why. Never silence a nitpick warning for a target
  you own.

## 4. Cross-Reference Completeness

- Link other documentation pages with `:doc:` and labeled sections with `:ref:`. Never refer to
  another page by bare title or file path in prose.
- Python roles (`:class:`, `:func:`, `:mod:`, ...) cannot resolve in these docs because no API
  is generated from the code. Put code symbols, endpoints, file paths, settings, environment
  variables, and shell snippets in inline literals (` `` `` `).
- Cross-references are NOT required (and should be omitted) inside `.. code-block::`
  directives, `::` literal blocks, diagram blocks, and section titles.
- When a page, label, endpoint, or setting is added, removed, or renamed, every reference to it
  across the whole docs tree MUST be updated in the same change. A rename without reference
  updates is a documentation regression.

## 5. Build Discipline (warnings as errors AND nitpicky)

Documentation is correct only when it builds clean under BOTH gates, which `make docs` (and
therefore CI) applies together:

```bash
make docs    # sphinx-build -n -W -b html docs docs/_build/html
```

- `-W` promotes every warning (undefined label, duplicate target, malformed
  directive, broken toctree) to an error.
- `-n` (nitpicky) flags every cross-reference that does not resolve to a known
  target — the primary defense against the stale references in Section 4.
- The build MUST succeed with ZERO warnings before delivering. A doc change that breaks the
  build is not done.
- Diagrams: `docs/developer/data-model.rst` draws its diagram inside `.. only:: graphviz` with
  an ASCII equivalent inside `.. only:: not graphviz`. Change both together, and validate
  complex diagrams in their authoring tool before committing.

## 6. Change Discipline

- Any code change MUST update the affected docstrings, documentation pages, and the `README`
  in the same change.
- A new or changed API endpoint MUST update its `docs/developer/api-*.rst` page in the same
  change; a new user-facing feature needs its page under `docs/user/`.
- NEVER leave stale or contradictory documentation. If a feature is removed,
  remove its documentation; if it is renamed, rename every reference.
