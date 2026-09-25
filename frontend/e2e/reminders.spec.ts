/**
 * The renewal reminder log as each role sees it: an account administrator
 * reads and filters it, a DART leader cannot reach it, and only a system
 * administrator can start a scan or read the email log behind it.
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
      response.url().includes('/admin/reminders/log') && response.url().includes('kind=t30'),
  );
  await page.getByLabel('Reminder').selectOption('t30');
  expect((await filtered).status()).toBe(200);
  await expect(page.getByLabel('Reminder')).toHaveValue('t30');
  await expect(page.getByText('No reminders sent yet')).toBeVisible();
});

test('the account administrator has no way to start a scan', async ({ page }) => {
  await signIn(page, DEMO.accountadmin);
  await page.goto('/portal/admin/reminders');
  await expect(page.getByRole('heading', { name: 'Renewal reminders' })).toBeVisible();

  await expect(page.getByRole('button', { name: 'Run now' })).toHaveCount(0);
  await expect(page.getByLabel('Dry run (send nothing)')).toHaveCount(0);
});

test('a DART leader cannot reach the reminder log', async ({ page }) => {
  await signIn(page, DEMO.leader);
  await page.goto('/portal/admin/reminders');

  await expect(page.getByRole('heading', { name: 'Not allowed' })).toBeVisible();
  await expect(
    page.getByRole('navigation', { name: 'Portal sections' }).getByRole('link', {
      name: 'Reminders',
    }),
  ).toHaveCount(0);
});

test('a system administrator keeps the run controls on the System page', async ({ page }) => {
  await signIn(page, DEMO.sysadmin);
  await page.goto('/portal/system');

  // The System page carries a second scan, the automatic renewals one, with
  // run controls of its own, so every control here is read inside its panel.
  const panel = page
    .locator('section.card')
    .filter({ has: page.getByRole('heading', { name: 'Renewal reminders' }) });
  await expect(panel).toBeVisible();
  await expect(panel.getByLabel('Dry run (send nothing)')).toBeChecked();

  await panel.getByRole('button', { name: 'Run now' }).click();
  await expect(panel.getByRole('status').filter({ hasText: /^Would send / })).toBeVisible();
  await expect(panel.getByRole('heading', { name: 'What this run would do' })).toBeVisible();

  // The fresh seed always leaves at least one member inside a reminder stage
  // with no mandate covering them, so the rehearsal's table is never empty.
  await expect(panel.getByRole('table', { name: /^[1-9]\d* actions?$/ })).toBeVisible();
});

test('a system administrator filters the email log and downloads it', async ({ page }) => {
  await signIn(page, DEMO.sysadmin);
  await page.goto('/portal/system');

  const panel = page
    .locator('section.card')
    .filter({ has: page.getByRole('heading', { name: 'Email log' }) });
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
