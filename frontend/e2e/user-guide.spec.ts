/**
 * The user guide at `/docs/` shows each reader the screens their roles reach.
 *
 * A page restricted to some roles redirects anyone else to the guide's front page,
 * and the sidebar leaves out every page the reader cannot open. A plain member keeps
 * the three captions and the member screens; the system administrator sees every
 * group. The search index the server hands a member names none of the pages they
 * cannot open, so their search finds nothing that only those pages say.
 */
import { expect, test } from '@playwright/test';
import type { Locator, Page } from '@playwright/test';

import { DEMO, signIn } from './helpers';

/** The groups of screens a member's roles never reach, by their directory in the guide. */
const ADMINISTRATOR_GROUPS = ['admin', 'finance', 'website'] as const;

/** The parts of Sphinx's search index these tests read. */
interface SearchIndex {
  docnames: string[];
  terms: Record<string, number | number[]>;
}

/** What Sphinx wraps the search index's JSON in. */
const INDEX_OPEN = 'Search.setIndex(';

/** Open the guide's front page and return its sidebar. */
async function openGuide(page: Page): Promise<Locator> {
  await page.goto('docs/');
  return page.locator('.sidebar-tree');
}

/** True when `docname` is a page in one of the groups a member's roles never reach. */
function isAdministratorPage(docname: string): boolean {
  return ADMINISTRATOR_GROUPS.some((group) => docname.startsWith(`${group}/`));
}

/** The search index the guide serves the signed-in reader of `page`. */
async function readSearchIndex(page: Page): Promise<SearchIndex> {
  const response = await page.request.get('docs/searchindex.js');
  expect(response.ok()).toBe(true);
  const text = (await response.text()).trim();
  expect(text.startsWith(INDEX_OPEN)).toBe(true);
  return JSON.parse(text.slice(INDEX_OPEN.length, -1)) as SearchIndex;
}

/**
 * A word of six letters or more that the index finds on two or more pages, all of them
 * administrator pages, or undefined. The index holds stems, so the caller confirms that
 * the system administrator's search finds the word before relying on it.
 */
function administratorOnlyWord(index: SearchIndex): string | undefined {
  return Object.entries(index.terms)
    .filter(([word]) => /^[a-z]{6,}$/.test(word))
    .map(([word, found]) => ({ word, pages: Array.isArray(found) ? found : [found] }))
    .filter(({ pages }) => pages.length > 1)
    .find(({ pages }) => pages.every((n) => isAdministratorPage(index.docnames[n] ?? '')))?.word;
}

/** Search the guide for `word` and return the sentence Sphinx closes the search with. */
async function searchSummary(page: Page, word: string): Promise<Locator> {
  await page.goto(`docs/search/?q=${word}`);
  const summary = page.locator('#search-results p.search-summary');
  await expect(summary).toBeVisible();
  return summary;
}

/** The guide groups the links in `tree` lead into, such as `member` or `admin`. */
async function linkedGroups(tree: Locator): Promise<Set<string>> {
  const paths = await tree
    .locator('a')
    .evaluateAll((anchors) =>
      anchors.map((anchor) => new URL((anchor as HTMLAnchorElement).href).pathname),
    );
  const groups = paths
    .map((path) => /\/docs\/([^/]+)\//.exec(path)?.[1])
    .filter((group) => group !== undefined);
  return new Set(groups);
}

test('a member opening an administrator page is sent to the guide index', async ({ page }) => {
  await signIn(page, DEMO.member);
  await page.goto('docs/admin/health-database/');

  await expect(page).toHaveURL(/\/docs\/$/);
  await expect(page.getByRole('heading', { name: 'User guide', level: 1 })).toBeVisible();
});

test("a member's sidebar lacks the administrator sections", async ({ page }) => {
  await signIn(page, DEMO.member);
  const tree = await openGuide(page);

  await expect(tree.locator('.caption-text')).toHaveText(['Start here', 'Screens', 'Reference']);
  const groups = await linkedGroups(tree);
  expect(groups.has('member')).toBe(true);
  expect(ADMINISTRATOR_GROUPS.filter((group) => groups.has(group))).toEqual([]);
});

test('the system administrator sees every section of the sidebar', async ({ page }) => {
  await signIn(page, DEMO.sysadmin);
  const tree = await openGuide(page);

  const groups = await linkedGroups(tree);
  expect(ADMINISTRATOR_GROUPS.filter((group) => groups.has(group))).toEqual([
    ...ADMINISTRATOR_GROUPS,
  ]);
});

test('the system administrator opens an administrator page', async ({ page }) => {
  await signIn(page, DEMO.sysadmin);
  await page.goto('docs/admin/health-database/');

  await expect(page).toHaveURL(/\/docs\/admin\/health-database\/$/);
});

test("a member's search index names no administrator page", async ({ page }) => {
  await signIn(page, DEMO.member);
  const index = await readSearchIndex(page);

  expect(index.docnames).toContain('member/profile');
  expect(index.docnames.filter(isAdministratorPage)).toEqual([]);
});

test('a word only administrator pages carry finds nothing for a member', async ({ page }) => {
  await signIn(page, DEMO.sysadmin);
  const word = administratorOnlyWord(await readSearchIndex(page));
  expect(word).toBeDefined();
  const adminSummary = await searchSummary(page, word ?? '');
  await expect(adminSummary).toHaveText(/^Search finished, found/);

  await page.context().clearCookies();
  await signIn(page, DEMO.member);
  const memberSummary = await searchSummary(page, word ?? '');

  await expect(memberSummary).toHaveText(/did not match any documents/);
  await expect(page.locator('ul.search > li')).toHaveCount(0);
});
