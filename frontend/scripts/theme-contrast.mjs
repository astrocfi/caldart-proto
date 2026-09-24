#!/usr/bin/env node
/**
 * WCAG 2.1 contrast gate for every theme in `src/styles/themes/`.
 *
 * Each theme file redefines the semantic color tokens under
 * `:root[data-theme='<slug>']`; anything it leaves out falls back to the
 * `:root` block in `tokens.css`. This script resolves both, composites the
 * translucent status fills over the surface they sit on (an `#rrggbbaa` value
 * read raw would report a contrast the reader never sees), and checks the
 * pairs that `base.css` and `site.css` actually paint text with.
 *
 * A theme whose slug is in `GROUND_IS_NOT_A_SURFACE` paints no text on
 * `--color-bg` at all, so its pairs are measured against the panel instead.
 *
 * Run with `--json` to emit the same results as JSON for the preview gallery.
 * Exits non-zero when any pair misses its threshold.
 */

import { readFileSync, readdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const STYLES_DIR = resolve(dirname(fileURLToPath(import.meta.url)), '..', 'src', 'styles');
const THEMES_DIR = join(STYLES_DIR, 'themes');

/** Minimum ratio for anything a reader has to read at body size. */
const TEXT_RATIO = 4.5;
/** Minimum ratio for large text and for non-text affordances such as the focus ring. */
const NON_TEXT_RATIO = 3;

/**
 * Themes whose `--color-bg` is a ground the page floats on rather than a
 * surface text is set on.
 *
 * The public site fills an opaque `.panel` (`--color-bg-raised`) and the
 * portal an opaque shell (`--color-bg-sunken`); with such a theme neither ever
 * leaves small text on the ground, so measuring against it would report a
 * contrast no reader meets.  Those themes are checked against the panel.
 */
const GROUND_IS_NOT_A_SURFACE = new Set(['duty']);

/** The surface the pairs of such a theme are measured against instead. */
const PANEL_TOKEN = '--color-bg-raised';

/**
 * The pairs to check.
 *
 * `fg` is the foreground token, `bg` the background token it sits on, and
 * `over` the ground a translucent `bg` is composited onto before comparison.
 */
const PAIRS = [
  { fg: '--color-fg', bg: '--color-bg', ratio: TEXT_RATIO },
  { fg: '--color-fg', bg: '--color-bg-raised', ratio: TEXT_RATIO },
  { fg: '--color-fg', bg: '--color-bg-sunken', ratio: TEXT_RATIO },
  { fg: '--color-muted', bg: '--color-bg', ratio: TEXT_RATIO },
  { fg: '--color-muted', bg: '--color-bg-raised', ratio: TEXT_RATIO },
  { fg: '--color-muted', bg: '--color-bg-sunken', ratio: TEXT_RATIO },
  { fg: '--color-primary', bg: '--color-bg', ratio: TEXT_RATIO },
  { fg: '--color-primary', bg: '--color-bg-raised', ratio: TEXT_RATIO },
  { fg: '--color-primary-fg', bg: '--color-primary', ratio: TEXT_RATIO },
  { fg: '--color-primary-fg', bg: '--color-primary-hover', ratio: TEXT_RATIO },
  { fg: '--color-accent', bg: '--color-bg', ratio: TEXT_RATIO },
  { fg: '--color-ok', bg: '--color-bg', ratio: TEXT_RATIO },
  { fg: '--color-warn', bg: '--color-bg', ratio: TEXT_RATIO },
  { fg: '--color-bad', bg: '--color-bg', ratio: TEXT_RATIO },
  { fg: '--color-ok', bg: '--color-ok-bg', over: '--color-bg', ratio: TEXT_RATIO },
  { fg: '--color-warn', bg: '--color-warn-bg', over: '--color-bg', ratio: TEXT_RATIO },
  { fg: '--color-bad', bg: '--color-bad-bg', over: '--color-bg', ratio: TEXT_RATIO },
  { fg: '--color-focus', bg: '--color-bg', ratio: NON_TEXT_RATIO, nonText: true },
];

/**
 * Every `--color-*` declaration inside the first block whose selector matches.
 *
 * `selectorPattern` is matched against the text preceding each `{`; the first
 * hit wins, which is all these single-block theme files ever contain.
 */
function readColorBlock(css, selectorPattern) {
  const blocks = [...css.replace(/\/\*[\s\S]*?\*\//g, '').matchAll(/([^{}]+)\{([^}]*)\}/g)];
  const block = blocks.find(([, selector]) => selectorPattern.test(selector.trim()));
  if (block === undefined) return null;
  const tokens = {};
  for (const [, name, value] of block[2].matchAll(/(--color-[\w-]+)\s*:\s*([^;]+);/g)) {
    tokens[name] = value.trim();
  }
  return tokens;
}

/** Parses `#rgb`, `#rrggbb` and `#rrggbbaa` into `{ r, g, b, a }` with 0-255 channels. */
function parseHex(value) {
  const hex = value.trim().replace(/^#/, '');
  const expand = (pair) => Number.parseInt(pair, 16);
  if (hex.length === 3) {
    return {
      r: expand(hex[0] + hex[0]),
      g: expand(hex[1] + hex[1]),
      b: expand(hex[2] + hex[2]),
      a: 1,
    };
  }
  if (hex.length === 6 || hex.length === 8) {
    return {
      r: expand(hex.slice(0, 2)),
      g: expand(hex.slice(2, 4)),
      b: expand(hex.slice(4, 6)),
      a: hex.length === 8 ? expand(hex.slice(6, 8)) / 255 : 1,
    };
  }
  throw new Error(`not a hex color: ${value}`);
}

/** Paints `top` over the opaque `bottom` and returns the opaque result. */
function composite(top, bottom) {
  const mix = (channel) => Math.round(top[channel] * top.a + bottom[channel] * (1 - top.a));
  return { r: mix('r'), g: mix('g'), b: mix('b'), a: 1 };
}

/** Relative luminance, per WCAG 2.1. */
function luminance({ r, g, b }) {
  const channel = (value) => {
    const s = value / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

/** Contrast ratio between two opaque colors, from 1 to 21. */
function contrast(a, b) {
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (light + 0.05) / (dark + 0.05);
}

/** Resolves one theme's tokens: its own declarations over the `tokens.css` defaults. */
function resolveTheme(defaults, overrides) {
  return { ...defaults, ...overrides };
}

/** Evaluates every pair for one resolved token set. */
function checkTheme(slug, tokens) {
  const ground = GROUND_IS_NOT_A_SURFACE.has(slug) ? PANEL_TOKEN : '--color-bg';
  const surface = (token) => (token === '--color-bg' ? ground : token);
  const rows = [];
  for (const untargeted of PAIRS) {
    const pair = {
      ...untargeted,
      bg: surface(untargeted.bg),
      over: untargeted.over === undefined ? undefined : surface(untargeted.over),
    };
    const fgValue = tokens[pair.fg];
    const bgValue = tokens[pair.bg];
    if (fgValue === undefined || bgValue === undefined) {
      throw new Error(`${slug}: ${pair.fg} or ${pair.bg} resolves to nothing`);
    }
    const under = pair.over === undefined ? null : parseHex(tokens[pair.over]);
    const bg = under === null ? parseHex(bgValue) : composite(parseHex(bgValue), under);
    const fgRaw = parseHex(fgValue);
    const fg = fgRaw.a === 1 ? fgRaw : composite(fgRaw, bg);
    const ratio = contrast(fg, bg);
    rows.push({
      fg: pair.fg,
      bg: pair.bg,
      over: pair.over ?? null,
      fgHex: fgValue,
      bgHex: bgValue,
      required: pair.ratio,
      ratio: Math.round(ratio * 100) / 100,
      passes: ratio >= pair.ratio,
      nonText: pair.nonText === true,
    });
  }
  return rows;
}

/** Reads `tokens.css` and every theme file, returning `{ slug, rows }` per theme. */
export function auditThemes() {
  const defaults = readColorBlock(readFileSync(join(STYLES_DIR, 'tokens.css'), 'utf8'), /^:root$/);
  if (defaults === null) throw new Error('tokens.css has no `:root` block');

  const files = readdirSync(THEMES_DIR)
    .filter((name) => name.endsWith('.css'))
    .sort();
  return files.map((file) => {
    const slug = file.replace(/\.css$/, '');
    const css = readFileSync(join(THEMES_DIR, file), 'utf8');
    const overrides = readColorBlock(css, new RegExp(`\\[data-theme=['"]${slug}['"]\\]`));
    if (overrides === null)
      throw new Error(`${file} declares no :root[data-theme='${slug}'] block`);
    return { slug, rows: checkTheme(slug, resolveTheme(defaults, overrides)) };
  });
}

function describePair(row) {
  const over = row.over === null ? '' : ` over ${row.over.replace('--color-', '')}`;
  return `${row.fg.replace('--color-', '')} on ${row.bg.replace('--color-', '')}${over}`;
}

function report(themes) {
  let failures = 0;
  for (const { slug, rows } of themes) {
    const failed = rows.filter((row) => !row.passes).length;
    failures += failed;
    process.stdout.write(`\n${slug}${failed === 0 ? '' : `  (${failed} failing)`}\n`);
    for (const row of rows) {
      const mark = row.passes ? 'ok  ' : 'FAIL';
      const pair = describePair(row).padEnd(46);
      const ratio = row.ratio.toFixed(2).padStart(6);
      process.stdout.write(`  ${mark} ${pair} ${ratio}:1  (needs ${row.required})\n`);
    }
  }
  return failures;
}

// Only when run as a command: `theme-previews.mjs` imports `auditThemes` and
// must not trip over a `process.exit` at import time.
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const themes = auditThemes();
  if (process.argv.includes('--json')) {
    process.stdout.write(`${JSON.stringify(themes, null, 2)}\n`);
    process.exit(themes.some(({ rows }) => rows.some((row) => !row.passes)) ? 1 : 0);
  }

  const failures = report(themes);
  process.stdout.write(
    failures === 0
      ? `\nAll ${themes.length} themes pass.\n`
      : `\n${failures} contrast failure(s) across ${themes.length} themes.\n`,
  );
  process.exit(failures === 0 ? 0 : 1);
}
