import { describe, expect, it } from 'vitest';

import { categoryLine } from './categories';

describe('categoryLine', () => {
  it.each([
    { category: 'helicopter', airworthiness: 'standard', line: 'Helicopter · Standard' },
    { category: 'weight_shift', airworthiness: '', line: 'Weight-shift control' },
    { category: '', airworthiness: 'standard', line: 'Category not recorded · Standard' },
    { category: '', airworthiness: '', line: 'Category not recorded' },
  ] as const)('reads $category and $airworthiness as "$line"', ({ line, ...aircraft }) => {
    expect(categoryLine(aircraft)).toBe(line);
  });
});
