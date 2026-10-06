/**
 * What only a laid-out page can show: a press that lands where it was aimed, a status
 * read whole, a row of tabs on one line, and an error that takes its hint's line.
 *
 * jsdom lays nothing out, so these run in a browser at the widths the portal is
 * checked at.
 */
import { expect, test } from '@playwright/test';
import type { Locator, Page } from '@playwright/test';

import { DEMO, signIn } from './helpers';

/** The widths the portal is checked at: a desktop, a tablet, and a phone. */
const DESKTOP = { width: 1920, height: 1080 };
const TABLET = { width: 820, height: 1180 };
const PHONE = { width: 390, height: 844 };

/** The Change password screen's second box, which carries a hint, and not the third. */
const NEW_PASSWORD = /^New password/;

/** The pixels between the bottom of a field's label and the top of its box. */
async function labelToBox(page: Page, label: RegExp): Promise<number> {
  const box = await page.getByLabel(label).boundingBox();
  const caption = await page.locator('label', { hasText: label }).first().boundingBox();
  if (box === null || caption === null) throw new Error(`${label} is not laid out`);
  return box.y - (caption.y + caption.height);
}

/** Whether `cell` shows all it holds, with nothing cut off at its right edge. */
async function isWhole(cell: Locator): Promise<boolean> {
  return cell.evaluate((element) => element.scrollWidth <= element.clientWidth + 1);
}

test('Cancel closes the add-aircraft form on its first press', async ({ page }) => {
  await page.setViewportSize(DESKTOP);
  await signIn(page, DEMO.member);
  await page.goto('portal/profile/aircraft');
  await page.getByRole('button', { name: 'Add a new aircraft' }).click();
  await expect(page.getByRole('combobox', { name: /^N-number/ })).toBeFocused();

  await page.getByRole('button', { name: 'Cancel' }).click();

  await expect(page.getByRole('button', { name: 'Add a new aircraft' })).toBeVisible();
});

test('Cancel closes the add-aircraft form on its first press after typing', async ({ page }) => {
  await page.setViewportSize(DESKTOP);
  await signIn(page, DEMO.member);
  await page.goto('portal/profile/aircraft');
  await page.getByRole('button', { name: 'Add a new aircraft' }).click();
  await page.getByRole('textbox', { name: 'Year' }).fill('19');

  await page.getByRole('button', { name: 'Cancel' }).click();

  await expect(page.getByRole('button', { name: 'Add a new aircraft' })).toBeVisible();
});

for (const size of [DESKTOP, TABLET]) {
  test(`every renewal status reads whole at ${size.width}`, async ({ page }) => {
    await page.setViewportSize(size);
    await signIn(page, DEMO.accountadmin);
    await page.goto('portal/admin/payments/renewals');
    const statuses = page.locator('tbody .status');
    await expect(statuses.first()).toBeVisible();

    const cut = [];
    for (const status of await statuses.all()) {
      if (!(await isWhole(status.locator('xpath=ancestor::td[1]')))) {
        cut.push(await status.textContent());
      }
    }
    expect(cut).toEqual([]);
  });
}

test('the member record keeps its tabs on one line on a phone', async ({ page }) => {
  await page.setViewportSize(PHONE);
  await signIn(page, DEMO.accountadmin);
  await page.goto('portal/admin/members');
  await page.getByRole('table').getByRole('link').first().click();
  const tabs = page.getByRole('tablist', { name: 'Member record sections' });
  const first = await tabs.getByRole('tab').first().boundingBox();
  const last = await tabs.getByRole('tab').last().boundingBox();

  expect(last?.y).toBe(first?.y);
});

test('the finance tabs stay on one line on a phone, the current one in view', async ({ page }) => {
  await page.setViewportSize(PHONE);
  await signIn(page, DEMO.treasurer);
  await page.goto('portal/admin/payments/reconciliation');
  const bar = page.getByRole('navigation', { name: 'Accounting sections' });
  const current = bar.getByRole('link', { name: 'Reconciliation' });

  await expect(current).toBeInViewport();
  const tops = await bar
    .getByRole('link')
    .evaluateAll((links) => links.map((link) => link.getBoundingClientRect().top));
  expect(new Set(tops).size).toBe(1);
});

test('an error on Change password takes its hint line, leaving no gap', async ({ page }) => {
  await page.setViewportSize(DESKTOP);
  await signIn(page, DEMO.member);
  await page.goto('portal/change-password');
  const before = await labelToBox(page, NEW_PASSWORD);

  await page.getByRole('button', { name: 'Change password' }).click();
  await expect(page.getByLabel(NEW_PASSWORD)).toHaveAttribute('aria-invalid', 'true');

  expect(await labelToBox(page, NEW_PASSWORD)).toBeLessThan(before);
});

test("the dashboard's recent payments read their For cells whole at 1920", async ({ page }) => {
  await page.setViewportSize(DESKTOP);
  await signIn(page, DEMO.member);
  await page.goto('portal/');
  const table = page.getByRole('table', { name: 'Your most recent payments' });
  await expect(table.locator('tbody tr').first()).toBeVisible();

  const cut = [];
  for (const cell of await table.locator('tbody tr td:nth-child(2)').all()) {
    if (!(await isWhole(cell))) cut.push(await cell.textContent());
  }
  expect(cut).toEqual([]);
});

test('Shift+Tab never leaves a field under the sticky header on a phone', async ({ page }) => {
  await page.setViewportSize(PHONE);
  await signIn(page, DEMO.member);
  await page.goto('portal/profile');
  const hours = page.getByLabel(/^Total hours/);
  await expect(hours).toBeVisible();
  await hours.focus();
  const bar = await page.locator('.portal__bar').boundingBox();
  if (bar === null) throw new Error('The header is not laid out');

  const hidden = [];
  for (let press = 0; press < 12; press += 1) {
    await page.keyboard.press('Shift+Tab');
    const box = await page.evaluate(() => {
      const focused = document.activeElement;
      if (!(focused instanceof HTMLElement) || focused.closest('.portal__bar') !== null) {
        return null;
      }
      const rect = focused.getBoundingClientRect();
      return { top: rect.top, name: focused.getAttribute('name') ?? focused.id };
    });
    if (box !== null && box.top < bar.y + bar.height) hidden.push(box.name);
  }
  expect(hidden).toEqual([]);
});

for (const size of [DESKTOP, TABLET]) {
  test(`New DART refused empty leaves no blank band above its boxes at ${size.width}`, async ({
    page,
  }) => {
    await page.setViewportSize(size);
    await signIn(page, DEMO.accountadmin);
    await page.goto('portal/admin/darts');
    await page.getByRole('button', { name: 'New DART' }).click();
    const name = page.getByRole('textbox', { name: /^Name/ }).first();
    const airports = page.getByRole('textbox', { name: /^Airports/ });

    await page.getByRole('button', { name: 'Add DART' }).click();
    await expect(name).toHaveAttribute('aria-invalid', 'true');
    await expect(airports).toHaveAttribute('aria-invalid', 'true');

    const gaps = [];
    for (const [box, label] of [
      [name, 'Name'],
      [airports, 'Airports'],
    ] as const) {
      const field = box.locator('xpath=ancestor::div[contains(@class, "field")][1]');
      const caption = await field.locator('.field__label').boundingBox();
      const drawn = await box.boundingBox();
      if (caption === null || drawn === null) throw new Error(`${label} is not laid out`);
      gaps.push(drawn.y - (caption.y + caption.height));
    }
    // The label's own margin, and no hint row held open above either box.
    expect(gaps.every((gap) => gap < 10)).toBe(true);
    const [left, right] = [await name.boundingBox(), await airports.boundingBox()];
    expect(Math.abs((left?.y ?? 0) - (right?.y ?? 1))).toBeLessThan(1);
  });
}
