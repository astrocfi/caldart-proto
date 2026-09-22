/**
 * Flow D in `docs/demo-walkthrough.rst`: an account administrator sees
 * payments per month and per year, and downloads the CSV.
 */
import { readFile } from 'node:fs/promises';

import { expect, test } from '@playwright/test';
import type { Locator, Page } from '@playwright/test';

import { DEMO, signIn } from './helpers';

/** The body rows of the by-period table — the header row is its own rowgroup. */
function periodRows(page: Page): Locator {
  return page
    .getByRole('region', { name: 'Payments by period' })
    .getByRole('rowgroup')
    .nth(1)
    .getByRole('row');
}

interface LedgerTotals {
  payments: number;
  months: number;
  years: number;
}

/**
 * Download the unfiltered CSV export and count what it holds.
 *
 * The export and the by-period summary are two different endpoints over the
 * same payments, so counting the CSV gives the summary's expected row counts
 * from outside the screen being tested.  The counts are read at the moment the
 * spec runs rather than from the seed, because an earlier spec in the same run
 * may have paid for a membership of its own.
 */
async function ledgerTotals(page: Page): Promise<LedgerTotals> {
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('link', { name: 'Export CSV' }).click(),
  ]);
  expect(download.suggestedFilename()).toMatch(/\.csv$/);
  const csv = await readFile(await download.path(), 'utf8');
  const lines = csv.trim().split('\n');
  expect(lines[0]).toContain('paid_on,name,email,plan');

  const paidOn = lines.slice(1).map((line) => line.split(',')[0] ?? '');
  return {
    payments: paidOn.length,
    months: new Set(paidOn.map((date) => date.slice(0, 7))).size,
    years: new Set(paidOn.map((date) => date.slice(0, 4))).size,
  };
}

test('an account administrator reads the monthly and yearly totals and exports them', async ({
  page,
}) => {
  await signIn(page, DEMO.accountadmin);

  await page
    .getByRole('navigation', { name: 'Portal sections' })
    .getByRole('link', { name: 'Payments' })
    .click();
  await expect(page).toHaveURL(/\/portal\/admin\/payments/);

  // The three headline tiles.
  await expect(page.getByText('This month')).toBeVisible();
  await expect(page.getByText('Year to date')).toBeVisible();
  await expect(page.getByText('Last 12 months')).toBeVisible();

  // Export CSV downloads the same payments the report groups, so it says how
  // many rows each grouping must have.
  const totals = await ledgerTotals(page);
  expect(totals.payments).toBeGreaterThan(totals.months);
  expect(totals.months).toBeGreaterThan(totals.years);

  // Month is the default grouping: one row per month that carries a payment.
  const periodTable = page.getByRole('region', { name: 'Payments by period' });
  await expect(periodTable.getByRole('columnheader', { name: 'Month' })).toBeVisible();
  await expect(periodRows(page)).toHaveCount(totals.months);

  // Switching to Year regroups the same money into one row per year.
  await page
    .getByRole('group', { name: 'Group payments by' })
    .getByRole('button', { name: 'Year' })
    .click();
  await expect(periodTable.getByRole('columnheader', { name: 'Year' })).toBeVisible();
  await expect(periodRows(page)).toHaveCount(totals.years);

  // The ledger below counts the same payments in its caption.
  await expect(page.getByRole('heading', { name: 'All payments' })).toBeVisible();
  await expect(page.getByText(`${totals.payments} payments`)).toBeVisible();
});

test('a filtered export carries the filter', async ({ page }) => {
  await signIn(page, DEMO.accountadmin);
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
