#!/usr/bin/env node
/**
 * Screenshots every portal route each demo role can reach, and checks each with axe.
 *
 * It drives a real CalDART server with the seeded demo data -- `make screenshots`
 * starts one against its own database -- and, for each demo account in turn, signs in
 * and visits every route that account's roles admit at three viewports. Each visit is
 * a full-page screenshot written to `<out>/<role>/<route-slug>@<width>.png`. Where a
 * route has one, it also captures the first inline delete confirmation, the first
 * confirmation panel, the first panel opened from a button, and the first dialog, each
 * with `-<kind>` before the `@`, and then closes it again; nothing is ever confirmed,
 * so the seed is left as found.
 *
 * Nothing here is a list of routes. The paths and the roles each needs are read from
 * `src/portal/routes/*.tsx` (a `RequireRole` wraps the paths under it) and `src/portal/nav.ts`;
 * the demo accounts come from `backend/apps/accounts/seed.py`; the roles an account holds
 * come from the server. A route with an id in it (`admin/members/:id`) is opened at the
 * first record a screen the role already visited links to. The confirmation panels that
 * can be opened safely are those `src/portal/features` builds with `ConfirmButton`.
 *
 * `<out>/manifest.json` lists every shot with the final URL, whether the page held an
 * empty state, and any console errors; `<out>/axe.json` holds the axe violations by role
 * and route (checked at the widest viewport only).
 *
 * Environment:
 *   SCREENSHOTS_BASE_URL  server to shoot (default http://localhost:8031)
 *   SCREENSHOTS_OUT_DIR   where the shots are written (default ../screenshots)
 *   SCREENSHOTS_ROLES     comma-separated demo keys to shoot (default every account)
 *   SCREENSHOTS_WORKERS   roles shot at once (default 4)
 */

import { mkdir, readdir, readFile, rm, writeFile } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import AxeBuilder from '@axe-core/playwright';
import { chromium } from '@playwright/test';

const HERE = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HERE, '..');
const PORTAL = join(FRONTEND, 'src', 'portal');
const SEED = resolve(FRONTEND, '..', 'backend', 'apps', 'accounts', 'seed.py');

const BASE_URL = (process.env.SCREENSHOTS_BASE_URL ?? 'http://localhost:8031').replace(/\/+$/, '');
const OUT_DIR = process.env.SCREENSHOTS_OUT_DIR ?? resolve(FRONTEND, 'screenshots');
const ONLY_ROLES = (process.env.SCREENSHOTS_ROLES ?? '').split(',').filter(Boolean);
const WORKERS = Number(process.env.SCREENSHOTS_WORKERS ?? 4);

const PORTAL_PREFIX = '/portal';
const API_ME = '/api/v1/auth/me';
const TIMEZONE = 'America/Los_Angeles';
const NAVIGATION_TIMEOUT_MS = 30_000;
const SETTLE_MS = 400;
const STEP_TIMEOUT_MS = 5000;
const AXE_VIEWPORT = '1920';

const VIEWPORTS = [
  { width: 1920, height: 1080 },
  { width: 820, height: 1180 },
  { width: 390, height: 844 },
];

/** Routes a signed-out visitor reaches; the walker is for the signed-in ones. */
const PUBLIC_PATHS = new Set(['login', 'forgot-password', 'reset-password', 'verify-email']);
const JOIN_PATHS = /^join(\/|$)/;

/** The Delete-pair trigger: a button holding the trashcan icon. */
/** The button that backs out of a delete confirmation: `Keep`, or `Keep it` on the aircraft record. */
const KEEP = /^Keep( it)?$/;

const TRASHCAN = 'button:has(svg path[d="M4 7h16"])';

/**
 * Per-route extra steps beyond the generic ones. A route matching `pattern` also opens
 * the dialog whose trigger button is named `dialogTrigger`.
 */
const EXTRA_STEPS = [{ pattern: /^bulk-email\/sent\/:id$/, dialogTrigger: 'View copy' }];

/** A directory's `.tsx` files that are not tests, with their text. */
async function readSources(dir) {
  const entries = await readdir(dir, { recursive: true, withFileTypes: true });
  const files = entries.filter(
    (e) => e.isFile() && /\.tsx?$/.test(e.name) && !/\.test\./.test(e.name),
  );
  return Promise.all(
    files.map(async (e) => ({
      name: e.name,
      text: await readFile(join(e.parentPath, e.name), 'utf8'),
    })),
  );
}

/**
 * The demo accounts as `{ key, email }`, read from the seed's `DEMO_ACCOUNTS`, and the
 * shared password.
 */
async function readAccounts() {
  const text = await readFile(SEED, 'utf8');
  const accounts = [...text.matchAll(/\(\s*"(\w+)",\s*"([^"]+@[^"]+)",/g)].map((m) => ({
    key: m[1],
    email: m[2],
  }));
  const password = /^DEMO_PASSWORD = "([^"]+)"/m.exec(text)?.[1];
  if (accounts.length === 0 || password === undefined) {
    throw new Error(`Found no demo accounts or no password in ${SEED}`);
  }
  return { accounts, password };
}

/**
 * Every private route as `{ path, roles }` (`roles` empty for any signed-in user).
 *
 * A route file's `path:` entries take the roles of the nearest `roles={[...]}` above
 * them; a `Navigate` redirect is not a screen. The nav's entries add what no route file
 * names, such as the index route behind `/`.
 */
async function readRoutes() {
  const files = (await readSources(join(PORTAL, 'routes'))).filter(
    (f) => !/^(index|auth|join|not-found)\./.test(f.name),
  );
  const found = new Map();
  for (const { text } of files) {
    let roles = [];
    for (const m of text.matchAll(
      /roles=\{\[([^\]]*)\]\}|\bpath:\s*'([^']+)'(?!,\s*element: <Navigate)/g,
    )) {
      if (m[1] !== undefined) {
        roles = [...m[1].matchAll(/'(\w+)'/g)].map((r) => r[1]);
      } else if (!PUBLIC_PATHS.has(m[2]) && !JOIN_PATHS.test(m[2])) {
        found.set(`/${m[2]}`, { path: `/${m[2]}`, roles });
      }
    }
  }
  const nav = await readFile(join(PORTAL, 'nav.ts'), 'utf8');
  for (const m of nav.matchAll(/to:\s*'([^']+)'[\s\S]*?roles:\s*\[([^\]]*)\]/g)) {
    if (!found.has(m[1])) {
      found.set(m[1], {
        path: m[1],
        roles: [...m[2].matchAll(/'(\w+)'/g)].map((r) => r[1]),
      });
    }
  }
  return [...found.values()].sort((a, b) => a.path.localeCompare(b.path));
}

/** The labels of the `ConfirmButton`s the features define, whose triggers only open a panel. */
async function readConfirmLabels() {
  const sources = await readSources(join(PORTAL, 'features'));
  const labels = sources.flatMap(({ text }) =>
    [...text.matchAll(/<ConfirmButton\s[\s\S]{0,200}?\blabel="([^"]+)"/g)].map((m) => m[1]),
  );
  return [...new Set(labels)];
}

/** Whether `roles` (the account's) admit a route needing one of `required`. */
function isAdmitted(roles, required) {
  return (
    roles.includes('system_admin') ||
    required.length === 0 ||
    required.some((r) => roles.includes(r))
  );
}

function hasParameter(path) {
  return path.includes(':');
}

/** `/admin/members/:id` as `admin-members-id`; `/` as `dashboard`. */
function slugOf(path) {
  const slug = path.replace(/^\/|\/$/g, '').replace(/[/:]+/g, '-');
  return slug === '' ? 'dashboard' : slug;
}

/** The pattern an href must match to be a record of the parameterized route. */
function recordPattern(path) {
  const body = path
    .split('/')
    .map((segment) =>
      segment.startsWith(':') ? '\\d+' : segment.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'),
    )
    .join('/');
  return new RegExp(`^${PORTAL_PREFIX}${body}$`);
}

function parentPath(path) {
  return path.slice(0, path.lastIndexOf('/')) || '/';
}

/** Sign in through the portal's login form; throws when the form does not take. */
async function signIn(page, email, password) {
  await page.goto(`${BASE_URL}${PORTAL_PREFIX}/login`);
  await page.getByRole('textbox', { name: 'Email address' }).fill(email);
  await page.getByLabel(/^Password/).fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.waitForURL((url) => !url.pathname.endsWith('/login'), {
    timeout: NAVIGATION_TIMEOUT_MS,
  });
}

/** The roles the signed-in account holds, as the server reports them. */
async function readRoles(page) {
  const response = await page.request.get(`${BASE_URL}${API_ME}`);
  const body = await response.json();
  return body.roles;
}

/** Load `url` and wait for the screen to settle. */
async function open(page, url) {
  await page.goto(url, { timeout: NAVIGATION_TIMEOUT_MS });
  await page
    .waitForLoadState('networkidle', { timeout: NAVIGATION_TIMEOUT_MS })
    .catch(() => undefined);
  await page.waitForTimeout(SETTLE_MS);
}

/** The paths of every link on the page. */
function readHrefs(page) {
  return page.evaluate(() => [...document.querySelectorAll('a[href]')].map((a) => a.pathname));
}

/** Writes one shot and notes it in the manifest. */
async function shoot(page, context, kind) {
  const suffix = kind === undefined ? '' : `-${kind}`;
  const file = `${context.slug}${suffix}@${page.viewportSize().width}.png`;
  await page.screenshot({ path: join(OUT_DIR, context.role, file), fullPage: true });
  context.manifest.push({
    role: context.role,
    route: context.path,
    file: `${context.role}/${file}`,
    url: page.url(),
    empty: (await page.locator('.empty-state').count()) > 0,
    errors: [...context.errors],
  });
}

/**
 * Presses the first visible control the step's trigger names, shoots what it opens, and
 * closes it again. Does nothing when there is no such control or it opens nothing; a step
 * that fails is noted in `context.problems` and the page is left for the next load to reset.
 */
async function openAndShoot(page, context, step) {
  const trigger = step.trigger.filter({ visible: true }).first();
  // A step that cannot finish quickly is not going to; the next load resets the page.
  page.setDefaultTimeout(STEP_TIMEOUT_MS);
  try {
    if ((await trigger.count()) === 0 || !(await trigger.isEnabled())) return;
    await trigger.click();
    const opened = await step.opened
      .filter({ visible: true })
      .first()
      .waitFor()
      .then(
        () => true,
        () => false,
      );
    if (opened) {
      await page.waitForTimeout(SETTLE_MS);
      await shoot(page, context, step.kind);
    }
    await step.close(page);
  } catch (error) {
    context.problems.push(
      `${context.path} (${step.kind} at ${page.viewportSize().width}): ${error.message.split('\n')[0]}`,
    );
    await page.keyboard.press('Escape');
  } finally {
    page.setDefaultTimeout(NAVIGATION_TIMEOUT_MS);
  }
}

/** The extra captures for a screen: each leaves the page as it found it. */
function extraSteps(page, route, confirmLabels) {
  const steps = [
    {
      kind: 'delete',
      trigger: page.locator(TRASHCAN),
      opened: page.getByRole('button', { name: KEEP }),
      close: (p) => p.getByRole('button', { name: KEEP }).first().click(),
    },
    ...confirmLabels.map((label) => ({
      kind: 'confirm',
      trigger: page.getByRole('button', { name: label, exact: true }),
      opened: page.locator('section[aria-label]').getByRole('button', { name: 'Cancel' }),
      close: (p) =>
        p.locator('section[aria-label]').getByRole('button', { name: 'Cancel' }).first().click(),
    })),
    {
      kind: 'panel',
      trigger: page.locator('.panel-button__toggle'),
      opened: page.locator('.panel-button__panel'),
      close: (p) => p.locator('.panel-button__toggle').first().click(),
    },
  ];
  for (const extra of EXTRA_STEPS) {
    if (extra.pattern.test(route.path.replace(/^\//, ''))) {
      steps.push({
        kind: 'dialog',
        trigger: page.getByRole('button', { name: extra.dialogTrigger, exact: true }),
        opened: page.locator('dialog[open]'),
        close: (p) =>
          p.locator('dialog[open]').getByRole('button', { name: 'Close' }).first().click(),
      });
    }
  }
  return steps;
}

/**
 * Captures every shot of one route for one role, and its axe result.
 * Returns the axe violations, or `null` when axe was not run.
 */
async function captureRoute(page, context, route, confirmLabels) {
  const url = `${BASE_URL}${PORTAL_PREFIX}${route.visit}`;
  let violations = null;
  for (const viewport of VIEWPORTS) {
    await page.setViewportSize(viewport);
    await open(page, url);
    await shoot(page, context);
    if (String(viewport.width) === AXE_VIEWPORT) {
      const result = await new AxeBuilder({ page }).analyze();
      violations = result.violations.map((v) => ({
        id: v.id,
        impact: v.impact,
        help: v.help,
        nodes: v.nodes.length,
      }));
    }
    for (const step of extraSteps(page, route, confirmLabels)) {
      await openAndShoot(page, context, step);
    }
  }
  return violations;
}

/** Shoots every route one demo account can reach. */
async function shootRole(browser, account, password, routes, confirmLabels) {
  const result = { role: account.key, manifest: [], axe: {}, problems: [], routeCount: 0 };
  const browserContext = await browser.newContext({ timezoneId: TIMEZONE });
  const page = await browserContext.newPage();
  page.setDefaultTimeout(NAVIGATION_TIMEOUT_MS);
  const errors = [];
  page.on('pageerror', (error) => errors.push(`pageerror: ${error.message}`));
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(`console: ${message.text()}`);
  });
  try {
    await mkdir(join(OUT_DIR, account.key), { recursive: true });
    await signIn(page, account.email, password);
    const roles = await readRoles(page);
    const reachable = routes.filter((route) => isAdmitted(roles, route.roles));
    const staticRoutes = reachable.filter((route) => !hasParameter(route.path));
    const hrefsByPath = new Map();
    const seen = [];
    for (const route of [...staticRoutes, ...reachable.filter((r) => hasParameter(r.path))]) {
      const context = {
        role: account.key,
        slug: slugOf(route.path),
        path: route.path,
        manifest: result.manifest,
        problems: result.problems,
        errors,
      };
      errors.length = 0;
      let visit = route.path;
      if (hasParameter(route.path)) {
        const wanted = recordPattern(route.path);
        const candidates = [...(hrefsByPath.get(parentPath(route.path)) ?? []), ...seen];
        const record = candidates.find((href) => wanted.test(href));
        if (record === undefined) {
          result.problems.push(`${route.path}: no record to open`);
          continue;
        }
        visit = record.slice(PORTAL_PREFIX.length);
      }
      try {
        const violations = await captureRoute(page, context, { ...route, visit }, confirmLabels);
        result.routeCount += 1;
        result.axe[route.path] = violations ?? [];
        const hrefs = await readHrefs(page);
        hrefsByPath.set(route.path, hrefs);
        seen.push(...hrefs);
      } catch (error) {
        result.problems.push(`${route.path}: ${error.message.split('\n')[0]}`);
      }
    }
  } finally {
    await browserContext.close();
  }
  return result;
}

/** Runs `task` over `items`, `limit` at a time, returning the results in order. */
async function mapPool(items, limit, task) {
  const results = new Array(items.length);
  let next = 0;
  const workers = Array.from({ length: Math.min(limit, items.length) }, async () => {
    while (next < items.length) {
      const index = next++;
      results[index] = await task(items[index]);
    }
  });
  await Promise.all(workers);
  return results;
}

/** Prints the routes with violations, then the rules by how many routes break them. */
function printAxeSummary(results) {
  const rows = results.flatMap((r) =>
    Object.entries(r.axe).map(([route, violations]) => ({
      route,
      role: r.role,
      count: violations.length,
      ids: violations.map((v) => v.id).join(', '),
    })),
  );
  const failing = rows.filter((row) => row.count > 0);
  console.log(`\naxe: ${failing.length} of ${rows.length} role-route pages have violations\n`);
  console.table(
    failing.map(({ route, role, count, ids }) => ({ route, role, violations: count, rules: ids })),
  );
  const byRule = new Map();
  for (const result of results) {
    for (const violations of Object.values(result.axe)) {
      for (const v of violations) byRule.set(v.id, (byRule.get(v.id) ?? 0) + 1);
    }
  }
  console.table(
    [...byRule.entries()].sort((a, b) => b[1] - a[1]).map(([rule, pages]) => ({ rule, pages })),
  );
}

async function main() {
  const { accounts, password } = await readAccounts();
  const chosen =
    ONLY_ROLES.length === 0 ? accounts : accounts.filter((a) => ONLY_ROLES.includes(a.key));
  if (chosen.length === 0) throw new Error(`No demo account matches ${ONLY_ROLES.join(', ')}`);
  const routes = await readRoutes();
  const confirmLabels = await readConfirmLabels();

  await rm(OUT_DIR, { recursive: true, force: true });
  await mkdir(OUT_DIR, { recursive: true });
  const browser = await chromium.launch();
  let results;
  try {
    results = await mapPool(chosen, WORKERS, (account) =>
      shootRole(browser, account, password, routes, confirmLabels),
    );
  } finally {
    await browser.close();
  }

  const manifest = results.flatMap((r) => r.manifest);
  await writeFile(join(OUT_DIR, 'manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`);
  const axe = Object.fromEntries(results.map((r) => [r.role, r.axe]));
  await writeFile(join(OUT_DIR, 'axe.json'), `${JSON.stringify(axe, null, 2)}\n`);

  console.table(
    results.map((r) => ({
      role: r.role,
      routes: r.routeCount,
      shots: r.manifest.length,
      problems: r.problems.length,
    })),
  );
  for (const r of results) for (const problem of r.problems) console.warn(`${r.role}: ${problem}`);
  printAxeSummary(results);
  console.log(`\n${manifest.length} screenshots in ${OUT_DIR}`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
