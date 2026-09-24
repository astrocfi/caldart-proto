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
    themes/squadron.css  ... and one file per remaining slug: flight-deck,
                         contrail, sectional, tarmac, coastal, slate,
                         meridian, monterey-night, granite
    scripts/theme-contrast.mjs   the WCAG gate `make lint` runs
    scripts/theme-previews.mjs   the screenshot gallery builder
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
``--color-signal-go``,     The status *dots*: filled shapes rather than type,
``--color-signal-warn``,   so they are brighter and further apart in hue than
``--color-signal-stop``    the status colors above
=========================  ==================================================

That is the whole set of color a theme redefines — twenty-one tokens, listed
above in the order ``themes/duty.css`` declares them.  A theme may redefine the
three type tokens below as well.  The three signal colors are optional: a theme
that leaves them out gets the values in ``tokens.css``, which are chosen to read
as go, caution and stop on any light ground.

Type
----

Each theme names all three faces, so the dropdown changes the type along with
the palette.  ``tokens.css`` carries the sierra set as the default.

``--font-display``
    The portal's headings and its wordmark.  Duty's is *Fraunces*, a variable
    serif with optical sizing; ``base.css`` sets ``font-variation-settings``
    with ``opsz`` matched to the size for ``h1``–``h4``, which a face with no
    ``opsz`` axis simply ignores.  The public site sets its headings in the
    body face instead: there the panel and its rules carry the structure.

``--font-body``
    Everything else.  Sierra's is *IBM Plex Sans*.

``--font-mono``
    Data that a reader scans or compares: N-numbers, certificate numbers,
    money, dates in tables, the EIN, airport identifiers.  Sierra's is *IBM
    Plex Mono*.

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

Fourteen themes ship.  Each one names its own three typefaces as well as its
own palette, so switching the dropdown changes the type too.

``duty`` (default)
    Blue-gray ground ``#CCD3DC``, a white panel, ink ``#1D2530``, navy
    ``#1F4E79``, the wordmark's red ``#B3261E`` for the one urgent action,
    lighter navy ``#3F7FB0`` for the sidebar, rule ``#CCD6E1``, muted
    ``#55606D``.  Fraunces / IBM Plex Sans / IBM Plex Mono.

``sierra``
    Warm paper ``#F4F1EA``, ink ``#1B1F24``, deep conifer ``#1F4D3A``, signal
    orange ``#BB4623``, poppy gold ``#F2A900``, rule ``#D9D3C7``, muted
    ``#64676E``.  Fraunces / IBM Plex Sans / IBM Plex Mono.

``pacific``
    Cooler paper ``#F6F7F5``, ink ``#14212B``, deep pacific ``#0F3D5C``, the
    same signal orange, fog ``#8DA9B8``.  Fraunces / IBM Plex Sans / IBM Plex
    Mono.

``night``
    Dark: paper ``#151719``, ink ``#ECE9E1``, primary ``#7FB69B``, accent
    ``#FF7A52``, secondary ``#F2C14E``.  Fraunces / IBM Plex Sans / IBM Plex
    Mono.

Status colors are close to shared: ok ``#1F7A4D``, warn ``#8F5C00``, bad
``#B3261E`` under ``duty``, adjusted per theme where contrast demands it.

``squadron``
    The CalDART logo on white: ground ``#FFFFFF``, cobalt ``#1B409A``, crimson
    ``#B8303F``, sky ``#4F8FE8``, ink ``#14213D``.  Barlow / Source Sans 3 /
    JetBrains Mono.

``flight-deck``
    The logo after dark: navy ``#0F1A33``, cobalt tint ``#7EA2FF``, crimson
    tint ``#EF6B78``, amber ``#FFC857``.  Exo 2 / Inter / IBM Plex Mono.

``contrail``
    The logo gone light and airy: sky paper ``#EEF4FB``, cobalt ``#1B409A``,
    crimson ``#B02C3A``, secondary ``#3B7DD8``.  Titillium Web / Open Sans /
    Roboto Mono.

``sectional``
    An aeronautical chart: chart cream ``#F7F3E8``, chart blue ``#2C5AA0``,
    airspace magenta ``#A72F80``, terrain tan ``#B3833F``.  Manrope / Source
    Sans 3 / Roboto Mono.

``tarmac``
    Industrial neutrals: concrete ``#F2F2F0``, asphalt ``#2B2F36``, safety
    yellow ``#E3B505`` on surfaces only, emphasis red ``#B40D27``.  Archivo /
    Karla / Fira Code.

``coastal``
    The California shoreline: fog ``#F3F6F7``, ocean teal ``#146C7A``, sunset
    coral ``#BD4A2A``, dune sand ``#C9A15A``.  Lora / Nunito Sans / Source
    Code Pro.

``slate``
    Cool corporate: ``#F5F7FA``, slate ``#34495E``, amber ``#A94C08``,
    secondary ``#2F7F9E``.  Merriweather / Work Sans / DM Mono.

``meridian``
    High-contrast civic: white, navy ``#0D3B66``, burnt orange ``#B03A0A``,
    secondary ``#166B64``.  Libre Franklin throughout, with Roboto Mono for
    data.

``monterey-night``
    Charcoal dark: ``#14171C``, sea green ``#5EC8B8``, amber ``#FFB454``, cool
    blue ``#8AB4F8``.  Sora / Inter / JetBrains Mono.

``granite``
    Near-monochrome: white, near-black ``#1F1F1F``, grays, and link blue
    ``#0A58CA``.  Inter Tight / Inter / Geist Mono.

The light themes share one status palette -- ok ``#27693F``, warn ``#825900``,
bad ``#AB3628`` -- and the two dark ones lift it so the same states stay
legible on a dark ground.

.. _theming-contrast-gate:

Contrast is a gate
------------------

``frontend/scripts/theme-contrast.mjs`` parses every file in ``themes/``,
resolves each theme's tokens against the ``tokens.css`` defaults and measures
the pairs ``base.css`` and ``site.css`` actually paint text with: ``--color-fg``
and ``--color-muted`` over all three grounds, ``--color-primary`` as link text,
``--color-primary-fg`` on both primary fills, ``--color-accent`` on the ground,
and each status color both on the ground and on its own translucent fill --
composited over the ground first, because an ``#rrggbbaa`` value read raw
reports a contrast no reader ever sees.  Text pairs must reach 4.5:1 and
non-text ones, such as the focus ring, 3:1.

``npm run theme-contrast`` prints a table per theme and exits non-zero on any
failure; ``make lint`` runs it, so a theme that fails cannot merge.


Preview gallery
---------------

``frontend/scripts/theme-previews.mjs`` shoots every theme against a running,
seeded server and writes a browsable gallery.  Start the server the way
``make e2e`` does -- a database of its own, ``db_reset --seed --noinput``,
``npm run build``, ``collectstatic``, then ``runserver`` -- and run::

   cd frontend && PREVIEW_BASE_URL=http://localhost:8130 npm run theme-previews

For each theme it captures the public home page, a public inner page, the
portal dashboard and the member profile at 1440x1000, plus the home page at
420px, by setting ``data-theme`` on ``<html>`` after load and waiting on
``document.fonts.ready``.  The output lands in ``theme-previews/`` (untracked;
the PNGs never enter git) as ``index.html``, a ``README.md`` and one directory
per slug.  Each entry carries the palette with hex values, the three font
families with their ``@fontsource`` packages, the contrast table, and how to
select or preview that theme.


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

         --color-ok: #27693f;
         --color-warn: #825900;
         --color-bad: #ab3628;
         --color-ok-bg: #27693f1f;
         --color-warn-bg: #8259001f;
         --color-bad-bg: #ab36281f;
         --color-neutral-bg: #6f665c17;

         --font-display: 'Lora Variable', 'Lora', Georgia, serif;
         --font-body: 'Karla Variable', 'Karla', -apple-system, sans-serif;
         --font-mono: 'Fira Code Variable', 'Fira Code', ui-monospace, monospace;

         color-scheme: light;
       }

   That is the complete set: every shipped theme redefines exactly these
   twenty-one color tokens — status colors and their translucent fills
   included — plus the three type tokens.  Every stack ends in a real system
   fallback, so the page reads correctly before the webfonts arrive.  A
   token you leave out falls back to the ``duty`` value in ``tokens.css``,
   which is rarely what you want — and on a dark theme is usually unreadable.
   A dark theme must also set ``color-scheme: dark`` so form controls and
   scrollbars follow.

#. Import it in ``styles/index.css``, after the other themes.

#. Register the slug in ``apps/cms/models.py``::

       THEME_CHOICES = (
           ("duty", "Duty (default, blue and red)"),
           ("sierra", "Sierra (warm paper)"),
           ...
           ("chaparral", "Chaparral (dry hills)"),
       )

#. Add it to ``THEMES`` in ``frontend/src/site/nav.ts``, so ``?theme=`` will
   preview it.

#. Update the ``choices`` recorded for the ``theme`` column in
   ``apps/cms/migrations/0001_initial.py``.  This prototype stacks no fix-up
   migrations: edit the migration that declares the field, then confirm
   ``manage.py makemigrations --check`` is satisfied.

#. Check the contrast with ``npm run theme-contrast``, which is part of
   ``make lint`` (see :ref:`theming-contrast-gate`).

#. ``make build`` and look at the home page, a standard page, the DART table,
   the members-only wall and the portal dashboard before calling it done.


Fonts
=====

Fonts are self-hosted through ``@fontsource`` packages so the site works with
no network.  ``index.css`` declares every face any theme can ask for, grouped
under a comment naming the theme that introduced it:

.. code-block:: css

   /* -- sierra ----------------------------------------------------------- */
   @import '@fontsource-variable/fraunces/full.css';
   @import '@fontsource/ibm-plex-sans/400.css';
   @import '@fontsource/ibm-plex-sans/500.css';
   @import '@fontsource/ibm-plex-sans/600.css';
   @import '@fontsource/ibm-plex-sans/400-italic.css';
   @import '@fontsource/ibm-plex-mono/400.css';
   @import '@fontsource/ibm-plex-mono/500.css';

   /* -- squadron --------------------------------------------------------- */
   @import '@fontsource/barlow/400.css';
   @import '@fontsource/barlow/600.css';
   @import '@fontsource/barlow/700.css';
   @import '@fontsource-variable/source-sans-3';
   @import '@fontsource-variable/source-sans-3/wght-italic.css';
   @import '@fontsource-variable/jetbrains-mono';

Declaring them all costs a reader nothing: an ``@font-face`` rule downloads its
file only when something on the page uses that family, so a visitor fetches
only the three faces the active theme names.

Prefer ``@fontsource-variable`` where the family has a variable build -- one
import covers the whole weight axis, plus a second ``wght-italic.css`` import
for a body face that needs italics.  A static package needs a file per weight,
so import only the weights in use: 400, 500 and 600 plus 400-italic for a body
face, 400/600/700 for a display face, 400 and 500 for a mono face.  Fraunces
uses the ``full`` build because the design system drives its ``opsz``, ``SOFT``
and ``WONK`` axes.

To change a theme's typeface, ``npm install`` the ``@fontsource`` package, add
the imports to ``index.css`` and name the family in that theme's ``--font-*``
token.  Nothing else refers to a font by name.

.. note::

   ``npm install`` crashes on this dependency tree under npm 10 with an
   ``edgesOut`` error.  Install with ``npx -y npm@11 install --save <pkg>`` and
   then verify the result with a clean ``npm ci``.


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
* **Contrast ≥ 4.5:1** for text in every theme, and ≥ 3:1 for the focus
  ring.  ``make lint`` measures it (see :ref:`theming-contrast-gate`), so this
  is a gate and not an aspiration.

Related
=======

:doc:`api-system` documents ``GET /site/config``, which reports the active
theme to the portal.
