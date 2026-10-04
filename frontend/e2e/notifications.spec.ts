/**
 * Notifications as an account administrator sets them up: an address outside
 * CalDART subscribed to sign-ups, a visitor joining as a friend with a DART,
 * the sign-up email at that address and at the DART's roster contact, and an
 * edit that drops sign-ups, after which a second friend's sign-up reaches the
 * roster contact alone and a deactivation sends the address nothing.
 */
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

import {
  DEMO,
  emailCountTo,
  followVerificationLink,
  latestEmailTo,
  signIn,
  uniqueEmail,
} from './helpers';

/** One DART as `GET /api/v1/admin/darts` answers, cut to what this spec reads. */
interface AdminDart {
  id: number;
  name: string;
  is_active: boolean;
  contacts: { email: string; receives_roster: boolean }[];
}

/** A DART a joiner can choose, and one address its roster goes to. */
interface RosterDart {
  id: number;
  name: string;
  rosterEmail: string;
}

/**
 * The first active DART with somebody ticked to receive its roster, read as the
 * signed-in account administrator.  Read rather than copied out of the seed, so
 * an earlier spec that changed a DART's people cannot leave this one stale.
 */
async function rosterDart(page: Page): Promise<RosterDart> {
  const response = await page.request.get('api/v1/admin/darts');
  expect(response.status()).toBe(200);
  const darts = (await response.json()) as AdminDart[];
  for (const dart of darts) {
    const contact = dart.contacts.find((each) => each.receives_roster && each.email !== '');
    if (dart.is_active && contact !== undefined) {
      return { id: dart.id, name: dart.name, rosterEmail: contact.email };
    }
  }
  throw new Error('No active DART has anybody ticked to receive its roster.');
}

/**
 * End the session by dropping its cookies, which works from any screen,
 * including the join wizard's, where the portal shows no Sign out button.
 */
async function signOut(page: Page): Promise<void> {
  await page.context().clearCookies();
}

/**
 * Join as a friend through the public wizard, choosing `dartId` on the profile
 * step, whose save is the sign-up the notification announces.  Ends on the
 * friend's pay step.
 */
async function joinAsFriend(
  page: Page,
  { first, email, dartId }: { first: string; email: string; dartId: number },
): Promise<void> {
  await page.goto('portal/join');
  await page.getByRole('radio', { name: /Join as a friend/ }).check();
  await page.getByRole('textbox', { name: 'First name' }).fill(first);
  await page.getByRole('textbox', { name: 'Last name' }).fill('Nansen');
  await page.getByRole('textbox', { name: 'Email address' }).fill(email);
  await page.getByLabel(/^Password/).fill('a-long-demo-passphrase');
  await page.getByRole('button', { name: 'Create account' }).click();
  await expect(page).toHaveURL(/\/portal\/join\/verify/);
  await followVerificationLink(page, email);

  await expect(page.getByRole('heading', { name: 'About you' })).toBeVisible();
  await page.getByRole('textbox', { name: 'Phone', exact: true }).fill('650-555-0144');
  await page.getByRole('combobox', { name: 'Address', exact: true }).fill('9 Taxiway Court');
  await page.getByRole('textbox', { name: 'City', exact: true }).fill('Watsonville');
  await page.getByRole('textbox', { name: 'ZIP code', exact: true }).fill('95076');
  await page.getByRole('combobox', { name: 'DART' }).selectOption(String(dartId));
  await page.getByRole('button', { name: 'Save and continue' }).click();
  await expect(page).toHaveURL(/\/portal\/join\/pay/);
}

test('an outside address hears of a sign-up, and stops once sign-ups are dropped', async ({
  page,
}) => {
  const outside = uniqueEmail('nosy');
  const first = `Nora${Date.now().toString(36)}`;
  const joiner = uniqueEmail('joiner');

  // The account administrator subscribes an address no account holds.
  await signIn(page, DEMO.accountadmin);
  const dart = await rosterDart(page);
  await page
    .getByRole('navigation', { name: 'Portal sections' })
    .getByRole('link', { name: 'Notifications' })
    .click();
  await expect(page).toHaveURL(/\/portal\/admin\/notifications/);
  await page.getByRole('button', { name: 'New subscription' }).click();
  const form = page.getByRole('form', { name: 'New subscription' });
  await form.getByLabel(/^Recipient email/).fill(outside);
  await form.getByRole('checkbox', { name: 'Sign-up', exact: true }).check();
  await form.getByRole('checkbox', { name: 'Friend became a member', exact: true }).check();
  await form.getByRole('button', { name: 'Save' }).click();

  // The server asks for the outside address to be confirmed before it saves.
  await expect(form.getByRole('alert')).toHaveText(
    'Tick the box to confirm this address may receive these notifications.',
  );
  await form.getByRole('checkbox', { name: /This address is outside CalDART/ }).check();
  const saved = page.waitForResponse(
    (response) =>
      response.url().endsWith('/notifications/subscriptions') &&
      response.request().method() === 'POST',
  );
  await form.getByRole('button', { name: 'Save' }).click();
  expect((await saved).status()).toBe(201);
  await expect(form).toHaveCount(0);

  const card = page
    .locator('section.card')
    .filter({ has: page.getByRole('heading', { name: 'Who hears about what' }) });
  const row = card.getByRole('row').filter({ hasText: outside });
  await expect(row).toContainText('Sign-up, Friend became a member');
  await signOut(page);

  // A visitor joins as a friend of that DART.
  await joinAsFriend(page, { first, email: joiner, dartId: dart.id });
  const headline = `${first} Nansen signed up as a friend`;

  const toOutside = await latestEmailTo(outside);
  expect(toOutside).toContain(headline);
  expect(toOutside).toContain(`DART: ${dart.name}`);
  expect(emailCountTo(outside)).toBe(1);
  // The roster contact may hold older mail, so wait for the newest to be this one.
  await expect.poll(() => latestEmailTo(dart.rosterEmail)).toContain(headline);
  await signOut(page);

  // The account administrator drops sign-ups from the subscription.
  await signIn(page, DEMO.accountadmin);
  await page.goto('portal/admin/notifications');
  await row.getByRole('button', { name: 'Edit' }).click();
  const edit = page.getByRole('form', { name: 'Edit subscription' });
  await expect(edit.getByRole('group', { name: 'Recipient' })).toHaveText(`Recipient${outside}`);
  await edit.getByRole('checkbox', { name: 'Sign-up', exact: true }).uncheck();
  const patched = page.waitForResponse(
    (response) =>
      /\/notifications\/subscriptions\/\d+$/.test(response.url()) &&
      response.request().method() === 'PATCH',
  );
  await edit.getByRole('button', { name: 'Save' }).click();
  expect((await patched).status()).toBe(200);
  await expect(edit).toHaveCount(0);
  await expect(row).toContainText('Friend became a member');
  await expect(row).not.toContainText('Sign-up');
  await signOut(page);

  // A second friend joins the same DART now that the subscription has dropped
  // sign-ups: the roster contact still hears of it, since that goes out
  // whether or not the address is subscribed, but the outside address does not.
  const secondFirst = `Nora${Date.now().toString(36)}`;
  const secondJoiner = uniqueEmail('joiner');
  await joinAsFriend(page, { first: secondFirst, email: secondJoiner, dartId: dart.id });
  const secondHeadline = `${secondFirst} Nansen signed up as a friend`;
  await expect.poll(() => latestEmailTo(dart.rosterEmail)).toContain(secondHeadline);
  expect(emailCountTo(outside)).toBe(1);
  await signOut(page);

  // The user administrator deactivates the seeded member.
  await signIn(page, DEMO.useradmin);
  await page.goto('portal/admin/users');
  await page.getByRole('searchbox', { name: 'Search' }).fill(DEMO.member);
  const link = page.getByRole('row').filter({ hasText: DEMO.member }).getByRole('link');
  const name = (await link.textContent()) ?? '';
  await link.click();
  await expect(page.getByRole('heading', { name, exact: true })).toBeVisible();
  const status = page.locator('section.card', {
    has: page.getByRole('heading', { name: 'Account status' }),
  });

  // Each action asks first: the button opens the panel holding the one that acts.
  await status.getByRole('button', { name: 'Deactivate account' }).click();
  await status
    .getByRole('region', { name: 'Deactivate account' })
    .getByRole('button', { name: 'Deactivate account' })
    .click();
  await expect(page.getByText('Account deactivated.')).toBeVisible();

  // The seeded account administrator hears of it, which proves the event went out,
  // and the outside address, no longer subscribed to anything it covers, does not.
  await expect
    .poll(() => latestEmailTo(DEMO.accountadmin))
    .toContain(`${name}'s account was deactivated`);
  expect(emailCountTo(outside)).toBe(1);

  // Leave the member as the seed made them, for the specs that follow.
  await status.getByRole('button', { name: 'Reactivate account' }).click();
  await status
    .getByRole('region', { name: 'Reactivate account' })
    .getByRole('button', { name: 'Reactivate account' })
    .click();
  await expect(status.getByRole('button', { name: 'Deactivate account' })).toBeVisible();
  await expect
    .poll(() => latestEmailTo(DEMO.accountadmin))
    .toContain(`${name}'s account was reactivated`);
});
