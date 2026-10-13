/**
 * Email addresses and the verify screen: a joiner corrects a mistyped address from
 * the verify step, and a member who asks to change their address keeps signing in
 * with the one they have until they follow the link mailed to the new one, while the
 * old address is told about the change.
 */
import { expect, test } from '@playwright/test';

import {
  JOINER_PASSWORD,
  completeOnboarding,
  emailCountTo,
  latestEmailTo,
  registerAccount,
  signInAsJoiner,
  uniqueEmail,
  verificationLink,
} from './helpers';

test('a joiner corrects the address from the verify step', async ({ page }) => {
  const typo = uniqueEmail('typo');
  const right = uniqueEmail('right');
  await registerAccount(page, typo, { as: 'friend', firstName: 'Irena' });
  await signInAsJoiner(page, typo);
  await expect(page).toHaveURL(/\/portal\/join\/verify/);

  await page.getByRole('link', { name: 'Use a different email address' }).click();
  await page.getByRole('textbox', { name: 'New email address' }).fill(right);
  await page.getByLabel(/^Current password/).fill(JOINER_PASSWORD);
  await page.getByRole('button', { name: 'Change email' }).click();

  await expect(page).toHaveURL(/\/portal\/join\/verify/);
  await expect(
    page.getByText(
      `We sent a link to ${right}. Your sign-in address stays ${typo} until you follow it.`,
    ),
  ).toBeVisible();
});

test('a member asks to change their address and confirms the new one', async ({ page }) => {
  const first = uniqueEmail('mover');
  const second = uniqueEmail('moved');
  await completeOnboarding(page, first, { as: 'friend', firstName: 'Irena' });
  const toldBefore = emailCountTo(first);

  await page.goto('portal/change-email');
  await page.getByRole('textbox', { name: 'New email address' }).fill(second);
  await page.getByLabel(/^Current password/).fill(JOINER_PASSWORD);
  await page.getByRole('button', { name: 'Change email' }).click();

  // Nothing changes yet: the portal stays open, and says the change is waiting.
  const waiting = `We sent a link to ${second}. Your sign-in address stays ${first} until you follow it.`;
  await expect(page.getByText(waiting).first()).toBeVisible();
  await expect(page).toHaveURL(/\/portal\/?$/);
  await expect(page.getByRole('navigation', { name: 'Portal sections' })).toBeVisible();
  await page.goto('portal/change-email');
  await expect(page.getByText(waiting)).toBeVisible();

  // The old address is told about the request.
  expect(emailCountTo(first)).toBe(toldBefore + 1);

  await page.goto(verificationLink(await latestEmailTo(second)));
  await expect(page.getByRole('heading', { name: 'Email address changed' })).toBeVisible();
  await expect(page.getByText(`${second} is your sign-in address from now on.`)).toBeVisible();
  await page.getByRole('link', { name: 'Continue' }).click();

  await expect(page).toHaveURL(/\/portal\/?$/);
  await expect(page.getByRole('heading', { name: /Welcome, Irena/ })).toBeVisible();
  // The old address is told again, now that the change has happened.
  await expect.poll(() => emailCountTo(first)).toBe(toldBefore + 2);
});
