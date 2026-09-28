# Brief for every layout mockup

You are building one static HTML mockup of the CalDART public home page. It is a
*layout* study: the owner will pick a page structure from ten candidates, then it
will be implemented in the Django templates. Colors and fonts are secondary; the
arrangement of the page is what is being judged.

## What the owner rejected

The current home page (screenshot: `theme-previews/sierra/site-home.png`) reads as
an AI-generated "Claude" page. The owner named these tells, and every one of them is
banned:

- small tracked uppercase "eyebrow" labels above headings
- a huge serif display headline floating in white space
- a pull-quote with a colored left rule
- numbered steps (01, 02, 03) separated by hairlines
- hairline dividers as the only visible structure
- "X, not Y" sentence constructions, anywhere
- three equal cards in a row with an icon each
- rounded pill buttons, gradients, glass or blur effects, drop-shadowed cards on a
  pastel ground, giant vertical padding between sections
- emoji, icon fonts, decorative unicode
- the IBM Plex / serif-display font pairing the current site uses

Aim instead for the way real organizations' sites look: a county emergency services
office, an EAA chapter, a Civil Air Patrol squadron, a volunteer fire company, a
community newsletter. Dense, specific, a little plain. Visible borders and boxes
where a box is useful. Real-looking widgets (a login form, a select, a table of
dates, a phone number in large type). Text that says concrete things.

## Rules

- One file: `layout-previews/<slug>/index.html`, all CSS inline in a `<style>` tag,
  no JavaScript unless the spec asks for it, no external resources. Images are the
  two shared SVGs (`../shared/california.svg`, `../shared/plane.svg`) and photo
  slots: a plainly labeled box, e.g. class `photo`, hatched or flat, with a caption
  like "Photo: ground crew at the Hayward workshop". Keep the caption; the owner
  needs to know what photo goes there.
- Use only the copy in `layout-previews/shared/copy.md`. Trim and reorder freely.
  Do not invent new marketing lines. Never write an "X, not Y" sentence.
- Fonts: only families installed on this machine, with a generic fallback.
  Available and useful: Liberation Sans (Arial), Liberation Sans Narrow, Nimbus
  Sans (Helvetica), Noto Sans, Ubuntu, DejaVu Sans (Verdana-ish), URW Gothic
  (Avant Garde), Liberation Serif / Nimbus Roman (Times), Bitstream Charter, Noto
  Serif, URW Bookman, C059 (Century Schoolbook), P052 (Palatino), Liberation Mono.
  Your spec names the pairing.
- Must work at 1440px and at 420px wide with no horizontal scrolling. Tables may
  scroll inside their own wrapper.
- Accessible: real `<nav>`, `<main>`, headings in order, labels on form fields,
  link text that means something, contrast at least 4.5:1 for body text.
- The header, navigation and footer are part of the layout: design them for this
  layout rather than copying the existing site's.
- `layout-previews/boxed-chapter/index.html` is a finished example of the standard
  (a classic boxed chapter site). Do not copy its structure; do match its level of
  finish and concreteness.

## Workflow

1. Read `layout-previews/shared/copy.md` and `layout-previews/boxed-chapter/index.html`.
2. Write your `index.html`.
3. Render: from the repository root run `node layout-previews/render.mjs <slug>`.
   It writes `desktop.png` and `mobile.png` next to your file.
4. Look at both PNGs with the Read tool. Fix anything that overflows, overlaps, looks
   unfinished, or matches a banned tell. Re-render until it is right. Check the
   mobile shot as carefully as the desktop one.
5. Do not run git commands, do not touch files outside your own directory, and do not
   edit the shared files.
6. Return, as plain text: the slug, the font pairing, four or five sentences that
   describe the page structure top to bottom (what a developer would need to
   rebuild it), and anything you could not resolve.
