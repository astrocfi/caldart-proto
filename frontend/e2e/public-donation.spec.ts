/**
 * A visitor who is not signed in gives through the public donation page: an amount,
 * their name, address and phone, then the mock provider.  The page thanks them, the
 * receipt reaches their address without a link to a portal they cannot sign in to,
 * and a second gift from the same address goes to the same donor.  An address that
 * already belongs to a member is sent to sign in instead.
 */
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

import { DEMO, latestEmailTo, uniqueEmail } from './helpers';

/** Fill in a $100 gift from `email` and go on to the payment. */
async function startGift(page: Page, email: string): Promise<void> {
  await page.goto('/donate/');
  await page.getByRole('radio', { name: /Bronze/ }).check();
  await page.getByRole('textbox', { name: 'First name' }).fill('Rosa');
  await page.getByRole('textbox', { name: 'Last name' }).fill('Delgado');
  await page.getByRole('textbox', { name: 'Email' }).fill(email);
  await page.getByRole('textbox', { name: 'Phone' }).fill('707-555-0142');
  await page.getByRole('button', { name: 'Continue to payment' }).click();
  await expect(page.getByText(`You are giving $100.00 as Rosa Delgado (${email}).`)).toBeVisible();
}

test('a visitor gives from a new address and is thanked', async ({ page }) => {
  const email = uniqueEmail('giver');
  await startGift(page, email);

  await page.getByRole('button', { name: 'Succeed' }).click();

  await expect(page.getByText(`A receipt is on its way to ${email}.`)).toBeVisible();
  await expect(page.getByText(/Thank you\. Your gift keeps CalDART/)).toBeVisible();
});

test("the donor's receipt carries no link to the portal", async ({ page }) => {
  const email = uniqueEmail('receipt');
  await startGift(page, email);
  await page.getByRole('button', { name: 'Succeed' }).click();
  await expect(page.getByText(`A receipt is on its way to ${email}.`)).toBeVisible();

  const receipt = await latestEmailTo(email);

  expect(receipt).toContain('Contribution: $100.00');
  expect(receipt).not.toContain('/portal/payments');
});

test('a second gift from the same address is taken as well', async ({ page }) => {
  const email = uniqueEmail('again');
  await startGift(page, email);
  await page.getByRole('button', { name: 'Succeed' }).click();
  await expect(page.getByText(`A receipt is on its way to ${email}.`)).toBeVisible();

  await startGift(page, email);
  await page.getByRole('button', { name: 'Succeed' }).click();

  await expect(page.getByText(`A receipt is on its way to ${email}.`)).toBeVisible();
});

test("a member's address is sent to sign in", async ({ page }) => {
  await startGift(page, DEMO.member);

  await page.getByRole('button', { name: 'Succeed' }).click();

  await expect(page.getByRole('alert')).toHaveText(
    'An account already uses that email address. Sign in to donate.',
  );
});
