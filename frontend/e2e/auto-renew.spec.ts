/**
 * A member turns automatic renewal on while paying, reads the standing
 * authority on their Payments screen, downloads a receipt, and turns it off
 * again.
 *
 * The account is created here rather than borrowed from the seed, because the
 * seeded members already carry mandates of their own and this flow is about a
 * member who has never had one.  The life member at the end is the seeded one:
 * their authority is over a contribution, since nothing of theirs renews.
 */
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

import { SEED, formatCents, signIn, uniqueEmail } from './helpers';

/** Steps 1 and 2 of the join wizard: an account, then a usable profile. */
async function register(page: Page, email: string): Promise<void> {
  await page.goto('/portal/join');
  await page.getByRole('textbox', { name: 'First name' }).fill('Rosa');
  await page.getByRole('textbox', { name: 'Last name' }).fill('Belmonte');
  await page.getByRole('textbox', { name: 'Email address' }).fill(email);
  await page.getByLabel(/^Password/).fill('a-long-demo-passphrase');
  await page.getByRole('button', { name: 'Create account' }).click();

  await expect(page.getByRole('heading', { name: 'About you' })).toBeVisible();
  await page.getByRole('textbox', { name: 'Phone', exact: true }).fill('650-555-0177');
  await page.getByRole('textbox', { name: 'Address', exact: true }).fill('9 Runway Lane');
  await page.getByRole('textbox', { name: 'City', exact: true }).fill('San Carlos');
  await page.getByRole('textbox', { name: 'ZIP code', exact: true }).fill('94070');
  await page.getByRole('button', { name: 'Save and continue' }).click();
  await expect(page.getByRole('heading', { name: 'Pay your dues' })).toBeVisible();
}

/** How far out the day this spec chooses falls: past any term it buys. */
const CHOSEN_CHARGE_YEARS = 5;

/** The same day of the month `years` from today, as `YYYY-MM-DD`. */
function yearsOnIso(years: number): string {
  const today = new Date();
  const next = new Date(today.getFullYear() + years, today.getMonth(), today.getDate());
  const month = String(next.getMonth() + 1).padStart(2, '0');
  const day = String(next.getDate()).padStart(2, '0');
  return `${next.getFullYear()}-${month}-${day}`;
}

/** The same day `years` from today, as the portal prints it. */
function yearsOnDisplay(years: number): string {
  return yearsOnIso(years).replaceAll('-', '/');
}

/** The day the signed-in member's membership runs out, from the API itself. */
async function expiryIso(page: Page): Promise<string> {
  const response = await page.request.get('/api/v1/me/membership');
  const body = (await response.json()) as { expires_on: string | null };
  expect(body.expires_on).not.toBeNull();
  return body.expires_on ?? '';
}

/** The card on `/portal/payments` headed `title`. */
function authorityCard(page: Page, title: string) {
  return page.locator('section').filter({ has: page.getByRole('heading', { name: title }) });
}

/** The Automatic renewal card on `/portal/payments`. */
function renewalCard(page: Page) {
  return authorityCard(page, 'Automatic renewal');
}

test('a member pays with renewal on, reads it, takes a receipt, and turns it off', async ({
  page,
}) => {
  await register(page, uniqueEmail('renewer'));

  // Pay with renewal on: the checkbox belongs to the annual plan, which is the
  // default, and the mock provider stands in for a card.
  await page.getByRole('checkbox', { name: 'Renew automatically each year' }).check();
  await page.getByRole('tab', { name: 'Test payment' }).click();
  await page.getByRole('button', { name: 'Succeed', exact: true }).click();

  await expect(page.getByRole('heading', { name: 'Welcome to CalDART' })).toBeVisible();
  await expect(page.getByText(/A receipt is on its way to your inbox/)).toBeVisible();

  // The Payments screen names the saved method and what will be charged.
  await page.goto('/portal/payments');
  const card = renewalCard(page);
  await expect(card.getByText('On', { exact: true })).toBeVisible();
  await expect(card.getByText('Test card ending 4242, expires 12/2030')).toBeVisible();
  await expect(card.getByText(formatCents(SEED.planPricesCents.annual))).toBeVisible();

  // Nothing was chosen at the checkout, so the charge falls on the day the term
  // it bought runs out.
  const expiry = await expiryIso(page);
  await expect(card.getByText(expiry.replaceAll('-', '/'))).toBeVisible();

  // The receipt the email carried can be fetched again, and it is a PDF.
  const receipt = page.getByRole('link', { name: 'Receipt' }).first();
  const href = await receipt.getAttribute('href');
  expect(href).not.toBeNull();
  const response = await page.request.get(href ?? '');
  expect(response.status()).toBe(200);
  expect(response.headers()['content-type']).toBe('application/pdf');

  // Turning it off asks first, and then the card says so.
  await card.getByRole('button', { name: 'Turn off' }).click();
  await page.getByRole('button', { name: 'Yes, turn it off' }).click();
  await expect(page.getByText('Automatic renewal is off.').first()).toBeVisible();
  await expect(card.getByText('Off', { exact: true })).toBeVisible();
  await expect(card.getByRole('button', { name: 'Turn on' })).toBeVisible();
});

test('a member turns automatic renewal on from the Payments screen alone', async ({ page }) => {
  await register(page, uniqueEmail('later'));

  // Pay without renewal, so the mandate is created on the Payments screen.
  await page.getByRole('tab', { name: 'Test payment' }).click();
  await page.getByRole('button', { name: 'Succeed', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Welcome to CalDART' })).toBeVisible();

  await page.goto('/portal/payments');
  const card = renewalCard(page);
  await expect(card.getByText('Off', { exact: true })).toBeVisible();

  await card.getByRole('button', { name: 'Turn on' }).click();

  // The first charge opens on the day the membership just bought runs out, and
  // any later day may be asked for instead.
  const firstCharge = card.getByLabel('First charge on');
  await expect(firstCharge).toHaveValue(await expiryIso(page));
  await firstCharge.fill(yearsOnIso(CHOSEN_CHARGE_YEARS));
  await expect(
    card.getByText(new RegExp(`on ${yearsOnDisplay(CHOSEN_CHARGE_YEARS)}, and each year after`)),
  ).toBeVisible();

  await card.getByRole('tab', { name: 'Test payment method' }).click();
  await card.getByRole('button', { name: 'Save this test card' }).click();

  await expect(page.getByText('Automatic renewal is on.').first()).toBeVisible();
  await expect(card.getByText('On', { exact: true })).toBeVisible();
  await expect(card.getByText('Test card ending 4242, expires 12/2030')).toBeVisible();

  // The day the member chose is the day the card reads back, and it is late
  // enough that the card says the membership runs out first.
  await expect(card.getByText(yearsOnDisplay(CHOSEN_CHARGE_YEARS))).toBeVisible();
  await expect(card.getByText(/after your membership runs out on/)).toBeVisible();
});

test('a life member reads their automatic contribution, turns it off, and turns it on again', async ({
  page,
}) => {
  await signIn(page, SEED.contributionMandate.email);
  await page.goto('/portal/payments');

  // The card is about the contribution: their membership never runs out.
  const card = authorityCard(page, 'Automatic contribution');
  await expect(card.getByText('On', { exact: true })).toBeVisible();
  await expect(card.getByText('Contribution charged each year')).toBeVisible();
  await expect(card.locator('dd').filter({ hasText: /\d{4}\/\d{2}\/\d{2} · \$/ })).toBeVisible();

  await card.getByRole('button', { name: 'Turn off' }).click();
  await page.getByRole('button', { name: 'Yes, turn it off' }).click();
  await expect(page.getByText('Automatic contribution is off.').first()).toBeVisible();
  await expect(card.getByText('Off', { exact: true })).toBeVisible();

  // Turning it on again offers a contribution and no plan at all, and the first
  // charge falls a year out: a life membership has no expiry to take.
  await card.getByRole('button', { name: 'Turn on' }).click();
  await expect(card.getByRole('radio', { name: /Annual/ })).toHaveCount(0);
  await expect(
    card.getByText(new RegExp(`on ${yearsOnDisplay(1)}, and each year after`)),
  ).toBeVisible();
  await card.getByRole('radio', { name: /Participating/ }).check();
  await card.getByRole('tab', { name: 'Test payment method' }).click();
  await card.getByRole('button', { name: 'Save this test card' }).click();

  await expect(page.getByText('Automatic contribution is on.').first()).toBeVisible();
  await expect(card.getByText('On', { exact: true })).toBeVisible();
  await expect(card.locator('dd').filter({ hasText: /\d{4}\/\d{2}\/\d{2} · \$/ })).toBeVisible();
});
