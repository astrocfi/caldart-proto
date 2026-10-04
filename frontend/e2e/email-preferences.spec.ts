/**
 * The kinds of bulk email: a person turns one off on Email preferences and it stays
 * off, and a system administrator adds, edits, and deletes a kind on Email types.
 */
import { expect, test } from '@playwright/test';

import { DEMO, signIn } from './helpers';

test('a member turns a kind of email off, and it stays off', async ({ page }) => {
  await signIn(page, DEMO.member);
  await page
    .getByRole('navigation', { name: 'Portal sections' })
    .getByRole('link', { name: 'Email preferences' })
    .click();
  await expect(page).toHaveURL(/\/portal\/email-preferences/);

  const mission = page.getByRole('switch', { name: 'Mission' });
  await expect(mission).toBeChecked();
  await mission.click();
  await expect(page.getByText('Mission turned off.')).toBeVisible();

  await page.reload();
  await expect(page.getByRole('switch', { name: 'Mission' })).not.toBeChecked();

  // Back on, so the seeded account receives Mission email again for every other spec.
  await page.getByRole('switch', { name: 'Mission' }).click();
  await expect(page.getByText('Mission turned on.')).toBeVisible();
  await expect(page.getByRole('switch', { name: 'Mission' })).toBeChecked();
});

test('a system administrator adds, edits, and deletes an email type', async ({ page }) => {
  const name = `Board news ${Date.now().toString(36)}`;

  await signIn(page, DEMO.sysadmin);
  await page
    .getByRole('navigation', { name: 'Portal sections' })
    .getByRole('link', { name: 'Email types' })
    .click();
  await expect(page).toHaveURL(/\/portal\/bulk-email\/types/);
  await expect(page.getByRole('rowheader', { name: 'Fundraising', exact: true })).toBeVisible();

  await page.getByRole('button', { name: 'New email type' }).click();
  await page.getByLabel('Name*').fill(name);
  await page.getByLabel('What it is for*').fill('What the board decided this month.');
  await page.getByRole('checkbox', { name: 'CalDART management' }).check();
  await page.getByRole('button', { name: 'Add email type' }).click();
  await expect(page.getByText(`${name} added.`)).toBeVisible();

  const row = page.getByRole('row').filter({ hasText: name });
  await expect(row).toContainText('CalDART management');
  await row.getByRole('button', { name: 'Edit' }).click();
  await page.getByRole('checkbox', { name: 'Recipients may turn it off' }).uncheck();
  await page.getByRole('checkbox', { name: 'DART leader' }).check();
  await page.getByRole('button', { name: 'Save changes' }).click();
  await expect(page.getByText(`${name} saved.`)).toBeVisible();
  await expect(row).toContainText('DART leader, CalDART management');
  await expect(row.getByRole('cell', { name: 'No', exact: true })).toBeVisible();

  await row.getByRole('button', { name: `Delete ${name}` }).click();
  await row.getByRole('button', { name: 'Delete', exact: true }).click();
  await expect(page.getByText(`${name} deleted.`)).toBeVisible();
  await expect(page.getByRole('row').filter({ hasText: name })).toHaveCount(0);
});
