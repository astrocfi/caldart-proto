# CalDART home page layouts

Ten page structures for the public home page. Each is a standalone mockup
(`<slug>/index.html`, all CSS inline, no JavaScript) built from one copy sheet,
`shared/copy.md`, so the layouts differ and the words do not. Open `index.html`
for the gallery, or any `<slug>/index.html` directly in a browser.

These are layouts, not themes. Colors and typefaces were chosen per mockup to
suit its structure and are not tied to the theme tokens in
`frontend/src/styles/themes/`; whichever layout is chosen gets implemented in
the Django templates and `site.css` and then takes its colors from the active
theme.

| # | Slug | Modeled on |
| --- | --- | --- |
| 1 | `county-bulletin` | a county office of emergency services site |
| 2 | `boxed-chapter` | an EAA chapter or CAP squadron site |
| 3 | `official-notice` | a state agency information page |
| 4 | `newsletter` | the front page of a printed club newsletter |
| 5 | `magazine` | a feature spread in a general-aviation magazine |
| 6 | `banner-split` | a regional non-profit with a photo banner |
| 7 | `brochure-bands` | a small non-profit's site-builder page |
| 8 | `audience-tabs` | a member-services hub with a search box |
| 9 | `status-board` | an operations center readiness page |
| 10 | `map-finder` | a "find your local unit" page |

## What was avoided

The brief (`shared/brief.md`) bans the tells of the current home page: eyebrow
labels, the large serif display headline, the ruled pull-quote, numbered steps
between hairlines, hairlines as the only structure, "X, not Y" phrasing, equal
card grids, pill buttons and gradients. Every mockup was checked for horizontal
overflow at 420px and 1440px and grepped for "X, not Y" constructions.

## Photos and assets

Photo slots are hatched boxes with a caption naming the photograph expected
there. `shared/california.svg` is a hand-projected outline of the state with
the fifteen DART airports pinned; `shared/plane.svg` is the airplane silhouette.
Both are placeholders for the real logo and photography.

## Regenerate

```
node layout-previews/render.mjs            # every mockup, desktop.png and mobile.png
node layout-previews/render.mjs newsletter # one mockup
node layout-previews/build-index.mjs       # rebuild index.html from layouts.json
```

`render.mjs` uses the Playwright that `frontend/` installs for the e2e suite,
so `make setup` must have run.
