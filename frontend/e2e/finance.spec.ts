/**
 * The treasurer's working day: filter the list, choose columns, export it,
 * refund part of a payment, and record a check.
 *
 * Everything here is asserted against the seeded database through
 * `manage.py seed_facts`, so a change to the demo data fails on the fact it
 * renamed rather than on a name typed into this spec.
 */
import { expect, test } from '@playwright/test';
import type { Locator, Page } from '@playwright/test';

import { DEMO, SEED, signIn, uniqueEmail } from './helpers';

/**
 * The rail carries two entries called Payments -- the member's own screen and
 * the finance area -- so the administration one is named by its address.
 */
function financeRailEntry(page: Page): Locator {
  return page
    .getByRole('navigation', { name: 'Portal sections' })
    .locator('a[href="/portal/admin/payments"]');
}

/** Open the finance area's Payments tab as the treasurer. */
async function openPaymentList(page: Page): Promise<void> {
  await signIn(page, DEMO.treasurer);
  await financeRailEntry(page).click();
  await expect(page).toHaveURL(/\/portal\/admin\/payments$/);
  await page.getByRole('navigation', { name: 'Finance sections' }).getByText('Payments').click();
  await expect(page).toHaveURL(/\/portal\/admin\/payments\/list/);
}

test('a treasurer reaches the finance area from the portal menu', async ({ page }) => {
  await signIn(page, DEMO.treasurer);

  await expect(financeRailEntry(page)).toBeVisible();
});

test('a treasurer does not reach the member register', async ({ page }) => {
  await signIn(page, DEMO.treasurer);
  await page.goto('/portal/admin/members');

  await expect(page.getByRole('heading', { name: 'Not allowed' })).toBeVisible();
});

test('a DART leader reaches none of the finance routes', async ({ page }) => {
  await signIn(page, DEMO.leader);

  for (const path of [
    '/portal/admin/payments',
    '/portal/admin/payments/list',
    '/portal/admin/payments/record',
    '/portal/admin/payments/members/1',
    '/portal/admin/payments/1',
  ]) {
    await page.goto(path);
    await expect(page.getByRole('heading', { name: 'Not allowed' })).toBeVisible();
  }
});

test('the list filters to the payments taken by hand', async ({ page }) => {
  await openPaymentList(page);

  await page.getByLabel('Provider').selectOption('manual');

  await expect(page.getByText(`${SEED.manualPaymentCount} payments`)).toBeVisible();
});

test('a chosen column reaches the table and the export link', async ({ page }) => {
  await openPaymentList(page);
  await page.getByRole('button', { name: 'Columns', exact: true }).click();
  await page.getByRole('checkbox', { name: 'Receipt' }).check();

  await expect(page.getByRole('link', { name: 'Export CSV' })).toHaveAttribute(
    'href',
    /columns=[^&]*receipt_number/,
  );
});

test('the treasurer downloads the list as a CSV and as a PDF', async ({ page }) => {
  await openPaymentList(page);

  const [csv] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('link', { name: 'Export CSV' }).click(),
  ]);
  expect(csv.suggestedFilename()).toMatch(/^caldart-payments-\d{4}-\d{2}-\d{2}\.csv$/);

  const [pdf] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('link', { name: 'Export PDF' }).click(),
  ]);
  expect(pdf.suggestedFilename()).toMatch(/^caldart-payments-\d{4}-\d{2}-\d{2}\.pdf$/);
});

test('a seeded refund is on the payment it came out of', async ({ page }) => {
  await openPaymentList(page);
  await page.getByLabel('Search').fill(SEED.refundedPayment.email);
  await page.getByRole('link', { name: SEED.refundedPayment.name }).first().click();

  await expect(
    page.getByRole('heading', { name: `Payment ${SEED.refundedPayment.receiptNumber}` }),
  ).toBeVisible();
  await expect(page.getByRole('table')).toContainText('Succeeded');
});

// A payment recorded by hand is the one a refund can be demonstrated on without
// a provider: the seed takes its card payments through Stripe and PayPal, which
// an end-to-end run has no keys for, while a manual refund calls nobody.
test('the treasurer refunds part of a payment and the status follows', async ({ page }) => {
  await openPaymentList(page);
  await page.getByLabel('Provider').selectOption('manual');
  await page.getByLabel('Status').selectOption('succeeded');
  await page.getByRole('table').getByRole('link').first().click();

  await page.getByRole('button', { name: 'Refund' }).click();
  const form = page.getByRole('form', { name: 'Refund this payment' });
  await form.getByLabel('Amount').fill('1.00');
  await form.getByRole('button', { name: 'Refund' }).click();

  await expect(page.getByText(/^Refunded \$1\.00\.$/)).toBeVisible();
  await expect(page.getByText('Partly refunded').first()).toBeVisible();
});

test('the treasurer records a check and finds it in the list', async ({ page }) => {
  await signIn(page, DEMO.treasurer);
  await page.goto('/portal/admin/payments/record');

  const reference = `E2E-${uniqueEmail('check').split('@')[0]}`;
  await page.getByLabel('Member').fill(SEED.refundedPayment.email);
  await page.getByRole('button', { name: new RegExp(SEED.refundedPayment.name) }).click();
  await page.getByLabel('Contribution').fill('12.00');
  await page.getByLabel('Reference').fill(reference);
  await page.getByRole('button', { name: 'Record the payment' }).click();

  await expect(page.getByRole('heading', { name: /^Payment CALDART-/ })).toBeVisible();
  await expect(page.getByText('By hand')).toBeVisible();

  await page.goto('/portal/admin/payments/list');
  await page.getByLabel('Search').fill(reference);
  await expect(page.getByText('1 payment')).toBeVisible();
});

test('the member ledger gathers one member whole history', async ({ page }) => {
  await openPaymentList(page);
  await page.getByLabel('Search').fill(SEED.refundedPayment.email);
  await page.getByRole('link', { name: SEED.refundedPayment.name }).first().click();
  await page
    .getByRole('link', { name: `Everything ${SEED.refundedPayment.name} has paid` })
    .click();

  await expect(page.getByRole('heading', { name: SEED.refundedPayment.name })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Totals' })).toBeVisible();
});
