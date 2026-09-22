/**
 * The renewal reminder log as each role sees it: an account administrator
 * reads and filters it, a DART leader cannot reach it, and only a system
 * administrator can start a scan.
 */
import { expect, test } from '@playwright/test';

import { DEMO, signIn } from './helpers';

test('an account administrator reads the reminder log and filters it by kind', async ({ page }) => {
  await signIn(page, DEMO.accountAdmin);

  await page
    .getByRole('navigation', { name: 'Portal sections' })
    .getByRole('link', { name: 'Reminders' })
    .click();
  await expect(page).toHaveURL(/\/portal\/admin\/reminders/);
  await expect(page.getByRole('heading', { name: 'Reminders' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Renewal reminders' })).toBeVisible();

  // Picking a kind sends the filter to the API rather than trimming the page.
  const filtered = page.waitForRequest(
    (request) =>
      request.url().includes('/admin/reminders/log') && request.url().includes('kind=t30'),
  );
  await page.getByLabel('Reminder').selectOption('t30');
  await filtered;
  await expect(page.getByLabel('Reminder')).toHaveValue('t30');
});

test('the account administrator has no way to start a scan', async ({ page }) => {
  await signIn(page, DEMO.accountAdmin);
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
  await signIn(page, DEMO.sysAdmin);
  await page.goto('/portal/system');

  await expect(page.getByRole('heading', { name: 'Renewal reminders' })).toBeVisible();
  await expect(page.getByLabel('Dry run (send nothing)')).toBeChecked();

  await page.getByRole('button', { name: 'Run now' }).click();
  await expect(page.getByRole('status').filter({ hasText: /^Would send / })).toBeVisible();
});
