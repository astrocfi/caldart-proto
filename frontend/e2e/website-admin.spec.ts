/**
 * Flow E (PLAN §1): a website administrator adds, edits and deletes a page in
 * the Wagtail admin — holding the `website_admin` role alone, not superuser
 * rights (PLAN §4.6).
 *
 * The page really is published, so the spec checks the public site between
 * each step rather than trusting the admin's own success messages.
 */
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

import { DEMO, DEMO_PASSWORD, signInToWagtail } from './helpers';

const stamp = Date.now().toString(36);
const TITLE = `Exercise notice ${stamp}`;
const EDITED = `${TITLE} updated`;
const SLUG = `exercise-notice-${stamp}`;

/** Wagtail keeps Publish in the editor's "More actions" dropdown. */
async function publish(page: Page): Promise<void> {
  await page.getByRole('button', { name: 'More actions' }).click();
  const button = page.getByRole('button', { name: 'Publish', exact: true });
  await expect(button).toBeVisible();
  await button.click();
  await page.waitForLoadState('networkidle');
}

test('a website administrator creates, edits and deletes a page', async ({ page }) => {
  await signInToWagtail(page, DEMO.webAdmin);

  // Into the page tree, and add a child of Home.  In the explorer a page's
  // title links to its editor, so take the id from there and open the
  // children of Home explicitly.
  await page.goto('/admin/pages/');
  const homeHref = await page
    .getByRole('link', { name: 'Home', exact: true })
    .first()
    .getAttribute('href');
  const homeId = (homeHref ?? '').split('/').filter(Boolean)[2];
  const homeUrl = `/admin/pages/${homeId}/`;
  await page.goto(homeUrl);
  await page.getByRole('link', { name: 'Add child page' }).first().click();
  await page.getByRole('link', { name: 'Standard page', exact: true }).click();

  // Wagtail's own form: stable Django field ids rather than its chrome.  The
  // slug is set by hand rather than left to the title's auto-fill, so the spec
  // knows the public URL it is about to check.
  await page.locator('#id_title').fill(TITLE);
  await page.locator('#id_intro').fill('A notice added by the end-to-end test.');
  await page.getByRole('tab', { name: 'Promote' }).click();
  await page.locator('#id_slug').fill(SLUG);
  await publish(page);
  await expect(page.getByText(/created and published/)).toBeVisible();

  // It is live on the public site.
  const created = await page.goto(`/${SLUG}/`);
  expect(created?.status()).toBe(200);
  await expect(page.getByRole('heading', { level: 1, name: TITLE })).toBeVisible();

  // Edit it from the explorer.
  await page.goto(homeUrl);
  await page.getByRole('link', { name: TITLE }).first().click();
  await expect(page.locator('#id_title')).toHaveValue(TITLE);
  const pageId = new URL(page.url()).pathname.split('/').filter(Boolean)[2];
  await page.locator('#id_title').fill(EDITED);
  await publish(page);

  const edited = await page.goto(`/${SLUG}/`);
  expect(edited?.status()).toBe(200);
  await expect(page.getByRole('heading', { level: 1, name: EDITED })).toBeVisible();

  // Delete it.
  await page.goto(`/admin/pages/${pageId}/delete/`);
  await page.getByRole('button', { name: /^Yes, delete it$/ }).click();
  await page.waitForLoadState('networkidle');

  const gone = await page.goto(`/${SLUG}/`);
  expect(gone?.status()).toBe(404);
});

test('a plain member cannot open the Wagtail admin', async ({ page }) => {
  await page.goto('/admin/login/');
  await page.getByLabel(/email/i).fill(DEMO.member);
  await page.getByLabel(/password/i).fill(DEMO_PASSWORD);
  await page.getByRole('button', { name: /sign in/i }).click();

  // Wagtail refuses the sign-in rather than showing the dashboard.
  await expect(page).toHaveURL(/\/admin\/login/);
});
