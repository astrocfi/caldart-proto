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
 * Split CSV text into its records, honoring RFC 4180 quoting.
 *
 * A cell holding a comma, a quote or a newline is exported quoted, so splitting
 * on those characters directly would mis-read the row a member with a comma in
 * their name produces.
 */
function parseCsv(text: string): string[][] {
  const records: string[][] = [];
  let record: string[] = [];
  let cell = '';
  let isQuoted = false;
  for (let i = 0; i < text.length; i += 1) {
    const char = text.charAt(i);
    if (isQuoted) {
      if (char !== '"') {
        cell += char;
      } else if (text.charAt(i + 1) === '"') {
        cell += '"';
        i += 1;
      } else {
        isQuoted = false;
      }
    } else if (char === '"') {
      isQuoted = true;
    } else if (char === ',') {
      record.push(cell);
      cell = '';
    } else if (char === '\n') {
      record.push(cell);
      records.push(record);
      record = [];
      cell = '';
    } else if (char !== '\r') {
      cell += char;
    }
  }
  if (cell !== '' || record.length > 0) {
    record.push(cell);
    records.push(record);
  }
  return records;
}

/**
 * Download the unfiltered CSV export and count what it holds.
 *
 * The export and the by-period summary are two different endpoints over the
 * same payments, so counting the CSV gives the summary's expected row counts
 * from outside the screen being tested.  The two endpoints do not cover the
 * same rows, though: the export carries every payment, while the summary counts
 * only the succeeded ones, so `months` and `years` come from the succeeded rows
 * alone and `payments` — which the ledger caption below the summary counts —
 * from all of them.  The counts are read at the moment the spec runs rather than
 * from the seed, because an earlier spec in the same run may have paid for a
 * membership of its own, or had a card declined.
 */
async function ledgerTotals(page: Page): Promise<LedgerTotals> {
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('link', { name: 'Export CSV' }).click(),
  ]);
  expect(download.suggestedFilename()).toMatch(/\.csv$/);
  const records = parseCsv(await readFile(await download.path(), 'utf8'));
  const header = records[0] ?? [];
  expect(header.slice(0, 4)).toEqual(['paid_on', 'name', 'email', 'plan']);
  const statusColumn = header.indexOf('status');
  expect(statusColumn).toBeGreaterThan(-1);

  const rows = records.slice(1);
  const succeeded = rows
    .filter((row) => row[statusColumn] === 'succeeded')
    .map((row) => row[0] ?? '');
  return {
    payments: rows.length,
    months: new Set(succeeded.map((date) => date.slice(0, 7))).size,
    years: new Set(succeeded.map((date) => date.slice(0, 4))).size,
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

  // Export CSV downloads every payment the screen reports on, so it says how
  // many rows each grouping must have and how many the ledger must count.
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
