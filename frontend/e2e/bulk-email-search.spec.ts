/**
 * The search on **Who gets it**: CalDART management chooses filters, sees the people
 * they match before anybody is added, adds them, and saves the search as a live group.
 *
 * The search is the holders of the management role, which the seed gives to one demo
 * account.
 */
import { expect, test } from '@playwright/test';

import { DEMO, signIn } from './helpers';

/** A name no other run of this spec has used. */
function fresh(what: string): string {
  return `${what} ${Date.now().toString(36)}`;
}

test('a search shows its people, adds them, and saves as a live group', async ({ page }) => {
  const group = fresh('Managers search');

  await signIn(page, DEMO.management);
  await page
    .getByRole('navigation', { name: 'Portal sections' })
    .getByRole('link', { name: 'Compose' })
    .click();
  await expect(page.getByRole('heading', { name: '1. Who gets it' })).toBeVisible();

  // The filters search first: the people they match show, and nobody is added yet.
  const filters = page.getByRole('search', { name: 'Choose people to add' });
  await filters.getByLabel('Role').selectOption('management');
  await expect(page.getByText(/^\d+ (person matches|people match) these filters\.$/)).toBeVisible();
  const matches = page.getByRole('table', { name: /^People these filters match: / });
  await expect(matches.getByRole('row').filter({ hasText: DEMO.management })).toContainText('Yes');
  await expect(page.getByText('Nobody is on the recipient list yet')).toBeVisible();

  // Add these people puts them on the recipient list.
  await page.getByRole('button', { name: 'Add these people' }).click();
  await expect(page.getByText(/^Added \d+ (person|people)[.;]/)).toBeVisible();
  const batch = page.getByRole('table', { name: /^Recipient list: / });
  await expect(batch.getByRole('row').filter({ hasText: DEMO.management })).toBeVisible();

  // Save as a group keeps the search; a press on the Live label chooses it.
  await page.getByRole('button', { name: 'Save as a group' }).click();
  const saveGroup = page.getByRole('form', { name: 'Save this search as a group' });
  await saveGroup.getByRole('textbox', { name: /Group name/ }).fill(group);
  await saveGroup.locator('label', { hasText: /^Live$/ }).click();
  await expect(saveGroup.getByRole('radio', { name: 'Live' })).toBeChecked();
  await saveGroup.getByRole('button', { name: 'Add group' }).click();
  await page.getByRole('link', { name: group, exact: true }).click();

  await expect(page.getByRole('heading', { name: group })).toBeVisible();
  await expect(page.getByText('Role: CalDART management')).toBeVisible();
});
