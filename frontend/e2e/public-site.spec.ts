/**
 * The public site's navigation bar, which is CSS and markup with no script
 * behind it — so the browser is the only place its behavior can be checked.
 */
import { expect, test } from '@playwright/test';

const SECTION_MENU = '.navbar__menu';

test('the section drop-down is closed until the pointer is over its section', async ({ page }) => {
  await page.goto('/');
  const menu = page.locator(SECTION_MENU).first();
  const about = page.getByRole('navigation', { name: 'Main' }).getByRole('link', {
    name: 'About Us',
    exact: true,
  });

  await expect(menu).toBeHidden();

  await about.hover();
  await expect(menu).toBeVisible();
  await expect(menu.getByRole('link', { name: 'Sponsors' })).toBeVisible();

  // Anywhere else on the page, and it is gone again.
  await page.mouse.move(10, 600);
  await expect(menu).toBeHidden();
});

test('the bar opens with Home and offers one way to join', async ({ page }) => {
  await page.goto('/');
  const bar = page.getByRole('navigation', { name: 'Main' });

  const titles = await bar.getByRole('link').allInnerTexts();
  expect(titles[0]).toBe('Home');
  expect(titles.filter((title) => title.startsWith('Join'))).toEqual(['Join CalDART']);
});
