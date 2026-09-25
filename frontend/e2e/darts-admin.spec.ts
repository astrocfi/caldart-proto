/**
 * Adding a DART from the portal: an account administrator creates one, and it
 * is offered on a member's profile the same moment, which is the whole point
 * of the screen.
 */
import { expect, test } from '@playwright/test';

import { DEMO, signIn } from './helpers';

const NAME = 'Shelter Cove';

/** The one seeded DART with a website page and nobody on it. */
const DELETABLE = 'San Carlos';

/** That team's own page on the public site, which outlives the team. */
const DELETABLE_PAGE = '/about/darts/sql/';

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
  await page.getByLabel('Name', { exact: true }).fill('Dana Whitfield');
  await page.getByLabel('Title').fill('DART leader');
  await page.getByRole('button', { name: 'Add DART' }).click();

  await expect(page.getByRole('cell', { name: NAME })).toBeVisible();

  // The public catalog is the same table, so the profile's DART box has it.
  await page.goto('/portal/profile');
  await expect(page.getByLabel('DART').getByRole('option', { name: NAME })).toHaveCount(1);
});

test('deleting a DART leaves its website page standing', async ({ page }) => {
  await signIn(page, DEMO.accountadmin);
  await page.goto('/portal/admin/darts');

  // The seed puts nobody on San Carlos and gives it a page, so the delete has a
  // page to unlink and no member to unaffiliate.
  const row = page.getByRole('row').filter({ hasText: DELETABLE }).first();
  await expect(row.getByRole('cell', { name: '0', exact: true })).toBeVisible();

  // Delete lives in the form, beside the team's name and its people, not in the
  // row: opening the DART is the first step of deleting it.
  await row.getByRole('button', { name: 'Edit' }).click();
  await page.getByRole('button', { name: 'Delete this DART' }).click();
  await expect(
    page.getByText(`Deleting ${DELETABLE} unlinks 1 website page. This cannot be undone.`),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Delete for good' }).click();

  await expect(page.getByRole('row').filter({ hasText: DELETABLE })).toHaveCount(0);

  // The page is content: it keeps its own words and loses only its DART.
  await page.goto(DELETABLE_PAGE);
  await expect(page.getByRole('heading', { name: DELETABLE, level: 1 })).toBeVisible();
});

test('the member count opens the member list filtered to that DART', async ({ page }) => {
  await signIn(page, DEMO.accountadmin);
  await page.goto('/portal/admin/darts');

  const row = page.getByRole('row').filter({ hasText: 'Palo Alto' }).first();
  await row.getByRole('link', { name: /^\d+$/ }).click();

  await expect(page).toHaveURL(/\/portal\/admin\/members\?dart=\d+/);
});

test('a plain member cannot reach the DART screen', async ({ page }) => {
  await signIn(page, DEMO.member);
  await page.goto('/portal/admin/darts');

  await expect(page.getByRole('link', { name: 'DARTs' })).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'DARTs', exact: true })).toHaveCount(0);
});
