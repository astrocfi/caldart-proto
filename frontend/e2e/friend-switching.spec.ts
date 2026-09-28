/**
 * A member becomes a friend of CalDART from the dashboard, a joiner changes their mind
 * on the pay step (and changes it back), and a friend becomes a member again by paying.
 *
 * A member whose membership is current becomes a friend the day after it runs out, and
 * can undo that until then.  Somebody who registers as a member is held at the pay step
 * until they pay or choose to be a friend instead.  Payment goes through the mock
 * provider, which is what `PAYMENTS_MOCK_ENABLED` is for.
 */
import { expect, test } from '@playwright/test';
import type { Locator, Page } from '@playwright/test';

import {
  completeOnboarding,
  completeProfileStep,
  followVerificationLink,
  registerAccount,
  uniqueEmail,
} from './helpers';

/** Pays for the preselected plan with the mock provider's success button. */
async function payWithMock(page: Page): Promise<void> {
  await page.getByRole('tab', { name: 'Test payment' }).click();
  await page.getByRole('button', { name: 'Succeed', exact: true }).click();
}

/** The dashboard's membership card, found by the headline it carries. */
function membershipCard(page: Page, headline: string): Locator {
  return page.locator('section.card', { has: page.getByRole('heading', { name: headline }) });
}

test('a current member asks to become a friend, then undoes it', async ({ page }) => {
  await completeOnboarding(page, uniqueEmail('switcher'), { as: 'member', firstName: 'Rosa' });
  await page.getByRole('link', { name: 'Go to my dashboard' }).click();

  const card = membershipCard(page, 'Your membership is current');
  await card.getByRole('button', { name: 'Make me a friend' }).click();
  await expect(
    card.getByText(/^Your membership stays current through \d{2}\/\d{2}\/\d{4}\./),
  ).toBeVisible();
  await card.getByRole('button', { name: 'Make me a friend' }).click();

  // The membership stays current, and the day of the change is shown.
  await expect(card.getByText(/^You become a friend on \d{2}\/\d{2}\/\d{4}\.$/)).toBeVisible();
  await card.getByRole('button', { name: 'Undo' }).click();
  await expect(card.getByRole('button', { name: 'Make me a friend' })).toBeVisible();
});

test('a joiner who changes their mind on the pay step becomes a friend', async ({ page }) => {
  const email = uniqueEmail('unpaid');
  await registerAccount(page, email, { as: 'member', firstName: 'Tomas' });
  await followVerificationLink(page, email);
  await completeProfileStep(page);
  await expect(page.getByRole('heading', { name: 'Pay your dues' })).toBeVisible();

  // Nothing else is open until they pay or choose to be a friend.
  await page.goto('portal/');
  await expect(page).toHaveURL(/\/portal\/join\/pay/);
  await expect(page.getByRole('navigation', { name: 'Portal sections' })).toHaveCount(0);

  await page.getByRole('radio', { name: /I changed my mind, I just want to be a friend/ }).check();
  await expect(page.getByRole('tab', { name: 'Test payment' })).toHaveCount(0);
  await page.getByRole('button', { name: 'Continue as a friend' }).click();

  // A friend may give, or not: the step offers a friend's contribution first.
  await expect(page.getByRole('heading', { name: 'Contribute to CalDART' })).toBeVisible();
  await expect(page).toHaveURL(/\/portal\/join\/pay/);
  await expect(page.getByRole('radio', { name: /Participating/ })).toBeVisible();
  await page.getByRole('button', { name: 'Not now' }).click();

  await expect(page).toHaveURL(/\/portal\/join\/done/);
  await expect(page.getByText('You are a friend of CalDART.', { exact: true })).toBeVisible();

  // The dashboard, with its rail, offers membership rather than a renewal.
  await page.getByRole('link', { name: 'Go to my dashboard' }).click();
  await expect(page).toHaveURL(/\/portal\/?$/);
  await expect(page.getByRole('navigation', { name: 'Portal sections' })).toBeVisible();
  const friendCard = membershipCard(page, 'You are a friend of CalDART');
  await expect(friendCard.getByRole('link', { name: /Renew/ })).toHaveCount(0);
  await friendCard.getByRole('link', { name: 'Make me a member' }).click();

  await expect(page).toHaveURL(/\/portal\/membership\/join/);
  await expect(page.getByRole('heading', { name: 'Become a member', level: 1 })).toBeVisible();
  // Becoming a member is paying for it: the friend card is the wizard's alone.
  await expect(
    page.getByRole('radio', { name: /I changed my mind, I just want to be a friend/ }),
  ).toHaveCount(0);
  await payWithMock(page);

  await expect(page).toHaveURL(/\/portal\/?$/);
  await expect(page.getByText('Thank you — you are a member of CalDART.')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Your membership is current' })).toBeVisible();
});

test('a joiner goes from member to friend and back again, then pays', async ({ page }) => {
  const email = uniqueEmail('undecided');
  await registerAccount(page, email, { as: 'member', firstName: 'Ulla' });
  await followVerificationLink(page, email);
  await completeProfileStep(page);

  await page.getByRole('radio', { name: /I changed my mind, I just want to be a friend/ }).check();
  await page.getByRole('button', { name: 'Continue as a friend' }).click();
  await expect(page.getByRole('heading', { name: 'Contribute to CalDART' })).toBeVisible();

  await page.getByRole('button', { name: 'I changed my mind, I want to be a member' }).click();
  await expect(page.getByRole('heading', { name: 'Pay your dues' })).toBeVisible();
  await expect(page).toHaveURL(/\/portal\/join\/pay/);
  await payWithMock(page);

  await expect(page).toHaveURL(/\/portal\/join\/done/);
  await expect(page.getByText('You are a member of CalDART.', { exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'Go to my dashboard' }).click();
  await expect(page).toHaveURL(/\/portal\/?$/);
  await expect(page.getByRole('heading', { name: 'Your membership is current' })).toBeVisible();
});
