/**
 * A bulk email written in the rich text editor: bold words, a link, a recipient
 * field, and an uploaded image, previewed as the first person receives it, then sent
 * by the background sender, which the system administrator runs from the Scheduled
 * page.
 *
 * `make e2e` runs with `DEBUG` off, so Django does not serve `/media/` and the image
 * itself never loads; the spec checks the address the email links it by instead.
 * The batch is the holders of the management role, which the seed gives to one demo
 * account.
 */
import { expect, test } from '@playwright/test';

import { DEMO, latestEmailTo, signIn } from './helpers';

/** A one-pixel PNG, the smallest image the upload accepts. */
const PIXEL_PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
  'base64',
);

/** The address the email links an uploaded image by. */
const IMAGE_SRC =
  /<img src="https?:\/\/[^"]+\/media\/bulk-email\/[0-9a-f]{32}\.png" alt="A blue square"/;

test('CalDART management writes a formatted email with an image, previews it, and sends it', async ({
  page,
}) => {
  const subject = `Fly-in news ${Date.now().toString(36)}`;

  await signIn(page, DEMO.management);
  await page
    .getByRole('navigation', { name: 'Portal sections' })
    .getByRole('link', { name: 'Compose' })
    .click();
  await expect(page).toHaveURL(/\/portal\/bulk-email\/compose\/\d+$/);

  const filters = page.getByRole('search', { name: 'Choose people to add' });
  await filters.getByLabel('Role').selectOption('management');
  await page.getByRole('button', { name: 'Add to batch' }).click();
  await expect(page.getByText(/^Added \d+ (person|people)[.;]/)).toBeVisible();

  await page.getByRole('textbox', { name: /^Subject/ }).fill(subject);
  const toolbar = page.getByRole('group', { name: 'Message formatting' });
  const message = page.getByRole('textbox', { name: 'Message' });
  // Each keystroke waits for the editor to hold the focus: a toolbar command hands it
  // back on the next frame, after a panel closes.
  const typeInMessage = async (keys: string): Promise<void> => {
    await expect(message).toBeFocused();
    await page.keyboard.type(keys);
  };
  await message.click();
  await toolbar.getByRole('button', { name: 'Bold' }).click();
  await typeInMessage('Fly-in on Saturday');
  await toolbar.getByRole('button', { name: 'Bold' }).click();
  await typeInMessage(' at Livermore. Details: ');
  await toolbar.getByRole('button', { name: 'Link' }).click();
  await page.getByLabel('Web or email address').fill('caldart.org/events');
  await page.getByRole('button', { name: 'Add link' }).click();
  await expect(message).toBeFocused();
  await page.keyboard.press('Enter');
  await typeInMessage('This copy went to ');
  await toolbar.getByRole('button', { name: 'Insert field' }).click();
  await page.getByRole('button', { name: /^Email address/ }).click();
  await typeInMessage('.');

  await page.getByLabel('Choose an image').setInputFiles({
    name: 'square.png',
    mimeType: 'image/png',
    buffer: PIXEL_PNG,
  });
  await expect(page.getByText('square.png is uploaded.')).toBeVisible();
  await page.getByLabel(/^Describe the image/).fill('A blue square');
  await page.getByRole('button', { name: 'Put image in' }).click();
  await expect(page.getByText('Saved', { exact: true })).toBeVisible();

  // The preview fills in the first person's own address, and keeps the formatting.
  const preview = page.getByRole('region', { name: 'Preview' });
  await expect(preview.getByText(/^Previewing as .+ \(1 of \d+\)$/)).toBeVisible();
  const frame = preview.locator('iframe');
  await expect(frame).toHaveAttribute('sandbox', '');
  await expect
    .poll(async () => (await frame.getAttribute('srcdoc')) ?? '')
    .toContain(`This copy went to ${DEMO.management}.`);
  const html = (await frame.getAttribute('srcdoc')) ?? '';
  expect(html).toContain('<strong>Fly-in on Saturday</strong>');
  expect(html).toContain('<a href="https://caldart.org/events">https://caldart.org/events</a>');
  expect(html).toMatch(IMAGE_SRC);

  await page.getByRole('button', { name: /^Send to \d+ (person|people)$/ }).click();
  const confirm = page.getByRole('region', { name: 'Confirm sending' });
  await confirm.getByRole('button', { name: 'Send now' }).click();
  await expect(page.getByRole('region', { name: 'Waiting to send' })).toBeVisible();

  await page.context().clearCookies();
  await signIn(page, DEMO.sysadmin);
  await page.goto('portal/system/scheduled');
  const sender = page
    .locator('section')
    .filter({ has: page.getByRole('heading', { name: 'Bulk email sender' }) });
  await sender.getByRole('button', { name: 'Run the bulk email sender now' }).click();
  await expect(sender.getByRole('row').filter({ hasText: DEMO.management })).toContainText('Sent');

  const email = await latestEmailTo(DEMO.management);
  expect(email).toContain(subject);
  expect(email).toContain('Fly-in on Saturday at Livermore. Details: https://caldart.org/events');
  expect(email).toContain(`This copy went to ${DEMO.management}.`);
  expect(email).toContain('<strong>Fly-in on Saturday</strong>');
  expect(email).toMatch(IMAGE_SRC);
});
