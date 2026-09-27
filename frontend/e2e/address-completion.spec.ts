/**
 * Address suggestions on the profile form.
 *
 * `make e2e` points the server at a stub in place of Geoapify, which answers
 * every query with `e2e/geoapify/autocomplete.json`: a match in Mountain View
 * and one in Las Vegas.  The spec types an address prefix, sees both offered
 * under the Address box, and picks each in turn, once with the mouse and once
 * from the keyboard.
 */
import { expect, test } from '@playwright/test';
import type { Locator, Page } from '@playwright/test';

import { DEMO, signIn } from './helpers';

const MOUNTAIN_VIEW = '1600 Amphitheatre Parkway, Mountain View, CA 94043';
const LAS_VEGAS = '1600 Amphitheater Drive, Las Vegas, NV 89109';

/** Type an address prefix into the Address box and wait for the list of suggestions. */
async function typeAddressPrefix(page: Page): Promise<Locator> {
  const address = page.getByRole('combobox', { name: 'Address', exact: true });
  await address.fill('');
  await address.pressSequentially('1600 Amph');
  const list = page.getByRole('listbox', { name: 'Suggested addresses' });
  await expect(list).toBeVisible();
  return list;
}

test('a picked suggestion fills the street, city, state, ZIP code, and county', async ({
  page,
}) => {
  await signIn(page, DEMO.member);
  await page.goto('/portal/profile');

  const list = await typeAddressPrefix(page);
  await expect(list.getByRole('option')).toHaveText([MOUNTAIN_VIEW, LAS_VEGAS]);
  await list.getByRole('option', { name: MOUNTAIN_VIEW }).click();

  await expect(list).toHaveCount(0);
  await expect(page.getByRole('combobox', { name: 'Address', exact: true })).toHaveValue(
    '1600 Amphitheatre Parkway',
  );
  await expect(page.getByRole('textbox', { name: 'City', exact: true })).toHaveValue(
    'Mountain View',
  );
  await expect(page.getByRole('combobox', { name: 'State', exact: true })).toHaveValue('CA');
  await expect(page.getByRole('textbox', { name: 'ZIP code', exact: true })).toHaveValue('94043');
  await expect(page.getByRole('combobox', { name: 'California county' })).toHaveValue(
    'Santa Clara',
  );
});

test('the keyboard picks a suggestion outside California and clears the county', async ({
  page,
}) => {
  await signIn(page, DEMO.member);
  await page.goto('/portal/profile');

  await typeAddressPrefix(page);
  await page.keyboard.press('ArrowDown');
  await page.keyboard.press('ArrowDown');
  await page.keyboard.press('Enter');

  await expect(page.getByRole('textbox', { name: 'City', exact: true })).toHaveValue('Las Vegas');
  await expect(page.getByRole('combobox', { name: 'State', exact: true })).toHaveValue('NV');
  await expect(page.getByRole('combobox', { name: 'California county' })).toHaveValue('');
});
