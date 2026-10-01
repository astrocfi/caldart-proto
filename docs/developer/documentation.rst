=============
Documentation
=============

How the documentation under ``docs/`` is built, published, and kept in step
with the code: the two builds, the static assets they ship, the pages only some
roles may read, the rules every diagram follows, the voice of each guide, and
the tests that fail when a page and the code disagree.  The documentation is
the specification, so a change to the software and the change to its page land
in the same pull request.


Where the pages live
====================

::

  docs/
    conf.py              the one Sphinx configuration, for both builds
    _ext/                guide_roles.py, the one local Sphinx extension
    index.rst            the root of the whole tree
    demo-walkthrough.rst a tour of the seeded demo site
    _static/             hand-written CSS and JavaScript the builds ship
    user/                the user guide: the pages the site serves at /docs/
      index.rst          the beginning, and the root of the guide build
      member/ admin/ finance/ website/
                         one page per screen, one directory per group
    developer/           this guide; built by make docs, never published

The user guide is arranged as one page per screen of the software, in four
groups, each a directory with its own ``index.rst``: ``member/`` (the screens
every signed-in person has, and the public site as a visitor sees it),
``admin/`` (leaders and administrators), ``finance/`` (the treasurer), and
``website/`` (the website administrator in Wagtail).  A page's path under
``docs/user/`` without its ``.rst`` is its slug, and the slug is the address
the portal's **Help** button opens: ``HELP_PAGES`` in
``frontend/src/portal/help.ts`` maps each portal route to one, so
``docs/user/member/profile.rst`` is ``/docs/member/profile/``.  Renaming or
moving a user page therefore changes a Help target, and the entry in
``HELP_PAGES`` changes with it.

The developer guide is organized by subsystem, with the cross-cutting chapters
(architecture, setup, configuration, data model, the API reference) first.
Nothing in either guide is generated from docstrings: there is no ``autodoc``,
and the API reference is written by hand.


The two builds
==============

``docs/conf.py`` configures two builds, and ``make docs`` runs both, the guide
first:

``make guide``
   ``sphinx-build -n -W -b dirhtml -t guide -c docs docs/user
   docs/_build/guide``.  The source tree is ``docs/user`` alone, so nothing
   outside it is part of this build.  The ``guide`` tag tells ``conf.py``
   which build this is (it sets the HTML title to *CalDART user guide*), and
   the ``dirhtml`` builder gives every page a directory of its own, so an
   address reads ``/docs/member/profile/``.  This is what the site serves:
   the ``user_guide`` view streams these files at ``/docs/`` to anyone signed
   in, from ``USER_GUIDE_ROOT`` (:doc:`configuration`), holds back the pages
   the reader's roles do not reach (:ref:`documentation-role-gated-pages`),
   and sends a visitor to the portal's login page first.

``make docs``
   ``sphinx-build -n -W -b html docs docs/_build/html``: the whole tree,
   both guides and the demo walkthrough, for contributors to read locally.
   ``make read-docs`` builds it and opens it in a browser (:doc:`setup`).

Both run nitpicky (``-n``: every cross-reference must resolve) with warnings
as errors (``-W``), locally and in CI.  A page the guide build cannot resolve
fails it just as the whole-tree build would, so a user page links only to
other user pages, with a relative ``:doc:`` target (``profile``,
``../faq``) that resolves the same way in both builds.  ``docs/conf.py`` has
no special case for the guide build: a reference into ``docs/developer/``
from a user page is an unresolved reference there, and fails it.  The tests in
:ref:`documentation-tests` catch such a reference before the build does.

Graphviz is optional.  ``conf.py`` enables ``sphinx.ext.graphviz`` and adds
the ``graphviz`` build tag only when ``dot`` is on ``PATH``, since the
extension would otherwise warn, and a warning fails the build.  Every diagram
therefore sits inside ``.. only:: graphviz`` with a text fallback inside
``.. only:: not graphviz`` (:ref:`documentation-diagrams`).


Static assets and the figure toolbar
====================================

``docs/_static/`` holds the only custom assets, all hand-written and
dependency-free, and ``conf.py`` ships them through ``html_static_path``,
``html_css_files``, and ``html_js_files``: the figure toolbar's two files, in
both builds.  The path is
relative to ``conf.py``, so the guide build, whose source tree is
``docs/user``, finds the same directory.  There are no custom templates.

``figure-zoom.css``
   Puts every Graphviz diagram (``figure div.graphviz``) on a white panel
   with a hairline border, because Graphviz draws black on a transparent
   ground that would vanish in furo's dark mode.  A diagram keeps its drawn
   size, so text stays at the size it was drawn at, and a diagram wider than
   the page scrolls sideways inside its panel.  The toolbar and overlay take
   their other colors from furo's own variables, so they follow the reader's
   light or dark choice.

``figure-zoom.js``
   Loaded with ``defer``; once the page has loaded it finds every
   ``<figure>`` that holds a Graphviz ``object.graphviz`` or an ``img`` and
   appends a toolbar with two controls:

   - **Open full size**, a link to the SVG or image itself that opens in a
     new tab (``target="_blank" rel="noopener"``).
   - **Zoom**, a button that opens a full-window overlay showing the drawing
     at its natural size in a scrollable panel.  **Close**, or the Escape
     key, closes it and returns focus to the button that opened it.  While
     it is open, Tab and Shift+Tab move focus between **Close** and the
     panel only, so keyboard focus never lands on a control hidden behind
     the overlay.

   The overlay is built once per page and reused.  The script sets no inline
   handlers and loads from the site's own origin, so it runs under the
   guide's content security policy unchanged (:ref:`configuration-csp`).
   The ``user_guide`` view serves it as ``text/javascript``, the stylesheet
   as ``text/css``, and a diagram under ``_images/`` as ``image/svg+xml``,
   and ``backend/tests/test_user_guide.py`` checks all three.

No package supplies any of these files, and nothing is added to the ``docs``
dependency group or to ``frontend/package.json`` for them.  To change the
toolbar, edit the two files, run ``make docs``, and open a page with a
diagram, such as ``docs/_build/html/developer/deployment.html``.


.. _documentation-role-gated-pages:

Role-gated pages
================

The guide shows each reader the screens their roles reach, and nothing else:
a plain member's sidebar lists the pages under **Start here**, their own
screens, and **Reference**, and their search finds only those pages, while the
system administrator's lists and finds every page.  Five pieces do it, and the
server does all of the hiding: no script in the browser takes anything out.

**The field.**  A page only some roles may read opens with a ``:roles:``
field, before its title::

  :roles: account_admin, dart_leader

  =======
  Members
  =======

The slugs are the role slugs of ``apps/accounts/roles.py``, separated by
commas.  A reader holding any one of them may read the page, and a system
administrator may read every page.  A page without the field is every signed-in
reader's.  Sphinx reads a field list that comes before anything else as the
page's metadata (``env.metadata``), so the field never shows on the page.  The
roles follow the portal's menu (``frontend/src/portal/nav.ts``): each page
names the roles of the menu entry for its screen, so every page under
``admin/``, ``finance/``, and ``website/`` carries the field, and no page under
``member/`` and no top-level page does.  A group's ``index.rst`` carries none:
its roles are computed.

**The extension.**  ``docs/_ext/guide_roles.py`` is a local Sphinx extension,
pure Python, which ``conf.py`` puts on ``sys.path`` and in ``extensions`` for
both builds.  Once every page is read it checks each field and warns, against
the page, about a slug that is not a role or a field that names none, so
``-W`` fails the build on a misspelling.  It spells the role slugs itself,
since it cannot import the Django project, and a test holds its list equal to
``ROLE_SLUGS``.  A page with no field of its own that lists others in a
toctree takes the union of their roles, so ``admin/index`` is readable by
every role that reaches any administrator screen, and it is open to everyone
when any page it lists is.  As each page is read, the extension also gives
every table of contents the ``no-search`` class, which Sphinx's indexer skips:
otherwise the titles a table of contents lists would be indexed as words of
the page holding it, and the front page would match a word from a restricted
page's title.  Each page's words are indexed under that page alone.

**The JSON.**  At the end of a successful HTML build the extension writes
``roles.json`` into the output directory, beside the front page: each
restricted page's docname and its slugs, in role order, and nothing for an
open page.  It writes the file under a temporary name beside it and renames it
into place, so the site reading it during a rebuild finds the old file or the
new one, never half of one::

  {
    "admin/health-database": ["system_admin"],
    "admin/members": ["dart_leader", "account_admin"],
    ...
  }

**The view.**  ``caldart.views.user_guide`` reads ``roles.json`` from
``USER_GUIDE_ROOT``, cached until the file's modification time changes, so a
rebuilt guide takes effect on the next request.  A page the file restricts is
served only to a reader for whom ``User.has_any_role`` is true of its slugs;
anyone else is redirected to the guide's front page.  The page is named by the
file the request resolves to, so ``admin/members/``,
``admin/members/index.html``, and a path that reaches it through ``..`` are
judged alike.  The static assets and every page the file does not name are
served to every reader, and a guide built without ``roles.json`` serves every
file as built.  A ``roles.json`` that is not valid JSON is logged as an error
and serves every file as built too, rather than failing every request.

The view never serves a file that names the restricted pages and that no
reader needs: ``roles.json`` itself, Sphinx's ``objects.inv`` inventory, and
any path with a part that starts with a dot, such as the ``.doctrees``
directory the build leaves in its output (it holds every page's whole text)
and ``.buildinfo``, all answer 404.  The guide build sets ``html_copy_source``
off, so no page's reStructuredText is published under ``_sources/``.

**The trimming.**  Every page and ``searchindex.js`` reach a reader with the
pages they may not open taken out, by ``caldart/guide_search.py``:

- *A page.*  Every sidebar (``.sidebar-tree``) and table-of-contents
  (``.toctree-wrapper``) entry whose link leads to a hidden page goes, with
  everything nested under it; so does every next or previous link at the
  foot of the page (``.related-pages``) and every ``<link rel="next">`` or
  ``<link rel="prev">`` in its head, which carries the page's title.  Then
  every list left with no entries goes, with the caption before it, and a
  table of contents left with no list.  Any other link to a hidden page,
  such as a ``:doc:`` reference in a page's prose, loses its anchor and keeps
  its text, so no link leads the reader to a page they cannot open; the
  words stay, since a screen's name is no secret.  A link is resolved
  against the page's own address and judged by the same rule as a request,
  and a link that leaves the guide is left alone.  A page that loses
  nothing is served byte for byte as built.  The page is parsed with
  Beautiful Soup's ``html.parser``.
- *The search index.*  The hidden pages leave ``docnames``, ``filenames``,
  and ``titles``, and the pages left are numbered afresh in the order they
  had.  Each word in ``terms`` and ``titleterms`` keeps only the pages left,
  written as one number when one page is left, as Sphinx writes it, and goes
  when none is; each entry in ``alltitles``, ``indexentries``, and
  ``objects`` on a hidden page goes, and a name with no entry left goes with
  it.  Every other field passes through.  An index that is not the
  ``Search.setIndex(...)`` call Sphinx writes, in the shapes above, is
  logged as an error and answers 404, so a format change never sends every
  page's words to a member.  A member's search therefore finds nothing on a
  restricted page, and Sphinx's own results and count need no correction.

The view reads the reader's roles once per request, and only for a file it
gates or trims, so a stylesheet or an image costs no query beyond the
session's.  A reader's reach is the set of restricted docnames they may not
open.  Both
trims are cached in memory per file, modification time, and reach, so readers
with the same reach share one copy, and a rebuilt guide is trimmed afresh; a
system administrator, from whom nothing is hidden, is served every file as
built.  A page and the index carry an ``ETag`` made of the file's modification
time and a digest of the reach, beside the ``Last-Modified`` every file
carries, so a reader whose roles change is sent the file again instead of a
304 for the copy trimmed for their old roles.

To restrict a new page, give it the field and run ``make guide``; to change
who reads a screen, change its menu entry and its page's field together.


.. _documentation-diagrams:

Diagrams
========

Diagrams are Graphviz, written inline with ``.. graphviz::`` and rendered to
SVG (``graphviz_output_format``).  Every diagram follows these rules:

- **Both builds.**  The ``.. graphviz::`` directive sits inside
  ``.. only:: graphviz``, and ``.. only:: not graphviz`` beside it carries a
  text sketch, a numbered list, or prose with the same pieces and the same
  relationships.  Change the two together.
- **Readable at page width.**  No diagram renders wider than 1000 points,
  and no text in it is smaller than 11 points: set ``fontsize=11`` (or more)
  on the graph, its nodes, and its edges.  A left-to-right layout that comes
  out wider than that becomes ``rankdir=TB``, and one that is still too
  wide is split into two diagrams, each with its own caption.  A long edge
  label is wrapped onto two lines with ``\l``.
- **A caption and alt text.**  The ``:caption:`` says what the diagram shows
  and what each arrow and box style means; the ``:alt:`` describes it in one
  sentence for a screen reader.
- **No markup inside the diagram.**  Code names inside a ``digraph`` are
  plain text; the prose around the figure puts them in literals.
- **Transparent ground.**  Keep ``bgcolor="transparent"``; the panel from
  ``figure-zoom.css`` supplies the white.

To check a diagram's size, build and read the width Graphviz wrote into each
SVG::

  make docs
  grep -o 'svg width="[0-9.]*pt"' docs/_build/html/_images/*.svg

Or render one on its own while you work on it, from the ``digraph`` copied
into a file: ``dot -Tsvg topology.dot -o topology.svg`` and open the result.


The user guide's voice
======================

Every page under ``docs/user/`` is written for a pilot or a DART volunteer who
is not a computer expert.  In brief:

- Second person, present tense, short sentences.  A page opens with what the
  screen is for in a sentence or two, then covers what you see, what you can
  do, and what happens next, and ends with an *If something looks wrong*
  paragraph.  No page runs past 250 lines.
- Screen names, buttons, menu entries, and field labels are bold, exactly as
  the software shows them; messages the software shows are italic, exactly
  as shown.  Copy each string from the code, never from memory.
- Roles are named in words (a DART leader, the treasurer), never by their
  code.
- No shell commands, environment variables, file paths, HTTP status codes,
  JSON, API paths, or code identifiers.  The user guide never names or links
  the developer guide; the only address it prints is the site's own.
- A short list of words is banned (among them *honest*, *robust*,
  *seamless*, *leverage*, *crucial*, and the *gate* and *surface* families),
  as is the contrast construction "X, not Y" and "X rather than Y": each true
  thing gets its own sentence.  Serial commas, American spelling, at most two
  em dashes on a page, and never a double hyphen.
- Standard aviation terms go unexplained; CalDART's own terms (DART, friend,
  roster) are explained in half a sentence where they first appear on a page.
- Every email a person can receive is described, by its subject line, on the
  page for the screen that causes it.
- A fact lives on one page and other pages link to it.

These rules are the user guide's rules in full, and the tests in
:ref:`documentation-tests` hold the pages to them.


The developer guide's rules
===========================

The developer guide is written for a competent Python and TypeScript developer
who is new to this codebase, and for the operator who runs it.  It describes
the system as it is, in the present tense, and never cites a plan from
``plans/``.  Code symbols, endpoints, file paths, settings, environment
variables, and shell snippets go in inline literals, because Python roles
cannot resolve without ``autodoc``; other pages are linked with ``:doc:`` and
labeled sections with ``:ref:``.  A command a procedure quotes is one a reader
can run as written: ``uv run backend/manage.py …`` for management commands,
and a make target where one exists.  ``.claude/rules/doc_python.md`` and the
``doc-dev-guide`` skill carry the full rules.


.. _documentation-tests:

Tests that keep the docs in step
================================

A hand-written guide drifts silently, so the test suite checks both guides
against the code on every run.

``backend/tests/test_docs_developer.py`` checks that:

- every API route, walked from ``caldart.api_urls`` with Django's resolver
  and the methods its view allows, appears as ``METHOD /path`` on some
  ``docs/developer/api-*.rst`` page, with ``{id}``-style placeholders
  normalized;
- every concrete model in the apps, and every concrete field of it, appears
  in :doc:`data-model`, the field name in a literal within its model's
  section;
- every environment variable the settings read appears in a literal in
  :doc:`configuration`: every name passed as the first argument to ``env(``
  or any of its typed readers (``env.int(``, ``env.bool(``, ``env.list(``,
  ``env.db(``, ``env.email_url(``, and the rest) or to ``_throttle_rate(`` in
  ``caldart/settings/*.py``, including a call split across lines;
- every management command module (one under an app's
  ``management/commands/`` that defines ``Command``) has a row in the
  command table in :doc:`setup`, and every target ``make help`` lists (a rule
  with a ``##`` summary in the ``Makefile``) has a row in its make target
  table;
- every unit under ``deploy/systemd/`` is named in :doc:`deployment`, in
  prose or in the commands that install it.

``backend/tests/test_docs_user.py`` checks that:

- every ``:doc:`` in ``docs/user/`` has a relative target, read from the
  page's own directory, that names a page under ``docs/user/`` (an absolute
  target fails, because the guide build reads it from ``docs/user/``), every
  ``:ref:`` names a label defined there, and no user page contains
  ``/developer/`` or the words "developer guide";
- no user page uses a banned word (case-insensitive, whole words, even in
  bold or italics) or the contrast construction, matched as ``,\s+not\s``,
  ``—\s*not\s``, and ``\brather than\b``.  Text in bold or italics is
  left out of the contrast check, because it quotes the software's own
  words: the member check's reason
  *Friend of CalDART, not a member* is shown exactly as the portal prints it;
- no user page contains a double hyphen outside a code block or a section
  adornment made only of hyphens, more than two em dashes, a line beginning
  with a comma, or more than 250 lines;
- every email purpose label in ``apps/mail/purposes.py`` appears somewhere in
  the user guide;
- ``docs/conf.py`` connects no ``missing-reference`` handler, so a link from
  a user page into the developer guide fails the guide build instead of
  rendering there;
- every page under ``admin/``, ``finance/``, and ``website/`` except an index
  carries a ``:roles:`` field naming exactly the roles its screen's menu entry
  names, every slug is a role, and no other page carries the field
  (:ref:`documentation-role-gated-pages`);
- the ``guide_roles`` extension's slugs equal ``ROLE_SLUGS``, and, run on a
  small project in a temporary directory, it writes each restricted page and
  a group index's union into ``roles.json``, leaves an index open when a page
  it lists is open, and fails a ``-W`` build on an unknown slug.

``frontend/src/portal/help.test.ts`` walks the route table exported by
``routes/index.tsx`` and checks that every screen's path pattern is a
``HELP_PAGES`` entry, that every ``HELP_PAGES`` pattern is a screen that
exists, that a concrete address for each screen (``/admin/payments/42``)
opens that screen's own page and not an earlier entry's, and that every slug
in ``HELP_PAGES`` is a file ``docs/user/<slug>.rst`` read from the
repository, so a Help button never opens a missing page.

``backend/tests/test_user_guide.py`` checks how ``/docs/`` is served: the
redirect to sign in, the directory index, the private revalidated caching,
the refusal of paths that leave the guide, the content type of each
asset the figure toolbar depends on, and ``roles.json``: a restricted page
redirects a reader without its roles and is served to one with them, a page
it does not name is served to a member, and a guide without it serves every
page.  ``backend/tests/test_user_guide_search.py`` checks the trimming: on a
stand-in guide, each field of a member's and a DART leader's search index,
each piece of navigation a member's page loses or keeps, a prose link to a
restricted page reduced to its text, the queries a page and a stylesheet cost, the system
administrator's untouched files, the ``ETag`` that changes with the reader's
reach, the refusal of the build files that name restricted pages, and an
index that cannot be trimmed; and, on a guide built by Sphinx with the
site's ``conf.py`` in a temporary directory, that no page a member is served
and not their index carries a word found only on a restricted page.
``frontend/e2e/user-guide.spec.ts`` checks the same in a browser: a member
typing an administrator page's address lands on the front page, a member's
sidebar has no administrator, treasurer, or website entries, and the system
administrator's has all three; a member's search index names no
administrator, treasurer, or website page, and a word the system
administrator's search finds only on such pages finds nothing for a member.

:doc:`testing` describes how the suites run.
