// Builds index.html (the clickable gallery) from layouts.json.
//
//   node layout-previews/build-index.mjs
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = dirname(fileURLToPath(import.meta.url));
const layouts = JSON.parse(readFileSync(join(root, 'layouts.json'), 'utf8'));

const escape = (text) =>
  text.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');

const section = (layout, index) => `
<section id="${layout.slug}">
  <h2>${index + 1}. ${escape(layout.title)} <code>${layout.slug}</code></h2>
  <p class="model">Modeled on: ${escape(layout.modeledOn)}</p>
  <p class="fonts">Type: ${escape(layout.fonts)}</p>
  <div class="shots">
    <figure><a href="${layout.slug}/desktop.png"><img class="desktop" src="${layout.slug}/desktop.png" alt="${escape(layout.title)} at 1440px"></a><figcaption>1440px (top of the page; click for all of it)</figcaption></figure>
    <figure><a href="${layout.slug}/mobile.png"><img class="mobile" src="${layout.slug}/mobile.png" alt="${escape(layout.title)} at 420px"></a><figcaption>420px</figcaption></figure>
  </div>
  <p><a href="${layout.slug}/index.html">Open the live mockup</a></p>
  <h3>Structure, top to bottom</h3>
  <ol>${layout.structure.map((line) => `<li>${escape(line)}</li>`).join('')}</ol>
</section>`;

const html = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CalDART home page layouts</title>
<style>
  body { margin: 0; font: 15px/1.5 "Liberation Sans", Arial, sans-serif; color: #111; background: #fff; }
  header, main { padding: 0 24px; max-width: 1200px; }
  header { padding-top: 24px; }
  h1 { font-size: 24px; margin: 0 0 6px; }
  header p { margin: 0 0 12px; max-width: 80ch; }
  nav ol { margin: 0; padding-left: 20px; columns: 2; }
  section { border-top: 2px solid #333; padding: 20px 0 28px; }
  h2 { font-size: 20px; margin: 0 0 4px; }
  h2 code { font-size: 14px; font-weight: normal; margin-left: 8px; color: #555; }
  h3 { font-size: 15px; margin: 18px 0 4px; }
  .model, .fonts { margin: 0; color: #444; }
  .shots { display: flex; flex-wrap: wrap; align-items: flex-start; gap: 16px; margin: 14px 0; }
  figure { margin: 0; }
  figure img { display: block; border: 1px solid #999; object-fit: cover; object-position: top; background: #fff; }
  figure img.desktop { width: 560px; height: 350px; max-width: 100%; }
  figure img.mobile { width: 140px; height: 350px; }
  figcaption { font-size: 13px; color: #444; }
  ol li { margin-bottom: 3px; }
  code { font-family: "Liberation Mono", monospace; }
</style>
</head>
<body>
<header>
  <h1>CalDART home page layouts</h1>
  <p>Ten page structures for the public home page, each a standalone mockup with the
     same copy (<code>shared/copy.md</code>). Thumbnails show the top of the full-page
     shot; click one for the whole page. <code>README.md</code> explains how to regenerate.</p>
  <nav><ol>${layouts.map((layout) => `<li><a href="#${layout.slug}">${escape(layout.title)}</a></li>`).join('')}</ol></nav>
</header>
<main>${layouts.map(section).join('\n')}
</main>
</body>
</html>
`;

writeFileSync(join(root, 'index.html'), html);
console.log(`wrote index.html for ${layouts.length} layouts`);
