=============
Documentation
=============

How the documentation under ``docs/`` is built, published, and kept in step
with the code: the two builds, the static assets both of them ship, the rules
every diagram follows, the voice of each guide, and the tests that fail when a
page and the code disagree.  The documentation is the specification, so a
change to the software and the change to its page land in the same pull
request.


Where the pages live
====================

::

  docs/
    conf.py              the one Sphinx configuration, for both builds
    index.rst            the root of the whole tree
    demo-walkthrough.rst a tour of the seeded demo site
    _static/             hand-written CSS and JavaScript both builds ship
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
   in, from ``USER_GUIDE_ROOT`` (:doc:`configuration`), and sends a visitor to
   the portal's login page first.

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

``docs/_static/`` holds the only custom assets, both hand-written and
dependency-free, and ``conf.py`` ships them in both builds through
``html_static_path``, ``html_css_files``, and ``html_js_files``.  The path is
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

No package supplies either file, and nothing is added to the ``docs``
dependency group or to ``frontend/package.json`` for them.  To change the
toolbar, edit the two files, run ``make docs``, and open a page with a
diagram, such as ``docs/_build/html/developer/deployment.html``.


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

- every ``:doc:`` in ``docs/user/`` names a page under ``docs/user/`` (a
  relative target is read from the page's own directory, an absolute one
  from ``docs/``), every ``:ref:`` names a label defined there, and no user
  page contains ``/developer/`` or the words "developer guide";
- no user page uses a banned word (case-insensitive, whole words) or the
  contrast construction, matched as ``,\s+not\s``, ``—\s*not\s``, and
  ``\brather than\b``.  Text in bold or italics is left out of both checks,
  because it quotes the software's own words: the member check's reason
  *Friend of CalDART, not a member* is shown exactly as the portal prints it;
- no user page contains a double hyphen outside a code block or a section
  adornment made only of hyphens, more than two em dashes, a line beginning
  with a comma, or more than 250 lines;
- every email purpose label in ``apps/mail/purposes.py`` appears somewhere in
  the user guide;
- ``docs/conf.py`` connects no ``missing-reference`` handler, so a link from
  a user page into the developer guide fails the guide build instead of
  rendering there.

``frontend/src/portal/help.test.ts`` walks the route table exported by
``routes/index.tsx`` and checks that every screen's path pattern is a
``HELP_PAGES`` entry, that every ``HELP_PAGES`` pattern is a screen that
exists, that a concrete address for each screen (``/admin/payments/42``)
opens that screen's own page and not an earlier entry's, and that every slug
in ``HELP_PAGES`` is a file ``docs/user/<slug>.rst`` read from the
repository, so a Help button never opens a missing page.

``backend/tests/test_user_guide.py`` checks how ``/docs/`` is served: the
redirect to sign in, the directory index, the private revalidated caching,
the refusal of paths that leave the guide, and the content type of each
asset the figure toolbar depends on.

:doc:`testing` describes how the suites run.
