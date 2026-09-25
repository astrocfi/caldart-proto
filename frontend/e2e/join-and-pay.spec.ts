/**
 * Flow A in `docs/demo-walkthrough.rst`: a visitor signs up and pays, and is a
 * current member immediately.
 *
 * Runs at desktop and at iPhone size, because this is the flow most likely to
 * happen on a phone at an airfield.  Payment goes through the mock provider,
 * which is what `PAYMENTS_MOCK_ENABLED` is for.
 */
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

import { SEED, formatCents, signIn, uniqueEmail } from './helpers';

/**
 * Walk the public site the way a visitor does: the Join CalDART page from the
 * navigation bar, then the call to action on it.  On a phone the bar is behind
 * the Menu button.
 */
async function joinFromPublicSite(page: Page): Promise<void> {
  await page.goto('/');
  // Scope to the bar: the welcome box carries a "Join CalDART" button of its
  // own, and on a phone the bar's copy is behind the Menu button.
  const join = page
    .getByRole('navigation', { name: 'Main' })
    .getByRole('link', { name: 'Join CalDART', exact: true });
  if (!(await join.isVisible())) {
    await page.getByRole('button', { name: 'Menu' }).click();
    await expect(join).toBeVisible();
  }
  await join.click();
  await expect(page).toHaveURL(/\/join\/$/);

  await page.getByRole('link', { name: 'Start your membership' }).click();
  await expect(page).toHaveURL(/\/portal\/join/);
}

/** Steps 1 and 2: an account, then the fields that make the profile complete. */
async function register(page: Page, first: string, email: string): Promise<void> {
  await page.getByRole('textbox', { name: 'First name' }).fill(first);
  await page.getByRole('textbox', { name: 'Last name' }).fill('Okonkwo');
  await page.getByRole('textbox', { name: 'Email address' }).fill(email);
  await page.getByLabel(/^Password/).fill('a-long-demo-passphrase');
  await page.getByRole('button', { name: 'Create account' }).click();

  await expect(page.getByRole('heading', { name: 'About you' })).toBeVisible();
  await page.getByRole('textbox', { name: 'Phone', exact: true }).fill('650-555-0142');
  await page.getByRole('textbox', { name: 'Address', exact: true }).fill('12 Skyway Road');
  await page.getByRole('textbox', { name: 'City', exact: true }).fill('San Carlos');
  await page.getByRole('textbox', { name: 'ZIP code', exact: true }).fill('94070');
  await page.getByRole('button', { name: 'Save and continue' }).click();
  await expect(page.getByRole('heading', { name: 'Pay your dues' })).toBeVisible();
}

test('a visitor joins from the public site and pays their dues', async ({ page }) => {
  const email = uniqueEmail('joiner');

  await joinFromPublicSite(page);
  await expect(page).toHaveURL(/\/portal\/join\/account/);
  await register(page, 'Wilma', email);

  // Step 3 — pay with the mock provider.
  await page.getByRole('tab', { name: 'Test payment' }).click();
  await expect(page.getByTestId('checkout-total')).toHaveText(
    formatCents(SEED.planPricesCents.annual),
  );
  await page.getByRole('button', { name: 'Succeed', exact: true }).click();

  // Step 4 — done, and the membership is live.
  await expect(page.getByRole('heading', { name: 'Welcome to CalDART' })).toBeVisible();
  await expect(page.getByText(/Your membership runs until/)).toBeVisible();

  // The dashboard agrees.
  await page.getByRole('link', { name: 'Go to my dashboard' }).click();
  await expect(page).toHaveURL(/\/portal\/?$/);
  await expect(page.getByRole('heading', { name: /Welcome, Wilma/ })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Your membership is current' })).toBeVisible();
  await expect(page.getByText('Current', { exact: true })).toBeVisible();
});

test('a declined payment says so and leaves the visitor able to try again', async ({ page }) => {
  await page.goto('/portal/join');
  await register(page, 'Dez', uniqueEmail('payer'));

  await page.getByRole('tab', { name: 'Test payment' }).click();
  await page.getByRole('button', { name: 'Fail', exact: true }).click();

  await expect(page.getByRole('alert')).toContainText('declined');
  await expect(page).toHaveURL(/\/portal\/join\/pay/);
  await expect(page.getByRole('button', { name: 'Succeed', exact: true })).toBeEnabled();
});

test('a life member contributes where the renew screen would renew', async ({ page }) => {
  await signIn(page, SEED.contributionMandate.email);
  await page.goto('/portal/renew');

  await expect(page.getByRole('heading', { name: 'Contribute to CalDART' })).toBeVisible();
  await expect(page.getByText('You are a life member. Thank you.')).toBeVisible();
  // Nothing is on sale here: a life member has bought their membership already.
  await expect(page.getByRole('radio', { name: /Annual/ })).toHaveCount(0);

  await page.getByRole('radio', { name: /Participating/ }).check();
  await page.getByRole('tab', { name: 'Test payment' }).click();
  await page.getByRole('button', { name: 'Succeed', exact: true }).click();

  await expect(page.getByText('Thank you for your contribution.').first()).toBeVisible();
  await expect(page).toHaveURL(/\/portal\/?$/);
});
