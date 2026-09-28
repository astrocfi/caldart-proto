/**
 * Email addresses and the verify screen: a joiner corrects a mistyped address from
 * the verify step, and a member who changes their address sees only the verify
 * screen, naming the new address, until they follow the link mailed to it.
 */
import { expect, test } from '@playwright/test';

import {
  JOINER_PASSWORD,
  completeOnboarding,
  latestEmailTo,
  registerAccount,
  uniqueEmail,
  verificationLink,
} from './helpers';

test('a joiner corrects the address from the verify step', async ({ page }) => {
  const typo = uniqueEmail('typo');
  const right = uniqueEmail('right');
  await registerAccount(page, typo, { as: 'friend', firstName: 'Irena' });

  await page.getByRole('link', { name: 'Use a different email address' }).click();
  await page.getByRole('textbox', { name: 'New email address' }).fill(right);
  await page.getByLabel(/^Current password/).fill(JOINER_PASSWORD);
  await page.getByRole('button', { name: 'Change email' }).click();

  await expect(page).toHaveURL(/\/portal\/join\/verify/);
  await expect(page.getByText(`We sent a verification message to ${right}.`)).toBeVisible();
});

test('a member changes their address and verifies the new one', async ({ page }) => {
  const first = uniqueEmail('mover');
  const second = uniqueEmail('moved');
  await completeOnboarding(page, first, { as: 'friend', firstName: 'Irena' });

  await page.goto('portal/change-email');
  await page.getByRole('textbox', { name: 'New email address' }).fill(second);
  await page.getByLabel(/^Current password/).fill(JOINER_PASSWORD);
  await page.getByRole('button', { name: 'Change email' }).click();

  // The new address is unverified, so the verify screen is all there is, with no rail.
  await expect(
    page.getByText(`Your email is now ${second}. We sent a verification message to it.`),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/portal\/join\/verify/);
  await expect(page.getByText(`We sent a verification message to ${second}.`)).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Portal sections' })).toHaveCount(0);

  // Ask for another message, then follow the newest one.
  await page.getByRole('button', { name: 'Resend verification message' }).click();
  await expect(page.getByText(`Verification message sent to ${second}.`)).toBeVisible();
  await page.goto(verificationLink(await latestEmailTo(second)));
  await expect(page.getByText(`${second} is verified.`)).toBeVisible();
  await page.getByRole('link', { name: 'Continue' }).click();

  await expect(page).toHaveURL(/\/portal\/?$/);
  await expect(page.getByRole('heading', { name: /Welcome, Irena/ })).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Portal sections' })).toBeVisible();
});
