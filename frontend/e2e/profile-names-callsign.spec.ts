/**
 * The member's own profile edits their first and last name, stored in the casing
 * `docs/user/member/profile.rst` describes, and their amateur radio callsign, which
 * takes a US callsign only.
 */
import { expect, test } from '@playwright/test';

import { completeOnboarding, uniqueEmail } from './helpers';

test('a member renames themselves and records a callsign on their profile', async ({ page }) => {
  const email = uniqueEmail('rename');
  await completeOnboarding(page, email, { as: 'friend', firstName: 'Dena' });

  await page.goto('portal/profile');
  const first = page.getByRole('textbox', { name: 'First name' });
  const last = page.getByRole('textbox', { name: 'Last name' });
  await expect(first).toHaveValue('Dena');
  await expect(last).toHaveValue('Okafor');

  // All capitals is title-cased; mixed case is kept as typed.
  await first.fill('DeAnna');
  await last.fill('SMITH');
  // The callsign box capitalizes as it is typed.
  const callsign = page.getByRole('textbox', { name: 'Amateur radio callsign' });
  await callsign.pressSequentially('w6abc');
  await expect(callsign).toHaveValue('W6ABC');
  await page.getByRole('button', { name: 'Save profile' }).click();
  await expect(page.getByText('Profile saved.')).toBeVisible();

  await page.reload();
  await expect(first).toHaveValue('DeAnna');
  await expect(last).toHaveValue('Smith');
  await expect(callsign).toHaveValue('W6ABC');
  // The header greets them by the new name.
  await page.goto('portal/');
  await expect(page.getByRole('heading', { name: 'Welcome, DeAnna' })).toBeVisible();
});

test('a callsign that is not a US one is refused and nothing is saved', async ({ page }) => {
  const email = uniqueEmail('callsign');
  await completeOnboarding(page, email, { as: 'friend', firstName: 'Omar' });

  await page.goto('portal/profile');
  const callsign = page.getByRole('textbox', { name: 'Amateur radio callsign' });
  await callsign.fill('X1ABC');
  await page.getByRole('button', { name: 'Save profile' }).click();
  await expect(page.getByText('Enter a US amateur radio callsign, such as W6ABC.')).toBeVisible();

  await page.reload();
  await expect(callsign).toHaveValue('');
});
