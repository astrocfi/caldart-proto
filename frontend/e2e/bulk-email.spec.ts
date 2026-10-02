/**
 * Bulk email as CalDART management sends it: the filters narrow the list to one
 * friend, the preview names her, the send goes behind a confirmation, and the
 * result, the history, and the email itself all say it went.
 */
import { expect, test } from '@playwright/test';

import { DEMO, latestEmailTo, signIn } from './helpers';

test('CalDART management previews and sends a bulk email to a filtered list', async ({ page }) => {
  const subject = `Hangar cleanup ${Date.now().toString(36)}`;

  await signIn(page, DEMO.management);
  await page
    .getByRole('navigation', { name: 'Portal sections' })
    .getByRole('link', { name: 'Bulk Email' })
    .click();
  await expect(page).toHaveURL(/\/portal\/admin\/bulk-email/);
  await expect(page.getByRole('heading', { level: 1, name: 'Bulk Email' })).toBeVisible();

  // Friends only, and of them only the demo friend, found by her address.
  const filters = page.getByRole('search', { name: 'Choose the recipients' });
  await filters.getByLabel('Kind').selectOption('friend');
  await filters.getByLabel('Search').fill(DEMO.friend);

  await page.getByRole('textbox', { name: /^Subject/ }).fill(subject);
  await page
    .getByRole('textbox', { name: /^Message/ })
    .fill('Bring gloves.\n\nWe start at nine on Saturday.');

  // The search box applies itself once the typing pauses; wait for the preview
  // that carries it rather than one sent before it landed.
  await expect(async () => {
    const previewed = page.waitForResponse(
      (response) =>
        response.url().endsWith('/bulk-email/preview') && response.request().method() === 'POST',
    );
    await page.getByRole('button', { name: 'Preview recipients' }).click();
    const body = (await (await previewed).json()) as { count: number };
    expect(body.count).toBe(1);
  }).toPass();

  await expect(page.getByRole('status')).toHaveText(
    /^1 person will be sent this email; \d+ (is|are) skipped\.$/,
  );
  const preview = page.getByRole('table', { name: /actions?$/ });
  await expect(preview.getByRole('row').filter({ hasText: DEMO.friend })).toContainText('To send');
  await expect(page.getByRole('link', { name: 'Download list' })).toHaveAttribute(
    'href',
    /\/bulk-email\/preview\.csv\?kind=friend&search=/,
  );

  await page.getByRole('button', { name: 'Send to 1 person' }).click();
  const sent = page.waitForResponse(
    (response) =>
      response.url().endsWith('/bulk-email/send') && response.request().method() === 'POST',
  );
  await page.getByRole('button', { name: 'Send now' }).click();
  expect((await sent).status()).toBe(201);

  const results = page.getByRole('region', { name: `Results of ${subject}` });
  await expect(results.getByRole('status')).toHaveText(/^Sent 1, failed 0, skipped \d+\.$/);
  await expect(results.getByRole('row').filter({ hasText: DEMO.friend })).toContainText('Sent');

  const history = page.getByRole('table', { name: /bulk emails? sent$/ });
  await expect(history.getByRole('row').filter({ hasText: subject })).toContainText(
    'Grace Holloway',
  );

  const email = await latestEmailTo(DEMO.friend);
  expect(email).toContain(subject);
});
