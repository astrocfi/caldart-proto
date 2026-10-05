/**
 * A phone box refuses a letter without moving the caret, so the next digit lands where
 * the typist put the caret.
 */
import { expect, test } from '@playwright/test';

import { DEMO, signIn } from './helpers';

test.use({ viewport: { width: 1920, height: 1080 } });

test('a refused letter typed mid-number leaves the next digit at the caret', async ({ page }) => {
  await signIn(page, DEMO.member);
  await page.goto('portal/profile');
  const phone = page.getByRole('textbox', { name: 'Phone', exact: true });
  await phone.fill('4155550100');
  await expect(phone).toHaveValue('415-555-0100');

  await phone.evaluate((input: HTMLInputElement) => input.setSelectionRange(6, 6));
  await phone.press('x');
  await phone.press('7');

  await expect(phone).toHaveValue('415-557-5010');
});
