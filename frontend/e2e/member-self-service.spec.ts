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
  await expect(page.getByRole('heading', { name: 'Your membership is current' })).toBeVisible();

  // Edit the profile and see it stick.
  await page.goto('/portal/profile');
  await page.getByRole('textbox', { name: 'Total hours' }).fill('1234');
  await page.getByRole('textbox', { name: 'Home airport', exact: true }).fill('SQL');
  await page.getByRole('button', { name: 'Save profile' }).click();
  await expect(page.getByText('Profile saved.')).toBeVisible();

  await page.reload();
  await expect(page.getByRole('textbox', { name: 'Total hours' })).toHaveValue('1234');

  // The form says what it wants: no leading K, one primary DART, and ground
  // support among the volunteer interests.
  await expect(page.getByText('Three characters, omit the leading K')).toBeVisible();
  await expect(page.getByText('Your primary DART')).toBeVisible();
  await expect(page.getByRole('checkbox', { name: 'Ground support' })).toBeVisible();

  // My aircraft ledes in one sentence and offers one way to add an airplane.
  await page.goto('/portal/profile/aircraft');
  await expect(page.getByText('The planes you commonly fly.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Add a new aircraft' })).toHaveCount(1);
  await expect(page.getByText('Not in the register? Add it yourself.')).toBeVisible();

  // Attach an airplane from the picker, then search for it again: the picker
  // leaves it out of the results and names it in a sentence underneath.
  const search = page.getByRole('searchbox', { name: 'Search the aircraft register' });
  await search.fill('Cessna');
  const firstResult = page.locator('.aircraft-result__ident').first();
  await expect(firstResult).toBeVisible();
  const nNumber = (await firstResult.innerText()).trim();
  await page.locator('.aircraft-result__button').first().click();
  await expect(page.getByText(`${nNumber} added.`)).toBeVisible();

  await search.fill(nNumber);
  await expect(page.getByText(`${nNumber} is already on your list.`)).toBeVisible();

  // The dashboard lists the members-only pages, and one of them opens.
  await page.goto('/portal/');
  const memberContent = page
    .locator('section')
    .filter({ has: page.getByRole('heading', { name: 'Member content' }) });
  const memberLink = memberContent.getByRole('listitem').getByRole('link').first();
  await expect(memberLink).toBeVisible();
  const title = (await memberLink.innerText()).trim();
  await memberLink.click();
  await expect(page.getByRole('heading', { level: 1, name: title })).toBeVisible();
  // The page itself, not the wall.
  await expect(page.getByRole('link', { name: 'Renew my membership' })).toHaveCount(0);
});

test('signing out takes a button, and no address can do it', async ({ page }) => {
  await signIn(page, DEMO.member);

  // Opening the old sign-out address is just an unknown path, and the session
  // survives it: the dashboard still knows who is here.
  await page.goto('/portal/logout');
  await expect(page.getByRole('heading', { level: 1, name: 'Page not found' })).toBeVisible();
  await page.goto('/portal/');
  await expect(page.getByRole('heading', { name: /^Welcome, / })).toBeVisible();

  await page.getByRole('button', { name: 'Sign out' }).click();
  await expect(page).toHaveURL(/\/portal\/login/);

  // The session really ended: a guarded screen asks for a sign-in again.
  await page.goto('/portal/profile');
  await expect(page).toHaveURL(/\/portal\/login\?next=%2Fprofile/);
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

test('a member reads their payments, and every settled one offers its receipt', async ({
  page,
}) => {
  await signIn(page, DEMO.member);

  await page
    .getByRole('navigation', { name: 'Portal sections' })
    .getByRole('link', {
      name: 'Payments',
    })
    .click();
  await expect(page).toHaveURL(/\/portal\/payments$/);
  await expect(page.getByRole('heading', { level: 1, name: 'Payments' })).toBeVisible();

  // The seeded member has paid dues more than once, so the table has rows and
  // each settled row carries a receipt.
  const receipts = page.getByRole('link', { name: 'Receipt' });
  await expect(receipts.first()).toBeVisible();

  const href = await receipts.first().getAttribute('href');
  const response = await page.request.get(href ?? '');
  expect(response.status()).toBe(200);
  expect(response.headers()['content-type']).toBe('application/pdf');
});
