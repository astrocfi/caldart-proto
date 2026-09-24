#!/usr/bin/env node
/**
 * Screenshots every shipped theme and builds a browsable gallery.
 *
 * It drives a real CalDART server -- start one the way `make e2e` does, with
 * seeded demo content -- and for each theme captures the public home page, a
 * public inner page, the portal dashboard and the member profile, plus a
 * narrow home page. The theme is applied by setting `data-theme` on
 * `<html>` after load, which is exactly what the server renders for that
 * setting in Wagtail Site Settings.
 *
 * Environment:
 *   PREVIEW_BASE_URL  server to shoot (default http://localhost:8130)
 *   PREVIEW_OUT_DIR   where the gallery is written (default ../theme-previews)
 *   PREVIEW_EMAIL     demo member sign-in (default member@example.org)
 *   PREVIEW_PASSWORD  demo password (default caldart-demo)
 */

import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { chromium } from '@playwright/test';

import { auditThemes } from './theme-contrast.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HERE, '..');
const STYLES = join(FRONTEND, 'src', 'styles');

const BASE_URL = process.env.PREVIEW_BASE_URL ?? 'http://localhost:8130';
const OUT_DIR = process.env.PREVIEW_OUT_DIR ?? resolve(FRONTEND, '..', 'theme-previews');
const EMAIL = process.env.PREVIEW_EMAIL ?? 'member@example.org';
const PASSWORD = process.env.PREVIEW_PASSWORD ?? 'caldart-demo';

const DESKTOP = { width: 1440, height: 1000 };
const MOBILE = { width: 420, height: 900 };

/** The public and portal shots taken at desktop width, in gallery order. */
const SHOTS = [
  { file: 'site-home.png', label: 'Public home', path: '/', portal: false },
  { file: 'site-inner.png', label: 'Public inner page', path: null, portal: false },
  { file: 'portal-dashboard.png', label: 'Portal dashboard', path: '/portal/', portal: true },
  { file: 'portal-profile.png', label: 'Member profile', path: '/portal/profile', portal: true },
];

/**
 * One theme's presentation data: intent, palette, fonts and packages.
 *
 * `intent` is the one-line summary the gallery prints; `fonts` names the three
 * faces with the @fontsource package each comes from.
 */
const THEME_NOTES = {
  sierra: {
    intent: 'The default: warm paper, deep conifer, signal orange.',
    fonts: {
      Display: ['Fraunces', '@fontsource-variable/fraunces'],
      Body: ['IBM Plex Sans', '@fontsource/ibm-plex-sans'],
      Mono: ['IBM Plex Mono', '@fontsource/ibm-plex-mono'],
    },
  },
  pacific: {
    intent: 'Cooler paper and a deep pacific blue primary.',
    fonts: {
      Display: ['Fraunces', '@fontsource-variable/fraunces'],
      Body: ['IBM Plex Sans', '@fontsource/ibm-plex-sans'],
      Mono: ['IBM Plex Mono', '@fontsource/ibm-plex-mono'],
    },
  },
  night: {
    intent: 'The dark counterpart to sierra, with lifted status colors.',
    fonts: {
      Display: ['Fraunces', '@fontsource-variable/fraunces'],
      Body: ['IBM Plex Sans', '@fontsource/ibm-plex-sans'],
      Mono: ['IBM Plex Mono', '@fontsource/ibm-plex-mono'],
    },
  },
  squadron: {
    intent: 'The CalDART logo on white: cobalt, crimson, sky, and a lot of air.',
    fonts: {
      Display: ['Barlow', '@fontsource/barlow'],
      Body: ['Source Sans 3', '@fontsource-variable/source-sans-3'],
      Mono: ['JetBrains Mono', '@fontsource-variable/jetbrains-mono'],
    },
  },
  'flight-deck': {
    intent: 'The logo after dark: navy instruments, cobalt tint, crimson and amber.',
    fonts: {
      Display: ['Exo 2', '@fontsource-variable/exo-2'],
      Body: ['Inter', '@fontsource-variable/inter'],
      Mono: ['IBM Plex Mono', '@fontsource/ibm-plex-mono'],
    },
  },
  contrail: {
    intent: 'The logo gone light and airy: high sky paper, cobalt, crimson.',
    fonts: {
      Display: ['Titillium Web', '@fontsource/titillium-web'],
      Body: ['Open Sans', '@fontsource-variable/open-sans'],
      Mono: ['Roboto Mono', '@fontsource-variable/roboto-mono'],
    },
  },
  sectional: {
    intent: 'An aeronautical chart: chart cream, chart blue, airspace magenta, terrain tan.',
    fonts: {
      Display: ['Manrope', '@fontsource-variable/manrope'],
      Body: ['Source Sans 3', '@fontsource-variable/source-sans-3'],
      Mono: ['Roboto Mono', '@fontsource-variable/roboto-mono'],
    },
  },
  tarmac: {
    intent: 'Industrial neutrals: concrete, asphalt, safety yellow on surfaces only.',
    fonts: {
      Display: ['Archivo', '@fontsource-variable/archivo'],
      Body: ['Karla', '@fontsource-variable/karla'],
      Mono: ['Fira Code', '@fontsource-variable/fira-code'],
    },
  },
  coastal: {
    intent: 'The California shoreline: fog paper, ocean teal, sunset coral, dune sand.',
    fonts: {
      Display: ['Lora', '@fontsource-variable/lora'],
      Body: ['Nunito Sans', '@fontsource-variable/nunito-sans'],
      Mono: ['Source Code Pro', '@fontsource-variable/source-code-pro'],
    },
  },
  slate: {
    intent: 'Cool corporate: slate blue-gray, amber emphasis, a teal supporting hue.',
    fonts: {
      Display: ['Merriweather', '@fontsource-variable/merriweather'],
      Body: ['Work Sans', '@fontsource-variable/work-sans'],
      Mono: ['DM Mono', '@fontsource/dm-mono'],
    },
  },
  meridian: {
    intent: 'High-contrast civic: white, navy, burnt orange, one typeface throughout.',
    fonts: {
      Display: ['Libre Franklin', '@fontsource-variable/libre-franklin'],
      Body: ['Libre Franklin', '@fontsource-variable/libre-franklin'],
      Mono: ['Roboto Mono', '@fontsource-variable/roboto-mono'],
    },
  },
  'monterey-night': {
    intent: 'Charcoal dark: sea green primary, amber accent, a cool blue support.',
    fonts: {
      Display: ['Sora', '@fontsource-variable/sora'],
      Body: ['Inter', '@fontsource-variable/inter'],
      Mono: ['JetBrains Mono', '@fontsource-variable/jetbrains-mono'],
    },
  },
  granite: {
    intent: 'Near-monochrome: white, near-black, grays, and one blue for links.',
    fonts: {
      Display: ['Inter Tight', '@fontsource-variable/inter-tight'],
      Body: ['Inter', '@fontsource-variable/inter'],
      Mono: ['Geist Mono', '@fontsource-variable/geist-mono'],
    },
  },
};

/** The palette swatches the gallery prints, in the order a theme declares them. */
const SWATCHES = [
  '--color-bg',
  '--color-bg-raised',
  '--color-bg-sunken',
  '--color-fg',
  '--color-primary',
  '--color-primary-fg',
  '--color-primary-hover',
  '--color-accent',
  '--color-secondary',
  '--color-rule',
  '--color-rule-strong',
  '--color-muted',
  '--color-ok',
  '--color-warn',
  '--color-bad',
  '--color-focus',
];

/** Reads one theme file and returns its `--color-*` declarations. */
async function readPalette(slug) {
  const css = await readFile(join(STYLES, 'themes', `${slug}.css`), 'utf8');
  const palette = {};
  for (const [, name, value] of css.matchAll(/(--color-[\w-]+)\s*:\s*([^;]+);/g)) {
    palette[name] = value.trim();
  }
  return palette;
}

/** Signs the demo member in, leaving the session on `context`. */
async function signIn(page) {
  await page.goto(`${BASE_URL}/portal/login`, { waitUntil: 'networkidle' });
  await page.getByLabel(/email/i).fill(EMAIL);
  await page.getByLabel(/password/i).fill(PASSWORD);
  await page.getByRole('button', { name: /log in|sign in/i }).click();
  await page.waitForURL(/\/portal\/?$/, { timeout: 20000 });
}

/** The URL of the first public page in the top navigation that is not the home page. */
async function findInnerPage(page) {
  await page.goto(BASE_URL, { waitUntil: 'networkidle' });
  const hrefs = await page.$$eval('header a[href^="/"]', (links) =>
    links.map((link) => link.getAttribute('href') ?? ''),
  );
  const inner = hrefs.find((href) => href !== '/' && !href.startsWith('/portal'));
  return inner ?? '/';
}

/** Applies `slug` to `<html>` and waits for the theme's webfonts to arrive. */
async function applyTheme(page, slug) {
  await page.evaluate((theme) => {
    document.documentElement.dataset.theme = theme;
  }, slug);
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(300);
}

/** Captures one page at `viewport` and writes it to `path`. */
async function shoot(page, url, slug, viewport, path) {
  await page.setViewportSize(viewport);
  await page.goto(url, { waitUntil: 'networkidle' });
  await applyTheme(page, slug);
  await page.screenshot({ path, animations: 'disabled' });
}

/** Escapes text for safe interpolation into the gallery's HTML. */
function escapeHtml(text) {
  return String(text).replace(
    /[&<>"']/g,
    (char) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char] ?? char,
  );
}

/** One theme's contrast rows as an HTML table. */
function contrastTable(rows) {
  const body = rows
    .map((row) => {
      const over = row.over === null ? '' : ` over ${row.over.replace('--color-', '')}`;
      const pair = `${row.fg.replace('--color-', '')} on ${row.bg.replace('--color-', '')}${over}`;
      const verdict = row.passes ? 'pass' : 'fail';
      return `<tr class="${verdict}"><td>${escapeHtml(pair)}</td><td>${row.ratio.toFixed(
        2,
      )}:1</td><td>${row.required}:1</td><td>${verdict}</td></tr>`;
    })
    .join('\n');
  return `<table class="contrast"><thead><tr><th>Pair</th><th>Ratio</th><th>Needs</th><th></th></tr></thead><tbody>${body}</tbody></table>`;
}

/** One theme's palette strip. */
function paletteStrip(palette) {
  return SWATCHES.filter((name) => palette[name] !== undefined)
    .map(
      (name) =>
        `<div class="swatch"><span class="chip" style="background:${escapeHtml(
          palette[name],
        )}"></span><code>${escapeHtml(name.replace('--color-', ''))}</code><code>${escapeHtml(
          palette[name],
        )}</code></div>`,
    )
    .join('\n');
}

/** The fonts table for one theme. */
function fontTable(fonts) {
  const rows = Object.entries(fonts)
    .map(
      ([role, [family, pkg]]) =>
        `<tr><td>${escapeHtml(role)}</td><td>${escapeHtml(family)}</td><td><code>${escapeHtml(
          pkg,
        )}</code></td></tr>`,
    )
    .join('\n');
  return `<table class="fonts"><thead><tr><th>Role</th><th>Family</th><th>Package</th></tr></thead><tbody>${rows}</tbody></table>`;
}

/** The whole self-contained gallery page. */
function galleryHtml(sections) {
  const nav = sections
    .map(({ slug }) => `<a href="#${escapeHtml(slug)}">${escapeHtml(slug)}</a>`)
    .join('\n');
  const body = sections
    .map(({ slug, intent, palette, fonts, rows, packages }) => {
      const thumbs = [...SHOTS, { file: 'mobile-home.png', label: 'Home at 420px' }]
        .map(
          ({ file, label }) =>
            `<figure><a href="${escapeHtml(slug)}/${file}"><img src="${escapeHtml(
              slug,
            )}/${file}" alt="${escapeHtml(`${slug}: ${label}`)}" loading="lazy"></a><figcaption>${escapeHtml(
              label,
            )}</figcaption></figure>`,
        )
        .join('\n');
      return `
<section id="${escapeHtml(slug)}">
  <h2>${escapeHtml(slug)}</h2>
  <p class="intent">${escapeHtml(intent)}</p>
  <div class="shots">${thumbs}</div>
  <h3>Palette</h3>
  <div class="palette">${paletteStrip(palette)}</div>
  <h3>Fonts</h3>
  ${fontTable(fonts)}
  <h3>Contrast (WCAG 2.1 AA)</h3>
  ${contrastTable(rows)}
  <h3>Reproduce</h3>
  <ul class="reproduce">
    <li>Theme file: <code>frontend/src/styles/themes/${escapeHtml(slug)}.css</code></li>
    <li>Attribute the server renders: <code>&lt;html data-theme="${escapeHtml(slug)}"&gt;</code></li>
    <li>Select it in Wagtail: <strong>Settings &rarr; Site settings &rarr; Theme</strong>, then save.</li>
    <li>Preview without saving (website or system administrator):
      <code>https://&lt;your-site&gt;/?theme=${escapeHtml(slug)}</code></li>
    <li>Font packages: <code>${escapeHtml(packages.join(' '))}</code></li>
  </ul>
</section>`;
    })
    .join('\n');

  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CalDART theme previews</title>
<style>
  :root { color-scheme: light; }
  body { margin: 0; font: 16px/1.6 -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         color: #16181c; background: #f7f7f6; }
  header { padding: 32px 24px 16px; border-bottom: 1px solid #dcdcd8; background: #fff; }
  h1 { margin: 0 0 8px; font-size: 28px; }
  header p { margin: 0 0 16px; max-width: 70ch; color: #55595f; }
  nav { display: flex; flex-wrap: wrap; gap: 8px; }
  nav a { padding: 4px 10px; border: 1px solid #cfcfca; border-radius: 2px;
          text-decoration: none; color: #16181c; font-size: 14px; }
  nav a:hover { background: #eceae5; }
  main { padding: 0 24px 64px; }
  section { padding: 32px 0; border-bottom: 1px solid #dcdcd8; }
  h2 { margin: 0 0 4px; font-size: 24px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
  h3 { margin: 28px 0 8px; font-size: 15px; text-transform: uppercase; letter-spacing: .08em;
       color: #55595f; }
  .intent { margin: 0; color: #55595f; }
  .shots { display: flex; flex-wrap: wrap; align-items: flex-start; gap: 16px; margin-top: 20px; }
  figure { margin: 0; }
  /* Cap the height, not the width, so the 420px-wide mobile shot sits in the
     same row as the 1440px ones instead of towering over them. */
  figure img { display: block; max-width: 340px; max-height: 236px; width: auto;
               height: auto; border: 1px solid #cfcfca; background: #fff; }
  figcaption { font-size: 13px; color: #55595f; padding-top: 4px; }
  .palette { display: flex; flex-wrap: wrap; gap: 8px; }
  .swatch { display: flex; align-items: center; gap: 6px; border: 1px solid #dcdcd8;
            background: #fff; padding: 4px 8px; font-size: 12px; }
  .chip { width: 18px; height: 18px; border: 1px solid #b6b6b0; display: inline-block; }
  table { border-collapse: collapse; font-size: 13px; background: #fff; }
  th, td { border: 1px solid #dcdcd8; padding: 4px 10px; text-align: left; }
  th { background: #f0efec; font-weight: 600; }
  tr.fail td { background: #fde8e6; }
  code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12.5px; }
  ul.reproduce { margin: 0; padding-left: 20px; max-width: 90ch; }
  ul.reproduce li { margin-bottom: 4px; }
</style>
</head>
<body>
<header>
  <h1>CalDART theme previews</h1>
  <p>Every theme shipped in <code>frontend/src/styles/themes/</code>, shot against the seeded
     demo site. Click a thumbnail for the full-size PNG. Contrast ratios come from
     <code>frontend/scripts/theme-contrast.mjs</code>, which <code>make lint</code> runs.</p>
  <nav>${nav}</nav>
</header>
<main>${body}</main>
</body>
</html>
`;
}

/** The same information as the gallery, in Markdown. */
function readmeMarkdown(sections) {
  const lines = [
    '# CalDART theme previews',
    '',
    'Every theme shipped in `frontend/src/styles/themes/`, shot against the seeded demo site.',
    'Open `index.html` in a browser for the clickable gallery.',
    '',
    'Regenerate: start a seeded server the way `make e2e` does, then',
    '`cd frontend && npm run theme-previews`.',
    '',
  ];
  for (const { slug, intent, palette, fonts, rows, packages } of sections) {
    lines.push(`## ${slug}`, '', intent, '');
    lines.push('| Shot | File |', '| --- | --- |');
    for (const { file, label } of [...SHOTS, { file: 'mobile-home.png', label: 'Home at 420px' }]) {
      lines.push(`| ${label} | \`${slug}/${file}\` |`);
    }
    lines.push('', '### Palette', '', '| Token | Value |', '| --- | --- |');
    for (const name of SWATCHES) {
      if (palette[name] !== undefined) lines.push(`| \`${name}\` | \`${palette[name]}\` |`);
    }
    lines.push('', '### Fonts', '', '| Role | Family | Package |', '| --- | --- | --- |');
    for (const [role, [family, pkg]] of Object.entries(fonts)) {
      lines.push(`| ${role} | ${family} | \`${pkg}\` |`);
    }
    lines.push(
      '',
      '### Contrast (WCAG 2.1 AA)',
      '',
      '| Pair | Ratio | Needs | |',
      '| --- | --- | --- | --- |',
    );
    for (const row of rows) {
      const over = row.over === null ? '' : ` over ${row.over.replace('--color-', '')}`;
      const pair = `${row.fg.replace('--color-', '')} on ${row.bg.replace('--color-', '')}${over}`;
      lines.push(
        `| ${pair} | ${row.ratio.toFixed(2)}:1 | ${row.required}:1 | ${row.passes ? 'pass' : 'FAIL'} |`,
      );
    }
    lines.push(
      '',
      '### Reproduce',
      '',
      `- Theme file: \`frontend/src/styles/themes/${slug}.css\``,
      `- Attribute the server renders: \`<html data-theme="${slug}">\``,
      '- Select it in Wagtail: **Settings -> Site settings -> Theme**, then save.',
      `- Preview without saving, as a website or system administrator: \`https://<your-site>/?theme=${slug}\``,
      `- Font packages: \`npm install ${packages.join(' ')}\``,
      '',
    );
  }
  return `${lines.join('\n')}\n`;
}

async function main() {
  const audit = auditThemes();
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: DESKTOP, deviceScaleFactor: 1 });
  const page = await context.newPage();

  const innerPath = await findInnerPage(page);
  await signIn(page);

  // The gallery reads best in the order the themes were designed in, not the
  // alphabetical order the audit walks the directory in.
  const order = Object.keys(THEME_NOTES);
  const ordered = [...audit].sort((a, b) => order.indexOf(a.slug) - order.indexOf(b.slug));

  const sections = [];
  for (const { slug, rows } of ordered) {
    const notes = THEME_NOTES[slug];
    if (notes === undefined) throw new Error(`no gallery notes for theme ${slug}`);
    const dir = join(OUT_DIR, slug);
    await mkdir(dir, { recursive: true });

    for (const shot of SHOTS) {
      const path = shot.path ?? innerPath;
      await shoot(page, `${BASE_URL}${path}`, slug, DESKTOP, join(dir, shot.file));
    }
    await shoot(page, `${BASE_URL}/`, slug, MOBILE, join(dir, 'mobile-home.png'));

    sections.push({
      slug,
      intent: notes.intent,
      fonts: notes.fonts,
      packages: [...new Set(Object.values(notes.fonts).map(([, pkg]) => pkg))],
      palette: await readPalette(slug),
      rows,
    });
    process.stdout.write(`shot ${slug}\n`);
  }

  await browser.close();
  await writeFile(join(OUT_DIR, 'index.html'), galleryHtml(sections), 'utf8');
  await writeFile(join(OUT_DIR, 'README.md'), readmeMarkdown(sections), 'utf8');
  process.stdout.write(`\nGallery: ${join(OUT_DIR, 'index.html')}\n`);
}

await main();
