/**
 * A person deactivates their own account from the profile page, is signed out,
 * and brings the account back from the sign-in page with the same password.
 */
import { expect, test } from '@playwright/test';

import { followVerificationLink, uniqueEmail } from './helpers';

const PASSWORD = 'a-long-demo-passphrase';

test('a person deactivates their account and reactivates it at sign-in', async ({ page }) => {
  const email = uniqueEmail('leaver');

  // A fresh account, so no other spec's demo account is touched.
  await page.goto('/portal/join');
  await page.getByRole('textbox', { name: 'First name' }).fill('Lena');
  await page.getByRole('textbox', { name: 'Last name' }).fill('Park');
  await page.getByRole('textbox', { name: 'Email address' }).fill(email);
  await page.getByLabel(/^Password/).fill(PASSWORD);
  await page.getByRole('button', { name: 'Create account' }).click();
  await expect(page.getByRole('heading', { name: 'Check your email' })).toBeVisible();
  await followVerificationLink(page, email);

  // Deactivate from the foot of the profile page.
  await page.goto('/portal/profile');
  const card = page.locator('section.card', {
    has: page.getByRole('heading', { name: 'Deactivate my account' }),
  });
  await card.getByLabel(/^Current password/).fill(PASSWORD);
  await card.getByRole('button', { name: 'Deactivate my account' }).click();

  await expect(page).toHaveURL(/\/portal\/login/);
  await expect(
    page.getByText('Your account is deactivated. Sign in any time to reactivate it.'),
  ).toBeVisible();

  // Signing in again is refused, with the offer to reactivate.
  await page.getByRole('textbox', { name: 'Email address' }).fill(email);
  await page.getByLabel(/^Password/).fill(PASSWORD);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByText('This account is deactivated. You can reactivate it.')).toBeVisible();
  await expect(
    page.getByText(
      'Reactivating brings back your roles and any membership that has not yet run out.',
    ),
  ).toBeVisible();

  // Reactivating signs the person in.
  await page.getByRole('button', { name: 'Reactivate my account' }).click();
  await expect(page).not.toHaveURL(/\/portal\/login/);
  await page.goto('/portal/profile');
  await expect(page.getByRole('heading', { name: 'My profile' })).toBeVisible();
});
