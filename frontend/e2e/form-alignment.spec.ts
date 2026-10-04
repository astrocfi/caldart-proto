/**
 * A two-column form lines its boxes up row by row: a hint sits under its label, and the
 * box beside a hinted one starts at the same height, while a row where neither field has
 * a hint, and every field on a phone, keeps its box just under its label.  An error hides
 * the hint without taking its line away, so the box does not move as the error comes and
 * goes.
 */
import { expect, test } from '@playwright/test';
import type { Locator, Page } from '@playwright/test';

import { DEMO, signIn } from './helpers';

/** The largest gap, in pixels, a label and its box may have between them without a hint. */
const LABEL_GAP_MAX = 8;

/** The pixels between the bottom of the label `label` names and the top of its box. */
async function labelGap(page: Page, label: string): Promise<number> {
  const caption = page
    .locator('label.field__label')
    .filter({ hasText: new RegExp(`^${label}\\*?$`) });
  const captionBounds = await caption.boundingBox();
  if (captionBounds === null) throw new Error(`The label ${label} is not on screen.`);
  return (await top(box(page, label))) - (captionBounds.y + captionBounds.height);
}

/** The top edge of `box`, in pixels. */
async function top(box: Locator): Promise<number> {
  const bounds = await box.boundingBox();
  if (bounds === null) throw new Error('The box is not on screen.');
  return bounds.y;
}

/** Each pair is two boxes the profile form draws side by side, the first with a hint. */
const PROFILE_ROWS: readonly (readonly [string, string])[] = [
  ['Phone', 'Alternate phone'],
  ['ZIP code', 'California county'],
  ['DART', 'Air Care Alliance number'],
];

/** The labeled box `label` names on `page`; a required field's label ends in a star. */
function box(page: Page, label: string): Locator {
  return page.getByLabel(new RegExp(`^${label}\\*?$`));
}

for (const width of [1920, 820]) {
  test(`the profile form's boxes line up row by row at ${width} px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await signIn(page, DEMO.member);
    await page.goto('portal/profile');
    await expect(box(page, 'Phone')).toBeVisible();

    for (const [hinted, plain] of PROFILE_ROWS) {
      expect(await top(box(page, plain)), `${hinted} beside ${plain}`).toBeCloseTo(
        await top(box(page, hinted)),
        0,
      );
    }
  });
}

test('a box stays put while an error replaces its hint', async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1000 });
  await signIn(page, DEMO.member);
  await page.goto('portal/profile');
  const zip = box(page, 'ZIP code');
  await expect(zip).toBeVisible();
  const before = await top(zip);

  await zip.fill('950');
  await zip.blur();
  await expect(page.getByText('Use a 5-digit ZIP code, such as 95035.')).toBeVisible();

  expect(await top(zip)).toBeCloseTo(before, 0);
});

for (const width of [1920, 390]) {
  test(`a field with no hint keeps its box under its label at ${width} px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await signIn(page, DEMO.member);
    await page.goto('portal/profile');
    await expect(box(page, 'City')).toBeVisible();

    for (const label of ['City', 'Address line 2', 'Emergency contact']) {
      expect(await labelGap(page, label), label).toBeLessThanOrEqual(LABEL_GAP_MAX);
    }
  });
}
