/**
 * Bulk email as CalDART management sends it: a batch built from two filter sets,
 * downloaded, sent behind a confirmation, and sent by the background sender, which
 * the system administrator runs from the Scheduled page; then a scheduled send
 * canceled back to a draft.
 *
 * `make e2e` sets `BULK_EMAIL_UNDO_SECONDS=0`, so a send is ready for the sender's
 * next run at once.  The two filter sets choose the holders of two roles, which the
 * seed gives to one demo account each, and whose inboxes no other spec reads.
 */
import { readFile } from 'node:fs/promises';

import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

import { DEMO, latestEmailTo, signIn } from './helpers';

/** A subject no other run of this spec has used. */
function freshSubject(what: string): string {
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

/** Add the holders of `role` to the batch, waiting for the add's sentence. */
async function addRole(page: Page, role: string): Promise<void> {
  const filters = page.getByRole('search', { name: 'Choose people to add' });
  await filters.getByLabel('Role').selectOption(role);
  await page.getByRole('button', { name: 'Add to batch' }).click();
  await expect(page.getByText(/^Added \d+ (person|people)[.;]/)).toBeVisible();
}

/** Write the subject and the message. */
async function write(page: Page, subject: string): Promise<void> {
  await page.getByRole('textbox', { name: /^Subject/ }).fill(subject);
  await page
    .getByRole('textbox', { name: /^Message/ })
    .fill('The hangar opens at nine.\n\nBring gloves.');
}

test('CalDART management builds a batch from two filter sets and sends it', async ({ page }) => {
  const subject = freshSubject('Hangar cleanup');

  await signIn(page, DEMO.management);
  await openCompose(page);
  await addRole(page, 'management');
  await addRole(page, 'system_admin');

  const batch = page.getByRole('table', { name: /^The batch: \d+ (person|people)$/ });
  await expect(batch.getByRole('row').filter({ hasText: DEMO.management })).toContainText('Yes');
  await expect(batch.getByRole('row').filter({ hasText: DEMO.sysadmin })).toContainText(
    'Role: System administrator',
  );

  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('link', { name: 'Download list' }).click(),
  ]);
  expect(download.suggestedFilename()).toMatch(/^caldart-bulk-email-\d+-batch\.csv$/);
  const csv = await readFile(await download.path(), 'utf8');
  expect(csv).toContain(DEMO.management);
  expect(csv).toContain(DEMO.sysadmin);

  await write(page, subject);
  await page.getByRole('button', { name: /^Send to \d+ (person|people)$/ }).click();
  const confirm = page.getByRole('region', { name: 'Confirm sending' });
  await expect(confirm).toContainText(subject);
  await confirm.getByRole('button', { name: 'Send now' }).click();
  await expect(
    page.getByRole('region', { name: 'Waiting to send' }).getByText(/^Starting to send/),
  ).toBeVisible();

  // The system administrator runs the background sender by hand.
  await page.context().clearCookies();
  await signIn(page, DEMO.sysadmin);
  await page.goto('portal/system/scheduled');
  const sender = page
    .locator('section')
    .filter({ has: page.getByRole('heading', { name: 'Bulk email sender' }) });
  await sender.getByRole('button', { name: 'Run the bulk email sender now' }).click();
  await expect(sender.getByRole('status')).toHaveText(
    /^Worked on \d+ bulk emails?: sent \d+, failed 0, and skipped \d+\.$/,
  );
  await expect(sender.getByRole('row').filter({ hasText: DEMO.management })).toContainText('Sent');

  await page
    .getByRole('navigation', { name: 'Portal sections' })
    .getByRole('link', { name: 'Sent', exact: true })
    .click();
  await page.getByRole('link', { name: subject, exact: true }).click();
  await expect(
    page.getByText(/^Sent to \d+ (person|people)\. Everyone was sent a copy\.$/),
  ).toBeVisible();
  const results = page.getByRole('table', { name: /^Results: / });
  await expect(results.getByRole('row').filter({ hasText: DEMO.sysadmin })).toContainText('Sent');

  expect(await latestEmailTo(DEMO.management)).toContain(subject);
});

test('a scheduled bulk email is canceled back to a draft', async ({ page }) => {
  const subject = freshSubject('Spring newsletter');

  await signIn(page, DEMO.management);
  await openCompose(page);
  await addRole(page, 'management');
  await write(page, subject);

  await page.getByRole('button', { name: 'Schedule for later' }).click();
  await page.getByRole('button', { name: 'Continue' }).click();
  const confirm = page.getByRole('region', { name: 'Confirm sending' });
  await expect(confirm).toContainText('Pacific time');
  await confirm.getByRole('button', { name: 'Schedule it' }).click();
  await expect(page.getByRole('region', { name: 'Waiting to send' })).toContainText(
    'Scheduled for',
  );

  await page
    .getByRole('navigation', { name: 'Portal sections' })
    .getByRole('link', { name: 'Drafts & scheduled' })
    .click();
  const row = page.getByRole('row').filter({ hasText: subject });
  await expect(row).toContainText('Scheduled');
  await row.getByRole('button', { name: `Cancel the send of ${subject}` }).click();
  await expect(row).toContainText('Draft');
});
