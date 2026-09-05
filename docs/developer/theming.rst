=======
Theming
=======

One design system dresses both halves of CalDART: the server-rendered Wagtail
site and the React member portal.  Both read the same CSS custom properties,
both take their palette from ``<html data-theme="...">``, and that attribute
comes from a single dropdown in Wagtail Site Settings.  Changing the whole look
is therefore one file, or one choice by a website administrator.

This page documents PLAN §9.


Where the files are
===================

::

  frontend/src/styles/
    index.css            the entry point: fonts, then tokens, base, themes
    tokens.css           every semantic token, with the sierra values
    base.css             reset, type scale, grid, forms, buttons, tables,
                         chips, cards, site header and footer
    themes/sierra.css    (the defaults live in tokens.css; this file is the
                         explicit `[data-theme="sierra"]` block)
    themes/pacific.css
    themes/night.css
    site.css             public-site-only styles; imports index.css
  frontend/src/portal/portal.css   portal-only styles

``site/main.ts`` imports ``styles/site.css``, and ``portal/main.tsx`` imports
``styles/index.css`` plus ``portal.css``.

.. note::

   ``site.css`` pulls in ``index.css`` itself rather than being a second
   import in ``main.ts``.  Two sibling imports leave the emitted order to
   Vite's chunking, and these rules must land *after* ``base.css`` to win a
   same-specificity tie.


Tokens
======

Components only ever reference **semantic** tokens.  Nothing outside
``tokens.css`` and the theme files may contain a raw colour.

Colour
------

=========================  ==================================================
Token                      Meaning
=========================  ==================================================
``--color-bg``             Page ground ("paper")
``--color-bg-raised``      Cards, table stripes, input fields
``--color-bg-sunken``      Wells, code, disabled controls
``--color-fg``             Body text ("ink")
``--color-primary``        Primary action, links, wordmark mark
``--color-primary-fg``     Text on a primary fill
``--color-primary-hover``  Primary hover fill
``--color-accent``         The one loud colour: hover, rules that matter,
                           the step numbers, the pull-quote rule
``--color-secondary``      A supporting hue, used sparingly
``--color-rule``           Hairline separators
``--color-rule-strong``    Input borders, the strongest hairline
``--color-muted``          Secondary text
``--color-focus``          Focus ring
``--color-ok``             Status foreground: current, paid, in date
``--color-warn``           Status foreground: expiring soon
``--color-bad``            Status foreground: expired, failed
``--color-ok-bg`` etc.     The matching status fills, at low alpha
=========================  ==================================================

Type
----

``--font-display``
    *Fraunces*, a variable serif with optical sizing.  Headings, the wordmark
    and pull-quotes.  Set ``font-variation-settings`` with ``opsz`` matched to
    the size, as ``base.css`` does for ``h1``–``h4``.

``--font-body``
    *IBM Plex Sans*.  Everything else.

``--font-mono``
    *IBM Plex Mono*.  Data that a reader scans or compares: N-numbers,
    certificate numbers, money, dates in tables, the EIN, airport identifiers.

Sizes run ``--text-xs`` … ``--text-4xl`` on a 1.25 scale anchored at 16px, with
``--leading-tight/snug/normal`` and ``--weight-normal/medium/semibold/bold``.

Space, shape and layout
-----------------------

``--space-1`` … ``--space-8`` (0.25rem → 6rem), ``--radius`` (2px — near-square
by design), ``--radius-pill``, ``--hairline`` (1px), ``--measure`` (68ch),
``--page-max``, ``--rail-width``, and ``--duration`` / ``--ease`` for motion.


How a theme reaches the page
============================

#. A website administrator picks a theme in **Settings → Site settings**.
#. ``apps.cms.context_processors.site_chrome`` puts the slug in the template
   context as ``theme``; ``caldart.views.portal_shell`` does the same for the
   SPA through ``SiteSettings.get_theme(request)``.
#. ``base.html`` and ``portal.html`` render
   ``<html lang="en" data-theme="{{ theme }}">``.
#. ``themes/<slug>.css`` redefines the tokens under
   ``:root[data-theme="<slug>"]``, and every component follows.

Because the attribute is on ``<html>`` and rendered by the server, there is no
flash of the wrong palette.

Previewing a theme
------------------

Website and system administrators can append ``?theme=<slug>`` to any public
URL.  ``context_processors.can_preview_theme`` sets
``data-theme-preview="allowed"`` on ``<html>``, and ``site/main.ts`` swaps
``data-theme`` client side when — and only when — that attribute is present and
the slug is one that ships.  It writes nothing to the server and nobody else
sees it.


The shipped themes
==================

``sierra`` (default)
    Warm paper ``#F4F1EA``, ink ``#1B1F24``, deep conifer ``#1F4D3A``, signal
    orange ``#E4572E``, poppy gold ``#F2A900``, rule ``#D9D3C7``.

``pacific``
    Cooler paper ``#F6F7F5``, ink ``#14212B``, deep pacific ``#0F3D5C``, the
    same signal orange, fog ``#8DA9B8``.

``night``
    Dark: paper ``#151719``, ink ``#ECE9E1``, primary ``#7FB69B``, accent
    ``#FF7A52``, secondary ``#F2C14E``.

Status colours are shared: ok ``#2E7D4F``, warn ``#C98A00``, bad ``#B23A2B``,
adjusted per theme where contrast demands it.


Adding a theme
==============

#. Create ``frontend/src/styles/themes/<slug>.css``::

       /* Chaparral: dry hills, high sun. */
       :root[data-theme='chaparral'] {
         --color-bg: #f7f3ec;
         --color-bg-raised: #fffdf8;
         --color-bg-sunken: #eee7db;
         --color-fg: #241f1a;
         --color-primary: #6b3f2a;
         --color-primary-fg: #fbf7f0;
         --color-primary-hover: #52301f;
         --color-accent: #b3462b;
         --color-secondary: #d99a2b;
         --color-rule: #ded5c6;
         --color-rule-strong: #bdb09a;
         --color-muted: #6f665c;
         --color-focus: #6b3f2a;
         --color-selection: #d99a2b33;
         color-scheme: light;
       }

   Redefine every token the shipped themes redefine; a token you leave out
   falls back to the ``sierra`` value in ``tokens.css``, which is rarely what
   you want.  A dark theme must also set ``color-scheme: dark`` so form
   controls and scrollbars follow.

#. Import it in ``styles/index.css``, after the other themes.

#. Register the slug in ``apps/cms/models.py``::

       THEME_CHOICES = (
           ("sierra", "Sierra (default, warm paper)"),
           ("pacific", "Pacific (cool paper)"),
           ("night", "Night (dark)"),
           ("chaparral", "Chaparral (dry hills)"),
       )

#. Add it to ``THEMES`` in ``frontend/src/site/nav.ts``, so ``?theme=`` will
   preview it.

#. ``manage.py makemigrations cms`` — ``choices`` changes are migrations.

#. Check the contrast: body text and muted text against both ``--color-bg``
   and ``--color-bg-raised`` must reach 4.5:1, and the focus ring must be
   visible against both.

#. ``make build`` and look at the home page, a standard page, the DART table,
   the members-only wall and the portal dashboard before calling it done.


Fonts
=====

Fonts are self-hosted through ``@fontsource`` packages so the site works with
no network:

.. code-block:: css

   @import '@fontsource-variable/fraunces/full.css';
   @import '@fontsource/ibm-plex-sans/400.css';
   @import '@fontsource/ibm-plex-sans/500.css';
   @import '@fontsource/ibm-plex-sans/600.css';
   @import '@fontsource/ibm-plex-sans/400-italic.css';
   @import '@fontsource/ibm-plex-mono/400.css';
   @import '@fontsource/ibm-plex-mono/500.css';

Only the weights actually used are imported; adding one means adding an
import.  Fraunces uses the ``full`` build because the design system drives its
``opsz``, ``SOFT`` and ``WONK`` axes.  Every stack in ``tokens.css`` ends in a
real system fallback, so a page still reads correctly before the webfonts
arrive.

To change a typeface, ``npm install`` the ``@fontsource`` package, swap the
imports in ``index.css`` and the family in the matching ``--font-*`` token.
Nothing else refers to a font by name.


House rules
===========

* **Semantic tokens only** in components.  If you need a colour that no token
  names, add the token — do not inline a hex value.
* **Hairlines, not boxes.**  Sections are separated by a ``1px``
  ``--color-rule`` and generous space.  No drop shadows, no background-colour
  bands, no floating rounded cards.
* **Near-square corners.**  ``--radius`` is 2px and stays that way.
* **Asymmetry is deliberate.**  The 12-column grid runs text at 7 columns and
  the aside at 4, with a column of air between them (``.col-text`` /
  ``.col-side``).
* **Mobile first.**  Every breakpoint in the system is ``min-width``; the
  narrow layout is the base case.
* **Focus rings are never removed**, and ``prefers-reduced-motion`` is
  honoured globally in ``base.css``.
* **Contrast ≥ 4.5:1** for text in every theme.
