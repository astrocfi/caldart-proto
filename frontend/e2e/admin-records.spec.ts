/**
 * The administration records where only a laid-out page or a real sign-in can show the
 * behavior: an account an administrator created signing in for the first time, a member
 * record's summary at phone width, the New member form's rows, and the DART form's
 * submit button holding still as the airports are checked.
 */
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

import { DEMO, JOINER_PASSWORD, followVerificationLink, signIn, uniqueEmail } from './helpers';

const PHONE = { width: 390, height: 844 };
const DESKTOP = { width: 1920, height: 1080 };

/** Create Pat Quinn on New member as the account administrator; return the record's path. */
async function createMember(page: Page, email: string): Promise<string> {
  await signIn(page, DEMO.accountadmin);
  await page.goto('portal/admin/members/new');
  await page.getByLabel(/^Email address/).fill(email);
  await page.getByLabel(/^First name/).fill('Pat');
  await page.getByLabel(/^Last name/).fill('Quinn');
  await page.getByLabel(/^Password/).fill(JOINER_PASSWORD);
  await page.getByRole('button', { name: 'Add member' }).click();
  await expect(page).toHaveURL(/\/portal\/admin\/members\/\d+$/);
  // Relative to the run's base address, which carries any URL prefix itself.
  const record = /portal\/admin\/members\/\d+$/.exec(page.url());
  if (record === null) throw new Error(`Not on a member record: ${page.url()}`);
  return record[0];
}

/** Sign in as the account just created, with the password the administrator gave it. */
async function signInAsCreated(page: Page, email: string): Promise<void> {
  await page.context().clearCookies();
  await page.goto('portal/login');
  await page.getByRole('textbox', { name: 'Email address' }).fill(email);
  await page.getByLabel(/^Password/).fill(JOINER_PASSWORD);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page).not.toHaveURL(/\/portal\/login/);
}

/** The pixels between the bottom of a field's label and the top of its box. */
async function labelToBox(page: Page, label: RegExp): Promise<number> {
  const box = await page.getByLabel(label).boundingBox();
  const caption = await page.locator('label', { hasText: label }).first().boundingBox();
  if (box === null || caption === null) throw new Error(`${label} is not laid out`);
  return box.y - (caption.y + caption.height);
}

test('an account an administrator created verifies its address, then opens the dashboard', async ({
  page,
}) => {
  const email = uniqueEmail('created');
  await createMember(page, email);

  await signInAsCreated(page, email);
  await expect(page).toHaveURL(/\/portal\/join\/verify/);

  await followVerificationLink(page, email);
  await signInAsCreated(page, email);

  await expect(page).toHaveURL(/\/portal\/?$/);
  await expect(page.getByText(/didn.t load|could not be read/)).toHaveCount(0);
});

test('a member record with no term reads whole at phone width, with no sideways scroll', async ({
  page,
}) => {
  const path = await createMember(page, uniqueEmail('noterm'));
  await page.setViewportSize(PHONE);
  await page.goto(path);
  await expect(page.getByText(/No membership yet/)).toBeVisible();

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});

test('New member lines up the names with no hint above either box', async ({ page }) => {
  await page.setViewportSize(DESKTOP);
  await signIn(page, DEMO.accountadmin);
  await page.goto('portal/admin/members/new');

  const first = await labelToBox(page, /^First name/);
  expect(await labelToBox(page, /^Last name/)).toBeCloseTo(first, 0);
});

test('the DART form holds its button still as the airports are checked on the way to it', async ({
  page,
}) => {
  await page.setViewportSize(DESKTOP);
  await signIn(page, DEMO.accountadmin);
  await page.goto('portal/admin/darts');
  await page.getByRole('button', { name: 'New DART' }).click();
  await page.getByLabel('Name*').fill('Steady Button');
  await page.getByLabel('Airports*').fill('PA');
  const button = page.getByRole('button', { name: 'Add DART' });
  const before = await button.boundingBox();

  await button.focus();

  await expect(page.getByLabel('Airports*')).toHaveAttribute('aria-invalid', 'true');
  expect((await button.boundingBox())?.y).toBeCloseTo(before?.y ?? Number.NaN, 0);
});
