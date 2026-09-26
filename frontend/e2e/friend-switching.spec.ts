/**
 * A member becomes a friend of CalDART from the dashboard, and a friend becomes a
 * member again by paying.
 *
 * A member whose membership is current becomes a friend the day after it runs out, and
 * can undo that until then; a member with nothing current becomes one at once.
 * Payment goes through the mock provider, which is what `PAYMENTS_MOCK_ENABLED` is for.
 */
import { expect, test } from '@playwright/test';
import type { Locator, Page } from '@playwright/test';

import { followVerificationLink, uniqueEmail } from './helpers';

/**
 * Steps 1 to 3 as a member: the account, the link mailed to its address, and the
 * fields that make the profile complete.  Ends on the pay step.
 */
async function registerMember(page: Page, first: string, email: string): Promise<void> {
  await page.goto('/portal/join');
  await page.getByRole('textbox', { name: 'First name' }).fill(first);
  await page.getByRole('textbox', { name: 'Last name' }).fill('Castellanos');
  await page.getByRole('textbox', { name: 'Email address' }).fill(email);
  await page.getByLabel(/^Password/).fill('a-long-demo-passphrase');
  await page.getByRole('button', { name: 'Create account' }).click();
  await expect(page.getByRole('heading', { name: 'Check your email' })).toBeVisible();
  await followVerificationLink(page, email);

  await expect(page.getByRole('heading', { name: 'About you' })).toBeVisible();
  await page.getByRole('textbox', { name: 'Phone', exact: true }).fill('650-555-0161');
  await page.getByRole('textbox', { name: 'Address', exact: true }).fill('7 Taxiway Court');
  await page.getByRole('textbox', { name: 'City', exact: true }).fill('Watsonville');
  await page.getByRole('textbox', { name: 'ZIP code', exact: true }).fill('95076');
  await page.getByRole('button', { name: 'Save and continue' }).click();
  await expect(page.getByRole('heading', { name: 'Pay your dues' })).toBeVisible();
}

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
  await registerMember(page, 'Rosa', uniqueEmail('switcher'));
  await payWithMock(page);
  await expect(page.getByRole('heading', { name: 'Welcome to CalDART' })).toBeVisible();
  await page.getByRole('link', { name: 'Go to my dashboard' }).click();

  const card = membershipCard(page, 'Your membership is current');
  await card.getByRole('button', { name: 'Make me a friend' }).click();
  await expect(
    card.getByText(/^Your membership stays current through \d{4}\/\d{2}\/\d{2}\./),
  ).toBeVisible();
  await card.getByRole('button', { name: 'Make me a friend' }).click();

  // The membership stays current, and the day of the change is shown.
  await expect(card.getByText(/^You become a friend on \d{4}\/\d{2}\/\d{2}\.$/)).toBeVisible();
  await card.getByRole('button', { name: 'Undo' }).click();
  await expect(card.getByRole('button', { name: 'Make me a friend' })).toBeVisible();
});

test('a member with nothing current becomes a friend at once, then a member', async ({ page }) => {
  await registerMember(page, 'Tomas', uniqueEmail('unpaid'));
  // Leave the pay step without paying.
  await page.goto('/portal/');

  await membershipCard(page, 'You are not a member yet')
    .getByRole('button', { name: 'Make me a friend' })
    .click();
  await expect(
    page.getByText(
      'You become a friend of CalDART today: no dues, no expiry, and no renewal reminders.',
    ),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Make me a friend' }).click();

  const friendCard = membershipCard(page, 'You are a friend of CalDART');
  await expect(friendCard).toBeVisible();
  await friendCard.getByRole('link', { name: 'Make me a member' }).click();

  await expect(page).toHaveURL(/\/portal\/membership\/join/);
  await expect(page.getByRole('heading', { name: 'Become a member', level: 1 })).toBeVisible();
  await payWithMock(page);

  await expect(page).toHaveURL(/\/portal\/?$/);
  await expect(page.getByText('Thank you — you are a member of CalDART.')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Your membership is current' })).toBeVisible();
});
