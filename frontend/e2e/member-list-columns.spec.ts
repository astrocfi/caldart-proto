/**
 * The member list's table follows its column chooser at a laptop's width, and the
 * Columns panel stays on a phone's screen.
 *
 * jsdom lays nothing out, so whether a ticked column survives the table's fitting to a
 * real width is checked here, in a browser.
 */
import { expect, test } from '@playwright/test';

import { DEMO, signIn } from './helpers';

test('a column ticked in the chooser shows in the table on a laptop', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await signIn(page, DEMO.accountadmin);
  await page.goto('portal/admin/members');
  const table = page.getByRole('table');
  await expect(table.getByRole('columnheader', { name: 'Medical expires' })).toBeVisible();
  await expect(table.getByRole('columnheader', { name: 'City' })).toHaveCount(0);

  await page.getByRole('button', { name: 'Columns', exact: true }).click();
  await page.getByRole('checkbox', { name: 'City' }).check();
  await page.keyboard.press('Escape');

  await expect(table.getByRole('columnheader', { name: 'City' })).toHaveCount(1);
});

test('the Columns panel opens within a phone screen', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await signIn(page, DEMO.accountadmin);
  await page.goto('portal/admin/members');

  await page.getByRole('button', { name: 'Columns', exact: true }).click();
  const panel = page.getByRole('group', { name: 'Columns in the table and the download' });
  const box = await panel.boundingBox();
  expect(box).not.toBeNull();
  expect(box?.x ?? -1).toBeGreaterThanOrEqual(0);
  expect((box?.x ?? 0) + (box?.width ?? 0)).toBeLessThanOrEqual(390);
});
