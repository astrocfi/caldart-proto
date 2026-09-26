/**
 * Somebody gives on a schedule from the Donate screen: monthly with the first
 * gift taken now, or quarterly with the first charge on a later day and nothing
 * taken today.  Either way the Payments screen then shows the Recurring donation
 * card with its cadence and its next charge.
 *
 * The account is created here rather than borrowed from the seed, so its
 * payments and its mandates are this spec's alone.  It pays no dues: a
 * recurring donation accompanies no membership.
 */
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

import { uniqueEmail } from './helpers';

/** How far out the later first charge falls. */
const LATER_DAYS = 10;

/** Create an account at the first step of the join wizard, which signs its owner in. */
async function createAccount(page: Page, email: string): Promise<void> {
  await page.goto('/portal/join');
  await page.getByRole('textbox', { name: 'First name' }).fill('Ines');
  await page.getByRole('textbox', { name: 'Last name' }).fill('Carvalho');
  await page.getByRole('textbox', { name: 'Email address' }).fill(email);
  await page.getByLabel(/^Password/).fill('a-long-demo-passphrase');
  await page.getByRole('button', { name: 'Create account' }).click();
  await expect(page.getByRole('heading', { name: 'Check your email' })).toBeVisible();
}

/** `day` as `YYYY-MM-DD`. */
function iso(day: Date): string {
  const month = String(day.getMonth() + 1).padStart(2, '0');
  const date = String(day.getDate()).padStart(2, '0');
  return `${day.getFullYear()}-${month}-${date}`;
}

/** `day` as the portal prints it. */
function display(day: Date): string {
  return iso(day).replaceAll('-', '/');
}

/**
 * The next charge the server stored for the signed-in person's donation, as the
 * portal prints it.  The server dates a charge in the organization's time zone,
 * which the runner's clock need not share, so the spec asks rather than works it out.
 */
async function storedNextCharge(page: Page): Promise<string> {
  const response = await page.request.get('/api/v1/me/donation');
  expect(response.ok()).toBe(true);
  const body = (await response.json()) as { mandate: { next_charge_on: string } | null };
  expect(body.mandate).not.toBeNull();
  return (body.mandate?.next_charge_on ?? '').replaceAll('-', '/');
}

/** The Recurring donation card on `/portal/payments`. */
function donationCard(page: Page) {
  return page
    .locator('section')
    .filter({ has: page.getByRole('heading', { name: 'Recurring donation' }) });
}

/** Choose the Participating tier on the Donate screen and make it recurring. */
async function chooseRecurringGift(page: Page): Promise<void> {
  await page.goto('/portal/donate');
  await expect(page.getByRole('heading', { name: 'Donate', level: 1 })).toBeVisible();
  await page.getByRole('radio', { name: /Participating/ }).check();
  await page.getByRole('checkbox', { name: 'Make this a recurring donation' }).check();
}

test('a monthly donation starting today is paid now and shows its next charge', async ({
  page,
}) => {
  await createAccount(page, uniqueEmail('monthly'));
  await chooseRecurringGift(page);

  await expect(page.getByRole('radio', { name: 'Monthly' })).toBeChecked();
  await expect(page.getByText(/today, and each month after that/)).toBeVisible();
  await page.getByRole('tab', { name: 'Test payment' }).click();
  await page.getByRole('button', { name: 'Succeed', exact: true }).click();

  await expect(page).toHaveURL(/\/portal\/payments$/);
  await expect(page.getByText('Thank you for your donation.').first()).toBeVisible();

  const card = donationCard(page);
  await expect(card.getByText('On', { exact: true })).toBeVisible();
  await expect(card.getByText('Monthly')).toBeVisible();
  await expect(card.getByText(await storedNextCharge(page))).toBeVisible();
  await expect(page.getByRole('link', { name: 'Receipt' })).toHaveCount(1);
});

test('a quarterly donation on a later day takes nothing today', async ({ page }) => {
  await createAccount(page, uniqueEmail('quarterly'));
  await chooseRecurringGift(page);

  const later = new Date();
  later.setDate(later.getDate() + LATER_DAYS);
  await page.getByRole('radio', { name: 'Quarterly' }).check();
  await page.getByLabel('First charge on').fill(iso(later));
  await expect(page.getByTestId('checkout-total')).toHaveText('$0.00');

  await page.getByRole('tab', { name: 'Test payment method' }).click();
  await page.getByRole('button', { name: 'Save this test card' }).click();

  await expect(page).toHaveURL(/\/portal\/payments$/);
  await expect(
    page.getByText(`Thank you. Your recurring donation starts on ${display(later)}.`).first(),
  ).toBeVisible();

  const card = donationCard(page);
  await expect(card.getByText('Quarterly')).toBeVisible();
  await expect(card.getByText(display(later))).toBeVisible();
  await expect(page.getByText('No payments yet')).toBeVisible();
});

test('a recurring donation is changed and turned off from the Payments screen', async ({
  page,
}) => {
  await createAccount(page, uniqueEmail('changer'));
  await chooseRecurringGift(page);
  await page.getByRole('tab', { name: 'Test payment' }).click();
  await page.getByRole('button', { name: 'Succeed', exact: true }).click();
  await expect(page).toHaveURL(/\/portal\/payments$/);

  const card = donationCard(page);
  await card.getByRole('button', { name: 'Change' }).click();
  await card.getByRole('radio', { name: 'Yearly' }).check();
  await card.getByRole('button', { name: 'Save changes' }).click();
  await expect(card.getByText('Yearly')).toBeVisible();

  await card.getByRole('button', { name: 'Turn off' }).click();
  await page.getByRole('button', { name: 'Yes, turn it off' }).click();
  await expect(page.getByText('Recurring donation is off.').first()).toBeVisible();
  await expect(card.getByRole('link', { name: 'Set up' })).toBeVisible();
});
