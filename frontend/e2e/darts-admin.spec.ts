/**
 * Adding a DART from the portal: an account administrator creates one, and it
 * is offered on a member's profile the same moment, which is the whole point
 * of the screen.  A DART lists as many people as it needs, and the Roster
 * column counts the ones ticked to receive the team's roster.
 */
import { expect, test } from '@playwright/test';
import type { Locator, Page } from '@playwright/test';

import { DEMO, signIn } from './helpers';

const NAME = 'Shelter Cove';

/** The one seeded DART with a website page and nobody on it. */
const DELETABLE = 'San Carlos';

/** That team's own page on the public site, which outlives the team. */
const DELETABLE_PAGE = '/about/darts/sql/';

/** A seeded DART no other spec edits, whose people this file adds to. */
const GROWING = 'Watsonville';

/** The Roster cell of `dart`'s row in the DARTs table. */
async function rosterCell(page: Page, dart: string): Promise<Locator> {
  // The headers are read once the row is on screen, so the index is the table's.
  const row = page.getByRole('row').filter({ hasText: dart }).first();
  await expect(row).toBeVisible();
  const headers = await page.getByRole('columnheader').allTextContents();
  const column = headers.findIndex((text) => text.startsWith('Roster'));
  expect(column).toBeGreaterThanOrEqual(0);
  return row.getByRole('cell').nth(column);
}

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

test('a DART takes a sixth person, and the Roster column counts the ticked ones', async ({
  page,
}) => {
  await signIn(page, DEMO.accountadmin);
  await page.goto('/portal/admin/darts');

  // The seed ticks each team's leader and deputy, both with an address.
  const before = await rosterCell(page, GROWING);
  await expect(before).toHaveText('2');

  await page
    .getByRole('row')
    .filter({ hasText: GROWING })
    .first()
    .getByRole('button', {
      name: 'Edit',
    })
    .click();

  // The seed lists two to four people; add rows until there are six.  Each row
  // is named before the next is added, since a nameless last row holds the
  // button back.
  const names = page.getByLabel('Name', { exact: true });
  const addPerson = page.getByRole('button', { name: 'Add a person' });
  const seeded = await names.count();
  for (let index = seeded; index < 6; index += 1) {
    await addPerson.click();
    await expect(addPerson).toBeDisabled();
    await names.nth(index).fill(`Volunteer ${index + 1}`);
    await page.getByLabel('Title').nth(index).fill('Ground team');
    await page
      .getByLabel('Email')
      .nth(index)
      .fill(`volunteer${index + 1}@example.test`);
  }
  await expect(names).toHaveCount(6);
  await page.getByRole('checkbox', { name: 'Volunteer 5 receives the roster' }).check();
  await page.getByRole('checkbox', { name: 'Volunteer 6 receives the roster' }).check();
  await page.getByRole('button', { name: 'Save DART' }).click();

  await expect(page.getByText(`${GROWING} saved.`)).toBeVisible();
  await expect(await rosterCell(page, GROWING)).toHaveText('4');
});
