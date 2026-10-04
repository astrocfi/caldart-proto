/**
 * The renewal reminder log as each role sees it: an account administrator
 * reads and filters it, a DART leader cannot reach it, and only a system
 * administrator can start a scan, change the reminder schedule, or read the
 * Sent emails log behind it.
 */
import { expect, test } from '@playwright/test';

import { DEMO, signIn } from './helpers';

test('an account administrator reads the reminder log and filters it by kind', async ({ page }) => {
  await signIn(page, DEMO.accountadmin);

  await page
    .getByRole('navigation', { name: 'Portal sections' })
    .getByRole('link', { name: 'Reminders' })
    .click();
  await expect(page).toHaveURL(/\/portal\/admin\/reminders/);
  await expect(page.getByRole('heading', { name: 'Reminders', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Renewal reminders' })).toBeVisible();

  // Picking a kind sends the filter to the API rather than trimming the page,
  // and the log renders the answer: a 403 would leave the same empty table, so
  // the response status is what proves the account admin may read the log.
  const filtered = page.waitForResponse(
    (response) =>
      response.url().includes('/admin/reminders/log') && response.url().includes('kind=second'),
  );
  await page.getByLabel('Reminder', { exact: true }).selectOption('second');
  expect((await filtered).status()).toBe(200);
  await expect(page.getByLabel('Reminder', { exact: true })).toHaveValue('second');
  await expect(page.getByText('No reminders of this kind')).toBeVisible();
});

test('the account administrator has no way to start a scan', async ({ page }) => {
  await signIn(page, DEMO.accountadmin);
  await page.goto('portal/admin/reminders');
  await expect(page.getByRole('heading', { name: 'Renewal reminders' })).toBeVisible();

  await expect(page.getByRole('button', { name: /^Run .* now$/ })).toHaveCount(0);
  await expect(page.getByLabel(/^Practice run/)).toHaveCount(0);
});

test('the account administrator reads the reminder schedule without changing it', async ({
  page,
}) => {
  await signIn(page, DEMO.accountadmin);
  await page.goto('portal/admin/reminders');

  const card = page
    .locator('section.card')
    .filter({ has: page.getByRole('heading', { name: 'Reminder schedule' }) });
  await expect(card.getByText('First reminder')).toBeVisible();
  await expect(card.getByRole('spinbutton')).toHaveCount(0);
  await expect(card.getByRole('button', { name: 'Save changes' })).toHaveCount(0);
});

test('a DART leader cannot reach the reminder log', async ({ page }) => {
  await signIn(page, DEMO.leader);
  await page.goto('portal/admin/reminders');

  await expect(page.getByRole('heading', { name: 'Not allowed' })).toBeVisible();
  await expect(
    page.getByRole('navigation', { name: 'Portal sections' }).getByRole('link', {
      name: 'Reminders',
    }),
  ).toHaveCount(0);
});

test('a system administrator keeps the run controls on the Scheduled page', async ({ page }) => {
  await signIn(page, DEMO.sysadmin);
  await page
    .getByRole('navigation', { name: 'Portal sections' })
    .getByRole('link', { name: 'Scheduled', exact: true })
    .click();
  await expect(page).toHaveURL(/\/portal\/system\/scheduled$/);

  // The Scheduled page carries other scans, the automatic renewal charges
  // first among them, with run controls of their own, so every control here
  // is read inside its panel.
  const panel = page
    .locator('section.card')
    .filter({ has: page.getByRole('heading', { name: 'Renewal reminder emails' }) });
  await expect(panel).toBeVisible();
  await expect(
    panel.getByLabel(
      'Practice run: show what would happen, send nothing (renewal reminder emails)',
    ),
  ).toBeChecked();

  await panel.getByRole('button', { name: 'Run now: renewal reminder emails' }).click();
  await expect(panel.getByRole('status').filter({ hasText: /^Would send / })).toBeVisible();
  await expect(panel.getByRole('heading', { name: 'What this run would do' })).toBeVisible();

  // The fresh seed always leaves at least one member inside a reminder stage
  // with no mandate covering them, so the rehearsal's table is never empty.
  await expect(panel.getByRole('table', { name: /^[1-9]\d* actions?$/ })).toBeVisible();
});

test('a system administrator saves the reminder schedule', async ({ page }) => {
  await signIn(page, DEMO.sysadmin);
  await page.goto('portal/system/scheduled');

  const card = page
    .locator('section.card')
    .filter({ has: page.getByRole('heading', { name: 'Reminder schedule' }) });
  await expect(card.getByLabel('First reminder')).toHaveValue(/^\d+$/);

  // Saving the stored days as they stand records who saved them, and leaves the
  // schedule the other specs rely on unchanged.
  const saved = page.waitForResponse(
    (response) =>
      response.url().includes('/admin/reminders/schedule') && response.request().method() === 'PUT',
  );
  await card.getByRole('button', { name: 'Save changes' }).click();
  expect((await saved).status()).toBe(200);
  await expect(card.getByText(/^Last saved \d{2}\/\d{2}\/\d{4} by /)).toBeVisible();
});

test('a system administrator filters the email log and downloads it', async ({ page }) => {
  await signIn(page, DEMO.sysadmin);
  await page.goto('portal/system/emails');
  await expect(page.getByRole('heading', { level: 1, name: 'Sent emails' })).toBeVisible();

  const panel = page.locator('section.card').filter({ has: page.getByLabel('Purpose') });
  await expect(panel).toBeVisible();
  await expect(panel.getByLabel('Purpose')).toBeVisible();
  await expect(panel.getByLabel('Status')).toBeVisible();
  await expect(panel.getByLabel('From')).toBeVisible();
  await expect(panel.getByLabel('To', { exact: true })).toBeVisible();
  await expect(panel.getByLabel('Search')).toBeVisible();

  // Picking a purpose sends the filter to the API rather than trimming the
  // page, and the table renders the answer: a 403 would leave the same empty
  // table, so the response status is what proves the log is readable here.
  const filtered = page.waitForResponse(
    (response) =>
      response.url().includes('/system/emails') && response.url().includes('purpose=receipt'),
  );
  await panel.getByLabel('Purpose').selectOption('receipt');
  expect((await filtered).status()).toBe(200);
  await expect(panel.getByLabel('Purpose')).toHaveValue('receipt');
  await expect(page).toHaveURL(/[?&]purpose=receipt/);

  // The export carries the filter the table shows, and downloads the report.
  const csv = panel.getByRole('link', { name: 'Export CSV' });
  await expect(csv).toHaveAttribute('href', /\/reports\/emails\/export\.csv\?.*purpose=receipt/);
  const download = await page.request.get((await csv.getAttribute('href')) ?? '');
  expect(download.status()).toBe(200);
  expect(download.headers()['content-type']).toBe('text/csv; charset=utf-8');
});
