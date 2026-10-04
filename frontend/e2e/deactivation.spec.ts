/**
 * A person deactivates their own account from the profile page, is signed out,
 * and brings the account back from the sign-in page with the same password.
 *
 * An account administrator deactivates and reactivates somebody else's account from
 * the member record's Delete or deactivate tab, and a user administrator blocks an account from
 * reactivating, after which its owner is told it has been closed.
 */
import { expect, test } from '@playwright/test';
import type { Locator, Page } from '@playwright/test';

import {
  DEMO,
  JOINER_PASSWORD as PASSWORD,
  completeOnboarding,
  emailCountTo,
  signIn,
  uniqueEmail,
} from './helpers';

/** What the owner of a blocked account is told, whatever the organization is called. */
const CLOSED = /^This account has been closed\. Contact .+ to reopen it\.$/;

/** A card on the page, found by its heading. */
function card(page: Page, heading: string): Locator {
  return page.locator('section.card', {
    has: page.getByRole('heading', { name: heading, exact: true }),
  });
}

/** Press an action that asks first, then the button in its panel that acts. */
async function confirm(scope: Locator, action: string): Promise<void> {
  await scope.getByRole('button', { name: action }).click();
  await scope.getByRole('region', { name: action }).getByRole('button', { name: action }).click();
}

/** Sign in as the person who owns `email`, through the portal's form. */
async function signInAs(page: Page, email: string): Promise<void> {
  await page.goto('portal/login');
  await page.getByRole('textbox', { name: 'Email address' }).fill(email);
  await page.getByLabel(/^Password/).fill(PASSWORD);
  await page.getByRole('button', { name: 'Sign in' }).click();
}

/** A fresh friend's account, signed out again, so no demo account is touched. */
async function freshFriend(page: Page, prefix: string): Promise<string> {
  const email = uniqueEmail(prefix);
  await completeOnboarding(page, email, { as: 'friend', firstName: 'Lena' });
  await page.context().clearCookies();
  return email;
}

/** Open the member record of the account at `email` on its Delete or deactivate tab. */
async function openDangerZone(page: Page, email: string): Promise<void> {
  const found = (await (
    await page.request.get(
      `api/v1/admin/members?include_inactive=true&search=${encodeURIComponent(email)}`,
    )
  ).json()) as { results: { user_id: number }[] };
  const row = found.results[0];
  expect(row).toBeDefined();
  await page.goto(`portal/admin/members/${row?.user_id ?? 0}`);
  await page.getByRole('tab', { name: 'Delete or deactivate' }).click();
}

test('a person deactivates their account and reactivates it at sign-in', async ({ page }) => {
  const email = uniqueEmail('leaver');

  // A fresh account, so no other spec's demo account is touched.
  await completeOnboarding(page, email, { as: 'friend', firstName: 'Lena' });

  // Deactivate from the foot of the profile page.
  await page.goto('portal/profile');
  const card = page.locator('section.card', {
    has: page.getByRole('heading', { name: 'Deactivate my account' }),
  });
  await card.getByLabel(/^Current password/).fill(PASSWORD);
  await card.getByRole('button', { name: 'Deactivate my account' }).click();

  await expect(page).toHaveURL(/\/portal\/login/);
  await expect(
    page.getByText('Your account is deactivated. Sign in any time to reactivate it.'),
  ).toBeVisible();

  // Signing in again is refused, with the offer to reactivate.
  await page.getByRole('textbox', { name: 'Email address' }).fill(email);
  await page.getByLabel(/^Password/).fill(PASSWORD);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByText('This account is deactivated. You can reactivate it.')).toBeVisible();
  await expect(
    page.getByText(
      'Reactivating brings back your roles and any membership that has not yet run out.',
    ),
  ).toBeVisible();

  // Reactivating signs the person in.
  await page.getByRole('button', { name: 'Reactivate my account' }).click();
  await expect(page).not.toHaveURL(/\/portal\/login/);
  await page.goto('portal/profile');
  await expect(page.getByRole('heading', { name: 'My profile' })).toBeVisible();
});

test('an account administrator deactivates and reactivates an account', async ({ page }) => {
  const email = await freshFriend(page, 'parted');

  await signIn(page, DEMO.accountadmin);
  await openDangerZone(page, email);
  const account = card(page, 'Account');
  await confirm(account, 'Deactivate account');
  await expect(account.getByRole('button', { name: 'Reactivate account' })).toBeVisible();
  await expect(page.getByText('Account deactivated', { exact: true })).toBeVisible();

  // The profile tab no longer carries an active switch.
  await page.getByRole('tab', { name: 'Profile' }).click();
  await expect(page.getByRole('checkbox', { name: /Account is active/ })).toHaveCount(0);

  // The person is refused, with the offer to reactivate.
  await page.context().clearCookies();
  await signInAs(page, email);
  await expect(page.getByText('This account is deactivated. You can reactivate it.')).toBeVisible();

  // The administrator brings the account back, and the person signs in again.
  await page.context().clearCookies();
  await signIn(page, DEMO.accountadmin);
  await openDangerZone(page, email);
  await confirm(card(page, 'Account'), 'Reactivate account');
  await expect(
    card(page, 'Account').getByRole('button', { name: 'Deactivate account' }),
  ).toBeVisible();

  await page.context().clearCookies();
  await signInAs(page, email);
  await expect(page).not.toHaveURL(/\/portal\/login/);
});

test('a user administrator blocks an account, and its owner cannot bring it back', async ({
  page,
}) => {
  const email = await freshFriend(page, 'closed');

  await signIn(page, DEMO.useradmin);
  await page.goto('portal/admin/users');
  await page
    .getByRole('combobox', { name: 'Account status' })
    .selectOption({ label: 'Active and deactivated' });
  await page.getByRole('searchbox', { name: 'Search' }).fill(email);
  await page.getByRole('row').filter({ hasText: email }).getByRole('link').click();
  const status = card(page, 'Account status');
  await confirm(status, 'Block reactivation');
  await expect(status.getByRole('button', { name: 'Allow reactivation' })).toBeVisible();
  await expect(status.getByRole('button', { name: 'Reactivate account' })).toBeDisabled();

  // Signing in with the right password is told the account is closed, and offered nothing.
  await page.context().clearCookies();
  await signInAs(page, email);
  await expect(page.getByText(CLOSED)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Reactivate my account' })).toHaveCount(0);

  // A password reset sends nothing.
  const before = emailCountTo(email);
  await page.goto('portal/forgot-password');
  await page.getByRole('textbox', { name: 'Email address' }).fill(email);
  await page.getByRole('button', { name: 'Email me a link' }).click();
  await expect(page.getByRole('heading', { name: 'Check your email' })).toBeVisible();
  expect(emailCountTo(email)).toBe(before);

  // Joining again with the address is refused the same way.
  await page.goto('portal/join');
  await page.getByRole('textbox', { name: 'First name' }).fill('Lena');
  await page.getByRole('textbox', { name: 'Last name' }).fill('Okafor');
  await page.getByRole('textbox', { name: 'Email address' }).fill(email);
  await page.getByLabel(/^Password/).fill(PASSWORD);
  await page.getByRole('button', { name: 'Create account' }).click();
  await expect(page.getByText(CLOSED)).toBeVisible();
});
