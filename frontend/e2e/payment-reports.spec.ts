/**
 * Flow D in `docs/demo-walkthrough.rst`: an account administrator sees
 * payments per month and per year, and downloads the CSV.
 *
 * The overview carries the tiles and the period table; the list and its
 * exports are the Payments tab beside it, so the counts the CSV gives are
 * fetched from there and asserted against the overview.
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

/** The statuses the by-period summary counts: the money arrived, whatever came back later. */
const RECEIVED_STATUSES = new Set(['succeeded', 'partially_refunded', 'refunded']);

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
 * only the ones whose money arrived — succeeded, and refunded in part or in
 * full, since a refund is netted rather than erased — so `months` and `years`
 * come from those rows alone and `payments` — which the ledger caption below
 * the summary counts — from all of them.  The counts are read at the moment the spec runs rather than
 * from the seed, because an earlier spec in the same run may have paid for a
 * membership of its own, or had a card declined.
 */
async function ledgerTotals(page: Page): Promise<LedgerTotals> {
  await page.goto('/portal/admin/payments/list');
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('link', { name: 'Export CSV' }).click(),
  ]);
  expect(download.suggestedFilename()).toMatch(/\.csv$/);
  const records = parseCsv(await readFile(await download.path(), 'utf8'));
  const header = records[0] ?? [];
  expect(header.slice(0, 4)).toEqual(['Date', 'Name', 'Email', 'Plan']);
  const statusColumn = header.indexOf('Status');
  expect(statusColumn).toBeGreaterThan(-1);

  const rows = records.slice(1);
  const succeeded = rows
    .filter((row) => RECEIVED_STATUSES.has(row[statusColumn] ?? ''))
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

  // The rail carries two entries called Payments: the member's own screen and
  // this one, so the administration entry is named by its address.
  await page
    .getByRole('navigation', { name: 'Portal sections' })
    .locator('a[href="/portal/admin/payments"]')
    .click();
  await expect(page).toHaveURL(/\/portal\/admin\/payments/);

  // The three headline tiles.
  await expect(page.getByText('This month')).toBeVisible();
  await expect(page.getByText('Year to date')).toBeVisible();
  await expect(page.getByText('Last 12 months')).toBeVisible();

  // Export CSV downloads every payment the area reports on, so it says how
  // many rows each grouping must have and how many the list must count.
  const totals = await ledgerTotals(page);
  expect(totals.payments).toBeGreaterThan(totals.months);
  expect(totals.months).toBeGreaterThan(totals.years);

  await page.goto('/portal/admin/payments');

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

  // The Payments tab counts the same payments in its caption.
  await page.goto('/portal/admin/payments/list');
  await expect(page.getByText(`${totals.payments} payments`)).toBeVisible();
});

test('a filtered export carries the filter', async ({ page }) => {
  await signIn(page, DEMO.accountadmin);
  await page.goto('/portal/admin/payments/list');

  await page.getByLabel('Provider').selectOption('mock');
  await expect(page.getByRole('link', { name: 'Export CSV' })).toHaveAttribute(
    'href',
    /\/reports\/payments\/export\.csv\?provider=mock/,
  );

  // The filter lives in the address, so the filtered list survives a reload.
  await expect(page).toHaveURL(/provider=mock/);
  await page.reload();
  await expect(page.getByLabel('Provider')).toHaveValue('mock');
});

test('a saved set of columns comes back after a reload', async ({ page }) => {
  await signIn(page, DEMO.accountadmin);
  await page.goto('/portal/admin/payments/list');
  const header = page.locator('thead');
  const chooser = page.getByRole('group', { name: 'Columns to show and export' });

  // Tick Receipt, untick Fee, and save the boxes as they stand under a name.
  await page.getByRole('button', { name: 'Columns' }).click();
  await chooser.getByRole('checkbox', { name: 'Receipt' }).check();
  await chooser.getByRole('checkbox', { name: 'Fee', exact: true }).uncheck();
  await chooser.getByRole('textbox', { name: 'Name for these columns' }).fill('Audit');
  await chooser.getByRole('button', { name: 'Save columns' }).click();
  await expect(chooser.getByRole('combobox', { name: 'Load columns' })).toHaveValue(/^\d+$/);
  await expect(chooser.getByRole('button', { name: 'Delete the saved set Audit' })).toBeVisible();

  // A reload starts from the default columns again.
  await page.reload();
  await expect(header.getByText('Fee', { exact: true })).toBeVisible();
  await expect(header.getByText('Receipt', { exact: true })).toHaveCount(0);

  // Loading the set puts its columns back, in the table and in the exports.
  await page.getByRole('button', { name: 'Columns' }).click();
  await chooser.getByRole('combobox', { name: 'Load columns' }).selectOption({ label: 'Audit' });
  await expect(header.getByText('Receipt', { exact: true })).toBeVisible();
  await expect(header.getByText('Fee', { exact: true })).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'Export CSV' })).toHaveAttribute(
    'href',
    /columns=paid_on%2Creceipt_number%2Cname/,
  );
});

test('a plain member cannot reach the payment reports', async ({ page }) => {
  await signIn(page, DEMO.member);
  await page.goto('/portal/admin/payments');
  await expect(page.getByRole('heading', { name: 'Not allowed' })).toBeVisible();
});
