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
 * is a GO whose airplane's insurance has lapsed.
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

test('a leader can check a tail number on its own', async ({ page }) => {
  const { name, nNumber } = SEED.leaderCheck.insuredPilot;
  await signIn(page, DEMO.leader);

  await page.goto('/portal/leader/aircraft');
  await page.getByRole('searchbox', { name: 'N-number' }).fill(nNumber);
  await page.getByRole('button', { name: /check/i }).click();

  const card = page.getByRole('region', { name: `Insurance for ${nNumber}` });
  await expect(card).toBeVisible();
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
