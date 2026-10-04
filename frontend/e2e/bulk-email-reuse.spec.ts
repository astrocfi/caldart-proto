/**
 * What CalDART management keeps to use again: a batch saved as a recipient group and a
 * message saved as a template, then a fresh draft started from both, and both found on
 * their own screens.
 *
 * The batch is the holders of the management role, which the seed gives to one demo
 * account, whose inbox no spec here reads: nothing is sent.
 */
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

import { DEMO, signIn } from './helpers';

/** A name no other run of this spec has used. */
function fresh(what: string): string {
  return `${what} ${Date.now().toString(36)}`;
}

/** Open Compose from the menu and wait for the draft's first card. */
async function openCompose(page: Page): Promise<void> {
  await page
    .getByRole('navigation', { name: 'Portal sections' })
    .getByRole('link', { name: 'Compose' })
    .click();
  await expect(page).toHaveURL(/\/portal\/bulk-email\/compose\/\d+$/);
  await expect(page.getByRole('heading', { name: '1. Who gets it' })).toBeVisible();
}

test('a saved group and a saved template start a fresh draft', async ({ page }) => {
  const group = fresh('Managers');
  const template = fresh('Hangar notice');
  const subject = fresh('Hangar opens');

  await signIn(page, DEMO.management);
  await openCompose(page);

  // Build a batch and keep it as a fixed group.
  const filters = page.getByRole('search', { name: 'Choose people to add' });
  await filters.getByLabel('Role').selectOption('management');
  await page.getByRole('button', { name: 'Add to batch' }).click();
  await expect(page.getByText(/^Added \d+ (person|people)[.;]/)).toBeVisible();
  await page.getByRole('button', { name: 'Save as a group' }).click();
  const saveGroup = page.getByRole('form', { name: 'Save the batch as a group' });
  await saveGroup.getByRole('textbox', { name: /Group name/ }).fill(group);
  await saveGroup.getByRole('button', { name: 'Save group' }).click();
  await expect(page.getByRole('link', { name: group, exact: true })).toBeVisible();

  // Write a message and keep it as a template.
  await page.getByRole('radio', { name: 'Operational' }).click();
  await expect(page.getByRole('radio', { name: 'Operational' })).toBeChecked();
  await page.getByRole('textbox', { name: /^Subject/ }).fill(subject);
  await page.getByRole('textbox', { name: 'Message' }).click();
  await page.keyboard.type('The hangar opens at nine.');
  await expect(page.getByText('Saved', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Save as a template' }).click();
  const saveTemplate = page.getByRole('form', { name: 'Save as a template' });
  await saveTemplate.getByRole('textbox', { name: /Template name/ }).fill(template);
  await saveTemplate.getByRole('button', { name: 'Save template' }).click();
  await expect(page.getByText(`Saved as the template ${template}.`)).toBeVisible();

  // A fresh draft starts from both.
  await openCompose(page);
  await expect(page.getByRole('textbox', { name: /^Subject/ })).toHaveValue('');
  await page.getByRole('button', { name: 'Add a saved group' }).click();
  await page.getByRole('button', { name: new RegExp(`^${group}: fixed, `) }).click();
  await expect(page.getByText(/^Added \d+ (person|people)\.$/)).toBeVisible();
  const batch = page.getByRole('table', { name: /^The batch: / });
  // Chosen by shows on a screen wide enough for every column of the batch.
  await page.setViewportSize({ width: 1600, height: 900 });
  await expect(batch.getByRole('row').filter({ hasText: DEMO.management })).toContainText(
    `Group: ${group}`,
  );

  await page.getByRole('button', { name: 'Start from a template' }).click();
  await page.getByRole('combobox', { name: 'Template' }).selectOption({ label: template });
  await page.getByRole('button', { name: 'Use this template' }).click();
  await expect(page.getByRole('textbox', { name: /^Subject/ })).toHaveValue(subject);
  await expect(page.getByRole('textbox', { name: 'Message' })).toContainText(
    'The hangar opens at nine.',
  );

  // Both are on their own screens.
  await page
    .getByRole('navigation', { name: 'Portal sections' })
    .getByRole('link', { name: 'Templates' })
    .click();
  await expect(page.getByRole('cell', { name: template, exact: true })).toBeVisible();
  await page
    .getByRole('navigation', { name: 'Portal sections' })
    .getByRole('link', { name: 'Recipient groups' })
    .click();
  await page.getByRole('link', { name: group, exact: true }).click();
  await expect(page.getByRole('heading', { level: 1, name: group })).toBeVisible();
  await expect(page.getByRole('cell', { name: DEMO.management, exact: true })).toBeVisible();
});
