/**
 * Flow B in `docs/demo-walkthrough.rst`: a member logs in, edits their
 * profile, and opens a members-only page.  The wall's other two states are
 * checked here too, because they are what makes a membership mean anything.
 */
import { expect, test } from '@playwright/test';

import { DEMO, DEMO_PASSWORD, signIn } from './helpers';

test('a member signs in, edits their profile and reads members-only content', async ({ page }) => {
  await signIn(page, DEMO.member);

  // The dashboard names them and says where their membership stands.
  await expect(page).toHaveURL(/\/portal\/?$/);
  await expect(page.getByRole('heading', { name: /^Welcome, / })).toBeVisible();
  await expect(page.locator('.dashboard__status .chip')).toHaveAttribute(
    'data-tone',
    /current|expiring/,
  );

  // Edit the profile and see it stick.
  await page.goto('/portal/profile');
  await page.getByRole('textbox', { name: 'Total hours' }).fill('1234');
  await page.getByRole('textbox', { name: 'Home airport', exact: true }).fill('SQL');
  await page.getByRole('button', { name: 'Save profile' }).click();
  await expect(page.getByText('Profile saved.')).toBeVisible();

  await page.reload();
  await expect(page.getByRole('textbox', { name: 'Total hours' })).toHaveValue('1234');

  // The dashboard lists the members-only pages, and one of them opens.
  await page.goto('/portal/');
  const memberLink = page.locator('.dashboard__links a[href^="/members"]').first();
  await expect(memberLink).toBeVisible();
  const title = (await memberLink.innerText()).trim();
  await memberLink.click();
  await expect(page.getByRole('heading', { level: 1, name: title })).toBeVisible();
  // The page itself, not the wall.
  await expect(page.getByRole('link', { name: 'Renew my membership' })).toHaveCount(0);
});

test('an expired member is walled out and offered a renewal', async ({ page }) => {
  await signIn(page, DEMO.expired);

  const response = await page.goto('/members/');
  expect(response?.status()).toBe(403);

  await page.locator('#main').getByRole('link', { name: 'Renew my membership' }).click();
  await expect(page).toHaveURL(/\/portal\/renew/);
  await expect(
    page.getByRole('heading', { level: 1, name: 'Renew your membership' }),
  ).toBeVisible();
});

test('a signed-out visitor is asked to sign in and comes back where they were', async ({
  page,
}) => {
  const response = await page.goto('/members/');
  expect(response?.status()).toBe(403);
  // The wall's own two calls to action, not the site header's.
  const wall = page.locator('#main');
  await expect(wall.getByRole('link', { name: 'Sign in' })).toBeVisible();
  await expect(wall.getByRole('link', { name: 'Join CalDART' })).toBeVisible();

  await page.goto('/portal/profile');
  await expect(page).toHaveURL(/\/portal\/login\?next=%2Fprofile/);
  await page.getByRole('textbox', { name: 'Email address' }).fill(DEMO.member);
  await page.getByLabel(/^Password/).fill(DEMO_PASSWORD);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page).toHaveURL(/\/portal\/profile$/);
});
