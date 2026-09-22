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

import { DEMO, signIn } from './helpers';

/** The member card, addressed by the accessible name the card carries. */
function memberCard(page: Page, name: string): Locator {
  return page.getByRole('region', { name: `Status for ${name}` });
}

/** Search the member check for `term` and open the result named `name`. */
async function lookUp(page: Page, term: string, name: string): Promise<Locator> {
  await page.goto('/portal/leader');
  await page.getByRole('searchbox', { name: 'Name, email or N-number' }).fill(term);
  await page.getByRole('button', { name: new RegExp(name) }).click();
  const card = memberCard(page, name);
  await expect(card).toBeVisible();
  return card;
}

test('a leader searches by name and reads the GO / NO-GO card', async ({ page }) => {
  await signIn(page, DEMO.leader);

  const card = await lookUp(page, 'Delgado', 'Owen Delgado');
  await expect(card.getByRole('status')).toContainText('NO-GO');
  await expect(card.getByRole('status')).toContainText('Membership expired');
  await expect(card.getByRole('status')).toContainText('Medical expired');

  // Every row a leader needs, in one card.
  await expect(card.getByRole('heading', { name: 'Owen Delgado' })).toBeVisible();
  await expect(card.getByRole('term').filter({ hasText: /^Membership$/ })).toBeVisible();
  await expect(card.getByRole('term').filter({ hasText: /^Medical$/ })).toBeVisible();
  await expect(card.getByRole('term').filter({ hasText: /^Certificate$/ })).toBeVisible();
  await expect(card.getByRole('heading', { name: 'Aircraft' })).toBeVisible();
  await expect(card.getByRole('listitem').filter({ hasText: 'N402FB' })).toContainText('Insured');

  // The card survives a reload, so it can be sent to another leader.
  await expect(page).toHaveURL(/\/portal\/leader\?member=\d+/);
  await page.reload();
  await expect(memberCard(page, 'Owen Delgado').getByRole('status')).toContainText('NO-GO');
});

test('a member who is current on both counts is a GO', async ({ page }) => {
  await signIn(page, DEMO.leader);

  const card = await lookUp(page, 'Raman', 'Priya Raman');
  await expect(card.getByRole('status')).toContainText('GO');
  await expect(card.getByRole('status')).toContainText('Membership and medical are current');
  await expect(card.getByRole('listitem').first()).toContainText('Insured');
});

test('a lapsed insurance policy is called out on the airplane, not the pilot', async ({ page }) => {
  await signIn(page, DEMO.leader);

  const card = await lookUp(page, 'Lindqvist', 'Ada Lindqvist');
  await expect(card.getByRole('status')).toContainText('GO');
  // The pilot is fine; the airframe says exactly why it is not.
  await expect(card.getByText('Insurance expired')).toBeVisible();
  await expect(card.getByText('Insured', { exact: true })).toHaveCount(0);
});

test('a leader can check a tail number on its own', async ({ page }) => {
  await signIn(page, DEMO.leader);

  await page.goto('/portal/leader/aircraft');
  await page.getByRole('searchbox', { name: 'N-number' }).fill('N402FB');
  await page.getByRole('button', { name: /check/i }).click();

  const card = page.getByRole('region', { name: 'Insurance for N402FB' });
  await expect(card).toBeVisible();
  await expect(card.getByRole('heading', { name: 'N402FB' })).toBeVisible();
  await expect(card.getByRole('status')).toContainText('INSURED');
  await expect(card.getByRole('status')).toContainText('Cover is current');
  await expect(card.getByRole('term').filter({ hasText: /^Insurance$/ })).toBeVisible();
  await expect(card.getByRole('term').filter({ hasText: /^Liability$/ })).toBeVisible();
  await expect(card.getByText('Owen Delgado')).toBeVisible();
});

test('a plain member cannot reach the leader check', async ({ page }) => {
  await signIn(page, DEMO.member);

  await page.goto('/portal/leader');

  await expect(page.getByRole('heading', { name: 'Not allowed' })).toBeVisible();
});
