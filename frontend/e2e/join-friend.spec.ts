/**
 * A visitor joins CalDART as a friend: no dues, a contribution they may skip, and a
 * dashboard that offers membership rather than a renewal.
 *
 * Payment goes through the mock provider, which is what `PAYMENTS_MOCK_ENABLED` is for.
 */
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

import { followVerificationLink, uniqueEmail } from './helpers';

/**
 * Steps 1 to 3 as a friend: the account, the link mailed to its address, then the
 * fields that make the profile complete.  Ends on the friend's pay step.
 */
async function registerAsFriend(page: Page, first: string, email: string): Promise<void> {
  await page.goto('/portal/join');
  await page.getByRole('radio', { name: /Join as a friend/ }).check();
  await page.getByRole('textbox', { name: 'First name' }).fill(first);
  await page.getByRole('textbox', { name: 'Last name' }).fill('Amundsen');
  await page.getByRole('textbox', { name: 'Email address' }).fill(email);
  await page.getByLabel(/^Password/).fill('a-long-demo-passphrase');
  await page.getByRole('button', { name: 'Create account' }).click();

  await expect(page).toHaveURL(/\/portal\/join\/verify/);
  await expect(page.getByText('Step 2 of 5 · Joining as a friend')).toBeVisible();
  await followVerificationLink(page, email);

  await expect(page.getByRole('heading', { name: 'About you' })).toBeVisible();
  await page.getByRole('textbox', { name: 'Phone', exact: true }).fill('650-555-0177');
  await page.getByRole('textbox', { name: 'Address', exact: true }).fill('3 Runway Lane');
  await page.getByRole('textbox', { name: 'City', exact: true }).fill('Half Moon Bay');
  await page.getByRole('textbox', { name: 'ZIP code', exact: true }).fill('94019');
  await page.getByRole('button', { name: 'Save and continue' }).click();

  await expect(page).toHaveURL(/\/portal\/join\/pay/);
  await expect(page.getByRole('heading', { name: 'Contribute to CalDART' })).toBeVisible();
  // A friend's checkout sells no plan.
  await expect(page.getByRole('radio', { name: /Annual/ })).toHaveCount(0);
}

test('a visitor joins as a friend and skips the contribution', async ({ page }) => {
  await registerAsFriend(page, 'Freya', uniqueEmail('friend'));

  await page.getByRole('button', { name: 'Not now' }).click();

  await expect(page).toHaveURL(/\/portal\/join\/done/);
  await expect(page.getByRole('heading', { name: 'Welcome to CalDART' })).toBeVisible();
  await expect(
    page.getByText('You are a friend of CalDART: no dues, no expiry. Become a member any time.'),
  ).toBeVisible();

  // The dashboard agrees, and offers membership rather than a renewal.
  await page.getByRole('link', { name: 'Go to my dashboard' }).click();
  await expect(page).toHaveURL(/\/portal\/?$/);
  await expect(page.getByRole('heading', { name: 'You are a friend of CalDART' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Make me a member' })).toHaveAttribute(
    'href',
    '/portal/membership/join',
  );
  await expect(page.getByRole('link', { name: /Renew/ })).toHaveCount(0);
});

test('a friend contributes on the way through the wizard', async ({ page }) => {
  await registerAsFriend(page, 'Finn', uniqueEmail('friend-giver'));

  await page.getByRole('radio', { name: /Participating/ }).check();
  await page.getByRole('tab', { name: 'Test payment' }).click();
  await page.getByRole('button', { name: 'Succeed', exact: true }).click();

  await expect(page).toHaveURL(/\/portal\/join\/done/);
  await expect(page.getByRole('heading', { name: 'Welcome to CalDART' })).toBeVisible();
  await expect(page.getByText('Friend', { exact: true })).toBeVisible();
});

test('coming back to the wizard, a friend lands on done rather than paying', async ({ page }) => {
  await registerAsFriend(page, 'Fiona', uniqueEmail('friend-return'));

  await page.goto('/portal/join');

  await expect(page).toHaveURL(/\/portal\/join\/done/);
  await expect(page.getByRole('heading', { name: 'Welcome to CalDART' })).toBeVisible();
});
