/**
 * Flow C in `docs/demo-walkthrough.rst`: a DART leader looks a member up and
 * sees the GO / NO-GO verdict with the medical and the insurance on the planes
 * they fly.
 *
 * Runs at desktop and at iPhone size — this is the flow that happens standing
 * on a ramp with a phone.
 *
 * The three demo accounts used here are seeded deliberately: the leader is
 * current with a current medical and an insured airplane (a GO), the expired
 * account is expired on both counts (a NO-GO), and the website administrator
 * is a GO whose airplane's insurance has lapsed.  The demo friend is a NO-GO
 * whose card calls them a friend of CalDART, never expired.
 */
import { expect, test } from '@playwright/test';
import type { Locator, Page } from '@playwright/test';

import { DEMO, SEED, signIn } from './helpers';

/** The member card, addressed by the accessible name the card carries. */
function memberCard(page: Page, name: string): Locator {
  return page.getByRole('region', { name: `Status for ${name}` });
}

/** Search the member check for `term` and open the result named `name`. */
async function lookUp(page: Page, term: string, name: string): Promise<Locator> {
  await page.goto('/portal/leader');
  await page.getByRole('searchbox', { name: 'Name, email, phone, or N-number' }).fill(term);
  await page.getByRole('button', { name: new RegExp(name) }).click();
  const card = memberCard(page, name);
  await expect(card).toBeVisible();
  return card;
}

/** The surname to search on, which is the last word of a seeded name. */
function surname(name: string): string {
  return name.split(' ').slice(-1)[0] ?? name;
}

test('a leader searches by name and reads the GO / NO-GO card', async ({ page }) => {
  const { name } = SEED.leaderCheck.expiredMember;
  await signIn(page, DEMO.leader);

  const card = await lookUp(page, surname(name), name);
  await expect(card.getByRole('status')).toContainText('NO-GO');
  await expect(card.getByRole('status')).toContainText('Membership expired');

  // Every row a leader needs, in one card.
  await expect(card.getByRole('heading', { name })).toBeVisible();
  await expect(card.getByRole('term').filter({ hasText: /^Membership$/ })).toBeVisible();
  await expect(card.getByRole('term').filter({ hasText: /^Medical$/ })).toBeVisible();
  await expect(card.getByRole('term').filter({ hasText: /^Certificate$/ })).toBeVisible();

  // The card survives a reload, so it can be sent to another leader.
  await expect(page).toHaveURL(/\/portal\/leader\?member=\d+/);
  await page.reload();
  await expect(memberCard(page, name).getByRole('status')).toContainText('NO-GO');
});

test('the results list answers go or no-go before the card is opened', async ({ page }) => {
  const { name } = SEED.leaderCheck.expiredMember;
  await signIn(page, DEMO.leader);

  await page.goto('/portal/leader');
  await page
    .getByRole('searchbox', { name: 'Name, email, phone, or N-number' })
    .fill(surname(name));
  const result = page.getByRole('button', { name: new RegExp(name) });
  await expect(result).toBeVisible();
  await expect(result).toContainText('NO-GO');
  // The row is the name and the verdict: the membership, the medical and the
  // rest belong to the card.
  await expect(result).not.toContainText('medical');
  await expect(result).not.toContainText('Member expired');
});

test('a friend of CalDART is a NO-GO, called a friend rather than expired', async ({ page }) => {
  // The seed's demo friend; `DemoAccount` lists the accounts every spec signs in
  // as, and nobody signs in as the friend here.
  const email = (DEMO as Record<string, string>).friend ?? '';
  await signIn(page, DEMO.leader);
  const [found] = (await (
    await page.request.get(`/api/v1/leader/search?q=${encodeURIComponent(email)}`)
  ).json()) as { name: string }[];
  const name = found?.name ?? email;

  const card = await lookUp(page, email, name);
  await expect(card.getByRole('status')).toContainText('NO-GO');
  await expect(card.getByRole('status')).toContainText('Friend of CalDART, not a member');
  const membership = card.getByRole('term').filter({ hasText: /^Membership$/ });
  await expect(membership.locator('xpath=following-sibling::dd[1]')).toContainText('Friend');
});

test('a member who is current on both counts is a GO', async ({ page }) => {
  const { name } = SEED.leaderCheck.insuredPilot;
  await signIn(page, DEMO.leader);

  const card = await lookUp(page, surname(name), name);
  await expect(card.getByRole('status')).toContainText('GO');
  await expect(card.getByRole('heading', { name: 'Aircraft' })).toBeVisible();
  await expect(card.getByRole('listitem').first()).toContainText('Insured');
});

test('a lapsed insurance policy is called out on the airplane, not the pilot', async ({ page }) => {
  const { name } = SEED.leaderCheck.lapsedInsurance;
  await signIn(page, DEMO.leader);

  const card = await lookUp(page, surname(name), name);
  // The pilot's own membership is current; the airframe says why it is not.
  await expect(card.getByText('Insurance expired').first()).toBeVisible();
});

test('a leader searches for a tail number and reads its insurance card', async ({ page }) => {
  const { name, nNumber } = SEED.leaderCheck.insuredPilot;
  await signIn(page, DEMO.leader);

  await page.goto('/portal/leader/aircraft');
  await expect(page.getByRole('button', { name: /Check aircraft/ })).toHaveCount(0);
  await page.getByRole('searchbox', { name: 'Search by N-number' }).fill(nNumber);
  // The result row answers before the card is opened.
  const result = page.getByRole('button', { name: new RegExp(nNumber) });
  await expect(result.getByText('GO', { exact: true })).toBeVisible();
  await result.click();

  const card = page.getByRole('region', { name: `Insurance for ${nNumber}` });
  await expect(card).toBeVisible();
  await expect(page).toHaveURL(new RegExp(`/portal/leader/aircraft\\?aircraft=${nNumber}$`));
  await expect(card.getByRole('heading', { name: nNumber })).toBeVisible();
  await expect(card.getByRole('status')).toContainText('INSURED');
  await expect(card.getByRole('status')).toContainText('Coverage is current');
  await expect(card.getByRole('term').filter({ hasText: /^Insurance$/ })).toBeVisible();
  await expect(card.getByRole('term').filter({ hasText: /^Liability$/ })).toBeVisible();
  // How old the record behind the insurance is, which a leader weighs against
  // the expiry date on it.
  const updated = card.getByRole('term').filter({ hasText: /^Last updated$/ });
  await expect(updated).toBeVisible();
  await expect(updated.locator('xpath=following-sibling::dd[1]')).toContainText(
    /\d{4}\/\d{2}\/\d{2}/,
  );
  await expect(card.getByText(name)).toBeVisible();
});

test('a plain member cannot reach the leader check', async ({ page }) => {
  await signIn(page, DEMO.member);

  await page.goto('/portal/leader');

  await expect(page.getByRole('heading', { name: 'Not allowed' })).toBeVisible();
});

// A leader reads the whole membership, narrows it by county, and takes the
// report away.  The county is the leader's own, read from their profile, so the
// filter is sure to list somebody whichever county the seed drew.
test('a leader filters the member list by county and downloads the PDF', async ({ page }) => {
  await signIn(page, DEMO.leader);
  const { county } = (await (await page.request.get('/api/v1/me/profile')).json()) as {
    county: string;
  };
  const me = (await (await page.request.get('/api/v1/auth/me')).json()) as {
    first_name: string;
    last_name: string;
  };

  // On a phone the menu is behind the Menu button.
  const members = page
    .getByRole('navigation', { name: 'Portal sections' })
    .getByRole('link', { name: 'Members' });
  if (!(await members.isVisible())) {
    await page.getByRole('button', { name: 'Menu' }).click();
  }
  await members.click();
  await expect(page.getByRole('heading', { name: 'Members' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'New member' })).toHaveCount(0);

  await page.getByLabel('County').selectOption(county);
  await expect(page).toHaveURL(/[?&]county=/);
  expect(new URL(page.url()).searchParams.get('county')).toBe(county);
  const self = page.getByRole('link', { name: `${me.first_name} ${me.last_name}` });
  await expect(self).toHaveAttribute('href', /\/portal\/leader\?member=\d+$/);

  const [pdf] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('link', { name: 'Export PDF' }).click(),
  ]);
  expect(pdf.suggestedFilename()).toMatch(/^caldart-members-\d{4}-\d{2}-\d{2}\.pdf$/);
  expect(new URL(pdf.url()).searchParams.get('county')).toBe(county);
});
