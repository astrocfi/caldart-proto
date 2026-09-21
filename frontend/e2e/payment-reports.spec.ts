/**
 * Flow D in `docs/demo-walkthrough.rst`: an account administrator sees
 * payments per month and per year, and downloads the CSV.
 */
import { readFile } from 'node:fs/promises';

import { expect, test } from '@playwright/test';

import { DEMO, signIn } from './helpers';

test('an account administrator reads the monthly and yearly totals and exports them', async ({
  page,
}) => {
  await signIn(page, DEMO.accountAdmin);

  await page
    .getByRole('navigation', { name: 'Portal sections' })
    .getByRole('link', { name: 'Payments' })
    .click();
  await expect(page).toHaveURL(/\/portal\/admin\/payments/);

  // The three headline tiles.
  await expect(page.getByText('This month')).toBeVisible();
  await expect(page.getByText('Year to date')).toBeVisible();
  await expect(page.getByText('Last 12 months')).toBeVisible();

  // Month is the default grouping; the table has one row per month.
  const periodTable = page.locator('.period-table');
  await expect(periodTable.getByRole('columnheader', { name: 'Month' })).toBeVisible();
  const monthRows = await periodTable.locator('tbody tr').count();
  expect(monthRows).toBeGreaterThan(0);

  // Switching to Year regroups the same money into fewer rows.
  await page
    .getByRole('group', { name: 'Group payments by' })
    .getByRole('button', { name: 'Year' })
    .click();
  await expect(periodTable.getByRole('columnheader', { name: 'Year' })).toBeVisible();
  const yearRows = await periodTable.locator('tbody tr').count();
  expect(yearRows).toBeGreaterThan(0);
  expect(yearRows).toBeLessThanOrEqual(monthRows);

  // The ledger below it lists individual payments with a status chip.
  await expect(page.getByRole('heading', { name: 'All payments' })).toBeVisible();
  await expect(page.locator('table').last().locator('tbody tr').first()).toBeVisible();

  // Export CSV downloads the same rows the filters describe.
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('link', { name: 'Export CSV' }).click(),
  ]);
  expect(download.suggestedFilename()).toMatch(/\.csv$/);
  const csv = await readFile(await download.path(), 'utf8');
  expect(csv.split('\n')[0]).toContain('paid_on,name,email,plan');
  expect(csv.trim().split('\n').length).toBeGreaterThan(1);
});

test('a filtered export carries the filter', async ({ page }) => {
  await signIn(page, DEMO.accountAdmin);
  await page.goto('/portal/admin/payments');

  await page.getByLabel('Provider').selectOption('mock');
  await expect(page.getByRole('link', { name: 'Export CSV' })).toHaveAttribute(
    'href',
    /provider=mock/,
  );
});

test('a plain member cannot reach the payment reports', async ({ page }) => {
  await signIn(page, DEMO.member);
  await page.goto('/portal/admin/payments');
  await expect(page.getByRole('heading', { name: 'Not allowed' })).toBeVisible();
});
