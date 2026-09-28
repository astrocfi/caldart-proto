// Renders every layout mockup to desktop and mobile PNGs.
//
//   node layout-previews/render.mjs [slug ...]
//
// Uses the Playwright the e2e suite installs under frontend/node_modules.
// Without arguments it renders every directory that holds an index.html.
import { readdirSync, existsSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = dirname(fileURLToPath(import.meta.url));
const require = createRequire(resolve(root, '../frontend/package.json'));
const { chromium } = require('playwright');
const wanted = process.argv.slice(2);
const slugs = readdirSync(root, { withFileTypes: true })
  .filter((entry) => entry.isDirectory() && existsSync(join(root, entry.name, 'index.html')))
  .map((entry) => entry.name)
  .filter((slug) => wanted.length === 0 || wanted.includes(slug));

const shots = [
  { name: 'desktop', width: 1440, height: 900 },
  { name: 'mobile', width: 420, height: 860 },
];

const browser = await chromium.launch();
for (const slug of slugs) {
  const url = pathToFileURL(resolve(root, slug, 'index.html')).href;
  for (const shot of shots) {
    const page = await browser.newPage({ viewport: { width: shot.width, height: shot.height } });
    await page.goto(url);
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({ path: join(root, slug, `${shot.name}.png`), fullPage: true });
    await page.close();
  }
  console.log(`rendered ${slug}`);
}
await browser.close();
