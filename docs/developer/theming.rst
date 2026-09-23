=======
Theming
=======

One design system dresses both halves of CalDART: the server-rendered Wagtail
site and the React member portal.  Both read the same CSS custom properties,
both take their palette from ``<html data-theme="...">``, and that attribute
comes from a single dropdown in Wagtail Site Settings.  Changing the whole look
is therefore one file, or one choice by a website administrator.


Where the files are
===================

::

  frontend/src/styles/
    index.css            the entry point: fonts, then tokens, base, themes
    tokens.css           every semantic token, with the duty values
    base.css             reset, type scale, grid, forms, buttons, tables,
                         chips, cards
    themes/duty.css      (the defaults live in tokens.css; this file is the
                         explicit `[data-theme="duty"]` block)
    themes/sierra.css
    themes/pacific.css
    themes/night.css
    site.css             the public site's own shape -- panel, masthead,
                         navigation bar, boxes, sidebar; imports index.css
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
``tokens.css`` and the theme files may contain a raw color, with one exception.

.. _theming-stripe-colors:

.. note::

   That exception is
   ``frontend/src/portal/features/checkout/StripePanel.tsx``.  Stripe's Payment
   Element renders in an iframe, which cannot read the page's CSS custom
   properties, so ``appearanceFromTokens()`` resolves each token with
   ``getComputedStyle`` and hands Stripe the computed value.  Every color
   lookup carries the duty hex as a fallback, for the case where the property
   resolves to nothing; the two lookups that are not colors, ``--font-body``
   and ``--radius``, fall back to a plain literal.  Change a duty color and
   change the matching fallback with it.

Color
-----

=========================  ==================================================
Token                      Meaning
=========================  ==================================================
``--color-bg``             Page ground ("paper")
``--color-bg-raised``      Cards, table stripes, input fields
``--color-bg-sunken``      Wells, code, disabled controls
``--color-fg``             Body text ("ink")
``--color-primary``        Primary action, links, the masthead rule, the
                           navigation bar and a box's title bar
``--color-primary-fg``     Text on a primary fill
``--color-primary-hover``  Primary hover fill
``--color-accent``         The one loud color: the request-for-help button,
                           and a rule that matters
``--color-secondary``      A supporting hue, used sparingly.  The public
                           site's sidebar bars do **not** use it: they mix a
                           lighter cut of ``--color-primary``, because under
                           some themes this token is a loud accent
``--color-rule``           Hairline separators
``--color-rule-strong``    Input borders, the strongest hairline
``--color-muted``          Secondary text
``--color-selection``      ``::selection`` background, at low alpha
``--color-ok``             Status foreground: current, paid, in date
``--color-warn``           Status foreground: expiring soon
``--color-bad``            Status foreground: expired, failed
``--color-ok-bg``,         The matching status fills, at low alpha
``--color-warn-bg``,
``--color-bad-bg``
``--color-neutral-bg``     Fill for a chip with no status at all
``--color-focus``          Focus ring
=========================  ==================================================

That is the whole set a theme redefines — twenty-one tokens, listed above in
the order ``themes/duty.css`` declares them.

Type
----

``--font-display``
    *Fraunces*, a variable serif with optical sizing.  The portal's headings
    and its wordmark.  Set ``font-variation-settings`` with ``opsz`` matched to
    the size, as ``base.css`` does for ``h1``–``h4``.  The public site sets its
    headings in the body face instead: there the panel and its rules carry the
    structure.

``--font-body``
    *IBM Plex Sans*.  Everything else.

``--font-mono``
    *IBM Plex Mono*.  Data that a reader scans or compares: N-numbers,
    certificate numbers, money, dates in tables, the EIN, airport identifiers.

Sizes run ``--text-xs`` … ``--text-4xl`` on a 1.25 scale anchored at 16px, with
``--leading-tight/snug/normal``, ``--weight-normal/medium/semibold/bold`` and
``--tracking-eyebrow``.  In the portal, headings ``h1``–``h4`` are set in the
display face, semibold, at ``--leading-tight``, and the ``.eyebrow`` label
above a heading is extra-small semibold body type in uppercase, spaced out by
``--tracking-eyebrow`` and colored ``--color-muted``.  The public site uses
neither: its box title bars name each section instead.

Space, shape, and layout
------------------------

``--space-1`` … ``--space-8`` (0.25rem → 6rem), ``--radius`` (6px — boxes
, buttons, and inputs are softened, not rounded), ``--radius-pill``,
``--hairline`` (1px), ``--measure`` (68ch), ``--page-max``, ``--rail-width``,
and ``--duration``, ``--duration-fast`` and ``--ease`` for motion.


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
URL.  Three things have to line up:

#. ``context_processors.can_preview_theme(user)`` returns ``True``, and
   ``site_chrome`` puts that boolean in the template context.
#. ``base.html`` turns it into an attribute —
   ``{% if can_preview_theme %} data-theme-preview="allowed"{% endif %}`` on
   ``<html>``.
#. ``site/main.ts`` swaps ``data-theme`` client side when, and only when, that
   attribute is present and the slug is one that ships.

It writes nothing to the server and nobody else sees it.

``portal.html`` does **not** emit the attribute, so ``?theme=`` previews the
public site only; the portal always renders the saved theme.


The shipped themes
==================

``duty`` (default)
    Blue-gray ground ``#CCD3DC``, a white panel, ink ``#1D2530``, navy
    ``#1F4E79``, the wordmark's red ``#B3261E`` for the one urgent action,
    lighter navy ``#3F7FB0`` for the sidebar, rule ``#CCD6E1``, muted
    ``#55606D``.

``sierra``
    Warm paper ``#F4F1EA``, ink ``#1B1F24``, deep conifer ``#1F4D3A``, signal
    orange ``#E4572E``, poppy gold ``#F2A900``, rule ``#D9D3C7``, muted
    ``#6B6F76``.

``pacific``
    Cooler paper ``#F6F7F5``, ink ``#14212B``, deep pacific ``#0F3D5C``, the
    same signal orange, fog ``#8DA9B8``.

``night``
    Dark: paper ``#151719``, ink ``#ECE9E1``, primary ``#7FB69B``, accent
    ``#FF7A52``, secondary ``#F2C14E``.

Status colors are close to shared: ok ``#1F7A4D``, warn ``#A86B00``, bad
``#B3261E`` under ``duty``, adjusted per theme where contrast demands it.


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

         --color-ok: #2e7d4f;
         --color-warn: #c98a00;
         --color-bad: #b23a2b;
         --color-ok-bg: #2e7d4f1f;
         --color-warn-bg: #c98a001f;
         --color-bad-bg: #b23a2b1f;
         --color-neutral-bg: #6f665c17;

         color-scheme: light;
       }

   That is the complete set: every shipped theme redefines exactly these
   twenty-one tokens, status colors and their translucent fills included.  A
   token you leave out falls back to the ``duty`` value in ``tokens.css``,
   which is rarely what you want — and on a dark theme is usually unreadable.
   A dark theme must also set ``color-scheme: dark`` so form controls and
   scrollbars follow.

#. Import it in ``styles/index.css``, after the other themes.

#. Register the slug in ``apps/cms/models.py``::

       THEME_CHOICES = (
           ("duty", "Duty (default, blue and red)"),
           ("sierra", "Sierra (warm paper)"),
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
``opsz``, ``SOFT``, and ``WONK`` axes.  Every stack in ``tokens.css`` ends in a
real system fallback, so a page still reads correctly before the webfonts
arrive.

To change a typeface, ``npm install`` the ``@fontsource`` package, swap the
imports in ``index.css`` and the family in the matching ``--font-*`` token.
Nothing else refers to a font by name.


House rules
===========

* **Plain and civic.**  Type, rules, and the panel carry the design, not
  decoration: no gradients, no glassmorphism or backdrop blur, no hero blobs
  and no emoji bullets.
* **Semantic tokens only** in components.  If you need a color that no token
  names, add the token — do not inline a hex value.  The one exception is
  :ref:`the Stripe panel <theming-stripe-colors>`, which has to hand computed
  values across an iframe boundary.
* **Boxes on the public site, hairlines in the portal.**  A public page is a
  stack of ``.box`` elements, each with a title bar in ``--color-primary``
  (``--color-secondary`` in the sidebar) and a bordered body.  The portal
  separates its sections with a ``1px`` ``--color-rule`` and space instead.
  Neither uses drop shadows.
* **Softened corners.**  ``--radius`` is 6px and stays that way.
* **One panel, two columns.**  The public site centers a ``.panel`` at
  ``--panel-max`` (62.5rem); inside it ``.panel__main`` takes the space left
  by a ``.panel__side`` of ``--side-width``, and below ``59.99rem`` the two
  stack.  The portal keeps the 12-column grid, running text at 7 columns and
  an aside at 4 from ``min-width: 60rem`` (``.col-text`` / ``.col-side``).
* **Mobile first.**  Layout breakpoints are ``min-width`` and the narrow
  layout is the base case.  A handful of ``max-width`` queries exist for the
  opposite job — collapsing the navigation bar below ``47.99rem`` and the
  sidebar below ``59.99rem`` — but reach for ``min-width`` unless you are
  genuinely undoing something wide.
* **Focus rings are never removed**, and ``prefers-reduced-motion`` is
  honored globally in ``base.css``.
* **Contrast ≥ 4.5:1** for text in every theme.

Related
=======

:doc:`api-system` documents ``GET /site/config``, which reports the active
theme to the portal.
