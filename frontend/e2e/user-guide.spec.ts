/**
 * The user guide at `/docs/` shows each reader the screens their roles reach.
 *
 * A page restricted to some roles redirects anyone else to the guide's front page,
 * and the sidebar leaves out every page the reader cannot open. A plain member keeps
 * the three captions and the member screens; the system administrator sees every
 * group.
 */
import { expect, test } from '@playwright/test';
import type { Locator, Page } from '@playwright/test';

import { DEMO, signIn } from './helpers';

/** The groups of screens a member's roles never reach, by their directory in the guide. */
const ADMINISTRATOR_GROUPS = ['admin', 'finance', 'website'] as const;

/** Open the guide's front page once its sidebar has been trimmed to the reader's roles. */
async function openGuide(page: Page): Promise<Locator> {
  await page.goto('docs/');
  await expect(page.locator('html')).not.toHaveClass(/guide-roles-pending/);
  return page.locator('.sidebar-tree');
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
