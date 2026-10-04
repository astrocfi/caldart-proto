/**
 * Bulk email as a DART leader sends it: to the members and friends of the DART on the
 * leader's own profile, and nobody else.  The compose screen names that DART in place
 * of the DART filter; the leader sends to themselves alone, found by address, so no
 * other spec's inbox changes; the system administrator runs the background sender;
 * and CalDART management then sees the send with its sender and its DART.
 *
 * `make e2e` sets `BULK_EMAIL_UNDO_SECONDS=0`, so a send is ready for the sender's
 * next run at once.
 */
import { expect, test } from '@playwright/test';

import { DEMO, latestEmailTo, signIn } from './helpers';

test('a DART leader sends bulk email to their own DART', async ({ page }) => {
  const subject = `Hangar night ${Date.now().toString(36)}`;

  await signIn(page, DEMO.leader);
  const sections = page.getByRole('navigation', { name: 'Portal sections' });
  await sections.getByRole('link', { name: 'Compose' }).click();
  await expect(page).toHaveURL(/\/portal\/bulk-email\/compose\/\d+$/);

  // The leader's DART stands in for the DART filter.
  const fixed = page.getByText(/^Sending to the .+ DART\. The filters choose people in that/);
  await expect(fixed).toBeVisible();
  const dart = /^Sending to the (.+) DART\./.exec((await fixed.textContent()) ?? '')?.[1] ?? '';
  expect(dart).not.toBe('');
  const filters = page.getByRole('search', { name: 'Choose people to add' });
  await expect(filters.getByLabel('DART', { exact: true })).toHaveCount(0);

  await filters.getByLabel('Search').fill(DEMO.leader);
  await page.getByRole('button', { name: 'Add to batch' }).click();
  await expect(page.getByText(/^Added 1 person[.;]/)).toBeVisible();
  const batch = page.getByRole('table', { name: 'The batch: 1 person' });
  // Chosen by shows on a screen wide enough for every column of the batch.
  await page.setViewportSize({ width: 1600, height: 900 });
  await expect(batch.getByRole('row').filter({ hasText: DEMO.leader })).toContainText(
    `DART: ${dart}`,
  );

  // A leader may send Operational email, and Fundraising is not offered.
  await page.getByRole('radio', { name: 'Operational' }).click();
  await expect(page.getByRole('radio', { name: 'Operational' })).toBeChecked();
  await expect(page.getByRole('radio', { name: 'Fundraising' })).toHaveCount(0);
  await page.getByRole('textbox', { name: /^Subject/ }).fill(subject);
  await page.getByRole('textbox', { name: 'Message' }).click();
  await page.keyboard.type('We meet at the hangar on Thursday.');

  await page.getByRole('button', { name: 'Send to 1 person' }).click();
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
  await expect(sender.getByRole('row').filter({ hasText: DEMO.leader })).toContainText('Sent');
  expect(await latestEmailTo(DEMO.leader)).toContain(subject);

  // The leader's own Sent list holds it, without the management-only columns.
  await page.context().clearCookies();
  await signIn(page, DEMO.leader);
  await page.goto('portal/bulk-email/sent');
  const own = page.getByRole('row').filter({ hasText: subject });
  await expect(own).toContainText('Sent');
  await expect(page.getByRole('columnheader', { name: 'From' })).toHaveCount(0);

  // CalDART management sees the send, who sent it, and the DART it went to.
  await page.context().clearCookies();
  await signIn(page, DEMO.management);
  await page.goto('portal/bulk-email/sent');
  const row = page.getByRole('row').filter({ hasText: subject });
  await expect(row.getByRole('cell', { name: dart, exact: true })).toBeVisible();
});
