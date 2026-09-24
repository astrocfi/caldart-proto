/**
 * Adding a DART from the portal: an account administrator creates one, and it
 * is offered on a member's profile the same moment, which is the whole point
 * of the screen.
 */
import { expect, test } from '@playwright/test';

import { DEMO, signIn } from './helpers';

const NAME = 'Shelter Cove';

test('an account administrator adds a DART and it is offered straight away', async ({ page }) => {
  await signIn(page, DEMO.accountadmin);

  await page
    .getByRole('navigation', { name: 'Portal sections' })
    .getByRole('link', { name: 'DARTs' })
    .click();
  await expect(page).toHaveURL(/\/portal\/admin\/darts/);

  await page.getByRole('button', { name: 'Add a DART' }).click();
  await page.getByLabel('Name*').fill(NAME);
  // The box upper-cases what is typed, takes more than one field, and trims
  // the ICAO K so one airport is written one way everywhere.
  await page.getByLabel('Airports*').fill('o86, kcrq');
  await expect(page.getByLabel('Airports*')).toHaveValue('O86, CRQ');
  await page.getByLabel('Town').fill('Whitethorn');
  await page.getByLabel('Name', { exact: true }).fill('Dana Whitfield');
  await page.getByLabel('Title').fill('DART leader');
  await page.getByRole('button', { name: 'Add DART' }).click();

  await expect(page.getByRole('cell', { name: NAME })).toBeVisible();

  // The public catalog is the same table, so the profile's DART box has it.
  await page.goto('/portal/profile');
  await expect(page.getByLabel('DART').getByRole('option', { name: NAME })).toHaveCount(1);
});

test('a DART with members on it cannot be deleted', async ({ page }) => {
  await signIn(page, DEMO.accountadmin);
  await page.goto('/portal/admin/darts');

  const row = page.getByRole('row').filter({ hasText: 'Palo Alto' }).first();
  await expect(row.getByRole('button', { name: 'Delete' })).toBeDisabled();
});

test('a plain member cannot reach the DART screen', async ({ page }) => {
  await signIn(page, DEMO.member);
  await page.goto('/portal/admin/darts');

  await expect(page.getByRole('link', { name: 'DARTs' })).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'DARTs', exact: true })).toHaveCount(0);
});
