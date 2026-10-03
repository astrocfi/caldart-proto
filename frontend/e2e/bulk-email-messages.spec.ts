/**
 * A bulk email after it went: the recipient reads it again under Messages, through the
 * View in browser link in their copy and from the menu; CalDART management reads that
 * copy on the delivery report and hides the email from Messages.
 *
 * `make e2e` sets `BULK_EMAIL_UNDO_SECONDS=0`, so a send is ready for the sender's next
 * run at once.  The batch is the holder of the website administrator role, whom the seed
 * gives one demo account and whose inbox no other spec reads.
 */
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

import { DEMO, DEMO_PASSWORD, latestEmailTo, signIn } from './helpers';

/** The portal menu. */
function menu(page: Page) {
  return page.getByRole('navigation', { name: 'Portal sections' });
}

/** Write and send an email to the website administrators, as CalDART management. */
async function sendToWebsiteAdmins(page: Page, subject: string): Promise<void> {
  await signIn(page, DEMO.management);
  await menu(page).getByRole('link', { name: 'Compose' }).click();
  await expect(page.getByRole('heading', { name: '1. Who gets it' })).toBeVisible();
  await page
    .getByRole('search', { name: 'Choose people to add' })
    .getByLabel('Role')
    .selectOption('website_admin');
  await page.getByRole('button', { name: 'Add to batch' }).click();
  await expect(page.getByText(/^Added \d+ (person|people)[.;]/)).toBeVisible();
  await page.getByRole('radio', { name: 'Operational' }).click();
  await page.getByRole('textbox', { name: /^Subject/ }).fill(subject);
  await page.getByRole('textbox', { name: 'Message' }).click();
  await page.keyboard.type('The hangar opens at nine.');
  await page.getByRole('button', { name: /^Send to \d+ (person|people)$/ }).click();
  await page
    .getByRole('region', { name: 'Confirm sending' })
    .getByRole('button', { name: 'Send now' })
    .click();
  await expect(page.getByRole('region', { name: 'Waiting to send' })).toBeVisible();
}

/** Run the background sender from the Scheduled page, as the system administrator. */
async function runSender(page: Page): Promise<void> {
  await page.context().clearCookies();
  await signIn(page, DEMO.sysadmin);
  await page.goto('portal/system/scheduled');
  const sender = page
    .locator('section')
    .filter({ has: page.getByRole('heading', { name: 'Bulk email sender' }) });
  await sender.getByRole('button', { name: 'Run the bulk email sender now' }).click();
  await expect(sender.getByRole('status')).toHaveText(/^Worked on \d+ bulk emails?: sent \d+/);
}

test('a recipient reads a bulk email again under Messages', async ({ page }) => {
  const subject = `Hangar news ${Date.now().toString(36)}`;
  await sendToWebsiteAdmins(page, subject);
  await runSender(page);

  // The copy's View in browser link opens the message, after signing in.
  const copy = await latestEmailTo(DEMO.webadmin);
  expect(copy).toContain(subject);
  const link = /View this email in your browser: (\S+)/.exec(copy)?.[1] ?? '';
  expect(link).toMatch(/\/portal\/messages\/\d+$/);
  await page.context().clearCookies();
  await page.goto(link);
  await expect(page).toHaveURL(/\/portal\/login/);
  await page.getByRole('textbox', { name: 'Email address' }).fill(DEMO.webadmin);
  await page.getByLabel(/^Password/).fill(DEMO_PASSWORD);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('heading', { level: 1, name: subject })).toBeVisible();
  await expect(page.getByTitle(`The email: ${subject}`)).toBeVisible();

  // Messages in the menu lists it, and its subject opens it.
  await menu(page).getByRole('link', { name: 'Messages' }).click();
  await page.getByRole('link', { name: subject, exact: true }).click();
  await expect(page.getByRole('heading', { level: 1, name: subject })).toBeVisible();
});

test('CalDART management reads a copy as it went and hides the email', async ({ page }) => {
  const subject = `Seminar notice ${Date.now().toString(36)}`;
  await sendToWebsiteAdmins(page, subject);
  await runSender(page);

  await page.context().clearCookies();
  await signIn(page, DEMO.management);
  await menu(page).getByRole('link', { name: 'Sent', exact: true }).click();
  await page.getByRole('link', { name: subject, exact: true }).click();
  await expect(page.getByLabel('Copies by result')).toContainText('Bounced0');

  await page
    .getByRole('button', { name: /^View the copy sent to / })
    .first()
    .click();
  const dialog = page.getByRole('dialog', { name: /^The copy sent to / });
  await expect(dialog).toContainText(subject);
  await dialog.getByRole('button', { name: 'Close' }).click();
  await expect(dialog).toHaveCount(0);

  await page.getByRole('button', { name: 'Hide from Messages' }).click();
  await page.getByRole('button', { name: 'Hide it' }).click();
  await expect(page.getByRole('button', { name: 'Show in Messages' })).toBeVisible();

  await page.context().clearCookies();
  await signIn(page, DEMO.webadmin);
  // Wait for the list itself, so its absence of the email is not read before it loads.
  const listed = page.waitForResponse((response) => response.url().endsWith('/api/v1/messages'));
  await menu(page).getByRole('link', { name: 'Messages' }).click();
  await listed;
  await expect(page.getByRole('heading', { level: 1, name: 'Messages' })).toBeVisible();
  await expect(page.getByRole('link', { name: subject, exact: true })).toHaveCount(0);
});
