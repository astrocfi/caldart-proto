/**
 * Flow C (PLAN §1): a DART leader looks a member up and sees the GO / NO-GO
 * verdict with the medical and the insurance on the planes they fly.
 *
 * Runs at desktop and at iPhone size — this is the flow that happens standing
 * on a ramp with a phone.
 *
 * The three demo accounts used here are seeded deliberately: the leader is
 * current with a current medical and an insured aeroplane (a GO), the expired
 * account is expired on both counts (a NO-GO), and the website administrator
 * is a GO whose aeroplane's insurance has lapsed.
 */
import { expect, test } from '@playwright/test';

import { DEMO, signIn } from './helpers';

test('a leader searches by name and reads the GO / NO-GO card', async ({ page }) => {
  await signIn(page, DEMO.leader);

  await page.goto('/portal/leader');
  await page.getByRole('searchbox', { name: 'Name, email or N-number' }).fill('Delgado');
  await page.getByRole('button', { name: /Owen Delgado/ }).click();

  const card = page.locator('.leader-card');
  await expect(card.getByText('NO-GO')).toBeVisible();
  await expect(card.getByText(/Membership expired/)).toBeVisible();
  await expect(card.getByText(/Medical expired/)).toBeVisible();

  // Every row a leader needs, in one card.
  await expect(card.getByRole('heading', { name: 'Owen Delgado' })).toBeVisible();
  await expect(card.getByText('Membership', { exact: true })).toBeVisible();
  await expect(card.getByText('Medical', { exact: true })).toBeVisible();
  await expect(card.getByText('Certificate', { exact: true })).toBeVisible();
  await expect(card.getByText('N402FB')).toBeVisible();
  await expect(card.locator('.leader-aircraft__row .chip')).toHaveText('Insured');

  // The card survives a reload, so it can be sent to another leader.
  await expect(page).toHaveURL(/\/portal\/leader\?member=\d+/);
  await page.reload();
  await expect(card.getByText('NO-GO')).toBeVisible();
});

test('a member who is current on both counts is a GO', async ({ page }) => {
  await signIn(page, DEMO.leader);

  await page.goto('/portal/leader');
  await page.getByRole('searchbox', { name: 'Name, email or N-number' }).fill('Raman');
  await page.getByRole('button', { name: /Priya Raman/ }).click();

  const card = page.locator('.leader-card');
  await expect(card.getByText('GO', { exact: true })).toBeVisible();
  await expect(card.getByText('Membership and medical are current')).toBeVisible();
  await expect(card.locator('.leader-aircraft__row .chip')).toHaveText('Insured');
});

test('a lapsed insurance policy is called out on the aeroplane, not the pilot', async ({
  page,
}) => {
  await signIn(page, DEMO.leader);

  await page.goto('/portal/leader');
  await page.getByRole('searchbox', { name: 'Name, email or N-number' }).fill('Lindqvist');
  await page.getByRole('button', { name: /Ada Lindqvist/ }).click();

  const card = page.locator('.leader-card');
  await expect(card.getByText('GO', { exact: true })).toBeVisible();
  await expect(card.locator('.leader-aircraft__row .chip')).not.toHaveText('Insured');
});

test('a leader can check a tail number on its own', async ({ page }) => {
  await signIn(page, DEMO.leader);

  await page.goto('/portal/leader/aircraft');
  await page.getByRole('searchbox', { name: 'N-number' }).fill('N402FB');
  await page.getByRole('button', { name: /check/i }).click();

  await expect(page.getByText('N402FB')).toBeVisible();
  await expect(page.getByText(/Owen Delgado/)).toBeVisible();
});

test('a plain member cannot reach the leader check', async ({ page }) => {
  await signIn(page, DEMO.member);

  await page.goto('/portal/leader');

  await expect(page.getByRole('heading', { name: 'Not allowed' })).toBeVisible();
});
