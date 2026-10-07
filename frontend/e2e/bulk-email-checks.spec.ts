/**
 * The checks before a bulk email goes: a Reply-To address the sender chooses, a test
 * copy to the sender alone, and the checks list warning about placeholder text without
 * stopping the send. The background sender, run from the Scheduled tasks page, then sends
 * the copies with the chosen Reply-To.
 *
 * The message holds no web link, so the checks never reach for the network. The batch
 * is the holders of the management role, which the seed gives to one demo account.
 */
import { expect, test } from '@playwright/test';

import { DEMO, latestEmailTo, signIn } from './helpers';

/** Where the replies to this spec's email go. */
const REPLY_TO = 'operations@example.org';

test('CalDART management sets a Reply-To, sends a test, reads the checks, and sends', async ({
  page,
}) => {
  const subject = `Hangar day ${Date.now().toString(36)}`;

  await signIn(page, DEMO.management);
  await page
    .getByRole('navigation', { name: 'Portal sections' })
    .getByRole('link', { name: 'Compose' })
    .click();
  await expect(page).toHaveURL(/\/portal\/bulk-email\/compose\/\d+$/);

  const filters = page.getByRole('search', { name: 'Choose people to add' });
  await filters.getByLabel('Role').selectOption('management');
  await page.getByRole('button', { name: 'Add these people' }).click();
  await expect(page.getByText(/^Added \d+ (person|people)[.;]/)).toBeVisible();

  await page.getByRole('radio', { name: 'Operational' }).click();
  await expect(page.getByRole('radio', { name: 'Operational' })).toBeChecked();
  await page.getByRole('textbox', { name: /^Subject/ }).fill(subject);
  const message = page.getByRole('textbox', { name: 'Message' });
  await message.click();
  await page.keyboard.type('Bring gloves. TODO: the start time.');

  // A Reply-To saves when it is left: one that is not an address is refused beside the
  // field, without holding back the subject and the message; a real one saves.
  const replyTo = page.getByRole('textbox', { name: 'Replies go to' });
  await replyTo.fill('operations@');
  await replyTo.blur();
  await expect(page.getByText('Enter a valid email address.')).toBeVisible();
  await expect(page.getByText('Saved', { exact: true })).toBeVisible();
  await replyTo.fill(REPLY_TO);
  await replyTo.blur();
  await expect(page.getByText('Address for replies saved.')).toBeVisible();

  // The test goes to the sender alone, with the chosen Reply-To.
  await page.getByRole('button', { name: 'Send me a test' }).click();
  await expect(page.getByText(`A test went to ${DEMO.management}.`)).toBeVisible();
  await expect
    .poll(async () => latestEmailTo(DEMO.management))
    .toContain(`Subject: [Test] ${subject}`);
  expect(await latestEmailTo(DEMO.management)).toContain(`Reply-To: ${REPLY_TO}`);

  // The placeholder is worth a look, and the email can still go.
  const checks = page.getByRole('region', { name: 'Checks' });
  await checks.getByRole('button', { name: 'Check again' }).click();
  await expect(checks).toContainText('Worth a look: The email still says "TODO".');
  await expect(checks).toContainText('You can still send.');

  await page.getByRole('button', { name: /^Send to \d+ (person|people)$/ }).click();
  const confirm = page.getByRole('region', { name: 'Confirm sending' });
  await confirm.getByRole('button', { name: 'Send', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Waiting to send' })).toBeVisible();

  await page.context().clearCookies();
  await signIn(page, DEMO.sysadmin);
  await page.goto('portal/system/scheduled');
  const sender = page
    .locator('section')
    .filter({ has: page.getByRole('heading', { name: 'Bulk email sender' }) });
  await sender.getByRole('button', { name: 'Run now: bulk email sender' }).click();
  await expect(sender.getByRole('row').filter({ hasText: DEMO.management })).toContainText('Sent');

  await expect.poll(async () => latestEmailTo(DEMO.management)).toContain(`Subject: ${subject}`);
  const copy = await latestEmailTo(DEMO.management);
  expect(copy).toContain(`Reply-To: ${REPLY_TO}`);
  expect(copy).not.toContain('[Test]');
});
