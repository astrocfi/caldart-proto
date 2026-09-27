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
import type { Page } from '@playwright/test';

import { DEMO, signIn } from './helpers';

const MOUNTAIN_VIEW = '1600 Amphitheatre Parkway, Mountain View, CA 94043';
const LAS_VEGAS = '1600 Amphitheater Drive, Las Vegas, NV 89109';

async function typeAddressPrefix(page: Page): Promise<void> {
  const address = page.getByRole('combobox', { name: 'Address', exact: true });
  await address.fill('');
  await address.pressSequentially('1600 Amph');
  await expect(page.getByRole('listbox', { name: 'Suggested addresses' })).toBeVisible();
}

test('a picked suggestion fills the street, city, state, ZIP code, and county', async ({
  page,
}) => {
  await signIn(page, DEMO.member);
  await page.goto('/portal/profile');

  await typeAddressPrefix(page);
  const options = page.getByRole('option');
  await expect(options).toHaveText([MOUNTAIN_VIEW, LAS_VEGAS]);
  await page.getByRole('option', { name: MOUNTAIN_VIEW }).click();

  await expect(page.getByRole('listbox')).toHaveCount(0);
  await expect(page.getByRole('combobox', { name: 'Address', exact: true })).toHaveValue(
    '1600 Amphitheatre Parkway',
  );
  await expect(page.getByRole('textbox', { name: 'City' })).toHaveValue('Mountain View');
  await expect(page.getByRole('combobox', { name: 'State' })).toHaveValue('CA');
  await expect(page.getByRole('textbox', { name: 'ZIP code' })).toHaveValue('94043');
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

  await expect(page.getByRole('textbox', { name: 'City' })).toHaveValue('Las Vegas');
  await expect(page.getByRole('combobox', { name: 'State' })).toHaveValue('NV');
  await expect(page.getByRole('combobox', { name: 'California county' })).toHaveValue('');
});
