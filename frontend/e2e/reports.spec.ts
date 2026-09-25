/**
 * Reports by email as an account administrator uses them: a subscription the
 * server refuses because its recipient may not read the report, the same one
 * accepted for somebody who may and sent at once, and every DART's roster
 * rehearsed.
 */
import { expect, test } from '@playwright/test';

import { DEMO, signIn } from './helpers';

test('an account administrator subscribes somebody to the member report and sends it', async ({
  page,
}) => {
  await signIn(page, DEMO.accountadmin);
  await page
    .getByRole('navigation', { name: 'Portal sections' })
    .getByRole('link', { name: 'Reports' })
    .click();
  await expect(page).toHaveURL(/\/portal\/admin\/reports/);
  await expect(page.getByRole('heading', { name: 'Reports', exact: true })).toBeVisible();

  await page.getByRole('button', { name: 'New subscription' }).click();
  await page.getByLabel('Report', { exact: true }).selectOption('members');
  const form = page.getByRole('form', { name: 'New subscription' });

  // The treasurer holds no role that may read the member report.
  await form.getByLabel(/^Recipient email/).fill(DEMO.treasurer);
  await form.getByRole('button', { name: 'Save' }).click();
  await expect(form.getByRole('alert')).toHaveText(
    /does not hold a role that may read this report\./,
  );

  await form.getByLabel(/^Recipient email/).fill(DEMO.accountadmin);
  const saved = page.waitForResponse(
    (response) =>
      response.url().endsWith('/reports/subscriptions') && response.request().method() === 'POST',
  );
  await form.getByRole('button', { name: 'Save' }).click();
  expect((await saved).status()).toBe(201);
  await expect(form).toHaveCount(0);

  const subscriptions = page
    .locator('section.card')
    .filter({ has: page.getByRole('heading', { name: 'Subscriptions' }) });
  const members = subscriptions.getByRole('row').filter({ hasText: /^CalDART membership report/ });
  await members.first().getByRole('button', { name: 'Send now' }).click();
  await expect(subscriptions.getByRole('status')).toHaveText(/^Sent to /);
});

test('an account administrator rehearses the DART rosters', async ({ page }) => {
  await signIn(page, DEMO.accountadmin);
  await page.goto('/portal/admin/reports');

  const card = page
    .locator('section.card')
    .filter({ has: page.getByRole('heading', { name: 'DART rosters' }) });
  // The seed ticks two people on every DART, so each one has a roster to send.
  const firstDart = card
    .getByRole('table', { name: /DARTs?$/ })
    .getByRole('row')
    .nth(1);
  const dartName = (await firstDart.getByRole('cell').first().textContent()) ?? '';
  expect(dartName).not.toBe('');

  // The seed generates the people's names, so read one ticked on that DART from its form.
  await page.goto('/portal/admin/darts');
  await page
    .getByRole('row')
    .filter({ hasText: dartName })
    .first()
    .getByRole('button', { name: 'Edit' })
    .click();
  const ticked = page.getByRole('checkbox', { name: / receives the roster$/, checked: true });
  const tickedLabel = (await ticked.first().getAttribute('aria-label')) ?? '';
  const person = tickedLabel.replace(/ receives the roster$/, '');
  expect(person).not.toBe('');

  await page.goto('/portal/admin/reports');
  await expect(card.getByLabel('Dry run (send nothing)')).toBeChecked();
  await card.getByRole('button', { name: 'Send rosters now' }).click();
  await expect(card.getByRole('status')).toHaveText(/^Would send [1-9]\d* emails?/);

  const actions = card.getByRole('table', { name: /^[1-9]\d* actions?$/ });
  const roster = actions.getByRole('row').filter({ hasText: person }).filter({ hasText: dartName });
  await expect(roster).toHaveCount(1);
  await expect(roster).toContainText('Roster');
});

test('a treasurer reads the subscriptions but not the DART rosters', async ({ page }) => {
  await signIn(page, DEMO.treasurer);
  await page.goto('/portal/admin/reports');

  await expect(page.getByRole('heading', { name: 'Subscriptions' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'DART rosters' })).toHaveCount(0);
});

test('a DART leader cannot reach the reports screen', async ({ page }) => {
  await signIn(page, DEMO.leader);
  await page.goto('/portal/admin/reports');

  await expect(page.getByRole('heading', { name: 'Not allowed' })).toBeVisible();
});
