/**
 * The finance area's reporting tabs, as a treasurer uses them: reconciling a
 * period against a statement, reading the year's giving, and administering the
 * standing renewal authorities.  The last test runs the renewal scan from the
 * system page, which is a system administrator's screen, not a treasurer's.
 */
import { expect, test } from '@playwright/test';
import type { Locator, Page } from '@playwright/test';

import { DEMO, signIn } from './helpers';

/** The body rows of the one table in a region with this caption. */
function bodyRows(page: Page, caption: RegExp): Locator {
  return page
    .locator('table')
    .filter({ has: page.locator('caption', { hasText: caption }) })
    .locator('tbody tr');
}

test('a treasurer reconciles a period and exports it', async ({ page }) => {
  await signIn(page, DEMO.treasurer);
  await page.goto('/portal/admin/payments/reconciliation');

  await expect(page.getByRole('heading', { name: 'Reconciliation', level: 1 })).toBeVisible();

  const byMonth = bodyRows(page, /Takings by month/);
  await expect(byMonth.first()).toBeVisible();
  const monthCount = await byMonth.count();
  expect(monthCount).toBeGreaterThan(1);

  // The same money regrouped: one row per provider that took any of it, which
  // is necessarily fewer rows than the months it was spread over.
  await page
    .getByRole('group', { name: 'Group takings by' })
    .getByRole('button', { name: 'Provider' })
    .click();
  const byProvider = bodyRows(page, /Takings by provider/);
  // The table keeps the rows it had while the regrouped ones are fetched, so
  // wait for a provider name in the first cell before counting.
  await expect(byProvider.first()).toContainText(/Stripe|PayPal|Test|By hand/);
  expect(await byProvider.count()).toBeLessThan(monthCount);

  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('link', { name: 'Export CSV' }).click(),
  ]);
  expect(download.suggestedFilename()).toMatch(/^caldart-reconciliation-.+\.csv$/);
});

/**
 * Show the contributions of `year` and wait for the table to settle, either on
 * rows or on the empty state.
 */
async function contributionRows(page: Page, year: number): Promise<Locator> {
  await page.getByLabel('Year').selectOption(String(year));
  const rows = bodyRows(page, new RegExp(`Contributions in ${year}`));
  await expect(rows.first().or(page.getByText('No contributions that year'))).toBeVisible();
  return rows;
}

test('a treasurer reads the year of giving and can print a statement', async ({ page }) => {
  await signIn(page, DEMO.treasurer);
  await page.goto('/portal/admin/payments/contributions');

  await expect(page.getByRole('heading', { name: 'Contributions', level: 1 })).toBeVisible();

  const thisYear = new Date().getFullYear();
  await expect(page.getByLabel('Year')).toHaveValue(String(thisYear));

  // The seed spreads its payments over the past two years, so early in January
  // the current year may hold none of them; last year always holds some.
  let rows = await contributionRows(page, thisYear);
  if ((await rows.count()) === 0) rows = await contributionRows(page, thisYear - 1);

  await expect(rows.first()).toBeVisible();
  await expect(rows.first().getByRole('link', { name: 'Statement' })).toHaveAttribute(
    'href',
    /\/statements\/\d{4}\.pdf$/,
  );
});

test('a treasurer turns a stalled renewal off', async ({ page }) => {
  await signIn(page, DEMO.treasurer);
  await page.goto('/portal/admin/payments/renewals');

  await expect(page.getByRole('heading', { name: 'Renewals', level: 1 })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Recent charges' })).toBeVisible();

  await page.getByLabel('Auto-renewal status').selectOption('paused');
  const paused = bodyRows(page, /renewals?$/);
  await expect(paused).toHaveCount(1);
  await expect(paused.first()).toContainText('Paused');

  await paused.first().getByRole('button', { name: 'Turn off' }).click();
  await paused.first().getByRole('button', { name: 'Yes, turn it off' }).click();

  // The mandate is canceled rather than deleted, so it leaves the paused list.
  await expect(page.getByText('No renewals match')).toBeVisible();
  await page.getByLabel('Auto-renewal status').selectOption('canceled');
  await expect(bodyRows(page, /renewals?$/).first()).toContainText('Off');
});

test('a system administrator rehearses the renewal scan', async ({ page }) => {
  await signIn(page, DEMO.sysadmin);
  await page.goto('/portal/system');

  const panel = page
    .locator('section.card')
    .filter({ has: page.getByRole('heading', { name: 'Automatic renewals' }) });
  await expect(panel.getByLabel('Dry run (charge nothing)')).toBeChecked();
  await panel.getByRole('button', { name: 'Run now' }).click();

  await expect(panel.getByRole('status').filter({ hasText: /^Would notice / })).toBeVisible();
});

test('a plain member reaches none of the finance reports', async ({ page }) => {
  await signIn(page, DEMO.member);
  await page.goto('/portal/admin/payments/reconciliation');
  await expect(page.getByRole('heading', { name: 'Not allowed' })).toBeVisible();
});
