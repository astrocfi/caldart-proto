/**
 * My profile's Save row sticks to the foot of the window once anything changes; on a
 * phone, a Tab walk through the form must never leave the focused field behind it.
 */
import { expect, test } from '@playwright/test';

import { DEMO, signIn } from './helpers';

test.use({ viewport: { width: 390, height: 844 } });

test('the stuck Save row never covers the field with the focus', async ({ page }) => {
  await signIn(page, DEMO.member);
  await page.goto('portal/profile');
  const firstName = page.getByRole('textbox', { name: 'First name', exact: true });
  await firstName.fill('Marta');
  await firstName.press('End');
  await firstName.type('x');

  const row = page.locator('.profile-form__actions[data-dirty="true"]');
  await expect(row).toBeVisible();

  for (let step = 0; step < 14; step += 1) {
    await page.keyboard.press('Tab');
    // The window may still be scrolling the field into place, so ask until it settles.
    await expect
      .poll(
        () =>
          page.evaluate(() => {
            const active = document.activeElement;
            const bar = document.querySelector('.profile-form__actions[data-dirty="true"]');
            if (active === null || bar === null || bar.contains(active)) return 0;
            if (active.closest('.profile-form') === null) return 0;
            const field = active.getBoundingClientRect();
            const stuck = bar.getBoundingClientRect();
            return Math.max(0, Math.round(field.bottom - stuck.top));
          }),
        { message: `focus step ${step + 1}` },
      )
      .toBe(0);
  }
});
