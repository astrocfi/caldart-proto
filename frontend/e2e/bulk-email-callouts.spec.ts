/**
 * A mission callout from end to end: CalDART management sends one to two people, one of
 * them answers from the button in the email without signing in, the Callouts screen
 * shows the answer, and **Remind non-responders** sends the callout again to the other
 * alone.
 *
 * `make e2e` sets `BULK_EMAIL_UNDO_SECONDS=0`, so a send is ready for the sender's next
 * run at once.  The two people are the demo verifier and the demo user administrator,
 * found by address, whose inboxes no other spec reads.
 */
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

import { DEMO, emailCountTo, latestEmailTo, signIn } from './helpers';

/** The portal menu. */
function menu(page: Page) {
  return page.getByRole('navigation', { name: 'Portal sections' });
}

/** Add the person with `address` to the batch, found by the filter bar's search. */
async function addByAddress(page: Page, address: string): Promise<void> {
  const filters = page.getByRole('search', { name: 'Choose people to add' });
  await filters.getByLabel('Search').fill(address);
  await page.getByRole('button', { name: 'Add these people' }).click();
  await expect(page.getByText(/^Added 1 person[.;]/)).toBeVisible();
}

/**
 * The one message in `file` addressed to `address`. The sender sends a run's copies over
 * one connection, which the file mail backend writes to one file, each message after a
 * line of dashes.
 */
function messageFor(file: string, address: string): string {
  const header = `to: ${address}`.toLowerCase();
  const found = file
    .split(/^-{79}$/m)
    .filter((part) => part.split(/\r?\n/).some((line) => line.toLowerCase() === header));
  expect(found).toHaveLength(1);
  return found[0] ?? '';
}

/** Run the background sender from the Scheduled page, as the system administrator. */
async function runSender(page: Page): Promise<void> {
  await page.context().clearCookies();
  await signIn(page, DEMO.sysadmin);
  await page.goto('portal/system/scheduled');
  const sender = page
    .locator('section')
    .filter({ has: page.getByRole('heading', { name: 'Bulk email sender' }) });
  await sender.getByRole('button', { name: 'Run now: bulk email sender' }).click();
  await expect(sender.getByRole('status')).toHaveText(/^Worked on \d+ bulk emails?: sent \d+/);
}

test('a callout is answered from its email, and the rest are reminded', async ({ page }) => {
  const subject = `Fire near Paradise ${Date.now().toString(36)}`;

  // CalDART management writes the callout to two people.
  await signIn(page, DEMO.management);
  await menu(page).getByRole('link', { name: 'Compose' }).click();
  await expect(page.getByRole('heading', { name: '1. Who gets it' })).toBeVisible();
  await addByAddress(page, DEMO.verifier);
  await addByAddress(page, DEMO.useradmin);
  await page.getByRole('switch', { name: 'This is a mission callout' }).click();
  await expect(page.getByRole('radio', { name: 'Mission' })).toBeChecked();
  await expect(page.getByRole('group', { name: 'Answers close' })).toBeVisible();
  await page.getByRole('textbox', { name: /^Subject/ }).fill(subject);
  await page.getByRole('textbox', { name: 'Message' }).click();
  await page.keyboard.type('Can you fly water and supplies to Chico on Saturday?');
  await page.getByRole('button', { name: 'Send to 2 people' }).click();
  await page
    .getByRole('region', { name: 'Confirm sending' })
    .getByRole('button', { name: 'Send now' })
    .click();
  await expect(page.getByRole('region', { name: 'Waiting to send' })).toBeVisible();
  await runSender(page);

  // The verifier answers from the button in their copy, without signing in.
  const copy = messageFor(await latestEmailTo(DEMO.verifier), DEMO.verifier);
  expect(copy).toContain(subject);
  const available = /^Available: (\S+)$/m.exec(copy)?.[1] ?? '';
  expect(available).toMatch(/\/mail\/callout\/[^/?]+\?answer=available$/);
  await page.context().clearCookies();
  await page.goto(available);
  await expect(page.getByRole('heading', { level: 1, name: subject })).toBeVisible();
  await expect(page.getByRole('radio', { name: 'Available', exact: true })).toBeChecked();
  await page.getByRole('textbox', { name: 'Note (optional)' }).fill('Aircraft at KSQL');
  await page.getByRole('button', { name: 'Send answer' }).click();
  await expect(page.getByText(/Thank you\. Your answer is Available/)).toBeVisible();

  // CalDART management reads the answer and reminds the one who has not answered.
  await signIn(page, DEMO.management);
  await menu(page).getByRole('link', { name: 'Callouts' }).click();
  await page.getByRole('link', { name: subject, exact: true }).click();
  await expect(page.getByLabel('Answers by kind')).toContainText('Available1');
  await expect(page.getByLabel('Answers by kind')).toContainText('No answer1');
  const answers = page.getByRole('table', { name: 'Answers: 2 people' });
  await expect(answers.getByRole('row').filter({ hasText: 'Aircraft at KSQL' })).toContainText(
    'Available',
  );

  const verifierBefore = emailCountTo(DEMO.verifier);
  const useradminBefore = emailCountTo(DEMO.useradmin);
  await page.getByRole('button', { name: 'Remind non-responders' }).click();
  await page.getByRole('button', { name: 'Send reminders' }).click();
  await expect(page.getByText('The reminders will be sent within a minute.')).toBeVisible();
  await runSender(page);

  await expect.poll(() => emailCountTo(DEMO.useradmin)).toBe(useradminBefore + 1);
  expect(await latestEmailTo(DEMO.useradmin)).toContain(subject);
  expect(emailCountTo(DEMO.verifier)).toBe(verifierBefore);
});
