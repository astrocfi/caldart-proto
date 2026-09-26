/**
 * A member changes their email address: the new address is unverified until its
 * owner follows the link mailed to it, and the dashboard says so until then.
 */
import { expect, test } from '@playwright/test';

import { latestEmailTo, uniqueEmail, verificationLink } from './helpers';

const PASSWORD = 'a-long-demo-passphrase';

test('a member changes their address and verifies the new one', async ({ page }) => {
  const first = uniqueEmail('mover');
  const second = uniqueEmail('moved');

  // Register; the wizard stops to ask for the first address to be verified.
  await page.goto('/portal/join');
  await page.getByRole('textbox', { name: 'First name' }).fill('Irena');
  await page.getByRole('textbox', { name: 'Last name' }).fill('Varga');
  await page.getByRole('textbox', { name: 'Email address' }).fill(first);
  await page.getByLabel(/^Password/).fill(PASSWORD);
  await page.getByRole('button', { name: 'Create account' }).click();
  await expect(page.getByRole('heading', { name: 'Check your email' })).toBeVisible();

  // Change the address from the menu's screen.
  await page.goto('/portal/change-email');
  await page.getByRole('textbox', { name: 'New email address' }).fill(second);
  await page.getByLabel(/^Current password/).fill(PASSWORD);
  await page.getByRole('button', { name: 'Change email' }).click();

  await expect(
    page.getByText(`Your email is now ${second}. We sent a verification message to it.`),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/portal\/?$/);
  const nudge = page.getByRole('heading', { name: 'Verify your email address' });
  await expect(nudge).toBeVisible();

  // Ask for another message, then follow the newest one.
  await page.getByRole('button', { name: 'Resend verification message' }).click();
  await expect(page.getByText(`Verification message sent to ${second}.`)).toBeVisible();
  await page.goto(verificationLink(await latestEmailTo(second)));
  await expect(page.getByText(`${second} is verified.`)).toBeVisible();

  await page.goto('/portal/');
  await expect(page.getByRole('heading', { name: /Welcome, Irena/ })).toBeVisible();
  await expect(nudge).toHaveCount(0);
});
